"""Test helper: express old workweek spans as Working and General windows.

Settings no longer accepts ``workweek_days`` / ``workday_start_local`` /
``workday_minutes``. Suites that used those fields to describe eligibility
write the same span onto both policies so the placer still sees it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

_RETIRED = ("workweek_days", "workday_start_local", "workday_minutes")


def patch_settings_with_availability(client: TestClient, payload: dict) -> None:
    body = dict(payload)
    days = body.pop("workweek_days", None)
    start = body.pop("workday_start_local", None)
    minutes = body.pop("workday_minutes", None)
    if body:
        response = client.patch("/api/v1/settings", json=body)
        assert response.status_code == 200, response.text
    if days is None and start is None and minutes is None:
        return
    day_count = int(days if days is not None else 7)
    clock = str(start or "08:00")[:5]
    length = int(minutes if minutes is not None else 480)
    windows = [
        {
            "weekday": day,
            "start_time": clock,
            "duration_minutes": length,
            "sort_order": 0,
        }
        for day in range(max(0, min(day_count, 7)))
    ]
    for slug in ("work", "general"):
        patched = client.patch(
            f"/api/v1/availability-policies/{slug}",
            json={"windows": windows},
        )
        assert patched.status_code == 200, patched.text
