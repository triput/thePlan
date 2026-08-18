"""API and scheduler tests for epic/project Time Map bind + live inherit (DEF-018)."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, joinedload

from app.models import Epic, FocusWindow, Project, Task, UserSettings
from app.scheduler.placement import place_task
from app.scheduler.windows import effective_preferred_time_window_id


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _owned_window_id(client: TestClient) -> str:
    windows = client.get("/api/v1/focus-windows").json()
    morning = next(row for row in windows if row["name"] == "Morning")
    return morning["id"]


def _settings(**overrides: object) -> UserSettings:
    settings = UserSettings(owner_id=uuid.uuid4())
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def test_post_epic_owned_window(client: TestClient) -> None:
    window_id = _owned_window_id(client)
    response = client.post(
        "/api/v1/epics",
        json={"title": f"epic-map-{_uid()}", "preferred_time_window_id": window_id},
    )
    assert response.status_code == 201, response.text
    assert response.json()["preferred_time_window_id"] == window_id


def test_post_project_owned_window(client: TestClient) -> None:
    window_id = _owned_window_id(client)
    response = client.post(
        "/api/v1/projects",
        json={"title": f"proj-map-{_uid()}", "preferred_time_window_id": window_id},
    )
    assert response.status_code == 201, response.text
    assert response.json()["preferred_time_window_id"] == window_id


def test_post_epic_unknown_window_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/epics",
        json={
            "title": f"epic-bad-{_uid()}",
            "preferred_time_window_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


def test_post_project_unknown_window_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": f"proj-bad-{_uid()}",
            "preferred_time_window_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


def test_patch_epic_owned_window_then_clear_and_omit(client: TestClient) -> None:
    window_id = _owned_window_id(client)
    created = client.post("/api/v1/epics", json={"title": f"epic-patch-{_uid()}"}).json()
    epic_id = created["id"]
    assert created["preferred_time_window_id"] is None

    bound = client.patch(
        f"/api/v1/epics/{epic_id}",
        json={"preferred_time_window_id": window_id},
    )
    assert bound.status_code == 200, bound.text
    assert bound.json()["preferred_time_window_id"] == window_id

    titled = client.patch(
        f"/api/v1/epics/{epic_id}",
        json={"title": f"epic-keep-map-{_uid()}"},
    )
    assert titled.status_code == 200, titled.text
    assert titled.json()["preferred_time_window_id"] == window_id

    cleared = client.patch(
        f"/api/v1/epics/{epic_id}",
        json={"preferred_time_window_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["preferred_time_window_id"] is None


def test_patch_project_owned_window_then_clear_and_omit(client: TestClient) -> None:
    window_id = _owned_window_id(client)
    created = client.post(
        "/api/v1/projects",
        json={"title": f"proj-patch-{_uid()}"},
    ).json()
    project_id = created["id"]
    assert created["preferred_time_window_id"] is None

    bound = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"preferred_time_window_id": window_id},
    )
    assert bound.status_code == 200, bound.text
    assert bound.json()["preferred_time_window_id"] == window_id

    titled = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": f"proj-keep-map-{_uid()}"},
    )
    assert titled.status_code == 200, titled.text
    assert titled.json()["preferred_time_window_id"] == window_id

    cleared = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"preferred_time_window_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["preferred_time_window_id"] is None


def test_effective_preferred_time_window_id_precedence() -> None:
    owner_id = uuid.uuid4()
    task_id = uuid.uuid4()
    project_id = uuid.uuid4()
    epic_id = uuid.uuid4()

    task = Task(owner_id=owner_id, title="inherit-task", preferred_time_window_id=task_id)
    project = Project(
        owner_id=owner_id, title="inherit-proj", preferred_time_window_id=project_id
    )
    epic = Epic(owner_id=owner_id, title="inherit-epic", preferred_time_window_id=epic_id)

    assert effective_preferred_time_window_id(task, project, epic) == task_id

    task.preferred_time_window_id = None
    assert effective_preferred_time_window_id(task, project, epic) == project_id

    project.preferred_time_window_id = None
    assert effective_preferred_time_window_id(task, project, epic) == epic_id

    epic.preferred_time_window_id = None
    assert effective_preferred_time_window_id(task, project, epic) is None

    inbox = Task(owner_id=owner_id, title="inbox", preferred_time_window_id=None)
    assert effective_preferred_time_window_id(inbox, None, None) is None


def test_place_task_inherits_project_strict_map_sibling_unbound(
    db_session: Session,
    client: TestClient,
    monkeypatch,
) -> None:
    import app.scheduler.placement as placement_mod

    fixed_now = datetime(2026, 8, 11, 7, 0, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            if tz is not None:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(placement_mod, "datetime", FixedDatetime)

    client.patch(
        "/api/v1/settings",
        json={
            "timezone": "UTC",
            "workweek_days": 7,
            "upcoming_horizon_days": 1,
            "inter_block_buffer_minutes": 0,
            "workday_start_local": "08:00",
            "workday_minutes": 600,
        },
    )

    created_map = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"Strict afternoon {_uid()}",
            "strict_mode": True,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "16:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert created_map.status_code == 201, created_map.text
    map_id = UUID(created_map.json()["id"])

    project_a = client.post(
        "/api/v1/projects",
        json={
            "title": f"bound-proj-{_uid()}",
            "preferred_time_window_id": str(map_id),
        },
    )
    assert project_a.status_code == 201, project_a.text
    project_a_id = UUID(project_a.json()["id"])

    project_b = client.post(
        "/api/v1/projects",
        json={"title": f"unbound-proj-{_uid()}"},
    )
    assert project_b.status_code == 201, project_b.text
    project_b_id = UUID(project_b.json()["id"])

    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    task_a = Task(
        owner_id=owner_id,
        title="inherit A",
        project_id=project_a_id,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=120,
        preferred_time_window_id=None,
    )
    task_b = Task(
        owner_id=owner_id,
        title="unbound B",
        project_id=project_b_id,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=120,
        preferred_time_window_id=None,
    )
    db_session.add_all([task_a, task_b])
    db_session.flush()

    project_a_row = db_session.get(Project, project_a_id)
    project_b_row = db_session.get(Project, project_b_id)
    assert project_a_row is not None
    assert project_b_row is not None

    effective_a = effective_preferred_time_window_id(task_a, project_a_row, None)
    assert effective_a == map_id
    assert effective_preferred_time_window_id(task_b, project_b_row, None) is None

    preferred = (
        db_session.query(FocusWindow)
        .options(joinedload(FocusWindow.bands))
        .filter(FocusWindow.id == map_id)
        .one()
    )
    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )
    horizon_start = fixed_now
    horizon_end = fixed_now.replace(hour=23, minute=59)

    result_a, _ = place_task(
        db_session,
        task=task_a,
        owner_id=owner_id,
        settings=settings,
        remaining_minutes=30,
        busy=[],
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        preferred_windows={preferred.id: preferred},
        now_utc=fixed_now,
        preferred_window_id=effective_a,
    )
    assert result_a.blocks_created == 1
    assert task_a.scheduled_blocks[0].start_time == datetime(
        2026, 8, 11, 14, 0, tzinfo=timezone.utc
    )

    result_b, _ = place_task(
        db_session,
        task=task_b,
        owner_id=owner_id,
        settings=settings,
        remaining_minutes=30,
        busy=[],
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        preferred_windows={preferred.id: preferred},
        now_utc=fixed_now,
        preferred_window_id=None,
    )
    assert result_b.blocks_created == 1
    assert task_b.scheduled_blocks[0].start_time == datetime(
        2026, 8, 11, 8, 0, tzinfo=timezone.utc
    )
