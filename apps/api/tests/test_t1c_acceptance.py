"""T1-C synthetic acceptance (proposal §3 / T1-8, T1-9, T1-13).

Disposable Postgres only (theplan-t1a-postgres, 127.0.0.1:5433). No live
provider calls: Google/Microsoft HTTP is mocked. Collect and Apply are
gate-only — these tests fail if either initiates sync.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings
from app.db import engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    SchedulePreview,
    ScheduleRun,
    ScheduledBlock,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.busy_map import busy_from_sources, load_immovable_busy_sources
from app.scheduler import calendar_freshness as cal_fresh
from app.scheduler.calendar_freshness import (
    COVERAGE_SYNC_FETCH_HEADROOM,
    default_explicit_sync_window,
    evaluate_calendar_freshness,
    required_coverage_window,
)
from app.scheduler.collect import collect_inputs
from app.scheduler.preview_inputs import fingerprint_collected_inputs
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services.calendar_coverage import _subscription_locks
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
_FERNET = Fernet.generate_key().decode("utf-8")
_APPLY_NOW = datetime(2026, 10, 19, 18, 0, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["host_ip"] == "127.0.0.1"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


@pytest.fixture(autouse=True)
def _reset_pagination_knobs() -> None:
    gcal.pagination_max_pages = None
    gcal._pull_pagination_complete = True
    yield
    gcal.pagination_max_pages = None
    gcal._pull_pagination_complete = True


def _settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        google_client_id="t1c-test-client",
        google_client_secret="t1c-test-secret",
        google_redirect_uri="http://127.0.0.1/unused",
        microsoft_client_id="t1c-ms-client",
        microsoft_client_secret="t1c-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _owner(db: Session, *, buffer_minutes: int = 15) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"t1c-renee-{token}@example.test",
        username=f"t1c_{token}",
        display_name="T1C acceptance",
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


def _account(
    db: Session,
    owner: User,
    *,
    provider: CalendarProvider = CalendarProvider.google,
    email: str | None = None,
) -> CalendarAccount:
    cfg = _settings()
    account = CalendarAccount(
        owner_id=owner.id,
        provider=provider,
        account_email=email or f"t1c-{uuid.uuid4().hex[:8]}@example.test",
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


def _sub(
    db: Session,
    account: CalendarAccount,
    *,
    calendar_id: str,
    summary: str,
    enabled: bool = True,
    cursor: str | None = None,
) -> CalendarSubscription:
    row = CalendarSubscription(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary=summary,
        role=CalendarSubscriptionRole.primary,
        is_enabled=enabled,
        sync_cursor=cursor,
        provider_timezone="UTC",
    )
    db.add(row)
    db.flush()
    return row


def _patch_gcal_clock(monkeypatch: pytest.MonkeyPatch, fixed: datetime) -> None:
    class _FixedNow:
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed.astimezone(tz)
            return fixed

    monkeypatch.setattr(gcal, "datetime", _FixedNow)


def _mint(
    sub: CalendarSubscription,
    *,
    now: datetime,
    start: datetime,
    end: datetime,
    generation: int = 1,
) -> None:
    sub.coverage_window_start = start
    sub.coverage_window_end = end
    sub.coverage_mode = "full"
    sub.coverage_success_at = now
    sub.coverage_fetched_at = now
    sub.coverage_pagination_complete = True
    sub.coverage_active_generation = generation
    sub.coverage_success_generation = generation
    sub.coverage_show_deleted = True
    sub.coverage_single_events = True
    sub.coverage_page_count = 1
    sub.coverage_item_count = 0
    sub.coverage_token_fingerprint = "seeded"
    sub.coverage_last_failure_at = None
    sub.coverage_last_failure_cause = None


def _g_event(
    event_id: str,
    start: datetime,
    end: datetime,
    *,
    summary: str | None = None,
    status: str = "confirmed",
    recurring_event_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": event_id,
        "summary": summary or event_id,
        "status": status,
        "start": {"dateTime": start.astimezone(UTC).isoformat().replace("+00:00", "Z")},
        "end": {"dateTime": end.astimezone(UTC).isoformat().replace("+00:00", "Z")},
    }
    if recurring_event_id:
        body["recurringEventId"] = recurring_event_id
    return body


def _patch_lists(
    monkeypatch: pytest.MonkeyPatch,
    *,
    full: Any,
    incremental: Any | None = None,
) -> None:
    monkeypatch.setattr(gcal, "list_calendar_events", full)
    if incremental is not None:
        monkeypatch.setattr(gcal, "list_calendar_events_incremental", incremental)


def _trust(db: Session, owner: User, settings: UserSettings, now: datetime):
    return evaluate_calendar_freshness(db, owner.id, settings, now)


def _causes(trust) -> set[str]:
    return {d.cause for d in trust.blocking_diagnostics}


def _names(trust) -> set[str]:
    return {d.calendar_name for d in trust.blocking_diagnostics}


def _sync(db: Session, account: CalendarAccount, start: datetime, end: datetime) -> int:
    return gcal.sync_account_events(
        db,
        settings=_settings(),
        account=account,
        time_min=start,
        time_max=end,
    )


def _wide_bounds(settings: UserSettings, now: datetime) -> tuple[datetime, datetime]:
    start, end = required_coverage_window(settings, now)
    return start - timedelta(hours=2), end + timedelta(hours=2)


def _patch_google_httpx(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def _wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(_wrapped)
    real = httpx.Client

    def _factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(gcal.httpx, "Client", _factory)
    return seen


def _params(request: httpx.Request) -> dict[str, str]:
    return {key: values[-1] for key, values in parse_qs(urlparse(str(request.url)).query).items()}


def test_t1_8_token_refresh_is_not_fresh(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="cal-token", summary="Token Only")
    account.last_synced_at = now
    account.token_expires_at = now + timedelta(hours=4)
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "calendar_coverage_missing" in _causes(trust)
    assert "Token Only" in _names(trust)


def test_t1_8_age_exceeded_blocks(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    start, end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-age", summary="Aging")
    _mint(sub, now=now - timedelta(minutes=16), start=start, end=end)
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert _causes(trust) == {"calendar_coverage_stale"}
    assert "Aging" in _names(trust)


def test_t1_8_incomplete_right_edge_blocks(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    required_start, required_end = required_coverage_window(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-edge", summary="Short Edge")
    _mint(
        sub,
        now=now,
        start=required_start - timedelta(hours=1),
        end=required_end - timedelta(hours=1),
    )
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "calendar_coverage_window_insufficient" in _causes(trust)


def test_t1c_default_sync_window_ready_one_second_after_sync(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dex: gate-only required window moves with now; default sync must fetch headroom."""
    owner, settings = _owner(db_session)
    sync_now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    collect_now = sync_now + timedelta(seconds=1)
    _patch_gcal_clock(monkeypatch, sync_now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="dex-headroom", summary="Headroom")
    fetch_start, fetch_end = default_explicit_sync_window(settings, sync_now)

    monkeypatch.setattr(
        gcal, "list_calendar_events", lambda *_a, **_k: ([], "headroom-token", 1)
    )
    gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=fetch_start,
        time_max=fetch_end,
    )
    db_session.refresh(sub)
    assert sub.coverage_window_end.astimezone(UTC) == fetch_end
    assert fetch_end > required_coverage_window(settings, sync_now)[1]

    trust = evaluate_calendar_freshness(db_session, owner.id, settings, collect_now)
    assert trust.ok is True, _causes(trust)


