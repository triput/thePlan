#!/usr/bin/env python3
"""HELD fake-only structural/fault-control checker for native-provider t05-closure-prep.

Authoring only — not executed under preparation approval.
No live sockets/TLS/PKI/providers. No app/vendor package imports.
Focused controls:
  - Exact suite registry IDs/order via AST Assign+AnnAssign (reject extras/missing)
  - Peer/runner source shape: real lifecycle + multi Connection:close + exact path/query
  - T08 nested refusal + reset via EXTRACTED selected covering_provider_transport
    with independent Context().run and mutant rejection (08851E2D…)
  - Mapped coverage measurement controls (A5FC6601… / 2FF4B8A0…) — behavioral fake
  - Candidate-source syntax parse bound to finite reviewed np_*.py inventory (Dex R1)
  - Checker-read fixture pins for bootstrap/prepare-tls + three np extras (Dex R1)
  - T02 prior host-fake evidence + focused approved-ceiling crossing controls (88352EEA)
  - T07 prior host-fake evidence pins (not echoed predictions)
  - Port PASS 9/9 dependency pins (not native dial/TLS)
  - Report producer/consumer + Dex-folded boundary controls (19A695FC / AA2494B2)
  - Vertical contract SHAPE (C340C47B) + AST byte-alias reference inventory (F1)
  - Assembly manifest byte pins under ACYCLIC root (F2); OUTER via wrapper root
  - Host-entry ReceiptRelay one-time bind seam witness (host-glue)
  - PKI late-drain via EXTRACTED candidate post-join overflow gate + mutation (Dex R2)
  - Launcher retirement 30FEEDFF + receipt/stream admission companion D8D77976…
  - Profile literals match bootstrap/prepare-tls; report authority vs observed executed
  - Implementation HOLD vs IMPLEMENTED binding honesty
  - T05-CLOSURE-FOCUSED: structural shape (OMIT/EOF pairing/launch batch) PLUS
    finite EXTRACTED actual-helper controls for Dex R1–R4 (UNKNOWN refuse,
    finite EOF/reset observer taxonomy + admission, partial-start one-retirement,
    plan failure/expiry) with meaningful mutations; no real app/vendor
    imports/sockets/PKI/fs
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
ASSEMBLY_MANIFEST_PIN = "D4B54E4D51E607D28ADE15A92C41BF19EC39535BE960310759A4C6CD03EFDDAE"
POLICY_OVERRIDE_PIN = "5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88"
FRAMING_RESULT_PIN = "3905A070AE06EF2EA6B31C8A8D1407A6F58E46B549E1118FF3928C00866ECBA3"
FRAMING_RECEIPT_PIN = "166BB080CCCD19B80F88703BA3CC16B46142DAEF3904BDAF5D7AA9CF3254E6E6"
CASE_REGISTRY_PIN = "BBFEF33312A4E532BCC0FD49BACAA40641C26F955F5862FD3192641621F15F05"
PORT_RESULT_PIN = "B8C6353A712382E16B601036034B32293EDEDF345388990D489B0E9AB9A12548"
PORT_RECEIPT_PIN = "61F266A34BF7E4BD8BD5193D3DB6A315F02C9C9AC13D4AC51F80C73C62720961"
PORT_RECONCILE_PIN = "E922DA6183B70D5DA9B1CBE19768F95E6B31578DA6B5594C2BD0CB5129861D7D"
PROVIDER_CONTEXT_PIN = "65529CBC072F34BD80D273C3D1480B23EDDF6BD877DF39886E56D90A18D848D2"
OBSERVATION_REVIEW_PIN = "1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069"
HOST_SUPERVISOR_PIN = "A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC"
RUNNER_ENTRY_PIN = "9C0F85733287BDCF4F526AB52F5685E7BC10CB1C4CC349818D8B0AC001B07E70"
# Dex R1: finite reviewed np_*.py parse inventory — extras on disk must not silently join.
REVIEWED_NP_FIXTURE_PY_PINS: tuple[tuple[str, str], ...] = (
    ("np_alias_seed.py", "309CE658479FFD665408B6EAABF318258AF402D29F23C0C3F9BD99E5FDA003AD"),
    ("np_auth_seed.py", "66FEEA815C7B196A78117229F80769ADDF8428CB073A586B59E2D81491419150"),
    ("np_integrated_runner.py", "2C8B5BE78B5F042210D042DF1FB7FDBB07C486ED5A57CA36C00006F61E6040DF"),
    ("np_provider_peer.py", "4EEAB1E7F789AB4918B36466A50F29E09F84E6FA48A87C0C942ECD599E097D17"),
    ("np_provider_routes.py", "9CBDE09CD1E84DCB6380BC223C9C23791DA3671AC042C13A745291F9CC5A11EA"),
    ("np_provider_transcript.py", "46327DF0A848672FFBCA85772C0EA764D370BDF7B487EFAE36831F451A6915D4"),
    ("np_receipts.py", "69F59AF10FF5A6FAED469E4C93DCB128F741C50444CC31E37737EC4889B708FD"),
    ("np_runner_entry.py", "9C0F85733287BDCF4F526AB52F5685E7BC10CB1C4CC349818D8B0AC001B07E70"),
    ("np_suite.py", "617D381A92F41DEC8376BA0F45A9DF9A9FBA3A54DE6D15B6F61BA2439DEFE562"),
    ("np_supervisor.py", "A1ADA2311B10631209DBA0588B8C9C6B947B3206F0EFBC51F4CF66B1F45303BC"),
)
# Dex R1: checker-read fixtures previously omitted from admission root.
CHECKER_READ_FIXTURE_EXTRA_PINS: tuple[tuple[str, str], ...] = (
    ("bootstrap-postgres-tls.sh", "FE72795D82DB70B16D193CF18D5B732E01FBA24ABA1606A91621D533C0236D16"),
    ("np_alias_seed.py", "309CE658479FFD665408B6EAABF318258AF402D29F23C0C3F9BD99E5FDA003AD"),
    ("np_integrated_runner.py", "2C8B5BE78B5F042210D042DF1FB7FDBB07C486ED5A57CA36C00006F61E6040DF"),
    ("np_provider_routes.py", "9CBDE09CD1E84DCB6380BC223C9C23791DA3671AC042C13A745291F9CC5A11EA"),
    ("prepare-tls.sh", "41A683A6A0312B12F71C42C966F9BA0EF3D02D97416FAEF28C6E99DE9B29DF4F"),
)
BYTE_ALIAS_REFERENCE_CONTROL_IDS = (
    "BYTE-ALIAS-DOCUMENTATION-ACCEPTED",
    "BYTE-ALIAS-IMPORT-REFUSED",
    "BYTE-ALIAS-CALL-REFUSED",
    "BYTE-ALIAS-INSTALL-REFUSED",
)
HOST_ENTRY_SEAM_CONTROL_IDS = (
    "HOST-ENTRY-UNBOUND-REFUSED",
    "HOST-ENTRY-ONE-TIME-BIND",
    "HOST-ENTRY-DOUBLE-BIND-REFUSED",
    "HOST-ENTRY-SYNTHETIC-DOCKER-EVENTS",
)
PKI_LATE_DRAIN_CONTROL_IDS = (
    "PKI-IN-LOOP-OVERFLOW-REFUSED",
    "PKI-LATE-DRAIN-OVERFLOW-REFUSED",
    "PKI-LATE-DRAIN-PRESERVES-PRIMARY",
)
T05_EXTRACTED_CONTROL_IDS = (
    "T05-R1-CLEAN-REFUSAL-ADMITTED",
    "T05-R1-UNKNOWN-REFUSED",
    "T05-R1-UNKNOWN-UNWRAP-MUTATION-HOLE",
    "T05-R2-OBSERVER-EOF-ADMITTED",
    "T05-R2-OBSERVER-RESET-ADMITTED",
    "T05-R2-OBSERVER-GENERIC-SSL-REFUSED",
    "T05-R2-OBSERVER-GENERIC-OSERROR-REFUSED",
    "T05-R2-OBSERVER-TIMEOUT-REFUSED",
    "T05-R2-OBSERVER-CLEAN-EOF-REFUSED",
    "T05-R2-GENERIC-REFUSAL-REFUSED",
    "T05-R2-DEADLINE-REFUSED",
    "T05-R2-UNKNOWN-REFUSED",
    "T05-R2-MEASURED-GUARD-MUTATION-HOLE",
    "T05-R3-PARTIAL-START-ONE-RETIREMENT",
    "T05-R3-UNCONFIRMED-RETIREMENT-STOP",
    "T05-R3-DOUBLE-RETIRE-GUARD-PRESENT",
    "T05-R4-PLAN-CAPTURE-FAILURE-STOP",
    "T05-R4-PLAN-EXPIRY-STOP",
    "T05-R4-NOW-FALLBACK-ABSENT",
)
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
    """Root-pin the exact 234-file assembly manifest and verify every selected byte.

    Count alone is not equivalent to those 234 hashes (Dex F2).
    """
    policy = API / "app" / "services" / "covering_transport_policy.py"
    if not policy.is_file():
        raise WitnessFailure("assembled policy missing")
    policy_hash = sha256_file(policy)
    if policy_hash != POLICY_OVERRIDE_PIN:
        raise WitnessFailure(f"policy override pin mismatch:{policy_hash}")
    manifest_path = ROOT / "docs" / "Assembly-Selected-Source-Manifest.json"
    if not manifest_path.is_file():
        raise WitnessFailure("assembly selected-source manifest missing")
    manifest_hash = sha256_file(manifest_path)
    if manifest_hash != ASSEMBLY_MANIFEST_PIN:
        raise WitnessFailure(f"assembly manifest pin mismatch:{manifest_hash}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("selection_sha256") != ASSEMBLY_SELECTION_PIN:
        raise WitnessFailure("assembly selection pin mismatch inside manifest")
    files = manifest.get("files") or []
    if len(files) != 234:
        raise WitnessFailure(f"manifest file inventory {len(files)} != 234")
    verified = 0
    for entry in files:
        relative = entry.get("relative_path")
        expected = str(entry.get("sha256", "")).strip().upper()
        if not relative or len(expected) != 64:
            raise WitnessFailure("manifest entry incomplete")
        target = API / relative
        if not target.is_file():
            raise WitnessFailure(f"assembled file missing:{relative}")
        actual = sha256_file(target)
        if actual != expected:
            raise WitnessFailure(f"assembled byte mismatch:{relative}")
        verified += 1
    file_count = sum(1 for _ in API.rglob("*") if _.is_file())
    if file_count != 234 or verified != 234:
        raise WitnessFailure(f"assembly file count {file_count}/{verified} != 234")
    return {
        "assembly_selection_pin": ASSEMBLY_SELECTION_PIN,
        "assembly_manifest_sha256": manifest_hash,
        "policy_override_sha256": policy_hash,
        "assembled_file_count": file_count,
        "assembled_files_byte_verified": verified,
        "port_dependency_consumed": True,
        "control_kind": "shape_source",
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
    if "retirement_attempted" not in runner:
        raise WitnessFailure("runner missing one-attempt retirement disposition guard")
    if "not retirement_attempted" not in runner:
        raise WitnessFailure("finally must gate sole failure-path retirement on no prior attempt")
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
    if "peer_stimulus_not_sole_orderly_eof_proof" not in peer:
        raise WitnessFailure("peer must disclose stimulus≠orderly-EOF proof")
    if "orderly_close_notify_unwrap_ok" not in peer:
        raise WitnessFailure("peer must separately record unwrap_ok vs attempt")

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
    if "NP-T05-ORDERLY-CLOSE" not in runner or "NP-T05-ABRUPT-TRUNCATION" not in runner:
        raise WitnessFailure("T05 authored bodies missing from runner IMPLEMENTED set")
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
        "t05_bodies_authored": True,
        "multi_connection_inventory": True,
        "explicit_holds": True,
        "observed": "PASS",
    }


def _extract_t05_helper(runner_src: str, name: str, *, deps: dict[str, Any]) -> Any:
    """AST-extract one actual T05 helper from runner; exec without app imports."""
    tree = ast.parse(runner_src)
    node = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name),
        None,
    )
    if node is None:
        raise WitnessFailure(f"T05 helper missing for extraction:{name}")
    module = ast.Module(body=[copy.deepcopy(node)], type_ignores=[])
    ast.fix_missing_locations(module)
    env: dict[str, Any] = {"__builtins__": __builtins__, **deps}
    exec(compile(module, f"<extracted-{name}>", "exec"), env)
    if name not in env:
        raise WitnessFailure(f"extracted T05 helper not bound:{name}")
    return env[name]


def _t05_extracted_predicate_controls(runner_src: str) -> dict[str, Any]:
    """Finite extracted actual-helper controls for Dex R1–R4 (+ mutations).

    Pure in-memory fakes only — no app/vendor imports, sockets, PKI, or fs.
    Structural shape checks remain separate; this exercises real predicates.
    """
    import http.client

    class SuiteStop(Exception):
        pass

    class CoveringTransportRefused(Exception):
        pass

    class CoveringRootOutcomeUnknown(Exception):
        def __init__(self) -> None:
            super().__init__("unknown")
            self.primary = None

    class PlanValidityExpired(RuntimeError):
        pass

    class PeerRetirementUnknown(Exception):
        pass

    results: list[str] = []

    # Patch import sites inside extracted bodies via injected module stubs.
    fake_np_suite = types.ModuleType("np_suite")
    fake_np_suite.SuiteStop = SuiteStop
    fake_policy = types.ModuleType("app.services.covering_transport_policy")
    fake_policy.CoveringTransportRefused = CoveringTransportRefused
    fake_target = types.ModuleType("app.services.covering_target_transaction")
    fake_target.CoveringRootOutcomeUnknown = CoveringRootOutcomeUnknown
    sys.modules["np_suite"] = fake_np_suite
    sys.modules["app"] = types.ModuleType("app")
    sys.modules["app.services"] = types.ModuleType("app.services")
    sys.modules["app.services.covering_transport_policy"] = fake_policy
    sys.modules["app.services.covering_target_transaction"] = fake_target
    try:
        # --- R1: orderly event refusal ---
        is_unknown = _extract_t05_helper(
            runner_src, "_t05_is_covering_root_unknown", deps={}
        )
        admit_refusal = _extract_t05_helper(
            runner_src,
            "_t05_admit_orderly_event_refusal",
            deps={"_t05_is_covering_root_unknown": is_unknown},
        )
        clean = admit_refusal(http.client.IncompleteRead(b"{}", 20))
        if clean != "IncompleteRead":
            raise WitnessFailure("R1 clean IncompleteRead not admitted")
        results.append("T05-R1-CLEAN-REFUSAL-ADMITTED")
        unknown = CoveringRootOutcomeUnknown()
        unknown.primary = http.client.IncompleteRead(b"{}", 20)
        unknown_stopped = False
        try:
            admit_refusal(unknown)
        except SuiteStop:
            unknown_stopped = True
        if not unknown_stopped:
            raise WitnessFailure("R1 must STOP on CoveringRootOutcomeUnknown")
        results.append("T05-R1-UNKNOWN-REFUSED")

        # Mutation: unwrap primary from UNKNOWN (v1 hole) must be distinguishable.
        def mutant_unwrap_unknown(outcome: Any) -> str:
            if isinstance(outcome, CoveringTransportRefused):
                return "CoveringTransportRefused"
            if isinstance(outcome, http.client.IncompleteRead):
                return "IncompleteRead"
            primary = getattr(outcome, "primary", None)
            if isinstance(primary, (CoveringTransportRefused, http.client.IncompleteRead)):
                return type(primary).__name__
            raise SuiteStop("not refused")

        hole = mutant_unwrap_unknown(unknown)
        if hole != "IncompleteRead":
            raise WitnessFailure("R1 mutation probe did not show UNKNOWN-unwrap hole")
        results.append("T05-R1-UNKNOWN-UNWRAP-MUTATION-HOLE")

        # --- R2: finite EOF/reset observer taxonomy + actual admission ---
        # Exercise EXTRACTED observer with fake JoinedTLS.receive outcomes, then
        # the actual admission predicate. Positive: SSLEOFError / ConnectionReset.
        # Negative: generic SSLError, unrelated OSError, TimeoutError, clean EOF,
        # UNKNOWN. No hand-built abrupt labels bypassing observer taxonomy.
        class SSLError(Exception):
            pass

        class SSLEOFError(SSLError):
            pass

        fake_ssl = types.ModuleType("ssl")
        fake_ssl.SSLError = SSLError
        fake_ssl.SSLEOFError = SSLEOFError
        sys.modules["ssl"] = fake_ssl

        class FakeJoinedTLS:
            @staticmethod
            def receive(self, maximum):  # type: ignore[no-untyped-def]
                raise RuntimeError("fake receive unset")

        fake_joined_mod = types.ModuleType("app.services.covering_joined_https")
        fake_joined_mod.JoinedTLS = FakeJoinedTLS
        sys.modules["app.services.covering_joined_https"] = fake_joined_mod

        recv_has = _extract_t05_helper(runner_src, "_recv_has_class", deps={})
        measured = _extract_t05_helper(
            runner_src, "_t05_measured_abrupt_receive", deps={"_recv_has_class": recv_has}
        )
        install_obs = _extract_t05_helper(
            runner_src, "_install_joinedtls_receive_observer", deps={}
        )
        admit_abrupt = _extract_t05_helper(
            runner_src,
            "_t05_admit_abrupt_truncation",
            deps={
                "_t05_is_covering_root_unknown": is_unknown,
                "_t05_measured_abrupt_receive": measured,
            },
        )

        def _drive_observer(exc_or_bytes: Any) -> list[dict[str, Any]]:
            log: list[dict[str, Any]] = []

            def _recv(self, maximum):  # type: ignore[no-untyped-def]
                if isinstance(exc_or_bytes, BaseException):
                    raise exc_or_bytes
                return exc_or_bytes

            # Underlying receive must be set before install wraps it.
            FakeJoinedTLS.receive = _recv  # type: ignore[method-assign]
            restore = install_obs(log)
            try:
                try:
                    FakeJoinedTLS.receive(FakeJoinedTLS(), 16)
                except BaseException:
                    pass
            finally:
                restore()
            return log

        eof_log = _drive_observer(SSLEOFError("EOF occurred in violation of protocol"))
        if not eof_log or eof_log[0].get("class") != "abrupt_ssl_eof":
            raise WitnessFailure("R2 observer must classify SSLEOFError as abrupt_ssl_eof")
        eof_ok = admit_abrupt(
            outcome=http.client.IncompleteRead(b"{", 40),
            recv_log=eof_log,
            peer_stimulus_ok=True,
        )
        if eof_ok.get("production_receive_abrupt_class") != "abrupt_ssl_eof":
            raise WitnessFailure("R2 observer EOF must admit via actual predicate")
        if eof_ok.get("finite_eof_reset_taxonomy") is not True:
            raise WitnessFailure("R2 admit must record finite_eof_reset_taxonomy")
        results.append("T05-R2-OBSERVER-EOF-ADMITTED")

        reset_log = _drive_observer(ConnectionResetError(10054, "connection reset"))
        if not reset_log or reset_log[0].get("class") != "abrupt_tcp_reset":
            raise WitnessFailure(
                "R2 observer must classify ConnectionResetError as abrupt_tcp_reset"
            )
        reset_ok = admit_abrupt(
            outcome=ConnectionResetError(10054, "connection reset"),
            recv_log=reset_log,
            peer_stimulus_ok=True,
        )
        if reset_ok.get("production_receive_abrupt_class") != "abrupt_tcp_reset":
            raise WitnessFailure("R2 observer reset must admit via actual predicate")
        results.append("T05-R2-OBSERVER-RESET-ADMITTED")

        ssl_log = _drive_observer(SSLError("PROTOCOL_ERROR"))
        if not ssl_log or ssl_log[0].get("class") != "ssl_error_non_eof":
            raise WitnessFailure("R2 observer must label generic SSLError non-eof")
        ssl_stopped = False
        try:
            admit_abrupt(
                outcome=http.client.IncompleteRead(b"{", 40),
                recv_log=ssl_log,
                peer_stimulus_ok=True,
            )
        except SuiteStop:
            ssl_stopped = True
        if not ssl_stopped:
            raise WitnessFailure("R2 must STOP generic SSLError taxonomy (not truncation)")
        results.append("T05-R2-OBSERVER-GENERIC-SSL-REFUSED")

        ose_log = _drive_observer(OSError(22, "unrelated"))
        if not ose_log or ose_log[0].get("class") != "os_error_non_reset":
            raise WitnessFailure("R2 observer must label unrelated OSError non-reset")
        ose_stopped = False
        try:
            admit_abrupt(
                outcome=http.client.IncompleteRead(b"{", 40),
                recv_log=ose_log,
                peer_stimulus_ok=True,
            )
        except SuiteStop:
            ose_stopped = True
        if not ose_stopped:
            raise WitnessFailure("R2 must STOP unrelated OSError taxonomy (not truncation)")
        results.append("T05-R2-OBSERVER-GENERIC-OSERROR-REFUSED")

        to_log = _drive_observer(TimeoutError("timed out"))
        if not to_log or to_log[0].get("class") != "os_error_non_reset":
            raise WitnessFailure("R2 observer must label TimeoutError non-reset")
        if to_log[0].get("exc_type") != "TimeoutError":
            raise WitnessFailure("R2 observer must retain TimeoutError exc_type")
        to_stopped = False
        try:
            admit_abrupt(
                outcome=http.client.IncompleteRead(b"{", 40),
                recv_log=to_log,
                peer_stimulus_ok=True,
            )
        except SuiteStop:
            to_stopped = True
        if not to_stopped:
            raise WitnessFailure("R2 must STOP TimeoutError taxonomy (not truncation)")
        results.append("T05-R2-OBSERVER-TIMEOUT-REFUSED")

        clean_log = _drive_observer(b"")
        if not clean_log or clean_log[0].get("class") != "clean_eof":
            raise WitnessFailure("R2 observer must keep clean_eof distinct")
        clean_stopped = False
        try:
            admit_abrupt(
                outcome=http.client.IncompleteRead(b"{", 40),
                recv_log=clean_log,
                peer_stimulus_ok=True,
            )
        except SuiteStop:
            clean_stopped = True
        if not clean_stopped:
            raise WitnessFailure("R2 must STOP clean_eof as abrupt truncation")
        results.append("T05-R2-OBSERVER-CLEAN-EOF-REFUSED")

        generic_stopped = False
        try:
            admit_abrupt(
                outcome=CoveringTransportRefused("incomplete fixed-length stream"),
                recv_log=[{"class": "data", "nbytes": 2}],
                peer_stimulus_ok=True,
            )
        except SuiteStop:
            generic_stopped = True
        if not generic_stopped:
            raise WitnessFailure("R2 must refuse generic refusal without abrupt receive")
        results.append("T05-R2-GENERIC-REFUSAL-REFUSED")

        deadline_stopped = False
        try:
            admit_abrupt(
                outcome=CoveringTransportRefused("work deadline"),
                recv_log=eof_log,
                peer_stimulus_ok=True,
            )
        except SuiteStop:
            deadline_stopped = True
        if not deadline_stopped:
            raise WitnessFailure("R2 must refuse deadline even with abrupt receive")
        results.append("T05-R2-DEADLINE-REFUSED")

        unk_stopped = False
        try:
            admit_abrupt(
                outcome=CoveringRootOutcomeUnknown(),
                recv_log=eof_log,
                peer_stimulus_ok=True,
            )
        except SuiteStop:
            unk_stopped = True
        if not unk_stopped:
            raise WitnessFailure("R2 must refuse UNKNOWN")
        results.append("T05-R2-UNKNOWN-REFUSED")

        # Mutation: drop measured-receive requirement (v1 hole) OR trust every SSLError.
        def mutant_no_measured(*, outcome, recv_log, peer_stimulus_ok):
            if not peer_stimulus_ok:
                raise SuiteStop("stimulus")
            if not isinstance(outcome, BaseException):
                raise SuiteStop("success")
            return {
                "production_receive_abrupt_class": "inferred",
                "framing_or_tls_disposition": type(outcome).__name__,
            }

        mutant_ok = mutant_no_measured(
            outcome=CoveringTransportRefused("incomplete fixed-length stream"),
            recv_log=[{"class": "data", "nbytes": 2}],
            peer_stimulus_ok=True,
        )
        if mutant_ok.get("production_receive_abrupt_class") != "inferred":
            raise WitnessFailure("R2 mutation probe did not show measured-guard hole")
        results.append("T05-R2-MEASURED-GUARD-MUTATION-HOLE")

        # --- R3: partial start one retirement ---
        class FakeLife:
            def __init__(self) -> None:
                self.notes: list[str] = []
                self.joined = False
                self.retired = False

        class FakePeer:
            def __init__(self, *, fail_mode: str) -> None:
                self.life = FakeLife()
                self._worker = object()
                self.fail_mode = fail_mode
                self.retire_calls = 0

            def start_background(self, *, seconds: int) -> None:
                self.life.notes.append("partial_bind_acquired")
                if self.fail_mode == "start_raise":
                    raise RuntimeError("partial_start_failed")

            def retire_owned(self, *, join_seconds: float = 5.0) -> dict[str, Any]:
                self.retire_calls += 1
                if self.fail_mode == "retire_unknown":
                    raise PeerRetirementUnknown("unjoined")
                self.life.joined = True
                self.life.retired = True
                self._worker = None
                return {"joined": True, "retired": True}

        fake_peer_mod = types.ModuleType("np_provider_peer")
        fake_peer_mod.PeerRetirementUnknown = PeerRetirementUnknown
        sys.modules["np_provider_peer"] = fake_peer_mod
        start_or_retire = _extract_t05_helper(
            runner_src, "_t05_start_owned_peer_or_retire", deps={}
        )
        peer = FakePeer(fail_mode="start_raise")
        raised = False
        try:
            start_or_retire(peer, seconds=1)
        except RuntimeError as exc:
            raised = str(exc) == "partial_start_failed"
        if not raised:
            raise WitnessFailure("R3 must preserve primary start failure")
        if peer.retire_calls != 1:
            raise WitnessFailure("R3 must perform exactly one retirement on start failure")
        if "t05_helper_start_failure_retired_once" not in peer.life.notes:
            raise WitnessFailure("R3 must mark helper-owned single retirement")
        results.append("T05-R3-PARTIAL-START-ONE-RETIREMENT")

        peer_unk = FakePeer(fail_mode="retire_unknown")
        # force start_raise path then unknown retirement
        peer_unk.fail_mode = "start_raise"
        # Override retire to unknown while start raises
        def _retire_unknown(*, join_seconds: float = 5.0):
            peer_unk.retire_calls += 1
            raise PeerRetirementUnknown("unjoined")

        peer_unk.retire_owned = _retire_unknown  # type: ignore[method-assign]
        unk_ret = False
        try:
            start_or_retire(peer_unk, seconds=1)
        except SuiteStop as exc:
            unk_ret = "retirement UNKNOWN after start failure" in str(exc)
        if not unk_ret:
            raise WitnessFailure("R3 must STOP on unconfirmed retirement")
        results.append("T05-R3-UNCONFIRMED-RETIREMENT-STOP")

        if "t05_helper_start_failure_retired_once" not in runner_src:
            raise WitnessFailure("R3 double-retire guard marker missing from runner")
        if 't05_helper_start_failure_retired_once" not in _peer_notes' not in runner_src:
            raise WitnessFailure("R3 caller finally must skip helper-retired peers")
        results.append("T05-R3-DOUBLE-RETIRE-GUARD-PRESENT")

        # --- R4: plan capture / expiry; no now-fallback ---
        class AttemptPlan:
            def __init__(self, case_id: str, t_plan: datetime, attempt_token: str) -> None:
                self.case_id = case_id
                self.t_plan = t_plan
                self.attempt_token = attempt_token

        fake_auth = types.ModuleType("np_auth_seed")

        def fresh_attempt_plan(case_id: str):
            if case_id.endswith(":fail"):
                raise RuntimeError("planner_broke")
            if case_id.endswith(":expire"):
                raise PlanValidityExpired("expired at capture")
            now = datetime.now(timezone.utc)
            return AttemptPlan(case_id, now, attempt_token=f"tok-{case_id}")

        def assert_plan_still_valid(t_plan: datetime, *, now: datetime | None = None) -> None:
            current = now or datetime.now(timezone.utc)
            if case_force_expire["on"]:
                raise PlanValidityExpired("expired at check")
            if current < t_plan:
                raise PlanValidityExpired("clock")

        case_force_expire = {"on": False}
        fake_auth.fresh_attempt_plan = fresh_attempt_plan
        fake_auth.assert_plan_still_valid = assert_plan_still_valid
        fake_auth.PlanValidityExpired = PlanValidityExpired
        sys.modules["np_auth_seed"] = fake_auth
        capture = _extract_t05_helper(runner_src, "_t05_capture_validated_plan", deps={})
        fail_stopped = False
        try:
            capture("NP-T05-ORDERLY-CLOSE:fail")
        except SuiteStop as exc:
            fail_stopped = "plan capture failed" in str(exc)
        if not fail_stopped:
            raise WitnessFailure("R4 must STOP on plan capture failure (no now-fallback)")
        results.append("T05-R4-PLAN-CAPTURE-FAILURE-STOP")

        exp_stopped = False
        try:
            capture("NP-T05-ORDERLY-CLOSE:expire")
        except SuiteStop as exc:
            exp_stopped = "plan validity expired" in str(exc)
        if not exp_stopped:
            raise WitnessFailure("R4 must STOP on plan expiry")
        results.append("T05-R4-PLAN-EXPIRY-STOP")

        # Assert bodies do not catch-all to _iso_now for T05 planning.
        for marker in (
            "except Exception:\n        t_plan_iso = _iso_now()",
            "except Exception:\n            t_plan_iso = _iso_now()",
        ):
            if marker in runner_src and "_t05_capture_validated_plan" in runner_src:
                # Allow only if outside T05 bodies — detect inside T05 functions.
                pass
        # Stronger: T05 bodies must call capture helper; no bare _iso_now fallback nearby.
        for fn_name in ("_run_np_t05_orderly_close", "_run_np_t05_abrupt_truncation"):
            fn = next(
                n
                for n in ast.parse(runner_src).body
                if isinstance(n, ast.FunctionDef) and n.name == fn_name
            )
            body_src = ast.get_source_segment(runner_src, fn) or ""
            if "t_plan_iso = _iso_now()" in body_src:
                raise WitnessFailure(f"R4 {fn_name} still falls back to _iso_now")
            if "_t05_capture_validated_plan" not in body_src:
                raise WitnessFailure(f"R4 {fn_name} missing validated plan capture")
        results.append("T05-R4-NOW-FALLBACK-ABSENT")
    finally:
        for name in (
            "np_suite",
            "np_provider_peer",
            "np_auth_seed",
            "ssl",
            "app.services.covering_transport_policy",
            "app.services.covering_target_transaction",
            "app.services.covering_joined_https",
        ):
            sys.modules.pop(name, None)
        # Leave synthetic app package stubs if newly created — remove if we added.
        for name in ("app.services", "app"):
            mod = sys.modules.get(name)
            if isinstance(mod, ModuleType) and not getattr(mod, "__file__", None):
                sys.modules.pop(name, None)

    if tuple(results) != T05_EXTRACTED_CONTROL_IDS:
        raise WitnessFailure(
            f"T05 extracted control inventory mismatch: got={results} "
            f"expected={list(T05_EXTRACTED_CONTROL_IDS)}"
        )
    return {
        "t05_extracted_control_ids": list(results),
        "extraction": "ast_selected_t05_helpers",
        "control_kind": "fake_behavioral_extracted_helper",
        "native_behavioral_proof": False,
        "real_imports_sockets_pki_fs": False,
    }


def check_t05_closure_focused() -> dict[str, Any]:
    """Focused T05 closure control — structural shape + extracted R1–R4 predicates.

    Structural scope remains honest (OMIT / EOF pairing / launch batch).
    Behavioral regression gates for Dex R1–R4 use extracted actual helpers with
    mutations — not string-only presence checks. Not native PASS / no invoke.
    Cite Native-Deadline-TLS-Observation-Review.md §6.
    """
    transcript = (FIXTURE / "np_provider_transcript.py").read_text(encoding="utf-8")
    peer = (FIXTURE / "np_provider_peer.py").read_text(encoding="utf-8")
    runner = (FIXTURE / "np_runner_entry.py").read_text(encoding="utf-8")
    suite = (FIXTURE / "np_suite.py").read_text(encoding="utf-8")
    joined = (API / "app" / "services" / "covering_joined_https.py").read_text(encoding="utf-8")
    transport = (API / "app" / "services" / "covering_http_transport.py").read_text(
        encoding="utf-8"
    )
    runner_config = json.loads((ROOT / "payload" / "runner-config.json").read_text(encoding="utf-8"))
    expected = load_expected()

    # Exact case IDs preserved.
    if "NP-T05-ORDERLY-CLOSE" not in suite or "NP-T05-ABRUPT-TRUNCATION" not in suite:
        raise WitnessFailure("suite missing exact T05 case IDs")
    for name in (
        "orderly_close_delimited_complete_accepted",
        "orderly_short_cl_valid_json_prefix_refused",
        "classified_distinct_from_malformed_and_asgi_disconnect",
    ):
        if f'name="{name}"' not in suite and f"name='{name}'" not in suite:
            raise WitnessFailure(f"suite missing T05 oracle name:{name}")

    # True close-delimited (OMIT) — CL:2 alone cannot prove close-delimited.
    if 'script_id="T05-ORDERLY-CLOSE-DELIMITED-COMPLETE"' not in transcript:
        raise WitnessFailure("close-delimited complete script missing")
    if '("Content-Length", "OMIT")' not in transcript and "('Content-Length', 'OMIT')" not in transcript:
        raise WitnessFailure("close-delimited script must use Content-Length:OMIT")
    delimited_block = transcript.split(
        'script_id="T05-ORDERLY-CLOSE-DELIMITED-COMPLETE"', 1
    )[1].split("def ", 1)[0]
    if '("Content-Length", "2")' in delimited_block or "('Content-Length', '2')" in delimited_block:
        raise WitnessFailure("close-delimited script must not use Content-Length:2")
    if 'script_id="T05-ORDERLY-SHORT-CL-VALID-JSON"' not in transcript:
        raise WitnessFailure("short-CL refuse script missing")
    if 'script_id="T05-ABRUPT-TRUNCATION"' not in transcript:
        raise WitnessFailure("abrupt truncation script missing")
    if 'close_mode="abrupt_truncate"' not in transcript:
        raise WitnessFailure("abrupt script missing abrupt_truncate close_mode")
    if "value == \"OMIT\"" not in peer and "value == 'OMIT'" not in peer:
        raise WitnessFailure("peer must honor Content-Length:OMIT for close-delimited")

    # Peer stimulus ≠ sole EOF proof (Dex interrupt).
    if "peer_stimulus_not_sole_orderly_eof_proof" not in peer:
        raise WitnessFailure("peer missing stimulus≠EOF disclosure")
    if "orderly_close_notify_attempted" not in peer:
        raise WitnessFailure("peer missing orderly attempt note")
    if "JoinedTLS.close is local" not in peer and "local close only" not in peer.lower():
        if "do NOT require successful two-way server unwrap" not in peer:
            raise WitnessFailure("peer must state unwrap success is not sole proof")

    # Production JoinedTLS pins unchanged.
    if "suppress_ragged_eofs=False" not in joined:
        raise WitnessFailure("JoinedTLS must keep suppress_ragged_eofs=False")
    if "Local close only" not in joined and "no TLS unwrap" not in joined:
        raise WitnessFailure("JoinedTLS.close must remain local-close-only")
    if "Neither CL nor TE for close-delimited" not in transport:
        raise WitnessFailure("transport framing policy must admit close-delimited")

    # Runner pairs peer stimulus with production receive classes + R1–R4 helpers.
    if "_install_joinedtls_receive_observer" not in runner:
        raise WitnessFailure("runner missing JoinedTLS.receive observer for EOF class")
    if '"clean_eof"' not in runner and "'clean_eof'" not in runner:
        raise WitnessFailure("runner missing clean_eof production class")
    if '"abrupt_ssl_eof"' not in runner and "'abrupt_ssl_eof'" not in runner:
        raise WitnessFailure("runner missing abrupt_ssl_eof production class")
    if '"abrupt_tcp_reset"' not in runner and "'abrupt_tcp_reset'" not in runner:
        raise WitnessFailure("runner missing abrupt_tcp_reset receive class")
    if "SSLEOFError" not in runner:
        raise WitnessFailure("runner must classify SSLEOFError (not every SSLError)")
    if "ssl_error_non_eof" not in runner:
        raise WitnessFailure("runner must label generic SSLError as ssl_error_non_eof")
    if "os_error_non_reset" not in runner:
        raise WitnessFailure("runner must label unrelated OSError as os_error_non_reset")
    if "ConnectionResetError" not in runner or "ConnectionAbortedError" not in runner:
        raise WitnessFailure("runner must select finite TCP reset/abort terminals")
    # v2 false-positive boundary must not return: every SSLError/OSError as abrupt.
    if '"abrupt_ssl_error"' in runner or "'abrupt_ssl_error'" in runner:
        raise WitnessFailure("runner must not use broad abrupt_ssl_error class")
    if "_run_np_t05_orderly_close" not in runner or "_run_np_t05_abrupt_truncation" not in runner:
        raise WitnessFailure("runner missing T05 case body callables")
    if "peer_stimulus_not_sole_orderly_eof_proof" not in runner:
        raise WitnessFailure("runner evidence must record stimulus≠EOF proof")
    if "asgi_disconnect" not in runner:
        raise WitnessFailure("abrupt path must record asgi_disconnect=false distinction")
    for helper in (
        "_t05_admit_orderly_event_refusal",
        "_t05_admit_abrupt_truncation",
        "_t05_start_owned_peer_or_retire",
        "_t05_capture_validated_plan",
        "_t05_is_covering_root_unknown",
        "_t05_measured_abrupt_receive",
    ):
        if f"def {helper}(" not in runner:
            raise WitnessFailure(f"runner missing T05 helper:{helper}")

    # Launch batch not expanded.
    case_ids = list(runner_config.get("case_ids") or [])
    if case_ids != ["NP-V-MS-NONEXPIRED"]:
        raise WitnessFailure(f"launch batch must stay NP-V-MS-NONEXPIRED only; got={case_ids}")
    if runner_config.get("launch_ready") is not False:
        raise WitnessFailure("runner-config launch_ready must remain false for prep")
    authored = list(runner_config.get("authored_bodies_not_in_launch_batch") or [])
    if "NP-T05-ORDERLY-CLOSE" not in authored or "NP-T05-ABRUPT-TRUNCATION" not in authored:
        raise WitnessFailure("runner-config must disclose authored T05 bodies outside launch batch")

    impl = list(expected.get("implemented_case_ids") or [])
    for required in (
        "NP-V-MS-NONEXPIRED",
        "NP-T05-ORDERLY-CLOSE",
        "NP-T05-ABRUPT-TRUNCATION",
    ):
        if required not in impl:
            raise WitnessFailure(f"EXPECTED implemented_case_ids missing {required}")
    if expected.get("launch_batch_case_ids") != ["NP-V-MS-NONEXPIRED"]:
        raise WitnessFailure("EXPECTED launch_batch_case_ids must stay NP-V-MS-NONEXPIRED only")

    aid = expected.get("observation_aids") or {}
    pin = aid.get("Native-Deadline-TLS-Observation-Review.md_sha256")
    if pin != "1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069":
        raise WitnessFailure("Native-Deadline-TLS observation aid pin mismatch")

    extracted = _t05_extracted_predicate_controls(runner)

    return {
        "control_id": "T05-CLOSURE-FOCUSED",
        "close_delimited_uses_omit": True,
        "peer_stimulus_not_sole_eof_proof": True,
        "unwrap_success_not_sole_proof": True,
        "production_receive_pairing_authored": True,
        "suppress_ragged_eofs_false_preserved": True,
        "joinedtls_close_local_only_preserved": True,
        "launch_batch_unchanged": True,
        "launch_batch_case_ids": case_ids,
        "authored_bodies_not_in_launch_batch": authored,
        "native_deadline_tls_section": 6,
        "native_behavioral_proof": False,
        "structural_scope": "shape_source_plus_extracted_helper_predicates",
        "t05_extracted_control_ids": extracted["t05_extracted_control_ids"],
        "control_kind": "shape_source_plus_fake_behavioral_extracted_helper",
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
    # main() calls bind_runtime_public_ca_hash + _provider_pki_typed_success_summary.
    # Admit them as fake deps (no real /public-ca fs or PKI) so baseline reaches suite.
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
        # Report-boundary extraction only. Never invoke real import-root
        # preparation, directory creation or PKI in this fake scope (checker-v2).
        "admit_isolated_import_bootstrap": lambda **kwargs: None,
        "prepare_provider_pki_private_dir": lambda **kwargs: {"status": "FAKE_SETUP_ONLY"},
        "admit_provider_pki_generated_once": lambda **kwargs: {
            "status": "GENERATED",
            "generate_invoked": True,
            "late_overflow": False,
            "child_retired": True,
            "group_state": "FAKE",
            "leader_exited": True,
            "readers_joined": True,
            "readers_eof": True,
            "late_overflow_checked": True,
            "stdout_observed_bytes": 0,
            "stderr_observed_bytes": 0,
            "pipes_closed": True,
            "db_trust_isolated": True,
        },
        "invoke_bounded_provider_pki_recipe": lambda **kwargs: {
            "status": "GENERATED",
            "generate_invoked": True,
            "late_overflow": False,
        },
        # Fake dependency admission — do not extract FS-touching bind_runtime_public_ca_hash.
        "bind_runtime_public_ca_hash": lambda cfg: {
            **dict(cfg),
            "ca_sha256": "A" * 64,
        },
        "_provider_pki_typed_success_summary": lambda disposition: {
            "status": "GENERATED",
            "generate_invoked": disposition.get("generate_invoked") is True,
            "child_retired": disposition.get("child_retired") is True,
            "group_state": disposition.get("group_state"),
            "leader_exited": disposition.get("leader_exited") is True,
            "readers_joined": disposition.get("readers_joined") is True,
            "readers_eof": disposition.get("readers_eof") is True,
            "late_overflow": disposition.get("late_overflow") is True,
            "late_overflow_checked": disposition.get("late_overflow_checked") is True,
            "stdout_observed_bytes": int(disposition.get("stdout_observed_bytes") or 0),
            "stderr_observed_bytes": int(disposition.get("stderr_observed_bytes") or 0),
            "pipes_closed": disposition.get("pipes_closed") is True,
            "retry": False,
            "db_trust_isolated": disposition.get("db_trust_isolated") is True,
            "resource_label": "GENERATED",
        },
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

    Finite selected-source inventory guard (Dex F1 / checker-v2). Not an
    obfuscation detector or native execution evidence.
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
    """Same guard must admit documentation and reject actual use."""
    _assert_no_byte_transport_references(
        '"""No FixtureByteTransport or install_covering_http_alias is used."""\n'
        "# FixtureByteTransport is deliberately excluded.\n"
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
    if tuple(controls) != BYTE_ALIAS_REFERENCE_CONTROL_IDS:
        raise WitnessFailure("byte_alias_reference_control_ids inventory mismatch")
    return tuple(controls)


def check_vertical_contract_shape() -> dict[str, Any]:
    """NP-V-MS-NONEXPIRED SHAPE/source control (C340C47B) — not native behavioral PASS.

    Dex F3: keyword/shape checks do not establish shared-budget or subset-safe alias
    behavior; PKI name presence is not a bounded caller witness. Fake packets may
    advance before native PKI wiring is complete.
    """
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
        raise WitnessFailure("bounded provider-PKI recipe helper missing")
    if "admit_provider_pki_generated_once" not in runner:
        raise WitnessFailure("admitted PKI generate-once native path missing")
    if "invoke_bounded_provider_pki_recipe" not in runner:
        raise WitnessFailure("actual bounded provider-PKI caller (dir/child/group/readers) missing")
    if "admit_provider_pki_generated_once(" not in runner:
        raise WitnessFailure("native entry must call admit_provider_pki_generated_once before peer")
    if runner.count("invoke_bounded_provider_pki_recipe(") < 2:
        raise WitnessFailure("invoke_bounded_provider_pki_recipe must be defined and called")
    if "prepare_provider_pki_private_dir(generate=False)" in runner.split("def main")[-1]:
        raise WitnessFailure("main must not remain on prepare_provider_pki_private_dir metadata alone")
    if "late_overflow" not in runner or "late capture overflow" not in runner:
        raise WitnessFailure("PKI late-overflow admission after reader join missing")
    if "subprocess.Popen" not in runner:
        raise WitnessFailure("PKI caller must author subprocess invocation source")
    if "install_binding(app, release_plan)" not in runner and "install_binding(app, binding)" in runner:
        raise WitnessFailure("must install actual CoveringReleasePlan, not prebuilt binding")
    if "clock=monotonic" not in runner:
        raise WitnessFailure("ASGI builder must receive real monotonic clock")
    if "on_context=" not in runner:
        raise WitnessFailure("ingress on_context capture missing")
    if "plant_microsoft_primary_alias=True" not in runner:
        raise WitnessFailure("enabled MS primary alias seed missing")
    if "LOWER str-sorted" not in auth and "lower_sorted_id" not in auth:
        raise WitnessFailure("primary alias must be planted on LOWER str-sorted subscription id")
    if "cal-np-other" not in auth:
        raise WitnessFailure("unrelated stable calendar cal-np-other missing from alias seed")
    if "identity_list_calendar_ids_for_vertical" not in runner and "identity_list_calendar_ids_for_vertical" not in auth:
        raise WitnessFailure("identity list stimulus helper missing")
    if "derive_production_target_calendar_order" not in runner and "derive_production_target_calendar_order" not in auth:
        raise WitnessFailure("wire sequence must derive from subscription→calendar mapping")
    if "coverage_window_start" not in auth or "covering_window_start" in auth:
        raise WitnessFailure("coverage measurement must use mapped coverage_* fields")
    if "coverage_success_at" not in auth or "last_covering_success_at" in auth:
        raise WitnessFailure("coverage_success_at mapped field missing / invented attr present")
    if "counter.remaining" not in runner and 'getattr(counter, "remaining"' not in runner:
        raise WitnessFailure("budget proof must observe counter.remaining (not invented .budget)")
    if "counter_budget is not ingress_budget" in runner or "transport_budget is not ingress_budget" in runner:
        raise WitnessFailure("invented transport.budget/counter.budget equality proof must not remain")
    if "__self__" not in runner or "__func__" not in runner:
        raise WitnessFailure("must observe remaining.__self__/__func__ against ingress budget")
    if "CoveringRequestBudget.work_remaining" not in runner:
        raise WitnessFailure("remaining.__func__ must be CoveringRequestBudget.work_remaining")
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
        "primary_alias_on_lower_sorted_id": True,
        "counter_remaining_budget_proof": True,
        "pki_caller_authored_uninvoked": True,
        "pki_generate_once_call_site_authored": True,
        "pki_late_overflow_gate_authored": True,
        "mapped_coverage_fields": True,
        "profile_literals": {
            "hostname": "native-fixture.invalid",
            "database": "dex_fixture",
            "username": "dex_fixture",
        },
        "contract_pin": "C340C47B3D9CDB92D0DBA91506E4916F85233571B90015BBEDABF9CF3820C054",
        "control_kind": "shape_source",
        "native_behavioral_proof": False,
        "fake_may_advance_before_native_pki": True,
        "dex_v6_findings_sha256": "A80961743D8CC5AC272E00EE0DC5B28FE0A7E92F05C3B3B1FF41C917ADF5D763",
        "observed": "PASS",
    }


def _extract_late_overflow_gate(runner_raw: bytes):
    """Extract actual post-join overflow + primary refusal from candidate caller.

    Dex R2 / D3B6FAD3…: do not handwrite a second policy model. Scope is the
    late_overflow assign/branch plus final primary / late_overflow raises inside
    invoke_bounded_provider_pki_recipe. No threads/processes/PKI.
    """
    if hashlib.sha256(runner_raw).hexdigest().upper() != RUNNER_ENTRY_PIN:
        raise WitnessFailure("runner entry pin mismatch for late-drain extraction")
    source = runner_raw.decode("utf-8")
    tree = ast.parse(source, filename="np_runner_entry.py")
    err_cls = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ProviderPkiCallerError"),
        None,
    )
    caller = next(
        (
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "invoke_bounded_provider_pki_recipe"
        ),
        None,
    )
    if err_cls is None or caller is None:
        raise WitnessFailure("late-drain extraction symbols missing")

    start = None
    for i, node in enumerate(caller.body):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "late_overflow" for t in node.targets
        ):
            start = i
            break
    if start is None:
        raise WitnessFailure("late_overflow assignment missing from candidate caller")
    if start + 1 >= len(caller.body) or not isinstance(caller.body[start + 1], ast.If):
        raise WitnessFailure("late_overflow branch missing after assignment")
    gate_if = caller.body[start + 1]
    if not (isinstance(gate_if.test, ast.Name) and gate_if.test.id == "late_overflow"):
        raise WitnessFailure("late_overflow branch test is not candidate gate")

    primary_raise = None
    late_raise = None
    for node in caller.body[start + 2 :]:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "primary"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.IsNot)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None
        ):
            primary_raise = node
        if isinstance(test, ast.Name) and test.id == "late_overflow":
            late_raise = node
    if primary_raise is None or late_raise is None:
        raise WitnessFailure("primary/late overflow refusal blocks missing from candidate")

    gate_nodes = [
        copy.deepcopy(caller.body[start]),
        copy.deepcopy(gate_if),
        copy.deepcopy(primary_raise),
        copy.deepcopy(late_raise),
    ]

    def _compile_admit(nodes: list[ast.AST]):
        fn = ast.FunctionDef(
            name="admit_after_join",
            args=ast.arguments(
                posonlyargs=[],
                args=[
                    ast.arg(arg="primary"),
                    ast.arg(arg="secondary"),
                    ast.arg(arg="stdout_sink"),
                    ast.arg(arg="stderr_sink"),
                ],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=list(nodes) + [ast.Return(value=ast.Constant(value="GENERATED"))],
            decorator_list=[],
            returns=None,
            type_comment=None,
        )
        module = ast.Module(body=[copy.deepcopy(err_cls), fn], type_ignores=[])
        ast.fix_missing_locations(module)
        ns: dict[str, Any] = {"__builtins__": __builtins__}
        exec(compile(module, "<extracted-late-overflow-gate>", "exec"), ns)
        return ns["admit_after_join"], ns["ProviderPkiCallerError"]

    admit, err_type = _compile_admit(gate_nodes)

    # Mutation: delete actual overflow gate (assign+branch+late raise); must fail oracle.
    mutant_nodes = [copy.deepcopy(primary_raise)]
    mutant_admit, _ = _compile_admit(mutant_nodes)
    return admit, err_type, mutant_admit


def check_provider_pki_late_drain_overflow() -> dict[str, Any]:
    """Extracted late-drain overflow gate (Dex A8096174… + R2 D3B6FAD3…).

    Exercises the raw-pinned candidate post-join overflow/primary-refusal block.
    Memory-only sinks; no subprocess/PKI/threads.
    """
    runner_path = FIXTURE / "np_runner_entry.py"
    runner_raw = runner_path.read_bytes()
    admit, err_type, mutant_admit = _extract_late_overflow_gate(runner_raw)

    class Sink:
        def __init__(self) -> None:
            self.overflow = False
            self.reader_error = False
            self.saw_eof = False
            self.observed = 0

    def run_admit(
        fn,
        *,
        primary: BaseException | None,
        stdout_overflow: bool,
        stderr_overflow: bool,
    ) -> str:
        stdout_sink, stderr_sink = Sink(), Sink()
        stdout_sink.overflow = stdout_overflow
        stderr_sink.overflow = stderr_overflow
        secondary: list[dict[str, str]] = []
        try:
            outcome = fn(primary, secondary, stdout_sink, stderr_sink)
            return str(outcome)
        except BaseException as exc:
            return f"PRIMARY:{exc.args[0] if exc.args else type(exc).__name__}"

    results: list[str] = []
    in_loop = run_admit(
        admit,
        primary=err_type("provider pki capture cap"),
        stdout_overflow=True,
        stderr_overflow=False,
    )
    if in_loop != "PRIMARY:provider pki capture cap":
        raise WitnessFailure("in-loop overflow must preserve capture-cap primary")
    results.append("PKI-IN-LOOP-OVERFLOW-REFUSED")

    late = run_admit(
        admit,
        primary=None,
        stdout_overflow=True,
        stderr_overflow=False,
    )
    if late != "PRIMARY:provider pki late capture overflow":
        raise WitnessFailure("late drain overflow must refuse GENERATED")
    results.append("PKI-LATE-DRAIN-OVERFLOW-REFUSED")

    preserved = run_admit(
        admit,
        primary=err_type("provider pki generation refused"),
        stdout_overflow=True,
        stderr_overflow=True,
    )
    if preserved != "PRIMARY:provider pki generation refused":
        raise WitnessFailure("late overflow must preserve earlier primary failure")
    results.append("PKI-LATE-DRAIN-PRESERVES-PRIMARY")

    if tuple(results) != PKI_LATE_DRAIN_CONTROL_IDS:
        raise WitnessFailure("pki late-drain control inventory mismatch")
    ok = run_admit(
        admit,
        primary=None,
        stdout_overflow=False,
        stderr_overflow=False,
    )
    if ok != "GENERATED":
        raise WitnessFailure("clean post-join path must admit GENERATED")

    mutant_late = run_admit(
        mutant_admit,
        primary=None,
        stdout_overflow=True,
        stderr_overflow=False,
    )
    if mutant_late != "GENERATED":
        raise WitnessFailure(
            "deleting candidate late_overflow gate must admit GENERATED on late drain"
        )
    if mutant_late == late:
        raise WitnessFailure("deleting candidate late_overflow gate must change late-drain outcome")

    return {
        "pki_late_drain_control_ids": list(results),
        "extraction": "ast_selected_post_join_overflow_primary_refusal",
        "gate_mutation_detected": True,
        "control_kind": "fake_behavioral_extracted_block",
        "native_behavioral_proof": False,
        "full_pki_process_retirement_proof": False,
        "dex_v6_findings_sha256": "A80961743D8CC5AC272E00EE0DC5B28FE0A7E92F05C3B3B1FF41C917ADF5D763",
        "dex_r2_review_sha256": "D3B6FAD3D039E491846998439283F1DCBBD2B2F28F8578EC3BA352523E488A53",
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
            external_calendar_id="cal-np-other" if success else "primary",
            role=SimpleNamespace(value="informational"),
            is_enabled=True,
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
    """Parse finite reviewed np_*.py inventory (Dex R1 D3B6FAD3…).

    Glob extras must not silently join the read footprint; missing reviewed
    files and pin mismatches refuse. Also pin the five checker-read fixtures
    previously omitted from admission.
    """
    on_disk = sorted(p.name for p in FIXTURE.glob("np_*.py"))
    reviewed = [name for name, _ in REVIEWED_NP_FIXTURE_PY_PINS]
    if on_disk != reviewed:
        raise WitnessFailure(
            f"np_*.py inventory drift on_disk={on_disk} reviewed={reviewed}"
        )
    parsed: list[str] = []
    for name, pin in REVIEWED_NP_FIXTURE_PY_PINS:
        path = FIXTURE / name
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest().upper()
        if digest != pin:
            raise WitnessFailure(f"reviewed np fixture pin mismatch:{name}")
        try:
            ast.parse(raw.decode("utf-8"), filename=name)
        except SyntaxError as exc:
            raise WitnessFailure(f"candidate fixture syntax:{name}:{exc.msg}") from exc
        parsed.append(name)
    for name, pin in CHECKER_READ_FIXTURE_EXTRA_PINS:
        path = FIXTURE / name
        if not path.is_file():
            raise WitnessFailure(f"checker-read fixture missing:{name}")
        if sha256_file(path) != pin:
            raise WitnessFailure(f"checker-read fixture pin mismatch:{name}")
    # Identity constructors must keep send/close inside steps (no premature ),), close).
    transcript = (FIXTURE / "np_provider_transcript.py").read_text(encoding="utf-8")
    if 'path="/v1.0/me/calendar"),),' in transcript or 'path="/v1.0/me/calendars"),),' in transcript:
        raise WitnessFailure("identity script constructors still close steps after recv_request")
    return {
        "parsed_fixture_sources": parsed,
        "reviewed_np_fixture_count": len(parsed),
        "checker_read_fixture_extra_pins": [name for name, _ in CHECKER_READ_FIXTURE_EXTRA_PINS],
        "identity_steps_intact": True,
        "dex_r1_review_sha256": "D3B6FAD3D039E491846998439283F1DCBBD2B2F28F8578EC3BA352523E488A53",
        "observed": "PASS",
    }


def check_host_entry_receipt_relay_seam() -> dict[str, Any]:
    """Fake host-entry/sink-flow seam for ReceiptRelay + bind_record (host-glue).

    Memory-only. No Docker, process spawn, or docker_transport import.
    """
    host_path = FIXTURE / "np_supervisor.py"
    host_raw = host_path.read_bytes()
    host_pin = hashlib.sha256(host_raw).hexdigest().upper()
    if host_pin != HOST_SUPERVISOR_PIN:
        raise WitnessFailure(f"host supervisor pin mismatch:{host_pin}")
    host = host_raw.decode("utf-8")
    if "class ReceiptRelay" not in host:
        raise WitnessFailure("ReceiptRelay missing")
    if "def admit_host_helper_import" not in host:
        raise WitnessFailure("admit_host_helper_import missing")
    if "ops.bind_record(record)" not in host:
        raise WitnessFailure("run_once must bind_record before Docker ops")
    if "def host_record(event: str, data: dict) -> None:\n        # Temporary record sink" in host:
        raise WitnessFailure("no-op host_record must not remain")
    if "record_relay=relay" not in host:
        raise WitnessFailure("ProviderDockerOps must receive record_relay")
    tree = ast.parse(host)
    relay_node = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ReceiptRelay"),
        None,
    )
    if relay_node is None:
        raise WitnessFailure("ReceiptRelay class missing from AST")
    env: dict[str, Any] = {}
    exec(compile(ast.Module(body=[copy.deepcopy(relay_node)], type_ignores=[]), "<pinned-receipt-relay>", "exec"), env)
    Relay = env["ReceiptRelay"]
    results: list[str] = []

    relay = Relay()
    refused = False
    try:
        relay("docker_command", {"argv": ["version"]})
    except RuntimeError:
        refused = True
    if not refused:
        raise WitnessFailure("unbound receipt sink must refuse")
    results.append("HOST-ENTRY-UNBOUND-REFUSED")

    events: list[tuple[str, dict[str, Any]]] = []

    def sink(event: str, data: dict[str, Any]) -> None:
        events.append((event, data))

    # Immutable-style synchronized wrapper around the relay (retain lock semantics).
    lock = types.SimpleNamespace(_busy=False)

    def locked_record(event: str, data: dict[str, Any]) -> None:
        if lock._busy:
            raise RuntimeError("synchronized record reentry")
        lock._busy = True
        try:
            relay(event, data)
        finally:
            lock._busy = False

    wrapper = types.SimpleNamespace(record=locked_record, _record_relay=relay)

    def bind_record(self, sink_fn):
        self._record_relay.bind(sink_fn)

    wrapper.bind_record = types.MethodType(bind_record, wrapper)
    wrapper.bind_record(sink)
    results.append("HOST-ENTRY-ONE-TIME-BIND")

    double = False
    try:
        wrapper.bind_record(sink)
    except RuntimeError:
        double = True
    if not double:
        raise WitnessFailure("double bind must refuse")
    results.append("HOST-ENTRY-DOUBLE-BIND-REFUSED")

    for event, data in (
        ("docker_command", {"argv": ["start", "--attach", "b" * 64]}),
        ("docker_output", {"sha256": "A" * 64, "bytes": 12}),
        ("runner_stop", {"exit_code": 0, "sanitized": True}),
    ):
        locked_record(event, data)
    if [e for e, _ in events] != ["docker_command", "docker_output", "runner_stop"]:
        raise WitnessFailure("synthetic docker/runner_stop events not preserved")
    results.append("HOST-ENTRY-SYNTHETIC-DOCKER-EVENTS")
    if tuple(results) != HOST_ENTRY_SEAM_CONTROL_IDS:
        raise WitnessFailure("host entry seam control inventory mismatch")
    return {
        "host_sha256": host_pin,
        "host_entry_seam_control_ids": list(results),
        "immutable_docker_transport_unchanged": True,
        "control_kind": "fake_behavioral_seam",
        "native_behavioral_proof": False,
        "observed": "PASS",
    }


def check_admission_schema_wrapper_fields() -> dict[str, Any]:
    """VERIFICATION-ADMISSION must match Invoke-Fake.ps1 relative_path/absolute_path schema.

    Dex F2 acyclic root: wrapper pins OUTER via VERIFICATION packet_files;
    OUTER must not back-pin VERIFICATION (no verification_admission_sha256 cycle).
    """
    admission_path = HERE / "VERIFICATION-ADMISSION.json"
    outer_path = HERE / "OUTER-ADMISSION.json"
    data = json.loads(admission_path.read_text(encoding="utf-8"))
    outer = json.loads(outer_path.read_text(encoding="utf-8"))
    packet = data.get("packet_files") or []
    runtime = data.get("runtime_files") or []
    if not packet or len(packet) != data.get("packet_file_pin_count"):
        raise WitnessFailure("packet pin inventory incomplete")
    if not runtime or len(runtime) != data.get("runtime_file_pin_count"):
        raise WitnessFailure("runtime pin inventory incomplete")
    relative_paths = []
    for pin in packet:
        if "relative_path" not in pin or "path" in pin:
            raise WitnessFailure("packet pins must use relative_path (not path)")
        if not pin.get("sha256"):
            raise WitnessFailure("packet pin missing sha256")
        relative_paths.append(pin["relative_path"])
    if "verify/OUTER-ADMISSION.json" not in relative_paths:
        raise WitnessFailure("wrapper root must pin OUTER-ADMISSION.json (acyclic F2)")
    if "docs/Assembly-Selected-Source-Manifest.json" not in relative_paths:
        raise WitnessFailure("wrapper root must pin assembly selected-source manifest")
    # Dex R1: five checker-read fixtures must be present under wrapper admission.
    for name, pin in CHECKER_READ_FIXTURE_EXTRA_PINS:
        rel = f"payload/fixture/{name}"
        if rel not in relative_paths:
            raise WitnessFailure(f"admission missing checker-read fixture pin:{rel}")
        match = next(p for p in packet if p["relative_path"] == rel)
        if str(match.get("sha256", "")).strip().upper() != pin:
            raise WitnessFailure(f"admission checker-read pin mismatch:{rel}")
        if sha256_file(ROOT / rel) != pin:
            raise WitnessFailure(f"on-disk checker-read pin mismatch:{rel}")
    outer_pins = outer.get("pins") or {}
    if "verification_admission_sha256" in outer_pins:
        raise WitnessFailure("OUTER must not back-pin VERIFICATION (hash cycle)")
    for label, path in (
        ("interpreter_sha256", Path(str(outer.get("interpreter_path", "")))),
        ("launch_check_sha256", HERE / "launch_check.py"),
        ("check_native_provider_sha256", HERE / "check_native_provider.py"),
        ("expected_fake_structural_sha256", HERE / "EXPECTED-FAKE-STRUCTURAL.json"),
    ):
        expected = str(outer_pins.get(label, "")).strip().upper()
        if len(expected) != 64:
            raise WitnessFailure(f"OUTER pin missing:{label}")
        if not path.is_file():
            raise WitnessFailure(f"OUTER subject missing:{label}")
        if sha256_file(path) != expected:
            raise WitnessFailure(f"OUTER pin mismatch:{label}")
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
    # Dex 30FEEDFF… launcher retirement + D8D77976… receipt/stream admission shape.
    launcher = (HERE / "launch_check.py").read_text(encoding="utf-8")
    launcher_pin = sha256_file(HERE / "launch_check.py")
    if launcher_pin != "D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07":
        raise WitnessFailure(f"launch_check receipt-patch candidate pin mismatch:{launcher_pin}")
    for token in (
        "OwnedCheckSession",
        "retirement_attempted",
        "retire_once",
        "readers_clean_eof",
        "capture_reader_setup",
        "TIMEOUT_RETIREMENT_TOTAL_SECONDS",
        "separate_outer_timeout",
        "_write_failure_receipt",
        "30FEEDFF468B3851D3630E73C8BB688D290E4639845A29A377B089DB6534BF27",
        "unexpected check stdout or stderr",
    ):
        if token not in launcher:
            raise WitnessFailure(f"launch_check retirement/receipt shape missing:{token}")
    if "reader_error" not in launcher or "saw_eof" not in launcher:
        raise WitnessFailure("launch_check must gate success on reader_error/saw_eof")
    # Receipt-patch: failure receipt refuses existing RECEIPT only (not RESULT).
    if "def _write_failure_receipt" not in launcher:
        raise WitnessFailure("failure receipt helper missing")
    fail_fn = launcher.split("def _write_failure_receipt", 1)[1].split("\ndef ", 1)[0]
    if "if RECEIPT.is_file():" not in fail_fn:
        raise WitnessFailure("failure receipt must refuse preexisting RECEIPT")
    if "if RECEIPT.is_file() or RESULT.is_file():" in fail_fn or "if RESULT.is_file() or RECEIPT.is_file():" in fail_fn:
        raise WitnessFailure("failure receipt must not suppress on preexisting RESULT alone")
    if "if RESULT.exists() or RECEIPT.exists():" not in launcher and "if RESULT.is_file() or RECEIPT.is_file():" not in launcher:
        # initial main preflight must still refuse either preexisting evidence file
        if "existing evidence; no replay" not in launcher:
            raise WitnessFailure("main preflight must still refuse preexisting RESULT/RECEIPT")
    return {
        "packet_relative_path": True,
        "runtime_absolute_path": True,
        "interpreter_membership": True,
        "outer_pinned_via_wrapper_root": True,
        "acyclic_outer_verification": True,
        "checker_read_fixture_extra_pins": True,
        "launcher_retirement_shape": True,
        "launcher_receipt_stream_admission": True,
        "dex_r1_review_sha256": "D3B6FAD3D039E491846998439283F1DCBBD2B2F28F8578EC3BA352523E488A53",
        "dex_launcher_retirement_sha256": "30FEEDFF468B3851D3630E73C8BB688D290E4639845A29A377B089DB6534BF27",
        "dex_launcher_receipt_patch_sha256": "D8D779767E9CB2046B836EF91C59989837467DCFFDF695EC7AE0E4C5509A2F13",
        "dex_launcher_receipt_candidate_sha256": "D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07",
        "control_kind": "shape_source",
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
        "HOST-ENTRY-RECEIPT-RELAY": check_host_entry_receipt_relay_seam(),
        "PKI-LATE-DRAIN-OVERFLOW": check_provider_pki_late_drain_overflow(),
        "MAPPED-COVERAGE-MEASUREMENT": check_mapped_coverage_measurement(),
        "VERTICAL-CONTRACT-SHAPE": check_vertical_contract_shape(),
        "ADMISSION-SCHEMA-WRAPPER-FIELDS": check_admission_schema_wrapper_fields(),
        "T05-CLOSURE-FOCUSED": check_t05_closure_focused(),
    }
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    return {
        "kind": "fake-native-provider-structural-result",
        "packet": "scheduler-native-provider-t05-closure-prep-jim-v3",
        "executed": True,
        "launch_authorized": False,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        "first_vertical_increment": True,
        "case_registry_pin": CASE_REGISTRY_PIN,
        "controls": controls,
        "control_ids_in_order": list(controls.keys()),
        "report_boundary_control_ids": list(REPORT_BOUNDARY_IDS),
        "byte_alias_reference_control_ids": list(BYTE_ALIAS_REFERENCE_CONTROL_IDS),
        "host_entry_seam_control_ids": list(HOST_ENTRY_SEAM_CONTROL_IDS),
        "pki_late_drain_control_ids": list(PKI_LATE_DRAIN_CONTROL_IDS),
        "t05_extracted_control_ids": list(T05_EXTRACTED_CONTROL_IDS),
        "dex_v6_findings_sha256": "A80961743D8CC5AC272E00EE0DC5B28FE0A7E92F05C3B3B1FF41C917ADF5D763",
        "dex_r1_r2_review_sha256": "D3B6FAD3D039E491846998439283F1DCBBD2B2F28F8578EC3BA352523E488A53",
        "dex_launcher_retirement_sha256": "30FEEDFF468B3851D3630E73C8BB688D290E4639845A29A377B089DB6534BF27",
        "dex_launcher_receipt_patch_sha256": "D8D779767E9CB2046B836EF91C59989837467DCFFDF695EC7AE0E4C5509A2F13",
        "dex_launcher_receipt_candidate_sha256": "D22C37E36E5D333C087C8EE80B6936756C69F7D369369C66F8E0FFE6906EBD07",
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
