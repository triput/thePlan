"""V3-D1: overnight Working tails keep owner_date and paint bands on the interval date."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import FocusWindow, TimeMapBand, TimeMapOverride, TimeMapOverrideBand
from app.models.enums import TimeMapBandTier
from app.scheduler.availability_materializer import (
    PolicyWindow,
    materialize_windows_for_local_date,
)
from app.scheduler.placement import (
    _search_windows_for_day,
    _spans_split_by_overrides,
    place_task,
    split_span_for_band_evaluation,
)
from app.scheduler.time_map_overrides import override_utc_bounds

UTC = timezone.utc
MONDAY = date(2026, 10, 12)
TUESDAY = date(2026, 10, 13)
MONDAY_BIT = 1 << 0
TUESDAY_BIT = 1 << 1
# POSIX Etc/GMT+1 is UTC−1, so Tuesday 00:00 there is Tuesday 01:00 UTC.
TAIL_OVERRIDE_TZ = "Etc/GMT+1"


def _window(weekday: int, start: time, duration: int) -> PolicyWindow:
    seconds = start.hour * 3600 + start.minute * 60 + start.second
    return PolicyWindow(
        weekday=weekday,
        start_time=start,
        duration_minutes=duration,
        ends_next_day=seconds + duration * 60 >= 86400,
    )


def _overnight() -> PolicyWindow:
    return _window(0, time(22, 0), 240)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=480,
        workweek_days=5,
        inter_block_buffer_minutes=0,
        auto_defer_enabled=False,
        default_min_block_duration_minutes=15,
        default_max_block_duration_minutes=240,
        default_max_block_unbounded=False,
    )


def _task(**overrides: object) -> SimpleNamespace:
    base = dict(
        id=uuid4(),
        project_id=None,
        deadline_at=None,
        soft_target_at=None,
        preferred_time_window_id=None,
        estimated_duration_minutes=30,
        remaining_minutes=30,
        worked_minutes=0,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        max_block_unbounded=False,
        keep_in_one_block=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _map(
    *bands: tuple[TimeMapBandTier, time, time, int],
    strict: bool = False,
) -> FocusWindow:
    window = FocusWindow(id=uuid4(), owner_id=uuid4(), name="Map", strict_mode=strict)
    for index, (tier, start, end, days) in enumerate(bands):
        window.bands.append(
            TimeMapBand(
                tier=tier,
                start_time=start,
                end_time=end,
                days_of_week=days,
                sort_order=index,
            )
        )
    return window


def _override(
    preferred: FocusWindow,
    *,
    bands: list[tuple[TimeMapBandTier, time, time, int]],
    strict: bool = False,
) -> TimeMapOverride:
    row = TimeMapOverride(
        id=uuid4(),
        owner_id=preferred.owner_id,
        map_id=preferred.id,
        local_start_date=TUESDAY,
        local_end_date=TUESDAY,
        timezone=TAIL_OVERRIDE_TZ,
        strict_mode=strict,
    )
    for index, (tier, start, end, days) in enumerate(bands):
        row.bands.append(
            TimeMapOverrideBand(
                tier=tier,
                start_time=start,
                end_time=end,
                days_of_week=days,
                sort_order=index,
            )
        )
    return row


def _place(
    *,
    now: datetime,
    preferred: FocusWindow,
    overrides: list[TimeMapOverride] | None = None,
    minutes: int = 30,
    horizon_end: datetime | None = None,
) -> tuple:
    window_id = preferred.id
    task = _task()
    task.preferred_time_window_id = window_id
    by_map = {window_id: overrides} if overrides else None
    result, _busy = place_task(
        None,  # type: ignore[arg-type]
        task=task,  # type: ignore[arg-type]
        owner_id=uuid4(),
        settings=_settings(),  # type: ignore[arg-type]
        remaining_minutes=minutes,
        busy=[],
        horizon_start=now,
        horizon_end=horizon_end or datetime(2026, 10, 13, 4, 0, tzinfo=UTC),
        preferred_windows={window_id: preferred},
        now_utc=now,
        preferred_window_id=window_id,
        persist_blocks=False,
        time_map_overrides_by_map=by_map,
        working_windows=[_overnight()],
        general_windows=[],
    )
    return result, result.proposed_blocks or []


def _search(day: date, preferred: FocusWindow, overrides: list[TimeMapOverride] | None = None):
    return _search_windows_for_day(
        day,
        _settings(),  # type: ignore[arg-type]
        ZoneInfo("UTC"),
        preferred,
        policy_windows=[_overnight()],
        overrides=overrides,
    )


def _overlaps(windows, start: datetime, end: datetime, tier: str | None = None) -> list:
    return [
        item
        for item in windows
        if item[0] < end and item[1] > start and (tier is None or item[2] == tier)
    ]


def test_v3_d1_owner_date_stays_monday_while_intervals_split_at_midnight() -> None:
    tz = ZoneInfo("UTC")
    monday_spans = materialize_windows_for_local_date([_overnight()], MONDAY, tz)
    assert monday_spans[0].owner_date == MONDAY
    assert monday_spans[0].start == datetime(2026, 10, 12, 22, 0, tzinfo=UTC)
    assert monday_spans[0].end == datetime(2026, 10, 13, 2, 0, tzinfo=UTC)

    carry = materialize_windows_for_local_date([_overnight()], TUESDAY, tz)
    assert carry[0].owner_date == MONDAY
    assert carry[0].start == datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
    assert carry[0].end == datetime(2026, 10, 13, 2, 0, tzinfo=UTC)

    split = split_span_for_band_evaluation(monday_spans[0].start, monday_spans[0].end, tz)
    assert [(item.local_date, item.start, item.end) for item in split] == [
        (MONDAY, datetime(2026, 10, 12, 22, 0, tzinfo=UTC), datetime(2026, 10, 13, 0, 0, tzinfo=UTC)),
        (TUESDAY, datetime(2026, 10, 13, 0, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC)),
    ]
    assert monday_spans[0].owner_date == MONDAY

    pieces = _spans_split_by_overrides(monday_spans, None, tz)
    assert [piece.owner_date for piece, _interval in pieces] == [MONDAY, MONDAY]
    assert [interval.local_date for _piece, interval in pieces] == [MONDAY, TUESDAY]

    carry_pieces = _spans_split_by_overrides(carry, None, tz)
    assert carry_pieces[0][0].owner_date == MONDAY
    assert carry_pieces[0][1].local_date == TUESDAY


def test_v3_d1_monday_start_non_strict_red_does_not_enter_tuesday() -> None:
    preferred = _map(
        (TimeMapBandTier.green, time(22, 0), time(23, 0), MONDAY_BIT),
        (TimeMapBandTier.red, time(0, 0), time(2, 0), TUESDAY_BIT),
        strict=False,
    )
    windows = _search(MONDAY, preferred)
    assert _overlaps(windows, datetime(2026, 10, 12, 22, 0, tzinfo=UTC), datetime(2026, 10, 12, 23, 0, tzinfo=UTC), "green")
    assert _overlaps(windows, datetime(2026, 10, 12, 23, 0, tzinfo=UTC), datetime(2026, 10, 13, 0, 0, tzinfo=UTC), "neutral")
    assert _overlaps(windows, datetime(2026, 10, 13, 0, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC)) == []

    _early, early_blocks = _place(now=datetime(2026, 10, 12, 22, 0, tzinfo=UTC), preferred=preferred)
    assert early_blocks[0].start_time == datetime(2026, 10, 12, 22, 0, tzinfo=UTC)
    assert early_blocks[0].end_time == datetime(2026, 10, 12, 22, 30, tzinfo=UTC)
    assert early_blocks[0].tier == "green"

    _late, late_blocks = _place(now=datetime(2026, 10, 12, 23, 45, tzinfo=UTC), preferred=preferred)
    assert len(late_blocks) == 1
    assert late_blocks[0].start_time == datetime(2026, 10, 12, 23, 45, tzinfo=UTC)
    assert late_blocks[0].end_time == datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
    assert late_blocks[0].tier == "neutral"


def test_v3_d1_tuesday_carry_in_non_strict_red_places_nothing() -> None:
    preferred = _map(
        (TimeMapBandTier.red, time(0, 0), time(2, 0), TUESDAY_BIT),
        strict=False,
    )
    windows = _search(TUESDAY, preferred)
    assert windows == []

    result, blocks = _place(now=datetime(2026, 10, 13, 0, 30, tzinfo=UTC), preferred=preferred)
    assert blocks == []
    assert result.blocks_created == 0
    assert result.last_failure is not None
    assert result.last_failure["code"] == "red_exclusion"
    assert "unplaced_red_exclusion" in result.observed_constraints


def test_v3_d1_monday_start_strict_tuesday_green() -> None:
    preferred = _map(
        (TimeMapBandTier.green, time(0, 0), time(2, 0), TUESDAY_BIT),
        strict=True,
    )
    windows = _search(MONDAY, preferred)
    assert windows == [
        (
            datetime(2026, 10, 13, 0, 0, tzinfo=UTC),
            datetime(2026, 10, 13, 2, 0, tzinfo=UTC),
            "green",
        )
    ]

    _result, blocks = _place(now=datetime(2026, 10, 12, 22, 0, tzinfo=UTC), preferred=preferred)
    assert blocks[0].start_time == datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
    assert blocks[0].end_time == datetime(2026, 10, 13, 0, 30, tzinfo=UTC)
    assert blocks[0].tier == "green"


def test_v3_d1_tuesday_carry_in_strict_tuesday_green() -> None:
    preferred = _map(
        (TimeMapBandTier.green, time(0, 0), time(2, 0), TUESDAY_BIT),
        strict=True,
    )
    windows = _search(TUESDAY, preferred)
    assert windows == [
        (
            datetime(2026, 10, 13, 0, 0, tzinfo=UTC),
            datetime(2026, 10, 13, 2, 0, tzinfo=UTC),
            "green",
        )
    ]

    _result, blocks = _place(now=datetime(2026, 10, 13, 0, 30, tzinfo=UTC), preferred=preferred)
    assert blocks[0].start_time == datetime(2026, 10, 13, 0, 30, tzinfo=UTC)
    assert blocks[0].end_time == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    assert blocks[0].tier == "green"


def test_v3_d1_override_bands_apply_on_the_tail() -> None:
    preferred = _map(
        (TimeMapBandTier.red, time(0, 0), time(2, 0), TUESDAY_BIT),
        strict=True,
    )
    row = _override(
        preferred,
        bands=[(TimeMapBandTier.green, time(0, 0), time(2, 0), TUESDAY_BIT)],
        strict=True,
    )
    start, end = override_utc_bounds(row)
    assert start == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 14, 1, 0, tzinfo=UTC)

    tz = ZoneInfo("UTC")
    span = materialize_windows_for_local_date([_overnight()], MONDAY, tz)[0]
    pieces = _spans_split_by_overrides([span], [row], tz)
    assert [(piece.owner_date, interval.local_date, interval.override, interval.start, interval.end) for piece, interval in pieces] == [
        (MONDAY, MONDAY, None, datetime(2026, 10, 12, 22, 0, tzinfo=UTC), datetime(2026, 10, 13, 0, 0, tzinfo=UTC)),
        (MONDAY, TUESDAY, None, datetime(2026, 10, 13, 0, 0, tzinfo=UTC), datetime(2026, 10, 13, 1, 0, tzinfo=UTC)),
        (MONDAY, TUESDAY, row, datetime(2026, 10, 13, 1, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC)),
    ]

    monday_windows = _search(MONDAY, preferred, [row])
    assert monday_windows == [
        (
            datetime(2026, 10, 13, 1, 0, tzinfo=UTC),
            datetime(2026, 10, 13, 2, 0, tzinfo=UTC),
            "green",
        )
    ]
    tuesday_windows = _search(TUESDAY, preferred, [row])
    assert tuesday_windows == monday_windows

    _from_monday, monday_blocks = _place(
        now=datetime(2026, 10, 12, 22, 0, tzinfo=UTC),
        preferred=preferred,
        overrides=[row],
    )
    assert monday_blocks[0].start_time == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    assert monday_blocks[0].end_time == datetime(2026, 10, 13, 1, 30, tzinfo=UTC)
    assert monday_blocks[0].tier == "green"

    _from_tuesday, tuesday_blocks = _place(
        now=datetime(2026, 10, 13, 0, 30, tzinfo=UTC),
        preferred=preferred,
        overrides=[row],
    )
    assert tuesday_blocks[0].start_time == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    assert tuesday_blocks[0].end_time == datetime(2026, 10, 13, 1, 30, tzinfo=UTC)
    assert tuesday_blocks[0].tier == "green"
