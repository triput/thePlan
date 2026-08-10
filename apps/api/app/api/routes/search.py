from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.routes.tasks import task_to_out
from app.db import get_db
from app.models import Task, TaskLabel, User
from app.schemas import PaginatedResponse, SearchLabelOut, SearchTaskOut

router = APIRouter(prefix="/search", tags=["search"])


def escape_ilike(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_task_to_out(task: Task, db: Session) -> SearchTaskOut:
    base = task_to_out(task, db)
    labels = [
        SearchLabelOut(id=link.label.id, name=link.label.name, color_hex=link.label.color_hex)
        for link in task.label_links
    ]
    return SearchTaskOut(
        **base.model_dump(),
        project_title=task.project.title if task.project is not None else None,
        labels=labels,
    )


@router.get("", response_model=PaginatedResponse)
def search_tasks(
    q: str = Query(...),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query_text = q.strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query cannot be empty",
        )

    pattern = f"%{escape_ilike(query_text)}%"
    base_query = (
        db.query(Task)
        .options(
            joinedload(Task.project),
            joinedload(Task.label_links).joinedload(TaskLabel.label),
        )
        .filter(
            Task.owner_id == user.id,
            or_(
                Task.title.ilike(pattern, escape="\\"),
                Task.description.ilike(pattern, escape="\\"),
            ),
        )
    )
    total = base_query.count()
    items = base_query.order_by(Task.updated_at.desc()).limit(limit).all()
    return PaginatedResponse(
        items=[search_task_to_out(item, db) for item in items],
        total=total,
        limit=limit,
        offset=0,
    )
