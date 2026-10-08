"""Compose scheduler: poll schedule_runs and execute replans outside the API.

The API inserts a ``schedule_runs`` row with ``status=running`` and returns 202.
This process claims those rows with a Postgres session advisory lock so two
workers cannot execute the same run, then calls ``run_replan``.

One-shot (debug)::

    python -m app.scheduler.worker --run-id <uuid>

Poll loop (Compose ``scheduler`` service)::

    python -m app.scheduler.worker --poll
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import ScheduleRun
from app.scheduler.replan import run_replan
from app.services.schedule_dispatch import reclaim_stale_runs_global

logger = logging.getLogger(__name__)

# Two-int advisory lock so we do not share a single bigint namespace with Alembic.
_LOCK_NAMESPACE = 1_886_415_950  # fits signed int32

_stop = threading.Event()


def advisory_keys(run_id: UUID) -> tuple[int, int]:
    """Stable (namespace, key) pair for a schedule run advisory lock."""
    folded = (run_id.int ^ (run_id.int >> 64)) & 0x7FFFFFFF
    if folded == 0:
        folded = 1
    return _LOCK_NAMESPACE, folded


def poll_interval_seconds() -> float:
    raw = float(get_settings().schedule_poll_seconds)
    if raw < 0.2:
        return 0.2
    return raw


def list_running_run_ids(db: Session) -> list[UUID]:
    """Oldest unfinished running rows first."""
    rows = (
        db.query(ScheduleRun.id)
        .filter(
            ScheduleRun.status == "running",
            ScheduleRun.finished_at.is_(None),
        )
        .order_by(ScheduleRun.started_at.asc(), ScheduleRun.id.asc())
        .all()
    )
    return [row[0] for row in rows]


def try_advisory_lock(connection, run_id: UUID) -> bool:
    namespace, key = advisory_keys(run_id)
    locked = connection.execute(
        text("SELECT pg_try_advisory_lock(:namespace, :key)"),
        {"namespace": namespace, "key": key},
    ).scalar()
    return bool(locked)


def release_advisory_lock(connection, run_id: UUID) -> None:
    namespace, key = advisory_keys(run_id)
    try:
        connection.execute(
            text("SELECT pg_advisory_unlock(:namespace, :key)"),
            {"namespace": namespace, "key": key},
        )
        connection.commit()
    except Exception:
        logger.exception("Failed to release scheduler lock for %s", run_id)
        connection.invalidate()


def _is_runnable(run_id: UUID) -> bool:
    db = SessionLocal()
    try:
        run = db.get(ScheduleRun, run_id)
        if run is None:
            logger.error("Schedule run %s disappeared before execution", run_id)
            return False
        if run.status != "running" or run.finished_at is not None:
            logger.info(
                "Schedule run %s no longer runnable (status=%s)",
                run_id,
                run.status,
            )
            return False
        return True
    finally:
        db.close()


def execute_locked(run_id: UUID) -> bool:
    """Run one replan if this process can lock a still-running row.

    False when another worker holds the lock, or the row is no longer runnable.
    """
    connection = engine.connect()
    locked = False
    try:
        locked = try_advisory_lock(connection, run_id)
        connection.commit()
        if not locked:
            logger.info("Schedule run %s already locked by another worker", run_id)
            return False
        if not _is_runnable(run_id):
            return False
        logger.info("Running schedule replan %s", run_id)
        run_replan(run_id)
        return True
    finally:
        if locked:
            release_advisory_lock(connection, run_id)
        connection.close()


def process_available_runs() -> int:
    """Reclaim stale runs, then execute every runnable row this process can lock."""
    db = SessionLocal()
    try:
        reclaimed = reclaim_stale_runs_global(db)
        db.commit()
        if reclaimed:
            logger.info("Reclaimed %s stale schedule run(s)", reclaimed)
        run_ids = list_running_run_ids(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    processed = 0
    for run_id in run_ids:
        if _stop.is_set():
            break
        try:
            if execute_locked(run_id):
                processed += 1
        except Exception:
            # One bad row must not skip every newer run until the 15-minute reclaim.
            logger.exception("Scheduler failed to execute run %s", run_id)
    return processed


def poll_forever() -> None:
    interval = poll_interval_seconds()
    logger.info("Scheduler worker polling schedule_runs every %ss", interval)
    while not _stop.is_set():
        try:
            processed = process_available_runs()
        except Exception:
            logger.exception("Scheduler poll failed")
            processed = 0
        if _stop.is_set():
            break
        if processed == 0:
            _stop.wait(interval)
    logger.info("Scheduler worker stopped")


def run_one(run_id: UUID) -> int:
    """Execute a single run. 0 when done or not runnable, 2 when another worker holds the lock."""
    connection = engine.connect()
    locked = False
    try:
        locked = try_advisory_lock(connection, run_id)
        connection.commit()
        if not locked:
            logger.error("Schedule run %s is already locked by another worker", run_id)
            return 2
        if not _is_runnable(run_id):
            return 0
        logger.info("Running schedule replan %s", run_id)
        run_replan(run_id)
        return 0
    finally:
        if locked:
            release_advisory_lock(connection, run_id)
        connection.close()


def _request_stop(signum: int, _frame: object) -> None:
    logger.info("Scheduler worker received signal %s; finishing current run", signum)
    _stop.set()


def _install_signals() -> None:
    signal.signal(signal.SIGINT, _request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_stop)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run the schedule replan worker")
    parser.add_argument("--run-id", type=UUID, help="Execute one schedule run UUID and exit")
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Poll schedule_runs until SIGTERM/SIGINT",
    )
    args = parser.parse_args()
    if bool(args.run_id) == bool(args.poll):
        parser.error("Specify exactly one of --run-id or --poll")

    _install_signals()
    if args.poll:
        poll_forever()
        return
    raise SystemExit(run_one(args.run_id))


if __name__ == "__main__":
    main()
