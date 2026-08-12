"""API tests for user settings expansion (W2b Slice 2)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_settings_returns_defaults(client: TestClient) -> None:
    reset = client.patch(
        "/api/v1/settings",
        json={
            "timezone": "UTC",
            "locale": "en-US",
            "workday_start_local": "08:00",
        },
    )
    assert reset.status_code == 200, reset.text

    response = client.get("/api/v1/settings")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["timezone"] == "UTC"
    assert body["locale"] == "en-US"
    assert body["workday_minutes"] == 480
    assert body["workday_start_local"] == "08:00"
    assert body["workweek_days"] == 5
    assert body["inter_block_buffer_minutes"] == 5
    assert body["upcoming_horizon_days"] == 7
    assert body["default_estimated_duration_minutes"] == 30
    assert body["default_min_block_duration_minutes"] == 15
    assert body["default_schedule_style"] == "standalone"
    assert body["auto_defer_enabled"] is True
    assert set(body["ups_weights"].keys()) == {"Wp", "Wu", "Wd", "We", "k"}


def test_patch_settings_workday_start(client: TestClient) -> None:
    patch = client.patch(
        "/api/v1/settings",
        json={"workday_start_local": "09:30"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["workday_start_local"] == "09:30"

    get_after = client.get("/api/v1/settings")
    assert get_after.status_code == 200
    assert get_after.json()["workday_start_local"] == "09:30"


def test_patch_settings_timezone_buffer_and_style(client: TestClient) -> None:
    patch = client.patch(
        "/api/v1/settings",
        json={
            "timezone": "America/Los_Angeles",
            "inter_block_buffer_minutes": 10,
            "default_schedule_style": "time_block",
            "default_estimated_duration_minutes": 45,
            "auto_defer_enabled": False,
        },
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["timezone"] == "America/Los_Angeles"
    assert body["inter_block_buffer_minutes"] == 10
    assert body["default_schedule_style"] == "time_block"
    assert body["default_estimated_duration_minutes"] == 45
    assert body["auto_defer_enabled"] is False

    get_after = client.get("/api/v1/settings")
    assert get_after.status_code == 200, get_after.text
    assert get_after.json()["timezone"] == "America/Los_Angeles"
    assert get_after.json()["default_schedule_style"] == "time_block"


def test_task_create_without_duration_uses_settings_default(client: TestClient) -> None:
    patch = client.patch(
        "/api/v1/settings",
        json={"default_estimated_duration_minutes": 52},
    )
    assert patch.status_code == 200, patch.text

    create = client.post(
        "/api/v1/tasks",
        json={"title": "Settings default duration task"},
    )
    assert create.status_code == 201, create.text
    assert create.json()["estimated_duration_minutes"] == 52

    explicit = client.post(
        "/api/v1/tasks",
        json={"title": "Explicit duration task", "estimated_duration_minutes": 90},
    )
    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["estimated_duration_minutes"] == 90


def test_quick_add_without_duration_uses_settings_default(client: TestClient) -> None:
    patch = client.patch(
        "/api/v1/settings",
        json={"default_estimated_duration_minutes": 37},
    )
    assert patch.status_code == 200, patch.text

    parse = client.post(
        "/api/v1/quick-add/parse",
        json={"text": "Just a title"},
    )
    assert parse.status_code == 200, parse.text
    assert parse.json()["estimated_duration_minutes"] == 37

    parse_with_token = client.post(
        "/api/v1/quick-add/parse",
        json={"text": "Deep work 2h"},
    )
    assert parse_with_token.status_code == 200, parse_with_token.text
    assert parse_with_token.json()["estimated_duration_minutes"] == 120
