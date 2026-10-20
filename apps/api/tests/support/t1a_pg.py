"""T1-A disposable Postgres helpers (test/script support — not runtime scheduler)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.scheduler.free_busy import (
    DISPOSABLE_TARGET_DB,
    T1A_FIXTURE_ROOT,
    finalize_snapshot_evidence,
    mutate_with_snapshot_gate,
    verify_snapshot_checksums,
    write_isolated_snapshot,
)

T1A_PG_CONTAINER = "theplan-t1a-postgres"
T1A_PG_USER = "t1a"
_HOUSEHOLD_PG_CONTAINER = "compose-postgres-1"
_EXPECTED_HOST_PORT = "5433"
_EXPECTED_HOST_IP = "127.0.0.1"


def _docker_exec(
    container: str, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", container, *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _inspect_json(name: str) -> dict[str, Any]:
    inspect = subprocess.run(
        ["docker", "inspect", name, "--format", "{{json .}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(inspect.stdout)


def _mount_identities(payload: dict[str, Any]) -> set[str]:
    """Host-side mount identities (Name/Source/Binds). Skip Destination — same
    in-container path on every Postgres image is not volume sharing."""
    ids: set[str] = set()
    for m in payload.get("Mounts") or []:
        name = str(m.get("Name") or "").strip()
        source = str(m.get("Source") or "").strip()
        if name:
            ids.add(f"name:{name}")
        if source:
            ids.add(f"source:{source}")
    for b in (payload.get("HostConfig") or {}).get("Binds") or []:
        ids.add(f"bind:{b}")
    return ids


def assert_t1a_container_isolated(container: str = T1A_PG_CONTAINER) -> dict[str, Any]:
    """Refuse household compose Postgres; verify name, DB, ports, mounts, network."""
    if container == _HOUSEHOLD_PG_CONTAINER:
        raise RuntimeError("refusing household compose-postgres-1")
    if container != T1A_PG_CONTAINER:
        raise RuntimeError(
            f"refusing unexpected container {container!r}; expected {T1A_PG_CONTAINER!r}"
        )

    payload = _inspect_json(container)
    ports = payload.get("NetworkSettings", {}).get("Ports") or {}
    bindings = ports.get("5432/tcp") or []
    if not bindings:
        raise RuntimeError("disposable Postgres has no published 5432/tcp binding")
    if len(bindings) != 1:
        raise RuntimeError(f"expected exactly one host binding, got {bindings!r}")
    bind = bindings[0]
    if bind.get("HostIp") != _EXPECTED_HOST_IP or bind.get("HostPort") != _EXPECTED_HOST_PORT:
        raise RuntimeError(
            f"expected publish {_EXPECTED_HOST_IP}:{_EXPECTED_HOST_PORT}, got {bind!r}"
        )

    networks = set((payload.get("NetworkSettings") or {}).get("Networks") or {})
    # Standalone disposable must not join compose project networks.
    compose_nets = {n for n in networks if n.startswith("compose") or "_default" in n}
    if compose_nets:
        raise RuntimeError(f"refusing compose-project networks: {sorted(compose_nets)}")
    if networks != {"bridge"}:
        raise RuntimeError(f"expected networks={{bridge}}, got {sorted(networks)}")

    mounts = payload.get("Mounts") or []
    binds = (payload.get("HostConfig") or {}).get("Binds") or []
    t1a_ids = _mount_identities(payload)
    try:
        household = _inspect_json(_HOUSEHOLD_PG_CONTAINER)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("cannot inspect household compose-postgres-1 for mount compare") from exc
    shared = t1a_ids & _mount_identities(household)
    if shared:
        raise RuntimeError(f"refusing shared mount/bind identity with household: {sorted(shared)}")

    db = _docker_exec(
        container,
        "psql",
        "-U",
        T1A_PG_USER,
        "-d",
        DISPOSABLE_TARGET_DB,
        "-tAc",
        "SELECT current_database()",
    )
    name = (db.stdout or "").strip()
    if name != DISPOSABLE_TARGET_DB:
        raise RuntimeError(f"current_database is {name!r}, expected {DISPOSABLE_TARGET_DB!r}")

    return {
        "container": container,
        "database": name,
        "host_ip": bind.get("HostIp"),
        "host_port": bind.get("HostPort"),
        "mounts": mounts,
        "binds": binds,
        "networks": sorted(networks),
        "shared_mount_identities": [],
        "status": (payload.get("State") or {}).get("Status"),
    }


def pg_dump_disposable_bytes(*, container: str = T1A_PG_CONTAINER) -> bytes:
    """Custom-format pg_dump from disposable DB only (via docker exec)."""
    assert_t1a_container_isolated(container)
    remote = "/tmp/t1a_acceptance.dump"
    _docker_exec(
        container,
        "pg_dump",
        "-U",
        T1A_PG_USER,
        "-d",
        DISPOSABLE_TARGET_DB,
        "-Fc",
        "-f",
        remote,
    )
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            ["docker", "cp", f"{container}:{remote}", str(tmp_path)],
            check=True,
            capture_output=True,
        )
        data = tmp_path.read_bytes()
        if not data:
            raise RuntimeError("pg_dump produced empty dump")
        return data
    finally:
        tmp_path.unlink(missing_ok=True)


def restore_isolated_snapshot_to_postgres(
    run_dir: Path,
    *,
    container: str = T1A_PG_CONTAINER,
) -> dict[str, Any]:
    """pg_restore verified db.dump into disposable theplan_t1a_test only.

    Requires pg_restore exit code 0 (``--exit-on-error``).
    """
    if not verify_snapshot_checksums(run_dir):
        raise RuntimeError("snapshot checksum failed; refuse restore / mutation")
    meta = assert_t1a_container_isolated(container)
    dump = run_dir / "db.dump"
    remote = "/tmp/t1a_restore.dump"
    subprocess.run(
        ["docker", "cp", str(dump), f"{container}:{remote}"],
        check=True,
        capture_output=True,
    )
    result = _docker_exec(
        container,
        "pg_restore",
        "-U",
        T1A_PG_USER,
        "-d",
        DISPOSABLE_TARGET_DB,
        "--clean",
        "--if-exists",
        "--exit-on-error",
        remote,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pg_restore failed rc={result.returncode}: "
            f"{(result.stderr or result.stdout or '')[-800:]}"
        )
    db = _docker_exec(
        container,
        "psql",
        "-U",
        T1A_PG_USER,
        "-d",
        DISPOSABLE_TARGET_DB,
        "-tAc",
        "SELECT current_database()",
    )
    restored_db = (db.stdout or "").strip()
    if restored_db != DISPOSABLE_TARGET_DB:
        raise RuntimeError(f"restore landed on {restored_db!r}")
    meta["restored_database"] = restored_db
    meta["pg_restore_rc"] = str(result.returncode)
    return meta


def psql_t(sql: str, *, container: str = T1A_PG_CONTAINER) -> str:
    result = _docker_exec(
        container,
        "psql",
        "-U",
        T1A_PG_USER,
        "-d",
        DISPOSABLE_TARGET_DB,
        "-tAc",
        sql,
    )
    return (result.stdout or "").strip()


def seed_034_probe_row() -> None:
    """Insert a real external_calendar_events row exercising 034 columns."""
    # Minimal owner + account so FK holds; disposable DB only.
    # Use separate statements — psql -c with multi-statement is fine via -c once.
    psql_t(
        "INSERT INTO users (id, email, username, password_hash, must_change_password, session_epoch) "
        "SELECT 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid, 't1a-probe@example.test', "
        "'t1a_probe', 'x', false, 0 "
        "WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid)"
    )
    psql_t(
        "INSERT INTO calendar_accounts (id, owner_id, provider, account_email, is_enabled, mirror_blocks) "
        "SELECT 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'::uuid, "
        "'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid, 'google', 't1a@example.test', true, false "
        "WHERE NOT EXISTS (SELECT 1 FROM calendar_accounts "
        "WHERE id = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'::uuid)"
    )
    psql_t("DELETE FROM external_calendar_events WHERE external_event_id = 't1a-synth-034'")
    psql_t(
        "INSERT INTO external_calendar_events ("
        "id, owner_id, calendar_account_id, provider, external_event_id, calendar_id, "
        "title, start_time, end_time, is_all_day, pending_deletion, "
        "transparency, free_busy_provenance, free_busy_prior_transparency, "
        "free_busy_prior_provenance, free_busy_sync_run_id, free_busy_change_history, "
        "source_zone_missing, free_busy_pending_exception"
        ") VALUES ("
        "uuid_generate_v4(), "
        "'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid, "
        "'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'::uuid, "
        "'google', 't1a-synth-034', 'cal-t1a', "
        "'T1A probe', now(), now() + interval '1 hour', false, false, "
        "'opaque', 'provider_explicit', 'transparent', "
        "'provider_default_omitted', 'batch-acceptance-1', "
        "'[{\"sync_run_id\":\"batch-acceptance-1\",\"from_transparency\":\"transparent\","
        "\"to_transparency\":\"opaque\"}]'::jsonb, "
        "false, false)"
    )


def measure_post_restore() -> dict[str, Any]:
    """Query actual restored values (not hardcoded expectations)."""
    return {
        "database": psql_t("SELECT current_database()"),
        "alembic_version": psql_t("SELECT version_num FROM alembic_version"),
        "probe_transparency": psql_t(
            "SELECT transparency FROM external_calendar_events "
            "WHERE external_event_id = 't1a-synth-034'"
        ),
        "probe_provenance": psql_t(
            "SELECT free_busy_provenance FROM external_calendar_events "
            "WHERE external_event_id = 't1a-synth-034'"
        ),
        "probe_sync_run_id": psql_t(
            "SELECT free_busy_sync_run_id FROM external_calendar_events "
            "WHERE external_event_id = 't1a-synth-034'"
        ),
        "probe_history_sync": psql_t(
            "SELECT free_busy_change_history->0->>'sync_run_id' "
            "FROM external_calendar_events WHERE external_event_id = 't1a-synth-034'"
        ),
        "probe_count": psql_t(
            "SELECT count(*)::text FROM external_calendar_events "
            "WHERE external_event_id = 't1a-synth-034'"
        ),
        "probe_source_timezone": psql_t(
            "SELECT COALESCE(source_timezone, '<null>') FROM external_calendar_events "
            "WHERE external_event_id = 't1a-synth-034'"
        ),
        "probe_source_zone_missing": psql_t(
            "SELECT source_zone_missing::text FROM external_calendar_events "
            "WHERE external_event_id = 't1a-synth-034'"
        ),
        "has_source_timezone_column": psql_t(
            "SELECT count(*)::text FROM information_schema.columns "
            "WHERE table_name='external_calendar_events' AND column_name='source_timezone'"
        ),
    }


def assert_disposable_database_url(url: str) -> None:
    """Guard: exact loopback host, port 5433, database theplan_t1a_test."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    port = parsed.port
    db = (parsed.path or "").lstrip("/")
    if host not in ("127.0.0.1", "localhost") or port != 5433 or db != DISPOSABLE_TARGET_DB:
        raise RuntimeError(
            "refusing DSN: require loopback host, port 5433, "
            f"database {DISPOSABLE_TARGET_DB!r}"
        )


__all__ = [
    "DISPOSABLE_TARGET_DB",
    "T1A_FIXTURE_ROOT",
    "T1A_PG_CONTAINER",
    "T1A_PG_USER",
    "assert_disposable_database_url",
    "assert_t1a_container_isolated",
    "finalize_snapshot_evidence",
    "measure_post_restore",
    "mutate_with_snapshot_gate",
    "pg_dump_disposable_bytes",
    "psql_t",
    "restore_isolated_snapshot_to_postgres",
    "seed_034_probe_row",
    "verify_snapshot_checksums",
    "write_isolated_snapshot",
]
