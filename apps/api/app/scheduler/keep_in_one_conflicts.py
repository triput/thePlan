"""Keep-in-one × pin conflict evaluation for placer and effective reads (S2-V2).

Aligned with future-tail reservation (S0 §2) and the §0.1 table. Pins are
protected: this module never resizes, extends, moves, unpins, or merges them.
Saving keep-in-one with a conflict is allowed elsewhere; the next preview
reports the conflict and proposes no automatic work.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ScheduledBlock, Task, UserSettings
from app.scheduler.availability_materializer import load_owner_policy_windows
from app.scheduler.pin_reservation import evaluate_auto_placement


def evaluate_keep_in_one_conflicts(
    db: Session,
    *,
    owner_id: UUID,
    task: Task,
    run_now: datetime,
) -> list[dict[str, Any]]:
    if not task.keep_in_one_block:
        return []
    settings = (
        db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one_or_none()
    )
    if settings is None:
        return []
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.task_id == task.id,
            ScheduledBlock.is_pinned.is_(True),
        )
        .all()
    )
    working_windows, _general = load_owner_policy_windows(db, owner_id)
    decision = evaluate_auto_placement(
        task, settings, blocks, run_now, working_windows=working_windows
    )
    return [dict(row) for row in decision.conflicts]
