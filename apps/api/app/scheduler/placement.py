"""Slice-and-fit placement for auto-scheduled blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypeAlias
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import (
    FocusWindow,
    ScheduleStatus,
    ScheduledBlock,
    Task,
    TimeMapBand,
    TimeMapOverride,
    UserSettings,
)
from app.scheduler.availability_materializer import (
    MaterializedSpan,
    coerce_policy_windows,
    materialize_windows_for_local_date,
    merge_utc_intervals,
)
from app.scheduler.time_map_overrides import (
    applicable_override_payload,
    effective_day_map,
    override_covering_instant,
    override_utc_bounds,
)
from app.models.enums import TimeMapBandTier
from app.scheduler.busy_map import (
    BusyInterval,
    FixedBufferConflict,
    add_busy_interval,
    expand_fixed_busy_for_placement,
    fixed_buffer_conflicts,
    interval_overlaps_busy,
)
from app.scheduler.reasons import (
    REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER,
    REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT,
    REASON_UNPLACED_BUSY_CONFLICT,
    REASON_UNPLACED_DEADLINE_LIMIT,
    REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK,
    REASON_UNPLACED_KEEP_IN_ONE_CONFLICT,
    REASON_UNPLACED_NO_TIME_MAP_INTERVAL,
    REASON_UNPLACED_PINNED_CONFLICT,
    REASON_UNPLACED_PROJECT_DAILY_CAP,
    REASON_UNPLACED_RED_EXCLUSION,
)
from app.services.chunking_effective import resolve_block_bounds
from app.services.busy_intervals import TimeInterval, ranges_overlap, subtract_intervals_from_range


ProjectDailyUsage: TypeAlias = dict[tuple[date, UUID | None], int]


@dataclass(frozen=True)
class ProposedBlock:
    task_id: UUID
    start_time: datetime
    end_time: datetime
    slice_minutes: int
    tier: str | None = None
    preferred_window_id: UUID | None = None


@dataclass
class PlacementResult:
    blocks_created: int
    overbooked: bool
    remaining_minutes: int = 0
    last_block_end: datetime | None = None
    last_placed_tier: str | None = None
    proposed_blocks: list[ProposedBlock] | None = None
    # Jules' reason codes, priority order. First entry is the primary constraint.
    observed_constraints: list[str] = field(default_factory=list)
    # ``last_failure`` is set only when this call placed zero blocks.
    # ``pass_hints`` lists those failure hints. A pre-existing fixed-buffer
    # conflict is also listed there, including when this call still placed.
    last_failure: dict[str, Any] | None = None
    pass_hints: list[dict[str, Any]] = field(default_factory=list)
    applicable_override: dict[str, Any] | None = None


# Short codes Jules maps onto ``unplaced_*`` reason codes. Do not rename without
# updating ``_HINT_BY_REASON`` and the placement_facts copy in calculate.
HINT_DEADLINE_LIMIT = "deadline_limit"
HINT_DAILY_CAP = "daily_cap"
HINT_MIN_BLOCK = "min_block"
HINT_NO_TIME_MAP_INTERVAL = "no_time_map_interval"
HINT_RED_EXCLUSION = "red_exclusion"
HINT_BUSY_CONFLICT = "busy_conflict"
HINT_PINNED_CONFLICT = "pinned_conflict"
HINT_FIXED_BUFFER_CONFLICT = "fixed_buffer_conflict"

_HINT_BY_REASON: dict[str, str] = {
    REASON_UNPLACED_DEADLINE_LIMIT: HINT_DEADLINE_LIMIT,
    REASON_UNPLACED_PROJECT_DAILY_CAP: HINT_DAILY_CAP,
    REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK: HINT_MIN_BLOCK,
    REASON_UNPLACED_NO_TIME_MAP_INTERVAL: HINT_NO_TIME_MAP_INTERVAL,
    REASON_UNPLACED_RED_EXCLUSION: HINT_RED_EXCLUSION,
    REASON_UNPLACED_BUSY_CONFLICT: HINT_BUSY_CONFLICT,
    REASON_UNPLACED_PINNED_CONFLICT: HINT_PINNED_CONFLICT,
    REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER: HINT_FIXED_BUFFER_CONFLICT,
}


def _day_cap_allows(
    day: date,
    project_id: UUID | None,
    slice_minutes: int,
    usage: ProjectDailyUsage | None,
    cap: int | None,
) -> bool:
    if cap is None or usage is None:
        return True
    used = usage.get((day, project_id), 0)
    return used + slice_minutes <= cap


def _record_project_minutes(
    day: date,
    project_id: UUID | None,
    minutes: int,
    usage: ProjectDailyUsage | None,
) -> None:
    if usage is None:
        return
    key = (day, project_id)
    usage[key] = usage.get(key, 0) + minutes


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_workday(day: date, workweek_days: int) -> bool:
    """Monday-first reading of the deprecated ``workweek_days`` column.

    Not eligibility. The placer and pin containment use stored Working/General
    windows via ``availability_materializer``.
    """
    return day.weekday() < workweek_days


def workday_bounds(day: date, settings: UserSettings, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, settings.workday_start_local, tzinfo=tz)
    end_local = start_local + timedelta(minutes=settings.workday_minutes)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def band_bounds(
    day: date,
    band: TimeMapBand,
    tz: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    """Wall-clock band on ``day`` in the operator timezone ``tz``.

    F4 overrides replace which bands apply. Those start/end times are still
    read here, including on spring-forward and fall-back days. The override's
    stored IANA zone selects the local dates (``effective_local_date_for_scheduling_day``)
    and the UTC span (``override_utc_bounds``). It does not reinterpret band
    times. Changing ``settings.timezone`` moves these instants and leaves
    stored override bounds where they were.
    """
    if not (band.days_of_week & (1 << day.weekday())):
        return None
    start_local = datetime.combine(day, band.start_time, tzinfo=tz)
    end_local = datetime.combine(day, band.end_time, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def intersect_ranges(
    a_start: datetime,
    a_end: datetime,
    b_start: datetime,
    b_end: datetime,
) -> tuple[datetime, datetime] | None:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if start < end:
        return start, end
    return None


def _subtract_red_from_clips(
    clips: list[tuple[datetime, datetime]],
    red_intervals: list[TimeInterval],
) -> list[tuple[datetime, datetime]]:
    if not clips or not red_intervals:
        return clips
    result: list[tuple[datetime, datetime]] = []
    for start, end in clips:
        for piece in subtract_intervals_from_range(start, end, red_intervals):
            result.append((piece.start, piece.end))
    return result


def _merge_tier_windows(
    windows: list[tuple[datetime, datetime, str | None]],
) -> list[tuple[datetime, datetime, str | None]]:
    """Union contiguous same-tier clips so one block can cross a boundary."""
    grouped: dict[str | None, list[tuple[datetime, datetime]]] = {
        "green": [],
        "yellow": [],
        "neutral": [],
        None: [],
    }
    for start, end, tier in windows:
        grouped.setdefault(tier, []).append((start, end))
    ordered: list[tuple[datetime, datetime, str | None]] = []
    for tier in ("green", "yellow", "neutral", None):
        for start, end in merge_utc_intervals(grouped.get(tier, [])):
            ordered.append((start, end, tier))
    return ordered


def _spans_split_by_overrides(
    spans: list[MaterializedSpan],
    overrides: list[TimeMapOverride] | None,
) -> list[tuple[MaterializedSpan, TimeMapOverride | None]]:
    """Split each span at stored-zone override bounds. Inclusive start, exclusive end."""
    if not spans:
        return []
    if not overrides:
        return [(span, None) for span in spans]
    cuts: list[datetime] = []
    for row in overrides:
        start, end = override_utc_bounds(row)
        cuts.extend((start, end))
    pieces: list[tuple[MaterializedSpan, TimeMapOverride | None]] = []
    for span in spans:
        points = [span.start, span.end]
        for cut in cuts:
            if span.start < cut < span.end:
                points.append(cut)
        points = sorted(set(points))
        for left, right in zip(points, points[1:]):
            if left >= right:
                continue
            piece = MaterializedSpan(start=left, end=right, owner_date=span.owner_date)
            pieces.append((piece, override_covering_instant(overrides, left)))
    return pieces


def _windows_from_bands(
    spans: list[MaterializedSpan],
    bands: list[Any],
    strict_mode: bool,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime, str | None]]:
    """Map bands ∩ eligibility spans. Neutral is each span minus that span's red."""
    collected: list[tuple[datetime, datetime, str | None]] = []
    for span in spans:
        green: list[tuple[datetime, datetime]] = []
        yellow: list[tuple[datetime, datetime]] = []
        red: list[tuple[datetime, datetime]] = []
        for band in bands:
            bounds = band_bounds(span.owner_date, band, tz)
            if bounds is None:
                continue
            hit = intersect_ranges(span.start, span.end, bounds[0], bounds[1])
            if hit is None:
                continue
            if band.tier == TimeMapBandTier.green:
                green.append(hit)
            elif band.tier == TimeMapBandTier.yellow:
                yellow.append(hit)
            elif band.tier == TimeMapBandTier.red:
                red.append(hit)
        red_intervals = [TimeInterval(start, end) for start, end in red]
        for start, end in _subtract_red_from_clips(green, red_intervals):
            collected.append((start, end, "green"))
        for start, end in _subtract_red_from_clips(yellow, red_intervals):
            collected.append((start, end, "yellow"))
        if not strict_mode:
            for item in subtract_intervals_from_range(span.start, span.end, red_intervals):
                collected.append((item.start, item.end, "neutral"))
    return _merge_tier_windows(collected)


