# ==============================================================================
#  File: apps/api/app/services/occurrence_disposition.py
#  Description: T2-S2 B-auto durable miss dispositions + R/S + T2-REC recovery.
#  Component: Occurrence disposition
#  Version: 1.6
#  Created: 2026-10-21
#  Last Update: 2026-10-21
# ==============================================================================

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, time, timezone
from types import SimpleNamespace
from typing import Any, Collection, Mapping
from uuid import UUID
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr
from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.config import get_settings
from app.models import ScheduledBlock, Task, TaskOccurrenceDisposition, TaskProgressEntry, UserSettings
from app.models.task_occurrence_disposition import (
    EVENT_DUPLICATE_MISS,
    EVENT_LEAVE_HELD,
    EVENT_MISS_DETECTED,
    EVENT_RECOVERED,
    EVENT_RELEASED,
    EVENT_SKIPPED,
    RESOLUTION_RECOVERED,
    RESOLUTION_RELEASED,
    RESOLUTION_SKIPPED,
    RESOLUTION_UNRESOLVED_HELD,
    DispositionEvent,
    ProgressEpochMembership,
)
from app.scheduler.input_fingerprint import normalize_occurrence_bounds
from app.scheduler.occurrence_bounds import (
    earliest_start_bound,
    effective_latest_start,
    geometry_infeasible,
    has_occurrence_bounds,
    in_flight_hold_trigger,
    unsupported_shape,
)
from app.scheduler.pin_reservation import reserved_minutes_from_blocks
from app.scheduler.reasons import REASON_OCCURRENCE_BOUNDS_MISS, ReasonFact
from app.scheduler.task_effort import placement_effort_minutes
from app.schemas.occurrence_disposition import RECOVER_REVIEW_CONTRACT_VERSION
from app.services.recurrence import RecurrenceSpec
from app.services.scheduling_revision import (
    assert_scheduling_revision,
    increment_scheduling_revision,
    lock_owner_scheduling,
)
from app.services.source_timezone import IndeterminateLocalTime, attach_naive_wall_clock
from app.services.task_chunking_guard import chunking_bounds_kwargs_for_create
from app.services.task_effort_init import initialize_task_effort_on_create
from app.services.task_occurrence_bounds import (
    assert_merged_bounds_not_inverted,
    require_timezone_aware_instant,
    validate_occurrence_bounds_patch,
)
from app.services.task_workflow import next_board_rank

_REVIEW_BINDING_DOMAIN = b"theplan-t2-rec-ui-review-binding-v1"
_CATCH_UP_INTENT_FIELDS = (
    "catch_up_due_at",
    "catch_up_start_no_earlier_at",
    "catch_up_start_no_later_at",
    "catch_up_deadline_at",
    "catch_up_remaining_minutes",
)

_BOUNDS_PATCH_FIELDS = frozenset(
    {"start_no_earlier_at", "start_no_later_at", "deadline_at"}
)
_TERMINAL_COVERED = (
    RESOLUTION_UNRESOLVED_HELD,
    RESOLUTION_RELEASED,
    RESOLUTION_SKIPPED,
    RESOLUTION_RECOVERED,
)
_ROLL_BOUND_FIELDS = (
    "start_no_earlier_at",
    "start_no_later_at",
    "deadline_at",
    "soft_target_at",
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
    skip_temporal: bool = False,
) -> None:
    """Usable-dates gate — not free-slot / horizon placement promise.

    Structural/geometry always. Temporal (``latest < now``, start_floor >
    latest) skipped only for series accept-past (§C-gate).
    """
    effort = placement_effort_minutes(task)
    if unsupported_shape(task, settings, effort_minutes=effort):
        raise ApiError(
            422,
            "Occurrence bounds still missed or invalid for remaining work",
            "BOUNDS_STILL_MISSED",
        )
    if geometry_infeasible(task, effort_minutes=effort):
        raise ApiError(
            422,
            "Occurrence bounds still missed or invalid for remaining work",
            "BOUNDS_STILL_MISSED",
        )
    if skip_temporal:
        return
    latest = effective_latest_start(task, effort_minutes=effort)
    earliest = earliest_start_bound(task)
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
    # Equivalent floor: cannot start early enough for remaining work.
    start_floor = now if earliest is None else max(now, earliest)
    if latest is not None and start_floor > latest:
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


