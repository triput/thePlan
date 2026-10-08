"""Horizon computation and unpinned block wipe for Update Schedule."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import ExternalCalendarEvent, ScheduledBlock, UserSettings
from app.services import google_calendar, microsoft_calendar

logger = logging.getLogger(__name__)


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


def _drop_mirrored_events(db: Session, settings: Settings, block: ScheduledBlock) -> None:
    """Cancel provider mirrors, then drop local rows so they cannot become external busy.

    Remote delete is synchronous via the calendar services. If a provider call fails,
    the local ExternalCalendarEvent is still removed before the block row goes away.
    Otherwise ON DELETE SET NULL clears scheduled_block_id and busy_map treats the
    leftover mirror as someone else's event.
    """
    for deleter in (
        google_calendar.delete_mirrored_block,
        microsoft_calendar.delete_mirrored_block,
    ):
        try:
            deleter(db, settings, block)
        except Exception:
            logger.exception(
                "Failed to delete mirrored calendar event for block %s",
                block.id,
            )

    leftovers = (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
        .all()
    )
    for row in leftovers:
        db.delete(row)
    if leftovers:
        db.flush()


def wipe_unpinned_blocks_in_horizon(
    db: Session,
    owner_id: UUID,
    horizon_start: datetime,
    horizon_end: datetime,
) -> int:
    """Delete unpinned blocks intersecting [horizon_start, horizon_end). Returns count deleted.

    Provider-mirrored events for those blocks are cancelled (Google and Microsoft)
    and their local ExternalCalendarEvent rows are removed. Pinned blocks and
    genuinely external events are left alone.
    """
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
    if not count:
        return 0

    settings = get_settings()
    for block in blocks:
        _drop_mirrored_events(db, settings, block)
        db.delete(block)
    db.flush()
    return count
