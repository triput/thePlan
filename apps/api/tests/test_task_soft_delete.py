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


def test_empty_trash_hard_deletes_trashed_only(client: TestClient, db_session: Session) -> None:
    trashed_a = _create_task(client, f"trash-a-{_uid()}")
    trashed_b = _create_task(client, f"trash-b-{_uid()}")
    live = _create_task(client, f"live-{_uid()}")

    assert client.delete(f"/api/v1/tasks/{trashed_a['id']}").status_code == 204
    assert client.delete(f"/api/v1/tasks/{trashed_b['id']}").status_code == 204

    trash_before = client.get("/api/v1/tasks", params={"trashed": True}).json()["items"]
    assert len(trash_before) == 2

    emptied = client.delete("/api/v1/tasks/trash")
    assert emptied.status_code == 204

    trash_after = client.get("/api/v1/tasks", params={"trashed": True}).json()["items"]
    assert trash_after == []

    assert client.get(f"/api/v1/tasks/{trashed_a['id']}").status_code == 404
    assert client.get(f"/api/v1/tasks/{trashed_b['id']}").status_code == 404
    assert db_session.get(Task, uuid.UUID(trashed_a["id"])) is None
    assert db_session.get(Task, uuid.UUID(trashed_b["id"])) is None

    live_list = client.get("/api/v1/tasks", params={"ids": [live["id"]]}).json()["items"]
    assert any(item["id"] == live["id"] for item in live_list)
    assert client.get(f"/api/v1/tasks/{live['id']}").status_code == 200


def test_empty_trash_leaves_live_tasks_when_trash_empty(client: TestClient) -> None:
    live = _create_task(client, f"still-live-{_uid()}")
    assert client.delete("/api/v1/tasks/trash").status_code == 204
    assert client.get(f"/api/v1/tasks/{live['id']}").status_code == 200


def test_empty_trash_purges_subtree_and_blocks(
    client: TestClient,
    db_session: Session,
) -> None:
    parent = _create_task(client, f"purge-parent-{_uid()}")
    child = _create_task(client, f"purge-child-{_uid()}", parent_task_id=parent["id"])
    sibling = _create_task(client, f"purge-sibling-{_uid()}")

    task_uuid = uuid.UUID(parent["id"])
    owner_id = db_session.get(Task, task_uuid).owner_id
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)
    pinned = ScheduledBlock(
        owner_id=owner_id,
        task_id=task_uuid,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        is_pinned=True,
    )
    db_session.add(pinned)
    db_session.flush()
    pinned_id = pinned.id

    assert client.delete(f"/api/v1/tasks/{parent['id']}").status_code == 204
    assert client.delete("/api/v1/tasks/trash").status_code == 204

    assert db_session.get(Task, uuid.UUID(parent["id"])) is None
    assert db_session.get(Task, uuid.UUID(child["id"])) is None
    assert db_session.get(ScheduledBlock, pinned_id) is None
    assert client.get(f"/api/v1/tasks/{sibling['id']}").status_code == 200


def test_hard_purge_single_trashed_task(client: TestClient, db_session: Session) -> None:
    task = _create_task(client, f"hard-one-{_uid()}")
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204

    purged = client.delete(f"/api/v1/tasks/{task['id']}", params={"hard": True})
    assert purged.status_code == 204
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
    assert db_session.get(Task, uuid.UUID(task["id"])) is None


def test_hard_purge_live_task_rejected(client: TestClient) -> None:
    task = _create_task(client, f"hard-live-{_uid()}")
    response = client.delete(f"/api/v1/tasks/{task['id']}", params={"hard": True})
    assert response.status_code == 409
    assert response.json()["code"] == "NOT_TRASHED"
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 200


def test_restore_after_empty_trash_other_items(client: TestClient) -> None:
    keep = _create_task(client, f"keep-restore-{_uid()}")
    toss = _create_task(client, f"toss-{_uid()}")

    assert client.delete(f"/api/v1/tasks/{toss['id']}").status_code == 204
    assert client.delete("/api/v1/tasks/trash").status_code == 204

    restored = client.post(f"/api/v1/tasks/{keep['id']}/restore")
    assert restored.status_code == 409
    assert client.get(f"/api/v1/tasks/{keep['id']}").status_code == 200


