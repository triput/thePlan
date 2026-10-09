"""Live schedule-style resolution for candidate filtering. ADR-006 / DEF-014.

Scheduler layer — task override, then project, then epic, else user default.
"""

from __future__ import annotations

from app.models import Epic, Project, ScheduleStyle, Task, UserSettings


def effective_schedule_style(
    task: Task,
    project: Project | None,
    epic: Epic | None,
    settings: UserSettings,
) -> ScheduleStyle:
    """Task override when set; else project; else epic; else user default."""
    if task.schedule_style is not None:
        return task.schedule_style
    if project is not None and project.schedule_style is not None:
        return project.schedule_style
    if epic is not None and epic.schedule_style is not None:
        return epic.schedule_style
    return settings.default_schedule_style


def effective_schedule_style_source(
    task: Task,
    project: Project | None,
    epic: Epic | None,
) -> str:
    """Which layer supplied the effective schedule style (for reason facts)."""
    if task.schedule_style is not None:
        return "task"
    if project is not None and project.schedule_style is not None:
        return "project"
    if epic is not None and epic.schedule_style is not None:
        return "epic"
    return "user_default"
