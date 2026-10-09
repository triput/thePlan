"""F4-W1: scheduler reads Time Map overrides at placement time."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, joinedload

from app.models import (
    FocusWindow,
    Task,
    TimeMapBand,
    TimeMapOverride,
    TimeMapOverrideBand,
    UserSettings,
)
from app.models.enums import TimeMapBandTier
from app.scheduler.placement import _search_windows_for_day, place_task
from app.scheduler.time_map_overrides import (
    load_time_map_overrides_for_horizon,
    resolve_override_for_date,
    select_override_for_scheduling_day,
)
from test_f3_w1_acceptance import (
    FIXED_NOW,
    _create_task,
    _explanation,
    _isolate_tasks,
    _patch_schedule_clock,
    _prepare_settings,
    _replan,
)

UTC = timezone.utc


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _settings(**overrides: object) -> UserSettings:
    settings = UserSettings(owner_id=uuid.uuid4())
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _map(*bands: tuple[TimeMapBandTier, time, time], strict_mode: bool = False) -> FocusWindow:
    window = FocusWindow(owner_id=uuid.uuid4(), name="Test Map", strict_mode=strict_mode)
    for index, (tier, start, end) in enumerate(bands):
        window.bands.append(
            TimeMapBand(
                tier=tier,
                start_time=start,
                end_time=end,
                days_of_week=127,
                sort_order=index,
            )
        )
    return window


def _override_row(
    *,
    owner_id: UUID,
    map_id: UUID,
    local_start: date,
    local_end: date,
    bands: list[tuple[TimeMapBandTier, time, time]],
    strict_mode: bool = False,
    tz: str = "UTC",
) -> TimeMapOverride:
    row = TimeMapOverride(
        owner_id=owner_id,
        map_id=map_id,
        local_start_date=local_start,
        local_end_date=local_end,
        timezone=tz,
        strict_mode=strict_mode,
    )
    for index, (tier, start, end) in enumerate(bands):
        row.bands.append(
            TimeMapOverrideBand(
                tier=tier,
                start_time=start,
                end_time=end,
                days_of_week=127,
                sort_order=index,
            )
        )
    return row


def test_override_day_replaces_bands_base_unchanged_other_days() -> None:
    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
    )
    tz = __import__("zoneinfo").ZoneInfo("UTC")
    preferred = _map((TimeMapBandTier.green, time(9, 0), time(12, 0)))
    day = date(2026, 8, 11)
    override = _override_row(
        owner_id=preferred.owner_id,
        map_id=preferred.id,
        local_start=day,
        local_end=day,
        bands=[(TimeMapBandTier.green, time(14, 0), time(17, 0))],
    )

    base_windows = _search_windows_for_day(day, settings, tz, preferred)
    override_windows = _search_windows_for_day(
        day,
        settings,
        tz,
        preferred,
        day_bands=list(override.bands),
        day_strict_mode=override.strict_mode,
    )
    next_day = date(2026, 8, 12)
    next_windows = _search_windows_for_day(next_day, settings, tz, preferred)

    assert base_windows[0][0] == datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
    assert override_windows[0][0] == datetime(2026, 8, 11, 14, 0, tzinfo=UTC)
    assert next_windows[0][0] == datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def test_place_task_uses_override_only_on_matching_day(
    db_session: Session,
    client: TestClient,
) -> None:
    fixed_now = datetime(2026, 8, 11, 7, 0, tzinfo=UTC)
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])

    created_map = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"F4 map {_uid()}",
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
    assert created_map.status_code == 201, created_map.text
    map_id = UUID(created_map.json()["id"])

    preferred = (
        db_session.query(FocusWindow)
        .options(joinedload(FocusWindow.bands))
        .filter(FocusWindow.id == map_id)
        .one()
    )

    override = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=date(2026, 8, 11),
        local_end=date(2026, 8, 11),
        bands=[(TimeMapBandTier.green, time(14, 0), time(16, 0))],
        strict_mode=True,
    )
    db_session.add(override)
    db_session.flush()

    task = Task(
        owner_id=owner_id,
        title="override placement",
        preferred_time_window_id=map_id,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    db_session.add(task)
    db_session.flush()

    settings = _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )
    horizon_start = fixed_now
    horizon_end = datetime(2026, 8, 14, 23, 59, tzinfo=UTC)
    overrides_by_map = {map_id: [override]}

    result, _ = place_task(
        db_session,
        task=task,
        owner_id=owner_id,
        settings=settings,
        remaining_minutes=30,
        busy=[],
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        preferred_windows={map_id: preferred},
        now_utc=fixed_now,
        preferred_window_id=map_id,
        time_map_overrides_by_map=overrides_by_map,
    )
    assert result.blocks_created == 1
    assert result.applicable_override is not None
    assert result.applicable_override["override_id"] == str(override.id)
    assert result.applicable_override["effective_local_date"] == "2026-08-11"
    assert task.scheduled_blocks[0].start_time == datetime(2026, 8, 11, 14, 0, tzinfo=UTC)

    day_after = date(2026, 8, 12)
    from zoneinfo import ZoneInfo

    next_windows = _search_windows_for_day(
        day_after,
        settings,
        ZoneInfo("UTC"),
        preferred,
    )
    assert next_windows[0][0] == datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


@pytest.fixture()
def scheduled(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)


def test_replan_placement_facts_include_applicable_override(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])

    created_map = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"F4 replan {_uid()}",
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
    assert created_map.status_code == 201, created_map.text
    map_id = UUID(created_map.json()["id"])

    override = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=FIXED_NOW.date(),
        local_end=FIXED_NOW.date(),
        bands=[(TimeMapBandTier.green, time(14, 0), time(17, 0))],
        strict_mode=True,
    )
    db_session.add(override)
    db_session.flush()

    task = _create_task(
        client,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        preferred_time_window_id=str(map_id),
    )
    _isolate_tasks(db_session, client, {UUID(task["id"])})
    _replan(client, db_session, monkeypatch)

    body = _explanation(client, task["id"])
    facts = body["explanation"]["placement_facts"]
    assert facts["applicable_override"] is not None
    assert facts["applicable_override"]["map_id"] == str(map_id)
    assert facts["placed_blocks"][0]["start_time"].startswith("2026-08-11T14:")


def _strict_morning_map(client: TestClient, db_session: Session) -> tuple[UUID, FocusWindow]:
    created = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"F4-A map {_uid()}",
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
    assert created.status_code == 201, created.text
    map_id = UUID(created.json()["id"])
    preferred = (
        db_session.query(FocusWindow)
        .options(joinedload(FocusWindow.bands))
        .filter(FocusWindow.id == map_id)
        .one()
    )
    return map_id, preferred


def _utc_settings() -> UserSettings:
    return _settings(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=600,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
    )


def _place_on_day(
    db_session: Session,
    *,
    owner_id: UUID,
    preferred: FocusWindow,
    overrides: list[TimeMapOverride],
    day: date,
) -> tuple[datetime, dict | None]:
    task = Task(
        owner_id=owner_id,
        title=f"f4-a {day.isoformat()} {_uid()}",
        preferred_time_window_id=preferred.id,
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
    )
    db_session.add(task)
    db_session.flush()
    now = datetime.combine(day, time(7, 0), tzinfo=UTC)
    result, _ = place_task(
        db_session,
        task=task,
        owner_id=owner_id,
        settings=_utc_settings(),
        remaining_minutes=30,
        busy=[],
        horizon_start=now,
        horizon_end=datetime(2026, 8, 20, 23, 59, tzinfo=UTC),
        preferred_windows={preferred.id: preferred},
        now_utc=now,
        preferred_window_id=preferred.id,
        time_map_overrides_by_map={preferred.id: overrides},
    )
    assert result.blocks_created == 1, day
    return task.scheduled_blocks[0].start_time, result.applicable_override


def _assert_base_morning(client: TestClient, map_id: UUID) -> None:
    base = client.get(f"/api/v1/focus-windows/{map_id}")
    assert base.status_code == 200, base.text
    body = base.json()
    assert body["strict_mode"] is True
    assert [(band["start_time"], band["end_time"]) for band in body["bands"]] == [
        ("09:00", "12:00")
    ]


def test_f4_a_one_day_override_leaves_base_outside_that_day(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    map_id, preferred = _strict_morning_map(client, db_session)
    only = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=date(2026, 8, 11),
        local_end=date(2026, 8, 11),
        bands=[(TimeMapBandTier.green, time(14, 0), time(16, 0))],
        strict_mode=True,
    )
    db_session.add(only)
    db_session.flush()

    before, before_meta = _place_on_day(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[only],
        day=date(2026, 8, 10),
    )
    on_day, on_meta = _place_on_day(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[only],
        day=date(2026, 8, 11),
    )
    after, after_meta = _place_on_day(
        db_session,
        owner_id=owner_id,
        preferred=preferred,
        overrides=[only],
        day=date(2026, 8, 12),
    )

    assert before == datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    assert before_meta is None
    assert on_day == datetime(2026, 8, 11, 14, 0, tzinfo=UTC)
    assert on_meta is not None
    assert on_meta["override_id"] == str(only.id)
    assert on_meta["effective_local_date"] == "2026-08-11"
    assert after == datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    assert after_meta is None
    _assert_base_morning(client, map_id)


def test_f4_a_multiday_inclusive_range_restores_base_outside(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    map_id, preferred = _strict_morning_map(client, db_session)
    span = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=date(2026, 8, 11),
        local_end=date(2026, 8, 13),
        bands=[(TimeMapBandTier.green, time(14, 0), time(17, 0))],
        strict_mode=True,
    )
    db_session.add(span)
    db_session.flush()
    expected = {
        date(2026, 8, 10): (datetime(2026, 8, 10, 9, 0, tzinfo=UTC), False),
        date(2026, 8, 11): (datetime(2026, 8, 11, 14, 0, tzinfo=UTC), True),
        date(2026, 8, 12): (datetime(2026, 8, 12, 14, 0, tzinfo=UTC), True),
        date(2026, 8, 13): (datetime(2026, 8, 13, 14, 0, tzinfo=UTC), True),
        date(2026, 8, 14): (datetime(2026, 8, 14, 9, 0, tzinfo=UTC), False),
    }
    for day, (start, uses_override) in expected.items():
        placed, meta = _place_on_day(
            db_session,
            owner_id=owner_id,
            preferred=preferred,
            overrides=[span],
            day=day,
        )
        assert placed == start
        if uses_override:
            assert meta is not None
            assert meta["override_id"] == str(span.id)
            assert meta["local_start_date"] == "2026-08-11"
            assert meta["local_end_date"] == "2026-08-13"
            assert meta["effective_local_date"] == day.isoformat()
        else:
            assert meta is None
    _assert_base_morning(client, map_id)


def test_f4_a_resolver_uses_date_not_list_order() -> None:
    """Non-overlapping rows listed backwards still match the day they cover.

    Corrupt overlap (the API rejects this) prefers the earlier start, then id,
    matching ``resolve_override_for_date``.
    """
    settings = _utc_settings()
    map_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    later = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=date(2026, 8, 12),
        local_end=date(2026, 8, 13),
        bands=[(TimeMapBandTier.green, time(16, 0), time(17, 0))],
    )
    earlier = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=date(2026, 8, 10),
        local_end=date(2026, 8, 11),
        bands=[(TimeMapBandTier.green, time(15, 0), time(16, 0))],
    )
    later.id = UUID(int=2)
    earlier.id = UUID(int=1)
    backwards = [later, earlier]

    assert (
        select_override_for_scheduling_day(backwards, day=date(2026, 8, 10), settings=settings)
        is earlier
    )
    assert (
        select_override_for_scheduling_day(backwards, day=date(2026, 8, 13), settings=settings)
        is later
    )
    assert select_override_for_scheduling_day(backwards, day=date(2026, 8, 14), settings=settings) is None

    duplicate_late = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=date(2026, 8, 11),
        local_end=date(2026, 8, 11),
        bands=[(TimeMapBandTier.green, time(14, 0), time(15, 0))],
    )
    duplicate_early = _override_row(
        owner_id=owner_id,
        map_id=map_id,
        local_start=date(2026, 8, 11),
        local_end=date(2026, 8, 11),
        bands=[(TimeMapBandTier.green, time(14, 0), time(15, 0))],
    )
    duplicate_late.id = UUID(int=9)
    duplicate_early.id = UUID(int=3)
    chosen = select_override_for_scheduling_day(
        [duplicate_late, duplicate_early],
        day=date(2026, 8, 11),
        settings=settings,
    )
    assert chosen is duplicate_early
    resolved = resolve_override_for_date(
        {map_id: [duplicate_late, duplicate_early]},
        map_id,
        date(2026, 8, 11),
    )
    assert resolved is duplicate_early


def _post_override(
    client: TestClient,
    map_id: UUID,
    *,
    start: str,
    end: str,
    start_time: str = "14:00",
    end_time: str = "17:00",
) -> dict:
    response = client.post(
        f"/api/v1/focus-windows/{map_id}/overrides",
        json={
            "local_start_date": start,
            "local_end_date": end,
            "timezone": "UTC",
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
    assert response.status_code == 201, response.text
    return response.json()


def test_f4_a_replan_multiday_inside_override_outside_base(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    """Collect loads the override; placement uses it on each inclusive day only."""
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    map_id, _preferred = _strict_morning_map(client, db_session)
    created = _post_override(client, map_id, start="2026-08-11", end="2026-08-13")

    def _task(soft: str | None) -> dict:
        extra: dict[str, object] = {
            "estimated_duration_minutes": 30,
            "preferred_time_window_id": str(map_id),
        }
        if soft is not None:
            extra["soft_target_at"] = soft
        return _create_task(client, **extra)

    start_day = _task(None)
    middle = _task("2026-08-12T08:00:00Z")
    end_day = _task("2026-08-13T08:00:00Z")
    after = _task("2026-08-14T08:00:00Z")
    _isolate_tasks(
        db_session,
        client,
        {UUID(row["id"]) for row in (start_day, middle, end_day, after)},
    )
    _replan(client, db_session, monkeypatch)

    def _facts(task: dict) -> dict:
        return _explanation(client, task["id"])["explanation"]["placement_facts"]

    start_facts = _facts(start_day)
    assert start_facts["placed_blocks"][0]["start_time"].startswith("2026-08-11T14:")
    assert start_facts["applicable_override"]["override_id"] == created["id"]
    assert start_facts["applicable_override"]["effective_local_date"] == "2026-08-11"
    assert start_facts["applicable_override"]["local_end_date"] == "2026-08-13"

    middle_facts = _facts(middle)
    assert middle_facts["placed_blocks"][0]["start_time"].startswith("2026-08-12T14:")
    assert middle_facts["applicable_override"]["effective_local_date"] == "2026-08-12"

    end_facts = _facts(end_day)
    assert end_facts["placed_blocks"][0]["start_time"].startswith("2026-08-13T14:")
    assert end_facts["applicable_override"]["effective_local_date"] == "2026-08-13"

    after_facts = _facts(after)
    assert after_facts["placed_blocks"][0]["start_time"].startswith("2026-08-14T09:")
    assert after_facts["applicable_override"] is None
    _assert_base_morning(client, map_id)


def test_f4_a_expired_override_stays_listed_and_base_places(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scheduled: None,
) -> None:
    _prepare_settings(
        client,
        workday_start_local="08:00",
        workday_minutes=600,
        auto_defer_enabled=False,
    )
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    map_id, _preferred = _strict_morning_map(client, db_session)
    expired = _post_override(
        client,
        map_id,
        start="2026-08-01",
        end="2026-08-10",
        start_time="14:00",
        end_time="17:00",
    )
    listed = client.get(f"/api/v1/focus-windows/{map_id}/overrides")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [expired["id"]]

    horizon_start = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    loaded = load_time_map_overrides_for_horizon(
        db_session,
        owner_id,
        {map_id},
        horizon_start,
        datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
    )
    assert loaded[map_id] == []

    task = _create_task(
        client,
        estimated_duration_minutes=30,
        preferred_time_window_id=str(map_id),
    )
    _isolate_tasks(db_session, client, {UUID(task["id"])})
    _replan(client, db_session, monkeypatch)
    facts = _explanation(client, task["id"])["explanation"]["placement_facts"]
    assert facts["placed_blocks"][0]["start_time"].startswith("2026-08-12T09:")
    assert facts["applicable_override"] is None
    _assert_base_morning(client, map_id)
