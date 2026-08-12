"""Merge external calendar busy + pinned blocks into sorted BUSY intervals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ExternalCalendarEvent, ScheduledBlock
from app.services.calendar_conflicts import ranges_overlap


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime


def _merge_intervals(intervals: list[BusyInterval]) -> list[BusyInterval]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda item: item.start)
    merged: list[BusyInterval] = [sorted_intervals[0]]
    for current in sorted_intervals[1:]:
        prev = merged[-1]
        if current.start <= prev.end:
            merged[-1] = BusyInterval(prev.start, max(prev.end, current.end))
        else:
            merged.append(current)
    return merged


def build_busy_map(
    db: Session,
    owner_id: UUID,
    range_start: datetime,
    range_end: datetime,
) -> list[BusyInterval]:
    """External events (non-mirror) + all pinned blocks overlapping the range."""
    intervals: list[BusyInterval] = []

    pinned = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.is_pinned.is_(True),
            ScheduledBlock.start_time < range_end,
            ScheduledBlock.end_time > range_start,
        )
        .all()
    )
    for block in pinned:
        intervals.append(BusyInterval(block.start_time, block.end_time))

    events = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner_id,
            ExternalCalendarEvent.scheduled_block_id.is_(None),
            ExternalCalendarEvent.start_time < range_end,
            ExternalCalendarEvent.end_time > range_start,
        )
        .all()
    )
    for event in events:
        intervals.append(BusyInterval(event.start_time, event.end_time))

    return _merge_intervals(intervals)


def add_busy_interval(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
    buffer_minutes: int,
) -> list[BusyInterval]:
    """Append a busy interval including post-block buffer and re-merge."""
    buffered_end = end + timedelta(minutes=buffer_minutes)
    return _merge_intervals([*busy, BusyInterval(start, buffered_end)])


def interval_overlaps_busy(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
) -> bool:
    for item in busy:
        if ranges_overlap(start, end, item.start, item.end):
            return True
    return False
