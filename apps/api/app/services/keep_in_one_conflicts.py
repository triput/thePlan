"""Keep-in-one × pin conflict visibility for effective reads (S2-P4 / §0.1).

Placer-aligned evaluation lives in the scheduler package (Tesla S2-V2).
This module is the API read hook; return structured conflicts when the
scheduler reports them, else an empty list (save-with-conflict still allowed).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Task
from app.schemas.task_scheduling import KeepInOneSchedulingConflictOut


def keep_in_one_scheduling_conflicts(
    db: Session,
    *,
    owner_id: UUID,
    task: Task,
    run_now: datetime,
) -> list[KeepInOneSchedulingConflictOut]:
    """Effective-read conflicts for keep-in-one vs protected pins (§0.1 table)."""
    from app.scheduler.keep_in_one_conflicts import evaluate_keep_in_one_conflicts

    raw = evaluate_keep_in_one_conflicts(db, owner_id=owner_id, task=task, run_now=run_now)
    return [KeepInOneSchedulingConflictOut.model_validate(item) for item in raw]
