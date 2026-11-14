"""In-runner entry for native-provider native-ready-prep-v1 first vertical.

PREPARATION AUTHORING ONLY. Real case dispatch/registry wiring lives here.
PKI child generation and peer bind require later launch authorization
(launch_ready must be true on runner-config). Incomplete cases are explicit
named HOLDs — never fabricated PASS. Unjoined/unconfirmed retirement → UNKNOWN.
No Docker daemon access from this seat.

Native-ready-prep-v1 folds Dex reconciliation C7B8FD74… + seams 57AA3A80… onto
tipped prep-v9: admit UID/config/guarded import roots BEFORE importing
np_integrated_runner/np_receipts; bind ephemeral in-memory ca_sha256 from
/public-ca/ca.crt before run_suite (I01/I02 custody; on-disk bytes preserved);
wire bounded safe PKI summary into successful runner report.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys
import threading
from time import monotonic
from typing import Any, Callable
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent
API_DIR = ROOT / "api"
RUNNER_CONFIG_NAME = "runner-config.json"
OUTPUT_BYTE_CAP = 1048576
REQUIRED_UID = 65534
PEER_SECONDS_DEFAULT = 120
COVERING_PATH = "/api/v1/calendar/covering-refresh"
PROVIDER_TLS_DIR = "/tmp/np-provider-tls"
PROVIDER_TLS_RECIPE = "prepare-np-provider-tls.sh"
PROVIDER_TLS_RECIPE_PATH = FIXTURE_DIR / PROVIDER_TLS_RECIPE
PROVIDER_PKI_SH_ABS = "/bin/sh"
PROVIDER_PKI_OPENSSL_ABS = "/usr/bin/openssl"
PROVIDER_PKI_GEN_SECONDS = 30
PROVIDER_PKI_REAP_SECONDS = 5
PROVIDER_PKI_READER_JOIN_SECONDS = 5
PROVIDER_PKI_WAIT_POLL_SECONDS = 0.05
PROVIDER_PKI_CAPTURE_CAP = 65536
PROVIDER_PKI_CHILD_ENV = {
    "PATH": "/usr/bin:/bin",
    "TMPDIR": "/tmp",
    "HOME": "/tmp",
    "LANG": "C",
    "LC_ALL": "C",
}

# Cases with authored runnable bodies under this prep successor.
IMPLEMENTED_CASE_IDS: frozenset[str] = frozenset({
    "NP-V-MS-NONEXPIRED",
    "NP-V-MS-REFRESH",
    "NP-V-MS-INVALID",
    "NP-T05-ORDERLY-CLOSE",
    "NP-T05-ABRUPT-TRUNCATION",
    "NP-T04-BODY-STALL",
})
_IMPORT_BOOTSTRAP_DONE = False
_PROVIDER_PKI_PREPARED = False


class RunnerEntryHeld(RuntimeError):
    """Admission / configuration HOLD — not a fabricated case PASS."""


class CaseBodyHold(RuntimeError):
    """Explicit named HOLD for an incomplete case body. Never emit as PASS."""

    def __init__(self, case_id: str, reason: str):
        self.case_id = case_id
        self.reason = reason
        super().__init__(f"HOLD:{case_id}:{reason}")


class BoundedOutput:
    """Hash/count console sink — raw console not retained for machine output."""

    def __init__(self) -> None:
        self.length = 0
        self.sha = hashlib.sha256()

    def write(self, value: str) -> int:
        data = value.encode("utf-8", errors="replace")
        self.length += len(data)
        if self.length > OUTPUT_BYTE_CAP:
            raise RuntimeError("runner console cap")
        self.sha.update(data)
        return len(value)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def load_runner_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RunnerEntryHeld("runner-config missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("launch_ready") is not True:
        raise RunnerEntryHeld("runner-config launch_ready is false — external operator gate")
    required = ("case_ids", "expected_unknown_cases", "runner_seconds", "runtime_pins")
    for key in required:
        if key not in data:
            raise RunnerEntryHeld(f"runner-config missing {key}")
    if type(data["runner_seconds"]) is not int or not 1 <= data["runner_seconds"] <= 3600:
        raise RunnerEntryHeld("runner_seconds must be frozen int on launch card")
    return data


def admit_runner_identity() -> None:
    if os.getuid() != REQUIRED_UID:
        raise RunnerEntryHeld("runner uid mismatch")
    if os.getuid() == 0:
        raise RunnerEntryHeld("root refused")


def admit_isolated_import_bootstrap(*, site_directories: list[str] | None = None) -> None:
    """Guard -I -S -B and admit only reviewed fixture/API/site roots.

    Adapted from passed native entry; packet layout uses payload/api (not
    workspace/apps/api). No ambient import path fallback. Prep does not invoke.
    """
    global _IMPORT_BOOTSTRAP_DONE
    if _IMPORT_BOOTSTRAP_DONE:
        return
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RunnerEntryHeld("require isolated -I -S -B invocation")
    if os.getuid() == 0:
        raise RunnerEntryHeld("root refused during import bootstrap")
    if not FIXTURE_DIR.is_dir() or not API_DIR.is_dir():
        raise RunnerEntryHeld("admitted fixture/api roots missing")
    admitted: list[str] = [str(FIXTURE_DIR), str(API_DIR)]
    if site_directories:
        for entry in site_directories:
            path = Path(entry)
            if not path.is_dir():
                raise RunnerEntryHeld(f"site directory missing:{entry}")
            admitted.append(str(path.resolve()))
    # Exact reviewed roots only; prepend so fixture/API win over any residual path.
    sys.path[:0] = admitted
    _IMPORT_BOOTSTRAP_DONE = True


class ProviderPkiCallerError(RuntimeError):
    """Bounded provider-PKI directory/child/group/readers failure. No raw keys."""


class _ProviderPkiCaptureSink:
    """Capped capture sink — observed may exceed retained; no unbounded event list."""

    def __init__(self) -> None:
        self.retained = bytearray()
        self.observed = 0
        self.overflow = False
        self.cap_observations = 0
        self.reader_error = False
        self.saw_eof = False


def _provider_pki_capture_reader(stream: Any, sink: _ProviderPkiCaptureSink) -> None:
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                sink.saw_eof = True
                return
            sink.observed += len(chunk)
            if sink.overflow:
                if sink.cap_observations < 1:
                    sink.cap_observations = 1
                continue
            if len(sink.retained) + len(chunk) > PROVIDER_PKI_CAPTURE_CAP:
                room = PROVIDER_PKI_CAPTURE_CAP - len(sink.retained)
                if room > 0:
                    sink.retained.extend(chunk[:room])
                sink.overflow = True
                sink.cap_observations = 1
                continue
            sink.retained.extend(chunk)
    except BaseException:
        sink.reader_error = True


def _provider_pki_group_probe(pgid: int | None) -> str:
    if pgid is None:
        return "unknown"
    try:
        os.killpg(pgid, 0)
        return "present"
    except ProcessLookupError:
        return "absent"
    except PermissionError:
        return "permission"
    except OSError:
        return "unknown"


def _provider_pki_retire_process_group(proc: Any, owned_pgid: int | None) -> dict[str, Any]:
    deadline = monotonic() + PROVIDER_PKI_REAP_SECONDS
    leader_exited = proc.poll() is not None
    state = _provider_pki_group_probe(owned_pgid)
    if state == "absent":
        return {"group_retired": True, "group_state": "absent", "leader_exited": leader_exited}
    if owned_pgid is not None:
        try:
            os.killpg(owned_pgid, signal.SIGKILL)
        except ProcessLookupError:
            state = "absent"
        except OSError:
            state = _provider_pki_group_probe(owned_pgid)
    while monotonic() < deadline:
        leader_exited = proc.poll() is not None
        state = _provider_pki_group_probe(owned_pgid)
        if state == "absent":
            return {"group_retired": True, "group_state": "absent", "leader_exited": leader_exited}
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        try:
            proc.wait(timeout=min(PROVIDER_PKI_WAIT_POLL_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            continue
    leader_exited = proc.poll() is not None
    state = _provider_pki_group_probe(owned_pgid)
    return {
        "group_retired": state == "absent",
        "group_state": state,
        "leader_exited": leader_exited,
    }


def _provider_pki_join_started_readers(
    started: list[threading.Thread], secondary: list[dict[str, Any]]
) -> bool:
    joined = True
    for reader in started:
        reader.join(timeout=PROVIDER_PKI_READER_JOIN_SECONDS)
        if reader.is_alive():
            joined = False
            secondary.append({"phase": "reader_join", "kind": "unjoined"})
    return joined


def _provider_pki_close_owned_pipes(
    owned_endpoints: list[dict[str, Any]], secondary: list[dict[str, Any]]
) -> int:
    unretired = 0
    for endpoint in owned_endpoints:
        pipe = endpoint.get("pipe")
        if pipe is None or endpoint.get("closed"):
            continue
        try:
            pipe.close()
            endpoint["closed"] = True
        except BaseException as error:
            unretired += 1
            secondary.append({"phase": "pipe_close", "kind": type(error).__name__})
    return unretired


def admit_provider_pki_private_dir() -> dict[str, Any]:
    """Admit/create private TLS_DIR ownership (uid/mode/empty) distinct from /public-ca.

    Directory admission only — does not spawn openssl.
    """
    if os.getuid() != REQUIRED_UID:
        raise ProviderPkiCallerError("provider pki uid")
    if PROVIDER_TLS_DIR != "/tmp/np-provider-tls":
        raise ProviderPkiCallerError("provider tls dir pin mismatch")
    if PROVIDER_TLS_DIR in ("/public-ca", "/fixture-tls"):
        raise ProviderPkiCallerError("provider tls dir collides with db trust")
    if not os.path.isdir(PROVIDER_TLS_DIR):
        previous = os.umask(0o077)
        try:
            os.mkdir(PROVIDER_TLS_DIR, 0o700)
            os.chmod(PROVIDER_TLS_DIR, 0o700)
        finally:
            os.umask(previous)
    owned = os.stat(PROVIDER_TLS_DIR)
    if owned.st_uid != REQUIRED_UID or stat.S_IMODE(owned.st_mode) != 0o700:
        raise ProviderPkiCallerError("provider tls ownership/mode")
    if os.listdir(PROVIDER_TLS_DIR):
        raise ProviderPkiCallerError("provider tls nonempty")
    return {
        "tls_dir": PROVIDER_TLS_DIR,
        "uid": REQUIRED_UID,
        "mode": "0700",
        "empty": True,
        "db_trust_isolated": True,
        "public_ca_untouched": "/public-ca",
    }


def invoke_bounded_provider_pki_recipe(
    *, generate: bool = False, launch_ready: bool = False
) -> dict[str, Any]:
    """Actual bounded provider-PKI recipe caller (directory/child/group/readers).

    AUTHORED in named entry/recipe roles. INVOKING held under preparation:
    generate must be True AND launch_ready must be True before any child spawn.
    No retry. Private keys stay in runner tmpfs; DB /public-ca trust stays separate.
    Real peer cannot run on PREPARED_NOT_GENERATED metadata alone.
    """
    if generate is not True or launch_ready is not True:
        raise RunnerEntryHeld(
            "provider PKI invoke held — require generate=True and launch_ready=True "
            "(prep authors the caller; does not invoke)"
        )
    if not PROVIDER_TLS_RECIPE_PATH.is_file():
        raise ProviderPkiCallerError("prepare-np-provider-tls.sh recipe missing")
    recipe = str(PROVIDER_TLS_RECIPE_PATH.resolve())
    dir_receipt = admit_provider_pki_private_dir()
    admission_deadline = monotonic() + PROVIDER_PKI_GEN_SECONDS
    stdout_sink = _ProviderPkiCaptureSink()
    stderr_sink = _ProviderPkiCaptureSink()
    constructed_readers: list[threading.Thread] = []
    started_readers: list[threading.Thread] = []
    owned_endpoints: list[dict[str, Any]] = []
    secondary: list[dict[str, Any]] = []
    proc = None
    owned_pgid = None
    group_report = {
        "group_retired": False,
        "group_state": "not_started",
        "leader_exited": False,
    }
    readers_joined = False
    pipes_closed = False
    primary: BaseException | None = None
    try:
        if monotonic() >= admission_deadline:
            primary = ProviderPkiCallerError("provider pki generation timeout")
        else:
            proc = subprocess.Popen(
                [PROVIDER_PKI_SH_ABS, recipe],
                executable=PROVIDER_PKI_SH_ABS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(PROVIDER_PKI_CHILD_ENV),
                cwd="/tmp",
                start_new_session=True,
                close_fds=True,
            )
            owned_pgid = proc.pid
            owned_endpoints = [
                {
                    "pipe": proc.stdout,
                    "reader": None,
                    "sink": stdout_sink,
                    "started": False,
                    "closed": False,
                },
                {
                    "pipe": proc.stderr,
                    "reader": None,
                    "sink": stderr_sink,
                    "started": False,
                    "closed": False,
                },
            ]
            for endpoint, name in (
                (owned_endpoints[0], "np-provider-openssl-stdout"),
                (owned_endpoints[1], "np-provider-openssl-stderr"),
            ):
                reader = threading.Thread(
                    target=_provider_pki_capture_reader,
                    args=(endpoint["pipe"], endpoint["sink"]),
                    name=name,
                    daemon=False,
                )
                constructed_readers.append(reader)
                endpoint["reader"] = reader
            for endpoint in owned_endpoints:
                reader = endpoint["reader"]
                if reader is None:
                    continue
                try:
                    reader.start()
                except BaseException as error:
                    secondary.append(
                        {"phase": "reader_start", "kind": type(error).__name__}
                    )
                    if primary is None:
                        primary = ProviderPkiCallerError("provider pki reader start")
                    break
                endpoint["started"] = True
                started_readers.append(reader)
            while primary is None:
                if stdout_sink.overflow or stderr_sink.overflow:
                    primary = ProviderPkiCallerError("provider pki capture cap")
                    break
                if stdout_sink.reader_error or stderr_sink.reader_error:
                    primary = ProviderPkiCallerError("provider pki capture reader")
                    break
                remaining = admission_deadline - monotonic()
                if remaining <= 0:
                    primary = ProviderPkiCallerError("provider pki generation timeout")
                    break
                try:
                    proc.wait(timeout=min(PROVIDER_PKI_WAIT_POLL_SECONDS, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if primary is None and proc.returncode != 0:
                primary = ProviderPkiCallerError("provider pki generation refused")
    except ProviderPkiCallerError as error:
        if primary is None:
            primary = error
        else:
            secondary.append({"phase": "generation", "kind": type(error).__name__})
    except BaseException as error:
        wrapped = ProviderPkiCallerError(type(error).__name__)
        wrapped.__cause__ = error
        if primary is None:
            primary = wrapped
        else:
            secondary.append({"phase": "generation", "kind": type(error).__name__})
    if owned_pgid is not None and proc is not None:
        try:
            group_report = _provider_pki_retire_process_group(proc, owned_pgid)
        except BaseException as error:
            group_report = {
                "group_retired": False,
                "group_state": "unknown",
                "leader_exited": proc.poll() is not None,
            }
            secondary.append({"phase": "group_retire", "kind": type(error).__name__})
    try:
        readers_joined = _provider_pki_join_started_readers(started_readers, secondary)
    except BaseException as error:
        readers_joined = False
        secondary.append({"phase": "reader_join", "kind": type(error).__name__})
    started_sinks = [item["sink"] for item in owned_endpoints if item.get("started")]
    readers_eof = (
        all(sink.saw_eof and not sink.reader_error for sink in started_sinks)
        if started_sinks
        else True
    )
    # Dex A8096174…: leader exit can precede reader drain. Recheck overflow AFTER
    # joins/EOF and before GENERATED; preserve any earlier primary failure.
    late_overflow = bool(stdout_sink.overflow or stderr_sink.overflow)
    if late_overflow:
        if primary is None:
            primary = ProviderPkiCallerError("provider pki late capture overflow")
        else:
            secondary.append({"phase": "late_overflow", "kind": "overflow_after_join"})
    pipes_unretired = 0
    try:
        pipes_unretired = _provider_pki_close_owned_pipes(owned_endpoints, secondary)
        pipes_closed = pipes_unretired == 0 and not any(
            item.get("phase") == "pipe_close" for item in secondary
        )
    except BaseException as error:
        pipes_closed = False
        secondary.append({"phase": "pipe_close", "kind": type(error).__name__})
    extra = {
        **dir_receipt,
        "recipe": PROVIDER_TLS_RECIPE,
        "recipe_abs": recipe,
        "sh_abs": PROVIDER_PKI_SH_ABS,
        "openssl_abs": PROVIDER_PKI_OPENSSL_ABS,
        "generate_invoked": True,
        "retry": False,
        "child_retired": group_report.get("group_retired") is True,
        "group_state": group_report.get("group_state"),
        "leader_exited": group_report.get("leader_exited"),
        "readers_joined": readers_joined,
        "readers_eof": readers_eof,
        "late_overflow_checked": True,
        "late_overflow": late_overflow,
        "readers_constructed": len(constructed_readers),
        "readers_started": len(started_readers),
        "owned_pipes": len(owned_endpoints),
        "pipes_closed": pipes_closed,
        "pipes_unretired": pipes_unretired,
        "secondary_retirement": list(secondary),
        "stdout_observed_bytes": stdout_sink.observed,
        "stderr_observed_bytes": stderr_sink.observed,
        "status": "GENERATED",
    }
    retirement_unknown = (
        owned_pgid is not None
        and group_report.get("group_state") in ("present", "permission", "unknown")
    ) or (started_readers and not readers_joined) or (
        started_sinks and not readers_eof
    ) or (pipes_unretired > 0) or (owned_endpoints and not pipes_closed)
    if primary is not None:
        raise primary
    if retirement_unknown:
        raise ProviderPkiCallerError("provider pki retirement unknown")
    if late_overflow:
        raise ProviderPkiCallerError("provider pki late capture overflow")
    if proc is None or proc.returncode != 0:
        raise ProviderPkiCallerError("provider pki generation mismatch")
    return extra


def prepare_provider_pki_private_dir(*, generate: bool = False) -> dict[str, Any]:
    """Prep-path PKI admission — recipe/pin contract without child spawn.

    Metadata alone is not runnable for a real peer. The admitted native entry
    path must call admit_provider_pki_generated_once / invoke_bounded_provider_pki_recipe
    exactly once and require GENERATED before peer startup.
    """
    global _PROVIDER_PKI_PREPARED
    if generate is not False:
        raise RunnerEntryHeld(
            "provider PKI generation held — use admit_provider_pki_generated_once "
            "under launch_ready; prep does not invoke"
        )
    if not PROVIDER_TLS_RECIPE_PATH.is_file():
        raise RunnerEntryHeld("prepare-np-provider-tls.sh recipe missing")
    if PROVIDER_TLS_DIR != "/tmp/np-provider-tls":
        raise RunnerEntryHeld("provider TLS dir pin mismatch")
    receipt = {
        "recipe": PROVIDER_TLS_RECIPE,
        "tls_dir": PROVIDER_TLS_DIR,
        "uid": REQUIRED_UID,
        "mode": "0700",
        "generate_invoked": False,
        "db_trust_isolated": True,
        "public_ca_untouched": "/public-ca",
        "child_group_readers_retirement": "C06_PATTERN_AUTHORED_UNINVOKED",
        "actual_caller": "admit_provider_pki_generated_once",
        "status": "PREPARED_NOT_GENERATED",
        "native_pki_gap": "caller_authored_invocation_held_until_launch",
    }
    _PROVIDER_PKI_PREPARED = True
    return receipt


_PROVIDER_PKI_GENERATE_ONCE_DONE = False


def admit_provider_pki_generated_once(*, launch_ready: bool) -> dict[str, Any]:
    """Admitted native path: generate disposable provider PKI exactly once.

    Requires successful GENERATED disposition BEFORE any peer startup.
    AUTHORED for the future launch path; preparation must not invoke it.
    Dex A8096174… — connect the bounded caller to the native entry path.
    """
    global _PROVIDER_PKI_GENERATE_ONCE_DONE
    if _PROVIDER_PKI_GENERATE_ONCE_DONE:
        raise ProviderPkiCallerError("provider pki generate-once already consumed")
    if launch_ready is not True:
        raise RunnerEntryHeld(
            "provider PKI generate-once held — launch_ready required "
            "(prep authors the call site; does not invoke)"
        )
    disposition = invoke_bounded_provider_pki_recipe(
        generate=True, launch_ready=True
    )
    _PROVIDER_PKI_GENERATE_ONCE_DONE = True
    if disposition.get("status") != "GENERATED":
        raise ProviderPkiCallerError("provider pki generation disposition refused")
    if disposition.get("generate_invoked") is not True:
        raise ProviderPkiCallerError("provider pki generate_invoked false")
    if disposition.get("late_overflow") is True:
        raise ProviderPkiCallerError("provider pki late capture overflow")
    return disposition


def provision_disposable_schema(factory: Any) -> dict[str, Any]:
    """Explicit disposable schema/provisioning before seed (setup ≠ app evidence)."""
    from app import db as app_db
    import app.models  # noqa: F401 — register mapped tables on Base.metadata

    setup = factory.open_setup_session()
    try:
        app_db.Base.metadata.create_all(setup.connection(), checkfirst=False)
        setup.commit()
    finally:
        factory.close(setup)
    # Prefer named provision_native when present on the passed lineage.
    provisioned = False
    try:
        from native_suite import provision_native  # type: ignore

        provision_native(factory)
        provisioned = True
    except ImportError:
        # Packet may not ship native_suite; create_all above is the required step.
        provisioned = False
    return {
        "create_all": True,
        "provision_native": provisioned,
        "synthetic_setup_separate_from_terminal_evidence": True,
    }


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hold_reason(case_id: str) -> str:
    return (
        f"case body not yet authored for execution-ready path; "
        f"obligation retained in np_suite registry; "
        f"first increment implements {sorted(IMPLEMENTED_CASE_IDS)}; "
        f"incomplete cases are HOLD not PASS"
    )


def _fixture_database_profile() -> Any:
    from app.services.covering_native_checkout import PostgreSQLPeer

    # DB trust stays /public-ca — distinct from provider /tmp/np-provider-tls.
    # Hostname/db/user literals must match immutable bootstrap+prepare-tls
    # (native-fixture.invalid / dex_fixture), not product db/scheduler defaults.
    return PostgreSQLPeer(
        hostname="native-fixture.invalid",
        address="127.0.0.1",
        port=5432,
        database="dex_fixture",
        username="dex_fixture",
        ca_file="/public-ca/ca.crt",
        absent_passfile="/tmp/np-absent-pgpass",
        client_cert="/tmp/np-absent-client.crt",
        client_key="/tmp/np-absent-client.key",
    )


def _runtime_pins_from_config() -> Any:
    from app.services.covering_native_orm_factory import NativeRuntimePins

    config_path = ROOT / RUNNER_CONFIG_NAME
    data = json.loads(config_path.read_text(encoding="utf-8"))
    pins = data.get("runtime_pins") or {}
    if not isinstance(pins, dict) or pins.get("python") is None:
        raise RunnerEntryHeld("runtime_pins.python must be frozen on launch card before run")
    return NativeRuntimePins(
        python=tuple(pins["python"]),
        psycopg=str(pins["psycopg"]),
        sqlalchemy=str(pins["sqlalchemy"]),
        pq_implementation=str(pins["pq_implementation"]),
        pq_runtime=int(pins["pq_runtime"]),
        pq_build=int(pins["pq_build"]),
    )


def _ms_provider_routes(*, peer_hostname: str, dial_address: str, dial_port: int, ca_file: str):
    """Exact MS identity vs event route classification for CoveringHTTP."""
    from app.services.covering_transport_policy import HTTPSPeer

    peer = HTTPSPeer(
        hostname=peer_hostname,
        address=dial_address,
        port=dial_port,
        ca_file=ca_file,
    )
    # Identity routes (not event): default calendar + calendars list (exact).
    # Event routes: trailing-slash prefix so /v1.0/me/calendars/{id}/calendarView
    # matches without making the identity list path ambiguous (path==prefix).
    return (
        (peer, "/v1.0/me/calendar", "identity"),
        (peer, "/v1.0/me/calendars", "identity"),
        (peer, "/v1.0/me/calendars/", "event"),
    )


def _extract_token_rollback_ack(native_terminals: list[dict[str, Any]]) -> bool:
    """TOKEN ROLLBACK from actual native terminal receipts — not guessed response keys."""
    for row in native_terminals:
        terminal = row.get("terminal") or row.get("token_terminal") or row.get("outcome")
        if terminal in ("ROLLBACK_ACKNOWLEDGED", "RootOutcome.ROLLBACK_ACKNOWLEDGED"):
            return True
        if row.get("token_rollback_ack") is True:
            return True
        name = str(terminal)
        if "ROLLBACK_ACKNOWLEDGED" in name and "COMMIT" not in name.split("ROLLBACK")[0]:
            return True
    return False


def _observe_token_terminals(native_terminals: list[dict[str, Any]]) -> Any:
    """Wrap production token terminal hook to capture acknowledgments."""
    from app.services.covering_target_transaction import RootOutcome

    def capture(outcome: Any) -> Any:
        label = outcome.name if hasattr(outcome, "name") else str(outcome)
        native_terminals.append(
            {
                "terminal": label,
                "token_rollback_ack": outcome is RootOutcome.ROLLBACK_ACKNOWLEDGED
                or label == "ROLLBACK_ACKNOWLEDGED",
            }
        )
        return outcome

    return capture


def _run_np_v_ms_nonexpired() -> dict[str, Any]:
    """Production vertical: Settings + covering-refresh ASGI + default JoinedTLS.

    Chain: CoveringReleasePlan.for_request → ProviderCounter → CoveringHTTP
    (default JoinedTLS) — no transport_factory injection, no FixtureByteTransport
    alias wrapper in the JoinedTLS claim. Synthetic peer serves finite
    Connection:close inventory on numeric loopback :443.
    """
    import inspect

    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_auth_seed import (
        COVERING_PATH as AUTH_COVERING_PATH,
        IDENTITY_DEFAULT_MS_CALENDAR_ID,
        STABLE_UNRELATED_MS_CALENDAR_ID,
        assert_plan_still_valid,
        covering_refresh_body,
        derive_production_target_calendar_order,
        fixture_settings,
        fresh_attempt_plan,
        identity_list_calendar_ids_for_vertical,
        inverted_subscription_ids,
        measure_subscription_coverage_state,
        PlanValidityExpired,
        seed_browser_owner_with_subscriptions,
        seed_token_plan,
    )
    from np_alias_seed import microsoft_primary_alias_seed, sanitized_alias_receipt
    from np_receipts import case_result_receipt
    from np_provider_routes import microsoft_graph_route
    from np_provider_transcript import ms_nonexpired_connection_inventory
    from np_provider_peer import SyntheticProviderPeer, PeerMaterial, PeerRetirementUnknown
    from i01_asgi_app import asgi_client, build_i01_asgi_app, install_binding
    from app.services.covering_release_plan import CoveringReleasePlan
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_http_dispatch import CoveringReleaseBinding
    from app.services.covering_target_transaction import RootOutcome
    from app.services.calendar_alias_canonicalize import MS_LEGACY_PRIMARY_ALIAS

    del AUTH_COVERING_PATH  # same path constant; COVERING_PATH used below
    case_id = "NP-V-MS-NONEXPIRED"
    decl = registry_by_id(include_cf=True)[case_id]
    plan = fresh_attempt_plan(case_id)
    t_plan_iso = plan.t_plan.isoformat()
    token_seed = seed_token_plan(case_id=case_id, provider="microsoft", expired=False)
    alias = microsoft_primary_alias_seed(case_id=case_id)
    settings = fixture_settings()

    # Default JoinedTLS must remain the CoveringHTTP transport_factory.
    sig = inspect.signature(CoveringHTTP.__init__)
    transport_default = sig.parameters["transport_factory"].default
    if transport_default is not JoinedTLS:
        raise SuiteStop("production CoveringHTTP default is not JoinedTLS")

    route = microsoft_graph_route()
    planted = inverted_subscription_ids(case_token=plan.attempt_token)
    # Seed factory opens setup session via native ORM factory (launch path).
    factory = _open_native_setup_factory(settings=settings)
    # Explicit disposable schema/provisioning BEFORE seed (blocker 3).
    schema_receipt = provision_disposable_schema(factory)
    setup = factory.open_setup_session()
    try:
        seed = seed_browser_owner_with_subscriptions(
            setup,
            settings=settings,
            username_prefix="np-ms-nonexpired",
            subscription_count=2,
            provider="microsoft",
            expired=False,
            mark_covering_fresh_at_seed=False,
            planted_subscription_ids=planted,
            t_plan=plan.t_plan,
            plant_microsoft_primary_alias=True,
        )
        setup.commit()
    finally:
        factory.close(setup)

    assert seed.request_window_start is not None and seed.request_window_end is not None
    assert seed.t_plan is not None
    assert_plan_still_valid(seed.t_plan)
    if MS_LEGACY_PRIMARY_ALIAS not in seed.calendar_ids:
        raise SuiteStop("enabled MS primary alias not planted on subscription row")

    wire_calendar_ids = derive_production_target_calendar_order(
        subscription_ids=list(seed.subscription_ids),
        subscription_calendar_map=dict(seed.subscription_calendar_map),
        primary_alias=MS_LEGACY_PRIMARY_ALIAS,
        identity_default_calendar_id=IDENTITY_DEFAULT_MS_CALENDAR_ID,
    )
    # Alias-Subset-Safe-Seed: identity list returns cal-ms-default (default) +
    # cal-np-other (nondefault). Sequence: default identity, list identity,
    # calendarView(cal-ms-default), calendarView(cal-np-other). After first
    # requested-row rewrite no primary remains → no second identity fetch.
    identity_list_ids = identity_list_calendar_ids_for_vertical()
    if identity_list_ids[0] != IDENTITY_DEFAULT_MS_CALENDAR_ID:
        raise SuiteStop("identity list must mark cal-ms-default as default")
    if identity_list_ids[1] != STABLE_UNRELATED_MS_CALENDAR_ID:
        raise SuiteStop("identity list must include unrelated stable calendar")
    if wire_calendar_ids != (
        IDENTITY_DEFAULT_MS_CALENDAR_ID,
        STABLE_UNRELATED_MS_CALENDAR_ID,
    ):
        raise SuiteStop(
            f"wire calendar order mismatch:{wire_calendar_ids!r}; "
            "expected (cal-ms-default, cal-np-other) from lower-ID primary rewrite"
        )
    before_external = dict(seed.subscription_calendar_map)
    lower_sorted = sorted(seed.subscription_ids, key=str)[0]
    if before_external.get(str(lower_sorted)) != MS_LEGACY_PRIMARY_ALIAS:
        raise SuiteStop("primary alias must sit on LOWER str-sorted subscription id")
    inventory_scripts = ms_nonexpired_connection_inventory(
        calendar_ids=tuple(seed.calendar_ids),
        identity_list_calendar_ids=identity_list_ids,
        wire_calendar_ids=wire_calendar_ids,
    )
    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}",
        route=route,
        connection_scripts=inventory_scripts,
        material=PeerMaterial(),
    )
    observations: dict[str, Any] = {}
    native_terminals: list[dict[str, Any]] = []
    client_inventory: list[dict[str, Any]] = []
    oauth_requests = 0
    held_transport: list[Any] = []
    captured_contexts: list[Any] = []
    worker_exceptions: list[BaseException] = []
    restore_worker_observer: Callable[[], None] | None = None
    real_request = None
    transport = None
    retirement_done = False
    retirement_attempted = False
    primary_failure: BaseException | None = None

    try:
        assert_plan_still_valid(plan.t_plan)
        peer.start_background(seconds=PEER_SECONDS_DEFAULT)

        database_profile = _fixture_database_profile()
        runtime_pins = _runtime_pins_from_config()
        provider_routes = _ms_provider_routes(
            peer_hostname=route.server_hostname,
            dial_address=route.dial_address,
            dial_port=route.dial_port,
            ca_file=route.ca_path,
        )
        # Install the actual CoveringReleasePlan — worker calls for_request(context.budget).
        # Do NOT preconstruct CoveringReleaseBinding or inject transport_factory.
        release_plan = CoveringReleasePlan(
            database_profile=database_profile,
            password_supplier=lambda: "",
            runtime_pins=runtime_pins,
            provider_routes=provider_routes,
            settings=settings,
        )
        if type(release_plan) is CoveringReleaseBinding:
            raise SuiteStop("must install CoveringReleasePlan, not prebuilt binding")

        # Measure BEFORE from persisted rows (not literal False).
        measure_db = factory.open_setup_session()
        try:
            before_state = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)
        if before_state["any_covering_success"] is True:
            raise SuiteStop("before-state already covering-success; vertical not distinguishable")

        def on_context(context: Any) -> None:
            captured_contexts.append(context)

        # Observe CoveringHTTP construction + request purposes during worker/POST.
        real_init = CoveringHTTP.__init__
        _install_token_terminal_observer(native_terminals)

        def capturing_init(self, *args, **kwargs):
            nonlocal real_request, transport
            real_init(self, *args, **kwargs)
            held_transport.append(self)
            transport = self
            if self.transport_factory is not JoinedTLS:
                raise SuiteStop("transport_factory injection refused — require default JoinedTLS")
            underlying = self.request

            def counted_request(method, url, *, purpose, **kwargs):
                nonlocal oauth_requests
                if purpose == "oauth":
                    oauth_requests += 1
                client_inventory.append(
                    {
                        "method": method,
                        "purpose": purpose,
                        "url_host_present": True,
                        "connection_close_expected": True,
                    }
                )
                return underlying(method, url, purpose=purpose, **kwargs)

            real_request = underlying
            self.request = counted_request  # type: ignore[method-assign]

        CoveringHTTP.__init__ = capturing_init  # type: ignore[method-assign]
        try:
            # Observe the dispatch worker boundary for this POST only (location-only diagnostic).
            restore_worker_observer = _install_worker_exception_observer(worker_exceptions)
            # Real monotonic clock — not ControllableClock(0.0) frozen budget evidence.
            app = build_i01_asgi_app(
                session_secret=settings.session_secret,
                clock=monotonic,
                on_context=on_context,
            )
            install_binding(app, release_plan)
            client = asgi_client(app)

            body = covering_refresh_body(
                list(seed.subscription_ids),
                window_start=seed.request_window_start,
                window_end=seed.request_window_end,
            )
            assert_plan_still_valid(seed.t_plan)
            response = client.post(
                COVERING_PATH,
                content=json.dumps(body).encode("utf-8"),
                headers={"content-type": "application/json"},
                cookies={"session": seed.cookie},
            )
        finally:
            # Unconditional exact restoration of the worker observer before any assertion.
            if restore_worker_observer is not None:
                restore_worker_observer()
                restore_worker_observer = None
            CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]
            # Restore observation hooks even on failure.
            try:
                if transport is not None and real_request is not None:
                    transport.request = real_request
            except Exception:
                pass

        assert_plan_still_valid(seed.t_plan)
        if not captured_contexts:
            raise SuiteStop("ingress on_context did not capture actual request context")
        ingress_context = captured_contexts[0]
        ingress_budget = getattr(ingress_context, "budget", None)
        if ingress_budget is None:
            raise SuiteStop("captured ingress context missing budget")
        if len(held_transport) != 1 or type(held_transport[0]) is not CoveringHTTP:
            raise SuiteStop("worker/POST did not construct exactly one CoveringHTTP")
        if transport is None:
            transport = held_transport[0]
        # Provisional-V5 (1CB895E0…): ProviderCounter stores budget.work_remaining as
        # counter.remaining — NOT counter.budget or transport.budget. Observe
        # remaining.__self__ (ingress budget) and remaining.__func__ (work_remaining).
        from app.services.covering_request_budget import CoveringRequestBudget

        counter = getattr(transport, "counter", None)
        if counter is None:
            raise SuiteStop("CoveringHTTP.counter missing after for_request")
        remaining_cb = getattr(counter, "remaining", None)
        if remaining_cb is None:
            raise SuiteStop("ProviderCounter.remaining missing")
        if getattr(transport, "budget", None) is not None:
            raise SuiteStop("do not invent transport.budget as proof")
        if getattr(counter, "budget", None) is not None:
            raise SuiteStop("do not invent counter.budget as proof")
        bound_budget = getattr(remaining_cb, "__self__", None)
        bound_func = getattr(remaining_cb, "__func__", None)
        if bound_budget is not ingress_budget:
            raise SuiteStop(
                "counter.remaining.__self__ is not the captured ingress context.budget"
            )
        if bound_func is not CoveringRequestBudget.work_remaining:
            raise SuiteStop(
                "counter.remaining.__func__ is not CoveringRequestBudget.work_remaining"
            )

        if response.status_code != 200:
            worker_failure = worker_exceptions[0] if worker_exceptions else None
            if worker_failure is not None:
                raise SuiteStop(f"covering-refresh status:{response.status_code}") from worker_failure
            raise SuiteStop(f"covering-refresh status:{response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SuiteStop("covering-refresh response is not a typed object")
        # Exact public schema (C340C47B): coverage_action + scheduling_readiness —
        # not truthiness of similarly named private-worker keys.
        if "coverage_action" not in payload or "scheduling_readiness" not in payload:
            raise SuiteStop("covering-refresh missing coverage_action/scheduling_readiness")
        coverage_action = payload["coverage_action"]
        readiness = payload["scheduling_readiness"]
        if not isinstance(coverage_action, dict) or not isinstance(readiness, dict):
            raise SuiteStop("coverage_action/scheduling_readiness must be objects")
        freshness_requested = coverage_action.get("freshness_requested")
        if not isinstance(freshness_requested, dict):
            raise SuiteStop("coverage_action.freshness_requested missing typed object")
        freshness_ok = freshness_requested.get("ok")
        all_ok = coverage_action.get("all_requested_covering_ok")
        scheduling_ready = readiness.get("scheduling_ready")
        scheduling_revision = readiness.get("scheduling_revision")
        freshness_all = readiness.get("freshness_all_enabled")
        if freshness_ok is not True:
            raise SuiteStop("freshness_requested.ok is not True")
        if all_ok is not True:
            raise SuiteStop("all_requested_covering_ok is not True")
        if scheduling_ready is not True:
            raise SuiteStop("scheduling_readiness.scheduling_ready is not True")
        if type(scheduling_revision) is not int or scheduling_revision < 1:
            raise SuiteStop("scheduling_revision not typed int>=1")
        if not isinstance(freshness_all, dict) or freshness_all.get("ok") is not True:
            raise SuiteStop("freshness_all_enabled.ok is not True")
        # Reject private-worker dictionary shapes leaking into the public route.
        for banned in ("command", "provider", "mode", "seed_hash", "assessment"):
            if banned in payload:
                raise SuiteStop(f"public covering-refresh must not carry private key:{banned}")

        # Measure AFTER from persisted rows.
        measure_db = factory.open_setup_session()
        try:
            after_state = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)

        if before_state["all_covering_success"] == after_state["all_covering_success"]:
            if after_state["all_covering_success"] is not True:
                raise SuiteStop("before/after coverage not distinguishable")
        if after_state["all_covering_success"] is not True:
            raise SuiteStop("after-state missing covering success")

        token_rollback_acked = _extract_token_rollback_ack(native_terminals)
        if oauth_requests != 0:
            raise SuiteStop("nonexpired path must not perform OAuth exchange")
        if not token_rollback_acked:
            raise SuiteStop("TOKEN ROLLBACK acknowledgment missing from native terminals")

        peer_state = peer.sanitized_state()
        served = int(peer_state.get("connection_count_served") or 0)
        admitted = int(peer_state.get("connection_count_admitted") or 0)
        if served != admitted or served != len(inventory_scripts):
            raise SuiteStop(
                f"peer exchange inventory mismatch served={served} admitted={admitted}"
            )
        if any(row.get("purpose") == "oauth" for row in client_inventory):
            raise SuiteStop("client inventory recorded oauth purpose")

        observations = {
            "no_oauth_request": "OBSERVED",
            "token_rollback_ack": True,
            "identity_event_assessment_separate": "OBSERVED",
            "covering_path": COVERING_PATH,
            "settings_module": "app.config.Settings",
            "joined_tls_default": True,
            "byte_transport_alias_used": False,
            "release_plan_installed": True,
            "primary_alias_planted": MS_LEGACY_PRIMARY_ALIAS,
            "primary_alias_on_lower_sorted_id": True,
            "wire_calendar_order": list(wire_calendar_ids),
            "schema_provisioned": schema_receipt,
            # Dex C7B8FD74 / First-Native-Result-Acceptance-Docket: drop stale
            # provider_pki_invoked=False prep metadata. Status agrees with the
            # suite-level typed provider_pki_summary on success only.
            "provider_pki_caller": "admit_provider_pki_generated_once",
            "provider_pki_status": (
                "GENERATED" if _PROVIDER_PKI_GENERATE_ONCE_DONE else "PREPARED_NOT_GENERATED"
            ),
        }
        after_external = dict(after_state.get("external_calendar_ids") or {})
        alias_rewrite = {
            "before_external_calendar_ids": before_external,
            "after_external_calendar_ids": after_external,
            "lower_sorted_subscription_id": str(lower_sorted),
            "primary_alias_before": MS_LEGACY_PRIMARY_ALIAS,
            "canonical_default_after": IDENTITY_DEFAULT_MS_CALENDAR_ID,
            "unrelated_stable": STABLE_UNRELATED_MS_CALENDAR_ID,
            "identity_list_ids": list(identity_list_ids),
            "second_identity_fetch_expected": False,
        }
        if after_external.get(str(lower_sorted)) == MS_LEGACY_PRIMARY_ALIAS:
            raise SuiteStop("primary alias remained after requested-row rewrite")
        if MS_LEGACY_PRIMARY_ALIAS in after_external.values():
            raise SuiteStop("enabled primary alias remains after first rewrite")
        measured = {
            "before": before_state,
            "after": after_state,
            "coverage_action": {
                "all_requested_covering_ok": all_ok,
                "freshness_requested_ok": freshness_ok,
            },
            "scheduling_readiness": {
                "scheduling_ready": scheduling_ready,
                "scheduling_revision": scheduling_revision,
                "freshness_all_enabled_ok": freshness_all.get("ok"),
            },
            "oauth_request_count": oauth_requests,
            "token_rollback_ack": token_rollback_acked,
            "native_terminals": list(native_terminals),
            "client_exchange_inventory": list(client_inventory),
            "alias_hash": alias.seed_hash,
            "token_label_hash": token_seed.label_hash,
            "root_outcome_rollback": RootOutcome.ROLLBACK_ACKNOWLEDGED.name,
            "ingress_budget_same_as_provider": True,
            "budget_proof": "counter.remaining.__self__/__func__",
            "wire_calendar_order": list(wire_calendar_ids),
            "alias_rewrite": alias_rewrite,
        }
        _ = sanitized_alias_receipt(alias)
        check_oracles_immediate(decl, {"no_oauth_request": "OBSERVED", "token_rollback_ack": "OBSERVED", "identity_event_assessment_separate": "OBSERVED"})
        t_check_iso = _iso_now()
        assert_plan_still_valid(plan.t_plan)
        # One confirmed bounded retirement — mark attempt BEFORE call so a raised
        # PeerRetirementUnknown cannot trigger a second attempt in finally.
        retirement_attempted = True
        retirement = peer.retire_owned(join_seconds=5.0)
        retirement_done = True
        workers_joined = retirement.get("joined") is True
        if not workers_joined:
            raise SuiteStop("peer worker unjoined — UNKNOWN")
        unexpected = [
            t
            for t in threading.enumerate()
            if t is not threading.main_thread() and t.name.startswith("np-peer-")
        ]
        if unexpected:
            raise SuiteStop("unjoined np-peer worker after retirement")

        return case_result_receipt(
            case_id=case_id,
            passed=True,
            workers_joined=True,
            expected_unknown=False,
            executed=True,
            prep_is_not_pass=True,
            observations=observations,
            t_plan_iso=t_plan_iso,
            t_check_iso=t_check_iso,
            measured=measured,
            peer_exchange_inventory=list(peer_state.get("exchange_inventory") or []),
            resource_disposition={
                "peer_retired": True,
                "peer_joined": True,
                "factory_closed": True,
                "provider_pki_status": (
                    "GENERATED"
                    if _PROVIDER_PKI_GENERATE_ONCE_DONE
                    else (
                        "PREPARED_NOT_GENERATED"
                        if _PROVIDER_PKI_PREPARED
                        else "NOT_PREPARED"
                    )
                ),
                "provider_pki_generated": _PROVIDER_PKI_GENERATE_ONCE_DONE is True,
            },
        )
    except PlanValidityExpired:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except PeerRetirementUnknown:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise SuiteStop("owned peer retirement UNKNOWN")
    except CaseBodyHold:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except SuiteStop:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except BaseException as exc:
        # Preserve original failure class through SuiteStop; do not skip report layer.
        primary_failure = exc
        raise SuiteStop(f"framework_stop:{case_id}:{type(exc).__name__}") from exc
    finally:
        try:
            if transport is not None and real_request is not None:
                transport.request = real_request
        except Exception:
            pass
        # Explicit attempt/disposition guard: only the sole failure-path retirement
        # when NO attempt has occurred. Never second-attempt after primary retirement
        # failure; never swallow PeerRetirementUnknown.
        if (
            not retirement_attempted
            and peer._worker is not None
            and not peer.life.joined
        ):  # noqa: SLF001
            retirement_attempted = True
            try:
                peer.retire_owned(join_seconds=5.0)
                retirement_done = True
            except PeerRetirementUnknown:
                if primary_failure is None:
                    raise SuiteStop("owned peer retirement UNKNOWN on cleanup")
                raise SuiteStop(
                    f"owned peer retirement UNKNOWN after primary:{type(primary_failure).__name__}"
                ) from primary_failure


def _ms_refresh_provider_routes(
    *,
    graph_hostname: str,
    token_hostname: str,
    dial_address: str,
    dial_port: int,
    ca_file: str,
    token_path: str,
):
    """NP-V-MS-REFRESH routes: the UNCHANGED graph identity/event table plus one exact
    OAuth route on a distinct login.microsoftonline.com HTTPSPeer (same CA/address/port).
    """
    from app.services.covering_transport_policy import HTTPSPeer

    graph_routes = _ms_provider_routes(
        peer_hostname=graph_hostname,
        dial_address=dial_address,
        dial_port=dial_port,
        ca_file=ca_file,
    )
    token_peer = HTTPSPeer(
        hostname=token_hostname,
        address=dial_address,
        port=dial_port,
        ca_file=ca_file,
    )
    return tuple(graph_routes) + ((token_peer, token_path, "oauth"),)


def _require_production_ms_token_path(*, settings: Any, token_hostname: str, token_path: str) -> None:
    """Cross-check the fixture-derived token path against the actual pinned production builder."""
    from urllib.parse import urlsplit

    from np_suite import SuiteStop
    from app.services import microsoft_calendar as production_ms

    production_url = production_ms._token_url(  # noqa: SLF001 — read-only pinned builder
        production_ms._normalize_tenant(settings.microsoft_tenant_id)  # noqa: SLF001
    )
    parts = urlsplit(production_url)
    if (
        parts.scheme != "https"
        or parts.hostname != token_hostname
        or parts.port is not None
        or parts.path != token_path
        or parts.query
        or parts.fragment
    ):
        raise SuiteStop("fixture MS token path disagrees with production _token_url")


def _actual_token_terminals(native_terminals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Native TOKEN terminal receipts only — excludes the observer marker row."""
    return [row for row in native_terminals if "observer" not in row]


