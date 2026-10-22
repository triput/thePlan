# ==============================================================================
#  File: apps/api/app/services/occurrence_disposition.py
#  Description: T2-S2 B-auto durable miss dispositions + R/S + T2-REC recovery.
#  Component: Occurrence disposition
#  Version: 1.4
#  Created: 2026-10-21
#  Last Update: 2026-10-21
# ==============================================================================

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.models import ScheduledBlock, Task, TaskOccurrenceDisposition, TaskProgressEntry
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
from app.services.recurrence import RecurrenceSpec, next_due_at
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


def _rrule_by_ints(rrule: str, name: str) -> list[int] | None:
    """Parse ``BYHOUR`` / ``BYMINUTE`` / ``BYSECOND`` values from an RRULE string.

    Returns ``None`` when the part is absent. Multi-value parts return every int
    in declaration order (e.g. ``BYHOUR=9,17`` → ``[9, 17]``).
    """
    needle = f"{name.upper()}="
    for part in rrule.upper().replace("RRULE:", "").split(";"):
        if part.startswith(needle):
            raw = part.split("=", 1)[1]
            if not raw:
                return None
            return [int(token) for token in raw.split(",") if token != ""]
    return None


def _intended_clock_component(
    by_values: list[int] | None,
    *,
    previous: int,
    candidate: int,
) -> int:
    """Resolve one civil clock component for successor wall re-attach.

    - Part absent → previous_due's component (DST clock-of-day preservation).
    - Single BY* value → that value (do not overwrite with previous_due).
    - Multi BY* → candidate when it satisfies the rule (preserves which
      occurrence ``next_due_at`` selected); otherwise the first listed value
      for fail-closed DST re-check.
    """
    if by_values is None:
        return previous
    if len(by_values) == 1:
        return by_values[0]
    if candidate in by_values:
        return candidate
    return by_values[0]


def _verify_due_wall_clock(
    due_utc: datetime,
    *,
    tz_name: str,
    previous_due: datetime,
    rrule: str,
) -> datetime:
    """Fail-closed re-attach of the successor's intended civil time (§C4 / A5b).

    Rebuild the intended wall on the successor civil date and re-attach via
    ``_attach_wall_or_reject`` so a DST gap/fold rejects instead of committing a
    snapped instant. Intended clock components:

    - ``BYHOUR`` / ``BYMINUTE`` / ``BYSECOND`` when present in ``rrule``
      (preserve the RRULE candidate's civil clock — do not replace with
      ``previous_due``'s clock).
    - Otherwise fall back to ``previous_due``'s H/M/S (clock-of-day
      preservation when the rule has no explicit BY* time parts).

    Never silently substitute ``previous_due``'s clock over a legitimate
    BYHOUR/BYMINUTE/BYSECOND landing.
    """
    prev_local = _as_rule_local(previous_due, tz_name)
    cand_local = _as_rule_local(due_utc, tz_name)
    by_hour = _rrule_by_ints(rrule, "BYHOUR")
    by_minute = _rrule_by_ints(rrule, "BYMINUTE")
    by_second = _rrule_by_ints(rrule, "BYSECOND")
    hour = _intended_clock_component(
        by_hour, previous=prev_local.hour, candidate=cand_local.hour
    )
    minute = _intended_clock_component(
        by_minute, previous=prev_local.minute, candidate=cand_local.minute
    )
    second = _intended_clock_component(
        by_second, previous=prev_local.second, candidate=cand_local.second
    )
    # Microseconds only travel with the previous_due fallback path (no BY*).
    microsecond = (
        prev_local.microsecond
        if by_hour is None and by_minute is None and by_second is None
        else 0
    )
    intended = datetime(
        cand_local.year,
        cand_local.month,
        cand_local.day,
        hour,
        minute,
        second,
        microsecond,
    )
    return _attach_wall_or_reject(intended, tz_name=tz_name, field="due_at")


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

    if spec.is_fixed:
        # Fixed: first instant strictly after missed due (completion instant unused).
        candidate = next_due_at(
            spec,
            previous_due=missed_due,
            completed_at=authorize_instant,
        )
    else:
        # Completion-anchored: first instant strictly after bound authorize instant.
        candidate = next_due_at(
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
            walker = next_due_at(
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
    candidate_utc = (
        candidate
        if candidate.tzinfo
        else candidate.replace(tzinfo=timezone.utc)
    ).astimezone(timezone.utc)

    # Wall verify first: may rewrite civil clock (BY* vs previous_due fallback)
    # or reject DST gap/fold. Past-choice MUST run on the final due so verify
    # cannot smuggle a past landing past the gate.
    verified = _verify_due_wall_clock(
        candidate_utc,
        tz_name=rule.timezone,
        previous_due=missed_due,
        rrule=rule.rrule,
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


def _apply_series_bounds_roll(
    task: Task,
    *,
    old_due: datetime,
    new_due: datetime,
    tz_name: str,
) -> None:
    for field in _ROLL_BOUND_FIELDS:
        current = getattr(task, field)
        rolled = _roll_instant_by_due_delta(
            current,
            old_due=old_due,
            new_due=new_due,
            tz_name=tz_name,
            field=field,
        )
        setattr(task, field, rolled)
    # Due itself already verified; assign after bound rolls so failure rolls back.
    task.due_at = new_due


def _assert_blocks_allow_next_normal(
    db: Session,
    *,
    owner_id: UUID,
    task_id: UUID,
    now_utc: datetime,
) -> None:
    """C2 fail-closed: same-task blocks/pins poison next-normal (no delete/unpin)."""
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
    if (
        in_flight_hold_trigger(
            stand_in,  # type: ignore[arg-type]
            reserved_minutes=reserved,
            pin_intervals=pin_intervals,
            scheduled_intervals=scheduled_intervals,
            now_utc=now,
        )
        or reserved > 0
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
    authorize_instant: datetime,
    accept_past_ack: bool = False,
    step_count: int | None = None,
    abort: bool = False,
    catch_up_due_at: datetime | None = None,
    catch_up_start_no_earlier_at: datetime | None = None,
    catch_up_start_no_later_at: datetime | None = None,
    catch_up_deadline_at: datetime | None = None,
    catch_up_remaining_minutes: int | None = None,
    note: str | None = None,
) -> RecoverHeldResult:
    """Reviewed recovery: catch-up one-off + series advance without ``complete_task``."""
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

    authorize = require_timezone_aware_instant(
        authorize_instant, field="authorize_instant"
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

    # Successor choice / abort before any mutation (A7 / C5 abort = no writes).
    new_due, accept_past_applied = _advance_series_due_without_complete(
        task,
        authorize_instant=authorize,
        accept_past_ack=accept_past_ack,
        step_count=step_count,
        abort=abort,
        now_utc=now_utc,
    )
    catch_up_remaining = _catch_up_remaining_default(
        task, override=catch_up_remaining_minutes
    )
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
