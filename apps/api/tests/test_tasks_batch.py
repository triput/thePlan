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
