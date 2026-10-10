# ==============================================================================
#  File: apps/api/app/services/schedule_preview_dispatch.py
#  Description: Admit and dispatch F6 schedule preview worker jobs (separate from direct replan).
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SchedulePreview
from app.scheduler.preview import run_preview
from app.services.schedule_dispatch import inline_thread_enabled

logger = logging.getLogger(__name__)


def admit_preview(db: Session, owner_id: UUID) -> SchedulePreview:
    """Insert a preview row and commit. Multiple previews per owner are allowed."""
    preview = SchedulePreview(owner_id=owner_id, status="running")
    db.add(preview)
    db.commit()
    db.refresh(preview)
    return preview


def dispatch_preview(preview_id: UUID, *, sync: bool = False) -> None:
    if sync:
        run_preview(preview_id)
        return

    if inline_thread_enabled():

        def _worker() -> None:
            try:
                run_preview(preview_id)
            except Exception:
                logger.exception("Background preview failed for %s", preview_id)

        thread = threading.Thread(target=_worker, name=f"preview-{preview_id}", daemon=True)
        thread.start()
        return

    # Compose scheduler polls schedule_previews in F6-W1 worker extension.
    logger.debug(
        "Preview %s queued (SCHEDULE_DISPATCH=%s)",
        preview_id,
        get_settings().schedule_dispatch,
    )
