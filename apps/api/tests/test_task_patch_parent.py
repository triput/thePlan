"""PATCH parent_task_id cycle guards (P1 correctness)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, title: str, **extra) -> dict:
    response = client.post("/api/v1/tasks", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_patch_parent_self_rejected(client: TestClient) -> None:
    task = _create_task(client, f"self-parent-{_uid()}")
    response = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"parent_task_id": task["id"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PARENT_CYCLE"


def test_patch_parent_descendant_rejected(client: TestClient) -> None:
    root = _create_task(client, f"root-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=root["id"])
    nested = _create_task(client, f"nested-{_uid()}", parent_task_id=child["id"])

    to_child = client.patch(
        f"/api/v1/tasks/{root['id']}",
        json={"parent_task_id": child["id"]},
    )
    assert to_child.status_code == 422
    assert to_child.json()["code"] == "PARENT_CYCLE"

    to_nested = client.patch(
        f"/api/v1/tasks/{root['id']}",
        json={"parent_task_id": nested["id"]},
    )
    assert to_nested.status_code == 422
    assert to_nested.json()["code"] == "PARENT_CYCLE"
