"""User settings GET/PATCH."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import UserSettingsOut, UserSettingsUpdate
from app.services.auth_users import get_or_provision_user_settings
from app.services.scheduling_revision import (
    SETTINGS_SCHEDULING_FIELDS,
    increment_scheduling_revision,
    lock_owner_scheduling,
)

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
    touches_scheduling = bool(SETTINGS_SCHEDULING_FIELDS.intersection(updates))
    scheduling_settings = lock_owner_scheduling(db, user.id) if touches_scheduling else None
    settings = get_or_provision_user_settings(db, user)
    if "timezone" in updates and updates["timezone"] is not None:
        updates["timezone"] = updates["timezone"].strip()
    for field, value in updates.items():
        setattr(settings, field, value)
    if touches_scheduling and scheduling_settings is not None:
        increment_scheduling_revision(db, scheduling_settings)
    db.commit()
    db.refresh(settings)
    return UserSettingsOut.model_validate(settings)
