"""User settings GET/PATCH."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import UserSettingsOut, UserSettingsUpdate
from app.services.auth_users import get_or_provision_user_settings

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
    settings = get_or_provision_user_settings(db, user)
    updates = body.model_dump(exclude_unset=True)
    if "timezone" in updates and updates["timezone"] is not None:
        updates["timezone"] = updates["timezone"].strip()
    for field, value in updates.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return UserSettingsOut.model_validate(settings)