def _run_np_v_ms_refresh() -> dict[str, Any]:
    """NP-V-MS-REFRESH (T06-SUCCESS-MICROSOFT): expired MS token refreshed on the
    production path, separate single-case batch.

    Chain: covering-refresh ASGI ingress → CoveringReleasePlan.for_request →
    ProviderCounter → CoveringHTTP (default JoinedTLS) → owning expired Microsoft
    refresh (one OAuth POST at the production-derived tenant path) → native TOKEN
    COMMIT (first target) / ROLLBACK (second target re-read) → IMPORT → final
    ASSESSMENT. No transport injection, clock freezing, reseed or retry.
    """
    import inspect

    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_auth_seed import (
        IDENTITY_DEFAULT_MS_CALENDAR_ID,
        STABLE_UNRELATED_MS_CALENDAR_ID,
        assert_plan_still_valid,
        covering_refresh_body,
        derive_production_target_calendar_order,
        fixture_settings,
        fresh_attempt_plan,
        identity_list_calendar_ids_for_vertical,
        inverted_subscription_ids,
        measure_account_credential_state,
        measure_subscription_coverage_state,
        PlanValidityExpired,
        seed_browser_owner_with_subscriptions,
        seed_token_plan,
    )
    from np_alias_seed import microsoft_primary_alias_seed, sanitized_alias_receipt
    from np_receipts import case_result_receipt
    from np_provider_routes import microsoft_graph_route, microsoft_token_route
    from np_provider_transcript import (
        MS_REFRESH_EXCHANGE_COUNT,
        MS_TOKEN_ENDPOINT_PATH,
        ms_refresh_connection_inventory,
    )
    from np_provider_peer import SyntheticProviderPeer, PeerMaterial, PeerRetirementUnknown
    from i01_asgi_app import asgi_client, build_i01_asgi_app, install_binding
    from app.services.covering_release_plan import CoveringReleasePlan
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_http_dispatch import CoveringReleaseBinding
    from app.services.covering_target_transaction import RootOutcome
    from app.services.calendar_alias_canonicalize import MS_LEGACY_PRIMARY_ALIAS

    case_id = "NP-V-MS-REFRESH"
    decl = registry_by_id(include_cf=True)[case_id]
    plan = fresh_attempt_plan(case_id)
    t_plan_iso = plan.t_plan.isoformat()
    token_seed = seed_token_plan(case_id=case_id, provider="microsoft", expired=True)
    alias = microsoft_primary_alias_seed(case_id=case_id)
    settings = fixture_settings()

    # Default JoinedTLS must remain the CoveringHTTP transport_factory.
    sig = inspect.signature(CoveringHTTP.__init__)
    transport_default = sig.parameters["transport_factory"].default
    if transport_default is not JoinedTLS:
        raise SuiteStop("production CoveringHTTP default is not JoinedTLS")

    graph_route = microsoft_graph_route()
    token_route = microsoft_token_route()
    if (
        token_route.dial_address != graph_route.dial_address
        or token_route.dial_port != graph_route.dial_port
        or token_route.ca_path != graph_route.ca_path
    ):
        raise SuiteStop("MS token route must share graph CA/address/port")
    _require_production_ms_token_path(
        settings=settings,
        token_hostname=token_route.server_hostname,
        token_path=MS_TOKEN_ENDPOINT_PATH,
    )

    planted = inverted_subscription_ids(case_token=plan.attempt_token)
    factory = _open_native_setup_factory(settings=settings)
    schema_receipt = provision_disposable_schema(factory)
    setup = factory.open_setup_session()
    try:
        seed = seed_browser_owner_with_subscriptions(
            setup,
            settings=settings,
            username_prefix="np-ms-refresh",
            subscription_count=2,
            provider="microsoft",
            expired=True,
            mark_covering_fresh_at_seed=False,
            planted_subscription_ids=planted,
            t_plan=plan.t_plan,
            plant_microsoft_primary_alias=True,
        )
        setup.commit()
    finally:
        factory.close(setup)

    assert seed.request_window_start is not None and seed.request_window_end is not None
    assert seed.t_plan is not None
    assert_plan_still_valid(seed.t_plan)
    if seed.token_expired is not True:
        raise SuiteStop("refresh vertical requires an expired seeded account")
    if len(seed.account_ids) != 1 or len(seed.subscription_ids) != 2:
        raise SuiteStop("refresh vertical requires two subscriptions on one account")
    account_id = seed.account_ids[0]
    if MS_LEGACY_PRIMARY_ALIAS not in seed.calendar_ids:
        raise SuiteStop("enabled MS primary alias not planted on subscription row")

    wire_calendar_ids = derive_production_target_calendar_order(
        subscription_ids=list(seed.subscription_ids),
        subscription_calendar_map=dict(seed.subscription_calendar_map),
        primary_alias=MS_LEGACY_PRIMARY_ALIAS,
        identity_default_calendar_id=IDENTITY_DEFAULT_MS_CALENDAR_ID,
    )
    identity_list_ids = identity_list_calendar_ids_for_vertical()
    if identity_list_ids != (IDENTITY_DEFAULT_MS_CALENDAR_ID, STABLE_UNRELATED_MS_CALENDAR_ID):
        raise SuiteStop("identity list must be (cal-ms-default default, cal-np-other)")
    if wire_calendar_ids != (IDENTITY_DEFAULT_MS_CALENDAR_ID, STABLE_UNRELATED_MS_CALENDAR_ID):
        raise SuiteStop(f"wire calendar order mismatch:{wire_calendar_ids!r}")
    before_external = dict(seed.subscription_calendar_map)
    lower_sorted = sorted(seed.subscription_ids, key=str)[0]
    if before_external.get(str(lower_sorted)) != MS_LEGACY_PRIMARY_ALIAS:
        raise SuiteStop("primary alias must sit on LOWER str-sorted subscription id")
    inventory_scripts = ms_refresh_connection_inventory(
        identity_list_calendar_ids=identity_list_ids,
        wire_calendar_ids=wire_calendar_ids,
    )
    if len(inventory_scripts) != MS_REFRESH_EXCHANGE_COUNT:
        raise SuiteStop("refresh inventory must contain exactly five exchanges")
    # One synthetic peer serves both vendor hostnames (leaf SAN covers both; same
    # numeric loopback dial). Runtime validation of this shared-peer assumption is
    # only by an authorized native run.
    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}",
        route=graph_route,
        connection_scripts=inventory_scripts,
        material=PeerMaterial(),
    )
    observations: dict[str, Any] = {}
    native_terminals: list[dict[str, Any]] = []
    client_inventory: list[dict[str, Any]] = []
    oauth_requests = 0
    held_transport: list[Any] = []
    captured_contexts: list[Any] = []
    real_request = None
    transport = None
    retirement_done = False
    retirement_attempted = False
    primary_failure: BaseException | None = None

    try:
        assert_plan_still_valid(plan.t_plan)

        # BEFORE: fresh native setup sessions; measured persisted rows.
        measure_db = factory.open_setup_session()
        try:
            credential_before = measure_account_credential_state(
                measure_db,
                settings=settings,
                account_id=account_id,
                reference_instant=plan.t_plan,
            )
            coverage_before = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)
        if credential_before["expiry_at_or_before_reference"] is not True:
            raise SuiteStop("before-state credential expiry is not at/before plan time")
        if (
            credential_before["seed_access_match"] is not True
            or credential_before["seed_refresh_match"] is not True
        ):
            raise SuiteStop("before-state credential does not hold declared seed values")
        if (
            credential_before["refreshed_access_match"] is not False
            or credential_before["rotated_refresh_match"] is not False
        ):
            raise SuiteStop("before-state credential already holds refreshed values")
        if coverage_before["any_covering_success"] is True:
            raise SuiteStop("before-state already covering-success; vertical not distinguishable")

        peer.start_background(seconds=PEER_SECONDS_DEFAULT)

        database_profile = _fixture_database_profile()
        runtime_pins = _runtime_pins_from_config()
        provider_routes = _ms_refresh_provider_routes(
            graph_hostname=graph_route.server_hostname,
            token_hostname=token_route.server_hostname,
            dial_address=graph_route.dial_address,
            dial_port=graph_route.dial_port,
            ca_file=graph_route.ca_path,
            token_path=MS_TOKEN_ENDPOINT_PATH,
        )
        release_plan = CoveringReleasePlan(
            database_profile=database_profile,
            password_supplier=lambda: "",
            runtime_pins=runtime_pins,
            provider_routes=provider_routes,
            settings=settings,
        )
        if type(release_plan) is CoveringReleaseBinding:
            raise SuiteStop("must install CoveringReleasePlan, not prebuilt binding")

        def on_context(context: Any) -> None:
            captured_contexts.append(context)

        real_init = CoveringHTTP.__init__
        _install_token_terminal_observer(native_terminals)

        def capturing_init(self, *args, **kwargs):
            nonlocal real_request, transport
            real_init(self, *args, **kwargs)
            held_transport.append(self)
            transport = self
            if self.transport_factory is not JoinedTLS:
                raise SuiteStop("transport_factory injection refused — require default JoinedTLS")
            underlying = self.request

            def counted_request(method, url, *, purpose, **kwargs):
                nonlocal oauth_requests
                if purpose == "oauth":
                    oauth_requests += 1
                client_inventory.append(
                    {
                        "method": method,
                        "purpose": purpose,
                        "url_host_present": True,
                        "connection_close_expected": True,
                    }
                )
                return underlying(method, url, purpose=purpose, **kwargs)

            real_request = underlying
            self.request = counted_request  # type: ignore[method-assign]

        CoveringHTTP.__init__ = capturing_init  # type: ignore[method-assign]
        try:
            app = build_i01_asgi_app(
                session_secret=settings.session_secret,
                clock=monotonic,
                on_context=on_context,
            )
            install_binding(app, release_plan)
            client = asgi_client(app)

            body = covering_refresh_body(
                list(seed.subscription_ids),
                window_start=seed.request_window_start,
                window_end=seed.request_window_end,
                horizon_label="np-ms-refresh-horizon-v1",
            )
            assert_plan_still_valid(seed.t_plan)
            response = client.post(
                COVERING_PATH,
                content=json.dumps(body).encode("utf-8"),
                headers={"content-type": "application/json"},
                cookies={"session": seed.cookie},
            )
        finally:
            CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]
            try:
                if transport is not None and real_request is not None:
                    transport.request = real_request
            except Exception:
                pass

        assert_plan_still_valid(seed.t_plan)
        if not captured_contexts:
            raise SuiteStop("ingress on_context did not capture actual request context")
        ingress_budget = getattr(captured_contexts[0], "budget", None)
        if ingress_budget is None:
            raise SuiteStop("captured ingress context missing budget")
        if len(held_transport) != 1 or type(held_transport[0]) is not CoveringHTTP:
            raise SuiteStop("worker/POST did not construct exactly one CoveringHTTP")
        if transport is None:
            transport = held_transport[0]
        from app.services.covering_request_budget import CoveringRequestBudget

        counter = getattr(transport, "counter", None)
        if counter is None:
            raise SuiteStop("CoveringHTTP.counter missing after for_request")
        remaining_cb = getattr(counter, "remaining", None)
        if remaining_cb is None:
            raise SuiteStop("ProviderCounter.remaining missing")
        if getattr(transport, "budget", None) is not None:
            raise SuiteStop("do not invent transport.budget as proof")
        if getattr(counter, "budget", None) is not None:
            raise SuiteStop("do not invent counter.budget as proof")
        if getattr(remaining_cb, "__self__", None) is not ingress_budget:
            raise SuiteStop("counter.remaining.__self__ is not the captured ingress context.budget")
        if getattr(remaining_cb, "__func__", None) is not CoveringRequestBudget.work_remaining:
            raise SuiteStop("counter.remaining.__func__ is not CoveringRequestBudget.work_remaining")

        if response.status_code != 200:
            raise SuiteStop(f"covering-refresh status:{response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SuiteStop("covering-refresh response is not a typed object")
        # Actual public CoveringRefreshResponse schema.
        overall_outcome = payload.get("overall_outcome")
        if overall_outcome != "success":
            raise SuiteStop(f"overall_outcome is not success:{overall_outcome!r}")
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != 2:
            raise SuiteStop("results must list exactly the two requested subscriptions")
        result_ids = set()
        for row in results:
            if not isinstance(row, dict):
                raise SuiteStop("results[] row is not a typed object")
            if row.get("status") != "ok" or row.get("phase") != "import":
                raise SuiteStop("every results[] row must be phase=import status=ok")
            result_ids.add(str(row.get("subscription_id")))
        if result_ids != {str(item) for item in seed.subscription_ids}:
            raise SuiteStop("results[] subscription ids do not match the requested pair")
        if "coverage_action" not in payload or "scheduling_readiness" not in payload:
            raise SuiteStop("covering-refresh missing coverage_action/scheduling_readiness")
        coverage_action = payload["coverage_action"]
        readiness = payload["scheduling_readiness"]
        if not isinstance(coverage_action, dict) or not isinstance(readiness, dict):
            raise SuiteStop("coverage_action/scheduling_readiness must be objects")
        freshness_requested = coverage_action.get("freshness_requested")
        if not isinstance(freshness_requested, dict):
            raise SuiteStop("coverage_action.freshness_requested missing typed object")
        freshness_ok = freshness_requested.get("ok")
        all_ok = coverage_action.get("all_requested_covering_ok")
        scheduling_ready = readiness.get("scheduling_ready")
        scheduling_revision = readiness.get("scheduling_revision")
        freshness_all = readiness.get("freshness_all_enabled")
        if freshness_ok is not True:
            raise SuiteStop("freshness_requested.ok is not True")
        if all_ok is not True:
            raise SuiteStop("all_requested_covering_ok is not True")
        if scheduling_ready is not True:
            raise SuiteStop("scheduling_readiness.scheduling_ready is not True")
        if type(scheduling_revision) is not int or scheduling_revision < 1:
            raise SuiteStop("scheduling_revision not typed int>=1")
        if not isinstance(freshness_all, dict) or freshness_all.get("ok") is not True:
            raise SuiteStop("freshness_all_enabled.ok is not True")
        if readiness.get("assessment_error") is not None:
            raise SuiteStop("final ASSESSMENT reported an assessment_error")
        for banned in ("command", "provider", "mode", "seed_hash", "assessment"):
            if banned in payload:
                raise SuiteStop(f"public covering-refresh must not carry private key:{banned}")

        # AFTER: fresh native setup session; semantic credential proof + coverage.
        t_final_check = datetime.now(timezone.utc)
        measure_db = factory.open_setup_session()
        try:
            credential_after = measure_account_credential_state(
                measure_db,
                settings=settings,
                account_id=account_id,
                reference_instant=t_final_check,
            )
            coverage_after = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)
        if (
            credential_after["refreshed_access_match"] is not True
            or credential_after["rotated_refresh_match"] is not True
        ):
            raise SuiteStop("persisted credential does not equal the declared refreshed values")
        if (
            credential_after["seed_access_match"] is not False
            or credential_after["seed_refresh_match"] is not False
        ):
            raise SuiteStop("persisted credential still equals the seed values")
        if credential_after["expiry_after_reference_plus_skew"] is not True:
            raise SuiteStop("persisted expiry not advanced beyond final check + 30s")
        if coverage_after["all_covering_success"] is not True:
            raise SuiteStop("after-state missing covering success")

        # Native TOKEN terminals: exactly COMMIT (first target) then ROLLBACK (second).
        token_terminals = _actual_token_terminals(native_terminals)
        terminal_sequence = [
            {"terminal": row.get("terminal"), "commit_requested": row.get("commit_requested")}
            for row in token_terminals
        ]
        if terminal_sequence != [
            {"terminal": RootOutcome.COMMIT_ACKNOWLEDGED.name, "commit_requested": True},
            {"terminal": RootOutcome.ROLLBACK_ACKNOWLEDGED.name, "commit_requested": False},
        ]:
            raise SuiteStop(f"TOKEN terminal sequence mismatch:{terminal_sequence!r}")

        # One OAuth request, first; exactly five client requests in production order.
        if oauth_requests != 1:
            raise SuiteStop(f"refresh path must perform exactly one OAuth exchange:{oauth_requests}")
        client_purposes = [(row.get("method"), row.get("purpose")) for row in client_inventory]
        if client_purposes != [
            ("POST", "oauth"),
            ("GET", "identity"),
            ("GET", "identity"),
            ("GET", "event"),
            ("GET", "event"),
        ]:
            raise SuiteStop(f"client request order mismatch:{client_purposes!r}")

        # Retirement barrier BEFORE final peer evidence (Dex 6ED9B65F; same contract as
        # Dex BB93F31E R1/R2): exactly one attempt, marked before the call; joined and no
        # worker error required; the final sanitized state is read only after the bounded join.
        retirement_attempted = True
        retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)
        retirement_done = True
        served = int(peer_state.get("connection_count_served") or 0)
        admitted = int(peer_state.get("connection_count_admitted") or 0)
        if served != admitted or served != len(inventory_scripts):
            raise SuiteStop(f"peer exchange inventory mismatch served={served} admitted={admitted}")
        peer_exchanges = list(peer_state.get("exchange_inventory") or [])
        if len(peer_exchanges) != MS_REFRESH_EXCHANGE_COUNT:
            raise SuiteStop("peer exchange inventory is not exactly five")
        first = peer_exchanges[0] if peer_exchanges else {}
        if first.get("method") != "POST" or first.get("path") != MS_TOKEN_ENDPOINT_PATH:
            raise SuiteStop("first peer exchange is not POST at the production token path")
        if any(row.get("method") != "GET" for row in peer_exchanges[1:]):
            raise SuiteStop("only the first peer exchange may be the OAuth POST")

        after_external = dict(coverage_after.get("external_calendar_ids") or {})
        if after_external.get(str(lower_sorted)) == MS_LEGACY_PRIMARY_ALIAS:
            raise SuiteStop("primary alias remained after requested-row rewrite")
        if MS_LEGACY_PRIMARY_ALIAS in after_external.values():
            raise SuiteStop("enabled primary alias remains after first rewrite")

        # Oracles are emitted only after every measured check above has passed.
        observations = {
            "owning_ms_refresh_joinedtls": "OBSERVED",
            "token_commit": "OBSERVED",
            "persistence": "OBSERVED",
            "covering_path": COVERING_PATH,
            "settings_module": "app.config.Settings",
            "joined_tls_default": True,
            "byte_transport_alias_used": False,
            "release_plan_installed": True,
            "ms_oauth_endpoint_path": MS_TOKEN_ENDPOINT_PATH,
            "primary_alias_planted": MS_LEGACY_PRIMARY_ALIAS,
            "primary_alias_on_lower_sorted_id": True,
            "wire_calendar_order": list(wire_calendar_ids),
            "schema_provisioned": schema_receipt,
            "provider_pki_caller": "admit_provider_pki_generated_once",
            "provider_pki_status": (
                "GENERATED" if _PROVIDER_PKI_GENERATE_ONCE_DONE else "PREPARED_NOT_GENERATED"
            ),
        }
        measured = {
            "credential_state_before": credential_before,
            "credential_state_after": credential_after,
            "coverage_before": coverage_before,
            "coverage_after": coverage_after,
            "public_response": {
                "overall_outcome": overall_outcome,
                "results": [
                    {
                        "subscription_id": str(row.get("subscription_id")),
                        "phase": row.get("phase"),
                        "status": row.get("status"),
                    }
                    for row in results
                ],
                "coverage_action": {
                    "all_requested_covering_ok": all_ok,
                    "freshness_requested_ok": freshness_ok,
                },
                "scheduling_readiness": {
                    "scheduling_ready": scheduling_ready,
                    "scheduling_revision": scheduling_revision,
                    "freshness_all_enabled_ok": freshness_all.get("ok"),
                    "assessment_error": readiness.get("assessment_error"),
                },
            },
            "oauth_request_count": oauth_requests,
            "token_terminal_sequence": terminal_sequence,
            "client_exchange_inventory": list(client_inventory),
            "alias_hash": alias.seed_hash,
            "label_hash": token_seed.label_hash,
            "ingress_budget_same_as_provider": True,
            "budget_proof": "counter.remaining.__self__/__func__",
            "wire_calendar_order": list(wire_calendar_ids),
            "alias_rewrite": {
                "before_external_calendar_ids": before_external,
                "after_external_calendar_ids": after_external,
                "lower_sorted_subscription_id": str(lower_sorted),
                "primary_alias_before": MS_LEGACY_PRIMARY_ALIAS,
                "canonical_default_after": IDENTITY_DEFAULT_MS_CALENDAR_ID,
                "unrelated_stable": STABLE_UNRELATED_MS_CALENDAR_ID,
                "identity_list_ids": list(identity_list_ids),
            },
        }
        _ = sanitized_alias_receipt(alias)
        check_oracles_immediate(
            decl,
            {"owning_ms_refresh_joinedtls": "OBSERVED", "token_commit": "OBSERVED", "persistence": "OBSERVED"},
        )
        t_check_iso = _iso_now()
        assert_plan_still_valid(plan.t_plan)
        unexpected = [
            t
            for t in threading.enumerate()
            if t is not threading.main_thread() and t.name.startswith("np-peer-")
        ]
        if unexpected:
            raise SuiteStop("unjoined np-peer worker after retirement")

        return case_result_receipt(
            case_id=case_id,
            passed=True,
            workers_joined=True,
            expected_unknown=False,
            executed=True,
            prep_is_not_pass=True,
            observations=observations,
            t_plan_iso=t_plan_iso,
            t_check_iso=t_check_iso,
            measured=measured,
            peer_exchange_inventory=peer_exchanges,
            resource_disposition={
                "peer_retired": True,
                "peer_joined": True,
                "factory_closed": True,
                "provider_pki_status": (
                    "GENERATED"
                    if _PROVIDER_PKI_GENERATE_ONCE_DONE
                    else ("PREPARED_NOT_GENERATED" if _PROVIDER_PKI_PREPARED else "NOT_PREPARED")
                ),
                "provider_pki_generated": _PROVIDER_PKI_GENERATE_ONCE_DONE is True,
            },
        )
    except PlanValidityExpired:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except PeerRetirementUnknown:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise SuiteStop("owned peer retirement UNKNOWN")
    except CaseBodyHold:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except SuiteStop:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except BaseException as exc:
        primary_failure = exc
        raise SuiteStop(f"framework_stop:{case_id}:{type(exc).__name__}") from exc
    finally:
        try:
            if transport is not None and real_request is not None:
                transport.request = real_request
        except Exception:
            pass
        if (
            not retirement_attempted
            and peer._worker is not None
            and not peer.life.joined
        ):  # noqa: SLF001
            retirement_attempted = True
            try:
                peer.retire_owned(join_seconds=5.0)
                retirement_done = True
            except PeerRetirementUnknown:
                if primary_failure is None:
                    raise SuiteStop("owned peer retirement UNKNOWN on cleanup")
                raise SuiteStop(
                    f"owned peer retirement UNKNOWN after primary:{type(primary_failure).__name__}"
                ) from primary_failure


