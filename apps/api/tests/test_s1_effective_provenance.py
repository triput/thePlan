"""S1 effective/provenance READ contract (A1–A7 acceptance packet)."""

from __future__ import annotations

import uuid
from datetime import time

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import AvailabilityPolicy, AvailabilityWindow, UserSettings
from app.models.enums import AvailabilityPolicySlug
from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY
from app.services.availability_seed import ensure_default_availability_policies


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _require_s1_head(db: Session) -> None:
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "030_progress_intent_hash", (
        f"test database alembic version is {version!r}; upgrade disposable PG to 030"
    )


def _effective(client: TestClient, task_id: str, *, on: str | None = None) -> dict:
    params = {"on": on} if on else None
    response = client.get(f"/api/v1/tasks/{task_id}/scheduling/effective", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _map(
    client: TestClient,
    *,
    name: str | None = None,
    strict_mode: bool = False,
    bands: list[dict] | None = None,
) -> dict:
    payload: dict = {
        "name": name or f"Map {_uid()}",
        "strict_mode": strict_mode,
        "bands": bands
        if bands is not None
        else [
            {
                "tier": "green",
                "start_time": "09:00",
                "end_time": "12:00",
                "days_of_week": 127,
                "sort_order": 0,
            }
        ],
    }
    created = client.post("/api/v1/focus-windows", json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def _windows(weekdays: tuple[int, ...] | range, start: str, duration: int) -> list[dict]:
    return [
        {
            "weekday": day,
            "start_time": start,
            "duration_minutes": duration,
            "sort_order": 0,
        }
        for day in weekdays
    ]


def test_a1_inheritance_and_clear_restores_origin(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    ensure_default_availability_policies(db_session, owner_id)
    db_session.flush()

    project_map = _map(client, name=f"Project map {_uid()}")
    task_map = _map(client, name=f"Task map {_uid()}")

    project = client.post(
        "/api/v1/projects",
        json={"title": f"P {_uid()}", "preferred_time_window_id": project_map["id"]},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"T {_uid()}", "project_id": project["id"]},
    ).json()

    inherited = _effective(client, task["id"])
    assert inherited["legacy_time_map_source"] == "project"
    assert inherited["time_map"]["origin"]["project_preferred_time_window_id"] == project_map["id"]
    assert inherited["time_map"]["effective_map_id"] == project_map["id"]

    client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": task_map["id"]},
    )
    overridden = _effective(client, task["id"])
    assert overridden["legacy_time_map_source"] == "task"
    assert overridden["time_map"]["origin"]["task_preferred_time_window_id"] == task_map["id"]

    client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"preferred_time_window_id": None},
    )
    restored = _effective(client, task["id"])
    assert restored["legacy_time_map_source"] == "project"
    assert restored["time_map"]["origin"]["task_preferred_time_window_id"] is None
    assert restored["time_map"]["effective_map_id"] == project_map["id"]


def test_a2_unclassified_fallback(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    task = client.post("/api/v1/tasks", json={"title": f"Fallback {_uid()}"}).json()
    body = _effective(client, task["id"])

    assert body["time_map"]["assignment_status"] == "unclassified_fallback"
    assert body["time_map"]["empty_kind"] == "no_assignment_fallback"
    assert body["general_policy_scheduling_effective"] is False
    assert body["working_hours_placer_active"] is True
    assert body["general_policy_saved"]["placer_active"] is False
    assert body["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY
    kinds = {row["kind"] for row in body["sources"]}
    assert "legacy_unclassified" in kinds
    assert "availability_general" in kinds


def test_a3_empty_map_distinctions(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    strict_empty = _map(
        client,
        name=f"Strict empty {_uid()}",
        strict_mode=True,
        bands=[],
    )
    loose_empty = _map(
        client,
        name=f"Loose empty {_uid()}",
        strict_mode=False,
        bands=[],
    )
    task_strict = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Strict {_uid()}",
            "preferred_time_window_id": strict_empty["id"],
        },
    ).json()
    task_loose = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Loose {_uid()}",
            "preferred_time_window_id": loose_empty["id"],
        },
    ).json()

    strict_body = _effective(client, task_strict["id"])
    assert strict_body["time_map"]["empty_kind"] == "assigned_empty_strict"
    assert strict_body["time_map"]["strict_mode"] is True
    assert strict_body["time_map"]["band_count"] == 0

    loose_body = _effective(client, task_loose["id"])
    assert loose_body["time_map"]["empty_kind"] == "assigned_empty_nonstrict"
    assert loose_body["time_map"]["strict_mode"] is False


