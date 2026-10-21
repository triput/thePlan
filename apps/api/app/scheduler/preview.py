# ==============================================================================
#  File: apps/api/app/scheduler/preview.py
#  Description: F6 replan preview worker — B-auto orchestration outside calculate.
#  Component: Replan Preview
#  Version: 1.2
#  Created: 2026-10-09
#  Last Update: 2026-10-21
# ==============================================================================

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import SchedulePreview
from app.scheduler.calendar_freshness import CalendarFreshnessError
from app.scheduler.free_busy import BusyInputTrustError
from app.scheduler.preview_orchestration import run_preview_orchestration

logger = logging.getLogger(__name__)

PREVIEW_TTL_MINUTES = 15


def _preview_expires(evaluated_at: datetime) -> datetime:
    return evaluated_at + timedelta(minutes=PREVIEW_TTL_MINUTES)


def _terminal_fail(
    db: Session,
    preview_id: UUID,
    *,
    error_message: str,
    stats_json: dict[str, Any] | None = None,
) -> None:
    """Lock + populate_existing runnable recheck before terminal failed write."""
    preview = (
        db.query(SchedulePreview)
        .filter(SchedulePreview.id == preview_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if preview is None or preview.status != "running" or preview.finished_at is not None:
        return
    preview.status = "failed"
    preview.error_message = error_message
    preview.finished_at = datetime.now(timezone.utc)
    preview.expires_at = None
    preview.proposal_json = None
    if stats_json is not None:
        preview.stats_json = stats_json
    db.commit()


def run_preview(preview_id: UUID, db: Session | None = None) -> None:
    """Calculate and persist a preview proposal. Never calls apply."""
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        run_preview_orchestration(db, preview_id)
    except BusyInputTrustError as exc:
        logger.warning("Schedule preview %s blocked by BusyInputTrust", preview_id)
        db.rollback()
        _terminal_fail(
            db,
            preview_id,
            error_message=str(exc),
            stats_json={"busy_input_trust": exc.trust.to_dict()},
        )
    except CalendarFreshnessError as exc:
        logger.warning("Schedule preview %s blocked by CalendarFreshness", preview_id)
        db.rollback()
        _terminal_fail(
            db,
            preview_id,
            error_message=str(exc),
            stats_json={"calendar_freshness_trust": exc.trust.to_dict()},
        )
    except Exception as exc:
        logger.exception("Schedule preview %s failed", preview_id)
        db.rollback()
        _terminal_fail(db, preview_id, error_message=str(exc))
    finally:
        if owns_session:
            db.close()
