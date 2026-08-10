"""API tests for task search by title and description."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Task, User
from app.models.enums import TaskPriority


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}", "color_hex": "#0A8558"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_search_matches_title_and_description(client: TestClient) -> None:
    uid = _uid()
    term = f"arch-{uid}"
    project = _create_project(client)
    project_title = project["title"]

    title_task = client.post(
        "/api/v1/tasks",
        json={"title": f"Review {term} spec", "project_id": project["id"]},
    )
    assert title_task.status_code == 201, title_task.text

    desc_task = client.post(
        "/api/v1/tasks",
        json={"title": f"Notes {_uid()}", "description": f"Contains {term} in body"},
    )
    assert desc_task.status_code == 201, desc_task.text

    response = client.get("/api/v1/search", params={"q": term})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["limit"] == 20
    assert body["offset"] == 0

    ids = {item["id"] for item in body["items"]}
    assert ids == {title_task.json()["id"], desc_task.json()["id"]}

    title_match = next(item for item in body["items"] if item["id"] == title_task.json()["id"])
    assert title_match["project_title"] == project_title
    assert title_match["labels"] == []

    desc_match = next(item for item in body["items"] if item["id"] == desc_task.json()["id"])
    assert desc_match["project_title"] is None


def test_search_includes_embedded_labels(client: TestClient) -> None:
    uid = _uid()
    term = f"label-{uid}"
    label = client.post(
        "/api/v1/labels",
        json={"name": f"dev-{uid}", "color_hex": "#112233"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"{term} task", "label_ids": [label["id"]]},
    ).json()

    response = client.get("/api/v1/search", params={"q": term})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == task["id"]
    assert item["label_ids"] == [label["id"]]
    assert item["labels"] == [
        {"id": label["id"], "name": label["name"], "color_hex": "#112233"}
    ]


def test_search_empty_or_missing_q_returns_422(client: TestClient) -> None:
    missing = client.get("/api/v1/search")
    assert missing.status_code == 422

    empty = client.get("/api/v1/search", params={"q": "   "})
    assert empty.status_code == 422
    assert empty.json()["detail"] == "Search query cannot be empty"


def test_search_no_match_returns_empty_items(client: TestClient) -> None:
    response = client.get("/api/v1/search", params={"q": f"nomatch-{_uid()}"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_search_escapes_wildcards(client: TestClient) -> None:
    uid = _uid()
    literal = f"100%-done-{uid}"
    client.post("/api/v1/tasks", json={"title": literal})
    client.post("/api/v1/tasks", json={"title": f"100X-done-{uid}"})

    response = client.get("/api/v1/search", params={"q": f"100%-done-{uid}"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == literal


def test_search_scoped_to_current_owner(client: TestClient, db_session: Session) -> None:
    uid = _uid()
    term = f"owner-{uid}"

    mine = client.post("/api/v1/tasks", json={"title": f"My {term} task"}).json()

    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uid}@example.test",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()
    db_session.add(
        Task(
            owner_id=other_user.id,
            title=f"Their {term} task",
            priority=TaskPriority.p4,
        )
    )
    db_session.flush()

    response = client.get("/api/v1/search", params={"q": term})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == mine["id"]
