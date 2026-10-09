"""F3 explanation reads: no replan, never_evaluated, stale duration, owner 404."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ScheduleRun, ScheduleTaskOutcome, Task, User
from app.scheduler.outcomes import persist_calculation_outcomes
from app.scheduler.reasons import REASON_PLACED, ReasonFact, TaskSchedulingOutcome, format_summary_text


def _create_task(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={"title": f"explain-{uuid.uuid4().hex[:8]}", "estimated_duration_minutes": 30},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_latest_index_declared() -> None:
    indexes = {idx.name: idx for idx in ScheduleTaskOutcome.__table__.indexes}
    latest = indexes["idx_schedule_task_outcomes_latest"]
    rendered = ", ".join(str(expr) for expr in latest.expressions)
    assert "owner_id" in rendered
    assert "task_id" in rendered
    assert "evaluated_at DESC" in rendered
    unique = {c.name for c in ScheduleTaskOutcome.__table__.constraints}
    assert "uq_schedule_task_outcomes_run_task" in unique


def test_never_evaluated_does_not_replan(client: TestClient, db_session: Session) -> None:
    task = _create_task(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    before = (
        db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count()
    )
    response = client.get(f"/api/v1/tasks/{task['id']}/schedule-explanation")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluation_state"] == "never_evaluated"
    assert body["explanation"] is None
    assert body["is_stale"] is False
    assert body["stale_categories"] == []
    assert body["summary_text"] == format_summary_text([])
    after = (
        db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count()
    )
    assert after == before


def _assert_summary_matches(summary: str, facts: list[dict]) -> None:
    typed = [ReasonFact(item["code"], item.get("params") or {}) for item in facts]
    assert summary == format_summary_text(typed)


def test_missing_task_is_404_without_a_hint(client: TestClient) -> None:
    response = client.get(f"/api/v1/tasks/{uuid.uuid4()}/schedule-explanation")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_other_owner_task_and_run_match_missing_404(
    client: TestClient,
    db_session: Session,
) -> None:
    me = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    other = User(
        email=f"f3-other-{uuid.uuid4().hex[:8]}@example.com",
        username=f"f3other{uuid.uuid4().hex[:8]}",
    )
    db_session.add(other)
    db_session.flush()
    assert other.id != me
    secret = Task(owner_id=other.id, title="not yours")
    foreign_run = ScheduleRun(
        owner_id=other.id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
    )
    db_session.add(secret)
    db_session.add(foreign_run)
    db_session.flush()

    missing_task = client.get(f"/api/v1/tasks/{uuid.uuid4()}/schedule-explanation")
    foreign_task = client.get(f"/api/v1/tasks/{secret.id}/schedule-explanation")
    assert missing_task.status_code == 404
    assert foreign_task.status_code == 404
    assert foreign_task.json() == missing_task.json()
    assert foreign_task.json()["detail"] == "Task not found"
    assert "not yours" not in foreign_task.text

    missing_run = client.get(f"/api/v1/schedule/runs/{uuid.uuid4()}")
    foreign_get = client.get(f"/api/v1/schedule/runs/{foreign_run.id}")
    assert missing_run.status_code == 404
    assert foreign_get.status_code == 404
    assert foreign_get.json() == missing_run.json()
    assert foreign_get.json()["detail"] == "Schedule run not found"

    missing_page = client.get(f"/api/v1/schedule/runs/{uuid.uuid4()}/explanations")
    foreign_page = client.get(f"/api/v1/schedule/runs/{foreign_run.id}/explanations")
    assert missing_page.status_code == 404
    assert foreign_page.status_code == 404
    assert foreign_page.json() == missing_page.json()

    listed = client.get("/api/v1/schedule/runs")
    assert listed.status_code == 200
    assert all(item["id"] != str(foreign_run.id) for item in listed.json()["items"])


def test_latest_explanation_stale_after_duration_change(
    client: TestClient,
    db_session: Session,
) -> None:
    task = _create_task(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    run = ScheduleRun(
        owner_id=owner_id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
        tasks_scheduled=1,
    )
    db_session.add(run)
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
                        {"placed_minutes": 30, "tier": "green", "time_window_source": "user_default"},
                    )
                ],
            )
        ],
    )
    db_session.flush()

    fresh = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation")
    assert fresh.status_code == 200, fresh.text
    fresh_body = fresh.json()
    assert fresh_body["evaluation_state"] == "evaluated"
    assert fresh_body["is_stale"] is False
    assert fresh_body["stale_categories"] == []
    assert fresh_body["explanation"]["reason_facts"][0]["code"] == REASON_PLACED
    _assert_summary_matches(fresh_body["summary_text"], fresh_body["explanation"]["reason_facts"])
    _assert_summary_matches(
        fresh_body["explanation"]["summary_text"],
        fresh_body["explanation"]["reason_facts"],
    )
    assert "Placed 30 minute(s)" in fresh_body["summary_text"]
    assert fresh_body["explanation"]["outcome"] == "placed"
    assert fresh_body["explanation"]["algorithm_version"] == "f3-w2"
    assert fresh_body["explanation"]["input_fingerprint"]

    listed = client.get(f"/api/v1/schedule/runs/{run.id}/explanations")
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["total"] == 1
    assert page["items"][0]["is_stale"] is False

    filtered = client.get(
        f"/api/v1/schedule/runs/{run.id}/explanations",
        params={"task_id": str(task_id)},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    runs = client.get("/api/v1/schedule/runs")
    assert runs.status_code == 200
    assert any(item["id"] == str(run.id) for item in runs.json()["items"])

    patched = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"estimated_duration_minutes": 90},
    )
    assert patched.status_code == 200, patched.text
    stale = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation")
    assert stale.status_code == 200, stale.text
    stale_body = stale.json()
    assert stale_body["is_stale"] is True
    assert stale_body["stale_categories"] == ["duration"]
    _assert_summary_matches(stale_body["summary_text"], stale_body["explanation"]["reason_facts"])
    # Still the recorded explanation, not a new replan.
    assert stale_body["explanation"]["schedule_run_id"] == str(run.id)
    listed_stale = client.get(f"/api/v1/schedule/runs/{run.id}/explanations")
    assert listed_stale.status_code == 200, listed_stale.text
    assert listed_stale.json()["items"][0]["is_stale"] is True
    assert listed_stale.json()["items"][0]["stale_categories"] == ["duration"]
    _assert_summary_matches(
        listed_stale.json()["items"][0]["summary_text"],
        listed_stale.json()["items"][0]["reason_facts"],
    )
    assert (
        db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count() >= 1
    )
    assert db_session.get(Task, task_id) is not None


def _record_placed(client: TestClient, db_session: Session) -> tuple[uuid.UUID, ScheduleRun]:
    task = _create_task(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    run = ScheduleRun(
        owner_id=owner_id,
        status="completed",
        finished_at=datetime.now(timezone.utc),
        tasks_scheduled=1,
    )
    db_session.add(run)
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
                        {"placed_minutes": 30, "tier": "green", "time_window_source": "user_default"},
                    )
                ],
            )
        ],
    )
    db_session.flush()
    return task_id, run


def test_fingerprint_categories_mark_stale_without_replan(
    client: TestClient,
    db_session: Session,
) -> None:
    """Deadline, map/style, and deps are W1 fingerprint inputs, same as duration."""
    task_id, run = _record_placed(client, db_session)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    runs_before = (
        db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count()
    )

    deadline = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"deadline_at": "2026-10-20T17:00:00Z"},
    )
    assert deadline.status_code == 200, deadline.text
    after_deadline = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation").json()
    assert after_deadline["is_stale"] is True
    assert after_deadline["stale_categories"] == ["deadline"]
    _assert_summary_matches(after_deadline["summary_text"], after_deadline["explanation"]["reason_facts"])

    cleared = client.patch(f"/api/v1/tasks/{task_id}", json={"deadline_at": None})
    assert cleared.status_code == 200, cleared.text
    fresh_again = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation").json()
    assert fresh_again["is_stale"] is False
    assert fresh_again["stale_categories"] == []

    styled = client.patch(f"/api/v1/tasks/{task_id}", json={"schedule_style": "manual"})
    assert styled.status_code == 200, styled.text
    after_style = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation").json()
    assert after_style["is_stale"] is True
    assert after_style["stale_categories"] == ["map_style"]

    unstyled = client.patch(f"/api/v1/tasks/{task_id}", json={"schedule_style": None})
    assert unstyled.status_code == 200, unstyled.text
    assert client.get(f"/api/v1/tasks/{task_id}/schedule-explanation").json()["is_stale"] is False

    blocker = _create_task(client)
    linked = client.post(
        f"/api/v1/tasks/{task_id}/dependencies",
        json={"blocking_task_id": blocker["id"], "dependent_task_id": str(task_id)},
    )
    assert linked.status_code == 201, linked.text
    after_deps = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation").json()
    assert after_deps["is_stale"] is True
    assert after_deps["stale_categories"] == ["deps", "prerequisite_state"]
    assert after_deps["explanation"]["schedule_run_id"] == str(run.id)
    page = client.get(f"/api/v1/schedule/runs/{run.id}/explanations").json()
    assert page["items"][0]["is_stale"] is True
    assert page["items"][0]["stale_categories"] == ["deps", "prerequisite_state"]
    runs_after = (
        db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count()
    )
    assert runs_after == runs_before


def test_foreign_run_is_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/schedule/runs/{uuid.uuid4()}/explanations")
    assert response.status_code == 404
    assert response.json()["detail"] == "Schedule run not found"


def test_incomplete_run_is_not_the_latest_explanation(
    client: TestClient,
    db_session: Session,
) -> None:
    task = _create_task(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    running = ScheduleRun(
        owner_id=owner_id,
        status="failed",
        finished_at=datetime.now(timezone.utc),
        error_message="calculation failed",
    )
    db_session.add(running)
    db_session.flush()
    db_session.add(
        ScheduleTaskOutcome(
            schedule_run_id=running.id,
            owner_id=owner_id,
            task_id=task_id,
            requested_minutes=30,
            pinned_minutes=0,
            placed_minutes=0,
            remaining_minutes=30,
            primary_reason_code="unplaced_horizon_exhausted",
            reason_facts=[{"code": "unplaced_horizon_exhausted", "params": {"remaining_minutes": 30}}],
            summary_text="Could not place 30 remaining minute(s) within the horizon.",
            outcome="unplaced",
        )
    )
    db_session.flush()
    response = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation")
    assert response.status_code == 200, response.text
    assert response.json()["evaluation_state"] == "never_evaluated"
