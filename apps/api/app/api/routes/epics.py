from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Epic, User
from app.schemas import EpicCreate, EpicOut, EpicUpdate, PaginatedResponse

router = APIRouter(prefix="/epics", tags=["epics"])


def _get_owned_epic(db: Session, epic_id: UUID, user: User) -> Epic:
    epic = db.get(Epic, epic_id)
    if epic is None or epic.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    return epic


@router.get("", response_model=PaginatedResponse)
def list_epics(
    archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = db.query(Epic).filter(Epic.owner_id == user.id, Epic.is_archived == archived)
    total = query.count()
    items = query.order_by(Epic.sort_order, Epic.created_at).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[EpicOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=EpicOut, status_code=status.HTTP_201_CREATED)
def create_epic(
    body: EpicCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicOut:
    epic = Epic(
        owner_id=user.id,
        title=body.title.strip(),
        description=body.description,
        color_hex=body.color_hex,
        start_date=body.start_date,
        target_date=body.target_date,
    )
    db.add(epic)
    db.commit()
    db.refresh(epic)
    return EpicOut.model_validate(epic)


@router.get("/{epic_id}", response_model=EpicOut)
def get_epic(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicOut:
    epic = _get_owned_epic(db, epic_id, user)
    return EpicOut.model_validate(epic)


@router.patch("/{epic_id}", response_model=EpicOut)
def update_epic(
    epic_id: UUID,
    body: EpicUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicOut:
    epic = _get_owned_epic(db, epic_id, user)
    updates = body.model_dump(exclude_unset=True)
    if "title" in updates and updates["title"] is not None:
        updates["title"] = updates["title"].strip()
    for field, value in updates.items():
        setattr(epic, field, value)
    db.commit()
    db.refresh(epic)
    return EpicOut.model_validate(epic)


@router.delete("/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_epic(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    epic = _get_owned_epic(db, epic_id, user)
    db.delete(epic)
    db.commit()


@router.post("/{epic_id}/archive", response_model=EpicOut)
def archive_epic(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicOut:
    epic = _get_owned_epic(db, epic_id, user)
    epic.is_archived = True
    db.commit()
    db.refresh(epic)
    return EpicOut.model_validate(epic)


@router.post("/{epic_id}/unarchive", response_model=EpicOut)
def unarchive_epic(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicOut:
    epic = _get_owned_epic(db, epic_id, user)
    epic.is_archived = False
    db.commit()
    db.refresh(epic)
    return EpicOut.model_validate(epic)
