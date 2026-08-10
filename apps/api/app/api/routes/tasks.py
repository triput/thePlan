from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Label, Task, TaskLabel, User
from app.schemas import PaginatedResponse, TaskCreate, TaskOut

router = APIRouter(prefix="/tasks", tags=["tasks"])


def task_to_out(task: Task) -> TaskOut:
    label_ids = [link.label_id for link in task.label_links]
    return TaskOut.model_validate({**TaskOut.model_validate(task).model_dump(), "label_ids": label_ids})


@router.get("", response_model=PaginatedResponse)
def list_tasks(
    project_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = db.query(Task).filter(Task.owner_id == user.id)
    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    total = query.count()
    items = query.order_by(Task.sort_order, Task.created_at).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[task_to_out(item) for item in items],
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
    task = Task(
        owner_id=user.id,
        title=body.title.strip(),
        description=body.description,
        project_id=body.project_id,
        section_id=body.section_id,
        parent_task_id=body.parent_task_id,
        priority=body.priority,
        due_at=body.due_at,
        estimated_duration_minutes=body.estimated_duration_minutes,
    )
    db.add(task)
    db.flush()

    if body.label_ids:
        labels = (
            db.query(Label)
            .filter(Label.owner_id == user.id, Label.id.in_(body.label_ids))
            .all()
        )
        for label in labels:
            db.add(TaskLabel(task_id=task.id, label_id=label.id))

    db.commit()
    db.refresh(task)
    return task_to_out(task)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task_to_out(task)
