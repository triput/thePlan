"""UTC intervals for stored availability windows (S2-V3).

Windows are wall-clock in the schedule timezone. ``ends_next_day`` belongs to
the start weekday: replacing that occurrence replaces the next-morning tail.
A later local date still sees the tail as carry-in so a run that begins after
midnight does not drop it (A11c).

Recurring DST (SPEC §4.3 / SS-13):

- Ambiguous fold: first occurrence (``fold=0``) for the start and the end.
- Spring-forward gap: a boundary inside the gap moves to the first valid
  instant after the gap. The other boundary stays. The whole window is not
  shifted to preserve elapsed duration. If both boundaries collapse to that
  instant, the occurrence is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.models import AvailabilityPolicy
from app.models.enums import AvailabilityPolicySlug


@dataclass(frozen=True)
class PolicyWindow:
    weekday: int
    start_time: time
    duration_minutes: int
    ends_next_day: bool
    sort_order: int = 0


@dataclass(frozen=True)
class MaterializedSpan:
    """Half-open UTC interval. ``owner_date`` is the occurrence's start local date."""

    start: datetime
    end: datetime
    owner_date: date


def as_policy_window(row: Any) -> PolicyWindow:
    if isinstance(row, PolicyWindow):
        return row
    if isinstance(row, dict):
        start = row["start_time"]
        if isinstance(start, str):
            start = time.fromisoformat(start)
        return PolicyWindow(
            weekday=int(row["weekday"]),
            start_time=start,
            duration_minutes=int(row["duration_minutes"]),
            ends_next_day=bool(row.get("ends_next_day", False)),
            sort_order=int(row.get("sort_order") or 0),
        )
    return PolicyWindow(
        weekday=int(row.weekday),
        start_time=row.start_time,
        duration_minutes=int(row.duration_minutes),
        ends_next_day=bool(row.ends_next_day),
        sort_order=int(getattr(row, "sort_order", 0) or 0),
    )


def coerce_policy_windows(rows: Sequence[Any] | None, settings: Any) -> list[PolicyWindow]:
    """Explicit rows win, including an empty list (zero eligible days).

    ``None`` is the direct-call fallback that still mirrors legacy
    ``workweek_*`` so older unit tests keep a Monday-first span. Collect
    always passes the stored policy rows.
    """
    if rows is None:
        return legacy_windows_from_settings(settings)
    return [as_policy_window(row) for row in rows]


def legacy_windows_from_settings(settings: Any) -> list[PolicyWindow]:
    """Monday-first span from deprecated settings fields. Not the placer SoT."""
    days = getattr(settings, "workweek_days", None)
    start = getattr(settings, "workday_start_local", None)
    minutes = getattr(settings, "workday_minutes", None)
    if not isinstance(days, int) or days <= 0:
        return []
    if not isinstance(start, time) or not isinstance(minutes, int) or minutes <= 0:
        return []
    count = min(days, 7)
    ends = _crosses_midnight(start, minutes)
    return [
        PolicyWindow(
            weekday=weekday,
            start_time=start,
            duration_minutes=minutes,
            ends_next_day=ends,
            sort_order=0,
        )
        for weekday in range(count)
    ]


def load_owner_policy_windows(
    db: Session, owner_id: UUID
) -> tuple[list[PolicyWindow], list[PolicyWindow]]:
    """Copy Working and General windows once. Personal is not eligibility."""
    rows = (
        db.query(AvailabilityPolicy)
        .options(joinedload(AvailabilityPolicy.windows))
        .filter(AvailabilityPolicy.owner_id == owner_id)
        .all()
    )
    working: list[PolicyWindow] = []
    general: list[PolicyWindow] = []
    seen: set[UUID] = set()
    for policy in rows:
        if policy.id in seen:
            continue
        seen.add(policy.id)
        copied = [as_policy_window(window) for window in policy.windows]
        if policy.slug == AvailabilityPolicySlug.work:
            working = copied
        elif policy.slug == AvailabilityPolicySlug.general:
            general = copied
    return working, general


def resolve_recurring_wall(day: date, clock: time, tz: ZoneInfo) -> datetime:
    """UTC instant for a recurring wall clock in ``tz``."""
    utc, exists = _fold0_utc(day, clock, tz)
    if exists:
        return utc
    return _first_valid_after_gap(utc, tz)


