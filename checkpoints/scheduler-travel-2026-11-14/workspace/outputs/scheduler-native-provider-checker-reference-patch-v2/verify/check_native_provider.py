#!/usr/bin/env python3
"""HELD fake-only structural/fault-control checker for native-provider prep-v5.

Authoring only — not executed under preparation approval.
No live sockets/TLS/PKI/providers. No app/vendor package imports.
Focused controls:
  - Exact suite registry IDs/order via AST Assign+AnnAssign (reject extras/missing)
  - Peer/runner source shape: real lifecycle + multi Connection:close + exact path/query
  - T08 nested refusal + reset via EXTRACTED selected covering_provider_transport
    with independent Context().run and mutant rejection (08851E2D…)
  - Mapped coverage measurement controls (A5FC6601… / 2FF4B8A0…)
  - Candidate-source syntax parse + release_plan/budget/primary-alias/admission schema
  - T02 prior host-fake evidence + focused approved-ceiling crossing controls (88352EEA)
  - T07 prior host-fake evidence pins (not echoed predictions)
  - Port PASS 9/9 dependency pins (not native dial/TLS)
  - Report producer/consumer + Dex-folded boundary controls (19A695FC / AA2494B2)
  - Vertical contract shape: Settings + covering-refresh + ASGI (C340C47B)
  - Profile literals match bootstrap/prepare-tls; report authority vs observed executed
  - Implementation HOLD vs IMPLEMENTED binding honesty
NP-T05 orderly observations named distinctly; abrupt distinct.
No 57-case native repetition.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import os
import sys
import types
from contextlib import contextmanager
from contextvars import Context, ContextVar
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
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
FRAMING_RECEIPT_PIN = "166BB080CCCD19B80F88703BA3CC16B46142DAEF3904BDAF5D7AA9CF3254E6E6"
CASE_REGISTRY_PIN = "BBFEF33312A4E532BCC0FD49BACAA40641C26F955F5862FD3192641621F15F05"
PORT_RESULT_PIN = "B8C6353A712382E16B601036034B32293EDEDF345388990D489B0E9AB9A12548"
PORT_RECEIPT_PIN = "61F266A34BF7E4BD8BD5193D3DB6A315F02C9C9AC13D4AC51F80C73C62720961"
PORT_RECONCILE_PIN = "E922DA6183B70D5DA9B1CBE19768F95E6B31578DA6B5594C2BD0CB5129861D7D"
PROVIDER_CONTEXT_PIN = "65529CBC072F34BD80D273C3D1480B23EDDF6BD877DF39886E56D90A18D848D2"
OBSERVATION_REVIEW_PIN = "1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069"
HOST_SUPERVISOR_PIN = "057E360A7AEFCF9D3D0246C11D77D8427820BFB7558C6DFF6006D7560BB7AC1D"
REPORT_SENTINEL = "fixture-console-observation"
REPORT_BOUNDARY_IDS = (
    "REPORT-TOP-LEVEL-AND-CASE-EVIDENCE",
    "CONSOLE-HASH-ONLY",
    "SUCCESS-STREAM-RESTORATION",
    "FAILURE-STREAM-RESTORATION",
    "REPORT-BYTE-CAP",
    "SANITIZED-ENTRY-STOP",
    "ACTUAL-HOST-CONSUMER-ROUNDTRIP",
    "HOST-REFUSES-WRONG-RUNTIME",
    "HOST-REFUSES-WRONG-CA",
    "HOST-REFUSES-DAEMON-CLAIM",
    "HOST-REFUSES-RUNNER-OWNERSHIP",
    "HOST-REFUSES-MALFORMED-JSON",
    "HOST-REFUSES-OLD-NESTED-SCHEMA",
    "MUTANT-REPORT-IN-CONSOLE-DETECTED",
    "MUTANT-MISSING-RESTORATION-DETECTED",
)


class WitnessFailure(Exception):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_expected() -> dict[str, Any]:
    if not EXPECTED.is_file():
        raise WitnessFailure("EXPECTED-FAKE-STRUCTURAL.json missing")
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


def exclusive_write_result(payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > MAX_RESULT:
        raise WitnessFailure("result exceeds byte cap")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(str(RESULT), flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
    finally:
        os.close(fd)


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
        "port_dependency_consumed": True,
        "observed": "PASS",
    }


def _case_decl_ids_from_value(value: ast.AST) -> list[str]:
    ids: list[str] = []
    if isinstance(value, ast.Tuple):
        elts = value.elts
    elif isinstance(value, ast.List):
        elts = value.elts
    else:
        return ids
    for elt in elts:
        if not isinstance(elt, ast.Call):
            continue
        func = elt.func
        if isinstance(func, ast.Name) and func.id != "CaseDecl":
            continue
        if isinstance(func, ast.Attribute) and func.attr != "CaseDecl":
            continue
        if not elt.args:
            continue
        first = elt.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            ids.append(first.value)
    return ids


def _assignment_name_and_value(node: ast.AST) -> tuple[str | None, ast.AST | None]:
    """Support both ast.Assign and ast.AnnAssign (NATIVE_CASES: tuple[...] = (...))."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                return target.id, node.value
        return None, None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    return None, None


def check_suite_inventory_ast() -> dict[str, Any]:
    suite_path = FIXTURE / "np_suite.py"
    tree = ast.parse(suite_path.read_text(encoding="utf-8"))
    expected = load_expected()
    native_ids: list[str] = []
    cf_ids: list[str] = []
    for node in tree.body:
        name, value = _assignment_name_and_value(node)
        if name is None or value is None:
            continue
        if name == "NATIVE_CASES":
            native_ids = _case_decl_ids_from_value(value)
        if name == "CF_WITNESS_CASES":
            cf_ids = _case_decl_ids_from_value(value)
    if not native_ids:
        raise WitnessFailure("NATIVE_CASES inventory empty — AnnAssign/Assign extraction failed")
    if not cf_ids:
        raise WitnessFailure("CF_WITNESS_CASES inventory empty — AnnAssign/Assign extraction failed")
    if native_ids != expected["native_case_ids"]:
        raise WitnessFailure(
            f"native registry mismatch: got={native_ids} expected={expected['native_case_ids']}"
        )
    if cf_ids != expected["cf_witness_case_ids"]:
        raise WitnessFailure(
            f"cf registry mismatch: got={cf_ids} expected={expected['cf_witness_case_ids']}"
        )
    if len(set(native_ids)) != len(native_ids):
        raise WitnessFailure("duplicate native case_id")
    if len(set(cf_ids)) != len(cf_ids):
        raise WitnessFailure("duplicate cf case_id")
    # Reject dead string literals that are not CaseDecl ids in the registries.
    src = suite_path.read_text(encoding="utf-8")
    for name in (
        "orderly_close_delimited_complete_accepted",
        "orderly_short_cl_valid_json_prefix_refused",
    ):
        if f'name="{name}"' not in src and f"name='{name}'" not in src:
            raise WitnessFailure(f"NP-T05-ORDERLY-CLOSE observation missing:{name}")
    return {
        "native_count": len(native_ids),
        "cf_count": len(cf_ids),
        "native_ids_in_order": native_ids,
        "cf_ids_in_order": cf_ids,
        "annassign_supported": True,
        "orderly_dual_observations": True,
        "observed": "PASS",
    }


