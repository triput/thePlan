# ==============================================================================
#  File: apps/api/tests/test_s1_d7_d9_duration.py
#  Description: Regressions for Dex S1-D7 / S1-D8 / S1-D9 duration findings.
#  Component: Scheduling / Settings / Progress
#  Version: 1.0
#  Created: 2026-10-12
#  Last Update: 2026-10-12
# ==============================================================================

"""S1-D7–D9: settings duration validation, combined nominal conversion, progress replay.

Requires disposable PostgreSQL at Alembic ``030_progress_intent_hash``.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Task, TaskProgressEntry, UserSettings

_REQUIRED_REVISION = "030_progress_intent_hash"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _require_s1_head(db: Session) -> None:
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_REVISION, (
        f"test database alembic version is {version!r}; upgrade disposable PG to {_REQUIRED_REVISION}"
    )


def _settings_snapshot(client: TestClient) -> dict:
    response = client.get("/api/v1/settings")
    assert response.status_code == 200, response.text
    return response.json()


# --- S1-D7 -----------------------------------------------------------------


def test_d7_negative_and_zero_ints_strings_422(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    before = _settings_snapshot(client)
    for field in ("nominal_workday_minutes", "default_estimated_duration_minutes"):
        for value in (-1, 0, "-1", "0"):
            rejected = client.patch("/api/v1/settings", json={field: value})
            assert rejected.status_code == 422, (field, value, rejected.text)
            after = _settings_snapshot(client)
            assert after[field] == before[field]
            assert after["scheduling_revision"] == before["scheduling_revision"]


def test_d7_valid_int_and_string_equivalents_ok(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    for payload, expected_nominal in (
        ({"nominal_workday_minutes": 420}, 420),
        ({"nominal_workday_minutes": "420"}, 420),
        ({"nominal_workday_minutes": "7h"}, 420),
    ):
        ok = client.patch("/api/v1/settings", json=payload)
        assert ok.status_code == 200, (payload, ok.text)
        assert ok.json()["nominal_workday_minutes"] == expected_nominal

    for payload, expected_default in (
        ({"default_estimated_duration_minutes": 90}, 90),
        ({"default_estimated_duration_minutes": "90"}, 90),
        ({"default_estimated_duration_minutes": "1h 30m"}, 90),
    ):
        ok = client.patch("/api/v1/settings", json=payload)
        assert ok.status_code == 200, (payload, ok.text)
        assert ok.json()["default_estimated_duration_minutes"] == expected_default


# --- S1-D8 -----------------------------------------------------------------


def test_d8_combined_nominal_uses_new_value_for_workday_default(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    assert client.patch("/api/v1/settings", json={"nominal_workday_minutes": 480}).status_code == 200

    existing = client.post(
        "/api/v1/tasks",
        json={"title": f"d8-keep-{_uid()}", "estimated_duration_minutes": 240},
    )
    assert existing.status_code == 201, existing.text
    task_id = existing.json()["id"]

    for nominal_payload in (420, "420", "7h"):
        assert (
            client.patch("/api/v1/settings", json={"nominal_workday_minutes": 480}).status_code
            == 200
        )
        combined = client.patch(
            "/api/v1/settings",
            json={
                "nominal_workday_minutes": nominal_payload,
                "default_estimated_duration_minutes": "1 workday",
            },
        )
        assert combined.status_code == 200, (nominal_payload, combined.text)
        body = combined.json()
        assert body["nominal_workday_minutes"] == 420
        assert body["default_estimated_duration_minutes"] == 420
        note = body.get("duration_conversion_note") or ""
        assert "420" in note
        assert "480" not in note

        still = client.get(f"/api/v1/tasks/{task_id}").json()
        assert still["estimated_duration_minutes"] == 240


# --- S1-D9 -----------------------------------------------------------------


def test_d9_exact_retry_after_nominal_change_replays(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    assert client.patch("/api/v1/settings", json={"nominal_workday_minutes": 480}).status_code == 200
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"d9-replay-{_uid()}", "estimated_duration_minutes": 600},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    rev = _settings_snapshot(client)["scheduling_revision"]
    key = str(uuid.uuid4())
    body = {
        "idempotency_key": key,
        "minutes_worked": 20,
        "remaining_minutes": "1 workday",
        "expected_revision": rev,
    }
    first = client.post(f"/api/v1/tasks/{task_id}/progress-entries", json=body)
    assert first.status_code == 200, first.text
    assert first.json()["replayed"] is False
    assert first.json()["remaining_estimate_minutes"] == 480
    assert first.json()["time_worked_minutes"] == 20

    assert client.patch("/api/v1/settings", json={"nominal_workday_minutes": 420}).status_code == 200

    replay = client.post(f"/api/v1/tasks/{task_id}/progress-entries", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["remaining_estimate_minutes"] == 480
    assert replay.json()["time_worked_minutes"] == 20
    assert replay.json()["entry"]["remaining_minutes"] == 480

    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    count = (
        db_session.query(TaskProgressEntry)
        .filter(TaskProgressEntry.task_id == uuid.UUID(task_id))
        .count()
    )
    assert count == 1
    task = db_session.get(Task, uuid.UUID(task_id))
    assert task is not None
    assert task.worked_minutes == 20
    assert task.remaining_minutes == 480
    settings = (
        db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    )
    assert settings.nominal_workday_minutes == 420


def test_d9_changed_payload_same_key_rejects(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    assert client.patch("/api/v1/settings", json={"nominal_workday_minutes": 480}).status_code == 200
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"d9-conflict-{_uid()}", "estimated_duration_minutes": 600},
    )
    task_id = created.json()["id"]
    rev = _settings_snapshot(client)["scheduling_revision"]
    key = str(uuid.uuid4())
    first = client.post(
        f"/api/v1/tasks/{task_id}/progress-entries",
        json={
            "idempotency_key": key,
            "minutes_worked": 20,
            "remaining_minutes": "1 workday",
            "expected_revision": rev,
        },
    )
    assert first.status_code == 200, first.text

    # Same key, different submitted remaining (even if it would resolve similarly).
    changed = client.post(
        f"/api/v1/tasks/{task_id}/progress-entries",
        json={
            "idempotency_key": key,
            "minutes_worked": 20,
            "remaining_minutes": 480,
            "expected_revision": rev,
        },
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["code"] == "IDEMPOTENCY_KEY_REUSE"
    count = (
        db_session.query(TaskProgressEntry)
        .filter(TaskProgressEntry.task_id == uuid.UUID(task_id))
        .count()
    )
    assert count == 1


def test_d9_sequential_same_key_replay_still_safe(
    client: TestClient, db_session: Session
) -> None:
    """Concurrent safety covered by D3; sequential exact retry remains replay-once."""
    _require_s1_head(db_session)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"d9-seq-{_uid()}", "estimated_duration_minutes": 100},
    )
    task_id = created.json()["id"]
    rev = _settings_snapshot(client)["scheduling_revision"]
    key = str(uuid.uuid4())
    body = {
        "idempotency_key": key,
        "minutes_worked": 15,
        "remaining_minutes": 40,
        "expected_revision": rev,
    }
    first = client.post(f"/api/v1/tasks/{task_id}/progress-entries", json=body)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/tasks/{task_id}/progress-entries", json=body)
    assert second.status_code == 200, second.text
    assert second.json()["replayed"] is True
    assert second.json()["time_worked_minutes"] == 15
    assert second.json()["remaining_estimate_minutes"] == 40
    count = (
        db_session.query(TaskProgressEntry)
        .filter(TaskProgressEntry.task_id == uuid.UUID(task_id))
        .count()
    )
    assert count == 1
