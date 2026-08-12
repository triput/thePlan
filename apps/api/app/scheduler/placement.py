"""Slice-and-fit placement for auto-scheduled blocks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import FocusWindow, ScheduleStatus, ScheduledBlock, Task, UserSettings
from app.scheduler.busy_map import BusyInterval, add_busy_interval, interval_overlaps_busy
from app.services.calendar_conflicts import ranges_overlap


@dataclass
class PlacementResult:
    blocks_created: int
    overbooked: bool


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_workday(day: date, workweek_days: int) -> bool:
    return day.weekday() < workweek_days


def workday_bounds(day: date, settings: UserSettings, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time(8, 0), tzinfo=tz)
    end_local = start_local + timedelta(minutes=settings.workday_minutes)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def focus_bounds(
    day: date,
    window: FocusWindow,
    tz: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    if not (window.days_of_week & (1 << day.weekday())):
        return None
    start_local = datetime.combine(day, window.start_time, tzinfo=tz)
    end_local = datetime.combine(day, window.end_time, tzinfo=tz)
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


def _search_windows_for_day(
    day: date,
    settings: UserSettings,
    tz: ZoneInfo,
    preferred: FocusWindow | None,
) -> list[tuple[datetime, datetime]]:
    if not is_workday(day, settings.workweek_days):
        return []

    work_start, work_end = workday_bounds(day, settings, tz)
    if preferred is None:
        return [(work_start, work_end)]

    focus = focus_bounds(day, preferred, tz)
    if focus is None:
        return [(work_start, work_end)]

    focus_start, focus_end = focus
    if preferred.is_hard:
        clipped = intersect_ranges(work_start, work_end, focus_start, focus_end)
        windows = [clipped] if clipped else []
        windows.append((work_start, work_end))
        return windows

    clipped = intersect_ranges(work_start, work_end, focus_start, focus_end)
    ordered: list[tuple[datetime, datetime]] = []
    if clipped:
        ordered.append(clipped)
    ordered.append((work_start, work_end))
    return ordered


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
) -> tuple[PlacementResult, list[BusyInterval]]:
    tz = ZoneInfo(settings.timezone)
    mbl = task.min_block_duration_minutes or settings.default_min_block_duration_minutes
    max_block = task.max_block_duration_minutes
    buffer_minutes = settings.inter_block_buffer_minutes
    preferred = preferred_windows.get(task.preferred_time_window_id) if task.preferred_time_window_id else None

    deadline = _ensure_utc(task.deadline_at) if task.deadline_at else None
    soft_target = effective_soft_target(task, settings, horizon_start, horizon_end)
    not_before = horizon_start
    if soft_target is not None and soft_target > not_before:
        not_before = soft_target

    remaining = remaining_minutes
    blocks_created = 0
    day = now_utc.astimezone(tz).date()
    end_day = horizon_end.astimezone(tz).date()

    while remaining > 0 and day <= end_day:
        windows = _search_windows_for_day(day, settings, tz, preferred)
        placed_today = False
        for window_start, window_end in windows:
            if window_end <= horizon_start or window_start >= horizon_end:
                continue
            search_start = max(window_start, horizon_start)
            search_end = min(window_end, horizon_end)

            while remaining > 0:
                slice_minutes = _slice_size(remaining, mbl, max_block)
                if slice_minutes is None:
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
                    break

                start, end = slot
                if interval_overlaps_busy(busy, start, end):
                    not_before = end
                    continue

                block = ScheduledBlock(
                    owner_id=owner_id,
                    task_id=task.id,
                    start_time=start,
                    end_time=end,
                    is_pinned=False,
                )
                db.add(block)
                db.flush()
                blocks_created += 1
                remaining -= slice_minutes
                not_before = end
                busy = add_busy_interval(busy, start, end, buffer_minutes)
                placed_today = True

                if remaining > 0 and remaining < mbl:
                    slice_minutes = remaining
                    slot = find_slot(
                        busy,
                        search_start,
                        search_end,
                        slice_minutes,
                        not_before,
                        deadline,
                    )
                    if slot is None:
                        break
                    start, end = slot
                    block = ScheduledBlock(
                        owner_id=owner_id,
                        task_id=task.id,
                        start_time=start,
                        end_time=end,
                        is_pinned=False,
                    )
                    db.add(block)
                    db.flush()
                    blocks_created += 1
                    remaining = 0
                    busy = add_busy_interval(busy, start, end, buffer_minutes)
                break

            if remaining <= 0:
                break
        day += timedelta(days=1)
        if not placed_today and remaining > 0:
            continue

    overbooked = remaining > 0
    if deadline is not None and remaining > 0:
        overbooked = True

    if overbooked:
        task.status = ScheduleStatus.overbooked
    elif blocks_created > 0:
        task.status = ScheduleStatus.scheduled
    else:
        if deadline is not None and not_before >= deadline:
            task.status = ScheduleStatus.overbooked
        elif remaining > 0:
            task.status = ScheduleStatus.overbooked

    db.flush()
    return PlacementResult(blocks_created=blocks_created, overbooked=overbooked), busy
