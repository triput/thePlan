"""Merged validation for T2-S1 start occurrence bounds."""

from __future__ import annotations

from datetime import datetime, timezone

from app.api.errors import ApiError
from app.models import Task

OCCURRENCE_BOUNDS_NAIVE_INSTANT = "OCCURRENCE_BOUNDS_NAIVE_INSTANT"


def require_timezone_aware_instant(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ApiError(
            422,
            f"{field} must include a timezone offset (fixed instant)",
            OCCURRENCE_BOUNDS_NAIVE_INSTANT,
            field=field,
        )
    return value.astimezone(timezone.utc)


def assert_merged_bounds_not_inverted(
    *,
    earliest: datetime | None,
    latest: datetime | None,
) -> None:
    if earliest is None or latest is None:
        return
    e = require_timezone_aware_instant(earliest, field="start_no_earlier_at")
    l = require_timezone_aware_instant(latest, field="start_no_later_at")
    if e > l:
        raise ApiError(
            422,
            "start_no_earlier_at must not be after start_no_later_at",
            "OCCURRENCE_BOUNDS_INVERTED",
        )


def validate_occurrence_bounds_on_create(
    *,
    start_no_earlier_at: datetime | None,
    start_no_later_at: datetime | None,
) -> None:
    if start_no_earlier_at is not None:
        require_timezone_aware_instant(
            start_no_earlier_at, field="start_no_earlier_at"
        )
    if start_no_later_at is not None:
        require_timezone_aware_instant(start_no_later_at, field="start_no_later_at")
    assert_merged_bounds_not_inverted(
        earliest=start_no_earlier_at,
        latest=start_no_later_at,
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
    if "start_no_earlier_at" in updates:
        value = updates["start_no_earlier_at"]
        if value is not None:
            require_timezone_aware_instant(value, field="start_no_earlier_at")  # type: ignore[arg-type]
    if "start_no_later_at" in updates:
        value = updates["start_no_later_at"]
        if value is not None:
            require_timezone_aware_instant(value, field="start_no_later_at")  # type: ignore[arg-type]
    earliest, latest = merged_bounds_after_patch(task, updates)
    assert_merged_bounds_not_inverted(earliest=earliest, latest=latest)
