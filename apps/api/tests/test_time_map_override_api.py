"""F4-W1 Time Map override persistence and nested API. Writes do not replan."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import FocusWindow, ScheduleRun, TimeMapOverride, User
from app.scheduler.time_map_overrides import (
    load_time_map_overrides_for_horizon,
    override_utc_bounds,
    resolve_override_for_date,
)

UTC = timezone.utc


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _map(client: TestClient, *, name: str | None = None) -> dict:
    created = client.post(
        "/api/v1/focus-windows",
        json={
            "name": name or f"Override map {_uid()}",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _override(client: TestClient, window_id: str, **overrides: object) -> dict:
    body: dict[str, object] = {
        "local_start_date": "2026-10-12",
        "local_end_date": "2026-10-14",
        "timezone": "America/Los_Angeles",
        "strict_mode": True,
        "bands": [
            {
                "tier": "green",
                "start_time": "14:00",
                "end_time": "17:00",
                "days_of_week": 31,
                "sort_order": 0,
            }
        ],
    }
    body.update(overrides)
    response = client.post(f"/api/v1/focus-windows/{window_id}/overrides", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_override_crud_keeps_base_map_and_does_not_replan(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    runs_before = db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count()
    window = _map(client)
    created = _override(client, window["id"])
    assert created["map_id"] == window["id"]
    assert created["timezone"] == "America/Los_Angeles"
    assert created["strict_mode"] is True
    assert created["local_start_date"] == "2026-10-12"
    assert created["local_end_date"] == "2026-10-14"
    assert created["bands"][0]["start_time"] == "14:00"
    assert created["bands"][0]["end_time"] == "17:00"

    base = client.get(f"/api/v1/focus-windows/{window['id']}")
    assert base.status_code == 200
    assert base.json()["bands"][0]["start_time"] == "09:00"
    assert base.json()["strict_mode"] is False

    listed = client.get(f"/api/v1/focus-windows/{window['id']}/overrides")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [created["id"]]

    got = client.get(f"/api/v1/focus-windows/{window['id']}/overrides/{created['id']}")
    assert got.status_code == 200
    assert got.json()["timezone"] == "America/Los_Angeles"

    patched = client.patch(
        f"/api/v1/focus-windows/{window['id']}/overrides/{created['id']}",
        json={"timezone": "America/New_York", "local_end_date": "2026-10-16"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["timezone"] == "America/New_York"
    assert patched.json()["local_end_date"] == "2026-10-16"
    assert patched.json()["bands"][0]["start_time"] == "14:00"

    deleted = client.delete(f"/api/v1/focus-windows/{window['id']}/overrides/{created['id']}")
    assert deleted.status_code == 204
    assert (
        client.get(f"/api/v1/focus-windows/{window['id']}/overrides/{created['id']}").status_code
        == 404
    )
    runs_after = db_session.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count()
    assert runs_after == runs_before


def test_empty_strict_bands_mean_all_day_unavailable(client: TestClient) -> None:
    window = _map(client)
    created = _override(
        client,
        window["id"],
        strict_mode=True,
        bands=[],
    )
    assert created["strict_mode"] is True
    assert created["bands"] == []

    omitted = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-11-02",
            "local_end_date": "2026-11-02",
            "timezone": "UTC",
            "strict_mode": True,
        },
    )
    assert omitted.status_code == 201, omitted.text
    assert omitted.json()["bands"] == []


def test_overlap_is_a_conflict_adjacent_and_other_maps_are_not(client: TestClient) -> None:
    window = _map(client)
    first = _override(client, window["id"])
    touching = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-14",
            "local_end_date": "2026-10-15",
            "timezone": "America/Los_Angeles",
            "strict_mode": False,
            "bands": [],
        },
    )
    assert touching.status_code == 409, touching.text
    body = touching.json()
    assert body["code"] == "TIME_MAP_OVERRIDE_OVERLAP"
    assert body["conflicting_override_id"] == first["id"]
    assert body["conflicting_local_start_date"] == "2026-10-12"
    assert body["conflicting_local_end_date"] == "2026-10-14"

    adjacent = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-15",
            "local_end_date": "2026-10-16",
            "timezone": "UTC",
            "strict_mode": False,
            "bands": [],
        },
    )
    assert adjacent.status_code == 201, adjacent.text

    other = _map(client)
    same_dates = _override(client, other["id"])
    assert same_dates["local_start_date"] == first["local_start_date"]

    moved = client.patch(
        f"/api/v1/focus-windows/{window['id']}/overrides/{adjacent.json()['id']}",
        json={"local_start_date": "2026-10-13", "local_end_date": "2026-10-13"},
    )
    assert moved.status_code == 409
    assert moved.json()["code"] == "TIME_MAP_OVERRIDE_OVERLAP"


def test_midnight_cross_and_bad_timezone_and_date_order(client: TestClient) -> None:
    window = _map(client)
    midnight = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-12",
            "local_end_date": "2026-10-12",
            "timezone": "America/Los_Angeles",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "22:00",
                    "end_time": "02:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert midnight.status_code == 422, midnight.text
    assert midnight.json()["code"] == "TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT"
    assert midnight.json()["band_index"] == 0

    overlap_bands = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-12",
            "local_end_date": "2026-10-12",
            "timezone": "UTC",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                },
                {
                    "tier": "green",
                    "start_time": "11:00",
                    "end_time": "13:00",
                    "days_of_week": 127,
                    "sort_order": 1,
                },
            ],
        },
    )
    assert overlap_bands.status_code == 422
    assert overlap_bands.json()["code"] == "TIME_MAP_BAND_OVERLAP"

    bad_tz = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-12",
            "local_end_date": "2026-10-12",
            "timezone": "Not/AZone",
            "strict_mode": True,
            "bands": [],
        },
    )
    assert bad_tz.status_code == 422
    assert bad_tz.json()["code"] == "TIME_MAP_OVERRIDE_TIMEZONE"

    backwards = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-14",
            "local_end_date": "2026-10-12",
            "timezone": "UTC",
            "strict_mode": True,
            "bands": [],
        },
    )
    assert backwards.status_code == 422
    assert backwards.json()["code"] == "TIME_MAP_OVERRIDE_INVALID_RANGE"


def test_other_owner_is_404_and_window_delete_cascades(
    client: TestClient,
    db_session: Session,
) -> None:
    window = _map(client, name=f"Mine {_uid()}")
    created = _override(client, window["id"], bands=[])
    other = User(
        email=f"override-{_uid()}@example.test",
        display_name="Other owner",
    )
    db_session.add(other)
    db_session.flush()
    secret = FocusWindow(owner_id=other.id, name="Secret Map", strict_mode=False)
    db_session.add(secret)
    db_session.flush()

    hidden = client.get(f"/api/v1/focus-windows/{secret.id}/overrides")
    assert hidden.status_code == 404
    assert "Secret" not in hidden.text

    foreign = client.get(
        f"/api/v1/focus-windows/{window['id']}/overrides/{uuid.uuid4()}"
    )
    assert foreign.status_code == 404

    deleted = client.delete(f"/api/v1/focus-windows/{window['id']}")
    assert deleted.status_code == 204
    db_session.expire_all()
    assert db_session.get(TimeMapOverride, uuid.UUID(created["id"])) is None


def test_expired_stays_listed_horizon_and_resolve_use_stored_timezone(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    window = _map(client)
    spring = _override(
        client,
        window["id"],
        local_start_date="2026-03-08",
        local_end_date="2026-03-08",
        timezone="America/Los_Angeles",
        strict_mode=True,
        bands=[],
    )
    expired = _override(
        client,
        window["id"],
        local_start_date="2020-01-01",
        local_end_date="2020-01-02",
        timezone="UTC",
        strict_mode=True,
        bands=[],
    )
    listed = client.get(f"/api/v1/focus-windows/{window['id']}/overrides")
    assert {row["id"] for row in listed.json()} == {spring["id"], expired["id"]}

    map_id = uuid.UUID(window["id"])
    row = db_session.get(TimeMapOverride, uuid.UUID(spring["id"]))
    assert row is not None
    start, end = override_utc_bounds(row)
    # 2026-03-08 is the US spring-forward day. Midnight PDT the next day is 07:00 UTC.
    assert start == datetime(2026, 3, 8, 8, 0, tzinfo=UTC)
    assert end == datetime(2026, 3, 9, 7, 0, tzinfo=UTC)

    def _loaded(horizon_start: datetime, horizon_end: datetime) -> dict:
        return load_time_map_overrides_for_horizon(
            db_session,
            owner_id,
            {map_id},
            horizon_start,
            horizon_end,
        )

    inside = _loaded(
        datetime(2026, 3, 9, 6, 0, tzinfo=UTC),
        datetime(2026, 3, 9, 6, 30, tzinfo=UTC),
    )
    assert [item.id for item in inside[map_id]] == [row.id]
    after = _loaded(
        datetime(2026, 3, 9, 7, 0, tzinfo=UTC),
        datetime(2026, 3, 9, 8, 0, tzinfo=UTC),
    )
    assert after[map_id] == []
    before = _loaded(
        datetime(2026, 3, 8, 7, 0, tzinfo=UTC),
        datetime(2026, 3, 8, 8, 0, tzinfo=UTC),
    )
    assert before[map_id] == []

    fall = _override(
        client,
        window["id"],
        local_start_date="2026-11-01",
        local_end_date="2026-11-01",
        timezone="America/Los_Angeles",
        strict_mode=True,
        bands=[],
    )
    fall_row = db_session.get(TimeMapOverride, uuid.UUID(fall["id"]))
    assert fall_row is not None
    fall_start, fall_end = override_utc_bounds(fall_row)
    assert fall_start == datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    assert fall_end == datetime(2026, 11, 2, 8, 0, tzinfo=UTC)

    matched = resolve_override_for_date(inside, map_id, date(2026, 3, 8))
    assert matched is not None
    assert matched.id == row.id
    assert resolve_override_for_date(inside, map_id, date(2026, 3, 7)) is None
    assert resolve_override_for_date(inside, map_id, date(2026, 3, 9)) is None
    assert resolve_override_for_date(inside, uuid.uuid4(), date(2026, 3, 8)) is None

    both = _loaded(
        datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
        datetime(2026, 3, 8, 13, 0, tzinfo=UTC),
    )
    assert expired["id"] not in {str(item.id) for item in both[map_id]}


def test_f4_c_covering_contained_and_identical_ranges_conflict(client: TestClient) -> None:
    window = _map(client)
    first = _override(client, window["id"])
    cases = [
        ("2026-10-01", "2026-10-31"),
        ("2026-10-13", "2026-10-13"),
        ("2026-10-12", "2026-10-14"),
        ("2026-10-10", "2026-10-12"),
    ]
    for start, end in cases:
        rejected = client.post(
            f"/api/v1/focus-windows/{window['id']}/overrides",
            json={
                "local_start_date": start,
                "local_end_date": end,
                "timezone": "UTC",
                "strict_mode": True,
                "bands": [],
            },
        )
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["code"] == "TIME_MAP_OVERRIDE_OVERLAP"
        assert rejected.json()["conflicting_override_id"] == first["id"]

    other = _map(client)
    independent = _override(client, other["id"])
    assert independent["local_start_date"] == first["local_start_date"]


def test_f4_c_rejected_overlap_and_midnight_leave_the_row_unchanged(
    client: TestClient,
) -> None:
    window = _map(client)
    first = _override(client, window["id"])
    neighbor = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-16",
            "local_end_date": "2026-10-18",
            "timezone": "UTC",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "10:00",
                    "end_time": "11:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert neighbor.status_code == 201, neighbor.text

    tightened = client.patch(
        f"/api/v1/focus-windows/{window['id']}/overrides/{neighbor.json()['id']}",
        json={"strict_mode": True},
    )
    assert tightened.status_code == 200, tightened.text
    assert tightened.json()["strict_mode"] is True
    assert tightened.json()["local_start_date"] == "2026-10-16"

    into_neighbor = client.patch(
        f"/api/v1/focus-windows/{window['id']}/overrides/{first['id']}",
        json={"local_end_date": "2026-10-16"},
    )
    assert into_neighbor.status_code == 409
    assert into_neighbor.json()["code"] == "TIME_MAP_OVERRIDE_OVERLAP"
    assert into_neighbor.json()["conflicting_override_id"] == neighbor.json()["id"]

    midnight = client.patch(
        f"/api/v1/focus-windows/{window['id']}/overrides/{first['id']}",
        json={
            "bands": [
                {
                    "tier": "green",
                    "start_time": "22:00",
                    "end_time": "02:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ]
        },
    )
    assert midnight.status_code == 422, midnight.text
    assert midnight.json()["code"] == "TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT"
    assert midnight.json()["band_index"] == 0

    second_band = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-20",
            "local_end_date": "2026-10-20",
            "timezone": "UTC",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                },
                {
                    "tier": "yellow",
                    "start_time": "22:00",
                    "end_time": "02:00",
                    "days_of_week": 127,
                    "sort_order": 1,
                },
            ],
        },
    )
    assert second_band.status_code == 422, second_band.text
    assert second_band.json()["code"] == "TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT"
    assert second_band.json()["band_index"] == 1

    zero = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-21",
            "local_end_date": "2026-10-21",
            "timezone": "UTC",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "09:00",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert zero.status_code == 422, zero.text
    assert zero.json()["code"] == "TIME_MAP_OVERRIDE_BAND_CROSSES_MIDNIGHT"

    evening = client.post(
        f"/api/v1/focus-windows/{window['id']}/overrides",
        json={
            "local_start_date": "2026-10-21",
            "local_end_date": "2026-10-21",
            "timezone": "UTC",
            "strict_mode": False,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "21:00",
                    "end_time": "23:30",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert evening.status_code == 201, evening.text

    kept = client.get(f"/api/v1/focus-windows/{window['id']}/overrides/{first['id']}")
    assert kept.status_code == 200
    assert kept.json()["local_start_date"] == "2026-10-12"
    assert kept.json()["local_end_date"] == "2026-10-14"
    assert kept.json()["bands"][0]["start_time"] == "14:00"
    assert kept.json()["bands"][0]["end_time"] == "17:00"
    neighbor_kept = client.get(
        f"/api/v1/focus-windows/{window['id']}/overrides/{neighbor.json()['id']}"
    )
    assert neighbor_kept.json()["local_start_date"] == "2026-10-16"
    assert neighbor_kept.json()["strict_mode"] is True


def test_f4_c_user_timezone_change_does_not_move_stored_bounds(
    client: TestClient,
    db_session: Session,
) -> None:
    window = _map(client)
    created = _override(
        client,
        window["id"],
        local_start_date="2026-03-08",
        local_end_date="2026-03-08",
        timezone="America/Los_Angeles",
        strict_mode=True,
        bands=[],
    )
    row = db_session.get(TimeMapOverride, uuid.UUID(created["id"]))
    assert row is not None
    bounds = override_utc_bounds(row)

    patched = client.patch("/api/v1/settings", json={"timezone": "America/New_York"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["timezone"] == "America/New_York"

    db_session.expire_all()
    row = db_session.get(TimeMapOverride, uuid.UUID(created["id"]))
    assert row is not None
    assert row.timezone == "America/Los_Angeles"
    assert override_utc_bounds(row) == bounds
    got = client.get(f"/api/v1/focus-windows/{window['id']}/overrides/{created['id']}")
    assert got.status_code == 200
    assert got.json()["timezone"] == "America/Los_Angeles"
    assert got.json()["local_start_date"] == "2026-03-08"
