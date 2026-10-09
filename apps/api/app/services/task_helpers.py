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
    visited: set[uuid.UUID] = {task_id}
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
            if child_id in visited:
                continue
            visited.add(child_id)
            descendant_ids.append(child_id)
            queue.append(child_id)
    return descendant_ids


def collect_live_descendant_ids(db: Session, task_id: uuid.UUID, owner_id: uuid.UUID) -> list[uuid.UUID]:
    """BFS over non-trashed descendants (any completion state)."""
    descendant_ids: list[uuid.UUID] = []
    queue: deque[uuid.UUID] = deque([task_id])
    visited: set[uuid.UUID] = {task_id}
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
            if child_id in visited:
                continue
            visited.add(child_id)
            descendant_ids.append(child_id)
            queue.append(child_id)
    return descendant_ids


def collect_descendant_ids(db: Session, task_id: uuid.UUID, owner_id: uuid.UUID) -> list[uuid.UUID]:
    """BFS over all descendants including already-trashed rows."""
    descendant_ids: list[uuid.UUID] = []
    queue: deque[uuid.UUID] = deque([task_id])
    visited: set[uuid.UUID] = {task_id}
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
            if child_id in visited:
                continue
            visited.add(child_id)
            descendant_ids.append(child_id)
            queue.append(child_id)
    return descendant_ids


def nearest_live_ancestor_id(
    db: Session,
    owner_id: uuid.UUID,
    start_parent_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Walk up from ``start_parent_id``; return the nearest non-trashed ancestor, or inbox root."""
    current = start_parent_id
    visited: set[uuid.UUID] = set()
    while current is not None:
        if current in visited:
            return None
        visited.add(current)
        row = db.get(Task, current)
        if row is None or row.owner_id != owner_id:
            return None
        if row.deleted_at is None:
            return row.id
        current = row.parent_task_id
    return None


def _parent_is_live(db: Session, owner_id: uuid.UUID, parent_task_id: uuid.UUID | None) -> bool:
    if parent_task_id is None:
        return True
    parent = db.get(Task, parent_task_id)
    return parent is not None and parent.owner_id == owner_id and parent.deleted_at is None


def reparent_live_tasks_with_invalid_parent(
    db: Session,
    owner_id: uuid.UUID,
    task_ids: list[uuid.UUID],
) -> None:
    """Point live tasks at the nearest live ancestor when parent is missing or trashed."""
    for task_id in task_ids:
        row = db.get(Task, task_id)
        if row is None or row.deleted_at is not None:
            continue
        if _parent_is_live(db, owner_id, row.parent_task_id):
            continue
        new_parent = nearest_live_ancestor_id(db, owner_id, row.parent_task_id)
        row.parent_task_id = new_parent
        row.nesting_level = resolve_nesting_level(db, owner_id, new_parent)


def detach_live_children_before_purge(
    db: Session,
    owner_id: uuid.UUID,
    purge_ids: set[uuid.UUID],
) -> None:
    """Reparent live rows that would CASCADE-delete when a trashed parent is hard-deleted."""
    if not purge_ids:
        return
    live_children = (
        db.query(Task)
        .filter(
            Task.owner_id == owner_id,
            Task.deleted_at.is_(None),
            Task.parent_task_id.in_(purge_ids),
        )
        .all()
    )
    for child in live_children:
        new_parent = nearest_live_ancestor_id(db, owner_id, child.parent_task_id)
        child.parent_task_id = new_parent
        child.nesting_level = resolve_nesting_level(db, owner_id, new_parent)
    # Production sessions use autoflush=False; CASCADE delete must see the
    # reparent UPDATE before the parent DELETE, or live children are removed.
    if live_children:
        db.flush()


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
    restored_ids = [
        row_id
        for (row_id,) in db.query(Task.id)
        .filter(Task.id.in_(ids), Task.deleted_at == wave)
        .all()
    ]
    db.query(Task).filter(Task.id.in_(restored_ids)).update(
        {Task.deleted_at: None},
        synchronize_session=False,
    )
    task.deleted_at = None
    reparent_live_tasks_with_invalid_parent(db, task.owner_id, restored_ids)


def _hard_delete_task_blocks(db: Session, task_ids: list[uuid.UUID]) -> None:
    """Permanently remove all scheduled blocks for the given task ids (pinned included)."""
    if not task_ids:
        return
    db.query(ScheduledBlock).filter(ScheduledBlock.task_id.in_(task_ids)).delete(
        synchronize_session=False,
    )


def hard_purge_trashed_task_subtree(db: Session, task: Task) -> int:
    """Permanently delete a trashed task and trashed descendants only. Returns rows removed."""
    if task.deleted_at is None:
        raise ApiError(409, "Task is not in trash", "NOT_TRASHED")
    subtree_ids = {task.id, *collect_descendant_ids(db, task.id, task.owner_id)}
    purge_ids = {
        row_id
        for (row_id,) in db.query(Task.id)
        .filter(Task.id.in_(subtree_ids), Task.deleted_at.isnot(None))
        .all()
    }
    if not purge_ids:
        return 0
    detach_live_children_before_purge(db, task.owner_id, purge_ids)
    _hard_delete_task_blocks(db, list(purge_ids))
    db.query(Task).filter(Task.id.in_(purge_ids)).delete(synchronize_session=False)
    return len(purge_ids)


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

    detach_live_children_before_purge(db, owner_id, trashed_ids)
    _hard_delete_task_blocks(db, list(trashed_ids))
    db.query(Task).filter(Task.id.in_(trashed_ids), Task.deleted_at.isnot(None)).delete(
        synchronize_session=False,
    )
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
