"""Resolve F4 Time Map overrides for scheduler placement (read path).

Tesla owns migration CRUD, overlap validation on write, and API routes.
This module loads persisted overrides and picks the effective map per local day.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.models import FocusWindow, TimeMapBand, TimeMapOverride, UserSettings


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def override_utc_bounds(override: TimeMapOverride) -> tuple[datetime, datetime]:
    """Inclusive local start through exclusive midnight after ``local_end_date``, in UTC.

    Boundaries use the override's stored IANA timezone, including DST transitions.
    A later change to ``user_settings.timezone`` does not move these bounds.
    Band wall-clock placement still uses the operator timezone
    (``placement.band_bounds``), not this zone.
    """
    tz = ZoneInfo(override.timezone)
    start_local = datetime.combine(override.local_start_date, time.min, tzinfo=tz)
    end_local = datetime.combine(
        override.local_end_date + timedelta(days=1),
        time.min,
        tzinfo=tz,
    )
    return _as_utc(start_local), _as_utc(end_local)


def override_intersects_horizon(
    override: TimeMapOverride,
    horizon_start: datetime,
    horizon_end: datetime,
) -> bool:
    """True when the override's stored-timezone span overlaps ``[horizon_start, horizon_end)``."""
    horizon_start = _as_utc(horizon_start)
    horizon_end = _as_utc(horizon_end)
    if horizon_end <= horizon_start:
        return False
    start, end = override_utc_bounds(override)
    return start < horizon_end and end > horizon_start


def load_time_map_overrides_for_maps(
    db: Session,
    owner_id: UUID,
    map_ids: set[UUID],
) -> dict[UUID, list[TimeMapOverride]]:
    """Every override on these maps, including expired rows (bands eager-loaded).

    Explanation fingerprints use this set. Placement must still drop rows that
    miss the horizon via ``overrides_intersecting_horizon``.
    """
    if not map_ids:
        return {}
    rows = (
        db.query(TimeMapOverride)
        .options(joinedload(TimeMapOverride.bands))
        .filter(
            TimeMapOverride.owner_id == owner_id,
            TimeMapOverride.map_id.in_(map_ids),
        )
        .all()
    )
    by_map: dict[UUID, list[TimeMapOverride]] = {map_id: [] for map_id in map_ids}
    seen: set[UUID] = set()
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        by_map.setdefault(row.map_id, []).append(row)
    for overrides in by_map.values():
        overrides.sort(key=lambda item: (item.local_start_date, item.created_at, str(item.id)))
    return by_map


def overrides_intersecting_horizon(
    overrides_by_map: dict[UUID, list[TimeMapOverride]],
    horizon_start: datetime,
    horizon_end: datetime,
) -> dict[UUID, list[TimeMapOverride]]:
    """Placement subset. Fingerprints keep the unfiltered map."""
    return {
        map_id: [
            row
            for row in rows
            if override_intersects_horizon(row, horizon_start, horizon_end)
        ]
        for map_id, rows in overrides_by_map.items()
    }


def load_time_map_overrides_for_horizon(
    db: Session,
    owner_id: UUID,
    map_ids: set[UUID],
    horizon_start: datetime,
    horizon_end: datetime,
) -> dict[UUID, list[TimeMapOverride]]:
    """Overrides per map that intersect the replan horizon (bands eager-loaded)."""
    return overrides_intersecting_horizon(
        load_time_map_overrides_for_maps(db, owner_id, map_ids),
        horizon_start,
        horizon_end,
    )


def effective_local_date_for_scheduling_day(
    day: date,
    settings: UserSettings,
    override: TimeMapOverride,
) -> date:
    """Override stored-zone civil date aligned with a schedule-local calendar day.

    Uses start-of-civil-day in ``settings.timezone`` (not ``workday_start_local``).
    Band wall-clock times stay in the operator timezone (``placement.band_bounds``).
    A later settings timezone change does not move ``override_utc_bounds``.
    """
    user_tz = ZoneInfo(settings.timezone)
    civil_start = datetime.combine(day, time.min, tzinfo=user_tz)
    return civil_start.astimezone(ZoneInfo(override.timezone)).date()


def _match_rank(row: TimeMapOverride) -> tuple[date, str]:
    """Earlier start wins; id breaks a corrupt duplicate range.

    Write-time overlap checks should make this tie-break unreachable. Placement
    and ``resolve_override_for_date`` both use it so list order cannot pick a
    different row than the read helper.
    """
    return (row.local_start_date, str(row.id))


def override_covering_instant(
    overrides: list[TimeMapOverride] | None,
    instant: datetime,
) -> TimeMapOverride | None:
    """Override whose stored-zone ``[start, end)`` contains ``instant``.

    Inclusive start, exclusive end. A schedule-local day can hold more than
    one of these; do not pick one override for the whole day.
    """
    if not overrides:
        return None
    instant = _as_utc(instant)
    matches = [
        row
        for row in overrides
        if override_utc_bounds(row)[0] <= instant < override_utc_bounds(row)[1]
    ]
    if not matches:
        return None
    matches.sort(key=_match_rank)
    return matches[0]


def select_override_for_scheduling_day(
    overrides: list[TimeMapOverride] | None,
    *,
    day: date,
    settings: UserSettings,
) -> TimeMapOverride | None:
    """At most one non-overlapping override per map; pick by override timezone date."""
    if not overrides:
        return None
    matches = [
        override
        for override in overrides
        if override.local_start_date
        <= effective_local_date_for_scheduling_day(day, settings, override)
        <= override.local_end_date
    ]
    if not matches:
        return None
    matches.sort(key=_match_rank)
    return matches[0]


def bands_for_day(
    bands: list[TimeMapBand] | list[Any],
    day: date,
) -> list[TimeMapBand | Any]:
    """Bands whose weekday bitmask includes this calendar day."""
    weekday_bit = 1 << day.weekday()
    return [band for band in bands if band.days_of_week & weekday_bit]


def effective_day_map(
    base: FocusWindow,
    day_override: TimeMapOverride | None,
    day: date,
) -> tuple[list[Any], bool]:
    """Replacement bands + strictness for one scheduling day (override wins in-range)."""
    if day_override is None:
        return bands_for_day(list(base.bands), day), base.strict_mode
    return bands_for_day(list(day_override.bands), day), day_override.strict_mode


def resolve_override_for_date(
    overrides_by_map: dict[UUID, list[TimeMapOverride]] | None,
    focus_window_id: UUID,
    local_date: date,
) -> TimeMapOverride | None:
    """Override whose inclusive local dates contain ``local_date``.

    ``local_date`` is a calendar date in that override's stored IANA timezone,
    not the operator's current settings timezone. Overlap on one map is rejected
    at write time, so at most one row should match. If bad data leaves two,
    the earlier start date wins, then id.
    """
    if not overrides_by_map:
        return None
    matches = [
        row
        for row in overrides_by_map.get(focus_window_id, [])
        if row.local_start_date <= local_date <= row.local_end_date
    ]
    if not matches:
        return None
    matches.sort(key=_match_rank)
    return matches[0]


def applicable_override_payload(
    override: TimeMapOverride,
    effective_local_date: date,
) -> dict[str, Any]:
    return {
        "override_id": str(override.id),
        "map_id": str(override.map_id),
        "local_start_date": override.local_start_date.isoformat(),
        "local_end_date": override.local_end_date.isoformat(),
        "timezone": override.timezone,
        "strict_mode": override.strict_mode,
        "effective_local_date": effective_local_date.isoformat(),
    }
