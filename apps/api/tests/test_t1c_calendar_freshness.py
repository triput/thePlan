"""T1-C smoke: freshness gate helpers (no live provider)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.scheduler.calendar_freshness import (
    FRESHNESS_AGE_CEILING,
    MIN_COVERAGE_PAD,
    coverage_pad_elapsed,
    proposal_padded_coverage_window,
)
from app.models import UserSettings


def test_coverage_pad_at_least_24h():
    settings = UserSettings(inter_block_buffer_minutes=15)
    assert coverage_pad_elapsed(settings) >= MIN_COVERAGE_PAD


def test_coverage_pad_unset_defaults_24h():
    settings = UserSettings(inter_block_buffer_minutes=None)
    assert coverage_pad_elapsed(settings) == MIN_COVERAGE_PAD


def test_proposal_window_spans_blocks():
    settings = UserSettings(inter_block_buffer_minutes=None, upcoming_horizon_days=7, timezone="UTC")
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    proposal = {
        "proposed_blocks": [
            {
                "start_time": "2026-10-20T09:00:00+00:00",
                "end_time": "2026-10-20T10:00:00+00:00",
            },
            {
                "start_time": "2026-10-21T14:00:00+00:00",
                "end_time": "2026-10-21T15:30:00+00:00",
            },
        ]
    }
    start, end = proposal_padded_coverage_window(proposal, settings, now)
    assert start == datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 22, 15, 30, tzinfo=timezone.utc)


def test_freshness_age_ceiling_candidate():
    assert FRESHNESS_AGE_CEILING == timedelta(minutes=15)
