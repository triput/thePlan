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


def _bump_revision(task: Task) -> None:
    task.board_revision += 1


def _rank_for_neighbors(before_rank: int | None, after_rank: int | None) -> int:
    if before_rank is not None and after_rank is not None:
        if before_rank >= after_rank:
            return (before_rank + after_rank) // 2 or _MIN_RANK
        return (before_rank + after_rank) // 2
    if before_rank is not None:
        return before_rank + _RANK_GAP
    if after_rank is not None:
        return max(_MIN_RANK, after_rank - _RANK_GAP)
    return _MIN_RANK


def _resolve_board_rank(
    db: Session,
    owner_id: UUID,
    *,
    explicit_rank: int | None,
    insert_before_id: UUID | None,
    insert_after_id: UUID | None,
) -> int | None:
    if explicit_rank is not None:
        return explicit_rank
    if insert_before_id is None and insert_after_id is None:
        return None

    before_rank: int | None = None
    after_rank: int | None = None
    if insert_before_id is not None:
        before = (
            db.query(Task.board_rank)
            .filter(Task.id == insert_before_id, Task.owner_id == owner_id)
            .one_or_none()
        )
        if before is None:
            raise ApiError(404, "insert_before task not found", "TASK_NOT_FOUND")
        before_rank = before[0]
    if insert_after_id is not None:
        after = (
            db.query(Task.board_rank)
            .filter(Task.id == insert_after_id, Task.owner_id == owner_id)
            .one_or_none()
        )
        if after is None:
            raise ApiError(404, "insert_after task not found", "TASK_NOT_FOUND")
        after_rank = after[0]
    return _rank_for_neighbors(before_rank, after_rank)


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
            _bump_revision(task)
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
        _bump_revision(task)
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
    _bump_revision(task)
    return recurrence_advanced, previous_due_at
