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
    CLDR_WINDOWS_ZONES_OTHER_VERSION,
    CLDR_WINDOWS_ZONES_RELEASE,
    CLDR_WINDOWS_ZONES_TYPE_VERSION,
    CLDR_WINDOWS_ZONES_URL,
    IndeterminateLocalTime,
    all_day_bounds_utc,
    attach_naive_wall_clock,
    pick_consistent_zone,
    resolve_iana_zone,
    windows_to_iana,
)

UTC = timezone.utc
OWNER_TZ = "America/Los_Angeles"  # must never reinterpret known source-local days
SOURCE_EASTERN = "America/New_York"
SOURCE_PACIFIC = "America/Los_Angeles"
SOURCE_CHICAGO = "America/Chicago"
SOURCE_TOKYO = "Asia/Tokyo"


def test_cldr_windows_zones_citation_pinned() -> None:
    """Dex item 6: cite CLDR windowsZones.xml source/version used for the map."""
    assert CLDR_WINDOWS_ZONES_RELEASE == "release-48"
    assert CLDR_WINDOWS_ZONES_OTHER_VERSION == "7e11800"
    assert CLDR_WINDOWS_ZONES_TYPE_VERSION == "2021a"
    assert "windowsZones.xml" in CLDR_WINDOWS_ZONES_URL
    assert "release-48" in CLDR_WINDOWS_ZONES_URL


def test_windows_to_iana_common_graph_ids() -> None:
    assert windows_to_iana("Pacific Standard Time") == "America/Los_Angeles"
    assert windows_to_iana("Eastern Standard Time") == "America/New_York"
    assert windows_to_iana("Tokyo Standard Time") == "Asia/Tokyo"
    assert resolve_iana_zone("Pacific Standard Time") == "America/Los_Angeles"
    assert resolve_iana_zone("America/Chicago") == "America/Chicago"
    assert resolve_iana_zone("Not A Real Zone/Anywhere") is None


def test_unsupported_explicit_candidate_not_silently_dropped() -> None:
    """Dex item 4: unsupported explicit zone must not fall through to another candidate."""
    zone, indeterminate = pick_consistent_zone(
        "Mars/Olympus_Mons",
        SOURCE_EASTERN,
    )
    assert zone is None
    assert indeterminate is True

    alone, alone_indet = pick_consistent_zone("NotAWindowsId")
    assert alone is None and alone_indet is True


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


def test_dst_indeterminate_ambiguous_fold_fails_closed() -> None:
    """Dex item 3: ambiguous local wall clock must not silently use fold=0."""
    naive = datetime(2026, 11, 1, 1, 30, 0)
    with pytest.raises(IndeterminateLocalTime):
        attach_naive_wall_clock(naive, SOURCE_PACIFIC)

    event = {
        "start": {"dateTime": "2026-11-01T01:30:00", "timeZone": SOURCE_PACIFIC},
        "end": {"dateTime": "2026-11-01T02:30:00", "timeZone": SOURCE_PACIFIC},
    }
    parsed = parse_google_event_times(event)
    assert parsed is not None
    assert parsed.source_zone_missing is True


