#!/usr/bin/env python3
"""HELD fake-only checker for the native NP-T03 B2a preparation (Dex 21BBE5B7, decision D46E6CF8).

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned): source/candidate runner, transcript and suite (source = passed
scheduler-native-ms-nonexpired-retirement-launch-matt-v2, candidate =
scheduler-native-provider-t03-b2a-prep-matt-v1), their four diffs, source/candidate
runner-config, launch-config and docker-ops-config, both payload and nested
manifests, and the unchanged peer (17EA148E), routes (9CBDE09C) and sanitizer.

Execution surfaces (all fake; no socket, TLS, certificate, PKI, DB, Docker, thread,
process or vendor package):
- BEHAVIORAL (extracted actual source units with named fakes): the D1 negative helper,
  the unchanged positive helper, and _t03_observe wired to the ACTUAL routes module and
  the actual transcript script units (each executed inside a privately registered
  ModuleType so future-annotated dataclasses resolve their module), the actual peer
  response serializer, and named fakes for the peer, CoveringHTTP, JoinedTLS, budget and
  policy. The actual stdlib ssl.SSLCertVerificationError class is used as a value only.
- STRUCTURAL (AST/text only): preservation, case bodies, oracle names, absence of schema
  setup, emitted receipt keys and configuration.

Proof scope: finite fixture/source properties. NOT proved: native certificate
verification, OpenSSL/TLS alert or peer error classes, wire timing, any T03 requirement.
"""
from __future__ import annotations

import ast
import email.feedparser
import email.parser
import hashlib
import http.client
import json
import json.decoder
import json.scanner
import os
import re
import ssl
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
PACKET_NAME = "scheduler-native-t03-b2a-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/source.py": "A2C32A2042A523BE932826666D87501AA57A6B4D0E4ECCB173AEDF966794B77D",
    "runner/candidate.py": "B9CF830D37B5F9B6E4D24E361C11C2069BC0E0DF692F418E6CB4AF25D52500A4",
    "transcript/source.py": "CFAB2D060BF03779A5B7BB7AF546F57124D5AF501CED6B93FFAAB76ED86AB6A3",
    "transcript/candidate.py": "7EF0CCA026D2A0243102290B7AE393D86F95D09ADD5C672C6AE4820AC07071F3",
    "suite/source.py": "AEC59FCDA058124FDF7265D41B8A660C4AD139CE13417F88FA637542CF9C1673",
    "suite/candidate.py": "F7303ADD3B90F3C8FE531CE26C2FC00C023A747D983F99A9DAD177684AB3478C",
    "diff/np_runner_entry.py.diff": "653D45E76F8CE631FE42C03E6665C7680DE79CD120B0EC265F37DE46BA441C79",
    "diff/np_provider_transcript.py.diff": "A158D735490F7A748BF9242F703181CD834F9A0C6106B424C37DF487D05F4997",
    "diff/np_suite.py.diff": "FC6F37ABB3815B8791F6EDB3673BA27DC6B06DC67292FD9FE44CAFADB2CA00A2",
    "diff/runner-config.json.diff": "5454BEB07BFE806B01A74CBFDE91288A66AC927CEF6462C965140C21D36DC25A",
    "config/source-runner-config.json": "8668F156909260BE7D9A9164757E144190DC79337778FB4CD0B704805DB0D029",
    "config/candidate-runner-config.json": "FF286F1ECE29775EC84592B221180B08FB88C1160F9479BD810435ED3AE35561",
    "config/source-launch-config.json": "03A131BCF99EF1E65E170E9203C37B037E0374EAA25FB0A3974889453A83F6C9",
    "config/candidate-launch-config.json": "F137A0154EAA5672B88F7352F54873E96AC330B763BD9B8067BE41B83614FDB0",
    "config/source-docker-ops-config.json": "5E6CEDCB2CB3D64122B840EBB38D278EED5121D6908102C209FEB98F18099A76",
    "config/candidate-docker-ops-config.json": "F4EFDC381BB8C45DEA65F44706C55C8A2B88D1183E3C262041CF06294949ECA2",
    "manifest/source.txt": "C058ECCED75C8783E8CDF5E5413137386D10E67A0B33C8122ACE5F2A2D24694A",
    "manifest/candidate.txt": "79810C46C3F42EB25C3B3A0BE4720960D5A5CD897F7AF4565BD20762BCD2F195",
    "manifest/source-nested.txt": "DA1D9A157E8F6BCB6512923126D2E76104E9D48CE39E27F40B687B5388C08BB8",
    "manifest/candidate-nested.txt": "538DB16FC2BD16E32A8ED8DC272456197855A79C97EA7219E475DFF201E6C061",
    "fixture/np_provider_peer.py": "17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039",
    "fixture/np_provider_routes.py": "9CBDE09CD1E84DCB6380BC223C9C23791DA3671AC042C13A745291F9CC5A11EA",
    "fixture/np_receipts.py": "69F59AF10FF5A6FAED469E4C93DCB128F741C50444CC31E37737EC4889B708FD",
}
RUNTIME_MODULE_PINS = {
    "http_client_pin": ("http.client", "3A752927A1257EDEBCABAD42CA9508AD532F91C15431755BFBE437A32AB13EB2"),
    "json_init_pin": ("json", "FEB17670E443E5DB2723F217727DCC5D5E155C40E4E6935B16061C88542F24E7"),
    "json_decoder_pin": ("json.decoder", "B719FBCFCEBD2B174F076E71292E22B1A17D9E258DBE896C768325383BAD4F80"),
    "json_scanner_pin": ("json.scanner", "9841566FB17315EBDD40A1CA9CB214F02CDE7171B187D4DC821C80120EA853C3"),
    "email_feedparser_pin": ("email.feedparser", "A3A309A212382FA3CA054DB3150C78B931D9E975FD55EDBC8D6230FDA91A5E6D"),
    "email_parser_pin": ("email.parser", "D8DF38F13F551011D93FEC18166E97BC7E3A0F9D6BD229059A540411C023AB3E"),
}

