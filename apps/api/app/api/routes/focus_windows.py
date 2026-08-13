"""Focus window (Time Map) CRUD."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db import get_db
from app.models import FocusWindow, User
from app.schemas import FocusWindowCreate, FocusWindowOut, FocusWindowUpdate
from app.services.focus_windows import (
    ensure_default_focus_windows,
    replace_bands,
    resolve_create_bands,
    resolve_create_strict_mode,
    resolve_update_bands,
)

router = APIRouter(prefix="/focus-windows", tags=["focus-windows"])


def _load_focus_window(db: Session, window_id: UUID) -> FocusWindow | None:
    return (
        db.query(FocusWindow)
        .options(joinedload(FocusWindow.bands))
        .filter(FocusWindow.id == window_id)
        .one_or_none()
    )


def _get_owned_focus_window(db: Session, window_id: UUID, user: User) -> FocusWindow:
    window = _load_focus_window(db, window_id)
    if window is None or window.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Focus window not found")
    return window


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
        .options(joinedload(FocusWindow.bands))
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
    bands = resolve_create_bands(body)
    window = FocusWindow(
        owner_id=user.id,
        name=body.name.strip(),
        strict_mode=resolve_create_strict_mode(body),
    )
    db.add(window)
    db.flush()
    replace_bands(db, window, bands)
    db.commit()
    window = _load_focus_window(db, window.id)
    assert window is not None
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
        window.name = updates["name"].strip()

    if "strict_mode" in updates and updates["strict_mode"] is not None:
        window.strict_mode = updates["strict_mode"]
    elif "is_hard" in updates and updates["is_hard"] is not None:
        window.strict_mode = updates["is_hard"]

    bands = resolve_update_bands(body, window)
    if bands is not None:
        replace_bands(db, window, bands)

    db.commit()
    window = _load_focus_window(db, window.id)
    assert window is not None
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
