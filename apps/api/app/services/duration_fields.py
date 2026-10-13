"""Resolve int-or-string duration fields on API writes."""

from __future__ import annotations

from app.api.errors import ApiError
from app.services.friendly_duration import FriendlyDurationResult, parse_friendly_duration


def resolve_minutes_field(
    raw: int | str | None,
    *,
    field_label: str,
    nominal_workday_minutes: int | None,
    allow_workdays: bool,
    allow_zero: bool,
    required: bool = False,
) -> FriendlyDurationResult | None:
    if raw is None:
        if required:
            raise ApiError(422, f"{field_label} is required", "INVALID_DURATION")
        return None
    return parse_friendly_duration(
        raw,
        field_label=field_label,
        nominal_workday_minutes=nominal_workday_minutes,
        allow_workdays=allow_workdays,
        allow_zero=allow_zero,
    )
