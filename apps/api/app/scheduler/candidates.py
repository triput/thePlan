"""Candidate task selection for Update Schedule."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Epic, Project, ScheduleStyle, ScheduledBlock, Task, UserSettings
from app.scheduler.style import effective_schedule_style, effective_schedule_style_source


@dataclass(frozen=True)
class TaskCandidate:
    task: Task
    remaining_minutes: int


@dataclass(frozen=True)
class ExcludedTask:
    """Open task evaluated but not auto-placed (manual/bundle or fully pinned)."""

    task: Task
    requested_minutes: int
    pinned_minutes: int
    remaining_minutes: int
    schedule_style: ScheduleStyle
    style_source: str


def pinned_minutes_for_task(db: Session, task_id: UUID) -> int:
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
        pinned_minutes = pinned_minutes_for_task(db, task.id)
        remaining = task.estimated_duration_minutes - pinned_minutes
        if remaining > 0:
            candidates.append(TaskCandidate(task=task, remaining_minutes=remaining))
    return candidates


def load_excluded_tasks(
    db: Session,
    owner_id: UUID,
    settings: UserSettings,
    candidate_ids: set[UUID],
) -> list[ExcludedTask]:
    """Classify open tasks skipped by ``load_candidates`` (not already candidates)."""
    if not candidate_ids:
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
    else:
        tasks = (
            db.query(Task)
            .filter(
                Task.owner_id == owner_id,
                Task.is_completed.is_(False),
                Task.deleted_at.is_(None),
                Task.id.notin_(candidate_ids),
            )
            .order_by(Task.sort_order, Task.created_at)
            .all()
        )
    if not tasks:
        return []

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

    excluded: list[ExcludedTask] = []
    for task in tasks:
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        style = effective_schedule_style(task, project, epic, settings)
        style_source = effective_schedule_style_source(task, project, epic)
        pinned_minutes = pinned_minutes_for_task(db, task.id)
        requested = task.estimated_duration_minutes
        remaining = requested - pinned_minutes
        if style in {ScheduleStyle.bundle, ScheduleStyle.manual}:
            excluded.append(
                ExcludedTask(
                    task=task,
                    requested_minutes=requested,
                    pinned_minutes=pinned_minutes,
                    remaining_minutes=max(0, remaining),
                    schedule_style=style,
                    style_source=style_source,
                )
            )
        elif remaining <= 0:
            excluded.append(
                ExcludedTask(
                    task=task,
                    requested_minutes=requested,
                    pinned_minutes=pinned_minutes,
                    remaining_minutes=0,
                    schedule_style=style,
                    style_source=style_source,
                )
            )
    return excluded
