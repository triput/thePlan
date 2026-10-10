# ==============================================================================
#  File: apps/api/app/scheduler/preview.py
#  Description: F6 replan preview worker — collect inputs and calculate without live writes.
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import SchedulePreview, UserSettings
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import ALGORITHM_VERSION
from app.scheduler.preview_inputs import fingerprint_collected_inputs, live_owner_fingerprint
from app.scheduler.preview_planning import preview_collection_time
from app.scheduler.preview_proposal import build_proposal_json, capture_before_blocks

logger = logging.getLogger(__name__)

PREVIEW_TTL_MINUTES = 15


def _preview_expires(evaluated_at: datetime) -> datetime:
    return evaluated_at + timedelta(minutes=PREVIEW_TTL_MINUTES)


def run_preview(preview_id: UUID, db: Session | None = None) -> None:
    """Calculate and persist a preview proposal. Never calls apply."""
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        preview = db.get(SchedulePreview, preview_id)
        if preview is None:
            logger.error("Schedule preview %s not found", preview_id)
            return
        if preview.status != "running":
            logger.warning(
                "Schedule preview %s is not running (status=%s)",
                preview_id,
                preview.status,
            )
            return

        wall_now = datetime.now(timezone.utc)
        now_utc = preview_collection_time(wall_now)
        settings = (
            db.query(UserSettings)
            .filter(UserSettings.owner_id == preview.owner_id)
            .one_or_none()
        )
        if settings is None:
            raise RuntimeError(f"User settings missing for owner {preview.owner_id}")

        inputs = collect_inputs(db, preview.owner_id, now_utc)
        before_blocks = capture_before_blocks(
            db,
            owner_id=preview.owner_id,
            horizon_start=inputs.horizon_start,
            horizon_end=inputs.horizon_end,
        )
        input_snapshot, input_fingerprint = fingerprint_collected_inputs(inputs)

        revision_at_start = int(settings.scheduling_revision)
        preview.scheduling_revision = revision_at_start
        preview.input_snapshot = input_snapshot
        preview.input_fingerprint = input_fingerprint
        preview.algorithm_version = ALGORITHM_VERSION
        db.flush()

        result = calculate(db, inputs)
        evaluated_at = datetime.now(timezone.utc)

        # Drop identity-map hits so a commit from another transaction is visible.
        # Unflushed domain dirt is discarded here; calculate must not flush it.
        db.expire_all()
        settings = (
            db.query(UserSettings)
            .filter(UserSettings.owner_id == preview.owner_id)
            .one()
        )
        # Replay the collect clock. UPS scores move with wall time; expiry covers that.
        live_snapshot, live_fingerprint = live_owner_fingerprint(
            db, preview.owner_id, now_utc
        )
        stale_inputs = live_fingerprint != input_fingerprint
        stale_revision = int(settings.scheduling_revision) != revision_at_start

        proposal = build_proposal_json(
            inputs=inputs,
            result=result,
            before_blocks=before_blocks,
        )
        preview.proposal_json = proposal
        preview.evaluated_at = evaluated_at
        preview.stats_json = dict(result.stats)
        preview.finished_at = evaluated_at

        if stale_inputs or stale_revision:
            preview.status = "stale"
            preview.expires_at = None
            preview.error_message = None
            if stale_revision:
                preview.stats_json = {
                    **(preview.stats_json or {}),
                    "stale_reason": "scheduling_revision",
                }
            else:
                preview.stats_json = {
                    **(preview.stats_json or {}),
                    "stale_reason": "input_fingerprint",
                    "live_input_snapshot": live_snapshot,
                }
        else:
            preview.status = "ready"
            preview.expires_at = _preview_expires(evaluated_at)

        db.commit()
    except Exception as exc:
        logger.exception("Schedule preview %s failed", preview_id)
        db.rollback()
        preview = db.get(SchedulePreview, preview_id)
        if preview is not None:
            preview.status = "failed"
            preview.error_message = str(exc)
            preview.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        if owns_session:
            db.close()