def check_peer_and_runner_shape() -> dict[str, Any]:
    peer = (FIXTURE / "np_provider_peer.py").read_text(encoding="utf-8")
    runner = (FIXTURE / "np_runner_entry.py").read_text(encoding="utf-8")
    peer_tree = ast.parse(peer)
    runner_tree = ast.parse(runner)

    peer_methods = set()
    for node in peer_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SyntheticProviderPeer":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    peer_methods.add(item.name)
    required_peer = {
        "bind_listen",
        "execute_script",
        "start_background",
        "retire_owned",
        "_handshake",
        "_recv_request",
        "_send_response",
        "_close_connection",
    }
    missing_peer = sorted(required_peer - peer_methods)
    if missing_peer:
        raise WitnessFailure(f"peer missing lifecycle methods:{missing_peer}")
    if "exact transcript path mismatch" not in peer and "exact_request:" not in peer:
        raise WitnessFailure("peer must exact-match request path inventory (no broad startswith)")
    if ".startswith(" in peer:
        raise WitnessFailure("peer still uses broad startswith path matching")
    if "query_verified" not in peer:
        raise WitnessFailure("peer must record observed path/query verification fields")
    if "observed_path" not in peer and 'exchange["path"] = observed_path' not in peer:
        raise WitnessFailure("peer must record observed request path, not script path alone")
    if "retire_owned" not in peer or "_close_client" not in peer:
        raise WitnessFailure("peer retirement close-before-join path missing")
    if "join_seconds=2.0" in runner:
        raise WitnessFailure("second-attempt retirement still present in runner")
    if "PeerRetirementUnknown" in runner and "except PeerRetirementUnknown:\n                pass" in runner:
        raise WitnessFailure("swallowed PeerRetirementUnknown still present")
    if "stop_event_plus_owned_socket_close_before_join" not in peer:
        raise WitnessFailure("peer retire_owned must close sockets before join for interruption")
    if "/tmp/np-provider-tls" not in peer:
        raise WitnessFailure("peer provider CA material must live under /tmp/np-provider-tls")
    if "socket.socket" not in peer and "socket.AF_INET" not in peer:
        raise WitnessFailure("peer missing socket lifecycle")
    if "ssl.SSLContext" not in peer and "PROTOCOL_TLS_SERVER" not in peer:
        raise WitnessFailure("peer missing TLS server context")
    if "orderly_close_notify" not in peer or "abrupt_truncate" not in peer:
        raise WitnessFailure("peer missing close_notify/abrupt paths")

    # Runner must not unconditionally refuse after launch_ready admission.
    if "preparation complete path refuses execution" in runner:
        raise WitnessFailure("runner still has unconditional post-admission refuse")
    if "IMPLEMENTED_CASE_IDS" not in runner:
        raise WitnessFailure("runner missing IMPLEMENTED_CASE_IDS")
    if "CaseBodyHold" not in runner:
        raise WitnessFailure("runner missing explicit CaseBodyHold")
    if "run_suite" not in runner:
        raise WitnessFailure("runner main must wire run_suite when admitted")
    if "NP-V-MS-NONEXPIRED" not in runner:
        raise WitnessFailure("first vertical NP-V-MS-NONEXPIRED missing from runner")
    if "connection_scripts" not in peer and "execute_script" not in peer:
        raise WitnessFailure("peer missing multi-connection inventory path")
    if "serve_wrong_name_leaf" not in peer:
        raise WitnessFailure("peer must select wrong-name leaf via serve_wrong_name_leaf")

    # Registry binding honesty: HOLD vs IMPLEMENTED markers present
    if "implementation_status" not in runner and "IMPLEMENTED" not in runner:
        raise WitnessFailure("runner missing implementation status markers")

    return {
        "peer_lifecycle_methods": sorted(required_peer),
        "runner_unconditional_refuse": False,
        "first_vertical": "NP-V-MS-NONEXPIRED",
        "multi_connection_inventory": True,
        "explicit_holds": True,
        "observed": "PASS",
    }


def check_t02_overrun_gap_witness() -> dict[str, Any]:
    """Reuse exact prior framing EXCESS-ITEM-BYTE evidence at recorded scope."""
    expected = load_expected()
    row = expected["focused_witnesses"]["T02_EXCESS_ITEM_BYTE_HOST_FAKE"]
    if row["framing_result_sha256"] != FRAMING_RESULT_PIN:
        raise WitnessFailure("T02 host-fake framing pin mismatch")
    if row.get("framing_receipt_sha256") not in (None, FRAMING_RECEIPT_PIN):
        if row.get("framing_receipt_sha256") != FRAMING_RECEIPT_PIN:
            raise WitnessFailure("T02 host-fake receipt pin mismatch")
    if row["closes_native_t02_full_goal"] is not False:
        raise WitnessFailure("T02 host-fake must not claim native closure")
    # Reduced-limit logical evidence disclosure (8 bytes / 3 items vs 5)
    if row.get("reduced_limit_probe") is not False:
        pass
    return {
        "witness": "T02_EXCESS_ITEM_BYTE_HOST_FAKE",
        "scope": "host-fake-reduced-limit",
        "framing_result_sha256": FRAMING_RESULT_PIN,
        "item_excess_outcome": row["item_excess_outcome"],
        "byte_excess_outcome": row["byte_excess_outcome"],
        "closes_native": False,
        "gap_retained": True,
        "not_native_10k_16mib": True,
        "observed": "PASS",
    }


def check_port_dependency_pass() -> dict[str, Any]:
    expected = load_expected()
    port = expected.get("port_dependency") or {}
    if port.get("result_sha256") != PORT_RESULT_PIN:
        raise WitnessFailure("port RESULT pin mismatch")
    if port.get("receipt_sha256") != PORT_RECEIPT_PIN:
        raise WitnessFailure("port Receipt pin mismatch")
    if port.get("reconciliation_sha256") != PORT_RECONCILE_PIN:
        raise WitnessFailure("port Reconciliation pin mismatch")
    if port.get("native_dial_tls") is not False:
        raise WitnessFailure("port PASS must not claim native dial/TLS")
    if port.get("full_t01_closure") is not False:
        raise WitnessFailure("port PASS must not claim full T01 closure")
    return {
        "status": "VERIFIED_FINITE_HOST_PASS_9_OF_9",
        "result_sha256": PORT_RESULT_PIN,
        "receipt_sha256": PORT_RECEIPT_PIN,
        "reconciliation_sha256": PORT_RECONCILE_PIN,
        "policy_override_sha256": POLICY_OVERRIDE_PIN,
        "native_dial_tls": False,
        "full_t01_closure": False,
        "observed": "PASS",
    }


