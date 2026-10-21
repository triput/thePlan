"""T2-S1 occurrence bounds — full disposable acceptance (theplan_s1_test @ :5433)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import ScheduledBlock, Task
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import STALE_OCCURRENCE_BOUNDS, diff_stale_categories
from app.scheduler.occurrence_bounds import (
    _feasible_start_exists_in_horizon,
    feasible_start_window,
    horizon_blocks_placement,
)
from app.scheduler.outcomes import snapshots_from_collected
from app.scheduler.preview import run_preview
from app.scheduler.reasons import (
    REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT,
    REASON_OCCURRENCE_BOUNDS_MISS,
    REASON_OCCURRENCE_BOUNDS_NO_SLOT,
    REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT,
    REASON_PLACED,
)
from test_schedule_replan import (
    FIXED_NOW,
    _create_task,
    _isolate_tasks,
    _patch_schedule_clock,
    _prepare_settings,
)

UTC = timezone.utc
_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "041_task_occurrence_bounds"


@pytest.fixture(autouse=True)
def _disposable_s1_database(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _day_time(days_ahead: int = 1, hour: int = 0, minute: int = 0) -> datetime:
    """Calendar day offset from FIXED_NOW with explicit local hour (not +hours drift)."""
    base = FIXED_NOW + timedelta(days=days_ahead)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _ready_preview(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    assert started.status_code == 202, started.text
    run_preview(uuid.UUID(started.json()["id"]), db=db_session)
    db_session.flush()
    got = client.get(f"/api/v1/schedule/previews/{started.json()['id']}")
    assert got.status_code == 200
    preview = got.json()
    assert preview["status"] == "ready"
    return preview


def _outcome(result, task_id: uuid.UUID):
    return next(item for item in result.outcomes if item.task_id == task_id)


def test_unit_horizon_allows_loose_upper_with_feasible_start_today() -> None:
    task = Task(
        title="unit",
        owner_id=uuid.uuid4(),
        estimated_duration_minutes=60,
        start_no_earlier_at=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
        start_no_later_at=datetime(2026, 10, 22, 17, 0, tzinfo=UTC),
        deadline_at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
    )
    hs = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    he = hs + timedelta(days=7)
    assert _feasible_start_exists_in_horizon(
        task, effort_minutes=60, horizon_start=hs, horizon_end=he
    )
    assert not horizon_blocks_placement(
        task, effort_minutes=60, horizon_start=hs, horizon_end=he
    )
    window = feasible_start_window(
        task, effort_minutes=60, horizon_start=hs, horizon_end=he
    )
    assert window is not None
    lo, hi = window
    assert lo <= datetime(2026, 10, 22, 11, 0, tzinfo=UTC) <= hi


def test_a1_unbounded_and_bound_combinations(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    cases = (
        ("unbounded", {}),
        ("lower", {"start_no_earlier_at": _iso(_day_time(1, 9))}),
        ("upper", {"start_no_later_at": _iso(_day_time(1, 17))}),
        (
            "both",
            {
                "start_no_earlier_at": _iso(_day_time(1, 9)),
                "start_no_later_at": _iso(_day_time(1, 17)),
            },
        ),
    )
    for label, bounds in cases:
        created = _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            priority="p1",
            **bounds,
        )
        task_id = uuid.UUID(created["id"])
        _isolate_tasks(db_session, client, {task_id})
        result = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
        outcome = _outcome(result, task_id)
        assert outcome.primary_code == REASON_PLACED, label
        assert len([b for b in result.proposed_blocks if b.task_id == task_id]) == 1


def test_a2_exact_start_and_loose_latest_finish_by(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    day = (FIXED_NOW + timedelta(days=1)).date()
    equal = _create_task(
        client,
        estimated_duration_minutes=30,
        schedule_style="time_block",
        start_no_earlier_at=_iso(datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)),
        start_no_later_at=_iso(datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)),
    )
    loose = _create_task(
        client,
        estimated_duration_minutes=60,
        schedule_style="time_block",
        start_no_earlier_at=_iso(datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)),
        start_no_later_at=_iso(datetime(day.year, day.month, day.day, 17, 0, tzinfo=UTC)),
        deadline_at=_iso(datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC)),
    )
    _isolate_tasks(db_session, client, {uuid.UUID(equal["id"]), uuid.UUID(loose["id"])})
    result = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
    prop_equal = [b for b in result.proposed_blocks if b.task_id == uuid.UUID(equal["id"])]
    assert len(prop_equal) == 1
    assert prop_equal[0].start_time == datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)
    prop_loose = [b for b in result.proposed_blocks if b.task_id == uuid.UUID(loose["id"])]
    assert len(prop_loose) == 1
    start = prop_loose[0].start_time
    assert start >= datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)
    assert start + timedelta(minutes=60) <= datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC)


def test_a2b_patch_geometry_infeasible_then_calculate(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    created = _create_task(
        client,
        estimated_duration_minutes=30,
        schedule_style="time_block",
        start_no_earlier_at=_iso(_day_time(1, 9)),
        deadline_at=_iso(_day_time(1, 10)),
    )
    task_id = uuid.UUID(created["id"])
    _isolate_tasks(db_session, client, {task_id})
    rev = int(client.get("/api/v1/settings").json()["scheduling_revision"])
    patched = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"remaining_estimate_minutes": 120, "expected_revision": rev},
    )
    assert patched.status_code == 200, patched.text
    outcome = _outcome(calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id)
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_NO_SLOT


def test_a3_no_slot_open_window(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
            deadline_at=_iso(_day_time(1, 9, 30)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_NO_SLOT


def test_a4_auto_defer_does_not_cross_hard_bounds(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    client.patch("/api/v1/settings", json={"auto_defer_enabled": True})
    owner_id = _owner_id(client)
    earliest = FIXED_NOW + timedelta(hours=4)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_earlier_at=_iso(earliest),
            soft_target_at=_iso(FIXED_NOW - timedelta(hours=2)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    blocks = [
        b
        for b in calculate(
            db_session, collect_inputs(db_session, owner_id, FIXED_NOW)
        ).proposed_blocks
        if b.task_id == task_id
    ]
    if blocks:
        assert blocks[0].start_time >= earliest


def test_a5_preview_persist_patch_apply_stale(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    preview = _ready_preview(client, db_session, monkeypatch)
    client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_earlier_at": _iso(_day_time(1, 10))},
    )
    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_STALE"
    assert STALE_OCCURRENCE_BOUNDS in rejected.json().get("stale_categories", [])


def test_a6_prefer_does_not_place_outside_bounds(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    day = (FIXED_NOW + timedelta(days=1)).date()
    latest = datetime(day.year, day.month, day.day, 14, 0, tzinfo=UTC)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_later_at=_iso(latest),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    blocks = [
        b
        for b in calculate(
            db_session, collect_inputs(db_session, owner_id, FIXED_NOW)
        ).proposed_blocks
        if b.task_id == task_id
    ]
    assert len(blocks) == 1
    assert blocks[0].start_time <= latest


def test_a7_miss_when_window_elapsed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_later_at=_iso(FIXED_NOW - timedelta(hours=1)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_MISS


def test_a8_merged_patch_null_omit_and_effective_read(
    client: TestClient, db_session: Session
) -> None:
    _prepare_settings(client)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"a8-{_uid()}",
            "start_no_earlier_at": _iso(_day_time(1, 9)),
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    merged_bad = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_later_at": _iso(_day_time(1, 8))},
    )
    assert merged_bad.status_code == 422
    assert merged_bad.json()["code"] == "OCCURRENCE_BOUNDS_INVERTED"
    ok = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_later_at": _iso(_day_time(1, 11))},
    )
    assert ok.status_code == 200
    cleared = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_earlier_at": None, "start_no_later_at": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["start_no_earlier_at"] is None
    eff = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    assert eff.status_code == 200
    assert eff.json()["occurrence_bounds"] is None


def test_a9_hold_pin_conflict_and_preserved_pin(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    pin_start = FIXED_NOW + timedelta(hours=2)
    pin_end = pin_start + timedelta(minutes=30)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(FIXED_NOW + timedelta(hours=5)),
            start_no_later_at=_iso(FIXED_NOW + timedelta(hours=6)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=pin_start,
            end_time=pin_end,
            is_pinned=True,
        )
    )
    db_session.commit()
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    codes = [f.code for f in outcome.reason_facts]
    assert REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT in codes
    assert REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT in codes
    after = db_session.query(ScheduledBlock).filter(ScheduledBlock.task_id == task_id).one()
    assert after.start_time == pin_start
    assert after.end_time == pin_end
    assert after.is_pinned is True


def test_a9b_calculate_twice_one_proposal_not_stacked(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    earliest = (FIXED_NOW + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_earlier_at=_iso(earliest),
            start_no_later_at=_iso(earliest + timedelta(hours=4)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    first = calculate(db_session, inputs)
    assert len([b for b in first.proposed_blocks if b.task_id == task_id]) == 1
    second = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW + timedelta(hours=2)))
    assert len([b for b in second.proposed_blocks if b.task_id == task_id]) == 1
    assert len(db_session.query(ScheduledBlock).filter(ScheduledBlock.task_id == task_id).all()) == 0


def test_a10_repeated_calculate_preserves_progress(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    rev = int(client.get("/api/v1/settings").json()["scheduling_revision"])
    progress = client.post(
        f"/api/v1/tasks/{task_id}/progress-entries",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": 15,
            "remaining_minutes": 45,
            "expected_revision": rev,
        },
    )
    assert progress.status_code == 200, progress.text
    db_session.expire_all()
    task = db_session.get(Task, task_id)
    assert task is not None
    assert task.worked_minutes == 15
    _outcome(calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id)
    db_session.refresh(task)
    assert task.worked_minutes == 15


def test_hold_started_block_outside_horizon(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_later_at=_iso(FIXED_NOW + timedelta(days=2)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    past_start = FIXED_NOW - timedelta(days=2)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=past_start,
            end_time=past_start + timedelta(minutes=30),
            is_pinned=False,
        )
    )
    db_session.commit()
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT


def test_hold_full_pin_coverage_bounded(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    ps = _day_time(1, 10)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=ps,
            end_time=ps + timedelta(minutes=30),
            is_pinned=True,
        )
    )
    db_session.commit()
    result = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
    outcome = next((o for o in result.outcomes if o.task_id == task_id), None)
    assert outcome is not None
    assert any(f.code == REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT for f in outcome.reason_facts)
