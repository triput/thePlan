#!/usr/bin/env python3
"""HELD fake-only checker for the native NP-V-GOOGLE-INVALID preparation v1 (Dex 5FA59395).

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
proven launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) are reused unchanged.

Subjects (raw-pinned): source/candidate runner and suite (source = corrected Google
scheduler-native-google-refresh-prep-dex-v3, candidate =
scheduler-native-google-invalid-prep-matt-v1), their three diffs, the unchanged
transcript (79025EC5), source/candidate runner-config, launch-config and
docker-ops-config, both payload and nested manifests, the unchanged peer (17EA148E),
sanitizer (69F59AF1) and auth seed (66FEEA81), and seven unchanged production files that
define the invalid_grant contract (transport, adapters, dispatch, refresh, refresh_import,
transport policy, alias canonicalizer).

Execution surfaces (all fake; no socket, TLS, certificate, PKI, DB, Docker, thread,
process, ASGI or vendor package):
- BEHAVIORAL: the actual unchanged google_token_invalid_grant_script (executed inside a
  privately registered ModuleType so frozen dataclasses resolve their module) serialized
  by the actual peer serializer; the actual sanitizer redact_mapping/_forbidden_key.
- STRUCTURAL (AST/text only): preservation, the production invalid_grant contract anchors,
  and the case body wiring (ingress, setup-only primary, observers inside try / restored /
  identity-guarded, exact public/native/state/unrelated/peer guards, single retirement).
  _run_np_v_google_invalid itself is NOT executed.

Proof scope: finite fixture/source properties. NOT proved: production rejection behavior,
typed reauthorization, TOKEN rollback, skipped IMPORT, the not-ready readiness values,
native TLS, wire timing or any T06 requirement.
"""
from __future__ import annotations

import ast
import builtins
import dataclasses  # noqa: F401  (disclosed unpinned runtime; extracted frozen dataclasses)
import hashlib
import json
import json.decoder
import json.scanner
import os
import re
import sys
import textwrap
import types
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-native-google-invalid-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/source.py": "FA9AF0A4DEFB974998A0714A3FBC024F70E5C145C08A225E216388B6AACEF1BE",
    "runner/candidate.py": "5852A6D365112CFE0A422F1E23C9F7F995A16CA00A510DDE82EF1E7CCAA66995",
    "suite/source.py": "E028812B852C73A1183D609803A450AB41B42CCDE44B4DEE4441EEDB21EA7D1A",
    "suite/candidate.py": "15C841CA2206B7A45CA52D2E0AA7318F7E3C8AC1A79F4485AC1775AA39C0CDA7",
    "transcript/unchanged.py": "79025EC55B3EFED65D610494753401F65818068B97DA76ACD626ED183C94B513",
    "diff/np_runner_entry.py.diff": "4DB5A3D33D9A766DD2898DCB4F43D11919DC59A2E0A0B5166FBEB2253A604835",
    "diff/np_suite.py.diff": "EBABB97F0AA68675BEA357FAD53893F4BBF046B15F35212C299203E359D1A9EB",
    "diff/runner-config.json.diff": "A1DBAFC4C9FFA8554ABF1F98BCE4C04C4BF64D1E7508A97F606259ACB5C0743C",
    "config/source-runner-config.json": "95278DF6B3756F39B5D45CF24C96B3435B20394D3A951FAD95DE5FB76095E7ED",
    "config/candidate-runner-config.json": "82B75D9F8EE0A102FE50FC31EF9C19C7792A77E85F28645497BCA7BFA6353826",
    "config/source-launch-config.json": "AF09151FDBD7734CA3613CF627FFD2CF808F805A8B9F0F35E4A69BF6FF6B7977",
    "config/candidate-launch-config.json": "180E9A4C1A347CA1CB1F61DCD919C7B13520C8D9B1C97727E79C8E8791F029AC",
    "config/source-docker-ops-config.json": "71CC87C42C2941001383D8126EAE48BA75B56EA18F4BA1A2791AF4D593FD2F8D",
    "config/candidate-docker-ops-config.json": "7725A15403FDBE699869FB105A0F543B0C28F70D4353D5DFEF615A0BC2A8315E",
    "manifest/source.txt": "001B0B8B9B4D71F23D0EDC61B652B2EED866B6B3F10381A9F139DFEDBD7DD1E4",
    "manifest/candidate.txt": "B5FC0353EAD1E66EB3E48FFA42606142A8FB6BE39B66AB8B0193BAEB01825A5F",
    "manifest/source-nested.txt": "FD3AB617FB33D6DDA89A9179929EA6A6FA743C0C115D2B76C104D40B7361B174",
    "manifest/candidate-nested.txt": "2C72B6A225616C113C952581DE011027A66AFA796BDE7663CB9366A95433A23E",
    "fixture/np_provider_peer.py": "17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039",
    "fixture/np_receipts.py": "69F59AF10FF5A6FAED469E4C93DCB128F741C50444CC31E37737EC4889B708FD",
    "fixture/np_auth_seed.py": "66FEEA815C7B196A78117229F80769ADDF8428CB073A586B59E2D81491419150",
    "app/covering_http_transport.py": "29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368",
    "app/covering_domain_adapters.py": "BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C",
    "app/covering_domain_dispatch.py": "E73EFF6812A191F3F03431B98990BBF3C61D09D8398101AC804DBD2B2E7F6566",
    "app/covering_refresh.py": "0605E983F728D99D90BD50CCB85A6FC71509FCFBC0ADF50B7C2E3280E3603E5E",
    "app/covering_refresh_import.py": "84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339",
    "app/covering_transport_policy.py": "5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88",
    "app/calendar_alias_canonicalize.py": "A661FE9287E0BE086CCB070DF8F227D2449CA9B70303140A7E38B4015A71946F",
}
RUNTIME_MODULE_PINS = {
    "json_init_pin": ("json", "FEB17670E443E5DB2723F217727DCC5D5E155C40E4E6935B16061C88542F24E7"),
    "json_decoder_pin": ("json.decoder", "B719FBCFCEBD2B174F076E71292E22B1A17D9E258DBE896C768325383BAD4F80"),
    "json_scanner_pin": ("json.scanner", "9841566FB17315EBDD40A1CA9CB214F02CDE7171B187D4DC821C80120EA853C3"),
}
UNPINNED_RUNTIME = ("dataclasses", "typing", "hashlib", "textwrap")

