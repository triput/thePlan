"""Track 1 T1-A: free/busy trust, snapshot gate, exception identity, calculate guard."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.scheduler.free_busy import (
    DISPOSABLE_TARGET_DB,
    BusyInputTrust,
    BusyInputTrustError,
    ExceptionIdentity,
    apply_transparency_update,
    clear_exception_policies,
    effective_free_busy_kind,
    evaluate_busy_input_trust,
    events_for_busy_merge,
    format_cli_listing,
    mutate_with_snapshot_gate,
    register_exception_policy,
    require_busy_input_trust,
    resolve_google_transparency,
    restore_isolated_snapshot,
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
    owner_id: str = "owner-1"
    provider: str = "google"
    source_zone_missing: bool = False
    free_busy_pending_exception: bool = False


HORIZON_START = datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc)
HORIZON_END = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)


def test_resolve_google_cases_a_b_c() -> None:
    assert resolve_google_transparency({"transparency": "transparent"})[2] == "free"
    assert resolve_google_transparency({})[1] == "provider_default_omitted"
    assert (
        resolve_google_transparency({}, field_projected=True)[1] == "unknown_projection"
    )


def test_unknown_and_cannot_prove_block() -> None:
    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    assert evaluate_busy_input_trust(
        [unknown], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    ).ok is False

    no_bounds = _Evt(None, "unknown_legacy", None, None)
    trust = evaluate_busy_input_trust(
        [no_bounds], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert trust.affected_horizon == "unknown_extent"


def test_busy_or_free_with_unknown_bounds_block() -> None:
    busy_no_bounds = _Evt("opaque", "provider_explicit", None, None)
    trust = evaluate_busy_input_trust(
        [busy_no_bounds], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert any("unknown_extent" in d.cause for d in trust.blocking_diagnostics)


def test_missing_zone_and_pending_exception_block() -> None:
    missing = _Evt(
        "opaque",
        "provider_explicit",
        HORIZON_START,
        HORIZON_END,
        source_zone_missing=True,
    )
    pending = _Evt(
        "opaque",
        "provider_explicit",
        HORIZON_START,
        HORIZON_END,
        free_busy_pending_exception=True,
    )
    assert evaluate_busy_input_trust(
        [missing], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    ).ok is False
    assert evaluate_busy_input_trust(
        [pending], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    ).ok is False


def test_transparent_ok_and_opaque_inside_transparent() -> None:
    free = _Evt("transparent", "provider_explicit", HORIZON_START, HORIZON_END)
    inner = _Evt(
        "opaque",
        "provider_explicit",
        datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 19, 19, 0, tzinfo=timezone.utc),
        external_event_id="inner",
    )
    assert evaluate_busy_input_trust(
        [free, inner], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    ).ok is True
    assert events_for_busy_merge([free, inner]) == [inner]


def test_exception_policy_scoped_to_calendar_not_title() -> None:
    clear_exception_policies()
    ident = ExceptionIdentity("owner-1", "google", "cal-1", "series-abc")
    register_exception_policy(ident, "free")
    try:
        assert (
            effective_free_busy_kind(
                transparency=None,
                provenance="unknown_legacy",
                identity=ident,
            )
            == "free"
        )
        # Same series on a different calendar → no policy (move must re-raise).
        moved = ExceptionIdentity("owner-1", "google", "cal-2", "series-abc")
        assert (
            effective_free_busy_kind(
                transparency=None,
                provenance="unknown_legacy",
                identity=moved,
            )
            == "unknown"
        )
    finally:
        clear_exception_policies()


def test_require_busy_input_trust_blocks_none_and_false() -> None:
    with pytest.raises(BusyInputTrustError) as missing:
        require_busy_input_trust(None)
    assert missing.value.trust.blocking_diagnostics[0].cause == "missing_busy_input_trust"

    trust = BusyInputTrust(ok=False, blocking_diagnostics=[])
    with pytest.raises(BusyInputTrustError):
        require_busy_input_trust(trust)


def test_calculate_entry_fails_closed_on_missing_trust() -> None:
    """Real calculate() entry — gate fires before placement."""
    from unittest.mock import MagicMock

    from app.scheduler.calculate import calculate

    inputs = MagicMock()
    inputs.busy_input_trust = None
    with pytest.raises(BusyInputTrustError) as exc:
        calculate(MagicMock(), inputs)
    assert exc.value.trust.blocking_diagnostics[0].cause == "missing_busy_input_trust"
    # No later attribute access should have been needed; ok=False diagnostic present.
    assert exc.value.trust.ok is False


def test_calculate_entry_fails_closed_on_unknown_trust() -> None:
    from unittest.mock import MagicMock

    from app.scheduler.calculate import calculate

    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    trust = evaluate_busy_input_trust(
        [unknown], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    inputs = MagicMock()
    inputs.busy_input_trust = trust
    with pytest.raises(BusyInputTrustError):
        calculate(MagicMock(), inputs)


def test_unknown_never_reaches_fake_apply() -> None:
    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    trust = evaluate_busy_input_trust(
        [unknown], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    applied = {"yes": False}

    def pipeline() -> None:
        require_busy_input_trust(trust)
        applied["yes"] = True

    with pytest.raises(BusyInputTrustError):
        pipeline()
    assert applied["yes"] is False
    assert events_for_busy_merge([unknown]) == []


def test_trust_to_dict_json_serializable() -> None:
    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    trust = evaluate_busy_input_trust(
        [unknown], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    payload = trust.to_dict()
    json.dumps(payload)  # must not raise
    assert payload["ok"] is False
    assert isinstance(payload["blocking_diagnostics"][0]["start"], str)


def test_apply_transparency_retains_prior() -> None:
    row = SimpleNamespace(
        transparency="opaque",
        free_busy_provenance="provider_default_omitted",
        free_busy_prior_transparency=None,
        free_busy_prior_provenance=None,
        free_busy_sync_run_id=None,
        free_busy_changed_at=None,
    )
    apply_transparency_update(
        row,
        stored="transparent",
        provenance="provider_explicit",
        sync_run_id="run-1",
    )
    assert row.transparency == "transparent"
    assert row.free_busy_prior_transparency == "opaque"
    assert row.free_busy_prior_provenance == "provider_default_omitted"
    assert row.free_busy_sync_run_id == "run-1"


def test_snapshot_rejects_bad_target_and_dummy_and_overwrite(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="theplan_t1a_test"):
        write_isolated_snapshot(
            target_db="household",
            db_dump_bytes=b"real-bytes",
            root=tmp_path,
        )
    with pytest.raises(ValueError, match="db_dump_bytes"):
        write_isolated_snapshot(db_dump_bytes=b"", root=tmp_path)

    run_dir = write_isolated_snapshot(
        run_id="fixed-run",
        db_dump_bytes=b"postgres-dump-bytes",
        alembic_head="034_external_event_free_busy",
        git_tip="abc123",
        captured_unchanged=[{"id": "1", "status": "captured_unchanged"}],
        root=tmp_path,
    )
    assert verify_snapshot_checksums(run_dir)
    with pytest.raises(FileExistsError):
        write_isolated_snapshot(
            run_id="fixed-run",
            db_dump_bytes=b"other",
            root=tmp_path,
        )


def test_snapshot_restore_and_mutation_gate(tmp_path: Path) -> None:
    household_marker = tmp_path / "household_theplan.marker"
    household_marker.write_text("untouched", encoding="utf-8")

    run_dir = write_isolated_snapshot(
        db_dump_bytes=b"RESTORE-ME",
        root=tmp_path / "t1a-fixtures",
    )
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["target_db"] == DISPOSABLE_TARGET_DB == "theplan_t1a_test"

    restore_path = tmp_path / "theplan_t1a_test" / "restored.dump"
    restored = restore_isolated_snapshot(run_dir, restore_to=restore_path)
    assert restored.read_bytes() == b"RESTORE-ME"
    assert "theplan_t1a_test" in str(restored)
    assert household_marker.read_text(encoding="utf-8") == "untouched"

    mutated = {"n": 0}

    def do_mutate() -> str:
        mutated["n"] += 1
        return "ok"

    assert mutate_with_snapshot_gate(run_dir, mutate_fn=do_mutate) == "ok"
    assert mutated["n"] == 1

    (run_dir / "db.dump").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="stop"):
        mutate_with_snapshot_gate(run_dir, mutate_fn=do_mutate)
    assert mutated["n"] == 1  # mutate not called after checksum failure


def test_empty_checksum_file_rejected(tmp_path: Path) -> None:
    run_dir = tmp_path / "empty"
    run_dir.mkdir()
    (run_dir / "db.dump").write_bytes(b"x")
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "checksums.sha256").write_text("", encoding="utf-8")
    assert verify_snapshot_checksums(run_dir) is False


def test_cli_listing_and_disposable_constant() -> None:
    assert DISPOSABLE_TARGET_DB == "theplan_t1a_test"
    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    text = format_cli_listing(
        evaluate_busy_input_trust(
            [unknown],
            horizon_start=HORIZON_START,
            horizon_end=HORIZON_END,
            calendar_name_by_id={"cal-1": "TP@Gmail"},
        )
    )
    assert "BusyInputTrust.ok=False" in text
    assert "TP@Gmail" in text
    assert "Meeting" in text
    assert "evt-1" in text
    assert "Rollups:" in text


def test_preview_seam_blocks_before_proposal() -> None:
    """Mirror run_preview: require trust before building a proposal."""
    unknown = _Evt(None, "unknown_legacy", HORIZON_START, HORIZON_END)
    trust = evaluate_busy_input_trust(
        [unknown], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    proposal = {"built": False}

    def run_preview_seam() -> None:
        require_busy_input_trust(trust)
        proposal["built"] = True
        proposal["json"] = {"blocks": [1]}

    with pytest.raises(BusyInputTrustError) as exc:
        run_preview_seam()
    assert proposal["built"] is False
    assert "json" not in proposal
    # stats_json-safe payload
    json.dumps({"busy_input_trust": exc.value.trust.to_dict()})
