"""F3-W2 acceptance through collect → calculate → apply.

Each new reason family once, placement_facts on a placed task, stale snapshot
v2 categories on GET, and a multi-fact summary that matches the formatter
with primary = the first fact.

Still deferred (W3, not a close): ``priority_ups``, ``time_map_overrides``,
and a run-summary web UI. F3 stays open.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CalendarAccount, ExternalCalendarEvent, ScheduledBlock, Task, TaskDependency
from app.models.enums import CalendarProvider
from app.scheduler.input_fingerprint import (
    DEFERRED_STALE_CATEGORIES,
    SNAPSHOT_VERSION,
    W2_STALE_CATEGORIES,
)
from app.scheduler.reasons import ReasonFact, format_summary_text
from test_f3_w1_acceptance import (
    FIXED_NOW,
    _create_task,
    _current_user_id,
    _explanation,
    _isolate_tasks,
    _iso,
    _patch_schedule_clock,
    _prepare_settings,
    _replan,
)

UTC = timezone.utc


@pytest.fixture()
def scheduled(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)


def _settings(client: TestClient, **extra: object) -> None:
    payload: dict[str, object] = {
        "workday_start_local": "08:00",
        "workday_minutes": 480,
        "auto_defer_enabled": False,
        "max_auto_schedule_minutes_per_project_per_day": None,
    }
    payload.update(extra)
    _prepare_settings(client, **payload)


def _keep(db_session: Session, client: TestClient, *task_ids: str) -> None:
    _isolate_tasks(db_session, client, {uuid.UUID(task_id) for task_id in task_ids})


def _codes(body: dict) -> list[str]:
    return [fact["code"] for fact in body["explanation"]["reason_facts"]]


def _horizon_dates():
    day = FIXED_NOW.date()
    last = (FIXED_NOW + timedelta(days=7)).date()
    while day <= last:
        yield day
        day += timedelta(days=1)


def _at(day, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def _account(db_session: Session, owner_id: uuid.UUID) -> CalendarAccount:
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.google,
        account_email=f"f3-w2-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc="enc-access",
        refresh_token_enc="enc-refresh",
        token_expires_at=FIXED_NOW + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=False,
    )
    db_session.add(account)
    db_session.flush()
    return account


def _external(
    db_session: Session,
    *,
    owner_id: uuid.UUID,
    account: CalendarAccount,
    start: datetime,
    end: datetime,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=owner_id,
        calendar_account_id=account.id,
        scheduled_block_id=None,
        provider=CalendarProvider.google,
        external_event_id=f"f3-w2-{uuid.uuid4().hex}",
        calendar_id="primary",
        title="Busy",
        start_time=start,
        end_time=end,
        is_all_day=False,
        last_synced_at=FIXED_NOW,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _pin(
    db_session: Session,
    *,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> ScheduledBlock:
    block = ScheduledBlock(
        owner_id=owner_id,
        task_id=task_id,
        start_time=start,
        end_time=end,
        is_pinned=True,
    )
    db_session.add(block)
    db_session.flush()
    return block


def _cover(
    db_session: Session,
    client: TestClient,
    *,
    pinned_task_id: uuid.UUID | None,
    account: CalendarAccount | None,
    start_hour: int,
    end_hour: int,
    source: str,
) -> None:
    owner_id = _current_user_id(client)
    for day in _horizon_dates():
        start, end = _at(day, start_hour), _at(day, end_hour)
        if source == "pinned":
            assert pinned_task_id is not None
            _pin(
                db_session,
                owner_id=owner_id,
                task_id=pinned_task_id,
                start=start,
                end=end,
            )
        else:
            assert account is not None
            _external(
                db_session,
                owner_id=owner_id,
                account=account,
                start=start,
                end=end,
            )


def _window(client: TestClient, *, strict: bool, bands: list[dict]) -> str:
    created = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"f3-w2-{uuid.uuid4().hex[:8]}",
            "strict_mode": strict,
            "bands": bands,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_deadline_limit_is_primary_when_nothing_placed(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        deadline_at=_iso(FIXED_NOW - timedelta(hours=1)),
    )
    _keep(db_session, client, task["id"])
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    explanation = body["explanation"]
    assert _codes(body)[0] == "unplaced_deadline_limit"
    assert explanation["primary_reason_code"] == "unplaced_deadline_limit"
    assert explanation["outcome"] == "unplaced"
    assert explanation["placed_minutes"] == 0
    assert "before the deadline" in body["summary_text"]
    assert explanation["algorithm_version"] == "f3-w2"
    assert explanation["input_snapshot"]["v"] == SNAPSHOT_VERSION


def test_dependency_cycle_blocks_both_members(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    owner_id = _current_user_id(client)
    first = _create_task(client, estimated_duration_minutes=30, priority="p1")
    second = _create_task(client, estimated_duration_minutes=30, priority="p1")
    db_session.add(
        TaskDependency(
            owner_id=owner_id,
            blocking_task_id=uuid.UUID(first["id"]),
            dependent_task_id=uuid.UUID(second["id"]),
        )
    )
    db_session.add(
        TaskDependency(
            owner_id=owner_id,
            blocking_task_id=uuid.UUID(second["id"]),
            dependent_task_id=uuid.UUID(first["id"]),
        )
    )
    _keep(db_session, client, first["id"], second["id"])
    _replan(client, db_session, monkeypatch)

    for task in (first, second):
        body = _explanation(client, task["id"])
        assert body["explanation"]["outcome"] == "blocked"
        assert _codes(body)[0] == "blocked_dependency_cycle"
        assert task["id"] in body["explanation"]["reason_facts"][0]["params"]["cycle_task_ids"]
        assert "dependency cycle" in body["summary_text"]


def test_project_daily_cap_keeps_the_local_date(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client, max_auto_schedule_minutes_per_project_per_day=10)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=30,
    )
    _keep(db_session, client, task["id"])
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    fact = body["explanation"]["reason_facts"][0]
    assert fact["code"] == "unplaced_project_daily_cap"
    assert fact["params"]["daily_cap_minutes"] == 10
    assert fact["params"]["local_date"] == "2026-08-11"
    assert body["explanation"]["outcome"] == "unplaced"
    assert "2026-08-11" in body["summary_text"]
    assert body["explanation"]["placement_facts"]["last_failure"]["reason_code"] == fact["code"]


def test_insufficient_min_block_when_workday_is_shorter(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    # Task create does not accept min/max block yet (schema-only columns).
    _settings(client, workday_minutes=20)
    task = _create_task(client, estimated_duration_minutes=30)
    row = db_session.get(Task, uuid.UUID(task["id"]))
    assert row is not None
    row.min_block_duration_minutes = 30
    row.max_block_duration_minutes = 30
    db_session.flush()
    _keep(db_session, client, task["id"])
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    fact = body["explanation"]["reason_facts"][0]
    assert fact["code"] == "unplaced_insufficient_min_block"
    assert fact["params"]["min_block_minutes"] == 30
    assert body["explanation"]["placed_minutes"] == 0
    assert "30 minutes" in body["summary_text"]


def test_strict_empty_map_is_no_time_map_interval(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    window_id = _window(client, strict=True, bands=[])
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        preferred_time_window_id=window_id,
    )
    _keep(db_session, client, task["id"])
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    assert _codes(body)[0] == "unplaced_no_time_map_interval"
    assert "No allowed Time Map interval" in body["summary_text"]
    assert body["explanation"]["outcome"] == "unplaced"


def test_red_band_covering_the_workday_is_red_exclusion(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    window_id = _window(
        client,
        strict=False,
        bands=[
            {
                "tier": "red",
                "start_time": "08:00",
                "end_time": "16:00",
                "days_of_week": 127,
                "sort_order": 0,
            }
        ],
    )
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        preferred_time_window_id=window_id,
    )
    _keep(db_session, client, task["id"])
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    assert _codes(body)[0] == "unplaced_red_exclusion"
    assert "red bands" in body["summary_text"]
    assert body["explanation"]["outcome"] == "unplaced"


def test_external_busy_conflict_is_its_own_reason(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    task = _create_task(client, estimated_duration_minutes=30, min_block_duration_minutes=30)
    _keep(db_session, client, task["id"])
    account = _account(db_session, _current_user_id(client))
    _cover(
        db_session,
        client,
        pinned_task_id=None,
        account=account,
        start_hour=8,
        end_hour=16,
        source="external",
    )
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    assert _codes(body) == ["unplaced_busy_conflict"]
    assert "External calendar busy" in body["summary_text"]
    assert "Pinned blocks" not in body["summary_text"]


def test_other_task_pin_is_pinned_conflict(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    holder = _create_task(client, estimated_duration_minutes=30, schedule_style="manual")
    task = _create_task(client, estimated_duration_minutes=30, min_block_duration_minutes=30)
    _keep(db_session, client, holder["id"], task["id"])
    _cover(
        db_session,
        client,
        pinned_task_id=uuid.UUID(holder["id"]),
        account=None,
        start_hour=8,
        end_hour=16,
        source="pinned",
    )
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    assert _codes(body) == ["unplaced_pinned_conflict"]
    assert "Pinned blocks conflict" in body["summary_text"]
    holder_body = _explanation(client, holder["id"])
    assert holder_body["explanation"]["reason_facts"][0]["code"] == "excluded_manual_or_bundle"


def test_lifecycle_completed_trashed_and_archived(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    completed = _create_task(client, estimated_duration_minutes=30)
    completed_manual = _create_task(
        client,
        estimated_duration_minutes=30,
        schedule_style="manual",
    )
    trashed = _create_task(client, estimated_duration_minutes=30)
    project = client.post("/api/v1/projects", json={"title": f"f3-arch-{uuid.uuid4().hex[:8]}"})
    assert project.status_code == 201, project.text
    archived = _create_task(
        client,
        estimated_duration_minutes=30,
        project_id=project.json()["id"],
    )
    _keep(
        db_session,
        client,
        completed["id"],
        completed_manual["id"],
        trashed["id"],
        archived["id"],
    )

    for task_id in (completed["id"], completed_manual["id"]):
        row = db_session.get(Task, uuid.UUID(task_id))
        assert row is not None
        row.is_completed = True
    db_session.flush()
    deleted = client.delete(f"/api/v1/tasks/{trashed['id']}")
    assert deleted.status_code == 204, deleted.text
    archived_project = client.post(f"/api/v1/projects/{project.json()['id']}/archive")
    assert archived_project.status_code == 200, archived_project.text

    _replan(client, db_session, monkeypatch)

    completed_body = _explanation(client, completed["id"])
    assert completed_body["explanation"]["reason_facts"][0]["code"] == "excluded_lifecycle_completed"
    assert completed_body["explanation"]["outcome"] == "excluded"
    assert "task completed" in completed_body["summary_text"]

    manual_body = _explanation(client, completed_manual["id"])
    assert (
        manual_body["explanation"]["reason_facts"][0]["code"]
        == "excluded_lifecycle_completed"
    )

    trashed_body = _explanation(client, trashed["id"])
    assert trashed_body["explanation"]["reason_facts"][0]["code"] == "excluded_lifecycle_trashed"
    assert "trash" in trashed_body["summary_text"]

    archived_body = _explanation(client, archived["id"])
    archived_fact = archived_body["explanation"]["reason_facts"][0]
    assert archived_fact["code"] == "excluded_lifecycle_archived"
    assert archived_fact["params"]["archived_scope"] == "project"
    assert "project archived" in archived_body["summary_text"]
    assert archived_body["explanation"]["placed_minutes"] == 0


def test_placed_task_persists_placement_facts(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    _keep(db_session, client, task["id"])
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    explanation = body["explanation"]
    assert explanation["reason_facts"][0]["code"] == "placed"
    assert explanation["outcome"] == "placed"
    assert explanation["placed_minutes"] == 30
    assert explanation["algorithm_version"] == "f3-w2"
    assert explanation["input_snapshot"]["v"] == SNAPSHOT_VERSION
    assert body["is_stale"] is False

    facts = explanation["placement_facts"]
    assert facts["timezone"] == "UTC"
    assert facts["horizon_start"]
    assert facts["horizon_end"]
    assert facts["schedule_style_source"]
    assert "time_window_source" in facts
    assert facts["applicable_override"] is None
    assert facts["placed_blocks"]
    assert facts["placed_blocks"][0]["slice_minutes"] == 30
    assert "last_failure" not in facts


def test_multi_fact_summary_matches_formatter_and_primary_is_first(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    holder = _create_task(client, estimated_duration_minutes=30, schedule_style="manual")
    task = _create_task(client, estimated_duration_minutes=30, min_block_duration_minutes=30)
    _keep(db_session, client, holder["id"], task["id"])
    owner_id = _current_user_id(client)
    account = _account(db_session, owner_id)
    _cover(
        db_session,
        client,
        pinned_task_id=uuid.UUID(holder["id"]),
        account=None,
        start_hour=8,
        end_hour=12,
        source="pinned",
    )
    _cover(
        db_session,
        client,
        pinned_task_id=None,
        account=account,
        start_hour=12,
        end_hour=16,
        source="external",
    )
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    facts = body["explanation"]["reason_facts"]
    assert [fact["code"] for fact in facts] == [
        "unplaced_pinned_conflict",
        "unplaced_busy_conflict",
    ]
    assert body["explanation"]["primary_reason_code"] == facts[0]["code"]
    typed = [ReasonFact(fact["code"], fact.get("params") or {}) for fact in facts]
    assert body["summary_text"] == format_summary_text(typed)
    assert body["summary_text"].index("Pinned blocks") < body["summary_text"].index(
        "External calendar"
    )


def test_stale_v2_categories_and_w3_keys_stay_quiet(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        priority="p4",
    )
    blocker = _create_task(client, estimated_duration_minutes=30, schedule_style="manual")
    dependent = _create_task(client, estimated_duration_minutes=30)
    owner_id = _current_user_id(client)
    db_session.add(
        TaskDependency(
            owner_id=owner_id,
            blocking_task_id=uuid.UUID(blocker["id"]),
            dependent_task_id=uuid.UUID(dependent["id"]),
        )
    )
    _keep(db_session, client, task["id"], blocker["id"], dependent["id"])
    _replan(client, db_session, monkeypatch)

    fresh = _explanation(client, task["id"])
    assert fresh["is_stale"] is False
    assert fresh["stale_categories"] == []
    assert fresh["explanation"]["input_snapshot"]["v"] == SNAPSHOT_VERSION
    for category in W2_STALE_CATEGORIES:
        assert category in fresh["explanation"]["input_snapshot"]
    for deferred in DEFERRED_STALE_CATEGORIES:
        assert deferred not in fresh["explanation"]["input_snapshot"]

    pin = _pin(
        db_session,
        owner_id=owner_id,
        task_id=uuid.UUID(task["id"]),
        start=FIXED_NOW + timedelta(days=1),
        end=FIXED_NOW + timedelta(days=1, minutes=15),
    )
    pinned = _explanation(client, task["id"])
    assert "pins" in pinned["stale_categories"]
    db_session.delete(pin)
    db_session.flush()
    assert _explanation(client, task["id"])["is_stale"] is False

    capped = client.patch(
        "/api/v1/settings",
        json={"max_auto_schedule_minutes_per_project_per_day": 45},
    )
    assert capped.status_code == 200, capped.text
    assert "project_daily_cap" in _explanation(client, task["id"])["stale_categories"]
    cleared = client.patch(
        "/api/v1/settings",
        json={"max_auto_schedule_minutes_per_project_per_day": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert _explanation(client, task["id"])["is_stale"] is False

    shifted = client.patch("/api/v1/settings", json={"timezone": "America/Los_Angeles"})
    assert shifted.status_code == 200, shifted.text
    assert "timezone_horizon_workweek" in _explanation(client, task["id"])["stale_categories"]
    restored = client.patch("/api/v1/settings", json={"timezone": "UTC"})
    assert restored.status_code == 200, restored.text
    assert _explanation(client, task["id"])["is_stale"] is False

    row = db_session.get(Task, uuid.UUID(task["id"]))
    assert row is not None
    row.is_completed = True
    db_session.flush()
    assert "lifecycle" in _explanation(client, task["id"])["stale_categories"]
    row.is_completed = False
    db_session.flush()
    assert _explanation(client, task["id"])["is_stale"] is False

    account = _account(db_session, owner_id)
    event = _external(
        db_session,
        owner_id=owner_id,
        account=account,
        start=FIXED_NOW + timedelta(days=2),
        end=FIXED_NOW + timedelta(days=2, hours=1),
    )
    assert "busy_external" in _explanation(client, task["id"])["stale_categories"]
    db_session.delete(event)
    db_session.flush()
    assert _explanation(client, task["id"])["is_stale"] is False

    due = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"due_at": _iso(FIXED_NOW + timedelta(days=3))},
    )
    assert due.status_code == 200, due.text
    assert "due_at_soft_target" in _explanation(client, task["id"])["stale_categories"]
    undoe = client.patch(f"/api/v1/tasks/{task['id']}", json={"due_at": None})
    assert undoe.status_code == 200, undoe.text
    assert _explanation(client, task["id"])["is_stale"] is False

    priority = client.patch(f"/api/v1/tasks/{task['id']}", json={"priority": "p1"})
    assert priority.status_code == 200, priority.text
    quiet = _explanation(client, task["id"])
    assert quiet["is_stale"] is False
    assert "priority_ups" not in quiet["stale_categories"]
    assert "time_map_overrides" not in quiet["stale_categories"]

    blocker_row = db_session.get(Task, uuid.UUID(blocker["id"]))
    assert blocker_row is not None
    blocker_row.estimated_duration_minutes = 90
    db_session.flush()
    dependent_body = _explanation(client, dependent["id"])
    assert "prerequisite_state" in dependent_body["stale_categories"]
    assert "deps" not in dependent_body["stale_categories"]