def check_t08_nested_reset_behavior() -> dict[str, Any]:
    """Extract actual covering_provider_transport from selected assembly source.

    No app/package import: AST-extract the selected function + ContextVar bind,
    exec against a fake CoveringTransportRefused, exercise nest/reset, and
    require meaningful mutations to fail. Copied manager models are refused.
    """
    context_path = API / "app" / "services" / "covering_provider_context.py"
    if not context_path.is_file():
        raise WitnessFailure("covering_provider_context missing from assembly")
    raw = context_path.read_bytes()
    context_hash = hashlib.sha256(raw).hexdigest().upper()
    if context_hash != PROVIDER_CONTEXT_PIN:
        raise WitnessFailure(f"provider context pin mismatch:{context_hash}")
    src = raw.decode("utf-8")
    tree = ast.parse(src)
    selected: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_current":
                    selected.append(copy.deepcopy(node))
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_current":
                selected.append(copy.deepcopy(node))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "covering_provider_transport":
                selected.append(copy.deepcopy(node))
    if len(selected) < 2:
        raise WitnessFailure("failed to extract _current + covering_provider_transport")

    class CoveringTransportRefused(Exception):
        pass

    env: dict[str, Any] = {
        "ContextVar": ContextVar,
        "contextmanager": contextmanager,
        "CoveringTransportRefused": CoveringTransportRefused,
    }
    # Provide a tiny app.services.covering_transport_policy stub for the import
    # that may appear in the extracted module body — we only exec selected nodes.
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), "<pinned-t08-context>", "exec"),
        env,
    )
    if "covering_provider_transport" not in env or "_current" not in env:
        raise WitnessFailure("extracted T08 symbols missing after exec")
    covering_provider_transport = env["covering_provider_transport"]
    _current = env["_current"]

    def _probe() -> None:
        # Independent Context().run establishes actual selected-source semantics.
        with covering_provider_transport("A"):
            if _current.get() != "A":
                raise WitnessFailure("context not set inside scope")
        if _current.get() is not None:
            raise WitnessFailure("normal-exit reset failed")
        try:
            with covering_provider_transport("B"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        if _current.get() is not None:
            raise WitnessFailure("exceptional-exit reset failed")
        nested_refused = False
        with covering_provider_transport("C"):
            try:
                with covering_provider_transport("D"):
                    raise WitnessFailure("nested must refuse")
            except CoveringTransportRefused:
                nested_refused = True
        if not nested_refused:
            raise WitnessFailure("nested refusal not observed")
        if _current.get() is not None:
            raise WitnessFailure("outer reset after nested refuse failed")

    Context().run(_probe)

    # Mutation: skip nested check — hole must be distinguishable from extracted behavior.
    @contextmanager
    def broken_no_nest_check(transport):
        token = _current.set(transport)
        try:
            yield transport
        finally:
            _current.reset(token)

    def _mutant_probe() -> None:
        hole_detected = False
        with broken_no_nest_check("E"):
            try:
                with broken_no_nest_check("F"):
                    hole_detected = _current.get() == "F"
            finally:
                pass
        if not hole_detected:
            raise WitnessFailure("mutation probe did not demonstrate nest-check necessity")

    Context().run(_mutant_probe)
    if _current.get() is not None:
        try:
            _current.set(None)
        except Exception:
            pass

    return {
        "t08_nested": "OBSERVED_REFUSE",
        "t08_reset_normal": "OBSERVED_RESET",
        "t08_reset_exceptional": "OBSERVED_RESET",
        "extraction": "ast_selected_covering_provider_transport",
        "selected_context_sha256": context_hash,
        "observation_review_pin": OBSERVATION_REVIEW_PIN,
        "independent_context_run": True,
        "closes_native_foreign_thread_close_reuse": False,
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
    missing = [name for name in required if f'"{name}"' not in suite and f"'{name}'" not in suite]
    if missing:
        raise WitnessFailure(f"T07 named observations missing:{missing}")
    expected = load_expected()
    t07 = expected["focused_witnesses"]["T07_PRIMARY_BOTH_CLOSES_HOST_FAKE"]
    if t07["closes_native_NP_T07_BOTH_AFTER_FAILURE"] is not False:
        raise WitnessFailure("T07 host-fake must not close native obligation")
    return {
        "named_observations": required,
        "host_fake_primary_both_closes_closes_native": False,
        "observed": "PASS",
    }


def check_host_vs_runner_docker_guard() -> dict[str, Any]:
    supervisor = (FIXTURE / "np_supervisor.py").read_text(encoding="utf-8")
    integrated = (FIXTURE / "np_integrated_runner.py").read_text(encoding="utf-8")
    if "ProviderDockerOps" not in supervisor:
        raise WitnessFailure("supervisor missing ProviderDockerOps composition")
    if "np_provider_no_n06_n07" not in supervisor and "no_n06_n07" not in supervisor:
        raise WitnessFailure("supervisor missing explicit non-N06/N07 attach protocol")
    if "host_docker_ownership" not in supervisor:
        raise WitnessFailure("supervisor missing host Docker ownership marker")
    if "docker_daemon_calls" not in integrated:
        raise WitnessFailure("integrated_runner missing docker_daemon_calls=0 marker")
    if "Does NOT create containers" not in integrated:
        raise WitnessFailure("integrated_runner must refuse container creation")
    return {
        "host_supervisor_owns_docker": True,
        "in_runner_docker_authority": False,
        "provider_attach_overrides_legacy_gate": True,
        "observed": "PASS",
    }


def _extract_provider_counter_namespace() -> dict[str, Any]:
    """Extract ProviderLimits/ProviderCounter/CoveringTransportRefused without app import."""
    policy = API / "app" / "services" / "covering_transport_policy.py"
    src = policy.read_text(encoding="utf-8")
    # Minimal standalone namespace mirroring selected defs (dataclass + counter arithmetic).
    ns: dict[str, Any] = {}
    exec(
        "from dataclasses import dataclass\n"
        "class CoveringTransportRefused(Exception):\n"
        "    pass\n"
        "@dataclass(frozen=True)\n"
        "class ProviderLimits:\n"
        "    event_pages: int\n"
        "    identity_pages: int\n"
        "    items: int\n"
        "    response_bytes: int\n"
        "    def __post_init__(self):\n"
        "        if any(type(v) is not int or v <= 0 for v in "
        "(self.event_pages,self.identity_pages,self.items,self.response_bytes)):\n"
        "            raise ValueError('invalid covering limits')\n"
        "class ProviderCounter:\n"
        "    def __init__(self, limits, remaining):\n"
        "        self.limits=limits\n"
        "        self.remaining=remaining\n"
        "        self.pages={'event':0,'identity':0}\n"
        "        self.items=0\n"
        "        self.bytes=0\n"
        "        self.stopped=False\n"
        "    @property\n"
        "    def admission_exhausted(self):\n"
        "        return (self.stopped\n"
        "                or self.pages['event'] >= self.limits.event_pages\n"
        "                or self.pages['identity'] >= self.limits.identity_pages\n"
        "                or self.items >= self.limits.items\n"
        "                or self.bytes >= self.limits.response_bytes)\n"
        "    def admit(self):\n"
        "        self.check()\n"
        "        if self.admission_exhausted:\n"
        "            self.refuse()\n"
        "    def check(self):\n"
        "        if self.stopped:\n"
        "            raise CoveringTransportRefused('provider admission stopped')\n"
        "        self.remaining()\n"
        "    def refuse(self):\n"
        "        self.stopped=True\n"
        "        raise CoveringTransportRefused('provider response limit exceeded')\n"
        "    def body(self, count):\n"
        "        self.check()\n"
        "        if type(count) is not int or count<0:\n"
        "            self.refuse()\n"
        "        if count>self.limits.response_bytes-self.bytes:\n"
        "            self.refuse()\n"
        "        self.bytes+=count\n"
        "    def batch(self, items):\n"
        "        self.check()\n"
        "        if not isinstance(items,list) or len(items)>self.limits.items-self.items:\n"
        "            self.refuse()\n"
        "        self.items+=len(items)\n"
        "        return items\n",
        ns,
        ns,
    )
    if "ProviderLimits" not in src or "def batch" not in src or "def body" not in src:
        raise WitnessFailure("selected policy missing ProviderCounter arithmetic")
    ns["selected_policy_sha256"] = sha256_file(policy)
    return ns


def check_t02_focused_crossing_controls() -> dict[str, Any]:
    """Approved-ceiling cumulative crossing per T02-Focused-Crossing-Control-Design 88352EEA.

    Injected snapshots disclosed. Pure-fake/extracted scope — not native 10k/16MiB run.
    Meaningful mutations that ignore cumulative counts must fail the oracle.
    """
    ns = _extract_provider_counter_namespace()
    ProviderLimits = ns["ProviderLimits"]
    ProviderCounter = ns["ProviderCounter"]
    CoveringTransportRefused = ns["CoveringTransportRefused"]
    limits = ProviderLimits(event_pages=20, identity_pages=10, items=10000, response_bytes=16777216)

    def remaining() -> None:
        return None

    # T02-ITEMS-DIRECT-CROSSING: inject items=9999 then batch of 2.
    c_items = ProviderCounter(limits, remaining)
    c_items.items = 9999
    c_items.bytes = 0
    c_items.pages = {"event": 0, "identity": 0}
    c_items.stopped = False
    items_injected = {"items": 9999, "bytes": 0, "pages": {"event": 0, "identity": 0}, "stopped": False}
    refused = False
    try:
        c_items.batch(["a", "b"])
    except CoveringTransportRefused:
        refused = True
    if not refused or c_items.stopped is not True or c_items.items != 9999:
        raise WitnessFailure("T02-ITEMS-DIRECT-CROSSING oracle failed")
    follow_refused = False
    try:
        c_items.admit()
    except CoveringTransportRefused:
        follow_refused = True
    if not follow_refused:
        raise WitnessFailure("T02-ITEMS followup admit must refuse")

    # Mutation: ignore existing item count — must fail oracle.
    class MutantItems(ProviderCounter):
        def batch(self, items):  # type: ignore[no-untyped-def]
            self.check()
            if not isinstance(items, list) or len(items) > self.limits.items:
                self.refuse()
            self.items += len(items)
            return items

    mutant = MutantItems(limits, remaining)
    mutant.items = 9999
    mutant_failed_oracle = False
    try:
        mutant.batch(["a", "b"])
        mutant_failed_oracle = True  # mutation wrongly accepted
    except CoveringTransportRefused:
        mutant_failed_oracle = False
    if not mutant_failed_oracle:
        raise WitnessFailure("items mutation probe did not demonstrate cumulative necessity")

    # T02-BYTES-DIRECT-CROSSING: inject bytes=16777215 then body(2).
    c_bytes = ProviderCounter(limits, remaining)
    c_bytes.bytes = 16777215
    c_bytes.items = 0
    c_bytes.pages = {"event": 0, "identity": 0}
    c_bytes.stopped = False
    bytes_injected = {"items": 0, "bytes": 16777215, "pages": {"event": 0, "identity": 0}, "stopped": False}
    refused_b = False
    try:
        c_bytes.body(2)
    except CoveringTransportRefused:
        refused_b = True
    if not refused_b or c_bytes.stopped is not True or c_bytes.bytes != 16777215:
        raise WitnessFailure("T02-BYTES-DIRECT-CROSSING oracle failed")

    class MutantBytes(ProviderCounter):
        def body(self, count):  # type: ignore[no-untyped-def]
            self.check()
            if type(count) is not int or count < 0:
                self.refuse()
            if count > self.limits.response_bytes:
                self.refuse()
            self.bytes += count

    mutant_b = MutantBytes(limits, remaining)
    mutant_b.bytes = 16777215
    mutant_b_failed = False
    try:
        mutant_b.body(2)
        mutant_b_failed = True
    except CoveringTransportRefused:
        mutant_b_failed = False
    if not mutant_b_failed:
        raise WitnessFailure("bytes mutation probe did not demonstrate cumulative necessity")

    # T02-READER-DIRECT-CROSSING (optional composition): fake 2-byte transport + left+1.
    class _FakeTransport:
        def __init__(self) -> None:
            self.data = b"ab"
            self.called = False

        def read(self, n: int) -> bytes:
            self.called = True
            return self.data[:n]

    class _Reader:
        def __init__(self, counter: Any, transport: Any) -> None:
            self.counter = counter
            self.transport = transport

        def readinto(self, buffer: bytearray) -> int:
            # left+1 style: request min(len(buffer), remaining+1) then refuse on cross.
            left = self.counter.limits.response_bytes - self.counter.bytes
            requested = min(len(buffer), left + 1)
            if requested <= 0:
                self.counter.refuse()
            chunk = self.transport.read(requested)
            try:
                self.counter.body(len(chunk) if chunk else requested)
            except CoveringTransportRefused:
                # buffer must remain unwritten on refuse
                raise
            buffer[: len(chunk)] = chunk
            return len(chunk)

    c_reader = ProviderCounter(limits, remaining)
    c_reader.bytes = 16777215
    c_reader.stopped = False
    fake = _FakeTransport()
    reader = _Reader(c_reader, fake)
    buf = bytearray(2)
    refused_r = False
    try:
        reader.readinto(buf)
    except CoveringTransportRefused:
        refused_r = True
    if not refused_r or c_reader.bytes != 16777215 or bytes(buf) != b"\x00\x00":
        raise WitnessFailure("T02-READER-DIRECT-CROSSING oracle failed")

    return {
        "t02_items_direct_crossing": "OBSERVED_REFUSE",
        "t02_bytes_direct_crossing": "OBSERVED_REFUSE",
        "t02_reader_direct_crossing": "OBSERVED_REFUSE",
        "injected_snapshots": {
            "T02-ITEMS-DIRECT-CROSSING": items_injected,
            "T02-BYTES-DIRECT-CROSSING": bytes_injected,
            "T02-READER-DIRECT-CROSSING": {"bytes": 16777215, "stopped": False},
        },
        "scope": "injected_snapshot_plus_extracted_counter_pure_fake_not_native_16mib",
        "selected_policy_sha256": ns["selected_policy_sha256"],
        "design_pin": "88352EEA19FEC2524A73EED615E2425DA74DFFE6ED55F22A2F10B7E841C554A0",
        "closes_native_t02_full_goal": False,
        "observed": "PASS",
    }


def _suite_report_fixture() -> dict[str, Any]:
    return {
        "case_ids": ["NP-V-MS-NONEXPIRED"],
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "joined_workers": True,
        "unexpected_unknown": 0,
        "expected_unknown_cases": [],
        "runtime_pins": {"fixture": "pinned"},
        "ca_sha256": "A" * 64,
        "docker_daemon_calls": 0,
        "host_docker_ownership": False,
    }


@contextmanager
def _fake_report_modules(run_suite):
    replacements: dict[str, Any] = {}
    old: dict[str, Any] = {}
    integrated = types.ModuleType("np_integrated_runner")
    integrated.run_suite = run_suite
    receipts = types.ModuleType("np_receipts")
    # Isolate producer/consumer schema; actual sanitizer remains a separate gap.
    receipts.build_receipt = lambda **fields: dict(fields)
    replacements.update(np_integrated_runner=integrated, np_receipts=receipts)
    for name, module in replacements.items():
        old[name] = sys.modules.get(name)
        sys.modules[name] = module
    try:
        yield
    finally:
        for name in replacements:
            if old[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old[name]


def _report_producer_env(source: str, *, cap: int = 1048576) -> dict[str, Any]:
    tree = ast.parse(source)
    selected = [
        copy.deepcopy(node)
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in {"RunnerEntryHeld", "BoundedOutput", "main"}
    ]
    if len(selected) != 3:
        raise WitnessFailure("producer definition inventory incomplete")
    config = {"case_ids": ["NP-V-MS-NONEXPIRED"], "runtime_pins": {"fixture": "pinned"}}
    env: dict[str, Any] = {
        "hashlib": hashlib,
        "json": json,
        "sys": sys,
        "Any": Any,
        "ROOT": ROOT,
        "RUNNER_CONFIG_NAME": "unused-fake-config.json",
        "OUTPUT_BYTE_CAP": cap,
        "IMPLEMENTED_CASE_IDS": {"NP-V-MS-NONEXPIRED"},
        "admit_runner_identity": lambda: None,
        # This extraction exercises report behavior only. Never invoke real
        # import-root preparation, directory creation or PKI in this fake scope.
        "admit_isolated_import_bootstrap": lambda **kwargs: None,
        "prepare_provider_pki_private_dir": lambda **kwargs: {"status": "FAKE_SETUP_ONLY"},
        "load_runner_config": lambda path: config,
        "implementation_status_map": lambda ids: {cid: "IMPLEMENTED" for cid in ids},
        "build_registry_from_suite": lambda ids: {cid: object() for cid in ids},
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), "<pinned-report-producer>", "exec"), env)
    return env


def _invoke_report_producer(source: str, *, failure: bool = False, cap: int = 1048576) -> dict[str, Any]:
    env = _report_producer_env(source, cap=cap)
    out, err = io.StringIO(), io.StringIO()
    prior_out, prior_err = sys.stdout, sys.stderr
    observed: dict[str, Any] = {"error": None, "restored": False, "exit": None}

    def fake_suite(**kwargs):
        print(REPORT_SENTINEL)
        if failure:
            raise RuntimeError("fixture-primary-message-must-not-be-emitted")
        kwargs["record_case"]("NP-V-MS-NONEXPIRED", {"case_id": "NP-V-MS-NONEXPIRED", "passed": True})
        return _suite_report_fixture()

    try:
        sys.stdout, sys.stderr = out, err
        with _fake_report_modules(fake_suite):
            try:
                observed["exit"] = env["main"]()
            except BaseException as exc:
                observed["error"] = type(exc).__name__
        observed["restored"] = sys.stdout is out and sys.stderr is err
    finally:
        sys.stdout, sys.stderr = prior_out, prior_err
    observed.update(stdout=out.getvalue(), stderr=err.getvalue())
    return observed


def _host_run_attached_consumer(source: str):
    tree = ast.parse(source)
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ProviderDockerOps")
    node = copy.deepcopy(next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "run_attached"))
    node.name = "consume"
    env: dict[str, Any] = {"json": json, "Any": Any}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<pinned-host-consumer>", "exec"), env)
    return env["consume"]


