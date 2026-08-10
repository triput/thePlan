from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import Label, Task, TaskLabel, User
from app.schemas import PaginatedResponse, ReorderRequest, TaskCompleteBody, TaskCreate, TaskOut, TaskUpdate
from app.services.reorder import batch_reorder_sort_order
from app.services.task_helpers import complete_task, mark_task_complete, resolve_nesting_level

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_owned_task(db: Session, task_id: UUID, user: User) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def task_to_out(task: Task, db: Session) -> TaskOut:
    label_ids = [link.label_id for link in task.label_links]
    open_subtask_count = (
        db.query(Task)
        .filter(
            Task.owner_id == task.owner_id,
            Task.parent_task_id == task.id,
            Task.is_completed.is_(False),
        )
        .count()
    )
    return TaskOut.model_validate(
        {
            **TaskOut.model_validate(task).model_dump(),
            "label_ids": label_ids,
            "open_subtask_count": open_subtask_count,
        }
    )


def _sync_task_labels(db: Session, task: Task, user: User, label_ids: list[UUID]) -> None:
    labels = db.query(Label).filter(Label.owner_id == user.id, Label.id.in_(label_ids)).all()
    found_ids = {label.id for label in labels}
    missing = [str(label_id) for label_id in label_ids if label_id not in found_ids]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Labels not found: {', '.join(missing)}")

    db.query(TaskLabel).filter(TaskLabel.task_id == task.id).delete(synchronize_session=False)
    for label in labels:
        db.add(TaskLabel(task_id=task.id, label_id=label.id))


@router.get("", response_model=PaginatedResponse)
def list_tasks(
    project_id: UUID | None = None,
    section_id: UUID | None = None,
    parent_task_id: UUID | None = None,
    is_completed: bool | None = None,
    inbox: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = db.query(Task).filter(Task.owner_id == user.id)
    if inbox:
        query = query.filter(Task.project_id.is_(None))
    elif project_id is not None:
        query = query.filter(Task.project_id == project_id)
    if section_id is not None:
        query = query.filter(Task.section_id == section_id)
    if parent_task_id is not None:
        query = query.filter(Task.parent_task_id == parent_task_id)
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)
    total = query.count()
    items = query.order_by(Task.sort_order, Task.created_at).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[task_to_out(item, db) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    try:
        nesting_level = resolve_nesting_level(db, user.id, body.parent_task_id)
    except ApiError as exc:
        raise exc

    task = Task(
        owner_id=user.id,
        title=body.title.strip(),
        description=body.description,
        project_id=body.project_id,
        section_id=body.section_id,
        parent_task_id=body.parent_task_id,
        nesting_level=nesting_level,
        priority=body.priority,
        due_at=body.due_at,
        deadline_at=body.deadline_at,
        soft_target_at=body.soft_target_at,
        estimated_duration_minutes=body.estimated_duration_minutes,
    )
    db.add(task)
    db.flush()

    if body.label_ids:
        _sync_task_labels(db, task, user, body.label_ids)

    db.commit()
    db.refresh(task)
    return task_to_out(task, db)


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_tasks(
    body: ReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    batch_reorder_sort_order(
        db,
        Task,
        user.id,
        body.items,
        not_found_detail="Tasks not found",
    )


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    return task_to_out(task, db)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: UUID,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    updates = body.model_dump(exclude_unset=True)
    label_ids = updates.pop("label_ids", None)

    if "title" in updates and updates["title"] is not None:
        updates["title"] = updates["title"].strip()

    if "parent_task_id" in updates:
        try:
            updates["nesting_level"] = resolve_nesting_level(db, user.id, updates["parent_task_id"])
        except ApiError as exc:
            raise exc

    for field, value in updates.items():
        setattr(task, field, value)

    if label_ids is not None:
        _sync_task_labels(db, task, user, label_ids)

    db.commit()
    db.refresh(task)
    return task_to_out(task, db)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    task = _get_owned_task(db, task_id, user)
    db.delete(task)
    db.commit()


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task_endpoint(
    task_id: UUID,
    body: TaskCompleteBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    try:
        complete_task(
            db,
            task,
            bulk_children=body.bulk_children,
            force_parent_only=body.force_parent_only,
        )
    except ApiError as exc:
        raise exc
    db.commit()
    db.refresh(task)
    return task_to_out(task, db)


@router.post("/{task_id}/uncomplete", response_model=TaskOut)
def uncomplete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    mark_task_complete(task, completed=False)
    db.commit()
    db.refresh(task)
    return task_to_out(task, db)
