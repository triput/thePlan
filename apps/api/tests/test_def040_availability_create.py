"""DEF-040 / DEF-045 — custom availability create + Prefer (not Must).

Disposable ``theplan_s1_test`` only. Alembic head ``033_custom_availability_slug``.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.models import Task, UserSettings
from app.models.scheduling_assignment import SchedulingAssignment
from app.scheduler.availability_materializer import load_owner_policy_windows
from app.scheduler.composition import RANK_ELIGIBLE, RANK_PREFER, composition_search_windows
from app.scheduler.composition_resolver import load_effective_compositions
from app.services.availability_seed import ensure_default_availability_policies
from app.services.s2_v3_availability_guard import (
    CUSTOM_POLICY_ASSIGNMENT_NOTE,
    V3_SCHEDULING_EFFECTIVE_NOTE,
)

TUESDAY = date(2026, 10, 13)
TZ = ZoneInfo("UTC")

_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "033_custom_availability_slug"


@pytest.fixture(autouse=True)
def _disposable_database(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD, (
        f"disposable database alembic version is {version!r}; "
        f"upgrade {_REQUIRED_DB} to {_REQUIRED_HEAD} before this gate"
    )


def _revision(client: TestClient) -> int:
    return int(client.get("/api/v1/settings").json()["scheduling_revision"])


def _weekday_windows(weekday: int, start: str, duration: int) -> list[dict]:
    return [
        {
            "weekday": weekday,
            "start_time": start,
            "duration_minutes": duration,
            "sort_order": 0,
        }
    ]


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _prepare(client: TestClient, db: Session) -> uuid.UUID:
    owner_id = _owner_id(client)
    ensure_default_availability_policies(db, owner_id)
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    settings.timezone = "UTC"
    db.commit()
    return owner_id


def _policies_by_slug(client: TestClient) -> dict[str, dict]:
    rows = client.get("/api/v1/availability-policies")
    assert rows.status_code == 200, rows.text
    return {row["slug"]: row for row in rows.json()}


def _fingerprint(row: dict) -> tuple:
    windows = tuple(
        (
            window["weekday"],
            window["start_time"],
            window["end_time"],
            window["duration_minutes"],
            window["sort_order"],
        )
        for window in row["windows"]
    )
    return (
        row["id"],
        row["name"],
        row["scheduling_effective"],
        row["scheduling_effective_note"],
        windows,
    )


def _create_afternoon(client: TestClient, *, weekday: int = TUESDAY.weekday()) -> dict:
    created = client.post(
        "/api/v1/availability-policies",
        json={
            "slug": "Afternoon",
            "name": "  Afternoon hours  ",
            "windows": _weekday_windows(weekday, "13:00", 240),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["slug"] == "afternoon"
    assert body["name"] == "Afternoon hours"
    assert body["scheduling_effective"] is False
    assert body["scheduling_effective_note"] == CUSTOM_POLICY_ASSIGNMENT_NOTE
    assert body["windows"][0]["start_time"] == "13:00"
    assert body["windows"][0]["end_time"] == "17:00"
    assert body["windows"][0]["duration_minutes"] == 240
    assert body["windows"][0]["ends_next_day"] is False
    return body


def _task(client: TestClient, **extra) -> dict:
    payload = {"title": f"Writing {uuid.uuid4().hex[:8]}", "estimated_duration_minutes": 60}
    payload.update(extra)
    created = client.post("/api/v1/tasks", json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def _put_rules(
    client: TestClient,
    task_id: str,
    *,
    must: list | None = None,
    prefer: list | None = None,
) -> dict:
    response = client.put(
        f"/api/v1/tasks/{task_id}/scheduling",
        json={
            "expected_revision": _revision(client),
            "may": {"presence": "omit"},
            "must": must or [],
            "prefer": prefer or [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _search_clips(db: Session, task_id: str):
    db.expire_all()
    task = db.get(Task, uuid.UUID(task_id))
    assert task is not None
    found = load_effective_compositions(db, task.owner_id, [task], {}, {})
    composed = found.get(task.id)
    assert composed is not None
    _working, general = load_owner_policy_windows(db, task.owner_id)
    return composed, composition_search_windows(TUESDAY, TZ, composed, general)


def test_create_custom_afternoon_policy_and_prefer_on_task(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    seeded = _policies_by_slug(client)
    before = {slug: _fingerprint(seeded[slug]) for slug in ("general", "work", "personal")}
    assert seeded["work"]["scheduling_effective"] is True
    assert seeded["general"]["scheduling_effective"] is True
    assert seeded["personal"]["scheduling_effective"] is False
    assert V3_SCHEDULING_EFFECTIVE_NOTE in seeded["work"]["scheduling_effective_note"]

    rev_before = _revision(client)
    body = _create_afternoon(client, weekday=0)
    policy_id = body["id"]
    assert _revision(client) == rev_before + 1

    after = _policies_by_slug(client)
    for slug in ("general", "work", "personal"):
        assert _fingerprint(after[slug]) == before[slug]
    assert after["personal"]["scheduling_effective_note"] != CUSTOM_POLICY_ASSIGNMENT_NOTE

    effective = client.get(
        f"/api/v1/availability-policies/{policy_id}/effective",
        params={"on": "2026-10-12"},
    )
    assert effective.status_code == 200, effective.text
    effective_body = effective.json()
    assert effective_body["scheduling_effective"] is False
    assert effective_body["scheduling_effective_note"] == CUSTOM_POLICY_ASSIGNMENT_NOTE
    assert effective_body["slug"] == "afternoon"

    reserved_rev = _revision(client)
    reserved = client.post(
        "/api/v1/availability-policies",
        json={
            "slug": "work",
            "name": "Nope",
            "windows": _weekday_windows(0, "09:00", 60),
        },
    )
    assert reserved.status_code == 422
    assert _revision(client) == reserved_rev
    assert _fingerprint(_policies_by_slug(client)["work"]) == before["work"]

    dup = client.post(
        "/api/v1/availability-policies",
        json={
            "slug": "AFTERNOON",
            "name": "Duplicate",
            "windows": _weekday_windows(0, "14:00", 60),
        },
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "AVAILABILITY_POLICY_SLUG_CONFLICT"
    db_session.rollback()
    assert _fingerprint(_policies_by_slug(client)["work"]) == before["work"]

    task = _task(client)
    patched = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={
            "min_block_duration_minutes": 60,
            "max_block_duration_minutes": 120,
            "keep_in_one_block": True,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["min_block_duration_minutes"] == 60
    assert patched.json()["max_block_duration_minutes"] == 120
    assert patched.json()["keep_in_one_block"] is True
    read_back = client.get(f"/api/v1/tasks/{task['id']}")
    assert read_back.status_code == 200, read_back.text
    assert read_back.json()["min_block_duration_minutes"] == 60
    assert read_back.json()["max_block_duration_minutes"] == 120
    assert read_back.json()["keep_in_one_block"] is True

    _put_rules(
        client,
        task["id"],
        prefer=[{"name": "afternoon", "policy_id": policy_id}],
    )
    local = client.get(f"/api/v1/tasks/{task['id']}/scheduling").json()
    assert local["family"] == "new_rule"
    assert local["preferred_time_window_id"] is None
    assert local["must"] == []
    assert local["prefer"][0]["policy_id"] == policy_id
    assert local["prefer"][0]["kind"] == "prefer"
    assert len(local["prefer"]) == 1


def test_legacy_map_collision_still_rejects_scheduling_put(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    afternoon = _create_afternoon(client)
    window_resp = client.post(
        "/api/v1/focus-windows",
        json={
            "name": "Legacy Afternoon",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "13:00",
                    "end_time": "17:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert window_resp.status_code == 201, window_resp.text
    window = window_resp.json()
    task = _task(client, preferred_time_window_id=window["id"])
    rev = _revision(client)
    collided = client.put(
        f"/api/v1/tasks/{task['id']}/scheduling",
        json={
            "expected_revision": rev,
            "may": {"presence": "omit"},
            "must": [],
            "prefer": [{"name": "afternoon", "policy_id": afternoon["id"]}],
        },
    )
    assert collided.status_code == 409
    assert collided.json()["code"] == "SCHEDULING_FAMILY_COLLISION"
    db_session.rollback()
    assert _revision(client) == rev
    local = client.get(f"/api/v1/tasks/{task['id']}/scheduling").json()
    assert local["family"] == "legacy"
    assert local["preferred_time_window_id"] == window["id"]
    assert local["prefer"] == []
    assert local["must"] == []
    assert (
        db_session.query(SchedulingAssignment)
        .filter(SchedulingAssignment.scope_id == uuid.UUID(task["id"]))
        .count()
        == 0
    )

    replaced = client.post(
        f"/api/v1/tasks/{task['id']}/scheduling/assignment/family-replace",
        json={
            "expected_revision": _revision(client),
            "target_family": "new_rule",
            "may": {"presence": "omit"},
            "must": [],
            "prefer": [{"name": "afternoon", "policy_id": afternoon["id"]}],
        },
    )
    assert replaced.status_code == 200, replaced.text
    body = replaced.json()
    assert body["family"] == "new_rule"
    assert body["assignment"]["preferred_time_window_id"] is None
    assert body["assignment"]["must"] == []
    assert body["assignment"]["prefer"][0]["policy_id"] == afternoon["id"]
    assert body["assignment"]["prefer"][0]["kind"] == "prefer"
    assert body["replacement_id"]

    general = client.patch(
        "/api/v1/availability-policies/general",
        json={"windows": _weekday_windows(TUESDAY.weekday(), "09:00", 480)},
    )
    assert general.status_code == 200, general.text
    _composed, clips = _search_clips(db_session, task["id"])
    ranks = [(item[0].hour, item[1].hour, item[2]) for item in clips]
    assert (13, 17, RANK_PREFER) in ranks
    assert (9, 17, RANK_ELIGIBLE) in ranks


@pytest.mark.parametrize(
    "slug",
    [
        "general",
        "Work",
        " PERSONAL ",
        "1afternoon",
        "after-noon",
        "a" * 64,
    ],
)
def test_reserved_and_invalid_slugs_rejected(
    client: TestClient, db_session: Session, slug: str
) -> None:
    _prepare(client, db_session)
    before = {
        key: _fingerprint(row)
        for key, row in _policies_by_slug(client).items()
        if key in ("general", "work", "personal")
    }
    rev = _revision(client)
    rejected = client.post(
        "/api/v1/availability-policies",
        json={
            "slug": slug,
            "name": "Nope",
            "windows": _weekday_windows(TUESDAY.weekday(), "13:00", 60),
        },
    )
    assert rejected.status_code == 422, rejected.text
    db_session.rollback()
    assert _revision(client) == rev
    after = _policies_by_slug(client)
    assert "afternoon" not in after
    for key, fingerprint in before.items():
        assert _fingerprint(after[key]) == fingerprint


def test_empty_windows_and_blank_name_rejected(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    rev = _revision(client)
    empty_windows = client.post(
        "/api/v1/availability-policies",
        json={"slug": "afternoon", "name": "Afternoon", "windows": []},
    )
    blank_name = client.post(
        "/api/v1/availability-policies",
        json={
            "slug": "evening",
            "name": "   ",
            "windows": _weekday_windows(TUESDAY.weekday(), "13:00", 60),
        },
    )
    assert empty_windows.status_code == 422
    assert blank_name.status_code == 422
    db_session.rollback()
    assert _revision(client) == rev
    slugs = set(_policies_by_slug(client))
    assert "afternoon" not in slugs
    assert "evening" not in slugs


def test_unknown_policy_uuid_does_not_assign(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _task(client)
    rev = _revision(client)
    missing = client.put(
        f"/api/v1/tasks/{task['id']}/scheduling",
        json={
            "expected_revision": rev,
            "may": {"presence": "omit"},
            "must": [],
            "prefer": [{"name": "afternoon", "policy_id": str(uuid.uuid4())}],
        },
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "AVAILABILITY_POLICY_NOT_FOUND"
    db_session.rollback()
    assert _revision(client) == rev
    local = client.get(f"/api/v1/tasks/{task['id']}/scheduling").json()
    assert local["family"] == "none"
    assert local["prefer"] == []


def test_custom_prefer_keeps_general_fallback_must_does_not(
    client: TestClient, db_session: Session
) -> None:
    owner_id = _prepare(client, db_session)
    general = client.patch(
        "/api/v1/availability-policies/general",
        json={"windows": _weekday_windows(TUESDAY.weekday(), "09:00", 480)},
    )
    assert general.status_code == 200, general.text
    general_fp = _fingerprint(_policies_by_slug(client)["general"])
    work_fp = _fingerprint(_policies_by_slug(client)["work"])
    afternoon = _create_afternoon(client)
    assert _fingerprint(_policies_by_slug(client)["general"]) == general_fp
    assert _fingerprint(_policies_by_slug(client)["work"]) == work_fp

    _working, general_windows = load_owner_policy_windows(db_session, owner_id)
    assert len(general_windows) == 1
    assert general_windows[0].start_time.hour == 9
    assert general_windows[0].duration_minutes == 480

    prefer_task = _task(client)
    must_task = _task(client)
    rule = [{"name": "afternoon", "policy_id": afternoon["id"]}]
    _put_rules(client, prefer_task["id"], prefer=rule)
    _put_rules(client, must_task["id"], must=rule)

    prefer_local = client.get(f"/api/v1/tasks/{prefer_task['id']}/scheduling").json()
    must_local = client.get(f"/api/v1/tasks/{must_task['id']}/scheduling").json()
    assert prefer_local["must"] == []
    assert prefer_local["prefer"][0]["kind"] == "prefer"
    assert must_local["prefer"] == []
    assert must_local["must"][0]["kind"] == "must"
    assert must_local["must"][0]["policy_id"] == afternoon["id"]

    prefer_composed, prefer_clips = _search_clips(db_session, prefer_task["id"])
    must_composed, must_clips = _search_clips(db_session, must_task["id"])
    assert prefer_composed.may_source == "general"
    assert [rule.rule_id for rule in prefer_composed.prefer_rules] == ["afternoon"]
    assert prefer_composed.must_rules == ()
    assert prefer_composed.prefer_rules[0].windows[0].duration_minutes == 240
    assert must_composed.prefer_rules == ()
    assert [rule.rule_id for rule in must_composed.must_rules] == ["afternoon"]

    prefer_ranks = [(item[0].hour, item[1].hour, item[2]) for item in prefer_clips]
    must_ranks = [(item[0].hour, item[1].hour, item[2]) for item in must_clips]
    assert prefer_ranks == [(13, 17, RANK_PREFER), (9, 17, RANK_ELIGIBLE)]
    assert must_ranks == [(13, 17, RANK_ELIGIBLE)]

    effective = client.get(f"/api/v1/tasks/{prefer_task['id']}/scheduling/effective")
    assert effective.status_code == 200, effective.text
    resolved = effective.json()["new_rule_assignment"]
    assert resolved["must"] == []
    assert resolved["prefer"][0]["policy_id"] == afternoon["id"]
    assert resolved["prefer"][0]["kind"] == "prefer"
    saved = effective.json()
    assert saved["general_policy_saved"]["policy_id"] != afternoon["id"]
    assert saved["general_policy_saved"]["slug"] == "general"
    assert saved["working_policy_saved"]["slug"] == "work"
    assert saved["general_policy_scheduling_effective"] is True
    assert saved["personal_policy_saved"]["placer_active"] is False
