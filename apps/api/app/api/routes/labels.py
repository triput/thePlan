from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Label, User
from app.schemas import LabelCreate, LabelOut, LabelUpdate, PaginatedResponse

router = APIRouter(prefix="/labels", tags=["labels"])


def normalize_label_name(name: str) -> str:
    normalized = name.strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Label name cannot be empty")
    return normalized


def _get_owned_label(db: Session, label_id: UUID, user: User) -> Label:
    label = db.get(Label, label_id)
    if label is None or label.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    return label


@router.get("", response_model=PaginatedResponse)
def list_labels(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = db.query(Label).filter(Label.owner_id == user.id)
    total = query.count()
    items = query.order_by(Label.name).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[LabelOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
def create_label(
    body: LabelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LabelOut:
    name = normalize_label_name(body.name)
    existing = db.query(Label).filter(Label.owner_id == user.id, Label.name == name).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Label '{name}' already exists",
        )
    label = Label(owner_id=user.id, name=name, color_hex=body.color_hex)
    db.add(label)
    db.commit()
    db.refresh(label)
    return LabelOut.model_validate(label)


@router.get("/{label_id}", response_model=LabelOut)
def get_label(
    label_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LabelOut:
    label = _get_owned_label(db, label_id, user)
    return LabelOut.model_validate(label)


@router.patch("/{label_id}", response_model=LabelOut)
def update_label(
    label_id: UUID,
    body: LabelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LabelOut:
    label = _get_owned_label(db, label_id, user)
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        name = normalize_label_name(updates["name"])
        existing = (
            db.query(Label)
            .filter(Label.owner_id == user.id, Label.name == name, Label.id != label.id)
            .first()
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Label '{name}' already exists",
            )
        updates["name"] = name
    for field, value in updates.items():
        setattr(label, field, value)
    db.commit()
    db.refresh(label)
    return LabelOut.model_validate(label)


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(
    label_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    label = _get_owned_label(db, label_id, user)
    db.delete(label)
    db.commit()
