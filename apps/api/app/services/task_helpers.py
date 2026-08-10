from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Task
from app.models.enums import ScheduleStatus


def resolve_nesting_level(db: Session, owner_id: uuid.UUID, parent_task_id: uuid.UUID | None) -> int:
    if parent_task_id is None:
        return 0
    parent = db.get(Task, parent_task_id)
    if parent is None or parent.owner_id != owner_id:
        raise ApiError(404, "Parent task not found", "PARENT_NOT_FOUND")
    next_level = parent.nesting_level + 1
    if next_level > 2:
        raise ApiError(
            400,
            "Maximum nesting depth is 2",
            "NESTING_DEPTH_EXCEEDED",
        )
    return next_level


def count_open_children(db: Session, task_id: uuid.UUID, owner_id: uuid.UUID) -> int:
    return (
        db.query(Task)
        .filter(
            Task.owner_id == owner_id,
            Task.parent_task_id == task_id,
            Task.is_completed.is_(False),
        )
        .count()
    )


def collect_open_descendant_ids(db: Session, task_id: uuid.UUID, owner_id: uuid.UUID) -> list[uuid.UUID]:
    descendant_ids: list[uuid.UUID] = []
    queue: deque[uuid.UUID] = deque([task_id])
    while queue:
        current_id = queue.popleft()
        children = (
            db.query(Task.id)
            .filter(
                Task.owner_id == owner_id,
                Task.parent_task_id == current_id,
                Task.is_completed.is_(False),
            )
            .all()
        )
        for (child_id,) in children:
            descendant_ids.append(child_id)
            queue.append(child_id)
    return descendant_ids


def mark_task_complete(task: Task, *, completed: bool) -> None:
    task.is_completed = completed
    if completed:
        task.completed_at = datetime.now(timezone.utc)
        task.status = ScheduleStatus.completed
    else:
        task.completed_at = None
        if task.status == ScheduleStatus.completed:
            task.status = ScheduleStatus.unscheduled


def _rule_to_spec(rule) -> "RecurrenceSpec":
    from app.services.recurrence import RecurrenceSpec

    return RecurrenceSpec(
        rrule=rule.rrule,
        is_fixed=rule.is_fixed,
        timezone=rule.timezone,
        starts_on=rule.starts_on,
        ends_on=rule.ends_on,
    )


def complete_task(
    db: Session,
    task: Task,
    *,
    bulk_children: bool | None,
    force_parent_only: bool,
) -> tuple[datetime | None, bool]:
    """Complete or advance recurrence.

    Returns (previous_due_at, recurrence_advanced).
    """
    open_count = count_open_children(db, task.id, task.owner_id)
    # Contract: omitted bulk_children → 409; explicit false → parent only;
    # true → bulk. force_parent_only is an alternate parent-only signal.
    if open_count > 0 and bulk_children is None and not force_parent_only:
        raise ApiError(
            409,
            f"Task has {open_count} open subtasks",
            "OPEN_CHILDREN",
            open_count=open_count,
        )

    now = datetime.now(timezone.utc)
    rule = task.recurrence_rule
    if rule is not None:
        from app.services.recurrence import next_due_at

        previous_due = task.due_at
        nxt = next_due_at(
            _rule_to_spec(rule),
            previous_due=previous_due,
            completed_at=now,
        )
        if nxt is not None:
            task.due_at = nxt
            task.is_completed = False
            task.completed_at = None
            if task.status == ScheduleStatus.completed:
                task.status = ScheduleStatus.unscheduled
            # Still bulk-complete children if requested when rolling over parent.
            if bulk_children is True:
                descendant_ids = collect_open_descendant_ids(db, task.id, task.owner_id)
                if descendant_ids:
                    db.query(Task).filter(Task.id.in_(descendant_ids)).update(
                        {
                            Task.is_completed: True,
                            Task.completed_at: now,
                            Task.status: ScheduleStatus.completed,
                        },
                        synchronize_session=False,
                    )
            return previous_due, True

    if bulk_children is True:
        descendant_ids = collect_open_descendant_ids(db, task.id, task.owner_id)
        if descendant_ids:
            db.query(Task).filter(Task.id.in_(descendant_ids)).update(
                {
                    Task.is_completed: True,
                    Task.completed_at: now,
                    Task.status: ScheduleStatus.completed,
                },
                synchronize_session=False,
            )

    mark_task_complete(task, completed=True)
    return None, False
