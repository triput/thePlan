"""Browser cookie and Bearer auth seed helpers for I01. Secrets stay in memory only."""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.api.deps import SESSION_EPOCH_KEY, SESSION_USER_ID_KEY
from app.config import Settings
from app.models import AgentCredential
from app.models.enums import CalendarProvider
from app.scheduler.calendar_freshness import required_coverage_window
from app.services.agent_credentials import SECRET_PREFIX, _compose_secret
from app.services.passwords import hash_password
from app.services.token_crypto import encrypt_token
from tests.support.assessment_sql_fixture import (
    mark_covering_fresh,
    seed_account,
    seed_owner,
    seed_subscription,
)

# Disposable fixture-only Fernet key (32 zero bytes, url-safe b64). Not a live secret.
FIXTURE_TOKEN_ENCRYPTION_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
FIXTURE_SESSION_SECRET = "i01-i02-fixture-session-secret-v1-not-production"

ATTEMPT_VALIDITY_SECONDS = 600
TOKEN_HORIZON = timedelta(days=7)
PULL_WINDOW_MAX = timedelta(days=42)
REQUEST_END_HEADROOM = timedelta(hours=1)


@dataclass
class BrowserSeed:
    owner_id: UUID
    user_id: UUID
    session_epoch: int
    subscription_ids: list[UUID]
    account_ids: list[UUID]
    cookie: str
    calendar_ids: list[str]
    subscription_calendar_map: dict[str, str]
    t_plan: datetime | None = None
    request_window_start: datetime | None = None
    request_window_end: datetime | None = None
    auth_channel: str = "browser"
    auth_seed_path: str = "assessment_sql_seed_owner+mint_signed_session_cookie"


@dataclass
class BearerSeed:
    owner_id: UUID
    user_id: UUID
    credential_id: UUID
    subscription_ids: list[UUID]
    plain_bearer: str
    auth_channel: str = "agent"
    auth_seed_path: str = "agent_credential_bearer"


class PlanValidityExpired(RuntimeError):
    """Attempt validity / horizon STOP — no reseed or retry."""


def fixture_settings() -> Settings:
    return Settings(
        token_encryption_key=FIXTURE_TOKEN_ENCRYPTION_KEY,
        session_secret=FIXTURE_SESSION_SECRET,
        seed_demo_user=False,
        google_client_id="fixture-google-client-id",
        google_client_secret="fixture-google-client-secret-not-live",
        google_redirect_uri="https://fixture.invalid/oauth/google",
    )


def mint_signed_session_cookie(
    *,
    user_id: UUID,
    session_epoch: int,
    secret: str = FIXTURE_SESSION_SECRET,
) -> str:
    payload = {
        SESSION_USER_ID_KEY: str(user_id),
        SESSION_EPOCH_KEY: int(session_epoch),
    }
    data = b64encode(json.dumps(payload).encode("utf-8"))
    return TimestampSigner(str(secret)).sign(data).decode("utf-8")


def _encrypt_placeholder(settings: Settings, label: str) -> str:
    return encrypt_token(settings, f"fixture-{label}-plaintext-not-for-receipt")


def _token_hex_prefix(case_token: str) -> str:
    """Deterministic hex-safe 8-char prefix from the actual case token."""
    digest = hashlib.sha256(case_token.lower().encode("utf-8")).hexdigest()
    prefix = digest[:8]
    if len(prefix) != 8 or any(ch not in "0123456789abcdef" for ch in prefix):
        raise RuntimeError("hex-safe UUID prefix construction refused")
    return prefix


def inverted_subscription_ids(*, case_token: str) -> list[UUID]:
    """Distinct per-case pair whose insertion order differs from str-sorted order.

    Planted as [...1, ...0] so insertion order is reverse of str sort. Uses a
    hex-safe digest of the real case token (e.g. i01c01 / i01c10) so UUID()
    construction succeeds. Cases must not reuse the same literal UUIDs across
    shared disposable DB attempts.
    """
    prefix = _token_hex_prefix(case_token)
    planted = [
        UUID(f"{prefix}-0000-4000-8000-000000000001"),
        UUID(f"{prefix}-0000-4000-8000-000000000000"),
    ]
    for item in planted:
        text = str(item)
        if any(ch not in "0123456789abcdef-" for ch in text):
            raise RuntimeError("non-hex slipped into planted UUID text")
    if planted[0] == planted[1]:
        raise RuntimeError("inverted subscription ids must be distinct")
    if sorted(planted, key=str) == planted:
        raise RuntimeError("inversion lost: planted order equals str sort")
    return planted


