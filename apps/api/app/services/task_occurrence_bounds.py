"""Merged validation for T2-S1 start occurrence bounds."""

from __future__ import annotations

from datetime import datetime, timezone

from app.api.errors import ApiError
from app.models import Task


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def assert_merged_bounds_not_inverted(
    *,
    earliest: datetime | None,
    latest: datetime | None,
) -> None:
    if earliest is None or latest is None:
        return
    e = _ensure_aware(earliest)
    l = _ensure_aware(latest)
    if e > l:
        raise ApiError(
            422,
            "start_no_earlier_at must not be after start_no_later_at",
            "OCCURRENCE_BOUNDS_INVERTED",
        )


def merged_bounds_after_patch(
    task: Task,
    updates: dict[str, object],
) -> tuple[datetime | None, datetime | None]:
    earliest = task.start_no_earlier_at
    latest = task.start_no_later_at
    if "start_no_earlier_at" in updates:
        earliest = updates["start_no_earlier_at"]  # type: ignore[assignment]
    if "start_no_later_at" in updates:
        latest = updates["start_no_later_at"]  # type: ignore[assignment]
    return earliest, latest


def validate_occurrence_bounds_patch(task: Task, updates: dict[str, object]) -> None:
    if "start_no_earlier_at" not in updates and "start_no_later_at" not in updates:
        return
    earliest, latest = merged_bounds_after_patch(task, updates)
    assert_merged_bounds_not_inverted(earliest=earliest, latest=latest)