def _retire_selected_peer_then_observe(peer: Any, *, join_seconds: float = 5.0) -> tuple[dict[str, Any], dict[str, Any]]:
    """Selected-case retirement barrier, then final peer evidence (Dex BB93F31E R1/R2).

    Exactly one call to the unchanged retire_owned with the existing bounded join; the
    caller marks retirement_attempted BEFORE calling, so a raise never causes a second
    attempt. PeerRetirementUnknown and any other exception propagate unchanged.
    Success requires joined is True AND worker_error_kind is None; otherwise STOP.
    The final sanitized_state (exchange inventory) is read only after the join.
    """
    from np_suite import SuiteStop

    retirement = peer.retire_owned(join_seconds=join_seconds)
    if retirement.get("joined") is not True:
        raise SuiteStop("selected peer worker unjoined — UNKNOWN")
    if retirement.get("worker_error_kind") is not None:
        raise SuiteStop("selected peer worker recorded an error")
    return retirement, peer.sanitized_state()


# NP-V-MS-INVALID exact expectations (source-derived; see CASE_IMPLEMENTATION_NOTES).
MS_INVALID_CLIENT_OUTCOME = (
    "exception",
    "CoveringReauthorizationRequired",
    "app.services.covering_transport_policy",
)
MS_INVALID_TOKEN_TERMINAL_ROWS = [
    {"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True, "commit_requested": False},
]
MS_INVALID_TERMINAL_OBSERVER_ROWS = [
    {"observer": "CoveringORMConnection.token_terminal", "terminal": None},
]
MS_INVALID_PREFLIGHT_CODE = "CALENDAR_ACCOUNT_DISCONNECTED"
MS_INVALID_ACTION_SUMMARY = {
    "requested": 1,
    "preflight_rejected": 1,
    "import_attempted": 0,
    "import_ok": 0,
    "import_failed": 0,
}
MS_INVALID_CREDENTIAL_SEMANTIC_KEYS = (
    "seed_access_match",
    "seed_refresh_match",
    "refreshed_access_match",
    "rotated_refresh_match",
    "expiry",
)


def _run_np_v_ms_invalid() -> dict[str, Any]:
    """NP-V-MS-INVALID (T06-INVALID-GRANT-MICROSOFT): separate single-case batch.

    Chain: covering-refresh ASGI ingress → CoveringReleasePlan.for_request →
    ProviderCounter → CoveringHTTP (default JoinedTLS) → owning expired Microsoft
    refresh (exactly one OAuth POST at the production-derived tenant path) → complete
    status-400 invalid_grant object → CoveringReauthorizationRequired → token port
    TokenRejected(CALENDAR_ACCOUNT_DISCONNECTED) with one native TOKEN ROLLBACK →
    preflight-rejected row, IMPORT (run_target) never entered → final ASSESSMENT.
    Observers call the originals, preserve return/exception identity and are all
    restored in finally. No transport injection, clock freezing, reseed or retry.
    """
    import inspect

    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_auth_seed import (
        assert_plan_still_valid,
        covering_refresh_body,
        fixture_settings,
        fresh_attempt_plan,
        measure_account_credential_state,
        measure_subscription_coverage_state,
        PlanValidityExpired,
        seed_browser_owner_with_subscriptions,
        seed_token_plan,
    )
    from np_receipts import case_result_receipt
    from np_provider_routes import microsoft_graph_route, microsoft_token_route
    from np_provider_transcript import (
        MS_INVALID_GRANT_EXCHANGE_COUNT,
        MS_TOKEN_ENDPOINT_PATH,
        ms_invalid_grant_connection_inventory,
    )
    from np_provider_peer import (
        SyntheticProviderPeer,
        PeerMaterial,
        PeerRetirementUnknown,
        _http_response_bytes,
    )
    from i01_asgi_app import asgi_client, build_i01_asgi_app, install_binding
    from app.services.covering_release_plan import CoveringReleasePlan
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_http_dispatch import CoveringReleaseBinding
    from app.services.covering_native_orm_factory import CoveringORMConnection
    from app.services.covering_role_connector import CoveringRoleConnector

    case_id = "NP-V-MS-INVALID"
    decl = registry_by_id(include_cf=True)[case_id]
    plan = fresh_attempt_plan(case_id)
    t_plan_iso = plan.t_plan.isoformat()
    token_seed = seed_token_plan(case_id=case_id, provider="microsoft", expired=True)
    settings = fixture_settings()

    sig = inspect.signature(CoveringHTTP.__init__)
    if sig.parameters["transport_factory"].default is not JoinedTLS:
        raise SuiteStop("production CoveringHTTP default is not JoinedTLS")

    graph_route = microsoft_graph_route()
    token_route = microsoft_token_route()
    if (
        token_route.dial_address != graph_route.dial_address
        or token_route.dial_port != graph_route.dial_port
        or token_route.ca_path != graph_route.ca_path
    ):
        raise SuiteStop("MS token route must share graph CA/address/port")
    _require_production_ms_token_path(
        settings=settings,
        token_hostname=token_route.server_hostname,
        token_path=MS_TOKEN_ENDPOINT_PATH,
    )

    factory = _open_native_setup_factory(settings=settings)
    schema_receipt = provision_disposable_schema(factory)
    setup = factory.open_setup_session()
    try:
        seed = seed_browser_owner_with_subscriptions(
            setup,
            settings=settings,
            username_prefix="np-ms-invalid",
            subscription_count=1,
            provider="microsoft",
            expired=True,
            mark_covering_fresh_at_seed=False,
            t_plan=plan.t_plan,
        )
        setup.commit()
    finally:
        factory.close(setup)

    if seed.request_window_start is None or seed.request_window_end is None or seed.t_plan is None:
        raise SuiteStop("invalid_grant seed missing request window or plan instant")
    assert_plan_still_valid(seed.t_plan)
    if seed.token_expired is not True:
        raise SuiteStop("invalid_grant vertical requires an expired seeded account")
    if len(seed.account_ids) != 1 or len(seed.subscription_ids) != 1:
        raise SuiteStop("invalid_grant vertical requires exactly one subscription on one account")
    account_id = seed.account_ids[0]
    subscription_id = seed.subscription_ids[0]
    inventory_scripts = ms_invalid_grant_connection_inventory()
    if len(inventory_scripts) != MS_INVALID_GRANT_EXCHANGE_COUNT:
        raise SuiteStop("invalid_grant inventory must contain exactly one exchange")
    token_sends = [s for s in inventory_scripts[0].steps if s.direction == "send_response"]
    token_requests = [s for s in inventory_scripts[0].steps if s.direction == "recv_request"]
    token_closes = [s for s in inventory_scripts[0].steps if s.direction == "close"]
    if (
        len(token_sends) != 1
        or len(token_requests) != 1
        or len(token_closes) != 1
        or token_requests[0].method != "POST"
        or token_requests[0].path != MS_TOKEN_ENDPOINT_PATH
        or token_sends[0].status != 400
        or token_closes[0].close_mode != "orderly_close_notify"
    ):
        raise SuiteStop("invalid_grant script is not one tenant-path POST / 400 / orderly close")
    expected_wire = _http_response_bytes(token_sends[0])
    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}",
        route=graph_route,
        connection_scripts=inventory_scripts,
        material=PeerMaterial(),
    )
    native_terminals: list[dict[str, Any]] = []
    client_inventory: list[dict[str, Any]] = []
    client_outcomes: list[tuple[str, str, str]] = []
    run_target_calls: list[int] = []
    oauth_requests = 0
    held_transport: list[Any] = []
    captured_contexts: list[Any] = []
    real_request = None
    transport = None
    real_init = CoveringHTTP.__init__
    real_terminal = CoveringORMConnection.token_terminal
    real_run_target = CoveringRoleConnector.run_target
    retirement_attempted = False
    primary_failure: BaseException | None = None

    try:
        assert_plan_still_valid(plan.t_plan)

        # BEFORE: fresh native setup session; measured persisted rows.
        measure_db = factory.open_setup_session()
        try:
            credential_before = measure_account_credential_state(
                measure_db,
                settings=settings,
                account_id=account_id,
                reference_instant=plan.t_plan,
            )
            coverage_before = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)
        if credential_before["expiry_at_or_before_reference"] is not True:
            raise SuiteStop("before-state credential expiry is not at/before plan time")
        if (
            credential_before["seed_access_match"] is not True
            or credential_before["seed_refresh_match"] is not True
            or credential_before["refreshed_access_match"] is not False
            or credential_before["rotated_refresh_match"] is not False
        ):
            raise SuiteStop("before-state credential does not hold exactly the declared seed values")
        if coverage_before["any_covering_success"] is True:
            raise SuiteStop("before-state already covering-success; vertical not distinguishable")

        peer.start_background(seconds=PEER_SECONDS_DEFAULT)

        provider_routes = _ms_refresh_provider_routes(
            graph_hostname=graph_route.server_hostname,
            token_hostname=token_route.server_hostname,
            dial_address=graph_route.dial_address,
            dial_port=graph_route.dial_port,
            ca_file=graph_route.ca_path,
            token_path=MS_TOKEN_ENDPOINT_PATH,
        )
        release_plan = CoveringReleasePlan(
            database_profile=_fixture_database_profile(),
            password_supplier=lambda: "",
            runtime_pins=_runtime_pins_from_config(),
            provider_routes=provider_routes,
            settings=settings,
        )
        if type(release_plan) is CoveringReleaseBinding:
            raise SuiteStop("must install CoveringReleasePlan, not prebuilt binding")

        def on_context(context: Any) -> None:
            captured_contexts.append(context)

        _install_token_terminal_observer(native_terminals)

        def counted_run_target(self, *args, **kwargs):
            run_target_calls.append(1)
            return real_run_target(self, *args, **kwargs)

        CoveringRoleConnector.run_target = counted_run_target  # type: ignore[method-assign]

        def capturing_init(self, *args, **kwargs):
            nonlocal real_request, transport
            real_init(self, *args, **kwargs)
            held_transport.append(self)
            transport = self
            if self.transport_factory is not JoinedTLS:
                raise SuiteStop("transport_factory injection refused — require default JoinedTLS")
            underlying = self.request

            def counted_request(method, url, *, purpose, **kwargs):
                nonlocal oauth_requests
                if purpose == "oauth":
                    oauth_requests += 1
                client_inventory.append({"method": method, "purpose": purpose})
                try:
                    result = underlying(method, url, purpose=purpose, **kwargs)
                except BaseException as exc:
                    client_outcomes.append(
                        ("exception", type(exc).__name__, type(exc).__module__)
                    )
                    raise
                client_outcomes.append(("response", type(result).__name__, type(result).__module__))
                return result

            real_request = underlying
            self.request = counted_request  # type: ignore[method-assign]

        CoveringHTTP.__init__ = capturing_init  # type: ignore[method-assign]
        try:
            app = build_i01_asgi_app(
                session_secret=settings.session_secret,
                clock=monotonic,
                on_context=on_context,
            )
            install_binding(app, release_plan)
            client = asgi_client(app)
            body = covering_refresh_body(
                [subscription_id],
                window_start=seed.request_window_start,
                window_end=seed.request_window_end,
                horizon_label="np-ms-invalid-horizon-v1",
            )
            assert_plan_still_valid(seed.t_plan)
            response = client.post(
                COVERING_PATH,
                content=json.dumps(body).encode("utf-8"),
                headers={"content-type": "application/json"},
                cookies={"session": seed.cookie},
            )
        finally:
            CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]
            CoveringORMConnection.token_terminal = real_terminal  # type: ignore[method-assign]
            CoveringRoleConnector.run_target = real_run_target  # type: ignore[method-assign]
            try:
                if transport is not None and real_request is not None:
                    transport.request = real_request
            except Exception:
                pass

        assert_plan_still_valid(seed.t_plan)
        if not captured_contexts:
            raise SuiteStop("ingress on_context did not capture actual request context")
        ingress_budget = getattr(captured_contexts[0], "budget", None)
        if ingress_budget is None:
            raise SuiteStop("captured ingress context missing budget")
        if len(held_transport) != 1 or type(held_transport[0]) is not CoveringHTTP:
            raise SuiteStop("worker/POST did not construct exactly one CoveringHTTP")
        from app.services.covering_request_budget import CoveringRequestBudget

        remaining_cb = getattr(getattr(held_transport[0], "counter", None), "remaining", None)
        if remaining_cb is None:
            raise SuiteStop("ProviderCounter.remaining missing")
        if getattr(remaining_cb, "__self__", None) is not ingress_budget:
            raise SuiteStop("counter.remaining.__self__ is not the captured ingress context.budget")
        if getattr(remaining_cb, "__func__", None) is not CoveringRequestBudget.work_remaining:
            raise SuiteStop("counter.remaining.__func__ is not CoveringRequestBudget.work_remaining")

        # Typed client rejection: exactly one OAuth request; its outcome is exactly the
        # transport's CoveringReauthorizationRequired (complete 400 invalid_grant object).
        if oauth_requests != 1 or client_inventory != [{"method": "POST", "purpose": "oauth"}]:
            raise SuiteStop(f"invalid_grant path must perform exactly one OAuth POST:{client_inventory!r}")
        if client_outcomes != [MS_INVALID_CLIENT_OUTCOME]:
            raise SuiteStop(f"OAuth client outcome is not typed reauthorization:{client_outcomes!r}")

        # Native TOKEN terminal: exactly one ROLLBACK acknowledgement; observer marker kept apart.
        token_terminals = _actual_token_terminals(native_terminals)
        observer_rows = [row for row in native_terminals if "observer" in row]
        if token_terminals != MS_INVALID_TOKEN_TERMINAL_ROWS:
            raise SuiteStop(f"TOKEN terminal rows mismatch:{token_terminals!r}")
        if observer_rows != MS_INVALID_TERMINAL_OBSERVER_ROWS:
            raise SuiteStop("token terminal observer marker missing or duplicated")

        # IMPORT never entered for the preflight-rejected target.
        if run_target_calls:
            raise SuiteStop(f"IMPORT run_target entered:{len(run_target_calls)}")

        # Actual public CoveringRefreshResponse contract (covering_refresh/_dispatch source).
        if response.status_code != 200:
            raise SuiteStop(f"covering-refresh status:{response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SuiteStop("covering-refresh response is not a typed object")
        overall_outcome = payload.get("overall_outcome")
        if overall_outcome != "no_op":
            raise SuiteStop(f"overall_outcome is not no_op:{overall_outcome!r}")
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
            raise SuiteStop("results must list exactly the one requested subscription")
        row = results[0]
        if (
            str(row.get("subscription_id")) != str(subscription_id)
            or row.get("phase") != "preflight"
            or row.get("status") != "preflight_rejected"
            or row.get("preflight_code") != MS_INVALID_PREFLIGHT_CODE
            or row.get("preflight_effects") != []
            or row.get("cause") is not None
            or row.get("upserted") != 0
        ):
            raise SuiteStop("result row is not the preflight-rejected CALENDAR_ACCOUNT_DISCONNECTED row")
        summary = payload.get("action_summary")
        if not isinstance(summary, dict) or any(
            summary.get(key) != value for key, value in MS_INVALID_ACTION_SUMMARY.items()
        ):
            raise SuiteStop("action_summary is not requested1/preflight_rejected1/import 0")
        coverage_action = payload.get("coverage_action")
        readiness = payload.get("scheduling_readiness")
        if not isinstance(coverage_action, dict) or not isinstance(readiness, dict):
            raise SuiteStop("coverage_action/scheduling_readiness must be objects")
        for banned in ("command", "provider", "mode", "seed_hash", "assessment"):
            if banned in payload:
                raise SuiteStop(f"public covering-refresh must not carry private key:{banned}")

        # AFTER: separate fresh native session; semantic credentials, expiry, coverage unchanged.
        t_final_check = datetime.now(timezone.utc)
        measure_db = factory.open_setup_session()
        try:
            credential_after = measure_account_credential_state(
                measure_db,
                settings=settings,
                account_id=account_id,
                reference_instant=t_final_check,
            )
            coverage_after = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)
        if any(
            credential_after[key] != credential_before[key]
            for key in MS_INVALID_CREDENTIAL_SEMANTIC_KEYS
        ):
            raise SuiteStop("persisted credential semantics or expiry changed after invalid_grant")
        if coverage_after != coverage_before:
            raise SuiteStop("subscription coverage state changed after invalid_grant")

        # Retirement barrier BEFORE final peer evidence (Dex BB93F31E R1/R2): exactly one
        # attempt, marked before the call; joined and no worker error required; the final
        # sanitized state is read only after the bounded join.
        retirement_attempted = True
        retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)
        # Completed peer-side stimulus (stimulus only; client claims are above).
        peer_exchanges = list(peer_state.get("exchange_inventory") or [])
        if (
            int(peer_state.get("connection_count_admitted") or 0) != MS_INVALID_GRANT_EXCHANGE_COUNT
            or int(peer_state.get("connection_count_served") or 0) != MS_INVALID_GRANT_EXCHANGE_COUNT
            or len(peer_exchanges) != MS_INVALID_GRANT_EXCHANGE_COUNT
            or peer_exchanges[0].get("method") != "POST"
            or peer_exchanges[0].get("path") != MS_TOKEN_ENDPOINT_PATH
            or peer_state.get("request_received") is not True
            or peer_state.get("response_sent") is not True
            or peer_state.get("close_mode_observed") != "orderly_close_notify"
            or peer_state.get("bytes_sent") != len(expected_wire)
        ):
            raise SuiteStop("peer exchange inventory is not one completed tenant-path POST/400")

        observations = {
            "token_rejected_after_unchanged_unit_rollback": "OBSERVED",
        }
        measured = {
            "credential_state_before": credential_before,
            "credential_state_after": credential_after,
            "coverage_before": coverage_before,
            "coverage_after": coverage_after,
            "public_response": {
                "overall_outcome": overall_outcome,
                "result_row": {
                    "subscription_id": str(row.get("subscription_id")),
                    "phase": row.get("phase"),
                    "status": row.get("status"),
                    "preflight_code": row.get("preflight_code"),
                },
                "action_summary": {key: summary.get(key) for key in MS_INVALID_ACTION_SUMMARY},
                "recorded_only": {
                    "all_requested_covering_ok": coverage_action.get("all_requested_covering_ok"),
                    "scheduling_ready": readiness.get("scheduling_ready"),
                    "assessment_error": readiness.get("assessment_error"),
                },
            },
            "oauth_request_count": oauth_requests,
            "client_outcomes": [list(item) for item in client_outcomes],
            "token_terminal_rows": token_terminals,
            "run_target_calls": len(run_target_calls),
            "peer_side_wire_bytes_sent_exact": True,
            "label_hash": token_seed.label_hash,
            "schema_provisioned": schema_receipt,
            "ingress_budget_same_as_provider": True,
            "joined_tls_default": True,
            "ms_oauth_endpoint_path": MS_TOKEN_ENDPOINT_PATH,
        }
        check_oracles_immediate(decl, observations)
        t_check_iso = _iso_now()
        assert_plan_still_valid(plan.t_plan)
        if any(
            t is not threading.main_thread() and t.name.startswith("np-peer-")
            for t in threading.enumerate()
        ):
            raise SuiteStop("unjoined np-peer worker after retirement")

        return case_result_receipt(
            case_id=case_id,
            passed=True,
            workers_joined=True,
            expected_unknown=False,
            executed=True,
            prep_is_not_pass=True,
            observations=observations,
            t_plan_iso=t_plan_iso,
            t_check_iso=t_check_iso,
            measured=measured,
            peer_exchange_inventory=peer_exchanges,
            resource_disposition={
                "peer_retired": True,
                "peer_joined": True,
                "factory_closed": True,
                "observers_restored": True,
                "provider_pki_status": (
                    "GENERATED"
                    if _PROVIDER_PKI_GENERATE_ONCE_DONE
                    else ("PREPARED_NOT_GENERATED" if _PROVIDER_PKI_PREPARED else "NOT_PREPARED")
                ),
                "provider_pki_generated": _PROVIDER_PKI_GENERATE_ONCE_DONE is True,
            },
        )
    except PlanValidityExpired:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except PeerRetirementUnknown:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise SuiteStop("owned peer retirement UNKNOWN")
    except CaseBodyHold:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except SuiteStop:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except BaseException as exc:
        primary_failure = exc
        raise SuiteStop(f"framework_stop:{case_id}:{type(exc).__name__}") from exc
    finally:
        CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]
        CoveringORMConnection.token_terminal = real_terminal  # type: ignore[method-assign]
        CoveringRoleConnector.run_target = real_run_target  # type: ignore[method-assign]
        try:
            if transport is not None and real_request is not None:
                transport.request = real_request
        except Exception:
            pass
        if (
            not retirement_attempted
            and peer._worker is not None
            and not peer.life.joined
        ):  # noqa: SLF001
            retirement_attempted = True
            try:
                peer.retire_owned(join_seconds=5.0)
            except PeerRetirementUnknown:
                if primary_failure is None:
                    raise SuiteStop("owned peer retirement UNKNOWN on cleanup")
                raise SuiteStop(
                    f"owned peer retirement UNKNOWN after primary:{type(primary_failure).__name__}"
                ) from primary_failure