def _as_rule_local(dt: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(tz)
    return dt.astimezone(tz)


def _rule_to_spec(rule: Any) -> RecurrenceSpec:
    return RecurrenceSpec(
        rrule=rule.rrule,
        is_fixed=bool(rule.is_fixed),
        timezone=rule.timezone,
        starts_on=rule.starts_on,
        ends_on=rule.ends_on,
    )


def _local_time_kind(naive: datetime, tz_name: str) -> str:
    """Gap (wall does not exist) vs fold (wall exists twice).

    ZoneInfo reports different offsets for both, and the shared exception text
    says "ambiguous or nonexistent". Round-trip of fold=0 is the distinction:
    a gap does not come back as the same civil time; a fold does.
    """
    tz = ZoneInfo(tz_name)
    fold0 = naive.replace(tzinfo=tz, fold=0)
    back = fold0.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
    if back != naive:
        return "gap"
    return "fold"


def _attach_wall_or_reject(
    naive: datetime,
    *,
    tz_name: str,
    field: str,
) -> datetime:
    try:
        return attach_naive_wall_clock(naive, tz_name)
    except IndeterminateLocalTime as exc:
        raise ApiError(
            422,
            f"Bounds roll indeterminate local time for {field}: {exc}",
            "BOUNDS_ROLL_INDETERMINATE_LOCAL",
            field=field,
            kind=_local_time_kind(naive, tz_name),
        ) from exc


def _select_next_due_occurrence_local(
    spec: RecurrenceSpec,
    *,
    previous_due: datetime | None,
    completed_at: datetime,
) -> datetime | None:
    """Recovery-path only: next RRULE occurrence with civil wall intact.

    Selection mirrors ``recurrence.next_due_at`` (fixed vs completion anchor,
    dtstart clock from previous_due, starts_on/ends_on frame). Returns the
    dateutil occurrence **before** UTC normalization so DST gap/fold civil
    H:M:S remain available for fail-closed re-attach.

    Does not modify ``recurrence.next_due_at`` / generic engine behavior.
    """
    tz = ZoneInfo(spec.timezone)
    completed_local = _as_rule_local(completed_at, spec.timezone)
    prev_local = (
        _as_rule_local(previous_due, spec.timezone) if previous_due is not None else None
    )
    if prev_local is not None:
        clock = time(prev_local.hour, prev_local.minute, prev_local.second)
    else:
        clock = time(9, 0)
    if spec.is_fixed:
        after = prev_local if prev_local is not None else completed_local
    else:
        after = completed_local
    frame_start = spec.starts_on or after.date()
    dtstart = datetime.combine(frame_start, clock, tzinfo=tz)
    rule = rrulestr(spec.rrule, dtstart=dtstart)
    for occ in rule:
        # Absolute compare matches next_due_at; civil wall stays on ``occ``.
        occ_abs = _as_rule_local(occ, spec.timezone)
        if occ_abs <= after:
            continue
        day = occ_abs.date()
        if spec.starts_on is not None and day < spec.starts_on:
            continue
        if spec.ends_on is not None and day > spec.ends_on:
            break
        return occ
    return None


def _verify_due_wall_clock(
    occurrence_local: datetime,
    *,
    tz_name: str,
) -> datetime:
    """Fail-closed re-attach of the selected RRULE civil occurrence (§C4 / A5).

    Intended naive wall = the selected occurrence's civil Y-M-D + H:M:S:u
    (``occurrence_local`` with tzinfo stripped). This is the wall dateutil
    selected — including FREQ=HOURLY / MINUTELY advances and BYHOUR landings —
    **before** any UTC round-trip can snap a DST gap/fold.

    Re-attach via ``_attach_wall_or_reject`` so gap/fold rejects instead of
    committing a snapped instant. No ``previous_due`` clock fallback and no
    per-BY* reconstruction.
    """
    intended = occurrence_local.replace(tzinfo=None)
    verified = _attach_wall_or_reject(intended, tz_name=tz_name, field="due_at")
    # Civil identity: attach must not rewrite the selected wall (snap would).
    verified_civil = _as_rule_local(verified, tz_name).replace(tzinfo=None)
    if verified_civil.replace(microsecond=0) != intended.replace(microsecond=0):
        raise ApiError(
            422,
            f"Bounds roll indeterminate local time for due_at: "
            f"verified civil {verified_civil.isoformat()} != "
            f"selected {intended.isoformat()}",
            "BOUNDS_ROLL_INDETERMINATE_LOCAL",
            field="due_at",
            kind=_local_time_kind(intended, tz_name),
        )
    return verified


def _roll_instant_by_due_delta(
    value: datetime | None,
    *,
    old_due: datetime,
    new_due: datetime,
    tz_name: str,
    field: str,
) -> datetime | None:
    if value is None:
        return None
    old_local = _as_rule_local(old_due, tz_name)
    new_local = _as_rule_local(new_due, tz_name)
    value_local = _as_rule_local(value, tz_name)
    offset = value_local - old_local
    rolled_naive = (new_local + offset).replace(tzinfo=None)
    return _attach_wall_or_reject(rolled_naive, tz_name=tz_name, field=field)


def _advance_series_due_without_complete(
    task: Task,
    *,
    authorize_instant: datetime,
    accept_past_ack: bool,
    step_count: int | None,
    abort: bool,
    now_utc: datetime,
) -> tuple[datetime, bool]:
    """Compute next-normal due without calling ``complete_task``.

    Returns ``(new_due_utc, accept_past_applied)``.
    """
    rule = task.recurrence_rule
    if rule is None:
        raise ApiError(
            422,
            "Reviewed recovery requires a recurring task; use release for one-offs",
            "RECOVERY_REQUIRES_RECURRING",
        )
    spec = _rule_to_spec(rule)
    missed_due = task.due_at
    if missed_due is None:
        raise ApiError(
            422,
            "Recurring task has no due_at to advance from",
            "RECURRENCE_NO_SUCCESSOR",
        )

    if abort:
        raise ApiError(422, "Recovery aborted by operator", "RECOVERY_ABORTED")

    # Fixed: first occurrence strictly after missed due.
    # Completion-anchored: first occurrence strictly after authorize instant.
    # Recovery-local select preserves civil wall before UTC snap (DST A5 / FREQ).
    candidate = _select_next_due_occurrence_local(
        spec,
        previous_due=missed_due,
        completed_at=authorize_instant,
    )

    if candidate is None:
        raise ApiError(
            422,
            "Recurrence has no successor occurrence",
            "RECURRENCE_NO_SUCCESSOR",
        )

    extra = int(step_count or 0)
    if extra > 0:
        walker = candidate
        for _ in range(extra):
            walker = _select_next_due_occurrence_local(
                spec,
                previous_due=walker,
                completed_at=authorize_instant,
            )
            if walker is None:
                raise ApiError(
                    422,
                    "Recurrence has no successor occurrence",
                    "RECURRENCE_NO_SUCCESSOR",
                )
        candidate = walker

    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    # Wall verify first: re-attach selected civil wall (fail-closed gap/fold).
    # Past-choice MUST run on the final due so verify cannot smuggle a past
    # landing past the gate.
    verified = _verify_due_wall_clock(
        candidate,
        tz_name=rule.timezone,
    )
    verified_utc = (
        verified if verified.tzinfo else verified.replace(tzinfo=timezone.utc)
    ).astimezone(timezone.utc)

    accept_past_applied = False
    if verified_utc < now:
        if not spec.is_fixed:
            # Completion-anchored should be future by construction; fail closed.
            raise ApiError(
                422,
                "Completion-anchored successor landing is still past",
                "BOUNDS_STILL_MISSED",
            )
        if accept_past_ack:
            accept_past_applied = True
        else:
            raise ApiError(
                422,
                "Fixed next-normal landing is still past; "
                "accept_past_ack, step_count, or abort required",
                "FIXED_PAST_REQUIRES_CHOICE",
            )

    return verified_utc, accept_past_applied


def _project_series_bounds_roll(
    task: Task,
    *,
    old_due: datetime,
    new_due: datetime,
    tz_name: str,
) -> dict[str, datetime | None]:
    """Pure bounds-roll math — no ORM attribute assignment."""
    rolled: dict[str, datetime | None] = {"due_at": new_due}
    for field in _ROLL_BOUND_FIELDS:
        rolled[field] = _roll_instant_by_due_delta(
            getattr(task, field),
            old_due=old_due,
            new_due=new_due,
            tz_name=tz_name,
            field=field,
        )
    return rolled


def _apply_series_bounds_roll(
    task: Task,
    *,
    old_due: datetime,
    new_due: datetime,
    tz_name: str,
) -> None:
    rolled = _project_series_bounds_roll(
        task, old_due=old_due, new_due=new_due, tz_name=tz_name
    )
    for field in _ROLL_BOUND_FIELDS:
        setattr(task, field, rolled[field])
    # Due itself already verified; assign after bound rolls so failure rolls back.
    task.due_at = rolled["due_at"]


def _blocks_prevent_next_normal(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    now_utc: datetime,
) -> bool:
    """C2 predicate: same-task blocks/pins poison next-normal (read-only)."""
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.task_id == task_id,
        )
        .all()
    )
    pins = [block for block in blocks if block.is_pinned]
    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    reserved = reserved_minutes_from_blocks(pins, now)
    pin_intervals = [(block.start_time, block.end_time) for block in pins]
    scheduled_intervals = [(block.start_time, block.end_time) for block in blocks]
    # Stand-in: after recovery live worked will be 0 / estimate.
    stand_in = SimpleNamespace(worked_minutes=0)
    return bool(
        in_flight_hold_trigger(
            stand_in,  # type: ignore[arg-type]
            reserved_minutes=reserved,
            pin_intervals=pin_intervals,
            scheduled_intervals=scheduled_intervals,
            now_utc=now,
        )
        or reserved > 0
    )


