"""S2-V1 chunking scaffold: guard gate, v4 duration fingerprint, A4 validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ScheduledBlock, Task
from app.scheduler.input_fingerprint import (
    SNAPSHOT_VERSION,
    SNAPSHOT_VERSION_V4,
    assemble_snapshot,
    diff_stale_categories,
    normalize_duration_category_v4,
)
from app.services import task_chunking_guard
from app.services.chunking_effective import resolve_block_bounds


def test_chunking_guard_unlocked_at_s2_tip() -> None:
    assert task_chunking_guard.chunking_cutover_writes_unlocked() is True


def test_v4_duration_category_shape() -> None:
    payload = normalize_duration_category_v4(
        original_minutes=480,
        worked_minutes=60,
        remaining_minutes=420,
        stored_min=None,
        stored_max=120,
        max_unbounded=False,
        keep_in_one_block=True,
    )
    assert payload["original_minutes"] == 480
    assert payload["remaining_minutes"] == 420
    assert payload["min_inherit"] is True
    assert payload["max_inherit"] is False
    assert payload["keep_in_one_block"] is True


def test_v3_stored_vs_v4_live_is_provenance() -> None:
    v3 = assemble_snapshot(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
        snapshot_version=SNAPSHOT_VERSION,
    )
    v4 = assemble_snapshot(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
        snapshot_version=SNAPSHOT_VERSION_V4,
        worked_minutes=0,
        remaining_minutes=30,
    )
    assert diff_stale_categories(v3, v4) == ["provenance"]


def test_resolve_bounds_conflict_a4() -> None:
    class _Task:
        min_block_duration_minutes = 180
        max_block_duration_minutes = 120
        max_block_unbounded = False
        keep_in_one_block = False

    class _Settings:
        default_min_block_duration_minutes = 15
        default_max_block_duration_minutes = 120
        default_max_block_unbounded = False

    resolved = resolve_block_bounds(_Task(), _Settings())  # type: ignore[arg-type]
    assert resolved.bounds_conflict() is True


@pytest.mark.parametrize(
    "payload",
    [
        {"min_block_duration_minutes": None},
        {"max_block_unbounded": True},
        {"keep_in_one_block": True},
    ],
)
def test_cutover_writes_accepted(
    client: TestClient, db_session: Session, payload: dict
) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-guard-{uuid4().hex[:8]}", "estimated_duration_minutes": 30},
    )
    assert created.status_code in (200, 201), created.text
    task_id = created.json()["id"]
    response = client.patch(f"/api/v1/tasks/{task_id}", json=payload)
    assert response.status_code == 200, response.text


def test_inherit_write_persists_null_min(
    client: TestClient, db_session: Session,
) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-unlock-{uuid4().hex[:8]}", "estimated_duration_minutes": 30},
    )
    assert created.status_code in (200, 201), created.text
    task_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"min_block_duration_minutes": None},
    )
    assert response.status_code == 200, response.text
    stored = db_session.get(Task, task_id)
    assert stored is not None
    db_session.refresh(stored)
    assert stored.min_block_duration_minutes is None


def test_bounds_conflict_rejected_a4(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-a4-{uuid4().hex[:8]}", "estimated_duration_minutes": 30},
    )
    task_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"min_block_duration_minutes": 200, "max_block_duration_minutes": 60},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CHUNKING_BOUNDS_CONFLICT"


def test_v4_assemble_includes_progress_fields() -> None:
    snap = assemble_snapshot(
        estimated_duration_minutes=90,
        min_block_duration_minutes=None,
        max_block_duration_minutes=None,
        deadline_at=datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc),
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
        snapshot_version=SNAPSHOT_VERSION_V4,
        worked_minutes=30,
        remaining_minutes=60,
        max_block_unbounded=False,
        keep_in_one_block=False,
    )
    assert snap["v"] == SNAPSHOT_VERSION_V4
    assert snap["duration"]["worked_minutes"] == 30
    assert snap["duration"]["min_inherit"] is True


def test_a1_cleared_bounds_read_user_default(
    client: TestClient, db_session: Session
) -> None:
    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200, settings.text
    defaults = settings.json()
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-a1-{uuid4().hex[:8]}", "estimated_duration_minutes": 90},
    )
    assert created.status_code in (200, 201), created.text
    task_id = created.json()["id"]
    cleared = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"min_block_duration_minutes": None, "max_block_duration_minutes": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json().get("code") != "CHUNKING_CUTOVER_PENDING"
    stored = db_session.get(Task, UUID(task_id))
    assert stored is not None
    db_session.refresh(stored)
    assert stored.min_block_duration_minutes is None
    assert stored.max_block_duration_minutes is None

    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    assert effective.status_code == 200, effective.text
    duration = effective.json()["duration"]
    assert duration["chunking_scheduling_effective"] is True
    assert duration["min_block_source"] == "user_default"
    assert duration["max_block_source"] == "user_default"
    assert duration["effective_min_block_duration_minutes"] == defaults["default_min_block_duration_minutes"]
    assert duration["effective_max_block_duration_minutes"] == defaults["default_max_block_duration_minutes"]


def test_a4_conflict_does_not_partial_write(client: TestClient, db_session: Session) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-a4-hold-{uuid4().hex[:8]}", "estimated_duration_minutes": 30},
    )
    task_id = created.json()["id"]
    seeded = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"min_block_duration_minutes": 25, "max_block_duration_minutes": 100},
    )
    assert seeded.status_code == 200, seeded.text
    conflict = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"min_block_duration_minutes": 200, "max_block_duration_minutes": 60},
    )
    assert conflict.status_code == 422
    assert conflict.json()["code"] == "CHUNKING_BOUNDS_CONFLICT"
    stored = db_session.get(Task, UUID(task_id))
    assert stored is not None
    db_session.refresh(stored)
    assert stored.min_block_duration_minutes == 25
    assert stored.max_block_duration_minutes == 100


def test_settings_no_limit_write_is_not_cutover_pending(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={"default_max_block_unbounded": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("code") != "CHUNKING_CUTOVER_PENDING"
    assert body["default_max_block_unbounded"] is True


def test_save_keep_in_one_with_shorter_pin_leaves_blocks(
    client: TestClient, db_session: Session
) -> None:
    """§0.1 saving vs scheduling: conflict is visible; the pin is not rewritten."""
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-save-{uuid4().hex[:8]}", "estimated_duration_minutes": 240},
    )
    assert created.status_code in (200, 201), created.text
    task_id = UUID(created.json()["id"])
    owner_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    pin_start = datetime.now(timezone.utc) + timedelta(hours=3)
    pin_end = pin_start + timedelta(hours=2)
    pin = ScheduledBlock(
        owner_id=owner_id,
        task_id=task_id,
        start_time=pin_start,
        end_time=pin_end,
        is_pinned=True,
    )
    db_session.add(pin)
    db_session.flush()
    pin_id = pin.id

    saved = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"keep_in_one_block": True, "max_block_unbounded": True},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json().get("code") != "CHUNKING_CUTOVER_PENDING"

    db_session.expire_all()
    rows = (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.task_id == task_id)
        .all()
    )
    assert len(rows) == 1
    stored_pin = rows[0]
    assert stored_pin.id == pin_id
    assert stored_pin.is_pinned is True
    assert stored_pin.start_time == pin_start
    assert stored_pin.end_time == pin_end

    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    assert effective.status_code == 200, effective.text
    conflicts = effective.json()["duration"]["keep_in_one_scheduling_conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["code"] == "keep_in_one_shorter_pin"
    assert conflicts[0]["detail"]["pins_protected"] is True
    assert conflicts[0]["detail"]["automatic_work_minutes"] == 0
    assert "240-minute" in conflicts[0]["message"]
    assert "120 minutes" in conflicts[0]["message"]
