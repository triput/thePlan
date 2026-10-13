"""Unit tests for friendly duration parsing."""

from __future__ import annotations

import pytest

from app.api.errors import ApiError
from app.services.friendly_duration import parse_friendly_duration


def test_composite_hours_minutes() -> None:
    result = parse_friendly_duration(
        "1h 30m",
        field_label="estimated_duration_minutes",
        allow_workdays=False,
        allow_zero=False,
    )
    assert result.minutes == 90


def test_fractional_hours() -> None:
    result = parse_friendly_duration(
        "1.5h",
        field_label="estimated_duration_minutes",
        allow_workdays=False,
        allow_zero=False,
    )
    assert result.minutes == 90


def test_workday_conversion_note() -> None:
    result = parse_friendly_duration(
        "1.5 workdays",
        field_label="estimated_duration_minutes",
        nominal_workday_minutes=480,
        allow_workdays=True,
        allow_zero=False,
    )
    assert result.minutes == 720
    assert result.conversion_note is not None


def test_rejects_ambiguous_days() -> None:
    with pytest.raises(ApiError) as exc:
        parse_friendly_duration(
            "2d",
            field_label="estimated_duration_minutes",
            allow_workdays=False,
            allow_zero=False,
        )
    assert exc.value.content["code"] == "AMBIGUOUS_DURATION_UNIT"
