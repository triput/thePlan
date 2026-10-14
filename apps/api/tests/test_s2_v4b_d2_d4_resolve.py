"""V4b-D2 / D4 — scoped family write → collect → placement, and fingerprints.

Disposable ``theplan_s1_test`` only. Alembic ``032_scheduling_day_scoped_ops``.
Does not activate, migrate the household, or bump the V4b token.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import FocusWindow, Task, UserSettings
from app.models.scheduling_day_scoped import SchedulingDayScopedOp
from app.scheduler.availability_materializer import load_owner_policy_windows
from app.scheduler.composition import composition_fingerprint, composition_search_windows
from app.scheduler.composition_resolver import load_effective_compositions
from app.scheduler.placement import place_task
from app.services.availability_seed import ensure_default_availability_policies

_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "032_scheduling_day_scoped_ops"
UTC = timezone.utc
TUESDAY = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
TUESDAY_END = datetime(2026, 10, 13, 18, 0, tzinfo=UTC)
NEXT_TUESDAY = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)
NEXT_TUESDAY_END = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
TZ_NAME = "UTC"


@pytest.fixture(autouse=True)
def _disposable_v4b_database(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB, (
        f"refusing to run S2-V4b resolve tests against {name!r}; "
        "set DATABASE_URL to disposable theplan_s1_test"
    )
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD, (
        f"disposable database alembic version is {version!r}; "
        f"upgrade {_REQUIRED_DB} to {_REQUIRED_HEAD} before this gate"
    )


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _revision(client: TestClient) -> int:
    response = client.get("/api/v1/settings")
    assert response.status_code == 200, response.text
    return int(response.json()["scheduling_revision"])


def _prepare(client: TestClient, db: Session) -> None:
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    ensure_default_availability_policies(db, owner_id)
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    settings.timezone = "UTC"
    db.commit()


def _policy(client: TestClient, slug: str, start: str, duration: int) -> dict:
    response = client.patch(
        f"/api/v1/availability-policies/{slug}",
        json={
            "windows": [
                {
                    "weekday": 1,
                    "start_time": start,
                    "duration_minutes": duration,
                    "sort_order": 0,
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _task(client: TestClient, **extra) -> dict:
    payload = {"title": f"T {_uid()}", "estimated_duration_minutes": 60}
    payload.update(extra)
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _project(client: TestClient) -> dict:
    response = client.post("/api/v1/projects", json={"title": f"P {_uid()}"})
    assert response.status_code == 201, response.text
    return response.json()


def _put_new_rule(client: TestClient, scope: str, scope_id: str, policy_id: str) -> None:
    plural = {"task": "tasks", "project": "projects"}[scope]
    response = client.put(
        f"/api/v1/{plural}/{scope_id}/scheduling",
        json={
            "expected_revision": _revision(client),
            "may": {"presence": "explicit", "rules": [{"name": "day", "policy_id": policy_id}]},
            "must": [],
            "prefer": [],
        },
    )
    assert response.status_code == 200, response.text


def _family(
    client: TestClient,
    task_id: str,
    body: dict,
) -> dict:
    response = client.post(
        f"/api/v1/tasks/{task_id}/scheduling/assignment/family-replace-scoped",
        json={"expected_revision": _revision(client), "on_date": "2026-10-13", **body},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _map(client: TestClient, start: str, end: str) -> dict:
    response = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"Map {_uid()}",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": start,
                    "end_time": end,
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _collected(db: Session, task_id: str):
    db.expire_all()
    task = db.get(Task, uuid.UUID(task_id))
    assert task is not None
    project = None
    projects = {}
    if task.project_id is not None:
        from app.models import Project

        project = db.get(Project, task.project_id)
        if project is not None:
            projects[project.id] = project
    found = load_effective_compositions(db, task.owner_id, [task], projects, {})
    return task, found.get(task.id)


def _eligible_hours(composed, day, general) -> list[tuple[int, int]]:
    from zoneinfo import ZoneInfo

    clips = composition_search_windows(day, ZoneInfo(TZ_NAME), composed, general)
    return [(item[0].hour, item[1].hour) for item in clips if item[2] == "eligible"]


def _place(db: Session, task: Task, composed, start: datetime, end: datetime):
    settings = db.query(UserSettings).filter(UserSettings.owner_id == task.owner_id).one()
    working, general = load_owner_policy_windows(db, task.owner_id)
    maps = {
        row.id: row
        for row in (
            db.query(FocusWindow).filter(FocusWindow.owner_id == task.owner_id).all()
        )
    }
    result, _busy = place_task(
        db,
        task=task,
        owner_id=task.owner_id,
        settings=settings,
        remaining_minutes=int(task.estimated_duration_minutes or 60),
        busy=[],
        horizon_start=start,
        horizon_end=end,
        preferred_windows=maps,
        now_utc=start,
        finalize_status=False,
        persist_blocks=False,
        working_windows=working,
        general_windows=general,
        composition=composed,
        ranking_protection=False,
    )
    return result, general


def test_unassigned_explicit_empty_family_reaches_the_placer(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    _policy(client, "general", "15:00", 60)
    task = _task(client)
    written = _family(
        client,
        task["id"],
        {
            "target_family": "new_rule",
            "may": {"presence": "explicit", "rules": [{"name": "closed", "empty_set": True}]},
        },
    )
    assert written["scheduling_revision"] >= 1
    stored, composed = _collected(db_session, task["id"])
    assert composed is not None
    _result_day, general = _place(db_session, stored, composed, TUESDAY, TUESDAY_END)
    assert _eligible_hours(composed, TUESDAY.date(), general) == []
    assert _result_day.blocks_created == 0
    later, _general = _place(db_session, stored, composed, NEXT_TUESDAY, NEXT_TUESDAY_END)
    assert later.blocks_created == 1
    assert later.proposed_blocks[0].start_time == datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


def test_scoped_none_suppresses_local_may_and_expiry_restores_it(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    morning = _policy(client, "work", "09:00", 60)
    _policy(client, "general", "15:00", 60)
    task = _task(client)
    _put_new_rule(client, "task", task["id"], morning["id"])
    _family(client, task["id"], {"target_family": "none"})
    stored, composed = _collected(db_session, task["id"])
    assert composed is not None
    inside, general = _place(db_session, stored, composed, TUESDAY, TUESDAY_END)
    assert (15, 16) in _eligible_hours(composed, TUESDAY.date(), general)
    assert (9, 10) not in _eligible_hours(composed, TUESDAY.date(), general)
    assert inside.proposed_blocks[0].start_time == datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
    outside, _general = _place(db_session, stored, composed, NEXT_TUESDAY, NEXT_TUESDAY_END)
    assert outside.proposed_blocks[0].start_time == datetime(2026, 10, 20, 9, 0, tzinfo=UTC)

    expired = _task(client)
    _put_new_rule(client, "task", expired["id"], morning["id"])
    _family(
        client,
        expired["id"],
        {"target_family": "none", "expires_at": "2026-10-13T00:00:00Z"},
    )
    expired_row, expired_comp = _collected(db_session, expired["id"])
    skipped, _general = _place(db_session, expired_row, expired_comp, TUESDAY, TUESDAY_END)
    assert skipped.proposed_blocks[0].start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


def test_inherited_family_and_legacy_transition_place(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    morning = _policy(client, "work", "09:00", 180)
    _policy(client, "general", "18:00", 60)
    project = _project(client)
    _put_new_rule(client, "project", project["id"], morning["id"])
    child = _task(client, project_id=project["id"])
    _family(
        client,
        child["id"],
        {
            "target_family": "new_rule",
            "may": {"presence": "explicit", "rules": [{"name": "closed", "empty_set": True}]},
        },
    )
    stored, composed = _collected(db_session, child["id"])
    inside, general = _place(db_session, stored, composed, TUESDAY, TUESDAY_END)
    assert _eligible_hours(composed, TUESDAY.date(), general) == []
    assert inside.blocks_created == 0
    outside, _general = _place(db_session, stored, composed, NEXT_TUESDAY, NEXT_TUESDAY_END)
    assert outside.proposed_blocks[0].start_time == datetime(2026, 10, 20, 9, 0, tzinfo=UTC)

    mapped = _task(client)
    _put_new_rule(client, "task", mapped["id"], morning["id"])
    window = _map(client, "14:00", "15:00")
    _family(
        client,
        mapped["id"],
        {"target_family": "legacy", "preferred_time_window_id": window["id"]},
    )
    mapped_row, mapped_comp = _collected(db_session, mapped["id"])
    legacy_day, _general = _place(db_session, mapped_row, mapped_comp, TUESDAY, TUESDAY_END)
    assert legacy_day.proposed_blocks[0].start_time == datetime(2026, 10, 13, 14, 0, tzinfo=UTC)
    restored, _general = _place(db_session, mapped_row, mapped_comp, NEXT_TUESDAY, NEXT_TUESDAY_END)
    assert restored.proposed_blocks[0].start_time == datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


def test_replacement_layer_policy_hours_change_the_collected_fingerprint(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    morning = _policy(client, "work", "09:00", 60)
    afternoon = _policy(client, "personal", "15:00", 60)
    task = _task(client)
    _put_new_rule(client, "task", task["id"], morning["id"])
    written = _family(
        client,
        task["id"],
        {
            "target_family": "new_rule",
            "may": {
                "presence": "explicit",
                "rules": [{"name": "pm", "policy_id": afternoon["id"]}],
            },
        },
    )
    _stored, before = _collected(db_session, task["id"])
    assert before is not None
    before_fp = composition_fingerprint(before)
    _working, general = load_owner_policy_windows(db_session, _stored.owner_id)
    assert (15, 16) in _eligible_hours(before, TUESDAY.date(), general)
    del _working

    shifted = client.patch(
        "/api/v1/availability-policies/personal",
        json={
            "windows": [
                {
                    "weekday": 1,
                    "start_time": "16:00",
                    "duration_minutes": 60,
                    "sort_order": 0,
                }
            ]
        },
    )
    assert shifted.status_code == 200, shifted.text
    _stored, after = _collected(db_session, task["id"])
    after_fp = composition_fingerprint(after)
    assert before_fp != after_fp
    assert before_fp["day_scoped"][0]["id"] == after_fp["day_scoped"][0]["id"]
    assert before_fp["day_scoped"][0]["selector"] == after_fp["day_scoped"][0]["selector"]
    assert before_fp["rules"] == after_fp["rules"]
    assert (
        before_fp["day_scoped"][0]["replacement_layer"]["may_rules"][0]["windows"][0]["start_time"]
        == "15:00:00"
    )
    assert (
        after_fp["day_scoped"][0]["replacement_layer"]["may_rules"][0]["windows"][0]["start_time"]
        == "16:00:00"
    )
    _working, general = load_owner_policy_windows(db_session, _stored.owner_id)
    assert (16, 17) in _eligible_hours(after, TUESDAY.date(), general)
    row = (
        db_session.query(SchedulingDayScopedOp)
        .filter(SchedulingDayScopedOp.id == uuid.UUID(written["replacement_id"]))
        .one()
    )
    assert str(row.id) == before_fp["day_scoped"][0]["id"]


def _bands(*rows: tuple[str, str, str]) -> list[dict]:
    return [
        {
            "tier": tier,
            "start_time": start,
            "end_time": end,
            "days_of_week": 127,
            "sort_order": index,
        }
        for index, (tier, start, end) in enumerate(rows)
    ]


def _focus(client: TestClient, *, strict: bool, bands: list[dict]) -> dict:
    response = client.post(
        "/api/v1/focus-windows",
        json={"name": f"Map {_uid()}", "strict_mode": strict, "bands": bands},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _accept_legacy(client: TestClient, task_id: str, window_id: str) -> None:
    _family(
        client,
        task_id,
        {"target_family": "legacy", "preferred_time_window_id": window_id},
    )


def _scoped_legacy_task(client: TestClient, db: Session, window_id: str) -> tuple[Task, object]:
    """Local new-rule May is morning-only. Working is that same patched policy."""
    morning = _policy(client, "work", "09:00", 180)
    task = _task(client)
    _put_new_rule(client, "task", task["id"], morning["id"])
    _accept_legacy(client, task["id"], window_id)
    return _collected(db, task["id"])


def test_scoped_legacy_retains_red_exclusion(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    window = _focus(
        client,
        strict=True,
        bands=_bands(("green", "14:00", "17:00"), ("red", "14:00", "15:00")),
    )
    stored, composed = _scoped_legacy_task(client, db_session, window["id"])
    placed, _general = _place(db_session, stored, composed, TUESDAY, TUESDAY_END)
    assert placed.blocks_created == 1
    start = placed.proposed_blocks[0].start_time
    assert start == datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
    assert placed.proposed_blocks[0].end_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)


def test_scoped_legacy_green_outranks_yellow(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    window = _focus(
        client,
        strict=True,
        bands=_bands(("yellow", "14:00", "17:00"), ("green", "16:00", "17:00")),
    )
    stored, composed = _scoped_legacy_task(client, db_session, window["id"])
    placed, _general = _place(db_session, stored, composed, TUESDAY, TUESDAY_END)
    assert placed.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)


def test_scoped_legacy_strict_omits_neutral_flexible_keeps_it(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    _policy(client, "work", "09:00", 180)
    work_id = _policy(client, "work", "09:00", 180)["id"]
    red_only = _bands(("red", "12:00", "13:00"))

    strict_task = _task(client, estimated_duration_minutes=90)
    _put_new_rule(client, "task", strict_task["id"], work_id)
    strict_map = _focus(client, strict=True, bands=red_only)
    _accept_legacy(client, strict_task["id"], strict_map["id"])
    strict_row, strict_comp = _collected(db_session, strict_task["id"])
    strict_placed, _general = _place(db_session, strict_row, strict_comp, TUESDAY, TUESDAY_END)
    assert strict_placed.blocks_created == 0

    flexible_task = _task(client, estimated_duration_minutes=90)
    _put_new_rule(client, "task", flexible_task["id"], work_id)
    flexible_map = _focus(client, strict=False, bands=red_only)
    _accept_legacy(client, flexible_task["id"], flexible_map["id"])
    flex_row, flex_comp = _collected(db_session, flexible_task["id"])
    flex_placed, _general = _place(db_session, flex_row, flex_comp, TUESDAY, TUESDAY_END)
    assert flex_placed.blocks_created == 1
    block = flex_placed.proposed_blocks[0]
    assert block.start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert block.end_time <= datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def test_scoped_legacy_dated_override_replaces_the_day(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    window = _focus(
        client,
        strict=True,
        bands=_bands(("green", "14:00", "17:00"), ("red", "14:00", "15:00")),
    )
    other = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-20",
            "local_end_date": "2026-10-20",
            "timezone": "UTC",
            "strict_mode": True,
            "bands": _bands(("green", "13:00", "14:00")),
        },
    )
    assert other.status_code == 201, other.text
    applicable = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-13",
            "local_end_date": "2026-10-13",
            "timezone": "UTC",
            "strict_mode": True,
            "bands": _bands(("green", "16:00", "17:00")),
        },
    )
    assert applicable.status_code == 201, applicable.text
    stored, composed = _scoped_legacy_task(client, db_session, window["id"])
    placed, _general = _place(db_session, stored, composed, TUESDAY, TUESDAY_END)
    assert placed.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)


def test_scoped_legacy_map_edits_change_the_collected_fingerprint(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    window = _focus(
        client,
        strict=True,
        bands=_bands(("green", "14:00", "17:00"), ("red", "14:00", "15:00")),
    )
    task = _task(client)
    _policy(client, "work", "09:00", 180)
    morning = _policy(client, "work", "09:00", 180)
    _put_new_rule(client, "task", task["id"], morning["id"])
    _accept_legacy(client, task["id"], window["id"])
    _stored, before = _collected(db_session, task["id"])
    before_fp = composition_fingerprint(before)
    legacy = before_fp["day_scoped"][0]["legacy_map"]
    assert legacy["strict_mode"] is True
    assert any(band["tier"] == "red" for band in legacy["bands"])

    widened = client.patch(
        f"/api/v1/focus-windows/{window['id']}",
        json={"bands": _bands(("green", "14:00", "17:00"), ("red", "14:00", "16:00"))},
    )
    assert widened.status_code == 200, widened.text
    _stored, after_band = _collected(db_session, task["id"])
    band_fp = composition_fingerprint(after_band)
    assert band_fp != before_fp
    assert band_fp["day_scoped"][0]["id"] == before_fp["day_scoped"][0]["id"]
    placed, _general = _place(db_session, _stored, after_band, TUESDAY, TUESDAY_END)
    assert placed.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)

    loosened = client.patch(
        f"/api/v1/focus-windows/{window['id']}",
        json={"strict_mode": False},
    )
    assert loosened.status_code == 200, loosened.text
    _stored, after_strict = _collected(db_session, task["id"])
    strict_fp = composition_fingerprint(after_strict)
    assert strict_fp != band_fp
    assert strict_fp["day_scoped"][0]["legacy_map"]["strict_mode"] is False

    override = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-13",
            "local_end_date": "2026-10-13",
            "timezone": "UTC",
            "strict_mode": True,
            "bands": _bands(("yellow", "16:30", "17:30")),
        },
    )
    assert override.status_code == 201, override.text
    _stored, after_override = _collected(db_session, task["id"])
    override_fp = composition_fingerprint(after_override)
    assert override_fp != strict_fp
    assert override_fp["day_scoped"][0]["legacy_map"]["overrides"]


def test_scoped_legacy_expiry_restores_same_day_baseline(
    client: TestClient, db_session: Session
) -> None:
    """A 13:00 expiry must not keep supplying the map's 14:00 slot."""
    _prepare(client, db_session)
    afternoon = _policy(client, "work", "16:00", 60)
    task = _task(client)
    _put_new_rule(client, "task", task["id"], afternoon["id"])
    window = _focus(
        client,
        strict=True,
        bands=_bands(("green", "14:00", "15:00")),
    )
    _family(
        client,
        task["id"],
        {
            "target_family": "legacy",
            "preferred_time_window_id": window["id"],
            "expires_at": "2026-10-13T13:00:00Z",
        },
    )
    stored, composed = _collected(db_session, task["id"])
    expiry = datetime(2026, 10, 13, 13, 0, tzinfo=UTC)
    horizon_end = datetime(2026, 10, 13, 18, 0, tzinfo=UTC)
    _working, general = load_owner_policy_windows(db_session, stored.owner_id)
    clips = composition_search_windows(
        TUESDAY.date(), ZoneInfo(TZ_NAME), composed, general, working_windows=_working
    )
    assert not any(item[0] < expiry < item[1] for item in clips)
    assert not any(item[0].hour == 14 for item in clips)
    assert any(item[0].hour == 16 and item[1].hour == 17 for item in clips)
    placed, general = _place(db_session, stored, composed, expiry, horizon_end)
    assert placed.blocks_created == 1
    block = placed.proposed_blocks[0]
    assert block.start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    assert block.end_time == datetime(2026, 10, 13, 17, 0, tzinfo=UTC)
    assert not (block.start_time < expiry < block.end_time)

    crossing_map = _focus(
        client,
        strict=True,
        bands=_bands(("green", "10:00", "11:00"), ("green", "14:00", "15:00")),
    )
    crossing_task = _task(client)
    _put_new_rule(client, "task", crossing_task["id"], afternoon["id"])
    _family(
        client,
        crossing_task["id"],
        {
            "target_family": "legacy",
            "preferred_time_window_id": crossing_map["id"],
            "expires_at": "2026-10-13T13:00:00Z",
        },
    )
    crossing_row, crossing_comp = _collected(db_session, crossing_task["id"])
    morning, _general = _place(
        db_session,
        crossing_row,
        crossing_comp,
        datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        horizon_end,
    )
    assert morning.proposed_blocks[0].start_time == datetime(2026, 10, 13, 10, 0, tzinfo=UTC)
    after_slot, _general = _place(
        db_session,
        crossing_row,
        crossing_comp,
        datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        horizon_end,
    )
    assert after_slot.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)

    straddle_map = _focus(
        client,
        strict=True,
        bands=_bands(("green", "12:30", "14:30")),
    )
    straddle_task = _task(client)
    _put_new_rule(client, "task", straddle_task["id"], afternoon["id"])
    _family(
        client,
        straddle_task["id"],
        {
            "target_family": "legacy",
            "preferred_time_window_id": straddle_map["id"],
            "expires_at": "2026-10-13T13:00:00Z",
        },
    )
    straddle_row, straddle_comp = _collected(db_session, straddle_task["id"])
    straddled, _general = _place(
        db_session,
        straddle_row,
        straddle_comp,
        datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        horizon_end,
    )
    assert straddled.blocks_created >= 1
    for block in straddled.proposed_blocks:
        assert not (block.start_time < expiry < block.end_time)
        assert block.end_time <= expiry or block.start_time >= datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    assert any(
        block.start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
        for block in straddled.proposed_blocks
    )
    assert any(block.end_time == expiry for block in straddled.proposed_blocks)

    nxt, _general = _place(db_session, stored, composed, NEXT_TUESDAY, NEXT_TUESDAY_END)
    assert nxt.proposed_blocks[0].start_time == datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    wednesday = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
    next_day, _general = _place(
        db_session,
        stored,
        composed,
        wednesday,
        datetime(2026, 10, 14, 18, 0, tzinfo=UTC),
    )
    assert next_day.blocks_created == 0


