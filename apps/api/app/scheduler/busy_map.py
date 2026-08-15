"""Merge external calendar busy + pinned blocks into sorted BUSY intervals.

Scheduler layer — input to fuzzy placement / replan (ADR-005, ADR-006).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ExternalCalendarEvent, ScheduledBlock
from app.services.busy_intervals import TimeInterval, merge_intervals, ranges_overlap


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime


def _to_time_intervals(intervals: list[BusyInterval]) -> list[TimeInterval]:
    return [TimeInterval(item.start, item.end) for item in intervals]


def _from_time_intervals(intervals: list[TimeInterval]) -> list[BusyInterval]:
    return [BusyInterval(item.start, item.end) for item in intervals]


def _merge_busy(intervals: list[BusyInterval]) -> list[BusyInterval]:
    return _from_time_intervals(merge_intervals(_to_time_intervals(intervals)))


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

    return _merge_busy(intervals)


def add_busy_interval(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
    buffer_minutes: int,
) -> list[BusyInterval]:
    """Append a busy interval including post-block buffer and re-merge."""
    buffered_end = end + timedelta(minutes=buffer_minutes)
    return _merge_busy([*busy, BusyInterval(start, buffered_end)])


def interval_overlaps_busy(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
) -> bool:
    for item in busy:
        if ranges_overlap(start, end, item.start, item.end):
            return True
    return False
