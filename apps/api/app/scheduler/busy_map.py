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


# Pins and external events are fixed. Scheduled auto blocks are not.
FIXED_BUSY_SOURCES = frozenset({"pinned", "external"})


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime
    source: str = "external"  # "pinned" | "external" | "scheduled"


@dataclass(frozen=True)
class FixedBufferConflict:
    """Two fixed items whose separation is tighter than the buffer.

    Bounds are the stored occupancy. Nothing here is a proposal to move them.
    """

    earlier_source: str
    later_source: str
    earlier_start: datetime
    earlier_end: datetime
    later_start: datetime
    later_end: datetime
    gap_minutes: int
    buffer_minutes: int


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
    """Append a newly placed auto block plus one buffer on each side, then re-merge.

    The buffer is separation, not work duration. One pad before ``start`` and
    one after ``end`` is the whole auto–auto gap, including a later block
    inserted earlier in the day and consecutive splits of one task. The two
    pads meet in that gap, so the separation is the buffer once, not twice.
    Pins and external events stay at their real bounds; ``find_slot`` consults
    ``expand_fixed_busy_for_placement`` for those and does not expand scheduled
    intervals again. Fixed items are not moved. Travel is not applied.
    """
    pad = timedelta(minutes=max(buffer_minutes, 0))
    return _merge_busy(
        [*busy, BusyInterval(start - pad, end + pad, source="scheduled")]
    )


def expand_fixed_busy_for_placement(
    busy: list[BusyInterval],
    buffer_minutes: int,
) -> list[BusyInterval]:
    """Consult view: grow pins and external events by the buffer on both sides.

    Scheduled intervals are returned unchanged. They already carry one pad on
    each side, and expanding them again would make the auto–auto gap twice
    the buffer.
    Does not replace the stored busy list.
    """
    if buffer_minutes <= 0:
        return busy
    pad = timedelta(minutes=buffer_minutes)
    expanded: list[BusyInterval] = []
    for item in busy:
        if item.source in FIXED_BUSY_SOURCES:
            expanded.append(
                BusyInterval(item.start - pad, item.end + pad, source=item.source)
            )
        else:
            expanded.append(item)
    return expanded


def fixed_buffer_conflicts(
    busy: list[BusyInterval],
    buffer_minutes: int,
) -> list[FixedBufferConflict]:
    """Report pre-existing fixed items closer than the buffer. Do not move them.

    S0 §6.1 row 8. Buffer 0 allows adjacency, including a zero gap. Overlap or
    a positive gap shorter than a positive buffer is a conflict. Scheduled
    auto blocks are not fixed items.
    """
    if buffer_minutes <= 0:
        return []
    fixed = [item for item in busy if item.source in FIXED_BUSY_SOURCES]
    fixed.sort(key=lambda item: (item.start, item.end, item.source))
    pad = timedelta(minutes=buffer_minutes)
    conflicts: list[FixedBufferConflict] = []
    for index, earlier in enumerate(fixed):
        for later in fixed[index + 1 :]:
            if later.start >= earlier.end + pad:
                break
            gap_minutes = int((later.start - earlier.end).total_seconds() // 60)
            if gap_minutes >= buffer_minutes:
                continue
            conflicts.append(
                FixedBufferConflict(
                    earlier_source=earlier.source,
                    later_source=later.source,
                    earlier_start=earlier.start,
                    earlier_end=earlier.end,
                    later_start=later.start,
                    later_end=later.end,
                    gap_minutes=gap_minutes,
                    buffer_minutes=buffer_minutes,
                )
            )
    return conflicts


def interval_overlaps_busy(
    busy: list[BusyInterval],
    start: datetime,
    end: datetime,
) -> bool:
    for item in busy:
        if ranges_overlap(start, end, item.start, item.end):
            return True
    return False