def _open_native_setup_factory(*, settings: Any) -> Any:
    """Open disposable setup factory — immutable AssessmentFactory lineage (i01)."""
    from assessment_binding import AssessmentFactory

    del settings  # Settings used by seed path; factory itself is DB profile/pins only.
    profile = _fixture_database_profile()
    pins = _runtime_pins_from_config()
    records: list[tuple[str, dict[str, Any]]] = []

    def record(event: str, data: dict[str, Any]) -> None:
        records.append((event, dict(data)))

    factory = AssessmentFactory(
        profile=profile,
        password_supplier=lambda: "",
        runtime_pins=pins,
        record=record,
    )
    factory._np_records = records  # noqa: SLF001 — fixture-local sanitized event sink
    return factory


def _for_request_capturing_transport(release_plan: Any, budget: Any, held: list[Any]) -> Any:
    """Call CoveringReleasePlan.for_request while capturing the CoveringHTTP instance."""
    from app.services.covering_http_transport import CoveringHTTP

    real_init = CoveringHTTP.__init__

    def capturing_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        held.append(self)

    CoveringHTTP.__init__ = capturing_init  # type: ignore[method-assign]
    try:
        return release_plan.for_request(budget)
    finally:
        CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]


def _install_worker_exception_observer(captured: list[BaseException]) -> Callable[[], None]:
    """Observe the production dispatch worker's run_bounded_domain call boundary.

    Location-only diagnostic aid. Delegates to the original callable with identical
    arguments and returns its identical result. On BaseException it retains at most
    ONE exception object (the first) and re-raises the same object with a bare raise.
    It never formats, prints or serializes the exception, its message or locals.
    Production modules are not edited; only the module global looked up by
    covering_http_dispatch._worker is swapped. The returned callable restores the
    exact original; callers must invoke it unconditionally.
    """
    from app.services import covering_http_dispatch as dispatch_module

    original = dispatch_module.run_bounded_domain

    def observed_run_bounded_domain(*args: Any, **kwargs: Any) -> Any:
        try:
            return original(*args, **kwargs)
        except BaseException as exc:
            if not captured:
                captured.append(exc)
            raise

    def restore() -> None:
        dispatch_module.run_bounded_domain = original

    dispatch_module.run_bounded_domain = observed_run_bounded_domain
    return restore


