"""API tests for inbox filter and nesting depth rejection on create."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, title: str, **extra) -> dict:
    response = client.post("/api/v1/tasks", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_inbox_filter_returns_null_project_tasks(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}"},
    ).json()
    inbox_task = _create_task(client, f"inbox-{_uid()}")
    project_task = _create_task(client, f"proj-task-{_uid()}", project_id=project["id"])

    response = client.get("/api/v1/tasks", params={"inbox": True})
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert inbox_task["id"] in ids
    assert project_task["id"] not in ids
    for item in response.json()["items"]:
        if item["id"] == inbox_task["id"]:
            assert item["project_id"] is None


def test_nesting_depth_rejection_on_create(client: TestClient) -> None:
    root = _create_task(client, f"root-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=root["id"])
    nested = _create_task(client, f"nested-{_uid()}", parent_task_id=child["id"])
    assert nested["nesting_level"] == 2

    response = client.post(
        "/api/v1/tasks",
        json={"title": f"too-deep-{_uid()}", "parent_task_id": nested["id"]},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "NESTING_DEPTH_EXCEEDED"


def test_parent_not_found_on_create(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tasks",
        json={"title": f"orphan-{_uid()}", "parent_task_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "PARENT_NOT_FOUND"
