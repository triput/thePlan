"""Offline ASGI harness for covering-refresh HTTP boundary proofs (I3 / H1–H2 / H6).

Test-only. Builds a FastAPI app that mirrors production middleware add-order + the
real ``calendar`` router **without** ``create_app`` lifespan/bootstrap and
without live DB/provider I/O.

Fail-closed fakes replace:
- ``get_db`` / PasswordChangeGate ``SessionLocal``
- ``app.api.deps.touch_last_used`` (the bound name ``get_current_user`` calls)
- ``run_covering_refresh`` (provider + covering DB orchestration)

Synthetic signed browser sessions use the same itsdangerous TimestampSigner
format as Starlette ``SessionMiddleware``.

Mirrored assembly is **not** itself parity proof — compare middleware add-order
and covering method/path against production ``create_app()`` (static introspect,
no lifespan) and the frozen constants below.
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
from app.api.errors import register_exception_handlers
from app.api.middleware import PasswordChangeGateMiddleware
from app.api.middleware.agent_boundary_a import AgentBoundaryAMiddleware
from app.api.routes import calendar as calendar_routes
from app.config import get_settings
from app.models import AgentCredential, User, UserSettings
from app.schemas.calendar import (
    CoveringActionOut,
    CoveringActionSummaryOut,
    CoveringRefreshRequest,
    CoveringRefreshResponse,
    CoveringRefreshResultRow,
    CoveringWindowOut,
    SchedulingReadinessOut,
)
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.services.passwords import hash_password

# Harness-only session secret — never a production secret.
HARNESS_SESSION_SECRET = "covering-refresh-http-harness-offline-session-secret-v1"
COVERING_PATH = "/api/v1/calendar/covering-refresh"
OFF_ROUTE_PATH = "/api/v1/harness/off-route-control"
WINDOW_START = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc)

# Frozen from ``app.main.create_app`` **add/call order** (first ``add_middleware``
# = innermost). Starlette stores ``user_middleware`` with insert-at-0, so raw
# ``user_middleware`` is outermost-first — helpers reverse to this add order.
PRODUCTION_MIDDLEWARE_ADD_ORDER: tuple[str, ...] = (
    "PasswordChangeGateMiddleware",
    "AgentBoundaryAMiddleware",
    "SessionMiddleware",
    "CORSMiddleware",
)
PRODUCTION_COVERING_METHOD_PATHS: frozenset[tuple[str, str]] = frozenset(
    {("POST", "/api/v1/calendar/covering-refresh")}
)


def _forbid_live_session_local() -> None:
    raise RuntimeError(
        "covering harness: live SessionLocal is unbound/forbidden "
        "(fail-closed; no DB endpoint profile)"
    )


class _FakeQuery:
    """Minimal SQLAlchemy-shaped query surface for auth deps only."""

    def __init__(self, store: "HarnessIdentityStore", entities: tuple[Any, ...]) -> None:
        self._store = store
        self._entities = entities
        self._id_eq: UUID | None = None
        self._require_password_hash = False
        self._limit: int | None = None

    def options(self, *_a: Any, **_k: Any) -> "_FakeQuery":
        return self

    def filter(self, *criteria: Any) -> "_FakeQuery":
        for crit in criteria:
            clause = str(crit)
            left = getattr(crit, "left", None)
            right = getattr(crit, "right", None)
            element = getattr(crit, "element", None)
            key = getattr(left, "key", None) or getattr(element, "key", None)
            if key == "id" and right is not None:
                value = getattr(right, "value", right)
                try:
                    self._id_eq = value if isinstance(value, UUID) else UUID(str(value))
                except (TypeError, ValueError):
                    self._id_eq = None
            if "password_hash" in clause and "IS NOT NULL" in clause.upper():
                self._require_password_hash = True
            elif key == "password_hash":
                self._require_password_hash = True
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    def order_by(self, *_a: Any, **_k: Any) -> "_FakeQuery":
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

    def one_or_none(self) -> Any:
        rows = self.all()
        if not rows:
            return None
        return rows[0]

    def all(self) -> list[Any]:
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


class _FakeResult:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def one_or_none(self) -> tuple[Any, ...] | None:
        return self._row


class FakeSession:
    """Fail-closed request/gate session used by auth + PasswordChangeGate only."""

    def __init__(self, store: "HarnessIdentityStore") -> None:
        self._store = store
        self.info: dict[str, Any] = {}

    def get(self, model: type[Any], ident: Any) -> Any:
        if model is User:
            return self._store.users.get(ident)
        if model is AgentCredential:
            return self._store.credentials.get(ident)
        return None

    def query(self, *entities: Any) -> _FakeQuery:
        return _FakeQuery(self._store, entities)

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
        params = params or {}
        sql = str(statement).lower()
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
        raise RuntimeError(f"covering harness FakeSession.execute unbound SQL: {sql[:120]}")

    def close(self) -> None:
        return None

    def commit(self) -> None:
        raise RuntimeError("covering harness: commit forbidden on FakeSession")

    def rollback(self) -> None:
        return None


@dataclass
class TouchTelemetry:
    """Records ``deps.touch_last_used`` credential ids (Bearer telemetry site)."""

    credential_ids: list[UUID] = field(default_factory=list)

    def __call__(self, credential_id: UUID) -> None:
        self.credential_ids.append(credential_id)

    def reset(self) -> None:
        self.credential_ids.clear()


@dataclass
class HarnessIdentityStore:
    users: dict[UUID, User] = field(default_factory=dict)
    credentials: dict[UUID, AgentCredential] = field(default_factory=dict)
    plaintext_secrets: dict[UUID, str] = field(default_factory=dict)

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
            scheduling_revision=0,
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


@dataclass
class FakeCoveringOrchestrator:
    """Fail-closed stand-in for ``run_covering_refresh`` (no provider/DB I/O).

    UNKNOWN raises here prove **HTTP exception mapping** only (route → 503), not
    native root/ack UNKNOWN coordination.
    """

    mode: str = "success"
    dispatched_subscription_ids: list[UUID] = field(default_factory=list)
    unadmitted_subscription_ids: list[UUID] = field(default_factory=list)
    call_bodies: list[CoveringRefreshRequest] = field(default_factory=list)
    call_owner_ids: list[UUID] = field(default_factory=list)
    provider_admissions: int = 0
    # Raise CoveringRootOutcomeUnknown after N admitted dispatches (0 = before any).
    unknown_after_dispatch_count: int | None = None

    def reset(self) -> None:
        self.dispatched_subscription_ids.clear()
        self.unadmitted_subscription_ids.clear()
        self.call_bodies.clear()
        self.call_owner_ids.clear()
        self.provider_admissions = 0

    def __call__(
        self,
        _db: Any,
        *,
        settings: Any,
        owner_id: UUID,
        body: CoveringRefreshRequest,
        now: datetime | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> CoveringRefreshResponse:
        _ = (settings, now, clock)
        self.call_bodies.append(body)
        self.call_owner_ids.append(owner_id)
        ids = list(body.subscription_ids)

        if self.mode == "raise_before_admission":
            raise RuntimeError("harness: unexpected raise_before_admission mode for HTTP path")

        results: list[CoveringRefreshResultRow] = []
        for index, sub_id in enumerate(ids):
            if (
                self.unknown_after_dispatch_count is not None
                and len(self.dispatched_subscription_ids) >= self.unknown_after_dispatch_count
            ):
                # Coordinator stop inside the fake — HTTP mapping proof only.
                raise CoveringRootOutcomeUnknown()

            # Post-ownership exhaustion: first target admitted; later targets are
            # classified unstarted/unadmitted (no provider admission increment).
            if self.mode == "post_ownership_deadline_exhaustion" and index > 0:
                self.unadmitted_subscription_ids.append(sub_id)
                results.append(
                    CoveringRefreshResultRow(
                        subscription_id=sub_id,
                        phase="preflight",
                        status="preflight_rejected",
                        preflight_code="CALENDAR_REFRESH_DEADLINE_EXCEEDED",
                    )
                )
                continue

            self.dispatched_subscription_ids.append(sub_id)
            self.provider_admissions += 1

            if self.mode == "partial_two":
                if index == 0:
                    results.append(
                        CoveringRefreshResultRow(
                            subscription_id=sub_id,
                            phase="import",
                            status="ok",
                            upserted=1,
                        )
                    )
                else:
                    results.append(
                        CoveringRefreshResultRow(
                            subscription_id=sub_id,
                            phase="import",
                            status="failed",
                            cause="provider_http_502",
                            upserted=0,
                        )
                    )
            elif self.mode == "post_ownership_deadline_exhaustion":
                results.append(
                    CoveringRefreshResultRow(
                        subscription_id=sub_id,
                        phase="import",
                        status="ok",
                        upserted=1,
                    )
                )
            else:
                results.append(
                    CoveringRefreshResultRow(
                        subscription_id=sub_id,
                        phase="import",
                        status="ok",
                        upserted=1,
                    )
                )

        import_ok = sum(1 for row in results if row.status == "ok")
        import_failed = sum(1 for row in results if row.status == "failed")
        preflight_rejected = sum(1 for row in results if row.phase == "preflight")
        if import_ok == len(results) and results:
            overall: str = "success"
        elif import_ok == 0 and import_failed > 0:
            overall = "failed"
        elif import_ok > 0 and (import_failed > 0 or preflight_rejected > 0):
            overall = "partial"
        elif not results:
            overall = "no_op"
        else:
            overall = "partial"

        window = CoveringWindowOut(start=WINDOW_START, end=WINDOW_END)
        return CoveringRefreshResponse(
            window_requested=window,
            window_effective=window,
            window_widened=False,
            window_widen_reason="",
            overall_outcome=overall,  # type: ignore[arg-type]
            action_summary=CoveringActionSummaryOut(
                requested=len(ids),
                preflight_rejected=preflight_rejected,
                import_attempted=import_ok + import_failed,
                import_ok=import_ok,
                import_failed=import_failed,
            ),
            results=results,
            coverage_action=CoveringActionOut(
                window=window,
                all_requested_covering_ok=overall == "success",
                freshness_requested={"ok": overall == "success"},
            ),
            scheduling_readiness=SchedulingReadinessOut(scheduling_revision=1),
            scheduling_revision_at_start=0,
            scheduling_revision_at_end=1,
            scheduling_revision_bumped=True,
        )


@dataclass
class CoveringHarness:
    client: TestClient
    store: HarnessIdentityStore
    orchestrator: FakeCoveringOrchestrator
    app: FastAPI
    touch_telemetry: TouchTelemetry


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
    """Middleware class names in ``add_middleware`` call order (innermost first).

    Starlette ``add_middleware`` inserts at index 0, so ``app.user_middleware``
    is outermost-first (CORS → … → PasswordChangeGate). Reverse to match
    ``PRODUCTION_MIDDLEWARE_ADD_ORDER`` / ``create_app`` call order.
    """
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


def covering_refresh_paths(app: FastAPI) -> list[tuple[str, str]]:
    """Legacy helper: (joined-methods, path) pairs."""
    by_path: dict[str, list[str]] = {}
    for method, path in covering_method_paths(app):
        by_path.setdefault(path, []).append(method)
    return [(",".join(sorted(methods)), path) for path, methods in sorted(by_path.items())]


def build_covering_refresh_harness_app(
    *,
    store: HarnessIdentityStore,
    orchestrator: FakeCoveringOrchestrator,
    session_secret: str = HARNESS_SESSION_SECRET,
) -> FastAPI:
    """Mirror production middleware + calendar router without lifespan/bootstrap."""
    os.environ.setdefault("SEED_DEMO_USER", "false")

    settings = get_settings()
    app = FastAPI(
        title="thePlan covering-refresh ASGI harness",
        version="0.0-harness",
    )
    register_exception_handlers(app)

    # Same add order as ``create_app`` (Starlette LIFO → CORS outermost).
    app.add_middleware(PasswordChangeGateMiddleware)
    app.add_middleware(AgentBoundaryAMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=False,
    )
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


@contextmanager
def covering_refresh_asgi_client(
    *,
    store: HarnessIdentityStore | None = None,
    orchestrator: FakeCoveringOrchestrator | None = None,
    monkeypatch: Any | None = None,
) -> Iterator[CoveringHarness]:
    """Yield harness with fail-closed SessionLocal + deps.touch_last_used patch."""
    identity = store or HarnessIdentityStore()
    orch = orchestrator or FakeCoveringOrchestrator()
    touch = TouchTelemetry()
    app = build_covering_refresh_harness_app(store=identity, orchestrator=orch)

    def _gate_session_local() -> FakeSession:
        return FakeSession(identity)

    import app.api.deps as deps_mod
    import app.api.middleware.password_change_gate as gate_mod
    import app.db as db_mod
    import app.services.agent_credentials as agent_cred_mod
    import app.services.covering_refresh as covering_refresh_mod

    # deps imports touch_last_used by name — patch the bound alias deps uses.
    previous = {
        "gate": gate_mod.SessionLocal,
        "db": db_mod.SessionLocal,
        "agent_sl": agent_cred_mod.SessionLocal,
        "agent_touch": agent_cred_mod.touch_last_used,
        "deps_touch": deps_mod.touch_last_used,
        "run": covering_refresh_mod.run_covering_refresh,
    }
    gate_mod.SessionLocal = _gate_session_local  # type: ignore[assignment]
    db_mod.SessionLocal = _forbid_live_session_local  # type: ignore[assignment]
    agent_cred_mod.SessionLocal = _forbid_live_session_local  # type: ignore[assignment]
    agent_cred_mod.touch_last_used = touch  # type: ignore[assignment]
    deps_mod.touch_last_used = touch  # type: ignore[assignment]
    covering_refresh_mod.run_covering_refresh = orch  # type: ignore[assignment]

    if monkeypatch is not None:
        monkeypatch.setattr(gate_mod, "SessionLocal", _gate_session_local)
        monkeypatch.setattr(db_mod, "SessionLocal", _forbid_live_session_local)
        monkeypatch.setattr(agent_cred_mod, "SessionLocal", _forbid_live_session_local)
        monkeypatch.setattr(agent_cred_mod, "touch_last_used", touch)
        monkeypatch.setattr(deps_mod, "touch_last_used", touch)
        monkeypatch.setattr(covering_refresh_mod, "run_covering_refresh", orch)

    try:
        with TestClient(app) as client:
            yield CoveringHarness(
                client=client,
                store=identity,
                orchestrator=orch,
                app=app,
                touch_telemetry=touch,
            )
    finally:
        gate_mod.SessionLocal = previous["gate"]  # type: ignore[assignment]
        db_mod.SessionLocal = previous["db"]  # type: ignore[assignment]
        agent_cred_mod.SessionLocal = previous["agent_sl"]  # type: ignore[assignment]
        agent_cred_mod.touch_last_used = previous["agent_touch"]  # type: ignore[assignment]
        deps_mod.touch_last_used = previous["deps_touch"]  # type: ignore[assignment]
        covering_refresh_mod.run_covering_refresh = previous["run"]  # type: ignore[assignment]
        app.dependency_overrides.clear()


def refresh_body(subscription_ids: list[UUID], **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "subscription_ids": [str(item) for item in subscription_ids],
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
    }
    body.update(extra)
    return body


def asgi_post_chunked_json(
    app: FastAPI,
    *,
    path: str,
    body: bytes,
    cookie: str | None = None,
    chunk_size: int = 2048,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
    response_wait_timeout_seconds: float = 5.0,
) -> tuple[int, bytes, list[tuple[bytes, bytes]]]:
    """POST via raw ASGI with multi-chunk ``http.request`` and **no** Content-Length.

    Proof boundary: streamed receive (not TestClient fixed-length ``content=``).
    After the last body chunk, wait for response completion (bounded timeout)
    before ``http.disconnect`` so the case measures chunking rather than a
    client-disconnect race.
    """
    import asyncio

    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    chunks = [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)] or [b""]
    state = {"i": 0}
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
        # Body fully delivered — do not disconnect until the response finishes
        # (or the synthetic wait bound elapses).
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
        # If the app finished without a final body frame, unblock receive.
        response_complete.set()

    asyncio.run(_run())
    assert response_start is not None
    status = int(response_start["status"])
    resp_headers = list(response_start.get("headers") or [])
    return status, b"".join(body_parts), resp_headers


__all__ = [
    "COVERING_PATH",
    "CoveringHarness",
    "FakeCoveringOrchestrator",
    "HARNESS_SESSION_SECRET",
    "HarnessIdentityStore",
    "OFF_ROUTE_PATH",
    "PRODUCTION_COVERING_METHOD_PATHS",
    "PRODUCTION_MIDDLEWARE_ADD_ORDER",
    "TouchTelemetry",
    "WINDOW_END",
    "WINDOW_START",
    "asgi_post_chunked_json",
    "build_covering_refresh_harness_app",
    "covering_method_paths",
    "covering_refresh_asgi_client",
    "covering_refresh_paths",
    "middleware_add_order_names",
    "mint_signed_session_cookie",
    "refresh_body",
]
