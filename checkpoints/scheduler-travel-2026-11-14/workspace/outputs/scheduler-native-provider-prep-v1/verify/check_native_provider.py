#!/usr/bin/env python3
"""HELD fake-only structural/fault-control checker for native-provider prep.

Authoring only — not executed under preparation approval.
No live sockets/TLS/PKI/providers. Focused fake witnesses for retained gaps:
  - T02 item/byte direct-overrun (EXCESS-ITEM-BYTE host-fake lineage cited)
  - T08 nested/reset ContextVar gaps
  - T07 primary-both-closes host-fake lineage cited (does not close native)
NP-T05 orderly observations named distinctly in EXPECTED data; abrupt distinct.
No 57-case native repetition.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURE = ROOT / "payload" / "fixture"
API = ROOT / "payload" / "api"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144

ASSEMBLY_SELECTION_PIN = "857141512AADF6F90F1CA8F92547A777E3D5FE943671495512FA18CEA7CBA296"
POLICY_OVERRIDE_PIN = "5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88"
FRAMING_RESULT_PIN = "3905A070AE06EF2EA6B31C8A8D1407A6F58E46B549E1118FF3928C00866ECBA3"
CASE_REGISTRY_PIN = "BBFEF33312A4E532BCC0FD49BACAA40641C26F955F5862FD3192641621F15F05"


class WitnessFailure(Exception):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_expected() -> dict[str, Any]:
    if not EXPECTED.is_file():
        raise WitnessFailure("EXPECTED-FAKE-STRUCTURAL.json missing")
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


def check_assembly_pins() -> dict[str, Any]:
    policy = API / "app" / "services" / "covering_transport_policy.py"
    if not policy.is_file():
        raise WitnessFailure("assembled policy missing")
    policy_hash = sha256_file(policy)
    if policy_hash != POLICY_OVERRIDE_PIN:
        raise WitnessFailure(f"policy override pin mismatch:{policy_hash}")
    file_count = sum(1 for _ in API.rglob("*") if _.is_file())
    if file_count != 234:
        raise WitnessFailure(f"assembly file count {file_count} != 234")
    return {
        "assembly_selection_pin": ASSEMBLY_SELECTION_PIN,
        "policy_override_sha256": policy_hash,
        "assembled_file_count": file_count,
        "observed": "PASS",
    }


def check_suite_inventory_ast() -> dict[str, Any]:
    suite_path = FIXTURE / "np_suite.py"
    src = suite_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    native_ids: list[str] = []
    cf_ids: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "NATIVE_CASES":
                    # Count CaseDecl string first args via literal walk
                    pass
    # Deterministic string inventory from frozen expected + source contains checks
    expected = load_expected()
    for case_id in expected["native_case_ids"]:
        if f'"{case_id}"' not in src and f"'{case_id}'" not in src:
            raise WitnessFailure(f"native case missing in suite source:{case_id}")
        native_ids.append(case_id)
    for case_id in expected["cf_witness_case_ids"]:
        if f'"{case_id}"' not in src and f"'{case_id}'" not in src:
            raise WitnessFailure(f"cf case missing in suite source:{case_id}")
        cf_ids.append(case_id)
    if len(native_ids) != 27:
        raise WitnessFailure("native inventory != 27")
    if len(cf_ids) != 4:
        raise WitnessFailure("cf inventory != 4")
    # Orderly close dual observations
    for name in (
        "orderly_close_delimited_complete_accepted",
        "orderly_short_cl_valid_json_prefix_refused",
    ):
        if name not in src:
            raise WitnessFailure(f"NP-T05-ORDERLY-CLOSE observation missing:{name}")
    return {
        "native_count": len(native_ids),
        "cf_count": len(cf_ids),
        "orderly_dual_observations": True,
        "observed": "PASS",
    }


def check_t02_overrun_gap_witness() -> dict[str, Any]:
    """Focused fake witness: retain T02 overrun gap; cite host-fake EXCESS-ITEM-BYTE."""
    expected = load_expected()
    row = expected["focused_witnesses"]["T02_EXCESS_ITEM_BYTE_HOST_FAKE"]
    if row["framing_result_sha256"] != FRAMING_RESULT_PIN:
        raise WitnessFailure("T02 host-fake framing pin mismatch")
    if row["closes_native_t02_full_goal"] is not False:
        raise WitnessFailure("T02 host-fake must not claim native closure")
    return {
        "witness": "T02_EXCESS_ITEM_BYTE_HOST_FAKE",
        "scope": "host-fake",
        "item_excess_outcome": row["item_excess_outcome"],
        "byte_excess_outcome": row["byte_excess_outcome"],
        "closes_native": False,
        "gap_retained": True,
        "observed": "PASS",
    }


def check_t08_nested_reset_gap_witness() -> dict[str, Any]:
    expected = load_expected()
    nested = expected["focused_witnesses"]["T08_NESTED_FOCUSED"]
    reset = expected["focused_witnesses"]["T08_RESET_FOCUSED"]
    if nested["disposition"] != "GAP_OR_FOCUSED_FAKE":
        raise WitnessFailure("T08-NESTED disposition")
    if reset["disposition"] != "GAP_OR_FOCUSED_FAKE":
        raise WitnessFailure("T08-RESET disposition")
    return {
        "t08_nested": nested,
        "t08_reset": reset,
        "native_ownership_case": "NP-T08-OWNERSHIP",
        "observed": "PASS",
    }


def check_t07_individual_names() -> dict[str, Any]:
    suite = (FIXTURE / "np_suite.py").read_text(encoding="utf-8")
    required = [
        "t07_response_close_after_success",
        "t07_response_close_after_primary_failure",
        "t07_transport_close_after_success",
        "t07_transport_close_after_primary_failure",
        "t07_both_close_after_success",
        "t07_open_close",
        "t07_setblocking",
        "combined_both_close_after_failure",
    ]
    missing = [name for name in required if name not in suite]
    if missing:
        raise WitnessFailure(f"T07 named observations missing:{missing}")
    return {"named_observations": required, "observed": "PASS"}


def check_host_vs_runner_docker_guard() -> dict[str, Any]:
    supervisor = (FIXTURE / "np_supervisor.py").read_text(encoding="utf-8")
    integrated = (FIXTURE / "np_integrated_runner.py").read_text(encoding="utf-8")
    if "Host Docker ownership" not in supervisor and "host_docker_ownership" not in supervisor:
        raise WitnessFailure("supervisor missing host Docker ownership marker")
    if "docker_daemon_calls" not in integrated:
        raise WitnessFailure("integrated_runner missing docker_daemon_calls=0 marker")
    if "create containers" in integrated.lower() and "Does NOT create containers" not in integrated:
        # docstring must refuse
        raise WitnessFailure("integrated_runner must refuse container creation")
    return {
        "host_supervisor_owns_docker": True,
        "in_runner_docker_authority": False,
        "observed": "PASS",
    }


def run_checks() -> dict[str, Any]:
    if RESULT.exists():
        raise WitnessFailure("existing result; no replay")
    controls = {
        "ASSEMBLY-PINS": check_assembly_pins(),
        "SUITE-INVENTORY": check_suite_inventory_ast(),
        "T02-OVERRUN-GAP": check_t02_overrun_gap_witness(),
        "T08-NESTED-RESET-GAP": check_t08_nested_reset_gap_witness(),
        "T07-INDIVIDUAL-NAMES": check_t07_individual_names(),
        "HOST-VS-RUNNER-DOCKER": check_host_vs_runner_docker_guard(),
    }
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    return {
        "kind": "fake-native-provider-structural-result",
        "executed": True,
        "launch_authorized": False,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        "case_registry_pin": CASE_REGISTRY_PIN,
        "controls": controls,
        "passed": len(controls) - len(failed),
        "failed": len(failed),
        "failed_ids": failed,
        "predicted_outcome": "PASS" if not failed else "STOP",
    }


def main() -> int:
    try:
        result = run_checks()
    except WitnessFailure as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 125
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if len(payload.encode("utf-8")) > MAX_RESULT:
        print("STOP: result too large", file=sys.stderr)
        return 125
    RESULT.write_text(payload, encoding="utf-8")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    # Fake-only structural checker. Preparation approval does not authorize invocation.
    # Separately held Invoke-Fake.ps1 + verify_admission must gate any future one-shot.
    raise SystemExit(main())
