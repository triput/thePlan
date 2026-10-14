"""S2-V3 window materializer, placer cutover, pin containment, fingerprint."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import FocusWindow, TimeMapBand, TimeMapOverride, TimeMapOverrideBand
from app.models.enums import TimeMapBandTier
from app.scheduler.availability_materializer import (
    PolicyWindow,
    materialize_windows_for_local_date,
    occurrence_span,
    resolve_recurring_wall,
)
from app.scheduler.input_fingerprint import (
    SCHEDULING_ACTIVATIONS,
    STALE_AVAILABILITY,
    STALE_SCHEDULING_ACTIVATION,
    assemble_snapshot,
    diff_stale_categories,
    owner_snapshot_predates_activation,
)
from app.scheduler.pin_reservation import _uncovered_outside_working
from app.scheduler.placement import _search_windows_for_day, place_task
from app.scheduler.time_map_overrides import (
    override_intersects_horizon,
    override_utc_bounds,
)
from app.services.availability_cutover_activation import (
    ACTIVATION_TOKEN,
    availability_activation_revision,
)

UTC = timezone.utc
LA = ZoneInfo("America/Los_Angeles")
TOKYO = ZoneInfo("Asia/Tokyo")


def _window(weekday: int, start: time, duration: int) -> PolicyWindow:
    seconds = start.hour * 3600 + start.minute * 60 + start.second
    return PolicyWindow(
        weekday=weekday,
        start_time=start,
        duration_minutes=duration,
        ends_next_day=seconds + duration * 60 >= 86400,
    )


def _settings(**overrides: object) -> SimpleNamespace:
    base = dict(
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
    base.update(overrides)
    return SimpleNamespace(**base)


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


def _map(*bands: tuple[TimeMapBandTier, time, time], strict: bool = False) -> FocusWindow:
    window = FocusWindow(id=uuid4(), owner_id=uuid4(), name="Map", strict_mode=strict)
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


def _override(
    preferred: FocusWindow,
    *,
    start: date,
    end: date,
    tz: str,
    bands: list[tuple[TimeMapBandTier, time, time]],
    strict: bool = False,
) -> TimeMapOverride:
    row = TimeMapOverride(
        id=uuid4(),
        owner_id=preferred.owner_id,
        map_id=preferred.id,
        local_start_date=start,
        local_end_date=end,
        timezone=tz,
        strict_mode=strict,
    )
    for index, (tier, band_start, band_end) in enumerate(bands):
        row.bands.append(
            TimeMapOverrideBand(
                tier=tier,
                start_time=band_start,
                end_time=band_end,
                days_of_week=127,
                sort_order=index,
            )
        )
    return row


def _place(
    *,
    task: SimpleNamespace,
    settings: SimpleNamespace,
    now: datetime,
    horizon_end: datetime,
    working: list[PolicyWindow],
    general: list[PolicyWindow],
    preferred: FocusWindow | None = None,
    overrides: list[TimeMapOverride] | None = None,
    minutes: int = 30,
) -> tuple:
    window_id = preferred.id if preferred is not None else None
    task.preferred_time_window_id = window_id
    by_map = {}
    if preferred is not None and overrides:
        by_map[preferred.id] = overrides
    result, _busy = place_task(
        None,  # type: ignore[arg-type]
        task=task,  # type: ignore[arg-type]
        owner_id=uuid4(),
        settings=settings,  # type: ignore[arg-type]
        remaining_minutes=minutes,
        busy=[],
        horizon_start=now,
        horizon_end=horizon_end,
        preferred_windows={preferred.id: preferred} if preferred is not None else {},
        now_utc=now,
        preferred_window_id=window_id,
        persist_blocks=False,
        time_map_overrides_by_map=by_map or None,
        working_windows=working,
        general_windows=general,
    )
    blocks = result.proposed_blocks or []
    return result, blocks


def test_materializer_split_windows_and_overnight_ownership() -> None:
    tz = ZoneInfo("UTC")
    monday = date(2026, 10, 12)
    tuesday = date(2026, 10, 13)
    split = [
        _window(0, time(9, 0), 180),
        _window(0, time(14, 0), 120),
    ]
    spans = materialize_windows_for_local_date(split, monday, tz)
    assert [(item.start.hour, item.end.hour) for item in spans] == [(9, 12), (14, 16)]

    overnight = _window(0, time(22, 0), 240)
    monday_spans = materialize_windows_for_local_date([overnight], monday, tz)
    assert monday_spans[0].start == datetime(2026, 10, 12, 22, 0, tzinfo=UTC)
    assert monday_spans[0].end == datetime(2026, 10, 13, 2, 0, tzinfo=UTC)
    assert monday_spans[0].owner_date == monday

    carry = materialize_windows_for_local_date([overnight], tuesday, tz)
    assert len(carry) == 1
    assert carry[0].start == datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
    assert carry[0].end == datetime(2026, 10, 13, 2, 0, tzinfo=UTC)
    assert carry[0].owner_date == monday


def test_dst_gap_snaps_boundary_and_skips_zero_duration() -> None:
    tz = LA
    spring = date(2026, 3, 8)
    window = _window(spring.weekday(), time(1, 30), 120)
    span = occurrence_span(window, spring, tz)
    assert span is not None
    assert span.start == datetime(2026, 3, 8, 9, 30, tzinfo=UTC)
    assert span.end == datetime(2026, 3, 8, 10, 30, tzinfo=UTC)
    assert span.end - span.start == timedelta(hours=1)

    skipped = occurrence_span(_window(spring.weekday(), time(2, 15), 20), spring, tz)
    assert skipped is None

    folded = occurrence_span(_window(date(2026, 11, 1).weekday(), time(1, 15), 30), date(2026, 11, 1), tz)
    assert folded is not None
    assert folded.start == datetime(2026, 11, 1, 8, 15, tzinfo=UTC)
    assert folded.end == datetime(2026, 11, 1, 8, 45, tzinfo=UTC)
    local = resolve_recurring_wall(date(2026, 11, 1), time(1, 15), tz).astimezone(tz)
    assert local.utcoffset() == timedelta(hours=-7)
    assert local.fold == 0


def test_a11c_tuesday_run_sees_monday_overnight_tail() -> None:
    now = datetime(2026, 10, 13, 0, 30, tzinfo=UTC)
    general = [_window(0, time(22, 0), 240)]
    result, blocks = _place(
        task=_task(),
        settings=_settings(),
        now=now,
        horizon_end=datetime(2026, 10, 13, 4, 0, tzinfo=UTC),
        working=[],
        general=general,
        minutes=30,
    )
    assert result.blocks_created == 1
    assert blocks[0].start_time == now
    assert blocks[0].end_time == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)


def test_a9_unclassified_uses_general_only() -> None:
    working = [_window(day, time(9, 0), 480) for day in range(5)]
    general = [_window(1, time(13, 0), 60)]
    now = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    _result, blocks = _place(
        task=_task(),
        settings=_settings(workweek_days=5),
        now=now,
        horizon_end=datetime(2026, 10, 14, 0, 0, tzinfo=UTC),
        working=working,
        general=general,
        minutes=30,
    )
    assert blocks[0].start_time == datetime(2026, 10, 13, 13, 0, tzinfo=UTC)

    monday = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
    missed, missed_blocks = _place(
        task=_task(),
        settings=_settings(),
        now=monday,
        horizon_end=datetime(2026, 10, 13, 0, 0, tzinfo=UTC),
        working=working,
        general=general,
        minutes=30,
    )
    assert missed.blocks_created == 0
    assert missed_blocks == []


def test_a10_mapped_clips_to_working_not_general() -> None:
    preferred = _map((TimeMapBandTier.green, time(9, 0), time(12, 0)), strict=True)
    working = [_window(1, time(10, 0), 60)]
    wide_general = [_window(day, time(8, 0), 600) for day in range(7)]
    now = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
    _result, blocks = _place(
        task=_task(),
        settings=_settings(),
        now=now,
        horizon_end=datetime(2026, 10, 14, 0, 0, tzinfo=UTC),
        working=working,
        general=wide_general,
        preferred=preferred,
        minutes=30,
    )
    assert blocks[0].start_time == datetime(2026, 10, 13, 10, 0, tzinfo=UTC)
    assert blocks[0].end_time == datetime(2026, 10, 13, 10, 30, tzinfo=UTC)

    _again, again_blocks = _place(
        task=_task(),
        settings=_settings(),
        now=now,
        horizon_end=datetime(2026, 10, 14, 0, 0, tzinfo=UTC),
        working=working,
        general=[],
        preferred=preferred,
        minutes=30,
    )
    assert again_blocks[0].start_time == blocks[0].start_time


def test_a11_tue_sat_working_ignores_monday_first_mirror() -> None:
    preferred = _map(strict=False)
    working = [_window(day, time(11, 0), 240) for day in (1, 2, 3, 4, 5)]
    settings = _settings(workweek_days=5, workday_start_local=time(9, 0), workday_minutes=480)
    monday = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
    missed, _blocks = _place(
        task=_task(),
        settings=settings,
        now=monday,
        horizon_end=datetime(2026, 10, 13, 0, 0, tzinfo=UTC),
        working=working,
        general=[_window(0, time(9, 0), 480)],
        preferred=preferred,
        minutes=30,
    )
    assert missed.blocks_created == 0

    tuesday = datetime(2026, 10, 13, 10, 0, tzinfo=UTC)
    _placed, blocks = _place(
        task=_task(),
        settings=settings,
        now=tuesday,
        horizon_end=datetime(2026, 10, 14, 0, 0, tzinfo=UTC),
        working=working,
        general=[],
        preferred=preferred,
        minutes=30,
    )
    assert blocks[0].start_time == datetime(2026, 10, 13, 11, 0, tzinfo=UTC)


def test_pin_containment_uses_working_windows_including_carry_in() -> None:
    settings = _settings(workweek_days=5)
    tue_sat = [_window(day, time(11, 0), 240) for day in (1, 2, 3, 4, 5)]
    monday_pin = _uncovered_outside_working(
        datetime(2026, 10, 12, 11, 0, tzinfo=UTC),
        datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
        settings,
        tue_sat,
    )
    assert monday_pin == [
        (
            datetime(2026, 10, 12, 11, 0, tzinfo=UTC),
            datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
        )
    ]
    tuesday_pin = _uncovered_outside_working(
        datetime(2026, 10, 13, 11, 0, tzinfo=UTC),
        datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        settings,
        tue_sat,
    )
    assert tuesday_pin == []

    overnight = [_window(0, time(22, 0), 240)]
    tail = _uncovered_outside_working(
        datetime(2026, 10, 13, 0, 30, tzinfo=UTC),
        datetime(2026, 10, 13, 1, 30, tzinfo=UTC),
        settings,
        overnight,
    )
    assert tail == []


def test_a11f_tokyo_override_splits_la_day_and_horizon() -> None:
    override_day = date(2026, 10, 13)
    preferred = _map((TimeMapBandTier.green, time(7, 0), time(12, 0)), strict=False)
    row = _override(
        preferred,
        start=override_day,
        end=override_day,
        tz="Asia/Tokyo",
        bands=[(TimeMapBandTier.green, time(7, 0), time(7, 30))],
        strict=True,
    )
    start, end = override_utc_bounds(row)
    assert start == datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 13, 15, 0, tzinfo=UTC)

    la_noon = datetime(2026, 10, 13, 19, 0, tzinfo=UTC)
    assert override_intersects_horizon(
        row, la_noon, la_noon + timedelta(hours=4)
    ) is False
    assert override_intersects_horizon(
        row,
        datetime(2026, 10, 13, 14, 0, tzinfo=UTC),
        datetime(2026, 10, 13, 20, 0, tzinfo=UTC),
    ) is True

    settings = _settings(timezone="America/Los_Angeles")
    working = [_window(1, time(7, 0), 300)]
    tz = LA
    windows = _search_windows_for_day(
        override_day,
        settings,  # type: ignore[arg-type]
        tz,
        preferred,
        policy_windows=working,
        overrides=[row],
    )
    green = [(item[0], item[1]) for item in windows if item[2] == "green"]
    assert green == [
        (datetime(2026, 10, 13, 14, 0, tzinfo=UTC), datetime(2026, 10, 13, 14, 30, tzinfo=UTC)),
        (datetime(2026, 10, 13, 15, 0, tzinfo=UTC), datetime(2026, 10, 13, 19, 0, tzinfo=UTC)),
    ]

    now = datetime(2026, 10, 13, 14, 0, tzinfo=UTC)
    _result, blocks = _place(
        task=_task(min_block_duration_minutes=60, max_block_duration_minutes=60),
        settings=settings,
        now=now,
        horizon_end=datetime(2026, 10, 13, 20, 0, tzinfo=UTC),
        working=working,
        general=[],
        preferred=preferred,
        overrides=[row],
        minutes=60,
    )
    assert blocks[0].start_time == datetime(2026, 10, 13, 15, 0, tzinfo=UTC)

    wide = _override(
        preferred,
        start=override_day,
        end=override_day,
        tz="Asia/Tokyo",
        bands=[(TimeMapBandTier.green, time(7, 0), time(12, 0))],
        strict=False,
    )
    _span, spanned = _place(
        task=_task(min_block_duration_minutes=15),
        settings=settings,
        now=now,
        horizon_end=datetime(2026, 10, 13, 20, 0, tzinfo=UTC),
        working=working,
        general=[],
        preferred=preferred,
        overrides=[wide],
        minutes=120,
    )
    assert spanned[0].start_time == datetime(2026, 10, 13, 14, 0, tzinfo=UTC)
    assert spanned[0].end_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)

    monday = date(2026, 10, 12)
    monday_override = _override(
        preferred,
        start=override_day,
        end=override_day,
        tz="Asia/Tokyo",
        bands=[(TimeMapBandTier.green, time(8, 0), time(8, 30))],
        strict=True,
    )
    monday_windows = _search_windows_for_day(
        monday,
        settings,  # type: ignore[arg-type]
        tz,
        preferred,
        policy_windows=[_window(0, time(7, 0), 300)],
        overrides=[monday_override],
    )
    assert monday_windows[0][0] == datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
    assert monday_windows[0][1] == datetime(2026, 10, 12, 15, 30, tzinfo=UTC)


def test_a11f_stored_zone_dst_day_is_not_24_hours_and_rows_stay_put() -> None:
    preferred = _map()
    row = _override(
        preferred,
        start=date(2026, 3, 8),
        end=date(2026, 3, 8),
        tz="America/Los_Angeles",
        bands=[],
    )
    start, end = override_utc_bounds(row)
    assert end - start == timedelta(hours=23)
    stored_tz = row.timezone
    stored_start = row.local_start_date
    settings = _settings(timezone="America/Los_Angeles")
    settings.timezone = "Asia/Tokyo"
    assert row.timezone == stored_tz
    assert row.local_start_date == stored_start
    assert override_utc_bounds(row) == (start, end)


def test_a11d_availability_fingerprint_uses_passed_windows_and_activation_token() -> None:
    assert ACTIVATION_TOKEN in SCHEDULING_ACTIVATIONS
    assert availability_activation_revision(4) == 5
    working = [_window(1, time(11, 0), 240)]
    general = [_window(1, time(13, 0), 60)]
    kwargs = dict(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
        timezone_name="UTC",
        upcoming_horizon_days=7,
        workday_start_local=time(8, 0),
        workday_minutes=480,
        workweek_days=5,
        inter_block_buffer_minutes=5,
        working_windows=working,
        general_windows=general,
    )
    stored = assemble_snapshot(**kwargs)
    assert "workday_start_local" not in stored["timezone_horizon_workweek"]
    assert "workweek_days" not in stored["timezone_horizon_workweek"]
    assert stored["availability"]["working"][0]["start_time"].startswith("11:00")
    ids = stored["scheduling_activation"]["ids"]
    assert ACTIVATION_TOKEN in ids
    from app.services.composition_cutover_activation import (
        ACTIVATION_TOKEN as V4_ACTIVATION_TOKEN,
    )
    from app.services.day_scoped_ranking_cutover_activation import (
        ACTIVATION_TOKEN as V4B_ACTIVATION_TOKEN,
    )

    assert V4_ACTIVATION_TOKEN in ids
    assert ids[-1] == V4B_ACTIVATION_TOKEN
    assert (
        ids.index(ACTIVATION_TOKEN)
        < ids.index(V4_ACTIVATION_TOKEN)
        < ids.index(V4B_ACTIVATION_TOKEN)
    )

    drifted = assemble_snapshot(**{**kwargs, "general_windows": [_window(1, time(15, 0), 60)]})
    assert diff_stale_categories(stored, drifted) == [STALE_AVAILABILITY]

    pre = {
        "snapshot_version": 4,
        "scheduling_activation": {
            "ids": ["s2-v1-duration-bounds", "s2-v2-pin-reservation"]
        },
    }
    assert owner_snapshot_predates_activation(pre) is True
    assert owner_snapshot_predates_activation(
        {"snapshot_version": 4, "scheduling_activation": {"ids": list(SCHEDULING_ACTIVATIONS)}}
    ) is False
    missing = dict(stored)
    missing["scheduling_activation"] = {"ids": ["s2-v1-duration-bounds", "s2-v2-pin-reservation"]}
    assert STALE_SCHEDULING_ACTIVATION in diff_stale_categories(missing, stored)
