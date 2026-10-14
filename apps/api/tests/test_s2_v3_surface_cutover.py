"""S2-V3 Jules surface: reject legacy workweek settings, effective-read honesty, A11e."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.s2_v3_availability_guard import (
    LEGACY_WORKWEEK_REJECT_CODE,
    V3_SCHEDULING_EFFECTIVE_NOTE,
    s2_v3_availability_cutover_live,
)
from app.services.scheduling_revision import SETTINGS_SCHEDULING_FIELDS


@pytest.fixture(autouse=True)
def _require_v3_live() -> None:
    assert s2_v3_availability_cutover_live(), "tests assume S2-V3 cutover flag is True at tip"


def test_deprecated_settings_fields_not_scheduling_revision_fields() -> None:
    assert "workweek_days" not in SETTINGS_SCHEDULING_FIELDS
    assert "workday_start_local" not in SETTINGS_SCHEDULING_FIELDS
    assert "workday_minutes" not in SETTINGS_SCHEDULING_FIELDS
    assert "nominal_workday_minutes" not in SETTINGS_SCHEDULING_FIELDS


def test_patch_settings_rejects_legacy_workweek_fields(client: TestClient) -> None:
    for payload in (
        {"workweek_days": 5},
        {"workday_start_local": "09:00"},
        {"workday_minutes": 480},
        {"workweek_days": 0, "inter_block_buffer_minutes": 10},
    ):
        response = client.patch("/api/v1/settings", json=payload)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == LEGACY_WORKWEEK_REJECT_CODE
        assert "availability-policies/work" in body["detail"]


def test_a11e_buffer_only_patch_with_legacy_zero_workweek_in_db(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    from app.models import UserSettings

    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    settings.workweek_days = 0
    db_session.flush()

    before = client.get("/api/v1/settings").json()
    start_rev = before["scheduling_revision"]

    patched = client.patch(
        "/api/v1/settings",
        json={"inter_block_buffer_minutes": before["inter_block_buffer_minutes"] + 1},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["workweek_days"] == 0
    assert body["inter_block_buffer_minutes"] == before["inter_block_buffer_minutes"] + 1
    assert body["scheduling_revision"] == start_rev + 1

    work = client.get("/api/v1/availability-policies/work")
    assert work.status_code == 200


def test_nominal_workday_minutes_still_patchable(client: TestClient) -> None:
    before = client.get("/api/v1/settings").json()
    nominal = before["nominal_workday_minutes"]
    target = 450 if nominal != 450 else 451
    patched = client.patch("/api/v1/settings", json={"nominal_workday_minutes": target})
    assert patched.status_code == 200, patched.text
    assert patched.json()["nominal_workday_minutes"] == target


def test_availability_policies_scheduling_effective_flags(client: TestClient) -> None:
    work = client.get("/api/v1/availability-policies/work").json()
    general = client.get("/api/v1/availability-policies/general").json()
    personal = client.get("/api/v1/availability-policies/personal").json()
    assert work["scheduling_effective"] is True
    assert general["scheduling_effective"] is True
    assert personal["scheduling_effective"] is False
    assert V3_SCHEDULING_EFFECTIVE_NOTE in work["scheduling_effective_note"]


def test_task_effective_read_v3_honesty(client: TestClient) -> None:
    task = client.post("/api/v1/tasks", json={"title": f"V3 effective {uuid.uuid4().hex[:6]}"}).json()
    body = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective").json()
    assert body["general_policy_scheduling_effective"] is True
    assert body["working_hours_placer_active"] is False
    assert body["working_policy_saved"]["placer_active"] is True
    assert body["general_policy_saved"]["placer_active"] is True
    assert V3_SCHEDULING_EFFECTIVE_NOTE in body["scheduling_effective_note"]
    legacy = next(s for s in body["sources"] if s["kind"] == "legacy_workweek")
    assert legacy["placer_active"] is False
