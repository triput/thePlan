"""Offline ASGI harness for independent domain-auth + ordered-result proofs.

Test-only. Mirrors production middleware add-order (including CoveringIngress)
and the real calendar router without create_app lifespan/bootstrap and without
live DB / provider / native I/O.

Implementation-snapshot binding (verified — no CoveringReleaseBinding.dispatch):
- Installs only
  CoveringReleaseBinding(parent_factory, session_factory,
  domain_ports=CoveringDomainPorts(token, locks, apply)).
- HTTP worker calls run_bounded_domain directly; harness never installs a
  dispatch callable (field absent in this snapshot).
- Real authenticate / credential policy / ownership preflight run against
  FakeSession. Provider/native/DB sockets are replaced; auth helpers are not
  monkeypatched.
- PortRecorder tags AUTH admissions as auth_identity vs auth_preflight
  (harness-only purpose labels — not a production seam).

Unbound (default): app.state.covering_release_binding absent -> production
CALENDAR_REFRESH_NOT_CONFIGURED (distinct from OUTCOME_UNKNOWN).
"""

from __future__ import annotations

import json
import os
from base64 import b64encode
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import SESSION_EPOCH_KEY, SESSION_USER_ID_KEY, get_current_user, get_db
from app.api.errors import ApiError, register_exception_handlers
from app.api.middleware import PasswordChangeGateMiddleware
from app.api.middleware.agent_boundary_a import AgentBoundaryAMiddleware
from app.api.middleware.covering_ingress import CoveringIngressMiddleware
from app.api.routes import calendar as calendar_routes
from app.config import get_settings
from app.models import AgentCredential, User, UserSettings
from app.models.calendar import CalendarAccount, CalendarSubscription
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.services.covering_domain_dispatch import (
    CoveringDomainPorts,
    TokenReady,
    TokenRejected,
)
from app.services.covering_http_dispatch import CoveringReleaseBinding
from app.services.covering_parent_adapter import NativeTerminalResult, ParentDriver
from app.services.covering_refresh_import import (
    OUTCOME_FAILED,
    OUTCOME_OK,
    ImportCoveringCacheResult,
)
from app.services.covering_refresh_locks import CoveringUnitLockReceipt
from app.services.covering_role_admission import CoveringRole
from app.services.covering_role_connector import (
    ParentBinding,
    RoleCompletion,
    SessionBinding,
)
from app.services.passwords import hash_password

HARNESS_SESSION_SECRET = "domain-auth-ordered-result-harness-offline-session-secret-v1"
COVERING_PATH = "/api/v1/calendar/covering-refresh"
OFF_ROUTE_PATH = "/api/v1/harness/off-route-control"
WINDOW_START = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc)

PRODUCTION_MIDDLEWARE_ADD_ORDER: tuple[str, ...] = (
    "PasswordChangeGateMiddleware",
    "AgentBoundaryAMiddleware",
    "SessionMiddleware",
    "CoveringIngressMiddleware",
    "CORSMiddleware",
)
PRODUCTION_COVERING_METHOD_PATHS: frozenset[tuple[str, str]] = frozenset(
    {("POST", "/api/v1/calendar/covering-refresh")}
)

REQUEST_BUDGET_TOTAL_SECONDS = 240
REQUEST_BUDGET_ORDINARY_SECONDS = 210
REQUEST_BUDGET_CLEANUP_SECONDS = 30
BODY_LIMIT_BYTES = 16 * 1024

PENDING_NATIVE_PARENT_REASON = (
    "PENDING INTEGRATION (not proof): reviewed native parent_factory / "
    "PostgreSQL driver still unbound — harness FakeParentDriver acknowledges "
    "terminals without native sockets (see UNSOUND-SEAMS.md)"
)

PENDING_ASSESSMENT_FRESHNESS_REASON = (
    "PENDING INTEGRATION (not proof): full ASSESSMENT freshness/readiness SQL "
    "surface not faked — harness defaults to classified ApiError so domain "
    "sanitizes assessment_error without claiming readiness parity"
)


class ControllableClock:
    """Monotonic stand-in for CoveringIngressMiddleware / CoveringRequestBudget."""

    def __init__(self, value: float = 0.0) -> None:
        self.value = float(value)

    def __call__(self) -> float:
        return self.value


def _forbid_live_session_local() -> None:
    raise RuntimeError(
        "domain-auth harness: live SessionLocal is unbound/forbidden "
        "(fail-closed; no DB endpoint profile)"
    )


class _FakeResult:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def one_or_none(self) -> tuple[Any, ...] | None:
        return self._row

    def one(self) -> tuple[Any, ...]:
        if self._row is None:
            raise RuntimeError("domain-auth harness: FakeResult.one with no row")
        return self._row


