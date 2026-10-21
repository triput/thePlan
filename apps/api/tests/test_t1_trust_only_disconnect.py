"""T1 trust-only disconnect — twin Boundary B invalidation on HTTP disconnect.

Disposable Postgres only (``T1A_REQUIRE_DISPOSABLE_DSN=1``, ``:5433``).
Production ``DELETE /api/v1/calendar/accounts/{id}``; Apply gate like Boundary B.

Historical note: pre-alignment count-gate bumped on any external row delete (E4/E5
false positives). Post-change semantics match sync ``increment_scheduling_revision_if_busy_or_trust_changed``.
"""

from __future__ import annotations

import inspect
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes.calendar import disconnect_calendar_account
from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import SessionLocal, engine
from app.models import (
    AvailabilityPolicy,
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    ExternalCalendarEvent,
    FocusWindow,
    FreeBusySeriesPolicy,
    FreeBusySeriesPolicyDecision,
    ScheduledBlock,
    Task,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.horizon import compute_horizon
from app.services.scheduling_revision import (
    immovable_busy_signature,
    owner_scheduling_lock_key,
    trust_blocking_signature,
)
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
_E7_ROLLBACK_EMAIL_LIKE = "renee-t1-disc-rb-%@example.com"


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


def _pre_change_count_gate_would_bump(db: Session, account_id: uuid.UUID) -> bool:
    """Disconnect invalidation @ fdfaa448^ — row-count gate, not signature twin."""
    return (
        db.query(ExternalCalendarEvent.id)
        .filter(
            ExternalCalendarEvent.calendar_account_id == account_id,
            *ExternalCalendarEvent.immovable_busy_clause(),
        )
        .count()
        > 0
    )


def _patch_signature_premises_capture(
    monkeypatch: pytest.MonkeyPatch, holder: dict[str, object]
) -> None:
    import app.api.routes.calendar as cal_routes
    import app.services.scheduling_revision as srev

    real = srev.increment_scheduling_revision_if_busy_or_trust_changed

    def capturing(
        db: Session,
        settings: UserSettings,
        owner_id: uuid.UUID,
        *,
        before_busy: tuple[tuple[str, str, str], ...],
        before_trust: tuple[tuple[str, str, str, str], ...],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> int | None:
        holder["before_busy"] = before_busy
        holder["before_trust"] = before_trust
        holder["after_busy"] = immovable_busy_signature(db, owner_id)
        holder["after_trust"] = trust_blocking_signature(
            db,
            owner_id,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
        return real(
            db,
            settings,
            owner_id,
            before_busy=before_busy,
            before_trust=before_trust,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )

    monkeypatch.setattr(srev, "increment_scheduling_revision_if_busy_or_trust_changed", capturing)
    monkeypatch.setattr(cal_routes, "increment_scheduling_revision_if_busy_or_trust_changed", capturing)


def _owner_retained_snapshot(db: Session, owner_id: uuid.UUID) -> dict[str, object]:
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    tasks = (
        db.query(Task)
        .filter(Task.owner_id == owner_id)
        .order_by(Task.id.asc())
        .all()
    )
    blocks = (
        db.query(ScheduledBlock)
        .filter(ScheduledBlock.owner_id == owner_id)
        .order_by(ScheduledBlock.id.asc())
        .all()
    )
    policies = (
        db.query(AvailabilityPolicy)
        .filter(AvailabilityPolicy.owner_id == owner_id)
        .order_by(AvailabilityPolicy.slug.asc())
        .all()
    )
    focus_maps = (
        db.query(FocusWindow)
        .filter(FocusWindow.owner_id == owner_id)
        .order_by(FocusWindow.id.asc())
        .all()
    )
    fb_policies = (
        db.query(FreeBusySeriesPolicy)
        .filter(FreeBusySeriesPolicy.owner_id == owner_id)
        .order_by(FreeBusySeriesPolicy.id.asc())
        .all()
    )
    fb_decisions = (
        db.query(FreeBusySeriesPolicyDecision)
        .join(FreeBusySeriesPolicy)
        .filter(FreeBusySeriesPolicy.owner_id == owner_id)
        .order_by(FreeBusySeriesPolicyDecision.id.asc())
        .all()
    )
    events = (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.owner_id == owner_id)
        .order_by(ExternalCalendarEvent.id.asc())
        .all()
    )
    return {
        "revision": int(settings.scheduling_revision),
        "settings": (
            settings.timezone,
            int(settings.inter_block_buffer_minutes),
            int(settings.upcoming_horizon_days),
            settings.default_schedule_style.value if settings.default_schedule_style else None,
        ),
        "tasks": tuple(
            (
                str(t.id),
                t.title,
                int(t.estimated_duration_minutes or 0),
                t.schedule_style.value if t.schedule_style else None,
                str(t.preferred_time_window_id) if t.preferred_time_window_id else None,
                int(t.remaining_minutes or 0),
            )
            for t in tasks
        ),
        "scheduled_blocks": tuple(
            (
                str(b.id),
                str(b.task_id),
                b.start_time.astimezone(UTC).isoformat(),
                b.end_time.astimezone(UTC).isoformat(),
                bool(b.is_pinned),
            )
            for b in blocks
        ),
        "availability": tuple(
            (
                p.slug.value if hasattr(p.slug, "value") else str(p.slug),
                int(w.weekday),
                w.start_time.isoformat(),
                w.end_time.isoformat(),
                int(w.duration_minutes),
            )
            for p in policies
            for w in sorted(p.windows, key=lambda row: (row.weekday, row.sort_order))
        ),
        "focus_windows": tuple(
            (
                str(m.id),
                m.name,
                bool(m.strict_mode),
                tuple(
                    (
                        band.tier.value,
                        band.start_time.isoformat(),
                        band.end_time.isoformat(),
                        int(band.days_of_week),
                        int(band.sort_order),
                    )
                    for band in sorted(m.bands, key=lambda row: row.sort_order)
                ),
            )
            for m in focus_maps
        ),
        "free_busy_policies": tuple(
            (
                str(p.id),
                p.provider.value,
                p.calendar_id,
                p.provider_series_id,
                p.mapping,
            )
            for p in fb_policies
        ),
        "free_busy_decisions": tuple(
            (str(d.id), str(d.policy_id), d.mapping, d.decision_source) for d in fb_decisions
        ),
        "external_events": tuple(
            (
                str(e.id),
                str(e.calendar_account_id),
                e.external_event_id,
                e.transparency,
                e.free_busy_provenance,
                str(e.task_id) if e.task_id else None,
                str(e.scheduled_block_id) if e.scheduled_block_id else None,
            )
            for e in events
        ),
    }


def _purge_e7_rollback_users() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        db.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": _E7_ROLLBACK_EMAIL_LIKE},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _commit_e7_rollback_fixture() -> dict[str, object]:
    """Committed owner for E7 later-session readback (not fixture savepoint cleanup)."""
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"renee-t1-disc-rb-{token}@example.com",
            username=f"renee-t1-disc-rb-{token}",
            display_name="Renee T1 disconnect rollback probe",
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
                scheduling_revision=5,
            )
        )
        _seed_always_on_availability(db, user.id)
        account, calendar_id = _calendar_account(db, user.id)
        sub = (
            db.query(CalendarSubscription)
            .filter(CalendarSubscription.calendar_account_id == account.id)
            .one()
        )
        db.add(
            CalendarSubscriptionRefreshFailure(
                subscription_id=sub.id,
                failure_at=datetime.now(UTC),
                cause="synthetic_disconnect_rollback_probe",
            )
        )
        start, end = _in_horizon_window()
        event = _add_external_event(
            db,
            owner_id=user.id,
            account=account,
            calendar_id=calendar_id,
            start_time=start,
            end_time=end,
            transparency=None,
            free_busy_provenance="unknown_projection",
        )
        task = Task(
            owner_id=user.id,
            title=f"rb-task-{token}",
            estimated_duration_minutes=60,
            schedule_style=ScheduleStyle.standalone,
        )
        db.add(task)
        db.flush()
        block = ScheduledBlock(
            owner_id=user.id,
            task_id=task.id,
            start_time=FIXED_NOW + timedelta(hours=3),
            end_time=FIXED_NOW + timedelta(hours=4),
            is_pinned=False,
        )
        db.add(block)
        db.flush()
        linked = _add_external_event(
            db,
            owner_id=user.id,
            account=account,
            calendar_id=calendar_id,
            start_time=start + timedelta(hours=1),
            end_time=end + timedelta(hours=1),
            transparency="opaque",
            free_busy_provenance="provider_explicit",
        )
        linked.task_id = task.id
        linked.scheduled_block_id = block.id
        db.flush()
        db.commit()
        return {
            "owner_id": user.id,
            "account_id": account.id,
            "sub_id": sub.id,
            "event_ids": (event.id, linked.id),
            "block_id": block.id,
            "rev_before": 5,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
    premises: dict[str, object] = {}
    _patch_signature_premises_capture(monkeypatch, premises)

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
    assert premises["before_busy"] == premises["after_busy"]
    assert premises["before_trust"] != premises["after_trust"]

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
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before_blocks = _block_set(db_session, owner_id)
    runs_before = _run_count(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)
    premises: dict[str, object] = {}
    _patch_signature_premises_capture(monkeypatch, premises)

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
    assert premises["before_busy"] != premises["after_busy"]
    assert premises["before_trust"] == premises["after_trust"]

    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_STALE"
    assert _block_set(db_session, owner_id) == before_blocks
    assert _run_count(db_session, owner_id) == runs_before


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
    premises: dict[str, object] = {}
    _patch_signature_premises_capture(monkeypatch, premises)

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
    assert premises["before_busy"] != premises["after_busy"]
    assert premises["before_trust"] != premises["after_trust"]

    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_STALE"


def test_baseline_pre_change_e1_count_gate_bumps_without_signature_twin(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BASELINE-PRE-CHANGE (@ fdfaa448^ count-gate): E1 fixture row still triggers gate."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
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
    db_session.flush()
    disconnect_now = datetime.now(UTC)
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    horizon_start, horizon_end = compute_horizon(settings, disconnect_now)
    before_busy = immovable_busy_signature(db_session, owner_id)
    before_trust = trust_blocking_signature(
        db_session, owner_id, horizon_start=horizon_start, horizon_end=horizon_end
    )
    assert before_trust != ()
    assert _pre_change_count_gate_would_bump(db_session, account.id) is True
    assert before_busy == immovable_busy_signature(db_session, owner_id)


def test_baseline_pre_change_e2_count_gate_bumps_without_signature_twin(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BASELINE-PRE-CHANGE (@ fdfaa448^ count-gate): E2 busy row triggers gate."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
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
    db_session.flush()
    disconnect_now = datetime.now(UTC)
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    horizon_start, horizon_end = compute_horizon(settings, disconnect_now)
    before_trust = trust_blocking_signature(
        db_session, owner_id, horizon_start=horizon_start, horizon_end=horizon_end
    )
    assert before_trust == ()
    assert _pre_change_count_gate_would_bump(db_session, account.id) is True


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


def test_owner_isolation_disconnect_bump(
    client: TestClient,
    db_session: Session,
) -> None:
    """Owner isolation (non-E): disconnect on owner A must not bump owner B revision."""
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


def test_e7_disconnect_pre_commit_failure_rolls_back_committed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E7: real disconnect path mutates, commit fails, fresh session sees original rows."""
    import app.api.routes.calendar as cal_routes
    import app.services.scheduling_revision as srev

    probe = {"armed": True, "increment_reached": False}
    real_inc = srev.increment_scheduling_revision_if_busy_or_trust_changed
    real_commit = Session.commit

    def traced_inc(*args, **kwargs):  # noqa: ANN002, ANN003
        probe["increment_reached"] = True
        return real_inc(*args, **kwargs)

    def guarded_commit(self: Session) -> None:
        if probe["armed"]:
            for frame in inspect.stack():
                if frame.function == "disconnect_calendar_account":
                    probe["armed"] = False
                    raise RuntimeError("forced disconnect pre-commit rollback")
        return real_commit(self)

    monkeypatch.setattr(srev, "increment_scheduling_revision_if_busy_or_trust_changed", traced_inc)
    monkeypatch.setattr(cal_routes, "increment_scheduling_revision_if_busy_or_trust_changed", traced_inc)
    monkeypatch.setattr(Session, "commit", guarded_commit)

    _purge_e7_rollback_users()
    try:
        seeded = _commit_e7_rollback_fixture()
        owner_id = seeded["owner_id"]
        account_id = seeded["account_id"]
        sub_id = seeded["sub_id"]
        rev_before = seeded["rev_before"]
        event_ids = seeded["event_ids"]
        block_id = seeded["block_id"]

        worker = SessionLocal()
        try:
            user = worker.get(User, owner_id)
            assert user is not None
            with pytest.raises(RuntimeError, match="forced disconnect pre-commit rollback"):
                disconnect_calendar_account(account_id, db=worker, user=user)
            worker.rollback()
            assert probe["increment_reached"] is True
        finally:
            worker.close()

        readback = SessionLocal()
        try:
            assert _revision(readback, owner_id) == rev_before
            account = readback.get(CalendarAccount, account_id)
            assert account is not None
            sub = readback.get(CalendarSubscription, sub_id)
            assert sub is not None
            assert (
                readback.query(CalendarSubscriptionRefreshFailure)
                .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub_id)
                .count()
                == 1
            )
            for event_id in event_ids:
                assert readback.get(ExternalCalendarEvent, event_id) is not None
            block = readback.get(ScheduledBlock, block_id)
            assert block is not None
            assert block.owner_id == owner_id
        finally:
            readback.close()
    finally:
        _purge_e7_rollback_users()


def test_e8_full_retained_set_unchanged_on_disconnect(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E8: disconnect removes only target account import rows; retained set unchanged."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    focus = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"disc-retain-{_uid()}",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert focus.status_code == 201, focus.text
    task = _create_task(
        client,
        estimated_duration_minutes=90,
        schedule_style="standalone",
        preferred_time_window_id=focus.json()["id"],
    )
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

    policy = FreeBusySeriesPolicy(
        owner_id=owner_id,
        provider=CalendarProvider.google,
        calendar_id="primary-retain",
        provider_series_id=f"series-{_uid()}",
        mapping="free",
        decision_source="manual_resolve",
    )
    db_session.add(policy)
    db_session.flush()
    db_session.add(
        FreeBusySeriesPolicyDecision(
            policy_id=policy.id,
            decided_at=datetime.now(UTC),
            reason="synthetic retain probe",
            mapping="free",
            decision_source="manual_resolve",
            snapshot={"probe": True},
        )
    )

    keep_account, keep_calendar_id = _calendar_account(
        db_session, owner_id, provider=CalendarProvider.google
    )
    keep_start, keep_end = _in_horizon_window()
    keep_event = _add_external_event(
        db_session,
        owner_id=owner_id,
        account=keep_account,
        calendar_id=keep_calendar_id,
        start_time=keep_start + timedelta(hours=6),
        end_time=keep_end + timedelta(hours=6),
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )

    drop_account, drop_calendar_id = _calendar_account(db_session, owner_id)
    ev_start, ev_end = _in_horizon_window()
    linked = _add_external_event(
        db_session,
        owner_id=owner_id,
        account=drop_account,
        calendar_id=drop_calendar_id,
        start_time=ev_start,
        end_time=ev_end,
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )
    linked.task_id = uuid.UUID(task["id"])
    linked.scheduled_block_id = block_id
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=drop_account,
        calendar_id=drop_calendar_id,
        start_time=ev_start + timedelta(hours=2),
        end_time=ev_end + timedelta(hours=2),
        transparency=None,
        free_busy_provenance="unknown_projection",
    )
    db_session.commit()

    before = _owner_retained_snapshot(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)
    drop_account_id = drop_account.id
    linked_event_id = linked.id

    deleted = client.delete(f"/api/v1/calendar/accounts/{drop_account_id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1

    db_session.expire_all()
    after = _owner_retained_snapshot(db_session, owner_id)
    assert after["revision"] == rev_before + 1
    assert after["tasks"] == before["tasks"]
    assert after["settings"] == before["settings"]
    assert after["availability"] == before["availability"]
    assert after["focus_windows"] == before["focus_windows"]
    assert after["free_busy_policies"] == before["free_busy_policies"]
    assert after["free_busy_decisions"] == before["free_busy_decisions"]
    assert after["scheduled_blocks"] == before["scheduled_blocks"]

    before_events = before["external_events"]
    after_events = after["external_events"]
    keep_sig = next(row for row in before_events if row[0] == str(keep_event.id))
    assert keep_sig in after_events
    assert all(row[1] != str(drop_account_id) for row in after_events)
    assert all(row[0] != str(linked_event_id) for row in after_events)
    block = db_session.get(ScheduledBlock, block_id)
    assert block is not None
    assert block.owner_id == owner_id