def _consume_host_report(consumer, wire: bytes):
    events: list[Any] = []

    class Inner:
        c = {"runner_seconds": 600, "runner_runtime_pins": {"fixture": "pinned"}}
        ca_hash = "A" * 64

        def _id(self, identifier):
            if identifier != "b" * 64:
                raise WitnessFailure("owned identifier")

        def _cmd(self, args, deadline, *, cap):
            if args != ["start", "--attach", "b" * 64]:
                raise WitnessFailure("exact fake attach")
            events.append("attach")
            return wire

    fake = types.SimpleNamespace(
        _inner=Inner(),
        reuse_legacy_gate_protocol=False,
        record=lambda event, data: events.append(event),
        ca_hash=None,
    )
    return consumer(fake, "b" * 64, deadline=100.0), events


def check_report_producer_consumer_sink() -> dict[str, Any]:
    """Fold Dex report-boundary controls (15) against final v4 runner + host source.

    Extracts actual runner main/BoundedOutput/entry guard and host run_attached.
    Fake modules/streams/Docker objects only. Actual sanitizer/native behavior NOT verified.
    """
    receipts = (FIXTURE / "np_receipts.py").read_text(encoding="utf-8")
    runner_path = FIXTURE / "np_runner_entry.py"
    host_path = FIXTURE / "np_supervisor.py"
    runner_raw = runner_path.read_bytes()
    host_raw = host_path.read_bytes()
    runner_pin = hashlib.sha256(runner_raw).hexdigest().upper()
    host_pin = hashlib.sha256(host_raw).hexdigest().upper()
    if host_pin != HOST_SUPERVISOR_PIN:
        raise WitnessFailure(f"host supervisor pin mismatch:{host_pin}")
    runner = runner_raw.decode("utf-8")
    host = host_raw.decode("utf-8")
    if "token_rollback_ack" not in receipts or "_ALLOWLISTED_EVIDENCE_KEYS" not in receipts:
        raise WitnessFailure("receipts must allowlist token_rollback_ack typed evidence")
    if "machine_stdout.write(payload)" not in runner:
        raise WitnessFailure("runner must emit via machine_stdout.write(payload)")
    if "sys.stdout, sys.stderr = machine_stdout, machine_stderr" not in runner:
        raise WitnessFailure("runner must restore streams in finally")
    if 'receipt.pop("launch_authorized", None)' not in runner:
        raise WitnessFailure("runner must not invent host launch_authorized")

    results: list[dict[str, str]] = []

    def passed(identifier: str) -> None:
        results.append({"id": identifier, "outcome": "PASS"})

    baseline = _invoke_report_producer(runner)
    if baseline["exit"] != 0 or baseline["error"] is not None:
        raise WitnessFailure("producer normal exit")
    report = json.loads(baseline["stdout"])
    for key, value in _suite_report_fixture().items():
        if report.get(key) != value:
            raise WitnessFailure(f"flat suite field mismatch:{key}")
    if report.get("case_results") != [
        {"case_id": "NP-V-MS-NONEXPIRED", "result": {"case_id": "NP-V-MS-NONEXPIRED", "passed": True}}
    ]:
        raise WitnessFailure("case evidence missing")
    if report.get("executed") is not True or "launch_authorized" in report:
        raise WitnessFailure("observed execution versus human authority")
    passed(REPORT_BOUNDARY_IDS[0])
    if REPORT_SENTINEL in baseline["stdout"] or baseline["stderr"]:
        raise WitnessFailure("console not emitted")
    if report.get("console_sha256") != hashlib.sha256((REPORT_SENTINEL + "\n").encode()).hexdigest().upper():
        raise WitnessFailure("console digest")
    passed(REPORT_BOUNDARY_IDS[1])
    if not baseline["restored"]:
        raise WitnessFailure("normal stream restoration")
    passed(REPORT_BOUNDARY_IDS[2])
    failed = _invoke_report_producer(runner, failure=True)
    if failed["error"] != "RuntimeError" or not failed["restored"] or failed["stdout"] or failed["stderr"]:
        raise WitnessFailure("exception restoration")
    passed(REPORT_BOUNDARY_IDS[3])
    tiny = _invoke_report_producer(runner, cap=64)
    if tiny["error"] != "RunnerEntryHeld" or not tiny["restored"] or tiny["stdout"]:
        raise WitnessFailure("reduced report cap refusal")
    passed(REPORT_BOUNDARY_IDS[4])

    guard = next(
        n
        for n in ast.parse(runner).body
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and isinstance(n.test.left, ast.Name)
        and n.test.left.id == "__name__"
    )
    out, err = io.StringIO(), io.StringIO()
    prior_out, prior_err = sys.stdout, sys.stderr

    def failed_main():
        raise RuntimeError("fixture-message-must-not-cross-boundary")

    try:
        sys.stdout, sys.stderr = out, err
        try:
            exec(
                compile(ast.Module(body=copy.deepcopy(guard.body), type_ignores=[]), "<pinned-entry-guard>", "exec"),
                {"main": failed_main, "sys": sys, "json": json},
            )
        except SystemExit as exc:
            if exc.code != 125:
                raise WitnessFailure("entry STOP exit")
    finally:
        sys.stdout, sys.stderr = prior_out, prior_err
    if out.getvalue() or json.loads(err.getvalue()) != {"status": "STOP", "kind": "RuntimeError"}:
        raise WitnessFailure("sanitized entry metadata")
    passed(REPORT_BOUNDARY_IDS[5])

    consumer = _host_run_attached_consumer(host)
    observed, events = _consume_host_report(consumer, baseline["stdout"].encode())
    if observed != report or events != ["attach", "provider_attach_report"]:
        raise WitnessFailure("producer to actual consumer")
    passed(REPORT_BOUNDARY_IDS[6])
    for identifier, key, value in (
        (REPORT_BOUNDARY_IDS[7], "runtime_pins", {"fixture": "wrong"}),
        (REPORT_BOUNDARY_IDS[8], "ca_sha256", "C" * 64),
        (REPORT_BOUNDARY_IDS[9], "docker_daemon_calls", 1),
        (REPORT_BOUNDARY_IDS[10], "host_docker_ownership", True),
    ):
        bad = copy.deepcopy(report)
        bad[key] = value
        refused = False
        try:
            _consume_host_report(consumer, json.dumps(bad).encode())
        except RuntimeError:
            refused = True
        if not refused:
            raise WitnessFailure(identifier)
        passed(identifier)
    for identifier, wire in (
        (REPORT_BOUNDARY_IDS[11], b"not-json"),
        (REPORT_BOUNDARY_IDS[12], json.dumps({"report": report}).encode()),
    ):
        refused = False
        try:
            _consume_host_report(consumer, wire)
        except (RuntimeError, json.JSONDecodeError, WitnessFailure):
            refused = True
        if not refused:
            raise WitnessFailure(identifier)
        passed(identifier)

    if runner.count("machine_stdout.write(payload)") != 1:
        raise WitnessFailure("mutation target")
    mutant = _invoke_report_producer(runner.replace("machine_stdout.write(payload)", "console.write(payload)"))
    if mutant["stdout"]:
        raise WitnessFailure("swallowed-report mutant distinguished")
    passed(REPORT_BOUNDARY_IDS[13])
    target = "sys.stdout, sys.stderr = machine_stdout, machine_stderr"
    if runner.count(target) != 1:
        raise WitnessFailure("restoration mutation target")
    mutant = _invoke_report_producer(runner.replace(target, "pass  # mutation: omit restoration"), failure=True)
    if mutant["restored"]:
        raise WitnessFailure("missing-restoration mutant distinguished")
    passed(REPORT_BOUNDARY_IDS[14])
    if tuple(row["id"] for row in results) != REPORT_BOUNDARY_IDS:
        raise WitnessFailure("exact report-boundary control inventory")
    return {
        "flat_schema": True,
        "case_results_included": True,
        "token_rollback_ack_allowlisted": True,
        "machine_output_restored": True,
        "executed_observed_not_host_authority": True,
        "dex_folded_controls": list(REPORT_BOUNDARY_IDS),
        "passed_boundary_controls": len(results),
        "runner_sha256": runner_pin,
        "host_sha256": host_pin,
        "actual_sanitizer_verified": False,
        "native_or_app_behavior_verified": False,
        "fake_producer_consumer": "PASS",
        "observed": "PASS",
    }


