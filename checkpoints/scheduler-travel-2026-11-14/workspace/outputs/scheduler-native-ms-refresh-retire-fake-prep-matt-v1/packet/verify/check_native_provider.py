#!/usr/bin/env python3
"""HELD fake-only checker for the native MS-REFRESH retirement-barrier preparation (Dex 6ED9B65F).

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned): source = Matt MS invalid-grant prep v2 runner 4CBF198E
(scheduler-native-provider-ms-invalid-prep-matt-v2), candidate =
scheduler-native-provider-ms-refresh-retire-prep-matt-v1 runner, their diff,
source/candidate runner-config, launch-config and docker-ops-config, both payload
manifests, both nested launch-packet manifests, and the unchanged provider peer
np_provider_peer.py (BFB271D7) whose retire_owned/sanitized_state interface the fake
peer models.

Execution surfaces (all fake; no socket, TLS, DB, Docker, process or vendor package):
- BEHAVIORAL: the extracted, byte-identical _retire_selected_peer_then_observe with a
  named fake peer (np_suite.SuiteStop is a named fake).
- STRUCTURAL (AST/text only): the _run_np_v_ms_refresh barrier/order/finally wiring
  and the exact body delta. Structural checks are labelled as structural; they are
  not a behavioral run of the whole case.

Proof scope: finite fixture/source properties of the corrected retirement barrier.
NOT proved: native refresh, T06 closure, peer timing, worker scheduling, or any
native TLS/database/provider behavior.
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
PACKET_NAME = "scheduler-native-ms-refresh-retire-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/source.py": "4CBF198E0ACC605897D99C00A334E50B58A1DC5B3AAE91FF7856A319BBA6F7E1",
    "runner/candidate.py": "1A95E8340B2D45B0DA4D77B14B7726E485691EB94B3CF765AD4497F96020A8B2",
    "diff/np_runner_entry.py.diff": "425F23FC3AD1991C993D60D7D69AEDB8C62619737F4E5A6B8F2AA434A90EEF5B",
    "config/source-runner-config.json": "10106B8278033FC0DBC83D5841446F2D2B7476960C90DB654AF4AAF25549E004",
    "config/candidate-runner-config.json": "D4C8BDBD83C3C5D0F76564C5E5BB6B5962CBBEBA4D3D3C3618E55DC8C693A88A",
    "diff/runner-config.json.diff": "4BCEFF6B8F376F5C6837B1F11B4107A09C042544ABE4599A7D840405CFC23EF0",
    "config/source-launch-config.json": "4584428948A544473C1F7ABF7E9AD87DBAFCDBB0828C987820C9CE2BE1C14098",
    "config/candidate-launch-config.json": "09C9D618DC0177FACD8E29A35DEDEEAFF637424D0C447C939B4834EC07EB7ED5",
    "config/source-docker-ops-config.json": "BC6F33B2928E429512628A5D402020018490B251A9D3A2C7CB7237095D81F605",
    "config/candidate-docker-ops-config.json": "9455026A775EF769C71D960A71ADEBC623BDC01299844C08B5F69F0C90130F1D",
    "manifest/source.txt": "D9F14FF142C972F886C9BA066E292B09E24BED4C51DD98F9DCAFDEB0632BC868",
    "manifest/candidate.txt": "CC02F38CFBD8542AD49DA8663FE3BCACD8F8712FDD97FE53D5F739A52C0CA687",
    "manifest/source-nested.txt": "545C6BDD6A9E99850ECA62F0779D58052BE7A57BBA661B154FD4DBFC6F54153E",
    "manifest/candidate-nested.txt": "C83A5E9E324C77465F03C3EEE371AEF7A16917FCD8335B943AFF98E2FAD7AB5B",
    "fixture/np_provider_peer.py": "BFB271D770D08BC161E9613564ECA799B7E28884D8211E10228F5973A4A271BF",
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
    "RETIREMENT-HELPER",
    "REFRESH-BARRIER-WIRING",
    "REFRESH-ASSERTIONS-PRESERVED",
    "BATCH-CONFIG",
    "PRIOR-FAKE-APPLICABILITY",
    "ACTUAL-SOURCE-MUTANTS",
)

HELPER = "_retire_selected_peer_then_observe"
CASE_FN = "_run_np_v_ms_refresh"
CASE_ID = "NP-V-MS-REFRESH"
BATCH_ID = "np-v-ms-refresh-single-case"
OWN_ROOT = "scheduler-native-provider-ms-refresh-retire-prep-matt-v1"
SOURCE_ROOT = "scheduler-native-provider-ms-invalid-prep-matt-v2"
FOREIGN_ROOTS = (SOURCE_ROOT, "ms-invalid-prep-matt-v1", "t05-client-cause", "t05-launch-dex", "t05-prep-matt",
                 "ms-refresh-launch-dex", "ms-merge-refresh-prep", "nonexpired-retirement-launch")
EVIDENCE_LEAF = "scheduler-native-provider-diagnostic-launch-v1.evidence"
LAUNCH_CHANGED_KEYS = {"batch_id", "case_ids", "manifest_sha256", "docker_ops_config_path", "receipt_directory",
                       "candidate_note", "dex_r1_revise_note"}
CHANGED_PAYLOAD_ROWS = {"fixture/np_runner_entry.py": "runner/candidate.py",
                        "runner-config.json": "config/candidate-runner-config.json"}
CHANGED_NESTED_ROWS = {"payload/fixture/np_runner_entry.py": "runner/candidate.py",
                       "payload/runner-config.json": "config/candidate-runner-config.json",
                       "payload/SHA256SUMS.txt": "manifest/candidate.txt",
                       "host/launch-config.json": "config/candidate-launch-config.json",
                       "host/docker-ops-config.json": "config/candidate-docker-ops-config.json"}
UNCHANGED_DEPENDENCY_ROWS = ("fixture/np_provider_peer.py", "fixture/np_provider_transcript.py",
                             "fixture/np_provider_routes.py", "fixture/np_suite.py", "fixture/np_integrated_runner.py",
                             "fixture/np_auth_seed.py", "fixture/np_alias_seed.py", "fixture/docker_transport.py",
                             "fixture/prepare-np-provider-tls.sh")
# Prior selected-retirement fake (Dex staging scheduler-ms-selected-retirement-fake-dex-v1, PASS 13/85,
# result A8CDBF04...): its MS-INVALID runner subject is exactly this packet's source runner.
PRIOR_SELECTED_FAKE_RUNNER_PIN = "4CBF198E0ACC605897D99C00A334E50B58A1DC5B3AAE91FF7856A319BBA6F7E1"
PRIOR_SELECTED_FAKE_RESULT_PIN = "A8CDBF04FD2D7FC5A76A7234B54F99322FC3FCD5B75A8455CA5CD3B22C85A4DF"

BARRIER_CALL = "retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)"
SOURCE_SNAPSHOT = "peer_state = peer.sanitized_state()"
REMOVED_LATE_BLOCK = (
    "retirement_attempted = True",
    "retirement = peer.retire_owned(join_seconds=5.0)",
    "retirement_done = True",
    'if retirement.get("joined") is not True:\n    raise SuiteStop("peer worker unjoined — UNKNOWN")',
)
REMOVED_UNJOINED_MESSAGE = "peer worker unjoined — UNKNOWN"

# Mutation anchors (each verified unique in the whole candidate runner text it edits).
BARRIER_BLOCK = ("        retirement_attempted = True\n"
                 "        retirement, peer_state = _retire_selected_peer_then_observe(peer, join_seconds=5.0)\n"
                 "        retirement_done = True\n")
M_WORKER_ERROR_REMOVED = ('    if retirement.get("worker_error_kind") is not None:\n'
                          '        raise SuiteStop("selected peer worker recorded an error")\n', '')
M_WORKER_ERROR_TRUTHY = ('    if retirement.get("worker_error_kind") is not None:\n',
                         '    if retirement.get("worker_error_kind"):\n')
M_HELPER_PRE_JOIN_A = ('    retirement = peer.retire_owned(join_seconds=join_seconds)\n',
                       '    early_state = peer.sanitized_state()\n'
                       '    retirement = peer.retire_owned(join_seconds=join_seconds)\n')
M_HELPER_PRE_JOIN_B = ('    return retirement, peer.sanitized_state()\n', '    return retirement, early_state\n')
M_BODY_PRE_JOIN_SNAPSHOT = (BARRIER_BLOCK, "        pre_state = peer.sanitized_state()\n" + BARRIER_BLOCK
                            + "        peer_state = pre_state\n")
M_BODY_SECOND_RETIRE = (BARRIER_BLOCK, BARRIER_BLOCK + "        peer.retire_owned(join_seconds=5.0)\n")
M_ATTEMPT_GUARD_MISSING = (BARRIER_BLOCK, BARRIER_BLOCK.replace("        retirement_attempted = True\n", "", 1))
M_HELPER_IGNORED = (BARRIER_BLOCK, "        retirement_attempted = True\n"
                                   "        retirement = peer.retire_owned(join_seconds=5.0)\n"
                                   "        peer_state = peer.sanitized_state()\n"
                                   "        retirement_done = True\n")


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
        old_start = int(match.group(1))
        old_len, new_len = int(match.group(2) or "1"), int(match.group(4) or "1")
        start = old_start - 1
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
                   "payload/fixture/np_runner_entry.py", 2),
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
    segment = ast.get_source_segment(text, unit_node(text, name), padded=True)
    require(segment is not None, f"no segment:{name}")
    return textwrap.dedent(segment)


def exec_units(text: str, names: tuple[str, ...], namespace: dict[str, Any], label: str) -> dict[str, Any]:
    for name in names:
        source = "from __future__ import annotations\n" + unit_text(text, name)
        exec(compile(source, f"<extracted:{label}:{name}>", "exec"), namespace)
    return namespace


def differing_names(left: str, right: str) -> tuple[set[str], set[str]]:
    def table(text: str) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for node in ast.parse(text).body:
            result.setdefault(ast.dump(node), []).append(node_name(node) or "<unnamed>")
        return result
    lt, rt = table(left), table(right)
    for dump in set(lt) & set(rt):
        require(len(lt[dump]) == len(rt[dump]), "duplicate top-level multiplicity changed")
    return ({n for d, ns in lt.items() if d not in rt for n in ns},
            {n for d, ns in rt.items() if d not in lt for n in ns})


def dump_stmt(snippet: str) -> str:
    return ast.dump(_single(ast.parse(textwrap.dedent(snippet)).body, "snippet"))


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [c for c in ast.walk(node) if isinstance(c, ast.Call) and (
        (isinstance(c.func, ast.Name) and c.func.id == name)
        or (isinstance(c.func, ast.Attribute) and c.func.attr == name))]


def _mutate(text: str, mutation: tuple[str, str]) -> str:
    require(text.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
    return text.replace(*mutation)


def check_preserved_outside_change() -> dict[str, Any]:
    src, cand = subject_text("runner/source.py"), subject_text("runner/candidate.py")
    got_cand, got_src = differing_names(cand, src)
    require(got_cand == {CASE_FN} and got_src == {CASE_FN}, "preserved:runner")
    cases = {"runner": "PASS"}
    require(unit_text(src, HELPER) == unit_text(cand, HELPER), "preserved:helper byte identical")
    cases["helper_byte_identical"] = "PASS"
    return {"cases": cases, "helper_sha256": sha256_bytes(unit_text(cand, HELPER).encode("utf-8")),
            "control_kind": "structural_source", "observed": "PASS"}


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


# ---------------------------------------------------------------------------
# RETIREMENT-HELPER (behavioral, extracted unchanged helper + named fake peer)
# ---------------------------------------------------------------------------

class SuiteStopFake(Exception):
    """Named fake for np_suite.SuiteStop (the helper imports it locally)."""


class FakePeerRetirementUnknown(Exception):
    """Named fake for np_provider_peer.PeerRetirementUnknown."""


class FakeSelectedPeer:
    """Named fake for the retire_owned/sanitized_state interface only.

    The final exchange-inventory row is published while the bounded join completes
    (inside retire_owned), modelling the asynchronous peer append/teardown that a
    pre-join snapshot would miss. Every call is recorded in order.
    """

    def __init__(self, *, joined: Any = True, worker_error: Any = None,
                 raises: BaseException | None = None) -> None:
        self.joined, self.worker_error, self.raises = joined, worker_error, raises
        self.calls: list[tuple[Any, ...]] = []
        self.inventory: list[dict[str, str]] = [{"method": "POST", "path": "/pre-join"}]

    def retire_owned(self, *, join_seconds: float) -> dict[str, Any]:
        self.calls.append(("retire", join_seconds))
        if self.raises is not None:
            raise self.raises
        self.inventory.append({"method": "GET", "path": "/published-during-join"})
        return {"joined": self.joined, "worker_error_kind": self.worker_error}

    def sanitized_state(self) -> dict[str, Any]:
        self.calls.append(("state",))
        return {"exchange_inventory": [dict(row) for row in self.inventory]}


def run_helper(runner_text: str, peer: FakeSelectedPeer) -> dict[str, Any]:
    namespace: dict[str, Any] = {"Any": Any}
    exec_units(runner_text, (HELPER,), namespace, "runner")
    escaped: BaseException | None = None
    result: Any = None
    with Sandbox(("np_suite",)) as box:
        box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStopFake
        try:
            result = namespace[HELPER](peer, join_seconds=5.0)
        except BaseException as exc:  # noqa: BLE001
            escaped = exc
    require("np_suite" not in sys.modules, "helper sandbox restored")
    return {"result": result, "escaped": escaped, "calls": list(peer.calls)}


def oracle_retire_behavior(runner_text: str) -> dict[str, str]:
    cases = {}
    run = run_helper(runner_text, FakeSelectedPeer())
    ok = (run["escaped"] is None and isinstance(run["result"], tuple) and len(run["result"]) == 2
          and run["result"][0] == {"joined": True, "worker_error_kind": None}
          and run["result"][1]["exchange_inventory"][-1] == {"method": "GET", "path": "/published-during-join"}
          and run["calls"] == [("retire", 5.0), ("state",)])
    require(ok, "retire:post-join state")
    cases["joined_no_error_post_join_state"] = "PASS"
    run = run_helper(runner_text, FakeSelectedPeer(worker_error="OSError"))
    require(type(run["escaped"]) is SuiteStopFake and run["calls"] == [("retire", 5.0)], "retire:worker error refused")
    cases["worker_error_refused"] = "PASS"
    run = run_helper(runner_text, FakeSelectedPeer(worker_error=""))
    require(type(run["escaped"]) is SuiteStopFake and run["calls"] == [("retire", 5.0)], "retire:empty error refused")
    cases["empty_error_refused_distinct_from_none"] = "PASS"
    run = run_helper(runner_text, FakeSelectedPeer(joined=False))
    require(type(run["escaped"]) is SuiteStopFake and run["calls"] == [("retire", 5.0)], "retire:unjoined refused")
    cases["unjoined_refused"] = "PASS"
    unknown = FakePeerRetirementUnknown("owned peer worker unjoined")
    run = run_helper(runner_text, FakeSelectedPeer(raises=unknown))
    require(run["escaped"] is unknown and run["calls"] == [("retire", 5.0)], "retire:unknown same object")
    cases["retirement_unknown_same_object"] = "PASS"
    other = RuntimeError("injected")
    run = run_helper(runner_text, FakeSelectedPeer(raises=other))
    require(run["escaped"] is other and run["calls"] == [("retire", 5.0)], "retire:other exception same object")
    cases["other_exception_same_object"] = "PASS"
    attempts = [sum(1 for c in run_helper(runner_text, peer)["calls"] if c[0] == "retire") for peer in (
        FakeSelectedPeer(), FakeSelectedPeer(worker_error="ValueError"), FakeSelectedPeer(worker_error=""),
        FakeSelectedPeer(joined=None), FakeSelectedPeer(raises=FakePeerRetirementUnknown()),
        FakeSelectedPeer(raises=KeyError("k")))]
    require(attempts == [1, 1, 1, 1, 1, 1], "retire:single attempt")
    cases["single_attempt_all_paths"] = "PASS"
    return cases


def check_retirement_helper() -> dict[str, Any]:
    return {"cases": oracle_retire_behavior(subject_text("runner/candidate.py")),
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# REFRESH-BARRIER-WIRING (structural)
# ---------------------------------------------------------------------------

def main_try(fn: ast.AST) -> ast.Try:
    return _single([s for s in fn.body if isinstance(s, ast.Try) and _calls(s, "case_result_receipt")], "main try")


def oracle_barrier(runner_text: str) -> dict[str, str]:
    cases = {}
    fn = unit_node(runner_text, CASE_FN)
    main = main_try(fn)
    dumps = [ast.dump(s) for s in main.body]
    idx = [i for i, d in enumerate(dumps) if d == dump_stmt(BARRIER_CALL)]
    require(len(idx) == 1 and len(_calls(fn, HELPER)) == 1, "barrier:helper called once")
    cases["helper_called_once"] = "PASS"
    i = idx[0]
    require(0 < i < len(dumps) - 1 and dumps[i - 1] == dump_stmt("retirement_attempted = True")
            and dumps[i + 1] == dump_stmt("retirement_done = True"), "barrier:attempt marked before helper")
    cases["attempt_marked_before_helper"] = "PASS"
    body_retires = [c for s in main.body for c in _calls(s, "retire_owned")]
    final_retires = [c for s in main.finalbody for c in _calls(s, "retire_owned")]
    guard = _single([s for s in main.finalbody if isinstance(s, ast.If) and _calls(s, "retire_owned")], "finally guard")
    guard_names = {n.id for n in ast.walk(guard.test) if isinstance(n, ast.Name)}
    require(not body_retires and len(final_retires) == 1 and "retirement_attempted" in guard_names,
            "barrier:no second retirement")
    cases["no_second_retirement"] = "PASS"
    body_states = [c for s in main.body for c in _calls(s, "sanitized_state")]
    barrier_line = main.body[i].lineno
    state_uses = [n.lineno for n in ast.walk(main) if isinstance(n, ast.Name) and n.id == "peer_state"
                  and isinstance(n.ctx, ast.Load)]
    check_line = _single(_calls(main, "check_oracles_immediate"), "check_oracles_immediate").lineno
    receipt = _single(_calls(main, "case_result_receipt"), "case_result_receipt")
    kw = {k.arg: k.value for k in receipt.keywords}
    require(not body_states and bool(state_uses) and min(state_uses) > barrier_line
            and barrier_line < check_line < receipt.lineno
            and all(isinstance(kw.get(k), ast.Constant) and kw[k].value is v
                    for k, v in (("passed", True), ("workers_joined", True), ("expected_unknown", False))),
            "barrier:post-join state only")
    cases["post_join_state_only"] = "PASS"
    return cases


def check_barrier_wiring() -> dict[str, Any]:
    return {"cases": oracle_barrier(subject_text("runner/candidate.py")),
            "scope_note": "structural evidence of order and guards in _run_np_v_ms_refresh; not a behavioral run of "
                          "the case",
            "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# REFRESH-ASSERTIONS-PRESERVED (structural)
# ---------------------------------------------------------------------------

def _suite_stop_messages(fn: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name) \
                and node.exc.func.id == "SuiteStop" and node.exc.args:
            arg = node.exc.args[0]
            out.add(arg.value if isinstance(arg, ast.Constant) else ast.dump(arg))
    return out


def check_assertions_preserved() -> dict[str, Any]:
    cases = {}
    src_fn = unit_node(subject_text("runner/source.py"), CASE_FN)
    cand_fn = unit_node(subject_text("runner/candidate.py"), CASE_FN)
    src_main, cand_main = main_try(src_fn), main_try(cand_fn)
    src_dumps = [ast.dump(s) for s in src_main.body]
    cand_dumps = [ast.dump(s) for s in cand_main.body]
    snap = [i for i, d in enumerate(src_dumps) if d == dump_stmt(SOURCE_SNAPSHOT)]
    late = [dump_stmt(s) for s in REMOVED_LATE_BLOCK]
    late_at = [i for i in range(len(src_dumps) - 3) if src_dumps[i:i + 4] == late]
    barrier = [dump_stmt(s) for s in ("retirement_attempted = True", BARRIER_CALL, "retirement_done = True")]
    bar_at = [i for i in range(len(cand_dumps) - 2) if cand_dumps[i:i + 3] == barrier]
    ok = len(snap) == 1 and len(late_at) == 1 and len(bar_at) == 1 and snap[0] < late_at[0] and bar_at[0] == snap[0]
    if ok:
        src_rest = src_dumps[:snap[0]] + src_dumps[snap[0] + 1:late_at[0]] + src_dumps[late_at[0] + 4:]
        cand_rest = cand_dumps[:bar_at[0]] + cand_dumps[bar_at[0] + 3:]
        ok = src_rest == cand_rest
    require(ok, "assertions:body delta exact")
    cases["body_delta_exact"] = "PASS"
    outside_src = [ast.dump(s) for s in src_fn.body if s is not src_main]
    outside_cand = [ast.dump(s) for s in cand_fn.body if s is not cand_main]
    require(outside_src == outside_cand
            and [ast.dump(h) for h in src_main.handlers] == [ast.dump(h) for h in cand_main.handlers]
            and [ast.dump(s) for s in src_main.finalbody] == [ast.dump(s) for s in cand_main.finalbody]
            and [ast.dump(s) for s in src_main.orelse] == [ast.dump(s) for s in cand_main.orelse],
            "assertions:handlers and finally identical")
    cases["handlers_finally_and_setup_identical"] = "PASS"
    src_msgs, cand_msgs = _suite_stop_messages(src_fn), _suite_stop_messages(cand_fn)
    require(REMOVED_UNJOINED_MESSAGE in src_msgs and cand_msgs == src_msgs - {REMOVED_UNJOINED_MESSAGE},
            "assertions:suite stop messages")
    cases["suite_stop_messages_preserved"] = "PASS"
    return {"cases": cases,
            "removed_message_note": "the removed late 'peer worker unjoined' check is subsumed by the helper's "
                                    "joined-is-True requirement (message 'selected peer worker unjoined - UNKNOWN'); "
                                    "the helper also adds the worker_error_kind-is-None requirement",
            "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# BATCH-CONFIG and PRIOR-FAKE-APPLICABILITY
# ---------------------------------------------------------------------------

def rows(text: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in text.splitlines():
        pin, sep, rel = line.partition("  ")
        require(sep == "  " and re.fullmatch(r"[0-9A-F]{64}", pin) is not None and rel not in table,
                "malformed manifest row")
        table[rel] = pin
    return table


def check_batch_config() -> dict[str, Any]:
    cases = {}
    cfg = json.loads(subject_text("config/candidate-runner-config.json"))
    src_cfg = json.loads(subject_text("config/source-runner-config.json"))
    require(cfg.get("case_ids") == [CASE_ID] and cfg.get("expected_unknown_cases") == []
            and cfg.get("launch_ready") is False and cfg.get("launch_authorized") is False
            and {k: v for k, v in cfg.items() if k != "case_ids"} == {k: v for k, v in src_cfg.items() if k != "case_ids"},
            "batch:runner config")
    cases["runner_config"] = "PASS"
    raw = subject_text("config/candidate-launch-config.json")
    launch, src_launch = json.loads(raw), json.loads(subject_text("config/source-launch-config.json"))
    note = str(launch.get("candidate_note"))
    require(launch.get("launch_ready") is False and launch.get("candidate_launch_ready_staged") is False
            and launch.get("human_launch_authorized") is False and launch.get("launch_authorized") is False
            and launch.get("case_ids") == [CASE_ID] and launch.get("expected_unknown_cases") == []
            and launch.get("batch_id") == BATCH_ID
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and src_launch.get("manifest_sha256") == SUBJECT_PINS["manifest/source.txt"]
            and OWN_ROOT in note and "host launch_ready=false" in note
            and "runner-config launch_ready=false" in note
            and not any(root in raw for root in FOREIGN_ROOTS) and set(launch) == set(src_launch)
            and all(launch[k] == src_launch[k] for k in src_launch if k not in LAUNCH_CHANGED_KEYS),
            "batch:launch config")
    cases["launch_config"] = "PASS"
    docker_raw = subject_text("config/candidate-docker-ops-config.json")
    src_docker_raw = subject_text("config/source-docker-ops-config.json")
    require(src_docker_raw.count(SOURCE_ROOT) == 7 and docker_raw.count(OWN_ROOT) == 7
            and not any(root in docker_raw for root in FOREIGN_ROOTS)
            and src_docker_raw.replace(SOURCE_ROOT, OWN_ROOT) == docker_raw, "batch:docker ops root rename only")
    cases["docker_ops_root_rename_only"] = "PASS"
    docker = json.loads(docker_raw)
    receipt_dir = str(launch.get("receipt_directory"))
    binds = [list(b) for b in (docker.get("roles") or {}).get("runner", {}).get("readonly_binds") or []]
    require(receipt_dir.endswith("\\" + OWN_ROOT + "\\" + EVIDENCE_LEAF)
            and docker.get("public_ca_directory") == receipt_dir + "\\public-ca"
            and [docker["public_ca_directory"], "/public-ca"] in binds
            and str(launch.get("docker_ops_config_path")).endswith(
                "\\" + OWN_ROOT + "\\scheduler-native-provider-diagnostic-launch-v1\\host\\docker-ops-config.json"),
            "batch:path agreement")
    cases["evidence_ca_readonly_bind_agreement"] = "PASS"
    s_rows, c_rows = rows(subject_text("manifest/source.txt")), rows(subject_text("manifest/candidate.txt"))
    changed = {rel for rel in s_rows if s_rows[rel] != c_rows.get(rel)}
    require(len(s_rows) == 257 and set(s_rows) == set(c_rows) and changed == set(CHANGED_PAYLOAD_ROWS)
            and all(c_rows[rel] == SUBJECT_PINS[subject] for rel, subject in CHANGED_PAYLOAD_ROWS.items())
            and s_rows["fixture/np_runner_entry.py"] == SUBJECT_PINS["runner/source.py"]
            and c_rows.get("fixture/np_provider_peer.py") == SUBJECT_PINS["fixture/np_provider_peer.py"],
            "batch:payload manifest delta")
    cases["payload_delta_exact"] = "PASS"
    s_nest, c_nest = rows(subject_text("manifest/source-nested.txt")), rows(subject_text("manifest/candidate-nested.txt"))
    changed = {rel for rel in s_nest if s_nest[rel] != c_nest.get(rel)}
    require(len(s_nest) == 269 and set(s_nest) == set(c_nest) and changed == set(CHANGED_NESTED_ROWS)
            and all(c_nest[rel] == SUBJECT_PINS[subject] for rel, subject in CHANGED_NESTED_ROWS.items())
            and s_nest["payload/SHA256SUMS.txt"] == SUBJECT_PINS["manifest/source.txt"]
            and s_nest["host/launch-config.json"] == SUBJECT_PINS["config/source-launch-config.json"],
            "batch:nested manifest delta")
    cases["nested_delta_exact"] = "PASS"
    return {"cases": cases, "control_kind": "config_data", "observed": "PASS"}


def check_prior_applicability() -> dict[str, Any]:
    cases = {}
    src, cand = subject_text("runner/source.py"), subject_text("runner/candidate.py")
    require(SUBJECT_PINS["runner/source.py"] == PRIOR_SELECTED_FAKE_RUNNER_PIN
            and unit_text(src, HELPER) == unit_text(cand, HELPER), "applicability:selected helper scope")
    cases["selected_fake_helper_scope_maps"] = "PASS"
    s_rows, c_rows = rows(subject_text("manifest/source.txt")), rows(subject_text("manifest/candidate.txt"))
    peer = subject_text("fixture/np_provider_peer.py")
    require(all(rel in s_rows and s_rows[rel] == c_rows.get(rel) for rel in UNCHANGED_DEPENDENCY_ROWS)
            and peer.count("    def retire_owned(self, *, join_seconds: float = 5.0) -> dict[str, Any]:\n") == 1
            and peer.count('            "worker_error_kind": type(self._error).__name__ if self._error else None,\n') == 1
            and peer.count("    def sanitized_state(self) -> dict[str, Any]:\n") == 1,
            "applicability:dependencies unchanged")
    cases["dependencies_unchanged_and_interface_literal"] = "PASS"
    return {"cases": cases, "not_transferred": [
        "Selected-retirement fake PASS 13/85 (Dex staging scheduler-ms-selected-retirement-fake-dex-v1, result "
        + PRIOR_SELECTED_FAKE_RESULT_PIN + ") verified the helper in this exact source runner (4CBF198E) and the "
        "MS-INVALID/NONEXPIRED body barriers; its MS-INVALID/NONEXPIRED body checks do not transfer to "
        "_run_np_v_ms_refresh, which is re-checked structurally here.",
        "Prior MS-REFRESH fakes covered the unchanged refresh units (token/transport/terminal/persistence) at their "
        "recorded scopes; nothing here re-establishes them, and no native refresh or T06 closure is claimed."],
        "control_kind": "applicability_map", "observed": "PASS"}


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
    "worker_error_guard_removed": "behavioral",
    "worker_error_truthiness": "behavioral",
    "helper_pre_join_snapshot": "behavioral",
    "body_pre_join_snapshot": "structural",
    "body_second_retirement": "structural",
    "attempt_guard_missing": "structural",
    "helper_ignored": "structural",
}


def check_mutants() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    mutants = {
        "worker_error_guard_removed": (lambda: oracle_retire_behavior(_mutate(runner, M_WORKER_ERROR_REMOVED)),
                                       "retire:worker error refused"),
        "worker_error_truthiness": (lambda: oracle_retire_behavior(_mutate(runner, M_WORKER_ERROR_TRUTHY)),
                                    "retire:empty error refused"),
        "helper_pre_join_snapshot": (lambda: oracle_retire_behavior(
            _mutate(_mutate(runner, M_HELPER_PRE_JOIN_A), M_HELPER_PRE_JOIN_B)), "retire:post-join state"),
        "body_pre_join_snapshot": (lambda: oracle_barrier(_mutate(runner, M_BODY_PRE_JOIN_SNAPSHOT)),
                                   "barrier:post-join state only"),
        "body_second_retirement": (lambda: oracle_barrier(_mutate(runner, M_BODY_SECOND_RETIRE)),
                                   "barrier:no second retirement"),
        "attempt_guard_missing": (lambda: oracle_barrier(_mutate(runner, M_ATTEMPT_GUARD_MISSING)),
                                  "barrier:attempt marked before helper"),
        "helper_ignored": (lambda: oracle_barrier(_mutate(runner, M_HELPER_IGNORED)), "barrier:helper called once"),
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
    require(expected.get("kind") == "native-ms-refresh-retire-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "RETIREMENT-HELPER": check_retirement_helper,
        "REFRESH-BARRIER-WIRING": check_barrier_wiring,
        "REFRESH-ASSERTIONS-PRESERVED": check_assertions_preserved,
        "BATCH-CONFIG": check_batch_config,
        "PRIOR-FAKE-APPLICABILITY": check_prior_applicability,
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