def test_dst_indeterminate_nonexistent_gap_fails_closed() -> None:
    """Dex item 3: spring-forward gap must not silently fold."""
    naive = datetime(2026, 3, 8, 2, 30, 0)
    with pytest.raises(IndeterminateLocalTime):
        attach_naive_wall_clock(naive, SOURCE_PACIFIC)

    event = {
        "isAllDay": False,
        "originalStartTimeZone": "Pacific Standard Time",
        "originalEndTimeZone": "Pacific Standard Time",
        "start": {
            "dateTime": "2026-03-08T02:30:00.0000000",
            "timeZone": "Pacific Standard Time",
        },
        "end": {
            "dateTime": "2026-03-08T03:30:00.0000000",
            "timeZone": "Pacific Standard Time",
        },
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None
    assert parsed.source_zone_missing is True


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
        is_all_day=True,
        source_zone_missing=True,
        source_timezone=None,
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


def test_ms_timed_prefer_utc_does_not_reinterpret_original_pacific() -> None:
    """Dex item 1: Prefer UTC wall clock + original* Pacific → absolute UTC, not Pacific wall."""
    event = {
        "isAllDay": False,
        "originalStartTimeZone": "Pacific Standard Time",
        "originalEndTimeZone": "Pacific Standard Time",
        "start": {"dateTime": "2026-10-19T17:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-19T18:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None
    assert parsed.source_zone_missing is False
    assert parsed.start == datetime(2026, 10, 19, 17, 0, tzinfo=UTC)
    assert parsed.end == datetime(2026, 10, 19, 18, 0, tzinfo=UTC)
    # Provenance may retain original* separately from the decode zone.
    assert parsed.source_timezone == SOURCE_PACIFIC
    # Must NOT be 17:00 Pacific → 00:00Z next day (PDT) or 01:00Z (PST).
    assert parsed.start != datetime(2026, 10, 20, 0, 0, tzinfo=UTC)
    assert parsed.start != datetime(2026, 10, 20, 1, 0, tzinfo=UTC)


def test_ms_all_day_tokyo_prefer_utc_recovers_civil_via_absolute() -> None:
    """Dex item 2: Prefer-UTC Tokyo all-day — do not slice UTC date then reattach Tokyo."""
    event = {
        "isAllDay": True,
        "originalStartTimeZone": "Tokyo Standard Time",
        "originalEndTimeZone": "Tokyo Standard Time",
        # Tokyo Oct 19 midnight = Oct 18 15:00Z; exclusive end Oct 20 midnight = Oct 19 15:00Z.
        "start": {"dateTime": "2026-10-18T15:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-19T15:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.source_timezone == SOURCE_TOKYO
    assert parsed.start == datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
    assert parsed.end == datetime(2026, 10, 19, 15, 0, tzinfo=UTC)
    # Wrong slice-and-reattach would treat civil Oct 18 Tokyo → Oct 17 15:00Z.
    wrong_slice, _ = all_day_bounds_utc(
        date(2026, 10, 18), date(2026, 10, 19), SOURCE_TOKYO
    )
    assert parsed.start != wrong_slice


def test_ms_all_day_utc_midnight_labeled_without_source_midnight_fails_closed() -> None:
    """Unproven floating: UTC 00:00 labeled + Eastern originals is not source midnight."""
    event = {
        "id": "ms-float",
        "subject": "Holiday",
        "isAllDay": True,
        "originalStartTimeZone": "Eastern Standard Time",
        "originalEndTimeZone": "Eastern Standard Time",
        "start": {"dateTime": "2026-10-19T00:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T00:00:00.0000000", "timeZone": "UTC"},
    }
    rejected = parse_microsoft_event_times(event)
    assert rejected is not None and rejected.source_zone_missing is True


def test_ms_all_day_prefer_utc_converted_eastern_trusted() -> None:
    """Prefer UTC correctly shifted Eastern midnight → recover civil + trust."""
    event = {
        "isAllDay": True,
        "originalStartTimeZone": "Eastern Standard Time",
        "originalEndTimeZone": "Eastern Standard Time",
        "start": {"dateTime": "2026-10-19T04:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T04:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.source_timezone == SOURCE_EASTERN
    assert parsed.start == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
    assert parsed.end == datetime(2026, 10, 20, 4, 0, tzinfo=UTC)


def test_ms_all_day_response_in_original_zone_midnight() -> None:
    """When response timeZone matches provenance midnight, decode + recover."""
    event = {
        "isAllDay": True,
        "originalStartTimeZone": "Eastern Standard Time",
        "originalEndTimeZone": "Eastern Standard Time",
        "start": {
            "dateTime": "2026-10-19T00:00:00.0000000",
            "timeZone": "Eastern Standard Time",
        },
        "end": {
            "dateTime": "2026-10-20T00:00:00.0000000",
            "timeZone": "Eastern Standard Time",
        },
    }
    parsed = parse_microsoft_event_times(event)
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.start == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)


def test_ms_all_day_display_only_fails_closed() -> None:
    display_only = {
        "id": "ms-2",
        "subject": "Holiday",
        "isAllDay": True,
        "start": {"dateTime": "2026-10-19T04:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T04:00:00.0000000", "timeZone": "UTC"},
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


def test_ms_windows_zone_spring_forward_prefer_utc() -> None:
    event = {
        "isAllDay": True,
        "originalStartTimeZone": "Pacific Standard Time",
        "originalEndTimeZone": "Pacific Standard Time",
        "start": {"dateTime": "2026-03-08T08:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-03-09T07:00:00.0000000", "timeZone": "UTC"},
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
        is_all_day=True,
        source_zone_missing=False,
        source_timezone=SOURCE_EASTERN,
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


def test_isolated_legacy_vs_absolute_trust_not_nullability() -> None:
    """Dex item 9: source_zone_missing + trust from actual flags, not nullability."""
    legacy_all_day = parse_google_event_times(
        {"start": {"date": "2026-10-19"}, "end": {"date": "2026-10-20"}}
    )
    assert legacy_all_day is not None
    assert legacy_all_day.source_zone_missing is True
    # Null source_timezone alone is not the trust signal — missing flag is.
    assert legacy_all_day.source_timezone is None

    absolute_timed = parse_microsoft_event_times(
        {
            "isAllDay": False,
            "start": {"dateTime": "2026-10-19T17:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-10-19T18:00:00Z", "timeZone": "UTC"},
        }
    )
    assert absolute_timed is not None
    assert absolute_timed.source_zone_missing is False
    # Provenance may be null while bounds are still trusted absolutes.
    assert absolute_timed.source_timezone is None

    ambiguous = parse_microsoft_event_times(
        {
            "isAllDay": True,
            "originalStartTimeZone": "Eastern Standard Time",
            "originalEndTimeZone": "Pacific Standard Time",
            "start": {"dateTime": "2026-10-19T04:00:00.0000000", "timeZone": "UTC"},
            "end": {"dateTime": "2026-10-20T04:00:00.0000000", "timeZone": "UTC"},
        }
    )
    assert ambiguous is not None
    assert ambiguous.source_zone_missing is True

    horizon_start = datetime(2026, 10, 19, 16, 0, tzinfo=UTC)
    horizon_end = datetime(2026, 10, 19, 19, 0, tzinfo=UTC)

    legacy_row = SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        start_time=legacy_all_day.start,
        end_time=legacy_all_day.end,
        calendar_id="cal",
        title="legacy",
        external_event_id="legacy-1",
        provider_series_id=None,
        owner_id="o",
        provider="google",
        is_all_day=True,
        source_zone_missing=legacy_all_day.source_zone_missing,
        source_timezone=legacy_all_day.source_timezone,
        free_busy_pending_exception=False,
        scheduled_block_id=None,
        pending_deletion=False,
    )
    abs_row = SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        start_time=absolute_timed.start,
        end_time=absolute_timed.end,
        calendar_id="cal",
        title="abs",
        external_event_id="abs-1",
        provider_series_id=None,
        owner_id="o",
        provider="microsoft",
        is_all_day=False,
        source_zone_missing=absolute_timed.source_zone_missing,
        source_timezone=absolute_timed.source_timezone,
        free_busy_pending_exception=False,
        scheduled_block_id=None,
        pending_deletion=False,
    )
    legacy_trust = evaluate_busy_input_trust(
        [legacy_row], horizon_start=horizon_start, horizon_end=horizon_end
    )
    abs_trust = evaluate_busy_input_trust(
        [abs_row], horizon_start=horizon_start, horizon_end=horizon_end
    )
    assert legacy_trust.ok is False
    assert any(d.cause == "missing_source_zone" for d in legacy_trust.blocking_diagnostics)
    assert abs_trust.ok is True
    assert events_for_busy_merge([legacy_row]) == []
    assert events_for_busy_merge([abs_row]) == [abs_row]


def test_ms_provenance_original_beats_calendar_default() -> None:
    """Dex: original* else calendar — explicit event zone must win over calendar."""
    event = {
        "isAllDay": True,
        "originalStartTimeZone": "Eastern Standard Time",
        "originalEndTimeZone": "Eastern Standard Time",
        "start": {"dateTime": "2026-10-19T04:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T04:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(
        event, calendar_timezone="America/Los_Angeles"
    )
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.source_timezone == SOURCE_EASTERN
    assert parsed.start == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)


def test_ms_provenance_unsupported_original_not_calendar_fallback() -> None:
    """Dex: unsupported explicit original* fails closed — no calendar fallthrough."""
    event = {
        "isAllDay": True,
        "originalStartTimeZone": "Mars/Olympus_Mons",
        "originalEndTimeZone": "Mars/Olympus_Mons",
        "start": {"dateTime": "2026-10-19T04:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T04:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(
        event, calendar_timezone=SOURCE_EASTERN
    )
    assert parsed is not None
    assert parsed.source_zone_missing is True
    assert parsed.source_timezone is None


def test_ms_provenance_calendar_default_when_originals_absent() -> None:
    event = {
        "isAllDay": True,
        "start": {"dateTime": "2026-10-19T04:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-20T04:00:00.0000000", "timeZone": "UTC"},
    }
    parsed = parse_microsoft_event_times(
        event, calendar_timezone=SOURCE_EASTERN
    )
    assert parsed is not None and not parsed.source_zone_missing
    assert parsed.source_timezone == SOURCE_EASTERN


def test_legacy_all_day_null_source_timezone_containment() -> None:
    """Pre-035 all-day with flag default false + null zone must not stay trusted."""
    from app.scheduler.free_busy import source_zone_untrusted

    legacy = SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        start_time=datetime(2026, 10, 19, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 10, 20, 0, 0, tzinfo=UTC),
        calendar_id="cal",
        title="legacy-utc-midnight",
        external_event_id="legacy-contain",
        provider_series_id=None,
        owner_id="o",
        provider="google",
        is_all_day=True,
        source_zone_missing=False,  # 034 server default
        source_timezone=None,
        free_busy_pending_exception=False,
        scheduled_block_id=None,
        pending_deletion=False,
    )
    abs_timed = SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        start_time=datetime(2026, 10, 19, 17, 0, tzinfo=UTC),
        end_time=datetime(2026, 10, 19, 18, 0, tzinfo=UTC),
        calendar_id="cal",
        title="abs-z",
        external_event_id="abs-null-prov",
        provider_series_id=None,
        owner_id="o",
        provider="microsoft",
        is_all_day=False,
        source_zone_missing=False,
        source_timezone=None,  # Julie: null named provenance OK for Z-offset timed
        free_busy_pending_exception=False,
        scheduled_block_id=None,
        pending_deletion=False,
    )
    assert source_zone_untrusted(legacy) is True
    assert source_zone_untrusted(abs_timed) is False
    horizon_start = datetime(2026, 10, 19, 16, 0, tzinfo=UTC)
    horizon_end = datetime(2026, 10, 19, 19, 0, tzinfo=UTC)
    legacy_trust = evaluate_busy_input_trust(
        [legacy], horizon_start=horizon_start, horizon_end=horizon_end
    )
    abs_trust = evaluate_busy_input_trust(
        [abs_timed], horizon_start=horizon_start, horizon_end=horizon_end
    )
    assert legacy_trust.ok is False
    assert any(d.cause == "missing_source_zone" for d in legacy_trust.blocking_diagnostics)
    assert events_for_busy_merge([legacy]) == []
    assert abs_trust.ok is True
    assert events_for_busy_merge([abs_timed]) == [abs_timed]


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
