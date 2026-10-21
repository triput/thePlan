# ==============================================================================
#  File: apps/api/app/services/occurrence_disposition.py
#  Description: T2-S2 B-auto durable miss dispositions + R/S release/skip writers.
#  Component: Occurrence disposition
#  Version: 1.2
#  Created: 2026-10-21
#  Last Update: 2026-10-21
# ==============================================================================

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.models import Task, TaskOccurrenceDisposition
from app.models.task_occurrence_disposition import (
    EVENT_DUPLICATE_MISS,
    EVENT_LEAVE_HELD,
    EVENT_MISS_DETECTED,
    EVENT_RELEASED,
    EVENT_SKIPPED,
    RESOLUTION_RELEASED,
    RESOLUTION_SKIPPED,
    RESOLUTION_UNRESOLVED_HELD,
    DispositionEvent,
)
from app.scheduler.input_fingerprint import normalize_occurrence_bounds
from app.scheduler.occurrence_bounds import (
    effective_latest_start,
    has_occurrence_bounds,
    unsupported_shape,
)
from app.scheduler.reasons import REASON_OCCURRENCE_BOUNDS_MISS, ReasonFact
from app.scheduler.task_effort import placement_effort_minutes
from app.services.scheduling_revision import (
    assert_scheduling_revision,
    increment_scheduling_revision,
    lock_owner_scheduling,
)
from app.services.task_occurrence_bounds import (
    require_timezone_aware_instant,
    validate_occurrence_bounds_patch,
)

_BOUNDS_PATCH_FIELDS = frozenset(
    {"start_no_earlier_at", "start_no_later_at", "deadline_at"}
)
_TERMINAL_COVERED = (
    RESOLUTION_UNRESOLVED_HELD,
    RESOLUTION_RELEASED,
    RESOLUTION_SKIPPED,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def episode_key_for_task(task: Task) -> str:
    """Normalized bound snapshot at miss detection (§1.9)."""
    payload = {
        "bounds": normalize_occurrence_bounds(
            task.start_no_earlier_at,
            task.start_no_later_at,
        ),
        "deadline_at": normalize_occurrence_bounds(None, task.deadline_at).get(
            "start_no_later_at"
        ),
    }
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return digest[:32]


def disposition_fingerprint_rows(
    db: Session, owner_id: UUID
) -> tuple[tuple[str, str, str], ...]:
    rows = (
        db.query(TaskOccurrenceDisposition)
        .filter(
            TaskOccurrenceDisposition.owner_id == owner_id,
            TaskOccurrenceDisposition.resolution.in_(
                (RESOLUTION_UNRESOLVED_HELD, RESOLUTION_SKIPPED)
            ),
        )
        .order_by(TaskOccurrenceDisposition.task_id, TaskOccurrenceDisposition.episode_key)
        .all()
    )
    return tuple(
        (str(row.task_id), row.episode_key, row.resolution) for row in rows
    )


def load_disposition_maps(
    db: Session, owner_id: UUID
) -> tuple[set[UUID], set[UUID], dict[UUID, TaskOccurrenceDisposition]]:
    rows = (
        db.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.owner_id == owner_id)
        .all()
    )
    unresolved: set[UUID] = set()
    skipped: set[UUID] = set()
    by_task: dict[UUID, TaskOccurrenceDisposition] = {}
    for row in rows:
        if row.resolution == RESOLUTION_UNRESOLVED_HELD:
            unresolved.add(row.task_id)
            by_task[row.task_id] = row
        elif row.resolution == RESOLUTION_SKIPPED:
            skipped.add(row.task_id)
            by_task[row.task_id] = row
    return unresolved, skipped, by_task


def normalize_disposition_category(
    row: TaskOccurrenceDisposition | None,
) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "resolution": row.resolution,
        "episode_key": row.episode_key,
    }


def miss_tasks_from_calculation(result: Any) -> dict[UUID, ReasonFact]:
    from app.scheduler.calculate import CalculationResult

    if not isinstance(result, CalculationResult):
        return {}
    misses: dict[UUID, ReasonFact] = {}
    for outcome in result.outcomes:
        for fact in outcome.reason_facts:
            if fact.code == REASON_OCCURRENCE_BOUNDS_MISS:
                misses[outcome.task_id] = fact
                break
    return misses


def _task_still_matches_miss(task: Task, fact: ReasonFact) -> bool:
    if not has_occurrence_bounds(task):
        return False
    params = fact.params or {}
    stored = normalize_occurrence_bounds(task.start_no_earlier_at, task.start_no_later_at)
    for key in ("start_no_earlier_at", "start_no_later_at"):
        if params.get(key) is not None and params.get(key) != stored.get(key):
            return False
    return True


