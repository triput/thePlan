"""One-shot: dump/mutate/restore on disposable T1-A Postgres; write evidence.json."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.scheduler.free_busy import (  # noqa: E402
    T1A_FIXTURE_ROOT,
    finalize_snapshot_evidence,
    write_isolated_snapshot,
)
from support.t1a_pg import (  # noqa: E402
    assert_t1a_container_isolated,
    measure_post_restore,
    mutate_with_snapshot_gate,
    pg_dump_disposable_bytes,
    psql_t,
    restore_isolated_snapshot_to_postgres,
    seed_034_probe_row,
)


def main() -> None:
    tip = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(ROOT.parents[1]),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{tip}-acceptance"

    meta = assert_t1a_container_isolated()
    seed_034_probe_row()
    before = measure_post_restore()
    dump = pg_dump_disposable_bytes()
    run_dir = write_isolated_snapshot(
        run_id=run_id,
        db_dump_bytes=dump,
        alembic_head=before["alembic_version"],
        git_tip=tip,
        captured_unchanged=[{"note": "034 probe on external_calendar_events; no household"}],
        root=T1A_FIXTURE_ROOT,
    )

    def mutate() -> None:
        psql_t(
            "UPDATE external_calendar_events SET transparency='transparent' "
            "WHERE external_event_id='t1a-synth-034'"
        )
        psql_t(
            "DELETE FROM external_calendar_events WHERE external_event_id='t1a-synth-034'"
        )

    mutate_with_snapshot_gate(run_dir, mutate_fn=mutate)
    mid = measure_post_restore()
    restore_meta = restore_isolated_snapshot_to_postgres(run_dir)
    after = measure_post_restore()

    evidence = {
        "git_tip": tip,
        "run_id": run_id,
        "isolation": {
            "container": meta["container"],
            "database": meta["database"],
            "host_ip": meta["host_ip"],
            "host_port": meta["host_port"],
            "networks": meta["networks"],
            "mounts_empty_or_non_household": len(meta["mounts"]) == 0
            or all("compose" not in str(m).lower() for m in meta["mounts"]),
            "household_isolation": (
                "compose-postgres-1 on host :5432; "
                "theplan-t1a-postgres on 127.0.0.1:5433 only"
            ),
        },
        "measured_before_dump": before,
        "measured_after_mutate": mid,
        "measured_after_restore": after,
        "restore": {
            "restored_database": restore_meta["restored_database"],
            "pg_restore_rc": restore_meta["pg_restore_rc"],
        },
        "auth_note": (
            "POSTGRES_HOST_AUTH_METHOD=trust; loopback publish only; "
            "no password in handoff"
        ),
        "prior_run_preserved": "20261019T2115Z-acceptance (pre-correction; not reclaimed)",
    }
    path = finalize_snapshot_evidence(run_dir, evidence)
    print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
