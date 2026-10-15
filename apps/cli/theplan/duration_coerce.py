"""Duration helpers for CLI → API payloads.

Plain minute integers stay JSON numbers. Friendly strings for estimate-style
fields may remain strings (server parses). Bound fields that only accept ints
are coerced locally with the same hour/minute rules as the API friendly parser.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from theplan.errors import CliError

_PLAIN_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")

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


def duration_json_value(raw: str) -> int | str:
    """Pass plain minute integers as JSON numbers; keep friendly strings as strings."""
    text = " ".join(raw.strip().split())
    if _PLAIN_NUMBER.fullmatch(text) and "." not in text:
        return int(text)
    return text


def _round_minutes(value: Decimal) -> int:
    if value <= 0:
        return 0
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def duration_minutes_value(
    raw: str,
    *,
    field_label: str,
    nominal_workday_minutes: int | None = None,
    allow_workdays: bool = False,
) -> int:
    """Parse friendly duration into whole minutes for int-only API fields.

    Mirrors apps/api friendly-duration rules (bare numbers = minutes; h/m
    composites; reject ambiguous calendar units). Workday units require
    ``allow_workdays`` and a positive ``nominal_workday_minutes``.
    """
    text = " ".join(str(raw).strip().split())
    if not text:
        raise CliError(
            code="INVALID_USAGE",
            message=f"{field_label} is required",
            exit_code=1,
        )

    if text.lstrip("-").isdigit() or (
        text.count(".") == 1 and text.lstrip("-").replace(".", "", 1).isdigit()
    ):
        as_decimal = Decimal(text)
        if as_decimal < 0:
            raise CliError(
                code="INVALID_USAGE",
                message=f"{field_label} must be non-negative",
                exit_code=1,
            )
        minutes = _round_minutes(as_decimal)
        if minutes == 0:
            raise CliError(
                code="INVALID_USAGE",
                message=f"{field_label} must be at least 1 minute",
                exit_code=1,
            )
        return minutes

    total = Decimal("0")
    workday_contrib = Decimal("0")
    matched = False
    for match in _TOKEN.finditer(text):
        matched = True
        num = Decimal(match.group("num"))
        if num < 0:
            raise CliError(
                code="INVALID_USAGE",
                message=f"{field_label} must be non-negative",
                exit_code=1,
            )
        unit = match.group("unit").lower()
        if unit in _FORBIDDEN_AMBIGUOUS:
            raise CliError(
                code="INVALID_USAGE",
                message=(
                    f"Ambiguous duration unit {unit!r} in {field_label}; "
                    "use hours/minutes (e.g. 1h, 90m, 1h 30m)"
                ),
                exit_code=1,
            )
        if unit in _MINUTE_UNIT:
            total += num
        elif unit in _HOUR_UNIT:
            total += num * Decimal("60")
        elif unit in _WORKDAY_UNIT:
            if not allow_workdays:
                raise CliError(
                    code="INVALID_USAGE",
                    message=(
                        f"Workday units are not allowed for {field_label}; "
                        "use hours/minutes (e.g. 1h, 120)"
                    ),
                    exit_code=1,
                )
            if nominal_workday_minutes is None or nominal_workday_minutes <= 0:
                raise CliError(
                    code="INVALID_USAGE",
                    message=(
                        f"{field_label} workday units need nominal_workday_minutes "
                        "(settings get → nominal_workday_minutes), or use hours/minutes"
                    ),
                    exit_code=1,
                )
            workday_contrib += num * Decimal(nominal_workday_minutes)
        else:
            raise CliError(
                code="INVALID_USAGE",
                message=f"Unsupported duration unit in {field_label}",
                exit_code=1,
            )

    if not matched:
        raise CliError(
            code="INVALID_USAGE",
            message=f"Could not parse {field_label}: {raw!r}",
            exit_code=1,
        )

    leftover = _TOKEN.sub("", text).strip()
    if leftover:
        raise CliError(
            code="INVALID_USAGE",
            message=f"Could not parse {field_label}: {raw!r}",
            exit_code=1,
        )

    minutes = _round_minutes(total + workday_contrib)
    if minutes == 0:
        raise CliError(
            code="INVALID_USAGE",
            message=f"{field_label} must be at least 1 minute",
            exit_code=1,
        )
    return minutes
