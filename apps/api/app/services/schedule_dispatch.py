"""Dispatch and stale-run reclaim for Update Schedule.

The schedule_runs row is the queue. Compose `scheduler` polls `status=running`
rows and executes them. The API does not start a thread unless
``SCHEDULE_DISPATCH=thread`` (API-only dev). Do not combine that bridge with
the scheduler service — both would execute the same run.

Admission allows one ``status=running`` row per owner. ``has_running_run``
is the fast path; the partial unique index
``uq_schedule_runs_one_running_per_owner`` rejects the loser of a double
insert with 409 ``SCHEDULE_RUN_IN_PROGRESS``. The worker still locks by
``run_id``; it never sees a second running row for that owner.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.models.schedule import ONE_RUNNING_PER_OWNER_INDEX, ScheduleRun
from app.scheduler.replan import run_replan

logger = logging.getLogger(__name__)

STALE_RUN_MINUTES = 15

_logged_external = False


def inline_thread_enabled() -> bool:
    """True only for the residual in-process bridge."""
    mode = get_settings().schedule_dispatch.strip().lower()
    if mode == "thread":
        return True
    if mode != "external":
        logger.warning("Unknown SCHEDULE_DISPATCH=%r; treating as external", mode)
    return False


def _stale_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=STALE_RUN_MINUTES)


def _mark_stale(runs: list[ScheduleRun]) -> int:
    now = datetime.now(timezone.utc)
    for run in runs:
        run.status = "failed"
        run.error_message = "stale run reclaimed"
        run.finished_at = now
    return len(runs)


def reclaim_stale_runs(db: Session, owner_id: UUID) -> int:
    """Mark owner running runs older than STALE_RUN_MINUTES as failed."""
    stale = (
        db.query(ScheduleRun)
        .filter(
            ScheduleRun.owner_id == owner_id,
            ScheduleRun.status == "running",
            ScheduleRun.started_at < _stale_cutoff(),
        )
        .all()
    )
    count = _mark_stale(stale)
    if count:
        db.flush()
    return count


def reclaim_stale_runs_global(db: Session) -> int:
    """Mark every running run older than STALE_RUN_MINUTES as failed."""
    stale = (
        db.query(ScheduleRun)
        .filter(
            ScheduleRun.status == "running",
            ScheduleRun.started_at < _stale_cutoff(),
        )
        .all()
    )
    count = _mark_stale(stale)
    if count:
        db.flush()
    return count


def has_running_run(db: Session, owner_id: UUID) -> bool:
    return (
        db.query(ScheduleRun.id)
        .filter(
            ScheduleRun.owner_id == owner_id,
            ScheduleRun.status == "running",
        )
        .first()
        is not None
    )


def _is_one_running_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    name = getattr(diag, "constraint_name", None) if diag is not None else None
    if name == ONE_RUNNING_PER_OWNER_INDEX:
        return True
    return ONE_RUNNING_PER_OWNER_INDEX in str(orig)


def admit_replan(db: Session, owner_id: UUID) -> ScheduleRun:
    """Insert the single running row for this owner, or 409 if one exists.

    The check and the insert are not one statement. Two requests can both
    pass ``has_running_run``. The partial unique index serializes them: the
    loser flushes inside a savepoint, that insert is rolled back, and the
    caller gets the same 409 as the fast path. ``dispatch_replan`` is not
    called for the loser.
    """
    reclaim_stale_runs(db, owner_id)
    if has_running_run(db, owner_id):
        raise ApiError(
            409,
            "A schedule run is already in progress",
            "SCHEDULE_RUN_IN_PROGRESS",
        )

    # SAVEPOINT so a unique violation undoes only this insert. Flush already
    # rolls that savepoint back; don't wrap it in a context manager, which
    # would close it a second time.
    db.begin_nested()
    run = ScheduleRun(owner_id=owner_id, status="running")
    db.add(run)
    try:
        db.flush()
    except IntegrityError as exc:
        conflict = _is_one_running_violation(exc)
        # An outer savepoint has to stay open. A normal request has none
        # left after the admit savepoint rolls back, so roll the request back.
        if db.get_nested_transaction() is None:
            db.rollback()
        if not conflict:
            raise
        logger.info(
            "Schedule admit rejected for owner %s: running row already exists",
            owner_id,
        )
        raise ApiError(
            409,
            "A schedule run is already in progress",
            "SCHEDULE_RUN_IN_PROGRESS",
        ) from exc

    db.commit()
    db.refresh(run)
    return run


def dispatch_replan(run_id: UUID, *, sync: bool = False) -> None:
    """Accept a committed schedule_runs row.

    ``sync=True`` runs inline (tests). Otherwise the row waits for the Compose
    scheduler, unless ``SCHEDULE_DISPATCH=thread``.
    """
    global _logged_external

    if sync:
        run_replan(run_id)
        return

    if inline_thread_enabled():
        def _worker() -> None:
            try:
                run_replan(run_id)
            except Exception:
                logger.exception("Background replan failed for run %s", run_id)

        thread = threading.Thread(target=_worker, name=f"replan-{run_id}", daemon=True)
        thread.start()
        return

    if not _logged_external:
        logger.info("Schedule dispatch is external; scheduler worker polls schedule_runs")
        _logged_external = True
    logger.info("Schedule run %s waiting for scheduler worker", run_id)