class _FakeQuery:
    """Minimal SQLAlchemy-shaped query surface for real auth + preflight."""

    def __init__(self, store: "HarnessIdentityStore", entities: tuple[Any, ...]) -> None:
        self._store = store
        self._entities = entities
        self._id_eq: UUID | None = None
        self._owner_id_eq: UUID | None = None
        self._ids_in: set[UUID] | None = None
        self._require_password_hash = False
        self._limit: int | None = None
        self._joined_account = False

    def options(self, *_a: Any, **_k: Any) -> "_FakeQuery":
        return self

    def join(self, *args: Any, **_k: Any) -> "_FakeQuery":
        target = args[0] if args else None
        if target is CalendarAccount or getattr(target, "__name__", "") == "CalendarAccount":
            self._joined_account = True
        return self

    @staticmethod
    def _as_uuid_set(right: Any) -> set[UUID]:
        values = getattr(right, "value", None)
        if values is None and hasattr(right, "clauses"):
            values = [getattr(c, "value", c) for c in right.clauses]
        if values is None:
            values = right
        try:
            seq = list(values)
        except TypeError:
            seq = [values]
        parsed: set[UUID] = set()
        for item in seq:
            raw = getattr(item, "value", item)
            try:
                parsed.add(raw if isinstance(raw, UUID) else UUID(str(raw)))
            except (TypeError, ValueError):
                continue
        return parsed

    def _absorb_criterion(self, crit: Any) -> None:
        type_name = type(crit).__name__
        if type_name in {"BooleanClauseList", "and_", "And"}:
            for child in list(getattr(crit, "clauses", []) or []):
                self._absorb_criterion(child)
            return

        clause = str(crit)
        left = getattr(crit, "left", None)
        right = getattr(crit, "right", None)
        element = getattr(crit, "element", None)
        key = getattr(left, "key", None) or getattr(element, "key", None)
        op = getattr(crit, "operator", None)
        op_name = getattr(op, "__name__", "") if op is not None else ""
        looks_like_in = (
            op_name in {"in_op", "in_ops"}
            or type_name == "In"
            or (type_name == "BinaryExpression" and " IN " in f" {clause.upper()} ")
        )

        if key == "id" and right is not None:
            if looks_like_in:
                parsed = self._as_uuid_set(right)
                if parsed:
                    self._ids_in = parsed
            else:
                value = getattr(right, "value", right)
                try:
                    self._id_eq = value if isinstance(value, UUID) else UUID(str(value))
                except (TypeError, ValueError):
                    self._id_eq = None

        if key == "owner_id" and right is not None:
            value = getattr(right, "value", right)
            try:
                self._owner_id_eq = value if isinstance(value, UUID) else UUID(str(value))
            except (TypeError, ValueError):
                self._owner_id_eq = None

        if "password_hash" in clause and "IS NOT NULL" in clause.upper():
            self._require_password_hash = True
        elif key == "password_hash":
            self._require_password_hash = True

        # Last-resort UUID harvest from stringified IN (...) clauses.
        if self._ids_in is None and " IN " in clause.upper():
            import re

            found = re.findall(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                clause,
            )
            if found:
                self._ids_in = {UUID(item) for item in found}

    def filter(self, *criteria: Any) -> "_FakeQuery":
        for crit in criteria:
            self._absorb_criterion(crit)
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    def order_by(self, *_a: Any, **_k: Any) -> "_FakeQuery":
        return self

    def with_for_update(self, *_a: Any, **_k: Any) -> "_FakeQuery":
        return self

    def populate_existing(self) -> "_FakeQuery":
        return self

    def _entity_is_user_id_only(self) -> bool:
        if len(self._entities) != 1:
            return False
        ent = self._entities[0]
        return getattr(ent, "key", None) == "id" and getattr(
            getattr(ent, "class_", None), "__name__", ""
        ) == "User"

    def _entity_is_user(self) -> bool:
        if len(self._entities) != 1:
            return False
        ent = self._entities[0]
        return ent is User or getattr(ent, "__name__", None) == "User"

    def _entity_is_user_settings(self) -> bool:
        if len(self._entities) != 1:
            return False
        ent = self._entities[0]
        return ent is UserSettings or getattr(ent, "__name__", None) == "UserSettings"

    def _entity_is_sub_account_pair(self) -> bool:
        if len(self._entities) != 2:
            return False
        names = {
            getattr(e, "__name__", None) or getattr(getattr(e, "class_", None), "__name__", None)
            for e in self._entities
        }
        return names == {"CalendarSubscription", "CalendarAccount"}

    def one_or_none(self) -> Any:
        rows = self.all()
        if not rows:
            return None
        return rows[0]

    def one(self) -> Any:
        rows = self.all()
        if len(rows) != 1:
            raise RuntimeError(
                f"domain-auth harness FakeQuery.one expected 1 row, got {len(rows)}"
            )
        return rows[0]

    def all(self) -> list[Any]:
        if self._entity_is_user_settings():
            settings = [
                u.settings for u in self._store.users.values() if u.settings is not None
            ]
            if self._owner_id_eq is not None:
                settings = [s for s in settings if s.owner_id == self._owner_id_eq]
            if self._limit is not None:
                settings = settings[: self._limit]
            return settings

        if self._entity_is_sub_account_pair() or (
            len(self._entities) == 2 and self._joined_account
        ):
            rows: list[tuple[CalendarSubscription, CalendarAccount]] = []
            for sub in self._store.subscriptions.values():
                if self._ids_in is not None and sub.id not in self._ids_in:
                    continue
                if self._id_eq is not None and sub.id != self._id_eq:
                    continue
                account = self._store.accounts.get(sub.calendar_account_id)
                if account is None:
                    continue
                rows.append((sub, account))
            if self._limit is not None:
                rows = rows[: self._limit]
            return rows

        users = list(self._store.users.values())
        if self._require_password_hash:
            users = [u for u in users if u.password_hash]
        if self._id_eq is not None:
            users = [u for u in users if u.id == self._id_eq]
        if self._limit is not None:
            users = users[: self._limit]
        if self._entity_is_user_id_only():
            return [(u.id,) for u in users]
        if self._entity_is_user():
            return users
        return []


