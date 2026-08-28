from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Reminder, ScheduledBlock, Task
from app.models.enums import ScheduleStatus


def resolve_nesting_level(db: Session, owner_id: uuid.UUID, parent_task_id: uuid.UUID | None) -> int:
    if parent_task_id is None:
        return 0
    parent = db.get(Task, parent_task_id)
    if parent is None or parent.owner_id != owner_id or parent.deleted_at is not None:
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
            Task.deleted_at.is_(None),
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
                Task.deleted_at.is_(None),
            )
            .all()
        )
        for (child_id,) in children:
            descendant_ids.append(child_id)
            queue.append(child_id)
    return descendant_ids


def collect_live_descendant_ids(db: Session, task_id: uuid.UUID, owner_id: uuid.UUID) -> list[uuid.UUID]:
    """BFS over non-trashed descendants (any completion state)."""
    descendant_ids: list[uuid.UUID] = []
    queue: deque[uuid.UUID] = deque([task_id])
    while queue:
        current_id = queue.popleft()
        children = (
            db.query(Task.id)
            .filter(
                Task.owner_id == owner_id,
                Task.parent_task_id == current_id,
                Task.deleted_at.is_(None),
            )
            .all()
        )
        for (child_id,) in children:
            descendant_ids.append(child_id)
            queue.append(child_id)
    return descendant_ids


def collect_descendant_ids(db: Session, task_id: uuid.UUID, owner_id: uuid.UUID) -> list[uuid.UUID]:
    """BFS over all descendants including already-trashed rows."""
    descendant_ids: list[uuid.UUID] = []
    queue: deque[uuid.UUID] = deque([task_id])
    while queue:
        current_id = queue.popleft()
        children = (
            db.query(Task.id)
            .filter(
                Task.owner_id == owner_id,
                Task.parent_task_id == current_id,
            )
            .all()
        )
        for (child_id,) in children:
            descendant_ids.append(child_id)
            queue.append(child_id)
    return descendant_ids


def soft_delete_task_subtree(db: Session, task: Task) -> datetime:
    """Soft-delete task + live descendants with one UTC stamp; hard-drop unpinned blocks.

    ``scheduled_blocks`` has no ``deleted_at`` column, so unpinned blocks for the
    stamped task ids are hard-deleted. Pinned blocks are left in place.
    """
    now = datetime.now(timezone.utc)
    ids = [task.id, *collect_live_descendant_ids(db, task.id, task.owner_id)]
    db.query(Task).filter(Task.id.in_(ids)).update(
        {Task.deleted_at: now},
        synchronize_session=False,
    )
    db.query(ScheduledBlock).filter(
        ScheduledBlock.task_id.in_(ids),
        ScheduledBlock.is_pinned.is_(False),
    ).delete(synchronize_session=False)
    task.deleted_at = now
    return now


def restore_task_subtree(db: Session, task: Task) -> None:
    """Clear ``deleted_at`` on this task and descendants stamped in the same wave."""
    if task.deleted_at is None:
        raise ApiError(409, "Task is not in trash", "NOT_TRASHED")
    wave = task.deleted_at
    ids = [task.id, *collect_descendant_ids(db, task.id, task.owner_id)]
    db.query(Task).filter(Task.id.in_(ids), Task.deleted_at == wave).update(
        {Task.deleted_at: None},
        synchronize_session=False,
    )
    task.deleted_at = None


def _hard_delete_task_blocks(db: Session, task_ids: list[uuid.UUID]) -> None:
    """Permanently remove all scheduled blocks for the given task ids (pinned included)."""
    if not task_ids:
        return
    db.query(ScheduledBlock).filter(ScheduledBlock.task_id.in_(task_ids)).delete(
        synchronize_session=False,
    )


def hard_purge_trashed_task_subtree(db: Session, task: Task) -> int:
    """Permanently delete a trashed task and all descendants. Returns rows removed."""
    if task.deleted_at is None:
        raise ApiError(409, "Task is not in trash", "NOT_TRASHED")
    ids = [task.id, *collect_descendant_ids(db, task.id, task.owner_id)]
    _hard_delete_task_blocks(db, ids)
    db.delete(task)
    return len(ids)


def empty_trash_for_user(
    db: Session,
    owner_id: uuid.UUID,
    *,
    older_than_days: int | None = None,
) -> int:
    """Permanently delete trashed tasks for ``owner_id``. Returns rows removed.

    When ``older_than_days`` is set, only purge tasks whose ``deleted_at`` is
    strictly older than that many days (UTC). When omitted, empty all trash.
    """
    query = db.query(Task).filter(Task.owner_id == owner_id, Task.deleted_at.isnot(None))
    if older_than_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        query = query.filter(Task.deleted_at < cutoff)
    trashed = query.all()
    if not trashed:
        return 0

    trashed_ids = {task.id for task in trashed}
    root_tasks = [
        task
        for task in trashed
        if task.parent_task_id is None or task.parent_task_id not in trashed_ids
    ]

    _hard_delete_task_blocks(db, list(trashed_ids))
    for task in root_tasks:
        db.delete(task)
    return len(trashed_ids)


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
    db.query(Reminder).filter(
        Reminder.task_id == task.id,
        Reminder.owner_id == task.owner_id,
        Reminder.is_fired.is_(False),
    ).update({Reminder.is_fired: True}, synchronize_session=False)
    return None, False
