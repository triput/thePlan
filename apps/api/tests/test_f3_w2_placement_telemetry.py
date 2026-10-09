"""F3-W2 placement failure hints. Additive on PlacementResult; no persist."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from app.models import FocusWindow, Task, TimeMapBand, UserSettings
from app.models.enums import TimeMapBandTier
from app.scheduler.busy_map import BusyInterval
from app.scheduler.placement import (
    HINT_BUSY_CONFLICT,
    HINT_DAILY_CAP,
    HINT_DEADLINE_LIMIT,
    HINT_MIN_BLOCK,
    HINT_NO_TIME_MAP_INTERVAL,
    HINT_PINNED_CONFLICT,
    HINT_RED_EXCLUSION,
    place_one_block,
)
from app.scheduler.reasons import (
    REASON_UNPLACED_BUSY_CONFLICT,
    REASON_UNPLACED_DEADLINE_LIMIT,
    REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK,
    REASON_UNPLACED_NO_TIME_MAP_INTERVAL,
    REASON_UNPLACED_PINNED_CONFLICT,
    REASON_UNPLACED_PROJECT_DAILY_CAP,
    REASON_UNPLACED_RED_EXCLUSION,
)

NOW = datetime(2026, 8, 11, 7, 0, tzinfo=timezone.utc)
HORIZON_END = NOW + timedelta(days=1)


def _settings(**overrides: object) -> UserSettings:
    settings = UserSettings(
        owner_id=uuid4(),
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=540,
        workweek_days=7,
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
        auto_defer_enabled=False,
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _task(**overrides: object) -> Task:
    task = Task(
        id=uuid4(),
        owner_id=uuid4(),
        title="telemetry",
        estimated_duration_minutes=30,
        min_block_duration_minutes=30,
        max_block_duration_minutes=30,
        project_id=uuid4(),
    )
    for key, value in overrides.items():
        setattr(task, key, value)
    return task


def _window(*bands: tuple[TimeMapBandTier, time, time], strict_mode: bool = False) -> FocusWindow:
    window = FocusWindow(id=uuid4(), owner_id=uuid4(), name="Map", strict_mode=strict_mode)
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


def _place(task: Task, settings: UserSettings, **kwargs: object):
    window = kwargs.pop("window", None)
    windows = {}
    window_id = None
    if window is not None:
        windows = {window.id: window}
        window_id = window.id
    return place_one_block(
        None,  # type: ignore[arg-type]
        task=task,
        owner_id=task.owner_id,
        settings=settings,
        remaining_minutes=kwargs.pop("remaining_minutes", task.estimated_duration_minutes),  # type: ignore[arg-type]
        busy=kwargs.pop("busy", []),  # type: ignore[arg-type]
        horizon_start=NOW,
        horizon_end=HORIZON_END,
        preferred_windows=windows,
        now_utc=NOW,
        preferred_window_id=window_id,
        project_daily_usage=kwargs.pop("project_daily_usage", {}),  # type: ignore[arg-type]
        daily_cap=kwargs.pop("daily_cap", None),  # type: ignore[arg-type]
        persist_blocks=False,
    )


def test_past_deadline_is_deadline_limit() -> None:
    task = _task(deadline_at=datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc))
    result, _ = _place(task, _settings())
    assert result.blocks_created == 0
    assert result.last_failure is not None
    assert result.last_failure["code"] == HINT_DEADLINE_LIMIT
    assert result.last_failure["reason_code"] == REASON_UNPLACED_DEADLINE_LIMIT
    assert result.observed_constraints[0] == REASON_UNPLACED_DEADLINE_LIMIT
    assert result.pass_hints[0]["params"]["remaining_minutes"] == 30


def test_daily_cap_hint() -> None:
    result, _ = _place(_task(), _settings(), daily_cap=10)
    assert result.last_failure is not None
    assert result.last_failure["code"] == HINT_DAILY_CAP
    assert result.last_failure["reason_code"] == REASON_UNPLACED_PROJECT_DAILY_CAP
    assert result.last_failure["params"]["daily_cap_minutes"] == 10
    assert result.last_failure["params"]["local_date"] == "2026-08-11"


def test_min_block_when_workday_is_shorter_than_mbl() -> None:
    settings = _settings(workday_minutes=20)
    task = _task(min_block_duration_minutes=30, estimated_duration_minutes=30)
    result, _ = _place(task, settings)
    assert result.last_failure is not None
    assert result.last_failure["code"] == HINT_MIN_BLOCK
    assert result.last_failure["reason_code"] == REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK
    assert result.last_failure["params"]["min_block_minutes"] == 30


def test_strict_empty_map_is_no_time_map_interval() -> None:
    window = _window(strict_mode=True)
    result, _ = _place(_task(), _settings(), window=window)
    assert result.last_failure is not None
    assert result.last_failure["code"] == HINT_NO_TIME_MAP_INTERVAL
    assert result.last_failure["reason_code"] == REASON_UNPLACED_NO_TIME_MAP_INTERVAL
    assert result.last_failure["params"]["strict_mode"] is True


def test_red_covering_workday_is_red_exclusion() -> None:
    window = _window((TimeMapBandTier.red, time(8, 0), time(17, 0)))
    result, _ = _place(_task(), _settings(), window=window)
    assert result.last_failure is not None
    assert result.last_failure["code"] == HINT_RED_EXCLUSION
    assert result.last_failure["reason_code"] == REASON_UNPLACED_RED_EXCLUSION


def test_pinned_and_external_are_distinct() -> None:
    day = datetime(2026, 8, 11, tzinfo=timezone.utc)
    pinned = BusyInterval(day.replace(hour=8), day.replace(hour=12), source="pinned")
    external = BusyInterval(day.replace(hour=12), day.replace(hour=17), source="external")
    result, _ = _place(_task(), _settings(), busy=[pinned, external])
    codes = [hint["code"] for hint in result.pass_hints]
    assert HINT_PINNED_CONFLICT in codes
    assert HINT_BUSY_CONFLICT in codes
    assert result.last_failure is not None
    assert result.last_failure["code"] == HINT_PINNED_CONFLICT
    assert result.last_failure["reason_code"] == REASON_UNPLACED_PINNED_CONFLICT
    by_code = {hint["code"]: hint for hint in result.pass_hints}
    assert by_code[HINT_BUSY_CONFLICT]["reason_code"] == REASON_UNPLACED_BUSY_CONFLICT
    assert by_code[HINT_BUSY_CONFLICT]["params"]["sources"] == ["external"]
    assert by_code[HINT_PINNED_CONFLICT]["params"]["sources"] == ["pinned"]


def test_scheduled_occupancy_is_not_a_busy_or_pinned_conflict() -> None:
    day = datetime(2026, 8, 11, tzinfo=timezone.utc)
    scheduled = BusyInterval(day.replace(hour=8), day.replace(hour=17), source="scheduled")
    result, _ = _place(_task(), _settings(), busy=[scheduled])
    assert result.blocks_created == 0
    assert result.last_failure is None
    assert result.pass_hints == []


def test_placed_pass_has_no_last_failure() -> None:
    task = _task(estimated_duration_minutes=60, max_block_duration_minutes=30, min_block_duration_minutes=30)
    result, _ = _place(task, _settings(), remaining_minutes=60)
    assert result.blocks_created == 1
    assert result.remaining_minutes == 30
    assert result.last_failure is None
    assert result.pass_hints == []