CONTROL_IDS = (
    "SUBJECT-PINS",
    "RUNTIME-PROVENANCE",
    "DIFF-REDERIVATION",
    "PRESERVED-OUTSIDE-CHANGE",
    "NEGATIVE-HELPER",
    "POSITIVE-HELPER-PRESERVED",
    "OBSERVE-WIRING",
    "CASE-BODIES",
    "RECEIPT-RETENTION",
    "CONFIG-AND-IMMUTABLES",
    "ACTUAL-SOURCE-MUTANTS",
)

T03_IDS = ["NP-T03-VALID", "NP-T03-WRONG-CA", "NP-T03-WRONG-NAME"]
OWN_ROOT = "scheduler-native-provider-t03-b2a-prep-matt-v1"
SOURCE_ROOT = "scheduler-native-ms-nonexpired-retirement-launch-matt-v2"
RUNNER_ADDED = {"T03_CERT_REFUSAL_OUTCOME", "T03_VALID_OUTCOME", "T03_NEGATIVE_PEER_ERROR_KINDS",
                "T03_NEGATIVE_PEER_PHASE", "T03_EXPECTATIONS", "T03_ORACLES", "_retire_negative_peer_then_observe",
                "_t03_observe", "_run_np_t03_case", "_run_np_t03_valid", "_run_np_t03_wrong_ca",
                "_run_np_t03_wrong_name"}
RUNNER_CHANGED = {"IMPLEMENTED_CASE_IDS", "_make_implemented_case"}
TRANSCRIPT_ADDED = {"T03_GET_PATH", "T03_VALID_BODY", "t03_valid_fixed_length_get_script"}
RUNNER_UNITS = ("PEER_SECONDS_DEFAULT", "T03_CERT_REFUSAL_OUTCOME", "T03_VALID_OUTCOME",
                "T03_NEGATIVE_PEER_ERROR_KINDS", "T03_NEGATIVE_PEER_PHASE", "T03_EXPECTATIONS")
LAUNCH_CHANGED_KEYS = {"launch_ready", "batch_id", "case_ids", "manifest_sha256", "docker_ops_config_path",
                       "receipt_directory", "candidate_launch_ready_staged", "candidate_note",
                       "implementation_increment"}
CHANGED_PAYLOAD_ROWS = {"fixture/np_runner_entry.py": "runner/candidate.py",
                        "fixture/np_provider_transcript.py": "transcript/candidate.py",
                        "fixture/np_suite.py": "suite/candidate.py",
                        "runner-config.json": "config/candidate-runner-config.json"}
CHANGED_NESTED_ROWS = {"payload/" + k: v for k, v in CHANGED_PAYLOAD_ROWS.items()}
CHANGED_NESTED_ROWS.update({"payload/SHA256SUMS.txt": "manifest/candidate.txt",
                            "host/launch-config.json": "config/candidate-launch-config.json",
                            "host/docker-ops-config.json": "config/candidate-docker-ops-config.json"})
IMMUTABLE_ROWS = {"fixture/np_provider_peer.py": "fixture/np_provider_peer.py",
                  "fixture/np_provider_routes.py": "fixture/np_provider_routes.py",
                  "fixture/np_receipts.py": "fixture/np_receipts.py"}
