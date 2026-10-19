"""One-shot: dump/mutate/restore on disposable T1-A Postgres; write evidence.json."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.scheduler.free_busy import (  # noqa: E402
    DISPOSABLE_TARGET_DB,
    T1A_FIXTURE_ROOT,
    T1A_PG_CONTAINER,
    T1A_PG_USER,
    assert_t1a_container_isolated,
    mutate_with_snapshot_gate,
    pg_dump_disposable_bytes,
    restore_isolated_snapshot_to_postgres,
    write_isolated_snapshot,
)


def _psql(sql: str) -> None:
    subprocess.run(
        [
            "docker",
            "exec",
            T1A_PG_CONTAINER,
            "psql",
            "-U",
            T1A_PG_USER,
            "-d",
            DISPOSABLE_TARGET_DB,
            "-c",
            sql,
        ],
        check=True,
    )


def main() -> None:
    tip = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(ROOT.parents[1]),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    meta = assert_t1a_container_isolated()
    _psql(
        "CREATE TABLE IF NOT EXISTS t1a_synth_probe "
        "(id int PRIMARY KEY, label text NOT NULL);"
        "TRUNCATE t1a_synth_probe;"
        "INSERT INTO t1a_synth_probe VALUES (1, 'baseline-row');"
    )
    dump = pg_dump_disposable_bytes()
    run_dir = write_isolated_snapshot(
        run_id="20261019T2115Z-acceptance",
        db_dump_bytes=dump,
        alembic_head="034_external_event_free_busy",
        git_tip=tip,
        captured_unchanged=[{"note": "synthetic probe only; no household rows"}],
        root=T1A_FIXTURE_ROOT,
    )

    def mutate() -> None:
        _psql(
            "UPDATE t1a_synth_probe SET label='mutated' WHERE id=1;"
            "INSERT INTO t1a_synth_probe VALUES (2, 'extra');"
        )

    mutate_with_snapshot_gate(run_dir, mutate_fn=mutate)
    restore_meta = restore_isolated_snapshot_to_postgres(run_dir)
    evidence = {
        "container": meta["container"],
        "database": meta["database"],
        "inspect": meta["inspect"],
        "household_isolation": (
            "compose-postgres-1 remains on host :5432; "
            "theplan-t1a-postgres publishes 127.0.0.1:5433 only"
        ),
        "alembic_head": "034_external_event_free_busy",
        "snapshot_run": str(run_dir),
        "restore": restore_meta,
        "auth_note": (
            "POSTGRES_HOST_AUTH_METHOD=trust; loopback publish only; "
            "no password in handoff"
        ),
        "final_state": (
            "container theplan-t1a-postgres running; "
            "db theplan_t1a_test at alembic 034; "
            "probe restored to baseline-row"
        ),
        "git_tip_at_evidence": tip,
    }
    out = run_dir / "evidence.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
