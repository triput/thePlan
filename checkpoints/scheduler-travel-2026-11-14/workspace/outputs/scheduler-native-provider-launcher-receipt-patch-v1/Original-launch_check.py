#!/usr/bin/env python3
"""Bounded local check launcher for native-provider fake-only verification (prep-v8).

PREPARED ONLY. Not invoked under preparation approval.
Lineage: scheduler-port-zero-fake-v1/packet/verify/invoke_port_fake.py bounded
capture / owned-child retirement / exclusive receipt pattern.
Dex Fake-Launcher-Retirement-Supplement 30FEEDFF…: partial-setup retirement,
post-join EOF+no-reader-error gate, exclusive failure receipt, one-attempt
kill/wait/join bookkeeping, truthful 120+5+5+5 limit freeze.
Capture bounds act DURING collection via bounded readers — not post-hoc slice
after unbounded PIPE drain. Exclusive-create receipt/result gates; no overwrite.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
OUTER_ADMISSION = HERE / "OUTER-ADMISSION.json"
CHECK = HERE / "check_native_provider.py"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
RECEIPT = HERE / "FAKE-NATIVE-PROVIDER-LAUNCH-RECEIPT.json"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
REQUIRED_ISOLATION_FLAGS = ("-I", "-S", "-B")
DEFAULT_CHECK_SECONDS = 120
TIMEOUT_SECONDS_CAP = 600
READER_JOIN_SECONDS = 5.0
POST_KILL_WAIT_SECONDS = 5.0
WAIT_POLL_SECONDS = 0.05
# Truthful disclosed collection+retirement bound after Dex 30FEEDFF… correction.
# Selected collection budget + kill/wait + two reader joins. No separate outer timeout.
TIMEOUT_RETIREMENT_TOTAL_SECONDS = (
    DEFAULT_CHECK_SECONDS + POST_KILL_WAIT_SECONDS + (2 * READER_JOIN_SECONDS)
)
CAPTURE_STDOUT_BYTES = 65536
CAPTURE_STDERR_BYTES = 65536
CAPTURE_RESULT_BYTES = 262144
CAPTURE_READ_CHUNK = 4096
LINEAGE = (
    "scheduler-port-zero-fake-v1/packet/verify/invoke_port_fake.py "
    "bounded-capture owned-child retirement exclusive-receipt; "
    "Dex Fake-Launcher-Retirement-Supplement 30FEEDFF468B3851D3630E73C8BB688D290E4639845A29A377B089DB6534BF27"
)
DEX_LAUNCHER_RETIREMENT_SHA256 = (
    "30FEEDFF468B3851D3630E73C8BB688D290E4639845A29A377B089DB6534BF27"
)


class LaunchStop(Exception):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def verify_parent_isolation() -> list[str]:
    missing: list[str] = []
    if not bool(getattr(sys.flags, "isolated", 0)):
        missing.append("-I")
    if not bool(getattr(sys.flags, "no_site", 0)):
        missing.append("-S")
    if not bool(getattr(sys.flags, "dont_write_bytecode", 0)):
        missing.append("-B")
    return missing


def load_admission() -> dict[str, Any]:
    if not OUTER_ADMISSION.is_file():
        raise LaunchStop("missing OUTER-ADMISSION.json")
    data = json.loads(OUTER_ADMISSION.read_text(encoding="utf-8"))
    if data.get("kind") != "scheduler-native-provider-fake-outer-admission":
        raise LaunchStop("admission kind mismatch")
    if data.get("launch_authorized") is not True:
        raise LaunchStop("launch_authorized is false (prep scaffold)")
    return data


def exclusive_write(path: Path, data: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(str(path), flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
    finally:
        os.close(fd)


class CaptureSink:
    def __init__(self, cap: int) -> None:
        self.retained = bytearray()
        self.observed = 0
        self.overflow = False
        self.saw_eof = False
        self.reader_error = False
        self.cap = cap


def _reader(stream, sink: CaptureSink, overflow_event: threading.Event) -> None:
    try:
        while True:
            chunk = stream.read(CAPTURE_READ_CHUNK)
            if not chunk:
                sink.saw_eof = True
                return
            sink.observed += len(chunk)
            if sink.overflow:
                continue
            if len(sink.retained) + len(chunk) > sink.cap:
                room = sink.cap - len(sink.retained)
                if room > 0:
                    sink.retained.extend(chunk[:room])
                sink.overflow = True
                overflow_event.set()
                continue
            sink.retained.extend(chunk)
    except BaseException:
        sink.reader_error = True
        overflow_event.set()


def validate_result_file(*, expected_controls: list[str]) -> dict[str, Any]:
    if not RESULT.is_file():
        raise LaunchStop("missing result")
    size = RESULT.stat().st_size
    if size > CAPTURE_RESULT_BYTES:
        raise LaunchStop("result exceeds byte cap")
    raw = RESULT.read_bytes()
    if len(raw) != size:
        raise LaunchStop("result size mismatch")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LaunchStop(f"malformed result:{exc!r}") from exc
    if not isinstance(payload, dict):
        raise LaunchStop("result not object")
    if payload.get("kind") != "fake-native-provider-structural-result":
        raise LaunchStop("result kind mismatch")
    if payload.get("prep_is_not_pass") is not True:
        raise LaunchStop("prep_is_not_pass required")
    if payload.get("endpoint") != "unbound":
        raise LaunchStop("endpoint must remain unbound")
    if payload.get("failed", 1) != 0:
        raise LaunchStop("result reports failed controls")
    controls = payload.get("controls")
    if not isinstance(controls, dict):
        raise LaunchStop("controls missing")
    order = payload.get("control_ids_in_order")
    if order != expected_controls:
        raise LaunchStop(f"control order mismatch:{order}")
    for name in expected_controls:
        row = controls.get(name)
        if not isinstance(row, dict) or row.get("observed") != "PASS":
            raise LaunchStop(f"control not PASS:{name}")
    return {
        "result_sha256": hashlib.sha256(raw).hexdigest().upper(),
        "result_bytes": size,
        "passed": payload.get("passed"),
        "nested_predicates": payload.get("nested_predicates"),
    }


def _append_secondary(bucket: list[dict[str, str]], *, kind: str, message: str, phase: str) -> None:
    bucket.append({"kind": kind, "message": message[:200], "phase": phase})


class OwnedCheckSession:
    """One-attempt ownership bookkeeping for check child + capture readers.

    retirement_attempted gates kill/wait/join so error handling never adds a
    second retirement after a prior failure. Unresolved disposition stays UNKNOWN.
    """

    def __init__(self) -> None:
        self.proc: subprocess.Popen[Any] | None = None
        self.stdout_sink: CaptureSink | None = None
        self.stderr_sink: CaptureSink | None = None
        self.t_out: threading.Thread | None = None
        self.t_err: threading.Thread | None = None
        self.readers_constructed = 0
        self.readers_started = 0
        self.overflow = threading.Event()
        self.exit_code: int | None = None
        self.timed_out = False
        self.killed = False
        self.retirement_attempted = False
        self.retirement_unknown = False
        self.readers_joined = False
        self.secondary: list[dict[str, str]] = []
        self.primary: BaseException | None = None

    def mark_primary(self, exc: BaseException) -> None:
        if self.primary is None:
            self.primary = exc
        else:
            _append_secondary(
                self.secondary,
                kind=type(exc).__name__,
                message=str(exc),
                phase="secondary_primary",
            )

    def retire_once(self) -> None:
        """Bounded kill/wait + join for owned child and started readers — once."""
        if self.retirement_attempted:
            self.retirement_unknown = True
            _append_secondary(
                self.secondary,
                kind="duplicate_retirement_refused",
                message="retirement already attempted",
                phase="retirement_guard",
            )
            return
        self.retirement_attempted = True
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
                self.killed = True
            except OSError as exc:
                self.retirement_unknown = True
                _append_secondary(
                    self.secondary,
                    kind=type(exc).__name__,
                    message=str(exc),
                    phase="owned_child_kill",
                )
            wait_deadline = time.monotonic() + POST_KILL_WAIT_SECONDS
            while time.monotonic() < wait_deadline:
                rc = proc.poll()
                if rc is not None:
                    self.exit_code = rc
                    break
                time.sleep(WAIT_POLL_SECONDS)
            if self.exit_code is None and proc.poll() is None:
                self.retirement_unknown = True
                _append_secondary(
                    self.secondary,
                    kind="owned_child_wait_unconfirmed",
                    message="child still present after kill/wait budget",
                    phase="owned_child_wait",
                )
            elif self.exit_code is None:
                self.exit_code = proc.poll()
        for label, thread in (("stdout", self.t_out), ("stderr", self.t_err)):
            if thread is None:
                continue
            try:
                thread.join(timeout=READER_JOIN_SECONDS)
            except RuntimeError as exc:
                self.retirement_unknown = True
                _append_secondary(
                    self.secondary,
                    kind=type(exc).__name__,
                    message=str(exc),
                    phase=f"reader_join_{label}",
                )
        alive = []
        if self.t_out is not None and self.t_out.is_alive():
            alive.append("stdout")
        if self.t_err is not None and self.t_err.is_alive():
            alive.append("stderr")
        self.readers_joined = not alive
        if alive:
            self.retirement_unknown = True
            _append_secondary(
                self.secondary,
                kind="reader_join_unconfirmed",
                message=",".join(alive),
                phase="reader_join",
            )

    def readers_clean_eof(self) -> bool:
        out = self.stdout_sink
        err = self.stderr_sink
        if out is None or err is None:
            return False
        if not self.readers_joined:
            return False
        if out.reader_error or err.reader_error:
            return False
        if not (out.saw_eof and err.saw_eof):
            return False
        return True

    def disposition(self) -> dict[str, Any]:
        out = self.stdout_sink
        err = self.stderr_sink
        return {
            "owned_child_present": self.proc is not None,
            "child_pid": int(self.proc.pid) if self.proc is not None else None,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "killed": self.killed,
            "readers_constructed": self.readers_constructed,
            "readers_started": self.readers_started,
            "readers_joined": self.readers_joined,
            "stdout_saw_eof": bool(out.saw_eof) if out is not None else False,
            "stderr_saw_eof": bool(err.saw_eof) if err is not None else False,
            "stdout_reader_error": bool(out.reader_error) if out is not None else False,
            "stderr_reader_error": bool(err.reader_error) if err is not None else False,
            "stdout_overflow": bool(out.overflow) if out is not None else False,
            "stderr_overflow": bool(err.overflow) if err is not None else False,
            "readers_clean_eof": self.readers_clean_eof(),
            "retirement_attempted": self.retirement_attempted,
            "retirement_unknown": self.retirement_unknown,
            "secondary_retirement": list(self.secondary),
        }


def _refuse_without_writing(reason: str, **extra: Any) -> int:
    payload = {"status": "STOP", "reason": reason, **extra}
    print(f"launch_check STOP: {reason}", file=sys.stderr)
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 125


def _write_failure_receipt(
    *,
    reason: str,
    started: float,
    seconds: int,
    session: OwnedCheckSession | None,
    primary: BaseException | None,
    **extra: Any,
) -> int:
    """Exclusive failure/disposition receipt. Never overwrite prior evidence."""
    if RECEIPT.is_file() or RESULT.is_file():
        return _refuse_without_writing(
            reason,
            preexisting_receipt=RECEIPT.is_file(),
            preexisting_result=RESULT.is_file(),
            primary_error=str(primary) if primary is not None else None,
            **extra,
        )
    disposition = session.disposition() if session is not None else {
        "owned_child_present": False,
        "retirement_attempted": False,
        "retirement_unknown": False,
    }
    status = "UNKNOWN" if (session is not None and session.retirement_unknown) else "STOP"
    primary_text = None
    if primary is not None:
        primary_text = str(primary.args[0]) if primary.args else type(primary).__name__
    elif session is not None and session.primary is not None:
        p = session.primary
        primary_text = str(p.args[0]) if p.args else type(p).__name__
    out = session.stdout_sink if session is not None else None
    err = session.stderr_sink if session is not None else None
    receipt = {
        "kind": "fake-native-provider-launch-receipt",
        "status": status,
        "reason": reason,
        "lineage": LINEAGE,
        "dex_launcher_retirement_sha256": DEX_LAUNCHER_RETIREMENT_SHA256,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        "launch_authorized": False,
        "primary_error": primary_text,
        "check_exit_code": disposition.get("exit_code"),
        "stdout_sha256": (
            hashlib.sha256(bytes(out.retained)).hexdigest().upper() if out is not None else None
        ),
        "stderr_sha256": (
            hashlib.sha256(bytes(err.retained)).hexdigest().upper() if err is not None else None
        ),
        "stdout_observed_bytes": out.observed if out is not None else 0,
        "stderr_observed_bytes": err.observed if err is not None else 0,
        "stdout_retained_bytes": len(out.retained) if out is not None else 0,
        "stderr_retained_bytes": len(err.retained) if err is not None else 0,
        "capture_stdout_cap": CAPTURE_STDOUT_BYTES,
        "capture_stderr_cap": CAPTURE_STDERR_BYTES,
        "capture_result_cap": CAPTURE_RESULT_BYTES,
        "check_seconds_budget": seconds,
        "post_kill_wait_seconds": POST_KILL_WAIT_SECONDS,
        "reader_join_seconds_each": READER_JOIN_SECONDS,
        "timeout_retirement_total_seconds": (
            seconds + POST_KILL_WAIT_SECONDS + (2 * READER_JOIN_SECONDS)
        ),
        "separate_outer_timeout": False,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "disposition": disposition,
        **extra,
    }
    try:
        exclusive_write(RECEIPT, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    except FileExistsError:
        return _refuse_without_writing(
            "receipt_exclusive_create_failed_preexisting",
            attempted_reason=reason,
            primary_error=primary_text,
            **extra,
        )
    print(f"launch_check STOP: {reason}", file=sys.stderr)
    return 125


def main() -> int:
    started = time.monotonic()
    session: OwnedCheckSession | None = None
    seconds = DEFAULT_CHECK_SECONDS
    try:
        missing = verify_parent_isolation()
        if missing:
            raise LaunchStop(f"parent_isolation_flags_missing:{missing}")
        if RESULT.exists() or RECEIPT.exists():
            return _refuse_without_writing(
                "existing evidence; no replay",
                preexisting_receipt=RECEIPT.is_file(),
                preexisting_result=RESULT.is_file(),
            )
        admission = load_admission()
        pins = admission.get("pins") or {}
        check_pin = str(pins.get("check_native_provider_sha256", "")).strip().upper()
        if not check_pin or sha256_file(CHECK) != check_pin:
            raise LaunchStop("check pin mismatch")
        expected_pin = str(pins.get("expected_fake_structural_sha256", "")).strip().upper()
        if not expected_pin or sha256_file(EXPECTED) != expected_pin:
            raise LaunchStop("expected pin mismatch")
        interpreter = Path(str(admission["interpreter_path"]))
        if sha256_file(interpreter) != str(pins.get("interpreter_sha256", "")).strip().upper():
            raise LaunchStop("interpreter pin mismatch")
        seconds = int(admission.get("check_seconds", DEFAULT_CHECK_SECONDS))
        if not 1 <= seconds <= TIMEOUT_SECONDS_CAP:
            raise LaunchStop("check_seconds out of bounds")
        expected_doc = json.loads(EXPECTED.read_text(encoding="utf-8"))
        expected_controls = list(expected_doc.get("control_ids_in_order") or [])
        if not expected_controls:
            raise LaunchStop("EXPECTED missing control_ids_in_order")

        env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C",
            "LC_ALL": "C",
            "PYTHONUTF8": "1",
        }
        cmd = [str(interpreter), *REQUIRED_ISOLATION_FLAGS, str(CHECK)]
        session = OwnedCheckSession()
        session.stdout_sink = CaptureSink(CAPTURE_STDOUT_BYTES)
        session.stderr_sink = CaptureSink(CAPTURE_STDERR_BYTES)
        try:
            session.proc = subprocess.Popen(
                cmd,
                cwd=str(HERE),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
        except OSError as exc:
            session.mark_primary(LaunchStop(f"spawn_failed:{exc!r}"))
            raise LaunchStop(f"spawn_failed:{exc!r}") from exc
        assert session.proc.stdout is not None and session.proc.stderr is not None
        # Reader construction/start is inside owned-child retirement scope (Dex 30FEEDFF…).
        try:
            session.t_out = threading.Thread(
                target=_reader,
                args=(session.proc.stdout, session.stdout_sink, session.overflow),
                daemon=True,
            )
            session.readers_constructed += 1
            session.t_err = threading.Thread(
                target=_reader,
                args=(session.proc.stderr, session.stderr_sink, session.overflow),
                daemon=True,
            )
            session.readers_constructed += 1
            session.t_out.start()
            session.readers_started += 1
            session.t_err.start()
            session.readers_started += 1
        except BaseException as exc:
            session.mark_primary(LaunchStop(f"capture_reader_setup:{type(exc).__name__}"))
            session.retire_once()
            raise LaunchStop(f"capture_reader_setup:{type(exc).__name__}") from exc

        deadline = time.monotonic() + seconds
        try:
            while True:
                if session.overflow.is_set():
                    session.retire_once()
                    break
                rc = session.proc.poll()
                if rc is not None:
                    session.exit_code = rc
                    break
                if time.monotonic() >= deadline:
                    session.timed_out = True
                    session.retire_once()
                    break
                time.sleep(WAIT_POLL_SECONDS)
        except BaseException as exc:
            session.mark_primary(LaunchStop(f"collection:{type(exc).__name__}"))
            session.retire_once()
            raise LaunchStop(f"collection:{type(exc).__name__}") from exc

        if not session.retirement_attempted:
            # Normal exit: one-attempt join path (kill skipped when child already exited).
            session.retire_once()

        out = session.stdout_sink
        err = session.stderr_sink
        assert out is not None and err is not None

        if out.overflow or err.overflow:
            raise LaunchStop("capture overflow during collection")
        if session.timed_out:
            raise LaunchStop("check timeout")
        if session.retirement_unknown:
            raise LaunchStop("reader join failure — UNKNOWN disposition")
        if not session.readers_joined:
            raise LaunchStop("reader join failure — UNKNOWN disposition")
        if out.reader_error or err.reader_error:
            raise LaunchStop("capture reader error — UNKNOWN disposition")
        if not (out.saw_eof and err.saw_eof):
            raise LaunchStop("capture reader EOF incomplete — UNKNOWN disposition")
        if session.exit_code != 0:
            raise LaunchStop(f"check exited {session.exit_code}")
        result_meta = validate_result_file(expected_controls=expected_controls)
        receipt = {
            "kind": "fake-native-provider-launch-receipt",
            "status": "PASS",
            "lineage": LINEAGE,
            "dex_launcher_retirement_sha256": DEX_LAUNCHER_RETIREMENT_SHA256,
            "check_exit_code": session.exit_code,
            "stdout_sha256": hashlib.sha256(bytes(out.retained)).hexdigest().upper(),
            "stderr_sha256": hashlib.sha256(bytes(err.retained)).hexdigest().upper(),
            "stdout_observed_bytes": out.observed,
            "stderr_observed_bytes": err.observed,
            "stdout_retained_bytes": len(out.retained),
            "stderr_retained_bytes": len(err.retained),
            "capture_stdout_cap": CAPTURE_STDOUT_BYTES,
            "capture_stderr_cap": CAPTURE_STDERR_BYTES,
            "capture_result_cap": CAPTURE_RESULT_BYTES,
            "readers_joined_eof": True,
            "readers_clean_eof": True,
            "stdout_reader_error": False,
            "stderr_reader_error": False,
            "killed": session.killed,
            "retirement_attempted": session.retirement_attempted,
            "retirement_unknown": False,
            "check_seconds_budget": seconds,
            "post_kill_wait_seconds": POST_KILL_WAIT_SECONDS,
            "reader_join_seconds_each": READER_JOIN_SECONDS,
            "timeout_retirement_total_seconds": (
                seconds + POST_KILL_WAIT_SECONDS + (2 * READER_JOIN_SECONDS)
            ),
            "separate_outer_timeout": False,
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "disposition": session.disposition(),
            "result": result_meta,
            "prep_is_not_pass": True,
            "endpoint": "unbound",
        }
        exclusive_write(RECEIPT, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        return 0
    except LaunchStop as exc:
        if session is not None and session.proc is not None and not session.retirement_attempted:
            session.mark_primary(exc)
            session.retire_once()
        elif session is not None:
            session.mark_primary(exc)
        return _write_failure_receipt(
            reason=str(exc),
            started=started,
            seconds=seconds,
            session=session,
            primary=exc,
        )
    except BaseException as exc:
        if session is not None and session.proc is not None and not session.retirement_attempted:
            session.mark_primary(exc)
            session.retire_once()
        elif session is not None:
            session.mark_primary(exc)
        return _write_failure_receipt(
            reason=f"unguarded:{type(exc).__name__}",
            started=started,
            seconds=seconds,
            session=session,
            primary=exc,
        )


if __name__ == "__main__":
    raise SystemExit(main())
