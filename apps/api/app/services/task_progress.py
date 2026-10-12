"""Atomic progress log (§1.2) — worked entry + confirmed remaining in one transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Task, TaskProgressEntry, User, UserSettings
from app.services.scheduling_revision import (
    assert_scheduling_revision,
    increment_scheduling_revision,
    lock_owner_scheduling,
)


@dataclass(frozen=True)
class ProgressIntent:
    task_id: uuid.UUID
    minutes_worked: int
    remaining_minutes: int
    note: str | None


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


def _assert_idempotency_intent(existing: TaskProgressEntry, intent: ProgressIntent) -> None:
    stored = _intent_from_entry(existing)
    if (
        stored.task_id != intent.task_id
        or stored.minutes_worked != intent.minutes_worked
        or stored.remaining_minutes != intent.remaining_minutes
        or stored.note != intent.note
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


def append_progress_entry(
    db: Session,
    user: User,
    task: Task,
    *,
    idempotency_key: uuid.UUID,
    minutes_worked: int,
    remaining_minutes: int,
    expected_revision: int,
    note: str | None,
) -> tuple[TaskProgressEntry, int, bool]:
    """Return (entry, scheduling_revision_after, replayed)."""
    if minutes_worked <= 0:
        raise ApiError(422, "minutes_worked must be positive", "INVALID_PROGRESS_MINUTES")
    if remaining_minutes < 0:
        raise ApiError(422, "remaining_minutes must be non-negative", "INVALID_REMAINING_MINUTES")

    intent = ProgressIntent(
        task_id=task.id,
        minutes_worked=minutes_worked,
        remaining_minutes=remaining_minutes,
        note=note,
    )

    existing = _lookup_idempotency_entry(db, user.id, idempotency_key)
    if existing is not None:
        _assert_idempotency_intent(existing, intent)
        settings = lock_owner_scheduling(db, user.id)
        return _replay_progress_entry(settings, existing)

    settings = lock_owner_scheduling(db, user.id)

    # Same-key retries can arrive while the first write still holds this lock.
    # Re-read after the lock so a waiter sees the committed row and replays.
    existing = _lookup_idempotency_entry(db, user.id, idempotency_key)
    if existing is not None:
        _assert_idempotency_intent(existing, intent)
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
        _assert_idempotency_intent(raced, intent)
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
