"""Progress column init on new tasks (§1 migration contract)."""

from __future__ import annotations

from app.models import Task


def initialize_task_effort_on_create(task: Task, estimate_minutes: int) -> None:
    task.estimated_duration_minutes = estimate_minutes
    task.worked_minutes = 0
    task.remaining_minutes = estimate_minutes
