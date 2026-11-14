"""Host-side supervision for native-provider prep.

PREPARED ONLY. Host Docker ownership only via immutable docker_transport.
Never imported as in-runner Docker authority. Never mounts Docker socket into runner.
No retries. Failed-container shutdown/removal separately gated by launch card.

Inherited DockerOps.run_attached is suite-specific (N06/N07 gate_pair). Provider
batches use ProviderDockerOps composition that overrides attach/report without
mutating the immutable helper bytes. Bounded owned retirement on success path only.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import sys
from pathlib import Path
from time import monotonic
from typing import Any


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


class ProviderDockerOps:
    """Compose immutable DockerOps; replace N06/N07 gate attach with NP report attach.

    When a batch intentionally reuses the old gate protocol, set
    reuse_legacy_gate_protocol=True and account for N06/N07 receipts explicitly.
    Default provider path does not assume N06/N07.
    """

    def __init__(self, inner: Any, *, reuse_legacy_gate_protocol: bool = False):
        self._inner = inner
        self.reuse_legacy_gate_protocol = reuse_legacy_gate_protocol
        self.ids = inner.ids
        self.record = inner.record
        self.ca_hash = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def run_attached(self, identifier: str, *, deadline: float) -> dict[str, Any]:
        if self.reuse_legacy_gate_protocol:
            report = self._inner.run_attached(identifier, deadline=deadline)
            self.ca_hash = self._inner.ca_hash
            return report
        # Provider path: attach runner only; no undeclared N06/N07 gate_pair protocol.
        self._inner._id(identifier)
        report = json.loads(
            self._inner._cmd(
                ["start", "--attach", identifier],
                deadline,
                cap=self._inner.c["runner_seconds"],
            )
        )
        self.ca_hash = self._inner.ca_hash
        if report.get("runtime_pins") != self._inner.c["runner_runtime_pins"]:
            raise RuntimeError("runner runtime pin mismatch")
        if report.get("ca_sha256") != self._inner.ca_hash:
            raise RuntimeError("runner public CA mismatch")
        if report.get("docker_daemon_calls", 0) != 0:
            raise RuntimeError("runner must not call Docker daemon")
        if report.get("host_docker_ownership") is not False:
            raise RuntimeError("in-runner host_docker_ownership must be false")
        self.record(
            "provider_attach_report",
            {
                "protocol": "np_runner_attach_no_n06_n07",
                "legacy_gate_reused": False,
                "case_ids": report.get("case_ids"),
            },
        )
        return report


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
                    "attach_protocol": "np_provider_no_n06_n07_default",
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


def prepare_provider_pki_caller_contract() -> dict[str, Any]:
    """Named-role contract for the authored bounded provider-PKI caller.

    Actual caller: np_runner_entry.invoke_bounded_provider_pki_recipe — directory
    ownership/mode/empty checks, exact recipe/interpreter inputs, bounded capture,
    owned process-group/readers retirement, no retry. Host admits private
    /tmp/np-provider-tls (uid 65534, 0700, empty) distinct from DB /public-ca.
    INVOKING held until launch card; PREPARED_NOT_GENERATED metadata alone is not
    runnable for a real peer. Prep must not execute this.
    """
    return {
        "tls_dir": "/tmp/np-provider-tls",
        "recipe": "payload/fixture/prepare-np-provider-tls.sh",
        "actual_caller": "np_runner_entry.invoke_bounded_provider_pki_recipe",
        "uid": 65534,
        "mode": "0700",
        "db_trust": "/public-ca",
        "generate_authorized": False,
        "child_group_readers_retirement": "C06_PATTERN_AUTHORED_UNINVOKED",
        "status": "PREPARED_NOT_GENERATED",
        "native_pki_gap": "caller_authored_invocation_held_until_launch",
    }


def plan_from_launch_config(config: dict[str, Any]) -> Plan:
    suite_seconds = config.get("suite_seconds")
    if type(suite_seconds) is not int:
        raise ValueError("suite_seconds must be frozen int on launch card")
    manifest = str(config.get("manifest_sha256", "")).strip().upper()
    return Plan(
        packet=str(config["packet"]),
        manifest_sha256=manifest,
        case_ids=tuple(config["case_ids"]),
        expected_unknown_cases=tuple(config["expected_unknown_cases"]),
        suite_seconds=suite_seconds,
        batch_id=str(config.get("batch_id", "UNFROZEN")),
    )


def main(argv: list[str] | None = None) -> int:
    """Host operator entry after Invoke-Native-Provider admission.

    Requires: --config PATH --receipt PATH --docker-config PATH
    launch_ready must already be true (operator script gates first).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 6 or args[0] != "--config" or args[2] != "--receipt" or args[4] != "--docker-config":
        print(
            "HELD: np_supervisor requires --config PATH --receipt PATH --docker-config PATH; "
            "launch card + frozen launch-config required; no Docker/ops under preparation",
            file=sys.stderr,
        )
        return 125

    config_path = Path(args[1])
    receipt_path = Path(args[3])
    docker_config_path = Path(args[5])
    if not config_path.is_file():
        raise SystemExit("STOP: launch-config missing")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("launch_ready") is not True:
        print("HELD: launch_ready is false — preparation scaffold only", file=sys.stderr)
        return 125
    if config.get("endpoint") != "unbound" and config.get("endpoint_binding_authorized") is not True:
        print("HELD: endpoint binding not authorized", file=sys.stderr)
        return 125

    plan = plan_from_launch_config(config)
    # Immutable helper import only when launch-authorized path runs.
    from docker_transport import DockerOps

    docker_config = json.loads(docker_config_path.read_text(encoding="utf-8"))

    def host_record(event: str, data: dict) -> None:
        # Temporary record sink until run_once opens exclusive receipt.
        pass

    inner = DockerOps(docker_config, host_record)
    ops = ProviderDockerOps(inner, reuse_legacy_gate_protocol=False)
    run_once(plan, ops, str(receipt_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
