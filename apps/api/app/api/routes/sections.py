from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Project, Section, User
from app.schemas import PaginatedResponse, SectionCreate, SectionOut, SectionUpdate

router = APIRouter(prefix="/sections", tags=["sections"])


def _get_owned_section(db: Session, section_id: UUID, user: User) -> Section:
    section = db.get(Section, section_id)
    if section is None or section.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


@router.get("", response_model=PaginatedResponse)
def list_sections(
    project_id: UUID = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    query = db.query(Section).filter(Section.owner_id == user.id, Section.project_id == project_id)
    total = query.count()
    items = query.order_by(Section.sort_order, Section.created_at).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[SectionOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
def create_section(
    body: SectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SectionOut:
    project = db.get(Project, body.project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    section = Section(
        owner_id=user.id,
        project_id=body.project_id,
        title=body.title.strip(),
        sort_order=body.sort_order,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return SectionOut.model_validate(section)


@router.get("/{section_id}", response_model=SectionOut)
def get_section(
    section_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SectionOut:
    section = _get_owned_section(db, section_id, user)
    return SectionOut.model_validate(section)


@router.patch("/{section_id}", response_model=SectionOut)
def update_section(
    section_id: UUID,
    body: SectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SectionOut:
    section = _get_owned_section(db, section_id, user)
    updates = body.model_dump(exclude_unset=True)
    if "title" in updates and updates["title"] is not None:
        updates["title"] = updates["title"].strip()
    for field, value in updates.items():
        setattr(section, field, value)
    db.commit()
    db.refresh(section)
    return SectionOut.model_validate(section)


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(
    section_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    section = _get_owned_section(db, section_id, user)
    db.delete(section)
    db.commit()
