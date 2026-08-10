"""API tests for batch reorder endpoints."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_project(client: TestClient, *, sort_order: int = 0) -> dict:
    project = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}", "color_hex": "#0A8558"},
    )
    assert project.status_code == 201, project.text
    body = project.json()
    if sort_order != 0:
        patched = client.patch(f"/api/v1/projects/{body['id']}", json={"sort_order": sort_order})
        assert patched.status_code == 200, patched.text
        body = patched.json()
    return body


def _create_section(client: TestClient, project_id: str, *, sort_order: int = 0) -> dict:
    section = client.post(
        "/api/v1/sections",
        json={"project_id": project_id, "title": f"sec-{_uid()}", "sort_order": sort_order},
    )
    assert section.status_code == 201, section.text
    return section.json()


def _create_task(client: TestClient, *, sort_order: int = 0, **extra) -> dict:
    payload = {"title": f"task-{_uid()}", **extra}
    if sort_order != 0:
        payload["sort_order"] = sort_order
    task = client.post("/api/v1/tasks", json=payload)
    assert task.status_code == 201, task.text
    body = task.json()
    if sort_order != 0 and body["sort_order"] != sort_order:
        patched = client.patch(f"/api/v1/tasks/{body['id']}", json={"sort_order": sort_order})
        assert patched.status_code == 200, patched.text
        body = patched.json()
    return body


def test_reorder_projects_updates_sort_order(client: TestClient) -> None:
    first = _create_project(client, sort_order=0)
    second = _create_project(client, sort_order=1)

    response = client.patch(
        "/api/v1/projects/reorder",
        json={
            "items": [
                {"id": first["id"], "sort_order": 5},
                {"id": second["id"], "sort_order": 2},
            ]
        },
    )
    assert response.status_code == 204, response.text

    listed = client.get("/api/v1/projects", params={"sort": "sort_order"})
    assert listed.status_code == 200
    by_id = {item["id"]: item for item in listed.json()["items"]}
    assert by_id[first["id"]]["sort_order"] == 5
    assert by_id[second["id"]]["sort_order"] == 2


def test_reorder_projects_missing_id_404(client: TestClient) -> None:
    project = _create_project(client)
    missing_id = str(uuid.uuid4())

    response = client.patch(
        "/api/v1/projects/reorder",
        json={
            "items": [
                {"id": project["id"], "sort_order": 0},
                {"id": missing_id, "sort_order": 1},
            ]
        },
    )
    assert response.status_code == 404
    assert missing_id in response.json()["detail"]


def test_reorder_sections_updates_sort_order(client: TestClient) -> None:
    project = _create_project(client)
    alpha = _create_section(client, project["id"], sort_order=0)
    beta = _create_section(client, project["id"], sort_order=1)

    response = client.patch(
        "/api/v1/sections/reorder",
        json={
            "items": [
                {"id": alpha["id"], "sort_order": 10},
                {"id": beta["id"], "sort_order": 3},
            ]
        },
    )
    assert response.status_code == 204, response.text

    listed = client.get("/api/v1/sections", params={"project_id": project["id"]})
    assert listed.status_code == 200
    by_id = {item["id"]: item for item in listed.json()["items"]}
    assert by_id[alpha["id"]]["sort_order"] == 10
    assert by_id[beta["id"]]["sort_order"] == 3


def test_reorder_tasks_updates_sort_order(client: TestClient) -> None:
    first = _create_task(client, sort_order=0)
    second = _create_task(client, sort_order=1)

    response = client.patch(
        "/api/v1/tasks/reorder",
        json={
            "items": [
                {"id": first["id"], "sort_order": 7},
                {"id": second["id"], "sort_order": 4},
            ]
        },
    )
    assert response.status_code == 204, response.text

    listed = client.get("/api/v1/tasks")
    assert listed.status_code == 200
    by_id = {item["id"]: item for item in listed.json()["items"]}
    assert by_id[first["id"]]["sort_order"] == 7
    assert by_id[second["id"]]["sort_order"] == 4


def test_reorder_tasks_missing_id_404(client: TestClient) -> None:
    task = _create_task(client)
    missing_id = str(uuid.uuid4())

    response = client.patch(
        "/api/v1/tasks/reorder",
        json={"items": [{"id": missing_id, "sort_order": 0}]},
    )
    assert response.status_code == 404
    assert missing_id in response.json()["detail"]

    unchanged = client.get(f"/api/v1/tasks/{task['id']}")
    assert unchanged.status_code == 200
    assert unchanged.json()["sort_order"] == task["sort_order"]
