"""Candidate task selection for Update Schedule."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ScheduleStyle, ScheduledBlock, Task, UserSettings


@dataclass(frozen=True)
class TaskCandidate:
    task: Task
    remaining_minutes: int


def _pinned_minutes_for_task(db: Session, task_id: UUID) -> int:
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.task_id == task_id,
            ScheduledBlock.is_pinned.is_(True),
        )
        .all()
    )
    total = 0
    for block in blocks:
        delta = block.end_time - block.start_time
        total += int(delta.total_seconds() // 60)
    return total


def load_candidates(
    db: Session,
    owner_id: UUID,
    settings: UserSettings,
) -> list[TaskCandidate]:
    """Incomplete tasks with remaining duration > 0; bundle default excludes all."""
    if settings.default_schedule_style == ScheduleStyle.bundle:
        return []

    tasks = (
        db.query(Task)
        .filter(
            Task.owner_id == owner_id,
            Task.is_completed.is_(False),
        )
        .order_by(Task.sort_order, Task.created_at)
        .all()
    )

    candidates: list[TaskCandidate] = []
    for task in tasks:
        pinned_minutes = _pinned_minutes_for_task(db, task.id)
        remaining = task.estimated_duration_minutes - pinned_minutes
        if remaining > 0:
            candidates.append(TaskCandidate(task=task, remaining_minutes=remaining))
    return candidates
