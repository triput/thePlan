"""Boundary B — trust-blocking signature → scheduling_revision at sync writers.

Disposable Postgres only (``T1A_REQUIRE_DISPOSABLE_DSN=1``, ``:5433``).
Provider HTTP mocked; production Google/MS ``sync_account_events`` entrypoints.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    SchedulePreview,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services.scheduling_revision import immovable_busy_signature
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

# Reuse F6 preview helpers (same disposable fixture patterns).
from test_f6_w2_preview_apply import (
    FIXED_NOW,
    _block_set,
    _create_task,
    _owner_id,
    _patch_schedule_clock,
    _prepare_settings,
    _ready_preview,
    _revision,
    _run_count,
    _uid,
)

UTC = timezone.utc


def _wall_now() -> datetime:
    """Real UTC now — trust compare uses sync-path ``datetime.now``, not FIXED_NOW."""
    return datetime.now(UTC)


def _iso_naive_utc(dt: datetime) -> str:
    """Graph/MS dateTime strings without offset (timeZone=UTC separately)."""
    return dt.astimezone(UTC).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")


def _in_horizon_bounds() -> tuple[str, str]:
    start = _wall_now() + timedelta(hours=2)
    return _iso_naive_utc(start), _iso_naive_utc(start + timedelta(hours=1))


def _out_of_horizon_bounds() -> tuple[str, str]:
    start = _wall_now() + timedelta(days=30)
    return _iso_naive_utc(start), _iso_naive_utc(start + timedelta(hours=1))


@pytest.fixture(autouse=True)
def _disposable_db_only() -> None:
    if os.environ.get("T1A_REQUIRE_DISPOSABLE_DSN") != "1":
        pytest.skip("Boundary B evidence requires T1A_REQUIRE_DISPOSABLE_DSN=1")
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _ms_account(db: Session, owner_id: uuid.UUID) -> tuple[CalendarAccount, str]:
    calendar_id = f"cal-b-{_uid()}"
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.microsoft,
        account_email=f"b-ms-{_uid()}@contoso.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(account)
    db.flush()
    db.add(
        CalendarSubscription(
            owner_id=owner_id,
            calendar_account_id=account.id,
            external_calendar_id=calendar_id,
            summary="Calendar",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
        )
    )
    db.flush()
    return account, calendar_id


def _google_account(db: Session, owner_id: uuid.UUID) -> tuple[CalendarAccount, str]:
    calendar_id = f"cal-g-b-{_uid()}"
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.google,
        account_email=f"b-g-{_uid()}@gmail.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(account)
    db.flush()
    db.add(
        CalendarSubscription(
            owner_id=owner_id,
            calendar_account_id=account.id,
            external_calendar_id=calendar_id,
            summary="Calendar",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
        )
    )
    db.flush()
    return account, calendar_id


def _ms_unknown_event(external_id: str, *, start: str, end: str) -> dict:
    return {
        "id": external_id,
        "type": "singleInstance",
        "subject": "Ambiguous free/busy",
        "showAs": "unknown",
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }


def _sync_window() -> tuple[datetime, datetime]:
    return FIXED_NOW - timedelta(days=1), FIXED_NOW + timedelta(days=40)


def test_boundary_b_google_sync_unknown_trust_bumps_preview_stale(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google twin: in-horizon trust-blocker via sync → revision +1 → PREVIEW_STALE."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before_blocks = _block_set(db_session, owner_id)
    runs_before = _run_count(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)
    before_busy = immovable_busy_signature(db_session, owner_id)

    account, _calendar_id = _google_account(db_session, owner_id)
    external_id = f"g-evt-unk-{_uid()}"
    start_s, end_s = _in_horizon_bounds()
    # Non opaque/transparent transparency → unknown_projection (trust-blocking).
    event = {
        "id": external_id,
        "status": "confirmed",
        "summary": "Ambiguous free/busy",
        "transparency": "unknown",
        "start": {"dateTime": f"{start_s}Z", "timeZone": "UTC"},
        "end": {"dateTime": f"{end_s}Z", "timeZone": "UTC"},
    }
    monkeypatch.setattr(
        gcal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(
        gcal,
        "list_calendar_events",
        lambda access, cal, *, time_min, time_max: ([event], "tok-next", 1),
    )

    window_start, window_end = _sync_window()
    upserted = gcal.sync_account_events(
        db_session,
        settings=get_settings(),
        account=account,
        time_min=window_start,
        time_max=window_end,
    )
    assert upserted == 1
    assert immovable_busy_signature(db_session, owner_id) == before_busy
    assert _revision(db_session, owner_id) == rev_before + 1

    row = (
        db_session.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner_id,
            ExternalCalendarEvent.external_event_id == external_id,
        )
        .one()
    )
    assert row.transparency is None
    assert row.free_busy_provenance == "unknown_projection"

    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_STALE"
    assert _block_set(db_session, owner_id) == before_blocks
    assert _run_count(db_session, owner_id) == runs_before


def test_boundary_b_trusted_free_add_keeps_revision_flat(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: trusted free add must not bump (busy flat + trust flat)."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, _calendar_id = _ms_account(db_session, owner_id)
    start_s, end_s = _in_horizon_bounds()
    event = {
        "id": f"evt-free-{_uid()}",
        "type": "singleInstance",
        "subject": "Focus (free)",
        "showAs": "free",
        "start": {"dateTime": start_s, "timeZone": "UTC"},
        "end": {"dateTime": end_s, "timeZone": "UTC"},
    }
    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", lambda *a, **k: [event])

    window_start, window_end = _sync_window()
    assert (
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )
        == 1
    )
    assert _revision(db_session, owner_id) == rev_before


def test_boundary_b_ms_trust_clear_and_cause_change_bump(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation classes: blocker clear + cause change each bump exactly once."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    rev = _revision(db_session, owner_id)

    account, _calendar_id = _ms_account(db_session, owner_id)
    external_id = f"evt-mut-{_uid()}"
    start_s, end_s = _in_horizon_bounds()
    phase = {"n": 0}

    def fake_view(access: str, calendar: str, *, time_min: datetime, time_max: datetime):
        phase["n"] += 1
        if phase["n"] == 1:
            # Add unknown (provider_explicit).
            return [_ms_unknown_event(external_id, start=start_s, end=end_s)]
        if phase["n"] == 2:
            # Cause change: omit showAs on complete payload → unknown_missing.
            return [
                {
                    "id": external_id,
                    "type": "singleInstance",
                    "subject": "Ambiguous free/busy",
                    "start": {"dateTime": start_s, "timeZone": "UTC"},
                    "end": {"dateTime": end_s, "timeZone": "UTC"},
                }
            ]
        # Clear blocker.
        return []

    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", fake_view)
    window_start, window_end = _sync_window()

    assert (
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )
        == 1
    )
    assert _revision(db_session, owner_id) == rev + 1
    rev = _revision(db_session, owner_id)

    assert (
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )
        == 1
    )
    assert _revision(db_session, owner_id) == rev + 1
    rev = _revision(db_session, owner_id)

    # Clear: full ms_view with empty events still upserts 0 but may rewrite coverage.
    ms_cal.sync_account_events(
        db_session,
        settings=get_settings(),
        account=account,
        time_min=window_start,
        time_max=window_end,
    )
    assert _revision(db_session, owner_id) == rev + 1


def test_boundary_b_ms_retime_into_and_out_of_horizon_bump(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retime into / out of owner ``compute_horizon`` under fixed sync_now."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    settings = (
        db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    )
    assert int(settings.upcoming_horizon_days) == 7

    account, _calendar_id = _ms_account(db_session, owner_id)
    external_id = f"evt-retime-{_uid()}"
    far_start, far_end = _out_of_horizon_bounds()
    near_start, near_end = _in_horizon_bounds()
    phase = {"n": 0}

    def fake_view(access: str, calendar: str, *, time_min: datetime, time_max: datetime):
        phase["n"] += 1
        if phase["n"] == 1:
            return [_ms_unknown_event(external_id, start=far_start, end=far_end)]
        if phase["n"] == 2:
            return [_ms_unknown_event(external_id, start=near_start, end=near_end)]
        return [_ms_unknown_event(external_id, start=far_start, end=far_end)]

    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", fake_view)
    window_start, window_end = _sync_window()

    rev0 = _revision(db_session, owner_id)
    # Out-of-horizon unknown: trust signature empty both sides → no bump.
    assert (
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )
        == 1
    )
    assert _revision(db_session, owner_id) == rev0

    # Retime into horizon → bump.
    assert (
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )
        == 1
    )
    assert _revision(db_session, owner_id) == rev0 + 1

    # Retime out of horizon → bump (membership drops).
    assert (
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )
        == 1
    )
    assert _revision(db_session, owner_id) == rev0 + 2


def test_boundary_b_ms_failed_sync_does_not_persist_revision(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rollback proof: apply failure must not leave a bumped scheduling_revision."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, _calendar_id = _ms_account(db_session, owner_id)
    start_s, end_s = _in_horizon_bounds()
    event = _ms_unknown_event(f"evt-roll-{_uid()}", start=start_s, end=end_s)
    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", lambda *a, **k: [event])

    def boom(*_a, **_k):
        raise RuntimeError("forced apply failure")

    monkeypatch.setattr(ms_cal, "_apply_subscription_ms_view", boom)

    window_start, window_end = _sync_window()
    with pytest.raises(RuntimeError, match="forced apply failure"):
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )

    # Nested apply rolled back; revision bump never reached.
    assert _revision(db_session, owner_id) == rev_before
    assert (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.owner_id == owner_id)
        .count()
        == 0
    )


def test_boundary_b_busy_and_trust_change_single_bump(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Busy + trust both change in one sync → exactly one revision increment."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, _calendar_id = _ms_account(db_session, owner_id)
    busy_start, busy_end = _in_horizon_bounds()
    unk_start = _iso_naive_utc(_wall_now() + timedelta(hours=5))
    unk_end = _iso_naive_utc(_wall_now() + timedelta(hours=6))
    # One busy (occupancy) + one unknown (trust) in the same pull.
    events = [
        {
            "id": f"evt-busy-{_uid()}",
            "type": "singleInstance",
            "subject": "Dentist",
            "showAs": "busy",
            "start": {"dateTime": busy_start, "timeZone": "UTC"},
            "end": {"dateTime": busy_end, "timeZone": "UTC"},
        },
        _ms_unknown_event(f"evt-unk-{_uid()}", start=unk_start, end=unk_end),
    ]
    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", lambda *a, **k: events)

    window_start, window_end = _sync_window()
    assert (
        ms_cal.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=window_start,
            time_max=window_end,
        )
        == 2
    )
    assert _revision(db_session, owner_id) == rev_before + 1

    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_STALE"
