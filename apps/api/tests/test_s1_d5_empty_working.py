"""S1-D5: empty Working is a stored zero-day mirror, not an IntegrityError.

S0: ``workweek_days = 0`` means no Working days. ``029_workweek_days_allow_zero``
replaces the 001 check (1–7) so that write can commit. These tests run against
disposable PostgreSQL ``theplan_s1_test`` after that upgrade. They refuse any
other database before the API client logs in.
"""

from __future__ import annotations

import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import UserSettings
from app.scheduler.placement import is_workday
from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY
from app.schemas.settings import UserSettingsUpdate
from app.services.availability_policies import _sync_workweek_from_working_windows
from app.services.availability_seed import ensure_default_availability_policies

_REQUIRED_DATABASE = "theplan_s1_test"
_REQUIRED_REVISION = "029_workweek_days_allow_zero"

# 2026-10-12 is a Monday. Legacy eligibility is weekday() < workweek_days.
_MONDAY = date(2026, 10, 12)
_WEDNESDAY = date(2026, 10, 14)
_THURSDAY = date(2026, 10, 15)
_SUNDAY = date(2026, 10, 18)


@pytest.fixture()
def disposable_db(db_session: Session) -> Session:
    """Read-only gate. Fail before the TestClient fixture writes anything."""
    name = db_session.execute(text("SELECT current_database()")).scalar()
    if name != _REQUIRED_DATABASE:
        pytest.fail(
            f"S1-D5 refuses database {name!r}; "
            "set DATABASE_URL to disposable theplan_s1_test"
        )
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    if version != _REQUIRED_REVISION:
        pytest.fail(
            f"disposable database alembic version is {version!r}; "
            f"upgrade theplan_s1_test to {_REQUIRED_REVISION} before this suite"
        )
    return db_session


def test_empty_working_is_zero_day_mirror_without_touching_clocks() -> None:
    settings = UserSettings(
        workweek_days=3,
        workday_start_local=time(10, 0),
        workday_minutes=360,
    )
    mirrored = _sync_workweek_from_working_windows(settings, [])
    assert mirrored is True
    assert settings.workweek_days == 0
    assert settings.workday_start_local == time(10, 0)
    assert settings.workday_minutes == 360
    assert is_workday(_MONDAY, settings.workweek_days) is False
    assert is_workday(_SUNDAY, settings.workweek_days) is False


def test_settings_update_accepts_zero_workweek_days_and_rejects_out_of_range() -> None:
    assert UserSettingsUpdate.model_validate({"workweek_days": 0}).workweek_days == 0
    assert UserSettingsUpdate.model_validate({"workweek_days": 7}).workweek_days == 7
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"workweek_days": -1})
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"workweek_days": 8})


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


def _prepare(client: TestClient, db: Session) -> tuple[uuid.UUID, int, list[dict[str, object]]]:
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
    general = client.get("/api/v1/availability-policies/general")
    assert general.status_code == 200, general.text
    return owner_id, revision, general.json()["windows"]


def _stored(db: Session, owner_id: uuid.UUID) -> UserSettings:
    db.expire_all()
    return db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()


