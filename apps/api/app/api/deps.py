from __future__ import annotations

import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.db import get_db
from app.models import User
from app.services.auth_users import get_user_by_id, is_setup_required

SESSION_USER_ID_KEY = "user_id"


def _parse_session_user_id(request: Request) -> uuid.UUID | None:
    raw = request.session.get(SESSION_USER_ID_KEY)
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


def set_session_user(request: Request, user_id: uuid.UUID) -> None:
    request.session[SESSION_USER_ID_KEY] = str(user_id)


def clear_session_user(request: Request) -> None:
    request.session.pop(SESSION_USER_ID_KEY, None)


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    user_id = _parse_session_user_id(request)
    if user_id is None:
        return None
    user = (
        db.query(User)
        .options(joinedload(User.settings))
        .filter(User.id == user_id)
        .one_or_none()
    )
    if user is None or user.is_disabled:
        return None
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    if is_setup_required(db):
        raise ApiError(401, "Initial setup required", "SETUP_REQUIRED")
    user = get_current_user_optional(request, db)
    if user is None:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise ApiError(403, "Admin access required", "FORBIDDEN")
    return user
