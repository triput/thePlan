"""S2-V4 assignment writers + resolver seam (A12–A14, A12a–A12f).

Disposable ``theplan_s1_test`` only. Alembic head ``033_custom_availability_slug``
(additive on ``031_scheduling_assignments``).
Rejected writes must not commit; the shared test session is rolled back after
each 4xx so a flush-before-raise cannot leak into the next assertion.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.models import (
    AvailabilityPolicy,
    Epic,
    FocusWindow,
    Project,
    Task,
    User,
    UserSettings,
)
from app.models.enums import (
    AvailabilityPolicySlug,
    ScheduleStatus,
    TaskWorkflowState,
)
from app.models.scheduling_assignment import SchedulingAssignment
from app.scheduler.availability_materializer import load_owner_policy_windows
from app.scheduler.collect import collect_inputs
from app.scheduler.composition import composition_search_windows
from app.scheduler.composition_resolver import load_effective_compositions
from app.scheduler.input_fingerprint import STALE_COMPOSITION
from app.scheduler.outcomes import live_snapshots_by_task
from app.scheduler.preview_inputs import fingerprint_collected_inputs
from app.services.availability_seed import ensure_default_availability_policies
from app.services.schedule_preview_staleness import preview_stale_categories

UTC = timezone.utc
TZ = ZoneInfo("UTC")
TUESDAY = date(2026, 10, 13)
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


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _revision(client: TestClient) -> int:
    response = client.get("/api/v1/settings")
    assert response.status_code == 200, response.text
    return int(response.json()["scheduling_revision"])


def _reject(db: Session, response, code: str) -> dict:
    assert response.status_code in (409, 422), response.text
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


def _map(client: TestClient, name: str | None = None) -> dict:
    response = client.post(
        "/api/v1/focus-windows",
        json={
            "name": name or f"Map {_uid()}",
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


def _task(client: TestClient, **extra) -> dict:
    payload = {"title": f"T {_uid()}", "estimated_duration_minutes": 60}
    payload.update(extra)
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _epic(client: TestClient) -> dict:
    response = client.post("/api/v1/epics", json={"title": f"E {_uid()}"})
    assert response.status_code == 201, response.text
    return response.json()


def _project(client: TestClient, epic_id: str | None = None) -> dict:
    payload: dict = {"title": f"P {_uid()}"}
    if epic_id is not None:
        payload["epic_id"] = epic_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _local(client: TestClient, scope: str, scope_id: str) -> dict:
    plural = {"task": "tasks", "project": "projects", "epic": "epics"}[scope]
    response = client.get(f"/api/v1/{plural}/{scope_id}/scheduling")
    assert response.status_code == 200, response.text
    return response.json()


def _rule(name: str, policy_id: str, *, empty_set: bool = False) -> dict:
    if empty_set:
        return {"name": name, "empty_set": True}
    return {"name": name, "policy_id": policy_id}


def _put_new_rule(
    client: TestClient,
    scope: str,
    scope_id: str,
    *,
    may: dict | None = None,
    must: list | None = None,
    prefer: list | None = None,
    extra: dict | None = None,
) -> dict:
    plural = {"task": "tasks", "project": "projects", "epic": "epics"}[scope]
    body: dict = {
        "expected_revision": _revision(client),
        "may": may if may is not None else {"presence": "omit", "rules": []},
        "must": must or [],
        "prefer": prefer or [],
    }
    if extra:
        body.update(extra)
    response = client.put(f"/api/v1/{plural}/{scope_id}/scheduling", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _replace(
    client: TestClient,
    scope: str,
    scope_id: str,
    body: dict,
):
    plural = {"task": "tasks", "project": "projects", "epic": "epics"}[scope]
    payload = {"expected_revision": _revision(client), **body}
    return client.post(
        f"/api/v1/{plural}/{scope_id}/scheduling/assignment/family-replace",
        json=payload,
    )


def _effective(db: Session, task: Task):
    project = db.get(Project, task.project_id) if task.project_id else None
    epic = db.get(Epic, project.epic_id) if project is not None and project.epic_id else None
    projects = {project.id: project} if project is not None else {}
    epics = {epic.id: epic} if epic is not None else {}
    db.expire_all()
    task = db.get(Task, task.id)
    assert task is not None
    found = load_effective_compositions(db, task.owner_id, [task], projects, epics)
    return task, found.get(task.id)


def _clips(db: Session, task: Task):
    task, composed = _effective(db, task)
    assert composed is not None
    _working, general = load_owner_policy_windows(db, task.owner_id)
    return composed, composition_search_windows(TUESDAY, TZ, composed, general)


def _hours(clips) -> list[tuple[int, int, str]]:
    return [(item[0].hour, item[0].minute, item[2]) for item in clips]


# --- A12 / A13 / A14 through stored rows ------------------------------------


def test_a12_may_union_must_intersect_prefer_rank_only(
    client: TestClient, db_session: Session
) -> None:
    policies = _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 180)
    general = _set_policy(client, "general", "11:00", 180)
    personal = _set_policy(client, "personal", "13:00", 60)
    task = _task(client)
    written = _put_new_rule(
        client,
        "task",
        task["id"],
        may={
            "presence": "explicit",
            "rules": [
                _rule("am", work["id"]),
                _rule("mid", general["id"]),
            ],
        },
        must=[_rule("need", work["id"])],
        prefer=[_rule("late", personal["id"])],
    )
    assert written["family"] == "new_rule"
    composed, clips = _clips(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert composed.may_source == "explicit"
    # May 09–12 ∪ 11–14, then Must 09–12 → 09–12. Prefer 13–14 does not extend it.
    assert [(item[0].hour, item[1].hour) for item in clips] == [(9, 12)]
    assert all(item[2] == "eligible" for item in clips)
    assert policies["work"]["id"] == work["id"]


def test_a13_prefer_without_may_does_not_create_hours(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    _set_policy(client, "general", "09:00", 480)
    personal = _set_policy(client, "personal", "19:00", 120)
    task = _task(client)
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "omit", "rules": []},
        prefer=[_rule("eve", personal["id"])],
    )
    composed, clips = _clips(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert composed.may_source == "general"
    assert clips
    assert all(item[0].hour < 17 for item in clips)
    assert not any(item[0].hour >= 19 for item in clips)


def test_a14_parent_must_survives_child_prefer(
    client: TestClient, db_session: Session
) -> None:
    """Parent evening May + narrower Must; child Prefer does not waive the Must."""
    _prepare(client, db_session)
    evening = _set_policy(client, "work", "19:00", 120)
    narrow = _set_policy(client, "general", "19:00", 90)
    prefer = _set_policy(client, "personal", "20:00", 60)
    epic = _epic(client)
    project = _project(client, epic["id"])
    task = _task(client, project_id=project["id"])
    _put_new_rule(
        client,
        "epic",
        epic["id"],
        may={"presence": "explicit", "rules": [_rule("eve", evening["id"])]},
        must=[_rule("narrow", narrow["id"])],
    )
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "omit", "rules": []},
        prefer=[_rule("later", prefer["id"])],
    )
    row = db_session.get(Task, uuid.UUID(task["id"]))
    composed, clips = _clips(db_session, row)
    must_names = [entry.rule_id for entry in composed.must_rules]
    assert "narrow" in must_names
    assert composed.may_source == "explicit"
    # May 19:00–21:00 ∩ Must 19:00–20:30. Prefer 20:00–21:00 ranks only the overlap.
    assert clips
    assert min(item[0] for item in clips) == datetime(2026, 10, 13, 19, 0, tzinfo=UTC)
    assert max(item[1] for item in clips) == datetime(2026, 10, 13, 20, 30, tzinfo=UTC)
    assert any(item[2] == "prefer" for item in clips)
    assert all(item[1] <= datetime(2026, 10, 13, 20, 30, tzinfo=UTC) for item in clips)


# --- A12a collision / replace / revert payload ------------------------------


def test_a12a_collision_rejects_and_replace_keeps_revert_payload(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    window = _map(client)
    task = _task(client)
    patched = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": window["id"]},
    )
    assert patched.status_code == 200, patched.text
    rev = _revision(client)
    collided = client.put(
        f"/api/v1/tasks/{task['id']}/scheduling",
        json={
            "expected_revision": rev,
            "may": {"presence": "omit", "rules": []},
            "must": [],
            "prefer": [],
        },
    )
    _reject(db_session, collided, "SCHEDULING_FAMILY_COLLISION")
    assert _revision(client) == rev
    local = _local(client, "task", task["id"])
    assert local["family"] == "legacy"
    assert local["preferred_time_window_id"] == window["id"]
    assert (
        db_session.query(SchedulingAssignment)
        .filter(SchedulingAssignment.scope_id == uuid.UUID(task["id"]))
        .count()
        == 0
    )

    work = _set_policy(client, "work", "09:00", 480)
    replaced = _replace(
        client,
        "task",
        task["id"],
        {
            "target_family": "new_rule",
            "may": {"presence": "explicit", "rules": [_rule("day", work["id"])]},
        },
    )
    assert replaced.status_code == 200, replaced.text
    body = replaced.json()
    assert body["family"] == "new_rule"
    assert body["replacement_id"]
    assert body["assignment"]["revert_replacement_id"] == body["replacement_id"]
    assert body["assignment"]["preferred_time_window_id"] is None
    assert body["assignment"]["family"] == "new_rule"

    # Legacy writer collides the other way and does not attach the map.
    other_map = _map(client, name=f"other-{_uid()}")
    rev = _revision(client)
    legacy_write = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": other_map["id"]},
    )
    _reject(db_session, legacy_write, "SCHEDULING_FAMILY_COLLISION")
    assert _revision(client) == rev
    again = _local(client, "task", task["id"])
    assert again["family"] == "new_rule"
    assert again["preferred_time_window_id"] is None
    assert again["revert_replacement_id"] == body["replacement_id"]


# --- A12b clear vs revert, stale, deleted ref -------------------------------


def test_a12b_clear_does_not_restore_and_revert_ignores_ancestor_hours(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    window = _map(client)
    epic = _epic(client)
    project = _project(client, epic["id"])
    task = _task(client, project_id=project["id"])
    client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": window["id"]},
    )
    work = _set_policy(client, "work", "09:00", 120)
    replaced = _replace(
        client,
        "task",
        task["id"],
        {
            "target_family": "new_rule",
            "may": {"presence": "explicit", "rules": [_rule("day", work["id"])]},
        },
    )
    assert replaced.status_code == 200, replaced.text
    replacement_id = replaced.json()["replacement_id"]

    ancestor = _put_new_rule(
        client,
        "epic",
        epic["id"],
        may={"presence": "explicit", "rules": [_rule("parent", work["id"])]},
        must=[_rule("stay", work["id"])],
    )
    shifted = _set_policy(client, "general", "15:00", 60)
    assert shifted["windows"][0]["start_time"].startswith("15:00")

    cleared = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/clear",
        json={"expected_revision": _revision(client)},
    )
    assert cleared.status_code == 200, cleared.text
    clear_body = cleared.json()
    assert clear_body["family"] == "none"
    assert clear_body["cleared"] is True
    assert clear_body["assignment"]["family"] == "none"
    assert clear_body["assignment"]["may"] is None
    assert clear_body["assignment"]["preferred_time_window_id"] is None
    assert clear_body["assignment"]["revert_replacement_id"] == replacement_id
    epic_local = _local(client, "epic", epic["id"])
    assert epic_local["family"] == "new_rule"
    assert [row["name"] for row in epic_local["must"]] == ["stay"]
    general = client.get("/api/v1/availability-policies/general").json()
    assert general["windows"][0]["start_time"].startswith("15:00")

    stale = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/revert",
        json={
            "expected_revision": ancestor["scheduling_revision"],
            "replacement_id": replacement_id,
        },
    )
    _reject(db_session, stale, "SCHEDULING_REVISION_CONFLICT")
    assert _local(client, "task", task["id"])["family"] == "none"

    mismatched = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/revert",
        json={
            "expected_revision": _revision(client),
            "replacement_id": str(uuid.uuid4()),
        },
    )
    _reject(db_session, mismatched, "SCHEDULING_REVERT_MISMATCH")
    assert _local(client, "task", task["id"])["family"] == "none"

    restored = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/revert",
        json={
            "expected_revision": _revision(client),
            "replacement_id": replacement_id,
        },
    )
    assert restored.status_code == 200, restored.text
    restored_body = restored.json()
    assert restored_body["family"] == "legacy"
    assert restored_body["assignment"]["preferred_time_window_id"] == window["id"]
    assert restored_body["assignment"]["revert_replacement_id"] is None
    epic_after = _local(client, "epic", epic["id"])
    assert [row["name"] for row in epic_after["must"]] == ["stay"]
    general_after = client.get("/api/v1/availability-policies/general").json()
    assert general_after["windows"][0]["start_time"].startswith("15:00")
    assert ancestor["scheduling_revision"] < restored_body["scheduling_revision"]


def test_a12b_deleted_map_and_policy_revert_reject(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    window = _map(client)
    task = _task(client)
    client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": window["id"]},
    )
    work = _set_policy(client, "work", "09:00", 60)
    to_new = _replace(
        client,
        "task",
        task["id"],
        {
            "target_family": "new_rule",
            "may": {"presence": "explicit", "rules": [_rule("day", work["id"])]},
        },
    )
    assert to_new.status_code == 200, to_new.text
    replacement_id = to_new.json()["replacement_id"]
    deleted = client.delete(f"/api/v1/focus-windows/{window['id']}")
    assert deleted.status_code == 204, deleted.text
    rejected = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/revert",
        json={
            "expected_revision": _revision(client),
            "replacement_id": replacement_id,
        },
    )
    body = _reject(db_session, rejected, "SCHEDULING_REVERT_UNUSABLE_PRIOR")
    assert "repair" in body
    assert _local(client, "task", task["id"])["family"] == "new_rule"

    # Prior new-rule payload that names a removed policy also rejects.
    personal = client.get("/api/v1/availability-policies/personal").json()
    second = _task(client)
    to_personal = _replace(
        client,
        "task",
        second["id"],
        {
            "target_family": "new_rule",
            "may": {"presence": "explicit", "rules": [_rule("mine", personal["id"])]},
        },
    )
    assert to_personal.status_code == 200, to_personal.text
    other_map = _map(client, name=f"hold-{_uid()}")
    to_legacy = _replace(
        client,
        "task",
        second["id"],
        {"target_family": "legacy", "preferred_time_window_id": other_map["id"]},
    )
    assert to_legacy.status_code == 200, to_legacy.text
    policy_row = db_session.get(AvailabilityPolicy, uuid.UUID(personal["id"]))
    assert policy_row is not None
    db_session.delete(policy_row)
    db_session.commit()
    policy_reject = client.post(
        f"/api/v1/tasks/{second['id']}/scheduling/assignment/revert",
        json={
            "expected_revision": _revision(client),
            "replacement_id": to_legacy.json()["replacement_id"],
        },
    )
    _reject(db_session, policy_reject, "SCHEDULING_REVERT_UNUSABLE_PRIOR")
    assert _local(client, "task", second["id"])["family"] == "legacy"
    assert _local(client, "task", second["id"])["preferred_time_window_id"] == other_map["id"]


def test_a12b_revert_without_payload_rejects(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    task = _task(client)
    rev = _revision(client)
    missing = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/revert",
        json={"expected_revision": rev, "replacement_id": str(uuid.uuid4())},
    )
    _reject(db_session, missing, "SCHEDULING_REVERT_NOT_AVAILABLE")
    assert _revision(client) == rev
    assert _local(client, "task", task["id"])["family"] == "none"


# --- A12c cross-family both directions --------------------------------------


def test_a12c_cross_family_precedence_both_directions(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    evening = _set_policy(client, "work", "19:00", 120)
    must = _set_policy(client, "general", "19:00", 60)
    legacy_epic = _epic(client)
    legacy_map = _map(client, name=f"epic-map-{_uid()}")
    client.patch(
        f"/api/v1/epics/{legacy_epic['id']}",
        json={"preferred_time_window_id": legacy_map["id"]},
    )
    project = _project(client, legacy_epic["id"])
    child_new = _task(client, project_id=project["id"])
    _put_new_rule(
        client,
        "task",
        child_new["id"],
        may={"presence": "explicit", "rules": [_rule("eve", evening["id"])]},
    )
    row = db_session.get(Task, uuid.UUID(child_new["id"]))
    composed, clips = _clips(db_session, row)
    assert composed.family.value == "new_rule"
    assert [item[0].hour for item in clips] == [19]
    effective = client.get(f"/api/v1/tasks/{child_new['id']}/scheduling/effective").json()
    assert effective["new_rule_assignment"]["family"] == "new_rule"
    assert effective["time_map"]["placer_active"] is False

    new_epic = _epic(client)
    _put_new_rule(
        client,
        "epic",
        new_epic["id"],
        may={"presence": "explicit", "rules": [_rule("eve", evening["id"])]},
        must=[_rule("narrow", must["id"])],
    )
    project2 = _project(client, new_epic["id"])
    child_legacy = _task(client, project_id=project2["id"])
    child_map = _map(client, name=f"child-map-{_uid()}")
    client.patch(
        f"/api/v1/tasks/{child_legacy['id']}",
        json={"preferred_time_window_id": child_map["id"]},
    )
    legacy_row = db_session.get(Task, uuid.UUID(child_legacy["id"]))
    legacy_composed, legacy_clips = _clips(db_session, legacy_row)
    assert legacy_composed.family.value == "legacy"
    assert legacy_composed.must_rules == ()
    assert legacy_clips == []
    legacy_effective = client.get(
        f"/api/v1/tasks/{child_legacy['id']}/scheduling/effective"
    ).json()
    assert legacy_effective["new_rule_assignment"]["family"] == "legacy"
    assert legacy_effective["new_rule_assignment"]["must"] == []
    assert legacy_effective["legacy_time_map_id"] == child_map["id"]
    assert legacy_effective["time_map"]["placer_active"] is True


# --- A12d absent / empty / distinct shapes ----------------------------------


def test_a12d_omit_clear_and_explicit_empty_are_distinct(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 180)
    general = _set_policy(client, "general", "09:00", 480)
    omit_task = _task(client)
    omitted = _put_new_rule(
        client,
        "task",
        omit_task["id"],
        may={"presence": "omit", "rules": []},
        must=[_rule("need", work["id"])],
    )
    assert omitted["assignment"]["may"]["presence"] == "omit"
    assert omitted["assignment"]["may"]["rules"] == []
    assert omitted["assignment"]["family"] == "new_rule"
    composed, clips = _clips(db_session, db_session.get(Task, uuid.UUID(omit_task["id"])))
    assert composed.may_source == "general"
    assert clips
    assert all(item[1] <= datetime(2026, 10, 13, 12, 0, tzinfo=UTC) for item in clips)

    empty_may = _task(client)
    emptied = _put_new_rule(
        client,
        "task",
        empty_may["id"],
        may={"presence": "explicit", "rules": []},
        prefer=[_rule("eve", general["id"])],
    )
    assert emptied["assignment"]["may"]["presence"] == "explicit"
    assert emptied["assignment"]["may"]["rules"] == []
    assert emptied["assignment"]["may"] != omitted["assignment"]["may"]
    empty_composed, empty_clips = _clips(
        db_session, db_session.get(Task, uuid.UUID(empty_may["id"]))
    )
    assert empty_composed.may_source == "explicit_empty"
    assert empty_clips == []

    empty_must = _task(client)
    _put_new_rule(
        client,
        "task",
        empty_must["id"],
        may={"presence": "explicit", "rules": [_rule("day", work["id"])]},
        must=[_rule("none", work["id"], empty_set=True)],
    )
    must_composed, must_clips = _clips(
        db_session, db_session.get(Task, uuid.UUID(empty_must["id"]))
    )
    assert must_composed.must_blocks_all is True
    assert must_clips == []

    cleared = client.post(
        f"/api/v1/tasks/{omit_task['id']}/scheduling/assignment/clear",
        json={"expected_revision": _revision(client)},
    )
    assert cleared.status_code == 200, cleared.text
    cleared_assignment = cleared.json()["assignment"]
    assert cleared_assignment["family"] == "none"
    assert cleared_assignment["may"] is None
    assert cleared_assignment["must"] == []
    assert cleared_assignment != omitted["assignment"]
    assert cleared_assignment["may"] != emptied["assignment"]["may"]


def test_a12d_omit_cannot_smuggle_may_rules(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    rev = _revision(client)
    response = client.put(
        f"/api/v1/tasks/{task['id']}/scheduling",
        json={
            "expected_revision": rev,
            "may": {"presence": "omit", "rules": [_rule("nope", work["id"])]},
        },
    )
    assert response.status_code == 422, response.text
    db_session.rollback()
    assert _revision(client) == rev
    assert _local(client, "task", task["id"])["family"] == "none"


# --- A12e personal eligibility + cross-owner --------------------------------


def test_a12e_personal_is_per_assignment_and_foreign_refs_reject(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    _set_policy(client, "work", "09:00", 480)
    personal = _set_policy(client, "personal", "19:00", 120)
    catalog = client.get("/api/v1/availability-policies/personal").json()
    assert catalog["scheduling_effective"] is False

    plain = _task(client)
    plain_effective = client.get(f"/api/v1/tasks/{plain['id']}/scheduling/effective").json()
    assert plain_effective["personal_policy_saved"]["placer_active"] is False
    assert plain_effective["new_rule_assignment"]["consumes_personal_policy"] is False
    assert plain_effective["new_rule_assignment"]["family"] == "none"

    consuming = _task(client)
    _put_new_rule(
        client,
        "task",
        consuming["id"],
        may={"presence": "explicit", "rules": [_rule("eve", personal["id"])]},
    )
    consumed = client.get(f"/api/v1/tasks/{consuming['id']}/scheduling/effective").json()
    assert consumed["personal_policy_saved"]["placer_active"] is True
    assert consumed["new_rule_assignment"]["consumes_personal_policy"] is True
    assert consumed["working_policy_saved"]["placer_active"] is True
    _composed, clips = _clips(db_session, db_session.get(Task, uuid.UUID(consuming["id"])))
    assert [item[0].hour for item in clips] == [19]

    owner_id = _owner_id(client)
    other = User(
        email=f"other-{_uid()}@example.com",
        username=f"other{_uid()}",
        display_name="Other",
    )
    db_session.add(other)
    db_session.flush()
    foreign_policy = AvailabilityPolicy(
        owner_id=other.id,
        slug=AvailabilityPolicySlug.personal.value,
        name="Foreign personal",
        sort_order=0,
    )
    foreign_window = FocusWindow(owner_id=other.id, name="Foreign map", strict_mode=False)
    foreign_task = Task(
        owner_id=other.id,
        title="not yours",
        estimated_duration_minutes=30,
        remaining_minutes=30,
        worked_minutes=0,
        status=ScheduleStatus.unscheduled,
        is_completed=False,
        workflow_state=TaskWorkflowState.ready,
    )
    db_session.add_all([foreign_policy, foreign_window, foreign_task])
    db_session.commit()
    assert other.id != owner_id

    rev = _revision(client)
    cross_policy = client.put(
        f"/api/v1/tasks/{consuming['id']}/scheduling",
        json={
            "expected_revision": rev,
            "may": {
                "presence": "explicit",
                "rules": [_rule("stolen", str(foreign_policy.id))],
            },
        },
    )
    _reject(db_session, cross_policy, "AVAILABILITY_POLICY_NOT_FOUND")
    assert _revision(client) == rev
    still = _local(client, "task", consuming["id"])
    assert still["may"]["rules"][0]["policy_id"] == personal["id"]

    rev = _revision(client)
    cross_map = _replace(
        client,
        "task",
        plain["id"],
        {"target_family": "legacy", "preferred_time_window_id": str(foreign_window.id)},
    )
    _reject(db_session, cross_map, "FOCUS_WINDOW_NOT_FOUND")
    assert _revision(client) == rev
    assert _local(client, "task", plain["id"])["family"] == "none"

    hidden = client.get(f"/api/v1/tasks/{foreign_task.id}/scheduling")
    assert hidden.status_code == 404, hidden.text
    assert hidden.json()["code"] == "NOT_FOUND"
    db_session.rollback()


# --- A12f snapshot consistency + preview stale ------------------------------


def _capture(db: Session, owner_id: uuid.UUID):
    db.expire_all()
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    inputs = collect_inputs(db, owner_id, datetime(2026, 10, 13, 12, 0, tzinfo=UTC))
    stored, _digest = fingerprint_collected_inputs(inputs)
    return settings, inputs, stored, int(settings.scheduling_revision)


def test_a12f_collected_snapshot_matches_live_and_preview_stales(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    day = _set_policy(client, "work", "09:00", 480)
    prefer = _set_policy(client, "personal", "16:00", 60)
    epic = _epic(client)
    project = _project(client, epic["id"])
    task = _task(client, project_id=project["id"])
    _put_new_rule(
        client,
        "epic",
        epic["id"],
        may={"presence": "explicit", "rules": [_rule("day", day["id"])]},
        must=[_rule("am", day["id"])],
    )
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "omit", "rules": []},
        prefer=[_rule("late", prefer["id"])],
    )
    owner_id = _owner_id(client)
    task_row = db_session.get(Task, uuid.UUID(task["id"]))
    assert task_row is not None
    _task_row, composed = _effective(db_session, task_row)
    assert composed is not None
    from app.scheduler.composition import composition_fingerprint

    fingerprint = composition_fingerprint(composed)
    _settings, inputs, stored, captured_rev = _capture(db_session, owner_id)
    live = live_snapshots_by_task(db_session, [db_session.get(Task, uuid.UUID(task["id"]))])
    live_composition = live[uuid.UUID(task["id"])]["composition"]
    collected_composition = inputs.input_snapshots[uuid.UUID(task["id"])]["composition"]
    stored_composition = stored["task_snapshots"][task["id"]]["composition"]
    assert collected_composition == live_composition == stored_composition == fingerprint
    assert fingerprint["family"] == "new_rule"

    added = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/add",
        json={
            "expected_revision": _revision(client),
            "name": "later",
            "kind": "prefer",
            "policy_id": prefer["id"],
        },
    )
    assert added.status_code == 200, added.text
    db_session.expire_all()
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    categories = preview_stale_categories(
        db_session,
        owner_id=owner_id,
        input_snapshot=stored,
        scheduling_revision=captured_rev,
        settings_revision=int(settings.scheduling_revision),
    )
    assert STALE_COMPOSITION in categories

    _settings, _inputs, stored_ancestor, ancestor_rev = _capture(db_session, owner_id)
    ancestor_edit = client.post(
        f"/api/v1/epics/{epic['id']}/scheduling/rules/add",
        json={
            "expected_revision": _revision(client),
            "name": "tighter",
            "kind": "must",
            "policy_id": day["id"],
        },
    )
    assert ancestor_edit.status_code == 200, ancestor_edit.text
    db_session.expire_all()
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    ancestor_categories = preview_stale_categories(
        db_session,
        owner_id=owner_id,
        input_snapshot=stored_ancestor,
        scheduling_revision=ancestor_rev,
        settings_revision=int(settings.scheduling_revision),
    )
    assert STALE_COMPOSITION in ancestor_categories

    _settings, _inputs, stored_rank, rank_rev = _capture(db_session, owner_id)
    ranked = client.patch(
        "/api/v1/availability-policies/personal",
        json={"windows": _windows(TUESDAY.weekday(), "18:00", 60)},
    )
    assert ranked.status_code == 200, ranked.text
    db_session.expire_all()
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    rank_categories = preview_stale_categories(
        db_session,
        owner_id=owner_id,
        input_snapshot=stored_rank,
        scheduling_revision=rank_rev,
        settings_revision=int(settings.scheduling_revision),
    )
    assert STALE_COMPOSITION in rank_categories


# --- §2.1 dated / weekday / context / ignore-all ---------------------------


def test_deferred_and_forbidden_forms_reject_with_no_write(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    seeded = _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "explicit", "rules": [_rule("day", work["id"])]},
    )
    replacement = _replace(
        client,
        "task",
        task["id"],
        {
            "target_family": "new_rule",
            "may": {"presence": "explicit", "rules": [_rule("day", work["id"])]},
        },
    )
    assert replacement.status_code == 200, replacement.text
    replacement_id = replacement.json()["replacement_id"]
    before = _local(client, "task", task["id"])
    assert before["family"] == "new_rule"
    assert len(before["may"]["rules"]) == 1

    cases = [
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/assignment/family-replace",
            {
                "expected_revision": _revision(client),
                "target_family": "legacy",
                "preferred_time_window_id": str(uuid.uuid4()),
                "weekday": 0,
            },
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/assignment/clear",
            {"expected_revision": _revision(client), "context": "home"},
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/assignment/revert",
            {
                "expected_revision": _revision(client),
                "replacement_id": replacement_id,
                "weekdays": [0],
            },
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "put",
            f"/api/v1/tasks/{task['id']}/scheduling",
            {
                "expected_revision": _revision(client),
                "may": {"presence": "explicit", "rules": []},
                "on": "2026-10-13",
            },
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/rules/add",
            {
                "expected_revision": _revision(client),
                "name": "monday",
                "kind": "may",
                "policy_id": work["id"],
                "date_range": {"start": "2026-10-13", "end": "2026-10-14"},
            },
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/rules/replace-named",
            {
                "expected_revision": _revision(client),
                "target_rule_name": "day",
                "target_rule_kind": "may",
                "replacement_name": "night",
                "policy_id": work["id"],
                "expiry": "2026-10-20",
            },
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/rules/waive-named",
            {
                "expected_revision": _revision(client),
                "target_rule_name": "day",
                "days_of_week": [0],
            },
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/rules/remove-named",
            {
                "expected_revision": _revision(client),
                "operation": "addition",
                "target_rule_name": "day",
                "date_range": {"start": "2026-10-13", "end": "2026-10-14"},
            },
            "SCHEDULING_EXCEPTION_FORM_DEFERRED",
        ),
        (
            "post",
            f"/api/v1/tasks/{task['id']}/scheduling/rules/add",
            {
                "expected_revision": _revision(client),
                "name": "free",
                "kind": "may",
                "policy_id": work["id"],
                "ignore_all_restrictions": True,
            },
            "SCHEDULING_EXCEPTION_FORBIDDEN",
        ),
    ]
    for method, path, payload, code in cases:
        response = getattr(client, method)(path, json=payload)
        _reject(db_session, response, code)
        current = _local(client, "task", task["id"])
        assert current["family"] == "new_rule"
        assert [row["name"] for row in current["may"]["rules"]] == ["day"]
        assert current["exceptions"] == []
        assert current["revert_replacement_id"] == replacement_id
    assert seeded["family"] == "new_rule"


def test_named_rule_on_legacy_family_rejects(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    window = _map(client)
    work = _set_policy(client, "work", "09:00", 60)
    task = _task(client)
    client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": window["id"]},
    )
    rev = _revision(client)
    added = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/rules/add",
        json={
            "expected_revision": rev,
            "name": "eve",
            "kind": "may",
            "policy_id": work["id"],
        },
    )
    _reject(db_session, added, "NAMED_RULE_REQUIRES_NEW_RULE_FAMILY")
    assert _revision(client) == rev
    local = _local(client, "task", task["id"])
    assert local["family"] == "legacy"
    assert local["preferred_time_window_id"] == window["id"]
    assert local["may"] is None


# --- V4-D4 targeted named-rule / exception removal --------------------------


def _plural(scope: str) -> str:
    return {"task": "tasks", "project": "projects", "epic": "epics"}[scope]


def _remove_named(
    client: TestClient,
    scope: str,
    scope_id: str,
    *,
    operation: str,
    target_rule_name: str,
    extra: dict | None = None,
):
    body: dict = {
        "expected_revision": _revision(client),
        "operation": operation,
        "target_rule_name": target_rule_name,
    }
    if extra:
        body.update(extra)
    return client.post(
        f"/api/v1/{_plural(scope)}/{scope_id}/scheduling/rules/remove-named",
        json=body,
    )


@pytest.mark.parametrize("scope", ("task", "project", "epic"))
def test_v4_d4_remove_named_addition_restores_and_keeps_siblings(
    client: TestClient, db_session: Session, scope: str
) -> None:
    """Remove one rule.add row; sibling local rules stay (task/project/epic)."""
    _prepare(client, db_session)
    day = _set_policy(client, "work", "09:00", 180)
    eve = _set_policy(client, "personal", "19:00", 120)
    epic = _epic(client)
    project = _project(client, epic["id"])
    task = _task(client, project_id=project["id"])
    scope_id = {"task": task["id"], "project": project["id"], "epic": epic["id"]}[scope]

    _put_new_rule(
        client,
        scope,
        scope_id,
        may={
            "presence": "explicit",
            "rules": [_rule("day", day["id"]), _rule("keep", day["id"])],
        },
        prefer=[_rule("late", eve["id"])],
    )
    added = client.post(
        f"/api/v1/{_plural(scope)}/{scope_id}/scheduling/rules/add",
        json={
            "expected_revision": _revision(client),
            "name": "extra",
            "kind": "may",
            "policy_id": eve["id"],
        },
    )
    assert added.status_code == 200, added.text
    before = _local(client, scope, scope_id)
    assert sorted(r["name"] for r in before["may"]["rules"]) == ["day", "extra", "keep"]
    assert [r["name"] for r in before["prefer"]] == ["late"]
    rev_before = _revision(client)

    removed = _remove_named(
        client, scope, scope_id, operation="addition", target_rule_name="extra"
    )
    assert removed.status_code == 200, removed.text
    body = removed.json()
    assert body["rule"]["name"] == "extra"
    assert body["exception"] is None
    assert body["scheduling_revision"] == rev_before + 1

    after = _local(client, scope, scope_id)
    assert sorted(r["name"] for r in after["may"]["rules"]) == ["day", "keep"]
    assert [r["name"] for r in after["prefer"]] == ["late"]
    assert after["exceptions"] == []
    assert _revision(client) == rev_before + 1


def test_v4_d4_remove_named_waive_restores_must_keeps_sibling_waiver(
    client: TestClient, db_session: Session
) -> None:
    """Removing one waive restores that Must; unrelated waive stays."""
    _prepare(client, db_session)
    day = _set_policy(client, "work", "09:00", 480)
    office = _set_policy(client, "general", "09:00", 240)
    desk = _set_policy(client, "personal", "10:00", 120)
    epic = _epic(client)
    project = _project(client, epic["id"])
    task = _task(client, project_id=project["id"])

    _put_new_rule(
        client,
        "project",
        project["id"],
        may={"presence": "explicit", "rules": [_rule("day", day["id"])]},
        must=[_rule("office", office["id"]), _rule("desk", desk["id"])],
    )
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "omit", "rules": []},
    )
    for name in ("office", "desk"):
        waived = client.post(
            f"/api/v1/tasks/{task['id']}/scheduling/rules/waive-named",
            json={
                "expected_revision": _revision(client),
                "target_rule_name": name,
            },
        )
        assert waived.status_code == 200, waived.text

    local = _local(client, "task", task["id"])
    assert sorted(e["target_rule_name"] for e in local["exceptions"]) == ["desk", "office"]
    row = db_session.get(Task, uuid.UUID(task["id"]))
    _task_row, composed = _effective(db_session, row)
    assert composed is not None
    assert set(composed.waived_must_ids) >= {"office", "desk"}
    assert "office" not in {e.rule_id for e in composed.must_rules}
    assert "desk" not in {e.rule_id for e in composed.must_rules}

    rev = _revision(client)
    stale = _remove_named(
        client,
        "task",
        task["id"],
        operation="waive_named",
        target_rule_name="office",
        extra={"expected_revision": rev - 1},
    )
    _reject(db_session, stale, "SCHEDULING_REVISION_CONFLICT")
    assert _revision(client) == rev
    assert sorted(
        e["target_rule_name"] for e in _local(client, "task", task["id"])["exceptions"]
    ) == ["desk", "office"]

    removed = _remove_named(
        client, "task", task["id"], operation="waive_named", target_rule_name="office"
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["exception"]["target_rule_name"] == "office"
    assert removed.json()["exception"]["operation"] == "waive_named"
    assert _revision(client) == rev + 1

    after_local = _local(client, "task", task["id"])
    assert [e["target_rule_name"] for e in after_local["exceptions"]] == ["desk"]
    db_session.expire_all()
    _task_row, restored = _effective(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert restored is not None
    must_ids = {e.rule_id for e in restored.must_rules}
    assert "office" in must_ids
    assert "desk" not in must_ids
    assert "desk" in set(restored.waived_must_ids)
    assert "office" not in set(restored.waived_must_ids)


def test_v4_d4_remove_named_replace_restores_underlying_may(
    client: TestClient, db_session: Session
) -> None:
    """Removing replace_named restores the named May; sibling replace stays."""
    _prepare(client, db_session)
    am = _set_policy(client, "work", "09:00", 180)
    pm = _set_policy(client, "general", "13:00", 180)
    night = _set_policy(client, "personal", "19:00", 60)
    epic = _epic(client)
    project = _project(client, epic["id"])
    task = _task(client, project_id=project["id"])

    _put_new_rule(
        client,
        "epic",
        epic["id"],
        may={
            "presence": "explicit",
            "rules": [_rule("am", am["id"]), _rule("pm", pm["id"])],
        },
    )
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "omit", "rules": []},
    )
    for target in ("am", "pm"):
        replaced = client.post(
            f"/api/v1/tasks/{task['id']}/scheduling/rules/replace-named",
            json={
                "expected_revision": _revision(client),
                "target_rule_name": target,
                "target_rule_kind": "may",
                "replacement_name": f"{target}-night",
                "policy_id": night["id"],
            },
        )
        assert replaced.status_code == 200, replaced.text

    local = _local(client, "task", task["id"])
    assert sorted(e["target_rule_name"] for e in local["exceptions"]) == ["am", "pm"]
    # Both May rules replaced with night-only → evening clips only.
    _task_row, before = _effective(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert before is not None
    may_ids_before = {e.rule_id for e in before.may_rules}
    assert "am-night" in may_ids_before or "am" not in may_ids_before

    removed = _remove_named(
        client, "task", task["id"], operation="replace_named", target_rule_name="am"
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["exception"]["operation"] == "replace_named"
    assert removed.json()["exception"]["target_rule_name"] == "am"

    after = _local(client, "task", task["id"])
    assert [e["target_rule_name"] for e in after["exceptions"]] == ["pm"]
    assert after["exceptions"][0]["replacement_name"] == "pm-night"

    db_session.expire_all()
    _task_row, restored = _effective(
        db_session, db_session.get(Task, uuid.UUID(task["id"]))
    )
    assert restored is not None
    may_ids = {e.rule_id for e in restored.may_rules}
    assert "am" in may_ids
    assert "pm-night" in may_ids or "pm" not in may_ids
    composed, clips = _clips(db_session, db_session.get(Task, uuid.UUID(task["id"])))
    assert composed is not None
    hours = {(item[0].hour, item[1].hour) for item in clips}
    # Restored am 09–12 must appear; pm still replaced by night 19–20.
    assert (9, 12) in hours
    assert any(start >= 19 for start, _end in hours)

    missing = _remove_named(
        client, "task", task["id"], operation="replace_named", target_rule_name="am"
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "NAMED_RULE_REMOVE_NOT_FOUND"
    db_session.rollback()
    assert [e["target_rule_name"] for e in _local(client, "task", task["id"])["exceptions"]] == [
        "pm"
    ]


def test_v4_d4_remove_named_scopes_project_and_epic_exceptions(
    client: TestClient, db_session: Session
) -> None:
    """Project/epic remove-named for waive/replace; does not touch other scopes."""
    _prepare(client, db_session)
    day = _set_policy(client, "work", "09:00", 480)
    tight = _set_policy(client, "general", "09:00", 120)
    epic = _epic(client)
    project = _project(client, epic["id"])
    task = _task(client, project_id=project["id"])

    _put_new_rule(
        client,
        "epic",
        epic["id"],
        may={"presence": "explicit", "rules": [_rule("day", day["id"])]},
        must=[_rule("tight", tight["id"])],
    )
    _put_new_rule(
        client,
        "project",
        project["id"],
        may={"presence": "omit", "rules": []},
    )
    epic_waive = client.post(
        f"/api/v1/epics/{epic['id']}/scheduling/rules/waive-named",
        json={
            "expected_revision": _revision(client),
            "target_rule_name": "tight",
        },
    )
    assert epic_waive.status_code == 200, epic_waive.text
    proj_replace = client.post(
        f"/api/v1/projects/{project['id']}/scheduling/rules/replace-named",
        json={
            "expected_revision": _revision(client),
            "target_rule_name": "day",
            "target_rule_kind": "may",
            "replacement_name": "day-narrow",
            "policy_id": tight["id"],
        },
    )
    assert proj_replace.status_code == 200, proj_replace.text

    removed_epic = _remove_named(
        client, "epic", epic["id"], operation="waive_named", target_rule_name="tight"
    )
    assert removed_epic.status_code == 200, removed_epic.text
    assert _local(client, "epic", epic["id"])["exceptions"] == []
    assert len(_local(client, "project", project["id"])["exceptions"]) == 1

    removed_proj = _remove_named(
        client,
        "project",
        project["id"],
        operation="replace_named",
        target_rule_name="day",
    )
    assert removed_proj.status_code == 200, removed_proj.text
    assert _local(client, "project", project["id"])["exceptions"] == []
    # Task still has no local exceptions; epic Must is restored in composition.
    _put_new_rule(
        client,
        "task",
        task["id"],
        may={"presence": "omit", "rules": []},
    )
    db_session.expire_all()
    _task_row, composed = _effective(
        db_session, db_session.get(Task, uuid.UUID(task["id"]))
    )
    assert composed is not None
    assert "tight" in {e.rule_id for e in composed.must_rules}