def test_t1c_gate_only_window_without_headroom_fails_one_second_later(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    sync_now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    collect_now = sync_now + timedelta(seconds=1)
    _patch_gcal_clock(monkeypatch, sync_now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="dex-narrow", summary="Narrow Fetch")
    gate_start, gate_end = required_coverage_window(settings, sync_now)

    monkeypatch.setattr(
        gcal, "list_calendar_events", lambda *_a, **_k: ([], "narrow-token", 1)
    )
    gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=gate_start,
        time_max=gate_end,
    )
    db_session.refresh(sub)

    trust = evaluate_calendar_freshness(db_session, owner.id, settings, collect_now)
    assert trust.ok is False
    assert "calendar_coverage_window_insufficient" in _causes(trust)


def test_t1c_default_sync_window_insufficient_beyond_fetch_headroom(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    sync_now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    _patch_gcal_clock(monkeypatch, sync_now)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="dex-edge", summary="Fetch Edge")
    fetch_start, fetch_end = default_explicit_sync_window(settings, sync_now)

    monkeypatch.setattr(
        gcal, "list_calendar_events", lambda *_a, **_k: ([], "edge-token", 1)
    )
    gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=fetch_start,
        time_max=fetch_end,
    )

    # Headroom equals the age ceiling; roll collect past fetch headroom without
    # hitting stale first so this case stays window-insufficient, not age-blocked.
    monkeypatch.setattr(cal_fresh, "FRESHNESS_AGE_CEILING", timedelta(hours=1))
    beyond = sync_now + COVERAGE_SYNC_FETCH_HEADROOM + timedelta(seconds=1)
    trust = evaluate_calendar_freshness(db_session, owner.id, settings, beyond)
    assert trust.ok is False
    assert "calendar_coverage_window_insufficient" in _causes(trust)


