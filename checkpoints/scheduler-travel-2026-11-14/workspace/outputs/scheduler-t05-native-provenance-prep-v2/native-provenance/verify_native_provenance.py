#!/usr/bin/env python3
"""Held T05 native parser provenance supervisor (AUTHORING ONLY — not invoked).

Derived from reviewed native-runtime-runner-only capability pattern. Pinned
runner image sha256:c220110432cf4adbb4005518a02808b754e0efb050b5de202e71872fecdbd2ab.

Describes identity/isolation, bounded capture, and success-only exact container
ID removal/absence verification for a later launch review. No Docker invocation
is included in preparation approval.

Concrete later-launch bounds (documented only):
- wall_clock_seconds: 300
- docker_commands_max: 24
- per_command_wait_seconds: 30 (attach/start inspect); 60 for probe attach
- stdout_capture_bytes: 262144 per command
- stderr_capture_bytes: 65536 per command
- capture_result_bytes: 524288 (complete three-file provenance envelope; STOP on overflow)
- collect_paths: exactly 3 files under /usr/local/lib/python3.12/...
- host reference raw total 164197 bytes; ~219KiB base64 estimate before metadata
- no network except loopback inside runner netns (none at create)
- readonly root + packet bind + cap_drop ALL + pids 32 + memory 256m
- success path: container removed by exact ID; ps filter shows absence
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PACKET = "scheduler-t05-native-provenance-prep-v2"

RUNNER_IMAGE = (
    "sha256:c220110432cf4adbb4005518a02808b754e0efb050b5de202e71872fecdbd2ab"
)
COLLECT_SCRIPT = HERE / "collect-parser-sources.sh"
TARGETS = (
    "/usr/local/lib/python3.12/http/client.py",
    "/usr/local/lib/python3.12/ssl.py",
    "/usr/local/lib/python3.12/email/message.py",
)

CAPTURE_STDOUT_BYTES = 262144
CAPTURE_STDERR_BYTES = 65536
CAPTURE_RESULT_BYTES = 524288
HOST_REFERENCE_RAW_TOTAL = 164197
ENVELOPE_BASE64_ESTIMATE = 219000

LIMITS = {
    "wall_clock_seconds": 300,
    "docker_commands_max": 24,
    "stdout_capture_bytes": CAPTURE_STDOUT_BYTES,
    "stderr_capture_bytes": CAPTURE_STDERR_BYTES,
    "capture_result_bytes": CAPTURE_RESULT_BYTES,
    "host_reference_raw_bytes_total": HOST_REFERENCE_RAW_TOTAL,
    "envelope_base64_estimate_bytes": ENVELOPE_BASE64_ESTIMATE,
    "per_file_max_bytes": 59093,
    "overflow_policy": "STOP_no_clip",
    "launch_ready": False,
    "execution_authorized": False,
    "invocation_included_in_prep": False,
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    spec = {
        "packet": PACKET,
        "class": "T05-NATIVE-PARSER-PROVENANCE-SUPERVISOR-HELD",
        "runner_image": RUNNER_IMAGE,
        "collect_script": str(COLLECT_SCRIPT.name),
        "collect_script_sha256": sha256_file(COLLECT_SCRIPT),
        "targets": list(TARGETS),
        "limits": LIMITS,
        "native_capture_limits_file": "Native-Capture-Limits.json",
        "isolation_profile": {
            "network_mode": "none",
            "read_only_root": True,
            "cap_drop": ["ALL"],
            "no_new_privileges": True,
            "pids_limit": 32,
            "memory_bytes": 268435456,
            "user": "65534:65534",
            "packet_mount": "ro",
        },
        "success_only_removal": {
            "require_exact_container_id_match": True,
            "verify_absence_via_ps_filter": True,
            "automatic_cleanup_on_failure": False,
        },
        "provenance_note": (
            "Captured bytes establish native layer only; do not equate to host "
            "Python311 pins used by fake framing packet."
        ),
    }
    # Held descriptor only — operator runs only after separate launch admission.
    (HERE / "SUPERVISOR-SPEC.json").write_text(
        json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
