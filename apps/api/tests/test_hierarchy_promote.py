"""DEF-023: promote / demote hierarchy (project↔epic, task→project)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_promote_project_to_epic_keeps_project_and_tasks(client: TestClient) -> None:
    tag = _uid()
    project = client.post(
        "/api/v1/projects",
        json={"title": f"Promo-{tag}", "description": "notes", "color_hex": "#112233"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"Stay-{tag}", "project_id": project["id"]},
    ).json()

    promoted = client.post(f"/api/v1/projects/{project['id']}/promote-to-epic")
    assert promoted.status_code == 200, promoted.text
    body = promoted.json()

    assert body["epic"]["title"] == f"Promo-{tag}"
    assert body["epic"]["description"] == "notes"
    assert body["epic"]["color_hex"] == "#112233"
    assert body["project"]["id"] == project["id"]
    assert body["project"]["epic_id"] == body["epic"]["id"]

    refreshed = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert refreshed["project_id"] == project["id"]

    epic_get = client.get(f"/api/v1/epics/{body['epic']['id']}")
    assert epic_get.status_code == 200


def test_demote_epic_to_project_orphans_children(client: TestClient) -> None:
    tag = _uid()
    epic = client.post("/api/v1/epics", json={"title": f"Epic-{tag}", "color_hex": "#445566"}).json()
    child_a = client.post(
        "/api/v1/projects",
        json={"title": f"ChildA-{tag}", "epic_id": epic["id"]},
    ).json()
    child_b = client.post(
        "/api/v1/projects",
        json={"title": f"ChildB-{tag}", "epic_id": epic["id"]},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"OnChild-{tag}", "project_id": child_a["id"]},
    ).json()

    demoted = client.post(f"/api/v1/epics/{epic['id']}/demote-to-project", json={})
    assert demoted.status_code == 200, demoted.text
    body = demoted.json()

    assert body["project"]["title"] == f"Epic-{tag}"
    assert body["project"]["color_hex"] == "#445566"
    assert body["project"]["epic_id"] is None
    assert set(body["orphaned_project_ids"]) == {child_a["id"], child_b["id"]}

    assert client.get(f"/api/v1/epics/{epic['id']}").status_code == 404

    a = client.get(f"/api/v1/projects/{child_a['id']}").json()
    b = client.get(f"/api/v1/projects/{child_b['id']}").json()
    assert a["epic_id"] is None
    assert b["epic_id"] is None
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["project_id"] == child_a["id"]


def test_demote_epic_rejects_self_target(client: TestClient) -> None:
    tag = _uid()
    epic = client.post("/api/v1/epics", json={"title": f"Self-{tag}"}).json()
    resp = client.post(
        f"/api/v1/epics/{epic['id']}/demote-to-project",
        json={"target_epic_id": epic["id"]},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "DEMOTE_TARGET_IS_SELF"


def test_promote_task_to_project_moves_subtree(client: TestClient) -> None:
    tag = _uid()
    epic = client.post("/api/v1/epics", json={"title": f"Home-{tag}"}).json()
    project = client.post(
        "/api/v1/projects",
        json={"title": f"Src-{tag}", "epic_id": epic["id"]},
    ).json()
    parent = client.post(
        "/api/v1/tasks",
        json={"title": f"Root-{tag}", "project_id": project["id"]},
    ).json()
    child = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Kid-{tag}",
            "project_id": project["id"],
            "parent_task_id": parent["id"],
        },
    ).json()

    promoted = client.post(
        f"/api/v1/tasks/{parent['id']}/promote-to-project",
        json={"include_descendants": True},
    )
    assert promoted.status_code == 200, promoted.text
    body = promoted.json()

    assert body["project"]["title"] == f"Root-{tag}"
    assert body["project"]["epic_id"] == epic["id"]
    assert body["task"]["id"] == parent["id"]
    assert body["task"]["project_id"] == body["project"]["id"]
    assert body["task"]["parent_task_id"] is None
    assert body["task"]["nesting_level"] == 0

    kid = client.get(f"/api/v1/tasks/{child['id']}").json()
    assert kid["project_id"] == body["project"]["id"]
    assert kid["parent_task_id"] == parent["id"]
    assert kid["nesting_level"] == 1


def test_promote_task_without_descendants_flag_rejects_children(client: TestClient) -> None:
    tag = _uid()
    parent = client.post("/api/v1/tasks", json={"title": f"P-{tag}"}).json()
    client.post(
        "/api/v1/tasks",
        json={"title": f"C-{tag}", "parent_task_id": parent["id"]},
    )

    resp = client.post(
        f"/api/v1/tasks/{parent['id']}/promote-to-project",
        json={"include_descendants": False},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PROMOTE_HAS_DESCENDANTS"
