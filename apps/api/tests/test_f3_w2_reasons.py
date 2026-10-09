"""F3-W2 reason families, multi-fact assembly, and placement_facts."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ScheduleTaskOutcome, Task, TaskDependency
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.reasons import (
    REASON_BLOCKED_DEPENDENCY_CYCLE,
    REASON_EXCLUDED_LIFECYCLE_COMPLETED,
    REASON_UNPLACED_DEADLINE_LIMIT,
    REASON_UNPLACED_HORIZON_EXHAUSTED,
    ReasonFact,
    format_summary_text,
)
from test_schedule_replan import (
    FIXED_NOW,
    _create_task,
    _isolate_tasks,
    _iso,
    _patch_schedule_clock,
    _prepare_settings,
    _replan_sync,
)


def test_w2_deadline_limit_summary() -> None:
    text = format_summary_text(
        [
            ReasonFact(
                REASON_UNPLACED_DEADLINE_LIMIT,
                {
                    "remaining_minutes": 30,
                    "deadline_at": "2026-01-01T12:00:00+00:00",
                },
            )
        ]
    )
    assert "before the deadline" in text
    assert "30" in text


def test_multi_fact_summary_joins_all() -> None:
    facts = [
        ReasonFact(REASON_UNPLACED_DEADLINE_LIMIT, {"remaining_minutes": 20}),
        ReasonFact(REASON_UNPLACED_HORIZON_EXHAUSTED, {"remaining_minutes": 20}),
    ]
    text = format_summary_text(facts)
    assert "deadline" in text.lower()
    assert "horizon" in text.lower()


def test_past_deadline_records_deadline_limit(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        deadline_at=_iso(FIXED_NOW - timedelta(hours=1)),
    )
    task_id = uuid.UUID(task["id"])
    _isolate_tasks(db_session, client, {task_id})
    run = _replan_sync(client, db_session, monkeypatch)
    assert run["status"] == "completed"

    row = (
        db_session.query(ScheduleTaskOutcome)
        .filter_by(schedule_run_id=uuid.UUID(run["id"]), task_id=task_id)
        .one()
    )
    assert row.primary_reason_code == REASON_UNPLACED_DEADLINE_LIMIT
    assert row.placement_facts is not None
    assert row.placement_facts.get("timezone")
    assert row.placement_facts.get("applicable_override") is None


def test_completed_task_gets_lifecycle_outcome(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=45)
    task_id = uuid.UUID(task["id"])
    row = db_session.get(Task, task_id)
    assert row is not None
    row.is_completed = True
    db_session.flush()
    _isolate_tasks(db_session, client, {task_id})

    run = _replan_sync(client, db_session, monkeypatch)
    outcome = (
        db_session.query(ScheduleTaskOutcome)
        .filter_by(schedule_run_id=uuid.UUID(run["id"]), task_id=task_id)
        .one_or_none()
    )
    assert outcome is not None
    assert outcome.primary_reason_code == REASON_EXCLUDED_LIFECYCLE_COMPLETED


def test_dependency_cycle_reason(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    a = _create_task(client, estimated_duration_minutes=30, priority="p1")
    b = _create_task(client, estimated_duration_minutes=30, priority="p1")
    a_id = uuid.UUID(a["id"])
    b_id = uuid.UUID(b["id"])
    db_session.add(
        TaskDependency(owner_id=owner_id, blocking_task_id=a_id, dependent_task_id=b_id)
    )
    db_session.add(
        TaskDependency(owner_id=owner_id, blocking_task_id=b_id, dependent_task_id=a_id)
    )
    _isolate_tasks(db_session, client, {a_id, b_id})

    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    result = calculate(db_session, inputs)
    codes = {
        outcome.primary_code
        for outcome in result.outcomes
        if outcome.task_id in {a_id, b_id}
    }
    assert REASON_BLOCKED_DEPENDENCY_CYCLE in codes
