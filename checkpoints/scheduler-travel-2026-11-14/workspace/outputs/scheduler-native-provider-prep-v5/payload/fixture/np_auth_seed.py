"""Disposable tokens/settings and per-case planning for native-provider prep.

PREPARED ONLY. Fixture-only Fernet/session material — not live credentials.
Fresh planning per distinct predeclared attempt; 600s plan validity; no failed-attempt reseed/retry.
Actual request clocks when claimed: work 210 / request 240 / cleanup 30.

Vertical contract (C340C47B): use app.config.Settings (NOT app.core.config/get_settings
ambient singleton). Persist disposable user/account/subscription/token rows and mint a
signed synthetic browser session. covering-refresh body uses subscription_ids + window.
"""
from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID


# Disposable fixture-only Fernet key (32 zero bytes, url-safe b64). Not a live secret.
FIXTURE_TOKEN_ENCRYPTION_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
FIXTURE_SESSION_SECRET = "np-provider-fixture-session-secret-v1-not-production"

ATTEMPT_VALIDITY_SECONDS = 600
WORK_DEADLINE_SECONDS = 210
REQUEST_DEADLINE_SECONDS = 240
CLEANUP_ALLOWANCE_SECONDS = 30
TOKEN_HORIZON = timedelta(days=7)
PULL_WINDOW_MAX = timedelta(days=42)
REQUEST_END_HEADROOM = timedelta(hours=1)

# Synthetic OAuth settings — disposable labels only
FIXTURE_MS_CLIENT_ID = "fixture-ms-client-id"
FIXTURE_MS_CLIENT_SECRET = "fixture-ms-client-secret-not-live"
FIXTURE_MS_TENANT = "common"
FIXTURE_MS_REDIRECT = "https://fixture.invalid/oauth/microsoft"
FIXTURE_GOOGLE_CLIENT_ID = "fixture-google-client-id"
FIXTURE_GOOGLE_CLIENT_SECRET = "fixture-google-client-secret-not-live"
FIXTURE_GOOGLE_REDIRECT = "https://fixture.invalid/oauth/google"

COVERING_PATH = "/api/v1/calendar/covering-refresh"


class PlanValidityExpired(RuntimeError):
    """Attempt validity / horizon STOP — no reseed or retry."""


@dataclass
class AttemptPlan:
    case_id: str
    t_plan: datetime
    attempt_token: str
    auth_channel: str = "fixture"
    notes: str = ""


@dataclass
class DisposableTokenSeed:
    case_id: str
    provider: str  # microsoft | google
    expired: bool
    label_hash: str
    settings_labels: dict[str, str] = field(default_factory=dict)


@dataclass
class BrowserSeed:
    """Persisted disposable seed — real DB rows + signed session cookie (not in-memory hashes alone)."""

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
    auth_seed_path: str = "np_auth_seed.seed_browser_owner_with_subscriptions"
    provider: str = "microsoft"
    token_expired: bool = False
    covering_marked_fresh_at_seed: bool = False


def capture_plan_instant() -> datetime:
    """Aware-UTC T_plan captured once per distinct predeclared attempt."""
    return datetime.now(timezone.utc)


def assert_plan_still_valid(t_plan: datetime, *, now: datetime | None = None) -> None:
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or t_plan.tzinfo is None:
        raise RuntimeError("plan validity requires aware UTC datetimes")
    if current > t_plan + timedelta(seconds=ATTEMPT_VALIDITY_SECONDS):
        raise PlanValidityExpired(
            "attempt validity expired at checked boundary — STOP; no reseed"
        )


def fresh_attempt_plan(case_id: str) -> AttemptPlan:
    """Fresh planning for each distinct predeclared attempt. Never reuse failed attempt."""
    if not case_id or not case_id.startswith("NP-"):
        raise RuntimeError("case_id refused")
    t_plan = capture_plan_instant()
    digest = hashlib.sha256(f"{case_id}|{t_plan.isoformat()}".encode("utf-8")).hexdigest()[:16]
    return AttemptPlan(case_id=case_id, t_plan=t_plan, attempt_token=digest)


def _label_hash(case_id: str, provider: str, kind: str) -> str:
    return hashlib.sha256(f"{case_id}|{provider}|{kind}".encode("utf-8")).hexdigest().upper()


def disposable_ms_settings() -> dict[str, str]:
    return {
        "microsoft_client_id": FIXTURE_MS_CLIENT_ID,
        "microsoft_client_secret": FIXTURE_MS_CLIENT_SECRET,
        "microsoft_tenant_id": FIXTURE_MS_TENANT,
        "microsoft_redirect_uri": FIXTURE_MS_REDIRECT,
        "token_encryption_key": FIXTURE_TOKEN_ENCRYPTION_KEY,
        "session_secret": FIXTURE_SESSION_SECRET,
        "live_credentials": "false",
    }