class FakeSession:
    """Fail-closed session replacing physical DB for AUTH/TELEMETRY/TOKEN/ASSESSMENT."""

    def __init__(
        self,
        store: "HarnessIdentityStore",
        *,
        role: CoveringRole | None = None,
        ports: "CoveringPortBundle | None" = None,
    ) -> None:
        self._store = store
        self._role = role
        self._ports = ports
        self.info: dict[str, Any] = {}
        self.new: set[Any] = set()
        self.dirty: set[Any] = set()
        self.deleted: set[Any] = set()
        self.identity_map: dict[Any, Any] = {}
        self._telemetry_updates = 0

    def expire(self, *_a: Any, **_k: Any) -> None:
        return None

    def expunge(self, *_a: Any, **_k: Any) -> None:
        return None

    def get(self, model: type[Any], ident: Any) -> Any:
        if model is User:
            return self._store.users.get(ident)
        if model is AgentCredential:
            return self._store.credentials.get(ident)
        if model is CalendarAccount:
            return self._store.accounts.get(ident)
        if model is CalendarSubscription:
            return self._store.subscriptions.get(ident)
        return None

    def query(self, *entities: Any) -> _FakeQuery:
        # ASSESSMENT: allow UserSettings for lock_owner_scheduling, then refuse
        # further ORM reads with a classified ApiError so domain sanitizes
        # assessment_error (full freshness SQL remains unbound — see seams doc).
        if (
            self._role is CoveringRole.ASSESSMENT
            and (self._ports is None or self._ports.assessment_mode == "api_error")
        ):
            only = entities[0] if len(entities) == 1 else None
            is_settings = only is UserSettings or getattr(only, "__name__", None) == "UserSettings"
            if not is_settings:
                raise ApiError(
                    503,
                    "harness assessment surface unbound",
                    "HARNESS_ASSESSMENT_UNBOUND",
                )
        return _FakeQuery(self._store, entities)

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
        params = params or {}
        sql = str(statement).lower()
        if "pg_advisory_xact_lock" in sql:
            return _FakeResult((True,))
        if "from agent_credentials" in sql and "revoked_at" in sql:
            cred_id = params.get("id")
            cred = self._store.credentials.get(cred_id) if cred_id else None
            if cred is None:
                return _FakeResult(None)
            return _FakeResult((cred.revoked_at is not None, cred.owner_id))
        if "from users" in sql and "is_disabled" in sql:
            uid = params.get("uid")
            user = self._store.users.get(uid) if uid else None
            if user is None:
                return _FakeResult(None)
            settings = self._store.settings_for(user.id)
            allow = bool(settings.allow_agent_cli_access) if settings else False
            return _FakeResult((bool(user.is_disabled), allow))
        if "update agent_credentials" in sql and "last_used_at" in sql:
            # TELEMETRY role owns this write unit; SessionLocal path stays forbidden.
            if self._role is not CoveringRole.TELEMETRY:
                raise RuntimeError(
                    "domain-auth harness: agent_credentials last_used UPDATE "
                    "outside TELEMETRY role is forbidden"
                )
            cred_id = params.get("id")
            cred = self._store.credentials.get(cred_id) if cred_id else None
            if cred is None or cred.revoked_at is not None:
                return _FakeResult((0,))
            self._telemetry_updates += 1
            if self._ports is not None:
                self._ports.recorder.telemetry_sql_updates += 1
                if self._ports.advance_clock_on_telemetry is not None:
                    self._ports.clock.value = float(self._ports.advance_clock_on_telemetry)
            return _FakeResult((1,))
        raise RuntimeError(
            f"domain-auth harness FakeSession.execute unbound SQL: {sql[:160]}"
        )

    def close(self) -> None:
        return None

    def commit(self) -> None:
        raise RuntimeError("domain-auth harness: commit forbidden on FakeSession")

    def rollback(self) -> None:
        return None

    def expire_all(self) -> None:
        return None


# Harness-only purpose labels for AUTH role reuse (identity vs ownership/preflight).
# Not production API — mirrors Domain-Review: AUTH identity → retire → (TELEMETRY) →
# fresh AUTH/preflight for ownership/revision.
PURPOSE_AUTH_IDENTITY = "auth_identity"
PURPOSE_AUTH_PREFLIGHT = "auth_preflight"
PURPOSE_TELEMETRY = "telemetry"
PURPOSE_TOKEN = "token"
PURPOSE_PARENT = "parent"
PURPOSE_ASSESSMENT = "assessment"
PURPOSE_RECORDER = "recorder"


@dataclass
class RoleAdmissionRecord:
    role: CoveringRole
    target: object | None
    identity: object
    purpose: str


