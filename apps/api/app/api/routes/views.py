# ==============================================================================
#  File: apps/api/app/api/routes/views.py
#  Description: Saved views CRUD and predicate-backed task query HTTP routes (F7).
#  Component: Saved Views
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations

import re
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.api.routes.tasks import task_to_out
from app.db import get_db
from app.models import Plan, SavedFilter, Task, User
from app.schemas import (
    SavedViewCreate,
    SavedViewOut,
    SavedViewTasksResponse,
    SavedViewUpdate,
)
from app.services.auth_users import get_or_provision_user_settings
from app.services.saved_filter_predicate import validate_predicate
from app.services.saved_filter_query import (
    apply_default_task_visibility,
    apply_predicate_to_query,
)
from app.services.saved_view_presentation import (
    merge_presentation,
    resolve_task_sort,
    task_order_by,
    validate_presentation,
)

router = APIRouter(prefix="/views", tags=["views"])

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?$")


def _slugify_name(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return (base[:100] if base else "view") or "view"


def _normalize_slug(raw: str) -> str:
    slug = raw.strip().lower()
    if not slug or len(slug) > 100 or not _SLUG_RE.match(slug):
        raise ApiError(422, "Invalid slug", "INVALID_SLUG")
    return slug


def _get_owned_view(db: Session, view_id: UUID, user: User) -> SavedFilter:
    row = db.query(SavedFilter).filter(SavedFilter.id == view_id).one_or_none()
    if row is None or row.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found")
    return row


def _get_owned_view_by_slug(db: Session, slug: str, user: User) -> SavedFilter:
    row = (
        db.query(SavedFilter)
        .filter(SavedFilter.owner_id == user.id, SavedFilter.slug == slug)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found")
    return row


def _reject_system_mutation(view: SavedFilter) -> None:
    if view.is_system:
        raise ApiError(403, "System views cannot be modified", "SYSTEM_VIEW_READ_ONLY")


def _ensure_unique_slug(db: Session, owner_id: uuid.UUID, slug: str, *, exclude_id: UUID | None) -> None:
    query = db.query(SavedFilter.id).filter(SavedFilter.owner_id == owner_id, SavedFilter.slug == slug)
    if exclude_id is not None:
        query = query.filter(SavedFilter.id != exclude_id)
    if query.limit(1).one_or_none() is not None:
        raise ApiError(422, "Slug already in use", "DUPLICATE_SLUG")


def _view_to_out(row: SavedFilter) -> SavedViewOut:
    return SavedViewOut.model_validate(row)


def _query_view_tasks(
    db: Session,
    user: User,
    view: SavedFilter,
    *,
    limit: int,
    offset: int,
    board_order: bool,
    sort: str | None = None,
) -> SavedViewTasksResponse:
    settings = get_or_provision_user_settings(db, user)
    predicate = validate_predicate(view.predicate_json)
    dims = predicate.get("dimensions") or {}
    explicit_project = bool(dims.get("project_ids") or dims.get("epic_ids"))

    query = (
        db.query(Task)
        .options(joinedload(Task.recurrence_rule), joinedload(Task.label_links))
        .filter(Task.owner_id == user.id)
    )
    query = apply_default_task_visibility(query, explicit_project_filter=explicit_project)
    applied = apply_predicate_to_query(
        query,
        db,
        user.id,
        predicate,
        timezone_name=settings.timezone,
        upcoming_horizon_days=settings.upcoming_horizon_days,
    )

    invalid_refs = applied.invalid_references or None
    if applied.unsatisfiable:
        return SavedViewTasksResponse(
            items=[],
            total=0,
            limit=limit,
            offset=offset,
            invalid_references=invalid_refs,
        )

    query = applied.query
    total = query.count()
    if board_order:
        # Board columns use board_rank; presentation_json.sort is ignored here.
        order = (Task.board_rank, Task.created_at)
    else:
        sort_key = resolve_task_sort(query_sort=sort, presentation=view.presentation_json)
        order = task_order_by(sort_key)
    rows = query.order_by(*order).offset(offset).limit(limit).all()
    plan_ids = {item.plan_id for item in rows if item.plan_id is not None}
    plan_names: dict[UUID, str] = {}
    if plan_ids:
        plan_names = {
            row.id: row.name
            for row in db.query(Plan).filter(Plan.owner_id == user.id, Plan.id.in_(plan_ids)).all()
        }
    return SavedViewTasksResponse(
        items=[task_to_out(item, db, plan_names=plan_names) for item in rows],
        total=total,
        limit=limit,
        offset=offset,
        invalid_references=invalid_refs,
    )


@router.get("", response_model=list[SavedViewOut])
def list_views(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SavedViewOut]:
    get_or_provision_user_settings(db, user)
    rows = (
        db.query(SavedFilter)
        .filter(SavedFilter.owner_id == user.id)
        .order_by(SavedFilter.is_system.desc(), SavedFilter.sort_order, SavedFilter.name)
        .all()
    )
    return [_view_to_out(row) for row in rows]


@router.post("", response_model=SavedViewOut, status_code=status.HTTP_201_CREATED)
def create_view(
    body: SavedViewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedViewOut:
    predicate = validate_predicate(body.predicate_json)
    slug = _normalize_slug(body.slug) if body.slug else _slugify_name(body.name)
    _ensure_unique_slug(db, user.id, slug, exclude_id=None)
    presentation = validate_presentation(body.presentation_json if body.presentation_json is not None else {})
    row = SavedFilter(
        owner_id=user.id,
        name=body.name.strip(),
        slug=slug,
        predicate_json=predicate,
        presentation_json=presentation,
        is_system=False,
        sort_order=body.sort_order if body.sort_order is not None else 100,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _view_to_out(row)


@router.get("/by-slug/{slug}/tasks", response_model=SavedViewTasksResponse)
def list_view_tasks_by_slug(
    slug: str,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    board_order: bool = Query(
        default=False,
        description="When true, order by board_rank then created_at.",
    ),
    sort: str | None = Query(
        default=None,
        description="Optional allowlisted sort key; overrides presentation_json.sort.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedViewTasksResponse:
    view = _get_owned_view_by_slug(db, _normalize_slug(slug), user)
    return _query_view_tasks(
        db, user, view, limit=limit, offset=offset, board_order=board_order, sort=sort
    )


@router.get("/{view_id}", response_model=SavedViewOut)
def get_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedViewOut:
    return _view_to_out(_get_owned_view(db, view_id, user))


@router.patch("/{view_id}", response_model=SavedViewOut)
def update_view(
    view_id: UUID,
    body: SavedViewUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedViewOut:
    row = _get_owned_view(db, view_id, user)
    _reject_system_mutation(row)
    updates = body.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] is not None:
        row.name = updates["name"].strip()
    if "slug" in updates and updates["slug"] is not None:
        slug = _normalize_slug(updates["slug"])
        _ensure_unique_slug(db, user.id, slug, exclude_id=row.id)
        row.slug = slug
    if "predicate_json" in updates and updates["predicate_json"] is not None:
        row.predicate_json = validate_predicate(updates["predicate_json"])
    if "presentation_json" in updates and updates["presentation_json"] is not None:
        row.presentation_json = merge_presentation(row.presentation_json or {}, updates["presentation_json"])
    if "sort_order" in updates and updates["sort_order"] is not None:
        row.sort_order = updates["sort_order"]

    db.commit()
    db.refresh(row)
    return _view_to_out(row)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    row = _get_owned_view(db, view_id, user)
    _reject_system_mutation(row)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{view_id}/tasks", response_model=SavedViewTasksResponse)
def list_view_tasks(
    view_id: UUID,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    board_order: bool = Query(
        default=False,
        description="When true, order by board_rank then created_at.",
    ),
    sort: str | None = Query(
        default=None,
        description="Optional allowlisted sort key; overrides presentation_json.sort.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedViewTasksResponse:
    view = _get_owned_view(db, view_id, user)
    return _query_view_tasks(
        db, user, view, limit=limit, offset=offset, board_order=board_order, sort=sort
    )
