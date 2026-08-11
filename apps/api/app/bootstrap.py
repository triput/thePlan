import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SavedFilter, User, UserSettings
from app.services.focus_windows import ensure_default_focus_windows

BOOTSTRAP_USER_ID = uuid.UUID(get_settings().bootstrap_user_id)

INBOX_PREDICATE: dict[str, Any] = {
    "op": "and",
    "clauses": [
        {"field": "project_id", "op": "is_null"},
        {"field": "is_completed", "op": "eq", "value": False},
    ],
}

TODAY_PREDICATE: dict[str, Any] = {
    "op": "and",
    "clauses": [
        {"field": "due_at", "op": "is_today"},
        {"field": "is_completed", "op": "eq", "value": False},
    ],
}

UPCOMING_PREDICATE: dict[str, Any] = {
    "op": "and",
    "clauses": [
        {"field": "due_at", "op": "within_days", "value": 7},
        {"field": "is_completed", "op": "eq", "value": False},
    ],
}

SYSTEM_FILTERS = [
    ("Inbox", "inbox", INBOX_PREDICATE, 1),
    ("Today", "today", TODAY_PREDICATE, 2),
    ("Upcoming", "upcoming", UPCOMING_PREDICATE, 3),
]


def ensure_bootstrap_user(db: Session, *, commit: bool = True) -> User:
    settings = get_settings()
    user = db.get(User, BOOTSTRAP_USER_ID)
    if user is None:
        user = User(
            id=BOOTSTRAP_USER_ID,
            email=settings.bootstrap_user_email,
            display_name=settings.bootstrap_user_display_name,
        )
        db.add(user)
        db.flush()

    if user is None:
        raise RuntimeError("Bootstrap user missing and could not be created")

    if user.settings is None:
        db.add(UserSettings(owner_id=user.id))

    existing_slugs = {
        slug
        for (slug,) in db.query(SavedFilter.slug).filter(SavedFilter.owner_id == user.id).all()
    }
    for name, slug, predicate, sort_order in SYSTEM_FILTERS:
        if slug not in existing_slugs:
            db.add(
                SavedFilter(
                    owner_id=user.id,
                    name=name,
                    slug=slug,
                    predicate_json=predicate,
                    is_system=True,
                    sort_order=sort_order,
                )
            )

    ensure_default_focus_windows(db, user.id)

    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user