@dataclass
class PortRecorder:
    """Records role/port use and AUTH purpose order — not a domain dispatcher."""

    role_admissions: list[RoleAdmissionRecord] = field(default_factory=list)
    role_retirements: list[CoveringRole] = field(default_factory=list)
    parent_targets: list[object] = field(default_factory=list)
    parent_lifecycle_events: list[str] = field(default_factory=list)
    token_calls: list[UUID] = field(default_factory=list)
    lock_calls: list[UUID] = field(default_factory=list)
    apply_calls: list[UUID] = field(default_factory=list)
    telemetry_role_count: int = 0
    telemetry_sql_updates: int = 0
    overlapping_role_attempts: int = 0
    role_conservation_violations: int = 0
    session_local_touch_attempts: int = 0
    identity_auth_retired_known: bool = False
    _active_roles: int = 0

    def reset(self) -> None:
        self.role_admissions.clear()
        self.role_retirements.clear()
        self.parent_targets.clear()
        self.parent_lifecycle_events.clear()
        self.token_calls.clear()
        self.lock_calls.clear()
        self.apply_calls.clear()
        self.telemetry_role_count = 0
        self.telemetry_sql_updates = 0
        self.overlapping_role_attempts = 0
        self.role_conservation_violations = 0
        self.session_local_touch_attempts = 0
        self.identity_auth_retired_known = False
        self._active_roles = 0

    @property
    def active_role_count(self) -> int:
        return self._active_roles

    def roles_accounting_sound(self) -> bool:
        """True only when ends match begins — never invent balance from a clamp."""
        return (
            self._active_roles == 0
            and self.role_conservation_violations == 0
            and self.overlapping_role_attempts == 0
        )

    def purpose_sequence(self) -> list[str]:
        return [rec.purpose for rec in self.role_admissions]

    def _purpose_for(self, role: CoveringRole) -> str:
        if role is CoveringRole.AUTH:
            if self.identity_auth_retired_known:
                return PURPOSE_AUTH_PREFLIGHT
            return PURPOSE_AUTH_IDENTITY
        if role is CoveringRole.TELEMETRY:
            return PURPOSE_TELEMETRY
        if role is CoveringRole.TOKEN:
            return PURPOSE_TOKEN
        if role is CoveringRole.PARENT:
            return PURPOSE_PARENT
        if role is CoveringRole.ASSESSMENT:
            return PURPOSE_ASSESSMENT
        if role is CoveringRole.RECORDER:
            return PURPOSE_RECORDER
        return role.value

    def note_begin(self, role: CoveringRole, target: object | None, identity: object) -> None:
        if self._active_roles > 0:
            self.overlapping_role_attempts += 1
        self._active_roles += 1
        purpose = self._purpose_for(role)
        self.role_admissions.append(
            RoleAdmissionRecord(
                role=role, target=target, identity=identity, purpose=purpose
            )
        )
        if role is CoveringRole.TELEMETRY:
            self.telemetry_role_count += 1
        if role is CoveringRole.PARENT:
            self.parent_lifecycle_events.append("begin")

    def note_parent_finish(self, command_tag: str) -> None:
        self.parent_lifecycle_events.append(f"finish:{command_tag}")

    def note_end(
        self,
        role: CoveringRole | None = None,
        *,
        known_retirement: bool = False,
    ) -> None:
        # Unbalanced end is a conservation violation. Do not clamp into success.
        if self._active_roles <= 0:
            self.role_conservation_violations += 1
        else:
            self._active_roles -= 1
        if role is not None:
            self.role_retirements.append(role)
            if role is CoveringRole.PARENT:
                self.parent_lifecycle_events.append(
                    "retire" if known_retirement else "retire_unknown"
                )
        if (
            known_retirement
            and role is CoveringRole.AUTH
            and not self.identity_auth_retired_known
        ):
            # Identity-AUTH known retirement unlocks preflight AUTH tagging and
            # (for Bearer) the TELEMETRY admission window in production policy.
            for rec in reversed(self.role_admissions):
                if rec.role is CoveringRole.AUTH:
                    if rec.purpose == PURPOSE_AUTH_IDENTITY:
                        self.identity_auth_retired_known = True
                    break


