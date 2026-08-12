"""Unit tests for UPS scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Task, UserSettings
from app.models.enums import TaskPriority
from app.scheduler.ups import (
    compute_urgency,
    compute_ups,
    normalize_dependent_score,
    slack_due_at,
)


def _settings(**overrides: object) -> UserSettings:
    settings = UserSettings(owner_id=__import__("uuid").uuid4())
    settings.ups_weights = {
        "Wp": 0.35,
        "Wu": 0.40,
        "Wd": 0.15,
        "We": 0.10,
        "k": 0.5,
    }
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def test_slack_due_prefers_deadline_then_soft_then_due() -> None:
    now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    task = Task(
        owner_id=__import__("uuid").uuid4(),
        title="t",
        deadline_at=now + timedelta(hours=1),
        soft_target_at=now + timedelta(hours=2),
        due_at=now + timedelta(hours=3),
    )
    assert slack_due_at(task) == task.deadline_at

    task.deadline_at = None
    assert slack_due_at(task) == task.soft_target_at

    task.soft_target_at = None
    assert slack_due_at(task) == task.due_at


def test_urgency_zero_when_no_due_date() -> None:
    now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    assert compute_urgency(due_at=None, now_utc=now, remaining_minutes=60, k=0.5) == 0.0


def test_urgency_max_when_slack_non_positive() -> None:
    now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    due = now + timedelta(minutes=30)
    urgency = compute_urgency(due_at=due, now_utc=now, remaining_minutes=60, k=0.5)
    assert urgency == 100.0


def test_urgency_decays_with_positive_slack() -> None:
    now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    due = now + timedelta(minutes=120)
    urgency = compute_urgency(due_at=due, now_utc=now, remaining_minutes=60, k=0.5)
    assert 0.0 < urgency < 100.0


def test_compute_ups_respects_weights() -> None:
    settings = _settings()
    now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    task = Task(owner_id=__import__("uuid").uuid4(), title="t", priority=TaskPriority.p1)
    score = compute_ups(
        task,
        settings=settings,
        remaining_minutes=60,
        now_utc=now,
        dependent_score=100.0,
        epic_score=100.0,
    )
    expected = 0.35 * 100 + 0.40 * 0 + 0.15 * 100 + 0.10 * 100
    assert score == expected


def test_normalize_dependent_score() -> None:
    assert normalize_dependent_score(0, 5) == 0.0
    assert normalize_dependent_score(3, 3) == 100.0
    assert normalize_dependent_score(1, 4) == 25.0
