"""Write path for temporary Time Map overrides.

Creating or editing an override does not replan. Placement later reads
horizon-intersecting rows. Explanation fingerprints include every override
on the task's effective map, so create, patch, and delete mark that
explanation stale without starting a run.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import FocusWindow, TimeMapOverride, TimeMapOverrideBand
from app.schemas.hierarchy import TimeMapBandIn
from app.services.focus_windows import validate_bands


def validate_iana_timezone(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ApiError(422, "timezone must be an IANA name", "TIME_MAP_OVERRIDE_TIMEZONE")
    try:
        ZoneInfo(cleaned)
    except (ZoneInfoNotFoundError, ValueError):
        raise ApiError(422, "timezone must be an IANA name", "TIME_MAP_OVERRIDE_TIMEZONE") from None
    return cleaned


def validate_override_date_range(start: date, end: date) -> None:
    if start > end:
        raise ApiError(
            422,
            "local_end_date must be on or after local_start_date",
            "TIME_MAP_OVERRIDE_INVALID_RANGE",
        )


def validate_override_bands(bands: list[TimeMapBandIn]) -> None:
    """Empty bands are allowed. With strict_mode they mean unavailable all day.

    A band whose end is not after its start crosses midnight (or is empty).
    Split that span into two bands that each stay inside one local day.
    """
    for index, band in enumerate(bands):
        if band.end_time <= band.start_time:
            raise ApiError(
                422,
                (
                    f"Band {index} crosses midnight; split it into two bands "
                    "that stay within one local day"
                ),
                "TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT",
                band_index=index,
            )
    validate_bands(bands)


def find_overlapping_override(
    db: Session,
    map_id: UUID,
    start: date,
    end: date,
    *,
    exclude_id: UUID | None = None,
) -> TimeMapOverride | None:
    """Inclusive local-date overlap on one map. Other maps are independent."""
    query = db.query(TimeMapOverride).filter(
        TimeMapOverride.map_id == map_id,
        TimeMapOverride.local_start_date <= end,
        TimeMapOverride.local_end_date >= start,
    )
    if exclude_id is not None:
        query = query.filter(TimeMapOverride.id != exclude_id)
    return query.order_by(TimeMapOverride.local_start_date, TimeMapOverride.id).first()


def _raise_overlap(conflict: TimeMapOverride) -> None:
    raise ApiError(
        409,
        "Override date range overlaps another override on this Time Map",
        "TIME_MAP_OVERRIDE_OVERLAP",
        conflicting_override_id=str(conflict.id),
        conflicting_local_start_date=conflict.local_start_date.isoformat(),
        conflicting_local_end_date=conflict.local_end_date.isoformat(),
    )


def _present(updates: dict[str, object], key: str, current: object) -> object:
    if key not in updates or updates[key] is None:
        return current
    return updates[key]


def _lock_map(db: Session, window: FocusWindow) -> None:
    db.query(FocusWindow).filter(FocusWindow.id == window.id).with_for_update().one()


def _assign_bands(override: TimeMapOverride, bands: list[TimeMapBandIn]) -> None:
    override.bands.clear()
    for band_in in bands:
        override.bands.append(
            TimeMapOverrideBand(
                tier=band_in.tier,
                start_time=band_in.start_time,
                end_time=band_in.end_time,
                days_of_week=band_in.days_of_week,
                sort_order=band_in.sort_order,
            )
        )


def create_time_map_override(
    db: Session,
    window: FocusWindow,
    *,
    local_start_date: date,
    local_end_date: date,
    timezone_name: str,
    strict_mode: bool,
    bands: list[TimeMapBandIn],
) -> TimeMapOverride:
    timezone_name = validate_iana_timezone(timezone_name)
    validate_override_date_range(local_start_date, local_end_date)
    validate_override_bands(bands)
    _lock_map(db, window)
    conflict = find_overlapping_override(db, window.id, local_start_date, local_end_date)
    if conflict is not None:
        _raise_overlap(conflict)
    row = TimeMapOverride(
        owner_id=window.owner_id,
        map_id=window.id,
        local_start_date=local_start_date,
        local_end_date=local_end_date,
        timezone=timezone_name,
        strict_mode=strict_mode,
    )
    _assign_bands(row, bands)
    db.add(row)
    db.flush()
    return row


def update_time_map_override(
    db: Session,
    window: FocusWindow,
    row: TimeMapOverride,
    updates: dict[str, object],
    bands: list[TimeMapBandIn] | None,
) -> TimeMapOverride:
    start = _present(updates, "local_start_date", row.local_start_date)
    end = _present(updates, "local_end_date", row.local_end_date)
    if not isinstance(start, date) or not isinstance(end, date):
        raise ApiError(
            422,
            "local_start_date and local_end_date must be calendar dates",
            "TIME_MAP_OVERRIDE_INVALID_RANGE",
        )
    timezone_name = row.timezone
    if "timezone" in updates and updates["timezone"] is not None:
        timezone_name = validate_iana_timezone(str(updates["timezone"]))
    validate_override_date_range(start, end)
    if bands is not None:
        validate_override_bands(bands)
    _lock_map(db, window)
    conflict = find_overlapping_override(
        db,
        window.id,
        start,
        end,
        exclude_id=row.id,
    )
    if conflict is not None:
        _raise_overlap(conflict)
    row.local_start_date = start
    row.local_end_date = end
    row.timezone = timezone_name
    if "strict_mode" in updates and updates["strict_mode"] is not None:
        row.strict_mode = bool(updates["strict_mode"])
    if bands is not None:
        _assign_bands(row, bands)
    db.flush()
    return row
