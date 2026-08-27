from datetime import datetime, timedelta, timezone
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.config import get_settings
from app.db import get_db
from app.models import ScheduledBlock, Task, User
from app.schemas import (
    ClearUnpinnedBlocksBody,
    ClearUnpinnedBlocksOut,
    PaginatedResponse,
    ReleaseRemainderBody,
    ReleaseRemainderOut,
    ScheduledBlockCreate,
    ScheduledBlockOut,
    ScheduledBlockUpdate,
)
from app.services.google_calendar import (
    delete_mirrored_block as delete_mirrored_block_google,
    push_scheduled_block as push_scheduled_block_google,
)
from app.services.microsoft_calendar import (
    delete_mirrored_block as delete_mirrored_block_microsoft,
    push_scheduled_block as push_scheduled_block_microsoft,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-blocks", tags=["scheduled-blocks"])

_MIN_BLOCK_AFTER_TRUNCATE = timedelta(minutes=1)


def push_scheduled_block(db: Session, settings, block: ScheduledBlock) -> None:
    """Push to Google and Microsoft; each provider no-ops when not configured/mirrored."""
    push_scheduled_block_google(db, settings, block)
    push_scheduled_block_microsoft(db, settings, block)


def delete_mirrored_block(db: Session, settings, block: ScheduledBlock) -> None:
    """Delete Google and Microsoft mirrors; each provider no-ops when none exists."""
    delete_mirrored_block_google(db, settings, block)
    delete_mirrored_block_microsoft(db, settings, block)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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


def _delete_block(db: Session, settings, block: ScheduledBlock) -> None:
    block_id = block.id
    try:
        delete_mirrored_block(db, settings, block)
        db.commit()
    except Exception:
        logger.exception("Failed to delete mirrored calendar event for block %s", block_id)
        db.rollback()
    db.delete(block)
    db.commit()


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


@router.post("/clear-unpinned", response_model=ClearUnpinnedBlocksOut)
def clear_unpinned_blocks(
    body: ClearUnpinnedBlocksBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClearUnpinnedBlocksOut:
    if body.end <= body.start:
        raise ApiError(422, "end must be after start", "INVALID_TIME_RANGE")

    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == user.id,
            ScheduledBlock.is_pinned.is_(False),
            ScheduledBlock.start_time < body.end,
            ScheduledBlock.end_time > body.start,
        )
        .all()
    )
    settings = get_settings()
    deleted_count = 0
    for block in blocks:
        _delete_block(db, settings, block)
        deleted_count += 1
    return ClearUnpinnedBlocksOut(deleted_count=deleted_count)


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
    block_id = block.id
    settings = get_settings()
    try:
        push_scheduled_block(db, settings, block)
        db.commit()
    except Exception:
        logger.exception("Failed to mirror scheduled block %s to calendar", block_id)
        db.rollback()
        block = db.get(ScheduledBlock, block_id)
        if block is None:
            raise
    return ScheduledBlockOut.model_validate(block)


@router.post("/{block_id}/release-remainder", response_model=ReleaseRemainderOut)
def release_block_remainder(
    block_id: UUID,
    body: ReleaseRemainderBody | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReleaseRemainderOut:
    block = _get_owned_block(db, block_id, user)
    at = _ensure_utc(body.at if body and body.at is not None else datetime.now(timezone.utc))
    start = _ensure_utc(block.start_time)
    end = _ensure_utc(block.end_time)

    if end <= at:
        raise ApiError(422, "Nothing to release — block already ended", "NOTHING_TO_RELEASE")

    settings = get_settings()

    if at <= start or (at - start) < _MIN_BLOCK_AFTER_TRUNCATE:
        _delete_block(db, settings, block)
        return ReleaseRemainderOut(block=None, deleted=True)

    block.end_time = at
    db.commit()
    db.refresh(block)
    try:
        push_scheduled_block(db, settings, block)
        db.commit()
    except Exception:
        logger.exception("Failed to mirror scheduled block %s to calendar", block.id)
        db.rollback()
        block = db.get(ScheduledBlock, block.id)
        if block is None:
            raise
    return ReleaseRemainderOut(block=ScheduledBlockOut.model_validate(block), deleted=False)


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
    block_id = block.id
    settings = get_settings()
    try:
        push_scheduled_block(db, settings, block)
        db.commit()
    except Exception:
        logger.exception("Failed to mirror scheduled block %s to calendar", block_id)
        db.rollback()
        block = db.get(ScheduledBlock, block_id)
        if block is None:
            raise
    return ScheduledBlockOut.model_validate(block)


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheduled_block(
    block_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    block = _get_owned_block(db, block_id, user)
    settings = get_settings()
    _delete_block(db, settings, block)
