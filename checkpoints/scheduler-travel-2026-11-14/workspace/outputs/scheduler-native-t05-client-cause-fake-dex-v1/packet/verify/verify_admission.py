#!/usr/bin/env python3
"""Outer hash admission for native-provider fake-only verification.

PREPARED ONLY. Not invoked under preparation approval.
Checks own bytes and subjects against independently root-pinned OUTER-ADMISSION.json,
then starts launch_check. Neither launcher nor this entry embeds its own raw-byte hash
as a self-waiving pin.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
OUTER_ADMISSION = HERE / "OUTER-ADMISSION.json"
VERIFY_ADMISSION = HERE / "verify_admission.py"
LAUNCHER = HERE / "launch_check.py"
REQUIRED_ISOLATION_FLAGS = ("-I", "-S", "-B")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _require_nonempty_pin(label: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"outer admission STOP: empty_or_invalid_pin:{label}")
    return value.strip().upper()


def verify_parent_isolation() -> list[str]:
    missing: list[str] = []
    if not bool(getattr(sys.flags, "isolated", 0)):
        missing.append("-I")
    if not bool(getattr(sys.flags, "no_site", 0)):
        missing.append("-S")
    if not bool(getattr(sys.flags, "dont_write_bytecode", 0)):
        missing.append("-B")
    return missing


def main() -> int:
    missing = verify_parent_isolation()
    if missing:
        print(
            f"outer admission STOP: parent_isolation_flags_missing:{missing}",
            file=sys.stderr,
        )
        return 125

    if not OUTER_ADMISSION.is_file():
        print("outer admission STOP: missing_OUTER-ADMISSION.json", file=sys.stderr)
        return 125

    try:
        admission = json.loads(OUTER_ADMISSION.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"outer admission STOP: malformed_OUTER-ADMISSION:{exc!r}", file=sys.stderr)
        return 125

    if not isinstance(admission, dict):
        print("outer admission STOP: malformed_OUTER-ADMISSION_type", file=sys.stderr)
        return 125

    if admission.get("kind") != "scheduler-native-provider-fake-outer-admission":
        print("outer admission STOP: kind_mismatch", file=sys.stderr)
        return 125

    if admission.get("launch_authorized") is not True:
        print(
            "outer admission STOP: launch_authorized_false_prep_scaffold",
            file=sys.stderr,
        )
        return 125

    pins = admission.get("pins")
    if not isinstance(pins, dict) or not pins:
        print("outer admission STOP: pins_missing_or_empty", file=sys.stderr)
        return 125

    interpreter_pin = _require_nonempty_pin(
        "interpreter_sha256", pins.get("interpreter_sha256")
    )
    launch_pin = _require_nonempty_pin(
        "launch_check_sha256", pins.get("launch_check_sha256")
    )
    check_pin = _require_nonempty_pin(
        "check_native_provider_sha256", pins.get("check_native_provider_sha256")
    )
    expected_pin = _require_nonempty_pin(
        "expected_fake_structural_sha256", pins.get("expected_fake_structural_sha256")
    )

    interpreter = Path(str(admission.get("interpreter_path", "")))
    if not interpreter.is_file():
        print("outer admission STOP: interpreter_missing", file=sys.stderr)
        return 125
    if sha256_file(interpreter) != interpreter_pin:
        print("outer admission STOP: interpreter_mismatch", file=sys.stderr)
        return 125
    if sha256_file(LAUNCHER) != launch_pin:
        print("outer admission STOP: launch_check_mismatch", file=sys.stderr)
        return 125
    if sha256_file(HERE / "check_native_provider.py") != check_pin:
        print("outer admission STOP: check_mismatch", file=sys.stderr)
        return 125
    expected_path = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
    if sha256_file(expected_path) != expected_pin:
        print("outer admission STOP: expected_mismatch", file=sys.stderr)
        return 125

    # Start launcher under same isolation; do not embed self-hash waiver.
    cmd = [str(interpreter), *REQUIRED_ISOLATION_FLAGS, str(LAUNCHER)]
    completed = subprocess.run(cmd, cwd=str(HERE), check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
