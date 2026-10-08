"""Dispatch mode and scheduler claim helpers.

Poll execution uses SessionLocal, which cannot see this file's fixture
transaction. Tests bind that helper to the fixture session (close is a no-op)
so a running row is visible without committing into the shared dev database.
A real commit would race the Compose scheduler. Advisory locks still use
separate pooled connections.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.config import Settings
from app.db import engine
from app.models import ScheduleRun, User
from app.scheduler import worker as worker_mod
from app.scheduler.worker import (
    advisory_keys,
    execute_locked,
    list_running_run_ids,
    poll_interval_seconds,
    process_available_runs,
    release_advisory_lock,
    run_one,
    try_advisory_lock,
)
from app.services.schedule_dispatch import (
    dispatch_replan,
    inline_thread_enabled,
    reclaim_stale_runs_global,
)

UTC = timezone.utc


class _VisibleSession:
    """SessionLocal stand-in. Worker code closes what it opens; the fixture must stay open."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def close(self) -> None:
        return None

    def __getattr__(self, name: str) -> object:
        return getattr(self._session, name)


@pytest.fixture(autouse=True)
def _reset_worker_stop():
    worker_mod._stop.clear()
    yield
    worker_mod._stop.clear()


def _bind_worker_session(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    monkeypatch.setattr(worker_mod, "SessionLocal", lambda: _VisibleSession(db_session))


def test_default_dispatch_is_external() -> None:
    assert Settings.model_fields["schedule_dispatch"].default == "external"


def test_schedule_route_does_not_start_threads() -> None:
    source = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "schedule.py"
    text = source.read_text(encoding="utf-8")
    assert "threading" not in text


def test_external_mode_does_not_start_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.schedule_dispatch.inline_thread_enabled", lambda: False)
    monkeypatch.setattr(
        "app.services.schedule_dispatch.threading.Thread",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("thread started")),
    )
    monkeypatch.setattr(
        "app.services.schedule_dispatch.run_replan",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("replan ran inline")),
    )
    dispatch_replan(uuid.uuid4())