@dataclass
class HarnessIdentityStore:
    users: dict[UUID, User] = field(default_factory=dict)
    credentials: dict[UUID, AgentCredential] = field(default_factory=dict)
    plaintext_secrets: dict[UUID, str] = field(default_factory=dict)
    accounts: dict[UUID, CalendarAccount] = field(default_factory=dict)
    subscriptions: dict[UUID, CalendarSubscription] = field(default_factory=dict)

    def settings_for(self, owner_id: UUID) -> UserSettings | None:
        user = self.users.get(owner_id)
        if user is None:
            return None
        return user.settings

    def add_browser_user(
        self,
        *,
        user_id: UUID | None = None,
        session_epoch: int = 1,
        is_disabled: bool = False,
        must_change_password: bool = False,
        allow_agent_cli_access: bool = True,
        password_hash: str | None = "harness-hash",
        scheduling_revision: int = 7,
    ) -> User:
        uid = user_id or uuid4()
        user = User(
            id=uid,
            username=f"harness-{uid.hex[:8]}",
            email=f"{uid.hex[:8]}@harness.local",
            password_hash=password_hash,
            display_name="Harness User",
            is_admin=False,
            is_disabled=is_disabled,
            must_change_password=must_change_password,
            session_epoch=session_epoch,
        )
        settings = UserSettings(
            id=uuid4(),
            owner_id=uid,
            allow_agent_cli_access=allow_agent_cli_access,
            scheduling_revision=scheduling_revision,
        )
        user.settings = settings
        self.users[uid] = user
        return user

    def add_agent_credential(
        self,
        owner: User,
        *,
        credential_id: UUID | None = None,
        revoked: bool = False,
        plaintext: str | None = None,
    ) -> tuple[AgentCredential, str]:
        from app.services.agent_credentials import SECRET_PREFIX

        cid = credential_id or uuid4()
        random_part = "HarnessSecretTokenValue0123456789abcd"
        plain = plaintext or f"{SECRET_PREFIX}{cid.hex}_{random_part}"
        row = AgentCredential(
            id=cid,
            owner_id=owner.id,
            label="harness",
            secret_hash=hash_password(plain),
            revoked_at=datetime.now(timezone.utc) if revoked else None,
        )
        self.credentials[cid] = row
        self.plaintext_secrets[cid] = plain
        return row, plain

    def register_owned_subscription(
        self,
        owner: User,
        subscription_id: UUID | None = None,
        *,
        access_token_enc: str | None = "harness-enc-token",
        account_enabled: bool = True,
        subscription_enabled: bool = True,
    ) -> UUID:
        sid = subscription_id or uuid4()
        account_id = uuid4()
        account = CalendarAccount(
            id=account_id,
            owner_id=owner.id,
            provider=CalendarProvider.google,
            account_email=f"{owner.id.hex[:8]}@cal.harness",
            access_token_enc=access_token_enc,
            is_enabled=account_enabled,
            mirror_blocks=False,
        )
        sub = CalendarSubscription(
            id=sid,
            owner_id=owner.id,
            calendar_account_id=account_id,
            external_calendar_id=f"ext-{sid.hex[:12]}",
            summary="harness-sub",
            role=CalendarSubscriptionRole.primary,
            is_enabled=subscription_enabled,
            coverage_active_generation=0,
        )
        self.accounts[account_id] = account
        self.subscriptions[sid] = sub
        return sid

    def revoke_credential(self, credential_id: UUID) -> None:
        cred = self.credentials[credential_id]
        cred.revoked_at = datetime.now(timezone.utc)


class FakeParentDriver:
    """Synthetic ParentDriver — NOT native PostgreSQL proof (see UNSOUND-SEAMS).

    Records exact PARENT admission pairing: finish tags + one retire note_end
    (including cutoff/abort retire). Clock hooks model ordinary→cleanup boundary
    for deadline-exhaustion fixtures without mutating production code.
    """

    def __init__(self, ports: CoveringPortBundle) -> None:
        self._ports = ports
        self._recorder = ports.recorder
        self._retired = False
        self._finish_acknowledged = False

    def finish(
        self, operation: Any, *, remaining: Callable[[], float]
    ) -> NativeTerminalResult:
        # remaining() must observe the pre-COMMIT ordinary clock (e.g. 209),
        # never a post-apply jump that already exhausted the work window.
        remaining()
        command_tag = operation.command.value
        # RootCommand values are bytes (b"COMMIT"); lifecycle log stays text.
        tag_text = (
            command_tag.decode("ascii")
            if isinstance(command_tag, (bytes, bytearray))
            else str(command_tag)
        )
        self._recorder.note_parent_finish(tag_text)
        self._finish_acknowledged = True
        return NativeTerminalResult(
            operation=operation,
            command_sent=True,
            command_tag=command_tag,
            drained=True,
            idle=True,
        )

    def cut_off_frontend(self) -> bool:
        return True

    def retire(self) -> bool:
        if self._retired:
            return True
        known = self._finish_acknowledged
        # Successful local retirement may spend one cleanup second (209 → 210)
        # after COMMIT acknowledgment — ordinary work already spent to 209.
        if (
            known
            and self._ports.advance_clock_on_first_parent_retire is not None
            and self._ports._parents_completed >= 1
            and self._ports._parent_retire_clock_advances == 0
        ):
            self._ports.clock.value = float(
                self._ports.advance_clock_on_first_parent_retire
            )
            self._ports._parent_retire_clock_advances += 1
        self._retired = True
        self._recorder.note_end(CoveringRole.PARENT, known_retirement=known)
        return True


def _ok_result(subscription_id: UUID, window_start: datetime, window_end: datetime) -> ImportCoveringCacheResult:
    return ImportCoveringCacheResult(
        subscription_id=subscription_id,
        outcome=OUTCOME_OK,
        preflight_code=None,
        preflight_effects=(),
        cause=None,
        upserted=1,
        rollback_required=False,
        commit_unit=True,
        needs_failure_unit=False,
        attempt=None,
        window_effective_start=window_start,
        window_effective_end=window_end,
        window_widened=False,
        window_widen_reason="none",
        coverage_generation_minted=1,
        scheduling_revision_bumped=False,
        scheduling_revision=None,
        provider_identity_list_called=True,
        provider_event_read_attempted=True,
    )