def capture_plan_instant() -> datetime:
    """Aware-UTC T_plan captured once per I01 attempt before seed work."""
    return datetime.now(timezone.utc)


def assert_plan_still_valid(t_plan: datetime, *, now: datetime | None = None) -> None:
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or t_plan.tzinfo is None:
        raise RuntimeError("plan validity requires aware UTC datetimes")
    if current > t_plan + timedelta(seconds=ATTEMPT_VALIDITY_SECONDS):
        raise PlanValidityExpired(
            "attempt validity expired at checked boundary — STOP; no reseed"
        )


def plan_request_coverage_window(
    settings,
    t_plan: datetime,
) -> tuple[datetime, datetime]:
    """Union required_coverage_window at T_plan and T_plan+600s + 1h end headroom.

    Span must be <= 42 days. Preserve timezone-aware bounds without inward rounding.
    """
    if t_plan.tzinfo is None:
        raise RuntimeError("T_plan must be timezone-aware UTC")
    w0_start, w0_end = required_coverage_window(settings, t_plan)
    w1_start, w1_end = required_coverage_window(
        settings, t_plan + timedelta(seconds=ATTEMPT_VALIDITY_SECONDS)
    )
    start = min(w0_start, w1_start)
    end = max(w0_end, w1_end) + REQUEST_END_HEADROOM
    if end - start > PULL_WINDOW_MAX:
        raise PlanValidityExpired(
            "unsupported coverage horizon exceeds 42-day pull cap — STOP before work"
        )
    return start, end


def production_ordered_calendar_ids(
    *,
    subscription_ids: list[UUID],
    subscription_calendar_map: dict[str, str],
) -> list[str]:
    """Walk subscription ids in production str-sort order; map each to its calendar."""
    ordered_subs = sorted(subscription_ids, key=str)
    calendars: list[str] = []
    for sub_id in ordered_subs:
        calendar_id = subscription_calendar_map.get(str(sub_id))
        if not calendar_id:
            raise RuntimeError(f"missing calendar mapping for subscription {sub_id}")
        calendars.append(calendar_id)
    return calendars


def seed_browser_owner_with_subscriptions(
    db: Session,
    *,
    settings: Settings,
    username_prefix: str,
    subscription_count: int,
    scheduling_revision: int = 1,
    generation: int = 1,
    provider: CalendarProvider = CalendarProvider.google,
    force_uuid_sort_inversion: bool = False,
    planted_subscription_ids: list[UUID] | None = None,
    t_plan: datetime | None = None,
    request_window: tuple[datetime, datetime] | None = None,
) -> BrowserSeed:
    plan_instant = t_plan if t_plan is not None else capture_plan_instant()
    assert_plan_still_valid(plan_instant)
    owner = seed_owner(
        db,
        username_prefix=username_prefix,
        scheduling_revision=scheduling_revision,
    )
    if request_window is None:
        window_start, window_end = plan_request_coverage_window(owner.settings, plan_instant)
    else:
        window_start, window_end = request_window
        if window_end - window_start > PULL_WINDOW_MAX:
            raise PlanValidityExpired(
                "unsupported coverage horizon exceeds 42-day pull cap — STOP before work"
            )
    account = seed_account(db, owner.user, provider=provider)
    account.access_token_enc = _encrypt_placeholder(settings, "access")
    account.refresh_token_enc = _encrypt_placeholder(settings, "refresh")
    account.token_expires_at = plan_instant + TOKEN_HORIZON
    success_at = plan_instant
    if planted_subscription_ids is not None:
        if len(planted_subscription_ids) != subscription_count:
            raise RuntimeError("planted_subscription_ids length mismatch")
    elif force_uuid_sort_inversion and subscription_count >= 2:
        planted_subscription_ids = inverted_subscription_ids(case_token=username_prefix)
        if subscription_count > 2:
            planted_subscription_ids = planted_subscription_ids + [
                uuid.uuid4() for _ in range(subscription_count - 2)
            ]
    subs = []
    calendar_ids: list[str] = []
    subscription_calendar_map: dict[str, str] = {}
    for index in range(subscription_count):
        sub_id = None
        if planted_subscription_ids is not None:
            sub_id = planted_subscription_ids[index]
        calendar_id = f"cal-{username_prefix}-{index}"
        sub = seed_subscription(
            db,
            account,
            calendar_id=calendar_id,
            summary=f"{username_prefix}-{index}",
            sub_id=sub_id,
        )
        mark_covering_fresh(
            sub,
            window_start=window_start,
            window_end=window_end,
            success_at=success_at,
            provider=provider,
            generation=generation,
        )
        subs.append(sub)
        calendar_ids.append(calendar_id)
        subscription_calendar_map[str(sub.id)] = calendar_id
    db.flush()
    cookie = mint_signed_session_cookie(
        user_id=owner.user.id,
        session_epoch=int(owner.user.session_epoch),
    )
    return BrowserSeed(
        owner_id=owner.owner_id,
        user_id=owner.user.id,
        session_epoch=int(owner.user.session_epoch),
        subscription_ids=[sub.id for sub in subs],
        account_ids=[account.id],
        cookie=cookie,
        calendar_ids=calendar_ids,
        subscription_calendar_map=subscription_calendar_map,
        t_plan=plan_instant,
        request_window_start=window_start,
        request_window_end=window_end,
    )


