"""API tests for epic aggregate task list filter."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_epic(client: TestClient, title: str) -> dict:
    response = client.post("/api/v1/epics", json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()


def _create_project(client: TestClient, title: str, **extra) -> dict:
    response = client.post("/api/v1/projects", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _create_task(client: TestClient, title: str, **extra) -> dict:
    response = client.post("/api/v1/tasks", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_epic_id_filter_returns_tasks_from_linked_projects(client: TestClient) -> None:
    epic = _create_epic(client, f"epic-{_uid()}")
    other_epic = _create_epic(client, f"epic-{_uid()}")

    linked = _create_project(client, f"proj-{_uid()}", epic_id=epic["id"])
    other = _create_project(client, f"proj-{_uid()}", epic_id=other_epic["id"])
    standalone = _create_project(client, f"proj-{_uid()}")

    in_epic = _create_task(client, f"in-epic-{_uid()}", project_id=linked["id"])
    in_other = _create_task(client, f"other-epic-{_uid()}", project_id=other["id"])
    in_standalone = _create_task(client, f"standalone-{_uid()}", project_id=standalone["id"])
    inbox = _create_task(client, f"inbox-{_uid()}")

    response = client.get("/api/v1/tasks", params={"epic_id": epic["id"], "is_completed": False})
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert in_epic["id"] in ids
    assert in_other["id"] not in ids
    assert in_standalone["id"] not in ids
    assert inbox["id"] not in ids
