"""Update Schedule orchestrator."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Epic,
    FocusWindow,
    Project,
    ScheduleRun,
    ScheduledBlock,
    Task,
    TaskDependency,
    UserSettings,
)
from app.models.enums import ScheduleStatus, TaskPriority
from app.scheduler.busy_map import build_busy_map
from app.scheduler.candidates import TaskCandidate, load_candidates, pinned_minutes_for_task
from app.scheduler.dependencies import order_candidates
from app.scheduler.horizon import compute_horizon, wipe_unpinned_blocks_in_horizon
from app.scheduler.placement import ProjectDailyUsage, place_one_block
from app.scheduler.ups import score_tasks
from app.scheduler.windows import effective_preferred_time_window_id
from app.services import google_calendar, microsoft_calendar

logger = logging.getLogger(__name__)

PRIORITY_ORDER = [
    TaskPriority.p1,
    TaskPriority.p2,
    TaskPriority.p3,
    TaskPriority.p4,
]

_PRIORITY_RANK = {priority: index for index, priority in enumerate(PRIORITY_ORDER)}


def _blockers_by_dependent(
    dependencies: list[TaskDependency],
    candidate_ids: set[UUID],
) -> dict[UUID, list[UUID]]:
    """Map each candidate to its blockers, including non-candidate prerequisites.

    Fully pinned (or otherwise non-candidate) blockers must stay on the edge so
    placement can enforce prerequisite finish times via ``not_before``.
    """
    blockers: dict[UUID, list[UUID]] = {task_id: [] for task_id in candidate_ids}
    for dep in dependencies:
        blocker = dep.blocking_task_id
        dependent = dep.dependent_task_id
        if dependent not in candidate_ids:
            continue
        blockers[dependent].append(blocker)
    return blockers


def _remaining_including_external_blockers(
    db: Session,
    owner_id: UUID,
    remaining_by_task: dict[UUID, int],
    blockers_by_dependent: dict[UUID, list[UUID]],
) -> dict[UUID, int]:
    """Fill remaining minutes for blockers excluded from auto-placement candidates."""
    merged = dict(remaining_by_task)
    missing = {
        blocker_id
        for deps in blockers_by_dependent.values()
        for blocker_id in deps
        if blocker_id not in merged
    }
    if not missing:
        return merged
    tasks = (
        db.query(Task)
        .filter(Task.owner_id == owner_id, Task.id.in_(missing))
        .all()
    )
    for task in tasks:
        if task.is_completed or task.deleted_at is not None:
            merged[task.id] = 0
            continue
        pinned = pinned_minutes_for_task(db, task.id)
        merged[task.id] = max(0, task.estimated_duration_minutes - pinned)
    for blocker_id in missing:
        merged.setdefault(blocker_id, 0)
    return merged


def _dependencies_ready(
    task_id: UUID,
    remaining_by_task: dict[UUID, int],
    blockers_by_dependent: dict[UUID, list[UUID]],
) -> bool:
    for blocker_id in blockers_by_dependent.get(task_id, []):
        if remaining_by_task.get(blocker_id, 0) > 0:
            return False
    return True


def _prerequisite_not_before(
    task_id: UUID,
    blockers_by_dependent: dict[UUID, list[UUID]],
    latest_block_end_by_task: dict[UUID, datetime],
    horizon_start: datetime,
) -> datetime:
    not_before = horizon_start
    for blocker_id in blockers_by_dependent.get(task_id, []):
        blocker_end = latest_block_end_by_task.get(blocker_id)
        if blocker_end is not None and blocker_end > not_before:
            not_before = blocker_end
    return not_before


def _placement_pass_order(
    candidates: list[TaskCandidate],
    ordered: list[TaskCandidate],
    ups_scores: dict[UUID, float],
) -> list[TaskCandidate]:
    """Priority and UPS among tasks ready this sweep; topo index breaks ties (deps win)."""
    topo_index = {item.task.id: index for index, item in enumerate(ordered)}
    return sorted(
        candidates,
        key=lambda item: (
            _PRIORITY_RANK.get(item.task.priority, len(PRIORITY_ORDER)),
            -ups_scores.get(item.task.id, 0.0),
            topo_index.get(item.task.id, len(ordered)),
        ),
    )


def _seed_prerequisite_block_ends(
    db: Session,
    owner_id: UUID,
    candidate_ids: set[UUID],
    horizon_start: datetime,
    horizon_end: datetime,
) -> dict[UUID, datetime]:
    """Latest pinned (or other pre-existing) block end per task in the replan horizon."""
    latest: dict[UUID, datetime] = {}
    if not candidate_ids:
        return latest
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.task_id.in_(candidate_ids),
            ScheduledBlock.start_time < horizon_end,
            ScheduledBlock.end_time > horizon_start,
        )
        .all()
    )
    for block in blocks:
        if block.task_id is None:
            continue
        prev = latest.get(block.task_id)
        if prev is None or block.end_time > prev:
            latest[block.task_id] = block.end_time
    return latest


def _push_mirrored_block(db: Session, settings, block: ScheduledBlock) -> None:
    google_calendar.push_scheduled_block(db, settings, block)
    microsoft_calendar.push_scheduled_block(db, settings, block)


def _load_user_settings(db: Session, owner_id: UUID) -> UserSettings:
    settings = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == owner_id)
        .one_or_none()
    )
    if settings is None:
        raise RuntimeError(f"User settings missing for owner {owner_id}")
    return settings


def run_replan(run_id: UUID, db: Session | None = None) -> None:
    """Execute a schedule run in its own DB session (or reuse provided session)."""
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    stats: dict[str, Any] = {}
    try:
        run = db.get(ScheduleRun, run_id)
        if run is None:
            logger.error("Schedule run %s not found", run_id)
            return
        if run.status != "running":
            logger.warning("Schedule run %s is not running (status=%s)", run_id, run.status)
            return

        owner_id = run.owner_id
        user_settings = _load_user_settings(db, owner_id)
        now_utc = datetime.now(timezone.utc)

        horizon_start, horizon_end = compute_horizon(user_settings, now_utc)
        stats["horizon_start"] = horizon_start.isoformat()
        stats["horizon_end"] = horizon_end.isoformat()

        wiped = wipe_unpinned_blocks_in_horizon(db, owner_id, horizon_start, horizon_end)
        stats["wiped_unpinned_blocks"] = wiped

        busy = build_busy_map(db, owner_id, horizon_start, horizon_end)

        candidates = load_candidates(db, owner_id, user_settings)
        stats["candidate_count"] = len(candidates)

        dependencies = (
            db.query(TaskDependency)
            .filter(TaskDependency.owner_id == owner_id)
            .all()
        )

        tasks = [item.task for item in candidates]
        remaining_by_task = {item.task.id: item.remaining_minutes for item in candidates}

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

        ups_scores = score_tasks(
            tasks,
            settings=user_settings,
            remaining_by_task=remaining_by_task,
            dependencies=dependencies,
            projects=projects,
            epics=epics,
            now_utc=now_utc,
        )

        ordered, dep_stats = order_candidates(candidates, dependencies, ups_scores)
        stats.update(dep_stats)

        effective_by_task: dict[UUID, UUID | None] = {}
        for item in ordered:
            task = item.task
            project = projects.get(task.project_id) if task.project_id else None
            epic = epics.get(project.epic_id) if project and project.epic_id else None
            effective_by_task[task.id] = effective_preferred_time_window_id(
                task, project, epic
            )

        preferred_ids = {wid for wid in effective_by_task.values() if wid}
        preferred_windows: dict[UUID, FocusWindow] = {}
        if preferred_ids:
            for window in (
                db.query(FocusWindow)
                .options(joinedload(FocusWindow.bands))
                .filter(FocusWindow.id.in_(preferred_ids))
                .all()
            ):
                preferred_windows[window.id] = window

        tasks_scheduled = 0
        blocks_created = 0
        overbooked_count = 0
        app_settings = get_settings()

        project_daily_usage: ProjectDailyUsage = {}
        daily_cap = user_settings.max_auto_schedule_minutes_per_project_per_day
        minutes_by_project: dict[str, int] = {}
        task_had_blocks: dict[UUID, bool] = {}

        candidate_ids = {item.task.id for item in candidates}
        blockers_by_dependent = _blockers_by_dependent(dependencies, candidate_ids)
        # One remaining map for placement + readiness: seed non-candidate
        # (e.g. fully pinned) blockers, then mutate as blocks are placed so
        # dependents unlock in later sweeps.
        remaining_by_task = _remaining_including_external_blockers(
            db,
            owner_id,
            remaining_by_task,
            blockers_by_dependent,
        )
        prereq_seed_ids = candidate_ids | {
            blocker_id
            for deps in blockers_by_dependent.values()
            for blocker_id in deps
        }
        latest_block_end_by_task = _seed_prerequisite_block_ends(
            db,
            owner_id,
            prereq_seed_ids,
            horizon_start,
            horizon_end,
        )

        placed_in_sweep = True
        while placed_in_sweep:
            placed_in_sweep = False
            ready = [
                candidate
                for candidate in ordered
                if remaining_by_task.get(candidate.task.id, 0) > 0
                and _dependencies_ready(
                    candidate.task.id,
                    remaining_by_task,
                    blockers_by_dependent,
                )
            ]
            if not ready:
                break
            for candidate in _placement_pass_order(ready, ordered, ups_scores):
                task_id = candidate.task.id
                remaining = remaining_by_task.get(task_id, 0)
                if remaining <= 0:
                    continue
                if not _dependencies_ready(
                    task_id, remaining_by_task, blockers_by_dependent
                ):
                    continue
                prereq_not_before = _prerequisite_not_before(
                    task_id,
                    blockers_by_dependent,
                    latest_block_end_by_task,
                    horizon_start,
                )
                result, busy = place_one_block(
                    db,
                    task=candidate.task,
                    owner_id=owner_id,
                    settings=user_settings,
                    remaining_minutes=remaining,
                    busy=busy,
                    horizon_start=horizon_start,
                    horizon_end=horizon_end,
                    preferred_windows=preferred_windows,
                    now_utc=now_utc,
                    preferred_window_id=effective_by_task[task_id],
                    project_daily_usage=project_daily_usage,
                    daily_cap=daily_cap,
                    prerequisite_not_before=prereq_not_before,
                )
                remaining_by_task[task_id] = result.remaining_minutes
                if result.blocks_created <= 0:
                    continue
                placed_in_sweep = True
                task_had_blocks[task_id] = True
                blocks_created += result.blocks_created
                if result.last_block_end is not None:
                    prev_end = latest_block_end_by_task.get(task_id)
                    if prev_end is None or result.last_block_end > prev_end:
                        latest_block_end_by_task[task_id] = result.last_block_end
                minutes_placed = remaining - result.remaining_minutes
                project_key = (
                    str(candidate.task.project_id)
                    if candidate.task.project_id
                    else "inbox"
                )
                minutes_by_project[project_key] = (
                    minutes_by_project.get(project_key, 0) + minutes_placed
                )

        for candidate in ordered:
            task_id = candidate.task.id
            task = candidate.task
            remaining = remaining_by_task.get(task_id, 0)
            if remaining <= 0 and task_had_blocks.get(task_id):
                task.status = ScheduleStatus.scheduled
            elif remaining > 0:
                task.status = ScheduleStatus.overbooked
                overbooked_count += 1

        tasks_scheduled = len(task_had_blocks)
        if minutes_by_project:
            stats["minutes_by_project"] = minutes_by_project

        db.flush()

        new_blocks = (
            db.query(ScheduledBlock)
            .filter(
                ScheduledBlock.owner_id == owner_id,
                ScheduledBlock.is_pinned.is_(False),
                ScheduledBlock.start_time >= horizon_start,
                ScheduledBlock.start_time < horizon_end,
            )
            .all()
        )
        for block in new_blocks:
            try:
                _push_mirrored_block(db, app_settings, block)
            except Exception:
                logger.exception("Failed to mirror block %s to calendar", block.id)

        run.tasks_scheduled = tasks_scheduled
        run.blocks_created = blocks_created
        run.overbooked_count = overbooked_count
        run.stats_json = stats
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        logger.exception("Schedule run %s failed", run_id)
        db.rollback()
        run = db.get(ScheduleRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            run.stats_json = stats or None
            db.commit()
    finally:
        if owns_session:
            db.close()
