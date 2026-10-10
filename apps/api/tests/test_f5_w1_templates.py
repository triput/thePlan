"""F5-W1 Coursera templates — catalog, propose, apply via handoff receipts.

Smoke covers F5-A shapes/attachments, F5-C replay vs a second instance, and F5-D
legacy outline propose plus the IBM fixture through the template proposer.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Epic, HandoffReceipt, Project, ScheduleStyle, Section, Task
from app.models.handoff import TEMPLATE_APPLY_KIND
from tests.test_outlines import _course_fragment, _current_user, _tiny_outline

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "testdata/outlines/ibm_rag_agentic_ai_professional_certificate_curriculum.json"
)


def test_templates_list_and_get(client: TestClient) -> None:
    listed = client.get("/api/v1/templates")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert ids == {"coursera_specialization", "coursera_course", "coursera_module"}

    detail = client.get("/api/v1/templates/coursera_specialization")
    assert detail.status_code == 200
    body = detail.json()
    assert body["version"] == 1
    assert "example_outline" in body
    assert body["is_scaffold"] is True


def test_template_specialization_propose_apply_idempotent(
    client: TestClient, db_session: Session
) -> None:
    outline = _tiny_outline()
    propose = client.post(
        "/api/v1/templates/coursera_specialization/propose",
        json={"outline": outline, "skip_optional": True},
    )
    assert propose.status_code == 200, propose.text
    prop_body = propose.json()
    assert prop_body["template_id"] == "coursera_specialization"
    assert prop_body["template_version"] == 1
    assert prop_body["is_scaffold"] is False
    assert prop_body["summary"]["epic_count"] == 1
    assert prop_body["summary"]["project_count"] == 1
    assert prop_body["summary"]["section_count"] == 1
    assert prop_body["summary"]["task_count"] == 1
    assert prop_body["summary"]["optional_skipped"] == 1
    assert any(item["field"] == "priority" for item in prop_body["resolved_defaults"])
    payload = prop_body["payload"]
    assert payload["schedule_policy"] == "manual"

    key = str(uuid.uuid4())
    apply_body = {"idempotency_key": key, **payload}
    first = client.post("/api/v1/templates/coursera_specialization/apply", json=apply_body)
    assert first.status_code == 200, first.text
    assert first.json()["replayed"] is False
    assert first.json()["template_id"] == "coursera_specialization"

    second = client.post("/api/v1/templates/coursera_specialization/apply", json=apply_body)
    assert second.status_code == 200
    assert second.json()["replayed"] is True

    receipt = client.get(f"/api/v1/templates/receipts/by-key/{key}")
    assert receipt.status_code == 200
    assert receipt.json()["receipt_id"] == first.json()["receipt_id"]
    assert receipt.json()["template_id"] == "coursera_specialization"

    handoff_lookup = client.get(f"/api/v1/handoffs/receipts/by-key/{key}")
    assert handoff_lookup.status_code == 404

    stored = (
        db_session.query(HandoffReceipt)
        .filter(HandoffReceipt.idempotency_key == uuid.UUID(key))
        .one()
    )
    assert stored.operation_kind == TEMPLATE_APPLY_KIND

    user = _current_user(client, db_session)
    epic = db_session.query(Epic).filter(Epic.owner_id == user.id, Epic.title == "Tiny Certificate").one()
    assert epic.schedule_style == ScheduleStyle.manual
    project = (
        db_session.query(Project)
        .filter(Project.owner_id == user.id, Project.epic_id == epic.id, Project.title == "Course One")
        .one()
    )
    section = (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id, Section.title == "Module A")
        .one()
    )
    task = (
        db_session.query(Task)
        .filter(Task.owner_id == user.id, Task.section_id == section.id)
        .one()
    )
    assert task.title == "Video: Hello"
    assert task.estimated_duration_minutes == 5
    assert task.schedule_style is None

    mutated = json.loads(json.dumps(payload))
    mutated["entities"][0]["title"] = "Not the same graph"
    conflict = client.post(
        "/api/v1/templates/coursera_specialization/apply",
        json={"idempotency_key": key, **mutated},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSE"
    assert (
        db_session.query(Epic).filter(Epic.owner_id == user.id, Epic.title == "Tiny Certificate").count()
        == 1
    )

    again = client.post(
        "/api/v1/templates/coursera_specialization/propose",
        json={"outline": outline, "skip_optional": True},
    )
    assert again.status_code == 200, again.text
    assert any("already appears" in warning for warning in again.json()["warnings"])

    key2 = str(uuid.uuid4())
    third = client.post(
        "/api/v1/templates/coursera_specialization/apply",
        json={"idempotency_key": key2, **payload},
    )
    assert third.status_code == 200, third.text
    assert third.json()["replayed"] is False
    assert third.json()["receipt_id"] != first.json()["receipt_id"]
    assert (
        db_session.query(Epic).filter(Epic.owner_id == user.id, Epic.title == "Tiny Certificate").count()
        == 2
    )


def _module_outline() -> dict:
    return {
        "module": {
            "module_order": 3,
            "title": "Week 3 lab",
            "tasks": [
                {
                    "task_type": "video",
                    "title": "Video: Lab intro",
                    "duration_minutes": 8,
                    "optional": False,
                    "task_order": 1,
                    "id": "m03-t01",
                }
            ],
        }
    }


def test_template_course_standalone_project_only(client: TestClient, db_session: Session) -> None:
    outline = _tiny_outline()
    course = outline["courses"][0]
    propose = client.post(
        "/api/v1/templates/coursera_course/propose",
        json={"outline": {"course": course}},
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    summary = body["summary"]
    assert summary["epic_count"] == 0
    assert summary["project_count"] == 1
    assert summary["section_count"] >= 1
    assert summary["task_count"] == 2

    key = str(uuid.uuid4())
    applied = client.post(
        "/api/v1/templates/coursera_course/apply",
        json={"idempotency_key": key, **body["payload"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["created_counts"]["epic"] == 0
    assert applied.json()["created_counts"]["project"] == 1

    user = _current_user(client, db_session)
    project = (
        db_session.query(Project)
        .filter(Project.owner_id == user.id, Project.title == "Course One")
        .one()
    )
    assert project.epic_id is None
    assert project.schedule_style == ScheduleStyle.manual
    section = (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id)
        .one()
    )
    assert section.title == "Module A"


def test_template_course_under_existing_epic(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    epic = Epic(owner_id=user.id, title="Existing Epic", sort_order=0)
    db_session.add(epic)
    db_session.flush()

    propose = client.post(
        "/api/v1/templates/coursera_course/propose",
        json={
            "outline": _course_fragment(),
            "attach_under": {"kind": "epic", "id": str(epic.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["summary"]["epic_count"] == 0
    assert body["summary"]["project_count"] == 1
    assert body["summary"]["task_count"] == 1

    applied = client.post(
        "/api/v1/templates/coursera_course/apply",
        json={"idempotency_key": str(uuid.uuid4()), **body["payload"]},
    )
    assert applied.status_code == 200, applied.text
    grafted = (
        db_session.query(Project)
        .filter(Project.owner_id == user.id, Project.title == "Grafted Course")
        .one()
    )
    assert grafted.epic_id == epic.id
    assert grafted.schedule_style == ScheduleStyle.manual


def test_template_specialization_grafts_courses_onto_epic(
    client: TestClient, db_session: Session
) -> None:
    user = _current_user(client, db_session)
    epic = Epic(owner_id=user.id, title="Existing Epic", sort_order=0)
    db_session.add(epic)
    db_session.flush()

    propose = client.post(
        "/api/v1/templates/coursera_specialization/propose",
        json={
            "outline": _tiny_outline(),
            "attach_under": {"kind": "epic", "id": str(epic.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["summary"]["epic_count"] == 0
    assert body["summary"]["project_count"] == 1

    applied = client.post(
        "/api/v1/templates/coursera_specialization/apply",
        json={"idempotency_key": str(uuid.uuid4()), **body["payload"]},
    )
    assert applied.status_code == 200, applied.text
    assert (
        db_session.query(Epic).filter(Epic.owner_id == user.id, Epic.title == "Tiny Certificate").count()
        == 0
    )
    project = (
        db_session.query(Project)
        .filter(Project.owner_id == user.id, Project.title == "Course One")
        .one()
    )
    assert project.epic_id == epic.id
    assert epic.title == "Existing Epic"


def test_template_module_under_project_replay_and_second_instance(
    client: TestClient, db_session: Session
) -> None:
    user = _current_user(client, db_session)
    project = Project(owner_id=user.id, title="Host Project", sort_order=0)
    db_session.add(project)
    db_session.flush()

    propose = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": _module_outline(),
            "attach_under": {"kind": "project", "id": str(project.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["summary"] == {
        "epic_count": 0,
        "project_count": 0,
        "section_count": 1,
        "task_count": 1,
        "optional_skipped": 0,
    }
    payload = body["payload"]

    key = str(uuid.uuid4())
    first = client.post(
        "/api/v1/templates/coursera_module/apply",
        json={"idempotency_key": key, **payload},
    )
    assert first.status_code == 200, first.text
    assert first.json()["replayed"] is False
    assert first.json()["template_id"] == "coursera_module"
    assert first.json()["created_counts"]["section"] == 1
    assert first.json()["created_counts"]["task"] == 1

    section = (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id, Section.title == "Week 3 lab")
        .one()
    )
    task = db_session.query(Task).filter(Task.owner_id == user.id, Task.section_id == section.id).one()
    assert task.title == "Video: Lab intro"
    assert task.project_id == project.id
    assert task.estimated_duration_minutes == 8
    assert (
        db_session.query(Project).filter(Project.owner_id == user.id, Project.title == "Week 3 lab").count()
        == 0
    )

    second = client.post(
        "/api/v1/templates/coursera_module/apply",
        json={"idempotency_key": key, **payload},
    )
    assert second.status_code == 200, second.text
    assert second.json()["replayed"] is True
    assert second.json()["receipt_id"] == first.json()["receipt_id"]
    assert (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id)
        .count()
        == 1
    )

    third = client.post(
        "/api/v1/templates/coursera_module/apply",
        json={"idempotency_key": str(uuid.uuid4()), **payload},
    )
    assert third.status_code == 200, third.text
    assert third.json()["replayed"] is False
    assert third.json()["receipt_id"] != first.json()["receipt_id"]
    assert (
        db_session.query(Section)
        .filter(Section.owner_id == user.id, Section.project_id == project.id, Section.title == "Week 3 lab")
        .count()
        == 2
    )


def test_template_module_under_section_adds_tasks_only(
    client: TestClient, db_session: Session
) -> None:
    user = _current_user(client, db_session)
    project = Project(owner_id=user.id, title="Host Project", sort_order=0)
    db_session.add(project)
    db_session.flush()
    section = Section(owner_id=user.id, project_id=project.id, title="Existing Section", sort_order=0)
    db_session.add(section)
    db_session.flush()

    propose = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": _module_outline(),
            "attach_under": {"kind": "section", "id": str(section.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    assert body["summary"]["section_count"] == 0
    assert body["summary"]["task_count"] == 1

    applied = client.post(
        "/api/v1/templates/coursera_module/apply",
        json={"idempotency_key": str(uuid.uuid4()), **body["payload"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["created_counts"]["section"] == 0
    assert applied.json()["created_counts"]["task"] == 1
    task = db_session.query(Task).filter(Task.owner_id == user.id, Task.title == "Video: Lab intro").one()
    assert task.section_id == section.id
    assert task.project_id == project.id
    assert (
        db_session.query(Section).filter(Section.owner_id == user.id, Section.project_id == project.id).count()
        == 1
    )


def test_template_module_attach_rules(client: TestClient, db_session: Session) -> None:
    missing = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={"outline": _module_outline()},
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "TEMPLATE_ATTACH_REQUIRED"

    user = _current_user(client, db_session)
    epic = Epic(owner_id=user.id, title="Not a project", sort_order=0)
    db_session.add(epic)
    db_session.flush()
    wrong_kind = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": _module_outline(),
            "attach_under": {"kind": "epic", "id": str(epic.id)},
        },
    )
    assert wrong_kind.status_code == 422
    assert wrong_kind.json()["code"] == "TEMPLATE_ATTACH_INVALID"

    absent = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": _module_outline(),
            "attach_under": {"kind": "project", "id": str(uuid.uuid4())},
        },
    )
    assert absent.status_code == 404
    assert absent.json()["code"] == "OUTLINE_ATTACH_NOT_FOUND"

    unknown = client.get("/api/v1/templates/not_a_template")
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "TEMPLATE_NOT_FOUND"


def test_template_course_rejects_certificate_outline(client: TestClient) -> None:
    one_course = _tiny_outline()
    response = client.post(
        "/api/v1/templates/coursera_course/propose",
        json={"outline": one_course},
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "OUTLINE_INVALID"
    assert "coursera_specialization" in response.json()["detail"]


def test_template_course_rejects_multi_course_outline(client: TestClient) -> None:
    outline = _tiny_outline()
    second = json.loads(json.dumps(outline["courses"][0]))
    second["course_order"] = 2
    second["title"] = "Course Two"
    response = client.post(
        "/api/v1/templates/coursera_course/propose",
        json={"outline": {"courses": [outline["courses"][0], second]}},
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "OUTLINE_INVALID"
    assert "exactly one course" in response.json()["detail"]


def test_template_skip_optional_with_nothing_left_is_invalid(
    client: TestClient, db_session: Session
) -> None:
    user = _current_user(client, db_session)
    project = Project(owner_id=user.id, title="Host Project", sort_order=0)
    db_session.add(project)
    db_session.flush()
    section = Section(owner_id=user.id, project_id=project.id, title="Existing Section", sort_order=0)
    db_session.add(section)
    db_session.flush()
    outline = _module_outline()
    outline["module"]["tasks"][0]["optional"] = True
    response = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": outline,
            "skip_optional": True,
            "attach_under": {"kind": "section", "id": str(section.id)},
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "OUTLINE_INVALID"


def test_template_scaffold_is_flagged(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    project = Project(owner_id=user.id, title="Host Project", sort_order=0)
    db_session.add(project)
    db_session.flush()
    detail = client.get("/api/v1/templates/coursera_module")
    assert detail.status_code == 200
    assert detail.json()["is_scaffold"] is True
    propose = client.post(
        "/api/v1/templates/coursera_module/propose",
        json={
            "outline": detail.json()["example_outline"],
            "attach_under": {"kind": "project", "id": str(project.id)},
        },
    )
    assert propose.status_code == 200, propose.text
    assert propose.json()["is_scaffold"] is True
    assert any("blank scaffold" in warning for warning in propose.json()["warnings"])


def test_legacy_outline_fixture_still_proposes(client: TestClient) -> None:
    outline = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    response = client.post(
        "/api/v1/outlines/propose",
        json={"template_id": "coursera_specialization", "outline": outline},
    )
    assert response.status_code == 200
    assert response.json()["summary"]["task_count"] > 100


def test_ibm_fixture_template_propose_matches_legacy(client: TestClient) -> None:
    outline = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    legacy = client.post(
        "/api/v1/outlines/propose",
        json={"template_id": "coursera_specialization", "outline": outline},
    )
    assert legacy.status_code == 200, legacy.text
    templated = client.post(
        "/api/v1/templates/coursera_specialization/propose",
        json={"outline": outline},
    )
    assert templated.status_code == 200, templated.text
    legacy_summary = legacy.json()["summary"]
    template_summary = templated.json()["summary"]
    assert template_summary["epic_count"] == legacy_summary["epic_count"] == 1
    assert template_summary["project_count"] == legacy_summary["project_count"] == 10
    assert template_summary["section_count"] == legacy_summary["section_count"] == 30
    assert template_summary["task_count"] == legacy_summary["task_count"] == 417
    assert templated.json()["payload"]["schedule_policy"] == "manual"
    assert templated.json()["template_id"] == "coursera_specialization"
