"""API and integration tests for Update Schedule replan."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ScheduleRun, ScheduledBlock
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


def _prepare_settings(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={
            "timezone": "UTC",
            "workweek_days": 7,
            "upcoming_horizon_days": 7,
            "inter_block_buffer_minutes": 0,
            "default_schedule_style": "standalone",
        },
    )
    assert response.status_code == 200, response.text


def _create_task(client: TestClient, **extra: object) -> dict:
    payload = {"title": f"task-{_uid()}", **extra}
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _replan_sync(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    # Prevent daemon thread (separate connection can't see the test transaction).
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
    return got.json()


def _current_user_id(client: TestClient) -> uuid.UUID:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    return uuid.UUID(me.json()["id"])


def test_replan_places_task_end_to_end(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=30)

    run = _replan_sync(client, db_session, monkeypatch)
    assert run["status"] == "completed"
    assert run["tasks_scheduled"] >= 1
    assert run["blocks_created"] >= 1

    refreshed = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert refreshed["status"] == "scheduled"

    horizon_start = FIXED_NOW
    horizon_end = FIXED_NOW + timedelta(days=7)
    blocks = client.get(
        "/api/v1/scheduled-blocks",
        params={"start": _iso(horizon_start), "end": _iso(horizon_end)},
    )
    assert blocks.status_code == 200
    task_blocks = [row for row in blocks.json()["items"] if row["task_id"] == task["id"]]
    assert len(task_blocks) >= 1


def test_replan_409_when_fresh_run_in_progress(client: TestClient, db_session: Session) -> None:
    owner_id = _current_user_id(client)
    db_session.add(ScheduleRun(owner_id=owner_id, status="running", started_at=datetime.now(UTC)))
    db_session.flush()

    response = client.post("/api/v1/schedule/replan")
    assert response.status_code == 409
    assert response.json()["code"] == "SCHEDULE_RUN_IN_PROGRESS"


def test_stale_reclaim_allows_new_run(client: TestClient, db_session: Session) -> None:
    owner_id = _current_user_id(client)
    stale_started = datetime.now(UTC) - timedelta(minutes=20)
    db_session.add(
        ScheduleRun(
            owner_id=owner_id,
            status="running",
            started_at=stale_started,
        )
    )
    db_session.flush()

    response = client.post("/api/v1/schedule/replan")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "running"


def test_pinned_block_avoided(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    # Pin covers 60m of a 120m task so remaining work still needs auto placement.
    task = _create_task(client, estimated_duration_minutes=120)

    pin_start = datetime(2026, 8, 11, 13, 0, tzinfo=UTC)
    pin_end = pin_start + timedelta(hours=1)
    db_session.add(
        ScheduledBlock(
            owner_id=_current_user_id(client),
            task_id=uuid.UUID(task["id"]),
            start_time=pin_start,
            end_time=pin_end,
            is_pinned=True,
        )
    )
    db_session.flush()

    _replan_sync(client, db_session, monkeypatch)

    horizon_start = FIXED_NOW
    horizon_end = FIXED_NOW + timedelta(days=7)
    blocks = client.get(
        "/api/v1/scheduled-blocks",
        params={"start": _iso(horizon_start), "end": _iso(horizon_end)},
    ).json()["items"]
    auto_blocks = [row for row in blocks if row["task_id"] == task["id"] and not row["is_pinned"]]
    assert auto_blocks
    for block in auto_blocks:
        auto_start = datetime.fromisoformat(block["start_time"].replace("Z", "+00:00"))
        auto_end = datetime.fromisoformat(block["end_time"].replace("Z", "+00:00"))
        overlaps = auto_start < pin_end and auto_end > pin_start
        assert not overlaps


def test_overbook_when_deadline_too_tight(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=120,
        deadline_at=_iso(FIXED_NOW + timedelta(minutes=30)),
    )

    run = _replan_sync(client, db_session, monkeypatch)
    assert run["status"] == "completed"
    assert run["overbooked_count"] >= 1

    refreshed = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert refreshed["status"] == "overbooked"


def test_bundle_gate_skips_auto_placement(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    patch = client.patch("/api/v1/settings", json={"default_schedule_style": "bundle"})
    assert patch.status_code == 200

    _create_task(client, estimated_duration_minutes=30)
    run = _replan_sync(client, db_session, monkeypatch)
    assert run["tasks_scheduled"] == 0
    assert run["blocks_created"] == 0


def test_get_run_not_found_for_other_user(client: TestClient) -> None:
    missing = client.get(f"/api/v1/schedule/runs/{uuid.uuid4()}")
    assert missing.status_code == 404


def test_get_run_requires_auth(auth_client: TestClient) -> None:
    response = auth_client.get(f"/api/v1/schedule/runs/{uuid.uuid4()}")
    assert response.status_code == 401


def test_tasks_route_does_not_import_scheduler() -> None:
    source = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "tasks.py"
    text = source.read_text(encoding="utf-8")
    assert "from app.scheduler" not in text
    assert "import app.scheduler" not in text
