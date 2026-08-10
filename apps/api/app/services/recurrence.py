"""Recurrence engine: RRULE patterns, every/every!, limited frames, quick-add tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

from app.api.errors import ApiError

WEEKDAY_TO_BYDAY = {
    "monday": "MO",
    "mon": "MO",
    "tuesday": "TU",
    "tue": "TU",
    "tues": "TU",
    "wednesday": "WE",
    "wed": "WE",
    "thursday": "TH",
    "thu": "TH",
    "thur": "TH",
    "thurs": "TH",
    "friday": "FR",
    "fri": "FR",
    "saturday": "SA",
    "sat": "SA",
    "sunday": "SU",
    "sun": "SU",
}

BYDAY_LABEL = {
    "MO": "Mon",
    "TU": "Tue",
    "WE": "Wed",
    "TH": "Thu",
    "FR": "Fri",
    "SA": "Sat",
    "SU": "Sun",
}

MONTH_INDEX = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

FREQ_UNITS = {
    "day": "DAILY",
    "days": "DAILY",
    "week": "WEEKLY",
    "weeks": "WEEKLY",
    "month": "MONTHLY",
    "months": "MONTHLY",
    "year": "YEARLY",
    "years": "YEARLY",
}

# every[!]? <pattern> [from ...] [to|until|through ...]
_WEEKDAY = (
    r"monday|mon|tuesday|tue|tues|wednesday|wed|thursday|thu|thur|thurs|"
    r"friday|fri|saturday|sat|sunday|sun"
)
_RECURRENCE_BLOCK = re.compile(
    rf"(?<=\s)(every!?)(?:\s+(\d+))?\s+"
    rf"(?:"
    rf"(day|days|week|weeks|month|months|year|years)"
    rf"|"
    rf"((?:{_WEEKDAY})(?:\s*,\s*(?:{_WEEKDAY}))*)"
    rf")"
    rf"(?=\s|$)",
    re.IGNORECASE,
)
_FROM_CLAUSE = re.compile(
    r"(?<=\s)from\s+(.+?)(?=\s+(?:to|until|through)\s+|\s*$)",
    re.IGNORECASE,
)
_UNTIL_CLAUSE = re.compile(
    r"(?<=\s)(?:to|until|through)\s+(.+?)(?=\s*$)",
    re.IGNORECASE,
)


@dataclass
class RecurrenceSpec:
    rrule: str
    is_fixed: bool = False
    timezone: str = "UTC"
    starts_on: date | None = None
    ends_on: date | None = None


def validate_rrule_pattern(rrule: str) -> str:
    cleaned = rrule.strip().upper().replace("RRULE:", "")
    if not cleaned.startswith("FREQ="):
        raise ApiError(422, "rrule must include FREQ=", "INVALID_RRULE")
    try:
        rrulestr(cleaned, dtstart=datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")))
    except (ValueError, TypeError) as exc:
        raise ApiError(422, f"Invalid rrule: {exc}", "INVALID_RRULE") from exc
    # Disallow UNTIL/COUNT in stored pattern — frames use starts_on/ends_on.
    if "UNTIL=" in cleaned or "COUNT=" in cleaned:
        raise ApiError(
            422,
            "Use starts_on/ends_on for series bounds; do not embed UNTIL/COUNT in rrule",
            "INVALID_RRULE",
        )
    return cleaned


def validate_frame(starts_on: date | None, ends_on: date | None) -> None:
    if starts_on is not None and ends_on is not None and ends_on < starts_on:
        raise ApiError(422, "ends_on must be on or after starts_on", "INVALID_FRAME")


def _as_local(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return dt.astimezone(tz)


def _occurrence_in_frame(occ_local: datetime, starts_on: date | None, ends_on: date | None) -> bool:
    day = occ_local.date()
    if starts_on is not None and day < starts_on:
        return False
    if ends_on is not None and day > ends_on:
        return False
    return True


def _build_rrule(pattern: str, *, dtstart: datetime):
    return rrulestr(pattern, dtstart=dtstart)


def first_due_at(
    spec: RecurrenceSpec,
    *,
    now: datetime | None = None,
    due_time: time | None = None,
) -> datetime | None:
    tz = ZoneInfo(spec.timezone)
    reference = _as_local(now or datetime.now(tz), tz)
    clock = due_time or time(9, 0)
    if spec.starts_on is not None:
        search_start = datetime.combine(spec.starts_on, clock, tzinfo=tz)
    else:
        search_start = datetime.combine(reference.date(), clock, tzinfo=tz)

    rule = _build_rrule(spec.rrule, dtstart=search_start)
    for occ in rule:
        occ_local = _as_local(occ, tz)
        if not _occurrence_in_frame(occ_local, spec.starts_on, spec.ends_on):
            if spec.ends_on is not None and occ_local.date() > spec.ends_on:
                break
            continue
        if occ_local < reference and spec.starts_on is None:
            continue
        return occ_local.astimezone(ZoneInfo("UTC"))
    return None


def next_due_at(
    spec: RecurrenceSpec,
    *,
    previous_due: datetime | None,
    completed_at: datetime,
) -> datetime | None:
    """Return next due in UTC, or None if the series is exhausted within the frame."""
    tz = ZoneInfo(spec.timezone)
    completed_local = _as_local(completed_at, tz)
    prev_local = _as_local(previous_due, tz) if previous_due else None

    if prev_local is not None:
        clock = time(prev_local.hour, prev_local.minute, prev_local.second)
    else:
        clock = time(9, 0)

    if spec.is_fixed:
        after = prev_local if prev_local is not None else completed_local
    else:
        after = completed_local

    frame_start = spec.starts_on or after.date()
    dtstart = datetime.combine(frame_start, clock, tzinfo=tz)
    rule = _build_rrule(spec.rrule, dtstart=dtstart)

    for occ in rule:
        occ_local = _as_local(occ, tz)
        if occ_local <= after:
            continue
        if not _occurrence_in_frame(occ_local, spec.starts_on, spec.ends_on):
            if spec.ends_on is not None and occ_local.date() > spec.ends_on:
                break
            continue
        return occ_local.astimezone(ZoneInfo("UTC"))
    return None


def humanize_recurrence(spec: RecurrenceSpec) -> str:
    bang = "Every!" if spec.is_fixed else "Every"
    parts = spec.rrule.upper().split(";")
    freq = "DAILY"
    interval = 1
    bydays: list[str] = []
    for part in parts:
        if part.startswith("FREQ="):
            freq = part.split("=", 1)[1]
        elif part.startswith("INTERVAL="):
            interval = int(part.split("=", 1)[1])
        elif part.startswith("BYDAY="):
            bydays = part.split("=", 1)[1].split(",")

    if bydays:
        day_labels = ", ".join(BYDAY_LABEL.get(d, d) for d in bydays)
        core = f"{bang} {day_labels}"
    else:
        unit = {
            "DAILY": "day" if interval == 1 else "days",
            "WEEKLY": "week" if interval == 1 else "weeks",
            "MONTHLY": "month" if interval == 1 else "months",
            "YEARLY": "year" if interval == 1 else "years",
        }.get(freq, freq.lower())
        if interval == 1:
            core = f"{bang} {unit}"
        else:
            core = f"{bang} {interval} {unit}"

    frame_bits: list[str] = []
    if spec.starts_on and spec.ends_on:
        frame_bits.append(f"{spec.starts_on.strftime('%b %d')}–{spec.ends_on.strftime('%b %d, %Y')}")
    elif spec.starts_on:
        frame_bits.append(f"from {spec.starts_on.strftime('%b %d, %Y')}")
    elif spec.ends_on:
        frame_bits.append(f"until {spec.ends_on.strftime('%b %d, %Y')}")

    if frame_bits:
        return f"{core} · {frame_bits[0]}"
    return core


def _parse_frame_date(token: str, *, local_today: date, tz: ZoneInfo) -> date | None:
    text = " ".join(token.strip().lower().split())
    if not text:
        return None
    if text in {"today"}:
        return local_today
    if text in {"tomorrow", "tom"}:
        return local_today + timedelta(days=1)
    if text == "next week":
        # Start of next week (Monday)
        days_ahead = (7 - local_today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return local_today + timedelta(days=days_ahead)
    if text in {"end of year", "end of the year"}:
        return date(local_today.year, 12, 31)
    if text in {"end of month", "end of the month"}:
        if local_today.month == 12:
            return date(local_today.year, 12, 31)
        return date(local_today.year, local_today.month + 1, 1) - timedelta(days=1)

    iso = re.fullmatch(r"(\d{4}-\d{2}-\d{2})", text)
    if iso:
        return date.fromisoformat(iso.group(1))

    us = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", text)
    if us:
        month, day = int(us.group(1)), int(us.group(2))
        year = int(us.group(3)) if us.group(3) else local_today.year
        return date(year, month, day)

    mon_day = re.fullmatch(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})",
        text,
    )
    if mon_day:
        month = MONTH_INDEX[mon_day.group(1)[:3]]
        return date(local_today.year, month, int(mon_day.group(2)))

    return None


def parse_recurrence_text(
    text: str,
    *,
    now: datetime | None = None,
    timezone_name: str = "UTC",
) -> tuple[str, RecurrenceSpec | None]:
    """Strip recurrence tokens from text; return (remaining_title, spec|None)."""
    working = f" {' '.join(text.strip().split())} "
    tz = ZoneInfo(timezone_name)
    reference = (now or datetime.now(tz)).astimezone(tz)
    local_today = reference.date()

    match = _RECURRENCE_BLOCK.search(working)
    if not match:
        return text.strip(), None

    is_fixed = match.group(1).lower() == "every!"
    interval = int(match.group(2) or "1")
    unit = match.group(3)
    weekdays_raw = match.group(4)

    if weekdays_raw:
        bydays: list[str] = []
        for token in re.split(r"\s*,\s*", weekdays_raw.strip()):
            key = token.lower()
            if key not in WEEKDAY_TO_BYDAY:
                raise ApiError(422, f"Unknown weekday: {token}", "INVALID_RECURRENCE")
            code = WEEKDAY_TO_BYDAY[key]
            if code not in bydays:
                bydays.append(code)
        rrule = f"FREQ=WEEKLY;INTERVAL={interval};BYDAY={','.join(bydays)}"
    else:
        freq = FREQ_UNITS[unit.lower()]
        rrule = f"FREQ={freq};INTERVAL={interval}"

    working = f"{working[: match.start()]} {working[match.end():]}"

    starts_on: date | None = None
    ends_on: date | None = None

    from_match = _FROM_CLAUSE.search(working)
    if from_match:
        starts_on = _parse_frame_date(from_match.group(1), local_today=local_today, tz=tz)
        if starts_on is None:
            raise ApiError(422, f"Could not parse recurrence start: {from_match.group(1)}", "INVALID_FRAME")
        working = f"{working[: from_match.start()]} {working[from_match.end():]}"

    until_match = _UNTIL_CLAUSE.search(working)
    if until_match:
        ends_on = _parse_frame_date(until_match.group(1), local_today=local_today, tz=tz)
        if ends_on is None:
            raise ApiError(422, f"Could not parse recurrence end: {until_match.group(1)}", "INVALID_FRAME")
        working = f"{working[: until_match.start()]} {working[until_match.end():]}"

    validate_frame(starts_on, ends_on)
    rrule = validate_rrule_pattern(rrule)

    title = " ".join(working.split()).strip() or text.strip()
    return title, RecurrenceSpec(
        rrule=rrule,
        is_fixed=is_fixed,
        timezone=timezone_name,
        starts_on=starts_on,
        ends_on=ends_on,
    )


def spec_from_parts(
    *,
    rrule: str | None = None,
    is_fixed: bool = False,
    timezone: str = "UTC",
    starts_on: date | None = None,
    ends_on: date | None = None,
    text: str | None = None,
) -> RecurrenceSpec:
    if text:
        _, parsed = parse_recurrence_text(f" {text.strip()} ", timezone_name=timezone)
        if parsed is None:
            raise ApiError(422, "Could not parse recurrence text", "INVALID_RECURRENCE")
        return parsed
    if not rrule:
        raise ApiError(422, "rrule or text is required", "INVALID_RECURRENCE")
    validate_frame(starts_on, ends_on)
    return RecurrenceSpec(
        rrule=validate_rrule_pattern(rrule),
        is_fixed=is_fixed,
        timezone=timezone,
        starts_on=starts_on,
        ends_on=ends_on,
    )
