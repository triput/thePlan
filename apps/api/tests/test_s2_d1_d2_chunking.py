"""S2-D1 settings default bounds validation; S2-D2 new-task inherit on create."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Task


def test_d1_settings_inverted_defaults_rejected(client: TestClient, db_session: Session) -> None:
    before = client.get("/api/v1/settings")
    assert before.status_code == 200, before.text
    prior_min = before.json()["default_min_block_duration_minutes"]
    prior_max = before.json()["default_max_block_duration_minutes"]

    response = client.patch(
        "/api/v1/settings",
        json={
            "default_min_block_duration_minutes": 180,
            "default_max_block_duration_minutes": 60,
            "default_max_block_unbounded": False,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CHUNKING_BOUNDS_CONFLICT"

    db_session.expire_all()
    after = client.get("/api/v1/settings")
    assert after.status_code == 200, after.text
    body = after.json()
    assert body["default_min_block_duration_minutes"] == prior_min
    assert body["default_max_block_duration_minutes"] == prior_max


def test_d1_partial_min_edit_inverts_rejected(client: TestClient) -> None:
    seeded = client.patch(
        "/api/v1/settings",
        json={
            "default_min_block_duration_minutes": 25,
            "default_max_block_duration_minutes": 90,
            "default_max_block_unbounded": False,
        },
    )
    assert seeded.status_code == 200, seeded.text

    conflict = client.patch(
        "/api/v1/settings",
        json={"default_min_block_duration_minutes": 120},
    )
    assert conflict.status_code == 422
    assert conflict.json()["code"] == "CHUNKING_BOUNDS_CONFLICT"

    ok = client.get("/api/v1/settings")
    assert ok.json()["default_min_block_duration_minutes"] == 25


def test_d1_turn_off_no_limit_when_max_below_min_rejected(client: TestClient) -> None:
    client.patch(
        "/api/v1/settings",
        json={
            "default_min_block_duration_minutes": 25,
            "default_max_block_duration_minutes": 90,
            "default_max_block_unbounded": False,
        },
    )
    high_min = client.patch(
        "/api/v1/settings",
        json={"default_min_block_duration_minutes": 180, "default_max_block_unbounded": True},
    )
    assert high_min.status_code == 200, high_min.text

    conflict = client.patch(
        "/api/v1/settings",
        json={"default_max_block_unbounded": False},
    )
    assert conflict.status_code == 422
    assert conflict.json()["code"] == "CHUNKING_BOUNDS_CONFLICT"

    still = client.get("/api/v1/settings")
    assert still.json()["default_max_block_unbounded"] is True


def test_d1_reject_leaves_inheriting_tasks_on_good_defaults(
    client: TestClient, db_session: Session
) -> None:
    client.patch(
        "/api/v1/settings",
        json={
            "default_min_block_duration_minutes": 25,
            "default_max_block_duration_minutes": 90,
            "default_max_block_unbounded": False,
        },
    )
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-d1-inherit-{uuid4().hex[:8]}", "estimated_duration_minutes": 30},
    )
    assert created.status_code in (200, 201), created.text
    task_id = created.json()["id"]

    bad = client.patch(
        "/api/v1/settings",
        json={"default_min_block_duration_minutes": 180, "default_max_block_duration_minutes": 60},
    )
    assert bad.status_code == 422

    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    assert effective.status_code == 200, effective.text
    duration = effective.json()["duration"]
    assert duration["min_block_source"] == "user_default"
    assert duration["effective_min_block_duration_minutes"] == 25
    assert duration["effective_max_block_duration_minutes"] == 90


def test_d2_new_task_inherits_user_defaults(client: TestClient, db_session: Session) -> None:
    client.patch(
        "/api/v1/settings",
        json={
            "default_min_block_duration_minutes": 25,
            "default_max_block_duration_minutes": 90,
            "default_max_block_unbounded": False,
        },
    )
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-d2-{uuid4().hex[:8]}", "estimated_duration_minutes": 45},
    )
    assert created.status_code in (200, 201), created.text
    task_id = UUID(created.json()["id"])

    stored = db_session.get(Task, task_id)
    assert stored is not None
    db_session.refresh(stored)
    assert stored.min_block_duration_minutes is None
    assert stored.max_block_duration_minutes is None
    assert stored.max_block_unbounded is False

    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    assert effective.status_code == 200, effective.text
    duration = effective.json()["duration"]
    assert duration["min_block_source"] == "user_default"
    assert duration["max_block_source"] == "user_default"
    assert duration["effective_min_block_duration_minutes"] == 25
    assert duration["effective_max_block_duration_minutes"] == 90


def test_d2_default_change_updates_inheriting_effective(client: TestClient) -> None:
    client.patch(
        "/api/v1/settings",
        json={
            "default_min_block_duration_minutes": 25,
            "default_max_block_duration_minutes": 90,
            "default_max_block_unbounded": False,
        },
    )
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"s2-d2-chg-{uuid4().hex[:8]}", "estimated_duration_minutes": 30},
    )
    task_id = created.json()["id"]

    updated = client.patch(
        "/api/v1/settings",
        json={
            "default_min_block_duration_minutes": 30,
            "default_max_block_duration_minutes": 100,
        },
    )
    assert updated.status_code == 200, updated.text

    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    duration = effective.json()["duration"]
    assert duration["min_block_source"] == "user_default"
    assert duration["effective_min_block_duration_minutes"] == 30
    assert duration["effective_max_block_duration_minutes"] == 100


def test_d2_explicit_bounds_on_create_stays_task_explicit(client: TestClient, db_session: Session) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"s2-d2-explicit-{uuid4().hex[:8]}",
            "estimated_duration_minutes": 60,
            "min_block_duration_minutes": 40,
            "max_block_duration_minutes": 80,
        },
    )
    assert created.status_code in (200, 201), created.text
    task_id = UUID(created.json()["id"])

    stored = db_session.get(Task, task_id)
    assert stored is not None
    db_session.refresh(stored)
    assert stored.min_block_duration_minutes == 40
    assert stored.max_block_duration_minutes == 80

    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    duration = effective.json()["duration"]
    assert duration["min_block_source"] == "task_explicit"
    assert duration["max_block_source"] == "task_explicit"
    assert duration["effective_min_block_duration_minutes"] == 40
    assert duration["effective_max_block_duration_minutes"] == 80