def disposable_google_settings() -> dict[str, str]:
    return {
        "google_client_id": FIXTURE_GOOGLE_CLIENT_ID,
        "google_client_secret": FIXTURE_GOOGLE_CLIENT_SECRET,
        "google_redirect_uri": FIXTURE_GOOGLE_REDIRECT,
        "token_encryption_key": FIXTURE_TOKEN_ENCRYPTION_KEY,
        "session_secret": FIXTURE_SESSION_SECRET,
        "live_credentials": "false",
    }


def fixture_settings():
    """Synthetic fixture Settings — app.config.Settings, not ambient get_settings."""
    from app.config import Settings

    return Settings(
        token_encryption_key=FIXTURE_TOKEN_ENCRYPTION_KEY,
        session_secret=FIXTURE_SESSION_SECRET,
        seed_demo_user=False,
        google_client_id=FIXTURE_GOOGLE_CLIENT_ID,
        google_client_secret=FIXTURE_GOOGLE_CLIENT_SECRET,
        google_redirect_uri=FIXTURE_GOOGLE_REDIRECT,
        microsoft_client_id=FIXTURE_MS_CLIENT_ID,
        microsoft_client_secret=FIXTURE_MS_CLIENT_SECRET,
        microsoft_redirect_uri=FIXTURE_MS_REDIRECT,
        microsoft_tenant_id=FIXTURE_MS_TENANT,
    )


def mint_signed_session_cookie(
    *,
    user_id: UUID,
    session_epoch: int,
    secret: str = FIXTURE_SESSION_SECRET,
) -> str:
    from itsdangerous import TimestampSigner
    from app.api.deps import SESSION_EPOCH_KEY, SESSION_USER_ID_KEY

    payload = {
        SESSION_USER_ID_KEY: str(user_id),
        SESSION_EPOCH_KEY: int(session_epoch),
    }
    data = b64encode(json.dumps(payload).encode("utf-8"))
    return TimestampSigner(str(secret)).sign(data).decode("utf-8")


def seed_token_plan(*, case_id: str, provider: str, expired: bool) -> DisposableTokenSeed:
    if provider not in ("microsoft", "google"):
        raise RuntimeError("provider must be microsoft|google")
    settings = disposable_ms_settings() if provider == "microsoft" else disposable_google_settings()
    return DisposableTokenSeed(
        case_id=case_id,
        provider=provider,
        expired=expired,
        label_hash=_label_hash(case_id, provider, "expired" if expired else "nonexpired"),
        settings_labels=settings,
    )


def inverted_subscription_ids(*, case_token: str) -> list[UUID]:
    digest = hashlib.sha256(case_token.lower().encode("utf-8")).hexdigest()
    prefix = digest[:8]
    planted = [
        UUID(f"{prefix}-0000-4000-8000-000000000001"),
        UUID(f"{prefix}-0000-4000-8000-000000000000"),
    ]
    if planted[0] == planted[1]:
        raise RuntimeError("inverted subscription ids must be distinct")
    if sorted(planted, key=str) == planted:
        raise RuntimeError("inversion lost: planted order equals str sort")
    return planted


def plan_request_coverage_window(settings, t_plan: datetime) -> tuple[datetime, datetime]:
    from app.scheduler.calendar_freshness import required_coverage_window

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


def covering_refresh_body(
    subscription_ids: list[UUID],
    *,
    window_start: datetime,
    window_end: datetime,
    horizon_label: str = "np-ms-nonexpired-horizon-v1",
) -> dict[str, Any]:
    """POST /api/v1/calendar/covering-refresh body — subscription_ids + window only."""
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


