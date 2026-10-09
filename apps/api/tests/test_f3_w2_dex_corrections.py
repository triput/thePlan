"""Dex F3-W2 P2 corrections: busy capture, cycle membership, naive deadline tz."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import TaskDependency
from app.scheduler.busy_map import busy_from_sources, load_immovable_busy_sources
from app.scheduler.calculate import _ensure_utc
from app.scheduler.collect import collect_inputs
from test_schedule_replan import (
    FIXED_NOW,
    _create_task,
    _isolate_tasks,
    _patch_schedule_clock,
    _prepare_settings,
    _replan_sync,
)


def test_ensure_utc_accepts_naive_datetime() -> None:
    naive = datetime(2026, 8, 11, 12, 0, 0)
    aware = _ensure_utc(naive)
    assert aware.tzinfo is not None
    assert aware == naive.replace(tzinfo=timezone.utc)


def test_collect_captures_immovable_busy_once(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dex residual: fingerprint must not re-query external busy after calc capture."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=30)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    _isolate_tasks(db_session, client, {task_id})

    calls = {"n": 0}
    real = load_immovable_busy_sources

    def counting(db: Session, oid: uuid.UUID):
        calls["n"] += 1
        return real(db, oid)

    monkeypatch.setattr(
        "app.scheduler.collect.load_immovable_busy_sources",
        counting,
    )

    def boom_live_busy(*_a, **_k):
        raise AssertionError("collect must not reload immovable busy for fingerprints")

    monkeypatch.setattr(
        "app.scheduler.outcomes.load_immovable_busy",
        boom_live_busy,
    )

    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    assert calls["n"] == 1
    assert inputs.busy == []
    assert inputs.immovable_busy == []
    assert inputs.input_snapshots[task_id]["busy_external"]["intervals"] == []


def test_busy_from_sources_derives_horizon_view_from_same_capture() -> None:
    pin = MagicMock()
    pin.start_time = FIXED_NOW + timedelta(hours=1)
    pin.end_time = FIXED_NOW + timedelta(hours=2)
    pin.task_id = uuid.uuid4()
    event = MagicMock()
    event.start_time = FIXED_NOW + timedelta(days=10)
    event.end_time = FIXED_NOW + timedelta(days=10, hours=1)
    full = busy_from_sources([pin], [event])
    horizon = busy_from_sources(
        [pin],
        [event],
        range_start=FIXED_NOW,
        range_end=FIXED_NOW + timedelta(days=7),
    )
    assert len(full) == 2
    assert len(horizon) == 1
    assert horizon[0].source == "pinned"


def test_snapshot_busy_uses_passed_capture_not_later_live(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate intervening edit between would-be first and second busy reads."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=30)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    _isolate_tasks(db_session, client, {task_id})

    captured_pins: list = []
    captured_events: list = []
    state = {"n": 0}

    def stub_sources(db: Session, oid: uuid.UUID):
        state["n"] += 1
        if state["n"] == 1:
            return captured_pins, captured_events
        # A second call would see an intervening external event.
        poison = MagicMock()
        poison.start_time = FIXED_NOW + timedelta(hours=9)
        poison.end_time = FIXED_NOW + timedelta(hours=10)
        return captured_pins, [poison]

    monkeypatch.setattr(
        "app.scheduler.collect.load_immovable_busy_sources",
        stub_sources,
    )
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    assert state["n"] == 1
    assert inputs.busy == []
    assert inputs.immovable_busy == []
    assert inputs.input_snapshots[task_id]["busy_external"]["intervals"] == []


def test_downstream_of_cycle_gets_prerequisite_not_cycle(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    a = _create_task(client, estimated_duration_minutes=30, priority="p1")
    b = _create_task(client, estimated_duration_minutes=30, priority="p1")
    c = _create_task(client, estimated_duration_minutes=30, priority="p1")
    a_id, b_id, c_id = uuid.UUID(a["id"]), uuid.UUID(b["id"]), uuid.UUID(c["id"])
    db_session.add_all(
        [
            TaskDependency(
                owner_id=owner_id, blocking_task_id=a_id, dependent_task_id=b_id
            ),
            TaskDependency(
                owner_id=owner_id, blocking_task_id=b_id, dependent_task_id=a_id
            ),
            TaskDependency(
                owner_id=owner_id, blocking_task_id=b_id, dependent_task_id=c_id
            ),
        ]
    )
    _isolate_tasks(db_session, client, {a_id, b_id, c_id})
    _replan_sync(client, db_session, monkeypatch)

    for task in (a, b):
        body = client.get(f"/api/v1/tasks/{task['id']}/schedule-explanation").json()
        assert body["explanation"]["reason_facts"][0]["code"] == "blocked_dependency_cycle"
        members = body["explanation"]["reason_facts"][0]["params"]["cycle_task_ids"]
        assert set(members) == {a["id"], b["id"]}
        assert c["id"] not in members

    body_c = client.get(f"/api/v1/tasks/{c['id']}/schedule-explanation").json()
    assert body_c["explanation"]["reason_facts"][0]["code"] == "blocked_prerequisite"
    assert b["id"] in body_c["explanation"]["reason_facts"][0]["params"]["blocking_task_ids"]
