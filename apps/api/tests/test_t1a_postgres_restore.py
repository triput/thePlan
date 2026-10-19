"""T1-A isolated Postgres dump/mutate/restore acceptance (disposable only)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.scheduler.free_busy import (
    DISPOSABLE_TARGET_DB,
    T1A_PG_CONTAINER,
    T1A_PG_USER,
    assert_t1a_container_isolated,
    mutate_with_snapshot_gate,
    pg_dump_disposable_bytes,
    restore_isolated_snapshot_to_postgres,
    write_isolated_snapshot,
)


def _container_running() -> bool:
    try:
        out = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                T1A_PG_CONTAINER,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return out.returncode == 0 and (out.stdout or "").strip() == "true"
    except OSError:
        return False


requires_t1a_pg = pytest.mark.skipif(
    not _container_running(),
    reason=f"disposable container {T1A_PG_CONTAINER} not running",
)


def _psql(sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            T1A_PG_CONTAINER,
            "psql",
            "-U",
            T1A_PG_USER,
            "-d",
            DISPOSABLE_TARGET_DB,
            "-tAc",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return (result.stdout or "").strip()


@requires_t1a_pg
def test_isolated_pg_dump_mutate_restore_recovers_rows(tmp_path: Path) -> None:
    meta = assert_t1a_container_isolated()
    assert meta["database"] == DISPOSABLE_TARGET_DB
    assert "5433" in meta["inspect"] or "127.0.0.1" in meta["inspect"]

    _psql(
        "CREATE TABLE IF NOT EXISTS t1a_synth_probe "
        "(id int PRIMARY KEY, label text NOT NULL);"
        "TRUNCATE t1a_synth_probe;"
        "INSERT INTO t1a_synth_probe VALUES (1, 'baseline-row');"
    )
    assert _psql("SELECT label FROM t1a_synth_probe WHERE id=1") == "baseline-row"
    alembic_before = _psql("SELECT version_num FROM alembic_version")

    dump = pg_dump_disposable_bytes()
    run_dir = write_isolated_snapshot(
        run_id="pg-restore-acceptance",
        db_dump_bytes=dump,
        alembic_head=alembic_before,
        git_tip="local-t1a",
        root=tmp_path,
    )

    def mutate() -> None:
        _psql(
            "UPDATE t1a_synth_probe SET label='mutated' WHERE id=1;"
            "INSERT INTO t1a_synth_probe VALUES (2, 'extra');"
        )

    mutate_with_snapshot_gate(run_dir, mutate_fn=mutate)
    assert _psql("SELECT label FROM t1a_synth_probe WHERE id=1") == "mutated"
    assert _psql("SELECT count(*)::text FROM t1a_synth_probe") == "2"

    restore_meta = restore_isolated_snapshot_to_postgres(run_dir)
    assert restore_meta["restored_database"] == DISPOSABLE_TARGET_DB
    assert _psql("SELECT label FROM t1a_synth_probe WHERE id=1") == "baseline-row"
    assert _psql("SELECT count(*)::text FROM t1a_synth_probe") == "1"
    assert _psql("SELECT version_num FROM alembic_version") == alembic_before


def test_refuses_household_container_name() -> None:
    with pytest.raises(RuntimeError, match="household"):
        assert_t1a_container_isolated("compose-postgres-1")
