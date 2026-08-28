"""API tests for PATCH /tasks/batch (DEF-015)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, **extra) -> dict:
    task = client.post("/api/v1/tasks", json={"title": f"task-{_uid()}", **extra})
    assert task.status_code == 201, task.text
    return task.json()


def test_batch_patch_schedule_style(client: TestClient) -> None:
    a = _create_task(client)
    b = _create_task(client)

    response = client.patch(
        "/api/v1/tasks/batch",
        json={
            "task_ids": [a["id"], b["id"]],
            "patch": {"schedule_style": "manual"},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 2
    assert {item["id"] for item in body["items"]} == {a["id"], b["id"]}
    assert all(item["schedule_style"] == "manual" for item in body["items"])

    assert client.get(f"/api/v1/tasks/{a['id']}").json()["schedule_style"] == "manual"
    assert client.get(f"/api/v1/tasks/{b['id']}").json()["schedule_style"] == "manual"


def test_batch_add_label_merges(client: TestClient) -> None:
    uid = _uid()
    existing = client.post("/api/v1/labels", json={"name": f"keep-{uid}"}).json()
    added = client.post("/api/v1/labels", json={"name": f"add-{uid}"}).json()
    task = _create_task(client, label_ids=[existing["id"]])

    response = client.patch(
        "/api/v1/tasks/batch",
        json={
            "task_ids": [task["id"]],
            "add_label_ids": [added["id"]],
        },
    )
    assert response.status_code == 200, response.text
    labels = set(response.json()["items"][0]["label_ids"])
    assert labels == {existing["id"], added["id"]}


def test_batch_requires_patch_or_labels(client: TestClient) -> None:
    task = _create_task(client)
    response = client.patch(
        "/api/v1/tasks/batch",
        json={"task_ids": [task["id"]], "patch": {}},
    )
    assert response.status_code == 422


def test_batch_patch_due_at(client: TestClient) -> None:
    a = _create_task(client)
    b = _create_task(client)
    due = "2026-09-01T17:00:00Z"

    response = client.patch(
        "/api/v1/tasks/batch",
        json={"task_ids": [a["id"], b["id"]], "patch": {"due_at": due}},
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 2
    assert all(item["due_at"].startswith("2026-09-01T17:00:00") for item in items)
    assert client.get(f"/api/v1/tasks/{a['id']}").json()["due_at"].startswith("2026-09-01T17:00:00")
    assert client.get(f"/api/v1/tasks/{b['id']}").json()["due_at"].startswith("2026-09-01T17:00:00")


def test_batch_clear_due_at(client: TestClient) -> None:
    a = _create_task(client, due_at="2026-09-01T17:00:00Z")
    b = _create_task(client, due_at="2026-09-02T12:00:00Z")

    response = client.patch(
        "/api/v1/tasks/batch",
        json={"task_ids": [a["id"], b["id"]], "patch": {"due_at": None}},
    )
    assert response.status_code == 200, response.text
    assert all(item["due_at"] is None for item in response.json()["items"])
    assert client.get(f"/api/v1/tasks/{a['id']}").json()["due_at"] is None
    assert client.get(f"/api/v1/tasks/{b['id']}").json()["due_at"] is None


def test_batch_move_project_clears_orphan_section(client: TestClient) -> None:
    source = client.post(
        "/api/v1/projects",
        json={"title": f"src-{_uid()}", "color_hex": "#0A8558"},
    ).json()
    target = client.post(
        "/api/v1/projects",
        json={"title": f"dst-{_uid()}", "color_hex": "#1B6CA8"},
    ).json()
    section = client.post(
        "/api/v1/sections",
        json={"project_id": source["id"], "title": f"sec-{_uid()}", "sort_order": 0},
    ).json()
    a = _create_task(client, project_id=source["id"], section_id=section["id"])
    b = _create_task(client, project_id=source["id"], section_id=section["id"])

    response = client.patch(
        "/api/v1/tasks/batch",
        json={
            "task_ids": [a["id"], b["id"]],
            "patch": {"project_id": target["id"]},
        },
    )
    assert response.status_code == 200, response.text
    for item in response.json()["items"]:
        assert item["project_id"] == target["id"]
        assert item["section_id"] is None

    for task_id in (a["id"], b["id"]):
        got = client.get(f"/api/v1/tasks/{task_id}").json()
        assert got["project_id"] == target["id"]
        assert got["section_id"] is None


def test_batch_add_label_missing_label_404(client: TestClient) -> None:
    task = _create_task(client)
    missing_id = "00000000-0000-4000-8000-000000000001"
    response = client.patch(
        "/api/v1/tasks/batch",
        json={
            "task_ids": [task["id"]],
            "add_label_ids": [missing_id],
        },
    )
    assert response.status_code == 404


def test_batch_move_to_inbox_clears_section(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}", "color_hex": "#0A8558"},
    ).json()
    section = client.post(
        "/api/v1/sections",
        json={"project_id": project["id"], "title": f"sec-{_uid()}", "sort_order": 0},
    ).json()
    task = _create_task(client, project_id=project["id"], section_id=section["id"])

    response = client.patch(
        "/api/v1/tasks/batch",
        json={
            "task_ids": [task["id"]],
            "patch": {"project_id": None},
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["project_id"] is None
    assert item["section_id"] is None

    got = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert got["project_id"] is None
    assert got["section_id"] is None


def test_batch_patch_and_add_labels_combined(client: TestClient) -> None:
    uid = _uid()
    label = client.post("/api/v1/labels", json={"name": f"combo-{uid}"}).json()
    task = _create_task(client)

    response = client.patch(
        "/api/v1/tasks/batch",
        json={
            "task_ids": [task["id"]],
            "patch": {"schedule_style": "manual"},
            "add_label_ids": [label["id"]],
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["schedule_style"] == "manual"
    assert label["id"] in item["label_ids"]
