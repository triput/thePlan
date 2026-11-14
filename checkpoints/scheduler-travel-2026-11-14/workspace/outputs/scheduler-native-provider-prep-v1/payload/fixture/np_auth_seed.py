"""Disposable tokens/settings and per-case planning for native-provider prep.

PREPARED ONLY. Fixture-only Fernet/session material — not live credentials.
Fresh planning per distinct predeclared attempt; 600s plan validity; no failed-attempt reseed/retry.
Actual request clocks when claimed: work 210 / request 240 / cleanup 30.
"""
from __future__ import annotations

import hashlib
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

# Synthetic OAuth settings — disposable labels only
FIXTURE_MS_CLIENT_ID = "fixture-ms-client-id"
FIXTURE_MS_CLIENT_SECRET = "fixture-ms-client-secret-not-live"
FIXTURE_MS_TENANT = "fixture-ms-tenant"
FIXTURE_MS_REDIRECT = "https://fixture.invalid/oauth/microsoft"
FIXTURE_GOOGLE_CLIENT_ID = "fixture-google-client-id"
FIXTURE_GOOGLE_CLIENT_SECRET = "fixture-google-client-secret-not-live"
FIXTURE_GOOGLE_REDIRECT = "https://fixture.invalid/oauth/google"


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
        "microsoft_client_secret_label": "fixture-ms-secret-label",
        "microsoft_tenant": FIXTURE_MS_TENANT,
        "microsoft_redirect_uri": FIXTURE_MS_REDIRECT,
        "token_encryption_key_label": "fixture-zero-fernet",
        "live_credentials": "false",
    }


def disposable_google_settings() -> dict[str, str]:
    return {
        "google_client_id": FIXTURE_GOOGLE_CLIENT_ID,
        "google_client_secret_label": "fixture-google-secret-label",
        "google_redirect_uri": FIXTURE_GOOGLE_REDIRECT,
        "token_encryption_key_label": "fixture-zero-fernet",
        "live_credentials": "false",
    }


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
