"""API tests for focus windows (Time Maps) and task preferred_time_window_id."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID, ensure_bootstrap_user
from app.models import FocusWindow
from app.models.enums import TimeMapBandTier
from app.services.focus_windows import ensure_default_focus_windows


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_ensure_default_focus_windows_seeds_three(db_session: Session) -> None:
    user = ensure_bootstrap_user(db_session, commit=False)
    db_session.query(FocusWindow).filter(FocusWindow.owner_id == user.id).delete(
        synchronize_session=False
    )
    db_session.flush()

    created = ensure_default_focus_windows(db_session, user.id)
    assert len(created) == 3
    names = {window.name for window in created}
    assert names == {"Morning", "Afternoon", "Evening"}
    for window in created:
        assert len(window.bands) == 1
        assert window.bands[0].tier == TimeMapBandTier.green
        assert window.bands[0].days_of_week == 127
        assert window.strict_mode is False

    assert ensure_default_focus_windows(db_session, user.id) == []


def test_list_focus_windows_ordered_by_name(client: TestClient) -> None:
    response = client.get("/api/v1/focus-windows")
    assert response.status_code == 200, response.text
    names = [row["name"] for row in response.json()]
    assert names == sorted(names)
    assert {"Morning", "Afternoon", "Evening"}.issubset(set(names))
    for row in response.json():
        assert "bands" in row
        assert len(row["bands"]) >= 1


def test_focus_window_crud(client: TestClient) -> None:
    uid = _uid()
    create = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"Deep Work {uid}",
            "strict_mode": True,
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "11:30",
                    "days_of_week": 31,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["strict_mode"] is True
    assert body["bands"][0]["start_time"] == "09:00"
    assert body["bands"][0]["end_time"] == "11:30"
    window_id = body["id"]

    get_one = client.get(f"/api/v1/focus-windows/{window_id}")
    assert get_one.status_code == 200
    assert get_one.json()["name"] == f"Deep Work {uid}"

    patch = client.patch(
        f"/api/v1/focus-windows/{window_id}",
        json={
            "name": f"Focus {uid}",
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "11:30",
                    "days_of_week": 127,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == f"Focus {uid}"
    assert patch.json()["bands"][0]["days_of_week"] == 127

    delete = client.delete(f"/api/v1/focus-windows/{window_id}")
    assert delete.status_code == 204
    assert client.get(f"/api/v1/focus-windows/{window_id}").status_code == 404


def test_focus_window_legacy_create_compat(client: TestClient) -> None:
    uid = _uid()
    create = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"Legacy {uid}",
            "start_time": "10:00",
            "end_time": "12:00",
            "days_of_week": 31,
            "is_hard": True,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["strict_mode"] is True
    assert len(body["bands"]) == 1
    assert body["bands"][0]["tier"] == "green"
    assert body["bands"][0]["start_time"] == "10:00"


def test_focus_window_invalid_range_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/focus-windows",
        json={
            "name": "Bad range",
            "bands": [
                {
                    "tier": "green",
                    "start_time": "14:00",
                    "end_time": "13:00",
                    "days_of_week": 127,
                }
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "FOCUS_WINDOW_INVALID_RANGE"


def test_focus_window_same_tier_overlap_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/focus-windows",
        json={
            "name": "Overlap",
            "bands": [
                {
                    "tier": "green",
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "days_of_week": 127,
                },
                {
                    "tier": "green",
                    "start_time": "11:00",
                    "end_time": "14:00",
                    "days_of_week": 127,
                },
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "TIME_MAP_BAND_OVERLAP"


def test_focus_window_other_user_not_visible(client: TestClient) -> None:
    created = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"Private-{_uid()}",
            "start_time": "10:00",
            "end_time": "11:00",
        },
    ).json()
    assert client.get(f"/api/v1/focus-windows/{created['id']}").status_code == 200

    other = uuid.uuid4()
    assert client.get(f"/api/v1/focus-windows/{other}").status_code == 404


def test_task_preferred_time_window_ownership(client: TestClient) -> None:
    windows = client.get("/api/v1/focus-windows").json()
    morning = next(row for row in windows if row["name"] == "Morning")

    created = client.post(
        "/api/v1/tasks",
        json={"title": f"Morning task {_uid()}", "preferred_time_window_id": morning["id"]},
    )
    assert created.status_code == 201, created.text
    assert created.json()["preferred_time_window_id"] == morning["id"]

    bogus = client.post(
        "/api/v1/tasks",
        json={"title": "Bad window", "preferred_time_window_id": str(uuid.uuid4())},
    )
    assert bogus.status_code == 404

    cleared = client.patch(
        f"/api/v1/tasks/{created.json()['id']}",
        json={"preferred_time_window_id": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["preferred_time_window_id"] is None


def test_delete_focus_window_sets_null_on_tasks(client: TestClient) -> None:
    uid = _uid()
    window = client.post(
        "/api/v1/focus-windows",
        json={
            "name": f"Temp {uid}",
            "start_time": "08:00",
            "end_time": "09:00",
        },
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"Bound {uid}", "preferred_time_window_id": window["id"]},
    ).json()
    assert task["preferred_time_window_id"] == window["id"]

    assert client.delete(f"/api/v1/focus-windows/{window['id']}").status_code == 204

    refreshed = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert refreshed["preferred_time_window_id"] is None


def test_quick_add_resolves_morning_window(client: TestClient) -> None:
    response = client.post(
        "/api/v1/quick-add/parse",
        json={"text": f"Write docs @morning p2 {_uid()}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["preferred_time_window_id"] is not None
    assert "time_window:" not in "".join(body["unresolved"])

    windows = client.get("/api/v1/focus-windows").json()
    morning = next(row for row in windows if row["name"] == "Morning")
    assert body["preferred_time_window_id"] == morning["id"]


def test_quick_add_unresolved_when_window_missing(client: TestClient) -> None:
    windows = client.get("/api/v1/focus-windows").json()
    morning = next(row for row in windows if row["name"] == "Morning")
    assert client.delete(f"/api/v1/focus-windows/{morning['id']}").status_code == 204

    response = client.post(
        "/api/v1/quick-add/parse",
        json={"text": "Plan day @morning"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["preferred_time_window_id"] is None
    assert "time_window:morning" in body["unresolved"]


def test_provision_seeds_focus_windows_on_register(auth_client: TestClient) -> None:
    uid = _uid()
    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"fw{uid}",
            "email": f"fw{uid}@example.com",
            "password": "test passphrase twelve",
        },
    )
    assert response.status_code == 201, response.text

    windows = auth_client.get("/api/v1/focus-windows")
    assert windows.status_code == 200
    names = {row["name"] for row in windows.json()}
    # Bootstrap claim may keep pre-existing operator windows on the live DB.
    assert {"Morning", "Afternoon", "Evening"}.issubset(names)
    for row in windows.json():
        assert "bands" in row
        assert "strict_mode" in row


def test_bootstrap_user_gets_default_windows(db_session: Session) -> None:
    db_session.query(FocusWindow).filter(FocusWindow.owner_id == BOOTSTRAP_USER_ID).delete(
        synchronize_session=False
    )
    db_session.flush()

    ensure_bootstrap_user(db_session, commit=False)
    count = (
        db_session.query(FocusWindow)
        .filter(FocusWindow.owner_id == BOOTSTRAP_USER_ID)
        .count()
    )
    assert count == 3
