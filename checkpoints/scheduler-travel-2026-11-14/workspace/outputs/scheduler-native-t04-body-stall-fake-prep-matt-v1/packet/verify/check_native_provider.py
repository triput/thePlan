#!/usr/bin/env python3
"""HELD fake-only checker for the native NP-T04-BODY-STALL preparation (Dex F465A4E2).

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned): source/candidate runner, peer, transcript and suite (source =
scheduler-native-provider-ms-refresh-retire-prep-matt-v1, candidate =
scheduler-native-provider-t04-body-stall-prep-matt-v1), their five diffs,
source/candidate runner-config, launch-config and docker-ops-config, both payload and
nested manifests, and three unchanged dependencies: microsoft_calendar.py,
covering_refresh_window.py and np_receipts.py.

Execution surfaces (all fake; no socket, TLS, DB, Docker, thread, process or vendor
package):
- BEHAVIORAL (extracted actual source units with named fakes): the peer _hold_stall,
  _send_response and _http_response_bytes; the transcript body-stall script and
  inventory; the runner timing predicate, exact-query derivation (over the actual
  production window module and calendarView param builders) and the restorable
  observers; the actual np_receipts redaction.
- STRUCTURAL (AST/text only): runner wiring (240 s case peer life, real monotonic
  clock, retirement barrier, observer restoration, allowlisted receipt keys),
  preservation and configuration. Structural checks are labelled as structural.

Proof scope: finite fixture/source properties. NOT proved: native elapsed time, TLS,
selector scheduling, database, native terminal or recorder outcomes, or any T04
requirement.
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
import math
import os
import re
import sys
import textwrap
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-native-t04-body-stall-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/source.py": "1A95E8340B2D45B0DA4D77B14B7726E485691EB94B3CF765AD4497F96020A8B2",
    "runner/candidate.py": "9DAE7119354CA65BCF02DF5D2868F81F34D111828684B1C9761C2C1B70A5E2D3",
    "peer/source.py": "BFB271D770D08BC161E9613564ECA799B7E28884D8211E10228F5973A4A271BF",
    "peer/candidate.py": "F721BBE741AE5E59DFFB67D0B6EE364982CC1705C27FD635A36752BD3F86BDFA",
    "transcript/source.py": "BEDCCFD3C3E8F776C4EC0B3379F863E976C73AF350DD6AE8B308518AB4A47735",
    "transcript/candidate.py": "D3B9379B7C062DFBB5E6CF13F6AD44003C040545383BF893B514C0A685861C6B",
    "suite/source.py": "DAB88CB352189411EED6A2181417CB813D592406598D89192FF307E9081205A1",
    "suite/candidate.py": "00DF3510E36B6A652D6073E6D1DDC8F475182222C8AEDB29BE8AE93B8EAFE173",
    "diff/np_runner_entry.py.diff": "8B4B11707DDBF799D662E4E8B87B74D4C86C5F61C7D4DF2A78E9A6FC682F7AF1",
    "diff/np_provider_peer.py.diff": "995F91A1248564F297C197C137CCC0385CE58BDEE4B4A6E634CFDBB0989CCBCC",
    "diff/np_provider_transcript.py.diff": "B97F9B2FA2EE9491DF866BB8DC43C7F67B6868F25DE7578E6B81E6028125A67C",
    "diff/np_suite.py.diff": "3A1B5798ECA6F09C471AE68925BE51FF8FE6656CB9BBA2BD09549D09B2557A60",
    "diff/runner-config.json.diff": "D0D1A6A454B9A2742EE8E2518B0585F403A94602ADC3F01B1304FCE0B7EA380F",
    "config/source-runner-config.json": "D4C8BDBD83C3C5D0F76564C5E5BB6B5962CBBEBA4D3D3C3618E55DC8C693A88A",
    "config/candidate-runner-config.json": "F43275F305C8BEEAE13B1372BE60278C8714E504DF6C9BB450284F6FCFE34923",
    "config/source-launch-config.json": "09C9D618DC0177FACD8E29A35DEDEEAFF637424D0C447C939B4834EC07EB7ED5",
    "config/candidate-launch-config.json": "98C791686CD5E91110AE32338E3302AB34A7D97F4880D6C39B4A5A9C0C36B355",
    "config/source-docker-ops-config.json": "9455026A775EF769C71D960A71ADEBC623BDC01299844C08B5F69F0C90130F1D",
    "config/candidate-docker-ops-config.json": "A4A6B4526FA3E7603BB5C076DC4AA68F94BC84C9783C56D10D89DA8AB6B30CD4",
    "manifest/source.txt": "CC02F38CFBD8542AD49DA8663FE3BCACD8F8712FDD97FE53D5F739A52C0CA687",
    "manifest/candidate.txt": "6CFB1DB748CEC474C298CE053CCD0D0446D9B55B54407E02F22FD60C862D7FDA",
    "manifest/source-nested.txt": "C83A5E9E324C77465F03C3EEE371AEF7A16917FCD8335B943AFF98E2FAD7AB5B",
    "manifest/candidate-nested.txt": "97E9B316F1E7C5A7E0F0AE3E1EA7DE3A1BCD59018E8094C7AF1D0878A9A4CF84",
    "app/microsoft_calendar.py": "6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF",
    "app/covering_refresh_window.py": "7E39381B06A9557F8E4D29EFDEE1A140AA123155058BE949213664087B8114C0",
    "fixture/np_receipts.py": "7F27A3C2CBCA73C27DCEC6C9DCF6277C7F131ACC3A561C4170636EAB5D5E24C7",
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
    "PEER-CLEAN-STOP",
    "TRANSCRIPT-STALL-SCRIPT",
    "QUERY-DERIVATION",
    "TIMING-PREDICATE",
    "RUNNER-WIRING",
    "OBSERVERS",
    "RECEIPT-RETENTION",
    "CONFIG-AND-IMMUTABLES",
    "ACTUAL-SOURCE-MUTANTS",
)

CASE_ID = "NP-T04-BODY-STALL"
CASE_FN = "_run_np_t04_body_stall"
OWN_ROOT = "scheduler-native-provider-t04-body-stall-prep-matt-v1"
SOURCE_ROOT = "scheduler-native-provider-ms-refresh-retire-prep-matt-v1"
RUNNER_ADDED = {
    "T04_BODY_STALL_PEER_SECONDS", "T04_BODY_STALL_PEER_SECONDS_CONFIG_KEY",
    "T04_BODY_STALL_PRODUCTION_WORK_SECONDS", "T04_BODY_STALL_DEADLINE_OUTCOME",
    "T04_BODY_STALL_CLIENT_PURPOSES", "T04_BODY_STALL_TOKEN_TERMINAL_ROWS",
    "T04_BODY_STALL_TERMINAL_OBSERVER_ROWS", "T04_BODY_STALL_PARENT_TERMINAL_ROWS",
    "T04_BODY_STALL_FAILURE_CAUSE", "T04_BODY_STALL_DEADLINE_CODE", "T04_BODY_STALL_ACTION_SUMMARY",
    "T04_BODY_STALL_KNOWN_REFUSAL", "_t04_body_stall_peer_seconds_from_config",
    "_t04_body_stall_exact_query", "_install_t04_parent_and_target_observers",
    "_t04_measure_failure_columns", "_t04_finite_instant", "_t04_body_stall_timing", CASE_FN,
}
RUNNER_CHANGED = {"IMPLEMENTED_CASE_IDS", "_make_implemented_case"}
TRANSCRIPT_ADDED = {"T04_BODY_STALL_EXCHANGE_COUNT", "T04_BODY_STALL_BODY_TEMPLATE",
                    "ms_graph_calendar_view_body_stall_script", "ms_body_stall_connection_inventory"}
PEER_METHODS_CHANGED = {"_send_response", "_hold_stall", "execute_script", "sanitized_state"}
LAUNCH_CHANGED_KEYS = {"batch_id", "case_ids", "t04_body_stall_peer_seconds", "manifest_sha256",
                       "docker_ops_config_path", "receipt_directory", "candidate_note"}
CHANGED_PAYLOAD_ROWS = {"fixture/np_runner_entry.py": "runner/candidate.py",
                        "fixture/np_provider_peer.py": "peer/candidate.py",
                        "fixture/np_provider_transcript.py": "transcript/candidate.py",
                        "fixture/np_suite.py": "suite/candidate.py",
                        "runner-config.json": "config/candidate-runner-config.json"}
CHANGED_NESTED_ROWS = {"payload/" + k: v for k, v in CHANGED_PAYLOAD_ROWS.items()}
CHANGED_NESTED_ROWS.update({"payload/SHA256SUMS.txt": "manifest/candidate.txt",
                            "host/launch-config.json": "config/candidate-launch-config.json",
                            "host/docker-ops-config.json": "config/candidate-docker-ops-config.json"})
IMMUTABLE_ROWS = ("fixture/np_receipts.py", "fixture/np_integrated_runner.py", "fixture/docker_transport.py",
                  "fixture/np_provider_routes.py", "fixture/np_auth_seed.py", "fixture/np_alias_seed.py",
                  "fixture/i01_asgi_app.py", "fixture/prepare-np-provider-tls.sh",
                  "api/app/services/microsoft_calendar.py", "api/app/services/covering_refresh_window.py")
QUERY_START = datetime(2026, 11, 14, 2, 0, 0, 123456, tzinfo=timezone.utc)
QUERY_END = datetime(2026, 11, 28, 2, 0, 0, 123456, tzinfo=timezone.utc)
QUERY_LITERAL = ("startDateTime=2026-11-14T02%3A00%3A00.123456Z"
                 "&endDateTime=2026-11-28T02%3A00%3A00.123456Z&%24top=100")
STALL_HEAD = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 12\r\n"
              b"Connection: close\r\n\r\n")

# Mutation anchors (each verified unique in the whole candidate text it edits).
M_PEER_LAX_STOP = ("        if self._stop.is_set() and exited < deadline:\n", "        if self._stop.is_set():\n")
M_PEER_DEADLINE_RETURNS = ("        raise PeerLifecycleError(deadline_message)\n", "        return\n")
M_PEER_BODY_SENT = ('            self._hold_stall(deadline=deadline, deadline_message="body stall held to deadline")\n'
                    '            return\n',
                    '            self._hold_stall(deadline=deadline, deadline_message="body stall held to deadline")\n')
M_RUN_DEFAULT_PEER = ("        peer.start_background(seconds=peer_seconds)\n",
                      "        peer.start_background(seconds=PEER_SECONDS_DEFAULT)\n")
M_RUN_DROPPED_KEY = ('            "token_terminal_sequence": token_terminals,\n',
                     '            "token_terminal_rows": token_terminals,\n')
M_RUN_EPSILON = ("    if not w <= x_t:\n", "    if not w - 1.0 <= x_t:\n")
M_RUN_NO_REASON = ('    if reason != "retired":\n'
                   '        raise SuiteStop(f"t04 body-stall exit reason not retired:{reason!r}")\n', "")
M_RUN_OBSERVER_COPY = ("        return returned\n", "        return (result, failure)\n")
M_RUN_QUERY_TOP = ('        "$top": "100",\n', '        "$top": "50",\n')


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
        "peer": ("peer/source.py", "peer/candidate.py", "diff/np_provider_peer.py.diff",
                 "payload/fixture/np_provider_peer.py", 6),
        "transcript": ("transcript/source.py", "transcript/candidate.py", "diff/np_provider_transcript.py.diff",
                       "payload/fixture/np_provider_transcript.py", 1),
        "suite": ("suite/source.py", "suite/candidate.py", "diff/np_suite.py.diff", "payload/fixture/np_suite.py", 1),
        "runner_config": ("config/source-runner-config.json", "config/candidate-runner-config.json",
                          "diff/runner-config.json.diff", "payload/runner-config.json", 2),
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


def unit_node(text: str, name: str, class_name: str | None = None) -> ast.AST:
    body = ast.parse(text).body
    if class_name is not None:
        body = _single([n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name],
                       f"class {class_name}").body
    return _single([n for n in body if node_name(n) == name], f"unit {name}")


def unit_text(text: str, name: str, class_name: str | None = None) -> str:
    node = unit_node(text, name, class_name)
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    lines = text.split("\n")[first - 1:node.end_lineno]
    return textwrap.dedent("\n".join(lines)) + "\n"


def exec_units(text: str, names: tuple[str, ...], namespace: dict[str, Any], label: str,
               class_name: str | None = None) -> dict[str, Any]:
    for name in names:
        source = "from __future__ import annotations\n" + unit_text(text, name, class_name)
        exec(compile(source, f"<extracted:{label}:{name}>", "exec"), namespace)
    return namespace


def top_table(text: str) -> dict[str, tuple[str, ...]]:
    """Named top-level units -> ordered dumps (repeated names keep every occurrence)."""
    table: dict[str, list[str]] = {}
    for node in ast.parse(text).body:
        name = node_name(node)
        if name is not None:
            table.setdefault(name, []).append(ast.dump(node))
    return {name: tuple(dumps) for name, dumps in table.items()}


def dump_stmt(snippet: str) -> str:
    return ast.dump(_single(ast.parse(textwrap.dedent(snippet)).body, "snippet"))


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [c for c in ast.walk(node) if isinstance(c, ast.Call) and (
        (isinstance(c.func, ast.Name) and c.func.id == name)
        or (isinstance(c.func, ast.Attribute) and c.func.attr == name))]


def _mutate(text: str, mutation: tuple[str, str]) -> str:
    require(text.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
    return text.replace(*mutation)


class Sandbox:
    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = names
        self.installed: list[str] = []

    def __enter__(self) -> "Sandbox":
        require(all(name not in sys.modules for name in self.names), "sandbox precondition")
        return self

    def put(self, name: str, module: types.ModuleType) -> types.ModuleType:
        require(name in self.names, f"sandbox name not declared:{name}")
        sys.modules[name] = module
        self.installed.append(name)
        return module

    def __exit__(self, *exc_info: Any) -> bool:
        for name in self.installed:
            sys.modules.pop(name, None)
        return False


class SuiteStopFake(Exception):
    """Named fake for np_suite.SuiteStop."""


def suite_box() -> Sandbox:
    return Sandbox(("np_suite",))


def with_suite(action: Callable[[], Any]) -> dict[str, Any]:
    with suite_box() as box:
        box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStopFake
        try:
            return {"value": action(), "raised": None}
        except BaseException as exc:  # noqa: BLE001
            return {"value": None, "raised": exc}


# ---------------------------------------------------------------------------
# PRESERVED-OUTSIDE-CHANGE (structural)
# ---------------------------------------------------------------------------

def check_preserved_outside_change() -> dict[str, Any]:
    cases = {}
    src, cand = top_table(subject_text("runner/source.py")), top_table(subject_text("runner/candidate.py"))
    added = set(cand) - set(src)
    changed = {n for n in set(src) & set(cand) if src[n] != cand[n]}
    require(added == RUNNER_ADDED and changed == RUNNER_CHANGED and set(src) <= set(cand), "preserved:runner")
    cases["runner"] = "PASS"
    p_src, p_cand = subject_text("peer/source.py"), subject_text("peer/candidate.py")
    ts, tc = top_table(p_src), top_table(p_cand)
    require(set(ts) == set(tc) and {n for n in ts if ts[n] != tc[n]} == {"PeerLifecycle", "SyntheticProviderPeer"},
            "preserved:peer")
    ms = {n.name: ast.dump(n) for n in unit_node(p_src, "SyntheticProviderPeer").body if isinstance(n, ast.FunctionDef)}
    mc = {n.name: ast.dump(n) for n in unit_node(p_cand, "SyntheticProviderPeer").body if isinstance(n, ast.FunctionDef)}
    require({n for n in set(ms) | set(mc) if ms.get(n) != mc.get(n)} == PEER_METHODS_CHANGED, "preserved:peer")
    cases["peer"] = "PASS"
    s, c = top_table(subject_text("transcript/source.py")), top_table(subject_text("transcript/candidate.py"))
    require(set(c) - set(s) == TRANSCRIPT_ADDED and set(s) <= set(c) and all(s[n] == c[n] for n in s),
            "preserved:transcript")
    cases["transcript"] = "PASS"
    s, c = top_table(subject_text("suite/source.py")), top_table(subject_text("suite/candidate.py"))
    require(set(s) == set(c) and {n for n in s if s[n] != c[n]} == {"CASE_IMPLEMENTATION_NOTES"}, "preserved:suite")
    cases["suite"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# PEER-CLEAN-STOP (behavioral, extracted actual peer units)
# ---------------------------------------------------------------------------

class PeerLifecycleErrorFake(RuntimeError):
    """Named fake for np_provider_peer.PeerLifecycleError."""


class FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class FakeStop:
    def __init__(self) -> None:
        self.flag = False

    def is_set(self) -> bool:
        return self.flag


def peer_namespace(peer_text: str, clock: FakeClock, on_poll: Callable[[], None]) -> dict[str, Any]:
    def fake_select(r, w, x, timeout):
        clock.now += timeout
        on_poll()
        return ([], [], [])

    namespace: dict[str, Any] = {
        "Any": Any, "monotonic": clock, "select": types.SimpleNamespace(select=fake_select),
        "PeerLifecycleError": PeerLifecycleErrorFake,
    }
    for name in ("ACCEPT_POLL_SECONDS", "HEADER_TERMINATOR", "RESPONSE_FRAMING_MODES"):
        exec(compile(unit_text(peer_text, name), f"<extracted:peer:{name}>", "exec"), namespace)
    exec_units(peer_text, ("_http_response_bytes",), namespace, "peer")
    exec_units(peer_text, ("_hold_stall", "_send_response"), namespace, "peer", class_name="SyntheticProviderPeer")
    return namespace


def fake_peer(mode: str, stop: FakeStop, sent: list[bytes], ns: dict[str, Any]) -> Any:
    self = types.SimpleNamespace(
        life=types.SimpleNamespace(stall_entered_at=None, stall_exit_at=None, stall_exit_reason=None,
                                   response_sent=False, phase_entered=None, close_mode_observed=None, notes=[]),
        _stop=stop)
    self._script_close_mode = lambda: mode
    self._send_all = lambda tls, data, *, deadline: sent.append(bytes(data))
    self._hold_stall = types.MethodType(ns["_hold_stall"], self)
    return self


def stall_step(peer_ns: dict[str, Any], transcript_ns: dict[str, Any]) -> Any:
    return transcript_ns["ms_graph_calendar_view_body_stall_script"](
        calendar_id="cal-ms-default", exact_query=QUERY_LITERAL).steps[1]


def oracle_peer(peer_text: str) -> dict[str, str]:
    cases = {}
    tns = transcript_namespace(subject_text("transcript/candidate.py"))
    # (a) owner stop strictly before deadline -> clean retired return.
    clock, stop = FakeClock(), FakeStop()
    ns = peer_namespace(peer_text, clock, lambda: setattr(stop, "flag", clock.now >= 101.0))
    self = fake_peer("stall_body", stop, [], ns)
    got = with_suite(lambda: ns["_hold_stall"](self, deadline=340.0, deadline_message="body stall held to deadline"))
    life = self.life
    require(got["raised"] is None and got["value"] is None and life.stall_exit_reason == "retired"
            and life.stall_entered_at == 100.0 and 100.0 < life.stall_exit_at < 340.0, "peer:retired clean return")
    cases["retired_clean_return"] = "PASS"
    # (b) deadline without stop -> unchanged PeerLifecycleError, reason deadline.
    clock, stop = FakeClock(), FakeStop()
    ns = peer_namespace(peer_text, clock, lambda: None)
    self = fake_peer("stall_body", stop, [], ns)
    got = with_suite(lambda: ns["_hold_stall"](self, deadline=100.2, deadline_message="body stall held to deadline"))
    require(type(got["raised"]) is PeerLifecycleErrorFake and got["raised"].args == ("body stall held to deadline",)
            and self.life.stall_exit_reason == "deadline", "peer:deadline error")
    cases["deadline_remains_error"] = "PASS"
    # (c) stop observed only at/after the deadline -> still a deadline error (strict).
    clock, stop = FakeClock(), FakeStop()
    ns = peer_namespace(peer_text, clock, lambda: setattr(stop, "flag", clock.now >= 100.2))
    self = fake_peer("stall_body", stop, [], ns)
    got = with_suite(lambda: ns["_hold_stall"](self, deadline=100.2, deadline_message="body stall held to deadline"))
    require(type(got["raised"]) is PeerLifecycleErrorFake and self.life.stall_exit_reason == "deadline",
            "peer:late stop strict")
    cases["late_stop_is_deadline"] = "PASS"
    # (d) body stall sends exactly the head (positive Content-Length), never the body.
    clock, stop, sent = FakeClock(), FakeStop(), []
    ns = peer_namespace(peer_text, clock, lambda: setattr(stop, "flag", True))
    self = fake_peer("stall_body", stop, sent, ns)
    got = with_suite(lambda: ns["_send_response"](self, None, deadline=340.0, step=stall_step(ns, tns)))
    require(got["raised"] is None and sent == [STALL_HEAD] and self.life.response_sent is True
            and self.life.phase_entered == "stall_body" and self.life.stall_exit_reason == "retired",
            "peer:body stall head only")
    cases["body_stall_head_only"] = "PASS"
    # (e) header stall sends nothing and returns cleanly on owner stop.
    clock, stop, sent = FakeClock(), FakeStop(), []
    ns = peer_namespace(peer_text, clock, lambda: setattr(stop, "flag", True))
    self = fake_peer("stall_header", stop, sent, ns)
    got = with_suite(lambda: ns["_send_response"](self, None, deadline=340.0, step=stall_step(ns, tns)))
    require(got["raised"] is None and sent == [] and self.life.stall_exit_reason == "retired"
            and self.life.response_sent is False, "peer:header stall clean")
    cases["header_stall_clean"] = "PASS"
    # (f) execute_script records start/deadline; sanitized_state exports the five fields (structural).
    fn = unit_node(peer_text, "execute_script", "SyntheticProviderPeer")
    body = [ast.dump(s) for s in fn.body]
    want = [dump_stmt("started = monotonic()"), dump_stmt("deadline = started + seconds"),
            dump_stmt("self.life.peer_started_at = started"), dump_stmt("self.life.peer_deadline_at = deadline")]
    idx = [i for i in range(len(body) - 3) if body[i:i + 4] == want]
    state = unit_text(peer_text, "sanitized_state", "SyntheticProviderPeer")
    require(len(idx) == 1 and all(f'"{k}": self.life.{k},' in state for k in (
        "peer_started_at", "peer_deadline_at", "stall_entered_at", "stall_exit_at", "stall_exit_reason")),
            "peer:instants recorded")
    cases["instants_recorded_structural"] = "PASS"
    return cases


def check_peer() -> dict[str, Any]:
    return {"cases": oracle_peer(subject_text("peer/candidate.py")), "control_kind": "extracted_behavior_fake",
            "structural_cases": ["instants_recorded_structural"], "observed": "PASS"}


# ---------------------------------------------------------------------------
# TRANSCRIPT-STALL-SCRIPT (behavioral, extracted actual transcript units)
# ---------------------------------------------------------------------------

def transcript_namespace(text: str) -> dict[str, Any]:
    from dataclasses import dataclass
    from typing import Literal

    namespace: dict[str, Any] = {"dataclass": dataclass, "Literal": Literal, "__name__": "transcript_subject"}
    exec_units(text, ("CloseMode", "ResponseFraming", "ExchangeStep", "ExchangeScript",
                      "ms_graph_identity_default_script", "ms_graph_identity_list_script",
                      "T04_BODY_STALL_EXCHANGE_COUNT", "T04_BODY_STALL_BODY_TEMPLATE",
                      "ms_graph_calendar_view_body_stall_script", "ms_body_stall_connection_inventory"),
               namespace, "transcript")
    return namespace


def oracle_transcript(text: str) -> dict[str, str]:
    cases = {}
    ns = transcript_namespace(text)
    inv = ns["ms_body_stall_connection_inventory"](identity_list_calendar_ids=("cal-ms-default", "cal-np-other"),
                                                   stall_calendar_id="cal-ms-default", exact_query=QUERY_LITERAL)
    require(len(inv) == 3 and [s.script_id for s in inv[:2]] == ["MS-GRAPH-IDENTITY-DEFAULT", "MS-GRAPH-IDENTITY-LIST"]
            and inv[2].purpose == "event", "transcript:three exchanges")
    cases["exactly_three_exchanges"] = "PASS"
    steps = inv[2].steps
    require([s.direction for s in steps] == ["recv_request", "send_response", "close"]
            and steps[0].method == "GET"
            and steps[0].path == f"/v1.0/me/calendars/cal-ms-default/calendarView?{QUERY_LITERAL}"
            and steps[2].close_mode == "stall_body", "transcript:exact path query")
    cases["exact_path_query_stall_body"] = "PASS"
    pns = peer_namespace(subject_text("peer/candidate.py"), FakeClock(), lambda: None)
    wire = with_suite(lambda: pns["_http_response_bytes"](steps[1]))
    head, sep, rest = (wire["value"] or b"").partition(b"\r\n\r\n")
    require(wire["raised"] is None and head + sep == STALL_HEAD and rest == b'{"value":[]}', "transcript:positive cl")
    cases["positive_content_length_head"] = "PASS"
    refused = []
    for query in ("", "a?b", "a#b"):
        try:
            ns["ms_graph_calendar_view_body_stall_script"](calendar_id="cal-ms-default", exact_query=query)
            refused.append(False)
        except RuntimeError:
            refused.append(True)
    require(refused == [True, True, True], "transcript:query refusal")
    cases["bad_query_refused"] = "PASS"
    return cases


def check_transcript() -> dict[str, Any]:
    return {"cases": oracle_transcript(subject_text("transcript/candidate.py")),
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# QUERY-DERIVATION (behavioral: actual runner unit over actual production units)
# ---------------------------------------------------------------------------

def query_call(runner_text: str, start: datetime, end: datetime) -> dict[str, Any]:
    window_ns: dict[str, Any] = {"__name__": "covering_refresh_window_subject"}
    exec(compile(subject_text("app/covering_refresh_window.py"), "<subject:covering_refresh_window>", "exec"), window_ns)
    ms_ns: dict[str, Any] = {"datetime": datetime, "timezone": timezone, "Any": Any}
    exec_units(subject_text("app/microsoft_calendar.py"), ("_ensure_aware", "_iso_z",
               "microsoft_event_list_window_params", "microsoft_calendar_view_list_params"), ms_ns, "ms")
    ns: dict[str, Any] = {"datetime": datetime, "timezone": timezone}
    exec_units(runner_text, ("_t04_body_stall_exact_query",), ns, "runner")
    names = ("np_suite", "app", "app.services", "app.services.microsoft_calendar", "app.services.covering_refresh_window")
    with Sandbox(names) as box:
        box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStopFake
        ms_mod = box.put("app.services.microsoft_calendar", types.ModuleType("app.services.microsoft_calendar"))
        ms_mod.microsoft_calendar_view_list_params = ms_ns["microsoft_calendar_view_list_params"]
        win_mod = box.put("app.services.covering_refresh_window", types.ModuleType("app.services.covering_refresh_window"))
        win_mod.effective_covering_pull_window = window_ns["effective_covering_pull_window"]
        services = box.put("app.services", types.ModuleType("app.services"))
        services.microsoft_calendar = ms_mod
        services.covering_refresh_window = win_mod
        app = box.put("app", types.ModuleType("app"))
        app.services = services
        try:
            return {"value": ns["_t04_body_stall_exact_query"](start, end), "raised": None}
        except BaseException as exc:  # noqa: BLE001
            return {"value": None, "raised": exc}


def oracle_query(runner_text: str) -> dict[str, str]:
    cases = {}
    got = query_call(runner_text, QUERY_START, QUERY_END)
    require(got["raised"] is None and got["value"] == QUERY_LITERAL, "query:exact literal")
    cases["exact_literal_from_window"] = "PASS"
    offset = timezone(timedelta(hours=-8))
    got = query_call(runner_text, QUERY_START.astimezone(offset), QUERY_END.astimezone(offset))
    require(got["raised"] is None and got["value"] == QUERY_LITERAL, "query:utc normalization")
    cases["offset_window_normalized_to_utc"] = "PASS"
    got = query_call(runner_text, QUERY_END, QUERY_START)
    require(got["raised"] is not None and type(got["raised"]).__name__ == "CoveringWindowError", "query:invalid window")
    cases["invalid_window_refused"] = "PASS"
    return cases


def check_query() -> dict[str, Any]:
    return {"cases": oracle_query(subject_text("runner/candidate.py")), "literal": QUERY_LITERAL,
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# TIMING-PREDICATE (behavioral, extracted actual runner units)
# ---------------------------------------------------------------------------

GOOD_TIMING = {"p0": 1000.0, "w": 1215.0, "s_in": 1012.0, "x_t": 1215.02, "t_resp": 1216.0,
               "t_ret": 1217.0, "s_out": 1217.05, "p_dl": 1240.0, "r": 1245.0, "reason": "retired"}
TIMING_VIOLATIONS = {
    "peer_after_budget": {"p0": 1006.0},
    "peer_deadline_before_work": {"p_dl": 1214.0},
    "stall_after_work_deadline": {"s_in": 1215.5},
    "exception_before_work_deadline": {"x_t": 1214.99},
    "response_before_exception": {"t_resp": 1215.01},
    "exit_after_peer_deadline": {"s_out": 1240.5},
    "deadline_exit_reason": {"reason": "deadline"},
    "missing_instant": {"s_in": None},
    "non_finite_instant": {"x_t": float("nan")},
    "integer_instant": {"t_ret": 1217},
}


def timing_call(runner_text: str, values: dict[str, Any]) -> dict[str, Any]:
    ns: dict[str, Any] = {"Any": Any}
    exec(compile(unit_text(runner_text, "T04_BODY_STALL_PRODUCTION_WORK_SECONDS"), "<extracted:runner:const>", "exec"), ns)
    exec_units(runner_text, ("_t04_finite_instant", "_t04_body_stall_timing"), ns, "runner")
    peer_state = {"peer_started_at": values["p0"], "peer_deadline_at": values["p_dl"],
                  "stall_entered_at": values["s_in"], "stall_exit_at": values["s_out"],
                  "stall_exit_reason": values["reason"]}
    return with_suite(lambda: ns["_t04_body_stall_timing"](
        peer_state=peer_state, work_deadline=values["w"], request_deadline=values["r"],
        client_exception_at=values["x_t"], response_at=values["t_resp"], retire_called_at=values["t_ret"]))


def oracle_timing(runner_text: str) -> dict[str, str]:
    cases = {}
    got = timing_call(runner_text, GOOD_TIMING)
    value = got["value"] or {}
    require(got["raised"] is None and value.get("budget_started_at_derived") == 1005.0
            and value.get("stall_exit_reason") == "retired" and value.get("work_deadline") == 1215.0
            and abs(value.get("client_exception_after_work_deadline_seconds", -1) - 0.02) < 1e-9,
            "timing:ordered values accepted")
    cases["ordered_values_accepted"] = "PASS"
    outcomes = {}
    for name, override in TIMING_VIOLATIONS.items():
        outcomes[name] = type(timing_call(runner_text, {**GOOD_TIMING, **override})["raised"]) is SuiteStopFake
    require(all(outcomes[n] for n in ("peer_after_budget", "peer_deadline_before_work", "stall_after_work_deadline",
                                      "exception_before_work_deadline", "response_before_exception",
                                      "exit_after_peer_deadline")), "timing:each inequality stops")
    cases["each_inequality_stops"] = "PASS"
    require(outcomes["deadline_exit_reason"], "timing:deadline reason stops")
    cases["deadline_reason_stops"] = "PASS"
    require(outcomes["missing_instant"] and outcomes["non_finite_instant"] and outcomes["integer_instant"],
            "timing:missing or non-finite stops")
    cases["missing_or_nonfinite_stops"] = "PASS"
    return cases


def check_timing() -> dict[str, Any]:
    return {"cases": oracle_timing(subject_text("runner/candidate.py")),
            "note": "no epsilon in any success inequality; lateness X_t-W is recorded data only",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# RUNNER-WIRING (structural)
# ---------------------------------------------------------------------------

def main_try(fn: ast.AST) -> ast.Try:
    return _single([s for s in fn.body if isinstance(s, ast.Try) and _calls(s, "case_result_receipt")], "main try")


def _dict_keys(node: ast.AST, assigned: str) -> list[str]:
    for n in ast.walk(node):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == assigned for t in n.targets) \
                and isinstance(n.value, ast.Dict):
            return [k.value for k in n.value.keys if isinstance(k, ast.Constant)]
    raise WitnessFailure(f"dict literal missing:{assigned}")


def oracle_wiring(runner_text: str) -> dict[str, str]:
    cases = {}
    module = ast.parse(runner_text)
    fn = unit_node(runner_text, CASE_FN)
    starts = _calls(fn, "start_background")
    require(len(starts) == 1 and ast.dump(starts[0]) == ast.dump(ast.parse("peer.start_background(seconds=peer_seconds)",
                                                                             mode="eval").body)
            and any(ast.dump(s) == dump_stmt("peer_seconds = _t04_body_stall_peer_seconds_from_config()") for s in fn.body)
            and not [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "PEER_SECONDS_DEFAULT"]
            and len([c for c in _calls(module, "start_background")
                     if ast.dump(c) == ast.dump(ast.parse("peer.start_background(seconds=PEER_SECONDS_DEFAULT)",
                                                          mode="eval").body)]) == 4,
            "wiring:case peer life")
    cases["case_peer_life_240_only"] = "PASS"
    builds = _calls(fn, "build_i01_asgi_app")
    require(len(builds) == 1 and any(k.arg == "clock" and isinstance(k.value, ast.Name) and k.value.id == "monotonic"
                                     for k in builds[0].keywords), "wiring:real monotonic clock")
    cases["real_monotonic_clock"] = "PASS"
    main = main_try(fn)
    dumps = [ast.dump(s) for s in main.body]
    bar = [i for i, d in enumerate(dumps) if d == dump_stmt(
        "retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)")]
    require(len(bar) == 1 and dumps[bar[0] - 2] == dump_stmt("retirement_attempted = True")
            and dumps[bar[0] - 1] == dump_stmt("retire_called_at = monotonic()")
            and dumps[bar[0] + 1] == dump_stmt("retirement_done = True")
            and not [c for s in main.body for c in _calls(s, "retire_owned")]
            and not [c for s in main.body for c in _calls(s, "sanitized_state")]
            and len([c for s in main.finalbody for c in _calls(s, "retire_owned")]) == 1, "wiring:retirement barrier")
    cases["single_retirement_barrier"] = "PASS"
    bar_line = main.body[bar[0]].lineno
    timing_line = _single(_calls(main, "_t04_body_stall_timing"), "timing call").lineno
    oracle_line = _single(_calls(main, "check_oracles_immediate"), "oracle call").lineno
    receipt_line = _single(_calls(main, "case_result_receipt"), "receipt").lineno
    require(bar_line < timing_line < oracle_line < receipt_line, "wiring:timing after retirement")
    cases["timing_after_retirement"] = "PASS"
    inner = _single([t for t in ast.walk(main) if isinstance(t, ast.Try) and t is not main and _calls(t, "post")],
                    "post try")
    require(bool(inner.body) and ast.dump(inner.body[-1]) == dump_stmt("response_at = monotonic()")
            and any(_calls(s, "restore_target_observers") for s in inner.finalbody)
            and any(_calls(s, "restore_worker_observer") for s in inner.finalbody), "wiring:observers restored")
    cases["observers_restored_in_finally"] = "PASS"
    keys = _dict_keys(fn, "measured")
    require("token_terminal_sequence" in keys and "token_terminal_rows" not in keys
            and _dict_keys(fn, "observations") == ["first_guard_body_phase_deadline"], "wiring:receipt keys")
    cases["allowlisted_token_key_and_oracle"] = "PASS"
    return cases


def check_wiring() -> dict[str, Any]:
    return {"cases": oracle_wiring(subject_text("runner/candidate.py")),
            "scope_note": "structural evidence of wiring in _run_np_t04_body_stall; not a behavioral run of the case",
            "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# OBSERVERS (behavioral, extracted actual runner unit with named fake classes)
# ---------------------------------------------------------------------------

def oracle_observers(runner_text: str) -> dict[str, str]:
    cases = {}
    ns: dict[str, Any] = {"Any": Any, "Callable": Callable}
    exec_units(runner_text, ("_install_t04_parent_and_target_observers",), ns, "runner")
    outcome_marker = types.SimpleNamespace(name="ROLLBACK_ACKNOWLEDGED")
    boom = RuntimeError("injected")

    class FakeParent:
        def finish_root(self, *, commit):
            if commit:
                raise boom
            return outcome_marker

    returned_obj = (types.SimpleNamespace(subscription_id="s1", outcome="failed", cause="covering_provider_read_failed"),
                    types.SimpleNamespace(persisted=True, refused=False, refuse_reason=None,
                                          cause="covering_provider_read_failed"))

    class FakeTxn:
        def run(self, **kwargs):
            return returned_obj

    originals = (FakeParent.finish_root, FakeTxn.run)
    names = ("app", "app.services", "app.services.covering_parent_adapter", "app.services.covering_target_transaction")
    with Sandbox(names) as box:
        box.put("app", types.ModuleType("app"))
        box.put("app.services", types.ModuleType("app.services"))
        box.put("app.services.covering_parent_adapter",
                types.ModuleType("app.services.covering_parent_adapter")).CoveringParentAdapter = FakeParent
        box.put("app.services.covering_target_transaction",
                types.ModuleType("app.services.covering_target_transaction")).CoveringTargetTransaction = FakeTxn
        parents: list[dict[str, Any]] = []
        runs: list[dict[str, Any]] = []
        restore = ns["_install_t04_parent_and_target_observers"](parents, runs)
        got_outcome = FakeParent().finish_root(commit=False)
        try:
            FakeParent().finish_root(commit=True)
            raised = None
        except BaseException as exc:  # noqa: BLE001
            raised = exc
        got_run = FakeTxn().run(owner_id=1)
        restore()
    require(got_outcome is outcome_marker and raised is boom
            and parents == [{"terminal": "ROLLBACK_ACKNOWLEDGED", "commit_requested": False},
                            {"raised": "RuntimeError", "module": "builtins", "commit_requested": True}],
            "observers:parent same return")
    cases["parent_same_return_and_exception"] = "PASS"
    require(got_run is returned_obj and runs == [{
        "subscription_id": "s1", "outcome": "failed", "cause": "covering_provider_read_failed",
        "failure_present": True, "failure_persisted": True, "failure_refused": False,
        "failure_refuse_reason": None, "failure_cause": "covering_provider_read_failed"}], "observers:target same return")
    cases["target_same_return_and_disposition"] = "PASS"
    require((FakeParent.finish_root, FakeTxn.run) == originals, "observers:restored exactly")
    cases["restored_exactly"] = "PASS"
    return cases


def check_observers() -> dict[str, Any]:
    return {"cases": oracle_observers(subject_text("runner/candidate.py")),
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# RECEIPT-RETENTION (behavioral actual sanitizer + structural key scan)
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
    fn = unit_node(runner_text, CASE_FN)
    scanned = _dict_keys(fn, "measured") + _dict_keys(fn, "observations")
    timing = unit_node(runner_text, "_t04_body_stall_timing")
    returns = [n.value for n in ast.walk(timing) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)]
    scanned += [k.value for r in returns for k in r.keys if isinstance(k, ast.Constant)]
    observers = unit_text(runner_text, "_install_t04_parent_and_target_observers")
    scanned += re.findall(r'"([a-z_]+)": ', observers)
    require(scanned and not [k for k in scanned if ns["_forbidden_key"](k)], "retention:no forbidden key")
    cases["every_emitted_key_survives"] = "PASS"
    sample = {"token_terminal_sequence": [{"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True,
                                           "commit_requested": False}],
              "parent_terminal_sequence": [{"terminal": "ROLLBACK_ACKNOWLEDGED", "commit_requested": False}],
              "failure_disposition": "PERSISTED", "timing": {"stall_exit_reason": "retired", "work_deadline": 1.0},
              "token_terminal_rows": [{"terminal": "X"}], "nested": {"access_token": "S", "ok": 1}}
    out = ns["redact_mapping"](sample)
    require(out["token_terminal_sequence"] == sample["token_terminal_sequence"]
            and out["parent_terminal_sequence"] == sample["parent_terminal_sequence"]
            and out["failure_disposition"] == "PERSISTED" and out["timing"] == sample["timing"],
            "retention:typed evidence survives")
    cases["typed_evidence_survives_sanitizer"] = "PASS"
    require("token_terminal_rows" not in out and out["nested"] == {"ok": 1}, "retention:privacy unchanged")
    cases["privacy_filter_unchanged"] = "PASS"
    return cases


def check_retention() -> dict[str, Any]:
    return {"cases": oracle_retention(subject_text("runner/candidate.py")),
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
    cfg = json.loads(subject_text("config/candidate-runner-config.json"))
    src = json.loads(subject_text("config/source-runner-config.json"))
    require(cfg.get("case_ids") == [CASE_ID] and cfg.get("expected_unknown_cases") == []
            and cfg.get("launch_ready") is False and cfg.get("t04_body_stall_peer_seconds") == 240
            and cfg.get("peer_seconds") == 120
            and src.get("case_ids") == ["NP-V-MS-REFRESH"] and "t04_body_stall_peer_seconds" not in src
            and {k: v for k, v in cfg.items() if k not in ("case_ids", "t04_body_stall_peer_seconds")}
            == {k: v for k, v in src.items() if k != "case_ids"},
            "config:runner")
    cases["runner_config"] = "PASS"
    raw = subject_text("config/candidate-launch-config.json")
    launch, src_launch = json.loads(raw), json.loads(subject_text("config/source-launch-config.json"))
    note = str(launch.get("candidate_note"))
    require(launch.get("launch_ready") is False and launch.get("candidate_launch_ready_staged") is False
            and launch.get("launch_authorized") is False and launch.get("human_launch_authorized") is False
            and launch.get("case_ids") == [CASE_ID] and launch.get("batch_id") == "np-v-t04-body-stall-single-case"
            and launch.get("t04_body_stall_peer_seconds") == 240
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and OWN_ROOT in note and "host launch_ready=false" in note and "runner-config launch_ready=false" in note
            and SOURCE_ROOT not in raw and set(launch) == set(src_launch) | {"t04_body_stall_peer_seconds"}
            and all(launch[k] == src_launch[k] for k in src_launch if k not in LAUNCH_CHANGED_KEYS), "config:launch")
    cases["launch_config"] = "PASS"
    d_src, d_cand = subject_text("config/source-docker-ops-config.json"), subject_text("config/candidate-docker-ops-config.json")
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
            and all(r in s_rows and s_rows[r] == c_rows[r] for r in IMMUTABLE_ROWS)
            and c_rows["api/app/services/microsoft_calendar.py"] == SUBJECT_PINS["app/microsoft_calendar.py"]
            and c_rows["api/app/services/covering_refresh_window.py"] == SUBJECT_PINS["app/covering_refresh_window.py"]
            and c_rows["fixture/np_receipts.py"] == SUBJECT_PINS["fixture/np_receipts.py"], "config:immutables")
    cases["api_and_helpers_immutable"] = "PASS"
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


MUTANT_KINDS = {
    "peer_lax_stop": "behavioral", "peer_deadline_returns": "behavioral", "peer_body_sent": "behavioral",
    "timing_epsilon": "behavioral", "timing_no_reason": "behavioral", "observer_copy_return": "behavioral",
    "query_top_changed": "behavioral", "default_peer_life": "structural", "dropped_token_key": "structural",
}


def check_mutants() -> dict[str, Any]:
    peer, runner = subject_text("peer/candidate.py"), subject_text("runner/candidate.py")
    mutants = {
        "peer_lax_stop": (lambda: oracle_peer(_mutate(peer, M_PEER_LAX_STOP)), "peer:late stop strict"),
        "peer_deadline_returns": (lambda: oracle_peer(_mutate(peer, M_PEER_DEADLINE_RETURNS)), "peer:deadline error"),
        "peer_body_sent": (lambda: oracle_peer(_mutate(peer, M_PEER_BODY_SENT)), "peer:body stall head only"),
        "timing_epsilon": (lambda: oracle_timing(_mutate(runner, M_RUN_EPSILON)), "timing:each inequality stops"),
        "timing_no_reason": (lambda: oracle_timing(_mutate(runner, M_RUN_NO_REASON)), "timing:deadline reason stops"),
        "observer_copy_return": (lambda: oracle_observers(_mutate(runner, M_RUN_OBSERVER_COPY)),
                                 "observers:target same return"),
        "query_top_changed": (lambda: oracle_query(_mutate(runner, M_RUN_QUERY_TOP)), "query:exact literal"),
        "default_peer_life": (lambda: oracle_wiring(_mutate(runner, M_RUN_DEFAULT_PEER)), "wiring:case peer life"),
        "dropped_token_key": (lambda: oracle_retention(_mutate(runner, M_RUN_DROPPED_KEY)),
                              "retention:no forbidden key"),
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
    require(expected.get("kind") == "native-t04-body-stall-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "PEER-CLEAN-STOP": check_peer,
        "TRANSCRIPT-STALL-SCRIPT": check_transcript,
        "QUERY-DERIVATION": check_query,
        "TIMING-PREDICATE": check_timing,
        "RUNNER-WIRING": check_wiring,
        "OBSERVERS": check_observers,
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