def _install_token_terminal_observer(native_terminals: list[dict[str, Any]]) -> None:
    """Wrap CoveringORMConnection.token_terminal to capture native TOKEN receipts."""
    from app.services.covering_native_orm_factory import CoveringORMConnection
    from app.services.covering_target_transaction import RootOutcome

    real = CoveringORMConnection.token_terminal

    def wrapped(self, *, commit, remaining):
        outcome = real(self, commit=commit, remaining=remaining)
        label = outcome.name if hasattr(outcome, "name") else str(outcome)
        native_terminals.append(
            {
                "terminal": label,
                "token_rollback_ack": outcome is RootOutcome.ROLLBACK_ACKNOWLEDGED,
                "commit_requested": bool(commit),
            }
        )
        return outcome

    CoveringORMConnection.token_terminal = wrapped  # type: ignore[method-assign]
    native_terminals.append({"observer": "CoveringORMConnection.token_terminal", "terminal": None})


# T05 finite client-outcome classes (exact class name, defining module). Anything
# else fails closed as a STOP; nothing is assumed from host-only fake behavior.
T05_SHORT_CL_REFUSAL_CLASS = ("IncompleteRead", "http.client")
T05_ABRUPT_CLIENT_CLASSES = frozenset({("SSLEOFError", "ssl"), ("ConnectionResetError", "builtins")})
# Finite classification of the exact scripted response wire (never the rebuilt API headers).
T05_SCRIPTED_WIRE_FRAMINGS = ("close_delimited", "exact_content_length", "other")


def _t05_classify_client_outcome(expectation: str, outcome: Any) -> str:
    """Finite T05 classification of one observed native client outcome.

    outcome is ("response", status, body_exact, scripted_wire_framing) or
    ("exception", class_name, class_module), where scripted_wire_framing is one of
    T05_SCRIPTED_WIRE_FRAMINGS. Only the exact expected shape maps to an oracle
    label; every other outcome raises SuiteStop (fail closed).
    """
    from np_suite import SuiteStop

    kind = outcome[0] if isinstance(outcome, tuple) and outcome else None
    if expectation == "complete_accept":
        if kind == "response" and outcome[1:] == (200, True, "close_delimited"):
            return "ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY"
        raise SuiteStop("t05 close-delimited positive not accepted exactly")
    if expectation == "fixed_length_accept":
        if kind == "response" and outcome[1:] == (200, True, "exact_content_length"):
            return "ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY"
        raise SuiteStop("t05 exact fixed-length positive not accepted exactly")
    if expectation == "short_cl_refuse":
        if kind == "exception" and tuple(outcome[1:]) == T05_SHORT_CL_REFUSAL_CLASS:
            return "REFUSED_AFTER_ORDERLY_CLOSE_NOTIFY"
        raise SuiteStop("t05 short-length prefix not refused by framing completeness")
    if expectation == "abrupt_distinct":
        if kind == "exception" and tuple(outcome[1:]) in T05_ABRUPT_CLIENT_CLASSES:
            return "OBSERVED"
        raise SuiteStop("t05 abrupt truncation not classified as transport EOF")
    raise SuiteStop("t05 unknown expectation")


