"""S1-D3: progress totals under independent PostgreSQL sessions.

Dex's retest requires two connections, not two ORM objects in one session, and
not the SQLite identity-map reproduction. These tests commit a throwaway owner
on disposable database ``theplan_s1_test`` and delete it afterward. They refuse
any other database before the first write.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from datetime import time as time_of_day

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import SessionLocal
from app.models import Task, TaskProgressEntry, User, UserSettings
from app.models.enums import ScheduleStyle
from app.services.scheduling_revision import owner_scheduling_lock_key
from app.services.task_progress import append_progress_entry

_PROBE_EMAIL_LIKE = "renee-s1d3-%@example.com"
_REQUIRED_DATABASE = "theplan_s1_test"
_REQUIRED_REVISION = "029_workweek_days_allow_zero"


@dataclass(frozen=True)
class _ProgressCall:
    idempotency_key: uuid.UUID
    minutes_worked: int
    remaining_minutes: int
    expected_revision: int


@dataclass
class _ProgressOutcome:
    replayed: bool | None = None
    revision: int | None = None
    error_code: str | None = None
    error: str | None = None
    pid: int | None = None


@dataclass(frozen=True)
class _Snapshot:
    worked_minutes: int
    remaining_minutes: int | None
    scheduling_revision: int
    entries: tuple[tuple[uuid.UUID, int, int], ...]


def _open_checked() -> Session:
    db = SessionLocal()
    try:
        name = db.execute(text("SELECT current_database()")).scalar()
    except Exception:
        db.close()
        raise
    if name != _REQUIRED_DATABASE:
        db.close()
        raise AssertionError(
            f"S1-D3 concurrency probe refuses database {name!r}; "
            "set DATABASE_URL to disposable theplan_s1_test"
        )
    return db


def _require_migration(db: Session) -> None:
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_REVISION, (
        f"disposable database alembic version is {version!r}; expected {_REQUIRED_REVISION}"
    )


@pytest.fixture(autouse=True)
def _disposable_s1_database() -> None:
    db = _open_checked()
    try:
        _require_migration(db)
    finally:
        db.close()


def _purge_probe_users() -> None:
    db = _open_checked()
    try:
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        db.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": _PROBE_EMAIL_LIKE},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _commit_probe_task() -> tuple[uuid.UUID, uuid.UUID]:
    """Commit a throwaway owner so a second connection can see the rows."""
    token = uuid.uuid4().hex[:12]
    db = _open_checked()
    try:
        user = User(
            email=f"renee-s1d3-{token}@example.com",
            username=f"renee-s1d3-{token}",
            display_name="Renee S1-D3 probe",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        if owner_scheduling_lock_key(user.id) == owner_scheduling_lock_key(BOOTSTRAP_USER_ID):
            raise RuntimeError("probe owner collided with the bootstrap scheduling lock key")
        db.add(
            UserSettings(
                owner_id=user.id,
                timezone="UTC",
                workday_minutes=480,
                workday_start_local=time_of_day(8, 0),
                workweek_days=5,
                inter_block_buffer_minutes=0,
                upcoming_horizon_days=7,
                default_schedule_style=ScheduleStyle.standalone,
                scheduling_revision=0,
            )
        )
        task = Task(
            owner_id=user.id,
            title=f"renee-s1d3-{token}",
            estimated_duration_minutes=100,
            worked_minutes=0,
            remaining_minutes=100,
        )
        db.add(task)
        db.commit()
        return user.id, task.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _apply_on(db: Session, owner_id: uuid.UUID, task_id: uuid.UUID, call: _ProgressCall) -> _ProgressOutcome:
    outcome = _ProgressOutcome()
    try:
        outcome.pid = int(db.execute(text("SELECT pg_backend_pid()")).scalar())
        user = db.get(User, owner_id)
        task = db.get(Task, task_id)
        assert user is not None and task is not None
        _entry, revision, replayed = append_progress_entry(
            db,
            user,
            task,
            idempotency_key=call.idempotency_key,
            minutes_worked=call.minutes_worked,
            remaining_minutes=call.remaining_minutes,
            expected_revision=call.expected_revision,
            note=None,
        )
        db.commit()
        outcome.replayed = replayed
        outcome.revision = revision
        return outcome
    except ApiError as exc:
        outcome.error_code = str(exc.content.get("code"))
        db.rollback()
        return outcome
    except Exception as exc:
        outcome.error = f"{type(exc).__name__}: {exc}"
        db.rollback()
        return outcome


def _snapshot(owner_id: uuid.UUID, task_id: uuid.UUID) -> _Snapshot:
    db = _open_checked()
    try:
        task = db.get(Task, task_id)
        settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
        rows = (
            db.query(TaskProgressEntry)
            .filter(TaskProgressEntry.task_id == task_id)
            .order_by(TaskProgressEntry.created_at, TaskProgressEntry.id)
            .all()
        )
        assert task is not None
        return _Snapshot(
            worked_minutes=int(task.worked_minutes),
            remaining_minutes=None if task.remaining_minutes is None else int(task.remaining_minutes),
            scheduling_revision=int(settings.scheduling_revision),
            entries=tuple(
                (row.idempotency_key, int(row.minutes_worked), int(row.remaining_minutes))
                for row in rows
            ),
        )
    finally:
        db.close()


def _blocking_pids(watch: Session, pid: int) -> list[int]:
    raw = watch.execute(text("SELECT pg_blocking_pids(:pid)"), {"pid": pid}).scalar()
    watch.rollback()
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [int(item) for item in raw]
    text_raw = str(raw).strip("{}")
    if not text_raw:
        return []
    return [int(part) for part in text_raw.split(",") if part]


def _overlap(
    owner_id: uuid.UUID, task_id: uuid.UUID, holder: _ProgressCall, waiter: _ProgressCall
) -> tuple[_ProgressOutcome, _ProgressOutcome]:
    """Run ``waiter`` only while ``holder`` has committed neither the entry nor the lock.

    The waiter uses its own connection. The test records that waiter's backend
    blocked on the holder's backend before the holder is allowed to commit.
    """
    holder_outcome = _ProgressOutcome()
    waiter_outcome = _ProgressOutcome()
    holder_ready = threading.Event()
    release_holder = threading.Event()
    waiter_pid_ready = threading.Event()
    waiter_finished = threading.Event()

    def run_holder() -> None:
        db = _open_checked()
        try:
            holder_outcome.pid = int(db.execute(text("SELECT pg_backend_pid()")).scalar())
            user = db.get(User, owner_id)
            task = db.get(Task, task_id)
            assert user is not None and task is not None
            _entry, revision, replayed = append_progress_entry(
                db,
                user,
                task,
                idempotency_key=holder.idempotency_key,
                minutes_worked=holder.minutes_worked,
                remaining_minutes=holder.remaining_minutes,
                expected_revision=holder.expected_revision,
                note=None,
            )
            holder_ready.set()
            if not release_holder.wait(12):
                raise TimeoutError("holder was not released")
            db.commit()
            holder_outcome.replayed = replayed
            holder_outcome.revision = revision
        except ApiError as exc:
            holder_outcome.error_code = str(exc.content.get("code"))
            db.rollback()
        except Exception as exc:
            holder_outcome.error = f"{type(exc).__name__}: {exc}"
            db.rollback()
        finally:
            holder_ready.set()
            db.close()

    def run_waiter() -> None:
        db = _open_checked()
        try:
            waiter_outcome.pid = int(db.execute(text("SELECT pg_backend_pid()")).scalar())
            waiter_pid_ready.set()
            db.execute(text("SET lock_timeout = '8s'"))
            user = db.get(User, owner_id)
            task = db.get(Task, task_id)
            assert user is not None and task is not None
            _entry, revision, replayed = append_progress_entry(
                db,
                user,
                task,
                idempotency_key=waiter.idempotency_key,
                minutes_worked=waiter.minutes_worked,
                remaining_minutes=waiter.remaining_minutes,
                expected_revision=waiter.expected_revision,
                note=None,
            )
            db.commit()
            waiter_outcome.replayed = replayed
            waiter_outcome.revision = revision
        except ApiError as exc:
            waiter_outcome.error_code = str(exc.content.get("code"))
            db.rollback()
        except Exception as exc:
            waiter_outcome.error = f"{type(exc).__name__}: {exc}"
            db.rollback()
        finally:
            waiter_finished.set()
            db.close()

    holder_thread = threading.Thread(target=run_holder, name="s1-d3-holder")
    waiter_thread = threading.Thread(target=run_waiter, name="s1-d3-waiter")
    watch = _open_checked()
    try:
        holder_thread.start()
        assert holder_ready.wait(8), f"holder did not reach the pre-commit lock: {holder_outcome}"
        assert holder_outcome.error is None and holder_outcome.error_code is None, holder_outcome
        waiter_thread.start()
        assert waiter_pid_ready.wait(8), f"waiter did not open its own session: {waiter_outcome}"
        assert holder_outcome.pid != waiter_outcome.pid

        blocked = False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not waiter_finished.is_set():
            if holder_outcome.pid in _blocking_pids(watch, waiter_outcome.pid or 0):
                blocked = True
                break
            time.sleep(0.05)
        assert blocked, (
            "waiter never blocked on the holder's PostgreSQL lock; "
            f"finished={waiter_finished.is_set()} holder={holder_outcome} waiter={waiter_outcome}"
        )
        assert not waiter_finished.is_set()
        release_holder.set()
        holder_thread.join(15)
        waiter_thread.join(15)
        assert not holder_thread.is_alive()
        assert not waiter_thread.is_alive()
        return holder_outcome, waiter_outcome
    finally:
        release_holder.set()
        holder_thread.join(15)
        waiter_thread.join(15)
        watch.close()


def test_independent_sessions_sum_worked_minutes() -> None:
    """Two connections stay open together so pool reuse cannot alias backend pids."""
    _purge_probe_users()
    owner_id, task_id = _commit_probe_task()
    first_db = _open_checked()
    second_db = _open_checked()
    try:
        first_pid = int(first_db.execute(text("SELECT pg_backend_pid()")).scalar())
        second_pid = int(second_db.execute(text("SELECT pg_backend_pid()")).scalar())
        assert first_pid != second_pid
        first_key = uuid.uuid4()
        second_key = uuid.uuid4()
        first = _apply_on(
            first_db,
            owner_id,
            task_id,
            _ProgressCall(first_key, minutes_worked=20, remaining_minutes=80, expected_revision=0),
        )
        second = _apply_on(
            second_db,
            owner_id,
            task_id,
            _ProgressCall(second_key, minutes_worked=30, remaining_minutes=45, expected_revision=1),
        )
        assert first.error is None and first.error_code is None, first
        assert second.error is None and second.error_code is None, second
        assert first.replayed is False and second.replayed is False
        assert first.pid == first_pid and second.pid == second_pid
        snap = _snapshot(owner_id, task_id)
        assert snap.worked_minutes == 50
        assert snap.remaining_minutes == 45
        assert snap.scheduling_revision == 2
        assert set(snap.entries) == {(first_key, 20, 80), (second_key, 30, 45)}
    finally:
        first_db.close()
        second_db.close()
        _purge_probe_users()


def test_other_session_stale_task_object_still_sums_worked() -> None:
    """Session B keeps a task loaded at worked=0 while session A commits +20.

    B then applies +30 with the post-commit revision. The stored total must be
    50 even though B's identity map was stale when the call started.
    """
    _purge_probe_users()
    owner_id, task_id = _commit_probe_task()
    stale = _open_checked()
    try:
        stale_task = stale.get(Task, task_id)
        assert stale_task is not None and stale_task.worked_minutes == 0
        first_key = uuid.uuid4()
        second_key = uuid.uuid4()
        writer = _open_checked()
        try:
            first = _apply_on(
                writer,
                owner_id,
                task_id,
                _ProgressCall(first_key, minutes_worked=20, remaining_minutes=80, expected_revision=0),
            )
        finally:
            writer.close()
        assert first.error is None and first.error_code is None, first
        assert stale_task.worked_minutes == 0

        user = stale.get(User, owner_id)
        assert user is not None
        _entry, revision, replayed = append_progress_entry(
            stale,
            user,
            stale_task,
            idempotency_key=second_key,
            minutes_worked=30,
            remaining_minutes=45,
            expected_revision=1,
            note=None,
        )
        assert replayed is False
        assert revision == 2
        stale.commit()
        snap = _snapshot(owner_id, task_id)
        assert snap.worked_minutes == 50
        assert snap.remaining_minutes == 45
        assert set(snap.entries) == {(first_key, 20, 80), (second_key, 30, 45)}
    finally:
        stale.rollback()
        stale.close()
        _purge_probe_users()


def test_overlapping_stale_revision_writes_nothing() -> None:
    _purge_probe_users()
    owner_id, task_id = _commit_probe_task()
    try:
        holder_key = uuid.uuid4()
        waiter_key = uuid.uuid4()
        holder, waiter = _overlap(
            owner_id,
            task_id,
            _ProgressCall(holder_key, minutes_worked=20, remaining_minutes=80, expected_revision=0),
            _ProgressCall(waiter_key, minutes_worked=30, remaining_minutes=10, expected_revision=0),
        )
        assert holder.error is None and holder.error_code is None, holder
        assert holder.replayed is False
        assert waiter.error is None, waiter
        assert waiter.error_code == "SCHEDULING_REVISION_CONFLICT"
        assert waiter.replayed is None
        snap = _snapshot(owner_id, task_id)
        assert snap.worked_minutes == 20
        assert snap.remaining_minutes == 80
        assert snap.scheduling_revision == 1
        assert snap.entries == ((holder_key, 20, 80),)
    finally:
        _purge_probe_users()


def test_overlapping_same_key_retry_replays_once() -> None:
    """A same-key retry that arrives while the first write still holds the lock.

    The waiter must replay that write. It must not insert a second entry or add
    the minutes again.
    """
    _purge_probe_users()
    owner_id, task_id = _commit_probe_task()
    try:
        key = uuid.uuid4()
        call = _ProgressCall(key, minutes_worked=15, remaining_minutes=40, expected_revision=0)
        holder, waiter = _overlap(owner_id, task_id, call, call)
        snap = _snapshot(owner_id, task_id)
        assert snap.worked_minutes == 15
        assert snap.remaining_minutes == 40
        assert snap.scheduling_revision == 1
        assert snap.entries == ((key, 15, 40),)
        assert holder.error is None and holder.error_code is None, holder
        assert holder.replayed is False
        assert waiter.error is None, waiter
        assert waiter.error_code is None, waiter
        assert waiter.replayed is True
    finally:
        _purge_probe_users()