def _assert_blocks_allow_next_normal(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    now_utc: datetime,
) -> None:
    """C2 fail-closed: same-task blocks/pins poison next-normal (no delete/unpin)."""
    if _blocks_prevent_next_normal(
        db, owner_id=owner_id, task_id=task_id, now_utc=now_utc
    ):
        raise ApiError(
            422,
            "Existing same-task blocks or pins prevent next-normal placement",
            "BLOCKS_PREVENT_NEXT_NORMAL",
        )


def _snapshot_miss_era_progress(
    db: Session,
    *,
    owner_id: UUID,
    task: Task,
    disposition: TaskOccurrenceDisposition,
) -> list[str]:
    """Snapshot open-epoch progress ids onto disposition; insert membership rows."""
    entries = (
        db.query(TaskProgressEntry)
        .filter(
            TaskProgressEntry.owner_id == owner_id,
            TaskProgressEntry.task_id == task.id,
        )
        .all()
    )
    already = {
        row.progress_entry_id
        for row in db.query(ProgressEpochMembership.progress_entry_id)
        .filter(
            ProgressEpochMembership.owner_id == owner_id,
            ProgressEpochMembership.task_id == task.id,
        )
        .all()
    }
    open_ids = [entry.id for entry in entries if entry.id not in already]
    sorted_ids = sorted(str(entry_id) for entry_id in open_ids)
    disposition.miss_era_worked_minutes = int(task.worked_minutes or 0)
    disposition.miss_era_remaining_minutes = task.remaining_minutes
    disposition.miss_era_estimated_minutes = int(task.estimated_duration_minutes)
    disposition.miss_era_entry_ids = sorted_ids
    for entry_id in open_ids:
        db.add(
            ProgressEpochMembership(
                progress_entry_id=entry_id,
                disposition_id=disposition.id,
                owner_id=owner_id,
                task_id=task.id,
            )
        )
    return sorted_ids


def _catch_up_remaining_default(
    task: Task,
    *,
    override: int | None,
) -> int:
    if override is not None:
        return int(override)
    live = task.remaining_minutes
    if live is None:
        return int(task.estimated_duration_minutes)
    return int(live)


def _create_catch_up_task(
    db: Session,
    *,
    series: Task,
    remaining_minutes: int,
    due_at: datetime | None,
    start_no_earlier_at: datetime | None,
    start_no_later_at: datetime | None,
    deadline_at: datetime | None,
) -> Task:
    chunking = chunking_bounds_kwargs_for_create(explicit_fields={})
    catch_up = Task(
        owner_id=series.owner_id,
        title=f"{series.title} (catch-up)",
        description=series.description,
        project_id=series.project_id,
        section_id=series.section_id,
        parent_task_id=None,
        nesting_level=0,
        priority=series.priority,
        due_at=due_at,
        deadline_at=deadline_at,
        start_no_earlier_at=start_no_earlier_at,
        start_no_later_at=start_no_later_at,
        preferred_time_window_id=series.preferred_time_window_id,
        plan_id=series.plan_id,
        schedule_style=series.schedule_style,
        board_rank=next_board_rank(db, series.owner_id),
        **chunking,
    )
    initialize_task_effort_on_create(catch_up, int(series.estimated_duration_minutes))
    catch_up.worked_minutes = 0
    catch_up.remaining_minutes = remaining_minutes
    db.add(catch_up)
    db.flush()
    return catch_up


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_intent_fields_set(fields_set: Collection[str] | None) -> frozenset[str]:
    if not fields_set:
        return frozenset()
    return frozenset(str(name) for name in fields_set if name in _CATCH_UP_INTENT_FIELDS)


def _canonical_recover_intent(
    *,
    accept_past_ack: bool,
    step_count: int | None,
    abort: bool,
    catch_up_due_at: datetime | None,
    catch_up_start_no_earlier_at: datetime | None,
    catch_up_start_no_later_at: datetime | None,
    catch_up_deadline_at: datetime | None,
    catch_up_remaining_minutes: int | None,
    intent_fields_set: Collection[str] | None,
) -> dict[str, Any]:
    """Omit vs null preserved for catch-up fields (Option A wire honesty)."""
    present = _normalize_intent_fields_set(intent_fields_set)
    values: dict[str, Any] = {
        "catch_up_due_at": catch_up_due_at,
        "catch_up_start_no_earlier_at": catch_up_start_no_earlier_at,
        "catch_up_start_no_later_at": catch_up_start_no_later_at,
        "catch_up_deadline_at": catch_up_deadline_at,
        "catch_up_remaining_minutes": catch_up_remaining_minutes,
    }
    catch_up: dict[str, Any] = {}
    for key in _CATCH_UP_INTENT_FIELDS:
        if key not in present:
            continue
        value = values[key]
        if key == "catch_up_remaining_minutes":
            catch_up[key] = None if value is None else int(value)
        else:
            catch_up[key] = _iso_utc(value) if isinstance(value, datetime) else value
    return {
        "accept_past_ack": bool(accept_past_ack),
        "step_count": None if step_count is None else int(step_count),
        "abort": bool(abort),
        "catch_up": catch_up,
    }


def _review_binding_key() -> bytes:
    secret = get_settings().session_secret.encode("utf-8")
    return hmac.new(secret, _REVIEW_BINDING_DOMAIN, hashlib.sha256).digest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


@dataclass(frozen=True)
class SessionWriteObservation:
    """Write-observation proof hook for Renee (fresh Session before/after review)."""

    new: tuple[str, ...]
    dirty: tuple[str, ...]
    deleted: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not self.new and not self.dirty and not self.deleted


