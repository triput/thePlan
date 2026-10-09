"""Dex F3-W1 P2 corrections: prereq seed + captured fingerprints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ScheduleRun, ScheduleTaskOutcome, ScheduledBlock, TaskDependency
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.outcomes import persist_calculation_outcomes
from app.scheduler.reasons import REASON_PLACED, ReasonFact, TaskSchedulingOutcome
from test_schedule_replan import (
    FIXED_NOW,
    _create_task,
    _isolate_tasks,
    _iso,
    _patch_schedule_clock,
    _prepare_settings,
    _replan_sync,
)


def test_old_unpinned_prereq_block_does_not_delay_dependent(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dex reproduction: leftover unpinned A@16:00 must not push B to 16:00."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])

    blocker = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        priority="p1",
        deadline_at=_iso(FIXED_NOW + timedelta(days=6)),
    )
    dependent = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        priority="p1",
        deadline_at=_iso(FIXED_NOW + timedelta(days=6)),
    )
    blocker_id = uuid.UUID(blocker["id"])
    dependent_id = uuid.UUID(dependent["id"])
    db_session.add(
        TaskDependency(
            owner_id=owner_id,
            blocking_task_id=blocker_id,
            dependent_task_id=dependent_id,
        )
    )
    _isolate_tasks(db_session, client, {blocker_id, dependent_id})

    # Stale unpinned block for A ending mid-afternoon — wiped on apply.
    doomed_start = FIXED_NOW + timedelta(days=1, hours=15, minutes=30)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=blocker_id,
            start_time=doomed_start,
            end_time=doomed_start + timedelta(minutes=30),
            is_pinned=False,
        )
    )
    db_session.flush()

    run = _replan_sync(client, db_session, monkeypatch)
    assert run["status"] == "completed"

    horizon_end = FIXED_NOW + timedelta(days=7)
    blocks = client.get(
        "/api/v1/scheduled-blocks",
        params={"start": _iso(FIXED_NOW), "end": _iso(horizon_end)},
    ).json()["items"]
    dependent_blocks = [
        row
        for row in blocks
        if row["task_id"] == dependent["id"] and not row["is_pinned"]
    ]
    assert dependent_blocks, "dependent should place"
    dependent_start = min(
        datetime.fromisoformat(row["start_time"].replace("Z", "+00:00"))
        for row in dependent_blocks
    )
    # Must not start at/after the wiped 16:00-ish leftover.
    assert dependent_start < doomed_start


def test_persist_uses_captured_snapshots_not_live_deps(
    client: TestClient,
    db_session: Session,
) -> None:
    """Fingerprint at apply must match collect-time deps, not a later edge."""
    task = _create_task(client)
    other = _create_task(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    other_id = uuid.UUID(other["id"])

    captured = {
        task_id: {
            "v": 1,
            "duration": {
                "estimated_duration_minutes": 30,
                "min_block_duration_minutes": 15,
                "max_block_duration_minutes": 120,
            },
            "deadline": {"deadline_at": None},
            "map_style": {
                "schedule_style": "auto",
                "time_window_id": None,
                "strict_mode": None,
                "bands": [],
            },
            "deps": {"blocking_task_ids": []},
        }
    }

    run = ScheduleRun(
        owner_id=owner_id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
        tasks_scheduled=1,
    )
    db_session.add(run)
    db_session.flush()

    # Live DB gains a dependency after "calculation" would have finished.
    db_session.add(
        TaskDependency(
            owner_id=owner_id,
            blocking_task_id=other_id,
            dependent_task_id=task_id,
        )
    )
    db_session.flush()

    persist_calculation_outcomes(
        db_session,
        run_id=run.id,
        owner_id=owner_id,
        outcomes=[
            TaskSchedulingOutcome(
                task_id=task_id,
                requested_minutes=30,
                pinned_minutes=0,
                placed_minutes=30,
                remaining_minutes=0,
                reason_facts=[
                    ReasonFact(
                        REASON_PLACED,
                        {
                            "placed_minutes": 30,
                            "tier": "green",
                            "time_window_source": "user_default",
                        },
                    )
                ],
            )
        ],
        input_snapshots=captured,
    )
    db_session.flush()

    row = (
        db_session.query(ScheduleTaskOutcome)
        .filter_by(schedule_run_id=run.id, task_id=task_id)
        .one()
    )
    assert row.input_snapshot is not None
    assert row.input_snapshot["deps"]["blocking_task_ids"] == []

    # Live read should see the new dep and mark stale.
    body = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation").json()
    assert body["is_stale"] is True
    assert "deps" in body["stale_categories"]


def test_collect_captures_input_snapshots(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=30)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    _isolate_tasks(db_session, client, {task_id})

    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    assert task_id in inputs.input_snapshots
    assert inputs.input_snapshots[task_id]["v"] == 1
    assert "deps" in inputs.input_snapshots[task_id]

    result = calculate(db_session, inputs)
    assert result.outcomes
