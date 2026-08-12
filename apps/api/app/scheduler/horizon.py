"""Horizon computation and unpinned block wipe for Update Schedule."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import ScheduledBlock, UserSettings


def compute_horizon(
    settings: UserSettings,
    now_utc: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return [start, end) horizon bounds in UTC; start is now in user TZ."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    tz = ZoneInfo(settings.timezone)
    start_local = now_utc.astimezone(tz)
    end_local = start_local + timedelta(days=settings.upcoming_horizon_days)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def wipe_unpinned_blocks_in_horizon(
    db: Session,
    owner_id: UUID,
    horizon_start: datetime,
    horizon_end: datetime,
) -> int:
    """Delete unpinned blocks intersecting [horizon_start, horizon_end). Returns count deleted."""
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.is_pinned.is_(False),
            ScheduledBlock.start_time < horizon_end,
            ScheduledBlock.end_time > horizon_start,
        )
        .all()
    )
    count = len(blocks)
    for block in blocks:
        db.delete(block)
    if count:
        db.flush()
    return count
