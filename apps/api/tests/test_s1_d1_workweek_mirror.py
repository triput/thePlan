"""S1-D1: shifted Working weeks must not rewrite the Monday-first legacy mirror.

``workweek_days`` means Monday through N (``is_workday``). Tuesday–Saturday and
weekend-only windows are saved as config (``scheduling_effective: false``) and
leave ``workweek_*`` / ``scheduling_revision`` alone. Monday-first same-hours
patterns still round-trip into the mirrors.
"""

from __future__ import annotations

import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import AvailabilityWindow, UserSettings
from app.scheduler.placement import is_workday
from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY
from app.services.availability_policies import _sync_workweek_from_working_windows
from app.services.availability_seed import ensure_default_availability_policies

# 2026-10-12 is a Monday. Legacy eligibility is weekday() < workweek_days.
_MONDAY = date(2026, 10, 12)
_THURSDAY = date(2026, 10, 15)
_FRIDAY = date(2026, 10, 16)
_SATURDAY = date(2026, 10, 17)
_SUNDAY = date(2026, 10, 18)


def _window(weekday: int, start: time, duration: int) -> AvailabilityWindow:
    return AvailabilityWindow(
        weekday=weekday,
        start_time=start,
        duration_minutes=duration,
        end_time=start,
        ends_next_day=False,
    )


def _baseline() -> UserSettings:
    return UserSettings(
        workweek_days=3,
        workday_start_local=time(10, 0),
        workday_minutes=360,
    )


def _assert_untouched(settings: UserSettings) -> None:
    assert settings.workweek_days == 3
    assert settings.workday_start_local == time(10, 0)
    assert settings.workday_minutes == 360


def test_shifted_contiguous_patterns_do_not_rewrite_legacy_mirror() -> None:
    tue_sat = _baseline()
    mirrored = _sync_workweek_from_working_windows(
        tue_sat,
        [_window(day, time(11, 0), 300) for day in (1, 2, 3, 4, 5)],
    )
    assert mirrored is False
    _assert_untouched(tue_sat)
    # The bug wrote 5, which is Monday–Friday: Monday eligible, Saturday excluded.
    assert is_workday(_MONDAY, tue_sat.workweek_days) is True
    assert is_workday(_SATURDAY, tue_sat.workweek_days) is False
    assert is_workday(_THURSDAY, tue_sat.workweek_days) is False

    weekend = _baseline()
    mirrored = _sync_workweek_from_working_windows(
        weekend,
        [_window(day, time(9, 0), 120) for day in (5, 6)],
    )
    assert mirrored is False
    _assert_untouched(weekend)
    # A silent write of 2 would have meant Monday–Tuesday, not the weekend.
    assert weekend.workweek_days != 2
    assert is_workday(_SATURDAY, weekend.workweek_days) is False
    assert is_workday(_SUNDAY, weekend.workweek_days) is False

    tuesday_only = _baseline()
    mirrored = _sync_workweek_from_working_windows(
        tuesday_only,
        [_window(1, time(9, 0), 480)],
    )
    assert mirrored is False
    _assert_untouched(tuesday_only)


def test_monday_first_pattern_still_updates_legacy_mirror() -> None:
    settings = _baseline()
    mirrored = _sync_workweek_from_working_windows(
        settings,
        [_window(day, time(8, 30), 240) for day in range(4)],
    )
    assert mirrored is True
    assert settings.workweek_days == 4
    assert settings.workday_start_local == time(8, 30)
    assert settings.workday_minutes == 240
    assert is_workday(_MONDAY, settings.workweek_days) is True
    assert is_workday(_THURSDAY, settings.workweek_days) is True
    assert is_workday(_FRIDAY, settings.workweek_days) is False


def test_noncontiguous_working_pattern_still_rejects_without_mirror_write() -> None:
    settings = _baseline()
    with pytest.raises(ApiError) as caught:
        _sync_workweek_from_working_windows(
            settings,
            [_window(day, time(9, 0), 480) for day in (0, 2, 4)],
        )
    assert caught.value.content["code"] == "WORKING_POLICY_NONCONTIGUOUS"
    _assert_untouched(settings)


def _require_028(db: Session) -> None:
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "028_availability_progress", (
        f"test database alembic version is {version!r}; "
        "upgrade the disposable test database to 028_availability_progress before this suite"
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
    _require_028(db)
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
    assert tue_body["scheduling_effective"] is False
    assert tue_body["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY
    assert [window["weekday"] for window in tue_body["windows"]] == [1, 2, 3, 4, 5]
    assert {window["start_time"] for window in tue_body["windows"]} == {"11:00"}
    assert {window["duration_minutes"] for window in tue_body["windows"]} == {300}

    stored = _stored_mirror(db_session, owner_id)
    _assert_untouched(stored)
    assert int(stored.scheduling_revision) == revision
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
    assert weekend_body["scheduling_effective"] is False
    assert weekend_body["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY
    assert [window["weekday"] for window in weekend_body["windows"]] == [5, 6]

    stored = _stored_mirror(db_session, owner_id)
    _assert_untouched(stored)
    assert int(stored.scheduling_revision) == revision
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
    assert body["scheduling_effective"] is False
    assert body["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY
    assert [window["weekday"] for window in body["windows"]] == [0, 1, 2, 3]
    assert body["windows"][0]["start_time"] == "08:30"
    assert body["windows"][0]["duration_minutes"] == 240
    assert body["windows"][0]["end_time"] == "12:30"

    stored = _stored_mirror(db_session, owner_id)
    assert stored.workweek_days == 4
    assert stored.workday_start_local == time(8, 30)
    assert stored.workday_minutes == 240
    assert int(stored.scheduling_revision) == revision + 1
    settings_body = client.get("/api/v1/settings")
    assert settings_body.status_code == 200, settings_body.text
    assert settings_body.json()["workweek_days"] == 4
    assert settings_body.json()["workday_start_local"] == "08:30"
    assert settings_body.json()["workday_minutes"] == 240
    assert is_workday(_MONDAY, stored.workweek_days) is True
    assert is_workday(_THURSDAY, stored.workweek_days) is True
    assert is_workday(_FRIDAY, stored.workweek_days) is False
