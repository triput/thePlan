"""Candidate task selection for Update Schedule."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Epic, Project, ScheduleStyle, ScheduledBlock, Task, UserSettings
from app.scheduler.style import effective_schedule_style


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
    """Incomplete tasks with remaining duration > 0; bundle/manual exclude auto-placement."""
    tasks = (
        db.query(Task)
        .filter(
            Task.owner_id == owner_id,
            Task.is_completed.is_(False),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.sort_order, Task.created_at)
        .all()
    )

    project_ids = {task.project_id for task in tasks if task.project_id}
    projects: dict[UUID, Project] = {}
    epics: dict[UUID, Epic] = {}
    if project_ids:
        for project in db.query(Project).filter(Project.id.in_(project_ids)).all():
            projects[project.id] = project
        epic_ids = {project.epic_id for project in projects.values() if project.epic_id}
        if epic_ids:
            for epic in db.query(Epic).filter(Epic.id.in_(epic_ids)).all():
                epics[epic.id] = epic

    candidates: list[TaskCandidate] = []
    for task in tasks:
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        if effective_schedule_style(task, project, epic, settings) in {
            ScheduleStyle.bundle,
            ScheduleStyle.manual,
        }:
            continue
        pinned_minutes = _pinned_minutes_for_task(db, task.id)
        remaining = task.estimated_duration_minutes - pinned_minutes
        if remaining > 0:
            candidates.append(TaskCandidate(task=task, remaining_minutes=remaining))
    return candidates
