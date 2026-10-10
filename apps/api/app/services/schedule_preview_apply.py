"""Apply an immutable schedule preview (F6-W2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import SchedulePreview, ScheduleRun, User
from app.scheduler.apply import apply_calculation
from app.scheduler.collect import collect_inputs
from app.scheduler.preview_inputs import collected_at_from_snapshot, live_owner_fingerprint
from app.scheduler.preview_proposal import calculation_result_from_proposal
from app.services.schedule_dispatch import has_running_run
from app.services.schedule_preview_staleness import preview_stale_categories
from app.services.scheduling_revision import lock_owner_scheduling

APPLY_RECEIPT_KEY = "apply_receipt"


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _existing_receipt(preview: SchedulePreview) -> dict[str, Any] | None:
    stats = preview.stats_json or {}
    receipt = stats.get(APPLY_RECEIPT_KEY)
    return receipt if isinstance(receipt, dict) else None


def _proposal_has_past_blocks(proposal: dict[str, Any], now: datetime) -> bool:
    for row in proposal.get("proposed_blocks") or []:
        if _parse_utc(row["start_time"]) < now:
            return True
    return False


def _validate_ready_for_apply(
    db: Session,
    preview: SchedulePreview,
    *,
    now: datetime,
) -> None:
    if preview.status != "ready":
        raise ApiError(
            409,
            f"Preview cannot be applied while status is {preview.status}",
            "PREVIEW_NOT_APPLICABLE",
        )
    if preview.proposal_json is None:
        raise ApiError(409, "Preview has no proposal", "PREVIEW_NOT_APPLICABLE")

    if preview.expires_at is not None and now >= preview.expires_at:
        preview.status = "expired"
        db.flush()
        raise ApiError(
            409,
            "Preview expired before apply",
            "PREVIEW_EXPIRED",
        )

    settings = lock_owner_scheduling(db, preview.owner_id)
    if has_running_run(db, preview.owner_id):
        raise ApiError(
            409,
            "A schedule run is already in progress",
            "SCHEDULE_RUN_IN_PROGRESS",
        )

    replay = collected_at_from_snapshot(preview.input_snapshot) or now
    _, live_fp = live_owner_fingerprint(db, preview.owner_id, replay)
    if preview.input_fingerprint != live_fp or int(settings.scheduling_revision) != int(
        preview.scheduling_revision
    ):
        categories = preview_stale_categories(
            db,
            owner_id=preview.owner_id,
            input_snapshot=preview.input_snapshot,
            scheduling_revision=int(preview.scheduling_revision),
            settings_revision=int(settings.scheduling_revision),
        )
        preview.status = "stale"
        db.flush()
        raise ApiError(
            409,
            "Scheduling inputs changed since this preview was calculated",
            "PREVIEW_STALE",
            stale_categories=categories,
        )

    if _proposal_has_past_blocks(preview.proposal_json, now):
        raise ApiError(
            409,
            "Proposal includes blocks that would start in the past",
            "PREVIEW_PAST_BLOCKS",
        )


def apply_schedule_preview(db: Session, user: User, preview: SchedulePreview) -> dict[str, Any]:
    """Commit preview proposal to the live schedule; idempotent by preview id."""
    locked = (
        db.query(SchedulePreview)
        .filter(SchedulePreview.id == preview.id, SchedulePreview.owner_id == user.id)
        .with_for_update()
        .one_or_none()
    )
    if locked is None:
        raise ApiError(404, "Schedule preview not found", "PREVIEW_NOT_FOUND")
    preview = locked
    db.refresh(preview)
    existing = _existing_receipt(preview)
    if preview.status == "applied":
        if existing is not None:
            return existing
        raise ApiError(
            409,
            "Preview was already applied",
            "PREVIEW_ALREADY_APPLIED",
        )

    now = datetime.now(timezone.utc)
    _validate_ready_for_apply(db, preview, now=now)

    settings = lock_owner_scheduling(db, preview.owner_id)
    if has_running_run(db, preview.owner_id):
        raise ApiError(
            409,
            "A schedule run is already in progress",
            "SCHEDULE_RUN_IN_PROGRESS",
        )

    proposal = preview.proposal_json
    assert proposal is not None
    result = calculation_result_from_proposal(proposal)
    replay = collected_at_from_snapshot(preview.input_snapshot) or now
    inputs = collect_inputs(db, preview.owner_id, replay)

    run = ScheduleRun(owner_id=preview.owner_id, status="running")
    db.add(run)
    db.flush()

    stats = apply_calculation(db, run=run, inputs=inputs, result=result)
    db.refresh(settings)

    receipt_id = uuid.uuid4()
    applied_at = datetime.now(timezone.utc)
    receipt: dict[str, Any] = {
        "receipt_id": str(receipt_id),
        "preview_id": str(preview.id),
        "schedule_run_id": str(run.id),
        "applied_at": applied_at.isoformat(),
        "blocks_created": int(stats.get("blocks_created", result.blocks_created)),
        "tasks_scheduled": int(run.tasks_scheduled or 0),
        "overbooked_count": int(run.overbooked_count or 0),
        "scheduling_revision": int(settings.scheduling_revision),
    }
    preview.status = "applied"
    preview.stats_json = {**(preview.stats_json or {}), APPLY_RECEIPT_KEY: receipt}
    preview.finished_at = preview.finished_at or applied_at
    db.flush()
    return receipt
