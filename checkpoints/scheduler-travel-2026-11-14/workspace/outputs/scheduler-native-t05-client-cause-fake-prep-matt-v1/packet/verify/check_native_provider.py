#!/usr/bin/env python3
"""HELD fake-only checker for the native T05 client-cause diagnostic preparation (Dex 9F9FF48E).

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned): source = failed-run staging runner 1D70164C (scheduler-native-
provider-t05-launch-dex-v1), candidate = scheduler-native-provider-t05-client-cause-prep-
matt-v1 runner, their diff, source/candidate runner-config and launch-config, both
payload manifests, and the unchanged host validator docker_transport.py (7F7EA820).

Execution surfaces (all fake; no socket, TLS, DB, Docker, process or vendor package):
- BEHAVIORAL: the extracted candidate helper _t05_classify_or_chain with the extracted
  unchanged classifier and expected tuples (np_suite.SuiteStop is a named fake), the
  extracted actual stop_payload over a sandboxed temporary owned root whose SHA256SUMS
  pins one fake owned module that raises the client exceptions (so tracebacks carry
  real owned frames), and the extracted actual host validator
  DockerOps._record_runner_stop with a named fake self.
- STRUCTURAL (AST/text only): _t05_observe capture/order wiring and the partition.
Structural checks are labelled as structural; they are not behavioral proof.

Proof scope: finite fixture/source properties of the diagnostic chain and its bounded
export. NOT proved: which client exception a native run produces, any native TLS/EOF
behavior, peer or retirement timing, or any T05 requirement.
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
import tempfile
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
PACKET_NAME = "scheduler-native-t05-client-cause-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/source.py": "1D70164C8EFD7D1CD0A9ED59F23D9F8A4ED9F68B806364B366E2E707259AAA7E",
    "runner/candidate.py": "1AEDEE93B1076D104E05700833548AE11B9AB4751E232E591FB615AAD72961BB",
    "diff/np_runner_entry.py.diff": "3818CF6A705C5297AF97C307E217C7944B5E046A84F18B11C2B3591B6BDD42AC",
    "config/source-runner-config.json": "9E45F6B686B9E34E455BCDC6154AB8E80A6E2F780D8134A380F15EBC135B706B",
    "config/candidate-runner-config.json": "96782CB425239BC6F121949DABE16B4B53528E249BE625DD25A9811DA7D07E71",
    "diff/runner-config.json.diff": "E16FF22B457597464DD191B67F8DE24C8B612BB585946AC8493C0A6E03203026",
    "config/source-launch-config.json": "A9E724563A489498BBA45E7B3E251373BABFAB341BCD91B64A00A7C648538DC3",
    "config/candidate-launch-config.json": "39AAEE8BA9A18BBB27AEA471CE1329F069C955CEFCE3AC35184804B230CA560E",
    "manifest/source.txt": "EEBC1403FB0FCDD58A23717F657C8910870D0CE6B66DFD0FD7EA5F030CB8054B",
    "manifest/candidate.txt": "4076B0D21601C31B8688586B241EB42A2E6B0026EE87D307A042CD01F570D2A6",
    "fixture/docker_transport.py": "7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53",
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
    "CHAIN-HELPER",
    "OBSERVE-WIRING",
    "STOP-PRODUCER-AND-VALIDATOR",
    "BATCH-CONFIG",
    "PRIOR-FAKE-APPLICABILITY",
    "ACTUAL-SOURCE-MUTANTS",
)

HELPER = "_t05_classify_or_chain"
CLASSIFIER_UNITS = ("T05_SHORT_CL_REFUSAL_CLASS", "T05_ABRUPT_CLIENT_CLASSES", "_t05_classify_client_outcome")
T05_IDS = ["NP-T05-ORDERLY-CLOSE", "NP-T05-ABRUPT-TRUNCATION"]
OWN_ROOT = "scheduler-native-provider-t05-client-cause-prep-matt-v1"
FOREIGN_ROOTS = ("t05-launch-dex-v1", "t05-prep-matt-v1", "t05-prep-matt-v2", "t05-prep-matt-v3",
                 "ms-invalid-prep-matt", "ms-nonexpired-retire", "nonexpired-retirement-launch")
LAUNCH_CHANGED_KEYS = {"launch_ready", "candidate_launch_ready_staged", "manifest_sha256", "docker_ops_config_path",
                       "receipt_directory", "candidate_note", "dex_r1_revise_note"}
CHANGED_PAYLOAD_ROWS = {"fixture/np_runner_entry.py": "runner/candidate.py",
                        "runner-config.json": "config/candidate-runner-config.json"}
SECRET = "NP-SECRET-MARKER-7F3A-DO-NOT-EXPORT"
RUNNER_ID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
OWNED_REL = "fixture/fake_owned.py"
FAKE_OWNED = (
    "def raise_plain(cls, message):\n"
    "    raise cls(message)\n"
    "\n"
    "\n"
    "def raise_cleanup(unknown_cls, primary_cls, message):\n"
    "    try:\n"
    "        raise primary_cls(message)\n"
    "    finally:\n"
    "        raise unknown_cls(message)\n"
    "\n"
    "\n"
    "def raise_suppressed(outer_cls, inner_cls, message):\n"
    "    try:\n"
    "        raise inner_cls(message)\n"
    "    except inner_cls:\n"
    "        raise outer_cls(message) from None\n"
    "\n"
    "\n"
    "def raise_deep(cls, message, depth):\n"
    "    if depth <= 0:\n"
    "        raise cls(message)\n"
    "    raise_deep(cls, message, depth - 1)\n"
    "\n"
    "\n"
    "def raise_chain4(classes, message):\n"
    "    try:\n"
    "        try:\n"
    "            try:\n"
    "                raise classes[3](message)\n"
    "            except classes[3]:\n"
    "                raise classes[2](message)\n"
    "        except classes[2]:\n"
    "            raise classes[1](message)\n"
    "    except classes[1]:\n"
    "        raise classes[0](message)\n"
)

# Mutation anchors (each verified unique in the whole runner text it edits).
M_CAUSE_DROPPED = ("        raise stop from client_exc\n", "        raise stop\n")
M_WRONG_CAUSE = ("        raise stop from client_exc\n", "        raise stop from RuntimeError()\n")
M_NONE_CHAINED = ("        if client_exc is None:\n            raise\n        raise stop from client_exc\n",
                  "        raise stop from client_exc\n")
M_EXPORT_MESSAGE = ("            exceptions.append({'kind': kind(current), 'frames': frames})\n",
                    "            exceptions.append({'kind': kind(current), 'frames': frames, 'message': str(current)})\n")
M_CHAIN_BEFORE_RETIRE = ("    finally:\n        retirement = peer.retire_owned(join_seconds=5.0)\n",
                         "    finally:\n        label = _t05_classify_or_chain(expectation, outcome, client_exc)\n"
                         "        retirement = peer.retire_owned(join_seconds=5.0)\n")
M_CAPTURE_DROPPED = ("            client_exc = exc\n", "")


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
                   "payload/fixture/np_runner_entry.py", 3),
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


def unit_node(text: str, name: str, class_name: str | None = None) -> ast.AST:
    body = ast.parse(text).body
    if class_name is not None:
        body = _single([n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name],
                       f"class {class_name}").body
    return _single([n for n in body if node_name(n) == name], f"unit {name}")


def unit_text(text: str, name: str, class_name: str | None = None) -> str:
    segment = ast.get_source_segment(text, unit_node(text, name, class_name), padded=True)
    require(segment is not None, f"no segment:{name}")
    return textwrap.dedent(segment)


def exec_units(text: str, names: tuple[str, ...], namespace: dict[str, Any], label: str,
               class_name: str | None = None) -> dict[str, Any]:
    for name in names:
        source = "from __future__ import annotations\n" + unit_text(text, name, class_name)
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


def dump_expr(snippet: str) -> str:
    return ast.dump(ast.parse(snippet, mode="eval").body)


def dump_stmt(snippet: str) -> str:
    return ast.dump(_single(ast.parse(textwrap.dedent(snippet)).body, "snippet"))


def _mutate(text: str, mutation: tuple[str, str]) -> str:
    require(text.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
    return text.replace(*mutation)


def check_preserved_outside_change() -> dict[str, Any]:
    got_cand, got_src = differing_names(subject_text("runner/candidate.py"), subject_text("runner/source.py"))
    require(got_cand == {"_t05_observe", HELPER} and got_src == {"_t05_observe"}, "preserved:runner")
    return {"cases": {"runner": "PASS"}, "control_kind": "structural_source", "observed": "PASS"}


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
# CHAIN-HELPER (behavioral, extracted candidate helper + unchanged classifier)
# ---------------------------------------------------------------------------

class SuiteStop(Exception):
    """Named fake for np_suite.SuiteStop (the helper and classifier import it locally)."""


def helper_namespace(runner_text: str) -> dict[str, Any]:
    namespace: dict[str, Any] = {"Any": Any}
    exec_units(runner_text, CLASSIFIER_UNITS + (HELPER,), namespace, "runner")
    return namespace


def call_helper(namespace: dict[str, Any], expectation: str, outcome: Any, client_exc: Any) -> dict[str, Any]:
    with Sandbox(("np_suite",)) as box:
        box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStop
        try:
            return {"label": namespace[HELPER](expectation, outcome, client_exc), "raised": None}
        except BaseException as exc:  # noqa: BLE001
            return {"label": None, "raised": exc}


def call_classifier(namespace: dict[str, Any], expectation: str, outcome: Any) -> dict[str, Any]:
    with Sandbox(("np_suite",)) as box:
        box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStop
        try:
            return {"label": namespace["_t05_classify_client_outcome"](expectation, outcome), "raised": None}
        except BaseException as exc:  # noqa: BLE001
            return {"label": None, "raised": exc}


def client_exception(name: str, module: str = "fake.client") -> BaseException:
    cls = type(name, (Exception,), {"__module__": module})
    try:
        raise cls(SECRET)
    except Exception as exc:  # noqa: BLE001
        return exc


ADMITTED = (
    ("complete_accept", ("response", 200, True, "close_delimited")),
    ("fixed_length_accept", ("response", 200, True, "exact_content_length")),
    ("short_cl_refuse", ("exception", "IncompleteRead", "http.client")),
    ("abrupt_distinct", ("exception", "SSLEOFError", "ssl")),
    ("abrupt_distinct", ("exception", "ConnectionResetError", "builtins")),
)
REFUSED = ("abrupt_distinct", ("exception", "RemoteDisconnected", "http.client"))


def oracle_chain(runner_text: str) -> dict[str, str]:
    cases = {}
    ns = helper_namespace(runner_text)
    ok = True
    for expectation, outcome in ADMITTED:
        direct = call_classifier(ns, expectation, outcome)
        for exc in (None, client_exception(outcome[1])):
            got = call_helper(ns, expectation, outcome, exc)
            ok = ok and got["raised"] is None and got["label"] == direct["label"] and direct["label"] is not None
    require(ok, "chain:admitted label unchanged")
    cases["admitted_label_unchanged"] = "PASS"
    client = client_exception("RemoteDisconnected", "http.client")
    direct = call_classifier(ns, *REFUSED)
    got = call_helper(ns, REFUSED[0], REFUSED[1], client)
    stop = got["raised"]
    guard = SuiteStop("stub guard")
    # A fresh namespace: the extracted helper resolves the classifier through its own
    # __globals__, so a stub must replace the name in the helper's namespace itself.
    stub_ns = helper_namespace(runner_text)

    def stub_classifier(expectation: str, outcome: Any) -> str:
        raise guard

    stub_ns["_t05_classify_client_outcome"] = stub_classifier
    stub_got = call_helper(stub_ns, REFUSED[0], REFUSED[1], client)
    require(type(stop) is SuiteStop and type(direct["raised"]) is SuiteStop
            and stop.args == direct["raised"].args and stop.__cause__ is client
            and stop.__suppress_context__ is True
            and stub_got["raised"] is guard and guard.__cause__ is client, "chain:refused same guard and cause")
    cases["refused_same_guard_and_cause"] = "PASS"
    got = call_helper(ns, REFUSED[0], REFUSED[1], None)
    none_stop = got["raised"]
    require(type(none_stop) is SuiteStop and none_stop.__cause__ is None and none_stop.__suppress_context__ is False
            and none_stop.__context__ is None and none_stop.args == direct["raised"].args, "chain:none fallback")
    cases["none_fallback"] = "PASS"
    unexpected = RuntimeError("unexpected classifier fault")

    def broken_classifier(expectation: str, outcome: Any) -> str:
        raise unexpected

    broken_ns = helper_namespace(runner_text)
    broken_ns["_t05_classify_client_outcome"] = broken_classifier
    got = call_helper(broken_ns, REFUSED[0], REFUSED[1], client_exception("SSLEOFError", "ssl"))
    require(got["raised"] is unexpected and unexpected.__cause__ is None, "chain:unexpected exception identity")
    cases["unexpected_exception_identity"] = "PASS"
    client = client_exception("IncompleteRead", "http.client")
    before = (client.__cause__, client.__context__, client.__suppress_context__, client.__traceback__, client.args)
    call_helper(ns, REFUSED[0], ("exception", "IncompleteRead", "http.client"), client)
    after = (client.__cause__, client.__context__, client.__suppress_context__, client.__traceback__, client.args)
    require(before[0] is after[0] and before[1] is after[1] and before[2] == after[2] and before[3] is after[3]
            and before[4] == after[4], "chain:client exception not mutated")
    cases["client_exception_not_mutated"] = "PASS"
    return cases


def check_chain() -> dict[str, Any]:
    return {"cases": oracle_chain(subject_text("runner/candidate.py")), "control_kind": "extracted_behavior_fake",
            "observed": "PASS"}


# ---------------------------------------------------------------------------
# OBSERVE-WIRING (structural)
# ---------------------------------------------------------------------------

def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [c for c in ast.walk(node) if isinstance(c, ast.Call) and (
        (isinstance(c.func, ast.Name) and c.func.id == name)
        or (isinstance(c.func, ast.Attribute) and c.func.attr == name))]


def oracle_wiring(runner_text: str) -> dict[str, str]:
    cases = {}
    fn = unit_node(runner_text, "_t05_observe")
    peer_try_idx = _single([i for i, s in enumerate(fn.body) if isinstance(s, ast.Try) and _calls(s, "start_background")],
                           "peer try")
    init = [i for i, s in enumerate(fn.body) if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
            and s.target.id == "client_exc" and isinstance(s.value, ast.Constant) and s.value.value is None]
    require(len(init) == 1 and init[0] < peer_try_idx, "wiring:client exc init none")
    cases["client_exc_init_none"] = "PASS"
    stores = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "client_exc" and isinstance(n.ctx, ast.Store)]
    inner = _single([t for t in ast.walk(fn.body[peer_try_idx]) if isinstance(t, ast.Try) and _calls(t, "request")
                     and t is not fn.body[peer_try_idx]], "client request try")
    handler = _single(inner.handlers, "client handler")
    require(len(stores) == 2 and handler.name == "exc" and ast.dump(handler.type) == dump_expr("Exception")
            and ast.dump(handler.body[0]) == dump_stmt("client_exc = exc")
            and ast.dump(handler.body[1]) == dump_stmt(
                'outcome = ("exception", type(exc).__name__, type(exc).__module__)'), "wiring:capture in client handler")
    cases["capture_in_client_handler_only"] = "PASS"
    retire_if = _single([i for i, s in enumerate(fn.body) if isinstance(s, ast.If) and "worker_error_kind" in ast.dump(s.test)],
                        "retirement check")
    inventory_if = _single([i for i, s in enumerate(fn.body) if isinstance(s, ast.If)
                            and "connection_count_admitted" in ast.dump(s.test)], "inventory check")
    chain_calls = _calls(fn, HELPER)
    top = [i for i, s in enumerate(fn.body) if ast.dump(s) == dump_stmt(
        "label = _t05_classify_or_chain(expectation, outcome, client_exc)")]
    require(len(chain_calls) == 1 and len(top) == 1 and peer_try_idx < retire_if < inventory_if < top[0],
            "wiring:chain after retirement")
    cases["chain_after_retirement_and_inventory"] = "PASS"
    module = ast.parse(runner_text)
    all_helper_calls = _calls(module, HELPER)
    require(not _calls(fn, "_t05_classify_client_outcome") and len(all_helper_calls) == 1,
            "wiring:classifier call replaced once")
    cases["classifier_call_replaced_once"] = "PASS"
    return cases


def check_wiring() -> dict[str, Any]:
    return {"cases": oracle_wiring(subject_text("runner/candidate.py")), "control_kind": "structural_source",
            "observed": "PASS"}


# ---------------------------------------------------------------------------
# STOP-PRODUCER-AND-VALIDATOR (behavioral, actual stop_payload + host validator)
# ---------------------------------------------------------------------------

class OwnedRoot:
    """Temporary sandboxed owned root: SHA256SUMS pins one fake owned module that raises."""

    def __enter__(self) -> "OwnedRoot":
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "fixture").mkdir()
        owned = self.root / OWNED_REL
        owned.write_bytes(FAKE_OWNED.encode("utf-8"))
        self.manifest = self.root / "SHA256SUMS.txt"
        self.manifest.write_text(f"{sha256_bytes(owned.read_bytes())}  {OWNED_REL}\n")
        self.module: dict[str, Any] = {}
        exec(compile(FAKE_OWNED, str(owned), "exec"), self.module)
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        self._tmp.cleanup()
        return False


def capture(fn: Callable[..., Any], *args: Any) -> BaseException:
    try:
        fn(*args)
    except BaseException as exc:  # noqa: BLE001
        return exc
    raise WitnessFailure("fake owned raise did not raise")


def named(name: str) -> type:
    return type(name, (Exception,), {})


def producer(runner_text: str, root: Path) -> Callable[[BaseException], dict[str, Any]]:
    namespace: dict[str, Any] = {"ROOT": root, "hashlib": hashlib, "json": json, "Path": Path}
    exec_units(runner_text, ("stop_payload",), namespace, "runner")
    return namespace["stop_payload"]


def validator(owned_root: OwnedRoot) -> Callable[[bytes], list[tuple[str, Any]]]:
    text = subject_text("fixture/docker_transport.py")
    namespace: dict[str, Any] = {"hashlib": hashlib, "json": json, "re": re, "Path": Path}
    exec_units(text, ("digest",), namespace, "docker_transport")
    exec_units(text, ("_record_runner_stop",), namespace, "docker_transport", class_name="DockerOps")

    def run(stderr: bytes) -> list[tuple[str, Any]]:
        records: list[tuple[str, Any]] = []
        fake_self = types.SimpleNamespace(
            ids={"runner": RUNNER_ID}, _id=lambda value: None,
            c={"source_directory": str(owned_root.root), "manifest": str(owned_root.manifest)},
            record=lambda event, data: records.append((event, data)))
        namespace["_record_runner_stop"](fake_self, ["start", "--attach", RUNNER_ID], stderr, 125)
        return records

    return run


def chained_stop(runner_text: str, client: BaseException) -> BaseException:
    ns = helper_namespace(runner_text)
    got = call_helper(ns, REFUSED[0], ("exception", type(client).__name__, "fake.client"), client)
    require(type(got["raised"]) is SuiteStop, "producer:chain setup")
    return got["raised"]


def line_of(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")


def oracle_producer(runner_text: str) -> dict[str, str]:
    cases = {}
    with OwnedRoot() as owned:
        produce, validate = producer(runner_text, owned.root), validator(owned)
        m = owned.module
        client = capture(m["raise_plain"], named("IncompleteRead"), SECRET)
        stop = chained_stop(runner_text, client)
        payload = produce(stop)
        records = validate(line_of(payload))
        require(SECRET not in line_of(payload).decode("utf-8") and SECRET not in repr(records)
                and records and records[0][0] == "runner_stop", "producer:secret markers absent")
        cases["secret_markers_absent"] = "PASS"
        diag = payload.get("diagnostic") or {}
        entries = diag.get("exceptions") or []
        require(payload.get("kind") == "SuiteStop" and [e.get("kind") for e in entries] == ["SuiteStop", "IncompleteRead"]
                and entries[1].get("frames") == [{"path": OWNED_REL, "line": 2}]
                and records[0][1].get("diagnostic", {}).get("exceptions") == entries, "producer:chain exact")
        cases["chain_exact_kinds_and_owned_frames"] = "PASS"
        require(entries[0].get("frames") == [] and diag.get("truncated") is True, "producer:non owned frames dropped")
        cases["non_owned_frames_dropped"] = "PASS"
        client = capture(m["raise_cleanup"], named("CoveringRootOutcomeUnknown"), named("SSLEOFError"), SECRET)
        payload = produce(chained_stop(runner_text, client))
        entries = (payload.get("diagnostic") or {}).get("exceptions") or []
        records = validate(line_of(payload))
        require([e.get("kind") for e in entries] == ["SuiteStop", "CoveringRootOutcomeUnknown", "SSLEOFError"]
                and records[0][0] == "runner_stop", "producer:cleanup unknown preserved")
        cases["cleanup_unknown_preserved"] = "PASS"
        client = capture(m["raise_suppressed"], named("RemoteDisconnected"), named("SSLEOFError"), SECRET)
        payload = produce(chained_stop(runner_text, client))
        entries = (payload.get("diagnostic") or {}).get("exceptions") or []
        require(client.__cause__ is None and client.__suppress_context__ is True
                and [e.get("kind") for e in entries] == ["SuiteStop", "RemoteDisconnected", "SSLEOFError"],
                "producer:suppressed context followed")
        cases["suppressed_context_followed"] = "PASS"
        client = capture(m["raise_chain4"], (named("Alpha"), named("Beta"), named("Gamma"), named("Delta")), SECRET)
        long_payload = produce(chained_stop(runner_text, client))
        deep = capture(m["raise_deep"], named("Deep"), SECRET, 12)
        deep_payload = produce(chained_stop(runner_text, deep))
        long_entries = (long_payload.get("diagnostic") or {}).get("exceptions") or []
        deep_entries = (deep_payload.get("diagnostic") or {}).get("exceptions") or []
        require([e.get("kind") for e in long_entries] == ["SuiteStop", "Alpha", "Beta"]
                and long_payload["diagnostic"]["truncated"] is True
                and len(deep_entries) == 2 and len(deep_entries[1]["frames"]) == 8
                and deep_payload["diagnostic"]["truncated"] is True
                and len(line_of(long_payload)) <= 4096 and len(line_of(deep_payload)) <= 4096
                and validate(line_of(long_payload))[0][0] == "runner_stop"
                and validate(line_of(deep_payload))[0][0] == "runner_stop", "producer:overflow truncation")
        cases["overflow_truncation_and_bounds"] = "PASS"
        owned.manifest.unlink()
        fallback = produce(chained_stop(runner_text, capture(m["raise_plain"], named("IncompleteRead"), SECRET)))
        records = validate(line_of(fallback))
        require(fallback == {"status": "STOP", "kind": "SuiteStop"}
                and records and records[0][0] in ("runner_stop", "runner_stop_diagnostic_refused"),
                "producer:diagnostic fallback")
        cases["diagnostic_fallback"] = "PASS"
    return cases


def check_producer() -> dict[str, Any]:
    return {"cases": oracle_producer(subject_text("runner/candidate.py")),
            "semantics_note": "the unchanged producer follows __cause__ else __context__, so a suppressed context is "
                              "still exported as a kind/location entry; this is the existing producer behavior",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


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
    src = json.loads(subject_text("config/source-runner-config.json"))
    require(cfg.get("case_ids") == T05_IDS and cfg.get("expected_unknown_cases") == [] and cfg.get("launch_ready") is False
            and src.get("launch_ready") is True
            and {k: v for k, v in cfg.items() if k != "launch_ready"} == {k: v for k, v in src.items() if k != "launch_ready"},
            "batch:runner config")
    cases["runner_config"] = "PASS"
    raw = subject_text("config/candidate-launch-config.json")
    launch, src_launch = json.loads(raw), json.loads(subject_text("config/source-launch-config.json"))
    require(launch.get("launch_ready") is False and launch.get("candidate_launch_ready_staged") is False
            and launch.get("human_launch_authorized") is False and launch.get("case_ids") == T05_IDS
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and src_launch.get("manifest_sha256") == SUBJECT_PINS["manifest/source.txt"]
            and all(OWN_ROOT in str(launch.get(k)) for k in ("docker_ops_config_path", "receipt_directory"))
            and not any(root in raw for root in FOREIGN_ROOTS) and set(launch) == set(src_launch)
            and all(launch[k] == src_launch[k] for k in src_launch if k not in LAUNCH_CHANGED_KEYS),
            "batch:launch config")
    cases["launch_config"] = "PASS"
    s_rows, c_rows = rows(subject_text("manifest/source.txt")), rows(subject_text("manifest/candidate.txt"))
    changed = {rel for rel in s_rows if s_rows[rel] != c_rows.get(rel)}
    require(set(s_rows) == set(c_rows) and changed == set(CHANGED_PAYLOAD_ROWS)
            and all(c_rows[rel] == SUBJECT_PINS[subject] for rel, subject in CHANGED_PAYLOAD_ROWS.items())
            and c_rows.get("fixture/docker_transport.py") == SUBJECT_PINS["fixture/docker_transport.py"],
            "batch:payload manifest delta")
    cases["payload_delta_exact"] = "PASS"
    return {"cases": cases, "control_kind": "config_data", "observed": "PASS"}


def check_prior_applicability() -> dict[str, Any]:
    cases = {}
    src, cand = subject_text("runner/source.py"), subject_text("runner/candidate.py")
    units = CLASSIFIER_UNITS + ("T05_SCRIPTED_WIRE_FRAMINGS", "_t05_scripted_wire_framing", "_t05_response_outcome",
                                "_run_np_t05_orderly_close", "_run_np_t05_abrupt_truncation", "stop_payload",
                                "_make_implemented_case", "IMPLEMENTED_CASE_IDS")
    require(all(unit_text(src, n) == unit_text(cand, n) for n in units), "applicability:t05 units")
    cases["t05_units_identical_except_observe"] = "PASS"
    s_rows, c_rows = rows(subject_text("manifest/source.txt")), rows(subject_text("manifest/candidate.txt"))
    require(all(s_rows.get(rel) == c_rows.get(rel) for rel in (
        "fixture/np_provider_peer.py", "fixture/np_provider_transcript.py", "fixture/np_suite.py",
        "fixture/np_integrated_runner.py", "fixture/docker_transport.py")), "applicability:peer transcript suite")
    cases["peer_transcript_suite_unchanged"] = "PASS"
    return {"cases": cases, "not_transferred": [
        "T05 fixture fake v2 PASS 14/74 (C4771F53): its finite properties apply to the unchanged T05 units listed here; "
        "its _t05_observe wiring checks do not transfer to the changed _t05_observe, re-checked structurally here.",
        "No native T05 class or EOF behavior is established; the failed run's client outcome remains unretained."],
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
    "cause_dropped": "behavioral",
    "wrong_cause": "behavioral",
    "none_fallback_chained": "behavioral",
    "producer_exports_message": "behavioral",
    "chain_before_retirement": "structural",
    "capture_dropped": "structural",
}


def check_mutants() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    mutants = {
        "cause_dropped": (lambda: oracle_chain(_mutate(runner, M_CAUSE_DROPPED)), "chain:refused same guard and cause"),
        "wrong_cause": (lambda: oracle_chain(_mutate(runner, M_WRONG_CAUSE)), "chain:refused same guard and cause"),
        "none_fallback_chained": (lambda: oracle_chain(_mutate(runner, M_NONE_CHAINED)), "chain:none fallback"),
        "producer_exports_message": (lambda: oracle_producer(_mutate(runner, M_EXPORT_MESSAGE)),
                                     "producer:secret markers absent"),
        "chain_before_retirement": (lambda: oracle_wiring(_mutate(runner, M_CHAIN_BEFORE_RETIRE)),
                                    "wiring:chain after retirement"),
        "capture_dropped": (lambda: oracle_wiring(_mutate(runner, M_CAPTURE_DROPPED)), "wiring:capture in client handler"),
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
    require(expected.get("kind") == "native-t05-client-cause-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "CHAIN-HELPER": check_chain,
        "OBSERVE-WIRING": check_wiring,
        "STOP-PRODUCER-AND-VALIDATOR": check_producer,
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
