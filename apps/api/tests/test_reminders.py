"""Time-based reminders API tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def test_reminder_crud_and_due_ack(client: TestClient) -> None:
    created = client.post("/api/v1/tasks", json={"title": "Take meds"})
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")

    due_create = client.post(
        f"/api/v1/tasks/{task_id}/reminders",
        json={"fire_at": past, "channel": "in_app"},
    )
    assert due_create.status_code == 201, due_create.text
    due_id = due_create.json()["id"]
    assert due_create.json()["is_fired"] is False

    future_create = client.post(
        f"/api/v1/tasks/{task_id}/reminders",
        json={"fire_at": future, "channel": "browser"},
    )
    assert future_create.status_code == 201, future_create.text
    future_id = future_create.json()["id"]

    listed = client.get(f"/api/v1/tasks/{task_id}/reminders")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    due = client.get("/api/v1/reminders/due")
    assert due.status_code == 200, due.text
    due_ids = {row["id"] for row in due.json()}
    assert due_id in due_ids
    assert future_id not in due_ids
    assert due.json()[0]["task_title"] == "Take meds"

    ack = client.post(f"/api/v1/reminders/{due_id}/ack")
    assert ack.status_code == 200
    assert ack.json()["is_fired"] is True

    ack_again = client.post(f"/api/v1/reminders/{due_id}/ack")
    assert ack_again.status_code == 200
    assert ack_again.json()["is_fired"] is True

    due_after = client.get("/api/v1/reminders/due")
    assert due_id not in {row["id"] for row in due_after.json()}

    patch = client.patch(
        f"/api/v1/reminders/{future_id}",
        json={"channel": "in_app"},
    )
    assert patch.status_code == 200
    assert patch.json()["channel"] == "in_app"

    deleted = client.delete(f"/api/v1/reminders/{future_id}")
    assert deleted.status_code == 204

    listed_after = client.get(f"/api/v1/tasks/{task_id}/reminders")
    assert len(listed_after.json()) == 1


def test_complete_dismisses_unfired_reminders(client: TestClient) -> None:
    created = client.post("/api/v1/tasks", json={"title": "One-shot"})
    assert created.status_code == 201
    task_id = created.json()["id"]

    future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    rem = client.post(
        f"/api/v1/tasks/{task_id}/reminders",
        json={"fire_at": future},
    )
    assert rem.status_code == 201
    rem_id = rem.json()["id"]

    complete = client.post(f"/api/v1/tasks/{task_id}/complete", json={})
    assert complete.status_code == 200

    listed = client.get(f"/api/v1/tasks/{task_id}/reminders")
    assert listed.status_code == 200
    row = next(r for r in listed.json() if r["id"] == rem_id)
    assert row["is_fired"] is True


def test_recurrence_advance_leaves_reminders(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "Daily habit",
            "due_at": "2026-08-10T09:00:00Z",
            "recurrence": {"rrule": "FREQ=DAILY;INTERVAL=1", "is_fixed": True},
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    future = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat().replace("+00:00", "Z")
    rem = client.post(
        f"/api/v1/tasks/{task_id}/reminders",
        json={"fire_at": future},
    )
    assert rem.status_code == 201
    rem_id = rem.json()["id"]

    complete = client.post(f"/api/v1/tasks/{task_id}/complete", json={})
    assert complete.status_code == 200
    assert complete.json()["recurrence_advanced"] is True

    listed = client.get(f"/api/v1/tasks/{task_id}/reminders")
    row = next(r for r in listed.json() if r["id"] == rem_id)
    assert row["is_fired"] is False


def test_reminder_ownership_404(client: TestClient) -> None:
    missing = "00000000-0000-4000-8000-000000000099"
    assert client.get(f"/api/v1/tasks/{missing}/reminders").status_code == 404
    assert client.post(
        f"/api/v1/tasks/{missing}/reminders",
        json={"fire_at": "2026-08-11T09:00:00Z"},
    ).status_code == 404
    assert client.post(f"/api/v1/reminders/{missing}/ack").status_code == 404
    assert client.delete(f"/api/v1/reminders/{missing}").status_code == 404