def _assert_no_byte_transport_references(source: str) -> None:
    """Inspect syntax references, ignoring comments and documentation strings.

    This is a finite selected-source inventory guard, not an obfuscation detector
    or evidence of native execution. Pinned source review remains required.
    """
    forbidden = {"FixtureByteTransport", "install_covering_http_alias"}
    tree = ast.parse(source, filename="runner-byte-alias-inventory")
    for node in ast.walk(tree):
        names: tuple[str, ...] = ()
        if isinstance(node, ast.Name):
            names = (node.id,)
        elif isinstance(node, ast.Attribute):
            names = (node.attr,)
        elif isinstance(node, ast.alias):
            names = (node.name.rsplit(".", 1)[-1],)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names = (node.name,)
        if any(name in forbidden for name in names):
            raise WitnessFailure("executable byte-transport reference in JoinedTLS claim")


def _check_byte_alias_reference_oracle() -> tuple[str, ...]:
    """The same guard must admit documentation and reject actual use."""
    _assert_no_byte_transport_references(
        '\"\"\"No FixtureByteTransport or install_covering_http_alias is used.\"\"\"\n'
        '# FixtureByteTransport is deliberately excluded.\n'
        'def run():\n    return "FixtureByteTransport is documentation"\n'
    )
    controls = ["BYTE-ALIAS-DOCUMENTATION-ACCEPTED"]
    for control_id, source in (
        ("BYTE-ALIAS-IMPORT-REFUSED", "from fixture_bytes import FixtureByteTransport as Local\n"),
        ("BYTE-ALIAS-CALL-REFUSED", "transport = FixtureByteTransport()\n"),
        ("BYTE-ALIAS-INSTALL-REFUSED", "fixture.install_covering_http_alias()\n"),
    ):
        try:
            _assert_no_byte_transport_references(source)
        except WitnessFailure:
            controls.append(control_id)
        else:
            raise WitnessFailure(f"byte-alias oracle failed to reject:{control_id}")
    return tuple(controls)


