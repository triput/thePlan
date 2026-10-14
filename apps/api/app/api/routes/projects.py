from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Project, User
from app.schemas import (
    EpicOut,
    PaginatedResponse,
    ProjectCreate,
    ProjectOut,
    ProjectPromoteToEpicOut,
    ProjectUpdate,
    ReorderRequest,
)
from app.services.hierarchy_promote import promote_project_to_epic
from app.services.ownership import verify_owned_epic, verify_owned_focus_window
from app.services.reorder import batch_reorder_sort_order
from app.services.scheduling_revision import (
    increment_scheduling_revision,
    lock_owner_scheduling,
    project_patch_touches_scheduling,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_owned_project(db: Session, project_id: UUID, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=PaginatedResponse)
def list_projects(
    epic_id: UUID | None = None,
    archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = db.query(Project).filter(Project.owner_id == user.id, Project.is_archived == archived)
    if epic_id is not None:
        query = query.filter(Project.epic_id == epic_id)
    total = query.count()
    items = query.order_by(Project.sort_order, Project.created_at).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[ProjectOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    if body.epic_id is not None:
        verify_owned_epic(db, body.epic_id, user)
    if body.preferred_time_window_id is not None:
        verify_owned_focus_window(db, body.preferred_time_window_id, user)
    settings = lock_owner_scheduling(db, user.id)
    project = Project(
        owner_id=user.id,
        title=body.title.strip(),
        description=body.description,
        epic_id=body.epic_id,
        color_hex=body.color_hex,
        preferred_time_window_id=body.preferred_time_window_id,
        schedule_style=body.schedule_style,
    )
    db.add(project)
    if body.preferred_time_window_id is not None or body.schedule_style is not None:
        increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_projects(
    body: ReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    batch_reorder_sort_order(
        db,
        Project,
        user.id,
        body.items,
        not_found_detail="Projects not found",
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = _get_owned_project(db, project_id, user)
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    updates = body.model_dump(exclude_unset=True)
    touches_scheduling = project_patch_touches_scheduling(updates)
    settings = lock_owner_scheduling(db, user.id) if touches_scheduling else None
    project = _get_owned_project(db, project_id, user)
    if "epic_id" in updates and updates["epic_id"] is not None:
        verify_owned_epic(db, updates["epic_id"], user)
    if "preferred_time_window_id" in updates:
        from app.services.scheduling_assignments import (
            assert_no_family_collision_for_legacy_write,
        )

        assert_no_family_collision_for_legacy_write(
            db,
            owner_id=user.id,
            scope="project",
            scope_id=project.id,
            new_preferred_time_window_id=updates["preferred_time_window_id"],
        )
        if updates["preferred_time_window_id"] is not None:
            verify_owned_focus_window(db, updates["preferred_time_window_id"], user)
    if "title" in updates and updates["title"] is not None:
        updates["title"] = updates["title"].strip()
    for field, value in updates.items():
        setattr(project, field, value)
    if touches_scheduling and settings is not None:
        increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    settings = lock_owner_scheduling(db, user.id)
    project = _get_owned_project(db, project_id, user)
    db.delete(project)
    increment_scheduling_revision(db, settings)
    db.commit()


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    settings = lock_owner_scheduling(db, user.id)
    project = _get_owned_project(db, project_id, user)
    project.is_archived = True
    increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/unarchive", response_model=ProjectOut)
def unarchive_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    settings = lock_owner_scheduling(db, user.id)
    project = _get_owned_project(db, project_id, user)
    project.is_archived = False
    increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/promote-to-epic", response_model=ProjectPromoteToEpicOut)
def promote_project_to_epic_endpoint(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectPromoteToEpicOut:
    """DEF-023: create epic from project meta; keep project UUID under the new epic."""
    settings = lock_owner_scheduling(db, user.id)
    project = _get_owned_project(db, project_id, user)
    epic, project = promote_project_to_epic(db, project, user.id)
    increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(epic)
    db.refresh(project)
    return ProjectPromoteToEpicOut(
        epic=EpicOut.model_validate(epic),
        project=ProjectOut.model_validate(project),
    )