def _search_windows_for_day(
    day: date,
    settings: UserSettings,
    tz: ZoneInfo,
    preferred: FocusWindow | None,
    *,
    day_bands: list[TimeMapBand] | list[Any] | None = None,
    day_strict_mode: bool | None = None,
    policy_windows: list[Any] | None = None,
    overrides: list[TimeMapOverride] | None = None,
) -> list[tuple[datetime, datetime, str | None]]:
    """Eligible clips on ``day``.

    ``policy_windows`` is General for an unclassified task and Working for a
    mapped one. ``None`` falls back to the deprecated Monday-first settings
    span so direct unit calls keep their fixture. ``day_bands`` is the direct
    test hook that substitutes one band list for the whole day; production
    passes ``overrides`` and splits at stored-zone bounds instead.
    """
    rows = coerce_policy_windows(policy_windows, settings)
    spans = materialize_windows_for_local_date(rows, day, tz)
    if not spans:
        return []
    if preferred is None and day_bands is None:
        merged = merge_utc_intervals([(span.start, span.end) for span in spans])
        return [(start, end, None) for start, end in merged]

    if day_bands is not None:
        strict_mode = (
            day_strict_mode
            if day_strict_mode is not None
            else (preferred.strict_mode if preferred is not None else False)
        )
        return _windows_from_bands(spans, list(day_bands), strict_mode, tz)

    pieces = _spans_split_by_overrides(spans, overrides)
    collected: list[tuple[datetime, datetime, str | None]] = []
    for piece, row in pieces:
        if preferred is None:
            collected.append((piece.start, piece.end, None))
            continue
        bands, strict_mode = effective_day_map(preferred, row, piece.owner_date)
        collected.extend(_windows_from_bands([piece], bands, strict_mode, tz))
    return _merge_tier_windows(collected)


