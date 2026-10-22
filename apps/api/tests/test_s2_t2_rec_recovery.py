"""T2-REC reviewed recovery — disposable acceptance (theplan_s1_test @ :5433).

Matrix A1–A22 plus clarifiers. No synthetic HTTP server.
A6b: separate SessionLocal sessions and a start-barrier race. Not an
exhaustive interleaving proof. The recover-then-rollback branch is session
rollback, not late-injected failure.
A11: early catch-up usable-dates gate, before series/event/revision writes.
A11b: failure after those writes, at the nested-savepoint final flush.
042→043 execution uses a separate database (theplan_s1_mig_test), never a
downgrade of theplan_s1_test.
A3 historical-block isolation is EXCEEDS_SLICE and is not claimed here.
Dex second bounce: A10e/A10f keep the selected civil occurrence for
FREQ=HOURLY and FREQ=MINUTELY;INTERVAL=30 (no previous_due H/M/S rewrite).
A5d/A5e: multi-valued BYHOUR gap and fold stay fail-closed, and a
legitimate selected hour is not replaced by another listed hour.
"""

from __future__ import annotations

import os
import subprocess
import threading
import uuid
from datetime import datetime, time as time_of_day, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import SessionLocal
from app.models import (
    Project,
    ScheduledBlock,
    Task,
    TaskOccurrenceDisposition,
    TaskProgressEntry,
    User,
    UserSettings,
)
from app.models.enums import ScheduleStyle
from app.models.task_occurrence_disposition import (
    EVENT_MISS_DETECTED,
    EVENT_RECOVERED,
    RESOLUTION_RECOVERED,
    RESOLUTION_RELEASED,
    RESOLUTION_SKIPPED,
    RESOLUTION_UNRESOLVED_HELD,
    DispositionCorrectionAudit,
    DispositionEvent,
    ProgressEpochMembership,
)
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import STALE_OCCURRENCE_DISPOSITION
from app.scheduler.preview import run_preview
from app.scheduler.preview_inputs import fingerprint_collected_inputs
from app.scheduler.task_effort import placement_effort_minutes
from app.services.availability_seed import ensure_default_availability_policies
from app.services.occurrence_disposition import episode_key_for_task, recover_held, release_held, skip_held
from app.services.scheduling_revision import (
    increment_scheduling_revision,
    lock_owner_scheduling,
    owner_scheduling_lock_key,
)
from test_schedule_replan import FIXED_NOW, _patch_schedule_clock, _prepare_settings

UTC = timezone.utc
_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "043_recovery_epoch"
_PROBE_EMAIL_LIKE = "renee-t2rec-%@example.com"

