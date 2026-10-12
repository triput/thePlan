"""Atomic progress log (§1.2) — worked entry + confirmed remaining in one transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Task, TaskProgressEntry, User
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling


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


def _assert_scheduling_revision(settings_revision: int, expected: int | None) -> None:
    if expected is None:
        return
    if settings_revision != expected:
        raise ApiError(
            409,
            "Scheduling inputs changed since this action was prepared",
            "SCHEDULING_REVISION_CONFLICT",
            expected_revision=expected,
            current_revision=settings_revision,
        )


def append_progress_entry(
    db: Session,
    user: User,
    task: Task,
    *,
    idempotency_key: uuid.UUID,
    minutes_worked: int,
    remaining_minutes: int,
    expected_revision: int | None,
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

    existing = (
        db.query(TaskProgressEntry)
        .filter(
            TaskProgressEntry.owner_id == user.id,
            TaskProgressEntry.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is not None:
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
        settings = lock_owner_scheduling(db, user.id)
        return existing, int(settings.scheduling_revision), True

    settings = lock_owner_scheduling(db, user.id)
    _assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    locked_task = (
        db.query(Task)
        .filter(Task.id == task.id, Task.owner_id == user.id)
        .with_for_update()
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
        raced = (
            db.query(TaskProgressEntry)
            .filter(
                TaskProgressEntry.owner_id == user.id,
                TaskProgressEntry.idempotency_key == idempotency_key,
            )
            .one_or_none()
        )
        if raced is None:
            raise
        stored = _intent_from_entry(raced)
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
            ) from None
        settings = lock_owner_scheduling(db, user.id)
        return raced, int(settings.scheduling_revision), True

    locked_task.worked_minutes = int(locked_task.worked_minutes) + minutes_worked
    locked_task.remaining_minutes = remaining_minutes
    revision = increment_scheduling_revision(db, settings)
    return entry, revision, False
