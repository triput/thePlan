"""F4-W2: override fingerprints, DST placement, inheritance and cross-map."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, joinedload

from app.models import FocusWindow, ScheduleRun, Task, TimeMapOverride, UserSettings
from app.models.enums import TimeMapBandTier
from app.scheduler.input_fingerprint import SNAPSHOT_VERSION
from app.scheduler.placement import place_task
from app.scheduler.time_map_overrides import override_utc_bounds
from test_f3_w1_acceptance import (
    _create_task,
    _explanation,
    _isolate_tasks,
    _prepare_settings,
    _replan,
)
from test_f4_w1_scheduler_overrides import (
    _override_row,
    _post_override,
    _settings,
    _strict_morning_map,
)

UTC = timezone.utc


@pytest.fixture()
def scheduled(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_f3_w1_acceptance import _patch_schedule_clock

    _patch_schedule_clock(monkeypatch)


def _run_count(db_session: Session, owner_id: UUID) -> int:
    return (
        db_session.query(ScheduleRun)
        .filter(ScheduleRun.owner_id == owner_id)
        .count()
    )


def _place(
    db_session: Session,
    *,
    owner_id: UUID,
    preferred: FocusWindow,
    overrides: list[TimeMapOverride],
    settings: UserSettings,
    now: datetime,
    horizon_end: datetime,
) -> tuple[datetime, dict | None]:
    task = Task(
        owner_id=owner_id,
        title=f"f4-w2 {now.isoformat()} {uuid.uuid4().hex[:8]}",
        preferred_time_window_id=preferred.id,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    db_session.add(task)
    db_session.flush()
    result, _ = place_task(
        db_session,
        task=task,
        owner_id=owner_id,
        settings=settings,
        remaining_minutes=30,
        busy=[],
        horizon_start=now,
        horizon_end=horizon_end,
        preferred_windows={preferred.id: preferred},
        now_utc=now,
        preferred_window_id=preferred.id,
        time_map_overrides_by_map={preferred.id: overrides},
    )
    assert result.blocks_created == 1, now
    return task.scheduled_blocks[0].start_time, result.applicable_override


def test_override_create_patch_delete_stales_fingerprint_without_replan(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    """Writes mark the explanation stale. They do not start a replan.

    An explicit replan then stores the new fingerprint. An override on another
    map does not.
    """
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    map_id, _preferred = _strict_morning_map(client, db_session)
    other = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"F4-W2 other {uuid.uuid4().hex[:8]}",
            "strict_mode": True,
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
    assert other.status_code == 201, other.text
    other_id = UUID(other.json()["id"])

    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        preferred_time_window_id=str(map_id),
    )
    _isolate_tasks(db_session, client, {UUID(task["id"])})
    _replan(client, db_session, monkeypatch)

    fresh = _explanation(client, task["id"])
    assert fresh["is_stale"] is False
    snapshot = fresh["explanation"]["input_snapshot"]
    assert snapshot["v"] == SNAPSHOT_VERSION == 3
    assert snapshot["time_map_overrides"] == {"overrides": []}
    fingerprint = fresh["explanation"]["input_fingerprint"]
    run_id = fresh["explanation"]["schedule_run_id"]
    runs = _run_count(db_session, owner_id)

    created = _post_override(client, map_id, start="2026-08-11", end="2026-08-11")
    assert _run_count(db_session, owner_id) == runs
    stale = _explanation(client, task["id"])
    assert stale["is_stale"] is True
    assert stale["stale_categories"] == ["time_map_overrides"]
    assert stale["explanation"]["input_fingerprint"] == fingerprint
    assert stale["explanation"]["schedule_run_id"] == run_id

    _replan(client, db_session, monkeypatch)
    recorded = _explanation(client, task["id"])
    assert recorded["is_stale"] is False
    recorded_fp = recorded["explanation"]["input_fingerprint"]
    assert recorded_fp != fingerprint
    rows = recorded["explanation"]["input_snapshot"]["time_map_overrides"]["overrides"]
    assert [row["id"] for row in rows] == [created["id"]]
    assert rows[0]["timezone"] == "UTC"
    assert rows[0]["bands"][0]["end"] == "17:00:00"
    runs = _run_count(db_session, owner_id)

    patched = client.patch(
        f"/api/v1/focus-windows/{map_id}/overrides/{created['id']}",
        json={
            "bands": [
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "18:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert _run_count(db_session, owner_id) == runs
    after_patch = _explanation(client, task["id"])
    assert after_patch["stale_categories"] == ["time_map_overrides"]
    assert after_patch["explanation"]["input_fingerprint"] == recorded_fp

    _replan(client, db_session, monkeypatch)
    repatched = _explanation(client, task["id"])
    assert repatched["is_stale"] is False
    patched_fp = repatched["explanation"]["input_fingerprint"]
    assert patched_fp != recorded_fp
    patched_rows = repatched["explanation"]["input_snapshot"]["time_map_overrides"]["overrides"]
    assert patched_rows[0]["bands"][0]["end"] == "18:00:00"
    runs = _run_count(db_session, owner_id)

    deleted = client.delete(f"/api/v1/focus-windows/{map_id}/overrides/{created['id']}")
    assert deleted.status_code == 204, deleted.text
    assert _run_count(db_session, owner_id) == runs
    after_delete = _explanation(client, task["id"])
    assert after_delete["stale_categories"] == ["time_map_overrides"]
    assert after_delete["explanation"]["input_fingerprint"] == patched_fp

    _replan(client, db_session, monkeypatch)
    cleared = _explanation(client, task["id"])
    assert cleared["is_stale"] is False
    assert cleared["explanation"]["input_snapshot"]["time_map_overrides"] == {"overrides": []}
    assert cleared["explanation"]["input_fingerprint"] != patched_fp

    _post_override(client, other_id, start="2026-08-11", end="2026-08-13")
    quiet = _explanation(client, task["id"])
    assert quiet["is_stale"] is False
    assert quiet["stale_categories"] == []


def test_dst_placement_uses_stored_iana_for_dates_and_operator_zone_for_bands(
    client: TestClient,
    db_session: Session,
) -> None:
    """Spring-forward and fall-back keep the W1 split.

    Date match uses the override's stored IANA zone. Band 14:00 is the
    operator's wall clock, so the UTC instant follows that zone's offset
    after the transition.
    """
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    _map_id, preferred = _strict_morning_map(client, db_session)
    la = _settings(
        timezone="America/Los_Angeles",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )
    spring = _override_row(
        owner_id=owner_id,
        map_id=preferred.id,
        local_start=date(2026, 3, 8),
        local_end=date(2026, 3, 8),
        bands=[(TimeMapBandTier.green, time(14, 0), time(16, 0))],
        strict_mode=True,
        tz="America/Los_Angeles",
    )
    fall = _override_row(
        owner_id=owner_id,
        map_id=preferred.id,
        local_start=date(2026, 11, 1),
        local_end=date(2026, 11, 1),
        bands=[(TimeMapBandTier.green, time(14, 0), time(16, 0))],
        strict_mode=True,
        tz="America/Los_Angeles",
    )
    db_session.add_all([spring, fall])
    db_session.flush()

    spring_start, spring_meta = _place(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[spring],
        settings=la,
        now=datetime(2026, 3, 8, 16, 0, tzinfo=UTC),
        horizon_end=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
    )
    # 14:00 PDT, after the 02:00 spring-forward, is 21:00 UTC (not 22:00 PST).
    assert spring_start == datetime(2026, 3, 8, 21, 0, tzinfo=UTC)
    assert spring_meta is not None
    assert spring_meta["timezone"] == "America/Los_Angeles"
    assert spring_meta["effective_local_date"] == "2026-03-08"

    fall_start, fall_meta = _place(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[fall],
        settings=la,
        now=datetime(2026, 11, 1, 16, 0, tzinfo=UTC),
        horizon_end=datetime(2026, 11, 3, 0, 0, tzinfo=UTC),
    )
    # 14:00 PST, after the fall-back, is 22:00 UTC (not 21:00 PDT).
    assert fall_start == datetime(2026, 11, 1, 22, 0, tzinfo=UTC)
    assert fall_meta is not None
    assert fall_meta["effective_local_date"] == "2026-11-01"

    # Stored bounds follow the override zone across the transition.
    # Spring local day is 23h UTC; fall-back local day is 25h UTC.
    assert override_utc_bounds(spring) == (
        datetime(2026, 3, 8, 8, 0, tzinfo=UTC),
        datetime(2026, 3, 9, 7, 0, tzinfo=UTC),
    )
    assert override_utc_bounds(fall) == (
        datetime(2026, 11, 1, 7, 0, tzinfo=UTC),
        datetime(2026, 11, 2, 8, 0, tzinfo=UTC),
    )


def test_override_date_can_differ_from_operator_day_bands_stay_operator_wall_clock(
    client: TestClient,
    db_session: Session,
) -> None:
    """00:30 in New York on 9 Mar is still 8 Mar in Los Angeles.

    The 8 Mar LA override applies to that New York workday. 14:00 is New York
    wall clock (18:00 UTC), not 14:00 Pacific (21:00 UTC). The previous New
    York calendar day is 7 Mar in Los Angeles, so the override does not apply
    and the base morning band is used.
    """
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    _map_id, preferred = _strict_morning_map(client, db_session)
    ny = _settings(
        timezone="America/New_York",
        workday_start_local=time(0, 30),
        workday_minutes=900,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )
    override = _override_row(
        owner_id=owner_id,
        map_id=preferred.id,
        local_start=date(2026, 3, 8),
        local_end=date(2026, 3, 8),
        bands=[(TimeMapBandTier.green, time(14, 0), time(16, 0))],
        strict_mode=True,
        tz="America/Los_Angeles",
    )
    db_session.add(override)
    db_session.flush()

    before, before_meta = _place(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[override],
        settings=ny,
        now=datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
        horizon_end=datetime(2026, 3, 9, 0, 0, tzinfo=UTC),
    )
    assert before == datetime(2026, 3, 8, 13, 0, tzinfo=UTC)
    assert before_meta is None

    on_match, match_meta = _place(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[override],
        settings=ny,
        now=datetime(2026, 3, 9, 12, 0, tzinfo=UTC),
        horizon_end=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
    )
    assert on_match == datetime(2026, 3, 9, 18, 0, tzinfo=UTC)
    assert match_meta is not None
    assert match_meta["timezone"] == "America/Los_Angeles"
    assert match_meta["effective_local_date"] == "2026-03-08"


def test_settings_timezone_change_does_not_move_stored_bounds_bands_follow_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    map_id, preferred = _strict_morning_map(client, db_session)
    created = client.post(
        f"/api/v1/focus-windows/{map_id}/overrides",
        json={
            "local_start_date": "2026-03-08",
            "local_end_date": "2026-03-08",
            "timezone": "America/Los_Angeles",
            "strict_mode": True,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "16:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    row = (
        db_session.query(TimeMapOverride)
        .options(joinedload(TimeMapOverride.bands))
        .filter(TimeMapOverride.id == UUID(created.json()["id"]))
        .one()
    )
    bounds = override_utc_bounds(row)
    assert bounds == (
        datetime(2026, 3, 8, 8, 0, tzinfo=UTC),
        datetime(2026, 3, 9, 7, 0, tzinfo=UTC),
    )

    utc_settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )
    utc_start, utc_meta = _place(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[row],
        settings=utc_settings,
        now=datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
        horizon_end=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
    )
    assert utc_start == datetime(2026, 3, 8, 14, 0, tzinfo=UTC)
    assert utc_meta is not None
    assert utc_meta["effective_local_date"] == "2026-03-08"

    patched = client.patch("/api/v1/settings", json={"timezone": "America/New_York"})
    assert patched.status_code == 200, patched.text
    db_session.expire_all()
    row = (
        db_session.query(TimeMapOverride)
        .options(joinedload(TimeMapOverride.bands))
        .filter(TimeMapOverride.id == UUID(created.json()["id"]))
        .one()
    )
    preferred = (
        db_session.query(FocusWindow)
        .options(joinedload(FocusWindow.bands))
        .filter(FocusWindow.id == map_id)
        .one()
    )
    assert row.timezone == "America/Los_Angeles"
    assert override_utc_bounds(row) == bounds

    ny = _settings(
        timezone="America/New_York",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )
    ny_start, ny_meta = _place(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[row],
        settings=ny,
        now=datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
        horizon_end=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
    )
    # 14:00 America/New_York, not 14:00 UTC and not 14:00 Pacific.
    assert ny_start == datetime(2026, 3, 8, 18, 0, tzinfo=UTC)
    assert ny_meta is not None
    assert ny_meta["timezone"] == "America/Los_Angeles"
    assert ny_meta["effective_local_date"] == "2026-03-08"
    assert override_utc_bounds(row) == bounds


def test_f4_b_inherited_override_unbound_task_and_cross_map(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    """Project map, and epic map when the project has none. Unbound and map B stay clear."""
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    map_a, _preferred_a = _strict_morning_map(client, db_session)
    map_b, _preferred_b = _strict_morning_map(client, db_session)
    map_c, _preferred_c = _strict_morning_map(client, db_session)
    created = _post_override(client, map_a, start="2026-08-11", end="2026-08-11")
    epic_override = _post_override(
        client,
        map_c,
        start="2026-08-11",
        end="2026-08-11",
        start_time="15:00",
        end_time="17:00",
    )
    epic = client.post(
        "/api/v1/epics",
        json={
            "title": f"f4-b-epic {uuid.uuid4().hex[:8]}",
            "preferred_time_window_id": str(map_c),
        },
    )
    assert epic.status_code == 201, epic.text
    epic_project = client.post(
        "/api/v1/projects",
        json={
            "title": f"f4-b-epic-proj {uuid.uuid4().hex[:8]}",
            "epic_id": epic.json()["id"],
        },
    )
    assert epic_project.status_code == 201, epic_project.text

    project = client.post(
        "/api/v1/projects",
        json={
            "title": f"f4-b {uuid.uuid4().hex[:8]}",
            "preferred_time_window_id": str(map_a),
        },
    )
    assert project.status_code == 201, project.text

    inherited = _create_task(
        client,
        title=f"inherited {uuid.uuid4().hex[:8]}",
        project_id=project.json()["id"],
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    assert inherited["preferred_time_window_id"] is None
    unbound = _create_task(
        client,
        title=f"unbound {uuid.uuid4().hex[:8]}",
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    other = _create_task(
        client,
        title=f"map-b {uuid.uuid4().hex[:8]}",
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        preferred_time_window_id=str(map_b),
    )
    via_epic = _create_task(
        client,
        title=f"via-epic {uuid.uuid4().hex[:8]}",
        project_id=epic_project.json()["id"],
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    assert via_epic["preferred_time_window_id"] is None
    _isolate_tasks(
        db_session,
        client,
        {UUID(row["id"]) for row in (inherited, unbound, other, via_epic)},
    )
    _replan(client, db_session, monkeypatch)

    inherited_body = _explanation(client, inherited["id"])
    inherited_facts = inherited_body["explanation"]["placement_facts"]
    assert inherited_facts["placed_blocks"][0]["start_time"].startswith("2026-08-11T14:")
    assert inherited_facts["applicable_override"]["override_id"] == created["id"]
    assert inherited_facts["applicable_override"]["map_id"] == str(map_a)
    inherited_rows = inherited_body["explanation"]["input_snapshot"]["time_map_overrides"][
        "overrides"
    ]
    assert [row["id"] for row in inherited_rows] == [created["id"]]
    assert inherited_body["is_stale"] is False

    unbound_body = _explanation(client, unbound["id"])
    unbound_facts = unbound_body["explanation"]["placement_facts"]
    assert unbound_facts["placed_blocks"][0]["start_time"].startswith("2026-08-11T12:")
    assert unbound_facts["applicable_override"] is None
    assert unbound_body["explanation"]["input_snapshot"]["time_map_overrides"] == {
        "overrides": []
    }

    other_body = _explanation(client, other["id"])
    other_facts = other_body["explanation"]["placement_facts"]
    assert other_facts["placed_blocks"][0]["start_time"].startswith("2026-08-12T09:")
    assert other_facts["applicable_override"] is None
    assert other_body["explanation"]["input_snapshot"]["time_map_overrides"] == {
        "overrides": []
    }

    epic_body = _explanation(client, via_epic["id"])
    epic_facts = epic_body["explanation"]["placement_facts"]
    assert epic_facts["placed_blocks"][0]["start_time"].startswith("2026-08-11T15:")
    assert epic_facts["applicable_override"]["override_id"] == epic_override["id"]
    assert epic_facts["applicable_override"]["map_id"] == str(map_c)
    epic_rows = epic_body["explanation"]["input_snapshot"]["time_map_overrides"]["overrides"]
    assert [row["id"] for row in epic_rows] == [epic_override["id"]]


def _strict_span_map(client: TestClient, start_time: str, end_time: str) -> UUID:
    created = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"F4-B span {uuid.uuid4().hex[:8]}",
            "strict_mode": True,
            "bands": [
                {
                    "tier": "green",
                    "start_time": start_time,
                    "end_time": end_time,
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    return UUID(created.json()["id"])


def test_f4_b_task_window_beats_project_override(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    """A task map is the effective map. The project's override does not apply."""
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    project_map, _project_window = _strict_morning_map(client, db_session)
    task_map = _strict_span_map(client, "13:00", "16:00")
    _post_override(client, project_map, start="2026-08-11", end="2026-08-11")
    project = client.post(
        "/api/v1/projects",
        json={
            "title": f"f4-b-task-wins {uuid.uuid4().hex[:8]}",
            "preferred_time_window_id": str(project_map),
        },
    )
    assert project.status_code == 201, project.text
    task = _create_task(
        client,
        title=f"task-map {uuid.uuid4().hex[:8]}",
        project_id=project.json()["id"],
        preferred_time_window_id=str(task_map),
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    _isolate_tasks(db_session, client, {UUID(task["id"])})
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    facts = body["explanation"]["placement_facts"]
    assert facts["placed_blocks"][0]["start_time"].startswith("2026-08-11T13:")
    assert facts["applicable_override"] is None
    assert body["explanation"]["input_snapshot"]["time_map_overrides"] == {"overrides": []}
    assert body["explanation"]["input_snapshot"]["map_style"]["time_window_id"] == str(task_map)


def test_f4_b_project_window_beats_epic_override(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    """A project map stops the chain. The epic override does not apply."""
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    epic_map, _epic_window = _strict_morning_map(client, db_session)
    project_map = _strict_span_map(client, "16:00", "18:00")
    _post_override(
        client,
        epic_map,
        start="2026-08-11",
        end="2026-08-11",
        start_time="15:00",
        end_time="17:00",
    )
    epic = client.post(
        "/api/v1/epics",
        json={
            "title": f"f4-b-stop {uuid.uuid4().hex[:8]}",
            "preferred_time_window_id": str(epic_map),
        },
    )
    assert epic.status_code == 201, epic.text
    project = client.post(
        "/api/v1/projects",
        json={
            "title": f"f4-b-stop-proj {uuid.uuid4().hex[:8]}",
            "epic_id": epic.json()["id"],
            "preferred_time_window_id": str(project_map),
        },
    )
    assert project.status_code == 201, project.text
    task = _create_task(
        client,
        title=f"project-map {uuid.uuid4().hex[:8]}",
        project_id=project.json()["id"],
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    assert task["preferred_time_window_id"] is None
    _isolate_tasks(db_session, client, {UUID(task["id"])})
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    facts = body["explanation"]["placement_facts"]
    assert facts["placed_blocks"][0]["start_time"].startswith("2026-08-11T16:")
    assert facts["applicable_override"] is None
    assert body["explanation"]["input_snapshot"]["time_map_overrides"] == {"overrides": []}
    assert body["explanation"]["input_snapshot"]["map_style"]["time_window_id"] == str(project_map)


def test_out_of_horizon_overrides_fingerprint_without_placing_or_replanning(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    """Expired and future rows stale the fingerprint and stay out of placement.

    A later replan records them. Rewriting the same bands does not stale again
    and does not start a run.
    """
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    map_id, _preferred = _strict_morning_map(client, db_session)
    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        preferred_time_window_id=str(map_id),
    )
    _isolate_tasks(db_session, client, {UUID(task["id"])})
    _replan(client, db_session, monkeypatch)
    runs = _run_count(db_session, owner_id)

    expired = _post_override(client, map_id, start="2020-01-01", end="2020-01-02")
    future = _post_override(client, map_id, start="2026-12-01", end="2026-12-03")
    assert _run_count(db_session, owner_id) == runs
    stale = _explanation(client, task["id"])
    assert stale["is_stale"] is True
    assert stale["stale_categories"] == ["time_map_overrides"]

    _replan(client, db_session, monkeypatch)
    recorded = _explanation(client, task["id"])
    assert recorded["is_stale"] is False
    rows = recorded["explanation"]["input_snapshot"]["time_map_overrides"]["overrides"]
    assert [row["id"] for row in rows] == [expired["id"], future["id"]]
    assert rows[0]["local_start_date"] == "2020-01-01"
    assert rows[1]["local_end_date"] == "2026-12-03"
    facts = recorded["explanation"]["placement_facts"]
    assert facts["applicable_override"] is None
    assert facts["placed_blocks"][0]["start_time"].startswith("2026-08-12T09:")
    fingerprint = recorded["explanation"]["input_fingerprint"]
    runs = _run_count(db_session, owner_id)

    patched = client.patch(
        f"/api/v1/focus-windows/{map_id}/overrides/{future['id']}",
        json={
            "bands": [
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "17:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert _run_count(db_session, owner_id) == runs
    quiet = _explanation(client, task["id"])
    assert quiet["is_stale"] is False
    assert quiet["explanation"]["input_fingerprint"] == fingerprint
