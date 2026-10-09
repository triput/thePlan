"""F1 planning handoff API — graph apply, idempotency, dependencies."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import HandoffReceipt, Project, Task, User
from app.scheduler.candidates import load_candidates
from app.services.auth_users import get_or_provision_user_settings


def _handoff_graph(*, extra_entities: list[dict] | None = None) -> dict:
    entities = [
        {"key": "project", "kind": "project", "title": "Build the agreed experiment"},
        {"key": "section_a", "kind": "section", "parent_key": "project", "title": "First slice"},
        {"key": "section_b", "kind": "section", "parent_key": "project", "title": "Second slice"},
        {"key": "design", "kind": "task", "parent_key": "section_a", "title": "Describe acceptance"},
        {"key": "nested", "kind": "task", "parent_key": "design", "title": "Nested example"},
        {"key": "build", "kind": "task", "parent_key": "section_b", "title": "Implement slice"},
    ]
    if extra_entities:
        entities.extend(extra_entities)
    return {
        "schema_version": 1,
        "source_refs": [
            {
                "system": "squirrel-board",
                "id": "IDEA-example",
                "url": "https://example.invalid/ideas/example",
            }
        ],
        "entities": entities,
        "dependencies": [{"blocking_key": "design", "dependent_key": "build"}],
    }


def test_handoff_propose_discloses_defaults(client: TestClient) -> None:
    response = client.post("/api/v1/handoffs/propose", json=_handoff_graph())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["payload"]["schedule_policy"] == "manual"
    fields = {(item["entity_key"], item["field"]) for item in body["resolved_defaults"]}
    assert ("design", "estimated_duration_minutes") in fields
    assert ("*", "schedule_policy") in fields


def test_f1_e_propose_discloses_priority_and_omits_due(client: TestClient) -> None:
    graph = _handoff_graph()
    response = client.post("/api/v1/handoffs/propose", json=graph)
    assert response.status_code == 200, response.text
    body = response.json()
    defaults = {
        (item["entity_key"], item["field"]): item["value"] for item in body["resolved_defaults"]
    }
    for task_key in ("design", "nested", "build"):
        assert defaults[(task_key, "priority")] == "p4"
        assert (task_key, "estimated_duration_minutes") in defaults
        entity = next(item for item in body["payload"]["entities"] if item["key"] == task_key)
        assert entity.get("due_at") is None

    applied = client.post(
        "/api/v1/handoffs/apply",
        json={"idempotency_key": str(uuid4()), **graph},
    )
    assert applied.status_code == 200, applied.text
    task_ids = [item["id"] for item in applied.json()["entities"] if item["kind"] == "task"]
    assert task_ids
    for task_id in task_ids:
        task = client.get(f"/api/v1/tasks/{task_id}").json()
        assert task["priority"] == "p4"
        assert task.get("due_at") is None


def test_f1_a_graph_create_and_readback(client: TestClient) -> None:
    key = uuid4()
    payload = _handoff_graph()
    apply_resp = client.post(
        "/api/v1/handoffs/apply",
        json={"idempotency_key": str(key), **payload},
    )
    assert apply_resp.status_code == 200, apply_resp.text
    result = apply_resp.json()
    assert result["replayed"] is False
    assert result["dependencies_created"] == 1

    by_kind = {item["kind"]: item for item in result["entities"]}
    project_id = by_kind["project"]["id"]
    project = client.get(f"/api/v1/projects/{project_id}").json()
    assert project["source_refs"][0]["id"] == "IDEA-example"

    task_ids = [item["id"] for item in result["entities"] if item["kind"] == "task"]
    assert len(task_ids) == 3
    for task_id in task_ids:
        task = client.get(f"/api/v1/tasks/{task_id}").json()
        assert task["schedule_style"] == "manual"
        assert task.get("due_at") is None

    nested = next(item for item in result["entities"] if item["key"] == "nested")
    assert nested["kind"] == "task"
    nested_task = client.get(f"/api/v1/tasks/{nested['id']}").json()
    assert nested_task["nesting_level"] == 1

    receipt = client.get(f"/api/v1/handoffs/receipts/by-key/{key}").json()
    assert receipt["idempotency_key"] == str(key)
    assert receipt["receipt_json"]["receipt_id"] == result["receipt_id"]


def test_f1_b_idempotent_replay(client: TestClient, db_session: Session) -> None:
    key = uuid4()
    payload = _handoff_graph()
    first = client.post("/api/v1/handoffs/apply", json={"idempotency_key": str(key), **payload})
    second = client.post("/api/v1/handoffs/apply", json={"idempotency_key": str(key), **payload})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert first.json()["receipt_id"] == second.json()["receipt_id"]
    count = db_session.query(HandoffReceipt).filter(HandoffReceipt.idempotency_key == key).count()
    assert count == 1
    project_count = db_session.query(Project).filter(Project.title == "Build the agreed experiment").count()
    assert project_count == 1


def test_f1_b_concurrent_unique_key_one_receipt(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second apply loses the pre-check and must collapse on the unique receipt key.

    The transactional Session and TestClient are not thread-safe, and a second
    connection cannot see this fixture's uncommitted rows. Skipping the first
    existence read is the overlapping-apply race: both callers pass the check,
    then the unique constraint keeps a single graph and receipt.
    """
    from app.schemas.handoffs import HandoffApplyRequest
    from app.services import handoff_apply

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    user = db_session.get(User, UUID(me.json()["id"]))
    assert user is not None

    key = uuid4()
    payload = _handoff_graph()
    title = f"Concurrent handoff {key}"
    payload["entities"][0]["title"] = title
    body = HandoffApplyRequest.model_validate({"idempotency_key": str(key), **payload})

    first = handoff_apply.apply_handoff(db_session, user, body)
    assert first.replayed is False

    real_existing = handoff_apply._existing_receipt
    skipped = False

    def miss_precheck(db: Session, owner: User, idempotency_key: UUID):
        nonlocal skipped
        if not skipped:
            skipped = True
            return None
        return real_existing(db, owner, idempotency_key)

    monkeypatch.setattr(handoff_apply, "_existing_receipt", miss_precheck)
    second = handoff_apply.apply_handoff(db_session, user, body)

    assert second.replayed is True
    assert second.receipt_id == first.receipt_id
    assert [item.id for item in second.entities] == [item.id for item in first.entities]
    assert (
        db_session.query(HandoffReceipt).filter(HandoffReceipt.idempotency_key == key).count()
        == 1
    )
    assert db_session.query(Project).filter(Project.title == title).count() == 1


