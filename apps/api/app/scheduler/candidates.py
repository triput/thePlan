"""Candidate task selection for Update Schedule."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Epic, Project, ScheduleStyle, ScheduledBlock, Task, UserSettings
from app.scheduler.reasons import (
    REASON_EXCLUDED_LIFECYCLE_ARCHIVED,
    REASON_EXCLUDED_LIFECYCLE_COMPLETED,
    REASON_EXCLUDED_LIFECYCLE_TRASHED,
)
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


@dataclass(frozen=True)
class LifecycleExcludedTask:
    """Task in evaluation scope but excluded by lifecycle (completed/trash/archive)."""

    task: Task
    requested_minutes: int
    reason_code: str
    archived_scope: str | None = None


def pinned_minutes_for_task(db: Session, task_id: UUID) -> int:
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.task_id == task_id,
            ScheduledBlock.is_pinned.is_(True),
        )
        .all()
    )
    return pinned_minutes_from_blocks(blocks)


def pinned_minutes_from_blocks(blocks: list[ScheduledBlock]) -> int:
    total = 0
    for block in blocks:
        delta = block.end_time - block.start_time
        total += int(delta.total_seconds() // 60)
    return total


def load_candidates(
    db: Session,
    owner_id: UUID,
    settings: UserSettings,
    *,
    pinned_minutes_by_task: dict[UUID, int] | None = None,
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
        if _task_archived_scope(task, projects, epics) is not None:
            continue
        if pinned_minutes_by_task is not None:
            pinned_minutes = pinned_minutes_by_task.get(task.id, 0)
        else:
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
    *,
    pinned_minutes_by_task: dict[UUID, int] | None = None,
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
        if pinned_minutes_by_task is not None:
            pinned_minutes = pinned_minutes_by_task.get(task.id, 0)
        else:
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


def _task_archived_scope(
    task: Task,
    projects: dict[UUID, Project],
    epics: dict[UUID, Epic],
) -> str | None:
    if not task.project_id:
        return None
    project = projects.get(task.project_id)
    if project is None:
        return None
    if project.is_archived:
        return "project"
    if project.epic_id:
        epic = epics.get(project.epic_id)
        if epic is not None and epic.is_archived:
            return "epic"
    return None


def load_lifecycle_excluded_tasks(
    db: Session,
    owner_id: UUID,
    _settings: UserSettings,
    *,
    already_evaluated_ids: set[UUID],
) -> list[LifecycleExcludedTask]:
    """Tasks with scheduling relevance but lifecycle exclusion (not auto-placed)."""
    tasks = (
        db.query(Task)
        .filter(Task.owner_id == owner_id)
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

    excluded: list[LifecycleExcludedTask] = []
    for task in tasks:
        if task.id in already_evaluated_ids:
            continue
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        if task.estimated_duration_minutes <= 0:
            continue

        archived_scope = _task_archived_scope(task, projects, epics)
        if task.is_completed:
            code = REASON_EXCLUDED_LIFECYCLE_COMPLETED
        elif task.deleted_at is not None:
            code = REASON_EXCLUDED_LIFECYCLE_TRASHED
        elif archived_scope is not None:
            code = REASON_EXCLUDED_LIFECYCLE_ARCHIVED
        else:
            continue

        excluded.append(
            LifecycleExcludedTask(
                task=task,
                requested_minutes=task.estimated_duration_minutes,
                reason_code=code,
                archived_scope=archived_scope,
            )
        )
    return excluded
