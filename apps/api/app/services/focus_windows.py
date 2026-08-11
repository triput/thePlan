from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy.orm import Session

from app.models import FocusWindow

DEFAULT_FOCUS_WINDOWS: tuple[tuple[str, time, time], ...] = (
    ("Morning", time(8, 0), time(12, 0)),
    ("Afternoon", time(12, 0), time(17, 0)),
    ("Evening", time(17, 0), time(21, 0)),
)

ALL_DAYS_BITSET = 127


def ensure_default_focus_windows(db: Session, user_id: uuid.UUID) -> list[FocusWindow]:
    """Insert Morning/Afternoon/Evening when the user has no focus windows."""
    existing = (
        db.query(FocusWindow.id).filter(FocusWindow.owner_id == user_id).limit(1).first()
    )
    if existing is not None:
        return []

    created: list[FocusWindow] = []
    for name, start_time, end_time in DEFAULT_FOCUS_WINDOWS:
        window = FocusWindow(
            owner_id=user_id,
            name=name,
            start_time=start_time,
            end_time=end_time,
            days_of_week=ALL_DAYS_BITSET,
            is_hard=False,
        )
        db.add(window)
        created.append(window)
    db.flush()
    return created
