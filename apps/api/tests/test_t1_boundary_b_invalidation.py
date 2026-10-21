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
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    ExternalCalendarEvent,
    Project,
    SchedulePreview,
    Task,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services.scheduling_revision import (
    immovable_busy_signature,
    owner_scheduling_lock_key,
    trust_blocking_signature,
)
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
    _seed_always_on_availability,
    _uid,
)

_BOUNDARY_B_ROLLBACK_EMAIL_LIKE = "renee-t1-b-rb-%@example.com"

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


# --- Collision STOP-FINDING (concrete fixture) + per-row identity --------------


def test_boundary_b_cross_provider_same_bare_id_no_sync_outage(
    client: TestClient,
    db_session: Session,
) -> None:
    """STOP-FINDING fixture: schema-legal cross-provider same bare id must not outage.

    ``unique_external_event`` is ``(provider, external_event_id)``. Two trusted
    busy rows (Google + MS) may share the same bare provider string. Prior
    Boundary B code raised ``RuntimeError`` on ANY duplicate bare diagnostic id
    in the owner's universe — a new sync outage instead of an empty/stable
    trust signature. Alignment: per-row ``evaluate_busy_input_trust`` + row UUID
    identity (not colon-joined composites).
    """
    _prepare_settings(client)
    owner_id = _owner_id(client)
    bare = f"shared-bare-{_uid()}"
    now = _wall_now()
    g_acct, g_cal = _google_account(db_session, owner_id)
    m_acct, m_cal = _ms_account(db_session, owner_id)

    g_row = ExternalCalendarEvent(
        owner_id=owner_id,
        calendar_account_id=g_acct.id,
        provider=CalendarProvider.google,
        external_event_id=bare,
        calendar_id=g_cal,
        title="G trusted busy",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        series_identity_state="verified_non_recurring",
    )
    m_row = ExternalCalendarEvent(
        owner_id=owner_id,
        calendar_account_id=m_acct.id,
        provider=CalendarProvider.microsoft,
        external_event_id=bare,
        calendar_id=m_cal,
        title="MS trusted busy",
        start_time=now + timedelta(hours=4),
        end_time=now + timedelta(hours=5),
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        series_identity_state="verified_non_recurring",
    )
    db_session.add_all([g_row, m_row])
    db_session.flush()
    assert g_row.id != m_row.id
    assert g_row.external_event_id == m_row.external_event_id == bare

    horizon_start, horizon_end = now, now + timedelta(days=7)
    # Both trusted → empty signature; must not raise.
    assert (
        trust_blocking_signature(
            db_session,
            owner_id,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
        == ()
    )

    # One blocker + one trusted, same bare id → only blocking row UUID in sig.
    m_row.transparency = None
    m_row.free_busy_provenance = "unknown_projection"
    db_session.flush()
    sig = trust_blocking_signature(
        db_session,
        owner_id,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    assert len(sig) == 1
    assert sig[0][0] == str(m_row.id)
    assert sig[0][1] == "unknown_free_busy:unknown_projection"


# --- Rollback evidence (committed later-session readback; both writers) -------


def _purge_boundary_b_rollback_users() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        db.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": _BOUNDARY_B_ROLLBACK_EMAIL_LIKE},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _commit_boundary_b_rollback_owner() -> uuid.UUID:
    """Committed disposable owner so SessionLocal() later-session readback works."""
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"renee-t1-b-rb-{token}@example.com",
            username=f"renee-t1-b-rb-{token}",
            display_name="Renee T1 Boundary B rollback probe",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        if owner_scheduling_lock_key(user.id) == owner_scheduling_lock_key(
            BOOTSTRAP_USER_ID
        ):
            raise RuntimeError("probe owner collided with bootstrap scheduling lock key")
        db.add(
            UserSettings(
                owner_id=user.id,
                timezone="UTC",
                inter_block_buffer_minutes=0,
                upcoming_horizon_days=7,
                default_schedule_style=ScheduleStyle.standalone,
                scheduling_revision=0,
            )
        )
        _seed_always_on_availability(db, user.id)
        project = Project(owner_id=user.id, title=f"renee-t1-b-rb-{token}")
        db.add(project)
        db.flush()
        db.add(
            Task(
                owner_id=user.id,
                project_id=project.id,
                title=f"renee-t1-b-rb-task-{token}",
                estimated_duration_minutes=60,
                schedule_style=ScheduleStyle.standalone,
            )
        )
        db.commit()
        return user.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _attach_ms_account(
    db: Session, owner_id: uuid.UUID
) -> tuple[CalendarAccount, CalendarSubscription, str]:
    calendar_id = f"cal-rb-ms-{_uid()}"
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.microsoft,
        account_email=f"rb-ms-{_uid()}@contoso.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(account)
    db.flush()
    sub = CalendarSubscription(
        owner_id=owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary="Calendar",
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
        sync_cursor=None,
    )
    db.add(sub)
    db.flush()
    return account, sub, calendar_id


def _attach_google_account(
    db: Session, owner_id: uuid.UUID
) -> tuple[CalendarAccount, CalendarSubscription, str]:
    calendar_id = f"cal-rb-g-{_uid()}"
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.google,
        account_email=f"rb-g-{_uid()}@gmail.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(account)
    db.flush()
    sub = CalendarSubscription(
        owner_id=owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary="Calendar",
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
        sync_cursor=None,
    )
    db.add(sub)
    db.flush()
    return account, sub, calendar_id


def _assert_clean_owner_state(
    db: Session,
    owner_id: uuid.UUID,
    *,
    rev: int,
    sub_id: uuid.UUID,
    sync_cursor: str | None,
) -> None:
    assert _revision(db, owner_id) == rev
    assert (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.owner_id == owner_id)
        .count()
        == 0
    )
    sub = db.get(CalendarSubscription, sub_id)
    assert sub is not None
    assert sub.sync_cursor == sync_cursor


def test_boundary_b_ms_outer_rollback_after_revision_producing_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful MS trust sync then outer rollback → later-session original state."""
    _patch_schedule_clock(monkeypatch)
    _purge_boundary_b_rollback_users()
    owner_id = _commit_boundary_b_rollback_owner()
    start_s, end_s = _in_horizon_bounds()
    external_id = f"evt-rb-ok-{_uid()}"
    event = _ms_unknown_event(external_id, start=start_s, end=end_s)
    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", lambda *a, **k: [event])

    try:
        setup = SessionLocal()
        try:
            account, sub, _cal = _attach_ms_account(setup, owner_id)
            account_id = account.id
            sub_id = sub.id
            cursor_before = sub.sync_cursor
            setup.commit()
        except Exception:
            setup.rollback()
            raise
        finally:
            setup.close()

        seed = SessionLocal()
        try:
            rev_before = _revision(seed, owner_id)
            account = seed.get(CalendarAccount, account_id)
            assert account is not None
            window_start, window_end = _sync_window()
            assert (
                ms_cal.sync_account_events(
                    seed,
                    settings=get_settings(),
                    account=account,
                    time_min=window_start,
                    time_max=window_end,
                )
                == 1
            )
            assert _revision(seed, owner_id) == rev_before + 1
            assert (
                seed.query(ExternalCalendarEvent)
                .filter(
                    ExternalCalendarEvent.owner_id == owner_id,
                    ExternalCalendarEvent.external_event_id == external_id,
                )
                .count()
                == 1
            )
            # Outer rollback after a successful revision-producing sync.
            seed.rollback()
        finally:
            seed.close()

        readback = SessionLocal()
        try:
            _assert_clean_owner_state(
                readback,
                owner_id,
                rev=0,
                sub_id=sub_id,
                sync_cursor=cursor_before,
            )
        finally:
            readback.close()
    finally:
        _purge_boundary_b_rollback_users()


def test_boundary_b_google_outer_rollback_after_revision_producing_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google twin: successful trust sync → outer rollback → later-session clean."""
    _patch_schedule_clock(monkeypatch)
    _purge_boundary_b_rollback_users()
    owner_id = _commit_boundary_b_rollback_owner()
    start_s, end_s = _in_horizon_bounds()
    external_id = f"g-evt-rb-ok-{_uid()}"
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

    try:
        setup = SessionLocal()
        try:
            account, sub, _cal = _attach_google_account(setup, owner_id)
            account_id = account.id
            sub_id = sub.id
            cursor_before = sub.sync_cursor
            setup.commit()
        except Exception:
            setup.rollback()
            raise
        finally:
            setup.close()

        seed = SessionLocal()
        try:
            rev_before = _revision(seed, owner_id)
            account = seed.get(CalendarAccount, account_id)
            assert account is not None
            window_start, window_end = _sync_window()
            assert (
                gcal.sync_account_events(
                    seed,
                    settings=get_settings(),
                    account=account,
                    time_min=window_start,
                    time_max=window_end,
                )
                == 1
            )
            assert _revision(seed, owner_id) == rev_before + 1
            seed.rollback()
        finally:
            seed.close()

        readback = SessionLocal()
        try:
            _assert_clean_owner_state(
                readback,
                owner_id,
                rev=0,
                sub_id=sub_id,
                sync_cursor=cursor_before,
            )
        finally:
            readback.close()
    finally:
        _purge_boundary_b_rollback_users()


def test_boundary_b_ms_mutate_then_post_apply_raise_outer_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MS: apply mutates trust input, post-apply helper raises, outer rollback.

    Proves revision/events do not persist after a real mutation — not merely that
    the bump was never reached. Caller must rollback; committing after the raise
    would persist staging and is explicitly not this proof.
    """
    import app.services.scheduling_revision as srev

    _patch_schedule_clock(monkeypatch)
    _purge_boundary_b_rollback_users()
    owner_id = _commit_boundary_b_rollback_owner()
    start_s, end_s = _in_horizon_bounds()
    external_id = f"evt-rb-mut-{_uid()}"
    event = _ms_unknown_event(external_id, start=start_s, end=end_s)
    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", lambda *a, **k: [event])

    mutated = {"events": 0}

    def boom_after_mutation(db, settings, owner_id, **kwargs):  # noqa: ANN001
        mutated["events"] = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.owner_id == owner_id)
            .count()
        )
        assert mutated["events"] >= 1, "expected apply to mutate before post-apply raise"
        raise RuntimeError("forced post-apply failure after trust input mutation")

    monkeypatch.setattr(
        srev, "increment_scheduling_revision_if_busy_or_trust_changed", boom_after_mutation
    )

    try:
        # Commit account first so later-session can observe subscription identity
        # after caller rolls back only the sync mutation txn.
        setup = SessionLocal()
        try:
            account, sub, _cal = _attach_ms_account(setup, owner_id)
            account_id = account.id
            sub_id = sub.id
            cursor_before = sub.sync_cursor
            setup.commit()
        except Exception:
            setup.rollback()
            raise
        finally:
            setup.close()

        seed = SessionLocal()
        try:
            rev_before = _revision(seed, owner_id)
            account = seed.get(CalendarAccount, account_id)
            assert account is not None
            window_start, window_end = _sync_window()
            with pytest.raises(
                RuntimeError, match="forced post-apply failure after trust input mutation"
            ):
                ms_cal.sync_account_events(
                    seed,
                    settings=get_settings(),
                    account=account,
                    time_min=window_start,
                    time_max=window_end,
                )
            assert mutated["events"] >= 1
            # In-session staging may still show the row; outer rollback clears it.
            seed.rollback()
            assert _revision(seed, owner_id) == rev_before
        finally:
            seed.close()

        readback = SessionLocal()
        try:
            _assert_clean_owner_state(
                readback,
                owner_id,
                rev=0,
                sub_id=sub_id,
                sync_cursor=cursor_before,
            )
            # Not the production apply-failure trust path — no failure sidecar.
            assert (
                readback.query(CalendarSubscriptionRefreshFailure)
                .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub_id)
                .count()
                == 0
            )
        finally:
            readback.close()
    finally:
        _purge_boundary_b_rollback_users()


def test_boundary_b_google_mutate_then_post_apply_raise_outer_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google twin: mutate trust input then post-apply raise → outer rollback."""
    import app.services.scheduling_revision as srev

    _patch_schedule_clock(monkeypatch)
    _purge_boundary_b_rollback_users()
    owner_id = _commit_boundary_b_rollback_owner()
    start_s, end_s = _in_horizon_bounds()
    external_id = f"g-evt-rb-mut-{_uid()}"
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

    mutated = {"events": 0}

    def boom_after_mutation(db, settings, owner_id, **kwargs):  # noqa: ANN001
        mutated["events"] = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.owner_id == owner_id)
            .count()
        )
        assert mutated["events"] >= 1
        raise RuntimeError("forced post-apply failure after trust input mutation")

    monkeypatch.setattr(
        srev, "increment_scheduling_revision_if_busy_or_trust_changed", boom_after_mutation
    )

    try:
        setup = SessionLocal()
        try:
            account, sub, _cal = _attach_google_account(setup, owner_id)
            account_id = account.id
            sub_id = sub.id
            cursor_before = sub.sync_cursor
            setup.commit()
        except Exception:
            setup.rollback()
            raise
        finally:
            setup.close()

        seed = SessionLocal()
        try:
            account = seed.get(CalendarAccount, account_id)
            assert account is not None
            window_start, window_end = _sync_window()
            with pytest.raises(
                RuntimeError, match="forced post-apply failure after trust input mutation"
            ):
                gcal.sync_account_events(
                    seed,
                    settings=get_settings(),
                    account=account,
                    time_min=window_start,
                    time_max=window_end,
                )
            assert mutated["events"] >= 1
            seed.rollback()
        finally:
            seed.close()

        readback = SessionLocal()
        try:
            _assert_clean_owner_state(
                readback,
                owner_id,
                rev=0,
                sub_id=sub_id,
                sync_cursor=cursor_before,
            )
        finally:
            readback.close()
    finally:
        _purge_boundary_b_rollback_users()