def test_f1_c_conflict_on_payload_change(client: TestClient) -> None:
    key = uuid4()
    payload = _handoff_graph()
    assert client.post("/api/v1/handoffs/apply", json={"idempotency_key": str(key), **payload}).status_code == 200
    payload["entities"][0]["title"] = "Changed title"
    conflict = client.post("/api/v1/handoffs/apply", json={"idempotency_key": str(key), **payload})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSE"


def test_f1_c_foreign_parent_no_partial_write(client: TestClient, db_session: Session) -> None:
    before = db_session.query(Project).count()
    payload = {
        "schema_version": 1,
        "entities": [
            {
                "key": "task",
                "kind": "task",
                "title": "Orphan attempt",
                "parent": {"kind": "section", "id": str(uuid4())},
            }
        ],
    }
    response = client.post(
        "/api/v1/handoffs/apply",
        json={"idempotency_key": str(uuid4()), **payload},
    )
    assert response.status_code == 422
    assert db_session.query(Project).count() == before
    assert db_session.query(Task).filter(Task.title == "Orphan attempt").count() == 0


def test_f1_c_cycle_rejected(client: TestClient) -> None:
    payload = _handoff_graph()
    payload["dependencies"] = [
        {"blocking_key": "design", "dependent_key": "build"},
        {"blocking_key": "build", "dependent_key": "design"},
    ]
    response = client.post(
        "/api/v1/handoffs/apply",
        json={"idempotency_key": str(uuid4()), **payload},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "HANDOFF_VALIDATION"


def test_f1_d_task_graft_leaves_parent_policy(client: TestClient, db_session: Session) -> None:
    from app.models import Project, Section
    from app.models.enums import ScheduleStyle

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    user = db_session.get(User, UUID(me.json()["id"]))
    assert user is not None
    project_row = Project(
        owner_id=user.id,
        title="Existing host",
        schedule_style=ScheduleStyle.standalone,
    )
    db_session.add(project_row)
    db_session.flush()
    section_row = Section(
        owner_id=user.id,
        project_id=project_row.id,
        title="Host section",
    )
    db_session.add(section_row)
    db_session.flush()
    project = {"id": str(project_row.id)}
    section = {"id": str(section_row.id)}
    before_style = ScheduleStyle.standalone.value

    payload = {
        "schema_version": 1,
        "source_refs": [{"system": "notes", "id": "graft-1"}],
        "schedule_policy": "manual",
        "entities": [
            {
                "key": "t",
                "kind": "task",
                "title": "Grafted task",
                "parent": {"kind": "section", "id": section["id"]},
            }
        ],
    }
    result = client.post(
        "/api/v1/handoffs/apply",
        json={"idempotency_key": str(uuid4()), **payload},
    )
    assert result.status_code == 200, result.text
    after_style = client.get(f"/api/v1/projects/{project['id']}").json()["schedule_style"]
    assert after_style == before_style
    task_id = result.json()["entities"][0]["id"]
    assert client.get(f"/api/v1/tasks/{task_id}").json()["schedule_style"] == "manual"


def test_f1_d_manual_excluded_from_candidates(
    client: TestClient,
    db_session: Session,
) -> None:
    key = uuid4()
    assert (
        client.post(
            "/api/v1/handoffs/apply",
            json={"idempotency_key": str(key), **_handoff_graph()},
        ).status_code
        == 200
    )
    task_row = db_session.query(Task).filter(Task.title == "Describe acceptance").one()
    owner_id = task_row.owner_id
    user = db_session.get(User, owner_id)
    assert user is not None
    user_settings = get_or_provision_user_settings(db_session, user)
    candidates = load_candidates(db_session, owner_id, user_settings)
    titles = {c.task.title for c in candidates}
    assert "Describe acceptance" not in titles
    assert "Implement slice" not in titles


def test_task_dependency_api_cycle(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"title": "Dep project"}).json()
    a = client.post(
        "/api/v1/tasks",
        json={"title": "A", "project_id": project["id"]},
    ).json()
    b = client.post(
        "/api/v1/tasks",
        json={"title": "B", "project_id": project["id"]},
    ).json()
    first = client.post(
        f"/api/v1/tasks/{a['id']}/dependencies",
        json={"blocking_task_id": a["id"], "dependent_task_id": b["id"]},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/v1/tasks/{b['id']}/dependencies",
        json={"blocking_task_id": b["id"], "dependent_task_id": a["id"]},
    )
    assert second.status_code == 422
    assert second.json()["code"] == "DEPENDENCY_CYCLE"

    listed = client.get(f"/api/v1/tasks/{a['id']}/dependencies")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    dep_id = listed.json()[0]["id"]
    deleted = client.delete(f"/api/v1/tasks/{a['id']}/dependencies/{dep_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/tasks/{a['id']}/dependencies").json() == []


def test_inherited_schedule_policy_on_handoff(client: TestClient) -> None:
    payload = _handoff_graph()
    payload["schedule_policy"] = "inherited"
    for entity in payload["entities"]:
        if entity["kind"] == "task":
            entity["schedule_policy"] = "inherited"
    result = client.post(
        "/api/v1/handoffs/apply",
        json={"idempotency_key": str(uuid4()), **payload},
    )
    assert result.status_code == 200, result.text
    for item in result.json()["entities"]:
        if item["kind"] != "task":
            continue
        task = client.get(f"/api/v1/tasks/{item['id']}").json()
        assert task["schedule_style"] is None
