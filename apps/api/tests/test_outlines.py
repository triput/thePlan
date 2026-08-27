"""Outline propose/apply tests — Theme F / ADR-011."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Epic, Label, Project, Section, Task, TaskLabel, User

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "testdata/outlines/ibm_rag_agentic_ai_professional_certificate_curriculum.json"
)
_BLANK = Path(__file__).resolve().parents[3] / "testdata/outlines/blank_hierarchy_v1.json"


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _load_blank() -> dict:
    return json.loads(_BLANK.read_text(encoding="utf-8"))


def _current_user(client: TestClient, db_session: Session) -> User:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    user = db_session.get(User, uuid.UUID(me.json()["id"]))
    assert user is not None
    return user


def _count_by_type(actions: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for action in actions:
        counts[action["type"]] = counts.get(action["type"], 0) + 1
    return counts


def _tiny_outline() -> dict:
    return {
        "certificate": {
            "title": "Tiny Certificate",
            "provider": "TestCo",
            "platform": "Coursera",
            "source_url": "https://example.com/cert",
            "notes": "fixture",
        },
        "courses": [
            {
                "course_order": 1,
                "title": "Course One",
                "estimated_hours": 2,
                "url": "https://example.com/course",
                "modules": [
                    {
                        "module_order": 1,
                        "title": "Module A",
                        "estimated_hours": 1,
                        "tasks": [
                            {
                                "task_type": "video",
                                "title": "Video: Hello",
                                "duration_minutes": 5,
                                "optional": False,
                                "task_order": 1,
                                "id": "c01-m01-t01",
                            },
                            {
                                "task_type": "reading",
                                "title": "(Optional) Reading: Extra",
                                "duration_minutes": 3,
                                "optional": True,
                                "task_order": 2,
                                "id": "c01-m01-t02",
                            },
                        ],
                    }
                ],
            }
        ],
    }


def _course_fragment() -> dict:
    return {
        "course": {
            "course_order": 2,
            "title": "Grafted Course",
            "modules": [
                {
                    "module_order": 1,
                    "title": "Graft Module",
                    "tasks": [
                        {
                            "task_type": "video",
                            "title": "Video: Graft task",
                            "duration_minutes": 10,
                            "optional": False,
                            "task_order": 1,
                            "id": "g01-m01-t01",
                        }
                    ],
                }
            ],
        }
    }


def _modules_fragment() -> dict:
    return {
        "modules": [
            {
                "module_order": 1,
                "title": "Graft Section",
                "tasks": [
                    {
                        "task_type": "reading",
                        "title": "Reading: Under project",
                        "duration_minutes": 8,
                        "optional": False,
                        "task_order": 1,
                        "id": "p01-m01-t01",
                    }
                ],
            }
        ]
    }


def test_propose_full_fixture(client: TestClient) -> None:
    outline = _load_fixture()
    res = client.post(
        "/api/v1/outlines/propose",
        json={"template_id": "coursera_specialization", "outline": outline},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template_id"] == "coursera_specialization"
    counts = _count_by_type(body["actions"])
    assert counts.get("create_epic") == 1
    assert counts.get("create_project") == 10
    assert counts.get("create_section") == 30
    assert counts.get("create_task") == 417
    assert body["summary"]["epic_count"] == 1
    assert body["summary"]["project_count"] == 10
    assert body["summary"]["section_count"] == 30
    assert body["summary"]["task_count"] == 417
    assert body["summary"]["optional_skipped"] == 0

    epic = next(a for a in body["actions"] if a["type"] == "create_epic")
    assert epic["key"] == "epic"
    assert "IBM RAG" in epic["title"]
    assert "provider:" in (epic["description"] or "")

    task = next(a for a in body["actions"] if a["type"] == "create_task")
    assert task["key"]
    assert task["description"] and task["description"].startswith("outline_id:")
    assert "video" in [n.lower() for n in task["label_names"]] or task["label_names"]


def test_propose_skip_optional(client: TestClient) -> None:
    outline = _load_fixture()
    res = client.post(
        "/api/v1/outlines/propose",
        json={
            "template_id": "coursera_specialization",
            "outline": outline,
            "skip_optional": True,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    counts = _count_by_type(body["actions"])
    assert counts.get("create_task") == 403
    assert body["summary"]["task_count"] == 403
    assert body["summary"]["optional_skipped"] == 14
    assert all(not a.get("optional") for a in body["actions"] if a["type"] == "create_task")


def test_propose_invalid_template(client: TestClient) -> None:
    res = client.post(
        "/api/v1/outlines/propose",
        json={"template_id": "nope", "outline": {"certificate": {"title": "x"}, "courses": []}},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "OUTLINE_INVALID"


def test_propose_invalid_outline(client: TestClient) -> None:
    res = client.post(
        "/api/v1/outlines/propose",
        json={"outline": {"courses": []}},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "OUTLINE_INVALID"


def test_apply_small_outline(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    outline = _tiny_outline()

    propose = client.post("/api/v1/outlines/propose", json={"outline": outline})
    assert propose.status_code == 200, propose.text
    actions = propose.json()["actions"]
    assert _count_by_type(actions) == {
        "create_epic": 1,
        "create_project": 1,
        "create_section": 1,
        "create_task": 2,
    }

    apply = client.post("/api/v1/outlines/apply", json={"actions": actions})
    assert apply.status_code == 200, apply.text
    results = apply.json()["results"]
    assert len(results) == 5
    assert all(r["ok"] for r in results)

    epic = db_session.query(Epic).filter(Epic.owner_id == user.id, Epic.title == "Tiny Certificate").one()
    project = (
        db_session.query(Project)
        .filter(Project.owner_id == user.id, Project.title == "Course One")
        .one()
    )
    assert project.epic_id == epic.id
    section = (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id)
        .one()
    )
    assert section.title == "Module A"

    tasks = (
        db_session.query(Task)
        .filter(Task.owner_id == user.id, Task.project_id == project.id)
        .order_by(Task.sort_order)
        .all()
    )
    assert len(tasks) == 2
    assert tasks[0].title == "Hello"
    assert tasks[0].section_id == section.id
    assert tasks[0].description == "outline_id: c01-m01-t01"
    assert tasks[0].estimated_duration_minutes == 5
    assert tasks[1].title == "Extra"
    assert tasks[1].estimated_duration_minutes == 3

    labels = {label.name.lower() for label in db_session.query(Label).filter(Label.owner_id == user.id)}
    assert "video" in labels
    assert "reading" in labels
    assert "optional" in labels

    task_label_names = {
        db_session.get(Label, tl.label_id).name.lower()  # type: ignore[union-attr]
        for tl in db_session.query(TaskLabel).filter(TaskLabel.task_id == tasks[1].id)
    }
    assert "reading" in task_label_names
    assert "optional" in task_label_names


def test_propose_hierarchy_v1_alias(client: TestClient) -> None:
    outline = _load_blank()
    res = client.post(
        "/api/v1/outlines/propose",
        json={"template_id": "hierarchy_v1", "outline": outline},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template_id"] == "hierarchy_v1"
    counts = _count_by_type(body["actions"])
    assert counts.get("create_epic") == 1
    assert counts.get("create_project") == 2
    assert counts.get("create_section") == 3
    assert counts.get("create_task") == 5


def test_propose_graft_under_epic(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    epic = Epic(owner_id=user.id, title="Existing Epic", sort_order=0)
    db_session.add(epic)
    db_session.flush()

    res = client.post(
        "/api/v1/outlines/propose",
        json={
            "outline": _course_fragment(),
            "attach_under": {"kind": "epic", "id": str(epic.id)},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    counts = _count_by_type(body["actions"])
    assert counts.get("create_epic", 0) == 0
    assert counts.get("create_project") == 1
    assert counts.get("create_section") == 1
    assert counts.get("create_task") == 1

    project = next(a for a in body["actions"] if a["type"] == "create_project")
    assert project["epic_id"] == str(epic.id)
    assert project.get("epic_key") is None


def test_propose_graft_under_project(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    epic = Epic(owner_id=user.id, title="Parent Epic", sort_order=0)
    db_session.add(epic)
    db_session.flush()
    project = Project(owner_id=user.id, epic_id=epic.id, title="Existing Project", sort_order=0)
    db_session.add(project)
    db_session.flush()

    res = client.post(
        "/api/v1/outlines/propose",
        json={
            "outline": _modules_fragment(),
            "attach_under": {"kind": "project", "id": str(project.id)},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    counts = _count_by_type(body["actions"])
    assert counts.get("create_epic", 0) == 0
    assert counts.get("create_project", 0) == 0
    assert counts.get("create_section") == 1
    assert counts.get("create_task") == 1

    section = next(a for a in body["actions"] if a["type"] == "create_section")
    assert section["project_id"] == str(project.id)
    assert section.get("project_key") is None

    task = next(a for a in body["actions"] if a["type"] == "create_task")
    assert task["project_id"] == str(project.id)


def test_apply_graft_under_epic(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    epic = Epic(owner_id=user.id, title="Target Epic", sort_order=0)
    db_session.add(epic)
    db_session.flush()

    propose = client.post(
        "/api/v1/outlines/propose",
        json={
            "outline": _course_fragment(),
            "attach_under": {"kind": "epic", "id": str(epic.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    actions = propose.json()["actions"]

    apply = client.post("/api/v1/outlines/apply", json={"actions": actions})
    assert apply.status_code == 200, apply.text
    assert all(r["ok"] for r in apply.json()["results"])

    grafted = (
        db_session.query(Project)
        .filter(Project.owner_id == user.id, Project.title == "Grafted Course")
        .one()
    )
    assert grafted.epic_id == epic.id
    assert (
        db_session.query(Epic)
        .filter(Epic.owner_id == user.id, Epic.title == "Grafted Course")
        .count()
        == 0
    )


def test_apply_graft_under_project(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    epic = Epic(owner_id=user.id, title="Parent Epic", sort_order=0)
    db_session.add(epic)
    db_session.flush()
    project = Project(owner_id=user.id, epic_id=epic.id, title="Target Project", sort_order=0)
    db_session.add(project)
    db_session.flush()

    propose = client.post(
        "/api/v1/outlines/propose",
        json={
            "outline": _modules_fragment(),
            "attach_under": {"kind": "project", "id": str(project.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    actions = propose.json()["actions"]

    apply = client.post("/api/v1/outlines/apply", json={"actions": actions})
    assert apply.status_code == 200, apply.text
    assert all(r["ok"] for r in apply.json()["results"])

    section = (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.title == "Graft Section")
        .one()
    )
    assert section.project_id == project.id


def test_propose_attach_not_found(client: TestClient) -> None:
    res = client.post(
        "/api/v1/outlines/propose",
        json={
            "outline": _course_fragment(),
            "attach_under": {"kind": "epic", "id": str(uuid.uuid4())},
        },
    )
    assert res.status_code == 404
    assert res.json()["code"] == "OUTLINE_ATTACH_NOT_FOUND"
