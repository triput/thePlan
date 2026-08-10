"""API tests for task complete / OPEN_CHILDREN / force_parent_only / bulk."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, title: str, **extra) -> dict:
    body = {"title": title, **extra}
    response = client.post("/api/v1/tasks", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_leaf_task_without_flags(client: TestClient) -> None:
    task = _create_task(client, f"leaf-{_uid()}")
    response = client.post(f"/api/v1/tasks/{task['id']}/complete", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["is_completed"] is True
    assert body["completed_at"] is not None
    assert body["status"] == "completed"


def test_complete_parent_with_open_children_omitted_returns_409(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])

    response = client.post(f"/api/v1/tasks/{parent['id']}/complete", json={})
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "OPEN_CHILDREN"
    assert body["open_count"] == 1
    assert "detail" in body

    still = client.get(f"/api/v1/tasks/{parent['id']}")
    assert still.json()["is_completed"] is False


def test_complete_parent_bulk_children_false_completes_parent_only(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])

    response = client.post(
        f"/api/v1/tasks/{parent['id']}/complete",
        json={"bulk_children": False},
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_completed"] is True

    child_after = client.get(f"/api/v1/tasks/{child['id']}")
    assert child_after.json()["is_completed"] is False


def test_complete_parent_force_parent_only(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])

    response = client.post(
        f"/api/v1/tasks/{parent['id']}/complete",
        json={"force_parent_only": True},
    )
    assert response.status_code == 200
    assert response.json()["is_completed"] is True
    assert client.get(f"/api/v1/tasks/{child['id']}").json()["is_completed"] is False


def test_complete_parent_bulk_children_true_completes_descendants(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])
    nested = _create_task(client, f"nested-{_uid()}", parent_task_id=child["id"])

    response = client.post(
        f"/api/v1/tasks/{parent['id']}/complete",
        json={"bulk_children": True},
    )
    assert response.status_code == 200
    assert response.json()["is_completed"] is True
    assert client.get(f"/api/v1/tasks/{child['id']}").json()["is_completed"] is True
    assert client.get(f"/api/v1/tasks/{nested['id']}").json()["is_completed"] is True


def test_uncomplete_parent_does_not_uncomplete_children(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])
    client.post(
        f"/api/v1/tasks/{parent['id']}/complete",
        json={"bulk_children": True},
    )

    response = client.post(f"/api/v1/tasks/{parent['id']}/uncomplete")
    assert response.status_code == 200
    assert response.json()["is_completed"] is False
    assert client.get(f"/api/v1/tasks/{child['id']}").json()["is_completed"] is True
