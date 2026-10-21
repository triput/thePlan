"""T2-S2-RS release/skip — disposable acceptance (theplan_s1_test @ :5433).

A1–A12 + A3b + Dex unlock clarifications (real rollback, dual-session race,
delayed old disposition_id, skip Apply stale without rev bump).
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime, timedelta, time as time_of_day, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import SessionLocal
from app.models import (
    Project,
    ScheduledBlock,
    Task,
    TaskOccurrenceDisposition,
    User,
    UserSettings,
)
from app.models.enums import ScheduleStyle
from app.models.task_occurrence_disposition import (
    EVENT_LEAVE_HELD,
    EVENT_MISS_DETECTED,
    EVENT_RELEASED,
    EVENT_SKIPPED,
    RESOLUTION_RELEASED,
    RESOLUTION_SKIPPED,
    RESOLUTION_UNRESOLVED_HELD,
    DispositionEvent,
)
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import STALE_OCCURRENCE_DISPOSITION
from app.scheduler.preview import run_preview
from app.services.availability_seed import ensure_default_availability_policies
from app.services.occurrence_disposition import (
    episode_key_for_task,
    release_held,
    skip_held,
)
from app.services.scheduling_revision import owner_scheduling_lock_key
from test_schedule_replan import FIXED_NOW, _create_task, _patch_schedule_clock, _prepare_settings

UTC = timezone.utc
_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "042_task_occurrence_dispositions"
_PROBE_EMAIL_LIKE = "justin-t2s2-rs-%@example.com"

cli_root = Path(__file__).resolve().parents[2] / "cli"
if str(cli_root) not in sys.path:
    sys.path.insert(0, str(cli_root))


@pytest.fixture(autouse=True)
def _disposable_db(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_schedule_clock(monkeypatch)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _prepare(client: TestClient, db: Session) -> None:
    _prepare_settings(client)
    ensure_default_availability_policies(db, _owner_id(client))
    db.commit()


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _miss_task(client: TestClient, db: Session, *, title: str | None = None) -> dict:
    latest = FIXED_NOW - timedelta(hours=2)
    return _create_task(
        client,
        title=title or f"Miss {_uid()}",
        estimated_duration_minutes=60,
        start_no_later_at=latest.isoformat().replace("+00:00", "Z"),
    )


def _ready_preview(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    assert started.status_code == 202, started.text
    run_preview(uuid.UUID(started.json()["id"]), db=db)
    db.flush()
    got = client.get(f"/api/v1/schedule/previews/{started.json()['id']}")
    assert got.status_code == 200
    return got.json()


def _revision(client: TestClient) -> int:
    return int(client.get("/api/v1/settings").json()["scheduling_revision"])


def _held_row(db: Session, task_id: str | uuid.UUID) -> TaskOccurrenceDisposition:
    return (
        db.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(str(task_id)))
        .one()
    )


def _future_later() -> str:
    return (datetime.now(UTC) + timedelta(days=3)).isoformat().replace("+00:00", "Z")


def _fresh_session_on(connection) -> Session:
    return Session(
        bind=connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )


def _bind_cli_to_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from theplan.api_client import api_error_from_response

    def api_json(
        method: str,
        path: str,
        *,
        json_body: dict | list | None = None,
        params: dict | None = None,
        **kwargs,
    ):
        call = getattr(client, method.lower())
        if method.upper() in {"GET", "DELETE"}:
            response = call(path, params=params)
        else:
            response = call(
                path,
                json=json_body if json_body is not None else kwargs.get("json"),
                params=params,
            )
        if response.status_code >= 400:
            raise api_error_from_response(response)
        if not response.content:
            return None
        return response.json()

    monkeypatch.setattr("theplan.commands.schedule.api_json", api_json)


def _purge_probe_users() -> None:
    db = SessionLocal()
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


def _commit_held_probe() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, int]:
    """Committed owner + unresolved held disposition for cross-session races."""
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"justin-t2s2-rs-{token}@example.com",
            username=f"justin-t2s2-rs-{token}",
            display_name="Justin T2-S2-RS probe",
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
            upcoming_horizon_days=7,
            default_schedule_style=ScheduleStyle.standalone,
            scheduling_revision=3,
        )
        db.add(settings)
        _seed_always_on_availability(db, user.id)
        project = Project(owner_id=user.id, title=f"justin-t2s2-rs-{token}")
        db.add(project)
        db.flush()
        latest = FIXED_NOW - timedelta(hours=2)
        task = Task(
            owner_id=user.id,
            project_id=project.id,
            title=f"justin-t2s2-rs-miss-{token}",
            estimated_duration_minutes=60,
            schedule_style=ScheduleStyle.standalone,
            start_no_later_at=latest,
        )
        db.add(task)
        db.flush()
        disp = TaskOccurrenceDisposition(
            owner_id=user.id,
            task_id=task.id,
            episode_key=episode_key_for_task(task),
            resolution=RESOLUTION_UNRESOLVED_HELD,
            bounds_snapshot={
                "start_no_earlier_at": None,
                "start_no_later_at": latest.isoformat(),
                "deadline_at": None,
            },
            miss_reason_code="occurrence_bounds_miss",
        )
        db.add(disp)
        db.flush()
        db.add(
            DispositionEvent(
                disposition_id=disp.id,
                event_type=EVENT_MISS_DETECTED,
                payload={"probe": True},
            )
        )
        db.commit()
        return user.id, task.id, disp.id, int(settings.scheduling_revision)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# A1–A12 + A3b
# ---------------------------------------------------------------------------


def test_a1_named_release_event_snapshot_immutable(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    snapshot_before = dict(row.bounds_snapshot)
    disp_id = str(row.id)
    rev = _revision(client)
    resp = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": disp_id,
            "expected_revision": rev,
            "start_no_later_at": _future_later(),
            "note": "retry",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["resolution"] == RESOLUTION_RELEASED
    assert body["bounds_snapshot"] == snapshot_before
    assert any(e["event_type"] == EVENT_RELEASED for e in body["events"])
    fresh = _fresh_session_on(db_session.connection())
    try:
        reread = fresh.get(TaskOccurrenceDisposition, uuid.UUID(disp_id))
        assert reread is not None
        assert reread.resolution == RESOLUTION_RELEASED
        assert dict(reread.bounds_snapshot) == snapshot_before
        assert any(e.event_type == EVENT_RELEASED for e in reread.events)
        assert reread.miss_reason_code is not None
    finally:
        fresh.close()


def test_a2_release_still_missed_rejects_and_rolls_back(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    snapshot_before = dict(row.bounds_snapshot)
    rev = _revision(client)
    task_before = client.get(f"/api/v1/tasks/{task['id']}").json()
    still_missed = (FIXED_NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    resp = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev,
            "start_no_later_at": still_missed,
            "note": "should-fail",
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "BOUNDS_STILL_MISSED"
    db_session.expire_all()
    reread = _held_row(db_session, task["id"])
    assert reread.resolution == RESOLUTION_UNRESOLVED_HELD
    assert dict(reread.bounds_snapshot) == snapshot_before
    assert not any(e.event_type == EVENT_RELEASED for e in reread.events)
    assert _revision(client) == rev
    task_after = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task_after["start_no_later_at"] == task_before["start_no_later_at"]


def test_a3_atomic_bounds_release_no_same_episode_rehold(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    old_key = row.episode_key
    rev_before = _revision(client)
    resp = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev_before,
            "start_no_later_at": _future_later(),
        },
    )
    assert resp.status_code == 200, resp.text
    assert _revision(client) == rev_before + 1
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    rows = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .all()
    )
    assert len(rows) == 1
    assert rows[0].resolution == RESOLUTION_RELEASED
    assert rows[0].episode_key == old_key


def test_a3b_later_miss_new_episode_prior_released_intact(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    prior_id = row.id
    prior_snapshot = dict(row.bounds_snapshot)
    prior_key = row.episode_key
    resp = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": _revision(client),
            "start_no_later_at": _future_later(),
        },
    )
    assert resp.status_code == 200, resp.text
    # Later genuine miss with changed usable dates → new episode_key.
    remiss = (FIXED_NOW - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    patched = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"expected_revision": _revision(client), "start_no_later_at": remiss},
    )
    assert patched.status_code == 200, patched.text
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    rows = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .order_by(TaskOccurrenceDisposition.created_at)
        .all()
    )
    assert len(rows) == 2
    prior = next(r for r in rows if r.id == prior_id)
    newer = next(r for r in rows if r.id != prior_id)
    assert prior.resolution == RESOLUTION_RELEASED
    assert dict(prior.bounds_snapshot) == prior_snapshot
    assert prior.episode_key == prior_key
    assert newer.resolution == RESOLUTION_UNRESOLVED_HELD
    assert newer.episode_key != prior_key


def test_a4_skip_no_block_progress_complete_mutation(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    task_orm = db_session.get(Task, uuid.UUID(task["id"]))
    assert task_orm is not None
    worked_before = task_orm.worked_minutes
    completed_before = task_orm.is_completed
    blocks_before = (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.task_id == task_orm.id)
        .count()
    )
    rev = _revision(client)
    resp = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev,
            "note": "suppress",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["resolution"] == RESOLUTION_SKIPPED
    assert any(e["event_type"] == EVENT_SKIPPED for e in resp.json()["events"])
    assert _revision(client) == rev
    db_session.expire_all()
    task_orm = db_session.get(Task, uuid.UUID(task["id"]))
    assert task_orm is not None
    assert task_orm.worked_minutes == worked_before
    assert task_orm.is_completed == completed_before
    assert (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.task_id == task_orm.id)
        .count()
        == blocks_before
    )


def test_a5_date_edit_alone_keeps_skipped(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    skip = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={"disposition_id": str(row.id), "expected_revision": _revision(client)},
    )
    assert skip.status_code == 200
    wider = _future_later()
    patched = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"expected_revision": _revision(client), "start_no_later_at": wider},
    )
    assert patched.status_code == 200, patched.text
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    rows = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .all()
    )
    assert len(rows) == 1
    assert rows[0].resolution == RESOLUTION_SKIPPED
    blocks = (preview.get("proposal") or {}).get("proposed_blocks") or (
        preview.get("proposal") or {}
    ).get("blocks") or []
    assert not any(b.get("task_id") == task["id"] for b in blocks)


def test_a6_stale_revision_before_terminal_noop(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    rev = _revision(client)
    # First release succeeds.
    ok = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev,
            "start_no_later_at": _future_later(),
        },
    )
    assert ok.status_code == 200, ok.text
    # Stale expected_revision on already-released must 409 — not terminal no-op.
    stale = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev,
            "start_no_later_at": _future_later(),
            "note": "stale-replay",
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "SCHEDULING_REVISION_CONFLICT"
    events = [
        e.event_type
        for e in _held_row(db_session, task["id"]).events
        if e.event_type == EVENT_RELEASED
    ]
    assert len(events) == 1


def test_a7_idempotent_same_terminal(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    rev0 = _revision(client)
    first = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={"disposition_id": str(row.id), "expected_revision": rev0, "note": "one"},
    )
    assert first.status_code == 200
    assert _revision(client) == rev0
    second = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev0,
            "note": "two",
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["resolution"] == RESOLUTION_SKIPPED
    assert _revision(client) == rev0
    skipped_events = [
        e for e in second.json()["events"] if e["event_type"] == EVENT_SKIPPED
    ]
    assert len(skipped_events) == 1


def test_a8_cross_terminal_conflict(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    skip = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={"disposition_id": str(row.id), "expected_revision": _revision(client)},
    )
    assert skip.status_code == 200
    conflict = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": _revision(client),
            "start_no_later_at": _future_later(),
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "CONFLICT_TERMINAL"


def test_a9_rev_bump_only_on_release(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    t_skip = _miss_task(client, db_session, title=f"Skip {_uid()}")
    t_rel = _miss_task(client, db_session, title=f"Rel {_uid()}")
    t_leave = _miss_task(client, db_session, title=f"Leave {_uid()}")
    _ready_preview(client, db_session, monkeypatch)
    rev0 = _revision(client)
    skip_row = _held_row(db_session, t_skip["id"])
    leave_row = _held_row(db_session, t_leave["id"])
    rel_row = _held_row(db_session, t_rel["id"])
    leave = client.post(
        f"/api/v1/schedule/held-misses/{t_leave['id']}/leave-held",
        json={"expected_revision": rev0, "note": "audit"},
    )
    assert leave.status_code == 200
    assert leave.json()["resolution"] == RESOLUTION_UNRESOLVED_HELD
    assert EVENT_LEAVE_HELD in [e["event_type"] for e in leave.json()["events"]]
    assert _revision(client) == rev0
    skipped = client.post(
        f"/api/v1/schedule/held-misses/{t_skip['id']}/skip",
        json={"disposition_id": str(skip_row.id), "expected_revision": rev0},
    )
    assert skipped.status_code == 200
    assert _revision(client) == rev0
    released = client.post(
        f"/api/v1/schedule/held-misses/{t_rel['id']}/release",
        json={
            "disposition_id": str(rel_row.id),
            "expected_revision": rev0,
            "start_no_later_at": _future_later(),
        },
    )
    assert released.status_code == 200, released.text
    assert _revision(client) == rev0 + 1


def test_a10_skip_and_release_stale_apply(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    row = _held_row(db_session, task["id"])
    rev = _revision(client)
    blocks_before = (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.owner_id == _owner_id(client))
        .count()
    )
    skip = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={"disposition_id": str(row.id), "expected_revision": rev},
    )
    assert skip.status_code == 200
    assert _revision(client) == rev  # no bump
    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    body = rejected.json()
    assert body["code"] == "PREVIEW_STALE"
    assert STALE_OCCURRENCE_DISPOSITION in body.get("stale_categories", [])
    assert (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.owner_id == _owner_id(client))
        .count()
        == blocks_before
    )


def test_a11_owner_isolation_and_old_disposition_id(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    old = _held_row(db_session, task["id"])
    old_id = old.id
    old_snapshot = dict(old.bounds_snapshot)
    # Release old episode, then create a newer held episode via remiss.
    assert (
        client.post(
            f"/api/v1/schedule/held-misses/{task['id']}/release",
            json={
                "disposition_id": str(old_id),
                "expected_revision": _revision(client),
                "start_no_later_at": _future_later(),
            },
        ).status_code
        == 200
    )
    remiss = (FIXED_NOW - timedelta(minutes=45)).isoformat().replace("+00:00", "Z")
    assert (
        client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"expected_revision": _revision(client), "start_no_later_at": remiss},
        ).status_code
        == 200
    )
    _ready_preview(client, db_session, monkeypatch)
    newer = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(
            TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]),
            TaskOccurrenceDisposition.resolution == RESOLUTION_UNRESOLVED_HELD,
        )
        .one()
    )
    # Delayed client with old disposition_id — idempotent on released; newer intact.
    delayed = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(old_id),
            "expected_revision": _revision(client),
            "start_no_later_at": _future_later(),
        },
    )
    assert delayed.status_code == 200, delayed.text
    assert delayed.json()["resolution"] == RESOLUTION_RELEASED
    db_session.expire_all()
    old_reread = db_session.get(TaskOccurrenceDisposition, old_id)
    assert old_reread is not None
    assert dict(old_reread.bounds_snapshot) == old_snapshot
    newer_reread = db_session.get(TaskOccurrenceDisposition, newer.id)
    assert newer_reread is not None
    assert newer_reread.resolution == RESOLUTION_UNRESOLVED_HELD

    # Owner isolation: foreign disposition_id → 404.
    other = User(
        email=f"other-rs-{_uid()}@example.com",
        username=f"other-rs-{_uid()}",
        display_name="Other",
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        session_epoch=0,
    )
    db_session.add(other)
    db_session.flush()
    foreign_task = Task(
        owner_id=other.id,
        title="foreign",
        estimated_duration_minutes=30,
        schedule_style=ScheduleStyle.standalone,
    )
    db_session.add(foreign_task)
    db_session.flush()
    foreign = TaskOccurrenceDisposition(
        owner_id=other.id,
        task_id=foreign_task.id,
        episode_key="foreign-ep",
        resolution=RESOLUTION_UNRESOLVED_HELD,
        bounds_snapshot={},
        miss_reason_code="occurrence_bounds_miss",
    )
    db_session.add(foreign)
    db_session.flush()
    iso = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={
            "disposition_id": str(foreign.id),
            "expected_revision": _revision(client),
        },
    )
    assert iso.status_code == 404
    assert db_session.get(TaskOccurrenceDisposition, foreign.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )


def test_a12_calculate_write_free_reads_suppress(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/skip",
        json={"disposition_id": str(row.id), "expected_revision": _revision(client)},
    )
    owner_id = _owner_id(client)
    before = db_session.query(TaskOccurrenceDisposition).count()
    before_events = db_session.query(DispositionEvent).count()
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    assert uuid.UUID(task["id"]) in inputs.skipped_task_ids
    calculate(db_session, inputs)
    db_session.flush()
    assert db_session.query(TaskOccurrenceDisposition).count() == before
    assert db_session.query(DispositionEvent).count() == before_events


# ---------------------------------------------------------------------------
# Dex clarifications
# ---------------------------------------------------------------------------


def test_competing_dual_session_release_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_schedule_clock(monkeypatch)
    _purge_probe_users()
    owner_id, task_id, disp_id, rev = _commit_held_probe()
    barrier = threading.Barrier(2)
    results: list[tuple[str, str | None]] = []

    def worker(action: str) -> None:
        from app.api.errors import ApiError

        db = SessionLocal()
        try:
            barrier.wait(timeout=15)
            if action == "release":
                future = datetime.now(UTC) + timedelta(days=3)
                release_held(
                    db,
                    owner_id=owner_id,
                    task_id=task_id,
                    disposition_id=disp_id,
                    expected_revision=rev,
                    bounds_updates={"start_no_later_at": future},
                )
            else:
                skip_held(
                    db,
                    owner_id=owner_id,
                    task_id=task_id,
                    disposition_id=disp_id,
                    expected_revision=rev,
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

    t1 = threading.Thread(target=worker, args=("release",))
    t2 = threading.Thread(target=worker, args=("skip",))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert len(results) == 2, results
    oks = [r for r in results if r[1] == "ok"]
    assert len(oks) == 1, results
    conflicts = [r for r in results if r[1] != "ok"]
    assert len(conflicts) == 1
    assert conflicts[0][1] in {
        "CONFLICT_TERMINAL",
        "SCHEDULING_REVISION_CONFLICT",
    }, results
    readback = SessionLocal()
    try:
        row = readback.get(TaskOccurrenceDisposition, disp_id)
        assert row is not None
        assert row.resolution in {RESOLUTION_RELEASED, RESOLUTION_SKIPPED}
        winner = oks[0][0]
        if winner == "release":
            assert row.resolution == RESOLUTION_RELEASED
        else:
            assert row.resolution == RESOLUTION_SKIPPED
    finally:
        readback.close()
        _purge_probe_users()


def test_cli_held_release_and_skip_parity(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from theplan.commands.schedule import run_schedule
    from theplan.main import _build_parser
    from theplan.output import set_output_format

    _prepare(client, db_session)
    t_rel = _miss_task(client, db_session, title=f"CLI-rel {_uid()}")
    t_skip = _miss_task(client, db_session, title=f"CLI-skip {_uid()}")
    _ready_preview(client, db_session, monkeypatch)
    rel_row = _held_row(db_session, t_rel["id"])
    skip_row = _held_row(db_session, t_skip["id"])
    _bind_cli_to_client(client, monkeypatch)
    set_output_format("json")
    run_schedule(
        _build_parser().parse_args(
            [
                "schedule",
                "held",
                "release",
                "--task-id",
                t_rel["id"],
                "--disposition-id",
                str(rel_row.id),
                "--expected-revision",
                str(_revision(client)),
                "--start-no-later-at",
                _future_later(),
                "--note",
                "cli-release",
            ]
        )
    )
    released = json.loads(capsys.readouterr().out)
    assert released["ok"] is True
    assert released["resolution"] == RESOLUTION_RELEASED
    run_schedule(
        _build_parser().parse_args(
            [
                "schedule",
                "held",
                "skip",
                "--task-id",
                t_skip["id"],
                "--disposition-id",
                str(skip_row.id),
                "--expected-revision",
                str(_revision(client)),
                "--note",
                "cli-skip",
            ]
        )
    )
    skipped = json.loads(capsys.readouterr().out)
    assert skipped["ok"] is True
    assert skipped["resolution"] == RESOLUTION_SKIPPED


def test_leave_held_regression_unchanged(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    rev = _revision(client)
    resp = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/leave-held",
        json={"expected_revision": rev, "note": "still held"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["resolution"] == RESOLUTION_UNRESOLVED_HELD
    assert EVENT_LEAVE_HELD in [e["event_type"] for e in resp.json()["events"]]
    assert _revision(client) == rev


def test_idempotent_release_ignores_new_bounds_patch(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = _held_row(db_session, task["id"])
    first_later = _future_later()
    rev0 = _revision(client)
    first = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev0,
            "start_no_later_at": first_later,
        },
    )
    assert first.status_code == 200
    rev1 = _revision(client)
    assert rev1 == rev0 + 1
    task_mid = client.get(f"/api/v1/tasks/{task['id']}").json()
    second_later = (datetime.now(UTC) + timedelta(days=10)).isoformat().replace(
        "+00:00", "Z"
    )
    second = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/release",
        json={
            "disposition_id": str(row.id),
            "expected_revision": rev1,
            "start_no_later_at": second_later,
            "note": "noop-bounds",
        },
    )
    assert second.status_code == 200
    assert _revision(client) == rev1
    task_after = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task_after["start_no_later_at"] == task_mid["start_no_later_at"]
    assert len([e for e in second.json()["events"] if e["event_type"] == EVENT_RELEASED]) == 1
