"""E10 bootstrap / schema readiness checks."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.bootstrap import SYSTEM_FILTERS, ensure_bootstrap_user
from app.models import Reminder, SavedFilter, ScheduleRun, Task
from app.models.enums import ScheduleStatus


def test_system_filter_slugs() -> None:
    assert [slug for _, slug, _, _ in SYSTEM_FILTERS] == ["inbox", "today", "upcoming"]


def test_ensure_bootstrap_user_seeds_smart_views(db_session: Session) -> None:
    user = ensure_bootstrap_user(db_session, commit=False)
    slugs = {
        row.slug
        for row in db_session.query(SavedFilter)
        .filter(SavedFilter.owner_id == user.id, SavedFilter.is_system.is_(True))
        .all()
    }
    assert slugs == {"inbox", "today", "upcoming"}


def test_task_has_deferred_schedule_columns() -> None:
    columns = {c.name for c in inspect(Task).columns}
    assert {"due_at", "deadline_at", "soft_target_at"} <= columns


def test_schedule_status_includes_overbooked() -> None:
    assert ScheduleStatus.overbooked.value == "overbooked"


def test_stub_tables_mapped() -> None:
    from app.models import CalendarAccount, FocusWindow, RecurrenceRule, Reminder as ReminderModel

    assert FocusWindow.__tablename__ == "focus_windows"
    assert RecurrenceRule.__tablename__ == "recurrence_rules"
    assert ReminderModel.__tablename__ == "reminders"
    assert CalendarAccount.__tablename__ == "calendar_accounts"


def test_reminder_fire_at_index_declared() -> None:
    names = {idx.name for idx in Reminder.__table__.indexes}
    assert "idx_reminders_fire_at" in names


def test_schedule_runs_owner_index_declared() -> None:
    names = {idx.name for idx in ScheduleRun.__table__.indexes}
    assert "idx_schedule_runs_owner" in names
