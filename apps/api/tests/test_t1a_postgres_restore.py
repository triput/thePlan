"""T1-A isolated Postgres dump/mutate/restore acceptance (disposable only)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.scheduler.free_busy import finalize_snapshot_evidence, write_isolated_snapshot
from tests.support.t1a_pg import (
    DISPOSABLE_TARGET_DB,
    T1A_PG_CONTAINER,
    assert_t1a_container_isolated,
    measure_post_restore,
    mutate_with_snapshot_gate,
    pg_dump_disposable_bytes,
    psql_t,
    restore_isolated_snapshot_to_postgres,
    seed_034_probe_row,
)


def _container_running() -> bool:
    try:
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", T1A_PG_CONTAINER],
            check=False,
            capture_output=True,
            text=True,
        )
        return out.returncode == 0 and (out.stdout or "").strip() == "true"
    except OSError:
        return False


requires_t1a_pg = pytest.mark.skipif(
    not _container_running(),
    reason=f"disposable container {T1A_PG_CONTAINER} not running — not acceptance evidence",
)


def test_refuses_household_container_name() -> None:
    with pytest.raises(RuntimeError, match="household"):
        assert_t1a_container_isolated("compose-postgres-1")


@requires_t1a_pg
def test_isolated_pg_dump_mutate_restore_recovers_034_fields(tmp_path: Path) -> None:
    meta = assert_t1a_container_isolated()
    assert meta["database"] == DISPOSABLE_TARGET_DB
    assert meta["host_port"] == "5433"
    assert meta["host_ip"] == "127.0.0.1"

    seed_034_probe_row()
    before = measure_post_restore()
    assert before["probe_transparency"] == "opaque"
    assert before["probe_history_sync"] == "batch-acceptance-1"
    assert before["alembic_version"] == "036_calendar_coverage_freshness"

    dump = pg_dump_disposable_bytes()
    run_dir = write_isolated_snapshot(
        run_id="pg-restore-unit",
        db_dump_bytes=dump,
        alembic_head=before["alembic_version"],
        git_tip="unit",
        root=tmp_path,
    )

    def mutate() -> None:
        psql_t(
            "UPDATE external_calendar_events SET transparency='transparent', "
            "free_busy_sync_run_id='mutated' WHERE external_event_id='t1a-synth-034'"
        )
        psql_t(
            "DELETE FROM external_calendar_events WHERE external_event_id='t1a-synth-034'"
        )

    mutate_with_snapshot_gate(run_dir, mutate_fn=mutate)
    assert measure_post_restore()["probe_count"] == "0"

    restore_meta = restore_isolated_snapshot_to_postgres(run_dir)
    assert restore_meta["pg_restore_rc"] == "0"
    measured = measure_post_restore()
    assert measured["probe_count"] == "1"
    assert measured["probe_transparency"] == before["probe_transparency"]
    assert measured["probe_provenance"] == before["probe_provenance"]
    assert measured["probe_sync_run_id"] == before["probe_sync_run_id"]
    assert measured["probe_history_sync"] == before["probe_history_sync"]
    assert measured["alembic_version"] == before["alembic_version"]
    assert (
        psql_t(
            "SELECT count(*)::text FROM information_schema.columns "
            "WHERE table_name='calendar_subscriptions' "
            "AND column_name='coverage_last_failure_at'"
        )
        == "1"
    )
    assert (
        psql_t(
            "SELECT count(*)::text FROM information_schema.columns "
            "WHERE table_name='external_calendar_events' "
            "AND column_name='is_provider_cancelled'"
        )
        == "1"
    )

    from app.scheduler.free_busy import verify_snapshot_checksums

    evidence_path = finalize_snapshot_evidence(
        run_dir,
        {
            "isolation": meta,
            "before": before,
            "after_restore": measured,
            "restore": {
                "restored_database": restore_meta["restored_database"],
                "pg_restore_rc": restore_meta["pg_restore_rc"],
            },
        },
    )
    assert evidence_path.is_file()
    assert verify_snapshot_checksums(run_dir)
    checksum_text = (run_dir / "checksums.sha256").read_text(encoding="utf-8")
    assert "evidence.json" in checksum_text


@requires_t1a_pg
def test_failed_pg_restore_does_not_pass_gate(tmp_path: Path) -> None:
    assert_t1a_container_isolated()
    seed_034_probe_row()
    run_dir = write_isolated_snapshot(
        run_id="pg-restore-negative",
        db_dump_bytes=b"this-is-not-a-custom-format-dump",
        alembic_head="036_calendar_coverage_freshness",
        root=tmp_path,
    )
    with pytest.raises(RuntimeError, match="pg_restore failed"):
        restore_isolated_snapshot_to_postgres(run_dir)
    # Probe still present — failed restore must not clear acceptance via rc=1 ignore
    assert measure_post_restore()["probe_count"] == "1"
