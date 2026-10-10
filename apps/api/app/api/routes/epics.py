from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import Epic, User
from app.schemas import (
    EpicCreate,
    EpicDemoteToProjectBody,
    EpicDemoteToProjectOut,
    EpicOut,
    EpicUpdate,
    PaginatedResponse,
    ProjectOut,
)
from app.services.hierarchy_promote import demote_epic_to_project
from app.services.ownership import verify_owned_focus_window
from app.services.scheduling_revision import (
    increment_scheduling_revision,
    lock_owner_scheduling,
    epic_patch_touches_scheduling,
)

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
    if body.preferred_time_window_id is not None:
        verify_owned_focus_window(db, body.preferred_time_window_id, user)
    settings = lock_owner_scheduling(db, user.id)
    epic = Epic(
        owner_id=user.id,
        title=body.title.strip(),
        description=body.description,
        color_hex=body.color_hex,
        start_date=body.start_date,
        target_date=body.target_date,
        preferred_time_window_id=body.preferred_time_window_id,
        schedule_style=body.schedule_style,
    )
    db.add(epic)
    if body.preferred_time_window_id is not None or body.schedule_style is not None:
        increment_scheduling_revision(db, settings)
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
    updates = body.model_dump(exclude_unset=True)
    touches_scheduling = epic_patch_touches_scheduling(updates)
    settings = lock_owner_scheduling(db, user.id) if touches_scheduling else None
    epic = _get_owned_epic(db, epic_id, user)
    if "preferred_time_window_id" in updates and updates["preferred_time_window_id"] is not None:
        verify_owned_focus_window(db, updates["preferred_time_window_id"], user)
    if "title" in updates and updates["title"] is not None:
        updates["title"] = updates["title"].strip()
    for field, value in updates.items():
        setattr(epic, field, value)
    if touches_scheduling and settings is not None:
        increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(epic)
    return EpicOut.model_validate(epic)


@router.delete("/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_epic(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    settings = lock_owner_scheduling(db, user.id)
    epic = _get_owned_epic(db, epic_id, user)
    db.delete(epic)
    increment_scheduling_revision(db, settings)
    db.commit()


@router.post("/{epic_id}/archive", response_model=EpicOut)
def archive_epic(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicOut:
    settings = lock_owner_scheduling(db, user.id)
    epic = _get_owned_epic(db, epic_id, user)
    epic.is_archived = True
    increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(epic)
    return EpicOut.model_validate(epic)


@router.post("/{epic_id}/unarchive", response_model=EpicOut)
def unarchive_epic(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicOut:
    settings = lock_owner_scheduling(db, user.id)
    epic = _get_owned_epic(db, epic_id, user)
    epic.is_archived = False
    increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(epic)
    return EpicOut.model_validate(epic)


@router.post("/{epic_id}/demote-to-project", response_model=EpicDemoteToProjectOut)
def demote_epic_to_project_endpoint(
    epic_id: UUID,
    body: EpicDemoteToProjectBody | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EpicDemoteToProjectOut:
    """DEF-023: fold epic into a new project; orphan former child projects."""
    settings = lock_owner_scheduling(db, user.id)
    epic = _get_owned_epic(db, epic_id, user)
    payload = body or EpicDemoteToProjectBody()
    try:
        project, orphaned_ids = demote_epic_to_project(
            db,
            epic,
            user.id,
            target_epic_id=payload.target_epic_id,
        )
    except ApiError as exc:
        raise exc
    increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(project)
    return EpicDemoteToProjectOut(
        project=ProjectOut.model_validate(project),
        orphaned_project_ids=orphaned_ids,
    )
