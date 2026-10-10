"""Nested Time Map override CRUD. Writes never start a replan."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db import get_db
from app.models import FocusWindow, TimeMapOverride, User
from app.schemas.time_map_overrides import (
    TimeMapOverrideCreate,
    TimeMapOverrideOut,
    TimeMapOverrideUpdate,
)
from app.services.scheduling_revision import bump_scheduling_revision, lock_owner_scheduling
from app.services.time_map_overrides import create_time_map_override, update_time_map_override

router = APIRouter(prefix="/focus-windows", tags=["focus-windows"])


def _owned_window(db: Session, window_id: UUID, user: User) -> FocusWindow:
    window = db.get(FocusWindow, window_id)
    if window is None or window.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Focus window not found")
    return window


def _load_override(
    db: Session,
    window: FocusWindow,
    override_id: UUID,
    user: User,
) -> TimeMapOverride:
    row = (
        db.query(TimeMapOverride)
        .options(joinedload(TimeMapOverride.bands))
        .filter(
            TimeMapOverride.id == override_id,
            TimeMapOverride.map_id == window.id,
            TimeMapOverride.owner_id == user.id,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time map override not found",
        )
    return row


@router.get("/{window_id}/overrides", response_model=list[TimeMapOverrideOut])
def list_time_map_overrides(
    window_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TimeMapOverrideOut]:
    """List overrides for one map, including expired rows. Does not replan."""
    window = _owned_window(db, window_id, user)
    rows = (
        db.query(TimeMapOverride)
        .options(joinedload(TimeMapOverride.bands))
        .filter(
            TimeMapOverride.map_id == window.id,
            TimeMapOverride.owner_id == user.id,
        )
        .order_by(TimeMapOverride.local_start_date, TimeMapOverride.id)
        .all()
    )
    return [TimeMapOverrideOut.model_validate(row) for row in rows]


@router.post(
    "/{window_id}/overrides",
    response_model=TimeMapOverrideOut,
    status_code=status.HTTP_201_CREATED,
)
def create_override(
    window_id: UUID,
    body: TimeMapOverrideCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TimeMapOverrideOut:
    """Store a dated replacement. Does not replan."""
    lock_owner_scheduling(db, user.id)
    window = _owned_window(db, window_id, user)
    row = create_time_map_override(
        db,
        window,
        local_start_date=body.local_start_date,
        local_end_date=body.local_end_date,
        timezone_name=body.timezone,
        strict_mode=body.strict_mode,
        bands=body.bands,
    )
    bump_scheduling_revision(db, user.id)
    db.commit()
    row = _load_override(db, window, row.id, user)
    return TimeMapOverrideOut.model_validate(row)


@router.get("/{window_id}/overrides/{override_id}", response_model=TimeMapOverrideOut)
def get_time_map_override(
    window_id: UUID,
    override_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TimeMapOverrideOut:
    window = _owned_window(db, window_id, user)
    row = _load_override(db, window, override_id, user)
    return TimeMapOverrideOut.model_validate(row)


@router.patch("/{window_id}/overrides/{override_id}", response_model=TimeMapOverrideOut)
def patch_time_map_override(
    window_id: UUID,
    override_id: UUID,
    body: TimeMapOverrideUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TimeMapOverrideOut:
    """Update dates, timezone, strictness, or bands. Does not replan."""
    lock_owner_scheduling(db, user.id)
    window = _owned_window(db, window_id, user)
    row = _load_override(db, window, override_id, user)
    updates = body.model_dump(exclude_unset=True)
    bands = body.bands if "bands" in updates and body.bands is not None else None
    update_time_map_override(db, window, row, updates, bands)
    bump_scheduling_revision(db, user.id)
    db.commit()
    row = _load_override(db, window, override_id, user)
    return TimeMapOverrideOut.model_validate(row)


@router.delete(
    "/{window_id}/overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_time_map_override(
    window_id: UUID,
    override_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Delete one override. Does not replan. Expired rows stay until this call."""
    lock_owner_scheduling(db, user.id)
    window = _owned_window(db, window_id, user)
    row = _load_override(db, window, override_id, user)
    db.delete(row)
    bump_scheduling_revision(db, user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
