"""DEF-024: soft-delete / trash list / restore for tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ScheduledBlock, Task


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, title: str, **extra) -> dict:
    body = {"title": title, **extra}
    response = client.post("/api/v1/tasks", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_soft_delete_hides_from_list_trash_lists_and_restore(
    client: TestClient,
) -> None:
    task = _create_task(client, f"trash-me-{_uid()}")
    task_id = task["id"]

    listed = client.get("/api/v1/tasks", params={"ids": [task_id]})
    assert listed.status_code == 200
    assert any(item["id"] == task_id for item in listed.json()["items"])

    deleted = client.delete(f"/api/v1/tasks/{task_id}")
    assert deleted.status_code == 204

    hidden = client.get("/api/v1/tasks", params={"ids": [task_id]})
    assert hidden.status_code == 200
    assert all(item["id"] != task_id for item in hidden.json()["items"])

    trash = client.get("/api/v1/tasks", params={"trashed": True})
    assert trash.status_code == 200
    trash_items = trash.json()["items"]
    match = next(item for item in trash_items if item["id"] == task_id)
    assert match["deleted_at"] is not None

    detail = client.get(f"/api/v1/tasks/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["deleted_at"] is not None

    restored = client.post(f"/api/v1/tasks/{task_id}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["deleted_at"] is None
    assert restored.json()["id"] == task_id

    again = client.get("/api/v1/tasks", params={"ids": [task_id]})
    assert any(item["id"] == task_id for item in again.json()["items"])
    assert all(
        item["deleted_at"] is None
        for item in again.json()["items"]
        if item["id"] == task_id
    )


def test_soft_delete_cascades_subtree_and_restore_wave(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])
    nested = _create_task(client, f"nested-{_uid()}", parent_task_id=child["id"])
    sibling = _create_task(client, f"sibling-{_uid()}")

    assert client.delete(f"/api/v1/tasks/{parent['id']}").status_code == 204

    for task_id in (parent["id"], child["id"], nested["id"]):
        body = client.get(f"/api/v1/tasks/{task_id}").json()
        assert body["deleted_at"] is not None

    assert client.get(f"/api/v1/tasks/{sibling['id']}").json()["deleted_at"] is None

    trash = client.get("/api/v1/tasks", params={"trashed": True}).json()["items"]
    trash_ids = {item["id"] for item in trash}
    assert parent["id"] in trash_ids
    assert child["id"] in trash_ids
    assert nested["id"] in trash_ids
    assert sibling["id"] not in trash_ids

    wave = client.get(f"/api/v1/tasks/{parent['id']}").json()["deleted_at"]
    assert client.get(f"/api/v1/tasks/{child['id']}").json()["deleted_at"] == wave
    assert client.get(f"/api/v1/tasks/{nested['id']}").json()["deleted_at"] == wave

    restored = client.post(f"/api/v1/tasks/{parent['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    for task_id in (parent["id"], child["id"], nested["id"]):
        assert client.get(f"/api/v1/tasks/{task_id}").json()["deleted_at"] is None


def test_soft_delete_hard_drops_unpinned_blocks_keeps_pinned(
    client: TestClient,
    db_session: Session,
) -> None:
    task = _create_task(client, f"blocked-{_uid()}")
    task_uuid = uuid.UUID(task["id"])
    owner_id = db_session.get(Task, task_uuid).owner_id
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)
    unpinned = ScheduledBlock(
        owner_id=owner_id,
        task_id=task_uuid,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        is_pinned=False,
    )
    pinned = ScheduledBlock(
        owner_id=owner_id,
        task_id=task_uuid,
        start_time=start + timedelta(hours=2),
        end_time=start + timedelta(hours=2, minutes=30),
        is_pinned=True,
    )
    db_session.add_all([unpinned, pinned])
    db_session.flush()
    unpinned_id = unpinned.id
    pinned_id = pinned.id

    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204

    assert db_session.get(ScheduledBlock, unpinned_id) is None
    kept = db_session.get(ScheduledBlock, pinned_id)
    assert kept is not None
    assert kept.is_pinned is True


def test_restore_non_trashed_returns_409(client: TestClient) -> None:
    task = _create_task(client, f"alive-{_uid()}")
    response = client.post(f"/api/v1/tasks/{task['id']}/restore")
    assert response.status_code == 409
    assert response.json()["code"] == "NOT_TRASHED"
