#!/usr/bin/env python3
"""Bounded launcher for held fake-only D2 path admission harness.

NOT executed during D2 path-admission preparation. This launcher IS the
in-process 30-second timeout supervisor for the check child. Outer
noncircular admission of this launcher's bytes is enforced by admit_outer.py
against OUTER-ADMISSION.json — this file does NOT embed or self-compare its
own final raw-byte hash.

Exit codes: 0 PASS / 1 FAIL / 124 timeout / 125 STOP or UNKNOWN
(termination unconfirmed, capture over-limit, reader retirement UNKNOWN,
primary collection/wait error, pin mismatch, or result gate refused).

Isolation: parent and child both require -I -S -B. Launcher verifies those
flags on the current process before admission and passes them to the child.
-I → sys.flags.isolated; -S → sys.flags.no_site (not merely no_user_site);
-B → sys.flags.dont_write_bytecode.

Pin enforcement layers (noncircular):
- Outer (admit_outer.py + OUTER-ADMISSION.json): interpreter + launcher +
  check + EXPECTED + INPUT-MANIFEST + PACKET-SHA256SUMS + admit_outer pins
  before starting this launcher.
- Launcher (this file, pre-child admission): interpreter SHA (hardcoded pin);
  check/EXPECTED-OUTPUT/INPUT-MANIFEST SHA vs PACKET-SHA256SUMS.txt
  (launcher self hash is NOT compared here); parent isolation flags; child
  argv isolation flags; capture-during-collection bounds.
- Check script (inside child): fixture source SHA vs INPUT-MANIFEST sources
  (four fixtures only) plus separate pinned launch-config static input before
  controls; FakeOS.path.join posixpath semantics; exact EXPECTED-OUTPUT
  control inventory + ordered contract.
- Result gate (launcher post-termination, only after confirmed termination +
  capture admission + reader retirement complete + no primary collection/
  wait error or unexpected collection interrupt): exact control IDs/order
  (EXPECTED control_ids_in_order / controls key order), every expected
  result, inventory_error=None, source_hashes_verified=True, executed=True.

Capture readers: during-read retained allocation is capped; ownership /
outcome accounting checks is_alive after join; still-live / incomplete /
error readers → UNKNOWN (no PASS / no result validation). Process exit
alone does not imply reader EOF. Overflow interrupts the child (kill) rather
than waiting for normal exit while readers drain. Timeout kill/wait
exceptions are retained as secondary termination evidence. Any collection
interrupt/error (including proc_wait_error with capture_stop=None) requires
explicit non-None child-exit confirmation before result validation or a
child_exited_normally claim; pe remains primary; no retries. Any primary
collection/wait error or unexpected collection interrupt also prevents
result admission/PASS even when child exit later proves 0 with a
valid-looking result file — retaining primary_error on a PASS receipt is
not stop-on-failure. Receipt pins child_pid (proc.pid at Popen success)
plus executable/argv and creation/start timestamp for read-only custody
reconciliation when termination is unconfirmed; no process enumeration,
retry, fallback, or new cleanup authority.
Disclosed bounds: TIMEOUT_SECONDS + POST_KILL_WAIT_SECONDS +
2×READER_JOIN_SECONDS = 45s total (see receipt timeout_retirement_limits).

Empty / whitespace pin literals refuse admission (no silent waive at freeze).
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
CHECK = HERE / "check_d2_path_admission_fake.py"
LAUNCHER = HERE / "invoke_d2_fake.py"
RESULT = HERE / "FAKE-D2-RESULT.json"
RECEIPT = HERE / "FAKE-D2-LAUNCH-RECEIPT.json"
EXPECTED = HERE / "EXPECTED-OUTPUT.json"
INPUT_MANIFEST = HERE / "INPUT-MANIFEST.json"
PACKET_SUMS = HERE / "PACKET-SHA256SUMS.txt"
TIMEOUT_SECONDS = 30
# Reader join / post-kill wait bounds (disclosed; no retry beyond these).
READER_JOIN_SECONDS = 5.0
POST_KILL_WAIT_SECONDS = 5.0
WAIT_POLL_SECONDS = 0.05
# Total disclosed wall bound for one attempt (no retry):
# TIMEOUT_SECONDS + POST_KILL_WAIT_SECONDS + 2 * READER_JOIN_SECONDS
TIMEOUT_RETIREMENT_TOTAL_SECONDS = (
    TIMEOUT_SECONDS + POST_KILL_WAIT_SECONDS + (2 * READER_JOIN_SECONDS)
)

# Frozen capture + retained byte limits (enforced + disclosed on receipt).
# Capture bounds act DURING collection via bounded readers — not merely after
# PIPE+communicate then a post-hoc size check. Over-limit → STOP (disclosed);
# owner interrupts child on observed overflow (does not wait out full timeout
# while readers drain).
CAPTURE_STDOUT_BYTES = 65536
CAPTURE_STDERR_BYTES = 65536
CAPTURE_RESULT_BYTES = 262144
RETAINED_STDOUT_BYTES = CAPTURE_STDOUT_BYTES
RETAINED_STDERR_BYTES = CAPTURE_STDERR_BYTES
RETAINED_RESULT_BYTES = CAPTURE_RESULT_BYTES
REQUIRED_ISOLATION_FLAGS = ("-I", "-S", "-B")
CAPTURE_READ_CHUNK = 4096

# Interpreter pin: launcher-enforced before child admission.
PINNED_INTERPRETER_PATH = (
    "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe"
)
PINNED_INTERPRETER_SHA256 = (
    "5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC"
)

# Packet-file pins live in PACKET-SHA256SUMS.txt (launcher compares live bytes).
# INTENTIONALLY excludes invoke_d2_fake.py — launcher must not
# self-admit via a co-updated pin of its own final raw bytes (noncircular).
# Launcher bytes are admitted by OUTER-ADMISSION.json via admit_outer.py.
PACKET_PIN_NAMES = (
    "check_d2_path_admission_fake.py",
    "EXPECTED-OUTPUT.json",
    "INPUT-MANIFEST.json",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _require_nonempty_pin(label: str, value: Any) -> str:
    """Empty conditional pin literals must not silently waive checks at freeze."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"empty_or_invalid_pin:{label}")
    return value.strip().upper()


