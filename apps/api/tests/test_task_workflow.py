"""F2 Kanban workflow API — columns, rank, revision, completion interactions."""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


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


def test_complete_bumps_revision_stale_workflow_conflicts(client: TestClient) -> None:
    task = _create_task(client, f"complete-rev-{_uid()}")
    assert task["board_revision"] == 0
    complete = client.post(f"/api/v1/tasks/{task['id']}/complete", json={})
    assert complete.status_code == 200, complete.text
    assert complete.json()["board_revision"] == 1
    stale = _workflow(client, task["id"], column="in_progress", expected_revision=0)
    assert stale.status_code == 409
    assert stale.json()["code"] == "BOARD_REVISION_CONFLICT"


def test_workflow_insert_before_and_after_rank(client: TestClient) -> None:
    anchor = _create_task(client, f"anchor-{_uid()}")
    neighbor = _create_task(client, f"neighbor-{_uid()}")
    # Pin a clear ascending gap regardless of create-time next_board_rank.
    assert (
        _workflow(
            client,
            anchor["id"],
            column="in_progress",
            expected_revision=anchor["board_revision"],
            board_rank=10_000_000,
        ).status_code
        == 200
    )
    neighbor = client.get(f"/api/v1/tasks/{neighbor['id']}").json()
    assert (
        _workflow(
            client,
            neighbor["id"],
            column="in_progress",
            expected_revision=neighbor["board_revision"],
            board_rank=20_000_000,
        ).status_code
        == 200
    )
    mover = _create_task(client, f"mover-{_uid()}")
    before = _workflow(
        client,
        mover["id"],
        column="in_progress",
        expected_revision=mover["board_revision"],
        insert_before_id=neighbor["id"],
    )
    assert before.status_code == 200, before.text
    neighbor_after = client.get(f"/api/v1/tasks/{neighbor['id']}").json()
    anchor_after = client.get(f"/api/v1/tasks/{anchor['id']}").json()
    assert before.json()["board_rank"] < neighbor_after["board_rank"]
    assert before.json()["board_rank"] > anchor_after["board_rank"]

    mover2 = _create_task(client, f"mover2-{_uid()}")
    after = _workflow(
        client,
        mover2["id"],
        column="in_progress",
        expected_revision=mover2["board_revision"],
        insert_after_id=anchor["id"],
    )
    assert after.status_code == 200, after.text
    assert after.json()["board_rank"] > anchor_after["board_rank"]
    assert after.json()["board_rank"] < neighbor_after["board_rank"]


def test_rank_between_unit() -> None:
    from app.services.task_workflow import _rank_between

    assert _rank_between(None, 2_000_000) == 1_000_000
    assert _rank_between(1_000_000, None) == 2_000_000
    assert _rank_between(10, 20) == 15
    assert _rank_between(10, 11) is None  # exhausted — caller re-gaps


def test_exhausted_gap_insert_before_preserves_order(
    client: TestClient,
    db_session: Session,
) -> None:
    """A=10,B=11,C=12; insert D before B must not jump B past C or tie D with A."""
    from app.models import Task as TaskModel
    from app.models.enums import TaskWorkflowState
    from app.services.task_workflow import _resolve_board_rank

    me = client.get("/api/v1/auth/me").json()
    owner_id = UUID(me["id"])
    a = _create_task(client, f"gap-a-{_uid()}")
    b = _create_task(client, f"gap-b-{_uid()}")
    c = _create_task(client, f"gap-c-{_uid()}")
    for task_id, rank in ((a["id"], 10), (b["id"], 11), (c["id"], 12)):
        row = db_session.get(TaskModel, UUID(task_id))
        assert row is not None
        row.board_rank = rank
        row.workflow_state = TaskWorkflowState.in_progress
    db_session.flush()

    d_rank = _resolve_board_rank(
        db_session,
        owner_id,
        explicit_rank=None,
        insert_before_id=UUID(b["id"]),
        insert_after_id=None,
    )
    db_session.flush()
    a_row = db_session.get(TaskModel, UUID(a["id"]))
    b_row = db_session.get(TaskModel, UUID(b["id"]))
    c_row = db_session.get(TaskModel, UUID(c["id"]))
    assert a_row and b_row and c_row and d_rank is not None
    assert a_row.board_rank < d_rank < b_row.board_rank < c_row.board_rank
    assert b_row.board_revision >= 1


