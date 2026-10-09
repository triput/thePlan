"""Persist per-task schedule outcomes for F3 reads.

Jules' apply path should call ``persist_calculation_outcomes`` so each row
gets an input snapshot and fingerprint. Direct ``ScheduleTaskOutcome`` inserts
still satisfy the table; a missing snapshot is ``provenance`` stale on read.

This module only writes rows. It does not commit and it does not replan.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Epic,
    FocusWindow,
    Project,
    ScheduleTaskOutcome,
    ScheduledBlock,
    Task,
    TaskDependency,
    UserSettings,
)
from app.scheduler.busy_map import BusyInterval, load_immovable_busy
from app.scheduler.input_fingerprint import (
    ALGORITHM_VERSION,
    assemble_snapshot,
    fingerprint_snapshot,
    normalize_busy_intervals,
    normalize_pin_intervals,
    normalize_prerequisite_states,
    outcome_family,
)
from app.scheduler.reasons import ReasonFact, TaskSchedulingOutcome, format_summary_text
from app.scheduler.style import effective_schedule_style
from app.scheduler.time_map_overrides import load_time_map_overrides_for_maps
from app.scheduler.windows import effective_preferred_time_window_id


def _bands_payload(window: FocusWindow | None) -> list[dict[str, Any]]:
    if window is None:
        return []
    payload: list[dict[str, Any]] = []
    for band in window.bands:
        tier = band.tier.value if hasattr(band.tier, "value") else str(band.tier)
        payload.append(
            {
                "tier": tier,
                "start": band.start_time,
                "end": band.end_time,
                "days_of_week": band.days_of_week,
                "sort_order": band.sort_order,
            }
        )
    return payload


def load_blocker_tasks(
    db: Session,
    owner_id: UUID,
    tasks: list[Task],
    dependencies: list[TaskDependency],
) -> dict[UUID, Task]:
    """Resolve blocker task rows for prerequisite_state fingerprints.

    Does not query pins or external busy — collect already captured those.
    """
    known: dict[UUID, Task] = {task.id: task for task in tasks}
    missing = {dep.blocking_task_id for dep in dependencies} - set(known)
    if missing:
        rows = (
            db.query(Task)
            .filter(Task.owner_id == owner_id, Task.id.in_(missing))
            .all()
        )
        for row in rows:
            known[row.id] = row
    return known


def load_snapshot_extras(
    db: Session,
    owner_id: UUID,
    tasks: list[Task],
    dependencies: list[TaskDependency],
) -> tuple[dict[UUID, Task], dict[UUID, list[ScheduledBlock]], list[BusyInterval]]:
    """Blocker rows, pins, and immovable busy for live explanation *reads*.

    Collect must not use this for persist fingerprints — it reloads busy/pins
    and can race calculation's capture. Prefer ``load_blocker_tasks`` plus the
    already-collected pin/busy maps.
    """
    known = load_blocker_tasks(db, owner_id, tasks, dependencies)
    pins: dict[UUID, list[ScheduledBlock]] = defaultdict(list)
    task_ids = list(known)
    if task_ids:
        pinned_rows = (
            db.query(ScheduledBlock)
            .filter(
                ScheduledBlock.owner_id == owner_id,
                ScheduledBlock.is_pinned.is_(True),
                ScheduledBlock.task_id.in_(task_ids),
            )
            .all()
        )
        for block in pinned_rows:
            pins[block.task_id].append(block)
    return known, pins, load_immovable_busy(db, owner_id)


def snapshots_from_collected(
    *,
    user_settings: UserSettings,
    tasks: list[Task],
    projects: dict[UUID, Project],
    epics: dict[UUID, Epic],
    dependencies: list[TaskDependency],
    preferred_windows: dict[UUID, FocusWindow],
    effective_window_by_task: dict[UUID, UUID | None] | None = None,
    tasks_by_id: dict[UUID, Task] | None = None,
    pinned_blocks_by_task: dict[UUID, list[ScheduledBlock]] | None = None,
    busy_intervals: list[BusyInterval] | None = None,
    time_map_overrides_by_map: dict[UUID, list[Any]] | None = None,
) -> dict[UUID, dict[str, Any]]:
    """Build v3 snapshots from values already collected for calculation.

    Uses the exact ``dependencies`` list the calculator saw — no second
    dependency read. Pins, blocker rows, and immovable busy are passed in
    from ``load_snapshot_extras`` (or omitted, which fingerprints as empty).
    ``time_map_overrides_by_map`` is every override on the effective maps,
    not the horizon-filtered placement subset.
    """
    if not tasks:
        return {}
    window_by_task = effective_window_by_task or {}
    blockers_by_task: dict[UUID, list[UUID]] = defaultdict(list)
    for dep in dependencies:
        blockers_by_task[dep.dependent_task_id].append(dep.blocking_task_id)
    known_tasks = tasks_by_id or {task.id: task for task in tasks}
    pins_by_task = pinned_blocks_by_task or {}
    overrides_by_map = time_map_overrides_by_map or {}
    busy_payload = normalize_busy_intervals(busy_intervals or [])
    workday_start = user_settings.workday_start_local

    snapshots: dict[UUID, dict[str, Any]] = {}
    for task in tasks:
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        style = effective_schedule_style(task, project, epic, user_settings)
        if task.id in window_by_task:
            window_id = window_by_task[task.id]
        else:
            window_id = effective_preferred_time_window_id(task, project, epic)
        window = preferred_windows.get(window_id) if window_id is not None else None
        blocking_ids = blockers_by_task.get(task.id, [])
        pinned_minutes, pin_intervals = normalize_pin_intervals(pins_by_task.get(task.id, []))
        snapshots[task.id] = assemble_snapshot(
            estimated_duration_minutes=task.estimated_duration_minutes,
            min_block_duration_minutes=task.min_block_duration_minutes,
            max_block_duration_minutes=task.max_block_duration_minutes,
            deadline_at=task.deadline_at,
            schedule_style=style.value,
            time_window_id=window_id,
            strict_mode=window.strict_mode if window is not None else None,
            bands=_bands_payload(window),
            blocking_task_ids=blocking_ids,
            pinned_minutes=pinned_minutes,
            pin_intervals=pin_intervals,
            project_daily_cap_minutes=user_settings.max_auto_schedule_minutes_per_project_per_day,
            timezone_name=user_settings.timezone,
            upcoming_horizon_days=user_settings.upcoming_horizon_days,
            workday_start_local=workday_start,
            workday_minutes=user_settings.workday_minutes,
            workweek_days=user_settings.workweek_days,
            inter_block_buffer_minutes=user_settings.inter_block_buffer_minutes,
            is_completed=task.is_completed,
            deleted_at=task.deleted_at,
            project_archived=bool(project.is_archived) if project is not None else False,
            epic_archived=bool(epic.is_archived) if epic is not None else False,
            busy_intervals=busy_payload,
            prerequisite_states=normalize_prerequisite_states(blocking_ids, known_tasks),
            due_at=task.due_at,
            soft_target_at=task.soft_target_at,
            auto_defer_enabled=user_settings.auto_defer_enabled,
            time_map_overrides=overrides_by_map.get(window_id, []) if window_id else [],
        )
    return snapshots


def live_snapshots_by_task(db: Session, tasks: list[Task]) -> dict[UUID, dict[str, Any]]:
    """Effective v3 snapshots for explanation *reads*. Empty if settings are missing.

    Collect/persist must not use this — it re-queries dependencies and can diverge
    from the edges calculation already used. Reads may query deps, pins, and busy.
    """
    if not tasks:
        return {}
    owner_id = tasks[0].owner_id
    settings = (
        db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one_or_none()
    )
    if settings is None:
        return {}

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

    task_ids = [task.id for task in tasks]
    dependencies = (
        db.query(TaskDependency)
        .filter(
            TaskDependency.owner_id == owner_id,
            TaskDependency.dependent_task_id.in_(task_ids),
        )
        .all()
    )

    window_ids: set[UUID] = set()
    window_by_task: dict[UUID, UUID | None] = {}
    for task in tasks:
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        window_id = effective_preferred_time_window_id(task, project, epic)
        window_by_task[task.id] = window_id
        if window_id is not None:
            window_ids.add(window_id)

    windows: dict[UUID, FocusWindow] = {}
    if window_ids:
        for window in (
            db.query(FocusWindow)
            .options(joinedload(FocusWindow.bands))
            .filter(FocusWindow.id.in_(window_ids))
            .all()
        ):
            windows[window.id] = window

    tasks_by_id, pins_by_task, immovable_busy = load_snapshot_extras(
        db, owner_id, tasks, dependencies
    )
    overrides_by_map = load_time_map_overrides_for_maps(db, owner_id, window_ids)
    return snapshots_from_collected(
        user_settings=settings,
        tasks=tasks,
        projects=projects,
        epics=epics,
        dependencies=dependencies,
        preferred_windows=windows,
        effective_window_by_task=window_by_task,
        tasks_by_id=tasks_by_id,
        pinned_blocks_by_task=pins_by_task,
        busy_intervals=immovable_busy,
        time_map_overrides_by_map=overrides_by_map,
    )


def summary_text_for_facts(facts: list[ReasonFact] | list[dict[str, Any]]) -> str:
    """Jules' formatter when the reason objects are available; same text from stored JSON."""
    typed: list[ReasonFact] = []
    for fact in facts:
        if isinstance(fact, ReasonFact):
            typed.append(fact)
            continue
        if isinstance(fact, dict) and fact.get("code"):
            params = fact.get("params") or {}
            typed.append(ReasonFact(str(fact["code"]), dict(params)))
    return format_summary_text(typed)


