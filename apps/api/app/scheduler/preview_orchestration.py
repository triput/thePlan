# ==============================================================================
#  File: apps/api/app/scheduler/preview_orchestration.py
#  Description: B-auto preview orchestration — record misses outside pure calculate.
#  Component: Replan Preview
#  Version: 1.1
#  Created: 2026-10-21
#  Last Update: 2026-10-21
# ==============================================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SchedulePreview, UserSettings
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.free_busy import require_busy_input_trust
from app.scheduler.input_fingerprint import ALGORITHM_VERSION
from app.scheduler.preview_guard import lock_running_preview, preview_still_runnable
from app.scheduler.preview_inputs import fingerprint_collected_inputs
from app.scheduler.preview_planning import preview_collection_time
from app.scheduler.preview_proposal import build_proposal_json, capture_before_blocks
from app.services.occurrence_disposition import (
    covered_episode_set,
    disposition_fingerprint_rows,
    miss_tasks_from_calculation,
    orchestration_input_drift,
    stage_auto_misses,
)
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling

logger = logging.getLogger(__name__)

MAX_ORCHESTRATION_ITER = 3


def _validate_collect(inputs: Any) -> None:
    require_busy_input_trust(inputs.busy_input_trust)
    from app.scheduler.calendar_freshness import require_calendar_freshness

    require_calendar_freshness(inputs.calendar_freshness_trust)


def _reconcile_consistent(
    misses: dict[UUID, Any],
    covered: set[tuple[UUID, str]],
) -> bool:
    for task_id in misses:
        if not any(tid == task_id for tid, _ in covered):
            return False
    return True


def _live_revision(db: Session, owner_id: UUID) -> int:
    return int(
        db.query(UserSettings.scheduling_revision)
        .filter(UserSettings.owner_id == owner_id)
        .scalar()
    )