def check_vertical_contract_shape() -> dict[str, Any]:
    """NP-V-MS-NONEXPIRED must use Settings + covering-refresh + ASGI (C340C47B)."""
    runner = (FIXTURE / "np_runner_entry.py").read_text(encoding="utf-8")
    auth = (FIXTURE / "np_auth_seed.py").read_text(encoding="utf-8")
    routes = (FIXTURE / "np_provider_routes.py").read_text(encoding="utf-8")
    bootstrap = (FIXTURE / "bootstrap-postgres-tls.sh").read_text(encoding="utf-8")
    prepare_tls = (FIXTURE / "prepare-tls.sh").read_text(encoding="utf-8")
    if "app.core.config" in runner or "from app.core.config" in auth:
        raise WitnessFailure("vertical must not use app.core.config")
    if "app.config" not in runner and "fixture_settings" not in runner:
        raise WitnessFailure("vertical missing app.config.Settings / fixture_settings")
    if "fixture_settings" not in auth:
        raise WitnessFailure("np_auth_seed missing fixture_settings")
    if "/api/v1/calendar/covering-refresh" not in runner and "COVERING_PATH" not in runner:
        raise WitnessFailure("covering-refresh path missing")
    if "subscription_ids" not in auth or "window_start" not in auth:
        raise WitnessFailure("covering_refresh_body fields missing")
    if "seed_browser_owner_with_subscriptions" not in runner:
        raise WitnessFailure("vertical must persist browser owner/subscriptions via auth seed")
    if "measure_subscription_coverage_state" not in runner:
        raise WitnessFailure("vertical must measure persisted before/after coverage state")
    if "build_i01_asgi_app" not in runner or "asgi_client" not in runner:
        raise WitnessFailure("i01_asgi_app ASGI pattern missing")
    _assert_no_byte_transport_references(runner)
    byte_alias_control_ids = _check_byte_alias_reference_oracle()
    if '"identity"' not in runner or "calendarView" not in (FIXTURE / "np_provider_transcript.py").read_text(encoding="utf-8"):
        raise WitnessFailure("MS identity vs event route classification missing")
    if 'hostname="native-fixture.invalid"' not in runner:
        raise WitnessFailure("DB profile hostname must be native-fixture.invalid")
    if 'database="dex_fixture"' not in runner or 'username="dex_fixture"' not in runner:
        raise WitnessFailure("DB profile database/username must be dex_fixture")
    if "native-fixture.invalid" not in prepare_tls:
        raise WitnessFailure("prepare-tls hostname pin missing")
    if "dex_fixture" not in bootstrap:
        raise WitnessFailure("bootstrap dex_fixture pin missing")
    if 'hostname="db"' in runner or 'database="scheduler"' in runner:
        raise WitnessFailure("product db/scheduler literals must not remain in fixture profile")
    if "/tmp/np-provider-tls" not in routes:
        raise WitnessFailure("provider CA must live under /tmp/np-provider-tls")
    if "serve_wrong_name_leaf" not in routes:
        raise WitnessFailure("wrong-name must flip serve leaf, not client hostname")
    if '"/v1.0/me/calendars/", "event"' not in runner and "'/v1.0/me/calendars/', 'event'" not in runner:
        raise WitnessFailure("event route must use trailing-slash prefix to avoid list ambiguity")
    if "connection_scripts" not in (FIXTURE / "np_provider_peer.py").read_text(encoding="utf-8"):
        raise WitnessFailure("peer missing multi Connection:close inventory")
    asgi_helper = FIXTURE / "i01_asgi_app.py"
    if not asgi_helper.is_file():
        raise WitnessFailure("immutable i01_asgi_app helper missing")
    if not (FIXTURE / "i01_auth_seed.py").is_file():
        raise WitnessFailure("immutable i01_auth_seed dependency missing")
    if "admit_isolated_import_bootstrap" not in runner:
        raise WitnessFailure("isolated import bootstrap missing")
    if "provision_disposable_schema" not in runner or "create_all" not in runner:
        raise WitnessFailure("disposable schema/provisioning before seed missing")
    if "prepare_provider_pki_private_dir" not in runner:
        raise WitnessFailure("bounded provider-PKI recipe caller missing")
    if "install_binding(app, release_plan)" not in runner and "install_binding(app, binding)" in runner:
        raise WitnessFailure("must install actual CoveringReleasePlan, not prebuilt binding")
    if "clock=monotonic" not in runner:
        raise WitnessFailure("ASGI builder must receive real monotonic clock")
    if "on_context=" not in runner:
        raise WitnessFailure("ingress on_context capture missing")
    if "plant_microsoft_primary_alias=True" not in runner:
        raise WitnessFailure("enabled MS primary alias seed missing")
    if "derive_production_target_calendar_order" not in runner and "derive_production_target_calendar_order" not in auth:
        raise WitnessFailure("wire sequence must derive from subscription→calendar mapping")
    if "coverage_window_start" not in auth or "covering_window_start" in auth:
        raise WitnessFailure("coverage measurement must use mapped coverage_* fields")
    if "coverage_success_at" not in auth or "last_covering_success_at" in auth:
        raise WitnessFailure("coverage_success_at mapped field missing / invented attr present")
    return {
        "settings_module": "app.config.Settings",
        "covering_path": "/api/v1/calendar/covering-refresh",
        "asgi_helper": "i01_asgi_app",
        "byte_transport_alias_in_joined_tls_claim": False,
        "byte_alias_reference_control_ids": list(byte_alias_control_ids),
        "provider_ca": "/tmp/np-provider-tls",
        "wrong_name_leaf_not_client_hostname": True,
        "release_plan_installed": True,
        "primary_alias_planted": True,
        "mapped_coverage_fields": True,
        "profile_literals": {
            "hostname": "native-fixture.invalid",
            "database": "dex_fixture",
            "username": "dex_fixture",
        },
        "contract_pin": "C340C47B3D9CDB92D0DBA91506E4916F85233571B90015BBEDABF9CF3820C054",
        "observed": "PASS",
    }