def persist_calculation_outcomes(
    db: Session,
    *,
    run_id: UUID,
    owner_id: UUID,
    outcomes: list[TaskSchedulingOutcome],
    evaluated_at: datetime | None = None,
    placement_facts_by_task: dict[UUID, dict[str, Any] | None] | None = None,
    input_snapshots: dict[UUID, dict[str, Any]] | None = None,
) -> list[ScheduleTaskOutcome]:
    """Insert one outcome row per task. Caller owns the transaction.

    Upserts on ``(schedule_run_id, task_id)`` so a retried apply replaces the
    recorded explanation instead of tripping the unique constraint.

    Prefer ``input_snapshots`` captured at collect/calculate time. Re-reading
    live inputs here would fingerprint post-collection edits the calculation
    never evaluated. Live snapshots remain for explanation *reads* only.
    """
    if not outcomes:
        return []
    when = evaluated_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    task_ids = [item.task_id for item in outcomes]
    if input_snapshots is not None:
        snapshots = input_snapshots
    else:
        # Test helpers / legacy callers without a collect snapshot.
        tasks = (
            db.query(Task)
            .filter(Task.owner_id == owner_id, Task.id.in_(task_ids))
            .all()
        )
        snapshots = live_snapshots_by_task(db, tasks)

    existing_rows = (
        db.query(ScheduleTaskOutcome)
        .filter(
            ScheduleTaskOutcome.schedule_run_id == run_id,
            ScheduleTaskOutcome.task_id.in_(task_ids),
        )
        .all()
    )
    existing_by_task = {row.task_id: row for row in existing_rows}

    saved: list[ScheduleTaskOutcome] = []
    for item in outcomes:
        snapshot = snapshots.get(item.task_id)
        facts_json = [fact.to_json() for fact in item.reason_facts]
        placement = None
        if placement_facts_by_task is not None:
            placement = placement_facts_by_task.get(item.task_id)
        if placement is None:
            raw_placement = getattr(item, "placement_facts", None)
            if isinstance(raw_placement, dict):
                placement = raw_placement
        values: dict[str, Any] = {
            "owner_id": owner_id,
            "evaluated_at": when,
            "outcome": outcome_family(item.primary_code),
            "requested_minutes": item.requested_minutes,
            "pinned_minutes": item.pinned_minutes,
            "placed_minutes": item.placed_minutes,
            "remaining_minutes": item.remaining_minutes,
            "primary_reason_code": item.primary_code,
            "reason_facts": facts_json,
            "summary_text": summary_text_for_facts(item.reason_facts),
            "placement_facts": placement,
            "input_snapshot": snapshot,
            "input_fingerprint": fingerprint_snapshot(snapshot),
            "algorithm_version": ALGORITHM_VERSION,
        }
        row = existing_by_task.get(item.task_id)
        if row is None:
            row = ScheduleTaskOutcome(
                schedule_run_id=run_id,
                task_id=item.task_id,
                **values,
            )
            db.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        saved.append(row)
    db.flush()
    return saved