def seed_wrong_owner_browser(
    db: Session,
    *,
    settings: Settings,
    foreign_subscription_ids: list[UUID],
) -> BrowserSeed:
    """Browser identity that does not own the requested subscription ids."""
    owner = seed_owner(db, username_prefix="i01-wrong-owner", scheduling_revision=1)
    cookie = mint_signed_session_cookie(
        user_id=owner.user.id,
        session_epoch=int(owner.user.session_epoch),
    )
    return BrowserSeed(
        owner_id=owner.owner_id,
        user_id=owner.user.id,
        session_epoch=int(owner.user.session_epoch),
        subscription_ids=list(foreign_subscription_ids),
        account_ids=[],
        cookie=cookie,
        calendar_ids=[],
        subscription_calendar_map={},
    )


def seed_agent_bearer(
    db: Session,
    *,
    settings: Settings,
    username_prefix: str,
    subscription_count: int = 1,
    allow_access: bool = True,
    t_plan: datetime | None = None,
) -> BearerSeed:
    plan_instant = t_plan if t_plan is not None else capture_plan_instant()
    assert_plan_still_valid(plan_instant)
    owner = seed_owner(db, username_prefix=username_prefix, scheduling_revision=1)
    owner.settings.allow_agent_cli_access = bool(allow_access)
    db.flush()
    window_start, window_end = plan_request_coverage_window(owner.settings, plan_instant)
    account = seed_account(db, owner.user)
    account.access_token_enc = _encrypt_placeholder(settings, "access")
    account.refresh_token_enc = _encrypt_placeholder(settings, "refresh")
    account.token_expires_at = plan_instant + TOKEN_HORIZON
    success_at = plan_instant
    subs = []
    for index in range(subscription_count):
        sub = seed_subscription(
            db,
            account,
            calendar_id=f"cal-agent-{username_prefix}-{index}",
            summary=f"agent-{username_prefix}-{index}",
        )
        mark_covering_fresh(
            sub,
            window_start=window_start,
            window_end=window_end,
            success_at=success_at,
            generation=1,
        )
        subs.append(sub)
    credential_id = uuid.uuid4()
    plain = _compose_secret(credential_id, secrets.token_urlsafe(32))
    row = AgentCredential(
        id=credential_id,
        owner_id=owner.user.id,
        label=f"{username_prefix}-cred",
        secret_hash=hash_password(plain),
    )
    db.add(row)
    db.flush()
    if not plain.startswith(SECRET_PREFIX):
        raise RuntimeError("agent secret composition refused")
    return BearerSeed(
        owner_id=owner.owner_id,
        user_id=owner.user.id,
        credential_id=credential_id,
        subscription_ids=[sub.id for sub in subs],
        plain_bearer=plain,
    )


def covering_refresh_body(
    subscription_ids: list[UUID],
    *,
    horizon_label: str = "i01-fixture-horizon-v1",
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    t_plan: datetime | None = None,
    user_settings=None,
) -> dict[str, Any]:
    """Build covering-refresh JSON body.

    Full scheduling_ready cases must pass the planned request window from seed
    (union of required_coverage_window at T_plan and T_plan+600s + 1h end headroom).
    When windows are omitted, plan from user_settings if provided; otherwise use a
    non-readiness local span from T_plan (not a substitute for scheduling_ready).
    """
    if window_start is None or window_end is None:
        plan_instant = t_plan if t_plan is not None else capture_plan_instant()
        if user_settings is not None:
            start, end = plan_request_coverage_window(user_settings, plan_instant)
        else:
            start = plan_instant
            end = plan_instant + timedelta(days=1)
        window_start = start if window_start is None else window_start
        window_end = end if window_end is None else window_end
    if window_end - window_start > PULL_WINDOW_MAX:
        raise PlanValidityExpired(
            "unsupported coverage horizon exceeds 42-day pull cap — STOP before work"
        )
    return {
        "subscription_ids": [str(item) for item in subscription_ids],
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "scheduling_horizon_label": horizon_label,
    }
