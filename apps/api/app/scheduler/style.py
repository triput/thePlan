"""Effective schedule style resolution for candidate filtering."""

from __future__ import annotations

from app.models import ScheduleStyle, Task, UserSettings


def effective_schedule_style(task: Task, settings: UserSettings) -> ScheduleStyle:
    """Task override when set; otherwise user default."""
    if task.schedule_style is not None:
        return task.schedule_style
    return settings.default_schedule_style