IMMUTABLE_UNPINNED = ("fixture/np_integrated_runner.py", "fixture/docker_transport.py", "fixture/i01_asgi_app.py",
                      "fixture/prepare-np-provider-tls.sh", "fixture/np_auth_seed.py")
FIXTURE_CA = "/tmp/np-provider-tls/ca.crt"
WRONG_CA = "/tmp/np-provider-tls/wrong-ca.crt"
GET_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
VALID_WIRE_LEN = 91

# Mutation anchors (each verified unique in the whole candidate runner text).
M_SET_WIDENED = ('T03_NEGATIVE_PEER_ERROR_KINDS = frozenset({"SSLError", "SSLEOFError", "ConnectionResetError"})\n',
                 'T03_NEGATIVE_PEER_ERROR_KINDS = frozenset({"SSLError", "SSLEOFError", "ConnectionResetError", '
                 '"PeerLifecycleError"})\n')
M_NONE_ADMITTED = ("    if type(kind) is not str or kind not in allowed_worker_errors:\n",
                   "    if kind is not None and kind not in allowed_worker_errors:\n")
M_PHASE_DROPPED = ('        or state.get("phase_entered") != expected_phase\n', "")
M_NOTE_DROPPED = ('    if notes != [f"worker_error:{kind}"]:\n'
                  '        raise SuiteStop("negative peer worker_error note is not exactly the returned kind")\n', "")
M_CA_SWAP_MIXED = ('    client_ca = WRONG_CA_PATH if expectation == "wrong_ca" else FIXTURE_CA_PATH\n',
                   '    client_ca = WRONG_CA_PATH if expectation == "wrong_name" else FIXTURE_CA_PATH\n')
M_NAME_ALSO_CA = ('    peer_route = google_api_route(wrong_name=(expectation == "wrong_name"))\n',
                  '    peer_route = google_api_route(wrong_name=(expectation == "wrong_name"), '
                  'wrong_ca=(expectation == "wrong_name"))\n')