def _failed_result(
    subscription_id: UUID, window_start: datetime, window_end: datetime
) -> ImportCoveringCacheResult:
    return ImportCoveringCacheResult(
        subscription_id=subscription_id,
        outcome=OUTCOME_FAILED,
        preflight_code=None,
        preflight_effects=(),
        cause="covering_provider_read_failed",
        upserted=0,
        rollback_required=True,
        commit_unit=False,
        needs_failure_unit=False,
        attempt=None,
        window_effective_start=window_start,
        window_effective_end=window_end,
        window_widened=False,
        window_widen_reason="none",
        coverage_generation_minted=None,
        scheduling_revision_bumped=False,
        scheduling_revision=None,
        provider_identity_list_called=True,
        provider_event_read_attempted=True,
    )


@dataclass
class CoveringPortBundle:
    """Physical DB/native/provider ports for CoveringReleaseBinding."""

    store: HarnessIdentityStore
    recorder: PortRecorder
    clock: ControllableClock
    # token outcomes: TokenReady | TokenRejected | "api_error" | "bad_type"
    token_script: dict[UUID, Any] = field(default_factory=dict)
    default_token: Any = field(default_factory=lambda: TokenRejected(code="HARNESS_TOKEN_REJECTED"))
    # apply outcomes: "ok" | "failed" | "revoke_credential_then_commit"
    apply_script: dict[UUID, str] = field(default_factory=dict)
    default_apply: str = "ok"
    assessment_mode: str = "api_error"  # or "unbound" (raises RuntimeError → UNKNOWN)
    advance_clock_on_telemetry: float | None = None
    # DA-O5 boundary: spend ordinary work to N before COMMIT (finish still sees
    # remaining>0), then advance to M during successful local PARENT retire.
    advance_ordinary_clock_before_first_commit: float | None = None
    advance_clock_on_first_parent_retire: float | None = None
    revoke_credential_id_on_apply: UUID | None = None
    _parents_completed: int = 0
    _parent_retire_clock_advances: int = 0

    def session_factory(
        self,
        role: CoveringRole,
        target: object | None,
        remaining: Callable[[], float],
    ) -> SessionBinding:
        _ = remaining()
        identity = object()
        self.recorder.note_begin(role, target, identity)
        session = FakeSession(self.store, role=role, ports=self)

        def close_known(cleanup_remaining: Callable[[], float]) -> RoleCompletion:
            _ = cleanup_remaining()
            self.recorder.note_end(role, known_retirement=True)
            return RoleCompletion(identity, True, True, True)

        def quarantine() -> None:
            self.recorder.note_end(role, known_retirement=False)

        return SessionBinding(session, identity, close_known, quarantine)

    def parent_factory(
        self,
        target: object,
        remaining: Callable[[], float],
    ) -> ParentBinding:
        _ = remaining()
        self.recorder.parent_targets.append(target)
        identity = object()
        # Exact PARENT admission — pairs with FakeParentDriver.retire note_end
        # (success or cutoff/abort). Omitting this zeroed-out overlap checks.
        self.recorder.note_begin(CoveringRole.PARENT, target, identity)
        session = FakeSession(self.store, role=CoveringRole.PARENT, ports=self)
        driver: ParentDriver = FakeParentDriver(self)
        return ParentBinding(
            session=session,
            identity=identity,
            root=object(),
            driver=driver,
        )

    def build_domain_ports(self) -> CoveringDomainPorts:
        return CoveringDomainPorts(
            token=self._token,
            locks=self._locks,
            apply=self._apply,
        )

    def _token(self, session: Any, target: Any, live_remaining: Callable[[], float]) -> Any:
        _ = session
        live_remaining()
        self.recorder.token_calls.append(target.subscription_id)
        scripted = self.token_script.get(target.subscription_id, self.default_token)
        if scripted == "api_error":
            raise ApiError(401, "token port api error", "HARNESS_TOKEN_API_ERROR")
        if scripted == "bad_type":
            return object()
        if isinstance(scripted, Exception):
            raise scripted
        return scripted

    @contextmanager
    def _locks(self, session: Any, target: Any, live_remaining: Callable[[], float]) -> Iterator[CoveringUnitLockReceipt]:
        _ = session
        live_remaining()
        self.recorder.lock_calls.append(target.subscription_id)
        yield CoveringUnitLockReceipt(
            owner_id=target.owner_id,
            account_id=target.account_id,
            subscription_id=target.subscription_id,
            account_identity_locked=True,
            _mint=object(),
        )

    def _apply(
        self,
        session: Any,
        target: Any,
        token: Any,
        window: Any,
        receipt: Any,
        adapter: Any,
        now: datetime,
        live_remaining: Callable[[], float],
    ) -> ImportCoveringCacheResult:
        _ = (session, token, receipt, adapter, now)
        live_remaining()
        self.recorder.apply_calls.append(target.subscription_id)
        mode = self.apply_script.get(target.subscription_id, self.default_apply)
        if mode == "revoke_credential_then_commit":
            if self.revoke_credential_id_on_apply is not None:
                self.store.revoke_credential(self.revoke_credential_id_on_apply)
            result = _ok_result(
                target.subscription_id, window.effective_start, window.effective_end
            )
        elif mode == "failed":
            result = _failed_result(
                target.subscription_id, window.effective_start, window.effective_end
            )
        else:
            result = _ok_result(
                target.subscription_id, window.effective_start, window.effective_end
            )
        self._parents_completed += 1
        # Ordinary spend only — must leave work_remaining > 0 for COMMIT finish.
        if (
            self.advance_ordinary_clock_before_first_commit is not None
            and self._parents_completed == 1
        ):
            self.clock.value = float(self.advance_ordinary_clock_before_first_commit)
        return result


