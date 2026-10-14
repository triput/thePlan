"""Scheduling input collection for replan / preview (F3 shared pipeline)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Epic,
    FocusWindow,
    Project,
    ScheduledBlock,
    TaskDependency,
    TimeMapOverride,
    UserSettings,
)
from app.scheduler.busy_map import (
    BusyInterval,
    busy_from_sources,
    load_immovable_busy_sources,
)
from app.scheduler.candidates import (
    ExcludedTask,
    LifecycleExcludedTask,
    TaskCandidate,
    load_candidates,
    load_excluded_tasks,
    load_lifecycle_excluded_tasks,
)
from app.scheduler.dependencies import order_candidates
from app.scheduler.horizon import compute_horizon
from app.scheduler.ups import score_tasks
from app.scheduler.time_map_overrides import (
    load_time_map_overrides_for_maps,
    overrides_intersecting_horizon,
)
from app.scheduler.availability_materializer import (
    PolicyWindow,
    load_owner_policy_windows,
)
from app.scheduler.windows import (
    effective_preferred_time_window_id,
    effective_preferred_time_window_source,
)
from app.scheduler.composition import EffectiveComposition
from app.scheduler.composition_resolver import load_effective_compositions


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
    lifecycle_excluded_tasks: list[LifecycleExcludedTask]
    dependencies: list[TaskDependency]
    projects: dict[UUID, Project]
    epics: dict[UUID, Epic]
    ups_scores: dict[UUID, float]
    ordered_candidates: list[TaskCandidate]
    dependency_stats: dict[str, Any]
    effective_window_by_task: dict[UUID, UUID | None]
    effective_window_source_by_task: dict[UUID, str | None]
    preferred_windows: dict[UUID, FocusWindow]
    time_map_overrides_by_map: dict[UUID, list[TimeMapOverride]]
    daily_cap: int | None
    # Captured at collect time so apply/persist does not re-read live inputs.
    input_snapshots: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    # Same pin/busy capture used for candidates, prereq seed, and fingerprints.
    pinned_blocks_by_task: dict[UUID, list[ScheduledBlock]] = field(default_factory=dict)
    immovable_busy: list[BusyInterval] = field(default_factory=list)
    # Same Working/General copy placement and the stored fingerprint use.
    working_windows: list[PolicyWindow] | None = None
    general_windows: list[PolicyWindow] | None = None
    # Resolved new-rule assignments. A missing task stays on the V3 path.
    # Fingerprints use ``composition_fingerprint`` on these same objects.
    composition_by_task: dict[UUID, EffectiveComposition] = field(default_factory=dict)


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
    working_windows, general_windows = load_owner_policy_windows(db, owner_id)
    horizon_start, horizon_end = compute_horizon(user_settings, now_utc)

    # One capture of immovable busy/pins for calculation + fingerprints.
    pinned_blocks, external_events = load_immovable_busy_sources(db, owner_id)
    immovable_busy = busy_from_sources(pinned_blocks, external_events)
    busy = busy_from_sources(
        pinned_blocks,
        external_events,
        range_start=horizon_start,
        range_end=horizon_end,
    )
    pinned_blocks_by_task: dict[UUID, list[ScheduledBlock]] = defaultdict(list)
    for block in pinned_blocks:
        if block.task_id is None:
            continue
        pinned_blocks_by_task[block.task_id].append(block)

    candidates = load_candidates(
        db,
        owner_id,
        user_settings,
        now_utc=now_utc,
        pinned_blocks_by_task=pinned_blocks_by_task,
        working_windows=working_windows,
    )
    candidate_ids = {item.task.id for item in candidates}
    excluded_tasks = load_excluded_tasks(
        db,
        owner_id,
        user_settings,
        candidate_ids,
        now_utc=now_utc,
        pinned_blocks_by_task=pinned_blocks_by_task,
        working_windows=working_windows,
    )
    already_evaluated = candidate_ids | {item.task.id for item in excluded_tasks}
    lifecycle_excluded_tasks = load_lifecycle_excluded_tasks(
        db,
        owner_id,
        user_settings,
        already_evaluated_ids=already_evaluated,
    )

    dependencies = (
        db.query(TaskDependency)
        .filter(TaskDependency.owner_id == owner_id)
        .all()
    )

    tasks = [item.task for item in candidates]
    remaining_by_task = {item.task.id: item.remaining_minutes for item in candidates}

    snapshot_tasks = tasks + [item.task for item in excluded_tasks]
    snapshot_tasks.extend(item.task for item in lifecycle_excluded_tasks)
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

    for item in (*excluded_tasks, *lifecycle_excluded_tasks):
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

    # Fingerprints keep every override on the effective map, including expired
    # rows. Placement uses the horizon overlap only, so a sliding ``now`` does
    # not by itself mark the explanation stale.
    overrides_for_fingerprint = load_time_map_overrides_for_maps(
        db,
        owner_id,
        preferred_ids,
    )
    time_map_overrides_by_map = overrides_intersecting_horizon(
        overrides_for_fingerprint,
        horizon_start,
        horizon_end,
    )

    daily_cap = user_settings.max_auto_schedule_minutes_per_project_per_day
    composition_by_task = load_effective_compositions(
        db,
        owner_id,
        snapshot_tasks,
        projects,
        epics,
    )

    # Fingerprints use the same deps + pins + immovable busy calculation saw.
    from app.scheduler.outcomes import load_blocker_tasks, snapshots_from_collected

    tasks_by_id = load_blocker_tasks(db, owner_id, snapshot_tasks, dependencies)
    input_snapshots = snapshots_from_collected(
        user_settings=user_settings,
        tasks=snapshot_tasks,
        projects=projects,
        epics=epics,
        dependencies=dependencies,
        preferred_windows=preferred_windows,
        effective_window_by_task=effective_window_by_task,
        tasks_by_id=tasks_by_id,
        pinned_blocks_by_task=dict(pinned_blocks_by_task),
        busy_intervals=immovable_busy,
        time_map_overrides_by_map=overrides_for_fingerprint,
        working_windows=working_windows,
        general_windows=general_windows,
        composition_by_task=composition_by_task,
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
        lifecycle_excluded_tasks=lifecycle_excluded_tasks,
        dependencies=dependencies,
        projects=projects,
        epics=epics,
        ups_scores=ups_scores,
        ordered_candidates=ordered_candidates,
        dependency_stats=dependency_stats,
        effective_window_by_task=effective_window_by_task,
        effective_window_source_by_task=effective_window_source_by_task,
        preferred_windows=preferred_windows,
        time_map_overrides_by_map=time_map_overrides_by_map,
        daily_cap=daily_cap,
        input_snapshots=input_snapshots,
        pinned_blocks_by_task=dict(pinned_blocks_by_task),
        immovable_busy=immovable_busy,
        working_windows=working_windows,
        general_windows=general_windows,
        composition_by_task=composition_by_task,
    )