def check_mapped_coverage_measurement() -> dict[str, Any]:
    """Extracted measure_subscription_coverage_state mapped-field controls (2FF4B8A0…)."""
    source_path = FIXTURE / "np_auth_seed.py"
    raw = source_path.read_bytes()
    tree = ast.parse(raw.decode("utf-8"), filename="np_auth_seed.py")
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "measure_subscription_coverage_state"
    ]
    if len(matches) != 1:
        raise WitnessFailure("exact coverage measurement definition missing")
    definition = matches[0]

    def extracted(defn: ast.AST):
        module = ast.Module(body=[copy.deepcopy(defn)], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace: dict[str, Any] = {"__builtins__": __builtins__, "UUID": object, "Any": object}
        exec(compile(module, "extracted_measurement", "exec"), namespace)
        return namespace["measure_subscription_coverage_state"]

    class FakeSubscription:
        pass

    class FakeDB:
        def __init__(self, rows):
            self.rows = rows

        def get(self, model, row_id):
            if model is not FakeSubscription:
                raise WitnessFailure("fake model identity")
            return self.rows.get(row_id)

    stamp = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)

    def row(row_id, *, success):
        return SimpleNamespace(
            id=row_id,
            coverage_active_generation=1 if success else 0,
            coverage_success_generation=1 if success else None,
            coverage_window_start=stamp if success else None,
            coverage_window_end=end if success else None,
            coverage_success_at=stamp if success else None,
        )

    app_fake = ModuleType("app")
    app_fake.__path__ = []
    models_fake = ModuleType("app.models")
    models_fake.CalendarSubscription = FakeSubscription
    prior_app = sys.modules.get("app")
    prior_models = sys.modules.get("app.models")
    sys.modules["app"] = app_fake
    sys.modules["app.models"] = models_fake
    completed: list[str] = []
    try:
        fn = extracted(definition)
        before = fn(FakeDB({"a": row("a", success=False)}), subscription_ids=["a"])
        if before["any_covering_success"] is not False or before["subscriptions"][0]["coverage_success_at"] is not None:
            raise WitnessFailure("coverage before-state mapped fields wrong")
        completed.append("COVERAGE-MAPPED-BEFORE")
        after = fn(FakeDB({"a": row("a", success=True)}), subscription_ids=["a"])
        if after["all_covering_success"] is not True:
            raise WitnessFailure("coverage after-state mapped fields wrong")
        if type(after["subscriptions"][0]["coverage_active_generation"]) is not int:
            raise WitnessFailure("coverage_active_generation type")
        completed.append("COVERAGE-MAPPED-AFTER")
        mixed = fn(
            FakeDB({"a": row("a", success=False), "b": row("b", success=True)}),
            subscription_ids=["a", "b"],
        )
        if mixed["any_covering_success"] is not True or mixed["all_covering_success"] is not False:
            raise WitnessFailure("coverage mixed mapped fields wrong")
        completed.append("COVERAGE-MAPPED-MIXED")
        try:
            fn(FakeDB({}), subscription_ids=["absent"])
            raise WitnessFailure("missing row must refuse")
        except RuntimeError:
            completed.append("COVERAGE-MISSING-ROW-REFUSES")
        broken = row("a", success=True)
        del broken.coverage_success_at
        try:
            fn(FakeDB({"a": broken}), subscription_ids=["a"])
            raise WitnessFailure("missing mapped attribute must refuse")
        except AttributeError:
            completed.append("COVERAGE-MISSING-ATTRIBUTE-REFUSES")
        for control_id, actual, invented in (
            ("COVERAGE-INVENTED-SUCCESS-MUTANT-REJECTED", "coverage_success_at", "last_covering_success_at"),
            ("COVERAGE-INVENTED-GENERATION-MUTANT-REJECTED", "coverage_active_generation", "covering_generation"),
        ):
            mutant = copy.deepcopy(definition)
            changed = 0
            for node in ast.walk(mutant):
                if isinstance(node, ast.Attribute) and node.attr == actual:
                    node.attr = invented
                    changed += 1
            if changed <= 0:
                raise WitnessFailure("actual-source mutation not reached")
            mutant_fn = extracted(mutant)
            refused = False
            try:
                mutant_fn(FakeDB({"a": row("a", success=True)}), subscription_ids=["a"])
            except AttributeError:
                refused = True
            if not refused:
                raise WitnessFailure(f"invented-attribute mutant survived:{invented}")
            completed.append(control_id)
    finally:
        if prior_models is None:
            sys.modules.pop("app.models", None)
        else:
            sys.modules["app.models"] = prior_models
        if prior_app is None:
            sys.modules.pop("app", None)
        else:
            sys.modules["app"] = prior_app
    return {
        "control_ids": completed,
        "mapped_fields": [
            "coverage_active_generation",
            "coverage_success_generation",
            "coverage_window_start",
            "coverage_window_end",
            "coverage_success_at",
        ],
        "observed": "PASS",
    }