def effective_soft_target(
    task: Task,
    settings: UserSettings,
    horizon_start: datetime,
    horizon_end: datetime,
) -> datetime | None:
    """Slide soft target for placement only when auto_defer is enabled."""
    soft = task.soft_target_at
    if soft is None:
        return None
    soft = _ensure_utc(soft)
    if not settings.auto_defer_enabled:
        return soft
    if soft < horizon_start or soft >= horizon_end:
        return horizon_start
    return soft


def find_slot(
    busy: list[BusyInterval],
    window_start: datetime,
    window_end: datetime,
    duration_minutes: int,
    not_before: datetime,
    deadline: datetime | None,
    buffer_minutes: int = 0,
) -> tuple[datetime, datetime] | None:
    if duration_minutes <= 0:
        return None

    # Fixed busy (pins, external events) blocks the buffer on both sides.
    # Scheduled intervals already include one pad on each side, so they are
    # not expanded here — that would double the auto–auto gap.
    if buffer_minutes > 0:
        busy = expand_fixed_busy_for_placement(busy, buffer_minutes)

    search_start = max(window_start, not_before)
    if deadline is not None:
        deadline = _ensure_utc(deadline)
        if search_start >= deadline:
            return None

    relevant = [
        item
        for item in busy
        if ranges_overlap(search_start, window_end, item.start, item.end)
    ]
    relevant.sort(key=lambda item: item.start)

    cursor = search_start
    duration = timedelta(minutes=duration_minutes)

    for item in relevant:
        if cursor + duration <= item.start and cursor < window_end:
            slot_end = cursor + duration
            if deadline is not None and slot_end > deadline:
                return None
            if slot_end <= window_end:
                return cursor, slot_end
        if item.end > cursor:
            cursor = item.end

    if cursor + duration <= window_end:
        slot_end = cursor + duration
        if deadline is not None and slot_end > deadline:
            return None
        return cursor, slot_end
    return None


def _slice_size(
    remaining: int,
    mbl: int,
    max_block: int,
) -> int | None:
    if remaining <= 0:
        return None
    if remaining <= max_block:
        target = remaining
    else:
        target = max_block
    if target >= mbl:
        return target
    if 0 < remaining < mbl:
        return remaining
    return None


def _busy_for_sources(busy: list[BusyInterval], *sources: str) -> list[BusyInterval]:
    allowed = set(sources)
    return [item for item in busy if item.source in allowed]


