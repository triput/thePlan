"""Human-friendly duration parsing (SPEC §5 / S1 duration slice)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.api.errors import ApiError

_MINUTE_UNIT = frozenset({"m", "min", "mins", "minute", "minutes"})
_HOUR_UNIT = frozenset({"h", "hr", "hrs", "hour", "hours"})
_WORKDAY_UNIT = frozenset({"workday", "workdays", "wd", "wds"})
_FORBIDDEN_AMBIGUOUS = frozenset(
    {
        "d",
        "day",
        "days",
        "w",
        "wk",
        "wks",
        "week",
        "weeks",
        "mo",
        "mon",
        "mth",
        "month",
        "months",
        "y",
        "yr",
        "yrs",
        "year",
        "years",
    }
)

_TOKEN = re.compile(
    r"(?P<num>-?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>minutes|minute|mins|min|hours|hour|hrs|hr|"
    r"workdays|workday|wds|wd|"
    r"months|month|mth|mon|mo|"
    r"days|day|weeks|week|wks|wk|years|year|yrs|yr|"
    r"m|h|d|w|y)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FriendlyDurationResult:
    minutes: int
    conversion_note: str | None = None


def _round_minutes(value: Decimal) -> int:
    if value <= 0:
        return 0
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_friendly_duration(
    raw: int | str,
    *,
    field_label: str,
    nominal_workday_minutes: int | None = None,
    allow_workdays: bool = False,
    allow_zero: bool = False,
) -> FriendlyDurationResult:
    """Parse friendly duration into whole minutes.

    Bare numbers in minutes-labeled fields are minutes. Rejects negatives and
    ambiguous calendar/week/month shorthands. Positive values that round to zero
    require at least one minute unless ``allow_zero``.
    """
    if isinstance(raw, int):
        if raw < 0:
            raise ApiError(
                422,
                f"{field_label} must be non-negative",
                "INVALID_DURATION",
            )
        if raw == 0 and not allow_zero:
            raise ApiError(
                422,
                f"{field_label} must be at least 1 minute",
                "INVALID_DURATION",
            )
        return FriendlyDurationResult(minutes=raw)

    text = " ".join(str(raw).strip().split())
    if not text:
        raise ApiError(422, f"{field_label} is required", "INVALID_DURATION")

    if text.lstrip("-").isdigit() or (
        text.count(".") == 1 and text.lstrip("-").replace(".", "", 1).isdigit()
    ):
        as_decimal = Decimal(text)
        if as_decimal < 0:
            raise ApiError(
                422,
                f"{field_label} must be non-negative",
                "INVALID_DURATION",
            )
        minutes = _round_minutes(as_decimal)
        if minutes == 0 and not allow_zero:
            raise ApiError(
                422,
                f"{field_label} must be at least 1 minute",
                "INVALID_DURATION",
            )
        return FriendlyDurationResult(minutes=minutes)

    total = Decimal("0")
    workday_minutes_contrib = Decimal("0")
    matched = False
    for match in _TOKEN.finditer(text):
        matched = True
        num = Decimal(match.group("num"))
        if num < 0:
            raise ApiError(
                422,
                f"{field_label} must be non-negative",
                "INVALID_DURATION",
            )
        unit = match.group("unit").lower()
        if unit in _FORBIDDEN_AMBIGUOUS:
            raise ApiError(
                422,
                f"Ambiguous duration unit {unit!r} in {field_label}; "
                "use hours/minutes or explicit workdays",
                "AMBIGUOUS_DURATION_UNIT",
            )
        if unit in _MINUTE_UNIT:
            total += num
        elif unit in _HOUR_UNIT:
            total += num * Decimal("60")
        elif unit in _WORKDAY_UNIT:
            if not allow_workdays:
                raise ApiError(
                    422,
                    f"Workday units are not allowed for {field_label}",
                    "INVALID_DURATION",
                )
            if nominal_workday_minutes is None or nominal_workday_minutes <= 0:
                raise ApiError(
                    422,
                    "nominal_workday_minutes must be configured before workday effort input",
                    "INVALID_DURATION",
                )
            workday_minutes_contrib += num * Decimal(nominal_workday_minutes)
        else:
            raise ApiError(
                422,
                f"Unsupported duration unit in {field_label}",
                "INVALID_DURATION",
            )

    if not matched:
        raise ApiError(
            422,
            f"Could not parse {field_label}: {raw!r}",
            "INVALID_DURATION",
        )

    leftover = _TOKEN.sub("", text).strip()
    if leftover:
        raise ApiError(
            422,
            f"Could not parse {field_label}: {raw!r}",
            "INVALID_DURATION",
        )

    total += workday_minutes_contrib
    minutes = _round_minutes(total)
    if minutes == 0 and not allow_zero:
        raise ApiError(
            422,
            f"{field_label} must be at least 1 minute",
            "INVALID_DURATION",
        )

    note: str | None = None
    if workday_minutes_contrib > 0 and nominal_workday_minutes is not None:
        note = (
            f"Converted workday effort using nominal_workday_minutes="
            f"{nominal_workday_minutes} → {minutes} minutes stored"
        )
    return FriendlyDurationResult(minutes=minutes, conversion_note=note)