@dataclass(frozen=True)
class StagedMiss:
    task_id: UUID
    episode_key: str
    disposition_id: UUID


def stage_auto_misses(
    db: Session,
    *,
    owner_id: UUID,
    preview_id: UUID,
    misses: dict[UUID, ReasonFact],
    covered_episode_keys: set[tuple[UUID, str]],
) -> list[StagedMiss]:
    """Insert or dedup unresolved_held rows (flush only — no commit)."""
    staged: list[StagedMiss] = []
    if not misses:
        return staged
    task_ids = list(misses)
    # Task-wide skip: never open a new unresolved_held for a skipped task.
    skipped_task_ids = {
        row.task_id
        for row in db.query(TaskOccurrenceDisposition.task_id)
        .filter(
            TaskOccurrenceDisposition.owner_id == owner_id,
            TaskOccurrenceDisposition.task_id.in_(task_ids),
            TaskOccurrenceDisposition.resolution == RESOLUTION_SKIPPED,
        )
        .all()
    }
    tasks = {
        row.id: row
        for row in db.query(Task)
        .filter(Task.owner_id == owner_id, Task.id.in_(task_ids))
        .populate_existing()
        .all()
    }
    for task_id, fact in misses.items():
        if task_id in skipped_task_ids:
            continue
        task = tasks.get(task_id)
        if task is None or not _task_still_matches_miss(task, fact):
            continue
        episode_key = episode_key_for_task(task)
        key = (task_id, episode_key)
        if key in covered_episode_keys:
            continue
        existing = (
            db.query(TaskOccurrenceDisposition)
            .filter(
                TaskOccurrenceDisposition.owner_id == owner_id,
                TaskOccurrenceDisposition.task_id == task_id,
                TaskOccurrenceDisposition.episode_key == episode_key,
            )
            .one_or_none()
        )
        if existing is not None and existing.resolution == RESOLUTION_UNRESOLVED_HELD:
            covered_episode_keys.add(key)
            staged.append(
                StagedMiss(task_id, episode_key, existing.id)
            )
            db.add(
                DispositionEvent(
                    disposition_id=existing.id,
                    event_type=EVENT_DUPLICATE_MISS,
                    payload={"preview_id": str(preview_id), "reason": fact.to_json()},
                    preview_id=preview_id,
                )
            )
            continue
        if existing is not None:
            # Terminal released/skipped (or unexpected) — do not overwrite history.
            covered_episode_keys.add(key)
            continue
        row = TaskOccurrenceDisposition(
            owner_id=owner_id,
            task_id=task_id,
            episode_key=episode_key,
            resolution=RESOLUTION_UNRESOLVED_HELD,
            bounds_snapshot={
                **normalize_occurrence_bounds(
                    task.start_no_earlier_at,
                    task.start_no_later_at,
                ),
                "deadline_at": task.deadline_at.isoformat() if task.deadline_at else None,
            },
            miss_reason_code=fact.code,
            miss_reason_params=dict(fact.params or {}),
        )
        db.add(row)
        db.flush()
        db.add(
            DispositionEvent(
                disposition_id=row.id,
                event_type=EVENT_MISS_DETECTED,
                payload={
                    "preview_id": str(preview_id),
                    "reason": fact.to_json(),
                    "engine_reason_preserved": True,
                },
                preview_id=preview_id,
            )
        )
        covered_episode_keys.add(key)
        staged.append(StagedMiss(task_id, episode_key, row.id))
    return staged


def covered_episode_set(db: Session, owner_id: UUID) -> set[tuple[UUID, str]]:
    """Episode keys that must not re-insert — held + terminal released/skipped."""
    rows = (
        db.query(TaskOccurrenceDisposition.task_id, TaskOccurrenceDisposition.episode_key)
        .filter(
            TaskOccurrenceDisposition.owner_id == owner_id,
            TaskOccurrenceDisposition.resolution.in_(_TERMINAL_COVERED),
        )
        .all()
    )
    return {(task_id, episode_key) for task_id, episode_key in rows}


def list_held_dispositions(db: Session, owner_id: UUID) -> list[TaskOccurrenceDisposition]:
    return (
        db.query(TaskOccurrenceDisposition)
        .options(joinedload(TaskOccurrenceDisposition.events))
        .filter(
            TaskOccurrenceDisposition.owner_id == owner_id,
            TaskOccurrenceDisposition.resolution == RESOLUTION_UNRESOLVED_HELD,
        )
        .order_by(TaskOccurrenceDisposition.updated_at.desc())
        .all()
    )


