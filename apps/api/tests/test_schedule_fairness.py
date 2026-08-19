"""Scheduling fairness — round-robin placement and per-project daily cap (DEF-017)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ExternalCalendarEvent, ScheduledBlock, Task
from tests.test_schedule_replan import (
    FIXED_NOW,
    _create_task,
    _current_user_id,
    _iso,
    _patch_schedule_clock,
    _prepare_settings,
    _replan_sync,
)

UTC = timezone.utc


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_project(client: TestClient, **extra: object) -> dict:
    payload = {"title": f"proj-{_uid()}", **extra}
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _isolate_tasks(db_session: Session, client: TestClient, keep_task_ids: set[uuid.UUID]) -> None:
    """Hide other open tasks and clear busy noise on shared local Postgres."""
    owner_id = _current_user_id(client)
    for task in (
        db_session.query(Task)
        .filter(Task.owner_id == owner_id, Task.is_completed.is_(False))
        .all()
    ):
        if task.id not in keep_task_ids:
            task.is_completed = True
    db_session.query(ExternalCalendarEvent).filter(ExternalCalendarEvent.owner_id == owner_id).delete()
    db_session.query(ScheduledBlock).filter(ScheduledBlock.owner_id == owner_id).delete()
    db_session.flush()


def _first_shared_day(
    client: TestClient,
    task_ids: list[str],
) -> tuple[datetime, datetime] | None:
    all_days: set[datetime.date] = set()
    for task_id in task_ids:
        for block in _blocks_for_task(client, task_id):
            start = datetime.fromisoformat(block["start_time"].replace("Z", "+00:00"))
            all_days.add(start.date())
    for day in sorted(all_days):
        day_start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        if all(_blocks_for_task(client, task_id, day_start=day_start, day_end=day_end) for task_id in task_ids):
            return day_start, day_end
    return None


def _blocks_for_task(
    client: TestClient,
    task_id: str,
    *,
    day_start: datetime | None = None,
    day_end: datetime | None = None,
) -> list[dict]:
    horizon_start = FIXED_NOW
    horizon_end = FIXED_NOW + timedelta(days=7)
    blocks = client.get(
        "/api/v1/scheduled-blocks",
        params={"start": _iso(horizon_start), "end": _iso(horizon_end)},
    )
    assert blocks.status_code == 200, blocks.text
    rows = [row for row in blocks.json()["items"] if row["task_id"] == task_id and not row["is_pinned"]]
    if day_start is None or day_end is None:
        return rows
    filtered: list[dict] = []
    for row in rows:
        start = datetime.fromisoformat(row["start_time"].replace("Z", "+00:00"))
        if start >= day_start and start < day_end:
            filtered.append(row)
    return filtered


def _block_minutes(block: dict) -> int:
    start = datetime.fromisoformat(block["start_time"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(block["end_time"].replace("Z", "+00:00"))
    return int((end - start).total_seconds() // 60)


def test_equal_priority_tasks_mix_on_first_day(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    project_a = _create_project(client)
    project_b = _create_project(client)
    task_a = _create_task(
        client,
        project_id=project_a["id"],
        estimated_duration_minutes=120,
        priority="p2",
    )
    task_b = _create_task(
        client,
        project_id=project_b["id"],
        estimated_duration_minutes=120,
        priority="p2",
    )
    _isolate_tasks(
        db_session,
        client,
        {uuid.UUID(task_a["id"]), uuid.UUID(task_b["id"])},
    )

    run = _replan_sync(client, db_session, monkeypatch)
    assert run["status"] == "completed"
    assert run["blocks_created"] >= 2
    assert run.get("stats_json", {}).get("candidate_count") == 2, run

    shared = _first_shared_day(client, [task_a["id"], task_b["id"]])
    assert shared is not None, "expected both tasks to share a scheduled day"
    day_start, day_end = shared
    day_a = _blocks_for_task(client, task_a["id"], day_start=day_start, day_end=day_end)
    day_b = _blocks_for_task(client, task_b["id"], day_start=day_start, day_end=day_end)
    assert day_a, "expected project A task to receive a block on the first local day"
    assert day_b, "expected project B task to receive a block on the first local day"
    assert sum(_block_minutes(block) for block in day_a) < 480


def test_p1_scheduled_before_p2(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    project_a = _create_project(client)
    project_b = _create_project(client)
    task_p1 = _create_task(
        client,
        project_id=project_a["id"],
        estimated_duration_minutes=60,
        priority="p1",
    )
    task_p2 = _create_task(
        client,
        project_id=project_b["id"],
        estimated_duration_minutes=60,
        priority="p2",
    )
    _isolate_tasks(
        db_session,
        client,
        {uuid.UUID(task_p1["id"]), uuid.UUID(task_p2["id"])},
    )

    _replan_sync(client, db_session, monkeypatch)

    p1_blocks = _blocks_for_task(client, task_p1["id"])
    p2_blocks = _blocks_for_task(client, task_p2["id"])
    assert p1_blocks
    assert p2_blocks
    p1_start = datetime.fromisoformat(p1_blocks[0]["start_time"].replace("Z", "+00:00"))
    p2_start = datetime.fromisoformat(p2_blocks[0]["start_time"].replace("Z", "+00:00"))
    assert p1_start < p2_start


def test_daily_project_cap_limits_first_day(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    cap_patch = client.patch(
        "/api/v1/settings",
        json={"max_auto_schedule_minutes_per_project_per_day": 60},
    )
    assert cap_patch.status_code == 200, cap_patch.text

    project = _create_project(client)
    task = _create_task(
        client,
        project_id=project["id"],
        estimated_duration_minutes=120,
        priority="p2",
    )
    task_row = db_session.get(Task, uuid.UUID(task["id"]))
    assert task_row is not None
    task_row.max_block_duration_minutes = 60
    db_session.flush()
    _isolate_tasks(db_session, client, {uuid.UUID(task["id"])})

    _replan_sync(client, db_session, monkeypatch)

    all_blocks = _blocks_for_task(client, task["id"])
    assert all_blocks
    first_start = min(
        datetime.fromisoformat(block["start_time"].replace("Z", "+00:00")) for block in all_blocks
    )
    day_start = datetime.combine(first_start.date(), datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    day_blocks = _blocks_for_task(client, task["id"], day_start=day_start, day_end=day_end)
    assert day_blocks
    assert sum(_block_minutes(block) for block in day_blocks) <= 60
