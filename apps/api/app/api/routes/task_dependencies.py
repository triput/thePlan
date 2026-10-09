"""Owner-scoped task dependency list/add/remove."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import Task, TaskDependency, User
from app.schemas.handoffs import TaskDependencyCreate, TaskDependencyOut
from app.services.task_dependencies import assert_no_cycle, assert_tasks_owned

router = APIRouter(prefix="/tasks", tags=["task-dependencies"])


def _dependency_out(row: TaskDependency) -> TaskDependencyOut:
    return TaskDependencyOut.model_validate(row)


@router.get("/{task_id}/dependencies", response_model=list[TaskDependencyOut])
def list_task_dependencies(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TaskDependencyOut]:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id or task.deleted_at is not None:
        raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
    rows = (
        db.query(TaskDependency)
        .filter(
            TaskDependency.owner_id == user.id,
            (
                (TaskDependency.blocking_task_id == task_id)
                | (TaskDependency.dependent_task_id == task_id)
            ),
        )
        .order_by(TaskDependency.created_at.asc())
        .all()
    )
    return [_dependency_out(row) for row in rows]


@router.post(
    "/{task_id}/dependencies",
    response_model=TaskDependencyOut,
    status_code=status.HTTP_201_CREATED,
)
def add_task_dependency(
    task_id: UUID,
    body: TaskDependencyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskDependencyOut:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id or task.deleted_at is not None:
        raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
    if task_id not in {body.blocking_task_id, body.dependent_task_id}:
        raise ApiError(
            422,
            "Path task must be blocking or dependent in the dependency",
            "DEPENDENCY_TASK_MISMATCH",
        )
    assert_tasks_owned(db, user.id, body.blocking_task_id, body.dependent_task_id)
    assert_no_cycle(db, user.id, body.blocking_task_id, body.dependent_task_id)

    existing = (
        db.query(TaskDependency)
        .filter(
            TaskDependency.blocking_task_id == body.blocking_task_id,
            TaskDependency.dependent_task_id == body.dependent_task_id,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.owner_id != user.id:
            raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
        return _dependency_out(existing)

    row = TaskDependency(
        owner_id=user.id,
        blocking_task_id=body.blocking_task_id,
        dependent_task_id=body.dependent_task_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _dependency_out(row)


@router.delete(
    "/{task_id}/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_task_dependency(
    task_id: UUID,
    dependency_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id or task.deleted_at is not None:
        raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
    row = db.get(TaskDependency, dependency_id)
    if row is None or row.owner_id != user.id:
        raise ApiError(404, "Dependency not found", "DEPENDENCY_NOT_FOUND")
    if task_id not in {row.blocking_task_id, row.dependent_task_id}:
        raise ApiError(404, "Dependency not found", "DEPENDENCY_NOT_FOUND")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
