"""T1-12 evidence — legacy null/null free/busy on production sync path (L1–L3, L-MS1).

Grounding checkout at implementation start: feature/0.7-s2-cutover @ dc0701d.
Dex unlock 2026-10-20: L1+L2+L3+L-MS1 mandatory; real sync_account_events only;
NULL storage until upsert; L2 bounded skip + collect trust + later resolve step.
Disposable Postgres only (T1A_REQUIRE_DISPOSABLE_DSN=1); provider HTTP mocked.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.calendar_freshness import evaluate_calendar_freshness
from app.scheduler.collect import collect_inputs
from app.scheduler.free_busy import (
    BusyInputTrustError,
    evaluate_busy_input_trust,
    events_for_busy_merge,
    require_busy_input_trust,
)
from app.scheduler.horizon import compute_horizon
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
_T1_12_START_SHA = "dc0701db083d3a0b2ea90b1f6b374e5ba4aae598"
_FERNET = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode(
    "utf-8"
)
_NOW = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
_LEGACY_EVENT_ID = "evt-legacy-k8s-1"
# Test-local observation only (Track-1-Contracts §4.1); not a provider guarantee.
_NOT_IN_BATCH_STATUS = "not_in_provider_batch"


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


@pytest.fixture(autouse=True)
def _reset_gcal_pagination() -> None:
    gcal.pagination_max_pages = None
    gcal._pull_pagination_complete = True
    yield
    gcal.pagination_max_pages = None
    gcal._pull_pagination_complete = True


def test_t1_12_start_sha_is_ancestor_of_tip() -> None:
    tip = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(["git", "merge-base", "--is-ancestor", _T1_12_START_SHA, tip])


def _settings(*, include_google: bool = True, include_ms: bool = False) -> Settings:
    kwargs: dict[str, Any] = {"token_encryption_key": _FERNET}
    if include_google:
        kwargs.update(
            google_client_id="t1-12-g",
            google_client_secret="t1-12-g-secret",
            google_redirect_uri="http://127.0.0.1/unused-g",
        )
    if include_ms:
        kwargs.update(
            microsoft_client_id="t1-12-ms",
            microsoft_client_secret="t1-12-ms-secret",
            microsoft_redirect_uri="http://127.0.0.1/unused-ms",
        )
    return Settings(**kwargs)


def _owner(db: Session) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"t1-12-{token}@example.test",
        username=f"t1_12_{token}",
        display_name="T1-12",
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
        inter_block_buffer_minutes=15,
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
    provider: CalendarProvider,
    calendar_id: str,
) -> CalendarAccount:
    cfg = _settings(
        include_google=provider == CalendarProvider.google,
        include_ms=provider == CalendarProvider.microsoft,
    )
    account = CalendarAccount(
        owner_id=owner.id,
        provider=provider,
        account_email=f"t1-12-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc=encrypt_token(cfg, "access"),
        refresh_token_enc=encrypt_token(cfg, "refresh"),
        token_expires_at=_NOW + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(account)
    db.flush()
    db.add(
        CalendarSubscription(
            owner_id=owner.id,
            calendar_account_id=account.id,
            external_calendar_id=calendar_id,
            summary="Primary",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
            provider_timezone="UTC",
        )
    )
    db.flush()
    return account


def _sub(db: Session, account: CalendarAccount) -> CalendarSubscription:
    return (
        db.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .one()
    )


def _event_bounds() -> tuple[datetime, datetime]:
    start = _NOW + timedelta(days=1)
    return start, start + timedelta(hours=1)


def _seed_legacy_row(
    db: Session,
    *,
    owner: User,
    account: CalendarAccount,
    calendar_id: str,
    external_id: str = _LEGACY_EVENT_ID,
    provider: CalendarProvider = CalendarProvider.google,
) -> ExternalCalendarEvent:
    start, end = _event_bounds()
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        provider=provider,
        external_event_id=external_id,
        calendar_id=calendar_id,
        title="Pre-034 legacy cache",
        start_time=start,
        end_time=end,
        is_all_day=False,
        last_synced_at=_NOW - timedelta(days=30),
        transparency=None,
        free_busy_provenance=None,
        free_busy_change_history=None,
        free_busy_sync_run_id=None,
        source_zone_missing=False,
        source_timezone="UTC",
    )
    db.add(row)
    db.flush()
    return row


def _mint_incremental_ready(sub: CalendarSubscription, *, window_start: datetime, window_end: datetime) -> None:
    sub.sync_cursor = "sync-token-v1"
    sub.coverage_window_start = window_start
    sub.coverage_window_end = window_end
    sub.coverage_mode = "full"
    sub.coverage_success_at = _NOW - timedelta(hours=2)
    sub.coverage_fetched_at = _NOW - timedelta(hours=2)
    sub.coverage_pagination_complete = True
    sub.coverage_active_generation = 1
    sub.coverage_success_generation = 1
    sub.coverage_show_deleted = True
    sub.coverage_single_events = True
    sub.coverage_page_count = 1
    sub.coverage_item_count = 0
    sub.coverage_token_fingerprint = "seeded"


def _g_event_body(
    external_id: str,
    start: datetime,
    end: datetime,
    *,
    transparency: str | None = "__present__",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": external_id,
        "summary": "Legacy revisit",
        "status": "confirmed",
        "start": {"dateTime": start.astimezone(UTC).isoformat().replace("+00:00", "Z")},
        "end": {"dateTime": end.astimezone(UTC).isoformat().replace("+00:00", "Z")},
    }
    if transparency != "__present__":
        if transparency is not None:
            body["transparency"] = transparency
    return body


def _patch_gcal_clock(monkeypatch: pytest.MonkeyPatch, fixed: datetime) -> None:
    real = gcal.datetime

    class _FixedNow(real):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed.astimezone(tz)
            return fixed

    monkeypatch.setattr(gcal, "datetime", _FixedNow)


def _patch_gcal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gcal, "get_valid_access_token", lambda *_a, **_k: "g-access")


def _sync_window() -> tuple[datetime, datetime]:
    return _NOW - timedelta(days=7), _NOW + timedelta(days=21)


def _trust_for_row(db: Session, owner: User, settings: UserSettings, row: ExternalCalendarEvent):
    horizon_start, horizon_end = compute_horizon(settings, _NOW)
    sub = _sub(db, db.get(CalendarAccount, row.calendar_account_id))
    return evaluate_busy_input_trust(
        [row],
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        calendar_name_by_id={row.calendar_id: sub.summary},
    )


def _captured_unchanged_metadata(external_event_id: str) -> list[dict[str, str]]:
    return [{"external_event_id": external_event_id, "status": _NOT_IN_BATCH_STATUS}]


@pytest.mark.parametrize(
    ("transparency", "expected_kind"),
    [("opaque", "busy"), ("transparent", "free")],
    ids=["opaque-busy", "transparent-free"],
)
def test_l1_legacy_null_resolved_on_full_fetch(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    transparency: str,
    expected_kind: str,
) -> None:
    """L1: pre-034 null/null row is populated when provider returns explicit transparency."""
    _patch_gcal_clock(monkeypatch, _NOW)
    _patch_gcal_token(monkeypatch)
    owner, settings = _owner(db_session)
    calendar_id = f"cal-l1-{uuid.uuid4().hex[:8]}"
    account = _account(db_session, owner, provider=CalendarProvider.google, calendar_id=calendar_id)
    sub = _sub(db_session, account)
    assert sub.sync_cursor is None
    row = _seed_legacy_row(
        db_session, owner=owner, account=account, calendar_id=calendar_id
    )
    start, end = row.start_time, row.end_time
    assert row.transparency is None and row.free_busy_provenance is None

    def _full_list(*_a: Any, **_k: Any) -> tuple[list[dict[str, Any]], str, int]:
        return (
            [_g_event_body(_LEGACY_EVENT_ID, start, end, transparency=transparency)],
            "sync-token-after-full",
            1,
        )

    monkeypatch.setattr(gcal, "list_calendar_events", _full_list)
    monkeypatch.setattr(
        gcal,
        "list_calendar_events_incremental",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("L1 uses full list")),
    )
    time_min, time_max = _sync_window()
    upserted = gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    db_session.flush()
    assert upserted == 1
    assert row.transparency == transparency
    assert row.free_busy_provenance == "provider_explicit"
    assert row.free_busy_sync_run_id is not None
    assert row.free_busy_provenance != "unknown_legacy"
    history = row.free_busy_change_history or []
    assert len(history) == 1
    assert history[0]["from_transparency"] is None
    assert history[0]["from_provenance"] is None
    assert history[0]["to_transparency"] == transparency
    assert history[0]["to_provenance"] == "provider_explicit"

    trust = _trust_for_row(db_session, owner, settings, row)
    assert trust.ok is True
    assert expected_kind in ("busy", "free")


def test_l2_incremental_skip_then_resolves_on_fetch(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L2: incremental omit leaves null/null + collect blocks; later fetch resolves."""
    _patch_gcal_clock(monkeypatch, _NOW)
    _patch_gcal_token(monkeypatch)
    owner, settings = _owner(db_session)
    calendar_id = f"cal-l2-{uuid.uuid4().hex[:8]}"
    account = _account(db_session, owner, provider=CalendarProvider.google, calendar_id=calendar_id)
    sub = _sub(db_session, account)
    row = _seed_legacy_row(
        db_session, owner=owner, account=account, calendar_id=calendar_id
    )
    start, end = row.start_time, row.end_time
    time_min, time_max = _sync_window()
    _mint_incremental_ready(sub, window_start=time_min, window_end=time_max)
    prior_sync_run = row.free_busy_sync_run_id
    prior_last_synced = row.last_synced_at
    prior_coverage_success = sub.coverage_success_at
    db_session.flush()

    phase = {"n": 0}

    def _incremental(*_a: Any, **_k: Any) -> tuple[list[dict[str, Any]], str, int]:
        if phase["n"] == 0:
            return ([], "sync-token-v2", 1)
        return (
            [_g_event_body(_LEGACY_EVENT_ID, start, end, transparency="opaque")],
            "sync-token-v3",
            1,
        )

    monkeypatch.setattr(gcal, "list_calendar_events_incremental", _incremental)
    monkeypatch.setattr(
        gcal,
        "list_calendar_events",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("L2 skip uses incremental")),
    )

    upserted_skip = gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    db_session.flush()
    assert upserted_skip == 0
    assert row.transparency is None
    assert row.free_busy_provenance is None
    assert row.free_busy_sync_run_id == prior_sync_run
    assert row.last_synced_at == prior_last_synced
    assert sub.coverage_success_at is not None
    assert sub.coverage_success_at >= prior_coverage_success
    assert sub.coverage_mode == "incremental"

    captured = _captured_unchanged_metadata(_LEGACY_EVENT_ID)
    assert captured[0]["status"] == _NOT_IN_BATCH_STATUS
    assert json.dumps(captured)

    trust_direct = _trust_for_row(db_session, owner, settings, row)
    assert trust_direct.ok is False
    diag = trust_direct.blocking_diagnostics[0]
    assert diag.cause == "unknown_free_busy"
    assert diag.event_id == _LEGACY_EVENT_ID
    assert diag.provenance is None

    inputs = collect_inputs(db_session, owner.id, _NOW)
    assert inputs.busy_input_trust is not None
    assert inputs.busy_input_trust.ok is False
    collect_diag = next(
        d for d in inputs.busy_input_trust.blocking_diagnostics if d.event_id == _LEGACY_EVENT_ID
    )
    assert collect_diag.cause == "unknown_free_busy"
    with pytest.raises(BusyInputTrustError):
        require_busy_input_trust(inputs.busy_input_trust)

    freshness = evaluate_calendar_freshness(db_session, owner.id, settings, _NOW)
    assert freshness.ok is True

    assert events_for_busy_merge([row]) == []

    phase["n"] = 1
    upserted_resolve = gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    db_session.flush()
    assert upserted_resolve == 1
    assert row.transparency == "opaque"
    assert row.free_busy_provenance == "provider_explicit"
    assert row.free_busy_sync_run_id is not None
    trust_after = _trust_for_row(db_session, owner, settings, row)
    assert trust_after.ok is True
    inputs_after = collect_inputs(db_session, owner.id, _NOW)
    require_busy_input_trust(inputs_after.busy_input_trust)


