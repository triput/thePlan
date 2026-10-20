"""T1-E gate-level fixtures (E11–E13): ms_view provenance narrow.

Disposable Postgres only (theplan-t1a-postgres, 127.0.0.1:5433). No provider
calls — coverage columns are seeded directly. Sync-path cases E1–E10 / E14–E22
belong to Tesla's suite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.calendar_freshness import (
    evaluate_calendar_freshness,
    required_coverage_window,
)
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
_FERNET = Fernet.generate_key().decode("utf-8")


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["host_ip"] == "127.0.0.1"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        microsoft_client_id="t1e-ms-client",
        microsoft_client_secret="t1e-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _owner(db: Session, *, buffer_minutes: int = 15) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"t1e-gate-{token}@example.test",
        username=f"t1e_{token}",
        display_name="T1E gate",
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        session_epoch=0,
    )
    db.add(user)
    db.flush()
    settings = UserSettings(
        owner_id=user.id,
        timezone="UTC",
        workday_minutes=480,
        workday_start_local=time(8, 0),
        workweek_days=5,
        inter_block_buffer_minutes=buffer_minutes,
        upcoming_horizon_days=7,
        default_schedule_style=ScheduleStyle.standalone,
        scheduling_revision=0,
    )
    db.add(settings)
    db.flush()
    return user, settings


def _ms_account(db: Session, owner: User) -> CalendarAccount:
    cfg = _settings()
    account = CalendarAccount(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        account_email=f"t1e-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc=encrypt_token(cfg, "access-token"),
        refresh_token_enc=encrypt_token(cfg, "refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=False,
        last_synced_at=None,
    )
    db.add(account)
    db.flush()
    return account


def _ms_sub(
    db: Session,
    account: CalendarAccount,
    *,
    calendar_id: str = "ms-cal",
    summary: str = "Outlook",
) -> CalendarSubscription:
    row = CalendarSubscription(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary=summary,
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
        sync_cursor=None,
        provider_timezone="UTC",
    )
    db.add(row)
    db.flush()
    return row


def _seed_success(
    sub: CalendarSubscription,
    *,
    now: datetime,
    window_start: datetime,
    window_end: datetime,
    mode: str | None,
    generation: int = 1,
    pagination_complete: bool = True,
) -> None:
    sub.coverage_window_start = window_start
    sub.coverage_window_end = window_end
    sub.coverage_mode = mode
    sub.coverage_success_at = now
    sub.coverage_fetched_at = now
    sub.coverage_pagination_complete = pagination_complete
    sub.coverage_active_generation = generation
    sub.coverage_success_generation = generation
    # Google-only params stay null on MS mint.
    sub.coverage_show_deleted = None
    sub.coverage_single_events = None
    sub.coverage_page_count = 1
    sub.coverage_item_count = 0
    sub.coverage_token_fingerprint = None
    sub.coverage_last_failure_at = None
    sub.coverage_last_failure_cause = None


def _wide_bounds(settings: UserSettings, now: datetime) -> tuple[datetime, datetime]:
    start, end = required_coverage_window(settings, now)
    return start - timedelta(hours=2), end + timedelta(hours=2)


def _causes(trust: Any) -> set[str]:
    return {d.cause for d in trust.blocking_diagnostics}


def _trust(db: Session, owner: User, settings: UserSettings, now: datetime):
    return evaluate_calendar_freshness(db, owner.id, settings, now)


@pytest.mark.parametrize("mode", [None, "full", "delta", "google_full"])
def test_e11_populated_success_without_ms_view_stays_unverified(
    db_session: Session,
    mode: str | None,
) -> None:
    """E11: populated success fields without coverage_mode=ms_view stay unverified."""
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    _seed_success(
        sub,
        now=now,
        window_start=window_start,
        window_end=window_end,
        mode=mode,
    )
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert len(trust.blocking_diagnostics) == 1
    diag = trust.blocking_diagnostics[0]
    assert diag.cause == "microsoft_coverage_unverified"
    assert diag.provenance == "microsoft_success_minting_deferred"
    assert "incomplete" not in diag.cause
    assert "cursor" not in diag.cause
    # Must not diagnose incompleteness from missing delta cursor.
    blob = str(trust.to_dict()).lower()
    assert "no delta" not in blob
    assert "delta cursor" not in blob


def test_e12_valid_ms_view_passes_shared_checks(db_session: Session) -> None:
    """E12: valid ms_view mint within age/window/generation passes (no age/pad retune)."""
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    _seed_success(
        sub,
        now=now - timedelta(minutes=5),
        window_start=window_start,
        window_end=window_end,
        mode="ms_view",
    )
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is True
    assert trust.blocking_diagnostics == []


def test_e13_ms_view_stale_is_google_parity_cause(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    _seed_success(
        sub,
        now=now - timedelta(minutes=16),
        window_start=window_start,
        window_end=window_end,
        mode="ms_view",
    )
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert _causes(trust) == {"calendar_coverage_stale"}
    assert "microsoft_coverage_unverified" not in _causes(trust)
    for diag in trust.blocking_diagnostics:
        assert "delta" not in diag.cause
        assert "cursor" not in (diag.cause or "")
        assert diag.provenance is None or diag.provenance != "microsoft_success_minting_deferred"


def test_e13_ms_view_insufficient_window(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    req_start, req_end = required_coverage_window(settings, now)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    # Window too narrow on the right edge.
    _seed_success(
        sub,
        now=now - timedelta(minutes=2),
        window_start=req_start - timedelta(hours=1),
        window_end=req_end - timedelta(hours=2),
        mode="ms_view",
    )
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert _causes(trust) == {"calendar_coverage_window_insufficient"}
    assert "microsoft_coverage_unverified" not in _causes(trust)


def test_e13_ms_view_generation_mismatch(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    _seed_success(
        sub,
        now=now - timedelta(minutes=2),
        window_start=window_start,
        window_end=window_end,
        mode="ms_view",
        generation=1,
    )
    sub.coverage_active_generation = 2
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert _causes(trust) == {"calendar_coverage_generation_mismatch"}
    assert "microsoft_coverage_unverified" not in _causes(trust)


def test_e13_ms_view_pagination_incomplete(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    _seed_success(
        sub,
        now=now - timedelta(minutes=2),
        window_start=window_start,
        window_end=window_end,
        mode="ms_view",
        pagination_complete=False,
    )
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert _causes(trust) == {"calendar_pagination_incomplete"}
    assert "microsoft_coverage_unverified" not in _causes(trust)


def test_e13_ms_view_failure_sidecar_blocks(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    success_at = now - timedelta(minutes=2)
    _seed_success(
        sub,
        now=success_at,
        window_start=window_start,
        window_end=window_end,
        mode="ms_view",
    )
    db_session.flush()
    failure = CalendarSubscriptionRefreshFailure(
        id=uuid.uuid4(),
        subscription_id=sub.id,
        failure_at=success_at + timedelta(seconds=30),
        cause="calendar_refresh_failed",
    )
    db_session.add(failure)
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "calendar_refresh_failed" in _causes(trust)
    assert "microsoft_coverage_unverified" not in _causes(trust)
    for diag in trust.blocking_diagnostics:
        assert "delta" not in diag.cause.lower()
        assert "no delta cursor" not in str(diag.to_jsonable()).lower()


def test_e13_ms_view_missing_success_is_coverage_missing(db_session: Session) -> None:
    """ms_view mode with cleared success uses Google-parity missing, not unverified."""
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    account = _ms_account(db_session, owner)
    sub = _ms_sub(db_session, account)
    sub.coverage_mode = "ms_view"
    sub.coverage_success_at = None
    sub.coverage_pagination_complete = False
    sub.coverage_active_generation = 1
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert _causes(trust) == {"calendar_coverage_missing"}
    assert "microsoft_coverage_unverified" not in _causes(trust)


def test_expire_attrs_exclude_caller_edits() -> None:
    """Shared module must not expire summary/sync_cursor (T1-C regression contract)."""
    from app.services.calendar_refresh_failures import FAILURE_PERSIST_EXPIRE_ATTRS
    from app.services import google_calendar as gcal

    assert "summary" not in FAILURE_PERSIST_EXPIRE_ATTRS
    assert "sync_cursor" not in FAILURE_PERSIST_EXPIRE_ATTRS
    assert gcal._FAILURE_PERSIST_EXPIRE_ATTRS is FAILURE_PERSIST_EXPIRE_ATTRS
