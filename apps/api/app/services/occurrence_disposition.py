# ==============================================================================
#  File: apps/api/app/services/occurrence_disposition.py
#  Description: T2-S2 B-auto durable miss dispositions (outside pure calculate).
#  Component: Occurrence disposition
#  Version: 1.1
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
    RESOLUTION_SKIPPED,
    RESOLUTION_UNRESOLVED_HELD,
    DispositionEvent,
)
from app.scheduler.input_fingerprint import normalize_occurrence_bounds
from app.scheduler.occurrence_bounds import has_occurrence_bounds
from app.scheduler.reasons import REASON_OCCURRENCE_BOUNDS_MISS, ReasonFact
from app.services.scheduling_revision import assert_scheduling_revision, lock_owner_scheduling


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
    tasks = {
        row.id: row
        for row in db.query(Task)
        .filter(Task.owner_id == owner_id, Task.id.in_(task_ids))
        .populate_existing()
        .all()
    }
    for task_id, fact in misses.items():
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
    rows = (
        db.query(TaskOccurrenceDisposition.task_id, TaskOccurrenceDisposition.episode_key)
        .filter(
            TaskOccurrenceDisposition.owner_id == owner_id,
            TaskOccurrenceDisposition.resolution == RESOLUTION_UNRESOLVED_HELD,
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
