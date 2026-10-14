"""F3-W1 acceptance: each landed reason is produced by collect→calculate→apply.

Deferred reason families (W2, not asserted here): completed/trashed/archived,
dependency cycle, no allowed Time Map interval, red exclusion, busy/pinned
conflict, deadline limit, insufficient contiguous minimum block, project daily
Past deadline with zero placement uses ``unplaced_deadline_limit`` (F3-W2).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ExternalCalendarEvent, ScheduleRun, ScheduledBlock, Task, TaskDependency
from app.scheduler.reasons import ReasonFact, format_summary_text
from app.scheduler.replan import run_replan

UTC = timezone.utc
FIXED_NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _patch_schedule_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.scheduler.placement as placement_mod
    import app.scheduler.replan as replan_mod
    import app.scheduler.ups as ups_mod

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            if tz is not None:
                return FIXED_NOW.astimezone(tz)
            return FIXED_NOW.replace(tzinfo=None)

    for module in (replan_mod, placement_mod, ups_mod):
        monkeypatch.setattr(module, "datetime", FixedDatetime)


def _prepare_settings(client: TestClient, **extra: object) -> None:
    from cutover_hours import patch_settings_with_availability

    patch_settings_with_availability(
        client,
        {
            "timezone": "UTC",
            "workweek_days": 7,
            "upcoming_horizon_days": 7,
            "inter_block_buffer_minutes": 0,
            "default_schedule_style": "standalone",
            **extra,
        },
    )


def _create_task(client: TestClient, **extra: object) -> dict:
    payload = {"title": f"f3-{_uid()}", **extra}
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _current_user_id(client: TestClient) -> uuid.UUID:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    return uuid.UUID(me.json()["id"])


def _isolate_tasks(db_session: Session, client: TestClient, keep_task_ids: set[uuid.UUID]) -> None:
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


def _replan(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_replan",
        lambda run_id, sync=False: None,
    )
    response = client.post("/api/v1/schedule/replan")
    assert response.status_code == 202, response.text
    body = response.json()
    run_replan(uuid.UUID(body["id"]), db=db_session)
    db_session.flush()
    got = client.get(f"/api/v1/schedule/runs/{body['id']}")
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "completed", got.text
    return got.json()


def _assert_summary_matches(summary: str, facts: list[dict]) -> None:
    typed = [ReasonFact(item["code"], item.get("params") or {}) for item in facts]
    assert summary == format_summary_text(typed)


def _explanation(client: TestClient, task_id: str) -> dict:
    response = client.get(f"/api/v1/tasks/{task_id}/schedule-explanation")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluation_state"] == "evaluated"
    explanation = body["explanation"]
    assert explanation is not None
    facts = explanation["reason_facts"]
    assert facts, body
    _assert_summary_matches(body["summary_text"], facts)
    _assert_summary_matches(explanation["summary_text"], facts)
    assert explanation["summary_text"] == body["summary_text"]
    assert explanation["primary_reason_code"] == facts[0]["code"]
    listed = client.get(
        f"/api/v1/schedule/runs/{explanation['schedule_run_id']}/explanations",
        params={"task_id": task_id},
    )
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["total"] == 1
    _assert_summary_matches(page["items"][0]["summary_text"], page["items"][0]["reason_facts"])
    assert page["items"][0]["reason_facts"] == facts
    return body


@pytest.fixture()
def scheduled(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)


def test_manual_and_bundle_are_excluded(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(client)
    manual = _create_task(client, estimated_duration_minutes=30, schedule_style="manual")
    bundle = _create_task(client, estimated_duration_minutes=30, schedule_style="bundle")
    _isolate_tasks(
        db_session,
        client,
        {uuid.UUID(manual["id"]), uuid.UUID(bundle["id"])},
    )
    _replan(client, db_session, monkeypatch)

    for task, style in ((manual, "manual"), (bundle, "bundle")):
        body = _explanation(client, task["id"])
        fact = body["explanation"]["reason_facts"][0]
        assert fact["code"] == "excluded_manual_or_bundle"
        assert fact["params"]["schedule_style"] == style
        assert body["explanation"]["outcome"] == "excluded"


def test_duration_covered_by_pins_is_excluded(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60)
    task_id = uuid.UUID(task["id"])
    owner_id = _current_user_id(client)
    _isolate_tasks(db_session, client, {task_id})
    pin_start = FIXED_NOW + timedelta(days=1)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=pin_start,
            end_time=pin_start + timedelta(minutes=60),
            is_pinned=True,
        )
    )
    db_session.flush()
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    fact = body["explanation"]["reason_facts"][0]
    assert fact["code"] == "excluded_duration_covered_by_pins"
    assert fact["params"]["pinned_minutes"] == 60
    assert fact["params"]["requested_minutes"] == 60
    assert body["explanation"]["placed_minutes"] == 0
    assert body["explanation"]["outcome"] == "excluded"


def test_unfinished_prerequisite_blocks_dependent(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(client)
    owner_id = _current_user_id(client)
    blocker = _create_task(client, estimated_duration_minutes=60, schedule_style="manual")
    dependent = _create_task(client, estimated_duration_minutes=30)
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
    db_session.flush()
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, dependent["id"])
    fact = body["explanation"]["reason_facts"][0]
    assert fact["code"] == "blocked_prerequisite"
    assert blocker["id"] in fact["params"]["blocking_task_ids"]
    assert body["explanation"]["outcome"] == "blocked"
    assert body["explanation"]["placed_minutes"] == 0


def test_placed_summary_matches_formatter(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        deadline_at=_iso(FIXED_NOW + timedelta(days=6)),
    )
    _isolate_tasks(db_session, client, {uuid.UUID(task["id"])})
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    assert body["is_stale"] is False
    assert body["stale_categories"] == []
    explanation = body["explanation"]
    assert explanation["reason_facts"][0]["code"] == "placed"
    assert explanation["placed_minutes"] == 30
    assert explanation["remaining_minutes"] == 0
    assert explanation["outcome"] == "placed"
    assert "Placed 30 minute(s)" in body["summary_text"]


def test_partial_fit_is_horizon_exhausted(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(client, workday_minutes=60, upcoming_horizon_days=1)
    task = _create_task(
        client,
        estimated_duration_minutes=180,
        min_block_duration_minutes=30,
        max_block_duration_minutes=60,
        deadline_at=_iso(FIXED_NOW + timedelta(days=3)),
    )
    _isolate_tasks(db_session, client, {uuid.UUID(task["id"])})
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    explanation = body["explanation"]
    assert explanation["placed_minutes"] > 0
    assert explanation["remaining_minutes"] > 0
    assert explanation["reason_facts"][0]["code"] == "unplaced_horizon_exhausted"
    assert explanation["reason_facts"][0]["params"]["remaining_minutes"] == explanation["remaining_minutes"]
    assert explanation["outcome"] == "unplaced"


def test_past_deadline_is_deadline_limit(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        deadline_at=_iso(FIXED_NOW - timedelta(hours=1)),
    )
    _isolate_tasks(db_session, client, {uuid.UUID(task["id"])})
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    explanation = body["explanation"]
    assert explanation["placed_minutes"] == 0
    assert explanation["remaining_minutes"] == 30
    assert explanation["reason_facts"][0]["code"] == "unplaced_deadline_limit"
    assert explanation["outcome"] == "unplaced"
