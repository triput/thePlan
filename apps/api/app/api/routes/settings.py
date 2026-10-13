# ==============================================================================
#  File: apps/api/app/api/routes/settings.py
#  Description: User settings GET/PATCH with duration field normalization.
#  Component: Scheduling / Settings
#  Version: 1.1
#  Created: 2026-10-01
#  Last Update: 2026-10-12
# ==============================================================================

"""User settings GET/PATCH."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import UserSettingsOut, UserSettingsUpdate
from app.services.auth_users import get_or_provision_user_settings
from app.services.duration_fields import resolve_minutes_field
from app.services.scheduling_revision import (
    SETTINGS_SCHEDULING_FIELDS,
    increment_scheduling_revision,
    lock_owner_scheduling,
)
from app.services.task_chunking_guard import reject_chunking_cutover_writes

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserSettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserSettingsOut:
    settings = get_or_provision_user_settings(db, user)
    if user.settings is None:
        db.commit()
        db.refresh(settings)
    return UserSettingsOut.model_validate(settings)


@router.patch("", response_model=UserSettingsOut)
def update_settings(
    body: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserSettingsOut:
    updates = body.model_dump(exclude_unset=True)
    reject_chunking_cutover_writes(updates)
    duration_conversion_note: str | None = None
    settings = get_or_provision_user_settings(db, user)
    # Resolve requested nominal first (int or string) so same-request workday
    # conversion of default_estimated_duration_minutes uses the new value (S1-D8).
    nominal = settings.nominal_workday_minutes
    if "nominal_workday_minutes" in updates:
        parsed = resolve_minutes_field(
            updates["nominal_workday_minutes"],
            field_label="nominal_workday_minutes",
            nominal_workday_minutes=None,
            allow_workdays=False,
            allow_zero=False,
            required=True,
        )
        assert parsed is not None
        updates["nominal_workday_minutes"] = parsed.minutes
        duration_conversion_note = parsed.conversion_note
        nominal = parsed.minutes
    if "default_estimated_duration_minutes" in updates:
        parsed = resolve_minutes_field(
            updates["default_estimated_duration_minutes"],
            field_label="default_estimated_duration_minutes",
            nominal_workday_minutes=nominal,
            allow_workdays=True,
            allow_zero=False,
            required=True,
        )
        assert parsed is not None
        updates["default_estimated_duration_minutes"] = parsed.minutes
        duration_conversion_note = duration_conversion_note or parsed.conversion_note
    touches_scheduling = bool(SETTINGS_SCHEDULING_FIELDS.intersection(updates))
    scheduling_settings = lock_owner_scheduling(db, user.id) if touches_scheduling else None
    if "timezone" in updates and updates["timezone"] is not None:
        updates["timezone"] = updates["timezone"].strip()
    for field, value in updates.items():
        setattr(settings, field, value)
    if touches_scheduling and scheduling_settings is not None:
        increment_scheduling_revision(db, scheduling_settings)
    db.commit()
    db.refresh(settings)
    out = UserSettingsOut.model_validate(settings)
    return out.model_copy(update={"duration_conversion_note": duration_conversion_note})
