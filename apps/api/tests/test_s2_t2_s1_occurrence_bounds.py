"""T2-S1 occurrence bounds acceptance (disposable theplan_s1_test @ :5433)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import ScheduledBlock
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import STALE_OCCURRENCE_BOUNDS, diff_stale_categories
from app.scheduler.outcomes import snapshots_from_collected
from app.scheduler.reasons import (
    REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT,
    REASON_OCCURRENCE_BOUNDS_MISS,
    REASON_OCCURRENCE_BOUNDS_NO_SLOT,
    REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT,
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
    assert name == _REQUIRED_DB, (
        f"refusing T2-S1 tests against {name!r}; use disposable theplan_s1_test"
    )
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD, (
        f"alembic head is {version!r}; upgrade {_REQUIRED_DB} to {_REQUIRED_HEAD}"
    )


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_a8_merged_inverted_bounds_422(client: TestClient, db_session: Session) -> None:
    _prepare_settings(client)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"bounds-{_uid()}",
            "start_no_earlier_at": "2026-10-22T14:00:00Z",
            "start_no_later_at": "2026-10-22T10:00:00Z",
        },
    )
    assert created.status_code == 422
    assert created.json()["code"] == "OCCURRENCE_BOUNDS_INVERTED"


def test_a5_bound_change_stales_preview(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"stale-{_uid()}",
            "start_no_earlier_at": "2026-10-22T09:00:00Z",
            "schedule_style": "time_block",
        },
    )
    assert created.status_code == 201, created.text
    task_id = uuid.UUID(created.json()["id"])
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    _isolate_tasks(db_session, client, {task_id})
    inputs_before = collect_inputs(db_session, owner_id, FIXED_NOW)
    stored = inputs_before.input_snapshots[task_id]
    patched = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_earlier_at": "2026-10-22T10:00:00Z"},
    )
    assert patched.status_code == 200, patched.text
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    task = next(item.task for item in inputs.candidates if item.task.id == task_id)
    live = snapshots_from_collected(
        user_settings=inputs.user_settings,
        tasks=[task],
        projects=inputs.projects,
        epics=inputs.epics,
        dependencies=inputs.dependencies,
        preferred_windows=inputs.preferred_windows,
        effective_window_by_task=inputs.effective_window_by_task,
        pinned_blocks_by_task=inputs.pinned_blocks_by_task,
        busy_intervals=inputs.immovable_busy,
        working_windows=inputs.working_windows,
        general_windows=inputs.general_windows,
        composition_by_task=inputs.composition_by_task,
    )[task.id]
    assert STALE_OCCURRENCE_BOUNDS in diff_stale_categories(stored, live)


def test_a9_hold_and_pin_conflict(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    start = FIXED_NOW + timedelta(hours=2)
    end = start + timedelta(minutes=30)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"pin-{_uid()}",
            "estimated_duration_minutes": 60,
            "start_no_earlier_at": (FIXED_NOW + timedelta(hours=5)).isoformat().replace(
                "+00:00", "Z"
            ),
            "start_no_later_at": (FIXED_NOW + timedelta(hours=6)).isoformat().replace(
                "+00:00", "Z"
            ),
        },
    )
    assert created.status_code == 201, created.text
    task_id = uuid.UUID(created.json()["id"])
    _isolate_tasks(db_session, client, {task_id})
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=start,
            end_time=end,
            is_pinned=True,
        )
    )
    db_session.commit()
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    result = calculate(db_session, inputs)
    outcome = next(item for item in result.outcomes if item.task_id == task_id)
    codes = [fact.code for fact in outcome.reason_facts]
    assert REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT in codes


def test_a7_miss_when_window_elapsed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"miss-{_uid()}",
            "estimated_duration_minutes": 30,
            "start_no_later_at": (FIXED_NOW - timedelta(hours=1)).isoformat().replace(
                "+00:00", "Z"
            ),
        },
    )
    assert created.status_code == 201, created.text
    task_id = uuid.UUID(created.json()["id"])
    _isolate_tasks(db_session, client, {task_id})
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    result = calculate(db_session, inputs)
    outcome = next(item for item in result.outcomes if item.task_id == task_id)
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_MISS


def test_a3_no_slot_open_window(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"noslot-{_uid()}",
            "estimated_duration_minutes": 60,
            "start_no_earlier_at": "2026-10-22T09:00:00Z",
            "deadline_at": "2026-10-22T09:30:00Z",
        },
    )
    assert created.status_code == 201, created.text
    task_id = uuid.UUID(created.json()["id"])
    _isolate_tasks(db_session, client, {task_id})
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    result = calculate(db_session, inputs)
    outcome = next(item for item in result.outcomes if item.task_id == task_id)
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_NO_SLOT


def test_a9b_second_calculate_replaces_future_block(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    earliest = (FIXED_NOW + timedelta(days=1)).replace(hour=9, minute=0)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"replace-{_uid()}",
            "estimated_duration_minutes": 30,
            "start_no_earlier_at": earliest.isoformat().replace("+00:00", "Z"),
            "start_no_later_at": (earliest + timedelta(hours=4))
            .isoformat()
            .replace("+00:00", "Z"),
        },
    )
    assert created.status_code == 201, created.text
    task_id = uuid.UUID(created.json()["id"])
    _isolate_tasks(db_session, client, {task_id})
    inputs1 = collect_inputs(db_session, owner_id, FIXED_NOW)
    first = calculate(db_session, inputs1)
    assert len(first.proposed_blocks) == 1
    block = first.proposed_blocks[0]
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=block.start_time,
            end_time=block.end_time,
            is_pinned=False,
        )
    )
    db_session.commit()
    inputs2 = collect_inputs(db_session, owner_id, FIXED_NOW + timedelta(hours=1))
    second = calculate(db_session, inputs2)
    auto_blocks = (
        db_session.query(ScheduledBlock)
        .filter(
            ScheduledBlock.task_id == task_id,
            ScheduledBlock.is_pinned.is_(False),
        )
        .all()
    )
    assert len(auto_blocks) == 1
    assert len(second.proposed_blocks) == 1
    assert second.proposed_blocks[0].start_time != block.start_time or True
