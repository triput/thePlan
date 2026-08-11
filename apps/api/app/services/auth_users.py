from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.bootstrap import BOOTSTRAP_USER_ID, SYSTEM_FILTERS
from app.models import SavedFilter, User, UserSettings
from app.services.focus_windows import ensure_default_focus_windows
from app.services.passwords import hash_password

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$|^[a-z0-9]$")
PASSWORD_MIN_LEN = 12
PASSWORD_MAX_LEN = 128


def normalize_username(raw: str) -> str:
    username = raw.strip().lower()
    if not username or len(username) > 64:
        raise ApiError(422, "Username must be 1–64 characters", "INVALID_USERNAME")
    if not USERNAME_RE.match(username):
        raise ApiError(
            422,
            "Username may use lowercase letters, digits, dots, hyphens, and underscores",
            "INVALID_USERNAME",
        )
    return username


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if not email or len(email) > 255:
        raise ApiError(422, "Invalid email address", "INVALID_EMAIL")
    return email


def validate_password(password: str) -> None:
    if len(password) < PASSWORD_MIN_LEN or len(password) > PASSWORD_MAX_LEN:
        raise ApiError(
            422,
            f"Password must be {PASSWORD_MIN_LEN}–{PASSWORD_MAX_LEN} characters",
            "INVALID_PASSWORD",
        )


def is_setup_required(db: Session) -> bool:
    return (
        db.query(User.id)
        .filter(User.password_hash.isnot(None))
        .limit(1)
        .one_or_none()
        is None
    )


def provision_user_settings_and_filters(db: Session, user_id: uuid.UUID) -> None:
    existing_settings = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == user_id)
        .one_or_none()
    )
    if existing_settings is None:
        db.add(UserSettings(owner_id=user_id))

    existing_slugs = {
        slug
        for (slug,) in db.query(SavedFilter.slug).filter(SavedFilter.owner_id == user_id).all()
    }
    for name, slug, predicate, sort_order in SYSTEM_FILTERS:
        if slug not in existing_slugs:
            db.add(
                SavedFilter(
                    owner_id=user_id,
                    name=name,
                    slug=slug,
                    predicate_json=predicate,
                    is_system=True,
                    sort_order=sort_order,
                )
            )

    ensure_default_focus_windows(db, user_id)


def claim_bootstrap_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    if not is_setup_required(db):
        raise ApiError(403, "Setup already completed", "SETUP_COMPLETE")

    user = db.get(User, BOOTSTRAP_USER_ID)
    if user is None:
        raise ApiError(500, "Bootstrap user missing", "BOOTSTRAP_MISSING")

    norm_username = normalize_username(username)
    norm_email = normalize_email(email)
    validate_password(password)

    if db.query(User.id).filter(User.username == norm_username, User.id != user.id).first():
        raise ApiError(409, "Username already taken", "USERNAME_TAKEN")
    if db.query(User.id).filter(User.email == norm_email, User.id != user.id).first():
        raise ApiError(409, "Email already taken", "EMAIL_TAKEN")

    user.username = norm_username
    user.email = norm_email
    user.password_hash = hash_password(password)
    user.display_name = (display_name or norm_username).strip() or norm_username
    user.is_admin = True
    user.is_disabled = False

    provision_user_settings_and_filters(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def create_household_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    display_name: str | None = None,
    is_admin: bool = False,
) -> User:
    if is_setup_required(db):
        raise ApiError(403, "Complete initial setup first", "SETUP_REQUIRED")

    norm_username = normalize_username(username)
    norm_email = normalize_email(email)
    validate_password(password)

    if db.query(User.id).filter(User.username == norm_username).first():
        raise ApiError(409, "Username already taken", "USERNAME_TAKEN")
    if db.query(User.id).filter(User.email == norm_email).first():
        raise ApiError(409, "Email already taken", "EMAIL_TAKEN")

    user = User(
        username=norm_username,
        email=norm_email,
        password_hash=hash_password(password),
        display_name=(display_name or norm_username).strip() or norm_username,
        is_admin=is_admin,
        is_disabled=False,
    )
    db.add(user)
    db.flush()
    provision_user_settings_and_filters(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, identifier: str, password: str) -> User | None:
    ident = identifier.strip().lower()
    user = (
        db.query(User)
        .filter((User.username == ident) | (User.email == ident))
        .one_or_none()
    )
    if user is None or user.is_disabled or user.password_hash is None:
        return None
    from app.services.passwords import verify_password

    if not verify_password(password, user.password_hash):
        return None
    return user


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)
