"""T1 trust-only disconnect — twin Boundary B invalidation on HTTP disconnect.

Disposable Postgres only (``T1A_REQUIRE_DISPOSABLE_DSN=1``, ``:5433``).
Production ``DELETE /api/v1/calendar/accounts/{id}``; Apply gate like Boundary B.

Historical note: pre-alignment count-gate bumped on any external row delete (E4/E5
false positives). Post-change semantics match sync ``increment_scheduling_revision_if_busy_or_trust_changed``.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import SessionLocal, engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    ScheduledBlock,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.services.scheduling_revision import owner_scheduling_lock_key
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

from test_f6_lock_writers import _iso
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

UTC = timezone.utc
_DISCONNECT_OWNER_EMAIL = "renee-t1-disc-%@example.com"


@pytest.fixture(autouse=True)
def _disposable_db_only() -> None:
    if os.environ.get("T1A_REQUIRE_DISPOSABLE_DSN") != "1":
        pytest.skip("Trust-only disconnect evidence requires T1A_REQUIRE_DISPOSABLE_DSN=1")
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _wall_now() -> datetime:
    return datetime.now(UTC)


def _in_horizon_window() -> tuple[datetime, datetime]:
    start = _wall_now() + timedelta(hours=2)
    return start, start + timedelta(hours=1)


def _out_of_horizon_window() -> tuple[datetime, datetime]:
    start = _wall_now() + timedelta(days=30)
    return start, start + timedelta(hours=1)


def _calendar_account(
    db: Session, owner_id: uuid.UUID, *, provider: CalendarProvider = CalendarProvider.microsoft
) -> tuple[CalendarAccount, str]:
    calendar_id = f"cal-disc-{_uid()}"
    account = CalendarAccount(
        owner_id=owner_id,
        provider=provider,
        account_email=f"disc-{_uid()}@contoso.test",
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


def _add_external_event(
    db: Session,
    *,
    owner_id: uuid.UUID,
    account: CalendarAccount,
    calendar_id: str,
    start_time: datetime,
    end_time: datetime,
    transparency: str | None,
    free_busy_provenance: str | None,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=owner_id,
        calendar_account_id=account.id,
        provider=account.provider,
        external_event_id=f"evt-{_uid()}",
        calendar_id=calendar_id,
        title="Fixture",
        start_time=start_time,
        end_time=end_time,
        transparency=transparency,
        free_busy_provenance=free_busy_provenance,
        series_identity_state="verified_non_recurring",
    )
    db.add(row)
    db.flush()
    return row


def test_e1_trust_only_disconnect_bumps_preview_stale(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E1: in-horizon trust blocker removed → +1 revision, Apply PREVIEW_STALE."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before_blocks = _block_set(db_session, owner_id)
    runs_before = _run_count(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    start, end = _in_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=start,
        end_time=end,
        transparency=None,
        free_busy_provenance="unknown_projection",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1

    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_STALE"
    assert _block_set(db_session, owner_id) == before_blocks
    assert _run_count(db_session, owner_id) == runs_before


def test_e2_busy_only_disconnect_bumps(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2: trusted busy removed, trust flat → +1."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    start, end = _in_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=start,
        end_time=end,
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1


def test_e3_busy_and_trust_disconnect_single_bump(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E3: busy + trust both change → exactly one increment."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    busy_start, busy_end = _in_horizon_window()
    unk_start = _wall_now() + timedelta(hours=5)
    unk_end = unk_start + timedelta(hours=1)
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=busy_start,
        end_time=busy_end,
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=unk_start,
        end_time=unk_end,
        transparency=None,
        free_busy_provenance="unknown_projection",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1

    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_STALE"


def test_e4_trusted_free_disconnect_revision_flat(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4: trusted free row removed — busy + trust flat (count-gate used to +1)."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    start, end = _in_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=start,
        end_time=end,
        transparency="transparent",
        free_busy_provenance="provider_explicit",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before


def test_e5_out_of_horizon_trust_disconnect_flat(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E5: out-of-horizon unknown removed — trust signature empty both sides."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    settings = (
        db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    )
    assert int(settings.upcoming_horizon_days) == 7
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    start, end = _out_of_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=start,
        end_time=end,
        transparency=None,
        free_busy_provenance="unknown_projection",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before


def test_e6_empty_account_disconnect_flat(
    client: TestClient,
    db_session: Session,
) -> None:
    """E6: account with no events → revision flat."""
    _prepare_settings(client)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, _calendar_id = _calendar_account(db_session, owner_id)
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before


def _commit_secondary_owner() -> uuid.UUID:
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"renee-t1-disc-{token}@example.com",
            username=f"renee-t1-disc-{token}",
            display_name="Renee T1 disconnect isolation",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        if owner_scheduling_lock_key(user.id) == owner_scheduling_lock_key(BOOTSTRAP_USER_ID):
            raise RuntimeError("probe owner collided with bootstrap scheduling lock key")
        db.add(
            UserSettings(
                owner_id=user.id,
                timezone="UTC",
                inter_block_buffer_minutes=0,
                upcoming_horizon_days=7,
                default_schedule_style=ScheduleStyle.standalone,
                scheduling_revision=3,
            )
        )
        _seed_always_on_availability(db, user.id)
        db.commit()
        return user.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_e7_owner_isolation_disconnect_bump(
    client: TestClient,
    db_session: Session,
) -> None:
    """E7: disconnect on owner A must not bump owner B revision."""
    _prepare_settings(client)
    owner_a = _owner_id(client)
    owner_b = _commit_secondary_owner()
    rev_a_before = _revision(db_session, owner_a)

    db_b = SessionLocal()
    try:
        rev_b_before = (
            db_b.query(UserSettings)
            .filter(UserSettings.owner_id == owner_b)
            .one()
            .scheduling_revision
        )
        account_b, calendar_id_b = _calendar_account(db_b, owner_b)
        start, end = _in_horizon_window()
        _add_external_event(
            db_b,
            owner_id=owner_b,
            account=account_b,
            calendar_id=calendar_id_b,
            start_time=start,
            end_time=end,
            transparency="opaque",
            free_busy_provenance="provider_explicit",
        )
        db_b.commit()
        account_b_id = account_b.id
    finally:
        db_b.close()

    # Primary client disconnects owner B's account via direct HTTP with auth as A — must 404.
    not_found = client.delete(f"/api/v1/calendar/accounts/{account_b_id}")
    assert not_found.status_code == 404, not_found.text

    account_a, calendar_id_a = _calendar_account(db_session, owner_a)
    start, end = _in_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_a,
        account=account_a,
        calendar_id=calendar_id_a,
        start_time=start,
        end_time=end,
        transparency=None,
        free_busy_provenance="unknown_projection",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account_a.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_a) == rev_a_before + 1

    db_b = SessionLocal()
    try:
        rev_b_after = (
            db_b.query(UserSettings)
            .filter(UserSettings.owner_id == owner_b)
            .one()
            .scheduling_revision
        )
        assert int(rev_b_after) == int(rev_b_before)
    finally:
        db_b.close()


def test_e8_scheduled_blocks_unchanged_on_disconnect(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E8: disconnect drops external rows only; scheduled_blocks retained."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    owner_id = _owner_id(client)
    start = FIXED_NOW + timedelta(hours=3)
    created = client.post(
        "/api/v1/scheduled-blocks",
        json={
            "task_id": task["id"],
            "start_time": _iso(start),
            "end_time": _iso(start + timedelta(hours=1)),
        },
    )
    assert created.status_code == 201, created.text
    block_id = uuid.UUID(created.json()["id"])
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    ev_start, ev_end = _in_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=ev_start,
        end_time=ev_end,
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1

    db_session.expire_all()
    block = db_session.get(ScheduledBlock, block_id)
    assert block is not None
    assert block.owner_id == owner_id
