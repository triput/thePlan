"""Apply scheduling calculation — blocks, status, outcomes, calendar mirror."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ScheduleRun, ScheduledBlock
from app.models.enums import ScheduleStatus
from app.scheduler.calculate import CalculationResult
from app.scheduler.collect import SchedulingInputs
from app.scheduler.horizon import wipe_unpinned_blocks_in_horizon
from app.scheduler.outcomes import persist_calculation_outcomes
from app.services import google_calendar, microsoft_calendar
from app.services.scheduling_revision import bump_scheduling_revision

logger = logging.getLogger(__name__)


def _push_mirrored_block(db: Session, settings, block: ScheduledBlock) -> None:
    google_calendar.push_scheduled_block(db, settings, block)
    microsoft_calendar.push_scheduled_block(db, settings, block)


def apply_calculation(
    db: Session,
    *,
    run: ScheduleRun,
    inputs: SchedulingInputs,
    result: CalculationResult,
) -> dict[str, Any]:
    """Persist wipe, blocks, task status, and per-task outcomes in one transaction."""
    stats = dict(result.stats)
    wiped = wipe_unpinned_blocks_in_horizon(
        db,
        inputs.owner_id,
        inputs.horizon_start,
        inputs.horizon_end,
    )
    stats["wiped_unpinned_blocks"] = wiped

    for block in result.proposed_blocks:
        db.add(
            ScheduledBlock(
                owner_id=inputs.owner_id,
                task_id=block.task_id,
                start_time=block.start_time,
                end_time=block.end_time,
                is_pinned=False,
            )
        )

    for candidate in inputs.ordered_candidates:
        task_id = candidate.task.id
        task = candidate.task
        remaining = result.remaining_by_task.get(task_id, 0)
        if remaining <= 0 and result.task_had_blocks.get(task_id):
            task.status = ScheduleStatus.scheduled
        elif remaining > 0:
            task.status = ScheduleStatus.overbooked

    db.flush()

    persist_calculation_outcomes(
        db,
        run_id=run.id,
        owner_id=inputs.owner_id,
        outcomes=result.outcomes,
        input_snapshots=inputs.input_snapshots,
        placement_facts_by_task=result.placement_facts_by_task,
    )

    new_blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == inputs.owner_id,
            ScheduledBlock.is_pinned.is_(False),
            ScheduledBlock.start_time >= inputs.horizon_start,
            ScheduledBlock.start_time < inputs.horizon_end,
        )
        .all()
    )
    app_settings = get_settings()
    for block in new_blocks:
        try:
            _push_mirrored_block(db, app_settings, block)
        except Exception:
            logger.exception("Failed to mirror block %s to calendar", block.id)

    run.tasks_scheduled = result.tasks_scheduled
    run.blocks_created = result.blocks_created
    run.overbooked_count = result.overbooked_count
    run.stats_json = stats
    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)

    bump_scheduling_revision(db, inputs.owner_id)

    return stats
