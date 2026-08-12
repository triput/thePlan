"""Dispatch and stale-run reclaim for Update Schedule."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ScheduleRun
from app.scheduler.replan import run_replan

logger = logging.getLogger(__name__)

STALE_RUN_MINUTES = 15


def reclaim_stale_runs(db: Session, owner_id: UUID) -> int:
    """Mark owner running runs older than STALE_RUN_MINUTES as failed."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_RUN_MINUTES)
    stale = (
        db.query(ScheduleRun)
        .filter(
            ScheduleRun.owner_id == owner_id,
            ScheduleRun.status == "running",
            ScheduleRun.started_at < cutoff,
        )
        .all()
    )
    for run in stale:
        run.status = "failed"
        run.error_message = "stale run reclaimed"
        run.finished_at = datetime.now(timezone.utc)
    if stale:
        db.flush()
    return len(stale)


def has_running_run(db: Session, owner_id: UUID) -> bool:
    return (
        db.query(ScheduleRun.id)
        .filter(
            ScheduleRun.owner_id == owner_id,
            ScheduleRun.status == "running",
        )
        .first()
        is not None
    )


def dispatch_replan(run_id: UUID, *, sync: bool = False) -> None:
    """Dispatch replan work; inline when sync=True (tests)."""
    if sync:
        run_replan(run_id)
        return

    def _worker() -> None:
        try:
            run_replan(run_id)
        except Exception:
            logger.exception("Background replan failed for run %s", run_id)

    thread = threading.Thread(target=_worker, name=f"replan-{run_id}", daemon=True)
    thread.start()
