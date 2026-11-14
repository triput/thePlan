#!/usr/bin/env python3
"""HELD fake-only checker for the native T05 fixture preparation.

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned): source = frozen MS-merge NONEXPIRED root roles, candidate =
scheduler-native-provider-t05-prep-matt-v3 roles (runner 4, suite 5, peer 7,
transcript 8), their unified diffs, role 10 np_auth_seed (unchanged; needed to load
the transcript module), runner/launch configs, both payload manifests, and the
unchanged application subjects covering_http_transport/policy/joined_https.

Execution surfaces (all fake): whole stdlib-only fixture modules np_auth_seed,
np_provider_transcript and np_suite in an exact sys.modules sandbox; extracted peer
serializer _http_response_bytes (source and candidate); extracted runner classifier
and scripted-wire framing helpers; the whole actual covering policy/transport modules
in a sandbox with fake app/httpx imports and an injected byte-buffer transport,
through the ACTUAL host http.client parser and ACTUAL json.loads behind a delegating
spy. Importing http.client transitively loads socket and ssl; no socket, SSL context
or TLS connection is constructed.

Client model (v3, Dex B1): by default the fake httpx.Response is
AutoLengthHttpxResponse, which represents the one relevant httpx 0.28.1 adaptation:
when production rebuilds the API response with non-empty bytes content and no
Content-Length header, Content-Length: len(content) is supplied. Finite scope: it does
not model httpx header case-insensitivity, multi-valued headers, decoding, streaming
or any other httpx behavior.

Proof scope: fixture serializer/transcript/suite-mapping/classifier/wiring source
behavior and the host-parser completeness-versus-decoding distinction on the exact
serializer bytes. NOT proved: native TLS close_notify/EOF behavior, the native client
exception classes, peer retirement natively, or any T05 requirement beyond these
finite fixture properties.
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
PACKET_NAME = "scheduler-native-t05-fake-prep-matt-v3"

SUBJECT_PINS = {
    "peer/source.py": "17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039",
    "peer/candidate.py": "BFB271D770D08BC161E9613564ECA799B7E28884D8211E10228F5973A4A271BF",
    "transcript/source.py": "0AA3BC093711B7EEBADD1F23A80BF86F2B5AEAB4C1224014537BB051FDDCE52E",
    "transcript/candidate.py": "562F61CDB9DEF3F35A1693E3C9CC13EB63D9F0535F9A0D3C190BF275E78751BF",
    "runner/source.py": "F7CFD3E6BA0107B3482766C3A8FA505C5BADD287DF843FACAEA2E79CFFE5385C",
    "runner/candidate.py": "1D70164C8EFD7D1CD0A9ED59F23D9F8A4ED9F68B806364B366E2E707259AAA7E",
    "suite/source.py": "46C9443D13E4CA526DEE4BEF5747D65AA0549CA0FFA963A8F8EB44595485370D",
    "suite/candidate.py": "9AED74EE4F00C5F88518A1B246D7B03D5E82C05DDF3596958D5483730C376792",
    "fixture/np_auth_seed.py": "2ADFA3ADCFDA8DB4D9D32EDFC9950AF354CE29ADFA1B5A8162FD5182DC22ED05",
    "diff/np_runner_entry.py.diff": "F646720F0D2A7271A8699FB5E44A22BE1F3B712F1AC648EDE5C78EB1F34CCC92",
    "diff/np_provider_peer.py.diff": "12A40E631007C3E8435D1BBB9741243A2CD8ABA841D84C79722FEF1B2D4A16A4",
    "diff/np_provider_transcript.py.diff": "97DF0CD7E57FFB65949BEFA44D962C70D4E7C3CC5F35C6538D9BE862ABBFD088",
    "diff/np_suite.py.diff": "A1CD13789A8EDFA4647088060E59BF9E7A6480B8D0DA35F49D4FF625B069C9A6",
    "diff/runner-config.json.diff": "AA0586060552193ED29DA1647F194B68DC985017F228D41F80402B28792CE72D",
    "config/source-runner-config.json": "9411AC387CCB735751E3D22C580EEFB2F9ADEE92F2E3725E1E36B7EACE7BE929",
    "config/candidate-runner-config.json": "96782CB425239BC6F121949DABE16B4B53528E249BE625DD25A9811DA7D07E71",
    "config/candidate-launch-config.json": "FB7968294F521E6155C70CF7EB2588FCF28791E58F3DCDA88C2D07CD616DCD43",
    "manifest/source.txt": "14FA30AD16E719150CA81F07274FF6AC8D3A2D80A065296D9FDB2830E2B00B46",
    "manifest/candidate.txt": "D03EA0D671DF61AB3E66B2E3B96D34B72AC9BDAF6282676A8A1328DEF853B0C5",
    "app/covering_http_transport.py": "29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368",
    "app/covering_transport_policy.py": "5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88",
    "app/covering_joined_https.py": "760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427",
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
    "SERIALIZER-DEFAULT-REGRESSION",
    "ORDERLY-POSITIVE-SERIALIZATION",
    "INVALID-MODE-REFUSALS",
    "CLIENT-COMPLETENESS-VS-DECODE",
    "OUTCOME-CLASSIFIER",
    "SUITE-ORDERLY-MAPPING",
    "RUNNER-WIRING",
    "BATCH-CONFIG",
    "PRIOR-FAKE-APPLICABILITY",
    "ACTUAL-SOURCE-MUTANTS",
)

T05_IDS = ["NP-T05-ORDERLY-CLOSE", "NP-T05-ABRUPT-TRUNCATION"]
ORDERLY_ID = "NP-T05-ORDERLY-CLOSE"
CHANGED_SCRIPT = "T05-ORDERLY-CLOSE-DELIMITED-COMPLETE"
FIXED_SCRIPT = "T05-ORDERLY-FIXED-LENGTH-COMPLETE"
SHORT_SCRIPT = "T05-ORDERLY-SHORT-CL-VALID-JSON"
ABRUPT_SCRIPT = "T05-ABRUPT-TRUNCATION"
EXPECTED_CLOSE_DELIMITED_WIRE = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                                 b"Connection: close\r\n\r\n{}")
EXPECTED_FIXED_LENGTH_WIRE = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n"
                              b"Connection: close\r\n\r\n{}")
VALID_COMPLETE_CL = "T05-VALID-COMPLETE-CONTENT-LENGTH"
SHORT_VALID_JSON = "T05-SHORT-LENGTH-VALID-JSON"
ACCEPTED = "ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY"
REFUSED = "REFUSED_AFTER_ORDERLY_CLOSE_NOTIFY"
# (oracle name, planning_ids, expected, stop_on_mismatch), in declaration order.
EXPECTED_ORDERLY_ORACLES = (
    ("orderly_close_delimited_complete_accepted", (), ACCEPTED, True),
    ("orderly_fixed_length_complete_accepted", (VALID_COMPLETE_CL,), ACCEPTED, True),
    ("orderly_short_cl_valid_json_prefix_refused", (SHORT_VALID_JSON,), REFUSED, True),
)
# (script factory, expectation) for the three sequential ORDERLY observations, in order.
EXPECTED_ORDERLY_OBSERVATIONS = (
    ("orderly_close_delimited_complete_script", "complete_accept"),
    ("orderly_fixed_length_complete_script", "fixed_length_accept"),
    ("orderly_short_cl_valid_json_refuse_script", "short_cl_refuse"),
)
INVENTORY_IDS = ("cal-ms-default", "cal-np-other")
STEP_FIELDS = ("direction", "method", "path", "status", "headers", "body_template", "close_mode", "note")
OWN_ROOT = "scheduler-native-provider-t05-prep-matt-v3"
FOREIGN_ROOTS = ("ms-merge-nonexpired-prep-matt-v1", "ms-merge-refresh-prep-matt-v1",
                 "peer-close-prep-matt-v1", "peer-close-launch-dex-v1", "scheduler-ms-refresh-prep-matt-v1",
                 "t05-prep-matt-v1", "t05-prep-matt-v2")
CHANGED_PAYLOAD_ROWS = {
    "fixture/np_runner_entry.py": "runner/candidate.py",
    "fixture/np_provider_peer.py": "peer/candidate.py",
    "fixture/np_provider_transcript.py": "transcript/candidate.py",
    "fixture/np_suite.py": "suite/candidate.py",
    "runner-config.json": "config/candidate-runner-config.json",
}

# Mutation anchors (statically read; unique within the text each mutation edits).
M_DELIM_CONN = ('        delimited_lines.append("Connection: close")\n',
                '        delimited_lines.append("Content-Length: 2")\n'
                '        delimited_lines.append("Connection: close")\n')
M_TE_REFUSAL = ('    if any(name.lower() == "transfer-encoding" for name, _ in step.headers):\n'
                '        raise PeerLifecycleError("fixture serializer does not emit Transfer-Encoding")\n', "")
M_AUTO_CONN = ('    lines.append("Connection: close")\n', '    lines.append("Connection: keep-alive")\n')
M_ABRUPT_SET = ('T05_ABRUPT_CLIENT_CLASSES = frozenset({("SSLEOFError", "ssl"), ("ConnectionResetError", "builtins")})',
                'T05_ABRUPT_CLIENT_CLASSES = frozenset({("SSLEOFError", "ssl"), ("ConnectionResetError", "builtins"), '
                '("IncompleteRead", "http.client")})')
M_FACTORY = ("    http = CoveringHTTP(counter=counter, routes=routes)\n",
             "    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=JoinedTLS)\n")
M_RETIRE = ("        retirement = peer.retire_owned(join_seconds=5.0)\n",
            '        retirement = {"joined": True, "worker_error_kind": None}\n')
# Scripted-wire framing bypassed: every response is called close-delimited.
M_WIRE_PREDICATE = ("    scripted_wire_framing = _t05_scripted_wire_framing(scripted_wire, expected_body)\n",
                    '    scripted_wire_framing = "close_delimited"\n')
# Framing conflation: an exact fixed-length wire is reported as close-delimited.
M_FRAMING_CONFLATION = ('        return "exact_content_length"\n', '        return "close_delimited"\n')
# Mapping swap (two anchors applied in sequence to the suite candidate).
M_MAP_SWAP_A = ('                name="orderly_close_delimited_complete_accepted",\n'
                "                planning_ids=(),\n",
                '                name="orderly_close_delimited_complete_accepted",\n'
                '                planning_ids=("T05-VALID-COMPLETE-CONTENT-LENGTH",),\n')
M_MAP_SWAP_B = ('                name="orderly_fixed_length_complete_accepted",\n'
                '                planning_ids=("T05-VALID-COMPLETE-CONTENT-LENGTH",),\n',
                '                name="orderly_fixed_length_complete_accepted",\n'
                "                planning_ids=(),\n")
# Fixed-length observation run under the close-delimited expectation.
M_FIXED_EXPECTATION = ('orderly_fixed_length_complete_script(), "fixed_length_accept")',
                       'orderly_fixed_length_complete_script(), "complete_accept")')


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
# Literal unified-diff re-derivation (exact positions; pure text)
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
        "peer": ("peer/source.py", "peer/candidate.py", "diff/np_provider_peer.py.diff",
                 "payload/fixture/np_provider_peer.py", 1),
        "transcript": ("transcript/source.py", "transcript/candidate.py", "diff/np_provider_transcript.py.diff",
                       "payload/fixture/np_provider_transcript.py", 5),
        "suite": ("suite/source.py", "suite/candidate.py", "diff/np_suite.py.diff", "payload/fixture/np_suite.py", 3),
        "runner_config": ("config/source-runner-config.json", "config/candidate-runner-config.json",
                          "diff/runner-config.json.diff", "payload/runner-config.json", 1),
    }.items():
        derived, files, hunks = apply_unified(subject_text(source), subject_text(diff))
        require(files == [f"a/{label}", f"b/{label}"] and hunks == hunks_expected
                and derived == subject_text(candidate), f"diff rederivation:{case}")
        cases[case] = "PASS"
    return {"cases": cases, "control_kind": "literal_text", "observed": "PASS"}


# ---------------------------------------------------------------------------
# AST helpers (locate segments only; nothing here compiles subject text)
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


def check_preserved_outside_change() -> dict[str, Any]:
    expected = {
        "runner": ({"IMPLEMENTED_CASE_IDS", "T05_SHORT_CL_REFUSAL_CLASS", "T05_ABRUPT_CLIENT_CLASSES",
                    "T05_SCRIPTED_WIRE_FRAMINGS", "_t05_classify_client_outcome", "_t05_scripted_wire_framing",
                    "_t05_response_outcome", "_t05_observe", "_run_np_t05_orderly_close",
                    "_run_np_t05_abrupt_truncation", "_make_implemented_case"},
                   {"IMPLEMENTED_CASE_IDS", "_make_implemented_case"}),
        "peer": ({"RESPONSE_FRAMING_MODES", "_http_response_bytes"}, {"_http_response_bytes"}),
        "transcript": ({"ResponseFraming", "ExchangeStep", "orderly_close_delimited_complete_script",
                        "orderly_fixed_length_complete_script", "finite_script_catalog"},
                       {"ExchangeStep", "orderly_close_delimited_complete_script", "finite_script_catalog"}),
        "suite": ({"NATIVE_CASES", "CASE_IMPLEMENTATION_NOTES"}, {"NATIVE_CASES", "CASE_IMPLEMENTATION_NOTES"}),
    }
    cases = {}
    for role, (cand_only, src_only) in expected.items():
        got_cand, got_src = differing_names(subject_text(f"{role}/candidate.py"), subject_text(f"{role}/source.py"))
        require(got_cand == cand_only and got_src == src_only, f"preserved:{role}")
        cases[role] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Sandbox shared by fixture and app module loading
# ---------------------------------------------------------------------------

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

    def load(self, name: str, source: str, filename: str) -> types.ModuleType:
        module = self.put(name, types.ModuleType(name))
        exec(compile(source, filename, "exec"), module.__dict__)
        return module

    def __exit__(self, *exc_info: Any) -> bool:
        for name in self.installed:
            sys.modules.pop(name, None)
        return False


FIXTURE_NAMES = ("np_auth_seed", "np_provider_transcript", "np_suite")


def load_inventories(which: str) -> dict[str, list[Any]]:
    """Load seed+transcript (source or candidate) and return the finite script inventories."""
    with Sandbox(FIXTURE_NAMES) as box:
        box.load("np_auth_seed", subject_text("fixture/np_auth_seed.py"), "<subject:np_auth_seed>")
        transcript = box.load("np_provider_transcript", subject_text(f"transcript/{which}.py"),
                              f"<subject:transcript:{which}>")
        result = {
            "catalog_scripts": list(transcript.finite_script_catalog()),
            "ms_nonexpired_inventory": list(transcript.ms_nonexpired_connection_inventory(
                calendar_ids=INVENTORY_IDS, identity_list_calendar_ids=INVENTORY_IDS,
                wire_calendar_ids=INVENTORY_IDS)),
            "ms_refresh_inventory": list(transcript.ms_refresh_connection_inventory(
                identity_list_calendar_ids=INVENTORY_IDS, wire_calendar_ids=INVENTORY_IDS)),
        }
    require(all(name not in sys.modules for name in FIXTURE_NAMES), "fixture sandbox restored")
    return result


_INVENTORIES: dict[str, dict[str, list[Any]]] = {}


def inventories(which: str) -> dict[str, list[Any]]:
    if which not in _INVENTORIES:
        _INVENTORIES[which] = load_inventories(which)
    return _INVENTORIES[which]


def script_by_id(which: str, script_id: str) -> Any:
    return _single([s for s in inventories(which)["catalog_scripts"] if s.script_id == script_id],
                   f"script {script_id}")


def send_step(script: Any) -> Any:
    return _single([s for s in script.steps if s.direction == "send_response"], "send step")


class PeerLifecycleError(RuntimeError):
    pass


def serializer(which: str, mutation: tuple[str, str] | None = None) -> Callable[[Any], bytes]:
    text = subject_text(f"peer/{which}.py")
    namespace: dict[str, Any] = {"PeerLifecycleError": PeerLifecycleError, "Any": Any, "ExchangeStep": object}
    if which == "candidate":
        exec(compile(unit_text(text, "RESPONSE_FRAMING_MODES"), "<extracted:peer:modes>", "exec"), namespace)
    source = unit_text(text, "_http_response_bytes")
    if mutation is not None:
        require(source.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
        source = source.replace(*mutation)
    exec(compile(source, f"<extracted:peer:{which}:_http_response_bytes>", "exec"), namespace)
    return namespace["_http_response_bytes"]


def step_fields(step: Any) -> tuple[Any, ...]:
    return tuple(getattr(step, name) for name in STEP_FIELDS)


# ---------------------------------------------------------------------------
# Serializer oracles
# ---------------------------------------------------------------------------

def oracle_regression(cand_ser: Callable[[Any], bytes]) -> dict[str, str]:
    src_ser = serializer("source")
    cases = {}
    for name in ("catalog_scripts", "ms_nonexpired_inventory", "ms_refresh_inventory"):
        src_scripts, cand_scripts = inventories("source")[name], inventories("candidate")[name]
        src_ids = [s.script_id for s in src_scripts]
        expected_ids = list(src_ids)
        if name == "catalog_scripts":
            require(src_ids.count(CHANGED_SCRIPT) == 1 and FIXED_SCRIPT not in src_ids,
                    f"default regression:{name}:script ids")
            expected_ids.insert(src_ids.index(CHANGED_SCRIPT) + 1, FIXED_SCRIPT)
        require([s.script_id for s in cand_scripts] == expected_ids, f"default regression:{name}:script ids")
        common = [c for c in cand_scripts if c.script_id != FIXED_SCRIPT]
        for src, cand in zip(src_scripts, common):
            if cand.script_id == CHANGED_SCRIPT:
                continue
            require(src.purpose == cand.purpose and len(src.steps) == len(cand.steps),
                    f"default regression:{name}:shape {cand.script_id}")
            for s_step, c_step in zip(src.steps, cand.steps):
                require(step_fields(s_step) == step_fields(c_step) and c_step.framing == "auto",
                        f"default regression:{name}:step {cand.script_id}")
                if c_step.direction == "send_response":
                    require(src_ser(s_step) == cand_ser(c_step), f"default regression:{name}:wire {cand.script_id}")
        cases[name] = "PASS"
    src_catalog = inventories("source")["catalog_scripts"]
    cand_catalog = inventories("candidate")["catalog_scripts"]
    src_ids = {s.script_id for s in src_catalog}
    changed = [c.script_id for s, c in zip(src_catalog, [c for c in cand_catalog if c.script_id != FIXED_SCRIPT])
               if [step_fields(x) for x in s.steps] != [step_fields(y) for y in c.steps]
               or any(y.framing != "auto" for y in c.steps)]
    added = [c.script_id for c in cand_catalog if c.script_id not in src_ids]
    require(changed == [CHANGED_SCRIPT] and added == [FIXED_SCRIPT], "default regression:catalog delta")
    cases["catalog_delta_changed_plus_added"] = "PASS"
    return cases


def oracle_close_delimited(cand_ser: Callable[[Any], bytes]) -> dict[str, str]:
    cases = {}
    step = send_step(script_by_id("candidate", CHANGED_SCRIPT))
    wire = cand_ser(step)
    require(step.framing == "close_delimited" and wire == EXPECTED_CLOSE_DELIMITED_WIRE,
            "close delimited:exact bytes")
    cases["exact_bytes"] = "PASS"
    head = wire.partition(b"\r\n\r\n")[0].lower()
    require(b"content-length" not in head and b"transfer-encoding" not in head, "close delimited:framing headers")
    cases["no_framing_headers"] = "PASS"
    require(b"\r\nContent-Length: 2\r\n" in serializer("source")(step), "close delimited:source appends length")
    cases["source_serializer_would_append_length"] = "PASS"
    fixed_script = script_by_id("candidate", FIXED_SCRIPT)
    fixed = send_step(fixed_script)
    fixed_wire = cand_ser(fixed)
    require(fixed.framing == "auto" and all(s.framing == "auto" for s in fixed_script.steps)
            and fixed_wire == EXPECTED_FIXED_LENGTH_WIRE, "fixed length:exact bytes")
    cases["fixed_length_exact_bytes"] = "PASS"
    require(serializer("source")(fixed) == fixed_wire, "fixed length:source serializer identical")
    cases["fixed_length_source_serializer_identical"] = "PASS"
    return cases


def _refused(ser: Callable[[Any], bytes], step: Any) -> bool:
    try:
        ser(step)
    except PeerLifecycleError:
        return True
    return False


def fake_step(framing: str, headers: tuple[tuple[str, str], ...]) -> Any:
    return types.SimpleNamespace(direction="send_response", status=200, headers=headers, body_template="{}",
                                 framing=framing)


def oracle_invalid(cand_ser: Callable[[Any], bytes]) -> dict[str, str]:
    cases = {}
    for case, step in (
        ("unknown_mode", fake_step("chunked", (("Content-Type", "application/json"),))),
        ("close_delimited_with_content_length", fake_step("close_delimited", (("Content-Length", "2"),))),
        ("auto_with_transfer_encoding", fake_step("auto", (("Transfer-Encoding", "chunked"),))),
        ("close_delimited_with_transfer_encoding", fake_step("close_delimited", (("Transfer-Encoding", "chunked"),))),
    ):
        require(_refused(cand_ser, step), f"invalid mode:{case}")
        cases[case] = "PASS"
    peer = subject_text("peer/candidate.py")
    send = unit_node(peer, "_send_response", "SyntheticProviderPeer")
    require(unit_text(peer, "_send_response", "SyntheticProviderPeer")
            == unit_text(subject_text("peer/source.py"), "_send_response", "SyntheticProviderPeer"),
            "invalid mode:send_response changed")
    serialize_lines = [n.lineno for n in ast.walk(send) if isinstance(n, ast.Assign)
                       and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                       and n.value.func.id == "_http_response_bytes"]
    send_lines = [n.lineno for n in ast.walk(send) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "_send_all"]
    require(len(serialize_lines) == 1 and send_lines and serialize_lines[0] < min(send_lines),
            "invalid mode:refusal precedes send")
    cases["refusal_precedes_send"] = "PASS"
    return cases


# ---------------------------------------------------------------------------
# Host-parser completeness versus decoding on the exact serializer bytes
# ---------------------------------------------------------------------------

APP_NAMES = ("app", "app.services", "app.services.covering_request_budget", "app.services.covering_transport_policy",
             "app.services.covering_joined_https", "app.services.covering_target_transaction", "httpx",
             "app.services.covering_http_transport")
TRANSPORT_FILE = "<subject:covering_http_transport.py>"
URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


class FakeRootOutcomeUnknown(Exception):
    pass


class FakeDeadlineExceeded(Exception):
    pass


class FakeHttpxRequest:
    def __init__(self, method: str, url: str) -> None:
        self.method, self.url = method, url


class FakeHttpxResponse:
    def __init__(self, status: int, *, content: bytes, headers: dict[str, str], request: Any) -> None:
        self.status_code, self.content, self.headers, self.request = status, content, headers, request


class AutoLengthHttpxResponse(FakeHttpxResponse):
    """DEFAULT client model (v3). Represents the one relevant httpx 0.28.1 adaptation:
    httpx.Response(status, content=<non-empty bytes>, headers=...) supplies
    Content-Length: len(content) when the given headers carry none (an explicit one is
    kept). Finite scope: nothing else of httpx is modelled (no case-insensitive header
    mapping, multi-valued headers, decoding or streaming)."""

    def __init__(self, status: int, *, content: bytes, headers: dict[str, str], request: Any) -> None:
        rebuilt = dict(headers)
        if content and not any(str(k).lower() == "content-length" for k in rebuilt):
            rebuilt["Content-Length"] = str(len(content))
        super().__init__(status, content=content, headers=rebuilt, request=request)


class JsonSpy:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.calls: list[bytes] = []
        self.raised: list[BaseException] = []

    def loads(self, data: Any, *args: Any, **kwargs: Any) -> Any:
        self.log.append("json")
        self.calls.append(bytes(data))
        try:
            return json.loads(data, *args, **kwargs)
        except BaseException as exc:  # noqa: BLE001
            self.raised.append(exc)
            raise


class FakeTransport:
    """JoinedTLS open/send/receive/close/sent interface over exact bytes.

    After the bytes, receive returns b"" (modelling an orderly close the client
    reads as EOF) or raises the injected object (modelling a transport error).
    """

    def __init__(self, response: bytes, after: BaseException | None, log: list[str]) -> None:
        self.response, self.after, self.log = response, after, log
        self.offset = 0
        self.opens = self.closes = 0
        self.sent = False

    def open(self) -> "FakeTransport":
        self.opens += 1
        return self

    def send(self, data: bytes) -> None:
        self.sent = True

    def receive(self, maximum: int) -> bytes:
        chunk = self.response[self.offset:self.offset + maximum]
        self.offset += len(chunk)
        if not chunk and self.after is not None:
            raise self.after
        return chunk

    def close(self) -> None:
        self.closes += 1
        self.log.append("transport_close")


def run_scenario(response: bytes, after: BaseException | None = None,
                 response_cls: type = AutoLengthHttpxResponse) -> dict[str, Any]:
    log: list[str] = []
    with Sandbox(APP_NAMES) as box:
        for name in ("app", "app.services"):
            box.put(name, types.ModuleType(name)).__path__ = []
        box.put("app.services.covering_request_budget",
                types.ModuleType("app.services.covering_request_budget")).CoveringDeadlineExceeded = FakeDeadlineExceeded
        policy = box.load("app.services.covering_transport_policy", subject_text("app/covering_transport_policy.py"),
                          "<subject:covering_transport_policy.py>")
        box.put("app.services.covering_joined_https",
                types.ModuleType("app.services.covering_joined_https")).JoinedTLS = type("JoinedTLS", (), {})
        box.put("app.services.covering_target_transaction",
                types.ModuleType("app.services.covering_target_transaction")).CoveringRootOutcomeUnknown = \
            FakeRootOutcomeUnknown
        httpx = box.put("httpx", types.ModuleType("httpx"))
        httpx.Request, httpx.Response = FakeHttpxRequest, response_cls
        module = box.load("app.services.covering_http_transport", subject_text("app/covering_http_transport.py"),
                          TRANSPORT_FILE)
        spy = JsonSpy(log)
        module.json = spy
        real_gate = module._admit_fixed_length_complete
        gate_calls: list[int] = []

        def counted_gate(response_obj: Any) -> None:
            log.append("gate")
            gate_calls.append(1)
            return real_gate(response_obj)

        module._admit_fixed_length_complete = counted_gate
        counter = policy.ProviderCounter(policy.approved_provider_limits(), lambda: 100.0)
        peer = policy.HTTPSPeer(hostname="www.googleapis.com", address="127.0.0.1", port=443, ca_file="/fake/ca.crt")
        transport = FakeTransport(response, after, log)
        client = module.CoveringHTTP(counter=counter, routes=((peer, "/calendar/v3/calendars/", "event"),),
                                     transport_factory=lambda p, remaining: transport)
        escaped: BaseException | None = None
        result: Any = None
        try:
            result = client.request("GET", URL, purpose="event")
        except BaseException as exc:  # noqa: BLE001
            escaped = exc
        refused_type = policy.CoveringTransportRefused
    require(all(name not in sys.modules for name in APP_NAMES), "app sandbox restored")
    return {"escaped": escaped, "result": result, "spy": spy, "gate_calls": len(gate_calls), "log": log,
            "transport": transport, "refused_type": refused_type}


def innermost(exc: BaseException) -> tuple[str, str]:
    tb = exc.__traceback__
    require(tb is not None, "exception without traceback")
    while tb.tb_next is not None:
        tb = tb.tb_next
    return tb.tb_frame.f_code.co_filename, tb.tb_frame.f_code.co_name


def check_client_completeness() -> dict[str, Any]:
    cand_ser = serializer("candidate")
    cases = {}
    cd_wire = cand_ser(send_step(script_by_id("candidate", CHANGED_SCRIPT)))
    cd_head = cd_wire.partition(b"\r\n\r\n")[0].lower()
    run = run_scenario(cd_wire)
    result = run["result"]
    # B1: the rebuilt API response carries the httpx-supplied Content-Length: 2 while
    # the scripted wire itself is close-delimited (no Content-Length, no Transfer-Encoding).
    require(run["escaped"] is None and type(result) is AutoLengthHttpxResponse and result.status_code == 200
            and result.content == b"{}" and result.headers.get("Content-Length") == "2"
            and not any(str(k).lower() == "transfer-encoding" for k in result.headers)
            and b"content-length" not in cd_head and b"transfer-encoding" not in cd_head
            and run["log"] == ["gate", "json", "transport_close"], "client:close delimited accepted")
    cases["close_delimited_accepted"] = "PASS"
    cases["fixed_length_accepted"] = oracle_fixed_length_client(subject_text("runner/candidate.py"))
    short_step = send_step(script_by_id("candidate", SHORT_SCRIPT))
    run = run_scenario(cand_ser(short_step))
    exc = run["escaped"]
    require(type(exc) is http.client.IncompleteRead and exc.expected == 18 and exc.partial == b""
            and innermost(exc) == (TRANSPORT_FILE, "read") and not run["spy"].calls and run["gate_calls"] == 0,
            "client:short length refused before decode")
    cases["short_cl_refused_before_decode"] = "PASS"
    invalid = types.SimpleNamespace(direction="send_response", status=200, headers=(("Content-Type", "application/json"),),
                                    body_template="{", framing="close_delimited")
    run = run_scenario(cand_ser(invalid))
    exc = run["escaped"]
    require(type(exc) is json.JSONDecodeError and run["spy"].raised == [exc] and run["spy"].calls == [b"{"]
            and run["gate_calls"] == 1 and not isinstance(exc, (http.client.HTTPException, run["refused_type"])),
            "client:complete invalid json reaches decode")
    cases["complete_invalid_json_decoded"] = "PASS"
    injected = type("SSLEOFError", (OSError,), {})("injected-transport-eof")
    run = run_scenario(cand_ser(send_step(script_by_id("candidate", ABRUPT_SCRIPT))), after=injected)
    require(run["escaped"] is injected and not run["spy"].calls and run["gate_calls"] == 0
            and run["transport"].closes == 1, "client:transport error propagates unchanged")
    cases["transport_error_propagates_unchanged"] = "PASS"
    cases["rebuilt_content_length_trap"] = oracle_rebuilt_trap(subject_text("runner/candidate.py"))
    return {"cases": cases, "eof_model": "fake b'' after bytes models a client-observed orderly EOF; not native TLS proof",
            "client_model": "AutoLengthHttpxResponse by default: httpx 0.28.1 supplies Content-Length for "
                            "non-empty rebuilt bytes content; nothing else of httpx modelled",
            "control_kind": "actual_source_host_parser", "observed": "PASS"}


def response_outcome_fn(runner_text: str) -> Callable[..., tuple[Any, ...]]:
    namespace: dict[str, Any] = {"Any": Any}
    for name in ("_t05_scripted_wire_framing", "_t05_response_outcome"):
        exec(compile(unit_text(runner_text, name), f"<extracted:runner:{name}>", "exec"), namespace)
    return namespace["_t05_response_outcome"]


def oracle_fixed_length_client(runner_text: str) -> str:
    """The exact fixed-length {} (Content-Length: 2) goes through the actual transport and
    host parser, classifies as exact_content_length from the scripted wire, and is
    accepted only under fixed_length_accept (it STOPs under complete_accept)."""
    outcome_fn = response_outcome_fn(runner_text)
    call = classifier(runner_text)
    wire = serializer("candidate")(send_step(script_by_id("candidate", FIXED_SCRIPT)))
    run = run_scenario(wire)
    result = run["result"]
    require(run["escaped"] is None and type(result) is AutoLengthHttpxResponse and result.status_code == 200
            and result.content == b"{}" and result.headers.get("Content-Length") == "2"
            and run["log"] == ["gate", "json", "transport_close"], "client:fixed length transport")
    outcome = outcome_fn(result.status_code, result.content, b"{}", wire)
    require(outcome == ("response", 200, True, "exact_content_length")
            and call("fixed_length_accept", outcome) == ACCEPTED
            and _stops(call, "complete_accept", outcome), "client:fixed length accepted")
    return "PASS"


def oracle_rebuilt_trap(runner_text: str) -> str:
    """A correct close-delimited result whose rebuilt API response gained Content-Length
    must still be accepted; a wire that really adds framing must still be refused."""
    outcome_fn = response_outcome_fn(runner_text)
    call = classifier(runner_text)
    cand_ser = serializer("candidate")
    wire = cand_ser(send_step(script_by_id("candidate", CHANGED_SCRIPT)))
    run = run_scenario(wire)
    result = run["result"]
    require(run["escaped"] is None and type(result) is AutoLengthHttpxResponse
            and result.headers.get("Content-Length") == "2", "client:rebuilt trap reproduced")
    outcome = outcome_fn(result.status_code, result.content, b"{}", wire)
    require(outcome == ("response", 200, True, "close_delimited")
            and call("complete_accept", outcome) == ACCEPTED
            and _stops(call, "fixed_length_accept", outcome), "client:rebuilt trap positive")
    cl_step = types.SimpleNamespace(direction="send_response", status=200,
                                    headers=(("Content-Type", "application/json"),), body_template="{}", framing="auto")
    cl_wire = cand_ser(cl_step)
    negative = outcome_fn(200, b"{}", b"{}", cl_wire)
    require(b"\r\nContent-Length: 2\r\n" in cl_wire and negative == ("response", 200, True, "exact_content_length")
            and _stops(call, "complete_accept", negative), "client:rebuilt trap negative")
    return "PASS"


# ---------------------------------------------------------------------------
# Runner classifier and wiring
# ---------------------------------------------------------------------------

class SuiteStop(Exception):
    pass


def classifier(runner_text: str) -> Callable[[str, Any], str]:
    namespace: dict[str, Any] = {"Any": Any}
    for name in ("T05_SHORT_CL_REFUSAL_CLASS", "T05_ABRUPT_CLIENT_CLASSES", "_t05_classify_client_outcome"):
        exec(compile(unit_text(runner_text, name), f"<extracted:runner:{name}>", "exec"), namespace)
    function = namespace["_t05_classify_client_outcome"]

    def call(expectation: str, outcome: Any) -> str:
        with Sandbox(FIXTURE_NAMES) as box:
            box.put("np_suite", types.ModuleType("np_suite")).SuiteStop = SuiteStop
            return function(expectation, outcome)

    return call


def _stops(call: Callable[[str, Any], str], expectation: str, outcome: Any) -> bool:
    try:
        call(expectation, outcome)
    except SuiteStop:
        return True
    return False


def oracle_classifier(runner_text: str) -> dict[str, str]:
    call = classifier(runner_text)
    cases = {}
    require(call("complete_accept", ("response", 200, True, "close_delimited")) == ACCEPTED,
            "classifier:complete_accept_exact")
    cases["complete_accept_exact"] = "PASS"
    require(all(_stops(call, "complete_accept", o) for o in (
        ("response", 200, False, "close_delimited"), ("response", 200, True, "exact_content_length"),
        ("response", 200, True, "other"), ("response", 201, True, "close_delimited"),
        ("response", 200, True, True), ("exception", "IncompleteRead", "http.client"))),
        "classifier:complete_accept_mismatch_stops")
    cases["complete_accept_mismatch_stops"] = "PASS"
    require(call("fixed_length_accept", ("response", 200, True, "exact_content_length")) == ACCEPTED,
            "classifier:fixed_accept_exact")
    cases["fixed_accept_exact"] = "PASS"
    require(all(_stops(call, "fixed_length_accept", o) for o in (
        ("response", 200, True, "close_delimited"), ("response", 200, True, "other"),
        ("response", 200, False, "exact_content_length"), ("response", 201, True, "exact_content_length"),
        ("response", 200, True, True), ("exception", "IncompleteRead", "http.client"))),
        "classifier:fixed_accept_mismatch_stops")
    cases["fixed_accept_mismatch_stops"] = "PASS"
    require(call("short_cl_refuse", ("exception", "IncompleteRead", "http.client")) == REFUSED,
            "classifier:short_refuse_exact")
    cases["short_refuse_exact"] = "PASS"
    require(all(_stops(call, "short_cl_refuse", o) for o in (
        ("exception", "JSONDecodeError", "json.decoder"), ("exception", "CoveringTransportRefused",
                                                           "app.services.covering_transport_policy"),
        ("exception", "IncompleteRead", "other.module"), ("response", 200, True, "close_delimited"),
        ("response", 200, True, "exact_content_length"))),
        "classifier:short_refuse_other_stops")
    cases["short_refuse_other_stops"] = "PASS"
    require(call("abrupt_distinct", ("exception", "SSLEOFError", "ssl")) == "OBSERVED"
            and call("abrupt_distinct", ("exception", "ConnectionResetError", "builtins")) == "OBSERVED",
            "classifier:abrupt_eof_observed")
    cases["abrupt_eof_observed"] = "PASS"
    require(all(_stops(call, "abrupt_distinct", o) for o in (
        ("exception", "IncompleteRead", "http.client"), ("exception", "JSONDecodeError", "json.decoder"),
        ("exception", "CoveringRootOutcomeUnknown", "app.services.covering_target_transaction"),
        ("response", 200, True, "close_delimited"), ("response", 200, True, "exact_content_length"))),
        "classifier:abrupt_other_stops")
    cases["abrupt_other_stops"] = "PASS"
    require(_stops(call, "something_else", ("response", 200, True, "close_delimited")),
            "classifier:unknown_expectation_stops")
    cases["unknown_expectation_stops"] = "PASS"
    return cases


# ---------------------------------------------------------------------------
# Suite ORDERLY mapping (whole stdlib-only np_suite module, source and candidate)
# ---------------------------------------------------------------------------

def load_suite(text: str, label: str) -> dict[str, Any]:
    with Sandbox(FIXTURE_NAMES) as box:
        suite = box.load("np_suite", text, f"<subject:suite:{label}>")
        result = {
            "counts": suite.validate_inventory_counts(),
            "decls": [decl_tuple(d) for d in tuple(suite.NATIVE_CASES) + tuple(suite.CF_WITNESS_CASES)],
            "registry_ids": list(suite.registry_by_id(include_cf=True)),
        }
    require(all(name not in sys.modules for name in FIXTURE_NAMES), "suite sandbox restored")
    return result


def decl_tuple(decl: Any) -> tuple[Any, ...]:
    return (decl.case_id, tuple(decl.planning_ids), decl.batch, decl.stimulus,
            tuple((o.name, tuple(o.planning_ids), o.expected, o.stop_on_mismatch) for o in decl.oracles),
            decl.expected_unknown, decl.native_tls_claim, decl.notes)


def planning_union(decls: list[tuple[Any, ...]]) -> set[str]:
    return {pid for d in decls for pid in d[1]} | {pid for d in decls for o in d[4] for pid in o[1]}


def oracle_suite_mapping(cand_text: str) -> dict[str, str]:
    cases = {}
    src, cand = load_suite(subject_text("suite/source.py"), "source"), load_suite(cand_text, "candidate")
    require(cand["counts"] == {"native": 27, "cf_witnesses": 4, "total_if_cf_included": 31}
            and len(cand["decls"]) == 31 and len(cand["registry_ids"]) == 31
            and [d[0] for d in cand["decls"]] == [d[0] for d in src["decls"]], "mapping:inventory_counts")
    cases["inventory_counts"] = "PASS"
    require(planning_union(cand["decls"]) == planning_union(src["decls"]), "mapping:planning_union_unchanged")
    cases["planning_union_unchanged"] = "PASS"
    orderly = _single([d for d in cand["decls"] if d[0] == ORDERLY_ID], "candidate ORDERLY declaration")
    oracles = {o[0]: o for o in orderly[4]}
    require(oracles.get(EXPECTED_ORDERLY_ORACLES[0][0]) == EXPECTED_ORDERLY_ORACLES[0],
            "mapping:close_delimited_oracle_unmapped")
    cases["close_delimited_oracle_unmapped"] = "PASS"
    holders = [(d[0], o[0]) for d in cand["decls"] for o in d[4] if VALID_COMPLETE_CL in o[1]]
    require(oracles.get(EXPECTED_ORDERLY_ORACLES[1][0]) == EXPECTED_ORDERLY_ORACLES[1]
            and holders == [(ORDERLY_ID, EXPECTED_ORDERLY_ORACLES[1][0])],
            "mapping:fixed_length_maps_valid_complete_cl")
    cases["fixed_length_maps_valid_complete_cl"] = "PASS"
    require(orderly[4] == EXPECTED_ORDERLY_ORACLES and orderly[1] == (VALID_COMPLETE_CL, SHORT_VALID_JSON)
            and all(d == s for d, s in zip(cand["decls"], src["decls"]) if d[0] != ORDERLY_ID),
            "mapping:orderly_declaration_exact")
    cases["orderly_declaration_exact"] = "PASS"
    return cases


def dump_expr(snippet: str) -> str:
    return ast.dump(ast.parse(snippet, mode="eval").body)


def dump_stmt(snippet: str) -> str:
    return ast.dump(_single(ast.parse(textwrap.dedent(snippet)).body, "snippet"))


def oracle_wiring(observe_src: str, runner_text: str) -> dict[str, str]:
    cases = {}
    fn = _single([n for n in ast.parse(observe_src).body if isinstance(n, ast.FunctionDef)], "_t05_observe")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "CoveringHTTP"]
    call = _single(calls, "CoveringHTTP construction")
    require(not call.args and sorted(k.arg or "" for k in call.keywords) == ["counter", "routes"]
            and any(ast.dump(s) == dump_stmt("counter = ProviderCounter(approved_provider_limits(), "
                                             "budget.work_remaining)") for s in fn.body)
            and any(isinstance(s, ast.If) and ast.dump(s.test) == dump_expr("http.transport_factory is not JoinedTLS")
                    for s in fn.body), "wiring:default_joined_tls_construction")
    cases["default_joined_tls_construction"] = "PASS"

    def index_of(predicate: Callable[[ast.stmt], bool], what: str) -> int:
        return _single([i for i, s in enumerate(fn.body) if predicate(s)], what)

    def contains_call(stmt: ast.stmt, attr_or_name: str) -> bool:
        return any(isinstance(n, ast.Call) and ((isinstance(n.func, ast.Attribute) and n.func.attr == attr_or_name)
                                                or (isinstance(n.func, ast.Name) and n.func.id == attr_or_name))
                   for n in ast.walk(stmt))

    validate = index_of(lambda s: isinstance(s, ast.Try) and contains_call(s, "_http_response_bytes"), "validation try")
    start = index_of(lambda s: isinstance(s, ast.Try) and contains_call(s, "start_background"), "peer try")
    require(validate < start, "wiring:framing_validated_before_peer_start")
    cases["framing_validated_before_peer_start"] = "PASS"
    peer_try = fn.body[start]
    classify = index_of(lambda s: isinstance(s, ast.Assign) and contains_call(s, "_t05_classify_client_outcome"),
                        "classification")
    state = index_of(lambda s: isinstance(s, ast.Assign) and contains_call(s, "sanitized_state"), "peer state")
    require(peer_try.finalbody and ast.dump(peer_try.finalbody[0]) ==
            dump_stmt("retirement = peer.retire_owned(join_seconds=5.0)")
            and start < state < classify, "wiring:retirement_in_finally_before_classification")
    cases["retirement_in_finally_before_classification"] = "PASS"
    for name in ("_run_np_t05_orderly_close", "_run_np_t05_abrupt_truncation"):
        body = unit_node(runner_text, name)
        oracle_lines = [n.lineno for n in ast.walk(body) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "check_oracles_immediate"]
        receipt = [n for n in ast.walk(body) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == "case_result_receipt"]
        receipt_call = _single(receipt, f"{name} receipt")
        kw = {k.arg: k.value for k in receipt_call.keywords}
        require(len(oracle_lines) == 1 and oracle_lines[0] < receipt_call.lineno
                and all(isinstance(kw.get(k), ast.Constant) and kw[k].value is v
                        for k, v in (("passed", True), ("workers_joined", True), ("expected_unknown", False))),
                f"wiring:bodies_oracle_then_receipt:{name}")
    cases["bodies_oracle_then_receipt"] = "PASS"
    orderly = unit_node(runner_text, "_run_np_t05_orderly_close")
    observe_calls = sorted((n for n in ast.walk(orderly) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id == "_t05_observe"), key=lambda n: (n.lineno, n.col_offset))
    shapes = [(a[1].func.id if len(a) == 3 and isinstance(a[1], ast.Call) and isinstance(a[1].func, ast.Name)
               and not a[1].args and not a[1].keywords else None,
               a[2].value if len(a) == 3 and isinstance(a[2], ast.Constant) else None)
              for a in (c.args for c in observe_calls)]
    obs_dicts = [n for n in ast.walk(orderly) if isinstance(n, ast.Assign) and len(n.targets) == 1
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "observations"]
    obs_dict = _single(obs_dicts, "ORDERLY observations").value
    require(shapes == list(EXPECTED_ORDERLY_OBSERVATIONS) and all(not c.keywords for c in observe_calls)
            and isinstance(obs_dict, ast.Dict)
            and [k.value for k in obs_dict.keys if isinstance(k, ast.Constant)] == [o[0] for o in EXPECTED_ORDERLY_ORACLES]
            and len(obs_dict.keys) == 3, "wiring:orderly_three_observations")
    cases["orderly_three_observations"] = "PASS"
    ids = unit_text(runner_text, "IMPLEMENTED_CASE_IDS")
    mapper = unit_text(runner_text, "_make_implemented_case")
    require(all(f'"{cid}"' in ids for cid in T05_IDS + ["NP-V-MS-NONEXPIRED", "NP-V-MS-REFRESH"])
            and ids.count('"NP-') == 4
            and "return _run_np_t05_orderly_close()" in mapper and "return _run_np_t05_abrupt_truncation()" in mapper,
            "wiring:mapper_and_implemented")
    cases["mapper_and_implemented"] = "PASS"
    rebuilt_header_reads = [n for n in ast.walk(fn) if isinstance(n, ast.Attribute) and n.attr == "headers"
                            and isinstance(n.value, ast.Name) and n.value.id == "response"]
    outcome_calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                     and n.func.id == "_t05_response_outcome"]
    require(not rebuilt_header_reads and len(outcome_calls) == 1 and not outcome_calls[0].keywords
            and [ast.dump(a) for a in outcome_calls[0].args]
            == [dump_expr(x) for x in ("response.status_code", "response.content", "expected_body", "expected_wire")],
            "wiring:no_rebuilt_header_oracle")
    cases["no_rebuilt_header_oracle"] = "PASS"
    return cases


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def check_regression() -> dict[str, Any]:
    return {"cases": oracle_regression(serializer("candidate")), "control_kind": "extracted_behavior_fake",
            "observed": "PASS"}


def check_close_delimited() -> dict[str, Any]:
    return {"cases": oracle_close_delimited(serializer("candidate")), "control_kind": "extracted_behavior_fake",
            "observed": "PASS"}


def check_invalid() -> dict[str, Any]:
    return {"cases": oracle_invalid(serializer("candidate")), "control_kind": "extracted_behavior_fake",
            "observed": "PASS"}


def check_classifier() -> dict[str, Any]:
    return {"cases": oracle_classifier(subject_text("runner/candidate.py")), "control_kind": "extracted_behavior_fake",
            "observed": "PASS"}


def check_suite_mapping() -> dict[str, Any]:
    return {"cases": oracle_suite_mapping(subject_text("suite/candidate.py")), "control_kind": "whole_module_fake",
            "observed": "PASS"}


def check_wiring() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    return {"cases": oracle_wiring(unit_text(runner, "_t05_observe"), runner), "control_kind": "structural_source",
            "observed": "PASS"}


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
    require(cfg.get("case_ids") == T05_IDS and cfg.get("expected_unknown_cases") == [] and cfg.get("launch_ready") is False,
            "batch:runner config")
    cases["runner_config"] = "PASS"
    raw = subject_text("config/candidate-launch-config.json")
    launch = json.loads(raw)
    require(launch.get("case_ids") == T05_IDS and launch.get("expected_unknown_cases") == []
            and launch.get("batch_id") == "np-t05-orderly-and-abrupt" and launch.get("launch_ready") is False
            and launch.get("candidate_launch_ready_staged") is False and launch.get("human_launch_authorized") is False
            and launch.get("endpoint") == "unbound"
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and all(OWN_ROOT in str(launch.get(k)) for k in ("docker_ops_config_path", "receipt_directory"))
            and not any(root in raw for root in FOREIGN_ROOTS), "batch:launch config")
    cases["launch_config"] = "PASS"
    src, cand = rows(subject_text("manifest/source.txt")), rows(subject_text("manifest/candidate.txt"))
    changed = {rel for rel in src if src[rel] != cand.get(rel)}
    require(set(src) == set(cand) and changed == set(CHANGED_PAYLOAD_ROWS)
            and all(cand[rel] == SUBJECT_PINS[subject] for rel, subject in CHANGED_PAYLOAD_ROWS.items()),
            "batch:payload manifest delta")
    cases["payload_delta_exact"] = "PASS"
    return {"cases": cases, "control_kind": "config_data", "observed": "PASS"}


def check_prior_applicability() -> dict[str, Any]:
    cases = {}
    src_peer, cand_peer = subject_text("peer/source.py"), subject_text("peer/candidate.py")
    src_cls = unit_node(src_peer, "SyntheticProviderPeer")
    cand_cls = unit_node(cand_peer, "SyntheticProviderPeer")
    require(ast.dump(src_cls) == ast.dump(cand_cls)
            and unit_text(src_peer, "_http_response_bytes") != unit_text(cand_peer, "_http_response_bytes"),
            "applicability:peer")
    cases["peer_class_identical_serializer_changed"] = "PASS"
    src_run, cand_run = subject_text("runner/source.py"), subject_text("runner/candidate.py")
    carried = ("_install_worker_exception_observer", "_run_np_v_ms_nonexpired", "stop_payload",
               "_ms_refresh_provider_routes", "_require_production_ms_token_path", "_actual_token_terminals",
               "_run_np_v_ms_refresh")
    require(all(unit_text(src_run, n) == unit_text(cand_run, n) for n in carried), "applicability:merge units")
    cases["merge_units_identical"] = "PASS"
    src_tr, cand_tr = subject_text("transcript/source.py"), subject_text("transcript/candidate.py")
    unchanged_scripts = ("ms_token_success_script", "ms_graph_identity_default_script", "ms_graph_identity_list_script",
                         "ms_graph_calendar_view_empty_script", "ms_nonexpired_connection_inventory",
                         "ms_refresh_connection_inventory", "orderly_short_cl_valid_json_refuse_script",
                         "abrupt_truncation_script")
    require(all(unit_text(src_tr, n) == unit_text(cand_tr, n) for n in unchanged_scripts), "applicability:transcript")
    cases["transcript_functions_identical"] = "PASS"
    return {"cases": cases, "not_transferred": [
        "peer-close fake PRESERVED-OUTSIDE-CHANGE (only _close_connection differs from 5568AF73): no longer true; "
        "_http_response_bytes now also differs. Current prerequisite: SERIALIZER-DEFAULT-REGRESSION.",
        "ms-refresh fake v2 OAUTH-ROUTE-TABLE (executed 5568AF73 _http_response_bytes): serializer changed. "
        "Current prerequisite: SERIALIZER-DEFAULT-REGRESSION wire equality for every MS script.",
        "ms-refresh fake v2 transcript-derived controls: ExchangeStep gained a defaulted field. Current prerequisite: "
        "SERIALIZER-DEFAULT-REGRESSION step-field equality plus transcript_functions_identical.",
        "merge fake ROLE-SELECTION peer row 17EA148E: does not describe this root (peer BFB271D7).",
        "T05 fake v2 CLIENT close_delimited_accepted (FakeHttpxResponse without the httpx 0.28.1 Content-Length "
        "supplement) and changed_script_is_only_delta: superseded. Current prerequisites: the v3 default "
        "AutoLengthHttpxResponse cases and catalog_delta_changed_plus_added."],
        "control_kind": "applicability_map", "observed": "PASS"}


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


def _mutate(text: str, mutation: tuple[str, str]) -> str:
    require(text.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
    return text.replace(*mutation)


def check_mutants() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    observe = unit_text(runner, "_t05_observe")
    mutants = {
        "close_delimited_appends_length": (lambda: oracle_close_delimited(serializer("candidate", M_DELIM_CONN)),
                                           "close delimited:exact bytes"),
        "transfer_encoding_refusal_removed": (lambda: oracle_invalid(serializer("candidate", M_TE_REFUSAL)),
                                              "invalid mode:auto_with_transfer_encoding"),
        "auto_path_altered": (lambda: oracle_regression(serializer("candidate", M_AUTO_CONN)),
                              "default regression:catalog_scripts:wire"),
        "abrupt_accepts_incomplete_read": (lambda: oracle_classifier(_mutate(runner, M_ABRUPT_SET)),
                                           "classifier:abrupt_other_stops"),
        "transport_factory_injected": (lambda: oracle_wiring(_mutate(observe, M_FACTORY), runner),
                                       "wiring:default_joined_tls_construction"),
        "retirement_removed": (lambda: oracle_wiring(_mutate(observe, M_RETIRE), runner),
                               "wiring:retirement_in_finally_before_classification"),
        "wire_framing_predicate_dropped": (lambda: oracle_rebuilt_trap(_mutate(runner, M_WIRE_PREDICATE)),
                                           "client:rebuilt trap negative"),
        "framing_conflation": (lambda: oracle_fixed_length_client(_mutate(runner, M_FRAMING_CONFLATION)),
                               "client:fixed length accepted"),
        "orderly_mapping_swapped": (lambda: oracle_suite_mapping(
            _mutate(_mutate(subject_text("suite/candidate.py"), M_MAP_SWAP_A), M_MAP_SWAP_B)),
            "mapping:close_delimited_oracle_unmapped"),
        "fixed_expectation_swapped": (lambda: oracle_wiring(observe, _mutate(runner, M_FIXED_EXPECTATION)),
                                      "wiring:orderly_three_observations"),
    }
    results = {name: _expect_detected(name, action, prefix) for name, (action, prefix) in mutants.items()}
    return {"mutants": results, "control_kind": "actual_source_mutant", "observed": "PASS"}


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
    require(expected.get("kind") == "native-t05-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "SERIALIZER-DEFAULT-REGRESSION": check_regression,
        "ORDERLY-POSITIVE-SERIALIZATION": check_close_delimited,
        "INVALID-MODE-REFUSALS": check_invalid,
        "CLIENT-COMPLETENESS-VS-DECODE": check_client_completeness,
        "OUTCOME-CLASSIFIER": check_classifier,
        "SUITE-ORDERLY-MAPPING": check_suite_mapping,
        "RUNNER-WIRING": check_wiring,
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
