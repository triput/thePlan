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
    source: str = "external"  # "pinned" | "external" | "scheduled"


def _to_time_intervals(intervals: list[BusyInterval]) -> list[TimeInterval]:
    return [TimeInterval(item.start, item.end) for item in intervals]


def _from_time_intervals(
    intervals: list[TimeInterval],
    *,
    source: str = "external",
) -> list[BusyInterval]:
    return [BusyInterval(item.start, item.end, source) for item in intervals]


def _merge_busy(intervals: list[BusyInterval]) -> list[BusyInterval]:
    if not intervals:
        return []
    by_source: dict[str, list[BusyInterval]] = {}
    for item in intervals:
        by_source.setdefault(item.source, []).append(item)
    merged: list[BusyInterval] = []
    for source, group in by_source.items():
        merged.extend(
            _from_time_intervals(merge_intervals(_to_time_intervals(group)), source=source)
        )
    merged.sort(key=lambda item: item.start)
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
        intervals.append(
            BusyInterval(block.start_time, block.end_time, source="pinned")
        )

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
        intervals.append(
            BusyInterval(event.start_time, event.end_time, source="external")
        )

    return _merge_busy(intervals)


def load_immovable_busy(db: Session, owner_id: UUID) -> list[BusyInterval]:
    """Every pinned block and non-mirror external event for the owner.

    Not clipped to the horizon. Explanation fingerprints use this so a sliding
    ``now`` does not mark ``busy_external`` stale. Auto-placed blocks are omitted;
    they are outputs of the run, not inputs.
    """
    intervals: list[BusyInterval] = []
    pinned = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.is_pinned.is_(True),
        )
        .all()
    )
    for block in pinned:
        intervals.append(BusyInterval(block.start_time, block.end_time, source="pinned"))

    events = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner_id,
            ExternalCalendarEvent.scheduled_block_id.is_(None),
        )
        .all()
    )
    for event in events:
        intervals.append(BusyInterval(event.start_time, event.end_time, source="external"))
    return _merge_busy(intervals)


def add_busy_interval(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
    buffer_minutes: int,
) -> list[BusyInterval]:
    """Append a busy interval including post-block buffer and re-merge."""
    buffered_end = end + timedelta(minutes=buffer_minutes)
    return _merge_busy([*busy, BusyInterval(start, buffered_end, source="scheduled")])


def interval_overlaps_busy(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
) -> bool:
    for item in busy:
        if ranges_overlap(start, end, item.start, item.end):
            return True
    return False
