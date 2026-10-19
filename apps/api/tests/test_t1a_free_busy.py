"""Track 1 T1-A: free/busy trust, Google transparency ingest, snapshot fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.scheduler.free_busy import (
    clear_exception_policies,
    effective_free_busy_kind,
    evaluate_busy_input_trust,
    events_for_busy_merge,
    format_cli_listing,
    register_exception_policy,
    resolve_google_transparency,
    verify_snapshot_checksums,
    write_isolated_snapshot,
)


@dataclass
class _Evt:
    transparency: str | None
    free_busy_provenance: str | None
    start_time: datetime | None
    end_time: datetime | None
    calendar_id: str = "cal-1"
    title: str = "Meeting"
    external_event_id: str = "evt-1"
    provider_series_id: str | None = None


HORIZON_START = datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc)
HORIZON_END = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)


def test_resolve_google_transparency_case_a_explicit() -> None:
    stored, prov, kind = resolve_google_transparency({"transparency": "transparent"})
    assert stored == "transparent"
    assert prov == "provider_explicit"
    assert kind == "free"

    stored, prov, kind = resolve_google_transparency({"transparency": "opaque"})
    assert stored == "opaque"
    assert prov == "provider_explicit"
    assert kind == "busy"


def test_resolve_google_transparency_case_b_omitted_default_opaque() -> None:
    stored, prov, kind = resolve_google_transparency({})
    assert stored == "opaque"
    assert prov == "provider_default_omitted"
    assert kind == "busy"


def test_resolve_google_transparency_case_c_projection() -> None:
    stored, prov, kind = resolve_google_transparency(
        {}, complete_representation=False, field_projected=True
    )
    assert stored is None
    assert prov == "unknown_projection"
    assert kind == "unknown"


def test_legacy_null_is_unknown() -> None:
    assert effective_free_busy_kind(transparency=None, provenance=None) == "unknown"
    assert (
        effective_free_busy_kind(transparency=None, provenance="unknown_legacy")
        == "unknown"
    )


def test_busy_merge_skips_transparent() -> None:
    free = _Evt("transparent", "provider_explicit", HORIZON_START, HORIZON_END)
    busy = _Evt("opaque", "provider_explicit", HORIZON_START, HORIZON_END)
    merged = events_for_busy_merge([free, busy])
    assert merged == [busy]


def test_unknown_intersecting_blocks_trust() -> None:
    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    trust = evaluate_busy_input_trust(
        [unknown], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert len(trust.blocking_diagnostics) == 1
    assert trust.rollups[0].count == 1


def test_cannot_prove_non_intersection_blocks() -> None:
    unknown_bounds = _Evt(None, "unknown_legacy", None, None)
    trust = evaluate_busy_input_trust(
        [unknown_bounds], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert trust.affected_horizon == "unknown_extent"


def test_transparent_only_trust_ok() -> None:
    free = _Evt("transparent", "provider_explicit", HORIZON_START, HORIZON_END)
    trust = evaluate_busy_input_trust(
        [free], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is True
    assert trust.blocking_diagnostics == []


def test_opaque_inside_transparent_busy_merge() -> None:
    outer = _Evt("transparent", "provider_explicit", HORIZON_START, HORIZON_END, title="Outer")
    inner = _Evt(
        "opaque",
        "provider_explicit",
        datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 19, 19, 0, tzinfo=timezone.utc),
        title="Inner",
        external_event_id="inner",
    )
    assert events_for_busy_merge([outer, inner]) == [inner]
    trust = evaluate_busy_input_trust(
        [outer, inner], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is True


def test_exception_policy_by_series_id_not_title() -> None:
    clear_exception_policies()
    register_exception_policy("series-abc", "free")
    try:
        kind = effective_free_busy_kind(
            transparency=None,
            provenance="unknown_legacy",
            provider_series_id="series-abc",
        )
        assert kind == "free"
        # Same title, different/missing series → still unknown
        kind2 = effective_free_busy_kind(
            transparency=None,
            provenance="unknown_legacy",
            provider_series_id=None,
        )
        assert kind2 == "unknown"
    finally:
        clear_exception_policies()


def test_cli_listing_includes_rollup() -> None:
    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    trust = evaluate_busy_input_trust(
        [unknown], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    text = format_cli_listing(trust)
    assert "BusyInputTrust.ok=False" in text
    assert "Rollups:" in text
    assert "refresh" in text


def test_isolated_snapshot_checksum_roundtrip(tmp_path: Path) -> None:
    run_dir = write_isolated_snapshot(
        run_id="test-run-1",
        target_db="theplan_t1a_test",
        alembic_head="034_external_event_free_busy",
        git_tip="deadbeef",
        captured_unchanged=[{"id": "legacy-1", "status": "captured_unchanged"}],
        db_dump_bytes=b"fixture",
        root=tmp_path,
    )
    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "db.dump").is_file()
    assert (run_dir / "checksums.sha256").is_file()
    assert verify_snapshot_checksums(run_dir) is True
    (run_dir / "db.dump").write_bytes(b"tampered")
    assert verify_snapshot_checksums(run_dir) is False
