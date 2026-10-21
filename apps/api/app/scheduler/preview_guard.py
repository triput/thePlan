# ==============================================================================
#  File: apps/api/app/scheduler/preview_guard.py
#  Description: Shared preview FOR UPDATE + runnable guard (T2-S2 B-auto).
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-21
#  Last Update: 2026-10-21
# ==============================================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SchedulePreview


def lock_running_preview(db: Session, preview_id: UUID) -> SchedulePreview | None:
    """Preview row lock with refreshed runnable recheck (all dispatch paths)."""
    preview = (
        db.query(SchedulePreview)
        .filter(SchedulePreview.id == preview_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if preview is None:
        return None
    if preview.status != "running" or preview.finished_at is not None:
        return None
    return preview


def preview_still_runnable(db: Session, preview_id: UUID) -> bool:
    preview = (
        db.query(SchedulePreview)
        .filter(SchedulePreview.id == preview_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if preview is None:
        return False
    return preview.status == "running" and preview.finished_at is None