def test_t1c_auth_failure_with_young_prior_marker_persists_after_rollback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    mint_now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    sync_now = mint_now + timedelta(seconds=1)
    gate_start, gate_end = required_coverage_window(settings, mint_now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="dex-auth", summary="Auth Fail")
    prior_cursor = "stable-cursor"
    sub.sync_cursor = prior_cursor
    _mint(
        sub,
        now=mint_now,
        start=gate_start - timedelta(days=1),
        end=gate_end + timedelta(days=1),
    )
    db_session.flush()
    sub_id = sub.id
    owner_id = owner.id

    _patch_gcal_clock(monkeypatch, sync_now)
    monkeypatch.setattr(
        gcal,
        "get_valid_access_token",
        lambda *_a, **_k: (_ for _ in ()).throw(
            ApiError(502, "Synthetic auth failure", "SYNTHETIC_AUTH")
        ),
    )

    with pytest.raises(ApiError):
        gcal.sync_account_events(
            db_session,
            settings=_settings(),
            account=account,
            time_min=gate_start,
            time_max=gate_end,
        )

    db_session.rollback()
    db_session.expire_all()
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    sub = db_session.get(CalendarSubscription, sub_id)
    assert sub is not None
    assert sub.sync_cursor == prior_cursor
    assert sub.coverage_last_failure_at is not None
    assert sub.coverage_last_failure_cause == "calendar_refresh_failed"
    trust = evaluate_calendar_freshness(db_session, owner_id, settings, sync_now)
    assert trust.ok is False
    assert "Auth Fail" in _names(trust)


def test_t1c_token_refresh_transport_failure_persists_after_rollback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    mint_now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    sync_now = mint_now + timedelta(seconds=1)
    gate_start, gate_end = required_coverage_window(settings, mint_now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="dex-transport", summary="Token Timeout")
    prior_cursor = "stable-cursor"
    sub.sync_cursor = prior_cursor
    _mint(
        sub,
        now=mint_now,
        start=gate_start - timedelta(days=1),
        end=gate_end + timedelta(days=1),
    )
    account.token_expires_at = mint_now - timedelta(minutes=1)
    db_session.flush()
    sub_id = sub.id
    owner_id = owner.id

    _patch_gcal_clock(monkeypatch, sync_now)
    monkeypatch.setattr(
        gcal,
        "refresh_access_token",
        lambda *_a, **_k: (_ for _ in ()).throw(httpx.ReadTimeout("Synthetic token timeout")),
    )

    with pytest.raises(httpx.ReadTimeout):
        gcal.sync_account_events(
            db_session,
            settings=_settings(),
            account=account,
            time_min=gate_start,
            time_max=gate_end,
        )

    db_session.rollback()
    db_session.expire_all()
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    sub = db_session.get(CalendarSubscription, sub_id)
    assert sub is not None
    assert sub.sync_cursor == prior_cursor
    assert sub.coverage_last_failure_at is not None
    assert sub.coverage_last_failure_cause == "calendar_refresh_failed"
    trust = evaluate_calendar_freshness(db_session, owner_id, settings, sync_now)
    assert trust.ok is False
    assert "Token Timeout" in _names(trust)


