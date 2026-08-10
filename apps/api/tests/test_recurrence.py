"""Recurrence engine and API tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.services.recurrence import (
    RecurrenceSpec,
    humanize_recurrence,
    next_due_at,
    parse_recurrence_text,
)


def test_parse_every_monday_wednesday_frame() -> None:
    title, spec = parse_recurrence_text(
        " Pay bills every monday, wednesday from 8/30 to 9/20 ",
        now=datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("UTC")),
        timezone_name="UTC",
    )
    assert title == "Pay bills"
    assert spec is not None
    assert spec.is_fixed is False
    assert "BYDAY=MO,WE" in spec.rrule
    assert spec.starts_on == date(2026, 8, 30)
    assert spec.ends_on == date(2026, 9, 20)


def test_parse_every_bang_two_weeks_until_eoy() -> None:
    title, spec = parse_recurrence_text(
        " Review every! 2 weeks from next week until end of year ",
        now=datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("UTC")),
        timezone_name="UTC",
    )
    assert "Review" in title
    assert spec is not None
    assert spec.is_fixed is True
    assert spec.rrule == "FREQ=WEEKLY;INTERVAL=2"
    assert spec.starts_on == date(2026, 8, 17)  # next Monday
    assert spec.ends_on == date(2026, 12, 31)


def test_next_due_every_vs_fixed() -> None:
    spec = RecurrenceSpec(rrule="FREQ=DAILY;INTERVAL=1", is_fixed=False, timezone="UTC")
    prev = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    completed = datetime(2026, 8, 5, 15, 0, tzinfo=timezone.utc)
    slid = next_due_at(spec, previous_due=prev, completed_at=completed)
    assert slid is not None
    assert slid.date() == date(2026, 8, 6)

    fixed = RecurrenceSpec(rrule="FREQ=DAILY;INTERVAL=1", is_fixed=True, timezone="UTC")
    caught = next_due_at(fixed, previous_due=prev, completed_at=completed)
    assert caught is not None
    assert caught.date() == date(2026, 8, 2)


def test_frame_exhausts() -> None:
    spec = RecurrenceSpec(
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=MO",
        is_fixed=True,
        timezone="UTC",
        starts_on=date(2026, 8, 10),
        ends_on=date(2026, 8, 17),
    )
    prev = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)
    assert next_due_at(spec, previous_due=prev, completed_at=prev) is None


def test_humanize() -> None:
    spec = RecurrenceSpec(
        rrule="FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE",
        is_fixed=False,
        timezone="UTC",
        starts_on=date(2026, 8, 30),
        ends_on=date(2026, 9, 20),
    )
    text = humanize_recurrence(spec)
    assert "Mon" in text and "Wed" in text


def test_api_recurrence_put_complete_rollover(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "Water plants",
            "due_at": "2026-08-10T09:00:00Z",
            "recurrence": {"rrule": "FREQ=DAILY;INTERVAL=1", "is_fixed": True},
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["recurrence"]["display"]
    task_id = task["id"]

    complete = client.post(f"/api/v1/tasks/{task_id}/complete", json={})
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["is_completed"] is False
    assert body["recurrence_advanced"] is True
    assert body["due_at"].startswith("2026-08-11")


def test_api_frame_end_completes(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "Camp week",
            "due_at": "2026-08-17T09:00:00Z",
            "recurrence": {
                "rrule": "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO",
                "is_fixed": True,
                "starts_on": "2026-08-10",
                "ends_on": "2026-08-17",
            },
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    complete = client.post(f"/api/v1/tasks/{task_id}/complete", json={})
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["is_completed"] is True
    assert body["recurrence_advanced"] is False


def test_quick_add_parse_recurrence(client: TestClient) -> None:
    parsed = client.post(
        "/api/v1/quick-add/parse",
        json={"text": "Standup every monday, wednesday from 8/30 to 9/20"},
    )
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()
    assert body["title"] == "Standup"
    assert body["recurrence"] is not None
    assert "BYDAY=MO,WE" in body["recurrence"]["rrule"]