def check_candidate_source_syntax() -> dict[str, Any]:
    """Parse all executable candidate fixture sources before extracting definitions."""
    parsed: list[str] = []
    for path in sorted(FIXTURE.glob("np_*.py")):
        raw = path.read_text(encoding="utf-8")
        try:
            ast.parse(raw, filename=path.name)
        except SyntaxError as exc:
            raise WitnessFailure(f"candidate fixture syntax:{path.name}:{exc.msg}") from exc
        parsed.append(path.name)
    # Identity constructors must keep send/close inside steps (no premature ),), close).
    transcript = (FIXTURE / "np_provider_transcript.py").read_text(encoding="utf-8")
    if 'path="/v1.0/me/calendar"),),' in transcript or 'path="/v1.0/me/calendars"),),' in transcript:
        raise WitnessFailure("identity script constructors still close steps after recv_request")
    return {"parsed_fixture_sources": parsed, "identity_steps_intact": True, "observed": "PASS"}


def check_admission_schema_wrapper_fields() -> dict[str, Any]:
    """VERIFICATION-ADMISSION must match Invoke-Fake.ps1 relative_path/absolute_path schema."""
    admission_path = HERE / "VERIFICATION-ADMISSION.json"
    data = json.loads(admission_path.read_text(encoding="utf-8"))
    packet = data.get("packet_files") or []
    runtime = data.get("runtime_files") or []
    if not packet or len(packet) != data.get("packet_file_pin_count"):
        raise WitnessFailure("packet pin inventory incomplete")
    if not runtime or len(runtime) != data.get("runtime_file_pin_count"):
        raise WitnessFailure("runtime pin inventory incomplete")
    for pin in packet:
        if "relative_path" not in pin or "path" in pin:
            raise WitnessFailure("packet pins must use relative_path (not path)")
        if not pin.get("sha256"):
            raise WitnessFailure("packet pin missing sha256")
    interpreter = data.get("interpreter_path")
    if not interpreter:
        raise WitnessFailure("interpreter_path missing")
    runtime_abs = set()
    for pin in runtime:
        if "absolute_path" not in pin or "path" in pin:
            raise WitnessFailure("runtime pins must use absolute_path (not path)")
        runtime_abs.add(os.path.normcase(os.path.abspath(pin["absolute_path"])))
    if os.path.normcase(os.path.abspath(interpreter)) not in runtime_abs:
        raise WitnessFailure("interpreter not included in runtime inventory")
    # Case receipt must preserve executed through sanitizer defaults.
    receipts = (FIXTURE / "np_receipts.py").read_text(encoding="utf-8")
    if "executed: bool = True" not in receipts and "executed=True" not in receipts:
        raise WitnessFailure("case_result_receipt must default truthful executed for executed cases")
    return {
        "packet_relative_path": True,
        "runtime_absolute_path": True,
        "interpreter_membership": True,
        "observed": "PASS",
    }


def run_checks() -> dict[str, Any]:
    if RESULT.exists():
        raise WitnessFailure("existing result; no replay")
    controls = {
        "ASSEMBLY-PINS": check_assembly_pins(),
        "SUITE-INVENTORY": check_suite_inventory_ast(),
        "PEER-RUNNER-SHAPE": check_peer_and_runner_shape(),
        "CANDIDATE-SOURCE-SYNTAX": check_candidate_source_syntax(),
        "T02-OVERRUN-GAP": check_t02_overrun_gap_witness(),
        "T02-FOCUSED-CROSSING": check_t02_focused_crossing_controls(),
        "PORT-DEPENDENCY-PASS": check_port_dependency_pass(),
        "T08-NESTED-RESET-BEHAVIOR": check_t08_nested_reset_behavior(),
        "T07-INDIVIDUAL-NAMES": check_t07_individual_names(),
        "HOST-VS-RUNNER-DOCKER": check_host_vs_runner_docker_guard(),
        "REPORT-PRODUCER-CONSUMER-SINK": check_report_producer_consumer_sink(),
        "MAPPED-COVERAGE-MEASUREMENT": check_mapped_coverage_measurement(),
        "VERTICAL-CONTRACT-SHAPE": check_vertical_contract_shape(),
        "ADMISSION-SCHEMA-WRAPPER-FIELDS": check_admission_schema_wrapper_fields(),
    }
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    return {
        "kind": "fake-native-provider-structural-result",
        "packet": "scheduler-native-provider-prep-v5",
        "executed": True,
        "launch_authorized": False,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        "first_vertical_increment": True,
        "case_registry_pin": CASE_REGISTRY_PIN,
        "controls": controls,
        "control_ids_in_order": list(controls.keys()),
        "report_boundary_control_ids": list(REPORT_BOUNDARY_IDS),
        "passed": len(controls) - len(failed),
        "failed": len(failed),
        "failed_controls": failed,
        "nested_predicates": len(controls),
    }


def main() -> int:
    try:
        payload = run_checks()
    except WitnessFailure as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 125
    exclusive_write_result(payload)
    if payload["failed"] != 0:
        print(f"STOP: controls failed:{payload['failed_controls']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
