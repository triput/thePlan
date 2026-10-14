"""S2-V3: Working window writes do not rewrite the Monday-first legacy mirror.

``workweek_days`` remains a deprecated column. Tuesday–Saturday, weekend-only,
Monday-first, gapped, and mixed-hours patterns store on the Working policy,
bump ``scheduling_revision``, and leave ``workweek_*`` untouched.
"""

from __future__ import annotations

import uuid
from datetime import date, time

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import UserSettings
from app.scheduler.placement import is_workday
from app.services.s2_v3_availability_guard import V3_SCHEDULING_EFFECTIVE_NOTE
from app.services.availability_seed import ensure_default_availability_policies

# 2026-10-12 is a Monday. Legacy eligibility is weekday() < workweek_days.
_MONDAY = date(2026, 10, 12)
_THURSDAY = date(2026, 10, 15)
_FRIDAY = date(2026, 10, 16)
_SATURDAY = date(2026, 10, 17)
_SUNDAY = date(2026, 10, 18)


def _assert_untouched(settings: UserSettings) -> None:
    assert settings.workweek_days == 3
    assert settings.workday_start_local == time(10, 0)
    assert settings.workday_minutes == 360


def _require_s1_head(db: Session) -> None:
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "030_progress_intent_hash", (
        f"test database alembic version is {version!r}; "
        "upgrade the disposable test database to 030_progress_intent_hash before this suite"
    )


def _windows(weekdays: tuple[int, ...] | range, start: str, duration: int) -> list[dict[str, object]]:
    return [
        {
            "weekday": day,
            "start_time": start,
            "duration_minutes": duration,
            "sort_order": 0,
        }
        for day in weekdays
    ]


def _prepare_legacy_mirror(client: TestClient, db: Session) -> tuple[uuid.UUID, int]:
    """Pin a Monday–Wednesday mirror that is neither 5 nor 2, and ensure Working exists."""
    _require_s1_head(db)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    settings.workweek_days = 3
    settings.workday_start_local = time(10, 0)
    settings.workday_minutes = 360
    revision = int(settings.scheduling_revision)
    db.flush()
    existing = client.get("/api/v1/availability-policies/work")
    if existing.status_code == 404:
        ensure_default_availability_policies(db, owner_id)
        db.flush()
    elif existing.status_code != 200:
        raise AssertionError(existing.text)
    return owner_id, revision


def _stored_mirror(db: Session, owner_id: uuid.UUID) -> UserSettings:
    db.expire_all()
    return db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()


def test_api_shifted_working_weeks_stay_config_only(
    client: TestClient, db_session: Session
) -> None:
    owner_id, revision = _prepare_legacy_mirror(client, db_session)

    tue_sat = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": _windows((1, 2, 3, 4, 5), "11:00", 300)},
    )
    assert tue_sat.status_code == 200, tue_sat.text
    tue_body = tue_sat.json()
    assert tue_body["scheduling_effective"] is True
    assert tue_body["scheduling_effective_note"] == V3_SCHEDULING_EFFECTIVE_NOTE
    assert [window["weekday"] for window in tue_body["windows"]] == [1, 2, 3, 4, 5]
    assert {window["start_time"] for window in tue_body["windows"]} == {"11:00"}
    assert {window["duration_minutes"] for window in tue_body["windows"]} == {300}

    stored = _stored_mirror(db_session, owner_id)
    _assert_untouched(stored)
    assert int(stored.scheduling_revision) == revision + 1
    settings_body = client.get("/api/v1/settings")
    assert settings_body.status_code == 200, settings_body.text
    assert settings_body.json()["workweek_days"] == 3
    assert settings_body.json()["workday_start_local"] == "10:00"
    assert settings_body.json()["workday_minutes"] == 360
    reread = client.get("/api/v1/availability-policies/work")
    assert reread.status_code == 200, reread.text
    assert [window["weekday"] for window in reread.json()["windows"]] == [1, 2, 3, 4, 5]
    assert is_workday(_MONDAY, stored.workweek_days) is True
    assert is_workday(_SATURDAY, stored.workweek_days) is False

    weekend = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": _windows((5, 6), "09:00", 120)},
    )
    assert weekend.status_code == 200, weekend.text
    weekend_body = weekend.json()
    assert weekend_body["scheduling_effective"] is True
    assert weekend_body["scheduling_effective_note"] == V3_SCHEDULING_EFFECTIVE_NOTE
    assert [window["weekday"] for window in weekend_body["windows"]] == [5, 6]

    stored = _stored_mirror(db_session, owner_id)
    _assert_untouched(stored)
    assert int(stored.scheduling_revision) == revision + 2
    settings_body = client.get("/api/v1/settings")
    assert settings_body.json()["workweek_days"] == 3
    assert settings_body.json()["workday_start_local"] == "10:00"
    assert settings_body.json()["workday_minutes"] == 360
    assert is_workday(_SATURDAY, stored.workweek_days) is False
    assert is_workday(_SUNDAY, stored.workweek_days) is False


def test_api_monday_first_working_week_round_trips_into_mirrors(
    client: TestClient, db_session: Session
) -> None:
    owner_id, revision = _prepare_legacy_mirror(client, db_session)

    patched = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": _windows(range(4), "08:30", 240)},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["scheduling_effective"] is True
    assert body["scheduling_effective_note"] == V3_SCHEDULING_EFFECTIVE_NOTE
    assert [window["weekday"] for window in body["windows"]] == [0, 1, 2, 3]
    assert body["windows"][0]["start_time"] == "08:30"
    assert body["windows"][0]["duration_minutes"] == 240
    assert body["windows"][0]["end_time"] == "12:30"

    stored = _stored_mirror(db_session, owner_id)
    _assert_untouched(stored)
    assert int(stored.scheduling_revision) == revision + 1
    settings_body = client.get("/api/v1/settings")
    assert settings_body.status_code == 200, settings_body.text
    assert settings_body.json()["workweek_days"] == 3
    assert settings_body.json()["workday_start_local"] == "10:00"
    assert settings_body.json()["workday_minutes"] == 360
    assert is_workday(_MONDAY, stored.workweek_days) is True
    assert is_workday(_THURSDAY, stored.workweek_days) is False
    assert is_workday(_FRIDAY, stored.workweek_days) is False


def test_api_split_gap_mixed_and_general_store_and_bump(
    client: TestClient, db_session: Session
) -> None:
    owner_id, revision = _prepare_legacy_mirror(client, db_session)
    split = client.patch(
        "/api/v1/availability-policies/work",
        json={
            "windows": [
                {"weekday": 0, "start_time": "09:00", "duration_minutes": 120, "sort_order": 0},
                {"weekday": 0, "start_time": "14:00", "duration_minutes": 90, "sort_order": 1},
                {"weekday": 2, "start_time": "11:00", "duration_minutes": 60, "sort_order": 0},
            ]
        },
    )
    assert split.status_code == 200, split.text
    weekdays = [window["weekday"] for window in split.json()["windows"]]
    assert weekdays == [0, 0, 2]
    stored = _stored_mirror(db_session, owner_id)
    _assert_untouched(stored)
    assert int(stored.scheduling_revision) == revision + 1

    general = client.patch(
        "/api/v1/availability-policies/general",
        json={"windows": _windows((1,), "13:00", 60)},
    )
    assert general.status_code == 200, general.text
    stored = _stored_mirror(db_session, owner_id)
    _assert_untouched(stored)
    assert int(stored.scheduling_revision) == revision + 2
