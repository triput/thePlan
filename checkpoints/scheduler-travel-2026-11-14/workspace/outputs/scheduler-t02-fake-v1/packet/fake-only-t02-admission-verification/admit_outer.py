#!/usr/bin/env python3
"""Outer noncircular admission for the held fake-only T02 admission harness.

NOT executed during T02 admission preparation.

This file is the exact enforcing outer invocation entry. It reads the reviewed
OUTER-ADMISSION.json (external to every pinned subject) and verifies
interpreter + launcher + check + EXPECTED-OUTPUT + INPUT-MANIFEST +
PACKET-SHA256SUMS + this admit_outer script against those pins BEFORE
starting the launcher. Empty / missing pin literals refuse (no silent waive).

Noncircular scheme:
- OUTER-ADMISSION.json holds subject SHA pins; it does NOT embed its own hash.
- This script does NOT embed its own final raw-byte hash.
- Launcher does NOT embed or self-compare its own final raw-byte hash.
- Operator/reviewer verifies OUTER-ADMISSION.json bytes via the hash published
  in Verification-Commands-Held.md / packet ARTIFACT-HASHES before invoke.

Layer map (exact):
1. Outer reviewed pin file: OUTER-ADMISSION.json (operator-compared hash)
2. Outer admit: this script (admit_outer.py) — enforces layer-1 pins, then spawns
3. Launcher: invoke_t02_fake.py — interpreter hardcoded pin; packet pins
   for check/EXPECTED/INPUT-MANIFEST vs PACKET-SHA256SUMS (not launcher self);
   isolation; bounded capture-during-collection; result inventory gate
4. Check script: fixture source SHA vs INPUT-MANIFEST; exact EXPECTED inventory

Exit codes mirror launcher: 0 PASS / 1 FAIL / 124 timeout / 125 STOP.
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
ADMIT_OUTER = HERE / "admit_outer.py"
LAUNCHER = HERE / "invoke_t02_fake.py"
REQUIRED_ISOLATION_FLAGS = ("-I", "-S", "-B")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _require_nonempty_pin(label: str, value: Any) -> str:
    """Empty / whitespace / non-str pin literals must NOT silently waive."""
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(
            f"outer admission STOP: empty_or_invalid_pin:{label}"
        )
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

    pins = admission.get("pins")
    if not isinstance(pins, dict) or not pins:
        print("outer admission STOP: pins_missing_or_empty", file=sys.stderr)
        return 125

    interpreter_pin = _require_nonempty_pin(
        "interpreter_sha256", pins.get("interpreter_sha256")
    )
    subjects = pins.get("subjects")
    if not isinstance(subjects, dict) or not subjects:
        print("outer admission STOP: subjects_missing_or_empty", file=sys.stderr)
        return 125

    required_subjects = (
        "admit_outer.py",
        "invoke_t02_fake.py",
        "check_t02_admission_fake.py",
        "EXPECTED-OUTPUT.json",
        "INPUT-MANIFEST.json",
        "PACKET-SHA256SUMS.txt",
    )
    for name in required_subjects:
        _require_nonempty_pin(f"subjects.{name}", subjects.get(name))

    interpreter = Path(sys.executable).resolve()
    if not interpreter.is_file():
        print("outer admission STOP: interpreter_missing", file=sys.stderr)
        return 125
    live_interpreter = sha256_file(interpreter)
    if live_interpreter != interpreter_pin:
        print(
            "outer admission STOP: interpreter_sha256_mismatch "
            f"expected={interpreter_pin} observed={live_interpreter}",
            file=sys.stderr,
        )
        return 125

    path_map = {
        "admit_outer.py": ADMIT_OUTER,
        "invoke_t02_fake.py": LAUNCHER,
        "check_t02_admission_fake.py": HERE / "check_t02_admission_fake.py",
        "EXPECTED-OUTPUT.json": HERE / "EXPECTED-OUTPUT.json",
        "INPUT-MANIFEST.json": HERE / "INPUT-MANIFEST.json",
        "PACKET-SHA256SUMS.txt": HERE / "PACKET-SHA256SUMS.txt",
    }
    for name, path in path_map.items():
        expected = _require_nonempty_pin(f"subjects.{name}", subjects[name])
        if not path.is_file():
            print(f"outer admission STOP: missing_subject:{name}", file=sys.stderr)
            return 125
        live = sha256_file(path)
        if live != expected:
            print(
                f"outer admission STOP: subject_sha256_mismatch:{name} "
                f"expected={expected} observed={live}",
                file=sys.stderr,
            )
            return 125

    # Admission passed — spawn launcher under the same isolation flags.
    # Launcher is a separate process; it must not rely on embedding its own hash.
    child_argv = [
        str(interpreter),
        "-I",
        "-S",
        "-B",
        str(LAUNCHER),
    ]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONUSERBASE", None)
    try:
        completed = subprocess.run(child_argv, cwd=str(HERE), env=env, check=False)
    except OSError as exc:
        print(f"outer admission STOP: launcher_spawn_failed:{exc!r}", file=sys.stderr)
        return 125
    return int(completed.returncode if completed.returncode is not None else 125)


if __name__ == "__main__":
    raise SystemExit(main())