def leave_held_acknowledgment(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    expected_revision: int,
    note: str | None = None,
) -> TaskOccurrenceDisposition:
    settings = lock_owner_scheduling(db, owner_id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)
    row = (
        db.query(TaskOccurrenceDisposition)
        .filter(
            TaskOccurrenceDisposition.owner_id == owner_id,
            TaskOccurrenceDisposition.task_id == task_id,
            TaskOccurrenceDisposition.resolution == RESOLUTION_UNRESOLVED_HELD,
        )
        .order_by(TaskOccurrenceDisposition.updated_at.desc())
        .first()
    )
    if row is None:
        raise ApiError(
            404,
            "No unresolved held disposition for this task",
            "DISPOSITION_NOT_FOUND",
        )
    db.add(
        DispositionEvent(
            disposition_id=row.id,
            event_type=EVENT_LEAVE_HELD,
            payload={"note": note} if note else {},
        )
    )
    db.flush()
    return row


def _load_named_disposition(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    disposition_id: UUID,
) -> TaskOccurrenceDisposition | None:
    return (
        db.query(TaskOccurrenceDisposition)
        .options(joinedload(TaskOccurrenceDisposition.events))
        .filter(
            TaskOccurrenceDisposition.id == disposition_id,
            TaskOccurrenceDisposition.owner_id == owner_id,
            TaskOccurrenceDisposition.task_id == task_id,
        )
        .populate_existing()
        .one_or_none()
    )


def _live_bounds_refs(task: Task) -> dict[str, str | None]:
    return {
        "start_no_earlier_at": (
            task.start_no_earlier_at.isoformat() if task.start_no_earlier_at else None
        ),
        "start_no_later_at": (
            task.start_no_later_at.isoformat() if task.start_no_later_at else None
        ),
        "deadline_at": task.deadline_at.isoformat() if task.deadline_at else None,
    }


def _assert_usable_dates_for_release(
    task: Task,
    settings: Any,
    *,
    now_utc: datetime,
) -> None:
    """Temporal miss/invalid only — not free-slot / horizon placement promise."""
    effort = placement_effort_minutes(task)
    if unsupported_shape(task, settings, effort_minutes=effort):
        raise ApiError(
            422,
            "Occurrence bounds still missed or invalid for remaining work",
            "BOUNDS_STILL_MISSED",
        )
    latest = effective_latest_start(task, effort_minutes=effort)
    now = now_utc
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    if latest is not None and latest < now:
        raise ApiError(
            422,
            "Occurrence bounds still missed or invalid for remaining work",
            "BOUNDS_STILL_MISSED",
        )


def _apply_live_bounds_patch(task: Task, bounds_updates: dict[str, Any]) -> None:
    updates = {
        key: value
        for key, value in bounds_updates.items()
        if key in _BOUNDS_PATCH_FIELDS
    }
    if not updates:
        return
    if "deadline_at" in updates and updates["deadline_at"] is not None:
        updates["deadline_at"] = require_timezone_aware_instant(
            updates["deadline_at"],  # type: ignore[arg-type]
            field="deadline_at",
        )
    validate_occurrence_bounds_patch(task, updates)
    for key, value in updates.items():
        setattr(task, key, value)


def release_held(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    disposition_id: UUID,
    expected_revision: int,
    note: str | None = None,
    bounds_updates: dict[str, Any] | None = None,
) -> TaskOccurrenceDisposition:
    """R-retry: clear named unresolved_held → released (+ optional atomic bounds)."""
    settings = lock_owner_scheduling(db, owner_id)
    # Stale revision precedes terminal no-op (§10.2).
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)
    row = _load_named_disposition(
        db,
        owner_id=owner_id,
        task_id=task_id,
        disposition_id=disposition_id,
    )
    if row is None:
        raise ApiError(
            404,
            "Held disposition not found for this task",
            "DISPOSITION_NOT_FOUND",
        )
    if row.resolution == RESOLUTION_RELEASED:
        # Same-terminal idempotent: no event, no rev bump, no bounds patch.
        return row
    if row.resolution == RESOLUTION_SKIPPED:
        raise ApiError(
            409,
            "Disposition already terminal with a different resolution",
            "CONFLICT_TERMINAL",
        )
    if row.resolution != RESOLUTION_UNRESOLVED_HELD:
        raise ApiError(
            409,
            "Disposition already terminal with a different resolution",
            "CONFLICT_TERMINAL",
        )

    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.owner_id == owner_id)
        .populate_existing()
        .one_or_none()
    )
    if task is None:
        raise ApiError(404, "Task not found", "TASK_NOT_FOUND")

    snapshot_before = dict(row.bounds_snapshot)
    now_utc = utc_now()
    # Nested savepoint: bounds + resolution + event + rev roll back together.
    with db.begin_nested():
        before_live = _live_bounds_refs(task)
        if bounds_updates:
            _apply_live_bounds_patch(task, bounds_updates)
        after_live = _live_bounds_refs(task)
        _assert_usable_dates_for_release(task, settings, now_utc=now_utc)
        row.resolution = RESOLUTION_RELEASED
        payload: dict[str, Any] = {
            "live_bounds_before": before_live,
            "live_bounds_after": after_live,
        }
        if note:
            payload["note"] = note
        db.add(
            DispositionEvent(
                disposition_id=row.id,
                event_type=EVENT_RELEASED,
                payload=payload,
            )
        )
        increment_scheduling_revision(db, settings)
        db.flush()
        # Immutable miss evidence — never rewrite snapshot.
        if dict(row.bounds_snapshot) != snapshot_before:
            raise ApiError(
                500,
                "bounds_snapshot mutated during release",
                "DISPOSITION_SNAPSHOT_CORRUPT",
            )
    db.refresh(row)
    return row