CONTROL_IDS = (
    "SUBJECT-PINS",
    "RUNTIME-PROVENANCE",
    "DIFF-REDERIVATION",
    "PRESERVED-OUTSIDE-CHANGE",
    "TRANSCRIPT-INVALID-SCRIPT",
    "PRODUCTION-CONTRACT",
    "CASE-WIRING",
    "RECEIPT-RETENTION",
    "CONFIG-AND-IMMUTABLES",
    "ACTUAL-SOURCE-MUTANTS",
)

CASE_ID = "NP-V-GOOGLE-INVALID"
RUN_FN = "_run_np_v_google_invalid"
OWN_ROOT = "scheduler-native-google-invalid-prep-matt-v1"
SOURCE_ROOT = "scheduler-native-google-refresh-prep-dex-v3"
ORACLE = "token_rejected_path_not_ms"
RUNNER_CONSTANT_UNITS = ("GOOGLE_INVALID_CLIENT_PURPOSES", "GOOGLE_INVALID_CLIENT_OUTCOMES",
                         "GOOGLE_INVALID_TOKEN_TERMINAL_SEQUENCE", "GOOGLE_INVALID_ACTION_SUMMARY",
                         "GOOGLE_INVALID_PREFLIGHT_CODE")
RUNNER_ADDED = set(RUNNER_CONSTANT_UNITS) | {RUN_FN}
RUNNER_CHANGED = {"IMPLEMENTED_CASE_IDS", "_make_implemented_case"}
RUNNER_REUSED_UNCHANGED = ("_run_np_v_google_refresh", "_run_np_v_ms_nonexpired", "_install_token_terminal_observer",
                           "_install_worker_exception_observer", "_install_google_parent_observer",
                           "_retire_selected_peer_then_observe", "_google_provider_routes",
                           "_measure_google_credential_state", "_measure_google_events",
                           "_measure_google_subscriptions", "_measure_owner_revision_and_busy")
TRANSCRIPT_UNITS = ("CloseMode", "ExchangeStep", "ExchangeScript", "google_token_invalid_grant_script")
LAUNCH_CHANGED_KEYS = {"batch_id", "case_ids", "manifest_sha256", "docker_ops_config_path",
                       "receipt_directory", "candidate_note", "implementation_increment"}
CHANGED_PAYLOAD_ROWS = {"fixture/np_runner_entry.py": "runner/candidate.py",
                        "fixture/np_suite.py": "suite/candidate.py",
                        "runner-config.json": "config/candidate-runner-config.json"}
CHANGED_NESTED_ROWS = {"payload/" + k: v for k, v in CHANGED_PAYLOAD_ROWS.items()}
CHANGED_NESTED_ROWS.update({"payload/SHA256SUMS.txt": "manifest/candidate.txt",
                            "host/launch-config.json": "config/candidate-launch-config.json",
                            "host/docker-ops-config.json": "config/candidate-docker-ops-config.json"})
IMMUTABLE_ROWS = {"fixture/np_provider_peer.py": "fixture/np_provider_peer.py",
                  "fixture/np_receipts.py": "fixture/np_receipts.py",
                  "fixture/np_auth_seed.py": "fixture/np_auth_seed.py",
                  "fixture/np_provider_transcript.py": "transcript/unchanged.py"}
IMMUTABLE_ROWS.update({f"api/app/services/{name}.py": f"app/{name}.py" for name in (
    "covering_http_transport", "covering_domain_adapters", "covering_domain_dispatch", "covering_refresh",
    "covering_refresh_import", "covering_transport_policy", "calendar_alias_canonicalize")})
IMMUTABLE_UNPINNED = ("fixture/np_provider_routes.py", "fixture/np_integrated_runner.py",
                      "fixture/docker_transport.py", "fixture/i01_asgi_app.py", "fixture/prepare-np-provider-tls.sh")
INVALID_BODY = '{"error":"invalid_grant"}'

# Mutation anchors. Runner anchors are mutated INSIDE the named function segment only and
# must occur exactly once there; the transcript anchor inside its named unit only.
M_OUTCOME_WIDENED = ('payload.get("overall_outcome") != "no_op"',
                     'payload.get("overall_outcome") not in ("no_op", "success")')
M_BUMP_TOLERATED = ('            or payload.get("scheduling_revision_bumped") is not False\n', "")
M_PARENT_DROPPED = ("        if parent_terminals != []:\n", "        if False:\n")
M_OUTCOME_LOOSENED = ("        if client_outcomes != GOOGLE_INVALID_CLIENT_OUTCOMES:\n",
                      "        if not client_outcomes:\n")
M_TOKEN_RESTORE_DROPPED = (
    "            CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]\n"
    "            CoveringORMConnection.token_terminal = real_terminal  # type: ignore[method-assign]\n",
    "            CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]\n"
    "            pass  # mutant: token terminal observer not restored\n")
M_SECOND_RETIRE = ("        retirement_done = True\n        peer_exchanges = list",
                   "        retirement_done = True\n        peer.retire_owned(join_seconds=5.0)\n"
                   "        peer_exchanges = list")
M_UNRELATED_DROPPED = ('            or after["unrelated_owner"] != before["unrelated_owner"]\n', "")
M_KEY_UNALLOWLISTED = ('            "covering_token_terminal": "ROLLBACK_ACKNOWLEDGED",\n',
                       '            "covering_token_terminal_label": "ROLLBACK_ACKNOWLEDGED",\n')
M_BODY_CHANGED = ("""body_template='{"error":"invalid_grant"}',""",
                  """body_template='{"error":"invalid_request"}',""")


class WitnessFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WitnessFailure(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


_SUBJECT_TEXT: dict[str, str] = {}


def subject_text(rel: str) -> str:
    if rel not in _SUBJECT_TEXT:
        raise WitnessFailure(f"subject not admitted:{rel}")
    return _SUBJECT_TEXT[rel]


def check_subject_pins() -> dict[str, Any]:
    observed = {}
    for rel, pin in SUBJECT_PINS.items():
        data = (SUBJECTS / rel).read_bytes()
        digest = sha256_bytes(data)
        require(digest == pin, f"subject pin mismatch:{rel}")
        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
        _SUBJECT_TEXT[rel] = data.decode("utf-8")
        observed[rel] = digest
    return {"subjects": observed, "control_kind": "raw_pin", "observed": "PASS"}


def check_runtime_provenance() -> dict[str, Any]:
    cases = {}
    for case, (module_name, pin) in RUNTIME_MODULE_PINS.items():
        module = sys.modules.get(module_name)
        require(module is not None and getattr(module, "__file__", None), f"runtime module absent:{module_name}")
        require(sha256_bytes(Path(module.__file__).read_bytes()) == pin, f"runtime pin mismatch:{module_name}")
        cases[case] = "PASS"
    disclosed = {name: name in sys.modules for name in UNPINNED_RUNTIME}
    require(all(disclosed.values()), "unpinned runtime module not loaded as disclosed")
    cases["unpinned_runtime_disclosed"] = "PASS"
    return {"cases": cases, "unpinned_runtime_modules": list(UNPINNED_RUNTIME),
            "control_kind": "runtime_provenance_partial", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Literal unified-diff re-derivation
# ---------------------------------------------------------------------------

_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*")


def apply_unified(original: str, diff: str) -> tuple[str, list[str], int]:
    src = original.split("\n")
    lines = diff.split("\n")
    out: list[str] = []
    files: list[str] = []
    pos = 0
    i = 0
    hunks = 0
    while i < len(lines) and not lines[i].startswith("@@"):
        if lines[i].startswith("--- ") or lines[i].startswith("+++ "):
            files.append(lines[i][4:])
        elif lines[i] != "":
            raise WitnessFailure("unexpected diff header line")
        i += 1
    while i < len(lines):
        if lines[i] == "" and i == len(lines) - 1:
            break
        match = _HUNK.fullmatch(lines[i])
        require(match is not None, "malformed hunk header")
        old_len, new_len = int(match.group(2) or "1"), int(match.group(4) or "1")
        start = int(match.group(1)) - 1 if old_len else int(match.group(1))
        require(start >= pos, "overlapping or unordered hunks")
        out.extend(src[pos:start])
        pos = start
        seen_old = seen_new = 0
        i += 1
        while i < len(lines) and not lines[i].startswith("@@"):
            if lines[i] == "" and i == len(lines) - 1:
                break
            tag, body = lines[i][:1], lines[i][1:]
            if tag == " ":
                require(pos < len(src) and src[pos] == body, f"context mismatch at {pos + 1}")
                out.append(body)
                pos += 1
                seen_old += 1
                seen_new += 1
            elif tag == "-":
                require(pos < len(src) and src[pos] == body, f"removal mismatch at {pos + 1}")
                pos += 1
                seen_old += 1
            elif tag == "+":
                out.append(body)
                seen_new += 1
            else:
                raise WitnessFailure("unexpected hunk line")
            i += 1
        require((seen_old, seen_new) == (old_len, new_len), "hunk length mismatch")
        hunks += 1
    out.extend(src[pos:])
    return "\n".join(out), files, hunks


def check_diff_rederivation() -> dict[str, Any]:
    cases = {}
    for case, (source, candidate, diff, label, hunks_expected) in {
        "runner": ("runner/source.py", "runner/candidate.py", "diff/np_runner_entry.py.diff",
                   "payload/fixture/np_runner_entry.py", 3),
        "suite": ("suite/source.py", "suite/candidate.py", "diff/np_suite.py.diff", "payload/fixture/np_suite.py", 1),
        "runner_config": ("config/source-runner-config.json", "config/candidate-runner-config.json",
                          "diff/runner-config.json.diff", "payload/runner-config.json", 1),
    }.items():
        derived, files, hunks = apply_unified(subject_text(source), subject_text(diff))
        require(files == [f"a/{label}", f"b/{label}"] and hunks == hunks_expected
                and derived == subject_text(candidate), f"diff rederivation:{case}")
        cases[case] = "PASS"
    return {"cases": cases, "control_kind": "literal_text", "observed": "PASS"}


# ---------------------------------------------------------------------------
# AST/text helpers (locate segments only)
# ---------------------------------------------------------------------------

def _single(nodes: list[Any], what: str) -> Any:
    require(len(nodes) == 1, f"expected exactly one {what}, found {len(nodes)}")
    return nodes[0]


def node_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def unit_node(text: str, name: str) -> ast.AST:
    return _single([n for n in ast.parse(text).body if node_name(n) == name], f"unit {name}")


def unit_span(text: str, name: str) -> tuple[int, int]:
    node = unit_node(text, name)
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return first, node.end_lineno


def unit_text(text: str, name: str) -> str:
    first, last = unit_span(text, name)
    return textwrap.dedent("\n".join(text.split("\n")[first - 1:last])) + "\n"


def exec_units(text: str, names: tuple[str, ...], namespace: dict[str, Any], label: str) -> dict[str, Any]:
    for name in names:
        source = "from __future__ import annotations\n" + unit_text(text, name)
        exec(compile(source, f"<extracted:{label}:{name}>", "exec"), namespace)
    return namespace


def top_table(text: str) -> dict[str, tuple[str, ...]]:
    table: dict[str, list[str]] = {}
    for node in ast.parse(text).body:
        name = node_name(node)
        if name is not None:
            table.setdefault(name, []).append(ast.dump(node))
    return {name: tuple(dumps) for name, dumps in table.items()}


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [c for c in ast.walk(node) if isinstance(c, ast.Call) and (
        (isinstance(c.func, ast.Name) and c.func.id == name)
        or (isinstance(c.func, ast.Attribute) and c.func.attr == name))]


def _kw(call: ast.Call, name: str) -> ast.AST:
    return _single([k.value for k in call.keywords if k.arg == name], f"keyword {name}")


def _mutate_unit(text: str, unit: str, mutation: tuple[str, str]) -> str:
    """Apply a mutation only inside one top-level unit; the anchor must be unique there."""
    first, last = unit_span(text, unit)
    lines = text.split("\n")
    segment = "\n".join(lines[first - 1:last])
    require(segment.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
    return "\n".join(lines[:first - 1] + segment.replace(*mutation).split("\n") + lines[last:])


def _expr(source: str) -> str:
    # Parenthesized so a multi-line guard parses as one expression (parentheses add no AST node).
    return ast.dump(ast.parse("(" + textwrap.dedent(source).strip() + ")", mode="eval").body)


def has_guard(fn: ast.AST, source: str) -> bool:
    """Exactly one `if <test>: raise SuiteStop(...)` in fn whose test equals the expression."""
    wanted = _expr(source)
    found = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and len(node.body) == 1 and isinstance(node.body[0], ast.Raise):
            exc = node.body[0].exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "SuiteStop" \
                    and ast.dump(node.test) == wanted:
                found += 1
    return found == 1


class Sandbox:
    """Owned sys.modules entries: refuses a pre-existing name, removes only its own on every exit path."""

    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = names
        self.installed: list[str] = []

    def __enter__(self) -> "Sandbox":
        require(all(name not in sys.modules for name in self.names), "sandbox precondition")
        return self

    def put(self, name: str, module: types.ModuleType) -> types.ModuleType:
        require(name in self.names and name not in sys.modules, f"sandbox name not declared or present:{name}")
        sys.modules[name] = module
        self.installed.append(name)
        return module

    def __exit__(self, *exc_info: Any) -> bool:
        for name in self.installed:
            sys.modules.pop(name, None)
        return False


def check_preserved_outside_change() -> dict[str, Any]:
    cases = {}
    src_text, cand_text = subject_text("runner/source.py"), subject_text("runner/candidate.py")
    src, cand = top_table(src_text), top_table(cand_text)
    require(set(cand) - set(src) == RUNNER_ADDED and set(src) <= set(cand)
            and {n for n in src if src[n] != cand[n]} == RUNNER_CHANGED, "preserved:runner")
    cases["runner"] = "PASS"
    require(all(unit_text(src_text, n) == unit_text(cand_text, n) for n in RUNNER_REUSED_UNCHANGED),
            "preserved:existing bodies and helpers")
    cases["existing_bodies_and_helpers_byte_identical"] = "PASS"
    ss, sc = top_table(subject_text("suite/source.py")), top_table(subject_text("suite/candidate.py"))
    rows_src = rows(subject_text("manifest/source.txt"))
    require(set(ss) == set(sc) and {n for n in ss if ss[n] != sc[n]} == {"CASE_IMPLEMENTATION_NOTES"}
            and rows_src.get("fixture/np_provider_transcript.py") == SUBJECT_PINS["transcript/unchanged.py"],
            "preserved:transcript and suite")
    cases["transcript_unchanged_and_suite_note_only"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# TRANSCRIPT-INVALID-SCRIPT (behavioral: actual unchanged script + actual serializer)
# ---------------------------------------------------------------------------

def oracle_transcript(transcript_text: str) -> dict[str, str]:
    from dataclasses import dataclass
    from typing import Literal

    cases = {}
    serializer: dict[str, Any] = {"Any": Any}
    exec_units(subject_text("fixture/np_provider_peer.py"), ("_http_response_bytes",), serializer, "peer")
    with Sandbox(("np_provider_transcript",)) as box:
        # Registered BEFORE executing decorated dataclasses (dataclasses resolves cls.__module__).
        module = box.put("np_provider_transcript", types.ModuleType("np_provider_transcript"))
        module.__dict__.update({"dataclass": dataclass, "Literal": Literal})
        exec_units(transcript_text, TRANSCRIPT_UNITS, module.__dict__, "transcript")
        script = module.google_token_invalid_grant_script()
    recv, send, close = script.steps
    require(len(script.steps) == 3 and (recv.direction, recv.method, recv.path) == ("recv_request", "POST", "/token")
            and send.direction == "send_response" and send.status == 400
            and json.loads(send.body_template) == {"error": "invalid_grant"} and send.body_template == INVALID_BODY
            and (close.direction, close.close_mode) == ("close", "orderly_close_notify"),
            "transcript:invalid grant script")
    cases["script_shape_exact"] = "PASS"
    wire = serializer["_http_response_bytes"](send)
    head, sep, body = wire.partition(b"\r\n\r\n")
    head_lines = head.split(b"\r\n")
    require(sep == b"\r\n\r\n" and body == INVALID_BODY.encode("utf-8") and head_lines[0].startswith(b"HTTP/1.1 400")
            and f"Content-Length: {len(body)}".encode("ascii") in head_lines and b"Connection: close" in head_lines
            and sum(1 for line in head_lines if line.lower().startswith(b"content-length:")) == 1,
            "transcript:fixed length wire")
    cases["fixed_length_wire_not_close_delimited"] = "PASS"
    return cases


def check_transcript() -> dict[str, Any]:
    return {"cases": oracle_transcript(subject_text("transcript/unchanged.py")),
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# PRODUCTION-CONTRACT (structural anchors in the unchanged production source)
# ---------------------------------------------------------------------------

def _ordered(text: str, anchors: tuple[str, ...]) -> bool:
    positions = []
    for anchor in anchors:
        if text.count(anchor) != 1:
            return False
        positions.append(text.index(anchor))
    return positions == sorted(positions)


def check_contract() -> dict[str, Any]:
    cases = {}
    transport = subject_text("app/covering_http_transport.py")
    require(_ordered(transport, (
        "            _admit_fixed_length_complete(response)\n            decoded=json.loads(body)\n",
        'if purpose=="oauth" and response.status>=400:',
        '                if response.status!=400 or decoded.get("error")!="invalid_grant":\n'
        "                    remapped=CoveringRootOutcomeUnknown()\n",
        "remapped=CoveringReauthorizationRequired()",
        "except CoveringReauthorizationRequired as exc:")), "contract:transport")
    cases["transport_exact_invalid_grant_only"] = "PASS"
    adapters = subject_text("app/covering_domain_adapters.py")
    require(_ordered(adapters, (
        "                except CoveringReauthorizationRequired:\n                    changed=False\n"
        "                    result=TokenRejected(PREFLIGHT_ACCOUNT_DISCONNECTED)\n",
        "expected=RootOutcome.COMMIT_ACKNOWLEDGED if changed else RootOutcome.ROLLBACK_ACKNOWLEDGED",
        "if terminal(commit=changed,remaining=remaining) is not expected:")), "contract:adapter")
    cases["adapter_rejection_requires_rollback"] = "PASS"
    dispatch = subject_text("app/covering_domain_dispatch.py")
    require(_ordered(dispatch, (
        "            if type(token) is TokenRejected:\n"
        "                results.append(_static_preflight_result(subscription_id=target.subscription_id,\n"
        "                    window=window, preflight_code=token.code))\n"
        "                continue\n",
        "result, failure = connector.run_target(",
        "final = _classified_role(connector, CoveringRole.ASSESSMENT, assess)")), "contract:dispatch")
    cases["dispatch_skips_import_then_assesses"] = "PASS"
    consts = runner_namespace(subject_text("runner/candidate.py"))
    require(subject_text("app/covering_refresh_import.py").count(
        f'PREFLIGHT_ACCOUNT_DISCONNECTED = "{consts["GOOGLE_INVALID_PREFLIGHT_CODE"]}"') == 1,
        "contract:preflight literal")
    cases["preflight_code_literal_matches"] = "PASS"
    refresh = subject_text("app/covering_refresh.py")
    require(refresh.count('    if import_attempted == 0:\n        return "no_op"\n') == 1
            and refresh.count('        phase: str = "preflight"\n        status: str = "preflight_rejected"\n') == 1
            and _ordered(unit_text(refresh, "_static_preflight_result"),
                         ("preflight_effects=(),", "cause=None,", "upserted=0,")), "contract:public mapping")
    cases["no_op_and_preflight_row_mapping"] = "PASS"
    outcome = consts["GOOGLE_INVALID_CLIENT_OUTCOMES"]
    require(subject_text("app/covering_transport_policy.py").count(
        "class CoveringReauthorizationRequired(Exception):") == 1
            and outcome == [("exception", "CoveringReauthorizationRequired", "app.services.covering_transport_policy")],
            "contract:exception identity")
    cases["typed_exception_module_and_name"] = "PASS"
    return {"cases": cases, "scope_note": "structural anchors in unchanged production source; production behavior "
                                          "is not executed here", "control_kind": "structural_source",
            "observed": "PASS"}


# ---------------------------------------------------------------------------
# CASE-WIRING (structural; the case body is not executed)
# ---------------------------------------------------------------------------

def runner_namespace(runner_text: str) -> dict[str, Any]:
    ns: dict[str, Any] = {}
    for name in RUNNER_CONSTANT_UNITS:
        exec(compile(unit_text(runner_text, name), f"<extracted:runner:{name}>", "exec"), ns)
    return ns


def suite_oracles(text: str, case_id: str) -> list[str]:
    for call in ast.walk(ast.parse(text)):
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "CaseDecl" and call.args \
                and isinstance(call.args[0], ast.Constant) and call.args[0].value == case_id:
            return [o.args[0].value for o in ast.walk(call) if isinstance(o, ast.Call) and isinstance(o.func, ast.Name)
                    and o.func.id == "_o"]
    raise WitnessFailure("suite declaration missing")


def _dict_keys(node: ast.AST) -> set[str]:
    require(isinstance(node, ast.Dict), "wiring:dict expected")
    return {k.value for k in node.keys if isinstance(k, ast.Constant)}


def module_level_names(text: str) -> set[str]:
    names: set[str] = set()

    def visit(stmts: list[ast.stmt]) -> None:
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
            for field in ("body", "orelse", "finalbody"):
                if isinstance(getattr(node, field, None), list):
                    visit(getattr(node, field))
            for handler in getattr(node, "handlers", []) or []:
                visit(handler.body)

    visit(ast.parse(text).body)
    return names


def free_names(fn: ast.AST) -> set[str]:
    bound: set[str] = set()
    loaded: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            (bound if isinstance(node.ctx, (ast.Store, ast.Del)) else loaded).add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
    return loaded - bound - set(dir(builtins))


RESULT_GUARD = """
results != [{"subscription_id": str(primary_target), "phase": "preflight", "status": "preflight_rejected",
             "preflight_code": GOOGLE_INVALID_PREFLIGHT_CODE, "preflight_effects": [], "cause": None, "upserted": 0}]
"""
READINESS_GUARD = """
    coverage_action.get("all_requested_covering_ok") is not False
    or freshness_requested.get("ok") is not False
    or readiness.get("scheduling_ready") is not False
    or freshness_all.get("ok") is not False
    or readiness.get("assessment_error") is not None
    or type(scheduling_revision) is not int
"""
REVISION_GUARD = """
    owner_after != owner_before
    or scheduling_revision != owner_after["scheduling_revision"]
    or payload.get("scheduling_revision_at_start") != owner_before["scheduling_revision"]
    or payload.get("scheduling_revision_at_end") != owner_after["scheduling_revision"]
    or payload.get("scheduling_revision_bumped") is not False
"""
UNRELATED_GUARD = """
    after["unrelated_credential"] != before["unrelated_credential"]
    or after["unrelated_coverage"] != before["unrelated_coverage"]
    or after["unrelated_events"] != before["unrelated_events"]
    or after["unrelated_subscriptions"] != before["unrelated_subscriptions"]
    or after["unrelated_owner"] != before["unrelated_owner"]
"""
PEER_GUARD = """
    int(peer_state.get("connection_count_admitted") or 0) != 1
    or int(peer_state.get("connection_count_served") or 0) != 1
    or [row.get("method") for row in peer_exchanges] != ["POST"]
    or peer_exchanges[0].get("path") != "/token"
    or peer_exchanges[0].get("close_mode_observed") != "orderly_close_notify"
    or peer_state.get("bytes_sent") != expected_bytes_sent
"""


def oracle_wiring(runner_text: str) -> dict[str, str]:
    cases = {}
    fn = unit_node(runner_text, RUN_FN)
    text = unit_text(runner_text, RUN_FN)
    implemented = ast.literal_eval(unit_node(runner_text, "IMPLEMENTED_CASE_IDS").value.args[0])
    mapper = unit_node(runner_text, "_make_implemented_case")
    require(implemented == {"NP-V-MS-NONEXPIRED", "NP-V-GOOGLE-REFRESH", CASE_ID}
            and len(_calls(mapper, RUN_FN)) == 1 and len(_calls(mapper, "_run_np_v_google_refresh")) == 1
            and f'"{CASE_ID}"' in unit_text(runner_text, "_make_implemented_case"), "wiring:case mapping")
    cases["case_mapping_exact"] = "PASS"
    oracle_call = _single(_calls(fn, "check_oracles_immediate"), "oracle check")
    receipt = _single(_calls(fn, "case_result_receipt"), "receipt")
    declared = suite_oracles(subject_text("suite/candidate.py"), CASE_ID)
    require(declared == suite_oracles(subject_text("suite/source.py"), CASE_ID) == [ORACLE]
            and _dict_keys(oracle_call.args[1]) == {ORACLE} and _dict_keys(_kw(receipt, "observations")) == {ORACLE},
            "wiring:oracle names")
    cases["oracle_name_equals_declaration"] = "PASS"
    build = _single(_calls(fn, "build_i01_asgi_app"), "asgi build")
    post = [c for c in _calls(fn, "post") if isinstance(c.func, ast.Attribute)
            and isinstance(c.func.value, ast.Name) and c.func.value.id == "client"]
    peer_call = _single(_calls(fn, "SyntheticProviderPeer"), "peer construction")
    require(isinstance(_kw(build, "clock"), ast.Name) and _kw(build, "clock").id == "monotonic"
            and len(_calls(fn, "install_binding")) == 1 and len(_calls(fn, "CoveringReleasePlan")) == 1
            and len(post) == 1 and isinstance(post[0].args[0], ast.Name) and post[0].args[0].id == "COVERING_PATH"
            and 'inspect.signature(CoveringHTTP.__init__).parameters["transport_factory"].default is not JoinedTLS' in text
            and "if self.transport_factory is not JoinedTLS:" in text and not _calls(fn, "transport_factory")
            and len(_calls(fn, "google_token_invalid_grant_script")) == 1
            and ast.unparse(_kw(peer_call, "route")) == "token_route"
            and ast.unparse(_kw(peer_call, "script")) == "invalid_script"
            and not _calls(fn, "refresh_access_token") and not _calls(fn, "get_valid_access_token"),
            "wiring:production ingress")
    cases["production_ingress_default_tls_no_shortcut"] = "PASS"
    helper = _calls(fn, "_retire_selected_peer_then_observe")
    owned = _calls(fn, "retire_owned")
    final = [n for n in ast.walk(fn) if isinstance(n, ast.Try) and n.finalbody]
    guard = [n for t in final for n in ast.walk(ast.Module(body=t.finalbody, type_ignores=[]))
             if isinstance(n, ast.If) and ast.dump(n.test) == _expr(
                 "not retirement_attempted and peer._worker is not None and not peer.life.joined")]
    require(len(helper) == 1 and len(owned) == 1 and len(guard) == 1
            and owned[0] in list(ast.walk(guard[0])), "wiring:single retirement")
    cases["single_retirement_paths"] = "PASS"
    ns = runner_namespace(runner_text)
    require(ns["GOOGLE_INVALID_CLIENT_PURPOSES"] == [("POST", "oauth")]
            and ns["GOOGLE_INVALID_TOKEN_TERMINAL_SEQUENCE"] == [
                {"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True, "commit_requested": False}]
            and ns["GOOGLE_INVALID_ACTION_SUMMARY"] == {"requested": 1, "preflight_rejected": 1,
                                                        "import_attempted": 0, "import_ok": 0, "import_failed": 0}
            and ns["GOOGLE_INVALID_PREFLIGHT_CODE"] == "CALENDAR_ACCOUNT_DISCONNECTED", "wiring:constants")
    cases["constants_literal"] = "PASS"
    seed_fn = unit_node(subject_text("fixture/np_auth_seed.py"), "seed_browser_owner_with_subscriptions")
    params = {a.arg for a in seed_fn.args.args + seed_fn.args.kwonlyargs}
    browser = unit_node(subject_text("fixture/np_auth_seed.py"), "BrowserSeed")
    fields = {n.target.id for n in browser.body if isinstance(n, ast.AnnAssign)}
    used = {a.attr for a in ast.walk(fn) if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)
            and a.value.id in ("seed", "unrelated")}
    seeds = _calls(fn, "seed_browser_owner_with_subscriptions")
    planting = [n for n in ast.walk(fn) if isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr in ("role", "external_calendar_id")]
    setup_try = [t for t in ast.walk(fn) if isinstance(t, ast.Try) and any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "commit"
        and isinstance(c.func.value, ast.Name) and c.func.value.id == "setup" for s in t.body for c in ast.walk(s))]
    commit_line = min((c.lineno for t in setup_try for s in t.body for c in ast.walk(s) if isinstance(c, ast.Call)
                       and isinstance(c.func, ast.Attribute) and c.func.attr == "commit"), default=0)
    in_setup = {id(n) for t in setup_try for s in t.body for n in ast.walk(s)}
    require(len(seeds) == 2 and all({k.arg for k in c.keywords} <= params for c in seeds) and used <= fields
            and all(ast.literal_eval(_kw(c, "subscription_count")) == 1 for c in seeds)
            and len(planting) == 2 and len(setup_try) == 1
            and sorted(ast.unparse(n) for n in planting) == [
                "primary_row.external_calendar_id = GOOGLE_PRIMARY_ALIAS",
                "primary_row.role = CalendarSubscriptionRole.primary"]
            and all(id(n) in in_setup and n.lineno < commit_line for n in planting)
            and not [n for n in ast.walk(fn) if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                     and n.attr == "is_enabled"], "wiring:seed and primary setup")
    cases["seed_signature_and_primary_setup_only"] = "PASS"
    unresolved = free_names(fn) - module_level_names(runner_text)
    require(not unresolved, f"wiring:free names:{sorted(unresolved)}")
    cases["free_names_resolve"] = "PASS"
    wanted = ("restore_parent_observer()", "restore_worker_observer()", "CoveringHTTP.__init__ = real_init",
              "CoveringORMConnection.token_terminal = real_terminal")
    restoring = [t for t in final if all(w in "\n".join(ast.unparse(s) for s in t.finalbody) for w in wanted)
                 and "restore_parent_observer()" in "\n".join(ast.unparse(s) for s in t.finalbody)]
    installs_inside = bool(restoring) and all(
        any(isinstance(n, ast.Call) and ast.unparse(n.func) == name for s in restoring[0].body for n in ast.walk(s))
        for name in ("_install_token_terminal_observer", "_install_worker_exception_observer",
                     "_install_google_parent_observer"))
    patch_inside = bool(restoring) and any(
        isinstance(n, ast.Assign) and ast.unparse(n) == "CoveringHTTP.__init__ = capturing_init"
        for s in restoring[0].body for n in ast.walk(s))
    outer = [t for t in final if any(isinstance(n, ast.If) and ast.dump(n.test) == _expr(
        "real_terminal is not None and CoveringORMConnection.token_terminal is not real_terminal")
        for s in t.finalbody for n in ast.walk(s))]
    require(len(restoring) == 1 and len(post) == 1
            and any(n is post[0] for s in restoring[0].body for n in ast.walk(s))
            and installs_inside and patch_inside and len(outer) == 1
            and "real_terminal = CoveringORMConnection.token_terminal" in text
            and has_guard(fn, "CoveringORMConnection.token_terminal is not real_terminal "
                              "or CoveringHTTP.__init__ is not real_init"), "wiring:observers restored")
    cases["observers_inside_try_restored_and_guarded"] = "PASS"
    require(has_guard(fn, 'not isinstance(payload, dict) or payload.get("overall_outcome") != "no_op"')
            and has_guard(fn, RESULT_GUARD) and has_guard(fn, READINESS_GUARD)
            and has_guard(fn, "oauth_requests != 1")
            and has_guard(fn, "[(row.get(\"method\"), row.get(\"purpose\")) for row in client_inventory] "
                              "!= GOOGLE_INVALID_CLIENT_PURPOSES")
            and has_guard(fn, "client_outcomes != GOOGLE_INVALID_CLIENT_OUTCOMES")
            and has_guard(fn, "token_sequence != GOOGLE_INVALID_TOKEN_TERMINAL_SEQUENCE")
            and has_guard(fn, "parent_terminals != []") and has_guard(fn, "worker_exceptions"),
            "wiring:public and native guards")
    cases["public_and_native_guards_exact"] = "PASS"
    require(has_guard(fn, 'after["credential"] != before["credential"] '
                          'or after["credential"]["refreshed_access_match"] is not False')
            and has_guard(fn, 'after["coverage"] != before["coverage"] or after["events"] '
                              'or after["subscriptions"] != expected_subscriptions')
            and has_guard(fn, REVISION_GUARD) and has_guard(fn, UNRELATED_GUARD), "wiring:state guards")
    cases["state_revision_and_unrelated_guards_exact"] = "PASS"
    require(has_guard(fn, PEER_GUARD), "wiring:peer inventory guard")
    cases["peer_inventory_guard_exact"] = "PASS"
    return cases


def check_wiring() -> dict[str, Any]:
    return {"cases": oracle_wiring(subject_text("runner/candidate.py")),
            "scope_note": "structural only: the case body is not executed",
            "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# RECEIPT-RETENTION
# ---------------------------------------------------------------------------

def receipt_namespace() -> dict[str, Any]:
    ns: dict[str, Any] = {"Any": Any}
    text = subject_text("fixture/np_receipts.py")
    for name in ("_FORBIDDEN_KEY_FRAGMENTS", "_ALLOWLISTED_EVIDENCE_KEYS"):
        exec(compile(unit_text(text, name), f"<extracted:receipts:{name}>", "exec"), ns)
    exec_units(text, ("_forbidden_key", "redact_mapping"), ns, "receipts")
    return ns


def oracle_retention(runner_text: str) -> dict[str, str]:
    cases = {}
    ns = receipt_namespace()
    fn = unit_node(runner_text, RUN_FN)
    oracle_call = _single(_calls(fn, "check_oracles_immediate"), "oracle check")
    receipt = _single(_calls(fn, "case_result_receipt"), "receipt")
    declared_drop = set(map(id, ast.walk(oracle_call))) | set(map(id, ast.walk(_kw(receipt, "observations"))))
    keys = [k.value for node in ast.walk(fn) if isinstance(node, ast.Dict) and id(node) not in declared_drop
            for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    consts = runner_namespace(runner_text)
    keys += [k for row in consts["GOOGLE_INVALID_TOKEN_TERMINAL_SEQUENCE"] for k in row]
    keys += list(consts["GOOGLE_INVALID_ACTION_SUMMARY"])
    require(len(keys) > 40 and {"token_terminal", "covering_token_terminal"} <= set(keys)
            and not [k for k in keys if ns["_forbidden_key"](k)] and ns["_forbidden_key"](ORACLE) is True,
            "retention:no forbidden key")
    cases["every_emitted_key_survives_oracle_drop_disclosed"] = "PASS"
    sample = {"token_terminal": consts["GOOGLE_INVALID_TOKEN_TERMINAL_SEQUENCE"],
              "covering_token_terminal": "ROLLBACK_ACKNOWLEDGED", "oauth_request_count": 1,
              "preflight_code": "CALENDAR_ACCOUNT_DISCONNECTED", "observations": {ORACLE: "OBSERVED"},
              "nested": {"refresh_token": "R", "ok": 1}}
    out = ns["redact_mapping"](sample)
    require(all(out[k] == sample[k] for k in ("token_terminal", "covering_token_terminal", "oauth_request_count",
                                               "preflight_code"))
            and out["observations"] == {} and out["nested"] == {"ok": 1}, "retention:typed evidence survives")
    cases["typed_evidence_survives_oracle_key_dropped"] = "PASS"
    return cases


def check_retention() -> dict[str, Any]:
    return {"cases": oracle_retention(subject_text("runner/candidate.py")),
            "disclosure": f"{ORACLE} contains 'token' and is dropped by the unchanged sanitizer; it is enforced in "
                          "memory and its evidence is retained under token_terminal/covering_token_terminal",
            "control_kind": "extracted_behavior_fake_and_structural", "observed": "PASS"}


# ---------------------------------------------------------------------------
# CONFIG-AND-IMMUTABLES
# ---------------------------------------------------------------------------

def rows(text: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in text.splitlines():
        pin, sep, rel = line.partition("  ")
        require(sep == "  " and re.fullmatch(r"[0-9A-F]{64}", pin) is not None and rel not in table,
                "malformed manifest row")
        table[rel] = pin
    return table


def check_config() -> dict[str, Any]:
    cases = {}
    cfg, src = (json.loads(subject_text(f"config/{side}-runner-config.json")) for side in ("candidate", "source"))
    require(cfg.get("case_ids") == [CASE_ID] and cfg.get("expected_unknown_cases") == [] and cfg.get("launch_ready") is False
            and src.get("launch_ready") is False and src.get("case_ids") == ["NP-V-GOOGLE-REFRESH"]
            and {k: v for k, v in cfg.items() if k != "case_ids"} == {k: v for k, v in src.items() if k != "case_ids"},
            "config:runner")
    cases["runner_config"] = "PASS"
    launch, src_launch = (json.loads(subject_text(f"config/{side}-launch-config.json")) for side in ("candidate", "source"))
    note = str(launch.get("candidate_note"))
    require(launch.get("launch_ready") is False and launch.get("candidate_launch_ready_staged") is False
            and launch.get("launch_authorized") is False and launch.get("human_launch_authorized") is False
            and launch.get("case_ids") == [CASE_ID] and launch.get("batch_id") == "np-v-google-invalid-single-case"
            and launch.get("expected_unknown_cases") == []
            and launch.get("implementation_increment", {}).get("implemented_case_ids")
            == ["NP-V-MS-NONEXPIRED", "NP-V-GOOGLE-REFRESH", CASE_ID]
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and OWN_ROOT in str(launch.get("docker_ops_config_path")) and OWN_ROOT in str(launch.get("receipt_directory"))
            and SOURCE_ROOT not in str(launch.get("docker_ops_config_path"))
            and "host launch_ready=false" in note and "runner-config launch_ready=false" in note
            and set(launch) == set(src_launch)
            and all(launch[k] == src_launch[k] for k in src_launch if k not in LAUNCH_CHANGED_KEYS), "config:launch")
    cases["launch_config"] = "PASS"
    d_src, d_cand = (subject_text(f"config/{side}-docker-ops-config.json") for side in ("source", "candidate"))
    require(d_src.count(SOURCE_ROOT) == 7 and d_src.replace(SOURCE_ROOT, OWN_ROOT) == d_cand, "config:docker rename")
    cases["docker_ops_root_rename_only"] = "PASS"
    s_rows, c_rows = rows(subject_text("manifest/source.txt")), rows(subject_text("manifest/candidate.txt"))
    changed = {r for r in s_rows if s_rows[r] != c_rows.get(r)}
    require(len(s_rows) == 257 and set(s_rows) == set(c_rows) and changed == set(CHANGED_PAYLOAD_ROWS)
            and all(c_rows[r] == SUBJECT_PINS[s] for r, s in CHANGED_PAYLOAD_ROWS.items()), "config:payload delta")
    cases["payload_delta_exact"] = "PASS"
    s_nest, c_nest = rows(subject_text("manifest/source-nested.txt")), rows(subject_text("manifest/candidate-nested.txt"))
    changed = {r for r in s_nest if s_nest[r] != c_nest.get(r)}
    require(len(s_nest) == 269 and set(s_nest) == set(c_nest) and changed == set(CHANGED_NESTED_ROWS)
            and all(c_nest[r] == SUBJECT_PINS[s] for r, s in CHANGED_NESTED_ROWS.items()), "config:nested delta")
    cases["nested_delta_exact"] = "PASS"
    api = [r for r in s_rows if r.startswith("api/")]
    require(len(api) == 234 and all(s_rows[r] == c_rows[r] for r in api)
            and all(c_rows.get(r) == SUBJECT_PINS[s] == s_rows.get(r) for r, s in IMMUTABLE_ROWS.items())
            and all(r in s_rows and s_rows[r] == c_rows[r] for r in IMMUTABLE_UNPINNED), "config:immutables")
    cases["api_transcript_peer_seed_sanitizer_immutable"] = "PASS"
    return {"cases": cases, "control_kind": "config_data", "observed": "PASS"}


# ---------------------------------------------------------------------------
# ACTUAL-SOURCE-MUTANTS
# ---------------------------------------------------------------------------

def _expect_detected(name: str, action: Callable[[], Any], prefix: str) -> str:
    try:
        action()
    except WitnessFailure as exc:
        if not str(exc).startswith(prefix):
            raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
        return "DETECTED"
    except BaseException:  # noqa: BLE001
        raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
    raise WitnessFailure(f"mutant survived:{name}")


MUTANT_KINDS = {"invalid_grant_body_changed": "behavioral", "covering_token_key_unallowlisted": "behavioral_sanitizer",
                "success_outcome_admitted": "structural", "revision_bump_tolerated": "structural",
                "parent_check_dropped": "structural", "client_outcome_loosened": "structural",
                "token_restore_dropped": "structural", "second_retirement": "structural",
                "unrelated_owner_check_dropped": "structural"}


def check_mutants() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    transcript = subject_text("transcript/unchanged.py")

    def wiring(mutation: tuple[str, str]) -> Callable[[], Any]:
        return lambda: oracle_wiring(_mutate_unit(runner, RUN_FN, mutation))

    mutants = {
        "invalid_grant_body_changed": (
            lambda: oracle_transcript(_mutate_unit(transcript, "google_token_invalid_grant_script", M_BODY_CHANGED)),
            "transcript:invalid grant script"),
        "covering_token_key_unallowlisted": (
            lambda: oracle_retention(_mutate_unit(runner, RUN_FN, M_KEY_UNALLOWLISTED)), "retention:no forbidden key"),
        "success_outcome_admitted": (wiring(M_OUTCOME_WIDENED), "wiring:public and native guards"),
        "revision_bump_tolerated": (wiring(M_BUMP_TOLERATED), "wiring:state guards"),
        "parent_check_dropped": (wiring(M_PARENT_DROPPED), "wiring:public and native guards"),
        "client_outcome_loosened": (wiring(M_OUTCOME_LOOSENED), "wiring:public and native guards"),
        "token_restore_dropped": (wiring(M_TOKEN_RESTORE_DROPPED), "wiring:observers restored"),
        "second_retirement": (wiring(M_SECOND_RETIRE), "wiring:single retirement"),
        "unrelated_owner_check_dropped": (wiring(M_UNRELATED_DROPPED), "wiring:state guards"),
    }
    results = {name: _expect_detected(name, action, prefix) for name, (action, prefix) in mutants.items()}
    return {"mutants": results, "mutant_kinds": MUTANT_KINDS, "control_kind": "actual_source_mutant",
            "observed": "PASS"}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

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


def compare_inventory(expected: dict[str, list[str]], actual: dict[str, list[str]]) -> None:
    require(list(expected) == list(actual), "inventory control keys differ")
    for key, cases in expected.items():
        require(list(actual[key]) == list(cases), f"inventory cases differ:{key}")


def run_checks() -> dict[str, Any]:
    if RESULT.exists():
        raise WitnessFailure("existing result; no replay")
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    require(expected.get("kind") == "native-google-invalid-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "TRANSCRIPT-INVALID-SCRIPT": check_transcript,
        "PRODUCTION-CONTRACT": check_contract,
        "CASE-WIRING": check_wiring,
        "RECEIPT-RETENTION": check_retention,
        "CONFIG-AND-IMMUTABLES": check_config,
        "ACTUAL-SOURCE-MUTANTS": check_mutants,
    }
    require(tuple(functions) == CONTROL_IDS, "internal control order")
    controls = {}
    for control_id, function in functions.items():
        try:
            controls[control_id] = function()
        except WitnessFailure:
            raise
        except Exception as exc:
            raise WitnessFailure(f"{control_id}:{type(exc).__name__}") from None
    actual_nested = {k: list(v.get("cases") or v.get("mutants") or {})
                     for k, v in controls.items() if v.get("cases") or v.get("mutants")}
    compare_inventory(expected.get("nested_case_ids") or {}, actual_nested)
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    nested = sum(len(v.get("cases") or v.get("mutants") or {"_": 1}) for v in controls.values())
    require(nested == expected.get("expected_nested_predicates"), "nested predicate total")
    return {
        "kind": "fake-native-provider-structural-result",
        "packet": PACKET_NAME,
        "executed": True,
        "launch_authorized": False,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        "native_proof": False,
        "controls": controls,
        "control_ids_in_order": list(controls.keys()),
        "passed": len(controls) - len(failed),
        "failed": len(failed),
        "failed_controls": failed,
        "nested_predicates": nested,
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