def test_t1c_pre_pull_failure_does_not_commit_unrelated_caller_transaction(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """google_oauth_callback pattern: failure markers persist; caller tx rolls back."""
    owner, settings = _owner(db_session)
    mint_now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    sync_now = mint_now + timedelta(seconds=1)
    gate_start, gate_end = required_coverage_window(settings, mint_now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="dex-oauth-tx", summary="OAuth Tx")
    prior_cursor = "oauth-cursor"
    sub.sync_cursor = prior_cursor
    _mint(
        sub,
        now=mint_now,
        start=gate_start - timedelta(days=1),
        end=gate_end + timedelta(days=1),
    )
    cfg = _settings()
    prior_token = account.access_token_enc
    prior_display = owner.display_name
    owner_id = owner.id
    account_id = account.id
    sub_id = sub.id

    db_session.flush()

    owner.display_name = "MUST NOT COMMIT WITH FAILURE"
    account.access_token_enc = encrypt_token(cfg, "oauth-pending-access")
    account.token_expires_at = mint_now - timedelta(minutes=1)

    _patch_gcal_clock(monkeypatch, sync_now)
    monkeypatch.setattr(
        gcal,
        "refresh_access_token",
        lambda *_a, **_k: (_ for _ in ()).throw(httpx.ReadTimeout("Synthetic token timeout")),
    )

    with pytest.raises(httpx.ReadTimeout):
        gcal.sync_account_events(
            db_session,
            settings=cfg,
            account=account,
            time_min=gate_start,
            time_max=gate_end,
        )

    db_session.rollback()
    db_session.expire_all()

    owner = db_session.get(User, owner_id)
    account = db_session.get(CalendarAccount, account_id)
    sub = db_session.get(CalendarSubscription, sub_id)
    assert owner is not None
    assert account is not None
    assert sub is not None
    assert owner.display_name == prior_display
    assert account.access_token_enc == prior_token
    assert sub.sync_cursor == prior_cursor
    assert sub.coverage_last_failure_at is not None
    assert sub.coverage_last_failure_cause == "calendar_refresh_failed"


def test_t1_8_pagination_flag_false_blocks_even_if_young(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    start, end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-page", summary="Truncated Flag")
    _mint(sub, now=now, start=start, end=end)
    sub.coverage_pagination_complete = False
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "calendar_pagination_incomplete" in _causes(trust)


def test_t1c_generation_mismatch_blocks(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    start, end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-gen", summary="Split Gen")
    _mint(sub, now=now, start=start, end=end, generation=2)
    sub.coverage_active_generation = 3
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "calendar_coverage_generation_mismatch" in _causes(trust)


def test_t1_8_covering_sync_drains_pages_and_keeps_overlap(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal/overlap", summary="Overlap")
    inside = window_start + timedelta(hours=3)
    overlap = _g_event(
        "overlap-before",
        window_start - timedelta(hours=2),
        window_start + timedelta(hours=1),
        summary="Started before timeMin",
    )
    later = _g_event("page-two", inside, inside + timedelta(hours=1), summary="Second page")

    def _handler(request: httpx.Request) -> httpx.Response:
        params = _params(request)
        assert params.get("singleEvents") == "true"
        assert params.get("showDeleted") == "true"
        assert "timeMin" in params and "timeMax" in params
        assert "syncToken" not in params
        if params.get("pageToken") == "page-2":
            return httpx.Response(200, json={"items": [later], "nextSyncToken": "sync-complete"})
        return httpx.Response(200, json={"items": [overlap], "nextPageToken": "page-2"})

    _patch_google_httpx(monkeypatch, _handler)
    _sync(db_session, account, window_start, window_end)
    db_session.refresh(sub)

    assert sub.coverage_success_at is not None
    assert sub.coverage_pagination_complete is True
    assert sub.coverage_show_deleted is True
    assert sub.coverage_single_events is True
    assert sub.coverage_mode == "full"
    assert sub.sync_cursor == "sync-complete"
    assert sub.coverage_success_generation == sub.coverage_active_generation
    assert sub.coverage_window_start is not None and sub.coverage_window_end is not None

    rows = {
        row.external_event_id: row
        for row in db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.owner_id == owner.id)
        .all()
    }
    assert "overlap-before" in rows
    assert rows["overlap-before"].start_time < window_start
    assert rows["overlap-before"].end_time > window_start
    assert "page-two" in rows

    _pins, events = load_immovable_busy_sources(db_session, owner.id)
    busy = busy_from_sources(events=events, pinned=_pins)
    assert any(item.source == "external" and item.start < window_start for item in busy)

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is True
    assert trust.blocking_diagnostics == []


def test_t1_8_truncated_page_does_not_mint_or_advance_cursor(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(
        db_session,
        account,
        calendar_id="cal-trunc",
        summary="Truncated",
        cursor="old-cursor",
    )
    _mint(sub, now=now, start=window_start, end=window_end)
    sub.sync_cursor = "old-cursor"
    db_session.flush()

    def _handler(request: httpx.Request) -> httpx.Response:
        params = _params(request)
        if params.get("pageToken") == "page-2":
            return httpx.Response(
                200, json={"items": [_g_event("secret", window_start, window_end)], "nextSyncToken": "should-not-store"}
            )
        return httpx.Response(
            200,
            json={
                "items": [_g_event("partial", window_start + timedelta(hours=1), window_start + timedelta(hours=2))],
                "nextPageToken": "page-2",
                "nextSyncToken": "partial-token-ignored",
            },
        )

    _patch_google_httpx(monkeypatch, _handler)
    gcal.pagination_max_pages = 1
    with pytest.raises(ApiError) as raised:
        _sync(db_session, account, window_start, window_end)
    assert raised.value.content["code"] == "CALENDAR_PAGINATION_INCOMPLETE"

    db_session.expire_all()
    sub = db_session.get(CalendarSubscription, sub.id)
    assert sub is not None
    assert sub.sync_cursor in (None, "old-cursor")
    assert sub.sync_cursor != "should-not-store"
    assert sub.sync_cursor != "partial-token-ignored"
    assert sub.coverage_success_at is None or (
        sub.coverage_last_failure_at is not None
        and sub.coverage_last_failure_at > sub.coverage_success_at
    )
    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "Truncated" in _names(trust)
    assert "calendar_coverage_stale" not in _causes(trust)
    cached = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id.in_(["partial", "secret"]))
        .count()
    )
    assert cached == 0


def test_t1c_mid_refresh_write_then_fail_is_not_ready(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-mid", summary="Mid Refresh", cursor=None)
    _mint(sub, now=now, start=window_start, end=window_end)
    prior_success = sub.coverage_success_at
    db_session.flush()
    writes = {"n": 0}
    real = gcal._upsert_external_event

    def _write_then_fail(*args: Any, **kwargs: Any) -> bool:
        writes["n"] += 1
        real(*args, **kwargs)
        raise RuntimeError("mid-refresh injected")

    monkeypatch.setattr(gcal, "_upsert_external_event", _write_then_fail)

    def _full(*_a: Any, **_k: Any):
        return (
            [_g_event("new-evt", window_start + timedelta(hours=4), window_start + timedelta(hours=5))],
            "cursor-should-not-advance",
            1,
        )

    _patch_lists(monkeypatch, full=_full)
    with pytest.raises(RuntimeError, match="mid-refresh injected"):
        _sync(db_session, account, window_start, window_end)

    assert writes["n"] >= 1
    db_session.expire_all()
    sub = db_session.get(CalendarSubscription, sub.id)
    assert sub is not None
    assert sub.sync_cursor != "cursor-should-not-advance"
    assert sub.coverage_success_at != prior_success or sub.coverage_last_failure_at is not None
    assert sub.coverage_last_failure_cause
    assert "token" not in (sub.coverage_last_failure_cause or "")
    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "Mid Refresh" in _names(trust)


def test_t1c_failed_attempt_stays_unready_after_rollback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback may restore a consistent cache; it must not restore readiness."""
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-rollback", summary="Rollback")
    _mint(sub, now=now, start=window_start, end=window_end)
    db_session.flush()
    sub_id = sub.id
    owner_id = owner.id
    real = gcal._upsert_external_event

    def _write_then_fail(*args: Any, **kwargs: Any) -> bool:
        real(*args, **kwargs)
        raise RuntimeError("rollback case")

    monkeypatch.setattr(gcal, "_upsert_external_event", _write_then_fail)

    def _full(*_a: Any, **_k: Any):
        return (
            [_g_event("rolled-evt", window_start + timedelta(hours=4), window_start + timedelta(hours=5))],
            "nope",
            1,
        )

    _patch_lists(monkeypatch, full=_full)
    with pytest.raises(RuntimeError, match="rollback case"):
        _sync(db_session, account, window_start, window_end)

    db_session.rollback()
    db_session.expire_all()
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    sub = db_session.get(CalendarSubscription, sub_id)
    assert sub is not None
    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "Rollback" in _names(trust)
    young_success_still_validates = (
        sub.coverage_success_at is not None
        and (sub.coverage_last_failure_at is None or sub.coverage_last_failure_at <= sub.coverage_success_at)
        and sub.coverage_pagination_complete
        and sub.coverage_success_generation == sub.coverage_active_generation
    )
    assert young_success_still_validates is False


def test_t1c_refresh_entry_points_are_serialized(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-serial", summary="Serial")
    db_session.flush()
    sub_id = sub.id
    release = threading.Event()
    entered = threading.Event()
    result: dict[str, bool] = {}

    def _other() -> None:
        assert entered.wait(3)
        lock = _subscription_locks[sub_id]
        acquired = lock.acquire(blocking=False)
        result["other_acquired"] = acquired
        if acquired:
            lock.release()
        release.set()

    def _full(*_a: Any, **_k: Any):
        assert _subscription_locks[sub_id].locked()
        entered.set()
        assert release.wait(3)
        return (
            [_g_event("serial-evt", window_start + timedelta(hours=1), window_start + timedelta(hours=2))],
            "serial-cursor",
            1,
        )

    threading.Thread(target=_other, daemon=True).start()
    _patch_lists(monkeypatch, full=_full)
    _sync(db_session, account, window_start, window_end)
    assert result["other_acquired"] is False
    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is True


def test_t1_9_one_failed_subscription_blocks_despite_sibling_success(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="alive-cal", summary="Alive Calendar")
    _sub(db_session, account, calendar_id="dead-cal", summary="Dead Calendar")
    db_session.flush()

    def _full(_access: str, calendar_id: str, *, time_min: datetime, time_max: datetime):
        if calendar_id == "dead-cal":
            raise ApiError(502, "subscription exploded", "GOOGLE_EVENTS_LIST")
        start = time_min + timedelta(hours=2)
        return ([_g_event("alive-evt", start, start + timedelta(minutes=30))], "alive-token", 1)

    _patch_lists(monkeypatch, full=_full)
    with pytest.raises(ApiError):
        _sync(db_session, account, window_start, window_end)

    db_session.expire_all()
    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert "Dead Calendar" in _names(trust)
    dead = next(d for d in trust.blocking_diagnostics if d.calendar_name == "Dead Calendar")
    assert dead.cause
    assert dead.blocking_current_proposal is True
    blob = str(trust.to_dict()).lower()
    assert "alive calendar" not in blob or trust.ok is False


def test_t1_9_diagnostic_has_recovery_hint(db_session: Session) -> None:
    """Proposal §1.1.6 / T1-9: calendar name + cause + recovery hint."""
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-hint", summary="Needs Hint")
    sub.coverage_last_failure_at = now
    sub.coverage_last_failure_cause = "google_subscription_refresh_failed"
    db_session.flush()

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    diag = trust.blocking_diagnostics[0]
    payload = diag.to_jsonable()
    assert payload["calendar_name"] == "Needs Hint"
    assert payload["cause"] == "google_subscription_refresh_failed"
    assert payload.get("recovery") or payload.get("recovery_hint")


def test_t1c_apply_rejects_aged_replay_without_writes_or_rejuvenation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.schedule_preview_apply import apply_schedule_preview

    owner, settings = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-apply", summary="Apply Age")
    coverage_start = _APPLY_NOW - timedelta(days=10)
    coverage_end = _APPLY_NOW + timedelta(days=40)
    _mint(sub, now=_APPLY_NOW, start=coverage_start, end=coverage_end)
    db_session.flush()

    inputs = collect_inputs(db_session, owner.id, _APPLY_NOW)
    snapshot, digest = fingerprint_collected_inputs(inputs)
    aged = _APPLY_NOW - timedelta(minutes=16)
    sub.coverage_success_at = aged
    sub.coverage_fetched_at = aged
    db_session.flush()

    block_start = _APPLY_NOW + timedelta(days=2)
    preview = SchedulePreview(
        owner_id=owner.id,
        status="ready",
        scheduling_revision=int(settings.scheduling_revision),
        input_fingerprint=digest,
        input_snapshot=snapshot,
        proposal_json={
            "proposed_blocks": [
                {
                    "task_id": str(uuid.uuid4()),
                    "start_time": block_start.isoformat(),
                    "end_time": (block_start + timedelta(hours=1)).isoformat(),
                }
            ]
        },
    )
    db_session.add(preview)
    db_session.flush()

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            if tz is None:
                return _APPLY_NOW.replace(tzinfo=None)
            return _APPLY_NOW.astimezone(tz)

    monkeypatch.setattr("app.services.schedule_preview_apply.datetime", _Frozen)

    def _no_sync(*_a: Any, **_k: Any) -> int:
        raise AssertionError("Apply initiated provider sync")

    monkeypatch.setattr(gcal, "sync_account_events", _no_sync)
    monkeypatch.setattr(ms_cal, "sync_account_events", _no_sync)

    runs_before = db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner.id).count()
    blocks_before = db_session.query(ScheduledBlock).filter(ScheduledBlock.owner_id == owner.id).count()

    with pytest.raises(ApiError) as raised:
        apply_schedule_preview(db_session, owner, preview)
    assert raised.value.content["code"] == "CALENDAR_FRESHNESS"
    body = raised.value.content["calendar_freshness_trust"]
    assert body["ok"] is False
    assert any(row["cause"] == "calendar_coverage_stale" for row in body["blocking_diagnostics"])

    db_session.refresh(sub)
    assert sub.coverage_success_at.astimezone(UTC) == aged
    assert sub.coverage_fetched_at.astimezone(UTC) == aged
    assert db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner.id).count() == runs_before
    assert db_session.query(ScheduledBlock).filter(ScheduledBlock.owner_id == owner.id).count() == blocks_before
    assert preview.status != "applied"


def test_t1c_collect_does_not_initiate_sync(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="cal-stale", summary="Stale Collect")
    db_session.flush()
    calls = {"n": 0}

    def _no_sync(*_a: Any, **_k: Any) -> int:
        calls["n"] += 1
        raise AssertionError("collect initiated provider sync")

    monkeypatch.setattr(gcal, "sync_account_events", _no_sync)
    monkeypatch.setattr(ms_cal, "sync_account_events", _no_sync)
    monkeypatch.setattr(gcal, "list_calendar_events", _no_sync)
    monkeypatch.setattr(ms_cal, "list_calendar_events", _no_sync)

    inputs = collect_inputs(db_session, owner.id, now)
    assert calls["n"] == 0
    assert inputs.calendar_freshness_trust is not None
    assert inputs.calendar_freshness_trust.ok is False
    assert settings.owner_id == owner.id


def test_t1c_google_incremental_omits_forbidden_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, str]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(_params(request))
        return httpx.Response(200, json={"items": [], "nextSyncToken": "next"})

    _patch_google_httpx(monkeypatch, _handler)
    gcal.list_calendar_events_incremental("tok", "cal-incr", "sync-abc")
    assert seen
    params = seen[-1]
    assert params.get("syncToken") == "sync-abc"
    assert params.get("singleEvents") == "true"
    for forbidden in ("timeMin", "timeMax", "q", "orderBy", "updatedMin"):
        assert forbidden not in params


def test_t1c_410_remints_full_baseline_and_failed_baseline_stays_unready(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-410", summary="Gone", cursor="stale-token")
    _mint(sub, now=now, start=window_start, end=window_end)
    sub.sync_cursor = "stale-token"
    db_session.flush()
    phase = {"full_fail": False, "incr": 0, "full": 0}

    def _incr(*_a: Any, **_k: Any):
        phase["incr"] += 1
        raise gcal.GoogleSyncTokenExpired()

    def _full(*_a: Any, **_k: Any):
        phase["full"] += 1
        if phase["full_fail"]:
            raise ApiError(502, "baseline failed", "GOOGLE_EVENTS_LIST")
        start = window_start + timedelta(hours=2)
        return ([_g_event("after-410", start, start + timedelta(minutes=45))], "baseline-new", 1)

    _patch_lists(monkeypatch, full=_full, incremental=_incr)
    _sync(db_session, account, window_start, window_end)
    db_session.refresh(sub)
    assert phase["incr"] == 1
    assert phase["full"] == 1
    assert sub.sync_cursor == "baseline-new"
    assert sub.sync_cursor != "stale-token"
    assert sub.coverage_success_at is not None
    assert _trust(db_session, owner, settings, now).ok is True

    phase["full_fail"] = True
    sub.sync_cursor = "will-410"
    db_session.flush()
    with pytest.raises(ApiError):
        _sync(db_session, account, window_start, window_end)
    db_session.expire_all()
    sub = db_session.get(CalendarSubscription, sub.id)
    assert sub is not None
    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    assert sub.sync_cursor != "will-410"


def test_t1c_widened_horizon_remints_on_explicit_sync_only(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    narrow_start, narrow_end = required_coverage_window(settings, now)
    wide_start = narrow_start - timedelta(days=3)
    wide_end = narrow_end + timedelta(days=3)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-wide", summary="Widen")
    calls = {"incr": 0, "full": 0}

    def _full(*_a: Any, **_k: Any):
        calls["full"] += 1
        token = "narrow-token" if calls["full"] == 1 else "wide-token"
        return ([], token, 1)

    def _incr(*_a: Any, **_k: Any):
        calls["incr"] += 1
        return ([], "incremental-token", 1)

    real_sync = gcal.sync_account_events
    _patch_lists(monkeypatch, full=_full, incremental=_incr)
    _sync(db_session, account, narrow_start, narrow_end)
    db_session.refresh(sub)
    assert sub.sync_cursor == "narrow-token"
    assert calls["incr"] == 0

    def _no_collect_sync(*_a: Any, **_k: Any) -> int:
        raise AssertionError("collect initiated sync after widen")

    # Widen is a requirement on the next explicit sync, not on collect.
    monkeypatch.setattr(gcal, "sync_account_events", _no_collect_sync)
    inputs = collect_inputs(db_session, owner.id, now)
    assert inputs.calendar_freshness_trust is not None
    # Stored window matches the default padded horizon, so collect stays ready.
    # The wider bounds are applied only by the explicit sync below.
    assert inputs.calendar_freshness_trust.ok is True
    monkeypatch.setattr(gcal, "sync_account_events", real_sync)

    _sync(db_session, account, wide_start, wide_end)
    db_session.refresh(sub)
    assert calls["incr"] == 0
    assert sub.sync_cursor == "wide-token"
    assert sub.coverage_window_start.astimezone(UTC) == wide_start
    assert sub.coverage_window_end.astimezone(UTC) == wide_end
    assert sub.coverage_mode == "full"


def test_t1_13_incremental_churn_updates_cache(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="cal-churn", summary="Churn")
    original_start = window_start + timedelta(hours=5)
    moved_start = original_start + timedelta(hours=2)
    phase = {"n": 0}

    def _full(*_a: Any, **_k: Any):
        phase["n"] += 1
        return (
            [_g_event("appt", original_start, original_start + timedelta(hours=1), summary="Original")],
            "cursor-1",
            1,
        )

    def _incr(*_a: Any, **_k: Any):
        phase["n"] += 1
        return (
            [
                _g_event("appt", moved_start, moved_start + timedelta(hours=1), summary="Moved"),
                _g_event("appt-new", moved_start + timedelta(hours=3), moved_start + timedelta(hours=4), summary="Added"),
            ],
            "cursor-2",
            1,
        )

    _patch_lists(monkeypatch, full=_full, incremental=_incr)
    _sync(db_session, account, window_start, window_end)
    _sync(db_session, account, window_start, window_end)
    rows = {
        row.external_event_id: row
        for row in db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.owner_id == owner.id)
        .all()
    }
    assert rows["appt"].title == "Moved"
    assert rows["appt"].start_time.astimezone(UTC) == moved_start
    assert "appt-new" in rows
    assert _trust(db_session, owner, settings, now).ok is True
    assert phase["n"] == 2


def test_t1c_cancellation_is_not_pending_deletion_and_exception_kept(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-cancel", summary="Cancel")
    kept_start = window_start + timedelta(hours=6)
    cancel_start = window_start + timedelta(hours=8)
    phase = {"n": 0}

    def _full(*_a: Any, **_k: Any):
        phase["n"] += 1
        if phase["n"] == 1:
            return (
                [
                    _g_event(
                        "exception-occ",
                        kept_start,
                        kept_start + timedelta(hours=1),
                        summary="Exception",
                        recurring_event_id="series-9",
                    ),
                    _g_event("will-cancel", cancel_start, cancel_start + timedelta(minutes=30), summary="Doomed"),
                ],
                "cursor-a",
                1,
            )
        return (
            [
                _g_event(
                    "exception-occ",
                    kept_start,
                    kept_start + timedelta(hours=1),
                    summary="Exception",
                    recurring_event_id="series-9",
                ),
                _g_event(
                    "will-cancel",
                    cancel_start,
                    cancel_start + timedelta(minutes=30),
                    status="cancelled",
                ),
            ],
            "cursor-b",
            1,
        )

    _patch_lists(monkeypatch, full=_full, incremental=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("full path")))
    _sync(db_session, account, window_start, window_end)
    sub.sync_cursor = None
    db_session.flush()
    _sync(db_session, account, window_start, window_end)

    rows = {
        row.external_event_id: row
        for row in db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.owner_id == owner.id)
        .all()
    }
    assert rows["exception-occ"].provider_series_id == "series-9"
    assert rows["exception-occ"].is_provider_cancelled is False
    cancelled = rows["will-cancel"]
    assert cancelled.is_provider_cancelled is True
    assert cancelled.pending_deletion is False
    _pins, events = load_immovable_busy_sources(db_session, owner.id)
    busy_ids = {event.external_event_id for event in events}
    assert "will-cancel" not in busy_ids
    assert "exception-occ" in busy_ids
    assert settings.upcoming_horizon_days == 7


def test_t1c_incremental_cancellation_keeps_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _settings_row = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(_settings_row, now)
    account = _account(db_session, owner)
    start = window_start + timedelta(hours=4)
    phase = {"n": 0}

    def _full(*_a: Any, **_k: Any):
        return ([_g_event("remote-gone", start, start + timedelta(hours=1), summary="There")], "c1", 1)

    def _incr(*_a: Any, **_k: Any):
        phase["n"] += 1
        return (
            [_g_event("remote-gone", start, start + timedelta(hours=1), status="cancelled")],
            "c2",
            1,
        )

    _patch_lists(monkeypatch, full=_full, incremental=_incr)
    _sync(db_session, account, window_start, window_end)
    _sync(db_session, account, window_start, window_end)
    row = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == "remote-gone")
        .one()
    )
    assert row.is_provider_cancelled is True
    assert row.pending_deletion is False
    assert phase["n"] == 1


def test_t1c_microsoft_unverified_blocks_and_does_not_mint(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft)
    sub = _sub(db_session, account, calendar_id="ms-cal", summary="Outlook")
    db_session.flush()

    monkeypatch.setattr(ms_cal, "get_valid_access_token", lambda *_a, **_k: "ms-access")

    def _delta(*_a: Any, **_k: Any):
        raise ms_cal.MicrosoftDeltaExpired()

    def _view(*_a: Any, **_k: Any):
        return [
            {
                "id": "ms-evt",
                "subject": "Graph block",
                "start": {"dateTime": "2026-10-20T15:00:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-10-20T16:00:00", "timeZone": "UTC"},
            }
        ]

    monkeypatch.setattr(ms_cal, "list_calendar_events", _delta)
    monkeypatch.setattr(ms_cal, "list_calendar_view", _view)
    ms_cal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=window_start,
        time_max=window_end,
    )
    db_session.refresh(sub)
    db_session.refresh(account)
    assert sub.coverage_success_at is None
    assert sub.coverage_success_generation is None
    assert sub.coverage_pagination_complete is False
    assert account.last_synced_at is not None

    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is False
    diag = trust.blocking_diagnostics[0]
    assert diag.cause == "microsoft_coverage_unverified"
    assert diag.provenance == "microsoft_success_minting_deferred"
    blob = str(trust.to_dict()).lower()
    assert "delta" not in blob
    assert "incomplete" not in diag.cause


def test_t1c_disabled_subscription_does_not_block(db_session: Session) -> None:
    owner, settings = _owner(db_session)
    now = datetime.now(UTC)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="cal-off", summary="Disabled", enabled=False)
    db_session.flush()
    trust = _trust(db_session, owner, settings, now)
    assert trust.ok is True
