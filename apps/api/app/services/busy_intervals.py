"""Shared half-open interval overlap and merge helpers.

Used by calendar conflict detection and the scheduler busy map.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def ranges_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """True when half-open intervals [a_start, a_end) and [b_start, b_end) intersect."""
    return a_start < b_end and a_end > b_start


def overlap_interval(
    a_start: datetime,
    a_end: datetime,
    b_start: datetime,
    b_end: datetime,
) -> tuple[datetime, datetime] | None:
    if not ranges_overlap(a_start, a_end, b_start, b_end):
        return None
    return max(a_start, b_start), min(a_end, b_end)


@dataclass(frozen=True)
class TimeInterval:
    start: datetime
    end: datetime


def merge_intervals(intervals: list[TimeInterval]) -> list[TimeInterval]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda item: item.start)
    merged: list[TimeInterval] = [sorted_intervals[0]]
    for current in sorted_intervals[1:]:
        prev = merged[-1]
        if current.start <= prev.end:
            merged[-1] = TimeInterval(prev.start, max(prev.end, current.end))
        else:
            merged.append(current)
    return merged


def subtract_intervals_from_range(
    range_start: datetime,
    range_end: datetime,
    exclusions: list[TimeInterval],
) -> list[TimeInterval]:
    """Return sub-intervals of [range_start, range_end) not covered by exclusions."""
    if range_start >= range_end:
        return []
    if not exclusions:
        return [TimeInterval(range_start, range_end)]

    merged = merge_intervals(exclusions)
    result: list[TimeInterval] = []
    cursor = range_start
    for exc in merged:
        if exc.start >= range_end:
            break
        if exc.end <= cursor:
            continue
        if cursor < exc.start:
            result.append(TimeInterval(cursor, min(exc.start, range_end)))
        cursor = max(cursor, exc.end)
    if cursor < range_end:
        result.append(TimeInterval(cursor, range_end))
    return [item for item in result if item.start < item.end]
