"""HELD noncircular hash admission for one separately authorized framing-ack check.

The root operator wrapper checks the complete packet/runtime inventory before
Python starts. This entry checks its own bytes and five other subjects against
the independently root-pinned OUTER-ADMISSION.json, then starts the launcher.
Neither launcher nor this entry embeds its own raw-byte hash. No invocation
during preparation. Inherited subprocess wait has no independent outer timeout;
bounded check supervision belongs to the launcher, with I/O/OS latency excluded.
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
LAUNCHER = HERE / "invoke_framing_ack_fake.py"
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
        "invoke_framing_ack_fake.py",
        "check_framing_ack.py",
        "EXPECTED.json",
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
        "invoke_framing_ack_fake.py": LAUNCHER,
        "check_framing_ack.py": HERE / "check_framing_ack.py",
        "EXPECTED.json": HERE / "EXPECTED.json",
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
