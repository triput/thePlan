from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import Label, TaskLabel, User
from app.schemas import (
    LabelBatchCreate,
    LabelBatchCreateResponse,
    LabelBatchSkipped,
    LabelCreate,
    LabelOut,
    LabelUpdate,
    PaginatedResponse,
)

router = APIRouter(prefix="/labels", tags=["labels"])


def normalize_label_name(name: str) -> str:
    normalized = name.strip().lower()
    if not normalized:
        raise ApiError(422, "Label name cannot be empty", "LABEL_NAME_EMPTY")
    return normalized


def _get_owned_label(db: Session, label_id: UUID, user: User) -> Label:
    label = db.get(Label, label_id)
    if label is None or label.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    return label


def _task_counts_for_labels(db: Session, label_ids: list[UUID]) -> dict[UUID, int]:
    if not label_ids:
        return {}
    rows = (
        db.query(TaskLabel.label_id, func.count(TaskLabel.task_id))
        .filter(TaskLabel.label_id.in_(label_ids))
        .group_by(TaskLabel.label_id)
        .all()
    )
    return {label_id: count for label_id, count in rows}


def _label_to_out(label: Label, task_count: int = 0) -> LabelOut:
    return LabelOut.model_validate(
        {
            **LabelOut.model_validate(label).model_dump(),
            "task_count": task_count,
        }
    )


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
    counts = _task_counts_for_labels(db, [item.id for item in items])
    return PaginatedResponse(
        items=[_label_to_out(item, counts.get(item.id, 0)) for item in items],
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
        raise ApiError(409, f"Label '{name}' already exists", "LABEL_DUPLICATE")
    label = Label(owner_id=user.id, name=name, color_hex=body.color_hex)
    db.add(label)
    db.commit()
    db.refresh(label)
    return _label_to_out(label)


@router.post("/batch", response_model=LabelBatchCreateResponse)
def batch_create_labels(
    body: LabelBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LabelBatchCreateResponse:
    created_labels: list[Label] = []
    skipped: list[LabelBatchSkipped] = []
    seen_in_request: set[str] = set()
    existing_names = {
        name for (name,) in db.query(Label.name).filter(Label.owner_id == user.id).all()
    }

    for item in body.labels:
        try:
            name = normalize_label_name(item.name)
        except ApiError:
            skipped.append(LabelBatchSkipped(name=item.name.strip(), reason="LABEL_NAME_EMPTY"))
            continue

        if name in seen_in_request:
            skipped.append(LabelBatchSkipped(name=name, reason="duplicate_in_request"))
            continue
        seen_in_request.add(name)

        if name in existing_names:
            skipped.append(LabelBatchSkipped(name=name, reason="LABEL_DUPLICATE"))
            continue

        label = Label(owner_id=user.id, name=name, color_hex=item.color_hex)
        db.add(label)
        created_labels.append(label)
        existing_names.add(name)

    if created_labels:
        db.commit()
        for label in created_labels:
            db.refresh(label)

    return LabelBatchCreateResponse(
        items=[_label_to_out(label) for label in created_labels],
        skipped=skipped,
    )


@router.get("/{label_id}", response_model=LabelOut)
def get_label(
    label_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LabelOut:
    label = _get_owned_label(db, label_id, user)
    counts = _task_counts_for_labels(db, [label.id])
    return _label_to_out(label, counts.get(label.id, 0))


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
            raise ApiError(409, f"Label '{name}' already exists", "LABEL_DUPLICATE")
        updates["name"] = name
    for field, value in updates.items():
        setattr(label, field, value)
    db.commit()
    db.refresh(label)
    counts = _task_counts_for_labels(db, [label.id])
    return _label_to_out(label, counts.get(label.id, 0))


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(
    label_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    label = _get_owned_label(db, label_id, user)
    db.delete(label)
    db.commit()