M_OUTCOME_WIDENED = ("    elif outcome != T03_CERT_REFUSAL_OUTCOME:\n", '    elif outcome[0] != "exception":\n')
M_SECOND_RETIRE = ('        retirement_attempted = True\n        if expectation == "valid":\n',
                   '        retirement_attempted = True\n        peer.retire_owned(join_seconds=5.0)\n'
                   '        if expectation == "valid":\n')


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
    disclosed = {name: name in sys.modules for name in ("socket", "ssl", "_ssl", "_json")}
    require(disclosed["socket"] is True, "http.client transitive socket import not observed")
    cases["transitive_modules_disclosed"] = "PASS"
    return {"cases": cases, "transitive_modules_loaded": disclosed,
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
        "transcript": ("transcript/source.py", "transcript/candidate.py", "diff/np_provider_transcript.py.diff",
                       "payload/fixture/np_provider_transcript.py", 1),
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
# AST helpers (locate segments only)
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


def unit_text(text: str, name: str) -> str:
    node = unit_node(text, name)
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return textwrap.dedent("\n".join(text.split("\n")[first - 1:node.end_lineno])) + "\n"


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


def _mutate(text: str, mutation: tuple[str, str]) -> str:
    require(text.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
    return text.replace(*mutation)


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


class SuiteStopFake(Exception):
    """Named fake for np_suite.SuiteStop."""


class PeerRetirementUnknownFake(RuntimeError):
    """Named fake for np_provider_peer.PeerRetirementUnknown."""


class PeerLifecycleErrorFake(RuntimeError):
    """Named fake for np_provider_peer.PeerLifecycleError."""


def check_preserved_outside_change() -> dict[str, Any]:
    cases = {}
    src, cand = top_table(subject_text("runner/source.py")), top_table(subject_text("runner/candidate.py"))
    require(set(cand) - set(src) == RUNNER_ADDED and set(src) <= set(cand)
            and {n for n in src if src[n] != cand[n]} == RUNNER_CHANGED, "preserved:runner")
    cases["runner"] = "PASS"
    require(src["_retire_selected_peer_then_observe"] == cand["_retire_selected_peer_then_observe"]
            and unit_text(subject_text("runner/source.py"), "_retire_selected_peer_then_observe")
            == unit_text(subject_text("runner/candidate.py"), "_retire_selected_peer_then_observe"),
            "preserved:positive helper")
    cases["positive_helper_byte_identical"] = "PASS"
    s, c = top_table(subject_text("transcript/source.py")), top_table(subject_text("transcript/candidate.py"))
    ss, sc = top_table(subject_text("suite/source.py")), top_table(subject_text("suite/candidate.py"))
    require(set(c) - set(s) == TRANSCRIPT_ADDED and set(s) <= set(c) and all(s[n] == c[n] for n in s)
            and set(ss) == set(sc) and {n for n in ss if ss[n] != sc[n]} == {"CASE_IMPLEMENTATION_NOTES"},
            "preserved:transcript and suite")
    cases["transcript_and_suite"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# NEGATIVE-HELPER / POSITIVE-HELPER-PRESERVED (behavioral, extracted actual helpers)
# ---------------------------------------------------------------------------

class FakeRetiringPeer:
    """Named fake for retire_owned/sanitized_state only; records every call."""

    def __init__(self, *, retirement: dict[str, Any] | None = None, state: dict[str, Any] | None = None,
                 raises: BaseException | None = None) -> None:
        self.retirement, self.state, self.raises = retirement or {}, state or {}, raises
        self.calls: list[str] = []

    def retire_owned(self, *, join_seconds: float) -> dict[str, Any]:
        self.calls.append(f"retire:{join_seconds}")
        if self.raises is not None:
            raise self.raises
        return dict(self.retirement)

    def sanitized_state(self) -> dict[str, Any]:
        self.calls.append("state")
        return dict(self.state)


REFUSAL_STATE = {"accepted": True, "handshake_complete": False, "request_received": False, "response_sent": False,
                 "bytes_received": 0, "bytes_sent": 0, "exchange_inventory": [], "phase_entered": "accepted",
                 "notes": ["bound:127.0.0.1:443", "worker_error:SSLError"]}


def helper_namespace(runner_text: str) -> dict[str, Any]:
    ns: dict[str, Any] = {"Any": Any}
    for name in RUNNER_UNITS:
        exec(compile(unit_text(runner_text, name), f"<extracted:runner:{name}>", "exec"), ns)
    exec_units(runner_text, ("_retire_selected_peer_then_observe", "_retire_negative_peer_then_observe"), ns, "runner")
    return ns


def call_with_suite(action: Callable[[], Any]) -> dict[str, Any]:
    with Sandbox(("np_suite",)) as box:
        box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStopFake
        try:
            return {"value": action(), "raised": None}
        except BaseException as exc:  # noqa: BLE001
            return {"value": None, "raised": exc}


def negative(ns: dict[str, Any], peer: FakeRetiringPeer) -> dict[str, Any]:
    return call_with_suite(lambda: ns["_retire_negative_peer_then_observe"](
        peer, allowed_worker_errors=ns["T03_NEGATIVE_PEER_ERROR_KINDS"],
        expected_phase=ns["T03_NEGATIVE_PEER_PHASE"], join_seconds=5.0))


def refusal(kind: Any, **override: Any) -> FakeRetiringPeer:
    state = {**REFUSAL_STATE, "notes": ["bound:127.0.0.1:443", f"worker_error:{kind}"], **override}
    return FakeRetiringPeer(retirement={"joined": True, "worker_error_kind": kind}, state=state)


ADVANCED_ROWS = {"handshake_complete": True, "request_received": True, "response_sent": True, "bytes_received": 1,
                 "bytes_sent": 1, "exchange_inventory": [{"method": "GET"}], "phase_entered": "handshake_complete",
                 "accepted": False}


def oracle_negative(runner_text: str) -> dict[str, str]:
    cases = {}
    ns = helper_namespace(runner_text)
    for kind in ("SSLError", "SSLEOFError", "ConnectionResetError"):
        peer = refusal(kind)
        got = negative(ns, peer)
        require(got["raised"] is None and got["value"][0]["worker_error_kind"] == kind
                and got["value"][1]["phase_entered"] == "accepted" and peer.calls == ["retire:5.0", "state"],
                "negative:planned refusal accepted")
    cases["planned_refusal_accepted"] = "PASS"
    # Isolates the None guard: every other predicate is shaped to pass.
    got = negative(ns, refusal(None))
    require(type(got["raised"]) is SuiteStopFake, "negative:none stops")
    cases["none_stops"] = "PASS"
    got = negative(ns, refusal("PeerLifecycleError"))
    got2 = negative(ns, refusal("FileNotFoundError"))
    require(type(got["raised"]) is SuiteStopFake and type(got2["raised"]) is SuiteStopFake,
            "negative:class outside set stops")
    cases["class_outside_set_stops"] = "PASS"
    stops = [type(negative(ns, refusal("SSLError", notes=notes))["raised"]) is SuiteStopFake for notes in (
        [], ["worker_error:SSLError", "worker_error:SSLError"], ["worker_error:SSLEOFError"])]
    require(all(stops), "negative:note mismatch stops")
    cases["note_mismatch_stops"] = "PASS"
    stops = {key: type(negative(ns, refusal("SSLError", **{key: value}))["raised"]) is SuiteStopFake
             for key, value in ADVANCED_ROWS.items()}
    require(all(stops.values()), "negative:advanced state stops")
    cases["advanced_state_stops"] = "PASS"
    unjoined = FakeRetiringPeer(retirement={"joined": False, "worker_error_kind": "SSLError"}, state=REFUSAL_STATE)
    unknown = PeerRetirementUnknownFake("owned peer worker unjoined")
    raising = FakeRetiringPeer(raises=unknown)
    a, b = negative(ns, unjoined), negative(ns, raising)
    require(type(a["raised"]) is SuiteStopFake and b["raised"] is unknown and raising.calls == ["retire:5.0"],
            "negative:unjoined and unknown")
    cases["unjoined_stops_unknown_same_object"] = "PASS"
    counts = []
    for peer in (refusal("SSLError"), refusal(None), refusal("SSLError", phase_entered="x"), unjoined,
                 FakeRetiringPeer(raises=PeerRetirementUnknownFake())):
        peer.calls = []
        negative(ns, peer)
        counts.append(sum(1 for c in peer.calls if c.startswith("retire")))
    require(counts == [1, 1, 1, 1, 1], "negative:single attempt")
    cases["single_attempt_all_paths"] = "PASS"
    return cases


def check_negative() -> dict[str, Any]:
    return {"cases": oracle_negative(subject_text("runner/candidate.py")),
            "hypothesis_note": "the frozen peer class set is a fail-closed fixture hypothesis, not native behavior",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_positive() -> dict[str, Any]:
    cases = {}
    ns = helper_namespace(subject_text("runner/candidate.py"))
    ok = call_with_suite(lambda: ns["_retire_selected_peer_then_observe"](
        FakeRetiringPeer(retirement={"joined": True, "worker_error_kind": None}, state={"x": 1}), join_seconds=5.0))
    require(ok["raised"] is None and ok["value"][1] == {"x": 1}, "positive:clean accepted")
    cases["clean_joined_accepted"] = "PASS"
    bad = [call_with_suite(lambda p=p: ns["_retire_selected_peer_then_observe"](p, join_seconds=5.0))["raised"]
           for p in (FakeRetiringPeer(retirement={"joined": True, "worker_error_kind": "SSLError"}),
                     FakeRetiringPeer(retirement={"joined": False, "worker_error_kind": None}))]
    require(all(type(x) is SuiteStopFake for x in bad), "positive:worker error refused")
    cases["worker_error_and_unjoined_refused"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# OBSERVE-WIRING (behavioral: actual _t03_observe + actual routes/transcript units)
# ---------------------------------------------------------------------------

class World:
    """Scenario state for the named fakes used by one _t03_observe call."""

    def __init__(self, *, client: Any, retirement: dict[str, Any], state: dict[str, Any]) -> None:
        self.client, self.retirement, self.state = client, retirement, state
        self.https_peers: list[dict[str, Any]] = []
        self.peers: list[Any] = []
        self.requests: list[tuple[str, str, str]] = []


def build_fake_modules(world: World, peer_text: str) -> dict[str, types.ModuleType]:
    peer_mod = types.ModuleType("np_provider_peer")

    class FakePeer:
        def __init__(self, *, peer_id, route, script, material):
            self.peer_id, self.route, self.script = peer_id, route, script
            self._worker = None
            self.life = types.SimpleNamespace(joined=False)
            self.calls: list[str] = []
            world.peers.append(self)

        def start_background(self, *, seconds):
            self.calls.append(f"start:{seconds}")
            self._worker = object()

        def retire_owned(self, *, join_seconds):
            self.calls.append(f"retire:{join_seconds}")
            self.life.joined = world.retirement.get("joined") is True
            return dict(world.retirement)

        def sanitized_state(self):
            self.calls.append("state")
            return dict(world.state)

    # Peer 17EA148E's serializer needs no module globals (no framing-mode table in this lineage).
    serializer_ns: dict[str, Any] = {"Any": Any}
    exec_units(peer_text, ("_http_response_bytes",), serializer_ns, "peer")
    peer_mod.PeerLifecycleError = PeerLifecycleErrorFake
    peer_mod.PeerRetirementUnknown = PeerRetirementUnknownFake
    peer_mod.PeerMaterial = lambda: object()
    peer_mod.SyntheticProviderPeer = FakePeer
    peer_mod._http_response_bytes = serializer_ns["_http_response_bytes"]

    class FakeJoinedTLS:
        pass

    class FakeHTTPSPeer:
        def __init__(self, *, hostname, address, port, ca_file):
            world.https_peers.append({"hostname": hostname, "address": address, "port": port, "ca_file": ca_file})

    class FakeHTTP:
        def __init__(self, *, counter, routes):
            self.transport_factory = FakeJoinedTLS
            self.routes = routes

        def request(self, method, url, *, purpose):
            world.requests.append((method, url, purpose))
            if isinstance(world.client, BaseException):
                raise world.client
            return types.SimpleNamespace(status_code=world.client[0], content=world.client[1])

    mods = {name: types.ModuleType(name) for name in (
        "app", "app.services", "app.services.covering_http_transport", "app.services.covering_joined_https",
        "app.services.covering_request_budget", "app.services.covering_transport_policy")}
    mods["app.services.covering_http_transport"].CoveringHTTP = FakeHTTP
    mods["app.services.covering_joined_https"].JoinedTLS = FakeJoinedTLS
    mods["app.services.covering_request_budget"].CoveringRequestBudget = lambda: types.SimpleNamespace(
        work_remaining=lambda: 1.0)
    policy = mods["app.services.covering_transport_policy"]
    policy.HTTPSPeer = FakeHTTPSPeer
    policy.ProviderCounter = lambda limits, remaining: types.SimpleNamespace(limits=limits, remaining=remaining)
    policy.approved_provider_limits = lambda: "limits"
    mods["np_provider_peer"] = peer_mod
    return mods


MODULE_NAMES = ("np_suite", "np_provider_routes", "np_provider_transcript", "np_provider_peer", "app", "app.services",
                "app.services.covering_http_transport", "app.services.covering_joined_https",
                "app.services.covering_request_budget", "app.services.covering_transport_policy")


def run_observe(runner_text: str, expectation: str, world: World) -> dict[str, Any]:
    from dataclasses import dataclass
    from typing import Literal

    ns = helper_namespace(runner_text)
    exec_units(runner_text, ("_t03_observe",), ns, "runner")
    with Sandbox(MODULE_NAMES) as box:
        box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStopFake
        # Registered BEFORE executing decorated dataclasses (dataclasses resolves cls.__module__).
        routes = box.put("np_provider_routes", types.ModuleType("np_provider_routes"))
        exec(compile(subject_text("fixture/np_provider_routes.py"), "<subject:np_provider_routes>", "exec"),
             routes.__dict__)
        transcript = box.put("np_provider_transcript", types.ModuleType("np_provider_transcript"))
        transcript.__dict__.update({"dataclass": dataclass, "Literal": Literal})
        exec_units(subject_text("transcript/candidate.py"), (
            "CloseMode", "ExchangeStep", "ExchangeScript", "T03_GET_PATH", "T03_VALID_BODY",
            "t03_valid_fixed_length_get_script"), transcript.__dict__, "transcript")
        for name, module in build_fake_modules(world, subject_text("fixture/np_provider_peer.py")).items():
            box.put(name, module)
        try:
            return {"value": ns["_t03_observe"](f"case-{expectation}", expectation), "raised": None}
        except BaseException as exc:  # noqa: BLE001
            return {"value": None, "raised": exc}


VALID_STATE = {"connection_count_admitted": 1, "connection_count_served": 1,
               "exchange_inventory": [{"method": "GET", "path": "/calendar/v3/calendars/primary/events"}],
               "handshake_complete": True, "request_received": True, "response_sent": True,
               "close_mode_observed": "orderly_close_notify", "bytes_sent": VALID_WIRE_LEN, "accepted": True,
               "bytes_received": 120, "phase_entered": "close:orderly_close_notify"}


def neg_world(client: Any) -> World:
    return World(client=client, retirement={"joined": True, "worker_error_kind": "SSLError"}, state=REFUSAL_STATE)


def oracle_observe(runner_text: str) -> dict[str, str]:
    cases = {}
    world = World(client=(200, b"{}"), retirement={"joined": True, "worker_error_kind": None}, state=VALID_STATE)
    got = run_observe(runner_text, "valid", world)
    peer = world.peers[0] if world.peers else None
    require(got["raised"] is None and got["value"]["client_outcome"] == ["response", 200, True]
            and world.https_peers == [{"hostname": "www.googleapis.com", "address": "127.0.0.1", "port": 443,
                                       "ca_file": FIXTURE_CA}]
            and peer is not None and peer.route.serve_wrong_name_leaf is False and peer.route.ca_path == FIXTURE_CA
            and peer.calls == ["start:120", "retire:5.0", "state"]
            and world.requests == [("GET", GET_URL, "event")], "observe:valid wiring")
    cases["valid_one_attempt_one_retirement"] = "PASS"
    world = neg_world(ssl.SSLCertVerificationError("fixture"))
    got = run_observe(runner_text, "wrong_ca", world)
    peer = world.peers[0] if world.peers else None
    require(got["raised"] is None and got["value"]["client_outcome"] == ["exception", "SSLCertVerificationError", "ssl"]
            and world.https_peers and world.https_peers[0]["ca_file"] == WRONG_CA
            and world.https_peers[0]["hostname"] == "www.googleapis.com"
            and peer.route.serve_wrong_name_leaf is False and peer.route.ca_path == FIXTURE_CA
            and peer.calls == ["start:120", "retire:5.0", "state"], "observe:wrong ca swap only")
    cases["wrong_ca_client_trust_only"] = "PASS"
    world = neg_world(ssl.SSLCertVerificationError("fixture"))
    got = run_observe(runner_text, "wrong_name", world)
    peer = world.peers[0] if world.peers else None
    require(got["raised"] is None and world.https_peers and world.https_peers[0]["ca_file"] == FIXTURE_CA
            and world.https_peers[0]["hostname"] == "www.googleapis.com"
            and peer.route.serve_wrong_name_leaf is True and peer.route.ca_path == FIXTURE_CA
            and peer.route.server_hostname == "www.googleapis.com"
            and peer.calls == ["start:120", "retire:5.0", "state"], "observe:wrong name swap only")
    cases["wrong_name_served_leaf_only"] = "PASS"
    outcomes = []
    for expectation, client in (("wrong_ca", (200, b"{}")), ("wrong_name", ConnectionResetError("x")),
                                ("wrong_name", ssl.SSLEOFError("x"))):
        world = neg_world(client)
        res = run_observe(runner_text, expectation, world)
        outcomes.append(type(res["raised"]) is SuiteStopFake and world.peers[0].calls.count("retire:5.0") == 1)
    world = World(client=ssl.SSLCertVerificationError("x"), retirement={"joined": True, "worker_error_kind": None},
                  state=VALID_STATE)
    res = run_observe(runner_text, "valid", world)
    outcomes.append(type(res["raised"]) is SuiteStopFake)
    require(all(outcomes), "observe:wrong outcome stops")
    cases["wrong_outcome_stops"] = "PASS"
    return cases


def check_observe() -> dict[str, Any]:
    return {"cases": oracle_observe(subject_text("runner/candidate.py")),
            "scope_note": "actual _t03_observe with actual routes and transcript units; peer, CoveringHTTP, JoinedTLS, "
                          "budget and policy are named fakes; no native TLS or certificate behavior is claimed",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# CASE-BODIES (structural)
# ---------------------------------------------------------------------------

def suite_oracles(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for call in ast.walk(ast.parse(text)):
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "CaseDecl" and call.args \
                and isinstance(call.args[0], ast.Constant) and call.args[0].value in T03_IDS:
            oracle_calls = [o for o in ast.walk(call) if isinstance(o, ast.Call) and isinstance(o.func, ast.Name)
                            and o.func.id == "_o"]
            out[call.args[0].value] = _single(oracle_calls, "oracle").args[0].value
    return out


def check_bodies() -> dict[str, Any]:
    cases = {}
    text = subject_text("runner/candidate.py")
    want = {"_run_np_t03_valid": ("NP-T03-VALID", "valid"), "_run_np_t03_wrong_ca": ("NP-T03-WRONG-CA", "wrong_ca"),
            "_run_np_t03_wrong_name": ("NP-T03-WRONG-NAME", "wrong_name")}
    ok = True
    for fn, args in want.items():
        body = unit_node(text, fn).body
        ok = ok and len(body) == 1 and ast.dump(body[0]) == ast.dump(ast.parse(
            f"return _run_np_t03_case({args[0]!r}, {args[1]!r})").body[0])
    implemented = ast.literal_eval(unit_node(text, "IMPLEMENTED_CASE_IDS").value.args[0])
    require(ok and set(T03_IDS) <= implemented and "NP-V-MS-NONEXPIRED" in implemented
            and all(f'"{cid}"' in unit_text(text, "_make_implemented_case") for cid in T03_IDS), "bodies:case mapping")
    cases["case_mapping_exact"] = "PASS"
    oracles = ast.literal_eval(unit_node(text, "T03_ORACLES").value)
    require(oracles == suite_oracles(subject_text("suite/candidate.py"))
            and oracles == suite_oracles(subject_text("suite/source.py")), "bodies:oracle names")
    cases["oracle_names_equal_declarations"] = "PASS"
    banned = ("provision_disposable_schema", "_open_native_setup_factory", "build_i01_asgi_app", "asgi_client")
    require(not any(_calls(unit_node(text, fn), name) for fn in ("_t03_observe", "_run_np_t03_case")
                    for name in banned), "bodies:no schema")
    cases["no_schema_or_asgi"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


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


def check_retention() -> dict[str, Any]:
    cases = {}
    ns = receipt_namespace()
    text = subject_text("runner/candidate.py")
    keys: list[str] = []
    for fn in ("_t03_observe", "_run_np_t03_case"):
        for node in ast.walk(unit_node(text, fn)):
            if isinstance(node, ast.Dict):
                keys += [k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    keys += list(ast.literal_eval(unit_node(text, "T03_ORACLES").value).values())
    require(len(keys) > 20 and not [k for k in keys if ns["_forbidden_key"](k)], "retention:no forbidden key")
    cases["every_emitted_key_survives"] = "PASS"
    sample = {"client_outcome": ["exception", "SSLCertVerificationError", "ssl"],
              "trust_swap": {"client_trust": "wrong_ca", "served_leaf": "vendor_san"},
              "peer_retirement": {"joined": True, "worker_error_kind": "SSLError", "single_attempt": True},
              "peer_post_join": {"phase_entered": "accepted", "bytes_sent": 0},
              "nested": {"private_key": "K", "ok": 1}}
    out = ns["redact_mapping"](sample)
    require(all(out[k] == sample[k] for k in ("client_outcome", "trust_swap", "peer_retirement", "peer_post_join"))
            and out["nested"] == {"ok": 1}, "retention:typed evidence survives")
    cases["typed_evidence_survives_privacy_unchanged"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_behavior_fake_and_structural", "observed": "PASS"}


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
    require(cfg.get("case_ids") == T03_IDS and cfg.get("expected_unknown_cases") == [] and cfg.get("launch_ready") is False
            and src.get("launch_ready") is True and src.get("case_ids") == ["NP-V-MS-NONEXPIRED"]
            and {k: v for k, v in cfg.items() if k not in ("case_ids", "launch_ready")}
            == {k: v for k, v in src.items() if k not in ("case_ids", "launch_ready")}, "config:runner")
    cases["runner_config"] = "PASS"
    raw = subject_text("config/candidate-launch-config.json")
    launch, src_launch = json.loads(raw), json.loads(subject_text("config/source-launch-config.json"))
    note = str(launch.get("candidate_note"))
    require(launch.get("launch_ready") is False and launch.get("candidate_launch_ready_staged") is False
            and launch.get("launch_authorized") is False and launch.get("human_launch_authorized") is False
            and launch.get("case_ids") == T03_IDS and launch.get("batch_id") == "np-t03-b2a"
            and launch.get("implementation_increment", {}).get("implemented_case_ids") == ["NP-V-MS-NONEXPIRED"] + T03_IDS
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and OWN_ROOT in str(launch.get("docker_ops_config_path")) and OWN_ROOT in str(launch.get("receipt_directory"))
            and "host launch_ready=false" in note and "runner-config launch_ready=false" in note
            and SOURCE_ROOT not in raw and set(launch) == set(src_launch)
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
    cases["api_peer_routes_helpers_immutable"] = "PASS"
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


MUTANT_KINDS = {name: "behavioral" for name in (
    "class_set_widened", "none_admitted", "phase_check_dropped", "note_check_dropped", "ca_swap_mixed",
    "wrong_name_also_swaps_ca", "outcome_widened", "second_retirement")}


def check_mutants() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    mutants = {
        "class_set_widened": (lambda: oracle_negative(_mutate(runner, M_SET_WIDENED)), "negative:class outside set stops"),
        "none_admitted": (lambda: oracle_negative(_mutate(runner, M_NONE_ADMITTED)), "negative:none stops"),
        "phase_check_dropped": (lambda: oracle_negative(_mutate(runner, M_PHASE_DROPPED)),
                                "negative:advanced state stops"),
        "note_check_dropped": (lambda: oracle_negative(_mutate(runner, M_NOTE_DROPPED)), "negative:note mismatch stops"),
        "ca_swap_mixed": (lambda: oracle_observe(_mutate(runner, M_CA_SWAP_MIXED)), "observe:wrong ca swap only"),
        "wrong_name_also_swaps_ca": (lambda: oracle_observe(_mutate(runner, M_NAME_ALSO_CA)),
                                     "observe:wrong name swap only"),
        "outcome_widened": (lambda: oracle_observe(_mutate(runner, M_OUTCOME_WIDENED)), "observe:wrong outcome stops"),
        "second_retirement": (lambda: oracle_observe(_mutate(runner, M_SECOND_RETIRE)), "observe:valid wiring"),
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
    require(expected.get("kind") == "native-t03-b2a-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "NEGATIVE-HELPER": check_negative,
        "POSITIVE-HELPER-PRESERVED": check_positive,
        "OBSERVE-WIRING": check_observe,
        "CASE-BODIES": check_bodies,
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
