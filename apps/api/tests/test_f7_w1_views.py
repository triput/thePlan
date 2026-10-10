"""F7-W1: saved views CRUD + task query paths."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bootstrap import ensure_bootstrap_user
from app.models import Task
from app.services.saved_filter_v1 import INBOX_PREDICATE_V1

INBOX_V1 = INBOX_PREDICATE_V1


def _user_view_predicate() -> dict:
    return {
        "v": 1,
        "dimensions": {
            "priorities": ["p1"],
            "completion": "open",
        },
    }


def test_list_views_includes_system(client: TestClient, db_session: Session) -> None:
    user = ensure_bootstrap_user(db_session, commit=False)
    response = client.get("/api/v1/views")
    assert response.status_code == 200
    body = response.json()
    slugs = {row["slug"] for row in body}
    assert {"inbox", "today", "upcoming"} <= slugs
    inbox = next(row for row in body if row["slug"] == "inbox")
    assert inbox["is_system"] is True
    assert inbox["predicate_json"]["v"] == 1
    assert inbox["predicate_json"]["dimensions"].get("inbox") is True


def test_create_get_patch_delete_user_view(client: TestClient) -> None:
    created = client.post(
        "/api/v1/views",
        json={
            "name": "Hot P1",
            "slug": "hot-p1",
            "predicate_json": _user_view_predicate(),
            "presentation_json": {"mode": "list"},
        },
    )
    assert created.status_code == 201, created.text
    view = created.json()
    view_id = view["id"]
    assert view["slug"] == "hot-p1"
    assert view["presentation_json"]["mode"] == "list"
    assert view["is_system"] is False

    fetched = client.get(f"/api/v1/views/{view_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Hot P1"

    patched = client.patch(
        f"/api/v1/views/{view_id}",
        json={"name": "Warm P1", "sort_order": 50},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Warm P1"
    assert patched.json()["sort_order"] == 50

    deleted = client.delete(f"/api/v1/views/{view_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/views/{view_id}").status_code == 404


def test_system_view_patch_and_delete_rejected(client: TestClient, db_session: Session) -> None:
    ensure_bootstrap_user(db_session, commit=False)
    listing = client.get("/api/v1/views")
    inbox = next(row for row in listing.json() if row["slug"] == "inbox")
    view_id = inbox["id"]

    patch_resp = client.patch(f"/api/v1/views/{view_id}", json={"name": "Nope"})
    assert patch_resp.status_code == 403
    assert patch_resp.json()["code"] == "SYSTEM_VIEW_READ_ONLY"

    delete_resp = client.delete(f"/api/v1/views/{view_id}")
    assert delete_resp.status_code == 403
    assert delete_resp.json()["code"] == "SYSTEM_VIEW_READ_ONLY"


def test_foreign_view_id_is_404(client: TestClient) -> None:
    missing = client.get(f"/api/v1/views/{uuid.uuid4()}")
    assert missing.status_code == 404


def test_inbox_tasks_by_slug_and_id(client: TestClient, db_session: Session) -> None:
    user = ensure_bootstrap_user(db_session, commit=False)
    task = Task(
        owner_id=user.id,
        title="Inbox item",
        project_id=None,
        is_completed=False,
    )
    db_session.add(task)
    db_session.flush()

    listing = client.get("/api/v1/views")
    inbox_id = next(row["id"] for row in listing.json() if row["slug"] == "inbox")

    by_id = client.get(f"/api/v1/views/{inbox_id}/tasks")
    assert by_id.status_code == 200
    body = by_id.json()
    assert body["total"] >= 1
    assert "limit" in body and "offset" in body
    ids = {item["id"] for item in body["items"]}
    assert str(task.id) in ids

    by_slug = client.get("/api/v1/views/by-slug/inbox/tasks")
    assert by_slug.status_code == 200
    assert by_slug.json()["total"] == body["total"]


def test_delete_view_does_not_delete_tasks(client: TestClient, db_session: Session) -> None:
    user = ensure_bootstrap_user(db_session, commit=False)
    created = client.post(
        "/api/v1/views",
        json={
            "name": "Disposable",
            "slug": "disposable-view",
            "predicate_json": INBOX_V1,
        },
    )
    view_id = created.json()["id"]
    task = Task(
        owner_id=user.id,
        title="Still here",
        project_id=None,
        is_completed=False,
    )
    db_session.add(task)
    db_session.flush()
    task_id = str(task.id)

    assert client.delete(f"/api/v1/views/{view_id}").status_code == 204
    tasks = client.get("/api/v1/tasks", params={"ids": [task_id]})
    assert tasks.status_code == 200
    assert tasks.json()["total"] == 1


def test_invalid_predicate_rejected_on_create(client: TestClient) -> None:
    response = client.post(
        "/api/v1/views",
        json={
            "name": "Bad",
            "predicate_json": {"op": "legacy"},
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PREDICATE"