def write_receipt(payload: dict) -> None:
    RECEIPT.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )


def _clip_bytes(raw: bytes, limit: int) -> str:
    if len(raw) <= limit:
        return raw.decode("utf-8", errors="replace")
    return raw[-limit:].decode("utf-8", errors="replace")


def verify_parent_isolation() -> list[str]:
    """Refuse admission unless this process was started with -I -S -B.

    -I → isolated (also implies -s / no_user_site; that alone is insufficient
         proof of -S).
    -S → no_site (site module not imported).
    -B → dont_write_bytecode.
    """
    missing: list[str] = []
    if not bool(getattr(sys.flags, "isolated", 0)):
        missing.append("-I")
    # -S must be evidenced by no_site. no_user_site is set by -I alone.
    if not bool(getattr(sys.flags, "no_site", 0)):
        missing.append("-S")
    if not bool(getattr(sys.flags, "dont_write_bytecode", 0)):
        missing.append("-B")
    return missing


def load_packet_pins() -> tuple[dict[str, str] | None, str | None]:
    """Load frozen packet SHA pins from PACKET-SHA256SUMS.txt."""
    if not PACKET_SUMS.is_file():
        return None, "missing_packet_sha256sums"
    try:
        text = PACKET_SUMS.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None, "malformed_packet_sha256sums"
    pins: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            return None, "malformed_packet_sha256sums_line"
        digest, name = parts[0].upper(), parts[1].replace("\\", "/").split("/")[-1]
        try:
            digest = _require_nonempty_pin(name, digest)
        except ValueError:
            return None, f"empty_packet_pin_{name}"
        pins[name] = digest
    for required in PACKET_PIN_NAMES:
        if required not in pins:
            return None, f"packet_pin_missing_{required}"
        try:
            pins[required] = _require_nonempty_pin(required, pins[required])
        except ValueError:
            return None, f"empty_packet_pin_{required}"
    return pins, None


