"""V4-D1–D3 regressions: Prefer rank, scoped Must identity, effective readback.

Disposable ``theplan_s1_test`` only. Does not own the V4-D4 removal surface.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Task
from test_s2_v4_assignments import (
    _clips,
    _effective,
    _local,
    _prepare,
    _project,
    _put_new_rule,
    _reject,
    _revision,
    _rule,
    _set_policy,
    _task,
)

_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "033_custom_availability_slug"


@pytest.fixture(autouse=True)
def _disposable_v4_database(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB, (
        f"refusing to run S2-V4 assignment tests against {name!r}; "
        "set DATABASE_URL to disposable theplan_s1_test"
    )
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD, (
        f"disposable database alembic version is {version!r}; "
        f"upgrade {_REQUIRED_DB} to {_REQUIRED_HEAD} before this gate"
    )


def _names(rows: list[dict]) -> set[tuple[str, str]]:
    return {(row["name"], row["source_scope"]) for row in rows}


def test_stored_same_named_must_is_preserved(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 480)
    personal = _set_policy(client, "personal", "13:00", 60)
    _set_policy(client, "general", "09:00", 480)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(client, "project", project["id"], must=[_rule("hours", work["id"])])
    _put_new_rule(client, "task", task["id"], must=[_rule("hours", personal["id"])])

    row = db_session.get(Task, uuid.UUID(task["id"]))
    composed, clips = _clips(db_session, row)
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("project", "hours"),
        ("task", "hours"),
    }
    assert [(item[0].hour, item[1].hour) for item in clips] == [(13, 14)]

    effective = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective").json()
    assert _names(effective["new_rule_assignment"]["must"]) == {
        ("hours", "project"),
        ("hours", "task"),
    }
    assert effective["new_rule_assignment"]["consumes_personal_policy"] is True


def test_effective_read_drops_inherited_waived_must(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    personal = _set_policy(client, "personal", "09:00", 180)
    _set_policy(client, "general", "09:00", 480)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(
        client, "project", project["id"], must=[_rule("office", personal["id"])]
    )
    _put_new_rule(client, "task", task["id"])
    waived = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/waive-named",
        json={
            "expected_revision": _revision(client),
            "target_rule_name": "office",
        },
    )
    assert waived.status_code == 200, waived.text

    _task_row, composed = _effective(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert composed is not None
    assert composed.must_rules == ()

    effective = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective").json()
    assignment = effective["new_rule_assignment"]
    assert assignment["must"] == []
    assert any(
        item["operation"] == "waive_named" and item["target_rule_name"] == "office"
        for item in assignment["exceptions_applied"]
    )
    assert assignment["consumes_personal_policy"] is False
    assert effective["personal_policy_saved"]["placer_active"] is False


def test_personal_flag_follows_rules_that_survive_the_waiver(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 480)
    personal = _set_policy(client, "personal", "16:00", 60)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(client, "project", project["id"], must=[_rule("office", work["id"])])
    _put_new_rule(
        client,
        "task",
        task["id"],
        prefer=[_rule("late", personal["id"])],
    )
    waived = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/waive-named",
        json={
            "expected_revision": _revision(client),
            "target_rule_name": "office",
        },
    )
    assert waived.status_code == 200, waived.text

    effective = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective").json()
    assignment = effective["new_rule_assignment"]
    assert assignment["must"] == []
    assert _names(assignment["prefer"]) == {("late", "task")}
    assert assignment["consumes_personal_policy"] is True
    assert effective["personal_policy_saved"]["placer_active"] is True


def test_effective_may_unions_parent_and_child(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    morning = _set_policy(client, "work", "09:00", 180)
    afternoon = _set_policy(client, "general", "13:00", 180)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(
        client,
        "project",
        project["id"],
        may={"presence": "explicit", "rules": [_rule("am", morning["id"])]},
    )
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "explicit", "rules": [_rule("pm", afternoon["id"])]},
    )

    _task_row, composed = _effective(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert composed is not None
    assert {(entry.rule_id, entry.scope) for entry in composed.may_rules} == {
        ("am", "project"),
        ("pm", "task"),
    }
    hours = {(item[0].hour, item[1].hour) for item in _clips(db_session, db_session.get(Task, uuid.UUID(task["id"])))[1]}
    assert (9, 12) in hours
    assert (13, 16) in hours

    effective = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective").json()
    may = effective["new_rule_assignment"]["may"]
    assert may["presence"] == "explicit"
    assert _names(may["rules"]) == {("am", "project"), ("pm", "task")}


def test_explicit_empty_may_clears_inherited_may_on_effective_read(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    personal = _set_policy(client, "personal", "19:00", 120)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(
        client,
        "project",
        project["id"],
        may={"presence": "explicit", "rules": [_rule("eve", personal["id"])]},
    )
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "explicit", "rules": []},
    )

    effective = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective").json()
    assignment = effective["new_rule_assignment"]
    assert assignment["may"]["presence"] == "explicit"
    assert assignment["may"]["rules"] == []
    assert assignment["consumes_personal_policy"] is False
    _task_row, composed = _effective(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert composed is not None
    assert composed.may_source == "explicit_empty"
    assert composed.may_rules == ()


def test_effective_read_shows_inherited_replacement(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 480)
    personal = _set_policy(client, "personal", "13:00", 60)
    _set_policy(client, "general", "09:00", 480)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(client, "project", project["id"], must=[_rule("office", work["id"])])
    _put_new_rule(client, "task", task["id"])
    replaced = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/replace-named",
        json={
            "expected_revision": _revision(client),
            "target_rule_name": "office",
            "target_rule_kind": "must",
            "replacement_name": "tight",
            "policy_id": personal["id"],
        },
    )
    assert replaced.status_code == 200, replaced.text

    _task_row, composed = _effective(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert composed is not None
    assert {entry.rule_id for entry in composed.must_rules} == {"tight"}
    assert [(item[0].hour, item[1].hour) for item in _clips(db_session, db_session.get(Task, uuid.UUID(task["id"])))[1]] == [
        (13, 14)
    ]

    effective = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective").json()
    must = effective["new_rule_assignment"]["must"]
    assert [row["name"] for row in must] == ["tight"]
    assert must[0]["source_scope"] == "task"
    assert must[0]["origin"] == "replacement"
    assert must[0]["policy_id"] == personal["id"]
    assert effective["new_rule_assignment"]["consumes_personal_policy"] is True


def _post_replace(client: TestClient, task_id: str, **body):
    return client.post(
        f"/api/v1/tasks/{task_id}/scheduling/rules/replace-named",
        json={"expected_revision": _revision(client), **body},
    )


def test_replacement_name_does_not_erase_sibling_must(
    client: TestClient, db_session: Session
) -> None:
    """V4-D2 residual: output name local-hours must not erase the sibling Must."""
    _prepare(client, db_session)
    wide = _set_policy(client, "work", "09:00", 480)
    narrow = _set_policy(client, "personal", "13:00", 60)
    _set_policy(client, "general", "09:00", 480)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(
        client, "project", project["id"], must=[_rule("parent-hours", wide["id"])]
    )
    _put_new_rule(
        client, "task", task["id"], must=[_rule("local-hours", narrow["id"])]
    )

    rev = _revision(client)
    rejected = _post_replace(
        client,
        task["id"],
        target_rule_name="parent-hours",
        target_rule_kind="must",
        replacement_name="local-hours",
        policy_id=wide["id"],
    )
    body = _reject(db_session, rejected, "RULE_NAME_CONFLICT")
    assert rejected.status_code == 409
    assert "local-hours" in body["detail"]
    assert "siblings stay" in body["detail"]
    assert body["replacement_name"] == "local-hours"
    assert body["target_rule_name"] == "parent-hours"
    assert _revision(client) == rev

    local = _local(client, "task", task["id"])
    assert local["exceptions"] == []
    assert [row["name"] for row in local["must"]] == ["local-hours"]

    row = db_session.get(Task, uuid.UUID(task["id"]))
    composed, clips = _clips(db_session, row)
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("project", "parent-hours"),
        ("task", "local-hours"),
    }
    assert [(item[0].hour, item[1].hour) for item in clips] == [(13, 14)]

    fresh = _post_replace(
        client,
        task["id"],
        target_rule_name="parent-hours",
        target_rule_kind="must",
        replacement_name="wide",
        policy_id=wide["id"],
    )
    assert fresh.status_code == 200, fresh.text
    row = db_session.get(Task, uuid.UUID(task["id"]))
    composed, clips = _clips(db_session, row)
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("task", "local-hours"),
        ("task", "wide"),
    }
    assert [(item[0].hour, item[1].hour) for item in clips] == [(13, 14)]


def test_replacement_name_collides_with_other_replace_output(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    wide = _set_policy(client, "work", "09:00", 480)
    _set_policy(client, "general", "09:00", 480)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(
        client,
        "project",
        project["id"],
        must=[
            _rule("parent-hours", wide["id"]),
            _rule("other-hours", wide["id"]),
        ],
    )
    _put_new_rule(client, "task", task["id"])
    first = _post_replace(
        client,
        task["id"],
        target_rule_name="parent-hours",
        target_rule_kind="must",
        replacement_name="shared-name",
        policy_id=wide["id"],
    )
    assert first.status_code == 200, first.text

    rev = _revision(client)
    rejected = _post_replace(
        client,
        task["id"],
        target_rule_name="other-hours",
        target_rule_kind="must",
        replacement_name="shared-name",
        policy_id=wide["id"],
    )
    body = _reject(db_session, rejected, "RULE_NAME_CONFLICT")
    assert "shared-name" in body["detail"]
    assert "parent-hours" in body["detail"]
    assert _revision(client) == rev
    local = _local(client, "task", task["id"])
    assert [row["target_rule_name"] for row in local["exceptions"]] == ["parent-hours"]
    assert local["exceptions"][0]["replacement_name"] == "shared-name"

    row = db_session.get(Task, uuid.UUID(task["id"]))
    composed, _clips_out = _clips(db_session, row)
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("project", "other-hours"),
        ("task", "shared-name"),
    }


def test_same_name_replacement_does_not_clobber_local_must(
    client: TestClient, db_session: Session
) -> None:
    """Inherited and local both named hours; output hours must not erase local."""
    _prepare(client, db_session)
    wide = _set_policy(client, "work", "09:00", 480)
    narrow = _set_policy(client, "personal", "13:00", 60)
    _set_policy(client, "general", "09:00", 480)
    project = _project(client)
    task = _task(client, project_id=project["id"])
    _put_new_rule(client, "project", project["id"], must=[_rule("hours", wide["id"])])
    _put_new_rule(client, "task", task["id"], must=[_rule("hours", narrow["id"])])

    rev = _revision(client)
    rejected = _post_replace(
        client,
        task["id"],
        target_rule_name="hours",
        target_rule_kind="must",
        replacement_name="hours",
        policy_id=wide["id"],
    )
    _reject(db_session, rejected, "RULE_NAME_CONFLICT")
    assert _revision(client) == rev
    assert _local(client, "task", task["id"])["exceptions"] == []
    row = db_session.get(Task, uuid.UUID(task["id"]))
    composed, clips = _clips(db_session, row)
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("project", "hours"),
        ("task", "hours"),
    }
    assert [(item[0].hour, item[1].hour) for item in clips] == [(13, 14)]


def test_inplace_replace_of_local_only_rule_keeps_its_name(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    wide = _set_policy(client, "work", "09:00", 480)
    narrow = _set_policy(client, "personal", "13:00", 60)
    _set_policy(client, "general", "09:00", 480)
    task = _task(client)
    _put_new_rule(client, "task", task["id"], must=[_rule("local-hours", narrow["id"])])
    replaced = _post_replace(
        client,
        task["id"],
        target_rule_name="local-hours",
        target_rule_kind="must",
        replacement_name="local-hours",
        policy_id=wide["id"],
    )
    assert replaced.status_code == 200, replaced.text
    row = db_session.get(Task, uuid.UUID(task["id"]))
    composed, clips = _clips(db_session, row)
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("task", "local-hours"),
    }
    assert [(item[0].hour, item[1].hour) for item in clips] == [(9, 17)]
