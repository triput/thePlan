"""Update Schedule orchestrator — collect → calculate → apply."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ScheduleRun
from app.scheduler.apply import apply_calculation
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.services.scheduling_revision import lock_owner_scheduling

logger = logging.getLogger(__name__)


def run_replan(run_id: UUID, db: Session | None = None) -> None:
    """Execute a schedule run in its own DB session (or reuse provided session)."""
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    stats: dict[str, Any] = {}
    try:
        run = db.get(ScheduleRun, run_id)
        if run is None:
            logger.error("Schedule run %s not found", run_id)
            return
        if run.status != "running":
            logger.warning("Schedule run %s is not running (status=%s)", run_id, run.status)
            return

        lock_owner_scheduling(db, run.owner_id)
        now_utc = datetime.now(timezone.utc)
        inputs = collect_inputs(db, run.owner_id, now_utc)
        result = calculate(db, inputs)
        stats = apply_calculation(db, run=run, inputs=inputs, result=result)
        db.commit()
    except Exception as exc:
        logger.exception("Schedule run %s failed", run_id)
        db.rollback()
        run = db.get(ScheduleRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            run.stats_json = stats or None
            db.commit()
    finally:
        if owns_session:
            db.close()