def _load_expected_controls() -> tuple[dict[str, Any] | None, list[str] | None, str | None]:
    if not EXPECTED.is_file():
        return None, None, "missing_expected_output"
    try:
        size = EXPECTED.stat().st_size
    except OSError:
        return None, None, "expected_stat_failed"
    if size > CAPTURE_RESULT_BYTES:
        return None, None, "expected_exceeds_byte_limit"
    try:
        payload = json.loads(EXPECTED.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, "malformed_expected_output"
    if not isinstance(payload, dict):
        return None, None, "malformed_expected_output"
    controls = payload.get("controls")
    if not isinstance(controls, dict) or not controls:
        return None, None, "expected_controls_missing"
    # Single deterministic ordered contract: explicit control_ids_in_order when
    # present must match controls key order; otherwise controls key order is
    # the frozen contract (EXPECTED starts N1,N2,...).
    expected_ids = list(controls.keys())
    explicit = payload.get("control_ids_in_order")
    if explicit is not None:
        if not isinstance(explicit, list) or [str(x) for x in explicit] != expected_ids:
            return None, None, "expected_control_ids_in_order_mismatch"
    return controls, expected_ids, None


def validate_result_file(
    *,
    started_at: float,
    expected_controls: dict[str, Any],
    expected_ids: list[str],
) -> tuple[bool, str | None, str | None, int | None]:
    """Refuse PASS from exit0 alone.

    Gates: fresh mtime, size before read, well-formed JSON, status PASS,
    class FAKE-D2-PATH-ADMISSION, exact expected control IDs *and order*, every
    expected control result, inventory_error is None, source_hashes_verified
    True, executed True. Malformed / missing / mismatched inventory → refuse.
    """
    if not RESULT.is_file():
        return False, None, "missing_result", None
    try:
        st = RESULT.stat()
        mtime = st.st_mtime
        size = int(st.st_size)
    except OSError:
        return False, None, "result_stat_failed", None
    if mtime + 0.001 < started_at:
        return False, None, "stale_preexisting_result", size
    # Size gate BEFORE read_bytes — retained-tail alone ≠ capture limit.
    if size > CAPTURE_RESULT_BYTES:
        return False, None, "result_exceeds_capture_limit", size
    raw = RESULT.read_bytes()
    read_bytes = len(raw)
    if read_bytes > CAPTURE_RESULT_BYTES:
        return False, sha256_file(RESULT), "result_exceeds_byte_limit", read_bytes
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, sha256_file(RESULT), "malformed_result", read_bytes
    if not isinstance(payload, dict):
        return False, sha256_file(RESULT), "malformed_result", read_bytes
    if payload.get("status") != "PASS":
        return False, sha256_file(RESULT), "result_status_not_pass", read_bytes
    if payload.get("class") != "FAKE-D2-PATH-ADMISSION":
        return False, sha256_file(RESULT), "result_class_mismatch", read_bytes
    if payload.get("inventory_error") is not None:
        return False, sha256_file(RESULT), "inventory_error_present", read_bytes
    if payload.get("source_hashes_verified") is not True:
        return False, sha256_file(RESULT), "source_hashes_not_verified", read_bytes
    if payload.get("executed") is not True:
        return False, sha256_file(RESULT), "executed_not_true", read_bytes

    order = payload.get("control_ids_in_order")
    controls = payload.get("controls")
    if not isinstance(order, list) or not isinstance(controls, dict):
        return False, sha256_file(RESULT), "malformed_inventory", read_bytes
    if order != expected_ids:
        return False, sha256_file(RESULT), "control_ids_order_mismatch", read_bytes
    if list(controls.keys()) != expected_ids:
        return False, sha256_file(RESULT), "controls_key_order_mismatch", read_bytes
    if set(controls.keys()) != set(expected_ids):
        return False, sha256_file(RESULT), "controls_set_mismatch", read_bytes
    for cid, spec in expected_controls.items():
        entry = controls.get(cid)
        if not isinstance(entry, dict):
            return False, sha256_file(RESULT), f"missing_control_{cid}", read_bytes
        want = spec.get("result")
        got = entry.get("result")
        if got != want:
            return (
                False,
                sha256_file(RESULT),
                f"control_result_mismatch_{cid}",
                read_bytes,
            )
    return True, sha256_file(RESULT), None, read_bytes


def _confirm_termination(proc: subprocess.Popen) -> tuple[bool, int | None, str]:
    """Confirm child exit after kill. No retry. Honest unconfirmed → STOP."""
    try:
        polled = proc.poll()
    except Exception:
        return False, None, "termination_unconfirmed"
    if polled is not None:
        return True, 124, "child_killed_after_timeout"
    if proc.returncode is not None:
        return True, 124, "child_killed_after_timeout"
    return False, 125, "termination_unconfirmed"


def _stop_receipt(reason: str, **extra: Any) -> int:
    write_receipt({"status": "STOP", "reason": reason, **extra})
    print(f"launcher refuses admission: {reason}", file=sys.stderr)
    return 125


class _BoundedPipeReader:
    """Read a pipe during collection; STOP intent when over capture limit.

    During-read retained allocation is capped. Finish ownership/outcome is
    accounted separately via retirement_state() — process exit alone does not
    imply EOF or a successful join.
    """

    def __init__(self, stream: Any, limit: int, label: str) -> None:
        self.stream = stream
        self.limit = limit
        self.label = label
        self.buf = bytearray()
        self.overflow = False
        self.error: str | None = None
        self.saw_eof = False
        self.start_error: str | None = None
        self._started = False
        self._thread = threading.Thread(
            target=self._run, name=f"bounded-capture-{label}", daemon=True
        )

    def start(self) -> None:
        try:
            self._thread.start()
            self._started = True
        except Exception as exc:  # noqa: BLE001 — capture path must not escape
            self.start_error = f"{type(exc).__name__}:{exc}"[:200]

    def _run(self) -> None:
        try:
            while True:
                chunk = self.stream.read(CAPTURE_READ_CHUNK)
                if not chunk:
                    self.saw_eof = True
                    break
                if self.overflow:
                    # Overflow already observed; owner interrupts the child.
                    # Keep reading only until pipe EOF after interrupt — do not
                    # treat continued drain as the stop mechanism itself.
                    continue
                if len(self.buf) + len(chunk) > self.limit:
                    remain = self.limit - len(self.buf)
                    if remain > 0:
                        self.buf.extend(chunk[:remain])
                    self.overflow = True
                    continue
                self.buf.extend(chunk)
        except Exception as exc:  # noqa: BLE001 — capture path must not escape
            self.error = f"{type(exc).__name__}:{exc}"[:200]

    def join(self, timeout: float | None = None) -> None:
        if self._started:
            self._thread.join(timeout)

    def is_alive(self) -> bool:
        return bool(self._started and self._thread.is_alive())

    def retirement_state(self) -> str:
        """Honest reader ownership outcome; never inferred from process exit."""
        if self.start_error is not None:
            return "start_failed"
        if not self._started:
            return "not_started"
        if self._thread.is_alive():
            return "alive_after_join"
        if self.error is not None:
            return "error"
        if self.saw_eof:
            if self.overflow:
                return "joined_eof_after_overflow"
            return "joined_eof"
        return "joined_incomplete"


_READER_UNKNOWN_STATES = frozenset(
    {
        "alive_after_join",
        "joined_incomplete",
        "error",
        "start_failed",
        "not_started",
    }
)


def _append_secondary(bucket: list[dict[str, str]], *, kind: str, message: str, phase: str) -> None:
    bucket.append(
        {
            "kind": kind,
            "message": message[:200],
            "phase": phase,
        }
    )


def _kill_and_wait(
    proc: subprocess.Popen,
    *,
    secondary: list[dict[str, str]],
    phase_prefix: str,
) -> None:
    """Kill child and wait once; retain kill/wait exceptions as secondary evidence."""
    try:
        proc.kill()
    except Exception as kill_exc:  # noqa: BLE001 — retain, do not swallow
        _append_secondary(
            secondary,
            kind=type(kill_exc).__name__,
            message=str(kill_exc),
            phase=f"{phase_prefix}_kill",
        )
    try:
        proc.wait(timeout=POST_KILL_WAIT_SECONDS)
    except Exception as wait_exc:  # noqa: BLE001 — retain, do not swallow
        _append_secondary(
            secondary,
            kind=type(wait_exc).__name__,
            message=str(wait_exc),
            phase=f"{phase_prefix}_wait",
        )


def _collect_bounded(
    proc: subprocess.Popen,
    *,
    timeout: float,
) -> tuple[
    bytes,
    bytes,
    bool,
    str | None,
    str | None,
    list[dict[str, str]],
    dict[str, str],
    str | None,
]:
    """Collect stdout/stderr with bounds enforced during read, not after.

    Overflow interrupts the child immediately (kill) rather than waiting for
    normal exit/timeout while readers drain. Reader join checks is_alive;
    still-live / incomplete / error outcomes are returned honestly and must
    block PASS / result validation. interrupt_reason is returned so callers
    can require explicit child-exit confirmation for every interrupt/error
    path (including proc_wait_error when capture_stop stays None). No retry
    beyond disclosed limits.
    """
    assert proc.stdout is not None and proc.stderr is not None
    out_reader = _BoundedPipeReader(proc.stdout, CAPTURE_STDOUT_BYTES, "stdout")
    err_reader = _BoundedPipeReader(proc.stderr, CAPTURE_STDERR_BYTES, "stderr")
    secondary: list[dict[str, str]] = []
    timed_out = False
    primary_error: str | None = None
    capture_stop: str | None = None
    interrupt_reason: str | None = None

    out_reader.start()
    err_reader.start()
    if out_reader.start_error is not None:
        capture_stop = f"stdout_reader_UNKNOWN:start_failed:{out_reader.start_error}"
        interrupt_reason = "reader_start_failed"
    elif err_reader.start_error is not None:
        capture_stop = f"stderr_reader_UNKNOWN:start_failed:{err_reader.start_error}"
        interrupt_reason = "reader_start_failed"

    deadline = time.monotonic() + timeout
    process_exited = False
    try:
        if interrupt_reason is None:
            while True:
                if out_reader.overflow:
                    capture_stop = "stdout_exceeds_capture_limit"
                    interrupt_reason = "capture_overflow"
                    break
                if err_reader.overflow:
                    capture_stop = "stderr_exceeds_capture_limit"
                    interrupt_reason = "capture_overflow"
                    break
                if out_reader.error is not None:
                    capture_stop = f"stdout_capture_error:{out_reader.error}"
                    interrupt_reason = "capture_error"
                    break
                if err_reader.error is not None:
                    capture_stop = f"stderr_capture_error:{err_reader.error}"
                    interrupt_reason = "capture_error"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    primary_error = "TimeoutExpired"
                    interrupt_reason = "timeout"
                    break
                try:
                    proc.wait(timeout=min(WAIT_POLL_SECONDS, remaining))
                    process_exited = True
                    break
                except subprocess.TimeoutExpired:
                    continue
    except Exception as wait_exc:  # noqa: BLE001 — retain; may leave readers live
        primary_error = f"proc_wait_error:{type(wait_exc).__name__}"
        interrupt_reason = "proc_wait_error"
        _append_secondary(
            secondary,
            kind=type(wait_exc).__name__,
            message=str(wait_exc),
            phase="proc_wait",
        )

    if interrupt_reason in (
        "capture_overflow",
        "capture_error",
        "timeout",
        "reader_start_failed",
        "proc_wait_error",
    ) and not process_exited:
        _kill_and_wait(
            proc,
            secondary=secondary,
            phase_prefix=interrupt_reason or "interrupt",
        )

    out_reader.join(timeout=READER_JOIN_SECONDS)
    err_reader.join(timeout=READER_JOIN_SECONDS)

    reader_retirement = {
        "stdout": out_reader.retirement_state(),
        "stderr": err_reader.retirement_state(),
    }

    # Overflow / capture error may already be set; still record reader UNKNOWN.
    for label, reader in (("stdout", out_reader), ("stderr", err_reader)):
        state = reader_retirement[label]
        if state in _READER_UNKNOWN_STATES:
            detail = f"{label}_reader_UNKNOWN:{state}"
            if reader.error and state == "error":
                detail = f"{detail}:{reader.error}"
            if reader.start_error and state == "start_failed":
                detail = f"{detail}:{reader.start_error}"
            if capture_stop is None:
                capture_stop = detail
            else:
                _append_secondary(
                    secondary,
                    kind="reader_retirement_UNKNOWN",
                    message=detail,
                    phase="reader_join",
                )
        elif reader.overflow and capture_stop is None:
            capture_stop = f"{label}_exceeds_capture_limit"
        elif reader.error and capture_stop is None:
            capture_stop = f"{label}_capture_error:{reader.error}"

    return (
        bytes(out_reader.buf),
        bytes(err_reader.buf),
        timed_out,
        primary_error,
        capture_stop,
        secondary,
        reader_retirement,
        interrupt_reason,
    )


def main() -> int:
    # Hardcoded interpreter pin must be non-empty at freeze (no silent waive).
    try:
        pinned_interpreter = _require_nonempty_pin(
            "PINNED_INTERPRETER_SHA256", PINNED_INTERPRETER_SHA256
        )
    except ValueError as exc:
        return _stop_receipt(str(exc))

    isolation_missing = verify_parent_isolation()
    interpreter = Path(sys.executable).resolve()
    interpreter_sha256 = sha256_file(interpreter) if interpreter.is_file() else None
    check_sha256 = sha256_file(CHECK) if CHECK.is_file() else None
    launcher_sha256 = sha256_file(LAUNCHER) if LAUNCHER.is_file() else None
    expected_sha256 = sha256_file(EXPECTED) if EXPECTED.is_file() else None
    manifest_sha256 = sha256_file(INPUT_MANIFEST) if INPUT_MANIFEST.is_file() else None

    base_ids = {
        "interpreter": str(interpreter),
        "interpreter_sha256": interpreter_sha256,
        "check_sha256": check_sha256,
        "launcher_sha256": launcher_sha256,
        "launcher_self_pin_compared": False,
        "pin_enforcement_layer": "launcher_pre_admission",
        "noncircular_note": (
            "launcher raw-byte hash admitted by OUTER-ADMISSION.json via "
            "admit_outer.py; not self-compared here"
        ),
    }

    if isolation_missing:
        return _stop_receipt(
            "parent_isolation_flags_missing",
            missing_flags=isolation_missing,
            required_flags=list(REQUIRED_ISOLATION_FLAGS),
            isolation_flag_evidence={
                "-I": "sys.flags.isolated",
                "-S": "sys.flags.no_site",
                "-B": "sys.flags.dont_write_bytecode",
            },
            **base_ids,
        )

    # --- Frozen pin comparison before child admission (launcher layer) ---
    if interpreter_sha256 != pinned_interpreter:
        return _stop_receipt(
            "interpreter_sha256_mismatch",
            expected_interpreter_sha256=pinned_interpreter,
            observed_interpreter_sha256=interpreter_sha256,
            pinned_interpreter_path=PINNED_INTERPRETER_PATH,
            observed_interpreter_path=str(interpreter),
            **base_ids,
        )

    packet_pins, pin_load_reason = load_packet_pins()
    if packet_pins is None:
        return _stop_receipt(pin_load_reason or "packet_pins_unavailable", **base_ids)

    live_packet = {
        "check_d2_path_admission_fake.py": check_sha256,
        "EXPECTED-OUTPUT.json": expected_sha256,
        "INPUT-MANIFEST.json": manifest_sha256,
    }
    for name, live in live_packet.items():
        expected_pin = packet_pins[name]
        if live is None:
            return _stop_receipt(
                f"missing_packet_file_{name}",
                expected_sha256=expected_pin,
                **base_ids,
            )
        if live != expected_pin:
            return _stop_receipt(
                f"packet_sha256_mismatch_{name}",
                file=name,
                expected_sha256=expected_pin,
                observed_sha256=live,
                **base_ids,
            )

    if not CHECK.is_file():
        write_receipt(
            {
                "status": "FAIL",
                "reason": "missing_check_script",
                "check": str(CHECK),
                **base_ids,
            }
        )
        print("missing check script", file=sys.stderr)
        return 1

    expected_controls, expected_ids, expected_load_reason = _load_expected_controls()
    if expected_controls is None or expected_ids is None:
        return _stop_receipt(
            expected_load_reason or "expected_load_failed",
            **base_ids,
        )

    # Refuse stale pre-existing result before admission.
    if RESULT.is_file():
        try:
            RESULT.unlink()
        except OSError as exc:
            return _stop_receipt(
                "stale_result_unlink_failed",
                error=repr(exc),
                **base_ids,
            )

    started = time.time()
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONUSERBASE", None)

    child_argv = [
        str(interpreter),
        "-I",
        "-S",
        "-B",
        str(CHECK),
    ]
    for flag in REQUIRED_ISOLATION_FLAGS:
        if flag not in child_argv:
            return _stop_receipt(
                "child_isolation_flags_missing",
                missing_flag=flag,
                child_argv=child_argv,
                **base_ids,
            )

    # Child custody pins (receipt preparation only). Retained as soon as
    # Popen succeeds so Dex can reconcile an unconfirmed child without this
    # launcher gaining process-enumeration / retry / cleanup authority.
    child_pid: int | None = None
    child_executable: str = str(interpreter)
    child_start_timestamp: float = started

    try:
        proc = subprocess.Popen(
            child_argv,
            cwd=str(HERE),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # binary — bounded readers enforce UTF-8 decode later
        )
    except OSError as exc:
        write_receipt(
            {
                "status": "FAIL",
                "reason": "spawn_failed",
                "error": repr(exc),
                "child_pid": None,
                "child_executable": child_executable,
                "child_argv": child_argv,
                "child_start_timestamp": child_start_timestamp,
                **base_ids,
            }
        )
        return 1

    child_pid = int(proc.pid)
    child_start_timestamp = time.time()

    timed_out = False
    stdout_raw = b""
    stderr_raw = b""
    returncode: int | None = None
    # Never claim normal exit / confirmed termination until returncode is
    # non-None. Interrupt/error paths (incl. proc_wait_error with
    # capture_stop=None) must confirm explicitly before result validation.
    # Primary collection/wait error or unexpected interrupt also blocks
    # result admission/PASS even after a later exit-0 confirmation.
    termination = "termination_unconfirmed"
    termination_confirmed = False
    secondary_termination: list[dict[str, str]] = []
    primary_error: str | None = None
    capture_stop_reason: str | None = None
    interrupt_reason: str | None = None
    reader_retirement: dict[str, str] = {
        "stdout": "not_started",
        "stderr": "not_started",
    }
    result_ok = False
    result_sha256: str | None = None
    result_gate_reason: str | None = None
    result_read_bytes: int | None = None

    try:
        try:
            (
                stdout_raw,
                stderr_raw,
                timed_out,
                pe,
                capture_stop_reason,
                collect_secondary,
                reader_retirement,
                interrupt_reason,
            ) = _collect_bounded(proc, timeout=TIMEOUT_SECONDS)
            if collect_secondary:
                secondary_termination.extend(collect_secondary)
            # Preserve pe as primary on collection interrupt/error; no retry.
            if pe and primary_error is None:
                primary_error = pe
            returncode = proc.returncode
            # Any collection interrupt/error requires explicit child-exit
            # confirmation — not only timed_out / capture_stop_reason.
            collection_interrupted = (
                timed_out
                or capture_stop_reason is not None
                or interrupt_reason is not None
                or pe is not None
            )
            if collection_interrupted:
                if timed_out:
                    confirmed, rc, term = _confirm_termination(proc)
                    if confirmed:
                        termination_confirmed = True
                        termination = term
                        returncode = rc
                    else:
                        termination_confirmed = False
                        termination = "termination_unconfirmed"
                        returncode = 125
                else:
                    # Overflow / capture-error / reader-start / proc_wait_error
                    # (even when capture_stop is None because readers EOF):
                    # confirm exit without inventing timeout rc.
                    try:
                        polled = proc.poll()
                    except Exception as poll_exc:  # noqa: BLE001 — retain evidence
                        polled = None
                        _append_secondary(
                            secondary_termination,
                            kind=type(poll_exc).__name__,
                            message=str(poll_exc),
                            phase="collection_interrupt_poll",
                        )
                    if polled is not None or proc.returncode is not None:
                        termination_confirmed = True
                        if capture_stop_reason is not None:
                            termination = "child_terminated_after_capture_stop"
                        else:
                            termination = (
                                "child_terminated_after_collection_interrupt"
                            )
                        returncode = int(
                            proc.returncode
                            if proc.returncode is not None
                            else polled  # type: ignore[arg-type]
                        )
                    else:
                        termination_confirmed = False
                        termination = "termination_unconfirmed"
                        returncode = 125
            elif proc.returncode is not None:
                termination_confirmed = True
                termination = "child_exited_normally"
                returncode = int(proc.returncode)
            else:
                termination_confirmed = False
                termination = "termination_unconfirmed"
                returncode = 125
        except Exception as exc:
            # Non-timeout communicate/collection errors: preserve primary, attempt
            # kill, STOP if termination unconfirmed; no retry; no result validation.
            primary_error = f"collect_error:{type(exc).__name__}"
            try:
                proc.kill()
            except Exception as kill_exc:
                _append_secondary(
                    secondary_termination,
                    kind=type(kill_exc).__name__,
                    message=str(kill_exc),
                    phase="kill_after_collect_error",
                )
            confirmed, rc, term = _confirm_termination(proc)
            if confirmed:
                termination_confirmed = True
                termination = "child_terminated_after_collect_error"
                returncode = int(rc if rc is not None else 125)
            else:
                termination_confirmed = False
                termination = "termination_unconfirmed"
                returncode = 125
            _append_secondary(
                secondary_termination,
                kind=type(exc).__name__,
                message=str(exc),
                phase="collect",
            )
    except Exception as outer_exc:
        # Absolute last resort: never leave without a STOP receipt.
        primary_error = primary_error or f"launcher_path_error:{type(outer_exc).__name__}"
        write_receipt(
            {
                "status": "STOP",
                "reason": "launcher_unguarded_failure_contained",
                "primary_error": primary_error,
                "secondary_termination_evidence": [
                    {
                        "kind": type(outer_exc).__name__,
                        "message": str(outer_exc)[:200],
                        "phase": "launcher_guard",
                    }
                ],
                "reader_retirement": reader_retirement,
                "termination": "termination_unconfirmed",
                "termination_confirmed": False,
                "child_pid": child_pid,
                "child_executable": child_executable,
                "child_argv": child_argv,
                "child_start_timestamp": child_start_timestamp,
                **base_ids,
            }
        )
        return 125

    elapsed = time.time() - started
    stdout_raw_bytes = len(stdout_raw)
    stderr_raw_bytes = len(stderr_raw)

    # Capture overflow already detected during collection; disclose STOP.
    if capture_stop_reason is None:
        if stdout_raw_bytes > CAPTURE_STDOUT_BYTES:
            capture_stop_reason = "stdout_exceeds_capture_limit"
        elif stderr_raw_bytes > CAPTURE_STDERR_BYTES:
            capture_stop_reason = "stderr_exceeds_capture_limit"

    reader_unknown = any(
        state in _READER_UNKNOWN_STATES for state in reader_retirement.values()
    )

    stdout_retained = _clip_bytes(stdout_raw, RETAINED_STDOUT_BYTES)
    stderr_retained = _clip_bytes(stderr_raw, RETAINED_STDERR_BYTES)

    # Do not validate/read child-owned result while termination unconfirmed,
    # capture over-limit, reader retirement UNKNOWN (alive/incomplete/error),
    # or any primary collection/wait error / unexpected collection interrupt.
    # Process exit alone never authorizes skipping reader ownership checks.
    # Later exit 0 + valid-looking result file must not admit PASS when
    # primary_error / interrupt_reason remain set (stop-on-failure).
    primary_collection_failure = (
        primary_error is not None or interrupt_reason is not None
    )
    if not termination_confirmed:
        result_ok = False
        result_gate_reason = "termination_unconfirmed_skip_result"
    elif capture_stop_reason is not None or reader_unknown:
        result_ok = False
        result_gate_reason = capture_stop_reason or (
            "reader_retirement_UNKNOWN:"
            + ",".join(f"{k}={v}" for k, v in reader_retirement.items())
        )
    elif primary_collection_failure:
        result_ok = False
        result_gate_reason = (
            "primary_collection_failure_blocks_result:"
            + str(primary_error or interrupt_reason)
        )
    else:
        result_ok, result_sha256, result_gate_reason, result_read_bytes = (
            validate_result_file(
                started_at=started,
                expected_controls=expected_controls,
                expected_ids=expected_ids,
            )
        )

    if reader_unknown:
        status = "UNKNOWN"
        exit_code = 125
        if primary_error is None:
            primary_error = capture_stop_reason or result_gate_reason
    elif capture_stop_reason is not None:
        status = "STOP"
        exit_code = 125
        if primary_error is None:
            primary_error = capture_stop_reason
    elif not termination_confirmed:
        status = "STOP"
        exit_code = 125
    elif timed_out:
        status = "TIMEOUT"
        exit_code = 124
    elif primary_collection_failure:
        # pe / interrupt retained as primary; confirmed exit 0 cannot PASS.
        status = "STOP"
        exit_code = 125
        if primary_error is None:
            primary_error = interrupt_reason
    elif returncode == 0 and result_ok:
        status = "PASS"
        exit_code = 0
    elif returncode == 0 and not result_ok:
        status = "FAIL"
        exit_code = 1
        if primary_error is None:
            primary_error = result_gate_reason or "exit0_without_valid_result"
    else:
        status = "FAIL"
        exit_code = int(returncode if returncode is not None else 1)

    receipt = {
        "status": status,
        "class": "FAKE-D2-LAUNCH",
        "interpreter": str(interpreter),
        "interpreter_sha256": interpreter_sha256,
        "pinned_interpreter_sha256": pinned_interpreter,
        "interpreter_pin_matched": interpreter_sha256 == pinned_interpreter,
        "check_script": str(CHECK.name),
        "check_sha256": check_sha256,
        "launcher_sha256": launcher_sha256,
        "launcher_self_pin_compared": False,
        "expected_output_sha256": expected_sha256,
        "input_manifest_sha256": manifest_sha256,
        "packet_pins": {name: packet_pins[name] for name in PACKET_PIN_NAMES},
        "expected_control_ids_in_order": expected_ids,
        "pin_enforcement": {
            "interpreter": "launcher_pre_admission_hardcoded_pin",
            "launcher_self": "outer_OUTER-ADMISSION_via_admit_outer_not_self",
            "check_script": "launcher_pre_admission_vs_PACKET-SHA256SUMS",
            "expected_output_file": "launcher_pre_admission_vs_PACKET-SHA256SUMS",
            "input_manifest_file": "launcher_pre_admission_vs_PACKET-SHA256SUMS",
            "fixture_source_hashes": "check_script_verify_source_hashes",
            "control_inventory": (
                "check_script_enforce_expected_inventory_and_launcher_result_gate"
            ),
            "ordered_contract": (
                "EXPECTED.controls key order == EXPECTED.control_ids_in_order "
                "== result.control_ids_in_order == result.controls key order"
            ),
        },
        "cwd": str(HERE),
        "timeout_seconds": TIMEOUT_SECONDS,
        "timeout_enforced_by": (
            "invoke_d2_fake._collect_bounded.poll_wait_interrupt_on_overflow"
        ),
        "timeout_retirement_limits": {
            "child_wait_seconds": TIMEOUT_SECONDS,
            "post_kill_wait_seconds": POST_KILL_WAIT_SECONDS,
            "reader_join_seconds_each": READER_JOIN_SECONDS,
            "wait_poll_seconds": WAIT_POLL_SECONDS,
            "total_disclosed_seconds": TIMEOUT_RETIREMENT_TOTAL_SECONDS,
            "no_retry": True,
            "overflow_interrupt": (
                "kill child on observed capture overflow; do not wait out "
                "full child_wait while readers drain"
            ),
        },
        "timed_out": timed_out,
        "returncode": returncode,
        "launcher_exit_code": exit_code,
        "elapsed_seconds": round(elapsed, 3),
        "child_pid": child_pid,
        "child_executable": child_executable,
        "child_argv": child_argv,
        "child_start_timestamp": child_start_timestamp,
        "child_custody": {
            "pid": child_pid,
            "executable": child_executable,
            "argv": child_argv,
            "start_timestamp": child_start_timestamp,
            "authority": (
                "receipt_preparation_only; no process_enumeration; "
                "no_retry; no_fallback; no_new_cleanup_authority"
            ),
        },
        "isolation": {
            "required_flags": list(REQUIRED_ISOLATION_FLAGS),
            "parent_flags_verified": True,
            "parent_flag_evidence": {
                "-I": "sys.flags.isolated",
                "-S": "sys.flags.no_site",
                "-B": "sys.flags.dont_write_bytecode",
            },
            "child_argv": child_argv,
            "child_flags_verified": True,
        },
        "capture_byte_limits": {
            "stdout": CAPTURE_STDOUT_BYTES,
            "stderr": CAPTURE_STDERR_BYTES,
            "result": CAPTURE_RESULT_BYTES,
            "mechanism": (
                "bounded pipe readers during collection (chunked); "
                "over-limit → interrupt child + STOP disclosed as "
                "capture_stop_reason; reader still-live/incomplete/error → "
                "UNKNOWN; process exit alone does not imply reader EOF; "
                "not post-hoc-only after unbounded communicate; "
                "result size gate before read_bytes"
            ),
        },
        "retained_byte_limits": {
            "stdout": RETAINED_STDOUT_BYTES,
            "stderr": RETAINED_STDERR_BYTES,
            "result": RETAINED_RESULT_BYTES,
            "mechanism": (
                "clip_utf8_tails_for_receipt_disclosure_only; "
                "capture admission is separate and during-collection; "
                "stale result unlinked pre-admission"
            ),
        },
        "stdout_tail": stdout_retained,
        "stderr_tail": stderr_retained,
        "stdout_raw_bytes": stdout_raw_bytes,
        "stderr_raw_bytes": stderr_raw_bytes,
        "result_path": str(RESULT.name),
        "result_present": RESULT.is_file(),
        "result_sha256": result_sha256,
        "result_read_bytes": result_read_bytes,
        "result_gate_ok": result_ok,
        "result_gate_reason": result_gate_reason,
        "capture_stop_reason": capture_stop_reason,
        "interrupt_reason": interrupt_reason,
        "reader_retirement": reader_retirement,
        "termination": termination,
        "termination_confirmed": termination_confirmed,
        "primary_error": primary_error,
        "secondary_termination_evidence": secondary_termination or None,
        "executed_in_preparation": False,
    }
    write_receipt(receipt)

    if stdout_retained:
        sys.stdout.write(stdout_retained)
        if not stdout_retained.endswith("\n"):
            sys.stdout.write("\n")
    if stderr_retained:
        sys.stderr.write(stderr_retained)
        if not stderr_retained.endswith("\n"):
            sys.stderr.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
