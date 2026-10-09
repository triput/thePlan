"""Live Time Map resolution at schedule time. ADR-006 / DEF-018.

Scheduler layer — task override, then project, then epic, else unbound.
"""

from __future__ import annotations

from uuid import UUID

from app.models import Epic, Project, Task


def effective_preferred_time_window_id(
    task: Task,
    project: Project | None,
    epic: Epic | None,
) -> UUID | None:
    """Task override when set; else project; else epic; else unbound."""
    if task.preferred_time_window_id is not None:
        return task.preferred_time_window_id
    if project is not None and project.preferred_time_window_id is not None:
        return project.preferred_time_window_id
    if epic is not None and epic.preferred_time_window_id is not None:
        return epic.preferred_time_window_id
    return None


def effective_preferred_time_window_source(
    task: Task,
    project: Project | None,
    epic: Epic | None,
) -> str | None:
    """Which layer bound the time map, if any."""
    if task.preferred_time_window_id is not None:
        return "task"
    if project is not None and project.preferred_time_window_id is not None:
        return "project"
    if epic is not None and epic.preferred_time_window_id is not None:
        return "epic"
    return None
