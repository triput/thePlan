"""FastAPI session/auth dependencies — browser cookie + agent Bearer resolution.

API deps layer — shared by routes; not domain services.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.db import get_db
from app.models import User
from app.services.agent_auth_context import bind_session_agent_guard
from app.services.agent_credentials import (
    evaluate_agent_access,
    find_credential_by_secret,
    touch_last_used,
)
from app.services.auth_users import is_setup_required

SESSION_USER_ID_KEY = "user_id"
SESSION_EPOCH_KEY = "session_epoch"

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _parse_session_user_id(request: Request) -> uuid.UUID | None:
    raw = request.session.get(SESSION_USER_ID_KEY)
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


def _parse_session_epoch(request: Request) -> int | None:
    raw = request.session.get(SESSION_EPOCH_KEY)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def session_epoch_matches(request: Request, user: User) -> bool:
    epoch = _parse_session_epoch(request)
    return epoch is not None and epoch == user.session_epoch


def set_session_user(request: Request, user_id: uuid.UUID, *, session_epoch: int) -> None:
    """Store the signed session cookie payload: user id plus epoch."""
    request.session[SESSION_USER_ID_KEY] = str(user_id)
    request.session[SESSION_EPOCH_KEY] = int(session_epoch)


def clear_session_user(request: Request) -> None:
    request.session.clear()


def extract_bearer_token(request: Request) -> str | None:
    """Return Bearer token when Authorization header present (incl. empty/malformed).

    Presence of a Bearer scheme classifies the request as an agent-path attempt (§4.2).
    """
    header = request.headers.get("authorization")
    if header is None:
        return None
    parts = header.split(None, 1)
    if len(parts) == 0:
        return None
    if parts[0].lower() != "bearer":
        return None
    if len(parts) == 1:
        return ""
    return parts[1].strip()


def request_has_bearer(request: Request) -> bool:
    header = request.headers.get("authorization")
    if header is None:
        return False
    parts = header.split(None, 1)
    return bool(parts) and parts[0].lower() == "bearer"


def _resolve_browser_user(request: Request, db: Session) -> User | None:
    user_id = _parse_session_user_id(request)
    if user_id is None:
        return None
    user = (
        db.query(User)
        .options(joinedload(User.settings))
        .filter(User.id == user_id)
        .one_or_none()
    )
    if user is None or user.is_disabled or not session_epoch_matches(request, user):
        return None
    return user


def _resolve_agent_user(request: Request, db: Session, token: str) -> User:
    """Auth gate for agent path — fresh credential + setting + disabled checks."""
    credential = find_credential_by_secret(db, token)
    if credential is None:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    # Fresh committed-visibility gate (not a process-lifetime cache).
    evaluate_agent_access(db, credential_id=credential.id, use_committed_visibility=True)
    user = (
        db.query(User)
        .options(joinedload(User.settings))
        .filter(User.id == credential.owner_id)
        .one_or_none()
    )
    if user is None or user.is_disabled:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    request.state.auth_channel = "agent"
    request.state.agent_credential_id = credential.id
    # Object-local stamp on the request Session (survives sync threadpool).
    # Middleware already set ContextVar for side SessionLocal inheritance.
    if request.method in _MUTATING_METHODS:
        bind_session_agent_guard(db, credential.id)
    touch_last_used(credential.id)
    return user


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    if request_has_bearer(request):
        token = extract_bearer_token(request)
        if token is None:
            return None
        try:
            return _resolve_agent_user(request, db, token)
        except ApiError:
            return None
    return _resolve_browser_user(request, db)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    if is_setup_required(db):
        raise ApiError(401, "Initial setup required", "SETUP_REQUIRED")
    # §4.2: Bearer present → agent path only; never fall back to cookie.
    if request_has_bearer(request):
        token = extract_bearer_token(request) or ""
        return _resolve_agent_user(request, db, token)
    user = _resolve_browser_user(request, db)
    if user is None:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    request.state.auth_channel = "browser"
    return user


def get_browser_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Browser-session-only auth for credential admin / allow-setting toggle.

    Bearer present (any outcome) → reject mixed/cannot-admin; no cookie fallback admin.
    """
    if is_setup_required(db):
        raise ApiError(401, "Initial setup required", "SETUP_REQUIRED")
    if request_has_bearer(request):
        raise ApiError(
            403,
            "Agent credentials cannot administer agent access",
            "AGENT_CREDENTIAL_CANNOT_ADMIN",
        )
    user = _resolve_browser_user(request, db)
    if user is None:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    request.state.auth_channel = "browser"
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise ApiError(403, "Admin access required", "FORBIDDEN")
    return user