# Tuesday weekly-books window at FIXED_NOW (2026-08-11 12:00 UTC).
_BOOKS_DUE = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
_BOOKS_EARLIEST = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
_BOOKS_LATEST = datetime(2026, 8, 11, 11, 0, tzinfo=UTC)
_BOOKS_DEADLINE = datetime(2026, 8, 11, 11, 30, tzinfo=UTC)
_AUG18 = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)
_CATCH_DUE = datetime(2026, 8, 13, 15, 0, tzinfo=UTC)
_CATCH_EARLIEST = datetime(2026, 8, 13, 14, 0, tzinfo=UTC)
_CATCH_LATEST = datetime(2026, 8, 13, 16, 0, tzinfo=UTC)
_CATCH_DEADLINE = datetime(2026, 8, 13, 16, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _disposable_db(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB
    port = db_session.execute(text("SHOW port")).scalar()
    # Inside the container the server port is 5432; the host mapping is :5433.
    # Refuse a household-shaped database name even if someone remaps ports.
    assert name != "theplan"
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD
    del port


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_schedule_clock(monkeypatch)
    monkeypatch.setattr(
        "app.services.occurrence_disposition.utc_now",
        lambda: FIXED_NOW,
    )


def _set_now(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(
        "app.services.occurrence_disposition.utc_now",
        lambda when=when: when,
    )


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _prepare(client: TestClient, db: Session) -> None:
    _prepare_settings(client)
    owner = _owner_id(client)
    ensure_default_availability_policies(db, owner)
    _seed_always_on_availability(db, owner)
    db.commit()


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _revision(client: TestClient) -> int:
    return int(client.get("/api/v1/settings").json()["scheduling_revision"])


def _seed_always_on_availability(db: Session, owner_id: uuid.UUID) -> None:
    from app.models import AvailabilityPolicy, AvailabilityWindow
    from app.models.enums import AvailabilityPolicySlug
    from app.services.availability_seed import derive_window_end

    ensure_default_availability_policies(db, owner_id)
    start = time_of_day(0, 0)
    end, overnight = derive_window_end(start, 1440)
    for slug in (AvailabilityPolicySlug.work.value, AvailabilityPolicySlug.general.value):
        policy = (
            db.query(AvailabilityPolicy)
            .filter(
                AvailabilityPolicy.owner_id == owner_id,
                AvailabilityPolicy.slug == slug,
            )
            .one()
        )
        policy.windows.clear()
        db.flush()
        for weekday in range(7):
            policy.windows.append(
                AvailabilityWindow(
                    owner_id=owner_id,
                    weekday=weekday,
                    start_time=start,
                    end_time=end,
                    ends_next_day=overnight,
                    duration_minutes=1440,
                    sort_order=0,
                )
            )
    db.flush()


def _series(
    client: TestClient,
    *,
    title: str,
    due: datetime,
    rrule: str,
    is_fixed: bool,
    earliest: datetime | None = None,
    latest: datetime | None = None,
    deadline: datetime | None = None,
    tz: str = "UTC",
    starts_on: str | None = None,
    ends_on: str | None = None,
    estimate: int = 60,
) -> dict:
    recurrence: dict = {"rrule": rrule, "is_fixed": is_fixed, "timezone": tz}
    if starts_on is not None:
        recurrence["starts_on"] = starts_on
    if ends_on is not None:
        recurrence["ends_on"] = ends_on
    payload: dict = {
        "title": title,
        "estimated_duration_minutes": estimate,
        "priority": "p1",
        "schedule_style": "standalone",
        "due_at": _iso(due),
        "recurrence": recurrence,
    }
    if earliest is not None:
        payload["start_no_earlier_at"] = _iso(earliest)
    if latest is not None:
        payload["start_no_later_at"] = _iso(latest)
    if deadline is not None:
        payload["deadline_at"] = _iso(deadline)
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _books(client: TestClient, *, title: str | None = None, is_fixed: bool = True) -> dict:
    return _series(
        client,
        title=title or f"Weekly books {_uid()}",
        due=_BOOKS_DUE,
        earliest=_BOOKS_EARLIEST,
        latest=_BOOKS_LATEST,
        deadline=_BOOKS_DEADLINE,
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=is_fixed,
    )


def _window_on(due: datetime) -> tuple[datetime, datetime, datetime]:
    return due, due + timedelta(hours=2), due + timedelta(hours=2, minutes=30)


def _log(client: TestClient, task_id: str, worked: int, remaining: int) -> dict:
    response = client.post(
        f"/api/v1/tasks/{task_id}/progress-entries",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": worked,
            "remaining_minutes": remaining,
            "expected_revision": _revision(client),
            "note": "logged",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _correct(
    client: TestClient,
    task_id: str,
    entry_id: str,
    *,
    worked: int = 5,
    remaining: int = 30,
) -> object:
    return client.post(
        f"/api/v1/tasks/{task_id}/progress-corrections",
        json={
            "corrects_entry_id": entry_id,
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": worked,
            "remaining_minutes": remaining,
            "expected_revision": _revision(client),
            "note": "historical",
        },
    )


def _hold(db: Session, task_id: str) -> TaskOccurrenceDisposition:
    task = db.get(Task, uuid.UUID(str(task_id)))
    assert task is not None
    row = TaskOccurrenceDisposition(
        owner_id=task.owner_id,
        task_id=task.id,
        episode_key=episode_key_for_task(task),
        resolution=RESOLUTION_UNRESOLVED_HELD,
        bounds_snapshot={
            "start_no_earlier_at": _iso(task.start_no_earlier_at) if task.start_no_earlier_at else None,
            "start_no_later_at": _iso(task.start_no_later_at) if task.start_no_later_at else None,
            "deadline_at": _iso(task.deadline_at) if task.deadline_at else None,
        },
        miss_reason_code="occurrence_bounds_miss",
    )
    db.add(row)
    db.flush()
    db.add(
        DispositionEvent(
            disposition_id=row.id,
            event_type=EVENT_MISS_DETECTED,
            payload={"probe": True},
        )
    )
    db.flush()
    return row


def _catch_up_body() -> dict:
    return {
        "catch_up_due_at": _iso(_CATCH_DUE),
        "catch_up_start_no_earlier_at": _iso(_CATCH_EARLIEST),
        "catch_up_start_no_later_at": _iso(_CATCH_LATEST),
        "catch_up_deadline_at": _iso(_CATCH_DEADLINE),
    }


def _recover(client: TestClient, task_id: str, disp_id: uuid.UUID, **extra: object):
    body = {
        "disposition_id": str(disp_id),
        "expected_revision": _revision(client),
        "authorize_instant": _iso(FIXED_NOW),
        **_catch_up_body(),
    }
    body.update(extra)
    return client.post(f"/api/v1/schedule/held-misses/{task_id}/recover", json=body)


def _task(db: Session, task_id: str) -> Task:
    db.expire_all()
    task = db.get(Task, uuid.UUID(str(task_id)))
    assert task is not None
    return task


def _entries(db: Session, task_id: uuid.UUID) -> list[TaskProgressEntry]:
    return (
        db.query(TaskProgressEntry)
        .filter(TaskProgressEntry.task_id == task_id)
        .all()
    )


def _memberships(db: Session, task_id: uuid.UUID) -> list[ProgressEpochMembership]:
    return (
        db.query(ProgressEpochMembership)
        .filter(ProgressEpochMembership.task_id == task_id)
        .all()
    )


def _catch_up_named(db: Session, title: str) -> list[Task]:
    return db.query(Task).filter(Task.title == f"{title} (catch-up)").all()


def _ready_preview(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    assert started.status_code == 202, started.text
    run_preview(uuid.UUID(started.json()["id"]), db=db)
    db.expire_all()
    got = client.get(f"/api/v1/schedule/previews/{started.json()['id']}")
    assert got.status_code == 200, got.text
    return got.json()


def test_migration_043_recovery_epoch_objects(db_session: Session) -> None:
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "043_recovery_epoch"
    tables = set(
        db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN "
                "('progress_epoch_membership', 'disposition_correction_audits')"
            )
        ).scalars()
    )
    assert tables == {"progress_epoch_membership", "disposition_correction_audits"}
    checks = set(
        db_session.execute(
            text(
                "SELECT conname FROM pg_constraint WHERE conname IN ("
                "'task_occurrence_dispositions_recovered_implies_snapshot', "
                "'task_occurrence_dispositions_catch_up_ne_task')"
            )
        ).scalars()
    )
    assert checks == {
        "task_occurrence_dispositions_recovered_implies_snapshot",
        "task_occurrence_dispositions_catch_up_ne_task",
    }
    trigger = db_session.execute(
        text(
            "SELECT tgname FROM pg_trigger "
            "WHERE tgname = 'disposition_correction_audits_append_only'"
        )
    ).scalar()
    assert trigger == "disposition_correction_audits_append_only"


_MIG_DB = "theplan_s1_mig_test"
_MIG_DSN = "postgresql+psycopg://t1a@127.0.0.1:5433/theplan_s1_mig_test"
_FORBIDDEN_MIG_DBS = frozenset({"theplan", "theplan_s1_test", "theplan_t1a_test"})


def _assert_isolated_mig_dsn(dsn: str) -> None:
    parsed = urlparse(dsn)
    name = (parsed.path or "").lstrip("/").split("?", 1)[0]
    assert parsed.hostname in {"127.0.0.1", "localhost"}
    assert parsed.port == 5433
    assert name == _MIG_DB
    assert name not in _FORBIDDEN_MIG_DBS
    assert name != _REQUIRED_DB


def _mig_admin_connect():
    import psycopg

    _assert_isolated_mig_dsn(_MIG_DSN)
    conn = psycopg.connect("postgresql://t1a@127.0.0.1:5433/postgres")
    conn.autocommit = True
    return conn


def _drop_mig_db() -> None:
    _assert_isolated_mig_dsn(_MIG_DSN)
    admin = _mig_admin_connect()
    try:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{_MIG_DB}" WITH (FORCE)')
    finally:
        admin.close()


def _alembic_upgrade_mig(revision: str) -> None:
    """Forward upgrade only. Never downgrades theplan_s1_test."""
    _assert_isolated_mig_dsn(_MIG_DSN)
    if revision.startswith("-") or "downgrade" in revision:
        raise AssertionError(f"refusing non-upgrade revision {revision!r}")
    env = os.environ.copy()
    env["DATABASE_URL"] = _MIG_DSN
    env["SEED_DEMO_USER"] = "false"
    api_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [str(api_root / ".venv" / "Scripts" / "python.exe"), "-m", "alembic", "upgrade", revision],
        cwd=str(api_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"alembic upgrade {revision} on {_MIG_DB} failed ({proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )


def test_migration_042_to_043_executes_and_retains_held_progress(db_session: Session) -> None:
    """Actual 042→043 upgrade on theplan_s1_mig_test. Shared theplan_s1_test stays 043.

    SHOW port inside the container is often 5432; the host DSN port is 5433.
    """
    _assert_isolated_mig_dsn(_MIG_DSN)
    shared_name = db_session.execute(text("SELECT current_database()")).scalar()
    shared_version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert shared_name == _REQUIRED_DB
    assert shared_version == "043_recovery_epoch"

    _drop_mig_db()
    admin = _mig_admin_connect()
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{_MIG_DB}"')
    finally:
        admin.close()

    owner_id = uuid.uuid4()
    task_id = uuid.uuid4()
    disp_id = uuid.uuid4()
    entry_id = uuid.uuid4()
    event_id = uuid.uuid4()
    idem = uuid.uuid4()
    try:
        _alembic_upgrade_mig("042_task_occurrence_dispositions")
        eng = create_engine(_MIG_DSN, pool_pre_ping=True)
        try:
            with eng.begin() as conn:
                got_db = conn.execute(text("SELECT current_database()")).scalar()
                got_ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                assert got_db == _MIG_DB
                assert got_db != "theplan"
                assert got_db != "theplan_s1_test"
                assert got_ver == "042_task_occurrence_dispositions"
                cols = set(
                    conn.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'task_occurrence_dispositions'"
                        )
                    ).scalars()
                )
                assert "catch_up_task_id" not in cols
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, username, display_name) "
                        "VALUES (:id, :email, :username, :display)"
                    ),
                    {
                        "id": owner_id,
                        "email": "renee-mig-042@example.com",
                        "username": "renee-mig-042",
                        "display": "Renee mig 042",
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO tasks ("
                        "id, owner_id, title, estimated_duration_minutes, "
                        "worked_minutes, remaining_minutes"
                        ") VALUES ("
                        ":id, :owner, :title, 45, 40, 5"
                        ")"
                    ),
                    {
                        "id": task_id,
                        "owner": owner_id,
                        "title": "mig held series",
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO task_occurrence_dispositions ("
                        "id, owner_id, task_id, episode_key, resolution, "
                        "bounds_snapshot, miss_reason_code"
                        ") VALUES ("
                        ":id, :owner, :task, :episode, 'unresolved_held', "
                        "CAST(:snap AS jsonb), 'occurrence_bounds_miss'"
                        ")"
                    ),
                    {
                        "id": disp_id,
                        "owner": owner_id,
                        "task": task_id,
                        "episode": "mig-episode-1",
                        "snap": '{"kept":"held"}',
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO disposition_events ("
                        "id, disposition_id, event_type, payload"
                        ") VALUES ("
                        ":id, :disp, 'miss_detected', CAST(:payload AS jsonb)"
                        ")"
                    ),
                    {
                        "id": event_id,
                        "disp": disp_id,
                        "payload": '{"kept":true}',
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO task_progress_entries ("
                        "id, owner_id, task_id, idempotency_key, intent_hash, "
                        "minutes_worked, remaining_minutes"
                        ") VALUES ("
                        ":id, :owner, :task, :idem, :intent, 40, 5"
                        ")"
                    ),
                    {
                        "id": entry_id,
                        "owner": owner_id,
                        "task": task_id,
                        "idem": idem,
                        "intent": "d" * 64,
                    },
                )
        finally:
            eng.dispose()

        _alembic_upgrade_mig("043_recovery_epoch")
        eng = create_engine(_MIG_DSN, pool_pre_ping=True)
        try:
            with eng.connect() as conn:
                assert conn.execute(text("SELECT current_database()")).scalar() == _MIG_DB
                assert (
                    conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                    == "043_recovery_epoch"
                )
                task = conn.execute(
                    text(
                        "SELECT title, estimated_duration_minutes, worked_minutes, "
                        "remaining_minutes FROM tasks WHERE id = :id"
                    ),
                    {"id": task_id},
                ).one()
                assert task.title == "mig held series"
                assert task.estimated_duration_minutes == 45
                assert task.worked_minutes == 40
                assert task.remaining_minutes == 5
                disp = conn.execute(
                    text(
                        "SELECT resolution, episode_key, bounds_snapshot, "
                        "miss_reason_code, catch_up_task_id, miss_era_worked_minutes, "
                        "miss_era_remaining_minutes, miss_era_estimated_minutes, "
                        "miss_era_entry_ids, authorize_instant "
                        "FROM task_occurrence_dispositions WHERE id = :id"
                    ),
                    {"id": disp_id},
                ).one()
                assert disp.resolution == "unresolved_held"
                assert disp.episode_key == "mig-episode-1"
                assert disp.bounds_snapshot == {"kept": "held"}
                assert disp.miss_reason_code == "occurrence_bounds_miss"
                assert disp.catch_up_task_id is None
                assert disp.miss_era_worked_minutes is None
                assert disp.miss_era_remaining_minutes is None
                assert disp.miss_era_estimated_minutes is None
                assert disp.miss_era_entry_ids is None
                assert disp.authorize_instant is None
                event = conn.execute(
                    text(
                        "SELECT event_type, payload FROM disposition_events "
                        "WHERE id = :id"
                    ),
                    {"id": event_id},
                ).one()
                assert event.event_type == "miss_detected"
                assert event.payload == {"kept": True}
                entry = conn.execute(
                    text(
                        "SELECT minutes_worked, remaining_minutes, task_id, owner_id "
                        "FROM task_progress_entries WHERE id = :id"
                    ),
                    {"id": entry_id},
                ).one()
                assert entry.minutes_worked == 40
                assert entry.remaining_minutes == 5
                assert entry.task_id == task_id
                assert entry.owner_id == owner_id
                membership = conn.execute(
                    text(
                        "SELECT count(*) FROM progress_epoch_membership "
                        "WHERE progress_entry_id = :id"
                    ),
                    {"id": entry_id},
                ).scalar()
                assert membership == 0
                tables = set(
                    conn.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public' AND table_name IN "
                            "('progress_epoch_membership', 'disposition_correction_audits')"
                        )
                    ).scalars()
                )
                assert tables == {
                    "progress_epoch_membership",
                    "disposition_correction_audits",
                }
                checks = set(
                    conn.execute(
                        text(
                            "SELECT conname FROM pg_constraint WHERE conname IN ("
                            "'task_occurrence_dispositions_recovered_implies_snapshot', "
                            "'task_occurrence_dispositions_catch_up_ne_task')"
                        )
                    ).scalars()
                )
                assert checks == {
                    "task_occurrence_dispositions_recovered_implies_snapshot",
                    "task_occurrence_dispositions_catch_up_ne_task",
                }
                trigger = conn.execute(
                    text(
                        "SELECT tgname FROM pg_trigger "
                        "WHERE tgname = 'disposition_correction_audits_append_only'"
                    )
                ).scalar()
                assert trigger == "disposition_correction_audits_append_only"
        finally:
            eng.dispose()
    finally:
        _drop_mig_db()

    db_session.expire_all()
    assert db_session.execute(text("SELECT current_database()")).scalar() == _REQUIRED_DB
    assert (
        db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        == "043_recovery_epoch"
    )


def test_a1_miss_era_ledger_snapshot_and_live_reset(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    logged = _log(client, task["id"], 25, 35)
    entry_id = logged["entry"]["id"]
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id)
    assert resp.status_code == 200, resp.text
    series = _task(db_session, task["id"])
    assert series.worked_minutes == 0
    assert series.remaining_minutes == 60
    assert placement_effort_minutes(series) == 60
    fresh = db_session.get(TaskOccurrenceDisposition, row.id)
    assert fresh is not None
    assert fresh.resolution == RESOLUTION_RECOVERED
    assert fresh.miss_era_worked_minutes == 25
    assert list(fresh.miss_era_entry_ids) == [entry_id]
    entries = _entries(db_session, series.id)
    assert sum(e.minutes_worked for e in entries) == 25
    assert all(e.task_id == series.id for e in entries)
    members = _memberships(db_session, series.id)
    assert {str(m.progress_entry_id) for m in members} == {entry_id}
    assert len(members) == len({m.progress_entry_id for m in members})
    catch = db_session.get(Task, fresh.catch_up_task_id)
    assert catch is not None and catch.id != series.id
    assert _entries(db_session, catch.id) == []


def test_a2_historical_correction_before_next_normal_log(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    logged = _log(client, task["id"], 25, 35)
    entry_id = logged["entry"]["id"]
    row = _hold(db_session, task["id"])
    recovered = _recover(client, task["id"], row.id)
    assert recovered.status_code == 200, recovered.text
    catch_id = uuid.UUID(recovered.json()["catch_up_task_id"])
    rev = _revision(client)
    snapshot = db_session.get(TaskOccurrenceDisposition, row.id)
    assert snapshot is not None
    ids_before = list(snapshot.miss_era_entry_ids)
    worked_before = snapshot.miss_era_worked_minutes
    correction = _correct(client, task["id"], entry_id)
    assert correction.status_code == 200, correction.text
    body = correction.json()
    assert body["replayed"] is False
    assert body["scheduling_revision"] == rev
    assert _revision(client) == rev
    new_id = body["entry"]["id"]
    assert body["entry"]["corrects_entry_id"] == entry_id
    db_session.expire_all()
    fresh = db_session.get(TaskOccurrenceDisposition, row.id)
    assert fresh is not None
    assert list(fresh.miss_era_entry_ids) == ids_before
    assert fresh.miss_era_worked_minutes == worked_before
    assert new_id not in list(fresh.miss_era_entry_ids)
    series = _task(db_session, task["id"])
    assert series.worked_minutes == 0
    assert series.remaining_minutes == 60
    assert placement_effort_minutes(series) == 60
    catch = db_session.get(Task, catch_id)
    assert catch is not None
    assert catch.worked_minutes == 0
    assert catch.remaining_minutes == 35
    assert _entries(db_session, catch.id) == []
    audits = (
        db_session.query(DispositionCorrectionAudit)
        .filter(DispositionCorrectionAudit.disposition_id == row.id)
        .all()
    )
    assert len(audits) == 1
    assert str(audits[0].target_entry_id) == entry_id
    assert str(audits[0].new_entry_id) == new_id
    member = (
        db_session.query(ProgressEpochMembership)
        .filter(ProgressEpochMembership.progress_entry_id == uuid.UUID(new_id))
        .one()
    )
    assert member.disposition_id == row.id
    assert member.task_id == series.id


def test_a2b_historical_correction_preserves_next_normal_live(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    logged = _log(client, task["id"], 25, 35)
    row = _hold(db_session, task["id"])
    recovered = _recover(client, task["id"], row.id)
    assert recovered.status_code == 200, recovered.text
    catch_id = uuid.UUID(recovered.json()["catch_up_task_id"])
    live = _log(client, task["id"], 10, 50)
    live_id = live["entry"]["id"]
    open_try = _correct(client, task["id"], live_id)
    assert open_try.status_code == 422, open_try.text
    assert open_try.json()["code"] == "HISTORICAL_CORRECTION_UNSUPPORTED"
    series = _task(db_session, task["id"])
    assert series.worked_minutes == 10
    assert series.remaining_minutes == 50
    assert placement_effort_minutes(series) == 50
    assert series.priority.value == "p1"
    correction = _correct(client, task["id"], logged["entry"]["id"], worked=8, remaining=40)
    assert correction.status_code == 200, correction.text
    series = _task(db_session, task["id"])
    assert series.worked_minutes == 10
    assert series.remaining_minutes == 50
    assert placement_effort_minutes(series) == 50
    assert series.priority.value == "p1"
    catch = db_session.get(Task, catch_id)
    assert catch is not None
    assert catch.worked_minutes == 0
    assert catch.remaining_minutes == 35
    assert _entries(db_session, catch.id) == []


def test_a2c_two_recoveries_correction_stays_in_first_epoch(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    first_log = _log(client, task["id"], 25, 35)
    first = _hold(db_session, task["id"])
    recovered = _recover(client, task["id"], first.id)
    assert recovered.status_code == 200, recovered.text
    first_catch = uuid.UUID(recovered.json()["catch_up_task_id"])
    between = _log(client, task["id"], 10, 50)
    # Next-normal window (Aug 18 09:00–11:00) is past once the clock moves to noon.
    later = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    _set_now(monkeypatch, later)
    second = _hold(db_session, task["id"])
    assert second.episode_key != first.episode_key
    again = _recover(
        client,
        task["id"],
        second.id,
        authorize_instant=_iso(later),
        catch_up_due_at=_iso(datetime(2026, 8, 19, 15, 0, tzinfo=UTC)),
        catch_up_start_no_earlier_at=_iso(datetime(2026, 8, 19, 14, 0, tzinfo=UTC)),
        catch_up_start_no_later_at=_iso(datetime(2026, 8, 19, 16, 0, tzinfo=UTC)),
        catch_up_deadline_at=_iso(datetime(2026, 8, 19, 16, 0, tzinfo=UTC)),
    )
    assert again.status_code == 200, again.text
    second_catch = uuid.UUID(again.json()["catch_up_task_id"])
    assert second_catch != first_catch
    db_session.expire_all()
    first_row = db_session.get(TaskOccurrenceDisposition, first.id)
    assert first_row is not None
    ids_before = list(first_row.miss_era_entry_ids)
    worked_before = first_row.miss_era_worked_minutes
    series = _task(db_session, task["id"])
    assert series.worked_minutes == 0
    assert series.remaining_minutes == 60
    live_before = (series.worked_minutes, series.remaining_minutes, series.priority.value)
    c1 = db_session.get(Task, first_catch)
    c2 = db_session.get(Task, second_catch)
    assert c1 is not None and c2 is not None
    catch_before = (
        (c1.worked_minutes, c1.remaining_minutes),
        (c2.worked_minutes, c2.remaining_minutes),
    )
    correction = _correct(client, task["id"], first_log["entry"]["id"])
    assert correction.status_code == 200, correction.text
    new_id = uuid.UUID(correction.json()["entry"]["id"])
    series = _task(db_session, task["id"])
    assert (series.worked_minutes, series.remaining_minutes, series.priority.value) == live_before
    assert placement_effort_minutes(series) == 60
    c1 = db_session.get(Task, first_catch)
    c2 = db_session.get(Task, second_catch)
    assert c1 is not None and c2 is not None
    assert (
        (c1.worked_minutes, c1.remaining_minutes),
        (c2.worked_minutes, c2.remaining_minutes),
    ) == catch_before
    first_row = db_session.get(TaskOccurrenceDisposition, first.id)
    assert first_row is not None
    assert list(first_row.miss_era_entry_ids) == ids_before
    assert first_row.miss_era_worked_minutes == worked_before
    chain = (
        db_session.query(ProgressEpochMembership)
        .filter(ProgressEpochMembership.progress_entry_id == new_id)
        .one()
    )
    assert chain.disposition_id == first.id
    second_ids = {
        m.progress_entry_id
        for m in _memberships(db_session, series.id)
        if m.disposition_id == second.id
    }
    first_ids = {
        m.progress_entry_id
        for m in _memberships(db_session, series.id)
        if m.disposition_id == first.id
    }
    assert uuid.UUID(between["entry"]["id"]) in second_ids
    assert uuid.UUID(first_log["entry"]["id"]) in first_ids
    assert new_id in first_ids
    assert first_ids.isdisjoint(second_ids)
    audits = (
        db_session.query(DispositionCorrectionAudit)
        .filter(DispositionCorrectionAudit.disposition_id == first.id)
        .all()
    )
    assert len(audits) == 1
    assert (
        db_session.query(DispositionCorrectionAudit)
        .filter(DispositionCorrectionAudit.disposition_id == second.id)
        .count()
        == 0
    )


def test_a3_blocks_fail_closed_and_clean_slate_places(
    client: TestClient, db_session: Session
) -> None:
    """Both C2 paths. Historical-block isolation stays EXCEEDS_SLICE — not proven."""
    _prepare(client, db_session)
    owner = _owner_id(client)

    pinned = _books(client, title=f"Pinned books {_uid()}")
    pin_row = _hold(db_session, pinned["id"])
    pin = ScheduledBlock(
        owner_id=owner,
        task_id=uuid.UUID(pinned["id"]),
        start_time=FIXED_NOW + timedelta(days=1),
        end_time=FIXED_NOW + timedelta(days=1, minutes=30),
        is_pinned=True,
    )
    db_session.add(pin)
    db_session.flush()
    pin_id = pin.id
    rejected_pin = _recover(client, pinned["id"], pin_row.id)
    assert rejected_pin.status_code == 422, rejected_pin.text
    assert rejected_pin.json()["code"] == "BLOCKS_PREVENT_NEXT_NORMAL"
    db_session.expire_all()
    still_pin = db_session.get(ScheduledBlock, pin_id)
    assert still_pin is not None
    assert still_pin.is_pinned is True
    assert still_pin.task_id == uuid.UUID(pinned["id"])
    assert db_session.get(TaskOccurrenceDisposition, pin_row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )
    assert _catch_up_named(db_session, pinned["title"]) == []

    past = _books(client, title=f"Past block books {_uid()}")
    past_row = _hold(db_session, past["id"])
    block = ScheduledBlock(
        owner_id=owner,
        task_id=uuid.UUID(past["id"]),
        start_time=FIXED_NOW - timedelta(days=1),
        end_time=FIXED_NOW - timedelta(days=1) + timedelta(minutes=30),
        is_pinned=False,
    )
    db_session.add(block)
    db_session.flush()
    block_id = block.id
    rejected_past = _recover(client, past["id"], past_row.id)
    assert rejected_past.status_code == 422, rejected_past.text
    assert rejected_past.json()["code"] == "BLOCKS_PREVENT_NEXT_NORMAL"
    db_session.expire_all()
    still_block = db_session.get(ScheduledBlock, block_id)
    assert still_block is not None
    assert still_block.is_pinned is False
    assert still_block.task_id == uuid.UUID(past["id"])
    assert _catch_up_named(db_session, past["title"]) == []

    clean = _books(client, title=f"Clean books {_uid()}")
    _log(client, clean["id"], 25, 35)
    clean_row = _hold(db_session, clean["id"])
    ok = _recover(client, clean["id"], clean_row.id)
    assert ok.status_code == 200, ok.text
    series = _task(db_session, clean["id"])
    assert series.worked_minutes == 0
    assert series.remaining_minutes == 60
    assert (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.task_id == series.id)
        .count()
        == 0
    )
    inputs = collect_inputs(db_session, owner, FIXED_NOW)
    result = calculate(db_session, inputs)
    db_session.flush()
    outcome = next(item for item in result.outcomes if item.task_id == series.id)
    assert outcome.placed_minutes == 60, [
        (fact.code, fact.params) for fact in outcome.reason_facts
    ]
    assert outcome.pinned_minutes == 0
    assert (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.task_id == series.id)
        .count()
        == 0
    )


def test_a4_no_successor_rejects(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Ended {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=DAILY;INTERVAL=1",
        is_fixed=True,
        ends_on="2026-08-10",
    )
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    due_before = _task(db_session, task["id"]).due_at
    resp = _recover(client, task["id"], row.id)
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "RECURRENCE_NO_SUCCESSOR"
    series = _task(db_session, task["id"])
    assert series.due_at == due_before
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )
    assert _revision(client) == rev
    assert _catch_up_named(db_session, task["title"]) == []


def test_a5_spring_gap_bound_fail_closed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    now = datetime(2026, 3, 8, 13, 0, tzinfo=UTC)
    _set_now(monkeypatch, now)
    due = datetime(2026, 3, 7, 17, 0, tzinfo=UTC)  # 12:00 EST
    latest = datetime(2026, 3, 7, 7, 30, tzinfo=UTC)  # 02:30 EST → rolls into the gap
    task = _series(
        client,
        title=f"Gap bound {_uid()}",
        due=due,
        latest=latest,
        rrule="FREQ=DAILY;INTERVAL=1",
        is_fixed=True,
        tz="America/New_York",
    )
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    before = _task(db_session, task["id"])
    due_before, latest_before = before.due_at, before.start_no_later_at
    resp = _recover(client, task["id"], row.id, authorize_instant=_iso(now))
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert body["field"] == "start_no_later_at"
    assert body["kind"] == "gap"
    series = _task(db_session, task["id"])
    assert series.due_at == due_before
    assert series.start_no_later_at == latest_before
    assert _revision(client) == rev
    assert _catch_up_named(db_session, task["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )


def test_a5b_successor_due_gap_and_fold_fail_closed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)

    gap_now = datetime(2026, 3, 7, 18, 0, tzinfo=UTC)
    _set_now(monkeypatch, gap_now)
    gap_due = datetime(2026, 3, 7, 7, 30, tzinfo=UTC)  # 02:30 EST; next wall is the gap
    gap = _series(
        client,
        title=f"Gap due {_uid()}",
        due=gap_due,
        rrule="FREQ=DAILY;INTERVAL=1",
        is_fixed=True,
        tz="America/New_York",
    )
    gap_row = _hold(db_session, gap["id"])
    gap_rev = _revision(client)
    gap_due_before = _task(db_session, gap["id"]).due_at
    gap_resp = _recover(client, gap["id"], gap_row.id, authorize_instant=_iso(gap_now))
    assert gap_resp.status_code == 422, gap_resp.text
    gap_body = gap_resp.json()
    assert gap_body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert gap_body["field"] == "due_at"
    assert gap_body["kind"] == "gap"
    assert _task(db_session, gap["id"]).due_at == gap_due_before
    assert _revision(client) == gap_rev
    assert _catch_up_named(db_session, gap["title"]) == []

    fold_now = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)
    _set_now(monkeypatch, fold_now)
    fold_due = datetime(2026, 10, 31, 5, 30, tzinfo=UTC)  # 01:30 EDT; next wall is the fold
    fold = _series(
        client,
        title=f"Fold due {_uid()}",
        due=fold_due,
        rrule="FREQ=DAILY;INTERVAL=1",
        is_fixed=True,
        tz="America/New_York",
    )
    fold_row = _hold(db_session, fold["id"])
    fold_rev = _revision(client)
    fold_resp = _recover(client, fold["id"], fold_row.id, authorize_instant=_iso(fold_now))
    assert fold_resp.status_code == 422, fold_resp.text
    fold_body = fold_resp.json()
    assert fold_body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert fold_body["field"] == "due_at"
    assert fold_body["kind"] == "fold"
    assert _revision(client) == fold_rev
    assert _catch_up_named(db_session, fold["title"]) == []


def _catch_after(now: datetime) -> dict:
    due = now + timedelta(days=3)
    return {
        "catch_up_due_at": _iso(due),
        "catch_up_start_no_earlier_at": _iso(due - timedelta(hours=1)),
        "catch_up_start_no_later_at": _iso(due + timedelta(hours=3)),
        "catch_up_deadline_at": _iso(due + timedelta(hours=4)),
    }


def test_a5c_explicit_byhour_dst_gap_and_fold_fail_closed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RRULE wall is the indeterminate time; previous due is a real clock.

    Replacing BYHOUR/BYMINUTE with the previous due's clock would land on a
    valid civil time and hide the gap or fold. Recovery must reject.
    """
    _prepare(client, db_session)

    gap_now = datetime(2026, 3, 7, 18, 0, tzinfo=UTC)
    _set_now(monkeypatch, gap_now)
    # 09:00 EST exists. BYHOUR=2;BYMINUTE=30 on 2026-03-08 does not.
    gap_due = datetime(2026, 3, 7, 14, 0, tzinfo=UTC)
    gap = _series(
        client,
        title=f"Explicit gap {_uid()}",
        due=gap_due,
        rrule="FREQ=DAILY;BYHOUR=2;BYMINUTE=30",
        is_fixed=False,
        tz="America/New_York",
    )
    gap_row = _hold(db_session, gap["id"])
    gap_rev = _revision(client)
    gap_due_before = _task(db_session, gap["id"]).due_at
    gap_resp = _recover(
        client,
        gap["id"],
        gap_row.id,
        authorize_instant=_iso(gap_now),
        **_catch_after(gap_now),
    )
    assert gap_resp.status_code == 422, gap_resp.text
    gap_body = gap_resp.json()
    assert gap_body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert gap_body["field"] == "due_at"
    assert gap_body["kind"] == "gap"
    assert _task(db_session, gap["id"]).due_at == gap_due_before
    assert _revision(client) == gap_rev
    assert _catch_up_named(db_session, gap["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, gap_row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )

    fold_now = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    _set_now(monkeypatch, fold_now)
    # 12:00 EDT exists. BYHOUR=1;BYMINUTE=30 on 2026-11-01 is the fold.
    fold_due = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)
    fold = _series(
        client,
        title=f"Explicit fold {_uid()}",
        due=fold_due,
        rrule="FREQ=DAILY;BYHOUR=1;BYMINUTE=30",
        is_fixed=False,
        tz="America/New_York",
    )
    fold_row = _hold(db_session, fold["id"])
    fold_rev = _revision(client)
    fold_due_before = _task(db_session, fold["id"]).due_at
    fold_resp = _recover(
        client,
        fold["id"],
        fold_row.id,
        authorize_instant=_iso(fold_now),
        **_catch_after(fold_now),
    )
    assert fold_resp.status_code == 422, fold_resp.text
    fold_body = fold_resp.json()
    assert fold_body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert fold_body["field"] == "due_at"
    assert fold_body["kind"] == "fold"
    assert _task(db_session, fold["id"]).due_at == fold_due_before
    assert _revision(client) == fold_rev
    assert _catch_up_named(db_session, fold["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, fold_row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )


def test_a5d_multi_byhour_gap_and_fold_fail_closed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multi-valued BYHOUR: the selected occurrence is the indeterminate wall.

    The other hour is listed first and is a real civil time. Rewriting to that
    first value would hide the gap or fold. Recovery must reject the selected
    occurrence, and the series due must stay on the miss.
    """
    _prepare(client, db_session)

    gap_now = datetime(2026, 3, 7, 23, 0, tzinfo=UTC)  # 18:00 EST, after 17:30
    _set_now(monkeypatch, gap_now)
    # 09:00 EST exists. Next selected wall is 02:30 on 2026-03-08 (the gap),
    # not 17:30. BYHOUR lists 17 first so a first-value rewrite would succeed.
    gap_due = datetime(2026, 3, 7, 14, 0, tzinfo=UTC)
    gap = _series(
        client,
        title=f"Multi gap {_uid()}",
        due=gap_due,
        rrule="FREQ=DAILY;BYHOUR=17,2;BYMINUTE=30",
        is_fixed=False,
        tz="America/New_York",
    )
    gap_row = _hold(db_session, gap["id"])
    gap_rev = _revision(client)
    gap_due_before = _task(db_session, gap["id"]).due_at
    gap_resp = _recover(
        client,
        gap["id"],
        gap_row.id,
        authorize_instant=_iso(gap_now),
        **_catch_after(gap_now),
    )
    assert gap_resp.status_code == 422, gap_resp.text
    gap_body = gap_resp.json()
    assert gap_body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert gap_body["field"] == "due_at"
    assert gap_body["kind"] == "gap"
    assert _task(db_session, gap["id"]).due_at == gap_due_before
    assert _revision(client) == gap_rev
    assert _catch_up_named(db_session, gap["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, gap_row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )

    fold_now = datetime(2026, 10, 31, 22, 0, tzinfo=UTC)  # 18:00 EDT, after 17:30
    _set_now(monkeypatch, fold_now)
    # 12:00 EDT exists. Next selected wall is 01:30 on 2026-11-01 (the fold),
    # not 17:30. BYHOUR lists 17 first.
    fold_due = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)
    fold = _series(
        client,
        title=f"Multi fold {_uid()}",
        due=fold_due,
        rrule="FREQ=DAILY;BYHOUR=17,1;BYMINUTE=30",
        is_fixed=False,
        tz="America/New_York",
    )
    fold_row = _hold(db_session, fold["id"])
    fold_rev = _revision(client)
    fold_due_before = _task(db_session, fold["id"]).due_at
    fold_resp = _recover(
        client,
        fold["id"],
        fold_row.id,
        authorize_instant=_iso(fold_now),
        **_catch_after(fold_now),
    )
    assert fold_resp.status_code == 422, fold_resp.text
    fold_body = fold_resp.json()
    assert fold_body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert fold_body["field"] == "due_at"
    assert fold_body["kind"] == "fold"
    assert _task(db_session, fold["id"]).due_at == fold_due_before
    assert _revision(client) == fold_rev
    assert _catch_up_named(db_session, fold["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, fold_row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )


def test_a5e_multi_byhour_keeps_legitimate_selected_occurrence(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do not replace the occurrence next_due_at selected with another BYHOUR.

    9 listed first still lands 17:00 after noon. 17 listed first still lands
    09:00 when that is the successor. On a spring-gap day and a fall-fold day,
    a selected 17:00 stays 17:00 — the other listed hour is not substituted
    and the day is not rejected.
    """
    _prepare(client, db_session)
    _set_now(monkeypatch, datetime(2026, 8, 11, 12, 0, tzinfo=UTC))
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    later = _series(
        client,
        title=f"BYHOUR 9,17 {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=DAILY;BYHOUR=9,17",
        is_fixed=False,
    )
    later_row = _hold(db_session, later["id"])
    _assert_byhour_17_landing(client, db_session, later, later_row.id)

    early_now = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
    _set_now(monkeypatch, early_now)
    early = _series(
        client,
        title=f"BYHOUR 17,9 {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=DAILY;BYHOUR=17,9",
        is_fixed=False,
    )
    early_row = _hold(db_session, early["id"])
    early_resp = _recover(
        client,
        early["id"],
        early_row.id,
        authorize_instant=_iso(early_now),
    )
    assert early_resp.status_code == 200, early_resp.text
    assert _task(db_session, early["id"]).due_at == datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
    early_stored = db_session.get(TaskOccurrenceDisposition, early_row.id)
    assert early_stored is not None
    early_recovered = [
        event for event in early_stored.events if event.event_type == EVENT_RECOVERED
    ]
    assert len(early_recovered) == 1
    assert early_recovered[0].payload["accept_past"] is False

    gap_now = datetime(2026, 3, 8, 14, 0, tzinfo=UTC)  # 10:00 EDT, after the gap
    _set_now(monkeypatch, gap_now)
    gap_due = datetime(2026, 3, 7, 22, 0, tzinfo=UTC)  # 17:00 EST
    gap_earliest, gap_latest, gap_deadline = _window_on(gap_due)
    gap_legit = _series(
        client,
        title=f"Gap day 17 {_uid()}",
        due=gap_due,
        earliest=gap_earliest,
        latest=gap_latest,
        deadline=gap_deadline,
        rrule="FREQ=DAILY;BYHOUR=2,17",
        is_fixed=False,
        tz="America/New_York",
    )
    gap_legit_row = _hold(db_session, gap_legit["id"])
    gap_legit_resp = _recover(
        client,
        gap_legit["id"],
        gap_legit_row.id,
        authorize_instant=_iso(gap_now),
        **_catch_after(gap_now),
    )
    assert gap_legit_resp.status_code == 200, gap_legit_resp.text
    assert _task(db_session, gap_legit["id"]).due_at == datetime(
        2026, 3, 8, 21, 0, tzinfo=UTC
    )

    fold_now = datetime(2026, 11, 1, 15, 0, tzinfo=UTC)  # 10:00 EST, after the fold
    _set_now(monkeypatch, fold_now)
    fold_due = datetime(2026, 10, 31, 21, 0, tzinfo=UTC)  # 17:00 EDT
    fold_earliest, fold_latest, fold_deadline = _window_on(fold_due)
    fold_legit = _series(
        client,
        title=f"Fold day 17 {_uid()}",
        due=fold_due,
        earliest=fold_earliest,
        latest=fold_latest,
        deadline=fold_deadline,
        rrule="FREQ=DAILY;BYHOUR=1,17",
        is_fixed=False,
        tz="America/New_York",
    )
    fold_legit_row = _hold(db_session, fold_legit["id"])
    fold_legit_resp = _recover(
        client,
        fold_legit["id"],
        fold_legit_row.id,
        authorize_instant=_iso(fold_now),
        **_catch_after(fold_now),
    )
    assert fold_legit_resp.status_code == 200, fold_legit_resp.text
    assert _task(db_session, fold_legit["id"]).due_at == datetime(
        2026, 11, 1, 22, 0, tzinfo=UTC
    )


def test_a6_fall_fold_bound_fail_closed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    now = datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
    _set_now(monkeypatch, now)
    due = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)  # 12:00 EDT
    latest = datetime(2026, 10, 31, 5, 30, tzinfo=UTC)  # 01:30 EDT → rolls into the fold
    task = _series(
        client,
        title=f"Fold bound {_uid()}",
        due=due,
        latest=latest,
        rrule="FREQ=DAILY;INTERVAL=1",
        is_fixed=True,
        tz="America/New_York",
    )
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    before_latest = _task(db_session, task["id"]).start_no_later_at
    resp = _recover(
        client,
        task["id"],
        row.id,
        authorize_instant=_iso(now),
        catch_up_due_at=_iso(datetime(2026, 11, 2, 16, 0, tzinfo=UTC)),
        catch_up_start_no_earlier_at=_iso(datetime(2026, 11, 2, 15, 0, tzinfo=UTC)),
        catch_up_start_no_later_at=_iso(datetime(2026, 11, 2, 18, 0, tzinfo=UTC)),
        catch_up_deadline_at=_iso(datetime(2026, 11, 2, 20, 0, tzinfo=UTC)),
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    assert body["field"] == "start_no_later_at"
    assert body["kind"] == "fold"
    assert _task(db_session, task["id"]).start_no_later_at == before_latest
    assert _revision(client) == rev
    assert _catch_up_named(db_session, task["title"]) == []


def _purge_probe_users() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        db.execute(
            text(
                "DELETE FROM task_occurrence_dispositions WHERE owner_id IN "
                "(SELECT id FROM users WHERE email LIKE :pattern)"
            ),
            {"pattern": _PROBE_EMAIL_LIKE},
        )
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


def _commit_recurring_probe(
    *,
    worked_minutes: int = 0,
    remaining_minutes: int = 60,
    with_progress: bool = False,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, int, str]:
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"renee-t2rec-{token}@example.com",
            username=f"renee-t2rec-{token}",
            display_name="Renee T2-REC probe",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        if owner_scheduling_lock_key(user.id) == owner_scheduling_lock_key(BOOTSTRAP_USER_ID):
            raise RuntimeError("probe owner collided with bootstrap scheduling lock key")
        settings = UserSettings(
            owner_id=user.id,
            timezone="UTC",
            inter_block_buffer_minutes=0,
            upcoming_horizon_days=14,
            default_schedule_style=ScheduleStyle.standalone,
            scheduling_revision=3,
        )
        db.add(settings)
        project = Project(owner_id=user.id, title=f"renee-t2rec-{token}")
        db.add(project)
        db.flush()
        title = f"renee-t2rec-series-{token}"
        task = Task(
            owner_id=user.id,
            project_id=project.id,
            title=title,
            estimated_duration_minutes=60,
            worked_minutes=worked_minutes,
            remaining_minutes=remaining_minutes,
            schedule_style=ScheduleStyle.standalone,
            due_at=_BOOKS_DUE,
            start_no_earlier_at=_BOOKS_EARLIEST,
            start_no_later_at=_BOOKS_LATEST,
            deadline_at=_BOOKS_DEADLINE,
        )
        db.add(task)
        db.flush()
        from app.models import RecurrenceRule

        db.add(
            RecurrenceRule(
                owner_id=user.id,
                task_id=task.id,
                rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
                is_fixed=True,
                timezone="UTC",
            )
        )
        disp = TaskOccurrenceDisposition(
            owner_id=user.id,
            task_id=task.id,
            episode_key=episode_key_for_task(task),
            resolution=RESOLUTION_UNRESOLVED_HELD,
            bounds_snapshot={"probe": True},
            miss_reason_code="occurrence_bounds_miss",
        )
        db.add(disp)
        if with_progress:
            if worked_minutes <= 0:
                raise RuntimeError("progress seed requires positive worked_minutes")
            db.add(
                TaskProgressEntry(
                    owner_id=user.id,
                    task_id=task.id,
                    idempotency_key=uuid.uuid4(),
                    intent_hash="c" * 64,
                    minutes_worked=worked_minutes,
                    remaining_minutes=remaining_minutes,
                )
            )
        db.commit()
        return user.id, task.id, disp.id, 3, title
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _probe_recover_kwargs(owner_id, task_id, disp_id, rev):
    return dict(
        owner_id=owner_id,
        task_id=task_id,
        disposition_id=disp_id,
        expected_revision=rev,
        authorize_instant=FIXED_NOW,
        catch_up_due_at=_CATCH_DUE,
        catch_up_start_no_earlier_at=_CATCH_EARLIEST,
        catch_up_start_no_later_at=_CATCH_LATEST,
        catch_up_deadline_at=_CATCH_DEADLINE,
    )


def test_a6b_separate_session_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Separate SessionLocal sessions, plus a two-thread start-barrier race.

    The barrier releases both workers together. That is one race shape, not
    an exhaustive interleaving proof.

    The recover-then-explicit-``rollback()`` branch shows an uncommitted
    recover does not survive ``session.rollback()``. It is not evidence of a
    failure injected after series reset, terminal disposition, event, and
    revision writes. That case is ``test_a11b_late_flush_failure_rolls_back``.
    """
    _patch_schedule_clock(monkeypatch)
    monkeypatch.setattr("app.services.occurrence_disposition.utc_now", lambda: FIXED_NOW)
    _purge_probe_users()
    try:
        owner_id, task_id, disp_id, rev, title = _commit_recurring_probe()
        stale = SessionLocal()
        try:
            settings = lock_owner_scheduling(stale, owner_id)
            increment_scheduling_revision(stale, settings)
            stale.commit()
        finally:
            stale.close()
        denied = SessionLocal()
        try:
            from app.api.errors import ApiError

            with pytest.raises(ApiError) as caught:
                recover_held(denied, **_probe_recover_kwargs(owner_id, task_id, disp_id, rev))
                denied.commit()
            assert caught.value.content["code"] == "SCHEDULING_REVISION_CONFLICT"
            denied.rollback()
        finally:
            denied.close()
        read = SessionLocal()
        try:
            row = read.get(TaskOccurrenceDisposition, disp_id)
            assert row is not None and row.resolution == RESOLUTION_UNRESOLVED_HELD
            assert (
                read.query(Task).filter(Task.title == f"{title} (catch-up)").count() == 0
            )
        finally:
            read.close()
        _purge_probe_users()

        owner_id, task_id, disp_id, rev, title = _commit_recurring_probe()
        rolled = SessionLocal()
        try:
            recover_held(rolled, **_probe_recover_kwargs(owner_id, task_id, disp_id, rev))
            rolled.rollback()
        finally:
            rolled.close()
        read = SessionLocal()
        try:
            row = read.get(TaskOccurrenceDisposition, disp_id)
            assert row is not None and row.resolution == RESOLUTION_UNRESOLVED_HELD
            settings = read.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
            assert int(settings.scheduling_revision) == rev
        finally:
            read.close()
        committed = SessionLocal()
        try:
            result = recover_held(
                committed, **_probe_recover_kwargs(owner_id, task_id, disp_id, rev)
            )
            committed.commit()
            assert result.replayed is False
        finally:
            committed.close()
        _purge_probe_users()

        def _race(kind: str) -> None:
            from app.api.errors import ApiError

            o, t, d, r, name = _commit_recurring_probe()
            barrier = threading.Barrier(2)
            results: list[tuple[str, str]] = []

            def worker(action: str) -> None:
                db = SessionLocal()
                try:
                    barrier.wait(timeout=15)
                    if action == "recover":
                        recover_held(db, **_probe_recover_kwargs(o, t, d, r))
                    elif action == "release":
                        release_held(
                            db,
                            owner_id=o,
                            task_id=t,
                            disposition_id=d,
                            expected_revision=r,
                            bounds_updates={
                                "start_no_earlier_at": datetime(2026, 8, 20, 14, 0, tzinfo=UTC),
                                "start_no_later_at": datetime(2026, 8, 20, 18, 0, tzinfo=UTC),
                                "deadline_at": datetime(2026, 8, 20, 20, 0, tzinfo=UTC),
                            },
                        )
                    else:
                        skip_held(
                            db,
                            owner_id=o,
                            task_id=t,
                            disposition_id=d,
                            expected_revision=r,
                        )
                    db.commit()
                    results.append((action, "ok"))
                except ApiError as exc:
                    db.rollback()
                    results.append((action, str(exc.content.get("code"))))
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    results.append((action, type(exc).__name__))
                finally:
                    db.close()

            other = {"recover": "recover", "release": "release", "skip": "skip"}[kind]
            first = "recover"
            threads = [
                threading.Thread(target=worker, args=(first,)),
                threading.Thread(target=worker, args=(other,)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)
            assert len(results) == 2, results
            oks = [item for item in results if item[1] == "ok"]
            assert len(oks) == 1, results
            assert results  # the loser is 409-class
            loser = next(item for item in results if item[1] != "ok")
            assert loser[1] in {"CONFLICT_TERMINAL", "SCHEDULING_REVISION_CONFLICT"}, results
            check = SessionLocal()
            try:
                row = check.get(TaskOccurrenceDisposition, d)
                assert row is not None
                catches = check.query(Task).filter(Task.title == f"{name} (catch-up)").count()
                if oks[0][0] == "recover":
                    assert row.resolution == RESOLUTION_RECOVERED
                    assert catches == 1
                elif oks[0][0] == "release":
                    assert row.resolution == RESOLUTION_RELEASED
                    assert catches == 0
                else:
                    assert row.resolution == RESOLUTION_SKIPPED
                    assert catches == 0
                settings = (
                    check.query(UserSettings).filter(UserSettings.owner_id == o).one()
                )
                # Skip is the existing no-bump terminal. Recover and release each bump once.
                expected_rev = r if oks[0][0] == "skip" else r + 1
                assert int(settings.scheduling_revision) == expected_rev
            finally:
                check.close()

        _race("recover")
        _race("release")
        _race("skip")
    finally:
        _purge_probe_users()


def test_a7_fixed_past_blocked_until_choice(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Fixed past {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=True,
    )
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    due_before = _task(db_session, task["id"]).due_at
    blocked = _recover(client, task["id"], row.id)
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "FIXED_PAST_REQUIRES_CHOICE"
    assert _task(db_session, task["id"]).due_at == due_before
    assert _revision(client) == rev
    aborted = _recover(client, task["id"], row.id, abort=True)
    assert aborted.status_code == 422, aborted.text
    assert aborted.json()["code"] == "RECOVERY_ABORTED"
    assert _task(db_session, task["id"]).due_at == due_before
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )
    assert _catch_up_named(db_session, task["title"]) == []
    assert _revision(client) == rev


def test_a7b_future_target_expired_latest_rejects(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 8, 4, 15, 0, tzinfo=UTC)
    task = _series(
        client,
        title=f"Expired latest {_uid()}",
        due=due,
        earliest=datetime(2026, 8, 4, 9, 0, tzinfo=UTC),
        latest=datetime(2026, 8, 4, 10, 0, tzinfo=UTC),
        deadline=datetime(2026, 8, 4, 18, 0, tzinfo=UTC),
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=True,
    )
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    due_before = _task(db_session, task["id"]).due_at
    resp = _recover(client, task["id"], row.id, accept_past_ack=True)
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "BOUNDS_STILL_MISSED"
    assert _task(db_session, task["id"]).due_at == due_before
    assert _revision(client) == rev
    assert _catch_up_named(db_session, task["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )


def test_a8_accept_past_one_catch_up(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Accept past {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=True,
    )
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id, accept_past_ack=True)
    assert resp.status_code == 200, resp.text
    series = _task(db_session, task["id"])
    assert series.due_at == datetime(2026, 7, 21, 9, 0, tzinfo=UTC)
    catches = _catch_up_named(db_session, task["title"])
    assert len(catches) == 1
    assert catches[0].id != series.id
    recovered = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == series.id)
        .all()
    )
    assert len(recovered) == 1
    assert recovered[0].resolution == RESOLUTION_RECOVERED


def test_a8b_accept_past_preview_may_rehold(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Rehold {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=True,
    )
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id, accept_past_ack=True)
    assert resp.status_code == 200, resp.text
    catch_id = uuid.UUID(resp.json()["catch_up_task_id"])
    owner = _owner_id(client)
    before_disp = db_session.query(TaskOccurrenceDisposition).count()
    inputs = collect_inputs(db_session, owner, FIXED_NOW)
    calculated = calculate(db_session, inputs)
    db_session.flush()
    assert db_session.query(TaskOccurrenceDisposition).count() == before_disp
    series_id = uuid.UUID(task["id"])
    outcome = next(item for item in calculated.outcomes if item.task_id == series_id)
    assert any(fact.code == "occurrence_bounds_miss" for fact in outcome.reason_facts)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready", preview
    db_session.expire_all()
    rows = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == series_id)
        .all()
    )
    assert len(_catch_up_named(db_session, task["title"])) == 1
    fresh_catch = db_session.get(Task, catch_id)
    assert fresh_catch is not None and fresh_catch.id == catch_id
    new_holds = [item for item in rows if item.resolution == RESOLUTION_UNRESOLVED_HELD]
    assert len(new_holds) == 1
    assert new_holds[0].episode_key != row.episode_key
    assert new_holds[0].catch_up_task_id is None
    recovered = [item for item in rows if item.id == row.id]
    assert recovered[0].resolution == RESOLUTION_RECOVERED
    assert recovered[0].catch_up_task_id == catch_id


def test_a9_step_further_one_catch_up_full_gate(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Step further {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=True,
    )
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id, step_count=4)
    assert resp.status_code == 200, resp.text
    series = _task(db_session, task["id"])
    assert series.due_at == _AUG18
    assert series.start_no_later_at is not None
    assert series.start_no_later_at > FIXED_NOW
    assert len(_catch_up_named(db_session, task["title"])) == 1


def test_a10_completion_anchored_skips_intermediates(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Anchored {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=False,
    )
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id, authorize_instant=_iso(FIXED_NOW))
    assert resp.status_code == 200, resp.text
    series = _task(db_session, task["id"])
    assert series.due_at == _AUG18
    assert len(_catch_up_named(db_session, task["title"])) == 1
    assert (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == series.id)
        .count()
        == 1
    )


def test_a10b_authorize_instant_not_shifted_by_later_now(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    reviewed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    task = _series(
        client,
        title=f"Stable anchor {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=DAILY;INTERVAL=1",
        is_fixed=False,
    )
    row = _hold(db_session, task["id"])
    # Wall clock moved past the reviewed Tuesday target. Recomputing from now
    # would land Wednesday Aug 12; commit must not take that later slot.
    _set_now(monkeypatch, datetime(2026, 8, 11, 12, 0, tzinfo=UTC))
    shifted = _recover(client, task["id"], row.id, authorize_instant=_iso(reviewed))
    assert shifted.status_code == 422, shifted.text
    assert shifted.json()["code"] == "BOUNDS_STILL_MISSED"
    assert _task(db_session, task["id"]).due_at == due
    assert _catch_up_named(db_session, task["title"]) == []

    kept = _series(
        client,
        title=f"Bound instant {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=DAILY;INTERVAL=1",
        is_fixed=False,
    )
    kept_row = _hold(db_session, kept["id"])
    delayed_now = datetime(2026, 8, 10, 18, 0, tzinfo=UTC)
    _set_now(monkeypatch, delayed_now)
    ok = _recover(client, kept["id"], kept_row.id, authorize_instant=_iso(reviewed))
    assert ok.status_code == 200, ok.text
    series = _task(db_session, kept["id"])
    assert series.due_at == datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
    stored = db_session.get(TaskOccurrenceDisposition, kept_row.id)
    assert stored is not None
    assert stored.authorize_instant == reviewed


def _assert_byhour_17_landing(
    client: TestClient, db_session: Session, task: dict, row_id: uuid.UUID
) -> None:
    expected = datetime(2026, 8, 11, 17, 0, tzinfo=UTC)
    resp = _recover(
        client,
        task["id"],
        row_id,
        authorize_instant=_iso(datetime(2026, 8, 11, 12, 0, tzinfo=UTC)),
    )
    assert resp.status_code == 200, resp.text
    series = _task(db_session, task["id"])
    assert series.due_at == expected
    stored = db_session.get(TaskOccurrenceDisposition, row_id)
    assert stored is not None
    recovered = [event for event in stored.events if event.event_type == EVENT_RECOVERED]
    assert len(recovered) == 1
    assert recovered[0].payload["accept_past"] is False
    assert len(_catch_up_named(db_session, task["title"])) == 1


def test_a10c_dex_byhour_boundless_keeps_rule_time(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dex probe: FREQ=DAILY;BYHOUR=17, no ends_on, completion-anchored UTC.

    Previous due Aug 10 09:00, authorize/now Aug 11 12:00. Next-normal due is
    Aug 11 17:00. No accept_past_ack.
    """
    _prepare(client, db_session)
    _set_now(monkeypatch, datetime(2026, 8, 11, 12, 0, tzinfo=UTC))
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"BYHOUR boundless {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=DAILY;BYHOUR=17",
        is_fixed=False,
    )
    row = _hold(db_session, task["id"])
    _assert_byhour_17_landing(client, db_session, task, row.id)


def test_a10d_byhour_open_frame_no_ends_on(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Open frame: starts_on set, ends_on omitted. Same BYHOUR=17 landing."""
    _prepare(client, db_session)
    _set_now(monkeypatch, datetime(2026, 8, 11, 12, 0, tzinfo=UTC))
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"BYHOUR open frame {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=DAILY;BYHOUR=17",
        is_fixed=False,
        starts_on="2026-08-01",
    )
    row = _hold(db_session, task["id"])
    _assert_byhour_17_landing(client, db_session, task, row.id)


def _assert_selected_civil_landing(
    client: TestClient,
    db_session: Session,
    task: dict,
    row_id: uuid.UUID,
    *,
    authorize: datetime,
    expected: datetime,
) -> None:
    resp = _recover(
        client,
        task["id"],
        row_id,
        authorize_instant=_iso(authorize),
    )
    assert resp.status_code == 200, resp.text
    series = _task(db_session, task["id"])
    assert series.due_at == expected
    stored = db_session.get(TaskOccurrenceDisposition, row_id)
    assert stored is not None
    recovered = [event for event in stored.events if event.event_type == EVENT_RECOVERED]
    assert len(recovered) == 1
    assert recovered[0].payload["accept_past"] is False
    assert len(_catch_up_named(db_session, task["title"])) == 1


def test_a10e_dex_hourly_keeps_selected_occurrence(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dex probe: FREQ=HOURLY, no BY*, completion-anchored UTC.

    Previous due Aug 10 09:00, authorize/now Aug 11 12:00. Next-normal is
    Aug 11 13:00. A previous_due H/M/S rewrite would land 09:00 and then
    BOUNDS_STILL_MISSED. No accept_past_ack.
    """
    _prepare(client, db_session)
    now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    _set_now(monkeypatch, now)
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Hourly {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=HOURLY",
        is_fixed=False,
    )
    row = _hold(db_session, task["id"])
    _assert_selected_civil_landing(
        client,
        db_session,
        task,
        row.id,
        authorize=now,
        expected=datetime(2026, 8, 11, 13, 0, tzinfo=UTC),
    )


def test_a10f_dex_minutely_interval_30_keeps_selected_occurrence(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dex probe: FREQ=MINUTELY;INTERVAL=30, no BY*, completion-anchored UTC.

    Previous due Aug 10 09:00, authorize/now Aug 11 12:00. Next-normal is
    Aug 11 12:30, not 09:00 and not BOUNDS_STILL_MISSED from a clock rewrite.
    """
    _prepare(client, db_session)
    now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    _set_now(monkeypatch, now)
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"Minutely {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=MINUTELY;INTERVAL=30",
        is_fixed=False,
    )
    row = _hold(db_session, task["id"])
    _assert_selected_civil_landing(
        client,
        db_session,
        task,
        row.id,
        authorize=now,
        expected=datetime(2026, 8, 11, 12, 30, tzinfo=UTC),
    )


def test_a11_gate_failure_rolls_back_nested_savepoint(
    client: TestClient, db_session: Session
) -> None:
    """Early catch-up usable-dates gate (BOUNDS_STILL_MISSED).

    The past catch-up window fails before series reset, terminal disposition,
    RECOVERED event, and revision bump. A clean task/ledger afterward shows
    that earlier snapshot/catch-up work did not commit. It does not prove
    rollback of those later writes. See test_a11b_late_flush_failure_rolls_back.
    """
    _prepare(client, db_session)
    task = _books(client)
    _log(client, task["id"], 25, 35)
    row = _hold(db_session, task["id"])
    series = _task(db_session, task["id"])
    before = (
        series.due_at,
        series.worked_minutes,
        series.remaining_minutes,
        series.start_no_later_at,
        series.deadline_at,
    )
    rev = _revision(client)
    members_before = len(_memberships(db_session, series.id))
    resp = _recover(
        client,
        task["id"],
        row.id,
        catch_up_due_at=_iso(FIXED_NOW - timedelta(hours=3)),
        catch_up_start_no_earlier_at=_iso(FIXED_NOW - timedelta(hours=4)),
        catch_up_start_no_later_at=_iso(FIXED_NOW - timedelta(hours=2)),
        catch_up_deadline_at=_iso(FIXED_NOW - timedelta(hours=1)),
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "BOUNDS_STILL_MISSED"
    series = _task(db_session, task["id"])
    assert (
        series.due_at,
        series.worked_minutes,
        series.remaining_minutes,
        series.start_no_later_at,
        series.deadline_at,
    ) == before
    fresh = db_session.get(TaskOccurrenceDisposition, row.id)
    assert fresh is not None
    assert fresh.resolution == RESOLUTION_UNRESOLVED_HELD
    assert fresh.catch_up_task_id is None
    assert not any(event.event_type == EVENT_RECOVERED for event in fresh.events)
    assert _revision(client) == rev
    assert len(_memberships(db_session, series.id)) == members_before
    assert _catch_up_named(db_session, task["title"]) == []


def test_a11b_late_flush_failure_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject failure after series reset, terminal disposition, event, and revision.

    Monkeypatch ``_recover_held_final_flush`` (the nested-savepoint boundary
    after those writes). The same session observes the writes; a fresh
    SessionLocal does not.
    """
    from app.services.occurrence_disposition import _recover_held_final_flush

    _patch_schedule_clock(monkeypatch)
    monkeypatch.setattr("app.services.occurrence_disposition.utc_now", lambda: FIXED_NOW)
    _purge_probe_users()
    seen = {"after_writes": False}
    try:
        owner_id, task_id, disp_id, rev, title = _commit_recurring_probe(
            worked_minutes=25,
            remaining_minutes=35,
            with_progress=True,
        )

        def _boom(db: Session) -> None:
            _recover_held_final_flush(db)
            row = db.get(TaskOccurrenceDisposition, disp_id)
            assert row is not None
            assert row.resolution == RESOLUTION_RECOVERED
            assert row.catch_up_task_id is not None
            settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
            assert int(settings.scheduling_revision) == rev + 1
            recovered = (
                db.query(DispositionEvent)
                .filter(
                    DispositionEvent.disposition_id == disp_id,
                    DispositionEvent.event_type == EVENT_RECOVERED,
                )
                .count()
            )
            assert recovered == 1
            series = db.get(Task, task_id)
            assert series is not None
            assert series.worked_minutes == 0
            assert series.remaining_minutes == 60
            assert series.due_at == _AUG18
            seen["after_writes"] = True
            raise RuntimeError("RENEE_LATE_INJECT")

        monkeypatch.setattr(
            "app.services.occurrence_disposition._recover_held_final_flush",
            _boom,
        )
        db = SessionLocal()
        try:
            with pytest.raises(RuntimeError, match="RENEE_LATE_INJECT"):
                recover_held(db, **_probe_recover_kwargs(owner_id, task_id, disp_id, rev))
            assert seen["after_writes"] is True
            db.rollback()
        finally:
            db.close()

        fresh = SessionLocal()
        try:
            series = fresh.get(Task, task_id)
            assert series is not None
            assert series.id == task_id
            assert series.owner_id == owner_id
            assert series.title == title
            assert series.estimated_duration_minutes == 60
            assert series.worked_minutes == 25
            assert series.remaining_minutes == 35
            assert series.due_at == _BOOKS_DUE
            assert series.start_no_earlier_at == _BOOKS_EARLIEST
            assert series.start_no_later_at == _BOOKS_LATEST
            assert series.deadline_at == _BOOKS_DEADLINE
            row = fresh.get(TaskOccurrenceDisposition, disp_id)
            assert row is not None
            assert row.resolution == RESOLUTION_UNRESOLVED_HELD
            assert row.catch_up_task_id is None
            assert row.authorize_instant is None
            assert row.miss_era_worked_minutes is None
            assert row.miss_era_entry_ids is None
            recovered = (
                fresh.query(DispositionEvent)
                .filter(
                    DispositionEvent.disposition_id == disp_id,
                    DispositionEvent.event_type == EVENT_RECOVERED,
                )
                .count()
            )
            assert recovered == 0
            settings = fresh.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
            assert int(settings.scheduling_revision) == rev
            assert fresh.query(Task).filter(Task.title == f"{title} (catch-up)").count() == 0
            entries = fresh.query(TaskProgressEntry).filter(TaskProgressEntry.task_id == task_id).all()
            assert len(entries) == 1
            assert entries[0].minutes_worked == 25
            assert (
                fresh.query(ProgressEpochMembership)
                .filter(ProgressEpochMembership.task_id == task_id)
                .count()
                == 0
            )
        finally:
            fresh.close()
    finally:
        _purge_probe_users()


def test_a12_happy_path_atomic_one_rev_bump(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    _log(client, task["id"], 25, 35)
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    resp = _recover(client, task["id"], row.id)
    assert resp.status_code == 200, resp.text
    assert _revision(client) == rev + 1
    series = _task(db_session, task["id"])
    assert series.due_at == _AUG18
    assert series.worked_minutes == 0
    assert series.remaining_minutes == 60
    fresh = db_session.get(TaskOccurrenceDisposition, row.id)
    assert fresh is not None and fresh.resolution == RESOLUTION_RECOVERED
    assert fresh.catch_up_task_id is not None
    assert len(_catch_up_named(db_session, task["title"])) == 1
    assert sum(1 for event in fresh.events if event.event_type == EVENT_RECOVERED) == 1


def test_a13_idempotent_rerecover(client: TestClient, db_session: Session) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    first = _recover(client, task["id"], row.id)
    assert first.status_code == 200, first.text
    catch_id = first.json()["catch_up_task_id"]
    rev = _revision(client)
    events = sum(
        1
        for event in db_session.get(TaskOccurrenceDisposition, row.id).events
        if event.event_type == EVENT_RECOVERED
    )
    second = _recover(client, task["id"], row.id)
    assert second.status_code == 200, second.text
    assert second.json()["catch_up_task_id"] == catch_id
    assert second.json()["resolution"] == RESOLUTION_RECOVERED
    assert _revision(client) == rev
    assert len(_catch_up_named(db_session, task["title"])) == 1
    db_session.expire_all()
    again = sum(
        1
        for event in db_session.get(TaskOccurrenceDisposition, row.id).events
        if event.event_type == EVENT_RECOVERED
    )
    assert again == events


def test_a14_stale_revision_precedes_noop(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    stale = _recover(client, task["id"], row.id, expected_revision=rev + 9)
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "SCHEDULING_REVISION_CONFLICT"
    assert _revision(client) == rev
    assert _catch_up_named(db_session, task["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )
    ok = _recover(client, task["id"], row.id)
    assert ok.status_code == 200, ok.text
    current = _revision(client)
    replay = _recover(client, task["id"], row.id, expected_revision=rev)
    assert replay.status_code == 409, replay.text
    assert replay.json()["code"] == "SCHEDULING_REVISION_CONFLICT"
    assert _revision(client) == current
    assert len(_catch_up_named(db_session, task["title"])) == 1


def test_a15_terminal_conflict_and_missing_id(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    released = _books(client, title=f"Released {_uid()}")
    rel_row = _hold(db_session, released["id"])
    rel = client.post(
        f"/api/v1/schedule/held-misses/{released['id']}/release",
        json={
            "disposition_id": str(rel_row.id),
            "expected_revision": _revision(client),
            "start_no_earlier_at": _iso(datetime(2026, 8, 20, 14, 0, tzinfo=UTC)),
            "start_no_later_at": _iso(datetime(2026, 8, 20, 18, 0, tzinfo=UTC)),
            "deadline_at": _iso(datetime(2026, 8, 20, 20, 0, tzinfo=UTC)),
        },
    )
    assert rel.status_code == 200, rel.text
    again = _recover(client, released["id"], rel_row.id)
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "CONFLICT_TERMINAL"

    skipped = _books(client, title=f"Skipped {_uid()}")
    skip_row = _hold(db_session, skipped["id"])
    skip = client.post(
        f"/api/v1/schedule/held-misses/{skipped['id']}/skip",
        json={
            "disposition_id": str(skip_row.id),
            "expected_revision": _revision(client),
        },
    )
    assert skip.status_code == 200, skip.text
    skip_recover = _recover(client, skipped["id"], skip_row.id)
    assert skip_recover.status_code == 409, skip_recover.text
    assert skip_recover.json()["code"] == "CONFLICT_TERMINAL"

    missing = _recover(client, released["id"], uuid.uuid4())
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "DISPOSITION_NOT_FOUND"


def test_a16_fingerprint_stale_once_calculate_write_free(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready", preview
    row = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .one()
    )
    rev = _revision(client)
    recovered = _recover(client, task["id"], row.id)
    assert recovered.status_code == 200, recovered.text
    assert _revision(client) == rev + 1
    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    body = rejected.json()
    assert body["code"] == "PREVIEW_STALE"
    assert STALE_OCCURRENCE_DISPOSITION in body.get("stale_categories", [])
    owner = _owner_id(client)
    _, fp_after = fingerprint_collected_inputs(collect_inputs(db_session, owner, FIXED_NOW))
    rev_after = _revision(client)
    replay = _recover(client, task["id"], row.id)
    assert replay.status_code == 200, replay.text
    assert _revision(client) == rev_after
    _, fp_replay = fingerprint_collected_inputs(collect_inputs(db_session, owner, FIXED_NOW))
    assert fp_replay == fp_after
    before_rows = db_session.query(TaskOccurrenceDisposition).count()
    before_events = db_session.query(DispositionEvent).count()
    calculate(db_session, collect_inputs(db_session, owner, FIXED_NOW))
    db_session.flush()
    assert db_session.query(TaskOccurrenceDisposition).count() == before_rows
    assert db_session.query(DispositionEvent).count() == before_events


def test_a17_catch_up_bounds_still_missed(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    past = _recover(
        client,
        task["id"],
        row.id,
        accept_past_ack=True,
        catch_up_due_at=_iso(FIXED_NOW - timedelta(hours=3)),
        catch_up_start_no_earlier_at=_iso(FIXED_NOW - timedelta(hours=4)),
        catch_up_start_no_later_at=_iso(FIXED_NOW - timedelta(hours=2)),
        catch_up_deadline_at=_iso(FIXED_NOW - timedelta(hours=1)),
    )
    assert past.status_code == 422, past.text
    assert past.json()["code"] == "BOUNDS_STILL_MISSED"
    assert _revision(client) == rev
    assert _catch_up_named(db_session, task["title"]) == []
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )
    tight = _recover(
        client,
        task["id"],
        row.id,
        catch_up_start_no_earlier_at=_iso(datetime(2026, 8, 13, 15, 0, tzinfo=UTC)),
        catch_up_deadline_at=_iso(datetime(2026, 8, 13, 15, 10, tzinfo=UTC)),
    )
    assert tight.status_code == 422, tight.text
    assert tight.json()["code"] == "BOUNDS_STILL_MISSED"
    assert _catch_up_named(db_session, task["title"]) == []
    assert _revision(client) == rev


def test_a18_catch_up_remaining_defaults(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)

    live = _books(client, title=f"Remain 35 {_uid()}")
    _log(client, live["id"], 25, 35)
    live_row = _hold(db_session, live["id"])
    live_resp = _recover(client, live["id"], live_row.id)
    assert live_resp.status_code == 200, live_resp.text
    live_catch = db_session.get(Task, uuid.UUID(live_resp.json()["catch_up_task_id"]))
    assert live_catch is not None
    assert live_catch.worked_minutes == 0
    assert live_catch.remaining_minutes == 35

    zero = _books(client, title=f"Remain 0 {_uid()}")
    _log(client, zero["id"], 25, 0)
    zero_row = _hold(db_session, zero["id"])
    zero_resp = _recover(client, zero["id"], zero_row.id)
    assert zero_resp.status_code == 200, zero_resp.text
    zero_catch = db_session.get(Task, uuid.UUID(zero_resp.json()["catch_up_task_id"]))
    assert zero_catch is not None
    assert zero_catch.worked_minutes == 0
    assert zero_catch.remaining_minutes == 0

    missing = _books(client, title=f"Remain null {_uid()}")
    _log(client, missing["id"], 25, 35)
    series = _task(db_session, missing["id"])
    series.remaining_minutes = None
    db_session.flush()
    missing_row = _hold(db_session, missing["id"])
    missing_resp = _recover(client, missing["id"], missing_row.id)
    assert missing_resp.status_code == 200, missing_resp.text
    missing_catch = db_session.get(Task, uuid.UUID(missing_resp.json()["catch_up_task_id"]))
    assert missing_catch is not None
    assert missing_catch.remaining_minutes == 60
    assert missing_catch.worked_minutes == 0

    override = _books(client, title=f"Override {_uid()}")
    _log(client, override["id"], 25, 35)
    override_row = _hold(db_session, override["id"])
    override_resp = _recover(
        client, override["id"], override_row.id, catch_up_remaining_minutes=60
    )
    assert override_resp.status_code == 200, override_resp.text
    override_catch = db_session.get(Task, uuid.UUID(override_resp.json()["catch_up_task_id"]))
    assert override_catch is not None
    assert override_catch.remaining_minutes == 60
    assert override_catch.worked_minutes == 0


def test_a19_completing_catch_up_does_not_advance_series(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id)
    assert resp.status_code == 200, resp.text
    series_due = _task(db_session, task["id"]).due_at
    catch_id = resp.json()["catch_up_task_id"]
    done = client.post(f"/api/v1/tasks/{catch_id}/complete", json={"force_parent_only": True})
    assert done.status_code == 200, done.text
    assert done.json()["is_completed"] is True
    series = _task(db_session, task["id"])
    assert series.due_at == series_due
    assert series.is_completed is False
    assert series.due_at == _AUG18


def test_a20_nonrecurring_rejected_release_remains(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"One-off {_uid()}",
            "estimated_duration_minutes": 60,
            "schedule_style": "standalone",
            "start_no_later_at": _iso(FIXED_NOW - timedelta(hours=2)),
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    row = _hold(db_session, task["id"])
    rev = _revision(client)
    rejected = _recover(client, task["id"], row.id)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "RECOVERY_REQUIRES_RECURRING"
    assert _revision(client) == rev
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )
    released = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": _revision(client),
            "start_no_later_at": _iso(datetime(2026, 8, 20, 16, 0, tzinfo=UTC)),
        },
    )
    assert released.status_code == 200, released.text
    assert released.json()["resolution"] == RESOLUTION_RELEASED


def test_a21_no_backlog_no_stack_no_fanout(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 7, 7, 9, 0, tzinfo=UTC)
    earliest, latest, deadline = _window_on(due)
    task = _series(
        client,
        title=f"No fanout {_uid()}",
        due=due,
        earliest=earliest,
        latest=latest,
        deadline=deadline,
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=TU",
        is_fixed=False,
    )
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id)
    assert resp.status_code == 200, resp.text
    catches = _catch_up_named(db_session, task["title"])
    assert len(catches) == 1
    series = _task(db_session, task["id"])
    assert series.due_at == _AUG18
    assert catches[0].due_at != series.due_at
    assert catches[0].id != series.id
    dispositions = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == series.id)
        .all()
    )
    assert len(dispositions) == 1
    backlog = db_session.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename ILIKE '%backlog%'"
        )
    ).all()
    assert backlog == []


def test_a22_tuesday_weekly_books_fixture(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client, title=f"Weekly books {_uid()}")
    logged = _log(client, task["id"], 25, 35)
    row = _hold(db_session, task["id"])
    resp = _recover(client, task["id"], row.id, authorize_instant=_iso(FIXED_NOW))
    assert resp.status_code == 200, resp.text
    series = _task(db_session, task["id"])
    assert series.due_at == _AUG18
    assert series.worked_minutes == 0
    assert series.remaining_minutes == 60
    assert placement_effort_minutes(series) == 60
    entries = _entries(db_session, series.id)
    assert sum(entry.minutes_worked for entry in entries) == 25
    assert all(entry.task_id == series.id for entry in entries)
    fresh = db_session.get(TaskOccurrenceDisposition, row.id)
    assert fresh is not None
    assert fresh.miss_era_worked_minutes == 25
    assert logged["entry"]["id"] in list(fresh.miss_era_entry_ids)
    catch = db_session.get(Task, fresh.catch_up_task_id)
    assert catch is not None
    assert catch.worked_minutes == 0
    assert catch.remaining_minutes == 35
    assert catch.due_at == _CATCH_DUE
    assert _entries(db_session, catch.id) == []
    assert series.is_completed is False
