# ==============================================================================
#  File: apps/api/tests/test_schedule_stale_summary.py
#  Description: Stale-summary covers every explanation on a run, including past page one.
#  Component: Schedule
#  Version: 1.0
#  Created: 2026-10-10
#  Last Update: 2026-10-10
# ==============================================================================

"""GET /schedule/runs/{id}/stale-summary — full-run aggregate, owner 404."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ScheduleRun, Task, User
from app.scheduler.outcomes import persist_calculation_outcomes
from app.scheduler.reasons import REASON_PLACED, ReasonFact, TaskSchedulingOutcome
from test_f3_w1_acceptance import _current_user_id, _prepare_settings
from test_f4_w1_scheduler_overrides import _post_override

# Explanations list rejects limit > 200. Page two starts at this offset.
_PAGE = 200
_ID_BASE = 0xA000


def _summary(client: TestClient, run_id: uuid.UUID):
    return client.get(f"/api/v1/schedule/runs/{run_id}/stale-summary")


def _record_run(
    db_session: Session,
    owner_id: uuid.UUID,
    tasks: list[Task],
) -> ScheduleRun:
    run = ScheduleRun(
        owner_id=owner_id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
        tasks_scheduled=len(tasks),
    )
    db_session.add(run)
    db_session.flush()
    persist_calculation_outcomes(
        db_session,
        run_id=run.id,
        owner_id=owner_id,
        outcomes=[
            TaskSchedulingOutcome(
                task_id=task.id,
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
            for task in tasks
        ],
    )
    db_session.flush()
    return run


def test_stale_summary_sees_override_on_page_two_only(
    client: TestClient,
    db_session: Session,
) -> None:
    """201 explanations: the only stale row sorts after the first 200.

    The explanations list at limit 200 misses it. The summary must not.
    """
    _prepare_settings(client)
    owner_id = _current_user_id(client)
    window = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"late-map-{uuid.uuid4().hex[:8]}",
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
    assert window.status_code == 201, window.text
    map_id = uuid.UUID(window.json()["id"])

    early_ids = [uuid.UUID(int=_ID_BASE + index) for index in range(_PAGE)]
    late_id = uuid.UUID(int=_ID_BASE + _PAGE + 1000)
    assert late_id > max(early_ids)
    tasks = [
        Task(
            id=task_id,
            owner_id=owner_id,
            title=f"early-{index}",
            estimated_duration_minutes=30,
        )
        for index, task_id in enumerate(early_ids)
    ]
    tasks.append(
        Task(
            id=late_id,
            owner_id=owner_id,
            title="late-override",
            estimated_duration_minutes=30,
            preferred_time_window_id=map_id,
        )
    )
    db_session.add_all(tasks)
    db_session.flush()
    run = _record_run(db_session, owner_id, tasks)

    fresh = _summary(client, run.id)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json() == {
        "stale_task_count": 0,
        "categories": [],
        "total_explanations": _PAGE + 1,
    }

    _post_override(client, map_id, start="2026-08-11", end="2026-08-11")

    page0 = client.get(
        f"/api/v1/schedule/runs/{run.id}/explanations",
        params={"limit": _PAGE, "offset": 0},
    )
    assert page0.status_code == 200, page0.text
    page0_body = page0.json()
    assert page0_body["total"] == _PAGE + 1
    assert len(page0_body["items"]) == _PAGE
    assert all(item["is_stale"] is False for item in page0_body["items"])
    assert all(item["task_id"] != str(late_id) for item in page0_body["items"])

    page1 = client.get(
        f"/api/v1/schedule/runs/{run.id}/explanations",
        params={"limit": _PAGE, "offset": _PAGE},
    )
    assert page1.status_code == 200, page1.text
    page1_items = page1.json()["items"]
    assert [item["task_id"] for item in page1_items] == [str(late_id)]
    assert page1_items[0]["is_stale"] is True
    assert page1_items[0]["stale_categories"] == ["time_map_overrides"]

    stale = _summary(client, run.id)
    assert stale.status_code == 200, stale.text
    body = stale.json()
    assert body["total_explanations"] == _PAGE + 1
    assert body["stale_task_count"] >= 1
    assert "time_map_overrides" in body["categories"]
    assert body["stale_task_count"] == 1


def test_stale_summary_empty_run_is_not_stale(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_id = _current_user_id(client)
    run = ScheduleRun(
        owner_id=owner_id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.flush()

    response = _summary(client, run.id)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "stale_task_count": 0,
        "categories": [],
        "total_explanations": 0,
    }


def test_stale_summary_foreign_run_matches_missing_404(
    client: TestClient,
    db_session: Session,
) -> None:
    other = User(
        email=f"stale-other-{uuid.uuid4().hex[:8]}@example.com",
        username=f"staleother{uuid.uuid4().hex[:8]}",
    )
    db_session.add(other)
    db_session.flush()
    foreign_run = ScheduleRun(
        owner_id=other.id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
    )
    db_session.add(foreign_run)
    db_session.flush()

    missing = _summary(client, uuid.uuid4())
    foreign = _summary(client, foreign_run.id)
    assert missing.status_code == 404
    assert foreign.status_code == 404
    assert foreign.json() == missing.json()
    assert foreign.json()["detail"] == "Schedule run not found"
