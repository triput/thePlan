"""Keep provider identity when a mirrored calendar delete fails.

Horizon wipe and block delete must not turn our own mirror into anonymous busy.
The row stays with ``pending_deletion`` until a later sync deletes the remote
event or observes that it is already gone.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import CalendarAccount, ExternalCalendarEvent

logger = logging.getLogger(__name__)


def mark_block_mirrors_pending_deletion(db: Session, block_id: UUID) -> int:
    """Unlink this block's mirrors and retain provider / calendar / event ids."""
    rows = (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.scheduled_block_id == block_id)
        .all()
    )
    for row in rows:
        row.pending_deletion = True
        row.scheduled_block_id = None
    if rows:
        db.flush()
    return len(rows)


def retry_pending_deletions(
    db: Session,
    *,
    account: CalendarAccount,
    access: str,
    delete_event: Callable[[str, str, str], None],
) -> set[str]:
    """Retry remote deletes for this account's tombstones.

    Every returned external id must be skipped by the sync import that follows.
    That includes ids whose delete just succeeded: the pull payload was taken
    before the retry and would otherwise recreate the row as external busy.
    """
    rows = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.calendar_account_id == account.id,
            ExternalCalendarEvent.pending_deletion.is_(True),
        )
        .all()
    )
    suppressed: set[str] = set()
    for row in rows:
        suppressed.add(row.external_event_id)
        try:
            delete_event(access, row.calendar_id, row.external_event_id)
        except Exception:
            logger.exception(
                "Pending calendar mirror delete failed provider=%s calendar=%s event=%s",
                getattr(row.provider, "value", row.provider),
                row.calendar_id,
                row.external_event_id,
            )
            continue
        db.delete(row)
    if rows:
        db.flush()
    return suppressed
