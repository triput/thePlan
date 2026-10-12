"""Fresh-account availability seed. Not an HTTP surface.

Existing owners are seeded in Alembic ``028_availability_progress`` from
``user_settings`` (and that SQL is frozen). This helper is the new-account
path: Working and General are independent Mon–Fri 09:00–17:00 copies, Personal
is a named policy with zero windows. It does not read ``workday_start_local``
(legacy default 08:00) and does not write blocks or ``scheduling_revision``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.availability import AvailabilityPolicy, AvailabilityWindow
from app.models.enums import AvailabilityPolicySlug

# Monday = 0, matching date.weekday() and workweek_days.
FRESH_WEEKDAYS: tuple[int, ...] = (0, 1, 2, 3, 4)
FRESH_START_LOCAL: time = time(9, 0)
FRESH_DURATION_MINUTES: int = 480

# (slug, display name, sort_order, seed windows)
_FRESH_POLICIES: tuple[tuple[AvailabilityPolicySlug, str, int, bool], ...] = (
    (AvailabilityPolicySlug.general, "General", 0, True),
    (AvailabilityPolicySlug.work, "Working", 1, True),
    (AvailabilityPolicySlug.personal, "Personal", 2, False),
)


def derive_window_end(start: time, duration_minutes: int) -> tuple[time, bool]:
    """Return ``(end_clock, ends_next_day)`` for a half-open window.

    ``ends_next_day`` is true when ``start + duration`` reaches or passes the
    next midnight (24h included). Matches the 028 check:
    ``EXTRACT(EPOCH FROM start_time) + duration_minutes * 60 >= 86400``.
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    anchor = datetime(
        2000,
        1,
        1,
        start.hour,
        start.minute,
        start.second,
        start.microsecond,
    )
    end = anchor + timedelta(minutes=duration_minutes)
    return end.time(), end.date() > anchor.date()


def ensure_default_availability_policies(
    db: Session, owner_id: uuid.UUID
) -> list[AvailabilityPolicy]:
    """Insert General, Working, and empty Personal when the owner has none.

    Returns the rows created. A no-op (empty list) when any policy already
    exists, including policies seeded by migration 028.
    """
    existing = (
        db.query(AvailabilityPolicy.id)
        .filter(AvailabilityPolicy.owner_id == owner_id)
        .limit(1)
        .first()
    )
    if existing is not None:
        return []

    end_time, ends_next_day = derive_window_end(FRESH_START_LOCAL, FRESH_DURATION_MINUTES)
    created: list[AvailabilityPolicy] = []
    for slug, name, sort_order, with_windows in _FRESH_POLICIES:
        policy = AvailabilityPolicy(
            owner_id=owner_id,
            slug=slug,
            name=name,
            sort_order=sort_order,
        )
        if with_windows:
            for weekday in FRESH_WEEKDAYS:
                policy.windows.append(
                    AvailabilityWindow(
                        owner_id=owner_id,
                        weekday=weekday,
                        start_time=FRESH_START_LOCAL,
                        end_time=end_time,
                        ends_next_day=ends_next_day,
                        duration_minutes=FRESH_DURATION_MINUTES,
                        sort_order=0,
                    )
                )
        db.add(policy)
        created.append(policy)
    db.flush()
    return created