def test_l3_omitted_transparency_distinct_from_legacy_null(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L3: omitted transparency on fetch → provider_default_omitted (case B), not legacy null."""
    _patch_gcal_clock(monkeypatch, _NOW)
    _patch_gcal_token(monkeypatch)
    owner, settings = _owner(db_session)
    calendar_id = f"cal-l3-{uuid.uuid4().hex[:8]}"
    account = _account(db_session, owner, provider=CalendarProvider.google, calendar_id=calendar_id)
    row = _seed_legacy_row(
        db_session,
        owner=owner,
        account=account,
        calendar_id=calendar_id,
        external_id="evt-legacy-omit-b",
    )
    start, end = row.start_time, row.end_time

    monkeypatch.setattr(
        gcal,
        "list_calendar_events",
        lambda *_a, **_k: (
            [_g_event_body("evt-legacy-omit-b", start, end, transparency=None)],
            "sync-token-l3",
            1,
        ),
    )
    monkeypatch.setattr(
        gcal,
        "list_calendar_events_incremental",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("L3 uses full list")),
    )
    time_min, time_max = _sync_window()
    gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    db_session.flush()
    assert row.transparency == "opaque"
    assert row.free_busy_provenance == "provider_default_omitted"
    assert row.free_busy_provenance is not None
    trust = _trust_for_row(db_session, owner, settings, row)
    assert trust.ok is True
    assert len(events_for_busy_merge([row])) == 1


def test_l_ms1_legacy_null_resolved_on_ms_view_sync(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L-MS1: legacy null/null resolved via Microsoft calendarView sync (actual view path)."""
    _patch_ms_clock(monkeypatch, _NOW)
    monkeypatch.setattr(ms_cal, "get_valid_access_token", lambda *_a, **_k: "ms-access")
    owner, settings = _owner(db_session)
    calendar_id = f"cal-ms1-{uuid.uuid4().hex[:8]}"
    account = _account(
        db_session, owner, provider=CalendarProvider.microsoft, calendar_id=calendar_id
    )
    ms_external = "evt-legacy-ms-1"
    row = _seed_legacy_row(
        db_session,
        owner=owner,
        account=account,
        calendar_id=calendar_id,
        external_id=ms_external,
        provider=CalendarProvider.microsoft,
    )
    start, end = row.start_time, row.end_time

    def _view(*_a: Any, **_k: Any) -> tuple[list[dict[str, Any]], int, bool]:
        return (
            [
                {
                    "id": ms_external,
                    "subject": "MS legacy",
                    "showAs": "busy",
                    "start": {
                        "dateTime": start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                        "timeZone": "UTC",
                    },
                    "end": {
                        "dateTime": end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                        "timeZone": "UTC",
                    },
                }
            ],
            1,
            True,
        )

    monkeypatch.setattr(ms_cal, "list_calendar_view", _view)
    monkeypatch.setattr(
        ms_cal,
        "list_calendar_events_incremental",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("L-MS1 uses calendarView only")),
    )
    time_min, time_max = _sync_window()
    upserted = ms_cal.sync_account_events(
        db_session,
        settings=_settings(include_google=False, include_ms=True),
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    db_session.flush()
    assert upserted == 1
    sub = _sub(db_session, account)
    assert sub.coverage_mode == "ms_view"
    assert row.transparency == "opaque"
    assert row.free_busy_provenance == "provider_explicit"
    assert row.free_busy_provenance != "unknown_legacy"
    history = row.free_busy_change_history or []
    assert len(history) == 1
    assert history[0]["from_transparency"] is None
    assert history[0]["from_provenance"] is None
    trust = _trust_for_row(db_session, owner, settings, row)
    assert trust.ok is True


def _patch_ms_clock(monkeypatch: pytest.MonkeyPatch, fixed: datetime) -> None:
    real = ms_cal.datetime

    class _FixedNow(real):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed.astimezone(tz)
            return fixed

    monkeypatch.setattr(ms_cal, "datetime", _FixedNow)
