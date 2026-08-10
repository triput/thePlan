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
