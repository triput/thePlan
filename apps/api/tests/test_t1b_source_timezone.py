"""Track 1 T1-B: source-zone date-only, DST, Windows/IANA, fail-closed missing zone."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.scheduler.busy_map import busy_from_sources
from app.scheduler.free_busy import evaluate_busy_input_trust, events_for_busy_merge
from app.services.google_calendar import parse_google_event_times
from app.services.microsoft_calendar import parse_microsoft_event_times
from app.services.source_timezone import (
    all_day_bounds_utc,
    resolve_iana_zone,
    windows_to_iana,
)

UTC = timezone.utc
OWNER_TZ = "America/Los_Angeles"  # must never reinterpret known source-local days
SOURCE_EASTERN = "America/New_York"
SOURCE_PACIFIC = "America/Los_Angeles"
SOURCE_CHICAGO = "America/Chicago"


def test_windows_to_iana_common_graph_ids() -> None:
    assert windows_to_iana("Pacific Standard Time") == "America/Los_Angeles"
    assert windows_to_iana("Eastern Standard Time") == "America/New_York"
    assert resolve_iana_zone("Pacific Standard Time") == "America/Los_Angeles"
    assert resolve_iana_zone("America/Chicago") == "America/Chicago"
    assert resolve_iana_zone("Not A Real Zone/Anywhere") is None


def test_t1_6_google_source_local_not_owner_reinterpretation() -> None:
    """Date-only on Eastern calendar must not use owner Pacific midnights."""
    event = {
        "start": {"date": "2026-10-19", "timeZone": SOURCE_EASTERN},
        "end": {"date": "2026-10-20", "timeZone": SOURCE_EASTERN},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None
    assert parsed.source_zone_missing is False
    assert parsed.source_timezone == SOURCE_EASTERN
    expected_start, expected_end = all_day_bounds_utc(
        date(2026, 10, 19), date(2026, 10, 20), SOURCE_EASTERN
    )
    owner_start, owner_end = all_day_bounds_utc(
        date(2026, 10, 19), date(2026, 10, 20), OWNER_TZ
    )
    assert parsed.start == expected_start
    assert parsed.end == expected_end
    assert parsed.start != owner_start
    assert parsed.end != owner_end
    # Eastern midnight = 04:00Z; Pacific midnight = 07:00Z in October.
    assert parsed.start == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
    assert parsed.end == datetime(2026, 10, 20, 4, 0, tzinfo=UTC)


def test_t1_6_spring_forward_exclusive_end_dst() -> None:
    """US Pacific spring-forward 2026-03-08: all-day spans 23 elapsed hours."""
    event = {
        "start": {"date": "2026-03-08", "timeZone": SOURCE_PACIFIC},
        "end": {"date": "2026-03-09", "timeZone": SOURCE_PACIFIC},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.start == datetime(2026, 3, 8, 8, 0, tzinfo=UTC)  # PST UTC-8
    assert parsed.end == datetime(2026, 3, 9, 7, 0, tzinfo=UTC)  # PDT UTC-7
    assert (parsed.end - parsed.start).total_seconds() == 23 * 3600


def test_t1_6_fall_back_exclusive_end_dst() -> None:
    """US Pacific fall-back 2026-11-01: all-day spans 25 elapsed hours."""
    event = {
        "start": {"date": "2026-11-01", "timeZone": SOURCE_PACIFIC},
        "end": {"date": "2026-11-02", "timeZone": SOURCE_PACIFIC},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.start == datetime(2026, 11, 1, 7, 0, tzinfo=UTC)  # PDT
    assert parsed.end == datetime(2026, 11, 2, 8, 0, tzinfo=UTC)  # PST
    assert (parsed.end - parsed.start).total_seconds() == 25 * 3600


def test_t1_6_multi_day_exclusive_end() -> None:
    event = {
        "start": {"date": "2026-10-19", "timeZone": SOURCE_CHICAGO},
        "end": {"date": "2026-10-22", "timeZone": SOURCE_CHICAGO},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    start, end = all_day_bounds_utc(
        date(2026, 10, 19), date(2026, 10, 22), SOURCE_CHICAGO
    )
    assert parsed.start == start
    assert parsed.end == end
    # Three source-local days: 19, 20, 21 — exclusive end 22.
    assert (parsed.end - parsed.start).total_seconds() == 3 * 24 * 3600


def test_t1_6_timed_conversion_with_zone() -> None:
    event = {
        "start": {"dateTime": "2026-10-19T09:30:00", "timeZone": SOURCE_EASTERN},
        "end": {"dateTime": "2026-10-19T10:30:00", "timeZone": SOURCE_EASTERN},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.is_all_day is False
    assert parsed.start == datetime(2026, 10, 19, 13, 30, tzinfo=UTC)
    assert parsed.end == datetime(2026, 10, 19, 14, 30, tzinfo=UTC)


def test_t1_6_google_calendar_default_zone_fallback() -> None:
    event = {
        "start": {"date": "2026-10-19"},
        "end": {"date": "2026-10-20"},
    }
    missing = parse_google_event_times(event)
    assert missing is not None and missing.source_zone_missing is True

    with_cal = parse_google_event_times(event, calendar_timezone=SOURCE_EASTERN)
    assert with_cal is not None and with_cal.source_zone_missing is False
    assert with_cal.source_timezone == SOURCE_EASTERN
    assert with_cal.start == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)


def test_t1_7_missing_zone_blocks_trust_not_busy_merge() -> None:
    event = {
        "start": {"date": "2026-10-19"},
        "end": {"date": "2026-10-20"},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None and parsed.source_zone_missing is True

    row = SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        start_time=parsed.start,
        end_time=parsed.end,
        calendar_id="cal-east",
        title="Birthday",
        external_event_id="all-day-no-zone",
        provider_series_id=None,
        owner_id="owner-1",
        provider="google",
        source_zone_missing=True,
        free_busy_pending_exception=False,
    )
    horizon_start = datetime(2026, 10, 19, 17, 0, tzinfo=UTC)
    horizon_end = datetime(2026, 10, 20, 1, 0, tzinfo=UTC)
    trust = evaluate_busy_input_trust(
        [row], horizon_start=horizon_start, horizon_end=horizon_end
    )
    assert trust.ok is False
    assert trust.affected_horizon == "unknown_extent"
    assert any(d.cause == "missing_source_zone" for d in trust.blocking_diagnostics)
    assert events_for_busy_merge([row]) == []
    assert busy_from_sources([], [row]) == []


def test_t1_7_unsupported_zone_fail_closed() -> None:
    event = {
        "start": {"date": "2026-10-19", "timeZone": "Mars/Olympus_Mons"},
        "end": {"date": "2026-10-20", "timeZone": "Mars/Olympus_Mons"},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None
    assert parsed.source_zone_missing is True
    assert parsed.source_timezone is None


def test_t1_7_indeterminate_conflicting_zones() -> None:
    event = {
        "start": {"date": "2026-10-19", "timeZone": SOURCE_EASTERN},
        "end": {"date": "2026-10-20", "timeZone": SOURCE_PACIFIC},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None
    assert parsed.source_zone_missing is True


def test_ms_all_day_uses_original_not_display_zone() -> None:
    """Prefer display UTC alone is not source provenance; original* wins."""
    event = {
        "id": "ms-1",
        "subject": "Holiday",
        "isAllDay": True,
        "originalStartTimeZone": "Eastern Standard Time",
        "originalEndTimeZone": "Eastern Standard Time",
        "start": {"dateTime": "2026-10-19T00:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T00:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.source_timezone == SOURCE_EASTERN
    assert parsed.start == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
    assert parsed.end == datetime(2026, 10, 20, 4, 0, tzinfo=UTC)

    display_only = {
        "id": "ms-2",
        "subject": "Holiday",
        "isAllDay": True,
        "start": {"dateTime": "2026-10-19T00:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T00:00:00.0000000", "timeZone": "UTC"},
    }
    rejected = parse_microsoft_event_times(display_only)
    assert rejected is not None and rejected.source_zone_missing is True


def test_ms_date_only_keys_unsupported() -> None:
    event = {
        "isAllDay": True,
        "start": {"date": "2026-10-19"},
        "end": {"date": "2026-10-20"},
        "originalStartTimeZone": "Pacific Standard Time",
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None
    assert parsed.source_zone_missing is True


def test_ms_timed_prefer_utc_naive_is_absolute() -> None:
    event = {
        "isAllDay": False,
        "start": {"dateTime": "2026-10-19T18:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-19T19:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.start == datetime(2026, 10, 19, 18, 0, tzinfo=UTC)
    assert parsed.end == datetime(2026, 10, 19, 19, 0, tzinfo=UTC)


def test_ms_windows_zone_spring_forward() -> None:
    event = {
        "isAllDay": True,
        "originalStartTimeZone": "Pacific Standard Time",
        "originalEndTimeZone": "Pacific Standard Time",
        "start": {"dateTime": "2026-03-08T00:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-03-09T00:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.start == datetime(2026, 3, 8, 8, 0, tzinfo=UTC)
    assert parsed.end == datetime(2026, 3, 9, 7, 0, tzinfo=UTC)


def test_bounds_feed_proposal_trust_when_zone_known() -> None:
    """Trusted opaque all-day with source zone → trust ok + busy merge occupancy."""
    parsed = parse_google_event_times(
        {
            "start": {"date": "2026-10-19", "timeZone": SOURCE_EASTERN},
            "end": {"date": "2026-10-20", "timeZone": SOURCE_EASTERN},
        }
    )
    assert parsed is not None
    row = SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        start_time=parsed.start,
        end_time=parsed.end,
        calendar_id="cal-east",
        title="NY Birthday",
        external_event_id="bday",
        provider_series_id=None,
        owner_id="owner-1",
        provider="google",
        source_zone_missing=False,
        free_busy_pending_exception=False,
        scheduled_block_id=None,
        pending_deletion=False,
    )
    # Horizon overlaps Eastern local Oct 19 afternoon (21:00Z).
    horizon_start = datetime(2026, 10, 19, 20, 0, tzinfo=UTC)
    horizon_end = datetime(2026, 10, 19, 22, 0, tzinfo=UTC)
    trust = evaluate_busy_input_trust(
        [row], horizon_start=horizon_start, horizon_end=horizon_end
    )
    assert trust.ok is True
    merged = busy_from_sources([], [row], range_start=horizon_start, range_end=horizon_end)
    assert len(merged) == 1
    assert merged[0].start == parsed.start
    assert merged[0].end == parsed.end


def test_upsert_persists_source_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from app.services import google_calendar as gc

    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    subscription = SimpleNamespace(
        id=uuid4(),
        external_calendar_id="cal-1",
        provider_timezone=None,
    )
    existing = SimpleNamespace(
        pending_deletion=False,
        calendar_id="cal-1",
        provider_series_id=None,
        calendar_account_id=None,
        title=None,
        start_time=None,
        end_time=None,
        is_all_day=False,
        last_synced_at=None,
        source_zone_missing=True,
        source_timezone=None,
        transparency=None,
        free_busy_provenance=None,
        free_busy_prior_transparency=None,
        free_busy_prior_provenance=None,
        free_busy_sync_run_id=None,
        free_busy_changed_at=None,
        free_busy_change_history=None,
        free_busy_pending_exception=False,
    )
    monkeypatch.setattr(gc, "_find_external_event", lambda *a, **k: existing)
    event = {
        "id": "evt-zone",
        "summary": "Holiday",
        "transparency": "opaque",
        "start": {"date": "2026-10-19", "timeZone": SOURCE_EASTERN},
        "end": {"date": "2026-10-20", "timeZone": SOURCE_EASTERN},
    }
    assert (
        gc._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=event,
            now=datetime.now(UTC),
            sync_run_id="t1b-1",
        )
        is True
    )
    assert existing.source_zone_missing is False
    assert existing.source_timezone == SOURCE_EASTERN
    assert existing.start_time == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
    assert existing.is_all_day is True
