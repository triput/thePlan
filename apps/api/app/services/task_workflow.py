"""F2 Kanban workflow transitions and board rank (separate from sort_order)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models.enums import TaskBoardColumn, TaskWorkflowState
from app.models.task import Task
from app.services.task_helpers import complete_task, mark_task_complete

_RANK_GAP = 1_000_000
_MIN_RANK = 1


def board_column_for_task(task: Task) -> TaskBoardColumn:
    if task.is_completed:
        return TaskBoardColumn.done
    return TaskBoardColumn(task.workflow_state.value)


def _assert_revision(task: Task, expected_revision: int) -> None:
    if task.board_revision != expected_revision:
        raise ApiError(
            409,
            "Task board state changed in another session",
            "BOARD_REVISION_CONFLICT",
            expected_revision=expected_revision,
            current_revision=task.board_revision,
        )


def bump_board_revision(task: Task) -> None:
    task.board_revision += 1


def bump_board_revision_if_column_changed(task: Task, before: TaskBoardColumn) -> None:
    if board_column_for_task(task) != before:
        bump_board_revision(task)


def next_board_rank(db: Session, owner_id: UUID) -> int:
    """Allocate a fresh board_rank after the owner's current maximum."""
    from sqlalchemy import func

    current = (
        db.query(func.max(Task.board_rank))
        .filter(Task.owner_id == owner_id)
        .scalar()
    )
    if current is None:
        return _RANK_GAP
    return int(current) + _RANK_GAP


def _rank_between(lower: int | None, upper: int | None) -> int | None:
    """Return a rank strictly between lower and upper when an integer gap exists."""
    if lower is not None and upper is not None:
        if upper - lower > 1:
            return (lower + upper) // 2
        return None
    if upper is not None:
        if upper > _MIN_RANK:
            candidate = upper - _RANK_GAP
            return candidate if candidate >= _MIN_RANK else max(_MIN_RANK, upper // 2)
        return None
    if lower is not None:
        return lower + _RANK_GAP
    return _RANK_GAP


def _resolve_board_rank(
    db: Session,
    owner_id: UUID,
    *,
    explicit_rank: int | None,
    insert_before_id: UUID | None,
    insert_after_id: UUID | None,
) -> int | None:
    """Ascending board_rank: insert_before → strictly less; insert_after → strictly greater.

    When the integer gap is exhausted, re-gap the neighbor so the insert stays ordered.
    """
    if explicit_rank is not None:
        return explicit_rank
    if insert_before_id is None and insert_after_id is None:
        return None

    before_task: Task | None = None
    after_task: Task | None = None
    if insert_before_id is not None:
        before_task = (
            db.query(Task)
            .filter(Task.id == insert_before_id, Task.owner_id == owner_id)
            .one_or_none()
        )
        if before_task is None:
            raise ApiError(404, "insert_before task not found", "TASK_NOT_FOUND")
    if insert_after_id is not None:
        after_task = (
            db.query(Task)
            .filter(Task.id == insert_after_id, Task.owner_id == owner_id)
            .one_or_none()
        )
        if after_task is None:
            raise ApiError(404, "insert_after task not found", "TASK_NOT_FOUND")

    upper = before_task.board_rank if before_task is not None else None
    lower = after_task.board_rank if after_task is not None else None

    # When only insert_before, find the previous card's rank as the lower bound.
    if before_task is not None and after_task is None:
        prev = (
            db.query(Task)
            .filter(
                Task.owner_id == owner_id,
                Task.deleted_at.is_(None),
                Task.id != before_task.id,
                (
                    (Task.board_rank < before_task.board_rank)
                    | (
                        (Task.board_rank == before_task.board_rank)
                        & (Task.created_at < before_task.created_at)
                    )
                ),
            )
            .order_by(Task.board_rank.desc(), Task.created_at.desc())
            .first()
        )
        if prev is not None:
            lower = prev.board_rank

    # When only insert_after, find the next card's rank as the upper bound.
    if after_task is not None and before_task is None:
        nxt = (
            db.query(Task)
            .filter(
                Task.owner_id == owner_id,
                Task.deleted_at.is_(None),
                Task.id != after_task.id,
                (
                    (Task.board_rank > after_task.board_rank)
                    | (
                        (Task.board_rank == after_task.board_rank)
                        & (Task.created_at > after_task.created_at)
                    )
                ),
            )
            .order_by(Task.board_rank.asc(), Task.created_at.asc())
            .first()
        )
        if nxt is not None:
            upper = nxt.board_rank

    mid = _rank_between(lower, upper)
    if mid is not None and (upper is None or mid < upper) and (lower is None or mid > lower):
        return mid

    # Exhausted / contaminated gap: push the insert_before neighbor up and sit in its old slot
    # (or between lower and that old slot when lower is strictly below).
    if before_task is not None:
        old = before_task.board_rank
        before_task.board_rank = old + _RANK_GAP
        db.flush()
        if lower is not None and lower < old:
            return (lower + old) // 2
        return old
    if after_task is not None:
        return after_task.board_rank + _RANK_GAP
    return next_board_rank(db, owner_id)


def _apply_open_workflow(
    task: Task,
    *,
    target: TaskWorkflowState,
    waiting_note: str | None,
    waiting_note_set: bool,
) -> None:
    task.workflow_state = target
    if target == TaskWorkflowState.waiting:
        if waiting_note_set:
            task.waiting_note = waiting_note.strip() if waiting_note else None
    else:
        task.waiting_note = None


def transition_task_workflow(
    db: Session,
    task: Task,
    *,
    column: TaskBoardColumn,
    expected_revision: int,
    waiting_note: str | None = None,
    waiting_note_set: bool = False,
    board_rank: int | None = None,
    insert_before_id: UUID | None = None,
    insert_after_id: UUID | None = None,
    bulk_children: bool | None = None,
    force_parent_only: bool = False,
) -> tuple[bool, datetime | None]:
    """Move a task on the Kanban board.

    Returns (recurrence_advanced, previous_due_at) when completing/advancing recurrence.
    """
    if task.deleted_at is not None:
        raise ApiError(409, "Task is trashed", "TASK_TRASHED")

    task = (
        db.query(Task)
        .filter(Task.id == task.id, Task.owner_id == task.owner_id)
        .with_for_update()
        .one()
    )
    _assert_revision(task, expected_revision)
    resolved_rank = _resolve_board_rank(
        db,
        task.owner_id,
        explicit_rank=board_rank,
        insert_before_id=insert_before_id,
        insert_after_id=insert_after_id,
    )

    recurrence_advanced = False
    previous_due_at = None

    if column == TaskBoardColumn.done:
        if task.is_completed:
            if resolved_rank is not None:
                task.board_rank = resolved_rank
            bump_board_revision(task)
            return False, None
        previous_due_at, recurrence_advanced = complete_task(
            db,
            task,
            bulk_children=bulk_children,
            force_parent_only=force_parent_only,
        )
        if recurrence_advanced:
            task.workflow_state = TaskWorkflowState.ready
        if resolved_rank is not None:
            task.board_rank = resolved_rank
        bump_board_revision(task)
        return recurrence_advanced, previous_due_at

    # Open column: uncomplete first when moving off Done.
    if task.is_completed:
        mark_task_complete(task, completed=False)

    open_target = TaskWorkflowState(column.value)
    _apply_open_workflow(
        task,
        target=open_target,
        waiting_note=waiting_note,
        waiting_note_set=waiting_note_set,
    )
    if resolved_rank is not None:
        task.board_rank = resolved_rank
    bump_board_revision(task)
    return recurrence_advanced, previous_due_at