def _t05_scripted_wire_framing(scripted_wire: bytes, expected_body: bytes) -> str:
    """Finite framing class of the exact scripted response wire.

    "close_delimited": no Content-Length and no Transfer-Encoding header line.
    "exact_content_length": exactly one Content-Length line whose ASCII-digit value
    equals len(expected_body), no Transfer-Encoding, and the wire body after the
    header terminator is exactly expected_body. Anything else is "other".
    """
    head, sep, wire_body = scripted_wire.partition(b"\r\n\r\n")
    if not sep:
        return "other"
    lines = head.split(b"\r\n")[1:]
    names = [line.partition(b":")[0].strip().lower() for line in lines]
    if b"transfer-encoding" in names:
        return "other"
    lengths = [
        line.partition(b":")[2].strip()
        for line, name in zip(lines, names)
        if name == b"content-length"
    ]
    if not lengths:
        return "close_delimited"
    if (
        len(lengths) == 1
        and lengths[0].isdigit()
        and int(lengths[0]) == len(expected_body)
        and wire_body == expected_body
    ):
        return "exact_content_length"
    return "other"


def _t05_response_outcome(
    status: int, content: bytes, expected_body: bytes, scripted_wire: bytes
) -> tuple[Any, ...]:
    """Client-observed status/body plus framing class of the exact scripted wire.

    The httpx.Response that CoveringHTTP returns is rebuilt by production code and
    httpx 0.28.1 supplies Content-Length for non-empty bytes content, so its headers
    are NOT the wire headers. Framing is judged on the exact scripted bytes (the
    peer's sent byte count is separately required to equal their length); the
    client side contributes only its status and exact body.
    """
    scripted_wire_framing = _t05_scripted_wire_framing(scripted_wire, expected_body)
    return ("response", status, content == expected_body, scripted_wire_framing)


def _t05_observe(case_id: str, script: Any, expectation: str) -> dict[str, Any]:
    """One finite T05 exchange through the production contracts.

    CoveringRequestBudget -> ProviderCounter(approved_provider_limits(),
    budget.work_remaining) -> CoveringHTTP with its DEFAULT JoinedTLS transport
    (the covering_release_plan.for_request construction), against the synthetic
    peer on numeric loopback :443 with verify-full. The response framing is
    validated before the peer starts; the peer is retired and joined before any
    classification, so an unjoined peer is a STOP whatever the client observed.
    No request/response body, header value, credential or error message is kept.
    """
    from np_suite import SuiteStop
    from np_provider_routes import google_api_route
    from np_provider_peer import (
        PeerLifecycleError,
        PeerMaterial,
        SyntheticProviderPeer,
        _http_response_bytes,
    )
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_request_budget import CoveringRequestBudget
    from app.services.covering_transport_policy import (
        HTTPSPeer,
        ProviderCounter,
        approved_provider_limits,
    )

    sends = [step for step in script.steps if step.direction == "send_response"]
    requests = [step for step in script.steps if step.direction == "recv_request"]
    closes = [step for step in script.steps if step.direction == "close"]
    if len(sends) != 1 or len(requests) != 1 or len(closes) != 1:
        raise SuiteStop("t05 script must be exactly one request, one response, one close")
    try:
        expected_wire = _http_response_bytes(sends[0])
    except PeerLifecycleError:
        raise SuiteStop("t05 response framing configuration refused before send") from None
    route = google_api_route()
    routes = (
        (
            HTTPSPeer(
                hostname=route.server_hostname,
                address=route.dial_address,
                port=route.dial_port,
                ca_file=route.ca_path,
            ),
            "/calendar/v3/calendars/",
            "event",
        ),
    )
    budget = CoveringRequestBudget()
    counter = ProviderCounter(approved_provider_limits(), budget.work_remaining)
    http = CoveringHTTP(counter=counter, routes=routes)
    if http.transport_factory is not JoinedTLS:
        raise SuiteStop("t05 requires the default JoinedTLS transport")
    url = f"https://{route.url_host}{requests[0].path}"
    expected_body = (sends[0].body_template or "").encode("utf-8")
    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}-{script.script_id}",
        route=route,
        script=script,
        material=PeerMaterial(),
    )
    outcome: Any = None
    try:
        peer.start_background(seconds=PEER_SECONDS_DEFAULT)
        try:
            response = http.request("GET", url, purpose="event")
        except Exception as exc:
            outcome = ("exception", type(exc).__name__, type(exc).__module__)
        else:
            # Never read response.headers here: production rebuilds the API object
            # (httpx 0.28.1 adds Content-Length for non-empty bytes content).
            outcome = _t05_response_outcome(
                response.status_code, response.content, expected_body, expected_wire
            )
    finally:
        retirement = peer.retire_owned(join_seconds=5.0)
    if retirement.get("joined") is not True or retirement.get("worker_error_kind") is not None:
        raise SuiteStop("t05 peer worker retirement not clean")
    state = peer.sanitized_state()
    if (
        state["connection_count_admitted"] != 1
        or state["connection_count_served"] != 1
        or state["request_received"] is not True
        or state["response_sent"] is not True
        or state["close_mode_observed"] != closes[0].close_mode
        or state["bytes_sent"] != len(expected_wire)
    ):
        raise SuiteStop("t05 peer exchange inventory mismatch")
    label = _t05_classify_client_outcome(expectation, outcome)
    measured = {
        "script_id": script.script_id,
        "expectation": expectation,
        "client_outcome_kind": outcome[0],
        "client_outcome_class": outcome[1] if outcome[0] == "exception" else None,
        "response_status": outcome[1] if outcome[0] == "response" else None,
        "body_exact": outcome[2] if outcome[0] == "response" else None,
        "scripted_wire_framing": outcome[3] if outcome[0] == "response" else None,
        "peer_side_wire_bytes_sent_exact": True,
        "peer_close_mode": state["close_mode_observed"],
        "default_joined_tls": True,
    }
    return {
        "label": label,
        "measured": measured,
        "inventory": list(state["exchange_inventory"]),
        "retirement": retirement,
    }


def _run_np_t05_orderly_close() -> dict[str, Any]:
    """NP-T05-ORDERLY-CLOSE: three separate observations after orderly close_notify.

    (a) supplementary complete close-delimited response accepted (exact body; the
    scripted wire has no CL/TE);
    (b) complete exact fixed-length response accepted (exact body; the scripted
    wire has one Content-Length equal to the body, no TE);
    (c) valid-JSON prefix shorter than Content-Length refused by the framing
    completeness path (IncompleteRead) before JSON decoding.
    Each observation owns, retires and joins its own peer, sequentially.
    """
    from np_suite import check_oracles_immediate, registry_by_id
    from np_auth_seed import assert_plan_still_valid, fresh_attempt_plan
    from np_provider_transcript import (
        orderly_close_delimited_complete_script,
        orderly_fixed_length_complete_script,
        orderly_short_cl_valid_json_refuse_script,
    )
    from np_receipts import case_result_receipt

    case_id = "NP-T05-ORDERLY-CLOSE"
    decl = registry_by_id(include_cf=True)[case_id]
    plan = fresh_attempt_plan(case_id)
    assert_plan_still_valid(plan.t_plan)
    complete = _t05_observe(case_id, orderly_close_delimited_complete_script(), "complete_accept")
    fixed = _t05_observe(case_id, orderly_fixed_length_complete_script(), "fixed_length_accept")
    short = _t05_observe(case_id, orderly_short_cl_valid_json_refuse_script(), "short_cl_refuse")
    observations = {
        "orderly_close_delimited_complete_accepted": complete["label"],
        "orderly_fixed_length_complete_accepted": fixed["label"],
        "orderly_short_cl_valid_json_prefix_refused": short["label"],
    }
    check_oracles_immediate(decl, observations)
    t_check_iso = _iso_now()
    assert_plan_still_valid(plan.t_plan)
    return case_result_receipt(
        case_id=case_id,
        passed=True,
        workers_joined=True,
        expected_unknown=False,
        observations=observations,
        t_plan_iso=plan.t_plan.isoformat(),
        t_check_iso=t_check_iso,
        measured={
            "close_delimited_complete": complete["measured"],
            "fixed_length_complete": fixed["measured"],
            "short_cl_valid_json": short["measured"],
        },
        peer_exchange_inventory=complete["inventory"] + fixed["inventory"] + short["inventory"],
        resource_disposition={
            "peer_retirements": [complete["retirement"], fixed["retirement"], short["retirement"]]
        },
    )


def _run_np_t05_abrupt_truncation() -> dict[str, Any]:
    """NP-T05-ABRUPT-TRUNCATION: abrupt TLS drop without close_notify mid-body.

    The observed native client outcome must be a transport EOF class (SSLEOFError
    under suppress_ragged_eofs=False, or ConnectionResetError from the peer's
    SO_LINGER-0 close), distinct from framing refusal (IncompleteRead), JSON
    decoding failure and ASGI disconnect. Any other class is a STOP.
    """
    from np_suite import check_oracles_immediate, registry_by_id
    from np_auth_seed import assert_plan_still_valid, fresh_attempt_plan
    from np_provider_transcript import abrupt_truncation_script
    from np_receipts import case_result_receipt

    case_id = "NP-T05-ABRUPT-TRUNCATION"
    decl = registry_by_id(include_cf=True)[case_id]
    plan = fresh_attempt_plan(case_id)
    assert_plan_still_valid(plan.t_plan)
    abrupt = _t05_observe(case_id, abrupt_truncation_script(), "abrupt_distinct")
    observations = {"classified_distinct_from_malformed_and_asgi_disconnect": abrupt["label"]}
    check_oracles_immediate(decl, observations)
    t_check_iso = _iso_now()
    assert_plan_still_valid(plan.t_plan)
    return case_result_receipt(
        case_id=case_id,
        passed=True,
        workers_joined=True,
        expected_unknown=False,
        observations=observations,
        t_plan_iso=plan.t_plan.isoformat(),
        t_check_iso=t_check_iso,
        measured={"abrupt_truncation": abrupt["measured"]},
        peer_exchange_inventory=abrupt["inventory"],
        resource_disposition={"peer_retirements": [abrupt["retirement"]]},
    )


