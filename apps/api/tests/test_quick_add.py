from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.enums import TaskPriority
from app.services.quick_add import parse_quick_add


def test_duration_minutes_not_months() -> None:
    draft = parse_quick_add("Write tests 1.5m p2")
    assert draft.estimated_duration_minutes == 1
    assert draft.priority == TaskPriority.p2
    assert draft.title == "Write tests"


def test_duration_hours() -> None:
    draft = parse_quick_add("Review architecture spec 1.5h p1")
    assert draft.estimated_duration_minutes == 90
    assert draft.priority == TaskPriority.p1
    assert draft.title == "Review architecture spec"


def test_duration_months_use_mo_suffix() -> None:
    draft = parse_quick_add("Plan roadmap 2mo")
    assert draft.estimated_duration_minutes == 19200
    assert draft.title == "Plan roadmap"


def test_epic_project_section_and_due_date() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("UTC"))
    draft = parse_quick_add(
        "Review architecture spec 1.5h p1 next Tue at 9am !!Organon #Dev/Backend",
        now=now,
        timezone_name="UTC",
    )
    assert draft.epic_name == "Organon"
    assert draft.project_name == "Dev"
    assert draft.section_name == "Backend"
    assert draft.estimated_duration_minutes == 90
    assert draft.priority == TaskPriority.p1
    assert draft.due_at is not None
    assert draft.due_at.hour == 9
    assert draft.title == "Review architecture spec"


def test_tonight_at_time() -> None:
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    draft = parse_quick_add(
        "Finish entering Coursera specialization tasks tonight at 9PM",
        now=now,
        timezone_name="America/Los_Angeles",
    )
    assert draft.title == "Finish entering Coursera specialization tasks"
    assert draft.due_at is not None
    assert draft.due_at.astimezone(ZoneInfo("America/Los_Angeles")).hour == 21
    assert draft.due_at.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat() == "2026-08-14"


def test_tomorrow_relative_date() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("UTC"))
    draft = parse_quick_add("Ship it tomorrow p3", now=now, timezone_name="UTC")
    assert draft.title == "Ship it"
    assert draft.priority == TaskPriority.p3
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-08-11"


def test_quoted_project_token() -> None:
    draft = parse_quick_add('Draft notes #"Client App"')
    assert draft.project_name == "Client App"
    assert draft.section_name is None
    assert draft.title == "Draft notes"


def test_unquoted_project_section_token() -> None:
    draft = parse_quick_add("Draft notes #Dev/Backend")
    assert draft.project_name == "Dev"
    assert draft.section_name == "Backend"
    assert draft.title == "Draft notes"


def test_bare_title_defaults() -> None:
    draft = parse_quick_add("Just a title")
    assert draft.title == "Just a title"
    assert draft.priority is None
    assert draft.estimated_duration_minutes is None
    assert draft.due_at is None
    assert draft.project_name is None


def test_duration_work_days() -> None:
    draft = parse_quick_add("Big chunk 2d")
    assert draft.estimated_duration_minutes == 960
    assert draft.title == "Big chunk"


def test_duration_prose_duration_n_minutes() -> None:
    draft = parse_quick_add("Deep work duration 60 minutes")
    assert draft.estimated_duration_minutes == 60
    assert draft.title == "Deep work"


def test_duration_prose_for_an_hour() -> None:
    draft = parse_quick_add("Focus block for an hour")
    assert draft.estimated_duration_minutes == 60
    assert draft.title == "Focus block"


def test_duration_prose_for_n_hours() -> None:
    draft = parse_quick_add("Workshop for 2 hours p2")
    assert draft.estimated_duration_minutes == 120
    assert draft.priority == TaskPriority.p2
    assert draft.title == "Workshop"


def test_at_24h_colon() -> None:
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    draft = parse_quick_add(
        "Ship notes tonight at 21:00",
        now=now,
        timezone_name="America/Los_Angeles",
    )
    assert draft.title == "Ship notes"
    assert draft.due_at is not None
    local = draft.due_at.astimezone(ZoneInfo("America/Los_Angeles"))
    assert local.hour == 21
    assert local.minute == 0


def test_bare_meridiem_time() -> None:
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    draft = parse_quick_add(
        "Call dentist tomorrow 8pm",
        now=now,
        timezone_name="America/Los_Angeles",
    )
    assert draft.title == "Call dentist"
    local = draft.due_at.astimezone(ZoneInfo("America/Los_Angeles"))
    assert local.hour == 20
    assert local.date().isoformat() == "2026-08-15"


def test_bare_24h_colon() -> None:
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    draft = parse_quick_add(
        "Standup tomorrow 14:30",
        now=now,
        timezone_name="America/Los_Angeles",
    )
    local = draft.due_at.astimezone(ZoneInfo("America/Los_Angeles"))
    assert local.hour == 14
    assert local.minute == 30
    assert draft.title == "Standup"


def test_military_time_at_and_bare() -> None:
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ZoneInfo("UTC"))
    with_at = parse_quick_add("Deploy tonight at 2100", now=now, timezone_name="UTC")
    bare = parse_quick_add("Deploy tonight 2100", now=now, timezone_name="UTC")
    assert with_at.due_at is not None and with_at.due_at.hour == 21
    assert bare.due_at is not None and bare.due_at.hour == 21
    assert with_at.title == "Deploy"
    assert bare.title == "Deploy"


def test_military_does_not_eat_year_token() -> None:
    draft = parse_quick_add("Write 2026 goals")
    assert draft.due_at is None
    assert draft.title == "Write 2026 goals"


def test_combined_due_and_duration_prose() -> None:
    now = datetime(2026, 8, 14, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    draft = parse_quick_add(
        "Study session tonight at 20:00 duration 60 minutes",
        now=now,
        timezone_name="America/Los_Angeles",
    )
    assert draft.estimated_duration_minutes == 60
    local = draft.due_at.astimezone(ZoneInfo("America/Los_Angeles"))
    assert local.hour == 20
    assert draft.title == "Study session"

