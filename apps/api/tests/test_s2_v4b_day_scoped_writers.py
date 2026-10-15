"""S2-V4b day-scoped writers — accept / reject only (A14b storage).

Disposable ``theplan_s1_test`` only. Alembic ``032_scheduling_day_scoped_ops``.
Does not exercise Tesla resolve / fingerprint / placer paths.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import UserSettings
from app.models.scheduling_assignment import SchedulingAssignment
from app.models.scheduling_day_scoped import SchedulingDayScopedOp
from app.services.availability_seed import ensure_default_availability_policies

_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "033_custom_availability_slug"
TUESDAY = date(2026, 10, 13)


@pytest.fixture(autouse=True)
def _disposable_v4b_database(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB, (
        f"refusing to run S2-V4b writer tests against {name!r}; "
        "set DATABASE_URL to disposable theplan_s1_test"
    )
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD, (
        f"disposable database alembic version is {version!r}; "
        f"upgrade {_REQUIRED_DB} to {_REQUIRED_HEAD} before this gate"
    )


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _revision(client: TestClient) -> int:
    response = client.get("/api/v1/settings")
    assert response.status_code == 200, response.text
    return int(response.json()["scheduling_revision"])


def _reject(db: Session, response, code: str) -> dict:
    assert response.status_code in (404, 409, 422), response.text
    body = response.json()
    assert body["code"] == code, body
    db.rollback()
    return body


def _windows(weekday: int, start: str, duration: int) -> list[dict]:
    return [
        {
            "weekday": weekday,
            "start_time": start,
            "duration_minutes": duration,
            "sort_order": 0,
        }
    ]


def _prepare(client: TestClient, db: Session) -> dict[str, dict]:
    owner_id = _owner_id(client)
    ensure_default_availability_policies(db, owner_id)
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    settings.timezone = "UTC"
    db.commit()
    rows = client.get("/api/v1/availability-policies").json()
    return {row["slug"]: row for row in rows}


def _set_policy(client: TestClient, slug: str, start: str, duration: int) -> dict:
    response = client.patch(
        f"/api/v1/availability-policies/{slug}",
        json={"windows": _windows(TUESDAY.weekday(), start, duration)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _task(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={"title": f"T {_uid()}", "estimated_duration_minutes": 60},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _map(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"Map {_uid()}",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _put_new_rule(client: TestClient, task_id: str, policy_id: str) -> dict:
    response = client.put(
        f"/api/v1/tasks/{task_id}/scheduling",
        json={
            "expected_revision": _revision(client),
            "may": {
                "presence": "explicit",
                "rules": [{"name": "day", "policy_id": policy_id}],
            },
            "must": [],
            "prefer": [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_standing_writers_still_reject_temporal_and_context(
    client: TestClient, db_session: Session
) -> None:
    policies = _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    _put_new_rule(client, task["id"], work["id"])
    before_rev = _revision(client)

    temporal = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/add",
        json={
            "expected_revision": before_rev,
            "name": "monday",
            "kind": "may",
            "policy_id": work["id"],
            "weekdays": [0],
        },
    )
    _reject(db_session, temporal, "SCHEDULING_EXCEPTION_FORM_DEFERRED")
    assert temporal.json()["deferred_to"] == "V4b"

    context = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/add",
        json={
            "expected_revision": _revision(client),
            "name": "home",
            "kind": "may",
            "policy_id": work["id"],
            "context": "home",
        },
    )
    _reject(db_session, context, "SCHEDULING_EXCEPTION_FORM_DEFERRED")
    assert context.json()["deferred_to"] == "V7"

    forbidden = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": _revision(client),
            "on_date": "2026-10-13",
            "policy_id": work["id"],
            "ignore_all": True,
        },
    )
    _reject(db_session, forbidden, "SCHEDULING_EXCEPTION_FORBIDDEN")
    assert _revision(client) == before_rev
    assert policies["work"]["id"] == work["id"]


def test_scoped_writer_without_selector_rejects_no_write(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    before_rev = _revision(client)
    response = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": before_rev,
            "policy_id": work["id"],
        },
    )
    _reject(db_session, response, "SCHEDULING_DAY_SELECTOR_REQUIRED")
    assert _revision(client) == before_rev
    assert (
        db_session.query(SchedulingDayScopedOp)
        .filter(SchedulingDayScopedOp.scope_id == uuid.UUID(task["id"]))
        .count()
        == 0
    )


def test_day_change_and_only_allow_accept_and_bump_revision(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    before = _revision(client)

    change = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": before,
            "on_date": "2026-10-13",
            "policy_id": work["id"],
            "expires_at": "2026-10-20T01:00:00+00:00",
        },
    )
    assert change.status_code == 200, change.text
    body = change.json()
    assert body["scheduling_revision"] == before + 1
    assert body["op"]["op_kind"] == "change_selected"
    assert body["op"]["selector_kind"] == "one_date"
    assert body["op"]["civil_on_date"] == "2026-10-13"
    assert body["op"]["expires_at"] is not None
    assert body["op"]["payload_kind"] == "policy"
    op_id = body["op"]["id"]

    only = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/only-allow",
        json={
            "expected_revision": _revision(client),
            "weekdays": [0, 2],
            "empty_set": True,
        },
    )
    assert only.status_code == 200, only.text
    assert only.json()["op"]["op_kind"] == "only_allow"
    assert only.json()["op"]["payload_kind"] == "empty"
    assert only.json()["op"]["civil_weekdays"] == [0, 2]

    listed = client.get(f"/api/v1/tasks/{task['id']}/scheduling/day-scoped")
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 2

    removed = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/remove-named-scoped",
        json={"expected_revision": _revision(client), "op_id": op_id},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["removed_op_id"] == op_id
    assert len(client.get(f"/api/v1/tasks/{task['id']}/scheduling/day-scoped").json()) == 1


def test_empty_vs_omit_and_civil_date_expiry_reject(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    before = _revision(client)

    omit = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": before,
            "on_date": "2026-10-13",
        },
    )
    _reject(db_session, omit, "SCHEDULING_DAY_PAYLOAD_INVALID")

    civil_expiry = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": before,
            "on_date": "2026-10-13",
            "policy_id": work["id"],
            "expires_on": "2026-10-20",
        },
    )
    _reject(db_session, civil_expiry, "SCHEDULING_DAY_EXPIRY_INVALID")
    assert _revision(client) == before


def test_overlap_replacements_require_which_replaces_which(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)

    first = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": _revision(client),
            "date_range": {"start": "2026-10-13", "end": "2026-10-15"},
            "policy_id": work["id"],
        },
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["op"]["id"]
    before = _revision(client)

    missing = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": before,
            "on_date": "2026-10-14",
            "policy_id": work["id"],
        },
    )
    _reject(db_session, missing, "SCHEDULING_DAY_OVERLAP_UNRESOLVED")
    assert _revision(client) == before

    ok = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": before,
            "on_date": "2026-10-14",
            "policy_id": work["id"],
            "replaces_op_ids": [first_id],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["op"]["replaces_op_ids"] == [first_id]


def test_addition_over_replacement_requires_addition_survives(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    _put_new_rule(client, task["id"], work["id"])

    change = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": _revision(client),
            "on_date": "2026-10-13",
            "policy_id": work["id"],
        },
    )
    assert change.status_code == 200, change.text
    before = _revision(client)

    only_missing = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/only-allow",
        json={
            "expected_revision": before,
            "on_date": "2026-10-13",
            "policy_id": work["id"],
        },
    )
    _reject(db_session, only_missing, "SCHEDULING_DAY_OVERLAP_UNRESOLVED")
    assert _revision(client) == before

    ok = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/only-allow",
        json={
            "expected_revision": before,
            "on_date": "2026-10-13",
            "policy_id": work["id"],
            "addition_survives": True,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["op"]["addition_survives"] is True


def test_named_scoped_on_legacy_rejects_no_conversion(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    window = _map(client)
    task = _task(client)
    patched = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": window["id"]},
    )
    assert patched.status_code == 200, patched.text
    before = _revision(client)

    response = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/add-scoped",
        json={
            "expected_revision": before,
            "name": "monday",
            "kind": "may",
            "policy_id": work["id"],
            "on_date": "2026-10-13",
        },
    )
    _reject(db_session, response, "NAMED_RULE_REQUIRES_NEW_RULE_FAMILY")
    assert _revision(client) == before
    assert (
        db_session.query(SchedulingDayScopedOp)
        .filter(SchedulingDayScopedOp.scope_id == uuid.UUID(task["id"]))
        .count()
        == 0
    )


def test_clear_scoped_does_not_delete_standing(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    _put_new_rule(client, task["id"], work["id"])
    before_count = (
        db_session.query(SchedulingAssignment)
        .filter(SchedulingAssignment.scope_id == uuid.UUID(task["id"]))
        .count()
    )
    assert before_count == 1

    cleared = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/clear-scoped",
        json={
            "expected_revision": _revision(client),
            "weekdays": [0],
        },
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["cleared_scoped"] is True
    assert cleared.json()["op"]["op_kind"] == "clear_scoped"

    db_session.expire_all()
    assert (
        db_session.query(SchedulingAssignment)
        .filter(SchedulingAssignment.scope_id == uuid.UUID(task["id"]))
        .count()
        == 1
    )
    local = client.get(f"/api/v1/tasks/{task['id']}/scheduling")
    assert local.status_code == 200
    assert local.json()["family"] == "new_rule"


def test_family_replace_scoped_and_revert_scoped(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    _put_new_rule(client, task["id"], work["id"])

    replaced = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/family-replace-scoped",
        json={
            "expected_revision": _revision(client),
            "on_date": "2026-10-13",
            "target_family": "none",
        },
    )
    assert replaced.status_code == 200, replaced.text
    replacement_id = replaced.json()["replacement_id"]
    assert replacement_id is not None
    # Standing assignment still present (overlay only).
    local = client.get(f"/api/v1/tasks/{task['id']}/scheduling")
    assert local.json()["family"] == "new_rule"

    reverted = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/revert-scoped",
        json={
            "expected_revision": _revision(client),
            "replacement_id": replacement_id,
        },
    )
    assert reverted.status_code == 200, reverted.text
    assert reverted.json()["restored_replacement_id"] == replacement_id
    assert reverted.json()["family"] == "new_rule"
    assert (
        db_session.query(SchedulingDayScopedOp)
        .filter(SchedulingDayScopedOp.id == uuid.UUID(replacement_id))
        .count()
        == 0
    )


def test_policy_backed_family_replace_scoped_serializes_and_resolves(
    client: TestClient, db_session: Session
) -> None:
    """V4b-D1: policy_id UUID in rules must survive JSONB flush and resolve."""
    from sqlalchemy.orm import joinedload

    from app.models import AvailabilityPolicy, Task
    from app.scheduler.day_scoped import (
        DayScopedOp,
        declaration_from_row,
        load_day_scoped_declarations,
    )

    _prepare(client, db_session)
    work = _set_policy(client, "work", "15:00", 60)
    task = _task(client)

    replaced = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/family-replace-scoped",
        json={
            "expected_revision": _revision(client),
            "on_date": "2026-10-13",
            "target_family": "new_rule",
            "may": {
                "presence": "explicit",
                "rules": [{"name": "scoped-day", "policy_id": work["id"]}],
            },
            "must": [],
            "prefer": [],
        },
    )
    assert replaced.status_code == 200, replaced.text
    replacement_id = uuid.UUID(replaced.json()["replacement_id"])

    db_session.expire_all()
    row = db_session.get(SchedulingDayScopedOp, replacement_id)
    assert row is not None
    payload = row.family_payload
    assert payload is not None
    assert payload["target_family"] == "new_rule"
    assert payload["may_presence"] == "explicit"
    assert len(payload["rules"]) == 1
    stored_policy_id = payload["rules"][0]["policy_id"]
    assert isinstance(stored_policy_id, str)
    assert stored_policy_id == work["id"]

    policies = {
        policy.id: policy
        for policy in (
            db_session.query(AvailabilityPolicy)
            .options(joinedload(AvailabilityPolicy.windows))
            .all()
        )
    }
    declaration = declaration_from_row(row, policies)
    assert declaration.operation == DayScopedOp.FAMILY_REPLACE_SCOPED
    layer = declaration.replacement_layer
    assert layer is not None
    assert layer.may_rules
    assert layer.may_rules[0].rule_id == "scoped-day"
    assert layer.may_rules[0].windows
    assert layer.may_rules[0].windows[0].start_time.hour == 15
    assert layer.may_rules[0].windows[0].duration_minutes == 60

    owner_id = _owner_id(client)
    task_row = db_session.get(Task, uuid.UUID(task["id"]))
    assert task_row is not None
    loaded = load_day_scoped_declarations(db_session, owner_id, [task_row])
    assert uuid.UUID(task["id"]) in loaded or task_row.id in loaded
    task_decls = loaded.get(task_row.id) or ()
    assert any(item.declaration_id == str(replacement_id) for item in task_decls)
    matched = next(
        item for item in task_decls if item.declaration_id == str(replacement_id)
    )
    assert matched.replacement_layer is not None
    assert matched.replacement_layer.may_rules[0].windows


def test_named_scoped_ops_accept(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    _put_new_rule(client, task["id"], work["id"])

    added = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/add-scoped",
        json={
            "expected_revision": _revision(client),
            "name": "monday-may",
            "kind": "may",
            "policy_id": work["id"],
            "selector": {"kind": "weekday_standing", "weekdays": [0]},
        },
    )
    assert added.status_code == 200, added.text
    assert added.json()["op"]["rule_name"] == "monday-may"

    replaced = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/replace-named-scoped",
        json={
            "expected_revision": _revision(client),
            "target_rule_name": "day",
            "target_rule_kind": "may",
            "replacement_name": "day-alt",
            "policy_id": work["id"],
            "date_range": {"start": "2026-10-13", "end": "2026-10-14"},
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["op"]["op_kind"] == "replace_named_scoped"

    waived = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/waive-named-scoped",
        json={
            "expected_revision": _revision(client),
            "target_rule_name": "must-x",
            "on_date": "2026-10-13",
        },
    )
    assert waived.status_code == 200, waived.text
    assert waived.json()["op"]["target_rule_kind"] == "must"


def test_context_on_scoped_writer_stays_v7_reject(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    before = _revision(client)
    response = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/day/change-selected",
        json={
            "expected_revision": before,
            "on_date": "2026-10-13",
            "policy_id": work["id"],
            "context_id": str(uuid.uuid4()),
        },
    )
    _reject(db_session, response, "SCHEDULING_EXCEPTION_FORM_DEFERRED")
    assert response.json()["deferred_to"] == "V7"
    assert _revision(client) == before
