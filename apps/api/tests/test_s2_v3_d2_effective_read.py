"""V3-D2: interval-aware dated effective read matches placer override bounds."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.enums import TimeMapBandTier
from app.scheduler.time_map_overrides import (
    effective_scheduling_day_segments,
    override_utc_bounds,
    scheduling_day_utc_bounds,
)
from app.services import task_scheduling_effective as effective
from test_s2_v3_window_math import _map, _override, _settings

UTC = timezone.utc


def test_v3_d2_tokyo_partial_override_exposes_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    mapped = _map((TimeMapBandTier.green, time(7, 0), time(12, 0)), strict=True)
    row = _override(
        mapped,
        start=date(2026, 10, 13),
        end=date(2026, 10, 13),
        tz="Asia/Tokyo",
        bands=[(TimeMapBandTier.red, time(7, 0), time(12, 0))],
        strict=True,
    )
    for band in [*mapped.bands, *row.bands]:
        band.id = uuid4()

    monkeypatch.setattr(
        effective,
        "load_time_map_overrides_for_maps",
        lambda *args, **kwargs: {mapped.id: [row]},
    )
    settings = _settings(timezone="America/Los_Angeles")
    result = effective._build_dated_resolution(
        None,
        SimpleNamespace(id=mapped.owner_id),
        on=date(2026, 10, 13),
        settings=settings,
        focus_window=mapped,
        window_source="task",
    )
    assert len(result.segments) == 2
    assert result.segments[0].source == "override"
    assert result.segments[0].end == datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
    assert result.segments[0].day_bands[0].tier.value == "red"
    assert result.segments[1].source == "base_map"
    assert result.segments[1].start == datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
    assert result.segments[1].day_bands[0].tier.value == "green"
    assert "part of this scheduling day" in (result.note or "").lower()
    assert result.replaces is not None
    assert "part of this scheduling day" in result.replaces.note.lower()


def test_v3_d2_start_boundary_splits_monday_la_tail() -> None:
    mapped = _map((TimeMapBandTier.green, time(7, 0), time(12, 0)), strict=False)
    row = _override(
        mapped,
        start=date(2026, 10, 13),
        end=date(2026, 10, 13),
        tz="Asia/Tokyo",
        bands=[(TimeMapBandTier.green, time(8, 0), time(8, 30))],
        strict=True,
    )
    settings = _settings(timezone="America/Los_Angeles")
    segments = effective_scheduling_day_segments(
        mapped,
        [row],
        date(2026, 10, 12),
        settings,  # type: ignore[arg-type]
    )
    assert len(segments) == 2
    assert segments[0].source == "base_map"
    assert segments[0].end == datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
    assert segments[1].source == "override"
    assert segments[1].start == datetime(2026, 10, 12, 15, 0, tzinfo=UTC)


def test_v3_d2_segments_align_with_placer_day_bounds() -> None:
    mapped = _map((TimeMapBandTier.green, time(7, 0), time(12, 0)), strict=True)
    row = _override(
        mapped,
        start=date(2026, 10, 13),
        end=date(2026, 10, 13),
        tz="Asia/Tokyo",
        bands=[(TimeMapBandTier.red, time(7, 0), time(12, 0))],
        strict=True,
    )
    settings = _settings(timezone="America/Los_Angeles")
    day = date(2026, 10, 13)
    day_start, day_end = scheduling_day_utc_bounds(day, settings)  # type: ignore[arg-type]
    o_start, o_end = override_utc_bounds(row)
    segments = effective_scheduling_day_segments(
        mapped,
        [row],
        day,
        settings,  # type: ignore[arg-type]
    )
    assert segments[0].start == day_start
    assert segments[0].end == o_end
    assert segments[1].start == o_end
    assert segments[1].end == day_end
