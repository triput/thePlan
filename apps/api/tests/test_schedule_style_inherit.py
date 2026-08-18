"""API tests for schedule_style inherit (project/epic) and PATCH round-trip (DEF-014)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_schedule_replan import (
    FIXED_NOW,
    _create_task,
    _iso,
    _patch_schedule_clock,
    _prepare_settings,
    _replan_sync,
)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _horizon_blocks(client: TestClient) -> list[dict]:
    horizon_start = FIXED_NOW
    horizon_end = FIXED_NOW + timedelta(days=7)
    response = client.get(
        "/api/v1/scheduled-blocks",
        params={"start": _iso(horizon_start), "end": _iso(horizon_end)},
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _create_epic(client: TestClient, **extra: object) -> dict:
    payload = {"title": f"epic-{_uid()}", **extra}
    response = client.post("/api/v1/epics", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_project(client: TestClient, **extra: object) -> dict:
    payload = {"title": f"proj-{_uid()}", **extra}
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_project_manual_skips_sibling_unbound_places(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)

    project_manual = _create_project(client, schedule_style="manual")
    project_unbound = _create_project(client)
    assert project_unbound["schedule_style"] is None

    task_manual = _create_task(
        client,
        estimated_duration_minutes=30,
        project_id=project_manual["id"],
    )
    task_unbound = _create_task(
        client,
        estimated_duration_minutes=30,
        project_id=project_unbound["id"],
        priority="p1",
            deadline_at=_iso(FIXED_NOW + timedelta(days=6)),
    )
    assert task_manual["schedule_style"] is None
    assert task_unbound["schedule_style"] is None

    _replan_sync(client, db_session, monkeypatch)
    blocks = _horizon_blocks(client)
    skipped = [row for row in blocks if row["task_id"] == task_manual["id"]]
    placed = [row for row in blocks if row["task_id"] == task_unbound["id"]]
    assert skipped == []
    assert len(placed) >= 1


def test_epic_manual_inherited_by_null_project_and_task_skips(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)

    epic = _create_epic(client, schedule_style="manual")
    project = _create_project(client, epic_id=epic["id"])
    assert project["schedule_style"] is None
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        project_id=project["id"],
    )
    assert task["schedule_style"] is None

    _replan_sync(client, db_session, monkeypatch)
    blocks = _horizon_blocks(client)
    task_blocks = [row for row in blocks if row["task_id"] == task["id"]]
    assert task_blocks == []


def test_task_standalone_override_on_manual_project_places(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)

    project = _create_project(client, schedule_style="manual")
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        project_id=project["id"],
        schedule_style="standalone",
        priority="p1",
            deadline_at=_iso(FIXED_NOW + timedelta(days=6)),
    )

    _replan_sync(client, db_session, monkeypatch)
    blocks = _horizon_blocks(client)
    task_blocks = [row for row in blocks if row["task_id"] == task["id"]]
    assert len(task_blocks) >= 1

    refreshed = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert refreshed["status"] == "scheduled"


def test_epic_schedule_style_round_trip(client: TestClient) -> None:
    created = client.post("/api/v1/epics", json={"title": f"epic-style-{_uid()}"})
    assert created.status_code == 201, created.text
    epic_id = created.json()["id"]
    assert created.json()["schedule_style"] is None

    bound = client.patch(f"/api/v1/epics/{epic_id}", json={"schedule_style": "manual"})
    assert bound.status_code == 200, bound.text
    assert bound.json()["schedule_style"] == "manual"

    got = client.get(f"/api/v1/epics/{epic_id}")
    assert got.status_code == 200, got.text
    assert got.json()["schedule_style"] == "manual"

    titled = client.patch(
        f"/api/v1/epics/{epic_id}",
        json={"title": f"epic-keep-style-{_uid()}"},
    )
    assert titled.status_code == 200, titled.text
    assert titled.json()["schedule_style"] == "manual"

    cleared = client.patch(f"/api/v1/epics/{epic_id}", json={"schedule_style": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["schedule_style"] is None


def test_project_schedule_style_round_trip(client: TestClient) -> None:
    created = client.post("/api/v1/projects", json={"title": f"proj-style-{_uid()}"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    assert created.json()["schedule_style"] is None

    bound = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"schedule_style": "manual"},
    )
    assert bound.status_code == 200, bound.text
    assert bound.json()["schedule_style"] == "manual"

    got = client.get(f"/api/v1/projects/{project_id}")
    assert got.status_code == 200, got.text
    assert got.json()["schedule_style"] == "manual"

    titled = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": f"proj-keep-style-{_uid()}"},
    )
    assert titled.status_code == 200, titled.text
    assert titled.json()["schedule_style"] == "manual"

    cleared = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"schedule_style": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["schedule_style"] is None