@dataclass
class DomainAuthHarness:
    client: TestClient
    store: HarnessIdentityStore
    ports: CoveringPortBundle
    app: FastAPI
    clock: ControllableClock
    binding_installed: bool


def mint_signed_session_cookie(
    *,
    user_id: UUID,
    session_epoch: int,
    secret: str = HARNESS_SESSION_SECRET,
) -> str:
    """Mint a Starlette SessionMiddleware-compatible signed session cookie value."""
    payload = {
        SESSION_USER_ID_KEY: str(user_id),
        SESSION_EPOCH_KEY: int(session_epoch),
    }
    data = b64encode(json.dumps(payload).encode("utf-8"))
    return TimestampSigner(str(secret)).sign(data).decode("utf-8")


def middleware_add_order_names(app: FastAPI) -> list[str]:
    """Middleware class names in add_middleware call order (innermost first)."""
    stored = [middleware.cls.__name__ for middleware in app.user_middleware]
    return list(reversed(stored))


def covering_method_paths(app: FastAPI) -> set[tuple[str, str]]:
    """Set of (METHOD, path) for covering-refresh registrations."""
    found: set[tuple[str, str]] = set()

    def _walk(routes: list[Any]) -> None:
        for route in routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            nested = getattr(route, "routes", None)
            if path is not None and methods is not None:
                norm = path.rstrip("/") or "/"
                if norm == COVERING_PATH or path.endswith("/calendar/covering-refresh"):
                    for method in methods:
                        if method == "HEAD":
                            continue
                        found.add((method, norm))
            if nested:
                _walk(list(nested))

    _walk(list(app.routes))
    return found