def _work_window_count(db: Session, owner_id: uuid.UUID) -> int:
    return int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM availability_windows AS w
                JOIN availability_policies AS p ON p.id = w.policy_id
                WHERE p.owner_id = :owner
                  AND p.slug = 'work'
                """
            ),
            {"owner": owner_id},
        ).scalar()
        or 0
    )


def _assert_check_rejects(db: Session, owner_id: uuid.UUID, bad: int) -> None:
    with pytest.raises(IntegrityError) as caught:
        with db.begin_nested():
            db.execute(
                text(
                    """
                    UPDATE user_settings
                    SET workweek_days = :days
                    WHERE owner_id = :owner
                    """
                ),
                {"days": bad, "owner": owner_id},
            )
            db.flush()
    assert "user_settings_workweek_days_check" in str(caught.value)


def test_api_empty_working_persists_zero_days_and_restores_monday_first(
    disposable_db: Session, client: TestClient
) -> None:
    owner_id, revision, general_windows = _prepare(client, disposable_db)

    shifted = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": _windows((1, 2, 3, 4, 5), "11:00", 300)},
    )
    assert shifted.status_code == 200, shifted.text
    stored = _stored(disposable_db, owner_id)
    assert stored.workweek_days == 3
    assert int(stored.scheduling_revision) == revision

    cleared = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": []},
    )
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["windows"] == []
    assert body["scheduling_effective"] is False
    assert body["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY

    stored = _stored(disposable_db, owner_id)
    assert stored.workweek_days == 0
    assert stored.workday_start_local == time(10, 0)
    assert stored.workday_minutes == 360
    assert int(stored.scheduling_revision) == revision + 1
    assert _work_window_count(disposable_db, owner_id) == 0
    assert is_workday(_MONDAY, stored.workweek_days) is False
    assert is_workday(_WEDNESDAY, stored.workweek_days) is False
    assert is_workday(_SUNDAY, stored.workweek_days) is False

    settings_body = client.get("/api/v1/settings")
    assert settings_body.status_code == 200, settings_body.text
    assert settings_body.json()["workweek_days"] == 0
    assert settings_body.json()["workday_start_local"] == "10:00"
    assert settings_body.json()["workday_minutes"] == 360
    assert settings_body.json()["scheduling_revision"] == revision + 1

    reread = client.get("/api/v1/availability-policies/work")
    assert reread.status_code == 200, reread.text
    assert reread.json()["windows"] == []
    general = client.get("/api/v1/availability-policies/general")
    assert general.status_code == 200, general.text
    assert general.json()["windows"] == general_windows

    _assert_check_rejects(disposable_db, owner_id, 8)
    _assert_check_rejects(disposable_db, owner_id, -1)
    stored = _stored(disposable_db, owner_id)
    assert stored.workweek_days == 0
    assert int(stored.scheduling_revision) == revision + 1

    restored = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": _windows(range(3), "10:00", 360)},
    )
    assert restored.status_code == 200, restored.text
    restored_body = restored.json()
    assert [window["weekday"] for window in restored_body["windows"]] == [0, 1, 2]
    assert {window["start_time"] for window in restored_body["windows"]} == {"10:00"}
    assert {window["duration_minutes"] for window in restored_body["windows"]} == {360}
    assert restored_body["scheduling_effective"] is False

    stored = _stored(disposable_db, owner_id)
    assert stored.workweek_days == 3
    assert stored.workday_start_local == time(10, 0)
    assert stored.workday_minutes == 360
    assert int(stored.scheduling_revision) == revision + 2
    assert _work_window_count(disposable_db, owner_id) == 3
    assert is_workday(_MONDAY, stored.workweek_days) is True
    assert is_workday(_WEDNESDAY, stored.workweek_days) is True
    assert is_workday(_THURSDAY, stored.workweek_days) is False

    settings_body = client.get("/api/v1/settings")
    assert settings_body.status_code == 200, settings_body.text
    assert settings_body.json()["workweek_days"] == 3
    assert settings_body.json()["scheduling_revision"] == revision + 2
    reread = client.get("/api/v1/availability-policies/work")
    assert [window["weekday"] for window in reread.json()["windows"]] == [0, 1, 2]


def test_api_settings_patch_zero_does_not_clear_working_windows(
    disposable_db: Session, client: TestClient
) -> None:
    """Settings may store 0. That write does not rewrite Working windows."""
    owner_id, revision, _general = _prepare(client, disposable_db)
    planted = client.patch(
        "/api/v1/availability-policies/work",
        json={"windows": _windows(range(3), "10:00", 360)},
    )
    assert planted.status_code == 200, planted.text
    planted_windows = planted.json()["windows"]
    assert [window["weekday"] for window in planted_windows] == [0, 1, 2]
    after_plant = _stored(disposable_db, owner_id)
    assert after_plant.workweek_days == 3
    planted_revision = int(after_plant.scheduling_revision)
    assert planted_revision == revision + 1

    patched = client.patch("/api/v1/settings", json={"workweek_days": 0})
    assert patched.status_code == 200, patched.text
    assert patched.json()["workweek_days"] == 0
    assert patched.json()["workday_start_local"] == "10:00"
    assert patched.json()["workday_minutes"] == 360
    assert patched.json()["scheduling_revision"] == planted_revision + 1

    stored = _stored(disposable_db, owner_id)
    assert stored.workweek_days == 0
    assert int(stored.scheduling_revision) == planted_revision + 1
    reread = client.get("/api/v1/availability-policies/work")
    assert reread.status_code == 200, reread.text
    assert [window["weekday"] for window in reread.json()["windows"]] == [0, 1, 2]
    assert _work_window_count(disposable_db, owner_id) == 3

    rejected = client.patch("/api/v1/settings", json={"workweek_days": 8})
    assert rejected.status_code == 422, rejected.text
    still = _stored(disposable_db, owner_id)
    assert still.workweek_days == 0
    assert int(still.scheduling_revision) == planted_revision + 1

    negative = client.patch("/api/v1/settings", json={"workweek_days": -1})
    assert negative.status_code == 422, negative.text
    still = _stored(disposable_db, owner_id)
    assert still.workweek_days == 0
