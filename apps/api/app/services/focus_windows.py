from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import FocusWindow, TimeMapBand
from app.models.enums import TimeMapBandTier
from app.schemas import TimeMapBandIn

DEFAULT_FOCUS_WINDOWS: tuple[tuple[str, time, time], ...] = (
    ("Morning", time(8, 0), time(12, 0)),
    ("Afternoon", time(12, 0), time(17, 0)),
    ("Evening", time(17, 0), time(21, 0)),
)

ALL_DAYS_BITSET = 127


def _band_times_overlap(a: TimeMapBandIn | TimeMapBand, b: TimeMapBandIn | TimeMapBand) -> bool:
    shared_days = a.days_of_week & b.days_of_week
    if shared_days == 0:
        return False
    return a.start_time < b.end_time and b.start_time < a.end_time


def validate_bands(bands: list[TimeMapBandIn]) -> None:
    for band in bands:
        if band.end_time <= band.start_time:
            raise ApiError(422, "end_time must be after start_time", "FOCUS_WINDOW_INVALID_RANGE")

    for index, left in enumerate(bands):
        for right in bands[index + 1 :]:
            if left.tier != right.tier:
                continue
            if _band_times_overlap(left, right):
                raise ApiError(
                    422,
                    f"Overlapping {left.tier.value} bands on shared days",
                    "TIME_MAP_BAND_OVERLAP",
                )


def replace_bands(db: Session, map: FocusWindow, bands: list[TimeMapBandIn]) -> None:
    validate_bands(bands)
    map.bands.clear()
    for band_in in bands:
        map.bands.append(
            TimeMapBand(
                tier=band_in.tier,
                start_time=band_in.start_time,
                end_time=band_in.end_time,
                days_of_week=band_in.days_of_week,
                sort_order=band_in.sort_order,
            )
        )
    db.flush()


def resolve_create_bands(body) -> list[TimeMapBandIn]:
    if body.bands is not None:
        return body.bands
    if body.start_time is None or body.end_time is None:
        raise ApiError(
            422,
            "Provide bands or legacy start_time/end_time",
            "FOCUS_WINDOW_INVALID_RANGE",
        )
    return [
        TimeMapBandIn(
            tier=TimeMapBandTier.green,
            start_time=body.start_time,
            end_time=body.end_time,
            days_of_week=body.days_of_week if body.days_of_week is not None else ALL_DAYS_BITSET,
            sort_order=0,
        )
    ]


def resolve_create_strict_mode(body) -> bool:
    if body.is_hard is not None:
        return body.is_hard
    return body.strict_mode


def resolve_update_bands(body, existing: FocusWindow) -> list[TimeMapBandIn] | None:
    if body.bands is not None:
        return body.bands
    legacy_fields = (body.start_time, body.end_time, body.days_of_week)
    if not any(value is not None for value in legacy_fields):
        return None

    if body.start_time is None or body.end_time is None:
        if len(existing.bands) != 1:
            raise ApiError(
                422,
                "Legacy start_time/end_time update requires a single existing band",
                "FOCUS_WINDOW_INVALID_RANGE",
            )
        current = existing.bands[0]
        return [
            TimeMapBandIn(
                tier=current.tier,
                start_time=body.start_time or current.start_time,
                end_time=body.end_time or current.end_time,
                days_of_week=body.days_of_week if body.days_of_week is not None else current.days_of_week,
                sort_order=current.sort_order,
            )
        ]

    return [
        TimeMapBandIn(
            tier=TimeMapBandTier.green,
            start_time=body.start_time,
            end_time=body.end_time,
            days_of_week=body.days_of_week if body.days_of_week is not None else ALL_DAYS_BITSET,
            sort_order=0,
        )
    ]


def ensure_default_focus_windows(db: Session, user_id: uuid.UUID) -> list[FocusWindow]:
    """Insert Morning/Afternoon/Evening when the user has no focus windows."""
    existing = (
        db.query(FocusWindow.id).filter(FocusWindow.owner_id == user_id).limit(1).first()
    )
    if existing is not None:
        return []

    created: list[FocusWindow] = []
    for name, start_time, end_time in DEFAULT_FOCUS_WINDOWS:
        window = FocusWindow(
            owner_id=user_id,
            name=name,
            strict_mode=False,
        )
        window.bands.append(
            TimeMapBand(
                tier=TimeMapBandTier.green,
                start_time=start_time,
                end_time=end_time,
                days_of_week=ALL_DAYS_BITSET,
                sort_order=0,
            )
        )
        db.add(window)
        created.append(window)
    db.flush()
    return created
