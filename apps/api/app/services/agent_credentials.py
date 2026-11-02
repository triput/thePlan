"""Agent/CLI Bearer credentials — create, verify, revoke (hash/verifier only)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db import SessionLocal
from app.models import AgentCredential, User, UserSettings
from app.services.passwords import hash_password, verify_password

SECRET_PREFIX = "tp_agent_"
_LABEL_MAX = 100


def _compose_secret(credential_id: uuid.UUID, random_part: str) -> str:
    return f"{SECRET_PREFIX}{credential_id.hex}_{random_part}"


def parse_secret_credential_id(plain: str) -> uuid.UUID | None:
    if not plain or not plain.startswith(SECRET_PREFIX):
        return None
    rest = plain[len(SECRET_PREFIX) :]
    if "_" not in rest:
        return None
    id_hex, _sep, _rand = rest.partition("_")
    if len(id_hex) != 32:
        return None
    try:
        return uuid.UUID(hex=id_hex)
    except ValueError:
        return None


def create_agent_credential(
    db: Session,
    user: User,
    *,
    label: str,
) -> tuple[AgentCredential, str]:
    settings = _require_settings(db, user)
    if not settings.allow_agent_cli_access:
        raise ApiError(403, "Agent and CLI access is disabled", "AGENT_ACCESS_DISABLED")
    cleaned = (label or "").strip()
    if not cleaned or len(cleaned) > _LABEL_MAX:
        raise ApiError(422, f"Label must be 1–{_LABEL_MAX} characters", "INVALID_LABEL")

    credential_id = uuid.uuid4()
    random_part = secrets.token_urlsafe(32)
    plain = _compose_secret(credential_id, random_part)
    row = AgentCredential(
        id=credential_id,
        owner_id=user.id,
        label=cleaned,
        secret_hash=hash_password(plain),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, plain


def list_agent_credentials(db: Session, user: User) -> list[AgentCredential]:
    return (
        db.query(AgentCredential)
        .filter(AgentCredential.owner_id == user.id)
        .order_by(AgentCredential.created_at.desc())
        .all()
    )


def revoke_agent_credential(db: Session, user: User, credential_id: uuid.UUID) -> AgentCredential:
    row = (
        db.query(AgentCredential)
        .filter(AgentCredential.id == credential_id, AgentCredential.owner_id == user.id)
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "Agent credential not found", "AGENT_CREDENTIAL_NOT_FOUND")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return row


def find_credential_by_secret(db: Session, plain: str) -> AgentCredential | None:
    """Resolve Bearer secret → row. Unknown/malformed → None (UNAUTHENTICATED)."""
    credential_id = parse_secret_credential_id(plain)
    if credential_id is None:
        return None
    row = db.get(AgentCredential, credential_id)
    if row is None:
        return None
    if not verify_password(plain, row.secret_hash):
        return None
    return row


def touch_last_used(credential_id: uuid.UUID) -> None:
    """Best-effort last_used_at on a short-lived side session (reads may not commit)."""
    db = SessionLocal()
    try:
        db.execute(
            text(
                "UPDATE agent_credentials SET last_used_at = NOW() "
                "WHERE id = :id AND revoked_at IS NULL"
            ),
            {"id": credential_id},
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def evaluate_agent_access(
    db: Session,
    *,
    credential_id: uuid.UUID,
    use_committed_visibility: bool = False,
) -> uuid.UUID:
    """Raise per §3.6 precedence. Returns owner_id when authorized.

    use_committed_visibility: raw SQL so other sessions' committed revoke/disable
    are visible (Boundary A final check — not ORM identity-map stale).
    """
    if use_committed_visibility:
        row = db.execute(
            text(
                "SELECT revoked_at IS NOT NULL AS revoked, owner_id "
                "FROM agent_credentials WHERE id = :id"
            ),
            {"id": credential_id},
        ).one_or_none()
        if row is None:
            raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
        revoked, owner_id = bool(row[0]), row[1]
        flags = db.execute(
            text(
                "SELECT u.is_disabled, COALESCE(s.allow_agent_cli_access, false) "
                "FROM users u "
                "LEFT JOIN user_settings s ON s.owner_id = u.id "
                "WHERE u.id = :uid"
            ),
            {"uid": owner_id},
        ).one_or_none()
        if flags is None:
            raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
        is_disabled, allow = bool(flags[0]), bool(flags[1])
    else:
        credential = db.get(AgentCredential, credential_id)
        if credential is None:
            raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
        revoked = credential.revoked_at is not None
        owner_id = credential.owner_id
        user = db.get(User, owner_id)
        if user is None:
            raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
        is_disabled = bool(user.is_disabled)
        settings = (
            db.query(UserSettings)
            .filter(UserSettings.owner_id == user.id)
            .one_or_none()
        )
        allow = bool(settings.allow_agent_cli_access) if settings is not None else False

    if revoked:
        raise ApiError(403, "Agent credential has been revoked", "AGENT_CREDENTIAL_REVOKED")
    if not allow:
        raise ApiError(403, "Agent and CLI access is disabled", "AGENT_ACCESS_DISABLED")
    if is_disabled:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    return owner_id


def assert_agent_write_still_authorized(db: Session, credential_id: uuid.UUID) -> None:
    """Boundary A final fresh check immediately before durable write commit."""
    evaluate_agent_access(db, credential_id=credential_id, use_committed_visibility=True)


def _require_settings(db: Session, user: User) -> UserSettings:
    from app.services.auth_users import get_or_provision_user_settings

    return get_or_provision_user_settings(db, user)
