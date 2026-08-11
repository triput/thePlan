from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Epic, FocusWindow, Project, Section, User
from app.models.enums import TaskPriority
from app.schemas import QuickAddParseRequest, QuickAddParseResponse, RecurrenceOut
from app.services.auth_users import get_or_provision_user_settings
from app.services.quick_add import parse_quick_add

router = APIRouter(prefix="/quick-add", tags=["quick-add"])


def _resolve_epic_id(db: Session, user: User, name: str | None) -> tuple[UUID | None, list[str]]:
    if not name:
        return None, []
    epic = (
        db.query(Epic)
        .filter(Epic.owner_id == user.id, func.lower(Epic.title) == name.lower())
        .first()
    )
    if epic is None:
        return None, [f"epic:{name}"]
    return epic.id, []


def _resolve_project_section(
    db: Session,
    user: User,
    project_name: str | None,
    section_name: str | None,
) -> tuple[UUID | None, UUID | None, list[str]]:
    unresolved: list[str] = []
    if not project_name:
        return None, None, unresolved

    project = (
        db.query(Project)
        .filter(Project.owner_id == user.id, func.lower(Project.title) == project_name.lower())
        .first()
    )
    if project is None:
        unresolved.append(f"project:{project_name}")
        return None, None, unresolved

    if not section_name:
        return project.id, None, unresolved

    section = (
        db.query(Section)
        .filter(
            Section.owner_id == user.id,
            Section.project_id == project.id,
            func.lower(Section.title) == section_name.lower(),
        )
        .first()
    )
    if section is None:
        unresolved.append(f"section:{section_name}")
        return project.id, None, unresolved

    return project.id, section.id, unresolved


def _resolve_focus_window(
    db: Session,
    user: User,
    token: str | None,
) -> tuple[UUID | None, list[str]]:
    if not token:
        return None, []
    window = (
        db.query(FocusWindow)
        .filter(
            FocusWindow.owner_id == user.id,
            func.lower(FocusWindow.name) == token.lower(),
        )
        .first()
    )
    if window is None:
        return None, [f"time_window:{token}"]
    return window.id, []


@router.post("/parse", response_model=QuickAddParseResponse)
def parse_quick_add_input(
    body: QuickAddParseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuickAddParseResponse:
    timezone_name = user.settings.timezone if user.settings else "UTC"
    draft = parse_quick_add(body.text, timezone_name=timezone_name)

    needs_settings_commit = user.settings is None
    settings = get_or_provision_user_settings(db, user)
    if needs_settings_commit:
        db.commit()

    estimated_duration_minutes = draft.estimated_duration_minutes
    if estimated_duration_minutes is None:
        estimated_duration_minutes = settings.default_estimated_duration_minutes

    unresolved: list[str] = []
    epic_id, epic_unresolved = _resolve_epic_id(db, user, draft.epic_name)
    unresolved.extend(epic_unresolved)

    project_id, section_id, placement_unresolved = _resolve_project_section(
        db,
        user,
        draft.project_name,
        draft.section_name,
    )
    unresolved.extend(placement_unresolved)

    preferred_time_window_id, window_unresolved = _resolve_focus_window(
        db,
        user,
        draft.preferred_time_window,
    )
    unresolved.extend(window_unresolved)

    priority = draft.priority or TaskPriority.p4

    recurrence = None
    if draft.recurrence_rrule and draft.recurrence_display:
        recurrence = RecurrenceOut(
            rrule=draft.recurrence_rrule,
            is_fixed=draft.recurrence_is_fixed,
            timezone=draft.recurrence_timezone,
            starts_on=draft.recurrence_starts_on,
            ends_on=draft.recurrence_ends_on,
            display=draft.recurrence_display,
        )

    return QuickAddParseResponse(
        title=draft.title,
        priority=priority,
        estimated_duration_minutes=estimated_duration_minutes,
        due_at=draft.due_at,
        epic_id=epic_id,
        project_id=project_id,
        section_id=section_id,
        preferred_time_window_id=preferred_time_window_id,
        unresolved=unresolved,
        recurrence=recurrence,
    )