def observe_session_writes(db: Session) -> SessionWriteObservation:
    """Snapshot identity-map write sets without logging secrets or bindings."""
    return SessionWriteObservation(
        new=tuple(sorted(type(obj).__name__ for obj in db.new)),
        dirty=tuple(sorted(type(obj).__name__ for obj in db.dirty)),
        deleted=tuple(sorted(type(obj).__name__ for obj in db.deleted)),
    )


def _effort_stand_in(
    *,
    series: Task,
    remaining_minutes: int,
    due_at: datetime | None,
    start_no_earlier_at: datetime | None,
    start_no_later_at: datetime | None,
    deadline_at: datetime | None,
    soft_target_at: datetime | None = None,
    worked_minutes: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        estimated_duration_minutes=int(series.estimated_duration_minutes),
        remaining_minutes=int(remaining_minutes),
        worked_minutes=int(worked_minutes),
        due_at=due_at,
        start_no_earlier_at=start_no_earlier_at,
        start_no_later_at=start_no_later_at,
        deadline_at=deadline_at,
        soft_target_at=soft_target_at,
        min_block_duration_minutes=series.min_block_duration_minutes,
        max_block_duration_minutes=series.max_block_duration_minutes,
        max_block_unbounded=bool(series.max_block_unbounded),
        keep_in_one_block=bool(series.keep_in_one_block),
    )


def _usable_dates_ok(
    stand_in: SimpleNamespace,
    settings: UserSettings,
    *,
    now_utc: datetime,
    skip_temporal: bool = False,
) -> tuple[bool, str | None]:
    try:
        _assert_usable_dates_for_release(
            stand_in,  # type: ignore[arg-type]
            settings,
            now_utc=now_utc,
            skip_temporal=skip_temporal,
        )
    except ApiError as exc:
        code = str(exc.content.get("code") or "BOUNDS_STILL_MISSED")
        return False, code
    return True, None


def _open_miss_era_progress_count(
    db: Session,
    *,
    owner_id: UUID,
    task: Task,
) -> int:
    entries = (
        db.query(TaskProgressEntry.id)
        .filter(
            TaskProgressEntry.owner_id == owner_id,
            TaskProgressEntry.task_id == task.id,
        )
        .all()
    )
    already = {
        row.progress_entry_id
        for row in db.query(ProgressEpochMembership.progress_entry_id)
        .filter(
            ProgressEpochMembership.owner_id == owner_id,
            ProgressEpochMembership.task_id == task.id,
        )
        .all()
    }
    return sum(1 for (entry_id,) in entries if entry_id not in already)


def _load_owner_settings_readonly(db: Session, owner_id: UUID) -> UserSettings:
    settings = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == owner_id)
        .one_or_none()
    )
    if settings is None:
        raise ApiError(404, "Settings not found", "SETTINGS_NOT_FOUND")
    return settings


@dataclass(frozen=True)
class RecoverHeldProjection:
    """Pure recovery review DTO shared by review and authorize pre-write."""

    disposition_id: UUID
    task_id: UUID
    episode_key: str
    expected_revision: int
    authorize_instant: datetime
    contract_version: str
    cadence_is_fixed: bool
    cadence_timezone: str
    rrule_summary: str | None
    eligibility_recurring: bool
    eligibility_one_off_use_release: bool
    next_normal_due_at: datetime | None
    next_normal_start_no_earlier_at: datetime | None
    next_normal_start_no_later_at: datetime | None
    next_normal_deadline_at: datetime | None
    next_normal_landing_is_past: bool
    next_normal_accept_past_required: bool
    next_normal_worked_minutes: int
    next_normal_remaining_minutes: int
    catch_up_remaining_default: int
    catch_up_remaining_minutes: int
    catch_up_due_at: datetime | None
    catch_up_start_no_earlier_at: datetime | None
    catch_up_start_no_later_at: datetime | None
    catch_up_deadline_at: datetime | None
    catch_up_usable_dates_ok: bool
    catch_up_reject_code: str | None
    series_usable_dates_ok: bool
    series_reject_code: str | None
    historical_worked_minutes: int
    historical_remaining_minutes: int | None
    historical_estimated_duration_minutes: int
    historical_progress_entry_count: int
    c2_blocks_prevent: bool
    c2_detail: str | None
    successor_status: str
    accept_past_applied_if_authorized: bool
    review_ok_for_authorize: bool
    intent_canonical: dict[str, Any]
    series_new_due: datetime | None
    series_accept_past_applied: bool

    def projection_claim(self) -> dict[str, Any]:
        """Exact reviewed targets for binding (§2.4) — cadence-stable fields only.

        Temporal gate booleans (landing_is_past / usable_dates_ok / review_ok)
        are rechecked under lock against CURRENT gate time and are not part of
        the MAC material, so clock skew between review and authorize cannot
        silently shift successor/dates while still failing closed on gates.
        """
        return {
            "next_normal": {
                "due_at": _iso_utc(self.next_normal_due_at),
                "start_no_earlier_at": _iso_utc(self.next_normal_start_no_earlier_at),
                "start_no_later_at": _iso_utc(self.next_normal_start_no_later_at),
                "deadline_at": _iso_utc(self.next_normal_deadline_at),
            },
            "next_normal_effort": {
                "worked_minutes": self.next_normal_worked_minutes,
                "remaining_minutes": self.next_normal_remaining_minutes,
            },
            "catch_up": {
                "remaining_minutes_default": self.catch_up_remaining_default,
                "remaining_minutes": self.catch_up_remaining_minutes,
                "due_at": _iso_utc(self.catch_up_due_at),
                "start_no_earlier_at": _iso_utc(self.catch_up_start_no_earlier_at),
                "start_no_later_at": _iso_utc(self.catch_up_start_no_later_at),
                "deadline_at": _iso_utc(self.catch_up_deadline_at),
            },
            "contract_version": self.contract_version,
        }