def test_recurrence_ready_advance_bumps_revision(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"recur-ready-{_uid()}",
            "due_at": "2026-10-08T09:00:00Z",
            "recurrence": {"rrule": "FREQ=DAILY;INTERVAL=1", "is_fixed": True},
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["board_column"] == "ready"
    assert task["board_revision"] == 0
    complete = client.post(f"/api/v1/tasks/{task['id']}/complete", json={})
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["board_column"] == "ready"
    assert body["board_revision"] == 1
    stale = _workflow(client, task["id"], column="done", expected_revision=0)
    assert stale.status_code == 409
    assert stale.json()["code"] == "BOARD_REVISION_CONFLICT"


def test_list_excludes_archived_project_and_epic_tasks(client: TestClient) -> None:
    epic_resp = client.post("/api/v1/epics", json={"title": f"epic-{_uid()}"})
    assert epic_resp.status_code == 201, epic_resp.text
    epic = epic_resp.json()
    project = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}", "epic_id": epic["id"]},
    ).json()
    archived_project = client.post(
        "/api/v1/projects",
        json={"title": f"arch-proj-{_uid()}"},
    ).json()
    client.post(f"/api/v1/projects/{archived_project['id']}/archive")

    in_live = _create_task(client, f"live-{_uid()}", project_id=project["id"])
    in_archived_project = _create_task(
        client,
        f"arch-proj-task-{_uid()}",
        project_id=archived_project["id"],
    )
    inbox = _create_task(client, f"inbox-{_uid()}")

    client.post(f"/api/v1/epics/{epic['id']}/archive")
    in_archived_epic = _create_task(client, f"epic-arch-{_uid()}", project_id=project["id"])

    listed = client.get("/api/v1/tasks", params={"limit": 200})
    assert listed.status_code == 200, listed.text
    ids = {item["id"] for item in listed.json()["items"]}
    assert inbox["id"] in ids
    assert in_live["id"] not in ids
    assert in_archived_project["id"] not in ids
    assert in_archived_epic["id"] not in ids

    by_project = client.get(
        "/api/v1/tasks",
        params={"project_id": archived_project["id"], "limit": 50},
    )
    assert by_project.status_code == 200
    scoped_ids = {item["id"] for item in by_project.json()["items"]}
    assert in_archived_project["id"] in scoped_ids

    # epic_id / ids must still hide archived-project tasks (Work board / smart ids).
    live_epic = client.post("/api/v1/epics", json={"title": f"live-epic-{_uid()}"}).json()
    live_proj = client.post(
        "/api/v1/projects",
        json={"title": f"live-under-{_uid()}", "epic_id": live_epic["id"]},
    ).json()
    arch_under = client.post(
        "/api/v1/projects",
        json={"title": f"arch-under-{_uid()}", "epic_id": live_epic["id"]},
    ).json()
    client.post(f"/api/v1/projects/{arch_under['id']}/archive")
    live_task = _create_task(client, f"epic-live-{_uid()}", project_id=live_proj["id"])
    arch_task = _create_task(client, f"epic-arch-proj-{_uid()}", project_id=arch_under["id"])
    by_epic = client.get("/api/v1/tasks", params={"epic_id": live_epic["id"], "limit": 100})
    assert by_epic.status_code == 200
    epic_ids = {item["id"] for item in by_epic.json()["items"]}
    assert live_task["id"] in epic_ids
    assert arch_task["id"] not in epic_ids

    by_ids = client.get(
        "/api/v1/tasks",
        params=[("ids", live_task["id"]), ("ids", arch_task["id"])],
    )
    assert by_ids.status_code == 200
    id_set = {item["id"] for item in by_ids.json()["items"]}
    assert live_task["id"] in id_set
    assert arch_task["id"] not in id_set


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
