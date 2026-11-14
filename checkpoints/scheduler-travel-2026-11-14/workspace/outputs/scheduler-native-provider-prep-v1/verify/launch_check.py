#!/usr/bin/env python3
"""Bounded local check launcher for native-provider fake-only verification.

PREPARED ONLY. Not invoked under preparation approval.
Inherits no independent outer timeout beyond admitted bounds; I/O/OS latency excluded
from app-deadline proof. Starts check_native_provider only after admission pins match.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
OUTER_ADMISSION = HERE / "OUTER-ADMISSION.json"
CHECK = HERE / "check_native_provider.py"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
RECEIPT = HERE / "FAKE-NATIVE-PROVIDER-LAUNCH-RECEIPT.json"
REQUIRED_ISOLATION_FLAGS = ("-I", "-S", "-B")
OUTPUT_CAP = 1048576
DEFAULT_CHECK_SECONDS = 120


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
        raise SystemExit("launch_check STOP: missing OUTER-ADMISSION.json")
    data = json.loads(OUTER_ADMISSION.read_text(encoding="utf-8"))
    if data.get("kind") != "scheduler-native-provider-fake-outer-admission":
        raise SystemExit("launch_check STOP: admission kind mismatch")
    if data.get("launch_authorized") is not True:
        raise SystemExit("launch_check STOP: launch_authorized is false (prep scaffold)")
    return data


def main() -> int:
    missing = verify_parent_isolation()
    if missing:
        print(f"launch_check STOP: parent_isolation_flags_missing:{missing}", file=sys.stderr)
        return 125
    if RESULT.exists() or RECEIPT.exists():
        print("launch_check STOP: existing evidence; no replay", file=sys.stderr)
        return 125
    admission = load_admission()
    pins = admission.get("pins") or {}
    check_pin = str(pins.get("check_native_provider_sha256", "")).strip().upper()
    if not check_pin or sha256_file(CHECK) != check_pin:
        print("launch_check STOP: check pin mismatch", file=sys.stderr)
        return 125
    interpreter = Path(str(admission["interpreter_path"]))
    if sha256_file(interpreter) != str(pins.get("interpreter_sha256", "")).strip().upper():
        print("launch_check STOP: interpreter pin mismatch", file=sys.stderr)
        return 125
    seconds = int(admission.get("check_seconds", DEFAULT_CHECK_SECONDS))
    if not 1 <= seconds <= 600:
        print("launch_check STOP: check_seconds out of bounds", file=sys.stderr)
        return 125

    # Bounded local child — no Docker, no sockets beyond what the fake checker uses (none).
    env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONUTF8": "1",
    }
    cmd = [str(interpreter), *REQUIRED_ISOLATION_FLAGS, str(CHECK)]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(HERE),
            env=env,
            capture_output=True,
            timeout=seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("launch_check STOP: check timeout", file=sys.stderr)
        return 124

    stdout = completed.stdout[:OUTPUT_CAP]
    stderr = completed.stderr[:OUTPUT_CAP]
    receipt = {
        "kind": "fake-native-provider-launch-receipt",
        "check_exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest().upper(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest().upper(),
        "stdout_len": len(completed.stdout),
        "stderr_len": len(completed.stderr),
        "check_seconds_budget": seconds,
        "result_present": RESULT.is_file(),
        "prep_is_not_pass": True,
        "endpoint": "unbound",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if completed.returncode != 0:
        print(f"launch_check STOP: check exited {completed.returncode}", file=sys.stderr)
        return completed.returncode if completed.returncode else 1
    if not RESULT.is_file():
        print("launch_check STOP: missing result", file=sys.stderr)
        return 125
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
