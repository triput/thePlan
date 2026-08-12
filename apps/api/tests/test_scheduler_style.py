"""Unit tests for schedule style resolution and workday bounds."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import ScheduleStyle, Task, UserSettings
from app.scheduler.placement import workday_bounds
from app.scheduler.style import effective_schedule_style


def _settings(**overrides: object) -> UserSettings:
    settings = UserSettings(owner_id=uuid4())
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _task(**overrides: object) -> Task:
    task = Task(owner_id=uuid4(), title="t")
    for key, value in overrides.items():
        setattr(task, key, value)
    return task


def test_effective_schedule_style_inherits_user_default() -> None:
    settings = _settings(default_schedule_style=ScheduleStyle.time_block)
    task = _task(schedule_style=None)
    assert effective_schedule_style(task, settings) == ScheduleStyle.time_block


def test_effective_schedule_style_uses_task_override() -> None:
    settings = _settings(default_schedule_style=ScheduleStyle.standalone)
    task = _task(schedule_style=ScheduleStyle.bundle)
    assert effective_schedule_style(task, settings) == ScheduleStyle.bundle


def test_workday_bounds_uses_settings_start() -> None:
    settings = _settings(
        workday_start_local=time(14, 30),
        workday_minutes=120,
    )
    tz = ZoneInfo("UTC")
    start, end = workday_bounds(date(2026, 8, 11), settings, tz)
    assert start == datetime(2026, 8, 11, 14, 30, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 11, 16, 30, tzinfo=timezone.utc)