def skip_held(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    disposition_id: UUID,
    expected_revision: int,
    note: str | None = None,
) -> TaskOccurrenceDisposition:
    """S-suppress: named unresolved_held → skipped (no rev bump; no block mutation)."""
    settings = lock_owner_scheduling(db, owner_id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)
    row = _load_named_disposition(
        db,
        owner_id=owner_id,
        task_id=task_id,
        disposition_id=disposition_id,
    )
    if row is None:
        raise ApiError(
            404,
            "Held disposition not found for this task",
            "DISPOSITION_NOT_FOUND",
        )
    if row.resolution == RESOLUTION_SKIPPED:
        return row
    if row.resolution == RESOLUTION_RELEASED:
        raise ApiError(
            409,
            "Disposition already terminal with a different resolution",
            "CONFLICT_TERMINAL",
        )
    if row.resolution != RESOLUTION_UNRESOLVED_HELD:
        raise ApiError(
            409,
            "Disposition already terminal with a different resolution",
            "CONFLICT_TERMINAL",
        )

    row.resolution = RESOLUTION_SKIPPED
    payload: dict[str, Any] = {}
    if note:
        payload["note"] = note
    db.add(
        DispositionEvent(
            disposition_id=row.id,
            event_type=EVENT_SKIPPED,
            payload=payload,
        )
    )
    db.flush()
    db.refresh(row)
    return row


def _non_disposition_task_drift(snap0: dict[str, Any], snap1: dict[str, Any]) -> bool:
    """True when any task-snapshot category other than occurrence_disposition differs."""
    keys = set(snap0) | set(snap1)
    for key in keys:
        if key == "occurrence_disposition":
            continue
        if snap0.get(key) != snap1.get(key):
            return True
    return False


def orchestration_input_drift(
    *,
    revision_at_start: int,
    revision_live: int,
    snapshot_at_start: dict[str, Any],
    fingerprint_at_start: str,
    snapshot_live: dict[str, Any],
    fingerprint_live: str,
    disposition_before: tuple[tuple[str, str, str], ...],
    disposition_live: tuple[tuple[str, str, str], ...],
    staged_keys: set[tuple[str, str, str]],
) -> bool:
    """External drift iff revision moved or fingerprint differs beyond staged disposition fields.

    Exemption is exact: only ``occurrence_disposition`` on tasks whose disposition
    rows were flushed in this txn (``staged_keys``). Any other field change on a
    staged task, or any change on a non-staged task, is drift.
    """
    if revision_live != revision_at_start:
        return True
    if fingerprint_at_start == fingerprint_live:
        return False
    before = set(disposition_before)
    live = set(disposition_live)
    if live != before | staged_keys:
        return True
    for key in ("dependency_edges", "ups_scores", "scheduling_activation", "snapshot_version"):
        if snapshot_at_start.get(key) != snapshot_live.get(key):
            return True
    staged_task_ids = {task_id for task_id, _, _ in staged_keys}
    snaps0 = snapshot_at_start.get("task_snapshots") or {}
    snaps1 = snapshot_live.get("task_snapshots") or {}
    if set(snaps0) != set(snaps1):
        return True
    if snaps0 or snaps1:
        for task_id, snap0 in snaps0.items():
            snap1 = snaps1.get(task_id) or {}
            if not isinstance(snap0, dict) or not isinstance(snap1, dict):
                return True
            if task_id in staged_task_ids:
                if _non_disposition_task_drift(snap0, snap1):
                    return True
            elif snap0 != snap1:
                return True
        return False
    # Fallback when task_snapshots absent: only whole-task hash equality (no blanket skip).
    t0 = snapshot_at_start.get("task_fingerprints") or {}
    t1 = snapshot_live.get("task_fingerprints") or {}
    if set(t0) != set(t1):
        return True
    for task_id, hash0 in t0.items():
        if hash0 != t1.get(task_id):
            return True
    return False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
