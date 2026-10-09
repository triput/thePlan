"""F2 Kanban workflow API — columns, rank, revision, completion interactions."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, title: str, **extra: object) -> dict:
    body = {"title": title, **extra}
    response = client.post("/api/v1/tasks", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _workflow(
    client: TestClient,
    task_id: str,
    *,
    column: str,
    expected_revision: int,
    **extra: object,
) -> dict:
    payload = {"column": column, "expected_revision": expected_revision, **extra}
    response = client.post(f"/api/v1/tasks/{task_id}/workflow", json=payload)
    return response


def test_new_task_defaults_ready_on_board(client: TestClient) -> None:
    task = _create_task(client, f"ready-{_uid()}")
    assert task["workflow_state"] == "ready"
    assert task["board_column"] == "ready"
    assert task["board_revision"] == 0
    assert task["waiting_note"] is None


def test_move_open_columns_and_waiting_note(client: TestClient) -> None:
    task = _create_task(client, f"move-{_uid()}")
    rev = task["board_revision"]
    r1 = _workflow(client, task["id"], column="in_progress", expected_revision=rev)
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["workflow_state"] == "in_progress"
    assert body["board_column"] == "in_progress"
    assert body["board_revision"] == rev + 1

    rev = body["board_revision"]
    r2 = _workflow(
        client,
        task["id"],
        column="waiting",
        expected_revision=rev,
        waiting_note="Blocked on review",
    )
    assert r2.status_code == 200, r2.text
    waiting = r2.json()
    assert waiting["workflow_state"] == "waiting"
    assert waiting["waiting_note"] == "Blocked on review"

    sort_before = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"sort_order": 999},
    )
    assert sort_before.status_code == 200
    rev = waiting["board_revision"]
    r3 = _workflow(client, task["id"], column="ready", expected_revision=rev, board_rank=42)
    assert r3.status_code == 200
    moved = r3.json()
    assert moved["workflow_state"] == "ready"
    assert moved["waiting_note"] is None
    assert moved["board_rank"] == 42
    assert moved["sort_order"] == 999


def test_waiting_does_not_change_schedule_style(client: TestClient) -> None:
    task = _create_task(client, f"sched-{_uid()}", schedule_style="standalone")
    style = task["schedule_style"]
    rev = task["board_revision"]
    response = _workflow(client, task["id"], column="waiting", expected_revision=rev)
    assert response.status_code == 200
    assert response.json()["schedule_style"] == style


def test_workflow_to_done_and_back(client: TestClient) -> None:
    task = _create_task(client, f"done-{_uid()}")
    rev = task["board_revision"]
    done = _workflow(client, task["id"], column="done", expected_revision=rev)
    assert done.status_code == 200, done.text
    completed = done.json()
    assert completed["is_completed"] is True
    assert completed["board_column"] == "done"

    rev = completed["board_revision"]
    reopen = _workflow(client, task["id"], column="in_progress", expected_revision=rev)
    assert reopen.status_code == 200, reopen.text
    open_again = reopen.json()
    assert open_again["is_completed"] is False
    assert open_again["workflow_state"] == "in_progress"
    assert open_again["board_column"] == "in_progress"


def test_done_open_children_409_without_bulk(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])
    rev = parent["board_revision"]
    response = _workflow(client, parent["id"], column="done", expected_revision=rev)
    assert response.status_code == 409
    assert response.json()["code"] == "OPEN_CHILDREN"
    unchanged = client.get(f"/api/v1/tasks/{parent['id']}")
    assert unchanged.json()["is_completed"] is False


def test_done_bulk_children_via_workflow(client: TestClient) -> None:
    parent = _create_task(client, f"parent-{_uid()}")
    child = _create_task(client, f"child-{_uid()}", parent_task_id=parent["id"])
    rev = parent["board_revision"]
    response = _workflow(
        client,
        parent["id"],
        column="done",
        expected_revision=rev,
        bulk_children=True,
    )
    assert response.status_code == 200, response.text
    parent_out = response.json()
    assert parent_out["is_completed"] is True
    child_out = client.get(f"/api/v1/tasks/{child['id']}").json()
    assert child_out["is_completed"] is True


def test_board_revision_conflict(client: TestClient) -> None:
    task = _create_task(client, f"rev-{_uid()}")
    stale = _workflow(client, task["id"], column="in_progress", expected_revision=0)
    assert stale.status_code == 200
    conflict = _workflow(client, task["id"], column="waiting", expected_revision=0)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "BOARD_REVISION_CONFLICT"


def test_list_workflow_filter_and_board_order(client: TestClient) -> None:
    a = _create_task(client, f"a-{_uid()}")
    b = _create_task(client, f"b-{_uid()}")
    _workflow(client, a["id"], column="in_progress", expected_revision=a["board_revision"])
    _workflow(
        client,
        b["id"],
        column="in_progress",
        expected_revision=b["board_revision"],
        board_rank=10,
    )
    listed = client.get("/api/v1/tasks", params={"workflow": "in_progress", "limit": 50})
    assert listed.status_code == 200
    body = listed.json()
    ids = [item["id"] for item in body["items"] if item["workflow_state"] == "in_progress"]
    assert a["id"] in ids and b["id"] in ids
    assert body["total"] >= 2


def test_recurrence_complete_advances_to_ready_not_done(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"recur-{_uid()}",
            "due_at": "2026-08-10T09:00:00Z",
            "recurrence": {"rrule": "FREQ=DAILY;INTERVAL=1", "is_fixed": True},
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    rev = task["board_revision"]
    _workflow(client, task["id"], column="in_progress", expected_revision=rev)
    refreshed = client.get(f"/api/v1/tasks/{task['id']}").json()
    rev = refreshed["board_revision"]
    done = _workflow(client, task["id"], column="done", expected_revision=rev)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["is_completed"] is False
    assert body["board_column"] == "ready"
    assert body["workflow_state"] == "ready"
    assert body["recurrence_advanced"] is True