def project_recover_held_review(
    db: Session,
    *,
    owner_id: UUID,
    task: Task,
    disposition: TaskOccurrenceDisposition,
    settings: UserSettings,
    expected_revision: int,
    authorize_instant: datetime,
    accept_past_ack: bool = False,
    step_count: int | None = None,
    abort: bool = False,
    catch_up_due_at: datetime | None = None,
    catch_up_start_no_earlier_at: datetime | None = None,
    catch_up_start_no_later_at: datetime | None = None,
    catch_up_deadline_at: datetime | None = None,
    catch_up_remaining_minutes: int | None = None,
    intent_fields_set: Collection[str] | None = None,
    now_utc: datetime | None = None,
) -> RecoverHeldProjection:
    """Pure recovery projection — no Session writes / flush / provider side effects."""
    authorize = require_timezone_aware_instant(
        authorize_instant, field="authorize_instant"
    )
    gate_now = now_utc or utc_now()
    if gate_now.tzinfo is None:
        gate_now = gate_now.replace(tzinfo=timezone.utc)
    else:
        gate_now = gate_now.astimezone(timezone.utc)

    intent_canonical = _canonical_recover_intent(
        accept_past_ack=accept_past_ack,
        step_count=step_count,
        abort=abort,
        catch_up_due_at=catch_up_due_at,
        catch_up_start_no_earlier_at=catch_up_start_no_earlier_at,
        catch_up_start_no_later_at=catch_up_start_no_later_at,
        catch_up_deadline_at=catch_up_deadline_at,
        catch_up_remaining_minutes=catch_up_remaining_minutes,
        intent_fields_set=intent_fields_set,
    )

    rule = task.recurrence_rule
    recurring = rule is not None
    historical_count = _open_miss_era_progress_count(
        db, owner_id=owner_id, task=task
    )
    catch_remaining_default = _catch_up_remaining_default(task, override=None)
    catch_remaining = _catch_up_remaining_default(
        task, override=catch_up_remaining_minutes
    )
    # Gate values: aware UTC or None. Omit vs null is binding-canonical only.
    catch_due = (
        require_timezone_aware_instant(catch_up_due_at, field="catch_up_due_at")
        if catch_up_due_at is not None
        else None
    )
    catch_earliest = (
        require_timezone_aware_instant(
            catch_up_start_no_earlier_at, field="catch_up_start_no_earlier_at"
        )
        if catch_up_start_no_earlier_at is not None
        else None
    )
    catch_latest = (
        require_timezone_aware_instant(
            catch_up_start_no_later_at, field="catch_up_start_no_later_at"
        )
        if catch_up_start_no_later_at is not None
        else None
    )
    catch_deadline = (
        require_timezone_aware_instant(
            catch_up_deadline_at, field="catch_up_deadline_at"
        )
        if catch_up_deadline_at is not None
        else None
    )
    assert_merged_bounds_not_inverted(earliest=catch_earliest, latest=catch_latest)

    c2_blocks = _blocks_prevent_next_normal(
        db, owner_id=owner_id, task_id=task.id, now_utc=gate_now
    )
    c2_detail = (
        "Existing same-task blocks or pins prevent next-normal placement"
        if c2_blocks
        else None
    )

    estimate = int(task.estimated_duration_minutes)
    successor_status = "ok"
    accept_past_applied = False
    landing_is_past = False
    accept_past_required = False
    new_due: datetime | None = None
    next_earliest: datetime | None = None
    next_latest: datetime | None = None
    next_deadline: datetime | None = None
    series_gate_ok = True
    series_gate_code: str | None = None

    if not recurring:
        successor_status = "RECOVERY_REQUIRES_RECURRING"
    elif abort:
        successor_status = "RECOVERY_ABORTED"
    elif task.due_at is None:
        successor_status = "RECURRENCE_NO_SUCCESSOR"
    else:
        try:
            new_due, accept_past_applied = _advance_series_due_without_complete(
                task,
                authorize_instant=authorize,
                accept_past_ack=accept_past_ack,
                step_count=step_count,
                abort=False,
                now_utc=gate_now,
            )
            rolled = _project_series_bounds_roll(
                task,
                old_due=task.due_at,
                new_due=new_due,
                tz_name=rule.timezone,  # type: ignore[union-attr]
            )
            next_earliest = rolled["start_no_earlier_at"]
            next_latest = rolled["start_no_later_at"]
            next_deadline = rolled["deadline_at"]
            landing_is_past = new_due < gate_now
            accept_past_required = bool(rule.is_fixed) and landing_is_past and not accept_past_ack
            series_stand_in = _effort_stand_in(
                series=task,
                remaining_minutes=estimate,
                due_at=new_due,
                start_no_earlier_at=next_earliest,
                start_no_later_at=next_latest,
                deadline_at=next_deadline,
                soft_target_at=rolled.get("soft_target_at"),
                worked_minutes=0,
            )
            series_gate_ok, series_gate_code = _usable_dates_ok(
                series_stand_in,
                settings,
                now_utc=gate_now,
                skip_temporal=accept_past_applied,
            )
        except ApiError as exc:
            code = str(exc.content.get("code") or "RECOVERY_REJECTED")
            if code == "FIXED_PAST_REQUIRES_CHOICE":
                successor_status = "FIXED_PAST_REQUIRES_CHOICE"
                accept_past_required = True
                landing_is_past = True
                accept_past_applied = False
                # Soft recompute with accept-past only to surface display targets.
                try:
                    candidate_due, _ = _advance_series_due_without_complete(
                        task,
                        authorize_instant=authorize,
                        accept_past_ack=True,
                        step_count=None,
                        abort=False,
                        now_utc=gate_now,
                    )
                    new_due = candidate_due
                    rolled = _project_series_bounds_roll(
                        task,
                        old_due=task.due_at,
                        new_due=candidate_due,
                        tz_name=rule.timezone,  # type: ignore[union-attr]
                    )
                    next_earliest = rolled["start_no_earlier_at"]
                    next_latest = rolled["start_no_later_at"]
                    next_deadline = rolled["deadline_at"]
                except ApiError:
                    new_due = None
            else:
                successor_status = code
                if code in {
                    "BOUNDS_ROLL_INDETERMINATE_LOCAL",
                    "RECURRENCE_NO_SUCCESSOR",
                    "BOUNDS_STILL_MISSED",
                    "RECOVERY_REQUIRES_RECURRING",
                }:
                    raise

    catch_stand_in = _effort_stand_in(
        series=task,
        remaining_minutes=catch_remaining,
        due_at=catch_due,
        start_no_earlier_at=catch_earliest,
        start_no_later_at=catch_latest,
        deadline_at=catch_deadline,
        worked_minutes=0,
    )
    catch_ok, catch_code = _usable_dates_ok(
        catch_stand_in, settings, now_utc=gate_now, skip_temporal=False
    )

    review_ok = (
        recurring
        and successor_status == "ok"
        and not c2_blocks
        and catch_ok
        and series_gate_ok
        and not abort
    )

    return RecoverHeldProjection(
        disposition_id=disposition.id,
        task_id=task.id,
        episode_key=disposition.episode_key,
        expected_revision=int(expected_revision),
        authorize_instant=authorize,
        contract_version=RECOVER_REVIEW_CONTRACT_VERSION,
        cadence_is_fixed=bool(rule.is_fixed) if rule is not None else False,
        cadence_timezone=rule.timezone if rule is not None else "UTC",
        rrule_summary=rule.rrule if rule is not None else None,
        eligibility_recurring=recurring,
        eligibility_one_off_use_release=not recurring,
        next_normal_due_at=new_due,
        next_normal_start_no_earlier_at=next_earliest,
        next_normal_start_no_later_at=next_latest,
        next_normal_deadline_at=next_deadline,
        next_normal_landing_is_past=landing_is_past,
        next_normal_accept_past_required=accept_past_required,
        next_normal_worked_minutes=0,
        next_normal_remaining_minutes=estimate,
        catch_up_remaining_default=catch_remaining_default,
        catch_up_remaining_minutes=catch_remaining,
        catch_up_due_at=catch_due,
        catch_up_start_no_earlier_at=catch_earliest,
        catch_up_start_no_later_at=catch_latest,
        catch_up_deadline_at=catch_deadline,
        catch_up_usable_dates_ok=catch_ok,
        catch_up_reject_code=catch_code,
        series_usable_dates_ok=series_gate_ok,
        series_reject_code=series_gate_code,
        historical_worked_minutes=int(task.worked_minutes or 0),
        historical_remaining_minutes=task.remaining_minutes,
        historical_estimated_duration_minutes=estimate,
        historical_progress_entry_count=historical_count,
        c2_blocks_prevent=c2_blocks,
        c2_detail=c2_detail,
        successor_status=successor_status,
        accept_past_applied_if_authorized=accept_past_applied,
        review_ok_for_authorize=review_ok,
        intent_canonical=intent_canonical,
        series_new_due=new_due,
        series_accept_past_applied=accept_past_applied,
    )


