from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import ScheduledBlock, Task, User
from app.schemas import (
    PaginatedResponse,
    ScheduledBlockCreate,
    ScheduledBlockOut,
    ScheduledBlockUpdate,
)

router = APIRouter(prefix="/scheduled-blocks", tags=["scheduled-blocks"])


def _validate_time_range(start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise ApiError(422, "end_time must be after start_time", "INVALID_TIME_RANGE")


def _get_owned_task(db: Session, task_id: UUID, user: User) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _get_owned_block(db: Session, block_id: UUID, user: User) -> ScheduledBlock:
    block = db.get(ScheduledBlock, block_id)
    if block is None or block.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled block not found")
    return block


@router.get("", response_model=PaginatedResponse)
def list_scheduled_blocks(
    start: datetime = Query(...),
    end: datetime = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    if end <= start:
        raise ApiError(422, "end must be after start", "INVALID_TIME_RANGE")

    query = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == user.id,
            ScheduledBlock.start_time < end,
            ScheduledBlock.end_time > start,
        )
        .order_by(ScheduledBlock.start_time)
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[ScheduledBlockOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ScheduledBlockOut, status_code=status.HTTP_201_CREATED)
def create_scheduled_block(
    body: ScheduledBlockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledBlockOut:
    _validate_time_range(body.start_time, body.end_time)
    _get_owned_task(db, body.task_id, user)

    block = ScheduledBlock(
        owner_id=user.id,
        task_id=body.task_id,
        start_time=body.start_time,
        end_time=body.end_time,
        is_pinned=body.is_pinned,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return ScheduledBlockOut.model_validate(block)


@router.get("/{block_id}", response_model=ScheduledBlockOut)
def get_scheduled_block(
    block_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledBlockOut:
    block = _get_owned_block(db, block_id, user)
    return ScheduledBlockOut.model_validate(block)


@router.patch("/{block_id}", response_model=ScheduledBlockOut)
def update_scheduled_block(
    block_id: UUID,
    body: ScheduledBlockUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScheduledBlockOut:
    block = _get_owned_block(db, block_id, user)
    updates = body.model_dump(exclude_unset=True)

    start_time = updates.get("start_time", block.start_time)
    end_time = updates.get("end_time", block.end_time)
    _validate_time_range(start_time, end_time)

    if "task_id" in updates and updates["task_id"] is not None:
        _get_owned_task(db, updates["task_id"], user)

    for field, value in updates.items():
        setattr(block, field, value)

    db.commit()
    db.refresh(block)
    return ScheduledBlockOut.model_validate(block)


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheduled_block(
    block_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    block = _get_owned_block(db, block_id, user)
    db.delete(block)
    db.commit()
