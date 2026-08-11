"""Focus window (Time Map) CRUD."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import FocusWindow, User
from app.schemas import FocusWindowCreate, FocusWindowOut, FocusWindowUpdate
from app.services.focus_windows import ensure_default_focus_windows

router = APIRouter(prefix="/focus-windows", tags=["focus-windows"])


def _get_owned_focus_window(db: Session, window_id: UUID, user: User) -> FocusWindow:
    window = db.get(FocusWindow, window_id)
    if window is None or window.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Focus window not found")
    return window


def _validate_window_times(start_time, end_time) -> None:
    if end_time <= start_time:
        raise ApiError(422, "end_time must be after start_time", "FOCUS_WINDOW_INVALID_RANGE")


@router.get("", response_model=list[FocusWindowOut])
def list_focus_windows(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FocusWindowOut]:
    # Lazy backfill for accounts created before Time Maps shipped
    if ensure_default_focus_windows(db, user.id):
        db.commit()
    rows = (
        db.query(FocusWindow)
        .filter(FocusWindow.owner_id == user.id)
        .order_by(FocusWindow.name)
        .all()
    )
    return [FocusWindowOut.model_validate(row) for row in rows]


@router.post("", response_model=FocusWindowOut, status_code=status.HTTP_201_CREATED)
def create_focus_window(
    body: FocusWindowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FocusWindowOut:
    _validate_window_times(body.start_time, body.end_time)
    window = FocusWindow(
        owner_id=user.id,
        name=body.name.strip(),
        start_time=body.start_time,
        end_time=body.end_time,
        days_of_week=body.days_of_week,
        is_hard=body.is_hard,
    )
    db.add(window)
    db.commit()
    db.refresh(window)
    return FocusWindowOut.model_validate(window)


@router.get("/{window_id}", response_model=FocusWindowOut)
def get_focus_window(
    window_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FocusWindowOut:
    window = _get_owned_focus_window(db, window_id, user)
    return FocusWindowOut.model_validate(window)


@router.patch("/{window_id}", response_model=FocusWindowOut)
def update_focus_window(
    window_id: UUID,
    body: FocusWindowUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FocusWindowOut:
    window = _get_owned_focus_window(db, window_id, user)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()

    start_time = updates.get("start_time", window.start_time)
    end_time = updates.get("end_time", window.end_time)
    _validate_window_times(start_time, end_time)

    for field, value in updates.items():
        setattr(window, field, value)
    db.commit()
    db.refresh(window)
    return FocusWindowOut.model_validate(window)


@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_focus_window(
    window_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    window = _get_owned_focus_window(db, window_id, user)
    db.delete(window)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
