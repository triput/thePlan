"""In-runner admission/registry guards for native-provider prep.

PREPARED ONLY. Suite registry/guard only: loopback-only namespace check,
nonroot/runtime/CA/inventory admission, serial case invoke, join checks.
Does NOT create containers, mount Docker socket, or call the Docker daemon.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import threading


def run_suite(*, config, registry, runtime_pins, record_case, outer_watchdog=None):
    if set(os.listdir("/sys/class/net")) != {"lo"}:
        raise RuntimeError("loopback-only namespace required")
    if os.getuid() == 0 or any(k.upper().startswith("PG") for k in os.environ):
        raise RuntimeError("runner identity/environment refused")
    if runtime_pins != config["runtime_pins"]:
        raise RuntimeError("runner runtime mismatch")
    ca_hash = hashlib.sha256(Path("/public-ca/ca.crt").read_bytes()).hexdigest().upper()
    if ca_hash != config["ca_sha256"]:
        raise RuntimeError("CA mismatch")
    ids = config["case_ids"]
    if not ids or len(set(ids)) != len(ids) or set(registry) != set(ids):
        raise RuntimeError("incomplete or extra case registry")
    expected_unknown = config["expected_unknown_cases"]
    if not set(expected_unknown) <= set(ids):
        raise RuntimeError("unexpected fault inventory")
    # Watchdog terminates the runner on timeout; never cleans up containers.
    watchdog = threading.Timer(config["runner_seconds"], lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    passed = []
    try:
        for case_id in ids:
            result = registry[case_id]()
            if (
                result.get("case_id") != case_id
                or result.get("passed") is not True
                or result.get("skipped", False) is not False
                or result.get("workers_joined") is not True
            ):
                raise RuntimeError("case evidence mismatch")
            if result.get("expected_unknown", False) != (case_id in expected_unknown):
                raise RuntimeError("unexpected UNKNOWN classification")
            unexpected = [
                t
                for t in threading.enumerate()
                if t is not threading.main_thread()
                and t is not watchdog
                and t is not outer_watchdog
            ]
            if unexpected:
                raise RuntimeError("unjoined case worker")
            record_case(case_id, result)
            passed.append(case_id)
        return {
            "case_ids": passed,
            "passed": len(passed),
            "failed": 0,
            "skipped": 0,
            "joined_workers": True,
            "unexpected_unknown": 0,
            "expected_unknown_cases": expected_unknown,
            "runtime_pins": runtime_pins,
            "ca_sha256": ca_hash,
            "docker_daemon_calls": 0,
            "host_docker_ownership": False,
        }
    finally:
        watchdog.cancel()
        watchdog.join(timeout=1)
        if watchdog.is_alive():
            raise RuntimeError("watchdog join failure")


if __name__ == "__main__":
    sys.exit("HELD: frozen case registry and reviewed binding invocation required")