def seed_browser_owner_with_subscriptions(
    db,
    *,
    settings,
    username_prefix: str,
    subscription_count: int,
    provider: str = "microsoft",
    expired: bool = False,
    mark_covering_fresh_at_seed: bool = False,
    scheduling_revision: int = 1,
    generation: int = 1,
    planted_subscription_ids: list[UUID] | None = None,
    t_plan: datetime | None = None,
    request_window: tuple[datetime, datetime] | None = None,
    plant_microsoft_primary_alias: bool = False,
) -> BrowserSeed:
    """Persist disposable owner/account/subscription/token rows; return signed cookie.

    Nonexpired vertical seeds with mark_covering_fresh_at_seed=False so measured
    before-state is distinguishable from post-refresh after-state.
    When plant_microsoft_primary_alias=True, the first enabled subscription uses
    MS_LEGACY_PRIMARY_ALIAS ("primary") so production requests live identity evidence.
    """
    from app.models.enums import CalendarProvider
    from app.services.calendar_alias_canonicalize import MS_LEGACY_PRIMARY_ALIAS
    from app.services.token_crypto import encrypt_token
    from tests.support.assessment_sql_fixture import (
        mark_covering_fresh,
        seed_account,
        seed_owner,
        seed_subscription,
    )

    plan_instant = t_plan if t_plan is not None else capture_plan_instant()
    assert_plan_still_valid(plan_instant)
    cal_provider = (
        CalendarProvider.microsoft if provider == "microsoft" else CalendarProvider.google
    )
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
    account = seed_account(db, owner.user, provider=cal_provider)
    account.access_token_enc = encrypt_token(settings, "fixture-access-plaintext-not-for-receipt")
    account.refresh_token_enc = encrypt_token(settings, "fixture-refresh-plaintext-not-for-receipt")
    if expired:
        account.token_expires_at = plan_instant - timedelta(minutes=5)
    else:
        account.token_expires_at = plan_instant + TOKEN_HORIZON
    if planted_subscription_ids is not None:
        if len(planted_subscription_ids) != subscription_count:
            raise RuntimeError("planted_subscription_ids length mismatch")
    subs = []
    calendar_ids: list[str] = []
    subscription_calendar_map: dict[str, str] = {}
    for index in range(subscription_count):
        sub_id = None
        if planted_subscription_ids is not None:
            sub_id = planted_subscription_ids[index]
        if plant_microsoft_primary_alias and index == 0:
            calendar_id = MS_LEGACY_PRIMARY_ALIAS
        else:
            calendar_id = f"cal-{username_prefix}-{index}"
        sub = seed_subscription(
            db,
            account,
            calendar_id=calendar_id,
            summary=f"{username_prefix}-{index}",
            sub_id=sub_id,
        )
        if mark_covering_fresh_at_seed:
            mark_covering_fresh(
                sub,
                window_start=window_start,
                window_end=window_end,
                success_at=plan_instant,
                provider=cal_provider,
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
        provider=provider,
        token_expired=expired,
        covering_marked_fresh_at_seed=mark_covering_fresh_at_seed,
    )


def derive_production_target_calendar_order(
    *,
    subscription_ids: list[UUID],
    subscription_calendar_map: dict[str, str],
    primary_alias: str = "primary",
    identity_default_calendar_id: str = "cal-ms-default",
) -> tuple[str, ...]:
    """Wire calendar order from planted ID→calendar map + production str-sort.

    Mirrors covering_refresh._preflight_load_targets sorted(subscription_ids, key=str).
    After live identity, MS_LEGACY_PRIMARY_ALIAS rewrites to the identity-default id.
    Do not use insertion order or merely sort calendar strings.
    """
    ordered: list[str] = []
    for sub_id in sorted(subscription_ids, key=lambda value: str(value)):
        calendar_id = subscription_calendar_map[str(sub_id)]
        if calendar_id == primary_alias:
            ordered.append(identity_default_calendar_id)
        else:
            ordered.append(calendar_id)
    return tuple(ordered)


def measure_subscription_coverage_state(db, *, subscription_ids: list[UUID]) -> dict[str, Any]:
    """Measured DB before/after — exact typed fields, not literal False expectations."""
    from app.models import CalendarSubscription

    rows = []
    for sub_id in subscription_ids:
        sub = db.get(CalendarSubscription, sub_id)
        if sub is None:
            raise RuntimeError(f"subscription missing:{sub_id}")
        rows.append(
            {
                "subscription_id": str(sub.id),
                "coverage_active_generation": sub.coverage_active_generation,
                "coverage_success_generation": sub.coverage_success_generation,
                "coverage_window_start": (
                    sub.coverage_window_start.isoformat()
                    if sub.coverage_window_start is not None
                    else None
                ),
                "coverage_window_end": (
                    sub.coverage_window_end.isoformat()
                    if sub.coverage_window_end is not None
                    else None
                ),
                "coverage_success_at": (
                    sub.coverage_success_at.isoformat()
                    if sub.coverage_success_at is not None
                    else None
                ),
                "has_covering_success": sub.coverage_success_at is not None,
            }
        )
    return {
        "subscriptions": rows,
        "any_covering_success": any(r["has_covering_success"] for r in rows),
        "all_covering_success": all(r["has_covering_success"] for r in rows) if rows else False,
    }


def clocks_declared() -> dict[str, int]:
    return {
        "work_deadline_seconds": WORK_DEADLINE_SECONDS,
        "request_deadline_seconds": REQUEST_DEADLINE_SECONDS,
        "cleanup_allowance_seconds": CLEANUP_ALLOWANCE_SECONDS,
        "attempt_validity_seconds": ATTEMPT_VALIDITY_SECONDS,
    }


def plan_receipt_fields(plan: AttemptPlan) -> dict[str, Any]:
    """Sanitized plan fields for receipts — no secrets."""
    return {
        "case_id": plan.case_id,
        "t_plan": plan.t_plan.isoformat(),
        "attempt_token_sha256_16": plan.attempt_token,
        "auth_channel": plan.auth_channel,
        "clocks": clocks_declared(),
    }


if __name__ == "__main__":
    raise SystemExit("HELD: np_auth_seed preparation only; no seeding or imports of app")