def test_empty_trash_older_than_days_selective(
    client: TestClient,
    db_session: Session,
) -> None:
    old = _create_task(client, f"old-trash-{_uid()}")
    recent = _create_task(client, f"recent-trash-{_uid()}")
    live = _create_task(client, f"live-keep-{_uid()}")

    assert client.delete(f"/api/v1/tasks/{old['id']}").status_code == 204
    assert client.delete(f"/api/v1/tasks/{recent['id']}").status_code == 204

    old_row = db_session.get(Task, uuid.UUID(old["id"]))
    assert old_row is not None
    old_row.deleted_at = datetime.now(timezone.utc) - timedelta(days=45)
    db_session.commit()

    purged = client.delete("/api/v1/tasks/trash", params={"older_than_days": 30})
    assert purged.status_code == 204

    assert db_session.get(Task, uuid.UUID(old["id"])) is None
    assert client.get(f"/api/v1/tasks/{recent['id']}").status_code == 200
    assert client.get(f"/api/v1/tasks/{recent['id']}").json()["deleted_at"] is not None
    assert client.get(f"/api/v1/tasks/{live['id']}").status_code == 200

    trash = client.get("/api/v1/tasks", params={"trashed": True}).json()["items"]
    trash_ids = {item["id"] for item in trash}
    assert recent["id"] in trash_ids
    assert old["id"] not in trash_ids


def test_empty_trash_older_than_days_rejects_zero(client: TestClient) -> None:
    response = client.delete("/api/v1/tasks/trash", params={"older_than_days": 0})
    assert response.status_code == 422


def test_restore_child_only_survives_empty_trash(
    client: TestClient,
    db_session: Session,
) -> None:
    """Restored subtask must not CASCADE-delete when trashed parent is purged."""
    parent = _create_task(client, f"trash-parent-{_uid()}")
    child = _create_task(client, f"trash-child-{_uid()}", parent_task_id=parent["id"])

    assert client.delete(f"/api/v1/tasks/{parent['id']}").status_code == 204

    restored = client.post(f"/api/v1/tasks/{child['id']}/restore")
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["deleted_at"] is None
    assert body["parent_task_id"] is None

    assert client.delete("/api/v1/tasks/trash").status_code == 204

    live = client.get(f"/api/v1/tasks/{child['id']}")
    assert live.status_code == 200
    assert live.json()["deleted_at"] is None
    assert db_session.get(Task, uuid.UUID(child["id"])) is not None

    assert client.get(f"/api/v1/tasks/{parent['id']}").status_code == 404


def test_empty_trash_flushes_detach_before_purge_when_live_child_under_trashed_parent(
    client: TestClient,
    db_session: Session,
) -> None:
    """Defensive detach must flush under autoflush=False before parent DELETE."""
    from app.services.task_helpers import empty_trash_for_user, soft_delete_task_subtree

    parent = _create_task(client, f"trash-parent-{_uid()}")
    child = _create_task(client, f"trash-child-{_uid()}", parent_task_id=parent["id"])
    parent_row = db_session.get(Task, uuid.UUID(parent["id"]))
    child_row = db_session.get(Task, uuid.UUID(child["id"]))
    assert parent_row is not None and child_row is not None

    soft_delete_task_subtree(db_session, parent_row)
    db_session.flush()
    # bulk update uses synchronize_session=False — expire so the next write is real
    db_session.expire_all()
    parent_row = db_session.get(Task, uuid.UUID(parent["id"]))
    child_row = db_session.get(Task, uuid.UUID(child["id"]))
    assert parent_row is not None and child_row is not None
    assert parent_row.deleted_at is not None
    assert child_row.deleted_at is not None

    # Simulate a live child still attached to a trashed parent (bypass restore helper).
    child_row.deleted_at = None
    assert child_row.parent_task_id == parent_row.id
    db_session.flush()

    removed = empty_trash_for_user(db_session, parent_row.owner_id)
    assert removed >= 1
    db_session.flush()
    db_session.expire_all()

    live = db_session.get(Task, uuid.UUID(child["id"]))
    assert live is not None
    assert live.deleted_at is None
    assert live.parent_task_id is None
    assert db_session.get(Task, uuid.UUID(parent["id"])) is None
