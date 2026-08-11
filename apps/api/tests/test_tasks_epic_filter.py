"""API tests for epic aggregate task list filter."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_epic_id_filter_returns_tasks_from_linked_projects(client: TestClient) -> None:
    epic = client.post("/api/v1/epics", json={"title": f"epic-{_uid()}"}).json()
    other_epic = client.post("/api/v1/epics", json={"title": f"epic-{_uid()}"}).json()

    linked = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}", "epic_id": epic["id"]},
    ).json()
    other = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}", "epic_id": other_epic["id"]},
    ).json()
    standalone = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}"},
    ).json()

    in_epic = client.post(
        "/api/v1/tasks",
        json={"title": f"in-epic-{_uid()}", "project_id": linked["id"]},
    ).json()
    in_other = client.post(
        "/api/v1/tasks",
        json={"title": f"other-epic-{_uid()}", "project_id": other["id"]},
    ).json()
    in_standalone = client.post(
        "/api/v1/tasks",
        json={"title": f"standalone-{_uid()}", "project_id": standalone["id"]},
    ).json()
    inbox = client.post("/api/v1/tasks", json={"title": f"inbox-{_uid()}"}).json()

    response = client.get("/api/v1/tasks", params={"epic_id": epic["id"], "is_completed": False})
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert in_epic["id"] in ids
    assert in_other["id"] not in ids
    assert in_standalone["id"] not in ids
    assert inbox["id"] not in ids