# NP-T04-BODY-STALL (Trish-approved design/preparation decision 4F2F3B3F; Dex F465A4E2).
# Case-specific peer life: admitted 240 s for this case ONLY; every other case keeps
# PEER_SECONDS_DEFAULT (120). Agreement with runner-config is checked before start.
T04_BODY_STALL_PEER_SECONDS = 240
T04_BODY_STALL_PEER_SECONDS_CONFIG_KEY = "t04_body_stall_peer_seconds"
# Production work allowance mirrored for clock-origin derivation only (budget l.23-24:
# request = started + 240, work = started + 210 from one `started` value). Never applied.
T04_BODY_STALL_PRODUCTION_WORK_SECONDS = 210.0
T04_BODY_STALL_DEADLINE_OUTCOME = (
    "exception",
    "CoveringDeadlineExceeded",
    "app.services.covering_request_budget",
)
T04_BODY_STALL_CLIENT_PURPOSES = [("GET", "identity"), ("GET", "identity"), ("GET", "event")]
T04_BODY_STALL_TOKEN_TERMINAL_ROWS = [
    {"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True, "commit_requested": False},
]
T04_BODY_STALL_TERMINAL_OBSERVER_ROWS = [
    {"observer": "CoveringORMConnection.token_terminal", "terminal": None},
]
T04_BODY_STALL_PARENT_TERMINAL_ROWS = [
    {"terminal": "ROLLBACK_ACKNOWLEDGED", "commit_requested": False},
]
T04_BODY_STALL_FAILURE_CAUSE = "covering_provider_read_failed"
T04_BODY_STALL_DEADLINE_CODE = "CALENDAR_REFRESH_DEADLINE_EXCEEDED"
T04_BODY_STALL_ACTION_SUMMARY = {
    "requested": 2,
    "preflight_rejected": 1,
    "import_attempted": 1,
    "import_ok": 0,
    "import_failed": 1,
}
T04_BODY_STALL_KNOWN_REFUSAL = "cleanup_deadline_exceeded"


def _t04_body_stall_peer_seconds_from_config() -> int:
    """Admitted case-specific peer life; must equal the frozen constant exactly."""
    from np_suite import SuiteStop

    data = json.loads((ROOT / RUNNER_CONFIG_NAME).read_text(encoding="utf-8"))
    value = data.get(T04_BODY_STALL_PEER_SECONDS_CONFIG_KEY)
    if type(value) is not int or value != T04_BODY_STALL_PEER_SECONDS:
        raise SuiteStop("t04 body-stall peer seconds disagree with runner-config")
    if T04_BODY_STALL_PEER_SECONDS == PEER_SECONDS_DEFAULT:
        raise SuiteStop("t04 body-stall must not reuse the default peer life")
    return value


def _t04_body_stall_exact_query(window_start: datetime, window_end: datetime) -> str:
    """Exact calendarView wire query for the first event GET, derived from the seed window.

    Fixture derivation (window -> UTC Z strings + $top=100) is cross-checked against the
    UNCHANGED production builder microsoft_calendar_view_list_params (read-only pinned
    call, no network); the wire form uses the same urlencode(..., doseq=True) as
    CoveringHTTP.request. Any disagreement STOPs before the peer starts.
    """
    from urllib.parse import urlencode

    from np_suite import SuiteStop
    from app.services import microsoft_calendar as production_ms
    from app.services.covering_refresh_window import effective_covering_pull_window

    window = effective_covering_pull_window(window_start, window_end)

    def _utc_z(value: datetime) -> str:
        if value.tzinfo is None:
            raise SuiteStop("t04 body-stall window must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    fixture_params = {
        "startDateTime": _utc_z(window.effective_start),
        "endDateTime": _utc_z(window.effective_end),
        "$top": "100",
    }
    production_params = production_ms.microsoft_calendar_view_list_params(
        time_min=window.effective_start, time_max=window.effective_end
    )
    if list(production_params.items()) != list(fixture_params.items()):
        raise SuiteStop("t04 body-stall query derivation disagrees with production builder")
    return urlencode(production_params, doseq=True)


def _install_t04_parent_and_target_observers(
    parent_terminals: list[dict[str, Any]],
    target_runs: list[dict[str, Any]],
) -> Callable[[], None]:
    """Observe PARENT finish_root and CoveringTargetTransaction.run for this POST only.

    Same-return/same-exception wrappers: each delegates to the unchanged production
    method with identical arguments, records finite typed fields, and returns the
    identical object (or re-raises the identical exception with a bare raise).
    Production modules are not edited; the returned callable restores both exactly.
    """
    from app.services.covering_parent_adapter import CoveringParentAdapter
    from app.services.covering_target_transaction import CoveringTargetTransaction

    real_finish_root = CoveringParentAdapter.finish_root
    real_run = CoveringTargetTransaction.run

    def observed_finish_root(self, *, commit):
        try:
            outcome = real_finish_root(self, commit=commit)
        except BaseException as exc:
            parent_terminals.append(
                {"raised": type(exc).__name__, "module": type(exc).__module__, "commit_requested": bool(commit)}
            )
            raise
        parent_terminals.append(
            {
                "terminal": outcome.name if hasattr(outcome, "name") else str(outcome),
                "commit_requested": bool(commit),
            }
        )
        return outcome

    def observed_run(self, **kwargs):
        try:
            returned = real_run(self, **kwargs)
        except BaseException as exc:
            target_runs.append({"raised": type(exc).__name__, "module": type(exc).__module__})
            raise
        result, failure = returned
        target_runs.append(
            {
                "subscription_id": str(result.subscription_id),
                "outcome": result.outcome,
                "cause": result.cause,
                "failure_present": failure is not None,
                "failure_persisted": None if failure is None else bool(failure.persisted),
                "failure_refused": None if failure is None else bool(failure.refused),
                "failure_refuse_reason": None if failure is None else failure.refuse_reason,
                "failure_cause": None if failure is None else failure.cause,
            }
        )
        return returned

    def restore() -> None:
        CoveringParentAdapter.finish_root = real_finish_root  # type: ignore[method-assign]
        CoveringTargetTransaction.run = real_run  # type: ignore[method-assign]

    CoveringParentAdapter.finish_root = observed_finish_root  # type: ignore[method-assign]
    CoveringTargetTransaction.run = observed_run  # type: ignore[method-assign]
    return restore


def _t04_measure_failure_columns(db: Any, *, subscription_ids: list[UUID]) -> dict[str, dict[str, Any]]:
    """Fresh persisted read of the two failure-recorder columns only (no credentials)."""
    from app.models import CalendarSubscription

    out: dict[str, dict[str, Any]] = {}
    for sub_id in subscription_ids:
        sub = db.get(CalendarSubscription, sub_id)
        if sub is None:
            raise RuntimeError("subscription missing for failure-column measurement")
        out[str(sub_id)] = {
            "failure_recorded": sub.coverage_last_failure_at is not None,
            "failure_cause": sub.coverage_last_failure_cause,
        }
    return out


def _t04_finite_instant(name: str, value: Any) -> float:
    import math

    from np_suite import SuiteStop

    if type(value) is not float or not math.isfinite(value):
        raise SuiteStop(f"t04 body-stall instant missing or non-finite:{name}")
    return value


def _t04_body_stall_timing(
    *,
    peer_state: dict[str, Any],
    work_deadline: Any,
    request_deadline: Any,
    client_exception_at: Any,
    response_at: Any,
    retire_called_at: Any,
) -> dict[str, Any]:
    """Finite same-process monotonic predicate (decision 4F2F3B3F); no epsilon.

    P0<B0; W=B0+210<P_dl=P0+240; S_in<W; W<=X_t<T_resp<T_ret<S_out<P_dl; exit retired.
    B0 is derived as W-210 (one `started` value sets both budget deadlines).
    """
    from np_suite import SuiteStop

    p0 = _t04_finite_instant("peer_started_at", peer_state.get("peer_started_at"))
    p_dl = _t04_finite_instant("peer_deadline_at", peer_state.get("peer_deadline_at"))
    s_in = _t04_finite_instant("stall_entered_at", peer_state.get("stall_entered_at"))
    s_out = _t04_finite_instant("stall_exit_at", peer_state.get("stall_exit_at"))
    w = _t04_finite_instant("work_deadline", work_deadline)
    r = _t04_finite_instant("request_deadline", request_deadline)
    x_t = _t04_finite_instant("client_exception_at", client_exception_at)
    t_resp = _t04_finite_instant("response_at", response_at)
    t_ret = _t04_finite_instant("retire_called_at", retire_called_at)
    b0 = w - T04_BODY_STALL_PRODUCTION_WORK_SECONDS
    reason = peer_state.get("stall_exit_reason")
    if reason != "retired":
        raise SuiteStop(f"t04 body-stall exit reason not retired:{reason!r}")
    if not p0 < b0:
        raise SuiteStop("t04 timing: peer did not start before the budget")
    if not w < p_dl:
        raise SuiteStop("t04 timing: peer deadline not after work deadline")
    if not s_in < w:
        raise SuiteStop("t04 timing: stall not entered before work deadline")
    if not w <= x_t:
        raise SuiteStop("t04 timing: client exception before work deadline")
    if not x_t < t_resp < t_ret < s_out < p_dl:
        raise SuiteStop("t04 timing: post-deadline order violated")
    return {
        "clock": "time.monotonic same process",
        "peer_started_at": p0,
        "peer_deadline_at": p_dl,
        "budget_started_at_derived": b0,
        "work_deadline": w,
        "request_deadline": r,
        "stall_entered_at": s_in,
        "client_exception_at": x_t,
        "response_at": t_resp,
        "retire_called_at": t_ret,
        "stall_exit_at": s_out,
        "stall_exit_reason": reason,
        "client_exception_after_work_deadline_seconds": x_t - w,
        "predicate": "P0<B0;W<P_dl;S_in<W;W<=X_t<T_resp<T_ret<S_out<P_dl;retired",
    }


def _run_np_t04_body_stall() -> dict[str, Any]:
    """NP-T04-BODY-STALL: production deadline during the first event body read.

    NONEXPIRED two-target lineage through actual covering-refresh ASGI ingress ->
    CoveringReleasePlan -> ProviderCounter -> CoveringHTTP (default JoinedTLS) with the
    real monotonic clock and unchanged production 210 work / 240 request / 30 cleanup
    clocks. Peer: two normal identity exchanges, then calendarView(cal-ms-default) with
    the exact seed-derived query: valid headers with positive Content-Length, body
    withheld. Expected: original client CoveringDeadlineExceeded; HTTP 200 failed with
    target 1 import/failed/covering_provider_read_failed and target 2 preflight
    CALENDAR_REFRESH_DEADLINE_EXCEEDED; no assessment; one TOKEN rollback (target 1);
    acknowledged PARENT rollback; recorder persisted or known cleanup refusal.
    """
    import inspect

    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_auth_seed import (
        IDENTITY_DEFAULT_MS_CALENDAR_ID,
        STABLE_UNRELATED_MS_CALENDAR_ID,
        assert_plan_still_valid,
        covering_refresh_body,
        derive_production_target_calendar_order,
        fixture_settings,
        fresh_attempt_plan,
        identity_list_calendar_ids_for_vertical,
        inverted_subscription_ids,
        measure_account_credential_state,
        measure_subscription_coverage_state,
        PlanValidityExpired,
        seed_browser_owner_with_subscriptions,
        seed_token_plan,
    )
    from np_alias_seed import microsoft_primary_alias_seed, sanitized_alias_receipt
    from np_receipts import case_result_receipt
    from np_provider_routes import microsoft_graph_route
    from np_provider_transcript import (
        T04_BODY_STALL_EXCHANGE_COUNT,
        ms_body_stall_connection_inventory,
    )
    from np_provider_peer import (
        HEADER_TERMINATOR,
        SyntheticProviderPeer,
        PeerMaterial,
        PeerRetirementUnknown,
        _http_response_bytes,
    )
    from i01_asgi_app import asgi_client, build_i01_asgi_app, install_binding
    from app.services.covering_release_plan import CoveringReleasePlan
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_http_dispatch import CoveringReleaseBinding
    from app.services.covering_refresh_import import EFFECT_CANONICALIZE_IDENTITY
    from app.services.calendar_alias_canonicalize import MS_LEGACY_PRIMARY_ALIAS

    case_id = "NP-T04-BODY-STALL"
    decl = registry_by_id(include_cf=True)[case_id]
    peer_seconds = _t04_body_stall_peer_seconds_from_config()
    plan = fresh_attempt_plan(case_id)
    t_plan_iso = plan.t_plan.isoformat()
    token_seed = seed_token_plan(case_id=case_id, provider="microsoft", expired=False)
    alias = microsoft_primary_alias_seed(case_id=case_id)
    settings = fixture_settings()

    sig = inspect.signature(CoveringHTTP.__init__)
    if sig.parameters["transport_factory"].default is not JoinedTLS:
        raise SuiteStop("production CoveringHTTP default is not JoinedTLS")

    route = microsoft_graph_route()
    planted = inverted_subscription_ids(case_token=plan.attempt_token)
    factory = _open_native_setup_factory(settings=settings)
    schema_receipt = provision_disposable_schema(factory)
    setup = factory.open_setup_session()
    try:
        seed = seed_browser_owner_with_subscriptions(
            setup,
            settings=settings,
            username_prefix="np-t04-body-stall",
            subscription_count=2,
            provider="microsoft",
            expired=False,
            mark_covering_fresh_at_seed=False,
            planted_subscription_ids=planted,
            t_plan=plan.t_plan,
            plant_microsoft_primary_alias=True,
        )
        setup.commit()
    finally:
        factory.close(setup)

    assert seed.request_window_start is not None and seed.request_window_end is not None
    assert seed.t_plan is not None
    assert_plan_still_valid(seed.t_plan)
    if len(seed.account_ids) != 1 or len(seed.subscription_ids) != 2:
        raise SuiteStop("body-stall requires exactly one MS account with two subscriptions")
    account_id = seed.account_ids[0]
    if MS_LEGACY_PRIMARY_ALIAS not in seed.calendar_ids:
        raise SuiteStop("enabled MS primary alias not planted on subscription row")
    wire_calendar_ids = derive_production_target_calendar_order(
        subscription_ids=list(seed.subscription_ids),
        subscription_calendar_map=dict(seed.subscription_calendar_map),
        primary_alias=MS_LEGACY_PRIMARY_ALIAS,
        identity_default_calendar_id=IDENTITY_DEFAULT_MS_CALENDAR_ID,
    )
    identity_list_ids = identity_list_calendar_ids_for_vertical()
    if tuple(identity_list_ids) != (IDENTITY_DEFAULT_MS_CALENDAR_ID, STABLE_UNRELATED_MS_CALENDAR_ID):
        raise SuiteStop("identity list must be (cal-ms-default, cal-np-other)")
    if tuple(wire_calendar_ids) != (IDENTITY_DEFAULT_MS_CALENDAR_ID, STABLE_UNRELATED_MS_CALENDAR_ID):
        raise SuiteStop(f"wire calendar order mismatch:{wire_calendar_ids!r}")
    before_external = dict(seed.subscription_calendar_map)
    lower_sorted = sorted(seed.subscription_ids, key=str)[0]
    higher_sorted = sorted(seed.subscription_ids, key=str)[1]
    if before_external.get(str(lower_sorted)) != MS_LEGACY_PRIMARY_ALIAS:
        raise SuiteStop("primary alias must sit on LOWER str-sorted subscription id")

    exact_query = _t04_body_stall_exact_query(seed.request_window_start, seed.request_window_end)
    inventory_scripts = ms_body_stall_connection_inventory(
        identity_list_calendar_ids=identity_list_ids,
        stall_calendar_id=wire_calendar_ids[0],
        exact_query=exact_query,
    )
    if len(inventory_scripts) != T04_BODY_STALL_EXCHANGE_COUNT:
        raise SuiteStop("body-stall inventory is not exactly three exchanges")
    # Exact peer-side wire bytes: complete responses for exchanges 0-1, head only for 2.
    full_sends = [
        _http_response_bytes(step)
        for script in inventory_scripts[:2]
        for step in script.steps
        if step.direction == "send_response"
    ]
    stall_sends = [step for step in inventory_scripts[2].steps if step.direction == "send_response"]
    if len(full_sends) != 2 or len(stall_sends) != 1:
        raise SuiteStop("body-stall scripts must declare exactly one response each")
    stall_head, stall_sep, _withheld = _http_response_bytes(stall_sends[0]).partition(HEADER_TERMINATOR)
    if not stall_sep or b"Content-Length: 12\r\n" not in stall_head + stall_sep:
        raise SuiteStop("body-stall head must declare the positive Content-Length")
    expected_bytes_sent = sum(len(item) for item in full_sends) + len(stall_head + stall_sep)

    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}",
        route=route,
        connection_scripts=inventory_scripts,
        material=PeerMaterial(),
    )
    native_terminals: list[dict[str, Any]] = []
    parent_terminals: list[dict[str, Any]] = []
    target_runs: list[dict[str, Any]] = []
    client_inventory: list[dict[str, Any]] = []
    client_outcomes: list[tuple[str, str, str]] = []
    client_outcome_times: list[float] = []
    oauth_requests = 0
    held_transport: list[Any] = []
    captured_contexts: list[Any] = []
    worker_exceptions: list[BaseException] = []
    restore_worker_observer: Callable[[], None] | None = None
    restore_target_observers: Callable[[], None] | None = None
    real_request = None
    transport = None
    response_at: float | None = None
    retirement_done = False
    retirement_attempted = False
    primary_failure: BaseException | None = None

    try:
        assert_plan_still_valid(plan.t_plan)
        measure_db = factory.open_setup_session()
        try:
            credential_before = measure_account_credential_state(
                measure_db, settings=settings, account_id=account_id, reference_instant=plan.t_plan
            )
            coverage_before = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
            failure_before = _t04_measure_failure_columns(
                measure_db, subscription_ids=list(seed.subscription_ids)
            )
        finally:
            factory.close(measure_db)
        if (
            credential_before["seed_access_match"] is not True
            or credential_before["seed_refresh_match"] is not True
            or credential_before["refreshed_access_match"] is not False
            or credential_before["rotated_refresh_match"] is not False
        ):
            raise SuiteStop("before-state credential does not hold exactly the declared seed values")
        if coverage_before["any_covering_success"] is not False:
            raise SuiteStop("before-state already covering-success; fresh seed required")
        if any(row["failure_recorded"] or row["failure_cause"] is not None for row in failure_before.values()):
            raise SuiteStop("before-state already carries a failure record; fresh seed required")

        peer.start_background(seconds=peer_seconds)

        release_plan = CoveringReleasePlan(
            database_profile=_fixture_database_profile(),
            password_supplier=lambda: "",
            runtime_pins=_runtime_pins_from_config(),
            provider_routes=_ms_provider_routes(
                peer_hostname=route.server_hostname,
                dial_address=route.dial_address,
                dial_port=route.dial_port,
                ca_file=route.ca_path,
            ),
            settings=settings,
        )
        if type(release_plan) is CoveringReleaseBinding:
            raise SuiteStop("must install CoveringReleasePlan, not prebuilt binding")

        def on_context(context: Any) -> None:
            captured_contexts.append(context)

        real_init = CoveringHTTP.__init__
        _install_token_terminal_observer(native_terminals)

        def capturing_init(self, *args, **kwargs):
            nonlocal real_request, transport
            real_init(self, *args, **kwargs)
            held_transport.append(self)
            transport = self
            if self.transport_factory is not JoinedTLS:
                raise SuiteStop("transport_factory injection refused — require default JoinedTLS")
            underlying = self.request

            def counted_request(method, url, *, purpose, **kwargs):
                nonlocal oauth_requests
                if purpose == "oauth":
                    oauth_requests += 1
                client_inventory.append({"method": method, "purpose": purpose})
                try:
                    result = underlying(method, url, purpose=purpose, **kwargs)
                except BaseException as exc:
                    # Original client outcome BEFORE any caller conversion; same object re-raised.
                    client_outcome_times.append(monotonic())
                    client_outcomes.append(("exception", type(exc).__name__, type(exc).__module__))
                    raise
                client_outcome_times.append(monotonic())
                client_outcomes.append(("response", type(result).__name__, type(result).__module__))
                return result

            real_request = underlying
            self.request = counted_request  # type: ignore[method-assign]

        CoveringHTTP.__init__ = capturing_init  # type: ignore[method-assign]
        try:
            restore_worker_observer = _install_worker_exception_observer(worker_exceptions)
            restore_target_observers = _install_t04_parent_and_target_observers(parent_terminals, target_runs)
            # Real monotonic clock — build_i01_asgi_app's ControllableClock(0.0) default is unsuitable.
            app = build_i01_asgi_app(
                session_secret=settings.session_secret,
                clock=monotonic,
                on_context=on_context,
            )
            install_binding(app, release_plan)
            client = asgi_client(app)
            body = covering_refresh_body(
                list(seed.subscription_ids),
                window_start=seed.request_window_start,
                window_end=seed.request_window_end,
                horizon_label="np-t04-body-stall-horizon-v1",
            )
            assert_plan_still_valid(seed.t_plan)
            response = client.post(
                COVERING_PATH,
                content=json.dumps(body).encode("utf-8"),
                headers={"content-type": "application/json"},
                cookies={"session": seed.cookie},
            )
            response_at = monotonic()
        finally:
            if restore_target_observers is not None:
                restore_target_observers()
                restore_target_observers = None
            if restore_worker_observer is not None:
                restore_worker_observer()
                restore_worker_observer = None
            CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]
            try:
                if transport is not None and real_request is not None:
                    transport.request = real_request
            except Exception:
                pass

        if not captured_contexts:
            raise SuiteStop("ingress on_context did not capture actual request context")
        ingress_budget = getattr(captured_contexts[0], "budget", None)
        if ingress_budget is None:
            raise SuiteStop("captured ingress context missing budget")
        if len(held_transport) != 1 or type(held_transport[0]) is not CoveringHTTP:
            raise SuiteStop("worker/POST did not construct exactly one CoveringHTTP")
        if transport is None:
            transport = held_transport[0]
        from app.services.covering_request_budget import CoveringRequestBudget

        counter = getattr(transport, "counter", None)
        remaining_cb = getattr(counter, "remaining", None) if counter is not None else None
        if remaining_cb is None:
            raise SuiteStop("ProviderCounter.remaining missing")
        if getattr(remaining_cb, "__self__", None) is not ingress_budget:
            raise SuiteStop("counter.remaining.__self__ is not the captured ingress context.budget")
        if getattr(remaining_cb, "__func__", None) is not CoveringRequestBudget.work_remaining:
            raise SuiteStop("counter.remaining.__func__ is not CoveringRequestBudget.work_remaining")
        # Read-only private deadlines (budget l.23-24); never modified.
        work_deadline = getattr(ingress_budget, "_work_deadline", None)
        request_deadline = getattr(ingress_budget, "_request_deadline", None)

        # Original client outcomes and inventory.
        if oauth_requests != 0:
            raise SuiteStop("body-stall path must not perform OAuth")
        purposes = [(row.get("method"), row.get("purpose")) for row in client_inventory]
        if purposes != T04_BODY_STALL_CLIENT_PURPOSES:
            raise SuiteStop(f"client request order mismatch:{purposes!r}")
        if [item[0] for item in client_outcomes[:2]] != ["response", "response"]:
            raise SuiteStop("identity exchanges did not both return a response")
        if len(client_outcomes) != 3 or client_outcomes[2] != T04_BODY_STALL_DEADLINE_OUTCOME:
            raise SuiteStop(f"event client outcome is not the production deadline:{client_outcomes!r}")
        if len(client_outcome_times) != 3:
            raise SuiteStop("client outcome instants missing")

        # Public response (exact two-target inventory).
        if response.status_code != 200:
            raise SuiteStop(f"covering-refresh status:{response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SuiteStop("covering-refresh response is not a typed object")
        if payload.get("overall_outcome") != "failed":
            raise SuiteStop(f"overall_outcome is not failed:{payload.get('overall_outcome')!r}")
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != 2:
            raise SuiteStop("results must list exactly the two requested subscriptions")
        by_id = {str(row.get("subscription_id")): row for row in results if isinstance(row, dict)}
        first = by_id.get(str(lower_sorted)) or {}
        second = by_id.get(str(higher_sorted)) or {}
        if (
            first.get("phase") != "import"
            or first.get("status") != "failed"
            or first.get("cause") != T04_BODY_STALL_FAILURE_CAUSE
            or first.get("upserted") != 0
            or first.get("preflight_code") is not None
            or list(first.get("preflight_effects") or []) != [EFFECT_CANONICALIZE_IDENTITY]
        ):
            raise SuiteStop("target 1 row is not import/failed/covering_provider_read_failed")
        if (
            second.get("phase") != "preflight"
            or second.get("status") != "preflight_rejected"
            or second.get("preflight_code") != T04_BODY_STALL_DEADLINE_CODE
            or second.get("cause") is not None
            or list(second.get("preflight_effects") or []) != []
        ):
            raise SuiteStop("target 2 row is not the static deadline preflight refusal")
        summary = payload.get("action_summary") or {}
        if {key: summary.get(key) for key in T04_BODY_STALL_ACTION_SUMMARY} != T04_BODY_STALL_ACTION_SUMMARY:
            raise SuiteStop("action_summary is not requested2/preflight1/attempted1/ok0/failed1")
        coverage_action = payload.get("coverage_action")
        readiness = payload.get("scheduling_readiness")
        if not isinstance(coverage_action, dict) or not isinstance(readiness, dict):
            raise SuiteStop("coverage_action/scheduling_readiness must be objects")
        if coverage_action.get("all_requested_covering_ok") is not False:
            raise SuiteStop("coverage_action must be fail-closed")
        if readiness.get("assessment_error") != T04_BODY_STALL_DEADLINE_CODE:
            raise SuiteStop("assessment must be skipped with the deadline readiness code")
        if payload.get("scheduling_revision_at_end") is not None or payload.get("scheduling_revision_bumped") is not False:
            raise SuiteStop("no assessment revision may be reported")
        for banned in ("command", "provider", "mode", "seed_hash", "assessment"):
            if banned in payload:
                raise SuiteStop(f"public covering-refresh must not carry private key:{banned}")

        # Native terminals, target transaction and recorder disposition.
        token_terminals = _actual_token_terminals(native_terminals)
        observer_rows = [row for row in native_terminals if "observer" in row]
        if token_terminals != T04_BODY_STALL_TOKEN_TERMINAL_ROWS:
            raise SuiteStop(f"TOKEN terminal rows mismatch:{token_terminals!r}")
        if observer_rows != T04_BODY_STALL_TERMINAL_OBSERVER_ROWS:
            raise SuiteStop("token terminal observer marker missing or duplicated")
        if parent_terminals != T04_BODY_STALL_PARENT_TERMINAL_ROWS:
            raise SuiteStop(f"PARENT terminal rows mismatch:{parent_terminals!r}")
        if len(target_runs) != 1 or "raised" in target_runs[0]:
            raise SuiteStop(f"exactly one classified target transaction required:{target_runs!r}")
        run_row = target_runs[0]
        if (
            run_row["subscription_id"] != str(lower_sorted)
            or run_row["outcome"] != "failed"
            or run_row["cause"] != T04_BODY_STALL_FAILURE_CAUSE
            or run_row["failure_present"] is not True
        ):
            raise SuiteStop("target transaction is not the failed target-1 import")
        persisted = run_row["failure_persisted"] is True and run_row["failure_refused"] is False
        known_refusal = (
            run_row["failure_persisted"] is False
            and run_row["failure_refused"] is True
            and run_row["failure_refuse_reason"] == T04_BODY_STALL_KNOWN_REFUSAL
        )
        if run_row["failure_cause"] != T04_BODY_STALL_FAILURE_CAUSE or persisted == known_refusal:
            raise SuiteStop("failure recorder disposition is neither persisted nor known cleanup refusal")
        failure_disposition = "PERSISTED" if persisted else "CLEANUP_ADMISSION_REFUSED"

        # Persisted after-state from separate sessions.
        measure_db = factory.open_setup_session()
        try:
            credential_after = measure_account_credential_state(
                measure_db, settings=settings, account_id=account_id, reference_instant=plan.t_plan
            )
            coverage_after = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
            failure_after = _t04_measure_failure_columns(
                measure_db, subscription_ids=list(seed.subscription_ids)
            )
        finally:
            factory.close(measure_db)
        if any(credential_after[key] != credential_before[key] for key in MS_INVALID_CREDENTIAL_SEMANTIC_KEYS):
            raise SuiteStop("persisted credential semantics or expiry changed")
        if coverage_after != coverage_before:
            raise SuiteStop("coverage state changed (rollback must leave both subscriptions unchanged)")
        expected_failure_after = {
            str(lower_sorted): (
                {"failure_recorded": True, "failure_cause": T04_BODY_STALL_FAILURE_CAUSE}
                if persisted
                else {"failure_recorded": False, "failure_cause": None}
            ),
            str(higher_sorted): {"failure_recorded": False, "failure_cause": None},
        }
        if failure_after != expected_failure_after:
            raise SuiteStop("persisted failure columns disagree with recorder disposition")

        # Retirement barrier BEFORE final peer evidence: one attempt, marked first.
        assert_plan_still_valid(plan.t_plan)
        retirement_attempted = True
        retire_called_at = monotonic()
        retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)
        retirement_done = True
        peer_exchanges = list(peer_state.get("exchange_inventory") or [])
        if (
            int(peer_state.get("connection_count_admitted") or 0) != T04_BODY_STALL_EXCHANGE_COUNT
            or int(peer_state.get("connection_count_served") or 0) != T04_BODY_STALL_EXCHANGE_COUNT
            or len(peer_exchanges) != T04_BODY_STALL_EXCHANGE_COUNT
            or [row.get("method") for row in peer_exchanges] != ["GET", "GET", "GET"]
            or peer_exchanges[2].get("query_verified") is not True
            or peer_exchanges[2].get("close_mode_observed") != "stall_body"
            or peer_state.get("response_sent") is not True
            or peer_state.get("bytes_sent") != expected_bytes_sent
        ):
            raise SuiteStop("peer inventory is not two identity exchanges plus one exact body stall")
        timing = _t04_body_stall_timing(
            peer_state=peer_state,
            work_deadline=work_deadline,
            request_deadline=request_deadline,
            client_exception_at=client_outcome_times[2],
            response_at=response_at,
            retire_called_at=retire_called_at,
        )
        if any(
            t is not threading.main_thread() and t.name.startswith("np-peer-")
            for t in threading.enumerate()
        ):
            raise SuiteStop("unjoined np-peer worker after retirement")

        observations = {"first_guard_body_phase_deadline": "OBSERVED"}
        check_oracles_immediate(decl, observations)
        t_check_iso = _iso_now()
        _ = sanitized_alias_receipt(alias)
        measured = {
            "client_outcomes": [list(item) for item in client_outcomes],
            "client_exchange_inventory": list(client_inventory),
            "oauth_request_count": oauth_requests,
            "public_response": {
                "status": 200,
                "overall_outcome": "failed",
                "target_rows": [
                    {key: first.get(key) for key in ("subscription_id", "phase", "status", "preflight_code", "cause", "upserted", "preflight_effects")},
                    {key: second.get(key) for key in ("subscription_id", "phase", "status", "preflight_code", "cause", "upserted", "preflight_effects")},
                ],
                "action_summary": dict(T04_BODY_STALL_ACTION_SUMMARY),
                "assessment_skipped_code": readiness.get("assessment_error"),
            },
            # Allowlisted typed key (np_receipts) — do not repeat the dropped
            # token_terminal_rows mistake.
            "token_terminal_sequence": token_terminals,
            "parent_terminal_sequence": list(parent_terminals),
            "target_transaction": dict(run_row),
            "failure_disposition": failure_disposition,
            "failure_columns_after": failure_after,
            "credential_state_before": credential_before,
            "credential_state_after": credential_after,
            "coverage_before": coverage_before,
            "coverage_after": coverage_after,
            "timing": timing,
            "peer_seconds_admitted": peer_seconds,
            "exact_query_bytes": len(exact_query.encode("ascii")),
            "peer_side_wire_bytes_sent_exact": True,
            "ingress_budget_same_as_provider": True,
            "joined_tls_default": True,
            "label_hash": token_seed.label_hash,
            "alias_hash": alias.seed_hash,
            "schema_provisioned": schema_receipt,
        }
        return case_result_receipt(
            case_id=case_id,
            passed=True,
            workers_joined=True,
            expected_unknown=False,
            executed=True,
            prep_is_not_pass=True,
            observations=observations,
            t_plan_iso=t_plan_iso,
            t_check_iso=t_check_iso,
            measured=measured,
            peer_exchange_inventory=peer_exchanges,
            resource_disposition={
                "peer_retired": True,
                "peer_joined": True,
                "peer_stall_exit_reason": timing["stall_exit_reason"],
                "factory_closed": True,
                "observers_restored": True,
                "provider_pki_status": (
                    "GENERATED"
                    if _PROVIDER_PKI_GENERATE_ONCE_DONE
                    else ("PREPARED_NOT_GENERATED" if _PROVIDER_PKI_PREPARED else "NOT_PREPARED")
                ),
                "provider_pki_generated": _PROVIDER_PKI_GENERATE_ONCE_DONE is True,
            },
        )
    except PlanValidityExpired:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except PeerRetirementUnknown:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise SuiteStop("owned peer retirement UNKNOWN")
    except CaseBodyHold:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except SuiteStop:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except BaseException as exc:
        primary_failure = exc
        raise SuiteStop(f"framework_stop:{case_id}:{type(exc).__name__}") from exc
    finally:
        try:
            if transport is not None and real_request is not None:
                transport.request = real_request
        except Exception:
            pass
        if (
            not retirement_attempted
            and peer._worker is not None
            and not peer.life.joined
        ):  # noqa: SLF001
            retirement_attempted = True
            try:
                peer.retire_owned(join_seconds=5.0)
                retirement_done = True
            except PeerRetirementUnknown:
                if primary_failure is None:
                    raise SuiteStop("owned peer retirement UNKNOWN on cleanup")
                raise SuiteStop(
                    f"owned peer retirement UNKNOWN after primary:{type(primary_failure).__name__}"
                ) from primary_failure


