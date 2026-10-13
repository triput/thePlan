"""S1 duration foundations (D-A1–D-A7). Requires disposable PG @ Alembic 029."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Task, UserSettings


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _require_s1_head(db: Session) -> None:
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "030_progress_intent_hash", (
        f"test database alembic version is {version!r}; upgrade disposable PG to 030"
    )


def test_d_a1_create_friendly_duration_variants(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    for label, payload in (
        ("1h 30m", {"estimated_duration_minutes": "1h 30m"}),
        ("90", {"estimated_duration_minutes": "90"}),
        ("1.5h", {"estimated_duration_minutes": "1.5h"}),
    ):
        created = client.post(
            "/api/v1/tasks",
            json={"title": f"dur-{label}-{_uid()}", **payload},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["estimated_duration_minutes"] == 90
        assert body["original_estimate_minutes"] == 90
        assert body["remaining_estimate_minutes"] == 90
        assert body["time_worked_minutes"] == 0


def test_d_a2_remaining_edit_friendly_original_unchanged(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"rem-{_uid()}", "estimated_duration_minutes": 120},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    rev = client.get("/api/v1/settings").json()["scheduling_revision"]
    patched = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"remaining_estimate_minutes": "45m", "expected_revision": rev},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["original_estimate_minutes"] == 120
    assert body["estimated_duration_minutes"] == 120
    assert body["remaining_estimate_minutes"] == 45


def test_d_a3_original_immutable_unchanged(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"imm-{_uid()}", "estimated_duration_minutes": 40},
    )
    task_id = created.json()["id"]
    blocked = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"estimated_duration_minutes": "1h"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "ORIGINAL_ESTIMATE_IMMUTABLE"
    read_back = client.get(f"/api/v1/tasks/{task_id}").json()
    assert read_back["estimated_duration_minutes"] == 40


def test_d_a4_nominal_change_does_not_rewrite_estimates(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    owner_id = client.get("/api/v1/auth/me").json()["id"]
    settings = (
        db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    )
    settings.nominal_workday_minutes = 480
    db_session.flush()

    created = client.post(
        "/api/v1/tasks",
        json={"title": f"wd-{_uid()}", "estimated_duration_minutes": "1 workday"},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    assert created.json()["estimated_duration_minutes"] == 480
    assert created.json()["duration_conversion_note"] is not None

    settings.nominal_workday_minutes = 450
    db_session.commit()

    read_back = client.get(f"/api/v1/tasks/{task_id}").json()
    assert read_back["estimated_duration_minutes"] == 480

    settings_patch = client.patch(
        "/api/v1/settings",
        json={"nominal_workday_minutes": "7h 30m"},
    )
    assert settings_patch.status_code == 200, settings_patch.text
    assert settings_patch.json()["nominal_workday_minutes"] == 450
    still = client.get(f"/api/v1/tasks/{task_id}").json()
    assert still["estimated_duration_minutes"] == 480


def test_d_a5_bounds_inherit_and_no_limit_writes_accepted(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"bounds-{_uid()}", "estimated_duration_minutes": 30},
    )
    task_id = created.json()["id"]
    inherit_min = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"min_block_duration_minutes": None},
    )
    assert inherit_min.status_code == 200, inherit_min.text

    no_limit = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"max_block_unbounded": True},
    )
    assert no_limit.status_code == 200, no_limit.text

    ok = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"min_block_duration_minutes": 20, "max_block_duration_minutes": 90},
    )
    assert ok.status_code == 200


def test_d_a5_effective_inherited_bounds_preview(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"inherit-bounds-{_uid()}", "estimated_duration_minutes": 30},
    )
    task_id = uuid.UUID(created.json()["id"])
    task_row = db_session.get(Task, task_id)
    assert task_row is not None
    task_row.min_block_duration_minutes = None
    task_row.max_block_duration_minutes = None
    db_session.commit()

    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective")
    assert effective.status_code == 200, effective.text
    duration = effective.json()["duration"]
    assert duration["chunking_scheduling_effective"] is True
    assert duration["effective_min_block_duration_minutes"] is not None
    assert duration["effective_max_block_duration_minutes"] is not None
    assert duration.get("inherited_bounds_preview") is None
    assert "preview-only" not in duration["note"].lower()


def test_d_a6_rejects_ambiguous_day_shorthand(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    response = client.post(
        "/api/v1/tasks",
        json={"title": f"bad-{_uid()}", "estimated_duration_minutes": "2d"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "AMBIGUOUS_DURATION_UNIT"


def test_d_a7_effective_duration_labels_match_task_progress(
    client: TestClient, db_session: Session
) -> None:
    _require_s1_head(db_session)
    created = client.post(
        "/api/v1/tasks",
        json={"title": f"eff-{_uid()}", "estimated_duration_minutes": 60},
    )
    task_id = created.json()["id"]
    rev = client.get("/api/v1/settings").json()["scheduling_revision"]
    client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"remaining_estimate_minutes": 25, "expected_revision": rev},
    )
    task = client.get(f"/api/v1/tasks/{task_id}").json()
    effective = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective").json()
    duration = effective["duration"]
    assert duration["original_estimate_minutes"] == task["original_estimate_minutes"]
    assert duration["estimated_duration_minutes"] == task["estimated_duration_minutes"]
    assert duration["time_worked_minutes"] == task["time_worked_minutes"]
    assert duration["remaining_estimate_minutes"] == task["remaining_estimate_minutes"]
    assert duration["placement_effort_minutes"] == 25
    assert duration["chunking_scheduling_effective"] is True
