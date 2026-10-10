"""F7 presentation_json sort: query apply, validation, PATCH merge."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Project, Task
from app.models.enums import TaskPriority


def _project(db: Session, owner_id: uuid.UUID) -> Project:
    project = Project(owner_id=owner_id, title=f"f7-sort-{uuid.uuid4().hex[:8]}")
    db.add(project)
    db.flush()
    return project


def _create_view(client: TestClient, project_id: uuid.UUID, **presentation: object) -> dict:
    body = {
        "name": f"sort-{uuid.uuid4().hex[:8]}",
        "predicate_json": {
            "v": 1,
            "dimensions": {
                "project_ids": [str(project_id)],
                "completion": "open",
            },
        },
        "presentation_json": presentation,
    }
    response = client.post("/api/v1/views", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _titles(client: TestClient, view_id: str, **params: object) -> list[str]:
    response = client.get(f"/api/v1/views/{view_id}/tasks", params=params)
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["items"]]


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def test_presentation_sort_title_applied(client: TestClient, db_session: Session) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    view = _create_view(client, project.id, mode="list", sort="title")
    db_session.add_all(
        [
            Task(
                owner_id=owner,
                project_id=project.id,
                title="Zebra",
                is_completed=False,
                sort_order=1,
            ),
            Task(
                owner_id=owner,
                project_id=project.id,
                title="Alpha",
                is_completed=False,
                sort_order=2,
            ),
            Task(
                owner_id=owner,
                project_id=project.id,
                title="Mango",
                is_completed=False,
                sort_order=0,
            ),
        ]
    )
    db_session.flush()

    assert _titles(client, view["id"]) == ["Alpha", "Mango", "Zebra"]


def test_query_sort_overrides_presentation(client: TestClient, db_session: Session) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    view = _create_view(client, project.id, mode="list", sort="title")
    db_session.add_all(
        [
            Task(owner_id=owner, project_id=project.id, title="Zebra", is_completed=False),
            Task(owner_id=owner, project_id=project.id, title="Alpha", is_completed=False),
        ]
    )
    db_session.flush()

    assert _titles(client, view["id"], sort="-title") == ["Zebra", "Alpha"]


def test_invalid_sort_on_query_422(client: TestClient, db_session: Session) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    view = _create_view(client, project.id, mode="list")
    response = client.get(f"/api/v1/views/{view['id']}/tasks", params={"sort": "board_rank"})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_SORT"


def test_invalid_sort_on_create_422(client: TestClient, db_session: Session) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    response = client.post(
        "/api/v1/views",
        json={
            "name": "Bad sort",
            "predicate_json": {
                "v": 1,
                "dimensions": {"project_ids": [str(project.id)], "completion": "open"},
            },
            "presentation_json": {"mode": "list", "sort": "nope"},
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_SORT"


def test_mode_only_patch_preserves_sort(client: TestClient, db_session: Session) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    view = _create_view(client, project.id, mode="board", sort="-priority")
    patched = client.patch(
        f"/api/v1/views/{view['id']}",
        json={"presentation_json": {"mode": "list"}},
    )
    assert patched.status_code == 200, patched.text
    pres = patched.json()["presentation_json"]
    assert pres["mode"] == "list"
    assert pres["sort"] == "-priority"


def test_board_order_wins_over_presentation_sort(
    client: TestClient, db_session: Session
) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    view = _create_view(client, project.id, mode="board", sort="title")
    low = Task(
        owner_id=owner,
        project_id=project.id,
        title="Low rank",
        is_completed=False,
        board_rank=20,
        sort_order=1,
    )
    high = Task(
        owner_id=owner,
        project_id=project.id,
        title="High rank",
        is_completed=False,
        board_rank=10,
        sort_order=99,
    )
    db_session.add_all([low, high])
    db_session.flush()

    assert _titles(client, view["id"]) == ["High rank", "Low rank"]
    assert _titles(client, view["id"], board_order=True) == ["High rank", "Low rank"]

    low.title = "AAA"
    high.title = "ZZZ"
    db_session.flush()

    assert _titles(client, view["id"]) == ["AAA", "ZZZ"]
    assert _titles(client, view["id"], board_order=True) == ["ZZZ", "AAA"]


def test_priority_sort_p1_first(client: TestClient, db_session: Session) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    view = _create_view(client, project.id, mode="list", sort="priority")
    db_session.add_all(
        [
            Task(
                owner_id=owner,
                project_id=project.id,
                title="p4",
                priority=TaskPriority.p4,
                is_completed=False,
            ),
            Task(
                owner_id=owner,
                project_id=project.id,
                title="p1",
                priority=TaskPriority.p1,
                is_completed=False,
            ),
            Task(
                owner_id=owner,
                project_id=project.id,
                title="p2",
                priority=TaskPriority.p2,
                is_completed=False,
            ),
        ]
    )
    db_session.flush()
    assert _titles(client, view["id"]) == ["p1", "p2", "p4"]
