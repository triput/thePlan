"""T2-S2 B-auto held miss — disposable acceptance (theplan_s1_test @ :5433)."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import TaskOccurrenceDisposition, UserSettings
from app.models.task_occurrence_disposition import (
    EVENT_LEAVE_HELD,
    EVENT_MISS_DETECTED,
    RESOLUTION_UNRESOLVED_HELD,
)
from app.scheduler.preview import run_preview
from app.services.availability_seed import ensure_default_availability_policies
from test_schedule_replan import FIXED_NOW, _create_task, _patch_schedule_clock, _prepare_settings

UTC = timezone.utc
_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "042_task_occurrence_dispositions"


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


def test_a4_duplicate_miss_idempotent(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    count1 = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .count()
    )
    _ready_preview(client, db_session, monkeypatch)
    count2 = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .count()
    )
    assert count1 == 1
    assert count2 == 1


def test_a5_widen_after_held_suppresses_placement(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    wider = (FIXED_NOW + timedelta(days=2)).isoformat().replace("+00:00", "Z")
    patch = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={
            "expected_revision": _revision(client),
            "start_no_later_at": wider,
        },
    )
    assert patch.status_code == 200, patch.text
    preview = _ready_preview(client, db_session, monkeypatch)
    row = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .one()
    )
    assert row.resolution == RESOLUTION_UNRESOLVED_HELD
    blocks = preview.get("proposal_json", {}).get("blocks") or []
    assert not any(b.get("task_id") == task["id"] for b in blocks)


def test_a6_preview_after_prior_held_ready(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    held = client.get("/api/v1/schedule/held-misses")
    assert held.status_code == 200
    assert len(held.json()) >= 1


def test_a1_external_revision_drift_aborts(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])
    def force_drift(**kwargs):
        return True

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration.orchestration_input_drift",
        force_drift,
    )
    run_preview(preview_id, db=db_session)
    db_session.flush()
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] in {"stale", "failed"}
    assert got.json()["status"] != "ready"


def test_a3_rollback_removes_flushed_dispositions(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])

    def boom(*_a, **_k):
        raise RuntimeError("commit_fail_probe")

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration.build_proposal_json",
        boom,
    )
    run_preview(preview_id, db=db_session)
    db_session.expire_all()
    count = db_session.query(TaskOccurrenceDisposition).count()
    assert count == 0
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] == "failed"


def test_a7_same_preview_sync_parallel_guard(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    preview = _ready_preview(client, db_session, monkeypatch)
    preview_id = uuid.UUID(preview["id"])
    count_after_first = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .count()
    )
    assert count_after_first == 1

    barrier = threading.Barrier(2)

    def second_attempt() -> None:
        barrier.wait(timeout=10)
        run_preview(preview_id)

    worker = threading.Thread(target=second_attempt)
    worker.start()
    worker.join(timeout=30)
    db_session.expire_all()
    assert (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .count()
        == 1
    )
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] == "ready"


def test_a8_max_iter_exhaustion_not_ready(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])
    monkeypatch.setattr("app.scheduler.preview_orchestration.MAX_ORCHESTRATION_ITER", 1)
    monkeypatch.setattr(
        "app.scheduler.preview_orchestration.miss_tasks_from_calculation",
        lambda _r: {uuid.uuid4(): type("F", (), {"code": "occurrence_bounds_miss", "params": {}})()},
    )
    run_preview(preview_id, db=db_session)
    db_session.flush()
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] == "failed"


def test_a10_trust_fail_rollback(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])

    def fail_trust(_inputs):
        from app.scheduler.free_busy import BusyInputTrustError
        from app.scheduler.free_busy import BusyInputTrust

        raise BusyInputTrustError("blocked", BusyInputTrust(ok=False, blocking_diagnostics=[]))

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration._validate_collect",
        fail_trust,
    )
    run_preview(preview_id, db=db_session)
    db_session.flush()
    assert db_session.query(TaskOccurrenceDisposition).count() == 0


def test_a2_two_previews_same_owner_serialized(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    rows = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .all()
    )
    assert len(rows) == 1


def test_leave_held_audit(
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
    events = [e["event_type"] for e in resp.json()["events"]]
    assert EVENT_LEAVE_HELD in events
    assert resp.json()["resolution"] == RESOLUTION_UNRESOLVED_HELD


def test_a9_second_pass_miss_recorded_or_exhaust(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"


def test_auto_records_miss_detected_event(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .one()
    )
    assert any(e.event_type == EVENT_MISS_DETECTED for e in row.events)
