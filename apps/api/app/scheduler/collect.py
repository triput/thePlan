"""Scheduling input collection for replan / preview (F3 shared pipeline)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import Epic, FocusWindow, Project, TaskDependency, UserSettings
from app.scheduler.busy_map import BusyInterval, build_busy_map
from app.scheduler.candidates import (
    ExcludedTask,
    TaskCandidate,
    load_candidates,
    load_excluded_tasks,
)
from app.scheduler.dependencies import order_candidates
from app.scheduler.horizon import compute_horizon
from app.scheduler.ups import score_tasks
from app.scheduler.windows import (
    effective_preferred_time_window_id,
    effective_preferred_time_window_source,
)


@dataclass
class SchedulingInputs:
    owner_id: UUID
    user_settings: UserSettings
    now_utc: datetime
    horizon_start: datetime
    horizon_end: datetime
    busy: list[BusyInterval]
    candidates: list[TaskCandidate]
    excluded_tasks: list[ExcludedTask]
    dependencies: list[TaskDependency]
    projects: dict[UUID, Project]
    epics: dict[UUID, Epic]
    ups_scores: dict[UUID, float]
    ordered_candidates: list[TaskCandidate]
    dependency_stats: dict[str, Any]
    effective_window_by_task: dict[UUID, UUID | None]
    effective_window_source_by_task: dict[UUID, str | None]
    preferred_windows: dict[UUID, FocusWindow]
    daily_cap: int | None
    # Captured at collect time so apply/persist does not re-read live inputs.
    input_snapshots: dict[UUID, dict[str, Any]] = field(default_factory=dict)


def _load_user_settings(db: Session, owner_id: UUID) -> UserSettings:
    settings = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == owner_id)
        .one_or_none()
    )
    if settings is None:
        raise RuntimeError(f"User settings missing for owner {owner_id}")
    return settings


def collect_inputs(
    db: Session,
    owner_id: UUID,
    now_utc: datetime,
) -> SchedulingInputs:
    """Read scheduling inputs; does not mutate blocks or task status."""
    user_settings = _load_user_settings(db, owner_id)
    horizon_start, horizon_end = compute_horizon(user_settings, now_utc)
    busy = build_busy_map(db, owner_id, horizon_start, horizon_end)

    candidates = load_candidates(db, owner_id, user_settings)
    candidate_ids = {item.task.id for item in candidates}
    excluded_tasks = load_excluded_tasks(db, owner_id, user_settings, candidate_ids)

    dependencies = (
        db.query(TaskDependency)
        .filter(TaskDependency.owner_id == owner_id)
        .all()
    )

    tasks = [item.task for item in candidates]
    remaining_by_task = {item.task.id: item.remaining_minutes for item in candidates}

    snapshot_tasks = tasks + [item.task for item in excluded_tasks]
    project_ids = {task.project_id for task in snapshot_tasks if task.project_id}
    projects: dict[UUID, Project] = {}
    epics: dict[UUID, Epic] = {}
    if project_ids:
        for project in db.query(Project).filter(Project.id.in_(project_ids)).all():
            projects[project.id] = project
        epic_ids = {project.epic_id for project in projects.values() if project.epic_id}
        if epic_ids:
            for epic in db.query(Epic).filter(Epic.id.in_(epic_ids)).all():
                epics[epic.id] = epic

    ups_scores = score_tasks(
        tasks,
        settings=user_settings,
        remaining_by_task=remaining_by_task,
        dependencies=dependencies,
        projects=projects,
        epics=epics,
        now_utc=now_utc,
    )

    ordered_candidates, dependency_stats = order_candidates(
        candidates, dependencies, ups_scores
    )

    effective_window_by_task: dict[UUID, UUID | None] = {}
    effective_window_source_by_task: dict[UUID, str | None] = {}
    for item in ordered_candidates:
        task = item.task
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        effective_window_by_task[task.id] = effective_preferred_time_window_id(
            task, project, epic
        )
        effective_window_source_by_task[task.id] = effective_preferred_time_window_source(
            task, project, epic
        )

    for item in excluded_tasks:
        task = item.task
        if task.id in effective_window_by_task:
            continue
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        effective_window_by_task[task.id] = effective_preferred_time_window_id(
            task, project, epic
        )
        effective_window_source_by_task[task.id] = effective_preferred_time_window_source(
            task, project, epic
        )

    preferred_ids = {wid for wid in effective_window_by_task.values() if wid}
    preferred_windows: dict[UUID, FocusWindow] = {}
    if preferred_ids:
        for window in (
            db.query(FocusWindow)
            .options(joinedload(FocusWindow.bands))
            .filter(FocusWindow.id.in_(preferred_ids))
            .all()
        ):
            preferred_windows[window.id] = window

    daily_cap = user_settings.max_auto_schedule_minutes_per_project_per_day

    # Build fingerprints from the same dependency list calculation will use —
    # do not re-query via live_snapshots_by_task (race with intervening commits).
    from app.scheduler.outcomes import snapshots_from_collected

    input_snapshots = snapshots_from_collected(
        user_settings=user_settings,
        tasks=snapshot_tasks,
        projects=projects,
        epics=epics,
        dependencies=dependencies,
        preferred_windows=preferred_windows,
        effective_window_by_task=effective_window_by_task,
    )

    return SchedulingInputs(
        owner_id=owner_id,
        user_settings=user_settings,
        now_utc=now_utc,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        busy=busy,
        candidates=candidates,
        excluded_tasks=excluded_tasks,
        dependencies=dependencies,
        projects=projects,
        epics=epics,
        ups_scores=ups_scores,
        ordered_candidates=ordered_candidates,
        dependency_stats=dependency_stats,
        effective_window_by_task=effective_window_by_task,
        effective_window_source_by_task=effective_window_source_by_task,
        preferred_windows=preferred_windows,
        daily_cap=daily_cap,
        input_snapshots=input_snapshots,
    )