def run_preview_orchestration(db: Session, preview_id: UUID) -> None:
    preview = lock_running_preview(db, preview_id)
    if preview is None:
        logger.warning("Preview %s skipped by runnable guard", preview_id)
        db.rollback()
        return

    owner_id = preview.owner_id
    wall_now = datetime.now(timezone.utc)
    now_utc = preview_collection_time(wall_now)

    try:
        # Ephemeral baseline — no domain writes. Miss set is advisory until
        # the under-lock authoritative recollect below.
        inputs = collect_inputs(db, owner_id, now_utc)
        _validate_collect(inputs)
        revision_r0 = int(inputs.user_settings.scheduling_revision)
        snapshot_f0, fingerprint_f0 = fingerprint_collected_inputs(inputs)
        disposition_before = disposition_fingerprint_rows(db, owner_id)
        covered = covered_episode_set(db, owner_id)
        staged_keys: set[tuple[str, str, str]] = set()

        staged_any = False
        final_inputs = inputs
        final_result = None

        for iteration in range(1, MAX_ORCHESTRATION_ITER + 1):
            # Lock order: preview already FOR UPDATE; owner lock before miss write.
            settings = lock_owner_scheduling(db, owner_id)
            if int(settings.scheduling_revision) != revision_r0:
                raise _OrchestrationAbort("stale", "scheduling_revision")

            # Authoritative refreshed collection under lock before any miss write.
            live_inputs = collect_inputs(db, owner_id, now_utc)
            _validate_collect(live_inputs)
            live_snapshot, live_fp = fingerprint_collected_inputs(live_inputs)
            disposition_live = disposition_fingerprint_rows(db, owner_id)
            if orchestration_input_drift(
                revision_at_start=revision_r0,
                revision_live=_live_revision(db, owner_id),
                snapshot_at_start=snapshot_f0,
                fingerprint_at_start=fingerprint_f0,
                snapshot_live=live_snapshot,
                fingerprint_live=live_fp,
                disposition_before=disposition_before,
                disposition_live=disposition_live,
                staged_keys=staged_keys,
            ):
                raise _OrchestrationAbort("stale", "input_fingerprint")

            live_result = calculate(db, live_inputs)
            misses = miss_tasks_from_calculation(live_result)

            new_staged = stage_auto_misses(
                db,
                owner_id=owner_id,
                preview_id=preview_id,
                misses=misses,
                covered_episode_keys=covered,
            )
            if new_staged:
                staged_any = True
                for item in new_staged:
                    staged_keys.add(
                        (str(item.task_id), item.episode_key, "unresolved_held")
                    )
            db.flush()

            reconcile_inputs = collect_inputs(db, owner_id, now_utc)
            _validate_collect(reconcile_inputs)
            reconcile_result = calculate(db, reconcile_inputs)
            reconcile_misses = miss_tasks_from_calculation(reconcile_result)

            uncovered = {
                tid
                for tid in reconcile_misses
                if not any(c[0] == tid for c in covered)
            }
            if uncovered and iteration < MAX_ORCHESTRATION_ITER:
                continue
            if uncovered:
                raise _OrchestrationAbort("failed", "max_iter_exhausted")

            if not _reconcile_consistent(reconcile_misses, covered):
                if iteration < MAX_ORCHESTRATION_ITER:
                    continue
                raise _OrchestrationAbort("failed", "reconcile_inconsistent")

            final_inputs = reconcile_inputs
            final_result = reconcile_result
            break
        else:
            raise _OrchestrationAbort("failed", "max_iter_exhausted")

        if final_result is None:
            raise _OrchestrationAbort("failed", "no_converged_result")

        # Converged result must stay inside C — no unchecked extra calculate publish.
        publish_misses = miss_tasks_from_calculation(final_result)
        if not _reconcile_consistent(publish_misses, covered):
            raise _OrchestrationAbort("failed", "publish_inconsistent")

        settings = lock_owner_scheduling(db, owner_id)
        revision_final = revision_r0
        if staged_any:
            revision_final = increment_scheduling_revision(db, settings)

        if not preview_still_runnable(db, preview_id):
            raise _OrchestrationAbort("failed", "not_runnable_before_commit")

        preview = (
            db.query(SchedulePreview)
            .filter(SchedulePreview.id == preview_id)
            .with_for_update()
            .populate_existing()
            .one_or_none()
        )
        if preview is None or preview.status != "running":
            raise _OrchestrationAbort("failed", "preview_missing")

        # Post-bump fingerprint + refreshed before_blocks (not baseline reuse).
        publish_inputs = collect_inputs(db, owner_id, now_utc)
        _validate_collect(publish_inputs)
        input_snapshot, input_fingerprint = fingerprint_collected_inputs(publish_inputs)
        before_blocks = capture_before_blocks(
            db,
            owner_id=owner_id,
            horizon_start=publish_inputs.horizon_start,
            horizon_end=publish_inputs.horizon_end,
        )
        proposal = build_proposal_json(
            inputs=publish_inputs,
            result=final_result,
            before_blocks=before_blocks,
        )
        evaluated_at = datetime.now(timezone.utc)
        preview.scheduling_revision = revision_final
        preview.input_snapshot = input_snapshot
        preview.input_fingerprint = input_fingerprint
        preview.algorithm_version = ALGORITHM_VERSION
        preview.proposal_json = proposal
        preview.evaluated_at = evaluated_at
        preview.stats_json = dict(final_result.stats)
        preview.finished_at = evaluated_at
        preview.status = "ready"
        from app.scheduler.preview import _preview_expires

        preview.expires_at = _preview_expires(evaluated_at)
        trust = getattr(publish_inputs, "busy_input_trust", None)
        if trust is not None:
            preview.stats_json = {
                **(preview.stats_json or {}),
                "busy_input_trust": {"ok": True},
            }
        db.commit()
    except _OrchestrationAbort as exc:
        db.rollback()
        _terminal_preview(db, preview_id, status=exc.status, reason=exc.reason)
    except Exception:
        db.rollback()
        raise


class _OrchestrationAbort(Exception):
    def __init__(self, status: str, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(reason)


def _terminal_preview(db: Session, preview_id: UUID, *, status: str, reason: str) -> None:
    """Lock + populate_existing recheck before terminal write (atomic with status)."""
    preview = (
        db.query(SchedulePreview)
        .filter(SchedulePreview.id == preview_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if preview is None or preview.status != "running" or preview.finished_at is not None:
        return
    preview.status = status
    preview.finished_at = datetime.now(timezone.utc)
    preview.expires_at = None
    preview.error_message = reason if status == "failed" else None
    if status == "stale":
        preview.stats_json = {
            **(preview.stats_json or {}),
            "stale_reason": reason,
        }
    db.commit()
