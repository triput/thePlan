"""API tests for named Plans and task plan_id bind semantics."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

PLAN_TARGET = "2026-09-15T17:00:00+00:00"
OVERRIDE_TARGET = "2026-09-20T12:00:00+00:00"
PRIOR_TARGET = "2026-09-01T09:00:00+00:00"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _parse_ts(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assert_ts(actual: str | None, expected: str | None) -> None:
    assert _parse_ts(actual) == _parse_ts(expected)


def _create_plan(client: TestClient, *, name: str | None = None, soft_target_at: str | None = PLAN_TARGET) -> dict:
    uid = _uid()
    payload: dict = {"name": name or f"Plan {uid}"}
    if soft_target_at is not None:
        payload["soft_target_at"] = soft_target_at
    response = client.post("/api/v1/plans", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_plans_list_ordered_by_name(client: TestClient) -> None:
    uid = _uid()
    client.post("/api/v1/plans", json={"name": f"Zulu {uid}"})
    client.post("/api/v1/plans", json={"name": f"Alpha {uid}"})

    response = client.get("/api/v1/plans")
    assert response.status_code == 200, response.text
    names = [row["name"] for row in response.json()]
    assert names == sorted(names)


def test_plan_crud(client: TestClient) -> None:
    uid = _uid()
    create = client.post(
        "/api/v1/plans",
        json={"name": f"Sprint {uid}", "soft_target_at": PLAN_TARGET},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["name"] == f"Sprint {uid}"
    _assert_ts(body["soft_target_at"], PLAN_TARGET)
    plan_id = body["id"]

    get_one = client.get(f"/api/v1/plans/{plan_id}")
    assert get_one.status_code == 200
    assert get_one.json()["name"] == f"Sprint {uid}"

    patch = client.patch(
        f"/api/v1/plans/{plan_id}",
        json={"name": f"Release {uid}", "soft_target_at": OVERRIDE_TARGET},
    )
    assert patch.status_code == 200
    patched = patch.json()
    assert patched["name"] == f"Release {uid}"
    _assert_ts(patched["soft_target_at"], OVERRIDE_TARGET)

    delete = client.delete(f"/api/v1/plans/{plan_id}")
    assert delete.status_code == 204
    assert client.get(f"/api/v1/plans/{plan_id}").status_code == 404


def test_plan_empty_name_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/plans", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["code"] == "PLAN_NAME_EMPTY"


def test_plan_other_user_not_visible(client: TestClient) -> None:
    created = _create_plan(client)
    assert client.get(f"/api/v1/plans/{created['id']}").status_code == 200
    assert client.get(f"/api/v1/plans/{uuid.uuid4()}").status_code == 404


def test_delete_plan_nulls_task_plan_id(client: TestClient) -> None:
    plan = _create_plan(client)
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"Bound {_uid()}", "plan_id": plan["id"]},
    )
    assert task.status_code == 201, task.text
    assert task.json()["plan_id"] == plan["id"]

    assert client.delete(f"/api/v1/plans/{plan['id']}").status_code == 204

    refreshed = client.get(f"/api/v1/tasks/{task.json()['id']}").json()
    assert refreshed["plan_id"] is None
    assert refreshed["plan_name"] is None


def test_task_bind_copies_plan_soft_target(client: TestClient) -> None:
    plan = _create_plan(client)
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"Plan bind {_uid()}", "plan_id": plan["id"]},
    )
    assert task.status_code == 201, task.text
    body = task.json()
    assert body["plan_id"] == plan["id"]
    assert body["plan_name"] == plan["name"]
    _assert_ts(body["soft_target_at"], PLAN_TARGET)


def test_task_bind_plan_without_soft_target_leaves_task_soft_target(client: TestClient) -> None:
    plan = _create_plan(client, soft_target_at=None)
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"No frame {_uid()}", "plan_id": plan["id"]},
    )
    assert task.status_code == 201, task.text
    assert task.json()["soft_target_at"] is None


def test_task_unbind_leaves_soft_target(client: TestClient) -> None:
    plan = _create_plan(client)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"Unbind {_uid()}", "plan_id": plan["id"]},
    ).json()
    _assert_ts(created["soft_target_at"], PLAN_TARGET)

    patched = client.patch(
        f"/api/v1/tasks/{created['id']}",
        json={"plan_id": None},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["plan_id"] is None
    assert body["plan_name"] is None
    _assert_ts(body["soft_target_at"], PLAN_TARGET)


def test_task_explicit_soft_target_in_same_patch_wins(client: TestClient) -> None:
    plan = _create_plan(client)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"Override {_uid()}", "plan_id": plan["id"]},
    ).json()
    _assert_ts(created["soft_target_at"], PLAN_TARGET)

    patched = client.patch(
        f"/api/v1/tasks/{created['id']}",
        json={"plan_id": plan["id"], "soft_target_at": OVERRIDE_TARGET},
    )
    assert patched.status_code == 200, patched.text
    _assert_ts(patched.json()["soft_target_at"], OVERRIDE_TARGET)


def test_task_create_explicit_soft_target_wins_over_plan_bind(client: TestClient) -> None:
    plan = _create_plan(client)
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Create override {_uid()}",
            "plan_id": plan["id"],
            "soft_target_at": OVERRIDE_TARGET,
        },
    )
    assert task.status_code == 201, task.text
    _assert_ts(task.json()["soft_target_at"], OVERRIDE_TARGET)


def test_task_soft_target_patch_does_not_clear_plan_id(client: TestClient) -> None:
    plan = _create_plan(client)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"Keep plan {_uid()}", "plan_id": plan["id"]},
    ).json()

    patched = client.patch(
        f"/api/v1/tasks/{created['id']}",
        json={"soft_target_at": PRIOR_TARGET},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["plan_id"] == plan["id"]
    assert body["plan_name"] == plan["name"]
    _assert_ts(body["soft_target_at"], PRIOR_TARGET)


def test_task_plan_id_other_user_rejected(client: TestClient) -> None:
    bogus = client.post(
        "/api/v1/tasks",
        json={"title": "Bad plan", "plan_id": str(uuid.uuid4())},
    )
    assert bogus.status_code == 404

    plan = _create_plan(client)
    task_id = client.post(
        "/api/v1/tasks",
        json={"title": f"Owned plan {_uid()}", "plan_id": plan["id"]},
    ).json()["id"]

    patch = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"plan_id": str(uuid.uuid4())},
    )
    assert patch.status_code == 404


def test_task_list_includes_plan_name(client: TestClient) -> None:
    plan = _create_plan(client, name=f"Listed {_uid()}")
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"List me {_uid()}", "plan_id": plan["id"]},
    ).json()

    listed = client.get("/api/v1/tasks", params={"limit": 200}).json()
    match = next(item for item in listed["items"] if item["id"] == task["id"])
    assert match["plan_id"] == plan["id"]
    assert match["plan_name"] == plan["name"]


def test_plan_without_soft_target_field(client: TestClient) -> None:
    uid = _uid()
    response = client.post("/api/v1/plans", json={"name": f"Open-ended {uid}"})
    assert response.status_code == 201, response.text
    assert response.json()["soft_target_at"] is None

    rebound = client.patch(
        f"/api/v1/tasks/{client.post('/api/v1/tasks', json={'title': f'Rebind {uid}'}).json()['id']}",
        json={"plan_id": response.json()["id"]},
    )
    assert rebound.status_code == 200
    assert rebound.json()["soft_target_at"] is None