def issue_recover_review_binding(
    *,
    owner_id: UUID,
    projection: RecoverHeldProjection,
    expected_revision: int,
) -> str:
    """Authenticated domain-separated review binding (stateless HMAC token)."""
    claims = {
        "contract_version": projection.contract_version,
        "owner_id": str(owner_id),
        "task_id": str(projection.task_id),
        "disposition_id": str(projection.disposition_id),
        "episode_key": projection.episode_key,
        "expected_revision": int(expected_revision),
        "authorize_instant": _iso_utc(projection.authorize_instant),
        "intent": projection.intent_canonical,
        "projection": projection.projection_claim(),
    }
    payload = _canonical(claims).encode("utf-8")
    digest = hmac.new(_review_binding_key(), payload, hashlib.sha256).hexdigest()
    return f"{RECOVER_REVIEW_CONTRACT_VERSION}.{_b64url(payload)}.{digest}"


def _parse_recover_review_binding(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ApiError(
            422,
            "Invalid recovery review binding",
            "REVIEW_BINDING_INVALID",
        )
    version, payload_b64, digest = parts
    if version != RECOVER_REVIEW_CONTRACT_VERSION:
        raise ApiError(
            422,
            "Recovery review binding contract version mismatch",
            "REVIEW_BINDING_INVALID",
        )
    try:
        payload = _b64url_decode(payload_b64)
    except (ValueError, TypeError) as exc:
        raise ApiError(
            422,
            "Invalid recovery review binding",
            "REVIEW_BINDING_INVALID",
        ) from exc
    expected = hmac.new(_review_binding_key(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, digest):
        raise ApiError(
            422,
            "Recovery review binding failed verification",
            "REVIEW_BINDING_INVALID",
        )
    try:
        claims = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError(
            422,
            "Invalid recovery review binding",
            "REVIEW_BINDING_INVALID",
        ) from exc
    if not isinstance(claims, dict):
        raise ApiError(
            422,
            "Invalid recovery review binding",
            "REVIEW_BINDING_INVALID",
        )
    return claims


def verify_recover_review_binding(
    *,
    owner_id: UUID,
    task_id: UUID,
    disposition_id: UUID,
    episode_key: str,
    expected_revision: int,
    review_binding: str,
    intent_canonical: Mapping[str, Any],
    projection: RecoverHeldProjection,
    authorize_instant_echo: datetime | None = None,
) -> datetime:
    """Recompute-verified binding check. Returns the bound authorize_instant."""
    claims = _parse_recover_review_binding(review_binding)
    try:
        bound_owner = UUID(str(claims["owner_id"]))
        bound_task = UUID(str(claims["task_id"]))
        bound_disp = UUID(str(claims["disposition_id"]))
        bound_rev = int(claims["expected_revision"])
        bound_episode = str(claims["episode_key"])
        bound_version = str(claims["contract_version"])
        bound_instant = _parse_iso_utc(str(claims["authorize_instant"]))
        bound_intent = claims["intent"]
        bound_projection = claims["projection"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(
            422,
            "Invalid recovery review binding claims",
            "REVIEW_BINDING_INVALID",
        ) from exc

    if bound_instant is None:
        raise ApiError(
            422,
            "Invalid recovery review binding claims",
            "REVIEW_BINDING_INVALID",
        )
    if (
        bound_owner != owner_id
        or bound_task != task_id
        or bound_disp != disposition_id
        or bound_episode != episode_key
        or bound_rev != int(expected_revision)
        or bound_version != RECOVER_REVIEW_CONTRACT_VERSION
    ):
        raise ApiError(
            422,
            "Recovery review binding does not match authorize request",
            "REVIEW_BINDING_MISMATCH",
        )
    if _canonical(bound_intent) != _canonical(dict(intent_canonical)):
        raise ApiError(
            422,
            "Recovery review binding intent mismatch",
            "REVIEW_BINDING_MISMATCH",
        )
    if _canonical(bound_projection) != _canonical(projection.projection_claim()):
        raise ApiError(
            422,
            "Recovery review binding projection mismatch",
            "REVIEW_BINDING_MISMATCH",
        )
    if authorize_instant_echo is not None:
        echo = require_timezone_aware_instant(
            authorize_instant_echo, field="authorize_instant"
        )
        if echo.astimezone(timezone.utc) != bound_instant.astimezone(timezone.utc):
            raise ApiError(
                422,
                "authorize_instant does not match review binding",
                "REVIEW_BINDING_MISMATCH",
            )
    return bound_instant.astimezone(timezone.utc)


@dataclass(frozen=True)
class RecoverHeldReviewResult:
    projection: RecoverHeldProjection
    review_binding: str
    expected_revision: int


def review_recover_held(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    disposition_id: UUID,
    expected_revision: int,
    accept_past_ack: bool = False,
    step_count: int | None = None,
    abort: bool = False,
    catch_up_due_at: datetime | None = None,
    catch_up_start_no_earlier_at: datetime | None = None,
    catch_up_start_no_later_at: datetime | None = None,
    catch_up_deadline_at: datetime | None = None,
    catch_up_remaining_minutes: int | None = None,
    intent_fields_set: Collection[str] | None = None,
) -> RecoverHeldReviewResult:
    """True read-only recovery review: server-issued instant + binding, no writes."""
    # Prefer expire + no-autoflush so identity map cannot flush dirty attrs.
    with db.no_autoflush:
        db.expire_all()
        settings = _load_owner_settings_readonly(db, owner_id)
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
        if row.resolution == RESOLUTION_RECOVERED:
            raise ApiError(
                409,
                "Disposition already terminal with a different resolution",
                "CONFLICT_TERMINAL",
            )
        if row.resolution in (RESOLUTION_RELEASED, RESOLUTION_SKIPPED):
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
            .options(joinedload(Task.recurrence_rule))
            .filter(Task.id == task_id, Task.owner_id == owner_id)
            .populate_existing()
            .one_or_none()
        )
        if task is None:
            raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
        if task.recurrence_rule is None:
            raise ApiError(
                422,
                "Reviewed recovery requires a recurring task; use release for one-offs",
                "RECOVERY_REQUIRES_RECURRING",
            )

        authorize_instant = utc_now()
        projection = project_recover_held_review(
            db,
            owner_id=owner_id,
            task=task,
            disposition=row,
            settings=settings,
            expected_revision=expected_revision,
            authorize_instant=authorize_instant,
            accept_past_ack=accept_past_ack,
            step_count=step_count,
            abort=abort,
            catch_up_due_at=catch_up_due_at,
            catch_up_start_no_earlier_at=catch_up_start_no_earlier_at,
            catch_up_start_no_later_at=catch_up_start_no_later_at,
            catch_up_deadline_at=catch_up_deadline_at,
            catch_up_remaining_minutes=catch_up_remaining_minutes,
            intent_fields_set=intent_fields_set,
            now_utc=authorize_instant,
        )
        binding = issue_recover_review_binding(
            owner_id=owner_id,
            projection=projection,
            expected_revision=expected_revision,
        )
        return RecoverHeldReviewResult(
            projection=projection,
            review_binding=binding,
            expected_revision=expected_revision,
        )


@dataclass(frozen=True)
class RecoverHeldResult:
    disposition: TaskOccurrenceDisposition
    catch_up_task_id: UUID
    replayed: bool = False


def _recover_held_final_flush(db: Session) -> None:
    """Final flush inside ``recover_held``'s nested savepoint.

    Boundary after series reset + terminal disposition/event/rev writes.
    Tests may monkeypatch this to inject late failure after those writes.
    """
    db.flush()


def recover_held(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    disposition_id: UUID,
    expected_revision: int,
    review_binding: str,
    accept_past_ack: bool = False,
    step_count: int | None = None,
    abort: bool = False,
    catch_up_due_at: datetime | None = None,
    catch_up_start_no_earlier_at: datetime | None = None,
    catch_up_start_no_later_at: datetime | None = None,
    catch_up_deadline_at: datetime | None = None,
    catch_up_remaining_minutes: int | None = None,
    intent_fields_set: Collection[str] | None = None,
    authorize_instant: datetime | None = None,
    note: str | None = None,
) -> RecoverHeldResult:
    """Reviewed recovery: verify binding under lock, then mutate.

    Uses the **bound** authorize_instant from ``review_binding`` (not fresh now).
    No silent unbound authorize path.
    """
    if not review_binding or not str(review_binding).strip():
        raise ApiError(
            422,
            "review_binding is required",
            "REVIEW_BINDING_REQUIRED",
        )

    settings = lock_owner_scheduling(db, owner_id)
    # Stale revision precedes terminal no-op / idempotent recover (§C8).
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
    if row.resolution == RESOLUTION_RECOVERED:
        if row.catch_up_task_id is None:
            raise ApiError(
                500,
                "Recovered disposition missing catch_up_task_id",
                "DISPOSITION_SNAPSHOT_CORRUPT",
            )
        return RecoverHeldResult(
            disposition=row,
            catch_up_task_id=row.catch_up_task_id,
            replayed=True,
        )
    if row.resolution in (RESOLUTION_RELEASED, RESOLUTION_SKIPPED):
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
        .options(joinedload(Task.recurrence_rule))
        .filter(Task.id == task_id, Task.owner_id == owner_id)
        .populate_existing()
        .one_or_none()
    )
    if task is None:
        raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
    if task.recurrence_rule is None:
        raise ApiError(
            422,
            "Reviewed recovery requires a recurring task; use release for one-offs",
            "RECOVERY_REQUIRES_RECURRING",
        )

    now_utc = utc_now()
    snapshot_before = dict(row.bounds_snapshot)
    old_due = task.due_at
    if old_due is None:
        raise ApiError(
            422,
            "Recurring task has no due_at to advance from",
            "RECURRENCE_NO_SUCCESSOR",
        )

    intent_canonical = _canonical_recover_intent(
        accept_past_ack=accept_past_ack,
        step_count=step_count,
        abort=abort,
        catch_up_due_at=catch_up_due_at,
        catch_up_start_no_earlier_at=catch_up_start_no_earlier_at,
        catch_up_start_no_later_at=catch_up_start_no_later_at,
        catch_up_deadline_at=catch_up_deadline_at,
        catch_up_remaining_minutes=catch_up_remaining_minutes,
        intent_fields_set=intent_fields_set,
    )
    # Bound instant from claims first (fail closed before projection work if
    # MAC/identity is wrong). Then recompute projection with that instant.
    claims = _parse_recover_review_binding(review_binding)
    try:
        bound_instant = _parse_iso_utc(str(claims["authorize_instant"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(
            422,
            "Invalid recovery review binding claims",
            "REVIEW_BINDING_INVALID",
        ) from exc
    if bound_instant is None:
        raise ApiError(
            422,
            "Invalid recovery review binding claims",
            "REVIEW_BINDING_INVALID",
        )

    # Binding verify uses bound-instant gate time (matches review issuance).
    projection_bound = project_recover_held_review(
        db,
        owner_id=owner_id,
        task=task,
        disposition=row,
        settings=settings,
        expected_revision=expected_revision,
        authorize_instant=bound_instant,
        accept_past_ack=accept_past_ack,
        step_count=step_count,
        abort=abort,
        catch_up_due_at=catch_up_due_at,
        catch_up_start_no_earlier_at=catch_up_start_no_earlier_at,
        catch_up_start_no_later_at=catch_up_start_no_later_at,
        catch_up_deadline_at=catch_up_deadline_at,
        catch_up_remaining_minutes=catch_up_remaining_minutes,
        intent_fields_set=intent_fields_set,
        now_utc=bound_instant,
    )
    authorize = verify_recover_review_binding(
        owner_id=owner_id,
        task_id=task_id,
        disposition_id=disposition_id,
        episode_key=row.episode_key,
        expected_revision=expected_revision,
        review_binding=review_binding,
        intent_canonical=intent_canonical,
        projection=projection_bound,
        authorize_instant_echo=authorize_instant,
    )
    # CURRENT gate time — fail closed on drift; no silent target shift.
    projection = project_recover_held_review(
        db,
        owner_id=owner_id,
        task=task,
        disposition=row,
        settings=settings,
        expected_revision=expected_revision,
        authorize_instant=bound_instant,
        accept_past_ack=accept_past_ack,
        step_count=step_count,
        abort=abort,
        catch_up_due_at=catch_up_due_at,
        catch_up_start_no_earlier_at=catch_up_start_no_earlier_at,
        catch_up_start_no_later_at=catch_up_start_no_later_at,
        catch_up_deadline_at=catch_up_deadline_at,
        catch_up_remaining_minutes=catch_up_remaining_minutes,
        intent_fields_set=intent_fields_set,
        now_utc=now_utc,
    )
    if _canonical(projection.projection_claim()) != _canonical(
        projection_bound.projection_claim()
    ):
        raise ApiError(
            422,
            "Recovery projection drifted under lock",
            "REVIEW_BINDING_MISMATCH",
        )
    if not projection.review_ok_for_authorize:
        if projection.c2_blocks_prevent:
            raise ApiError(
                422,
                projection.c2_detail
                or "Existing same-task blocks or pins prevent next-normal placement",
                "BLOCKS_PREVENT_NEXT_NORMAL",
            )
        if projection.successor_status == "FIXED_PAST_REQUIRES_CHOICE":
            raise ApiError(
                422,
                "Fixed next-normal landing is still past; "
                "accept_past_ack, step_count, or abort required",
                "FIXED_PAST_REQUIRES_CHOICE",
            )
        if projection.successor_status == "RECOVERY_ABORTED":
            raise ApiError(422, "Recovery aborted by operator", "RECOVERY_ABORTED")
        if not projection.catch_up_usable_dates_ok:
            raise ApiError(
                422,
                "Occurrence bounds still missed or invalid for remaining work",
                projection.catch_up_reject_code or "BOUNDS_STILL_MISSED",
            )
        if not projection.series_usable_dates_ok:
            raise ApiError(
                422,
                "Occurrence bounds still missed or invalid for remaining work",
                projection.series_reject_code or "BOUNDS_STILL_MISSED",
            )
        raise ApiError(
            422,
            "Recovery review is not authorizable",
            (
                projection.successor_status
                if projection.successor_status != "ok"
                else "RECOVERY_REJECTED"
            ),
        )

    new_due = projection.series_new_due
    accept_past_applied = projection.series_accept_past_applied
    if new_due is None:
        raise ApiError(
            422,
            "Recurrence has no successor occurrence",
            "RECURRENCE_NO_SUCCESSOR",
        )

    catch_up_remaining = projection.catch_up_remaining_minutes
    catch_due = projection.catch_up_due_at
    catch_earliest = projection.catch_up_start_no_earlier_at
    catch_latest = projection.catch_up_start_no_later_at
    catch_deadline = projection.catch_up_deadline_at

    catch_up_task_id: UUID
    # Nested savepoint: catch-up + series + disposition + rev roll back together.
    with db.begin_nested():
        # C2 before any identity mutation.
        _assert_blocks_allow_next_normal(
            db, owner_id=owner_id, task_id=task_id, now_utc=now_utc
        )

        miss_ids = _snapshot_miss_era_progress(
            db, owner_id=owner_id, task=task, disposition=row
        )

        catch_up = _create_catch_up_task(
            db,
            series=task,
            remaining_minutes=catch_up_remaining,
            due_at=catch_due,
            start_no_earlier_at=catch_earliest,
            start_no_later_at=catch_latest,
            deadline_at=catch_deadline,
        )
        catch_up_task_id = catch_up.id
        # Catch-up gate: always full temporal usable-dates (never accept-past).
        _assert_usable_dates_for_release(catch_up, settings, now_utc=now_utc)

        _apply_series_bounds_roll(
            task,
            old_due=old_due,
            new_due=new_due,
            tz_name=task.recurrence_rule.timezone,
        )
        # Reset live effort before series gate so next-normal is gated on
        # estimate (not miss-era remaining). Snapshot already captured above.
        estimate = int(task.estimated_duration_minutes)
        task.worked_minutes = 0
        task.remaining_minutes = estimate
        # Series gate: structural always; temporal unless accept-past.
        _assert_usable_dates_for_release(
            task,
            settings,
            now_utc=now_utc,
            skip_temporal=accept_past_applied,
        )

        row.catch_up_task_id = catch_up_task_id
        row.authorize_instant = authorize
        row.resolution = RESOLUTION_RECOVERED
        payload: dict[str, Any] = {
            "catch_up_task_id": str(catch_up_task_id),
            "authorize_instant": authorize.isoformat(),
            "series_due_before": old_due.isoformat(),
            "series_due_after": new_due.isoformat(),
            "accept_past": accept_past_applied,
            "step_count": step_count,
            "miss_era_entry_ids": miss_ids,
            "catch_up_remaining_minutes": catch_up_remaining,
            "contract_version": RECOVER_REVIEW_CONTRACT_VERSION,
        }
        if note:
            payload["note"] = note
        db.add(
            DispositionEvent(
                disposition_id=row.id,
                event_type=EVENT_RECOVERED,
                payload=payload,
            )
        )
        increment_scheduling_revision(db, settings)
        _recover_held_final_flush(db)
        if dict(row.bounds_snapshot) != snapshot_before:
            raise ApiError(
                500,
                "bounds_snapshot mutated during recover",
                "DISPOSITION_SNAPSHOT_CORRUPT",
            )

    db.refresh(row)
    return RecoverHeldResult(
        disposition=row,
        catch_up_task_id=catch_up_task_id,
        replayed=False,
    )