def test_sync_runs_inline_even_when_external(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.schedule_dispatch.inline_thread_enabled", lambda: False)
    seen: list[uuid.UUID] = []
    monkeypatch.setattr(
        "app.services.schedule_dispatch.run_replan",
        lambda run_id: seen.append(run_id),
    )
    run_id = uuid.uuid4()
    dispatch_replan(run_id, sync=True)
    assert seen == [run_id]


def test_thread_mode_starts_daemon_without_running_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.schedule_dispatch.inline_thread_enabled", lambda: True)
    calls: list[object] = []

    class FakeThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:
            calls.append({"name": name, "daemon": daemon, "target": target})

        def start(self) -> None:
            calls.append("start")

    monkeypatch.setattr("app.services.schedule_dispatch.threading.Thread", FakeThread)
    monkeypatch.setattr(
        "app.services.schedule_dispatch.run_replan",
        lambda *args, **kwargs: calls.append("replan"),
    )
    run_id = uuid.uuid4()
    dispatch_replan(run_id)
    assert calls[0]["daemon"] is True
    assert str(run_id) in str(calls[0]["name"])
    assert calls[1] == "start"
    assert "replan" not in calls
    calls[0]["target"]()
    assert calls[-1] == "replan"


def test_thread_target_swallows_replan_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.schedule_dispatch.inline_thread_enabled", lambda: True)
    started: list[object] = []

    class FakeThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:
            self._target = target

        def start(self) -> None:
            started.append(self._target)

    monkeypatch.setattr("app.services.schedule_dispatch.threading.Thread", FakeThread)

    def boom(run_id: uuid.UUID) -> None:
        raise RuntimeError(f"replan blew up for {run_id}")

    monkeypatch.setattr("app.services.schedule_dispatch.run_replan", boom)
    dispatch_replan(uuid.uuid4())
    started[0]()


def test_dispatch_mode_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stub:
        def __init__(self, mode: str) -> None:
            self.schedule_dispatch = mode

    monkeypatch.setattr("app.services.schedule_dispatch.get_settings", lambda: Stub(" Thread "))
    assert inline_thread_enabled() is True
    monkeypatch.setattr("app.services.schedule_dispatch.get_settings", lambda: Stub("weird"))
    assert inline_thread_enabled() is False


def test_poll_interval_clamps_to_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubSettings:
        schedule_poll_seconds = 0

    monkeypatch.setattr("app.scheduler.worker.get_settings", lambda: StubSettings())
    assert poll_interval_seconds() == 0.2


def test_advisory_keys_are_stable_and_signed() -> None:
    run_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
    first = advisory_keys(run_id)
    assert first == advisory_keys(run_id)
    namespace, key = first
    assert namespace == 1_886_415_950
    assert 1 <= key <= 0x7FFFFFFF


def test_advisory_lock_is_exclusive() -> None:
    run_id = uuid.uuid4()
    first = engine.connect()
    second = engine.connect()
    try:
        assert try_advisory_lock(first, run_id) is True
        first.commit()
        assert try_advisory_lock(second, run_id) is False
        second.rollback()
    finally:
        release_advisory_lock(first, run_id)
        first.close()
        second.close()


def _owner_id(db: Session) -> uuid.UUID:
    user = db.get(User, BOOTSTRAP_USER_ID)
    if user is None:
        user = db.query(User).first()
    assert user is not None
    return user.id


def _retire_running(db: Session, owner_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    rows = (
        db.query(ScheduleRun)
        .filter(ScheduleRun.owner_id == owner_id, ScheduleRun.status == "running")
        .all()
    )
    for row in rows:
        row.status = "failed"
        row.finished_at = now
    if rows:
        db.flush()


def _other_owner(db: Session) -> uuid.UUID:
    user = User(
        email=f"sched-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Schedule other",
    )
    db.add(user)
    db.flush()
    return user.id


def test_list_running_run_ids_orders_oldest_first(db_session: Session) -> None:
    owner_id = _owner_id(db_session)
    other_id = _other_owner(db_session)
    _retire_running(db_session, owner_id)
    now = datetime.now(UTC)
    older = ScheduleRun(owner_id=owner_id, status="running", started_at=now - timedelta(minutes=5))
    newer = ScheduleRun(owner_id=other_id, status="running", started_at=now)
    done = ScheduleRun(
        owner_id=owner_id,
        status="completed",
        started_at=now - timedelta(minutes=10),
        finished_at=now,
    )
    db_session.add_all([older, newer, done])
    db_session.flush()

    ids = list_running_run_ids(db_session)
    assert older.id in ids
    assert newer.id in ids
    assert ids.index(older.id) < ids.index(newer.id)
    assert done.id not in ids


def test_global_reclaim_fails_only_stale_runs(db_session: Session) -> None:
    owner_id = _owner_id(db_session)
    other_id = _other_owner(db_session)
    _retire_running(db_session, owner_id)
    now = datetime.now(UTC)
    stale = ScheduleRun(
        owner_id=owner_id,
        status="running",
        started_at=now - timedelta(minutes=20),
    )
    fresh = ScheduleRun(owner_id=other_id, status="running", started_at=now)
    db_session.add_all([stale, fresh])
    db_session.flush()

    reclaimed = reclaim_stale_runs_global(db_session)
    assert reclaimed >= 1
    assert db_session.get(ScheduleRun, stale.id).status == "failed"
    assert db_session.get(ScheduleRun, stale.id).error_message == "stale run reclaimed"
    assert db_session.get(ScheduleRun, fresh.id).status == "running"


def _running(
    db_session: Session,
    *,
    age: timedelta = timedelta(),
    owner_id: uuid.UUID | None = None,
) -> ScheduleRun:
    owner = _owner_id(db_session) if owner_id is None else owner_id
    _retire_running(db_session, owner)
    run = ScheduleRun(
        owner_id=owner,
        status="running",
        started_at=datetime.now(UTC) - age,
    )
    db_session.add(run)
    db_session.flush()
    return run


def test_lock_holder_is_the_only_worker_that_replans(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Peer sees the same running row and must not enter run_replan."""
    run = _running(db_session)
    _bind_worker_session(monkeypatch, db_session)
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(worker_mod, "run_replan", lambda run_id: calls.append(run_id))

    holder = engine.connect()
    try:
        assert try_advisory_lock(holder, run.id) is True
        holder.commit()
        assert execute_locked(run.id) is False
        assert run_one(run.id) == 2
        assert calls == []
    finally:
        release_advisory_lock(holder, run.id)
        holder.close()

    assert execute_locked(run.id) is True
    assert calls == [run.id]


def test_execute_locked_releases_lock_when_replan_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _running(db_session)
    _bind_worker_session(monkeypatch, db_session)

    def boom(run_id: uuid.UUID) -> None:
        raise RuntimeError(f"boom {run_id}")

    monkeypatch.setattr(worker_mod, "run_replan", boom)
    with pytest.raises(RuntimeError, match="boom"):
        execute_locked(run.id)

    follower = engine.connect()
    try:
        assert try_advisory_lock(follower, run.id) is True
        follower.commit()
    finally:
        release_advisory_lock(follower, run.id)
        follower.close()


def test_process_available_runs_executes_visible_running_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _running(db_session)
    done = ScheduleRun(
        owner_id=run.owner_id,
        status="completed",
        started_at=datetime.now(UTC) - timedelta(minutes=10),
        finished_at=datetime.now(UTC),
    )
    db_session.add(done)
    db_session.flush()
    _bind_worker_session(monkeypatch, db_session)
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(worker_mod, "run_replan", lambda run_id: calls.append(run_id))

    processed = process_available_runs()
    assert run.id in calls
    assert done.id not in calls
    assert processed >= 1


def test_process_available_runs_continues_after_one_failure(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    older = _running(db_session, age=timedelta(minutes=5))
    newer = _running(db_session, owner_id=_other_owner(db_session))
    _bind_worker_session(monkeypatch, db_session)
    calls: list[uuid.UUID] = []

    def maybe(run_id: uuid.UUID) -> None:
        if run_id == older.id:
            raise RuntimeError("older broke")
        calls.append(run_id)

    monkeypatch.setattr(worker_mod, "run_replan", maybe)
    processed = process_available_runs()
    assert newer.id in calls
    assert older.id not in calls
    assert processed >= 1


def test_poll_forever_keeps_going_after_poll_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def flaky() -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("postgres blinked")
        worker_mod._stop.set()
        return 0

    monkeypatch.setattr(worker_mod, "process_available_runs", flaky)
    monkeypatch.setattr(worker_mod, "poll_interval_seconds", lambda: 0.01)
    worker_mod.poll_forever()
    assert calls["n"] == 2


def test_replan_route_external_stays_running(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /replan commits a running row and does not execute it in external mode."""
    monkeypatch.setattr("app.services.schedule_dispatch.inline_thread_enabled", lambda: False)
    monkeypatch.setattr(
        "app.services.schedule_dispatch.run_replan",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("replan ran inline")),
    )
    monkeypatch.setattr(
        "app.services.schedule_dispatch.threading.Thread",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("thread started")),
    )
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    owner_id = uuid.UUID(me.json()["id"])
    # Hide committed running rows for this owner inside the test transaction only.
    for existing in (
        db_session.query(ScheduleRun)
        .filter(ScheduleRun.owner_id == owner_id, ScheduleRun.status == "running")
        .all()
    ):
        existing.status = "failed"
        existing.finished_at = datetime.now(UTC)
    db_session.flush()

    response = client.post("/api/v1/schedule/replan")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "running"
    stored = db_session.get(ScheduleRun, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.status == "running"
    assert stored.finished_at is None