def test_new_rule_and_clear_midday_expiry_restore_standing(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    afternoon = _policy(client, "work", "16:00", 60)
    _policy(client, "general", "14:00", 60)
    early = _policy(client, "personal", "14:00", 60)
    task = _task(client)
    _put_new_rule(client, "task", task["id"], afternoon["id"])
    _family(
        client,
        task["id"],
        {
            "target_family": "new_rule",
            "expires_at": "2026-10-13T13:00:00Z",
            "may": {
                "presence": "explicit",
                "rules": [{"name": "early", "policy_id": early["id"]}],
            },
        },
    )
    stored, composed = _collected(db_session, task["id"])
    placed, general = _place(
        db_session,
        stored,
        composed,
        datetime(2026, 10, 13, 13, 0, tzinfo=UTC),
        datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert (14, 15) not in _eligible_hours(composed, TUESDAY.date(), general)
    assert (16, 17) in _eligible_hours(composed, TUESDAY.date(), general)
    assert placed.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)

    cleared = _task(client)
    _put_new_rule(client, "task", cleared["id"], afternoon["id"])
    _family(
        client,
        cleared["id"],
        {"target_family": "none", "expires_at": "2026-10-13T13:00:00Z"},
    )
    cleared_row, cleared_comp = _collected(db_session, cleared["id"])
    cleared_place, cleared_general = _place(
        db_session,
        cleared_row,
        cleared_comp,
        datetime(2026, 10, 13, 13, 0, tzinfo=UTC),
        datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert (14, 15) not in _eligible_hours(cleared_comp, TUESDAY.date(), cleared_general)
    assert cleared_place.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
