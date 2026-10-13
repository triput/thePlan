# ==============================================================================
#  File: apps/api/app/services/task_progress.py
#  Description: Atomic progress log with submitted-intent idempotency.
#  Component: Scheduling / Progress
#  Version: 1.1
#  Created: 2026-10-12
#  Last Update: 2026-10-12
# ==============================================================================

"""Atomic progress log (§1.2) — worked entry + confirmed remaining in one transaction."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Task, TaskProgressEntry, User, UserSettings
from app.services.duration_fields import resolve_minutes_field
from app.services.scheduling_revision import (
    assert_scheduling_revision,
    increment_scheduling_revision,
    lock_owner_scheduling,
)

# Pre-030 backfill sentinel — compare resolved minutes only for those rows.
_LEGACY_RESOLVED_ONLY_HASH = "legacy-resolved-only"


@dataclass(frozen=True)
class ProgressIntent:
    task_id: uuid.UUID
    minutes_worked: int
    remaining_minutes: int
    note: str | None


def _canonical_duration_token(raw: int | str) -> int | str:
    """Stable fingerprint token for duration fields (int 480 ≡ string \"480\")."""
    if isinstance(raw, int):
        return raw
    text = " ".join(str(raw).strip().split())
    if not text:
        return text
    if text.lstrip("-").isdigit():
        return int(text)
    return text


def progress_intent_hash(
    *,
    task_id: uuid.UUID,
    minutes_worked: int | str,
    remaining_minutes: int | str,
    note: str | None,
) -> str:
    """Hash submitted (pre-resolution) progress intent — independent of nominal."""
    payload = {
        "task_id": str(task_id),
        "minutes_worked": _canonical_duration_token(minutes_worked),
        "remaining_minutes": _canonical_duration_token(remaining_minutes),
        "note": note,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _intent_from_entry(entry: TaskProgressEntry) -> ProgressIntent:
    return ProgressIntent(
        task_id=entry.task_id,
        minutes_worked=entry.minutes_worked,
        remaining_minutes=entry.remaining_minutes,
        note=entry.note,
    )


def _lookup_idempotency_entry(
    db: Session,
    owner_id: uuid.UUID,
    idempotency_key: uuid.UUID,
) -> TaskProgressEntry | None:
    return (
        db.query(TaskProgressEntry)
        .filter(
            TaskProgressEntry.owner_id == owner_id,
            TaskProgressEntry.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )


def _assert_idempotency_intent(
    existing: TaskProgressEntry,
    *,
    intent_hash: str,
    resolved: ProgressIntent,
) -> None:
    stored_hash = existing.intent_hash
    if stored_hash and stored_hash != _LEGACY_RESOLVED_ONLY_HASH:
        if stored_hash != intent_hash:
            raise ApiError(
                409,
                "Idempotency key already used with a different payload",
                "IDEMPOTENCY_KEY_REUSE",
            )
        return

    stored = _intent_from_entry(existing)
    if (
        stored.task_id != resolved.task_id
        or stored.minutes_worked != resolved.minutes_worked
        or stored.remaining_minutes != resolved.remaining_minutes
        or stored.note != resolved.note
    ):
        raise ApiError(
            409,
            "Idempotency key already used with a different payload",
            "IDEMPOTENCY_KEY_REUSE",
        )


def _replay_progress_entry(
    settings: UserSettings,
    existing: TaskProgressEntry,
) -> tuple[TaskProgressEntry, int, bool]:
    return existing, int(settings.scheduling_revision), True


def _resolve_progress_durations(
    *,
    minutes_worked_raw: int | str,
    remaining_minutes_raw: int | str,
    nominal_workday_minutes: int,
) -> tuple[int, int]:
    worked = resolve_minutes_field(
        minutes_worked_raw,
        field_label="minutes_worked",
        nominal_workday_minutes=nominal_workday_minutes,
        allow_workdays=False,
        allow_zero=False,
        required=True,
    )
    remaining = resolve_minutes_field(
        remaining_minutes_raw,
        field_label="remaining_minutes",
        nominal_workday_minutes=nominal_workday_minutes,
        allow_workdays=True,
        allow_zero=True,
        required=True,
    )
    assert worked is not None and remaining is not None
    return worked.minutes, remaining.minutes


def append_progress_entry(
    db: Session,
    user: User,
    task: Task,
    *,
    idempotency_key: uuid.UUID,
    minutes_worked_raw: int | str,
    remaining_minutes_raw: int | str,
    expected_revision: int,
    note: str | None,
    nominal_workday_minutes: int,
) -> tuple[TaskProgressEntry, int, bool]:
    """Return (entry, scheduling_revision_after, replayed).

    Idempotency compares the submitted intent hash (stable across later nominal
    changes). Duration strings are resolved against ``nominal_workday_minutes``
    only on first commit; exact retries replay the committed interpretation.
    """
    intent_hash = progress_intent_hash(
        task_id=task.id,
        minutes_worked=minutes_worked_raw,
        remaining_minutes=remaining_minutes_raw,
        note=note,
    )

    existing = _lookup_idempotency_entry(db, user.id, idempotency_key)
    if existing is not None:
        # Replay path: do not re-parse against current nominal (S1-D9).
        if existing.intent_hash == _LEGACY_RESOLVED_ONLY_HASH:
            minutes_worked, remaining_minutes = _resolve_progress_durations(
                minutes_worked_raw=minutes_worked_raw,
                remaining_minutes_raw=remaining_minutes_raw,
                nominal_workday_minutes=nominal_workday_minutes,
            )
            _assert_idempotency_intent(
                existing,
                intent_hash=intent_hash,
                resolved=ProgressIntent(
                    task_id=task.id,
                    minutes_worked=minutes_worked,
                    remaining_minutes=remaining_minutes,
                    note=note,
                ),
            )
        else:
            _assert_idempotency_intent(
                existing,
                intent_hash=intent_hash,
                resolved=ProgressIntent(
                    task_id=task.id,
                    minutes_worked=existing.minutes_worked,
                    remaining_minutes=existing.remaining_minutes,
                    note=note,
                ),
            )
        settings = lock_owner_scheduling(db, user.id)
        return _replay_progress_entry(settings, existing)

    minutes_worked, remaining_minutes = _resolve_progress_durations(
        minutes_worked_raw=minutes_worked_raw,
        remaining_minutes_raw=remaining_minutes_raw,
        nominal_workday_minutes=nominal_workday_minutes,
    )
    if minutes_worked <= 0:
        raise ApiError(422, "minutes_worked must be positive", "INVALID_PROGRESS_MINUTES")
    if remaining_minutes < 0:
        raise ApiError(422, "remaining_minutes must be non-negative", "INVALID_REMAINING_MINUTES")

    resolved = ProgressIntent(
        task_id=task.id,
        minutes_worked=minutes_worked,
        remaining_minutes=remaining_minutes,
        note=note,
    )

    settings = lock_owner_scheduling(db, user.id)

    # Same-key retries can arrive while the first write still holds this lock.
    # Re-read after the lock so a waiter sees the committed row and replays.
    existing = _lookup_idempotency_entry(db, user.id, idempotency_key)
    if existing is not None:
        _assert_idempotency_intent(existing, intent_hash=intent_hash, resolved=resolved)
        return _replay_progress_entry(settings, existing)

    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    locked_task = (
        db.query(Task)
        .filter(Task.id == task.id, Task.owner_id == user.id)
        .with_for_update()
        .populate_existing()
        .one()
    )

    entry = TaskProgressEntry(
        owner_id=user.id,
        task_id=locked_task.id,
        idempotency_key=idempotency_key,
        intent_hash=intent_hash,
        minutes_worked=minutes_worked,
        remaining_minutes=remaining_minutes,
        note=note,
    )
    db.add(entry)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        settings = lock_owner_scheduling(db, user.id)
        raced = _lookup_idempotency_entry(db, user.id, idempotency_key)
        if raced is None:
            raise
        _assert_idempotency_intent(raced, intent_hash=intent_hash, resolved=resolved)
        return _replay_progress_entry(settings, raced)

    db.execute(
        update(Task)
        .where(Task.id == locked_task.id, Task.owner_id == user.id)
        .values(
            worked_minutes=Task.worked_minutes + minutes_worked,
            remaining_minutes=remaining_minutes,
        )
    )
    db.refresh(locked_task)
    revision = increment_scheduling_revision(db, settings)
    return entry, revision, False
