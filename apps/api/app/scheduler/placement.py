"""Slice-and-fit placement for auto-scheduled blocks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TypeAlias
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import FocusWindow, ScheduleStatus, ScheduledBlock, Task, TimeMapBand, UserSettings
from app.models.enums import TimeMapBandTier
from app.scheduler.busy_map import BusyInterval, add_busy_interval, interval_overlaps_busy
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


def _clip_band_to_workday(
    day: date,
    band: TimeMapBand,
    settings: UserSettings,
    tz: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    bounds = band_bounds(day, band, tz)
    if bounds is None:
        return None
    work_start, work_end = workday_bounds(day, settings, tz)
    return intersect_ranges(work_start, work_end, bounds[0], bounds[1])


def _search_windows_for_day(
    day: date,
    settings: UserSettings,
    tz: ZoneInfo,
    preferred: FocusWindow | None,
) -> list[tuple[datetime, datetime, str | None]]:
    if not is_workday(day, settings.workweek_days):
        return []

    work_start, work_end = workday_bounds(day, settings, tz)
    if preferred is None:
        return [(work_start, work_end, None)]

    green_clips: list[tuple[datetime, datetime]] = []
    yellow_clips: list[tuple[datetime, datetime]] = []
    red_clips: list[tuple[datetime, datetime]] = []

    for band in preferred.bands:
        clipped = _clip_band_to_workday(day, band, settings, tz)
        if clipped is None:
            continue
        if band.tier == TimeMapBandTier.green:
            green_clips.append(clipped)
        elif band.tier == TimeMapBandTier.yellow:
            yellow_clips.append(clipped)
        elif band.tier == TimeMapBandTier.red:
            red_clips.append(clipped)

    red_intervals = [TimeInterval(start, end) for start, end in red_clips]
    green_clips = _subtract_red_from_clips(green_clips, red_intervals)
    yellow_clips = _subtract_red_from_clips(yellow_clips, red_intervals)

    ordered: list[tuple[datetime, datetime, str | None]] = [
        (start, end, "green") for start, end in green_clips
    ] + [(start, end, "yellow") for start, end in yellow_clips]

    if not preferred.strict_mode:
        neutral = subtract_intervals_from_range(work_start, work_end, red_intervals)
        ordered.extend((item.start, item.end, "neutral") for item in neutral)

    return ordered


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
) -> tuple[datetime, datetime] | None:
    if duration_minutes <= 0:
        return None

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
) -> tuple[PlacementResult, list[BusyInterval]]:
    tz = ZoneInfo(settings.timezone)
    mbl = task.min_block_duration_minutes or settings.default_min_block_duration_minutes
    max_block = task.max_block_duration_minutes
    buffer_minutes = settings.inter_block_buffer_minutes
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

    while remaining > 0 and day <= end_day:
        if blocks_limit is not None and blocks_created >= blocks_limit:
            break
        windows = _search_windows_for_day(day, settings, tz, preferred)
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
                slice_candidates = _decreasing_slice_sizes(remaining, mbl, max_block)
                if not slice_candidates:
                    break

                placed_in_window = False
                for slice_minutes in slice_candidates:
                    if not _day_cap_allows(
                        day, task.project_id, slice_minutes, project_daily_usage, daily_cap
                    ):
                        day_cap_blocked = True
                        break
                    slot = find_slot(
                        busy,
                        search_start,
                        search_end,
                        slice_minutes,
                        not_before,
                        deadline,
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
                    busy = add_busy_interval(busy, start, end, buffer_minutes)
                    _record_project_minutes(day, task.project_id, slice_minutes, project_daily_usage)
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
    return (
        PlacementResult(
            blocks_created=blocks_created,
            overbooked=overbooked if finalize_status else False,
            remaining_minutes=remaining,
            last_block_end=last_block_end,
            last_placed_tier=last_placed_tier,
            proposed_blocks=proposed if proposed else None,
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
    )
