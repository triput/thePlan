# ==============================================================================
#  File: apps/api/app/scheduler/preview_orchestration.py
#  Description: B-auto preview orchestration — record misses outside pure calculate.
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-21
#  Last Update: 2026-10-21
# ==============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
from app.scheduler.reasons import REASON_OCCURRENCE_BOUNDS_MISS
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


@dataclass
class _OrchestrationBaseline:
    revision_r0: int
    fingerprint_f0: str
    snapshot_f0: dict[str, Any]
    disposition_before: tuple[tuple[str, str, str], ...]
    before_blocks: list[dict[str, Any]]
    now_utc: datetime
    covered: set[tuple[UUID, str]] = field(default_factory=set)
    staged_keys: set[tuple[str, str, str]] = field(default_factory=set)


def _validate_collect(inputs: Any) -> None:
    require_busy_input_trust(inputs.busy_input_trust)
    from app.scheduler.calendar_freshness import require_calendar_freshness

    require_calendar_freshness(inputs.calendar_freshness_trust)


def _misses_covered(misses: dict[UUID, Any], covered: set[tuple[UUID, str]]) -> bool:
    for task_id in misses:
        if not any(tid == task_id for tid, _ in covered):
            return False
    return True


def _reconcile_consistent(
    misses: dict[UUID, Any],
    covered: set[tuple[UUID, str]],
) -> bool:
    for task_id in misses:
        if not any(tid == task_id for tid, _ in covered):
            return False
    return True


def run_preview_orchestration(db: Session, preview_id: UUID) -> None:
    preview = lock_running_preview(db, preview_id)
    if preview is None:
        logger.warning("Preview %s skipped by runnable guard", preview_id)
        db.rollback()
        return

    wall_now = datetime.now(timezone.utc)
    now_utc = preview_collection_time(wall_now)

    try:
        inputs = collect_inputs(db, preview.owner_id, now_utc)
        _validate_collect(inputs)
        baseline = _OrchestrationBaseline(
            revision_r0=int(inputs.user_settings.scheduling_revision),
            fingerprint_f0="",
            snapshot_f0={},
            disposition_before=disposition_fingerprint_rows(db, preview.owner_id),
            before_blocks=capture_before_blocks(
                db,
                owner_id=preview.owner_id,
                horizon_start=inputs.horizon_start,
                horizon_end=inputs.horizon_end,
            ),
            now_utc=now_utc,
            covered=covered_episode_set(db, preview.owner_id),
        )
        snapshot, fingerprint = fingerprint_collected_inputs(inputs)
        baseline.fingerprint_f0 = fingerprint
        baseline.snapshot_f0 = snapshot

        result = calculate(db, inputs)
        misses = miss_tasks_from_calculation(result)

        settings = lock_owner_scheduling(db, preview.owner_id)
        if int(settings.scheduling_revision) != baseline.revision_r0:
            raise _OrchestrationAbort("stale", "scheduling_revision")

        staged_any = False
        final_inputs = inputs
        final_result = result

        for iteration in range(1, MAX_ORCHESTRATION_ITER + 1):
            if iteration > 1:
                final_inputs = collect_inputs(db, preview.owner_id, now_utc)
                _validate_collect(final_inputs)
                final_result = calculate(db, final_inputs)
                misses = miss_tasks_from_calculation(final_result)

            live_snapshot, live_fp = fingerprint_collected_inputs(final_inputs)
            disposition_live = disposition_fingerprint_rows(db, preview.owner_id)
            if orchestration_input_drift(
                revision_at_start=baseline.revision_r0,
                revision_live=int(
                    db.query(UserSettings.scheduling_revision)
                    .filter(UserSettings.owner_id == preview.owner_id)
                    .scalar()
                ),
                snapshot_at_start=baseline.snapshot_f0,
                fingerprint_at_start=baseline.fingerprint_f0,
                snapshot_live=live_snapshot,
                fingerprint_live=live_fp,
                disposition_before=baseline.disposition_before,
                disposition_live=disposition_live,
                staged_keys=baseline.staged_keys,
            ):
                raise _OrchestrationAbort("stale", "input_fingerprint")

            new_staged = stage_auto_misses(
                db,
                owner_id=preview.owner_id,
                preview_id=preview.id,
                misses=misses,
                covered_episode_keys=baseline.covered,
            )
            if new_staged:
                staged_any = True
                for item in new_staged:
                    baseline.staged_keys.add(
                        (str(item.task_id), item.episode_key, "unresolved_held")
                    )
            db.flush()

            reconcile_inputs = collect_inputs(db, preview.owner_id, now_utc)
            _validate_collect(reconcile_inputs)
            reconcile_result = calculate(db, reconcile_inputs)
            reconcile_misses = miss_tasks_from_calculation(reconcile_result)

            uncovered = {
                tid
                for tid in reconcile_misses
                if not any(c[0] == tid for c in baseline.covered)
            }
            if uncovered and iteration < MAX_ORCHESTRATION_ITER:
                misses = {tid: reconcile_misses[tid] for tid in uncovered}
                continue
            if uncovered:
                raise _OrchestrationAbort("failed", "max_iter_exhausted")

            if not _reconcile_consistent(reconcile_misses, baseline.covered):
                if iteration < MAX_ORCHESTRATION_ITER:
                    misses = reconcile_misses
                    continue
                raise _OrchestrationAbort("failed", "reconcile_inconsistent")

            final_inputs = reconcile_inputs
            final_result = reconcile_result
            break
        else:
            raise _OrchestrationAbort("failed", "max_iter_exhausted")

        settings = lock_owner_scheduling(db, preview.owner_id)
        revision_final = baseline.revision_r0
        if staged_any:
            revision_final = increment_scheduling_revision(db, settings)

        if not preview_still_runnable(db, preview_id):
            raise _OrchestrationAbort("failed", "not_runnable_before_commit")

        preview = db.get(SchedulePreview, preview_id)
        if preview is None:
            raise _OrchestrationAbort("failed", "preview_missing")
        publish_inputs = collect_inputs(db, preview.owner_id, now_utc)
        _validate_collect(publish_inputs)
        publish_result = calculate(db, publish_inputs)
        input_snapshot, input_fingerprint = fingerprint_collected_inputs(publish_inputs)
        proposal = build_proposal_json(
            inputs=publish_inputs,
            result=publish_result,
            before_blocks=baseline.before_blocks,
        )
        evaluated_at = datetime.now(timezone.utc)
        preview.scheduling_revision = revision_final
        preview.input_snapshot = input_snapshot
        preview.input_fingerprint = input_fingerprint
        preview.algorithm_version = ALGORITHM_VERSION
        preview.proposal_json = proposal
        preview.evaluated_at = evaluated_at
        preview.stats_json = dict(publish_result.stats)
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
    preview = db.get(SchedulePreview, preview_id)
    if preview is None or preview.status != "running":
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
