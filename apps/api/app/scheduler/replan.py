"""Update Schedule orchestrator."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import SessionLocal
from app.models import Epic, FocusWindow, Project, ScheduleRun, ScheduledBlock, TaskDependency, UserSettings
from app.scheduler.busy_map import build_busy_map
from app.scheduler.candidates import load_candidates
from app.scheduler.dependencies import order_candidates
from app.scheduler.horizon import compute_horizon, wipe_unpinned_blocks_in_horizon
from app.scheduler.placement import place_task
from app.scheduler.ups import score_tasks
from app.services import google_calendar, microsoft_calendar

logger = logging.getLogger(__name__)


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

        preferred_ids = {
            item.task.preferred_time_window_id
            for item in ordered
            if item.task.preferred_time_window_id
        }
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

        for candidate in ordered:
            result, busy = place_task(
                db,
                task=candidate.task,
                owner_id=owner_id,
                settings=user_settings,
                remaining_minutes=candidate.remaining_minutes,
                busy=busy,
                horizon_start=horizon_start,
                horizon_end=horizon_end,
                preferred_windows=preferred_windows,
                now_utc=now_utc,
            )
            if result.blocks_created > 0:
                tasks_scheduled += 1
            blocks_created += result.blocks_created
            if result.overbooked:
                overbooked_count += 1

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