def _make_implemented_case(case_id: str) -> Callable[[], dict[str, Any]]:
    if case_id == "NP-V-MS-NONEXPIRED":
        def _run() -> dict[str, Any]:
            return _run_np_v_ms_nonexpired()

        _run.__name__ = f"run_{case_id}"
        return _run
    if case_id == "NP-V-MS-REFRESH":
        def _run_refresh() -> dict[str, Any]:
            return _run_np_v_ms_refresh()

        _run_refresh.__name__ = f"run_{case_id}"
        return _run_refresh
    if case_id == "NP-V-MS-INVALID":
        def _run_invalid() -> dict[str, Any]:
            return _run_np_v_ms_invalid()

        _run_invalid.__name__ = f"run_{case_id}"
        return _run_invalid
    if case_id == "NP-T05-ORDERLY-CLOSE":
        def _run_t05_orderly() -> dict[str, Any]:
            return _run_np_t05_orderly_close()

        _run_t05_orderly.__name__ = f"run_{case_id}"
        return _run_t05_orderly
    if case_id == "NP-T05-ABRUPT-TRUNCATION":
        def _run_t05_abrupt() -> dict[str, Any]:
            return _run_np_t05_abrupt_truncation()

        _run_t05_abrupt.__name__ = f"run_{case_id}"
        return _run_t05_abrupt
    if case_id == "NP-T04-BODY-STALL":
        def _run_t04_body_stall() -> dict[str, Any]:
            return _run_np_t04_body_stall()

        _run_t04_body_stall.__name__ = f"run_{case_id}"
        return _run_t04_body_stall
    raise CaseBodyHold(case_id, "no implemented body mapper")


def _make_hold_case(case_id: str, decl: Any) -> Callable[[], dict[str, Any]]:
    reason = _hold_reason(case_id)

    def _run() -> dict[str, Any]:
        raise CaseBodyHold(case_id, reason)

    _run.__name__ = f"hold_{case_id}"
    _run.decl = decl  # type: ignore[attr-defined]
    _run.hold_reason = reason  # type: ignore[attr-defined]
    _run.implementation_status = "HOLD"  # type: ignore[attr-defined]
    return _run


def build_registry_from_suite(case_ids: list[str]) -> dict[str, Callable[[], dict[str, Any]]]:
    """Bind finite declared cases to callables.

    Implemented cases get production/native bodies. Incomplete cases get explicit
    CaseBodyHold callables — never silent omission, never fabricated PASS.
    """
    from np_suite import registry_by_id

    decls = registry_by_id(include_cf=True)
    if set(case_ids) - set(decls):
        raise RunnerEntryHeld("case_ids not in finite suite registry")

    registry: dict[str, Callable[[], dict[str, Any]]] = {}
    for case_id in case_ids:
        decl = decls[case_id]
        if case_id in IMPLEMENTED_CASE_IDS:
            fn = _make_implemented_case(case_id)
            fn.decl = decl  # type: ignore[attr-defined]
            fn.implementation_status = "IMPLEMENTED"  # type: ignore[attr-defined]
            registry[case_id] = fn
        else:
            registry[case_id] = _make_hold_case(case_id, decl)
    return registry


def implementation_status_map(case_ids: list[str] | None = None) -> dict[str, str]:
    from np_suite import case_ids as suite_case_ids

    ids = list(case_ids) if case_ids is not None else list(suite_case_ids(include_cf=True))
    return {
        case_id: ("IMPLEMENTED" if case_id in IMPLEMENTED_CASE_IDS else "HOLD")
        for case_id in ids
    }


def _provider_pki_typed_success_summary(disposition: dict[str, Any]) -> dict[str, Any]:
    """Bounded safe PKI summary for successful runner report only.

    Typed status/generation/retirement/EOF/overflow/counts — never key, cert,
    body, or credential bytes. Do not call on failure paths; STOP stays
    status/kind only (C7B8FD74… / Dex acceptance docket).
    """
    if disposition.get("status") != "GENERATED":
        raise RunnerEntryHeld("provider PKI typed summary requires GENERATED disposition")
    return {
        "status": "GENERATED",
        "generate_invoked": disposition.get("generate_invoked") is True,
        "child_retired": disposition.get("child_retired") is True,
        "group_state": disposition.get("group_state"),
        "leader_exited": disposition.get("leader_exited") is True,
        "readers_joined": disposition.get("readers_joined") is True,
        "readers_eof": disposition.get("readers_eof") is True,
        "late_overflow": disposition.get("late_overflow") is True,
        "late_overflow_checked": disposition.get("late_overflow_checked") is True,
        "stdout_observed_bytes": int(disposition.get("stdout_observed_bytes") or 0),
        "stderr_observed_bytes": int(disposition.get("stderr_observed_bytes") or 0),
        "pipes_closed": disposition.get("pipes_closed") is True,
        "retry": False,
        "db_trust_isolated": disposition.get("db_trust_isolated") is True,
        "resource_label": "GENERATED",
    }


def bind_runtime_public_ca_hash(config: dict[str, Any]) -> dict[str, Any]:
    """I01/I02 custody: ephemeral in-memory ca_sha256 from /public-ca/ca.crt.

    Preserves on-disk runner-config bytes. Distinct from provider PKI trust.
    Host equality remains ProviderDockerOps compare to transferred public hash.
    """
    bound = dict(config)
    public_ca = Path("/public-ca/ca.crt")
    if not public_ca.is_file():
        raise RunnerEntryHeld("public CA missing at /public-ca/ca.crt")
    bound["ca_sha256"] = hashlib.sha256(public_ca.read_bytes()).hexdigest().upper()
    return bound


def stop_payload(error):
    """Bounded locations only. Never format exception messages, locals or SQL."""
    original = {'status': 'STOP', 'kind': type(error).__name__}
    try:
        import re
        def kind(exc):
            name = type(exc).__name__
            return name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception'
        root = ROOT.resolve()
        owned = {}
        for row in (root/'SHA256SUMS.txt').read_text().splitlines():
            pin, rel = row.split('  ', 1)
            if re.fullmatch(r'[A-F0-9]{64}', pin) and re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', rel) and rel.endswith('.py'):
                path = (root/rel).resolve()
                if path.is_relative_to(root) and path.relative_to(root).as_posix() == rel:
                    owned[rel] = pin
        exceptions, seen = [], set()
        current, truncated = error, False
        while current is not None and len(exceptions) < 3 and id(current) not in seen:
            seen.add(id(current))
            frames = []
            tb = current.__traceback__
            walked = 0
            while tb is not None and walked < 128:
                walked += 1
                path = Path(tb.tb_frame.f_code.co_filename).resolve()
                if path.is_relative_to(root):
                    rel = path.relative_to(root).as_posix()
                    if rel in owned:
                        data = path.read_bytes()
                        if hashlib.sha256(data).hexdigest().upper() == owned[rel] and 1 <= tb.tb_lineno <= len(data.splitlines()):
                            frames.append({'path': rel, 'line': tb.tb_lineno})
                            if len(frames) > 8:
                                del frames[0]
                                truncated = True
                        else:
                            truncated = True
                    else:
                        truncated = True
                else:
                    truncated = True
                tb = tb.tb_next
            truncated = truncated or tb is not None
            exceptions.append({'kind': kind(current), 'frames': frames})
            current = current.__cause__ if current.__cause__ is not None else current.__context__
        truncated = truncated or current is not None
        result = {'status': 'STOP', 'kind': kind(error), 'diagnostic': {
            'version': 1, 'exceptions': exceptions, 'truncated': truncated}}
        while len((json.dumps(result)+'\n').encode('utf-8')) > 4096:
            populated = next((entry for entry in exceptions if entry['frames']), None)
            if populated is None:
                raise ValueError('diagnostic cap')
            del populated['frames'][0]
            result['diagnostic']['truncated'] = True
        return result
    except BaseException:
        return original  # Diagnostic failure must not replace the primary kind.


def main() -> int:
    """Admit identity + launch_ready config, bind registry, run serial suite.

    External gate: launch_ready must be true. Incomplete HOLD cases in an
    admitted batch cause CaseBodyHold → non-zero STOP (never PASS).
    Prefer incremental batches that only admit IMPLEMENTED_CASE_IDS until
    remaining bodies are authored.

    Dex seams (57AA3A80… / C7B8FD74…): admit UID + frozen config + guarded
    import roots BEFORE importing np_integrated_runner / np_receipts; bind
    dynamic DB public-CA hash in-memory before run_suite; wire typed PKI
    success summary into the successful report only.

    Report contract (19A695FC… + Dex AA2494B2… adapted): capture console to
    BoundedOutput (hash-only), restore original streams in finally, emit exactly
    one byte-bounded sanitized flat report (top-level suite fields + case_results)
    on the machine-output stream. Runtime executed=true is observed; human
    launch_authorized stays with the independent host approval ledger.
    """
    # Seam 1: UID + config + guarded bootstrap BEFORE sibling imports.
    admit_runner_identity()
    config_path = ROOT / RUNNER_CONFIG_NAME
    config = load_runner_config(config_path)
    admit_isolated_import_bootstrap(
        site_directories=list(config.get("site_directories") or [])
    )
    from np_integrated_runner import run_suite
    from np_receipts import build_receipt

    # Seam 2: ephemeral in-memory CA hash; do not write admitted runner-config.
    config = bind_runtime_public_ca_hash(config)

    # Admitted PKI generate-once BEFORE peer/suite. Prep authors; does not invoke.
    provider_pki_disposition = admit_provider_pki_generated_once(
        launch_ready=config.get("launch_ready") is True
    )
    if provider_pki_disposition.get("status") != "GENERATED":
        raise RunnerEntryHeld("provider PKI GENERATED disposition required before peer")
    provider_pki_summary = _provider_pki_typed_success_summary(provider_pki_disposition)
    case_ids = list(config["case_ids"])
    status = implementation_status_map(case_ids)
    held = [cid for cid, st in status.items() if st == "HOLD"]
    if held:
        raise RunnerEntryHeld(
            "admitted case_ids include explicit HOLD bodies: "
            + ",".join(held)
            + "; narrow batch to implemented "
            + ",".join(sorted(IMPLEMENTED_CASE_IDS))
            + " or complete HOLD bodies before launch_ready run"
        )

    registry = build_registry_from_suite(case_ids)
    if set(registry) != set(case_ids):
        raise RunnerEntryHeld("registry binding mismatch")

    console = BoundedOutput()
    machine_stdout, machine_stderr = sys.stdout, sys.stderr
    case_results: list[dict[str, Any]] = []

    def record_case(case_id: str, result: dict[str, Any]) -> None:
        case_results.append({"case_id": case_id, "result": result})

    try:
        sys.stdout = console  # type: ignore[assignment]
        sys.stderr = console  # type: ignore[assignment]
        report = run_suite(
            config=config,
            registry=registry,
            runtime_pins=config["runtime_pins"],
            record_case=record_case,
        )
    finally:
        # The console sink never owns the machine-readable report channel.
        sys.stdout, sys.stderr = machine_stdout, machine_stderr

    # Preserve the host's top-level suite schema. Case results pass through the
    # existing sanitizer; this does not weaken secret exclusions.
    # Seam 6 / C7B8FD74: typed PKI success summary only on this successful path.
    receipt = build_receipt(
        **report,
        kind="runner_suite_report",
        executed=True,
        case_results=case_results,
        implementation_status=status,
        console_sha256=console.sha.hexdigest().upper(),
        console_bytes=console.length,
        console_policy="hash_only_raw_console_not_retained",
        provider_pki_summary=provider_pki_summary,
        failure_evidence_limits={
            "stop_schema": ["status", "kind", "diagnostic_optional"],
            "includes_raw_traceback": False,
            "includes_packet_owned_source_locations": True,
            "diagnostic_byte_cap": 4096,
            "diagnostic_exception_cap": 3,
            "diagnostic_frames_per_exception_cap": 8,
            "diagnostic_fallback": "original_status_kind",
            "includes_key_cert_body_credential_bytes": False,
            "provider_pki_summary_on_stop": False,
            "note": "STOP does not inherit success PKI summary; no inferred success",
        },
    )
    # Human launch authority is recorded by the independently reviewed host ledger.
    receipt.pop("launch_authorized", None)
    payload = json.dumps(receipt, sort_keys=True) + "\n"
    if len(payload.encode("utf-8")) > OUTPUT_BYTE_CAP:
        raise RunnerEntryHeld("machine report byte cap exceeded")
    machine_stdout.write(payload)
    machine_stdout.flush()
    return 0


if __name__ == "__main__":
    try:
        _exit_code = main()
    except BaseException as exc:
        # Existing location-only format: no messages, locals, SQL, key/cert/body
        # or credential bytes. Bounded diagnostic failure preserves primary kind.
        # Successful PKI summary is never copied into a STOP envelope.
        _stop = json.dumps(stop_payload(exc), sort_keys=True) + "\n"
        sys.stderr.write(_stop)
        sys.stderr.flush()
        _exit_code = 125
    raise SystemExit(_exit_code)
