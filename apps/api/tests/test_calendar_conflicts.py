"""Unit tests for calendar overlap / conflict helpers (no DB)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.calendar_conflicts import ranges_overlap


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 11, hour, minute, tzinfo=timezone.utc)


def test_ranges_overlap_no_intersection() -> None:
    assert ranges_overlap(_dt(9), _dt(10), _dt(10), _dt(11)) is False
    assert ranges_overlap(_dt(10), _dt(11), _dt(9), _dt(10)) is False


def test_ranges_overlap_partial() -> None:
    assert ranges_overlap(_dt(9), _dt(11), _dt(10), _dt(12)) is True
    assert ranges_overlap(_dt(10), _dt(12), _dt(9), _dt(11)) is True


def test_ranges_overlap_contained() -> None:
    assert ranges_overlap(_dt(9), _dt(12), _dt(10), _dt(11)) is True
    assert ranges_overlap(_dt(10), _dt(11), _dt(9), _dt(12)) is True


def test_ranges_overlap_identical() -> None:
    assert ranges_overlap(_dt(9), _dt(10), _dt(9), _dt(10)) is True