def test_boundary_b_ms_apply_failure_commits_failure_trust_not_revision_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production apply-failure path: durable failure trust, not revision rollback proof.

    Raising at ``_apply_subscription_ms_view`` entry never mutates trust inputs;
    autonomous ``commit_refresh_failure`` still persists unreadiness. That is a
    failure-trust qualification — **not** evidence that a revision-producing sync
    rolled back. Caller commit after a post-apply helper raise must not be
    mistaken for this path either.
    """
    _patch_schedule_clock(monkeypatch)
    _purge_boundary_b_rollback_users()
    owner_id = _commit_boundary_b_rollback_owner()
    start_s, end_s = _in_horizon_bounds()
    event = _ms_unknown_event(f"evt-rb-fail-{_uid()}", start=start_s, end=end_s)
    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok"
    )
    monkeypatch.setattr(ms_cal, "list_calendar_view", lambda *a, **k: [event])

    def boom_apply(*_a, **_k):
        raise RuntimeError("forced apply entry failure")

    monkeypatch.setattr(ms_cal, "_apply_subscription_ms_view", boom_apply)

    try:
        setup = SessionLocal()
        try:
            account, sub, _cal = _attach_ms_account(setup, owner_id)
            account_id = account.id
            sub_id = sub.id
            setup.commit()
        except Exception:
            setup.rollback()
            raise
        finally:
            setup.close()

        seed = SessionLocal()
        try:
            rev_before = _revision(seed, owner_id)
            account = seed.get(CalendarAccount, account_id)
            assert account is not None
            window_start, window_end = _sync_window()
            with pytest.raises(RuntimeError, match="forced apply entry failure"):
                ms_cal.sync_account_events(
                    seed,
                    settings=get_settings(),
                    account=account,
                    time_min=window_start,
                    time_max=window_end,
                )
            # Caller rolls back staging; failure trust commits independently.
            seed.rollback()
            assert _revision(seed, owner_id) == rev_before
        finally:
            seed.close()

        readback = SessionLocal()
        try:
            assert _revision(readback, owner_id) == 0
            assert (
                readback.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.owner_id == owner_id)
                .count()
                == 0
            )
            sub = readback.get(CalendarSubscription, sub_id)
            assert sub is not None
            # Production failure-trust qualification retained.
            assert sub.coverage_last_failure_cause == "microsoft_apply_ms_view_failed" or (
                readback.query(CalendarSubscriptionRefreshFailure)
                .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub_id)
                .count()
                >= 1
            )
        finally:
            readback.close()
    finally:
        _purge_boundary_b_rollback_users()


def test_boundary_b_google_apply_failure_commits_failure_trust_not_revision_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google twin: apply-entry failure persists failure trust; not rollback proof."""
    _patch_schedule_clock(monkeypatch)
    _purge_boundary_b_rollback_users()
    owner_id = _commit_boundary_b_rollback_owner()
    start_s, end_s = _in_horizon_bounds()
    event = {
        "id": f"g-evt-rb-fail-{_uid()}",
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

    def boom_full(*_a, **_k):
        raise RuntimeError("forced google apply entry failure")

    monkeypatch.setattr(gcal, "_apply_subscription_full", boom_full)
    monkeypatch.setattr(gcal, "_apply_subscription_incremental", boom_full)

    try:
        setup = SessionLocal()
        try:
            account, sub, _cal = _attach_google_account(setup, owner_id)
            account_id = account.id
            sub_id = sub.id
            setup.commit()
        except Exception:
            setup.rollback()
            raise
        finally:
            setup.close()

        seed = SessionLocal()
        try:
            account = seed.get(CalendarAccount, account_id)
            assert account is not None
            window_start, window_end = _sync_window()
            with pytest.raises(RuntimeError, match="forced google apply entry failure"):
                gcal.sync_account_events(
                    seed,
                    settings=get_settings(),
                    account=account,
                    time_min=window_start,
                    time_max=window_end,
                )
            seed.rollback()
        finally:
            seed.close()

        readback = SessionLocal()
        try:
            assert _revision(readback, owner_id) == 0
            assert (
                readback.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.owner_id == owner_id)
                .count()
                == 0
            )
            sub = readback.get(CalendarSubscription, sub_id)
            assert sub is not None
            cause = sub.coverage_last_failure_cause or ""
            sidecar = (
                readback.query(CalendarSubscriptionRefreshFailure)
                .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub_id)
                .count()
            )
            assert sidecar >= 1 or cause in (
                "google_apply_full_failed",
                "google_apply_incremental_failed",
            )
        finally:
            readback.close()
    finally:
        _purge_boundary_b_rollback_users()
