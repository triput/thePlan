"""Host-side supervision for native-provider prep.

PREPARED ONLY. Host Docker ownership only via immutable docker_transport.
Never imported as in-runner Docker authority. Never mounts Docker socket into runner.
No retries. Failed-container shutdown/removal separately gated by launch card.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from time import monotonic


@dataclass(frozen=True)
class Plan:
    packet: str
    manifest_sha256: str
    case_ids: tuple[str, ...]
    expected_unknown_cases: tuple[str, ...]
    suite_seconds: int
    batch_id: str = "UNFROZEN"

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z0-9-]{1,80}", self.packet):
            raise ValueError("packet identity")
        if not re.fullmatch(r"[A-F0-9]{64}", self.manifest_sha256):
            raise ValueError("manifest pin")
        if (
            not self.case_ids
            or len(set(self.case_ids)) != len(self.case_ids)
            or any(not re.fullmatch(r"[A-Z][A-Z0-9_-]{1,79}", x) for x in self.case_ids)
            or not set(self.expected_unknown_cases) <= set(self.case_ids)
        ):
            raise ValueError("case inventory")
        if type(self.suite_seconds) is not int or not 1 <= self.suite_seconds <= 3600:
            raise ValueError("explicit reviewed suite deadline required")


def run_once(plan: Plan, ops, receipt_path: str) -> None:
    """Only a future explicitly approved invocation may call this function.

    ops.check_identity(id, role, deadline) must verify full ID, packet label,
    immutable image, mounts, namespace, user and all isolation constraints.
    Never resolve a mutable name for cleanup. No automatic failure-path disposal
    unless the reviewed launch card explicitly includes it.
    """
    plan.validate()
    ids: dict[str, str] = {}
    deadline = monotonic() + plan.suite_seconds
    with open(receipt_path, "x", encoding="utf-8") as receipt:

        def record(event: str, data: dict) -> None:
            receipt.write(json.dumps({"event": event, "data": data}, sort_keys=True) + "\n")
            receipt.flush()
            os.fsync(receipt.fileno())

        def call(method, *args):
            if monotonic() >= deadline:
                raise TimeoutError("suite deadline")
            result = method(*args, deadline=deadline)
            if monotonic() >= deadline:
                raise TimeoutError("deadline at operation return")
            return result

        def identity(role: str, state: str, exit_code=None) -> None:
            facts = call(ops.check_identity, ids[role], role)
            if facts["status"] != state:
                raise RuntimeError("container state mismatch")
            if exit_code is not None and facts["exit_code"] != exit_code:
                raise RuntimeError("container exit mismatch")

        try:
            record(
                "attempt",
                {
                    "packet": plan.packet,
                    "manifest": plan.manifest_sha256,
                    "batch_id": plan.batch_id,
                    "host_docker_ownership": True,
                    "runner_docker_authority": False,
                },
            )
            if call(ops.verify_inputs, plan.manifest_sha256) is not True:
                raise RuntimeError("input mismatch")
            if call(ops.verify_runtime_pins) is not True:
                raise RuntimeError("runtime mismatch")
            for role in ("database", "runner"):
                identifier = call(ops.create, role, dict(ids))
                if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{64}", identifier):
                    raise RuntimeError("creation identity UNKNOWN")
                if identifier in ids.values():
                    raise RuntimeError("duplicate container identity")
                ids[role] = identifier
                record("created", {"role": role, "id": identifier})
                identity(role, "created")
                if role == "database":
                    if call(ops.start_database, identifier) != identifier:
                        raise RuntimeError("database start mismatch")
                    identity(role, "running")
                    if call(ops.verify_fixture_ready, identifier) is not True:
                        raise RuntimeError("fixture TLS/readiness mismatch")
            report = call(ops.run_attached, ids["runner"])
            identity("runner", "exited", 0)
            if (
                report["case_ids"] != list(plan.case_ids)
                or report["passed"] != len(plan.case_ids)
                or report["skipped"] != 0
                or report["failed"] != 0
                or report["joined_workers"] is not True
                or report["unexpected_unknown"] != 0
                or report["expected_unknown_cases"] != list(plan.expected_unknown_cases)
            ):
                raise RuntimeError("case evidence mismatch")
            if call(ops.verify_inputs, plan.manifest_sha256) is not True:
                raise RuntimeError("post-run input mismatch")
            record("suite_pass", report)
            # Sole success cleanup path. No cleanup in except/finally.
            identity("runner", "exited", 0)
            if call(ops.remove_exact, ids["runner"]) != ids["runner"]:
                raise RuntimeError("runner removal mismatch")
            if call(ops.verify_absent, ids["runner"]) is not True:
                raise RuntimeError("runner absence UNKNOWN")
            record("removed", {"role": "runner", "id": ids["runner"]})
            identity("database", "running")
            if call(ops.sigint_exact, ids["database"]) != ids["database"]:
                raise RuntimeError("database signal mismatch")
            if call(ops.wait_exact, ids["database"]) != 0:
                raise RuntimeError("database shutdown mismatch")
            identity("database", "exited", 0)
            if call(ops.remove_exact, ids["database"]) != ids["database"]:
                raise RuntimeError("database removal mismatch")
            if call(ops.verify_absent, ids["database"]) is not True:
                raise RuntimeError("database absence UNKNOWN")
            record("removed", {"role": "database", "id": ids["database"]})
            record("complete", {"success": True})
        except BaseException as error:
            record(
                "stopped",
                {
                    "kind": type(error).__name__,
                    "known_ids": ids,
                    "automatic_cleanup": False,
                    "retry": False,
                    "failed_container_shutdown_gated": True,
                },
            )
            raise


if __name__ == "__main__":
    raise SystemExit(
        "HELD: np_supervisor host-side only; launch card + frozen launch-config required; "
        "no Docker/ops invocation under preparation"
    )