def test_d6_dated_empty_kind_uses_resolved_day_not_whole_map(
    client: TestClient, db_session: Session
) -> None:
    """D6: dated read classifies empty_kind from display day bands/strict, not whole map."""
    _require_s1_head(db_session)
    mon_only_strict = _map(
        client,
        name=f"Mon strict {_uid()}",
        strict_mode=True,
        bands=[
            {
                "tier": "green",
                "start_time": "09:00",
                "end_time": "12:00",
                "days_of_week": 1,
                "sort_order": 0,
            }
        ],
    )
    mon_only_loose = _map(
        client,
        name=f"Mon loose {_uid()}",
        strict_mode=False,
        bands=[
            {
                "tier": "green",
                "start_time": "09:00",
                "end_time": "12:00",
                "days_of_week": 1,
                "sort_order": 0,
            }
        ],
    )
    task_strict = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Weekday strict {_uid()}",
            "preferred_time_window_id": mon_only_strict["id"],
        },
    ).json()
    task_loose = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Weekday loose {_uid()}",
            "preferred_time_window_id": mon_only_loose["id"],
        },
    ).json()
    # 2026-10-13 is Tuesday; maps have Monday bands only (whole-map band_count > 0).
    strict_body = _effective(client, task_strict["id"], on="2026-10-13")
    assert strict_body["time_map"]["band_count"] == 0
    assert strict_body["time_map"]["empty_kind"] == "assigned_empty_strict"
    assert strict_body["dated_resolution"]["performed"] is True
    strict_empty_src = next(
        s for s in strict_body["sources"] if s["kind"] == "time_map_empty_strict"
    )
    assert strict_empty_src["placer_active"] is True

    loose_body = _effective(client, task_loose["id"], on="2026-10-13")
    assert loose_body["time_map"]["band_count"] == 0
    assert loose_body["time_map"]["empty_kind"] == "assigned_empty_nonstrict"


def test_d6_dated_override_empty_strict_base_with_banded_override(
    client: TestClient, db_session: Session
) -> None:
    """Dex: strict empty base map + dated override with bands → not_applicable, no empty-strict source."""
    _require_s1_head(db_session)
    base = _map(
        client,
        name=f"Strict empty base {_uid()}",
        strict_mode=True,
        bands=[],
    )
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Override fill {_uid()}",
            "preferred_time_window_id": base["id"],
        },
    ).json()
    override = client.post(
        f"/api/v1/focus-windows/{base['id']}/overrides",
        json={
            "local_start_date": "2026-10-12",
            "local_end_date": "2026-10-14",
            "timezone": "America/Los_Angeles",
            "strict_mode": True,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "17:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert override.status_code == 201, override.text

    body = _effective(client, task["id"], on="2026-10-13")
    assert body["time_map"]["band_count"] == 1
    assert body["time_map"]["empty_kind"] == "not_applicable"
    assert body["time_map"]["strict_mode"] is True
    empty_strict_kinds = {
        s["kind"] for s in body["sources"] if s["kind"] == "time_map_empty_strict"
    }
    assert empty_strict_kinds == set()


def test_d6_dated_override_nonempty_base_with_empty_strict_override(
    client: TestClient, db_session: Session
) -> None:
    """Dex: banded strict base + dated empty strict override → assigned_empty_strict on that day."""
    _require_s1_head(db_session)
    base = _map(
        client,
        name=f"Strict banded base {_uid()}",
        strict_mode=True,
    )
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Override clear {_uid()}",
            "preferred_time_window_id": base["id"],
        },
    ).json()
    override = client.post(
        f"/api/v1/focus-windows/{base['id']}/overrides",
        json={
            "local_start_date": "2026-10-12",
            "local_end_date": "2026-10-14",
            "timezone": "America/Los_Angeles",
            "strict_mode": True,
            "bands": [],
        },
    )
    assert override.status_code == 201, override.text

    body = _effective(client, task["id"], on="2026-10-13")
    assert body["time_map"]["band_count"] == 0
    assert body["time_map"]["empty_kind"] == "assigned_empty_strict"
    assert body["time_map"]["strict_mode"] is True
    strict_src = next(
        s for s in body["sources"] if s["kind"] == "time_map_empty_strict"
    )
    assert "Strict empty map" in (strict_src["detail"] or "")
    assert strict_src["placer_active"] is True


