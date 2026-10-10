"""F5-B template apply — labels, optional skip, scaffold, estimate disclosure.

W1 proved shapes and skip counts. These tests check the created graph.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Epic, Label, Project, Section, Task, TaskLabel, UserSettings
from tests.test_outlines import _current_user, _tiny_outline

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "testdata/outlines/ibm_rag_agentic_ai_professional_certificate_curriculum.json"
)


def _labels(db: Session, task_id: uuid.UUID) -> set[str]:
    names: set[str] = set()
    for row in db.query(TaskLabel).filter(TaskLabel.task_id == task_id):
        label = db.get(Label, row.label_id)
        assert label is not None
        names.add(label.name.lower())
    return names


def _apply(client: TestClient, template_id: str, payload: dict) -> dict:
    response = client.post(
        f"/api/v1/templates/{template_id}/apply",
        json={"idempotency_key": str(uuid.uuid4()), **payload},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_template_apply_round_trips_labels_urls_and_order(
    client: TestClient, db_session: Session
) -> None:
    outline = _tiny_outline()
    propose = client.post(
        "/api/v1/templates/coursera_specialization/propose",
        json={"outline": outline},
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["summary"]["task_count"] == 2
    assert body["summary"]["optional_skipped"] == 0
    assert any("Course One=2" in warning for warning in body["warnings"])
    assert any("Module A=1" in warning for warning in body["warnings"])
    assert any("not task scheduling durations" in warning for warning in body["warnings"])

    tasks = [entity for entity in body["payload"]["entities"] if entity["kind"] == "task"]
    by_title = {entity["title"]: entity for entity in tasks}
    assert set(by_title) == {"Video: Hello", "Reading: Extra"}
    assert by_title["Video: Hello"]["label_names"] == ["video"]
    assert by_title["Video: Hello"]["estimated_duration_minutes"] == 5
    assert by_title["Video: Hello"]["sort_order"] == 1
    assert by_title["Reading: Extra"]["label_names"] == ["reading", "optional"]
    assert by_title["Reading: Extra"]["estimated_duration_minutes"] == 3
    assert by_title["Reading: Extra"]["sort_order"] == 2
    assert by_title["Video: Hello"]["estimated_duration_minutes"] != 2 * 60

    project = next(entity for entity in body["payload"]["entities"] if entity["kind"] == "project")
    description = project["description"] or ""
    assert "url: https://example.com/course" in description
    assert "estimated_hours: 2" in description
    assert "module_estimated_hours: Module A=1" in description
    epic = next(entity for entity in body["payload"]["entities"] if entity["kind"] == "epic")
    assert "source_url: https://example.com/cert" in (epic["description"] or "")
    assert body["payload"]["source_refs"][0]["url"] == "https://example.com/cert"

    applied = _apply(client, "coursera_specialization", body["payload"])
    assert applied["created_counts"]["task"] == 2

    user = _current_user(client, db_session)
    stored_epic = (
        db_session.query(Epic).filter(Epic.owner_id == user.id, Epic.title == "Tiny Certificate").one()
    )
    assert stored_epic.source_refs
    assert stored_epic.source_refs[0]["url"] == "https://example.com/cert"
    stored_project = (
        db_session.query(Project)
        .filter(Project.owner_id == user.id, Project.epic_id == stored_epic.id, Project.title == "Course One")
        .one()
    )
    assert "estimated_hours: 2" in (stored_project.description or "")
    assert "url: https://example.com/course" in (stored_project.description or "")
    assert "module_estimated_hours: Module A=1" in (stored_project.description or "")

    hello = db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Video: Hello").one()
    extra = db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Reading: Extra").one()
    assert hello.sort_order == 1
    assert extra.sort_order == 2
    assert hello.estimated_duration_minutes == 5
    assert extra.estimated_duration_minutes == 3
    assert _labels(db_session, hello.id) == {"video"}
    assert _labels(db_session, extra.id) == {"reading", "optional"}


def test_template_skip_optional_excludes_tasks_from_created_graph(
    client: TestClient, db_session: Session
) -> None:
    outline = _tiny_outline()
    propose = client.post(
        "/api/v1/templates/coursera_course/propose",
        json={"outline": {"course": outline["courses"][0]}, "skip_optional": True},
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["summary"]["task_count"] == 1
    assert body["summary"]["optional_skipped"] == 1
    titles = [entity["title"] for entity in body["payload"]["entities"] if entity["kind"] == "task"]
    assert titles == ["Video: Hello"]
    assert all("optional" not in entity.get("label_names", []) for entity in body["payload"]["entities"])

    applied = _apply(client, "coursera_course", body["payload"])
    assert applied["created_counts"]["task"] == 1

    user = _current_user(client, db_session)
    assert db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Reading: Extra").count() == 0
    hello = db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Video: Hello").one()
    assert _labels(db_session, hello.id) == {"video"}
    assert "optional" not in _labels(db_session, hello.id)


def test_template_blank_scaffold_apply_creates_placeholder_graph(
    client: TestClient, db_session: Session
) -> None:
    detail = client.get("/api/v1/templates/coursera_specialization")
    assert detail.status_code == 200, detail.text
    outline = detail.json()["example_outline"]
    propose = client.post(
        "/api/v1/templates/coursera_specialization/propose",
        json={"outline": outline},
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["is_scaffold"] is True
    assert any("blank scaffold" in warning for warning in body["warnings"])
    assert body["summary"] == {
        "epic_count": 1,
        "project_count": 2,
        "section_count": 3,
        "task_count": 5,
        "optional_skipped": 0,
    }

    applied = _apply(client, "coursera_specialization", body["payload"])
    assert applied["replayed"] is False
    assert applied["created_counts"]["epic"] == 1
    assert applied["created_counts"]["project"] == 2
    assert applied["created_counts"]["section"] == 3
    assert applied["created_counts"]["task"] == 5

    user = _current_user(client, db_session)
    epic = (
        db_session.query(Epic)
        .filter(Epic.owner_id == user.id, Epic.title == "Your program or learning path title")
        .one()
    )
    assert epic.schedule_style is not None
    welcome = (
        db_session.query(Task)
        .filter(Task.owner_id == user.id, Task.title == "Video: Welcome and overview")
        .one()
    )
    quiz = db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Practice quiz").one()
    assert welcome.estimated_duration_minutes == 12
    assert welcome.estimated_duration_minutes != 4 * 60
    assert _labels(db_session, welcome.id) == {"video"}
    assert _labels(db_session, quiz.id) == {"assignment", "optional"}


def test_template_module_scaffold_apply_under_project(
    client: TestClient, db_session: Session
) -> None:
    user = _current_user(client, db_session)
    project = Project(owner_id=user.id, title="Scaffold Host", sort_order=0)
    db_session.add(project)
    db_session.flush()

    detail = client.get("/api/v1/templates/coursera_module")
    assert detail.status_code == 200, detail.text
    outline = detail.json()["example_outline"]
    propose = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": outline,
            "attach_under": {"kind": "project", "id": str(project.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["is_scaffold"] is True
    assert any("blank scaffold" in warning for warning in body["warnings"])
    assert body["summary"]["section_count"] == 1
    assert body["summary"]["task_count"] == 3
    assert body["summary"]["optional_skipped"] == 0

    applied = _apply(client, "coursera_module", body["payload"])
    assert applied["created_counts"]["section"] == 1
    assert applied["created_counts"]["task"] == 3
    section = (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id)
        .one()
    )
    assert section.title.startswith("Week 1")
    titles = {
        task.title
        for task in db_session.query(Task).filter(Task.owner_id == user.id, Task.section_id == section.id)
    }
    assert titles == {
        "Video: Welcome and overview",
        "Reading: Syllabus and setup guide",
        "Practice quiz",
    }


def test_template_estimated_hours_are_not_task_durations(
    client: TestClient, db_session: Session
) -> None:
    outline = {
        "course": {
            "course_order": 1,
            "title": "Hours Course",
            "estimated_hours": 9,
            "url": "https://example.com/hours-course",
            "modules": [
                {
                    "module_order": 1,
                    "title": "Hours Module",
                    "estimated_hours": 3,
                    "tasks": [
                        {
                            "task_type": "video",
                            "title": "Video: Timed clip",
                            "duration_minutes": 12,
                            "optional": False,
                            "task_order": 1,
                            "id": "h1",
                        },
                        {
                            "task_type": "reading",
                            "title": "Reading: No duration",
                            "optional": False,
                            "task_order": 2,
                            "id": "h2",
                        },
                    ],
                }
            ],
        }
    }
    propose = client.post("/api/v1/templates/coursera_course/propose", json={"outline": outline})
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert any("Hours Course=9" in warning for warning in body["warnings"])
    assert any("Hours Module=3" in warning for warning in body["warnings"])
    assert any("disclosed default" in warning for warning in body["warnings"])

    user = _current_user(client, db_session)
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == user.id).one()
    default_minutes = settings.default_estimated_duration_minutes
    assert default_minutes != 9 * 60
    assert default_minutes != 3 * 60

    duration_defaults = [
        item
        for item in body["resolved_defaults"]
        if item["field"] == "estimated_duration_minutes"
    ]
    assert len(duration_defaults) == 1
    assert duration_defaults[0]["entity_key"] == "h2"
    assert duration_defaults[0]["value"] == default_minutes

    by_title = {
        entity["title"]: entity
        for entity in body["payload"]["entities"]
        if entity["kind"] == "task"
    }
    assert by_title["Video: Timed clip"]["estimated_duration_minutes"] == 12
    assert by_title["Reading: No duration"]["estimated_duration_minutes"] == default_minutes
    project = next(entity for entity in body["payload"]["entities"] if entity["kind"] == "project")
    description = project["description"] or ""
    assert "estimated_hours: 9" in description
    assert "module_estimated_hours: Hours Module=3" in description
    assert "url: https://example.com/hours-course" in description

    _apply(client, "coursera_course", body["payload"])
    timed = db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Video: Timed clip").one()
    untimed = (
        db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Reading: No duration").one()
    )
    stored = (
        db_session.query(Project).filter(Project.owner_id == user.id, Project.title == "Hours Course").one()
    )
    assert timed.estimated_duration_minutes == 12
    assert untimed.estimated_duration_minutes == default_minutes
    assert "estimated_hours: 9" in (stored.description or "")
    assert stored.source_refs
    assert stored.source_refs[0]["url"] == "https://example.com/hours-course"


def test_template_module_estimated_hours_warn_and_do_not_set_duration(
    client: TestClient, db_session: Session
) -> None:
    user = _current_user(client, db_session)
    project = Project(owner_id=user.id, title="Module Hours Host", sort_order=0)
    db_session.add(project)
    db_session.flush()
    outline = {
        "module": {
            "module_order": 1,
            "title": "Estimate Module",
            "estimated_hours": 4,
            "tasks": [
                {
                    "task_type": "lab",
                    "title": "Lab: Short",
                    "duration_minutes": 8,
                    "optional": False,
                    "task_order": 1,
                    "id": "est-1",
                }
            ],
        }
    }
    propose = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": outline,
            "attach_under": {"kind": "project", "id": str(project.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert any("Estimate Module=4" in warning for warning in body["warnings"])
    task_entity = next(entity for entity in body["payload"]["entities"] if entity["kind"] == "task")
    assert task_entity["estimated_duration_minutes"] == 8
    assert task_entity["estimated_duration_minutes"] != 4 * 60

    _apply(client, "coursera_module", body["payload"])
    task = db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Lab: Short").one()
    assert task.estimated_duration_minutes == 8
    assert _labels(db_session, task.id) == {"lab"}
    section = (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id, Section.title == "Estimate Module")
        .one()
    )
    assert task.section_id == section.id


def test_ibm_template_apply_matches_propose_counts(client: TestClient, db_session: Session) -> None:
    outline = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    propose = client.post(
        "/api/v1/templates/coursera_specialization/propose",
        json={"outline": outline},
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["summary"]["task_count"] == 417
    assert body["summary"]["project_count"] == 10
    assert body["summary"]["section_count"] == 30
    assert any("not task scheduling durations" in warning for warning in body["warnings"])
    assert any("Noted on " in warning for warning in body["warnings"])

    applied = _apply(client, "coursera_specialization", body["payload"])
    assert applied["created_counts"]["epic"] == 1
    assert applied["created_counts"]["project"] == 10
    assert applied["created_counts"]["section"] == 30
    assert applied["created_counts"]["task"] == 417

    by_key = {row["key"]: row["id"] for row in applied["entities"]}
    epic_entity = next(entity for entity in body["payload"]["entities"] if entity["kind"] == "epic")
    epic = db_session.get(Epic, uuid.UUID(by_key[epic_entity["key"]]))
    assert epic is not None
    assert "IBM RAG" in epic.title

    project_entity = next(
        entity
        for entity in body["payload"]["entities"]
        if entity["kind"] == "project" and "estimated_hours:" in (entity.get("description") or "")
    )
    project = db_session.get(Project, uuid.UUID(by_key[project_entity["key"]]))
    assert project is not None
    assert project.epic_id == epic.id
    assert "estimated_hours:" in (project.description or "")

    task_entity = next(
        entity for entity in body["payload"]["entities"] if entity["kind"] == "task" and entity["label_names"]
    )
    task = db_session.get(Task, uuid.UUID(by_key[task_entity["key"]]))
    assert task is not None
    assert task.title == task_entity["title"]
    assert task.estimated_duration_minutes == task_entity["estimated_duration_minutes"]
    assert _labels(db_session, task.id) == {name.lower() for name in task_entity["label_names"]}