def _max_contiguous_minutes(
    busy: list[BusyInterval],
    window_start: datetime,
    window_end: datetime,
    not_before: datetime,
    deadline: datetime | None,
    buffer_minutes: int = 0,
) -> int:
    if buffer_minutes > 0:
        busy = expand_fixed_busy_for_placement(busy, buffer_minutes)
    search_start = max(window_start, not_before)
    if deadline is not None:
        deadline = _ensure_utc(deadline)
        if search_start >= deadline:
            return 0
        window_end = min(window_end, deadline)
    if search_start >= window_end:
        return 0

    relevant = [
        item
        for item in busy
        if ranges_overlap(search_start, window_end, item.start, item.end)
    ]
    relevant.sort(key=lambda item: item.start)
    cursor = search_start
    best = 0
    for item in relevant:
        if item.start > cursor:
            gap = int((item.start - cursor).total_seconds() // 60)
            if gap > best:
                best = gap
        if item.end > cursor:
            cursor = item.end
    if cursor < window_end:
        gap = int((window_end - cursor).total_seconds() // 60)
        if gap > best:
            best = gap
    return best


def _overrides_for_window(
    preferred: FocusWindow | None,
    window_id: UUID | None,
    overrides_by_map: dict[UUID, list[TimeMapOverride]] | None,
) -> list[TimeMapOverride]:
    if preferred is None or window_id is None or not overrides_by_map:
        return []
    return list(overrides_by_map.get(window_id) or [])


def _day_search_windows(
    day: date,
    settings: UserSettings,
    tz: ZoneInfo,
    preferred: FocusWindow | None,
    window_id: UUID | None,
    overrides_by_map: dict[UUID, list[TimeMapOverride]] | None,
    working_windows: list[Any] | None,
    general_windows: list[Any] | None,
) -> list[tuple[datetime, datetime, str | None]]:
    policy = general_windows if preferred is None else working_windows
    return _search_windows_for_day(
        day,
        settings,
        tz,
        preferred,
        policy_windows=policy,
        overrides=_overrides_for_window(preferred, window_id, overrides_by_map),
    )


def _map_block_reason(
    day: date,
    settings: UserSettings,
    tz: ZoneInfo,
    preferred: FocusWindow,
    *,
    policy_windows: list[Any] | None = None,
    overrides: list[TimeMapOverride] | None = None,
) -> str | None:
    """Why a bound map offers no allowed window on a day that has eligibility.

    ``None`` means the day still has a placeable clip, or the policy has no
    span that day (not a map failure). ``no_time_map_interval`` means the map
    never painted an allowed band on those spans. ``red_exclusion`` means red
    removed every clip that would have been allowed.
    """
    windows = _search_windows_for_day(
        day,
        settings,
        tz,
        preferred,
        policy_windows=policy_windows,
        overrides=overrides,
    )
    if windows:
        return None
    rows = coerce_policy_windows(policy_windows, settings)
    spans = materialize_windows_for_local_date(rows, day, tz)
    if not spans:
        return None
    pieces = _spans_split_by_overrides(spans, overrides)
    saw_allowed = False
    saw_red = False
    for piece, row in pieces:
        bands, strict_mode = effective_day_map(preferred, row, piece.owner_date)
        green_or_yellow = False
        red_hit = False
        for band in bands:
            bounds = band_bounds(piece.owner_date, band, tz)
            if bounds is None:
                continue
            if intersect_ranges(piece.start, piece.end, bounds[0], bounds[1]) is None:
                continue
            if band.tier == TimeMapBandTier.red:
                red_hit = True
            elif band.tier in {TimeMapBandTier.green, TimeMapBandTier.yellow}:
                green_or_yellow = True
        if red_hit:
            saw_red = True
        if green_or_yellow or not strict_mode:
            saw_allowed = True
    if saw_allowed and saw_red:
        return HINT_RED_EXCLUSION
    if saw_red and not saw_allowed:
        return HINT_RED_EXCLUSION
    return HINT_NO_TIME_MAP_INTERVAL


def _observe_unplaced_constraints(
    *,
    task: Task,
    settings: UserSettings,
    remaining: int,
    busy: list[BusyInterval],
    horizon_start: datetime,
    horizon_end: datetime,
    preferred: FocusWindow | None,
    preferred_window_id: UUID | None,
    overrides_by_map: dict[UUID, list[TimeMapOverride]] | None,
    now_utc: datetime,
    not_before: datetime,
    deadline: datetime | None,
    mbl: int,
    max_block: int,
    daily_cap: int | None,
    project_daily_usage: ProjectDailyUsage | None,
    day_cap_blocked: bool,
    cap_blocked_day: date | None,
    buffer_minutes: int = 0,
    working_windows: list[Any] | None = None,
    general_windows: list[Any] | None = None,
) -> list[str]:
    """Observed placement constraints for F3 (not a unique root-cause proof)."""
    if remaining <= 0:
        return []

    observed: list[str] = []
    tz = ZoneInfo(settings.timezone)
    deadline_utc = _ensure_utc(deadline) if deadline is not None else None

    if deadline_utc is not None:
        deadline_binds = not_before >= deadline_utc or deadline_utc <= horizon_start
        if not deadline_binds:
            slice_minutes = _slice_size(remaining, mbl, max_block)
            if slice_minutes is not None:
                fits_with_deadline = False
                fits_without_deadline = False
                day = now_utc.astimezone(tz).date()
                end_day = horizon_end.astimezone(tz).date()
                while day <= end_day:
                    for window_start, window_end, _tier in _day_search_windows(
                        day,
                        settings,
                        tz,
                        preferred,
                        preferred_window_id,
                        overrides_by_map,
                        working_windows,
                        general_windows,
                    ):
                        if window_end <= horizon_start or window_start >= horizon_end:
                            continue
                        search_start = max(window_start, horizon_start)
                        search_end = min(window_end, horizon_end)
                        if (
                            find_slot(
                                busy,
                                search_start,
                                search_end,
                                slice_minutes,
                                not_before,
                                deadline_utc,
                                buffer_minutes=buffer_minutes,
                            )
                            is not None
                        ):
                            fits_with_deadline = True
                        if (
                            find_slot(
                                busy,
                                search_start,
                                search_end,
                                slice_minutes,
                                not_before,
                                None,
                                buffer_minutes=buffer_minutes,
                            )
                            is not None
                        ):
                            fits_without_deadline = True
                    day += timedelta(days=1)
                deadline_binds = fits_without_deadline and not fits_with_deadline
        if deadline_binds:
            observed.append(REASON_UNPLACED_DEADLINE_LIMIT)

    if day_cap_blocked and daily_cap is not None:
        observed.append(REASON_UNPLACED_PROJECT_DAILY_CAP)

    day = now_utc.astimezone(tz).date()
    end_day = horizon_end.astimezone(tz).date()
    allowed_windows = 0
    max_gap = 0
    while day <= end_day:
        windows = _day_search_windows(
            day,
            settings,
            tz,
            preferred,
            preferred_window_id,
            overrides_by_map,
            working_windows,
            general_windows,
        )
        for window_start, window_end, _tier in windows:
            if window_end <= horizon_start or window_start >= horizon_end:
                continue
            allowed_windows += 1
            gap = _max_contiguous_minutes(
                busy,
                max(window_start, horizon_start),
                min(window_end, horizon_end),
                not_before,
                deadline_utc,
                buffer_minutes=buffer_minutes,
            )
            if gap > max_gap:
                max_gap = gap
        day += timedelta(days=1)

    if preferred is not None and allowed_windows == 0:
        map_reasons: set[str] = set()
        day = now_utc.astimezone(tz).date()
        while day <= end_day:
            reason = _map_block_reason(
                day,
                settings,
                tz,
                preferred,
                policy_windows=working_windows,
                overrides=_overrides_for_window(
                    preferred, preferred_window_id, overrides_by_map
                ),
            )
            if reason is not None:
                map_reasons.add(reason)
            day += timedelta(days=1)
        if HINT_NO_TIME_MAP_INTERVAL in map_reasons:
            observed.append(REASON_UNPLACED_NO_TIME_MAP_INTERVAL)
        if HINT_RED_EXCLUSION in map_reasons:
            observed.append(REASON_UNPLACED_RED_EXCLUSION)

    need = min(max_block, remaining) if remaining > max_block else remaining
    if need >= mbl and max_gap > 0 and max_gap < mbl:
        observed.append(REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK)

    slice_minutes = _slice_size(remaining, mbl, max_block)
    if slice_minutes is not None and allowed_windows > 0:
        without_external = _busy_for_sources(busy, "pinned", "scheduled")
        without_pinned = _busy_for_sources(busy, "external", "scheduled")
        has_external = any(item.source == "external" for item in busy)
        has_pinned = any(item.source == "pinned" for item in busy)
        day = now_utc.astimezone(tz).date()
        fits_if_ignore_external = False
        fits_if_ignore_pinned = False
        while day <= end_day:
            for window_start, window_end, _tier in _day_search_windows(
                day,
                settings,
                tz,
                preferred,
                preferred_window_id,
                overrides_by_map,
                working_windows,
                general_windows,
            ):
                if window_end <= horizon_start or window_start >= horizon_end:
                    continue
                search_start = max(window_start, horizon_start)
                search_end = min(window_end, horizon_end)
                full_slot = find_slot(
                    busy,
                    search_start,
                    search_end,
                    slice_minutes,
                    not_before,
                    deadline_utc,
                    buffer_minutes=buffer_minutes,
                )
                if full_slot is not None:
                    continue
                if has_external and (
                    find_slot(
                        without_external,
                        search_start,
                        search_end,
                        slice_minutes,
                        not_before,
                        deadline_utc,
                        buffer_minutes=buffer_minutes,
                    )
                    is not None
                ):
                    fits_if_ignore_external = True
                if has_pinned and (
                    find_slot(
                        without_pinned,
                        search_start,
                        search_end,
                        slice_minutes,
                        not_before,
                        deadline_utc,
                        buffer_minutes=buffer_minutes,
                    )
                    is not None
                ):
                    fits_if_ignore_pinned = True
            day += timedelta(days=1)
        # Dropping the source reveals a slot the full busy list does not have.
        if has_external and fits_if_ignore_external:
            observed.append(REASON_UNPLACED_BUSY_CONFLICT)
        if has_pinned and fits_if_ignore_pinned:
            observed.append(REASON_UNPLACED_PINNED_CONFLICT)

    # Stable order for primary_code = first observed constraint.
    order = [
        REASON_UNPLACED_DEADLINE_LIMIT,
        REASON_UNPLACED_PROJECT_DAILY_CAP,
        REASON_UNPLACED_NO_TIME_MAP_INTERVAL,
        REASON_UNPLACED_RED_EXCLUSION,
        REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK,
        REASON_UNPLACED_PINNED_CONFLICT,
        REASON_UNPLACED_BUSY_CONFLICT,
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for code in order:
        if code in observed and code not in seen:
            ordered.append(code)
            seen.add(code)
    return ordered


def _pass_hints(
    codes: list[str],
    *,
    remaining: int,
    deadline: datetime | None,
    daily_cap: int | None,
    cap_day: date | None,
    mbl: int,
    window_id: UUID | None,
    strict_mode: bool | None,
    buffer_minutes: int = 0,
    fixed_conflicts: list[FixedBufferConflict] | None = None,
) -> list[dict[str, Any]]:
    """Structured hints in the same order as ``codes`` (Jules' priority)."""
    hints: list[dict[str, Any]] = []
    for code in codes:
        short = _HINT_BY_REASON.get(code)
        if short is None:
            continue
        params: dict[str, Any] = {"remaining_minutes": remaining}
        if short == HINT_DEADLINE_LIMIT and deadline is not None:
            params["deadline_at"] = _ensure_utc(deadline).isoformat()
        elif short == HINT_DAILY_CAP:
            if daily_cap is not None:
                params["daily_cap_minutes"] = daily_cap
            if cap_day is not None:
                params["local_date"] = cap_day.isoformat()
        elif short == HINT_MIN_BLOCK:
            params["min_block_minutes"] = mbl
        elif short in {HINT_NO_TIME_MAP_INTERVAL, HINT_RED_EXCLUSION}:
            params["time_window_id"] = str(window_id) if window_id else None
            params["strict_mode"] = strict_mode
        elif short == HINT_BUSY_CONFLICT:
            params["sources"] = ["external"]
            if buffer_minutes > 0:
                params["buffer_minutes"] = buffer_minutes
        elif short == HINT_PINNED_CONFLICT:
            params["sources"] = ["pinned"]
            if buffer_minutes > 0:
                params["buffer_minutes"] = buffer_minutes
        elif short == HINT_FIXED_BUFFER_CONFLICT:
            params["buffer_minutes"] = buffer_minutes
            if fixed_conflicts:
                first = fixed_conflicts[0]
                params["gap_minutes"] = first.gap_minutes
                params["sources"] = [first.earlier_source, first.later_source]
                params["fixed_pair_count"] = len(fixed_conflicts)
        hints.append({"code": short, "reason_code": code, "params": params})
    return hints


def slice_sizes_for_remaining(
    remaining: int,
    *,
    min_block: int,
    max_block: int | None,
    keep_in_one: bool,
) -> list[int]:
    """Slice lengths the placer may try, preferred size first.

    No limit (``max_block is None``) does not invent a synthetic cap.
    Keep-in-one is exactly one slice of the whole remaining budget, including
    a final remainder shorter than ``min_block``. Chunked placement may also
    end on a remainder shorter than min. Buffer minutes are not included.
    """
    if remaining <= 0:
        return []
    if keep_in_one:
        return [remaining]
    cap = remaining if max_block is None else max_block
    return _decreasing_slice_sizes(remaining, min_block, cap)


def _decreasing_slice_sizes(remaining: int, mbl: int, max_block: int) -> list[int]:
    """Preferred slice first, then smaller multiples of min block down to mbl."""
    preferred = _slice_size(remaining, mbl, max_block)
    if preferred is None:
        return []
    sizes: list[int] = []
    size = preferred
    while size > mbl:
        if size <= remaining:
            sizes.append(size)
        size -= mbl
    if mbl <= remaining:
        sizes.append(mbl)
    if 0 < remaining < mbl and remaining not in sizes:
        sizes.append(remaining)
    return sizes


def _refuse_placement(
    task: Task,
    db: Session,
    *,
    remaining: int,
    busy: list[BusyInterval],
    reason_code: str,
    params: dict[str, Any],
    finalize_status: bool,
    persist_blocks: bool,
) -> tuple[PlacementResult, list[BusyInterval]]:
    """Place nothing. Does not resize, move, or unpin existing blocks."""
    hint = {"code": reason_code, "reason_code": reason_code, "params": dict(params)}
    if finalize_status and persist_blocks:
        task.status = ScheduleStatus.overbooked
        db.flush()
    return (
        PlacementResult(
            blocks_created=0,
            overbooked=True if finalize_status else False,
            remaining_minutes=remaining,
            observed_constraints=[reason_code],
            last_failure=hint,
            pass_hints=[hint],
        ),
        busy,
    )


def place_task(
    db: Session,
    *,
    task: Task,
    owner_id: UUID,
    settings: UserSettings,
    remaining_minutes: int,
    busy: list[BusyInterval],
    horizon_start: datetime,
    horizon_end: datetime,
    preferred_windows: dict[UUID, FocusWindow],
    now_utc: datetime,
    preferred_window_id: UUID | None = None,
    max_blocks: int | None = None,
    finalize_status: bool = True,
    project_daily_usage: ProjectDailyUsage | None = None,
    daily_cap: int | None = None,
    prerequisite_not_before: datetime | None = None,
    persist_blocks: bool = True,
    time_map_overrides_by_map: dict[UUID, list[TimeMapOverride]] | None = None,
    working_windows: list[Any] | None = None,
    general_windows: list[Any] | None = None,
) -> tuple[PlacementResult, list[BusyInterval]]:
    # Operator zone for band wall-clock. Eligibility is Working or General.
    # Override date scope is each row's stored IANA zone, split at its UTC bounds.
    tz = ZoneInfo(settings.timezone)
    working_resolved = coerce_policy_windows(working_windows, settings)
    general_resolved = coerce_policy_windows(general_windows, settings)
    bounds = resolve_block_bounds(task, settings)
    mbl = bounds.effective_min_minutes
    keep_in_one = bounds.keep_in_one_block
    # None means No limit: slice sizing must not clamp to a synthetic max.
    max_block = None if bounds.max_unbounded else bounds.effective_max_minutes
    buffer_minutes = settings.inter_block_buffer_minutes
    if bounds.bounds_conflict():
        return _refuse_placement(
            task,
            db,
            remaining=remaining_minutes,
            busy=busy,
            reason_code=REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT,
            params={
                "remaining_minutes": remaining_minutes,
                "min_block_minutes": bounds.effective_min_minutes,
                "max_block_minutes": bounds.effective_max_minutes,
                "min_source": bounds.min_source,
                "max_source": bounds.max_source,
            },
            finalize_status=finalize_status,
            persist_blocks=persist_blocks,
        )
    if (
        keep_in_one
        and max_block is not None
        and remaining_minutes > max_block
    ):
        return _refuse_placement(
            task,
            db,
            remaining=remaining_minutes,
            busy=busy,
            reason_code=REASON_UNPLACED_KEEP_IN_ONE_CONFLICT,
            params={
                "remaining_minutes": remaining_minutes,
                "arrangement": "exceeds_max",
                "max_block_minutes": max_block,
                "pins_protected": True,
                "automatic_work_minutes": 0,
            },
            finalize_status=finalize_status,
            persist_blocks=persist_blocks,
        )
    window_id = preferred_window_id if preferred_window_id is not None else task.preferred_time_window_id
    preferred = preferred_windows.get(window_id) if window_id else None

    deadline = _ensure_utc(task.deadline_at) if task.deadline_at else None
    soft_target = effective_soft_target(task, settings, horizon_start, horizon_end)
    not_before = horizon_start
    if soft_target is not None and soft_target > not_before:
        not_before = soft_target
    if prerequisite_not_before is not None:
        prerequisite_not_before = _ensure_utc(prerequisite_not_before)
        if prerequisite_not_before > not_before:
            not_before = prerequisite_not_before

    remaining = remaining_minutes
    blocks_created = 0
    last_block_end: datetime | None = None
    last_placed_tier: str | None = None
    proposed: list[ProposedBlock] = []
    day = now_utc.astimezone(tz).date()
    end_day = horizon_end.astimezone(tz).date()

    blocks_limit = max_blocks if max_blocks is not None else None
    cap_blocked_day: date | None = None
    day_cap_blocked_ever = False
    applicable_override: dict[str, Any] | None = None

    while remaining > 0 and day <= end_day:
        if blocks_limit is not None and blocks_created >= blocks_limit:
            break
        windows = _day_search_windows(
            day,
            settings,
            tz,
            preferred,
            window_id,
            time_map_overrides_by_map,
            working_resolved,
            general_resolved,
        )
        placed_today = False
        day_cap_blocked = False
        for window_start, window_end, window_tier in windows:
            if window_end <= horizon_start or window_start >= horizon_end:
                continue
            search_start = max(window_start, horizon_start)
            search_end = min(window_end, horizon_end)

            while remaining > 0:
                if blocks_limit is not None and blocks_created >= blocks_limit:
                    break
                slice_candidates = slice_sizes_for_remaining(
                    remaining,
                    min_block=mbl,
                    max_block=None if keep_in_one or max_block is None else max_block,
                    keep_in_one=keep_in_one,
                )
                if not slice_candidates:
                    break

                placed_in_window = False
                for slice_minutes in slice_candidates:
                    if not _day_cap_allows(
                        day, task.project_id, slice_minutes, project_daily_usage, daily_cap
                    ):
                        day_cap_blocked = True
                        day_cap_blocked_ever = True
                        if cap_blocked_day is None:
                            cap_blocked_day = day
                        break
                    slot = find_slot(
                        busy,
                        search_start,
                        search_end,
                        slice_minutes,
                        not_before,
                        deadline,
                        buffer_minutes=buffer_minutes,
                    )
                    if slot is None:
                        continue

                    start, end = slot
                    if interval_overlaps_busy(busy, start, end):
                        not_before = end
                        continue

                    if persist_blocks:
                        block = ScheduledBlock(
                            owner_id=owner_id,
                            task_id=task.id,
                            start_time=start,
                            end_time=end,
                            is_pinned=False,
                        )
                        db.add(block)
                        db.flush()
                    else:
                        proposed.append(
                            ProposedBlock(
                                task_id=task.id,
                                start_time=start,
                                end_time=end,
                                slice_minutes=slice_minutes,
                                tier=window_tier,
                                preferred_window_id=window_id,
                            )
                        )
                    blocks_created += 1
                    remaining -= slice_minutes
                    not_before = end
                    last_block_end = end
                    last_placed_tier = window_tier
                    # Buffer is separation, not work duration: ``remaining``
                    # drops by slice_minutes only. One pad on each side of this
                    # block is the single auto–auto gap, including a later
                    # insert placed earlier in the day. Fixed clearance is the
                    # consult view inside find_slot, so this pad is not applied
                    # again to pins or to scheduled intervals.
                    busy = add_busy_interval(busy, start, end, buffer_minutes)
                    _record_project_minutes(day, task.project_id, slice_minutes, project_daily_usage)
                    placed_override = override_covering_instant(
                        _overrides_for_window(
                            preferred, window_id, time_map_overrides_by_map
                        ),
                        start,
                    )
                    if placed_override is not None:
                        local = start.astimezone(ZoneInfo(placed_override.timezone)).date()
                        applicable_override = applicable_override_payload(
                            placed_override, local
                        )
                    placed_today = True
                    placed_in_window = True
                    break

                if day_cap_blocked:
                    break
                if not placed_in_window:
                    break

                if blocks_limit is not None and blocks_created >= blocks_limit:
                    break
                break

            if remaining <= 0 or (blocks_limit is not None and blocks_created >= blocks_limit):
                break
            if day_cap_blocked:
                break
        day += timedelta(days=1)
        if blocks_limit is not None and blocks_created >= blocks_limit:
            break
        if not placed_today and remaining > 0:
            continue

    overbooked = remaining > 0
    if deadline is not None and remaining > 0:
        overbooked = True

    if finalize_status and persist_blocks:
        if overbooked:
            task.status = ScheduleStatus.overbooked
        elif blocks_created > 0:
            task.status = ScheduleStatus.scheduled
        else:
            if deadline is not None and not_before >= deadline:
                task.status = ScheduleStatus.overbooked
            elif remaining > 0:
                task.status = ScheduleStatus.overbooked

    if persist_blocks:
        db.flush()

    observed: list[str] = []
    if remaining > 0:
        observed = _observe_unplaced_constraints(
            task=task,
            settings=settings,
            remaining=remaining,
            busy=busy,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            preferred=preferred,
            preferred_window_id=window_id,
            overrides_by_map=time_map_overrides_by_map,
            now_utc=now_utc,
            not_before=not_before,
            deadline=deadline,
            mbl=mbl,
            max_block=remaining if max_block is None else int(max_block),
            daily_cap=daily_cap,
            project_daily_usage=project_daily_usage,
            day_cap_blocked=day_cap_blocked_ever,
            cap_blocked_day=cap_blocked_day,
            buffer_minutes=buffer_minutes,
            working_windows=working_resolved,
            general_windows=general_resolved,
        )

    # Row 8: pre-existing pins/events closer than the buffer are reported.
    # Their stored bounds are unchanged (add_busy_interval does not move them).
    conflicts = fixed_buffer_conflicts(busy, buffer_minutes)
    if conflicts and REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER not in observed:
        observed.append(REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER)

    hints: list[dict[str, Any]] = []
    last_failure: dict[str, Any] | None = None
    if blocks_created == 0 and observed:
        hints = _pass_hints(
            observed,
            remaining=remaining,
            deadline=deadline,
            daily_cap=daily_cap,
            cap_day=cap_blocked_day,
            mbl=mbl,
            window_id=window_id,
            strict_mode=preferred.strict_mode if preferred is not None else None,
            buffer_minutes=buffer_minutes,
            fixed_conflicts=conflicts,
        )
        last_failure = hints[0] if hints else None
    elif conflicts:
        # Placement may still succeed elsewhere on the day. The tight fixed
        # pair is a pass fact, not a failure of this block.
        hints = _pass_hints(
            [REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER],
            remaining=remaining,
            deadline=deadline,
            daily_cap=daily_cap,
            cap_day=cap_blocked_day,
            mbl=mbl,
            window_id=window_id,
            strict_mode=preferred.strict_mode if preferred is not None else None,
            buffer_minutes=buffer_minutes,
            fixed_conflicts=conflicts,
        )

    return (
        PlacementResult(
            blocks_created=blocks_created,
            overbooked=overbooked if finalize_status else False,
            remaining_minutes=remaining,
            last_block_end=last_block_end,
            last_placed_tier=last_placed_tier,
            proposed_blocks=proposed if proposed else None,
            observed_constraints=observed,
            last_failure=last_failure,
            pass_hints=hints,
            applicable_override=applicable_override,
        ),
        busy,
    )


def place_one_block(
    db: Session,
    *,
    task: Task,
    owner_id: UUID,
    settings: UserSettings,
    remaining_minutes: int,
    busy: list[BusyInterval],
    horizon_start: datetime,
    horizon_end: datetime,
    preferred_windows: dict[UUID, FocusWindow],
    now_utc: datetime,
    preferred_window_id: UUID | None = None,
    project_daily_usage: ProjectDailyUsage | None = None,
    daily_cap: int | None = None,
    prerequisite_not_before: datetime | None = None,
    persist_blocks: bool = True,
    time_map_overrides_by_map: dict[UUID, list[TimeMapOverride]] | None = None,
    working_windows: list[Any] | None = None,
    general_windows: list[Any] | None = None,
) -> tuple[PlacementResult, list[BusyInterval]]:
    """Place at most one scheduled block for round-robin replan sweeps."""
    return place_task(
        db,
        task=task,
        owner_id=owner_id,
        settings=settings,
        remaining_minutes=remaining_minutes,
        busy=busy,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        preferred_windows=preferred_windows,
        now_utc=now_utc,
        preferred_window_id=preferred_window_id,
        max_blocks=1,
        finalize_status=False,
        project_daily_usage=project_daily_usage,
        daily_cap=daily_cap,
        prerequisite_not_before=prerequisite_not_before,
        persist_blocks=persist_blocks,
        time_map_overrides_by_map=time_map_overrides_by_map,
        working_windows=working_windows,
        general_windows=general_windows,
    )