def test_a4_dated_override_and_skip_without_on(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    window = _map(client, name=f"Override base {_uid()}")
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Override task {_uid()}",
            "preferred_time_window_id": window["id"],
        },
    ).json()
    override = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-12",
            "local_end_date": "2026-10-14",
            "timezone": "America/Los_Angeles",
            "strict_mode": True,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "17:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert override.status_code == 201, override.text
    override_id = override.json()["id"]

    skipped = _effective(client, task["id"])
    assert skipped["dated_resolution"]["performed"] is False
    assert skipped["dated_resolution"]["on"] is None
    assert "not performed" in (skipped["dated_resolution"]["note"] or "").lower()

    on_day = _effective(client, task["id"], on="2026-10-13")
    dated = on_day["dated_resolution"]
    assert dated["performed"] is True
    assert dated["on"] == "2026-10-13"
    assert dated["override"] is not None
    assert dated["override"]["override_id"] == override_id
    assert dated["override"]["payload"]["base_map_id"] == window["id"]
    assert dated["override"]["payload"]["inheritance_source"] == "task"
    assert on_day["time_map"]["strict_mode"] is True
    assert on_day["time_map"]["band_count"] >= 1
    replaces = dated["replaces"]
    assert replaces is not None
    assert replaces["effective_strict_mode"] is True
    assert replaces["base_map_id"] == window["id"]


def test_effective_read_survives_non_mirrorable_working_windows(
    client: TestClient, db_session: Session
) -> None:
    """GET must not 422 when saved Working windows cannot mirror (read-only preview)."""
    _require_s1_head(db_session)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    ensure_default_availability_policies(db_session, owner_id)
    work = (
        db_session.query(AvailabilityPolicy)
        .filter(
            AvailabilityPolicy.owner_id == owner_id,
            AvailabilityPolicy.slug == AvailabilityPolicySlug.work,
        )
        .one()
    )
    db_session.add(
        AvailabilityWindow(
            owner_id=owner_id,
            policy_id=work.id,
            weekday=0,
            start_time=time(8, 0),
            end_time=time(12, 0),
            ends_next_day=False,
            duration_minutes=240,
            sort_order=99,
        )
    )
    db_session.flush()

    task = client.post("/api/v1/tasks", json={"title": f"Read safe {_uid()}"}).json()
    response = client.get(f"/api/v1/tasks/{task['id']}/scheduling/effective")
    assert response.status_code == 200, response.text
    saved = response.json()["working_policy_saved"]
    assert saved["diverges_from_legacy"] is True
    assert saved["placer_active"] is False


def test_a5_working_divergence_shows_both(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    settings.workweek_days = 3
    settings.workday_start_local = time(10, 0)
    settings.workday_minutes = 360
    db_session.flush()

    ensure_default_availability_policies(db_session, owner_id)
    db_session.flush()

    patched = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": _windows((1, 2, 3, 4, 5), "11:00", 300)},
    )
    assert patched.status_code == 200, patched.text

    task = client.post("/api/v1/tasks", json={"title": f"Diverge {_uid()}"}).json()
    body = _effective(client, task["id"])

    assert body["working_hours_active"]["workweek_days"] == 3
    assert body["working_hours_active"]["placer_active"] is True
    assert body["working_policy_saved"]["placer_active"] is False
    assert body["working_policy_saved"]["diverges_from_legacy"] is True
    assert len(body["working_policy_saved"]["windows"]) == 5
    work_source = next(s for s in body["sources"] if s["kind"] == "availability_work")
    assert work_source["placer_active"] is False
    assert "Diverges" in (work_source["detail"] or "")


def test_a6_api_structured_fields_present(client: TestClient, db_session: Session) -> None:
    _require_s1_head(db_session)
    task = client.post("/api/v1/tasks", json={"title": f"Shape {_uid()}"}).json()
    body = _effective(client, task["id"])
    for key in (
        "time_map",
        "working_hours_active",
        "working_policy_saved",
        "general_policy_saved",
        "personal_policy_saved",
        "dated_resolution",
        "duration",
    ):
        assert key in body
    assert body["duration"]["placement_effort_minutes"] == body["placement_effort_minutes"]
    assert body["duration"]["estimated_duration_minutes"] == body["duration"]["original_estimate_minutes"]
    assert body["duration"]["chunking_scheduling_effective"] is True
