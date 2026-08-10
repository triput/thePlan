from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models.enums import TaskPriority

EPIC_PATTERN = re.compile(
    r'(?:!!|epic:)(?:"([^"]+)"|\'([^\']+)\'|(\S+))',
    re.IGNORECASE,
)
PROJECT_SECTION_PATTERN = re.compile(
    r'#(?:"([^"]+)"|\'([^\']+)\'|([^/\s]+)(?:/([^/\s]+))?)',
    re.IGNORECASE,
)
PRIORITY_PATTERN = re.compile(r"(?<=\s)(?:p|P|!)(1|2|3|4)(?=\s|$)")
DURATION_PATTERN = re.compile(
    r"(?<=\s)(\d+(?:\.\d+)?)\s*"
    r"(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|"
    r"w|wk|wks|week|weeks|mo|mon|mth|month|months|y|yr|yrs|year|years)"
    r"(?=\s|$)",
    re.IGNORECASE,
)
TIME_WINDOW_PATTERN = re.compile(r"(?<=\s)@(morning|afternoon|evening)(?=\s|$)", re.IGNORECASE)
TIME_AT_PATTERN = re.compile(
    r"(?<=\s)at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?=\s|$)",
    re.IGNORECASE,
)
RELATIVE_DATE_PATTERN = re.compile(
    r"(?<=\s)(today|tomorrow|tom|yesterday)(?=\s|$)",
    re.IGNORECASE,
)
NEXT_WEEKDAY_PATTERN = re.compile(
    r"(?<=\s)next\s+(monday|mon|tuesday|tue|tues|wednesday|wed|thursday|thu|thur|thurs|"
    r"friday|fri|saturday|sat|sunday|sun)(?=\s|$)",
    re.IGNORECASE,
)
ISO_DATE_PATTERN = re.compile(r"(?<=\s)(\d{4}-\d{2}-\d{2})(?=\s|$)")
US_DATE_PATTERN = re.compile(r"(?<=\s)(\d{1,2}/\d{1,2}/\d{4})(?=\s|$)")
DASH_DATE_PATTERN = re.compile(r"(?<=\s)(\d{1,2}-[A-Za-z]{3})(?=\s|$)")
MONTH_DAY_PATTERN = re.compile(
    r"(?<=\s)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})(?=\s|$)",
    re.IGNORECASE,
)

DURATION_MULTIPLIERS: dict[str, int] = {
    "m": 1,
    "min": 1,
    "mins": 1,
    "minute": 1,
    "minutes": 1,
    "h": 60,
    "hr": 60,
    "hrs": 60,
    "hour": 60,
    "hours": 60,
    "d": 480,
    "day": 480,
    "days": 480,
    "w": 2400,
    "wk": 2400,
    "wks": 2400,
    "week": 2400,
    "weeks": 2400,
    "mo": 9600,
    "mon": 9600,
    "mth": 9600,
    "month": 9600,
    "months": 9600,
    "y": 115200,
    "yr": 115200,
    "yrs": 115200,
    "year": 115200,
    "years": 115200,
}

WEEKDAY_INDEX = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
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


@dataclass
class QuickAddDraft:
    title: str
    priority: TaskPriority | None = None
    estimated_duration_minutes: int | None = None
    due_at: datetime | None = None
    epic_name: str | None = None
    project_name: str | None = None
    section_name: str | None = None
    preferred_time_window: str | None = None
    unresolved: list[str] = field(default_factory=list)
    recurrence_rrule: str | None = None
    recurrence_is_fixed: bool = False
    recurrence_starts_on: date | None = None
    recurrence_ends_on: date | None = None
    recurrence_timezone: str = "UTC"
    recurrence_display: str | None = None


def _first_group(match: re.Match[str]) -> str:
    return next(group for group in match.groups() if group is not None)


def _remove_match(text: str, match: re.Match[str]) -> str:
    start, end = match.span()
    return f"{text[:start]} {text[end:]}".strip()


def _parse_duration_minutes(value: str, unit: str) -> int:
    multiplier = DURATION_MULTIPLIERS[unit.lower()]
    return int(float(value) * multiplier)


