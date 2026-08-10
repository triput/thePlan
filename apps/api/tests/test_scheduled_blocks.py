"""API tests for scheduled blocks CRUD and calendar task due-date filters."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

UTC = timezone.utc


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _create_task(client: TestClient, title: str | None = None) -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={"title": title or f"task-{_uid()}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _block_payload(task_id: str, start: datetime, end: datetime, **extra: object) -> dict:
    payload = {
        "task_id": task_id,
        "start_time": _iso(start),
        "end_time": _iso(end),
    }
    payload.update(extra)
    return payload


def test_scheduled_blocks_crud(client: TestClient) -> None:
    task = _create_task(client)
    start = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
    end = start + timedelta(hours=1, minutes=30)

    created = client.post(
        "/api/v1/scheduled-blocks",
        json=_block_payload(task["id"], start, end, is_pinned=True),
    )
    assert created.status_code == 201, created.text
    block = created.json()
    assert block["task_id"] == task["id"]
    assert block["is_pinned"] is True
    assert "created_at" in block
    assert "updated_at" in block

    got = client.get(f"/api/v1/scheduled-blocks/{block['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == block["id"]

    new_end = end + timedelta(minutes=30)
    patched = client.patch(
        f"/api/v1/scheduled-blocks/{block['id']}",
        json={"end_time": _iso(new_end), "is_pinned": False},
    )
    assert patched.status_code == 200
    assert patched.json()["is_pinned"] is False
    assert patched.json()["end_time"].startswith("2026-08-11T11:00:00")

    deleted = client.delete(f"/api/v1/scheduled-blocks/{block['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/scheduled-blocks/{block['id']}").status_code == 404


def test_create_block_invalid_time_range(client: TestClient) -> None:
    task = _create_task(client)
    start = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
    response = client.post(
        "/api/v1/scheduled-blocks",
        json=_block_payload(task["id"], start, start),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_TIME_RANGE"


def test_create_block_unknown_task_404(client: TestClient) -> None:
    start = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    response = client.post(
        "/api/v1/scheduled-blocks",
        json=_block_payload(str(uuid.uuid4()), start, end),
    )
    assert response.status_code == 404


def test_list_blocks_overlap_range(client: TestClient) -> None:
    task = _create_task(client)
    window_start = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)
    window_end = window_start + timedelta(days=1)

    inside = client.post(
        "/api/v1/scheduled-blocks",
        json=_block_payload(
            task["id"],
            datetime(2026, 8, 11, 9, 0, tzinfo=UTC),
            datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
        ),
    ).json()
    outside = client.post(
        "/api/v1/scheduled-blocks",
        json=_block_payload(
            task["id"],
            datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
            datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
        ),
    ).json()

    listed = client.get(
        "/api/v1/scheduled-blocks",
        params={"start": _iso(window_start), "end": _iso(window_end)},
    )
    assert listed.status_code == 200, listed.text
    ids = {item["id"] for item in listed.json()["items"]}
    assert inside["id"] in ids
    assert outside["id"] not in ids


def test_list_blocks_requires_start_and_end(client: TestClient) -> None:
    response = client.get("/api/v1/scheduled-blocks")
    assert response.status_code == 422


def test_patch_block_can_change_task(client: TestClient) -> None:
    task_a = _create_task(client)
    task_b = _create_task(client)
    start = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    block = client.post(
        "/api/v1/scheduled-blocks",
        json=_block_payload(task_a["id"], start, end),
    ).json()

    patched = client.patch(
        f"/api/v1/scheduled-blocks/{block['id']}",
        json={"task_id": task_b["id"]},
    )
    assert patched.status_code == 200
    assert patched.json()["task_id"] == task_b["id"]


def test_list_tasks_due_from_due_to(client: TestClient) -> None:
    uid = _uid()
    due_in = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
    due_out = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)
    no_due = client.post("/api/v1/tasks", json={"title": f"no-due-{uid}"}).json()
    in_range = client.post(
        "/api/v1/tasks",
        json={"title": f"in-range-{uid}", "due_at": _iso(due_in)},
    ).json()
    out_range = client.post(
        "/api/v1/tasks",
        json={"title": f"out-range-{uid}", "due_at": _iso(due_out)},
    ).json()

    window_start = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 18, 0, 0, tzinfo=UTC)
    response = client.get(
        "/api/v1/tasks",
        params={"due_from": _iso(window_start), "due_to": _iso(window_end)},
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert in_range["id"] in ids
    assert out_range["id"] not in ids
    assert no_due["id"] not in ids