def build_domain_auth_harness_app(
    *,
    store: HarnessIdentityStore,
    clock: ControllableClock,
    session_secret: str = HARNESS_SESSION_SECRET,
) -> FastAPI:
    """Mirror production middleware + calendar router without lifespan/bootstrap."""
    os.environ.setdefault("SEED_DEMO_USER", "false")

    settings = get_settings()
    app = FastAPI(
        title="thePlan domain-auth ordered-result ASGI harness (impl)",
        version="0.0-harness-impl",
    )
    register_exception_handlers(app)

    app.add_middleware(PasswordChangeGateMiddleware)
    app.add_middleware(AgentBoundaryAMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(CoveringIngressMiddleware, clock=clock)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(calendar_routes.router)

    @api_router.get("/harness/off-route-control")
    def off_route_get() -> dict[str, object]:
        return {"ok": True, "route": "off-route-control"}

    @api_router.post("/harness/off-route-control")
    def off_route_post(user: User = Depends(get_current_user)) -> dict[str, object]:
        return {"ok": True, "route": "off-route-control", "user_id": str(user.id)}

    app.include_router(api_router)

    def _override_get_db() -> Iterator[FakeSession]:
        session = FakeSession(store)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    return app


def install_domain_binding(app: FastAPI, ports: CoveringPortBundle) -> None:
    """Install CoveringReleaseBinding(parent, session, domain_ports) — no dispatch."""
    # Explicit kwargs: parent_factory, session_factory, domain_ports only.
    # CoveringReleaseBinding.dispatch does not exist on this snapshot; do not add one.
    app.state.covering_release_binding = CoveringReleaseBinding(
        parent_factory=ports.parent_factory,
        session_factory=ports.session_factory,
        domain_ports=CoveringDomainPorts(
            token=ports._token,
            locks=ports._locks,
            apply=ports._apply,
        ),
    )


def install_wrong_type_binding(app: FastAPI) -> None:
    """Wrong-type binding must fail closed as NOT_CONFIGURED (not UNKNOWN)."""
    app.state.covering_release_binding = object()


@contextmanager
def domain_auth_asgi_client(
    *,
    store: HarnessIdentityStore | None = None,
    install_binding: bool = False,
    install_wrong_binding: bool = False,
    clock: ControllableClock | None = None,
) -> Iterator[DomainAuthHarness]:
    """Yield harness with fail-closed SessionLocal; optional domain binding."""
    identity = store or HarnessIdentityStore()
    recorder = PortRecorder()
    clock_obj = clock or ControllableClock(0.0)
    ports = CoveringPortBundle(store=identity, recorder=recorder, clock=clock_obj)
    app = build_domain_auth_harness_app(store=identity, clock=clock_obj)
    if install_wrong_binding:
        install_wrong_type_binding(app)
    elif install_binding:
        install_domain_binding(app, ports)

    def _gate_session_local() -> FakeSession:
        return FakeSession(identity)

    def _session_local_touch_tripwire(*_a: Any, **_k: Any) -> None:
        recorder.session_local_touch_attempts += 1
        _forbid_live_session_local()

    import app.api.middleware.password_change_gate as gate_mod
    import app.db as db_mod
    import app.services.agent_credentials as agent_cred_mod

    previous = {
        "gate": gate_mod.SessionLocal,
        "db": db_mod.SessionLocal,
        "agent_sl": agent_cred_mod.SessionLocal,
    }
    gate_mod.SessionLocal = _gate_session_local  # type: ignore[assignment]
    db_mod.SessionLocal = _forbid_live_session_local  # type: ignore[assignment]
    agent_cred_mod.SessionLocal = _session_local_touch_tripwire  # type: ignore[assignment]

    try:
        with TestClient(app) as client:
            yield DomainAuthHarness(
                client=client,
                store=identity,
                ports=ports,
                app=app,
                clock=clock_obj,
                binding_installed=install_binding,
            )
    finally:
        gate_mod.SessionLocal = previous["gate"]  # type: ignore[assignment]
        db_mod.SessionLocal = previous["db"]  # type: ignore[assignment]
        agent_cred_mod.SessionLocal = previous["agent_sl"]  # type: ignore[assignment]
        app.dependency_overrides.clear()
        if hasattr(app.state, "covering_release_binding"):
            delattr(app.state, "covering_release_binding")


def refresh_body(subscription_ids: list[UUID], **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "subscription_ids": [str(item) for item in subscription_ids],
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
    }
    body.update(extra)
    return body


def sorted_subscription_ids(ids: list[UUID]) -> list[UUID]:
    """Domain preflight orders by str(uuid) — not request order."""
    return sorted(ids, key=lambda value: str(value))


def asgi_post_chunked_json(
    app: FastAPI,
    *,
    path: str,
    body: bytes,
    cookie: str | None = None,
    chunk_size: int = 2048,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
    response_wait_timeout_seconds: float = 5.0,
    disconnect_after_body: bool = False,
) -> tuple[int | None, bytes, list[tuple[bytes, bytes]]]:
    """POST via raw ASGI with multi-chunk http.request and no Content-Length."""
    import asyncio

    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    chunks = [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)] or [b""]
    state = {"i": 0, "disconnected": False}
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
        (b"host", b"testserver"),
    ]
    if cookie:
        headers.append((b"cookie", f"session={cookie}".encode("latin-1")))
    if extra_headers:
        headers.extend(extra_headers)

    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    response_start: dict[str, Any] | None = None
    body_parts: list[bytes] = []
    response_complete = asyncio.Event()

    async def receive() -> dict[str, Any]:
        idx = state["i"]
        if idx < len(chunks):
            chunk = chunks[idx]
            state["i"] = idx + 1
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": idx < len(chunks) - 1,
            }
        if disconnect_after_body and not state["disconnected"]:
            state["disconnected"] = True
            return {"type": "http.disconnect"}
        try:
            await asyncio.wait_for(
                response_complete.wait(),
                timeout=response_wait_timeout_seconds,
            )
        except asyncio.TimeoutError:
            pass
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        nonlocal response_start
        if message["type"] == "http.response.start":
            response_start = message
        elif message["type"] == "http.response.body":
            body_parts.append(message.get("body", b"") or b"")
            if not message.get("more_body", False):
                response_complete.set()

    async def _run() -> None:
        await app(scope, receive, send)
        response_complete.set()

    asyncio.run(_run())
    if response_start is None:
        return None, b"".join(body_parts), []
    status = int(response_start["status"])
    resp_headers = list(response_start.get("headers") or [])
    return status, b"".join(body_parts), resp_headers


__all__ = [
    "BODY_LIMIT_BYTES",
    "COVERING_PATH",
    "ControllableClock",
    "CoveringPortBundle",
    "DomainAuthHarness",
    "HARNESS_SESSION_SECRET",
    "HarnessIdentityStore",
    "OFF_ROUTE_PATH",
    "PENDING_ASSESSMENT_FRESHNESS_REASON",
    "PENDING_NATIVE_PARENT_REASON",
    "PRODUCTION_COVERING_METHOD_PATHS",
    "PRODUCTION_MIDDLEWARE_ADD_ORDER",
    "PURPOSE_ASSESSMENT",
    "PURPOSE_AUTH_IDENTITY",
    "PURPOSE_AUTH_PREFLIGHT",
    "PURPOSE_PARENT",
    "PURPOSE_RECORDER",
    "PURPOSE_TELEMETRY",
    "PURPOSE_TOKEN",
    "PortRecorder",
    "REQUEST_BUDGET_CLEANUP_SECONDS",
    "REQUEST_BUDGET_ORDINARY_SECONDS",
    "REQUEST_BUDGET_TOTAL_SECONDS",
    "TokenReady",
    "TokenRejected",
    "WINDOW_END",
    "WINDOW_START",
    "asgi_post_chunked_json",
    "build_domain_auth_harness_app",
    "covering_method_paths",
    "domain_auth_asgi_client",
    "install_domain_binding",
    "install_wrong_type_binding",
    "middleware_add_order_names",
    "mint_signed_session_cookie",
    "refresh_body",
    "sorted_subscription_ids",
]
