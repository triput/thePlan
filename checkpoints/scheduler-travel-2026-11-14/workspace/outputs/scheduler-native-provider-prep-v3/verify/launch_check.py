#!/usr/bin/env python3
"""Bounded local check launcher for native-provider fake-only verification (prep-v2).

PREPARED ONLY. Not invoked under preparation approval.
Lineage: scheduler-port-zero-fake-v1/packet/verify/invoke_port_fake.py bounded
capture / owned-child retirement / exclusive receipt pattern.
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
CAPTURE_STDOUT_BYTES = 65536
CAPTURE_STDERR_BYTES = 65536
CAPTURE_RESULT_BYTES = 262144
CAPTURE_READ_CHUNK = 4096
LINEAGE = (
    "scheduler-port-zero-fake-v1/packet/verify/invoke_port_fake.py "
    "bounded-capture owned-child retirement exclusive-receipt"
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


def main() -> int:
    started = time.monotonic()
    try:
        missing = verify_parent_isolation()
        if missing:
            raise LaunchStop(f"parent_isolation_flags_missing:{missing}")
        if RESULT.exists() or RECEIPT.exists():
            raise LaunchStop("existing evidence; no replay")
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
        overflow = threading.Event()
        stdout_sink = CaptureSink(CAPTURE_STDOUT_BYTES)
        stderr_sink = CaptureSink(CAPTURE_STDERR_BYTES)
        proc = subprocess.Popen(
            cmd,
            cwd=str(HERE),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        assert proc.stdout is not None and proc.stderr is not None
        t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_sink, overflow), daemon=True)
        t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_sink, overflow), daemon=True)
        t_out.start()
        t_err.start()
        deadline = time.monotonic() + seconds
        exit_code: int | None = None
        timed_out = False
        killed = False
        while True:
            if overflow.is_set():
                try:
                    proc.kill()
                except OSError:
                    pass
                killed = True
                break
            rc = proc.poll()
            if rc is not None:
                exit_code = rc
                break
            if time.monotonic() >= deadline:
                timed_out = True
                try:
                    proc.kill()
                except OSError:
                    pass
                killed = True
                break
            time.sleep(WAIT_POLL_SECONDS)
        if exit_code is None:
            # Post-kill wait
            wait_deadline = time.monotonic() + POST_KILL_WAIT_SECONDS
            while time.monotonic() < wait_deadline:
                rc = proc.poll()
                if rc is not None:
                    exit_code = rc
                    break
                time.sleep(WAIT_POLL_SECONDS)
        t_out.join(timeout=READER_JOIN_SECONDS)
        t_err.join(timeout=READER_JOIN_SECONDS)
        readers_joined = (not t_out.is_alive()) and (not t_err.is_alive())
        if stdout_sink.overflow or stderr_sink.overflow:
            raise LaunchStop("capture overflow during collection")
        if timed_out:
            raise LaunchStop("check timeout")
        if not readers_joined:
            raise LaunchStop("reader join failure — UNKNOWN disposition")
        if exit_code != 0:
            raise LaunchStop(f"check exited {exit_code}")
        result_meta = validate_result_file(expected_controls=expected_controls)
        receipt = {
            "kind": "fake-native-provider-launch-receipt",
            "lineage": LINEAGE,
            "check_exit_code": exit_code,
            "stdout_sha256": hashlib.sha256(bytes(stdout_sink.retained)).hexdigest().upper(),
            "stderr_sha256": hashlib.sha256(bytes(stderr_sink.retained)).hexdigest().upper(),
            "stdout_observed_bytes": stdout_sink.observed,
            "stderr_observed_bytes": stderr_sink.observed,
            "stdout_retained_bytes": len(stdout_sink.retained),
            "stderr_retained_bytes": len(stderr_sink.retained),
            "capture_stdout_cap": CAPTURE_STDOUT_BYTES,
            "capture_stderr_cap": CAPTURE_STDERR_BYTES,
            "capture_result_cap": CAPTURE_RESULT_BYTES,
            "readers_joined_eof": bool(stdout_sink.saw_eof and stderr_sink.saw_eof and readers_joined),
            "killed": killed,
            "check_seconds_budget": seconds,
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "result": result_meta,
            "prep_is_not_pass": True,
            "endpoint": "unbound",
        }
        exclusive_write(RECEIPT, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        return 0
    except LaunchStop as exc:
        print(f"launch_check STOP: {exc}", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
