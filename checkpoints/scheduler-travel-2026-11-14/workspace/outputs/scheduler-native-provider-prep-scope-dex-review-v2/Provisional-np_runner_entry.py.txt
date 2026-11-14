"""In-runner entry for native-provider prep.

PREPARED ONLY. Imports suite, binds disposable settings, typed receipt.
PKI child generation and peer bind require later launch authorization.
Unjoined/unconfirmed retirement → UNKNOWN. No Docker daemon access.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
RUNNER_CONFIG_NAME = "runner-config.json"
OUTPUT_BYTE_CAP = 1048576
REQUIRED_UID = 65534


class RunnerEntryHeld(RuntimeError):
    pass


class BoundedOutput:
    def __init__(self) -> None:
        self.length = 0
        self.sha = hashlib.sha256()

    def write(self, value: str) -> int:
        data = value.encode("utf-8", errors="replace")
        self.length += len(data)
        if self.length > OUTPUT_BYTE_CAP:
            raise RuntimeError("runner console cap")
        self.sha.update(data)
        return len(value)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def load_runner_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RunnerEntryHeld("runner-config missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("launch_ready") is not True:
        raise RunnerEntryHeld("runner-config launch_ready is false — preparation scaffold only")
    required = ("case_ids", "expected_unknown_cases", "runner_seconds", "runtime_pins")
    for key in required:
        if key not in data:
            raise RunnerEntryHeld(f"runner-config missing {key}")
    return data


def build_registry_from_suite(case_ids: list[str]) -> dict[str, Callable[[], dict[str, Any]]]:
    """Bind finite declared cases. Actual case bodies activate only under launch card."""
    # Local import keeps preparation static; suite module is inventory + oracles.
    from np_suite import registry_by_id, SuiteStop, check_oracles_immediate
    from np_auth_seed import fresh_attempt_plan, assert_plan_still_valid, PlanValidityExpired
    from np_receipts import case_result_receipt

    decls = registry_by_id(include_cf=True)
    if set(case_ids) - set(decls):
        raise RunnerEntryHeld("case_ids not in finite suite registry")

    def make_held_case(case_id: str) -> Callable[[], dict[str, Any]]:
        decl = decls[case_id]

        def _run() -> dict[str, Any]:
            raise RunnerEntryHeld(
                f"case body not authorized for execution: {case_id}; "
                f"stimulus={decl.stimulus!r}; oracles={[o.name for o in decl.oracles]}"
            )

        _run.__name__ = f"held_{case_id}"
        _run.decl = decl  # type: ignore[attr-defined]
        _run.check_oracles_immediate = check_oracles_immediate  # type: ignore[attr-defined]
        _run.fresh_attempt_plan = fresh_attempt_plan  # type: ignore[attr-defined]
        _run.assert_plan_still_valid = assert_plan_still_valid  # type: ignore[attr-defined]
        _run.PlanValidityExpired = PlanValidityExpired  # type: ignore[attr-defined]
        _run.SuiteStop = SuiteStop  # type: ignore[attr-defined]
        _run.case_result_receipt = case_result_receipt  # type: ignore[attr-defined]
        return _run

    return {case_id: make_held_case(case_id) for case_id in case_ids}


def admit_runner_identity() -> None:
    if os.getuid() != REQUIRED_UID:
        raise RunnerEntryHeld("runner uid mismatch")
    if os.getuid() == 0:
        raise RunnerEntryHeld("root refused")


def main() -> int:
    admit_runner_identity()
    config_path = ROOT / RUNNER_CONFIG_NAME
    config = load_runner_config(config_path)
    # Bound registry exists for admission; integrated_runner performs serial invoke.
    registry = build_registry_from_suite(list(config["case_ids"]))
    if set(registry) != set(config["case_ids"]):
        raise RunnerEntryHeld("registry binding mismatch")
    raise RunnerEntryHeld(
        "np_runner_entry preparation complete path refuses execution; "
        "invoke only after frozen launch card sets launch_ready and authorizes case bodies"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RunnerEntryHeld as exc:
        print(f"HELD: {exc}", file=sys.stderr)
        raise SystemExit(125)
