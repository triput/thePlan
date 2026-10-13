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


def load_immovable_busy_sources(
    db: Session,
    owner_id: UUID,
) -> tuple[list[ScheduledBlock], list[ExternalCalendarEvent]]:
    """Load pinned blocks and non-mirror external events once for collect.

    Callers derive horizon-filtered calculation busy and fingerprint busy from
    the same rows so an intervening commit cannot diverge them.
    """
    pinned = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.is_pinned.is_(True),
        )
        .all()
    )
    events = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner_id,
            *ExternalCalendarEvent.immovable_busy_clause(),
        )
        .all()
    )
    return pinned, events


def busy_from_sources(
    pinned: list[ScheduledBlock],
    events: list[ExternalCalendarEvent],
    *,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> list[BusyInterval]:
    """Build merged busy from already-loaded pins/events.

    When ``range_start``/``range_end`` are set, only intervals overlapping that
    range are included (calculation horizon view).
    """
    intervals: list[BusyInterval] = []
    for block in pinned:
        if range_start is not None and range_end is not None:
            if not (block.start_time < range_end and block.end_time > range_start):
                continue
        intervals.append(
            BusyInterval(block.start_time, block.end_time, source="pinned")
        )
    for event in events:
        if range_start is not None and range_end is not None:
            if not (event.start_time < range_end and event.end_time > range_start):
                continue
        intervals.append(
            BusyInterval(event.start_time, event.end_time, source="external")
        )
    return _merge_busy(intervals)


def build_busy_map(
    db: Session,
    owner_id: UUID,
    range_start: datetime,
    range_end: datetime,
) -> list[BusyInterval]:
    """External events (non-mirror) + all pinned blocks overlapping the range."""
    pinned, events = load_immovable_busy_sources(db, owner_id)
    return busy_from_sources(
        pinned, events, range_start=range_start, range_end=range_end
    )


def load_immovable_busy(db: Session, owner_id: UUID) -> list[BusyInterval]:
    """Every pinned block and non-mirror external event for the owner.

    Not clipped to the horizon. Explanation fingerprints use this so a sliding
    ``now`` does not mark ``busy_external`` stale. Auto-placed blocks are omitted;
    they are outputs of the run, not inputs.

    Prefer ``load_immovable_busy_sources`` + ``busy_from_sources`` during collect
    so calculation and fingerprint share one capture.
    """
    pinned, events = load_immovable_busy_sources(db, owner_id)
    return busy_from_sources(pinned, events)


def add_busy_interval(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
    buffer_minutes: int,
) -> list[BusyInterval]:
    """Append a busy interval including trailing buffer and re-merge.

    SS-30 / A15 is not closed. The buffer is separation, not work duration.
    Padding is the trailing edge of a newly placed auto block only. Evidence
    still owed: both sides of fixed busy (pins and external events) and the
    same gap between consecutive auto blocks of one task.
    """
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
