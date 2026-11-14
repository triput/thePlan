"""In-runner entry for native-provider t05-closure-prep-jim-v2.

PREPARATION AUTHORING ONLY. Real case dispatch/registry wiring lives here.
PKI child generation and peer bind require later launch authorization
(launch_ready must be true on runner-config). Incomplete cases are explicit
named HOLDs — never fabricated PASS. Unjoined/unconfirmed retirement → UNKNOWN.
No Docker daemon access from this seat.

Successor of t05-closure-prep-jim-v1 (Dex R1–R5): NP-T05-ORDERLY-CLOSE and
NP-T05-ABRUPT-TRUNCATION fixture bodies. Launch batch remains
NP-V-MS-NONEXPIRED only (do not silently fold T05 into runner-config case_ids).
T05 pairs peer close stimulus with production JoinedTLS.receive under
suppress_ragged_eofs=False; peer orderly_close_notify_attempted alone is not
orderly-EOF proof (Native-Deadline-TLS §6; JoinedTLS.close is local-only).
R1: refuse CoveringRootOutcomeUnknown before unwrap when expected_unknown=false.
R2: abrupt requires measured TLS EOF/reset receive + stimulus; no generic refuse.
R3: helper-owned peer retirement on start_background partial-acquisition failure.
R4: fresh validated plan per declared exchange; no now-fallback; no retries.
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
# Launch batch (runner-config case_ids) stays NP-V-MS-NONEXPIRED only.
IMPLEMENTED_CASE_IDS: frozenset[str] = frozenset(
    {
        "NP-V-MS-NONEXPIRED",
        "NP-T05-ORDERLY-CLOSE",
        "NP-T05-ABRUPT-TRUNCATION",
    }
)
_IMPORT_BOOTSTRAP_DONE = False
_PROVIDER_PKI_PREPARED = False
T05_EVENT_PATH = "/calendar/v3/calendars/primary/events"
T05_EVENT_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


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


def _google_event_provider_routes(
    *, peer_hostname: str, dial_address: str, dial_port: int, ca_file: str
):
    """Exact Google event route for T05 framing/TLS closure observations."""
    from app.services.covering_transport_policy import HTTPSPeer

    peer = HTTPSPeer(
        hostname=peer_hostname,
        address=dial_address,
        port=dial_port,
        ca_file=ca_file,
    )
    return ((peer, T05_EVENT_PATH, "event"),)


def _t05_work_remaining(deadline: float) -> Callable[[], float]:
    from app.services.covering_transport_policy import CoveringTransportRefused

    def remaining() -> float:
        left = deadline - monotonic()
        if left <= 0:
            raise CoveringTransportRefused("work deadline")
        return left

    return remaining


def _install_joinedtls_receive_observer(recv_log: list[dict[str, Any]]) -> Callable[[], None]:
    """Observe production JoinedTLS.receive classes without retaining raw bodies.

    Finite abrupt terminal classes at the receive boundary:
    - abrupt_ssl_error (ssl.SSLError)
    - abrupt_tcp_reset (OSError / ConnectionResetError observed on receive)
    Clean EOF remains distinct (empty read under suppress_ragged_eofs=False).
    """
    import ssl as ssl_mod

    from app.services.covering_joined_https import JoinedTLS

    real_receive = JoinedTLS.receive

    def observing_receive(self, maximum):  # type: ignore[no-untyped-def]
        try:
            data = real_receive(self, maximum)
            if data == b"":
                recv_log.append({"class": "clean_eof", "nbytes": 0})
            else:
                recv_log.append({"class": "data", "nbytes": len(data)})
            return data
        except ssl_mod.SSLError as exc:
            recv_log.append(
                {
                    "class": "abrupt_ssl_error",
                    "exc_type": type(exc).__name__,
                }
            )
            raise
        except OSError as exc:
            # Native TCP reset / connection abort observed at receive — not inferred
            # from a generic framing refusal elsewhere.
            recv_log.append(
                {
                    "class": "abrupt_tcp_reset",
                    "exc_type": type(exc).__name__,
                }
            )
            raise

    JoinedTLS.receive = observing_receive  # type: ignore[method-assign]

    def restore() -> None:
        JoinedTLS.receive = real_receive  # type: ignore[method-assign]

    return restore


def _peer_notes(peer: Any) -> list[str]:
    notes = list(getattr(peer.life, "notes", []) or [])
    return [str(n) for n in notes]


def _peer_stimulus_is(peer: Any, mode: str) -> bool:
    observed = getattr(peer.life, "close_mode_observed", None)
    notes = _peer_notes(peer)
    return observed == mode or any(f"peer_close_stimulus:{mode}" == n for n in notes)


def _recv_has_class(recv_log: list[dict[str, Any]], name: str) -> bool:
    return any(row.get("class") == name for row in recv_log)


def _t05_is_covering_root_unknown(exc: BaseException) -> bool:
    """True when outcome is CoveringRootOutcomeUnknown (type or exact class name)."""
    if type(exc).__name__ == "CoveringRootOutcomeUnknown":
        return True
    try:
        from app.services.covering_target_transaction import CoveringRootOutcomeUnknown

        return isinstance(exc, CoveringRootOutcomeUnknown)
    except Exception:
        return False


def _t05_admit_orderly_event_refusal(outcome: Any) -> str:
    """Admit short-CL event refusal classes only; STOP UNKNOWN before unwrap.

    expected_unknown=false event cases must not PASS on cleanup/retirement
    CoveringRootOutcomeUnknown even when primary is IncompleteRead/refused.
    """
    import http.client

    from np_suite import SuiteStop
    from app.services.covering_transport_policy import CoveringTransportRefused

    if isinstance(outcome, BaseException) and _t05_is_covering_root_unknown(outcome):
        raise SuiteStop(
            "event refusal refused CoveringRootOutcomeUnknown "
            "(expected_unknown=false; do not unwrap primary)"
        )
    if isinstance(outcome, CoveringTransportRefused):
        text = str(outcome)
        if "work deadline" in text:
            raise SuiteStop("deadline refusal is not orderly short-CL event evidence")
        return "CoveringTransportRefused"
    if isinstance(outcome, http.client.IncompleteRead):
        return "IncompleteRead"
    raise SuiteStop(
        "short-CL valid JSON prefix was not refused after orderly close_notify:"
        f"{type(outcome).__name__ if outcome is not None else 'None'}"
    )


def _t05_measured_abrupt_receive(recv_log: list[dict[str, Any]]) -> str | None:
    """Return finite abrupt receive terminal class, else None."""
    if _recv_has_class(recv_log, "abrupt_ssl_error"):
        return "abrupt_ssl_error"
    if _recv_has_class(recv_log, "abrupt_tcp_reset"):
        return "abrupt_tcp_reset"
    return None


def _t05_admit_abrupt_truncation(
    *,
    outcome: Any,
    recv_log: list[dict[str, Any]],
    peer_stimulus_ok: bool,
) -> dict[str, Any]:
    """Require measured abrupt TLS EOF/reset receive + stimulus + distinct refuse.

    Generic CoveringTransportRefused / IncompleteRead alone is insufficient.
    Reject UNKNOWN, deadline, malformed-JSON-only, success, and unrelated classes.
    """
    import http.client
    import ssl as ssl_mod

    from np_suite import SuiteStop
    from app.services.covering_transport_policy import CoveringTransportRefused

    if not peer_stimulus_ok:
        raise SuiteStop("abrupt peer stimulus missing")
    if not isinstance(outcome, BaseException):
        raise SuiteStop("abrupt truncation must not accept a complete object")
    if _t05_is_covering_root_unknown(outcome):
        raise SuiteStop(
            "abrupt truncation refused CoveringRootOutcomeUnknown "
            "(expected_unknown=false; do not unwrap primary)"
        )
    abrupt_class = _t05_measured_abrupt_receive(recv_log)
    if abrupt_class is None:
        raise SuiteStop(
            "abrupt truncation requires measured production TLS EOF/reset "
            "receive terminal evidence (abrupt_ssl_error|abrupt_tcp_reset)"
        )
    text = str(outcome)
    if isinstance(outcome, CoveringTransportRefused) and "work deadline" in text:
        raise SuiteStop("deadline refusal is not abrupt TLS truncation evidence")
    if isinstance(outcome, CoveringTransportRefused) and "JSON object required" in text:
        raise SuiteStop("abrupt truncation classified as malformed JSON only")
    admitted_framing = isinstance(
        outcome,
        (ssl_mod.SSLError, OSError, http.client.IncompleteRead, CoveringTransportRefused),
    )
    if not admitted_framing:
        raise SuiteStop(
            f"abrupt truncation unrelated framing/refusal:{type(outcome).__name__}"
        )
    return {
        "production_receive_abrupt_class": abrupt_class,
        "framing_or_tls_disposition": type(outcome).__name__,
        "peer_stimulus_required": True,
        "generic_refusal_alone_insufficient": True,
    }


def _t05_start_owned_peer_or_retire(
    peer: Any,
    *,
    seconds: int,
) -> None:
    """Start peer; on failure after partial acquisition, one bounded retirement.

    Preserves primary start failure. STOP on unconfirmed retirement.
    Caller must not re-retire after this helper raises (peer already retired).
    """
    from np_suite import SuiteStop
    from np_provider_peer import PeerRetirementUnknown

    try:
        peer.start_background(seconds=seconds)
    except BaseException as start_exc:
        # Mark so caller finally cannot double-retire after helper-owned cleanup.
        peer.life.notes.append("t05_helper_start_failure_retirement")
        try:
            retirement = peer.retire_owned(join_seconds=5.0)
        except PeerRetirementUnknown as ret_exc:
            raise SuiteStop(
                "owned peer retirement UNKNOWN after start failure:"
                f"{type(start_exc).__name__}"
            ) from start_exc
        if retirement.get("joined") is not True:
            raise SuiteStop(
                "owned peer unjoined after start failure retirement:"
                f"{type(start_exc).__name__}"
            ) from start_exc
        peer.life.notes.append("t05_helper_start_failure_retired_once")
        raise


def _t05_capture_validated_plan(case_id: str) -> tuple[Any, str]:
    """Fresh plan for one declared exchange; failure/expiry STOP; no now-fallback."""
    from np_suite import SuiteStop
    from np_auth_seed import (
        assert_plan_still_valid,
        fresh_attempt_plan,
        PlanValidityExpired,
    )

    try:
        plan = fresh_attempt_plan(case_id)
    except PlanValidityExpired as exc:
        raise SuiteStop(f"plan validity expired at capture:{case_id}") from exc
    except BaseException as exc:
        raise SuiteStop(
            f"plan capture failed:{case_id}:{type(exc).__name__}"
        ) from exc
    try:
        assert_plan_still_valid(plan.t_plan)
    except PlanValidityExpired as exc:
        raise SuiteStop(f"plan validity expired before exchange:{case_id}") from exc
    return plan, plan.t_plan.isoformat()


def _t05_assert_plan_valid_after(plan: Any, *, exchange_id: str) -> None:
    from np_suite import SuiteStop
    from np_auth_seed import assert_plan_still_valid, PlanValidityExpired

    try:
        assert_plan_still_valid(plan.t_plan)
    except PlanValidityExpired as exc:
        raise SuiteStop(
            f"plan validity expired after exchange:{exchange_id}"
        ) from exc


def _run_t05_covering_exchange(
    *,
    case_id: str,
    scripts: tuple[Any, ...],
    recv_log: list[dict[str, Any]],
) -> tuple[Any, Any | BaseException | None, Any]:
    """One/finite Connection:close inventory through default CoveringHTTP→JoinedTLS."""
    import inspect

    from np_suite import SuiteStop
    from np_provider_peer import SyntheticProviderPeer, PeerMaterial
    from np_provider_routes import google_api_route
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_transport_policy import (
        ProviderCounter,
        approved_provider_limits,
    )

    sig = inspect.signature(CoveringHTTP.__init__)
    if sig.parameters["transport_factory"].default is not JoinedTLS:
        raise SuiteStop("production CoveringHTTP default is not JoinedTLS")
    # Preserve suppress_ragged_eofs=False — do not mutate JoinedTLS.open.
    joined_src = Path(
        __import__("app.services.covering_joined_https", fromlist=["JoinedTLS"]).__file__
        or ""
    )
    if joined_src.is_file():
        text = joined_src.read_text(encoding="utf-8")
        if "suppress_ragged_eofs=False" not in text:
            raise SuiteStop("JoinedTLS must keep suppress_ragged_eofs=False")
        if "Local close only" not in text and "no TLS unwrap" not in text:
            raise SuiteStop("JoinedTLS.close must remain local-close-only")

    route = google_api_route()
    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}",
        route=route,
        connection_scripts=scripts,
        material=PeerMaterial(),
    )
    deadline = monotonic() + float(PEER_SECONDS_DEFAULT)
    remaining = _t05_work_remaining(deadline)
    counter = ProviderCounter(approved_provider_limits(), remaining)
    routes = _google_event_provider_routes(
        peer_hostname=route.server_hostname,
        dial_address=route.dial_address,
        dial_port=route.dial_port,
        ca_file=route.ca_path,
    )
    transport = CoveringHTTP(counter=counter, routes=routes)
    if transport.transport_factory is not JoinedTLS:
        raise SuiteStop("transport_factory injection refused — require default JoinedTLS")

    restore_recv = _install_joinedtls_receive_observer(recv_log)
    outcome: Any | BaseException | None = None
    try:
        # Ownership reachable before risky startup; helper retires once on failure.
        _t05_start_owned_peer_or_retire(peer, seconds=PEER_SECONDS_DEFAULT)
        try:
            outcome = transport.request("GET", T05_EVENT_URL, purpose="event")
        except BaseException as exc:  # noqa: BLE001 — classify then re-bound
            outcome = exc
        return peer, outcome, transport
    finally:
        restore_recv()


def _run_np_t05_orderly_close() -> dict[str, Any]:
    """NP-T05-ORDERLY-CLOSE: dual observations under orderly peer stimulus + production EOF.

    (a) close-delimited complete JSON accepted after observed clean EOF
    (b) valid-JSON short-CL refused after orderly close_notify / clean EOF
    Peer orderly_close_notify_attempted is stimulus only — not sole EOF proof.
    Fresh validated plan per exchange (a) and (b); no shared plan; no now-fallback.
    """
    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_receipts import case_result_receipt
    from np_provider_transcript import (
        orderly_close_delimited_complete_script,
        orderly_short_cl_valid_json_refuse_script,
    )
    from np_provider_peer import PeerRetirementUnknown
    import httpx

    case_id = "NP-T05-ORDERLY-CLOSE"
    decl = registry_by_id(include_cf=True)[case_id]

    observations: dict[str, Any] = {}
    evidence: dict[str, Any] = {
        "peer_stimulus_not_sole_orderly_eof_proof": True,
        "joinedtls_close_local_only": True,
        "suppress_ragged_eofs": False,
        "asgi_disconnect": False,
        "native_deadline_tls_section": 6,
        "fresh_plan_per_exchange": True,
    }
    retirement_attempted = False
    retirement_done = False
    primary_failure: BaseException | None = None
    peer = None
    t_plan_iso_a = ""
    t_plan_iso_b = ""

    # --- observation (a): close-delimited complete ---
    recv_a: list[dict[str, Any]] = []
    try:
        plan_a, t_plan_iso_a = _t05_capture_validated_plan(f"{case_id}:a")
        peer, outcome_a, _transport_a = _run_t05_covering_exchange(
            case_id=f"{case_id}:a",
            scripts=(orderly_close_delimited_complete_script(),),
            recv_log=recv_a,
        )
        retirement_attempted = True
        retirement = peer.retire_owned(join_seconds=5.0)
        retirement_done = True
        if retirement.get("joined") is not True:
            raise SuiteStop("peer worker unjoined — UNKNOWN")
        if not _peer_stimulus_is(peer, "orderly_close_notify"):
            raise SuiteStop("orderly peer stimulus missing for observation a")
        notes_a = _peer_notes(peer)
        if "orderly_close_notify_attempted" not in notes_a:
            raise SuiteStop("orderly close_notify attempt note missing")
        # Attempt label alone insufficient — require production clean EOF + accept.
        if not _recv_has_class(recv_a, "clean_eof"):
            raise SuiteStop(
                "orderly close-delimited missing production clean_eof under "
                "suppress_ragged_eofs=False"
            )
        if isinstance(outcome_a, BaseException):
            raise SuiteStop(
                f"close-delimited complete not accepted:{type(outcome_a).__name__}"
            )
        if not isinstance(outcome_a, httpx.Response):
            raise SuiteStop("close-delimited complete missing httpx.Response")
        _t05_assert_plan_valid_after(plan_a, exchange_id=f"{case_id}:a")
        observations["orderly_close_delimited_complete_accepted"] = (
            "ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY"
        )
        evidence["obs_a"] = {
            "peer_close_mode_observed": peer.life.close_mode_observed,
            "peer_unwrap_ok_note": "orderly_close_notify_unwrap_ok" in notes_a,
            "production_receive_clean_eof": True,
            "framing_disposition": "accepted_close_delimited",
            "unwrap_success_not_required_as_sole_proof": True,
            "t_plan_iso": t_plan_iso_a,
            "attempt_token": plan_a.attempt_token,
        }
    except PeerRetirementUnknown:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise SuiteStop("owned peer retirement UNKNOWN") from primary_failure
    except SuiteStop:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except BaseException as exc:
        primary_failure = exc
        raise SuiteStop(f"framework_stop:{case_id}:a:{type(exc).__name__}") from exc
    finally:
        if (
            peer is not None
            and not retirement_attempted
            and "t05_helper_start_failure_retired_once" not in _peer_notes(peer)
            and peer._worker is not None
            and not peer.life.joined
        ):  # noqa: SLF001
            retirement_attempted = True
            try:
                peer.retire_owned(join_seconds=5.0)
                retirement_done = True
            except PeerRetirementUnknown as cleanup_exc:
                if primary_failure is None:
                    raise SuiteStop("owned peer retirement UNKNOWN on cleanup") from cleanup_exc
                raise SuiteStop(
                    f"owned peer retirement UNKNOWN after primary:{type(primary_failure).__name__}"
                ) from primary_failure

    # --- observation (b): short-CL valid JSON refused after orderly EOF ---
    peer_b = None
    retirement_b_attempted = False
    recv_b: list[dict[str, Any]] = []
    try:
        plan_b, t_plan_iso_b = _t05_capture_validated_plan(f"{case_id}:b")
        if plan_b.attempt_token == evidence.get("obs_a", {}).get("attempt_token"):
            raise SuiteStop("orderly a/b must not share one attempt plan token")
        peer_b, outcome_b, _transport_b = _run_t05_covering_exchange(
            case_id=f"{case_id}:b",
            scripts=(orderly_short_cl_valid_json_refuse_script(),),
            recv_log=recv_b,
        )
        retirement_b_attempted = True
        retirement_b = peer_b.retire_owned(join_seconds=5.0)
        if retirement_b.get("joined") is not True:
            raise SuiteStop("peer worker unjoined — UNKNOWN")
        if not _peer_stimulus_is(peer_b, "orderly_close_notify"):
            raise SuiteStop("orderly peer stimulus missing for observation b")
        if not _recv_has_class(recv_b, "clean_eof"):
            raise SuiteStop(
                "orderly short-CL missing production clean_eof under "
                "suppress_ragged_eofs=False"
            )
        refuse_class = _t05_admit_orderly_event_refusal(outcome_b)
        _t05_assert_plan_valid_after(plan_b, exchange_id=f"{case_id}:b")
        observations["orderly_short_cl_valid_json_prefix_refused"] = (
            "REFUSED_AFTER_ORDERLY_CLOSE_NOTIFY"
        )
        evidence["obs_b"] = {
            "peer_close_mode_observed": peer_b.life.close_mode_observed,
            "production_receive_clean_eof": True,
            "framing_disposition": "refused_incomplete_fixed_length",
            "refuse_class": refuse_class,
            "t_plan_iso": t_plan_iso_b,
            "attempt_token": plan_b.attempt_token,
            "unknown_unwrap_refused": True,
        }
        check_oracles_immediate(
            decl,
            {
                k: str(v)
                for k, v in observations.items()
                if k
                in (
                    "orderly_close_delimited_complete_accepted",
                    "orderly_short_cl_valid_json_prefix_refused",
                )
            },
        )
        return case_result_receipt(
            case_id=case_id,
            passed=True,
            workers_joined=True,
            expected_unknown=False,
            executed=True,
            prep_is_not_pass=True,
            observations=observations,
            t_plan_iso=t_plan_iso_b,
            t_check_iso=_iso_now(),
            measured={
                "t05_evidence": evidence,
                "recv_a": recv_a,
                "recv_b": recv_b,
                "t_plan_iso_a": t_plan_iso_a,
                "t_plan_iso_b": t_plan_iso_b,
            },
            peer_exchange_inventory=[],
            resource_disposition={
                "peer_retired": True,
                "peer_joined": True,
                "obs_a_retired": retirement_done,
                "obs_b_retired": True,
            },
        )
    except PeerRetirementUnknown:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise SuiteStop("owned peer retirement UNKNOWN") from primary_failure
    except SuiteStop:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except BaseException as exc:
        primary_failure = exc
        raise SuiteStop(f"framework_stop:{case_id}:b:{type(exc).__name__}") from exc
    finally:
        if (
            peer_b is not None
            and not retirement_b_attempted
            and "t05_helper_start_failure_retired_once" not in _peer_notes(peer_b)
            and peer_b._worker is not None
            and not peer_b.life.joined
        ):  # noqa: SLF001
            retirement_b_attempted = True
            try:
                peer_b.retire_owned(join_seconds=5.0)
            except PeerRetirementUnknown as cleanup_exc:
                if primary_failure is None:
                    raise SuiteStop("owned peer retirement UNKNOWN on cleanup") from cleanup_exc
                raise SuiteStop(
                    f"owned peer retirement UNKNOWN after primary:{type(primary_failure).__name__}"
                ) from primary_failure


def _run_np_t05_abrupt_truncation() -> dict[str, Any]:
    """NP-T05-ABRUPT-TRUNCATION: abrupt TLS without close_notify ≠ malformed/ASGI."""
    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_receipts import case_result_receipt
    from np_provider_transcript import abrupt_truncation_script
    from np_provider_peer import PeerRetirementUnknown

    case_id = "NP-T05-ABRUPT-TRUNCATION"
    decl = registry_by_id(include_cf=True)[case_id]
    plan, t_plan_iso = _t05_capture_validated_plan(case_id)

    recv_log: list[dict[str, Any]] = []
    retirement_attempted = False
    primary_failure: BaseException | None = None
    peer = None
    try:
        peer, outcome, _transport = _run_t05_covering_exchange(
            case_id=case_id,
            scripts=(abrupt_truncation_script(),),
            recv_log=recv_log,
        )
        retirement_attempted = True
        retirement = peer.retire_owned(join_seconds=5.0)
        if retirement.get("joined") is not True:
            raise SuiteStop("peer worker unjoined — UNKNOWN")
        if not _peer_stimulus_is(peer, "abrupt_truncate"):
            raise SuiteStop("abrupt peer stimulus missing")
        notes = _peer_notes(peer)
        if "abrupt_truncate_without_close_notify" not in notes:
            raise SuiteStop("abrupt truncate note missing")

        abrupt_meta = _t05_admit_abrupt_truncation(
            outcome=outcome,
            recv_log=recv_log,
            peer_stimulus_ok=True,
        )
        _t05_assert_plan_valid_after(plan, exchange_id=case_id)

        observations = {
            "classified_distinct_from_malformed_and_asgi_disconnect": "OBSERVED",
        }
        evidence = {
            "peer_close_mode_observed": peer.life.close_mode_observed,
            "peer_stimulus_not_sole_abrupt_proof": True,
            "production_receive_abrupt_class": abrupt_meta["production_receive_abrupt_class"],
            "production_receive_abrupt_ssl_error": (
                abrupt_meta["production_receive_abrupt_class"] == "abrupt_ssl_error"
            ),
            "framing_or_tls_disposition": abrupt_meta["framing_or_tls_disposition"],
            "asgi_disconnect": False,
            "malformed_json_only": False,
            "suppress_ragged_eofs": False,
            "joinedtls_close_local_only": True,
            "native_deadline_tls_section": 6,
            "generic_refusal_alone_insufficient": True,
            "unknown_unwrap_refused": True,
            "t_plan_iso": t_plan_iso,
            "attempt_token": plan.attempt_token,
        }
        check_oracles_immediate(decl, observations)
        return case_result_receipt(
            case_id=case_id,
            passed=True,
            workers_joined=True,
            expected_unknown=False,
            executed=True,
            prep_is_not_pass=True,
            observations=observations,
            t_plan_iso=t_plan_iso,
            t_check_iso=_iso_now(),
            measured={"t05_evidence": evidence, "recv_log": recv_log},
            peer_exchange_inventory=[],
            resource_disposition={"peer_retired": True, "peer_joined": True},
        )
    except PeerRetirementUnknown:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise SuiteStop("owned peer retirement UNKNOWN") from primary_failure
    except SuiteStop:
        primary_failure = sys.exc_info()[1]  # type: ignore[assignment]
        raise
    except BaseException as exc:
        primary_failure = exc
        raise SuiteStop(f"framework_stop:{case_id}:{type(exc).__name__}") from exc
    finally:
        if (
            peer is not None
            and not retirement_attempted
            and "t05_helper_start_failure_retired_once" not in _peer_notes(peer)
            and peer._worker is not None
            and not peer.life.joined
        ):  # noqa: SLF001
            retirement_attempted = True
            try:
                peer.retire_owned(join_seconds=5.0)
            except PeerRetirementUnknown as cleanup_exc:
                if primary_failure is None:
                    raise SuiteStop("owned peer retirement UNKNOWN on cleanup") from cleanup_exc
                raise SuiteStop(
                    f"owned peer retirement UNKNOWN after primary:{type(primary_failure).__name__}"
                ) from primary_failure


def _make_implemented_case(case_id: str) -> Callable[[], dict[str, Any]]:
    if case_id == "NP-V-MS-NONEXPIRED":
        def _run() -> dict[str, Any]:
            return _run_np_v_ms_nonexpired()

        _run.__name__ = f"run_{case_id}"
        return _run
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
            "stop_schema": ["status", "kind"],
            "includes_traceback": False,
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
        # Failure evidence limits disclosed: status + kind only. No traceback,
        # exception text, locals, raw console, key/cert/body/credential bytes,
        # and no inferred PKI success summary on STOP (C7B8FD74…).
        _stop = json.dumps({"status": "STOP", "kind": type(exc).__name__}, sort_keys=True) + "\n"
        sys.stderr.write(_stop)
        sys.stderr.flush()
        _exit_code = 125
    raise SystemExit(_exit_code)