def _next_weekday(base: date, weekday: int) -> date:
    days_ahead = (weekday - base.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def _combine_date_time(
    due_date: date,
    due_time: time | None,
    tz: ZoneInfo,
) -> datetime:
    if due_time is None:
        due_time = time(9, 0)
    local_dt = datetime.combine(due_date, due_time, tzinfo=tz)
    return local_dt.astimezone(ZoneInfo("UTC"))


def _parse_at_time(match: re.Match[str]) -> time:
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return time(hour, minute)


def parse_quick_add(text: str, *, now: datetime | None = None, timezone_name: str = "UTC") -> QuickAddDraft:
    working = f" {' '.join(text.strip().split())} "
    tz = ZoneInfo(timezone_name)
    reference = (now or datetime.now(tz)).astimezone(tz)
    local_today = reference.date()

    draft = QuickAddDraft(title=text.strip())
    due_date: date | None = None
    due_time: time | None = None

    from app.services.recurrence import first_due_at, humanize_recurrence, parse_recurrence_text

    title_after_recurrence, recurrence = parse_recurrence_text(
        working,
        now=reference,
        timezone_name=timezone_name,
    )
    if recurrence is not None:
        draft.recurrence_rrule = recurrence.rrule
        draft.recurrence_is_fixed = recurrence.is_fixed
        draft.recurrence_starts_on = recurrence.starts_on
        draft.recurrence_ends_on = recurrence.ends_on
        draft.recurrence_timezone = recurrence.timezone
        draft.recurrence_display = humanize_recurrence(recurrence)
        working = f" {title_after_recurrence} "

    epic_match = EPIC_PATTERN.search(working)
    if epic_match:
        draft.epic_name = _first_group(epic_match)
        working = _remove_match(working, epic_match)

    project_match = PROJECT_SECTION_PATTERN.search(working)
    if project_match:
        draft.project_name = project_match.group(1) or project_match.group(2) or project_match.group(3)
        draft.section_name = project_match.group(4)
        working = _remove_match(working, project_match)

    priority_match = PRIORITY_PATTERN.search(working)
    if priority_match:
        draft.priority = TaskPriority(f"p{priority_match.group(1)}")
        working = _remove_match(working, priority_match)

    duration_match = DURATION_PATTERN.search(working)
    if duration_match:
        draft.estimated_duration_minutes = _parse_duration_minutes(
            duration_match.group(1),
            duration_match.group(2),
        )
        working = _remove_match(working, duration_match)

    window_match = TIME_WINDOW_PATTERN.search(working)
    if window_match:
        draft.preferred_time_window = window_match.group(1).lower()
        working = _remove_match(working, window_match)

    time_match = TIME_AT_PATTERN.search(working)
    if time_match:
        due_time = _parse_at_time(time_match)
        working = _remove_match(working, time_match)

    relative_match = RELATIVE_DATE_PATTERN.search(working)
    if relative_match:
        token = relative_match.group(1).lower()
        if token in {"today"}:
            due_date = local_today
        elif token in {"tomorrow", "tom"}:
            due_date = local_today + timedelta(days=1)
        elif token == "yesterday":
            due_date = local_today - timedelta(days=1)
        working = _remove_match(working, relative_match)

    next_weekday_match = NEXT_WEEKDAY_PATTERN.search(working)
    if next_weekday_match:
        weekday = WEEKDAY_INDEX[next_weekday_match.group(1).lower()]
        due_date = _next_weekday(local_today, weekday)
        working = _remove_match(working, next_weekday_match)

    iso_match = ISO_DATE_PATTERN.search(working)
    if iso_match:
        due_date = date.fromisoformat(iso_match.group(1))
        working = _remove_match(working, iso_match)

    us_match = US_DATE_PATTERN.search(working)
    if us_match:
        month, day, year = us_match.group(1).split("/")
        due_date = date(int(year), int(month), int(day))
        working = _remove_match(working, us_match)

    dash_match = DASH_DATE_PATTERN.search(working)
    if dash_match:
        day_str, month_str = dash_match.group(1).split("-")
        month = MONTH_INDEX[month_str.lower()]
        due_date = date(local_today.year, month, int(day_str))
        working = _remove_match(working, dash_match)

    month_day_match = MONTH_DAY_PATTERN.search(working)
    if month_day_match:
        month = MONTH_INDEX[month_day_match.group(1).lower()[:3]]
        due_date = date(local_today.year, month, int(month_day_match.group(2)))
        working = _remove_match(working, month_day_match)

    if due_date is not None:
        draft.due_at = _combine_date_time(due_date, due_time, tz)
    elif recurrence is not None:
        draft.due_at = first_due_at(recurrence, now=reference, due_time=due_time)

    draft.title = working.strip()
    if not draft.title:
        draft.title = text.strip()

    return draft