def occurrence_span(
    window: PolicyWindow,
    start_day: date,
    tz: ZoneInfo,
) -> MaterializedSpan | None:
    """Full occurrence beginning on ``start_day``, including an overnight tail."""
    end_day, end_clock = _add_wall_minutes(start_day, window.start_time, window.duration_minutes)
    start = resolve_recurring_wall(start_day, window.start_time, tz)
    end = resolve_recurring_wall(end_day, end_clock, tz)
    if end <= start:
        return None
    return MaterializedSpan(start=start, end=end, owner_date=start_day)


def materialize_windows_for_local_date(
    windows: Sequence[Any],
    day: date,
    tz: ZoneInfo,
) -> list[MaterializedSpan]:
    """Spans the placer should see while standing on local ``day``.

    The occurrence that starts on ``day`` is returned whole (tail included).
    Earlier occurrences contribute only the slice that falls on ``day``.
    """
    policy = [as_policy_window(row) for row in windows]
    if not policy:
        return []
    day_start = resolve_recurring_wall(day, time.min, tz)
    next_start = resolve_recurring_wall(day + timedelta(days=1), time.min, tz)
    spans: list[MaterializedSpan] = []
    for window in policy:
        for back in range(0, 8):
            occurrence = day - timedelta(days=back)
            if occurrence.weekday() != window.weekday:
                continue
            full = occurrence_span(window, occurrence, tz)
            if full is None:
                continue
            if back == 0:
                spans.append(full)
                continue
            start = max(full.start, day_start)
            end = min(full.end, next_start)
            if start < end:
                spans.append(MaterializedSpan(start=start, end=end, owner_date=occurrence))
    spans.sort(key=lambda item: (item.start, item.end, item.owner_date.toordinal()))
    return spans


def merge_utc_intervals(
    windows: Sequence[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    ordered = sorted(windows, key=lambda item: (item[0], item[1]))
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for window_start, window_end in ordered[1:]:
        last_start, last_end = merged[-1]
        if window_start <= last_end:
            merged[-1] = (last_start, max(last_end, window_end))
        else:
            merged.append((window_start, window_end))
    return merged


def covered_minutes_between(
    windows: Sequence[Any],
    start: datetime,
    end: datetime,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    """Policy coverage clipped to ``[start, end)``, merged."""
    start = _as_utc(start)
    end = _as_utc(end)
    if end <= start:
        return []
    day = start.astimezone(tz).date() - timedelta(days=1)
    last = end.astimezone(tz).date()
    covered: list[tuple[datetime, datetime]] = []
    while day <= last:
        for span in materialize_windows_for_local_date(windows, day, tz):
            clip_start = max(start, span.start)
            clip_end = min(end, span.end)
            if clip_start < clip_end:
                covered.append((clip_start, clip_end))
        day += timedelta(days=1)
    return merge_utc_intervals(covered)


def _crosses_midnight(start: time, duration_minutes: int) -> bool:
    seconds = start.hour * 3600 + start.minute * 60 + start.second
    return seconds + duration_minutes * 60 >= 86400


def _add_wall_minutes(day: date, clock: time, minutes: int) -> tuple[date, time]:
    total = clock.hour * 60 + clock.minute + minutes
    extra_days, minute_of_day = divmod(total, 24 * 60)
    return day + timedelta(days=extra_days), time(minute_of_day // 60, minute_of_day % 60, clock.second)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fold0_utc(day: date, clock: time, tz: ZoneInfo) -> tuple[datetime, bool]:
    naive = datetime.combine(day, clock)
    aware = naive.replace(tzinfo=tz, fold=0)
    utc = aware.astimezone(timezone.utc)
    back = utc.astimezone(tz).replace(tzinfo=None)
    return utc, back == naive


def _first_valid_after_gap(bogus_utc: datetime, tz: ZoneInfo) -> datetime:
    """Earliest real instant at or after the gap that swallowed ``bogus_utc``."""
    post = bogus_utc.astimezone(tz).utcoffset()
    if post is None:
        return bogus_utc
    cursor = bogus_utc
    prev = bogus_utc
    found = False
    for _ in range(360):
        prev = cursor - timedelta(minutes=1)
        if prev.astimezone(tz).utcoffset() != post:
            found = True
            break
        cursor = prev
    if not found:
        return bogus_utc
    lo = prev
    hi = cursor
    while hi - lo > timedelta(seconds=1):
        mid = lo + (hi - lo) / 2
        if mid.astimezone(tz).utcoffset() == post:
            hi = mid
        else:
            lo = mid
    instant = lo
    limit = hi + timedelta(seconds=2)
    while instant.astimezone(tz).utcoffset() != post and instant < limit:
        instant += timedelta(seconds=1)
    return instant.astimezone(timezone.utc).replace(microsecond=0)
