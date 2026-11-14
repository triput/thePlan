#!/usr/bin/env python3
"""HELD fake-only checker for the native NP-V-GOOGLE-REFRESH preparation (Dex CEBD83C3).

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned): source/candidate runner, transcript and suite (source = passed
scheduler-native-ms-nonexpired-retirement-launch-matt-v2, candidate =
scheduler-native-google-refresh-prep-matt-v1), their four diffs, source/candidate
runner-config, launch-config and docker-ops-config, both payload and nested manifests,
the unchanged peer (17EA148E), sanitizer (69F59AF1) and auth seed (66FEEA81), and the
unchanged production google_calendar.py (8A335971), export_baseline.py (39EB4E58) and
covering_refresh_window.py (7E39381B).

Execution surfaces (all fake; no socket, TLS, certificate, PKI, DB, Docker, thread,
process, ASGI or vendor package):
- BEHAVIORAL (extracted actual source units with named fakes): the new Google transcript
  units executed inside a privately registered ModuleType (frozen dataclasses resolve their
  module there), the actual peer response serializer, the actual production _iso_z /
  google_mirror_datetime_token / _ensure_aware_utc units, the whole actual
  covering_refresh_window module (registered), and the runner's new route, query,
  credential, event and PARENT-observer helpers with named fakes for HTTPSPeer, the ORM
  session/models, token_crypto and CoveringParentAdapter.
- STRUCTURAL (AST/text only): preservation, the case body wiring (ingress, single
  retirement, guards, restoration, free names), oracle names, emitted receipt keys and
  configuration. _run_np_v_google_refresh itself is NOT executed.

Proof scope: finite fixture/source properties. NOT proved: production refresh, import,
coverage or assessment behavior; native TLS; wire timing; the PARENT/TOKEN sequences
(source-derived expectations); any T06 requirement.
"""
from __future__ import annotations

import ast
import builtins
import dataclasses  # noqa: F401  (disclosed unpinned runtime; used by extracted transcript dataclasses)
import enum
import hashlib
import json
import json.decoder
import json.scanner
import os
import re
import sys
import textwrap
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-native-google-refresh-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/source.py": "A2C32A2042A523BE932826666D87501AA57A6B4D0E4ECCB173AEDF966794B77D",
    "runner/candidate.py": "6C0FA135955CC2DA476A2657E4F66B456E5B0F6F08074B8BFFB696FEEBF2F5DB",
    "transcript/source.py": "CFAB2D060BF03779A5B7BB7AF546F57124D5AF501CED6B93FFAAB76ED86AB6A3",
    "transcript/candidate.py": "D74EB1FE1393605251A95449B32D27D580FC19CC5427459E2806B78C7B63A82C",
    "suite/source.py": "AEC59FCDA058124FDF7265D41B8A660C4AD139CE13417F88FA637542CF9C1673",
    "suite/candidate.py": "98DCC0422D04A11417CB5AE78B85ED5FCDA2F3132594A196005B4DD1B67531D4",
    "diff/np_runner_entry.py.diff": "0E5938B73F1B92CEC914DFDC6D157CEAE471E817C6D0BA19EFBF4393902C5FF4",
    "diff/np_provider_transcript.py.diff": "D3A072E110377BF5E36500773CF633F5709AE03704FAD2AF9D8993BEB4DF0755",
    "diff/np_suite.py.diff": "7ABEA8CA2D1489E2D23AA71E44848AB585733C3DCBB2D3BB5968A300131057AF",
    "diff/runner-config.json.diff": "7D48720399CFAE7274BB72911E335181CD6713061FA950CC75A2E1C087CC9AA3",
    "config/source-runner-config.json": "8668F156909260BE7D9A9164757E144190DC79337778FB4CD0B704805DB0D029",
    "config/candidate-runner-config.json": "95278DF6B3756F39B5D45CF24C96B3435B20394D3A951FAD95DE5FB76095E7ED",
    "config/source-launch-config.json": "03A131BCF99EF1E65E170E9203C37B037E0374EAA25FB0A3974889453A83F6C9",
    "config/candidate-launch-config.json": "F0B8A78FB5CABFB914044F1ED35EB206809B43E59B1EDFEDCE3FEE284E302452",
    "config/source-docker-ops-config.json": "5E6CEDCB2CB3D64122B840EBB38D278EED5121D6908102C209FEB98F18099A76",
    "config/candidate-docker-ops-config.json": "317A0C195CE80EF9C7D8BB6492D20272CBCCBDE3DED3A531BDB11E27C307F813",
    "manifest/source.txt": "C058ECCED75C8783E8CDF5E5413137386D10E67A0B33C8122ACE5F2A2D24694A",
    "manifest/candidate.txt": "63325E1542472C93045278A36A37F3DC3C6EA1F44DCE50CA951D55A44E4ABEB8",
    "manifest/source-nested.txt": "DA1D9A157E8F6BCB6512923126D2E76104E9D48CE39E27F40B687B5388C08BB8",
    "manifest/candidate-nested.txt": "E29827DBDA20D363D103B6D72B859523AA88E394D9AD56AF7C449F2FB6F178C4",
    "fixture/np_provider_peer.py": "17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039",
    "fixture/np_receipts.py": "69F59AF10FF5A6FAED469E4C93DCB128F741C50444CC31E37737EC4889B708FD",
    "fixture/np_auth_seed.py": "66FEEA815C7B196A78117229F80769ADDF8428CB073A586B59E2D81491419150",
    "app/google_calendar.py": "8A33597198FEFBC8D5E6671D56FE4118091F89255A6F46A8589117127318231F",
    "app/export_baseline.py": "39EB4E58DE2096F951383F70CDD814F82970FA65A640B9E26E5BA50DF94A2347",
    "app/covering_refresh_window.py": "7E39381B06A9557F8E4D29EFDEE1A140AA123155058BE949213664087B8114C0",
}
RUNTIME_MODULE_PINS = {
    "json_init_pin": ("json", "FEB17670E443E5DB2723F217727DCC5D5E155C40E4E6935B16061C88542F24E7"),
    "json_decoder_pin": ("json.decoder", "B719FBCFCEBD2B174F076E71292E22B1A17D9E258DBE896C768325383BAD4F80"),
    "json_scanner_pin": ("json.scanner", "9841566FB17315EBDD40A1CA9CB214F02CDE7171B187D4DC821C80120EA853C3"),
}
UNPINNED_RUNTIME = ("urllib.parse", "datetime", "dataclasses", "typing", "enum", "uuid")

CONTROL_IDS = (
    "SUBJECT-PINS",
    "RUNTIME-PROVENANCE",
    "DIFF-REDERIVATION",
    "PRESERVED-OUTSIDE-CHANGE",
    "TRANSCRIPT-SCRIPTS",
    "ROUTES-AND-QUERY",
    "CREDENTIAL-MEASUREMENT",
    "EVENT-MEASUREMENT",
    "PARENT-OBSERVER",
    "CASE-WIRING",
    "RECEIPT-RETENTION",
    "CONFIG-AND-IMMUTABLES",
    "ACTUAL-SOURCE-MUTANTS",
)

CASE_ID = "NP-V-GOOGLE-REFRESH"
RUN_FN = "_run_np_v_google_refresh"
OWN_ROOT = "scheduler-native-google-refresh-prep-matt-v1"
SOURCE_ROOT = "scheduler-native-ms-nonexpired-retirement-launch-matt-v2"
RUNNER_ADDED = {"GOOGLE_SEED_ACCESS_PLAINTEXT", "GOOGLE_SEED_REFRESH_PLAINTEXT", "GOOGLE_EVENTS_PREFIX",
                "GOOGLE_CLIENT_PURPOSES", "GOOGLE_TOKEN_TERMINAL_SEQUENCE", "GOOGLE_PARENT_TERMINAL_SEQUENCE",
                "GOOGLE_ACTION_SUMMARY", "GOOGLE_CREDENTIAL_SEMANTIC_KEYS", "GOOGLE_EVENT_IDS",
                "_google_provider_routes", "_google_events_exact_query", "_measure_google_credential_state",
                "_measure_google_events", "_install_google_parent_observer", RUN_FN}
RUNNER_CHANGED = {"IMPLEMENTED_CASE_IDS", "_make_implemented_case"}
RUNNER_REUSED_UNCHANGED = ("_retire_selected_peer_then_observe", "_install_token_terminal_observer",
                           "_install_worker_exception_observer", "_open_native_setup_factory",
                           "provision_disposable_schema", "_fixture_database_profile", "_runtime_pins_from_config")
TRANSCRIPT_ADDED = {"GOOGLE_REFRESHED_ACCESS_PLAINTEXT", "GOOGLE_ROTATED_REFRESH_PLAINTEXT",
                    "GOOGLE_REFRESH_EXPIRES_IN_SECONDS", "GOOGLE_REFRESH_EXCHANGE_COUNT", "GOOGLE_TOKEN_PATH",
                    "google_token_refresh_success_script", "google_busy_event", "google_events_one_page_script",
                    "google_refresh_connection_inventory"}
TRANSCRIPT_UNITS = ("CloseMode", "ExchangeStep", "ExchangeScript", "GOOGLE_REFRESHED_ACCESS_PLAINTEXT",
                    "GOOGLE_ROTATED_REFRESH_PLAINTEXT", "GOOGLE_REFRESH_EXPIRES_IN_SECONDS",
                    "GOOGLE_REFRESH_EXCHANGE_COUNT", "GOOGLE_TOKEN_PATH", "google_token_refresh_success_script",
                    "google_busy_event", "google_events_one_page_script", "google_refresh_connection_inventory")
RUNNER_CONSTANT_UNITS = ("GOOGLE_SEED_ACCESS_PLAINTEXT", "GOOGLE_SEED_REFRESH_PLAINTEXT", "GOOGLE_EVENTS_PREFIX",
                         "GOOGLE_CLIENT_PURPOSES", "GOOGLE_TOKEN_TERMINAL_SEQUENCE",
                         "GOOGLE_PARENT_TERMINAL_SEQUENCE", "GOOGLE_ACTION_SUMMARY",
                         "GOOGLE_CREDENTIAL_SEMANTIC_KEYS", "GOOGLE_EVENT_IDS")
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
                  "fixture/np_receipts.py": "fixture/np_receipts.py",
                  "fixture/np_auth_seed.py": "fixture/np_auth_seed.py",
                  "api/app/services/google_calendar.py": "app/google_calendar.py",
                  "api/app/services/export_baseline.py": "app/export_baseline.py",
                  "api/app/services/covering_refresh_window.py": "app/covering_refresh_window.py"}
IMMUTABLE_UNPINNED = ("fixture/np_provider_routes.py", "fixture/np_integrated_runner.py",
                      "fixture/docker_transport.py", "fixture/i01_asgi_app.py", "fixture/prepare-np-provider-tls.sh")

REFRESHED = "np-google-refreshed-access-not-for-receipt"
ROTATED = "np-google-rotated-refresh-not-for-receipt"
SEED_ACCESS = "fixture-access-plaintext-not-for-receipt"
SEED_REFRESH = "fixture-refresh-plaintext-not-for-receipt"
QUERY_LITERAL = ("timeMin=2026-11-20T09%3A00%3A00.123456Z&timeMax=2026-11-21T03%3A30%3A00Z"
                 "&singleEvents=true&showDeleted=true&orderBy=startTime&maxResults=2500")
CREDENTIAL_KEYS = {"seed_access_match", "seed_refresh_match", "refreshed_access_match", "rotated_refresh_match",
                   "expiry", "expiry_at_or_before_reference"}

# Mutation anchors (each verified unique in the whole candidate text it mutates).
M_REFRESH_OMITTED = ('            "refresh_token": GOOGLE_ROTATED_REFRESH_PLAINTEXT,\n', "")
M_QUERY_WRONG = ('        "showDeleted": "true",\n', '        "showDeleted": "false",\n')
M_ROTATED_VS_ACCESS = ('        "rotated_refresh_match": refresh == GOOGLE_ROTATED_REFRESH_PLAINTEXT,\n',
                       '        "rotated_refresh_match": access == GOOGLE_ROTATED_REFRESH_PLAINTEXT,\n')
M_PARENT_SWALLOW = ('            parent_terminals.append({"raised": type(exc).__name__, "commit_requested": bool(commit)})\n'
                    '            raise\n',
                    '            parent_terminals.append({"raised": type(exc).__name__, "commit_requested": bool(commit)})\n'
                    '            return None\n')
M_SORT_DROPPED = ('    return sorted(out, key=lambda item: (item["calendar_id"], item["external_event_id"]))\n',
                  "    return out\n")
M_SECOND_RETIRE = ("        retirement_done = True\n        peer_exchanges = list",
                   "        retirement_done = True\n        peer.retire_owned(join_seconds=5.0)\n"
                   "        peer_exchanges = list")
M_KEY_UNALLOWLISTED = ('            "token_terminal": token_sequence,\n',
                       '            "token_terminal_sequence": token_sequence,\n')
M_UNRELATED_DROPPED = ('        if after["unrelated_coverage"] != before["unrelated_coverage"] or after["unrelated_events"]:\n',
                       '        if after["unrelated_coverage"] != before["unrelated_coverage"]:\n')


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
    import urllib.parse  # noqa: F401  (loaded here so the disclosure below is deterministic)

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


def _expr(source: str) -> str:
    # Parenthesized so a multi-line guard parses as one expression (parentheses add no AST node).
    return ast.dump(ast.parse("(" + textwrap.dedent(source).strip() + ")", mode="eval").body)


def guard_tests(fn: ast.AST, message: str) -> list[str]:
    """Dumps of every `if <test>: raise SuiteStop(<message>)` in fn with a constant message."""
    found = []
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and len(node.body) == 1 and isinstance(node.body[0], ast.Raise):
            exc = node.body[0].exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "SuiteStop" \
                    and exc.args and isinstance(exc.args[0], ast.Constant) and exc.args[0].value == message:
                found.append(ast.dump(node.test))
    return found


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
            "preserved:reused helpers")
    cases["reused_helpers_byte_identical"] = "PASS"
    s, c = top_table(subject_text("transcript/source.py")), top_table(subject_text("transcript/candidate.py"))
    ss, sc = top_table(subject_text("suite/source.py")), top_table(subject_text("suite/candidate.py"))
    require(set(c) - set(s) == TRANSCRIPT_ADDED and set(s) <= set(c) and all(s[n] == c[n] for n in s)
            and set(ss) == set(sc) and {n for n in ss if ss[n] != sc[n]} == {"CASE_IMPLEMENTATION_NOTES"},
            "preserved:transcript and suite")
    cases["transcript_and_suite"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# TRANSCRIPT-SCRIPTS (behavioral: actual transcript units in a registered ModuleType)
# ---------------------------------------------------------------------------

def peer_serializer() -> Callable[[Any], bytes]:
    ns: dict[str, Any] = {"Any": Any}
    exec_units(subject_text("fixture/np_provider_peer.py"), ("_http_response_bytes",), ns, "peer")
    return ns["_http_response_bytes"]


def with_transcript(transcript_text: str, action: Callable[[types.ModuleType], Any],
                    extra: tuple[str, ...] = (), setup: Callable[[Sandbox], None] | None = None) -> Any:
    from dataclasses import dataclass
    from typing import Literal

    with Sandbox(("np_provider_transcript",) + extra) as box:
        # Registered BEFORE executing decorated dataclasses (dataclasses resolves cls.__module__).
        module = box.put("np_provider_transcript", types.ModuleType("np_provider_transcript"))
        module.__dict__.update({"dataclass": dataclass, "Literal": Literal})
        exec_units(transcript_text, TRANSCRIPT_UNITS, module.__dict__, "transcript")
        if setup is not None:
            setup(box)
        return action(module)


def _raises(action: Callable[[], Any], kind: type) -> bool:
    try:
        action()
    except kind:
        return True
    return False


def oracle_transcript(transcript_text: str) -> dict[str, str]:
    cases = {}
    serialize = peer_serializer()

    def token(t: types.ModuleType) -> None:
        script = t.google_token_refresh_success_script()
        recv, send, close = script.steps
        body = json.loads(send.body_template)
        wire = serialize(send)
        head, _, wire_body = wire.partition(b"\r\n\r\n")
        require(len(script.steps) == 3 and (recv.direction, recv.method, recv.path) == ("recv_request", "POST", "/token")
                and send.direction == "send_response" and send.status == 200
                and body == {"access_token": REFRESHED, "expires_in": 3600, "refresh_token": ROTATED,
                             "token_type": "Bearer"}
                and wire_body == send.body_template.encode("utf-8")
                and f"Content-Length: {len(wire_body)}".encode("ascii") in head.split(b"\r\n")
                and (close.direction, close.close_mode) == ("close", "orderly_close_notify"),
                "transcript:token body")

    with_transcript(transcript_text, token)
    cases["token_body_and_framing"] = "PASS"

    def event(t: types.ModuleType) -> None:
        ok = t.google_busy_event(event_id="e1", start_z="2026-11-20T10:00:00Z", end_z="2026-11-20T11:00:00Z")
        require(ok == {"id": "e1", "status": "confirmed", "start": {"dateTime": "2026-11-20T10:00:00Z"},
                       "end": {"dateTime": "2026-11-20T11:00:00Z"}, "transparency": "opaque"}
                and _raises(lambda: t.google_busy_event(event_id="e", start_z="2026-11-20T10:00:00+00:00",
                                                        end_z="2026-11-20T11:00:00Z"), RuntimeError)
                and _raises(lambda: t.google_busy_event(event_id="e", start_z="2026-11-20T11:00:00Z",
                                                        end_z="2026-11-20T10:00:00Z"), RuntimeError),
                "transcript:busy event")

    with_transcript(transcript_text, event)
    cases["busy_event_shape_and_refusals"] = "PASS"

    def events_script(t: types.ModuleType) -> None:
        ev = t.google_busy_event(event_id="e1", start_z="2026-11-20T10:00:00Z", end_z="2026-11-20T11:00:00Z")
        script = t.google_events_one_page_script(calendar_id="cal-a/b@c", exact_query="q=1&r=2", event=ev)
        recv, send, close = script.steps
        require((recv.method, recv.path) == ("GET", "/calendar/v3/calendars/cal-a%2Fb%40c/events?q=1&r=2")
                and json.loads(send.body_template) == {"kind": "calendar#events", "items": [ev]}
                and "nextPageToken" not in send.body_template and "nextSyncToken" not in send.body_template
                and close.close_mode == "orderly_close_notify" and script.purpose == "event"
                and all(_raises(lambda q=q: t.google_events_one_page_script(calendar_id="c", exact_query=q, event=ev),
                                RuntimeError) for q in ("", "a?b", "a#b")),
                "transcript:events path query")

    with_transcript(transcript_text, events_script)
    cases["events_path_query_exact"] = "PASS"

    def inventory(t: types.ModuleType) -> None:
        evs = (t.google_busy_event(event_id="e1", start_z="2026-11-20T10:00:00Z", end_z="2026-11-20T11:00:00Z"),
               t.google_busy_event(event_id="e2", start_z="2026-11-20T12:00:00Z", end_z="2026-11-20T13:00:00Z"))
        scripts = t.google_refresh_connection_inventory(wire_calendar_ids=("cal-1", "cal-2"), exact_query="q=1",
                                                        events=evs)
        paths = [s.steps[0].path for s in scripts]
        bodies = [json.loads(s.steps[1].body_template) for s in scripts[1:]]
        require(len(scripts) == 3 and [s.steps[0].method for s in scripts] == ["POST", "GET", "GET"]
                and paths == ["/token", "/calendar/v3/calendars/cal-1/events?q=1",
                              "/calendar/v3/calendars/cal-2/events?q=1"]
                and [b["items"][0]["id"] for b in bodies] == ["e1", "e2"]
                and _raises(lambda: t.google_refresh_connection_inventory(
                    wire_calendar_ids=("cal-1",), exact_query="q=1", events=evs[:1]), RuntimeError)
                and _raises(lambda: t.google_refresh_connection_inventory(
                    wire_calendar_ids=("a", "b", "c"), exact_query="q=1", events=evs), RuntimeError),
                "transcript:inventory")

    with_transcript(transcript_text, inventory)
    cases["inventory_exact_three_ordered"] = "PASS"
    peer = subject_text("fixture/np_provider_peer.py")
    require(peer.count('expected_path, expected_separator, expected_query = step.path.partition("?")') == 1
            and peer.count("not actual_separator or actual_query != expected_query") == 1
            and peer.count('exchange["query_verified"] = bool(step.path and "?" in step.path)') == 1,
            "transcript:peer exact query")
    cases["peer_exact_query_semantics_present"] = "PASS"
    return cases


def check_transcript() -> dict[str, Any]:
    return {"cases": oracle_transcript(subject_text("transcript/candidate.py")),
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# ROUTES-AND-QUERY (behavioral: actual production _iso_z chain + actual window module)
# ---------------------------------------------------------------------------

QUERY_MODULES = ("app", "app.services", "app.services.google_calendar", "app.services.covering_refresh_window",
                 "app.services.covering_transport_policy")


def runner_namespace(runner_text: str, names: tuple[str, ...]) -> dict[str, Any]:
    ns: dict[str, Any] = {"Any": Any, "Callable": Callable, "datetime": datetime, "timezone": timezone,
                          "UUID": uuid.UUID}
    for name in RUNNER_CONSTANT_UNITS:
        exec(compile(unit_text(runner_text, name), f"<extracted:runner:{name}>", "exec"), ns)
    return exec_units(runner_text, names, ns, "runner")


def with_query_modules(box: Sandbox, peers: list[dict[str, Any]]) -> None:
    mods = {name: box.put(name, types.ModuleType(name)) for name in QUERY_MODULES}
    baseline_ns: dict[str, Any] = {"datetime": datetime, "timezone": timezone}
    exec_units(subject_text("app/export_baseline.py"), ("_ensure_aware_utc", "google_mirror_datetime_token"),
               baseline_ns, "export_baseline")
    google = mods["app.services.google_calendar"]
    google.__dict__.update({"datetime": datetime, "google_mirror_datetime_token":
                            baseline_ns["google_mirror_datetime_token"]})
    exec_units(subject_text("app/google_calendar.py"), ("_iso_z",), google.__dict__, "google_calendar")
    window = mods["app.services.covering_refresh_window"]
    exec(compile(subject_text("app/covering_refresh_window.py"), "<subject:covering_refresh_window>", "exec"),
         window.__dict__)

    class FakeHTTPSPeer:
        def __init__(self, *, hostname, address, port, ca_file):
            self.fields = {"hostname": hostname, "address": address, "port": port, "ca_file": ca_file}
            peers.append(self.fields)

    mods["app.services.covering_transport_policy"].HTTPSPeer = FakeHTTPSPeer
    mods["app"].services = mods["app.services"]
    mods["app.services"].google_calendar = google
    mods["app.services"].covering_refresh_window = window
    mods["app.services"].covering_transport_policy = mods["app.services.covering_transport_policy"]


def run_query(runner_text: str, start: datetime, end: datetime) -> str:
    ns = runner_namespace(runner_text, ("_google_events_exact_query",))
    with Sandbox(QUERY_MODULES) as box:
        with_query_modules(box, [])
        return ns["_google_events_exact_query"](start, end)


def oracle_query(runner_text: str) -> dict[str, str]:
    cases = {}
    ns = runner_namespace(runner_text, ("_google_provider_routes",))
    peers: list[dict[str, Any]] = []
    api = types.SimpleNamespace(server_hostname="www.googleapis.com", dial_address="127.0.0.1", dial_port=443,
                                ca_path="/tmp/ca.crt")
    tok = types.SimpleNamespace(server_hostname="oauth2.googleapis.com", dial_address="127.0.0.1", dial_port=443,
                                ca_path="/tmp/ca.crt")
    with Sandbox(QUERY_MODULES) as box:
        with_query_modules(box, peers)
        routes = ns["_google_provider_routes"](api_route=api, token_route=tok)
    require(len(routes) == 2 and [(r[1], r[2]) for r in routes] == [("/token", "oauth"),
                                                                     ("/calendar/v3/calendars/", "event")]
            and [r[0].fields["hostname"] for r in routes] == ["oauth2.googleapis.com", "www.googleapis.com"]
            and all(p["address"] == "127.0.0.1" and p["port"] == 443 and p["ca_file"] == "/tmp/ca.crt"
                    for p in peers) and len(peers) == 2
            and not any("calendarList" in r[1] or "/users/me" in r[1] for r in routes), "query:routes")
    cases["routes_classify_oauth_and_event_only"] = "PASS"
    got = run_query(runner_text, datetime(2026, 11, 20, 9, 0, 0, 123456, tzinfo=timezone.utc),
                    datetime(2026, 11, 21, 3, 30, tzinfo=timezone.utc))
    require(got == QUERY_LITERAL, "query:literal")
    cases["exact_query_literal_with_microseconds"] = "PASS"
    plus2 = timezone(timedelta(hours=2))
    got = run_query(runner_text, datetime(2026, 11, 20, 11, 0, 0, 123456, tzinfo=plus2),
                    datetime(2026, 11, 21, 5, 30, tzinfo=plus2))
    require(got == QUERY_LITERAL, "query:literal")
    cases["offset_input_normalized_to_utc"] = "PASS"
    prod = unit_node(subject_text("app/google_calendar.py"), "list_calendar_events")
    prod_dict = _single([n.value for n in ast.walk(prod) if isinstance(n, ast.Assign)
                         and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "params"], "production params")
    mine = _single([n.value for n in ast.walk(unit_node(runner_text, "_google_events_exact_query"))
                    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "params"],
                   "runner params")
    require([k.value for k in prod_dict.keys] == [k.value for k in mine.keys]
            and [ast.dump(v) for v in prod_dict.values[2:]] == [ast.dump(v) for v in mine.values[2:]]
            and all(isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "_iso_z"
                    for v in prod_dict.values[:2])
            and all(isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "_iso_z"
                    for v in mine.values[:2]), "query:production params mirror")
    cases["params_mirror_production_source"] = "PASS"
    return cases


def check_query() -> dict[str, Any]:
    return {"cases": oracle_query(subject_text("runner/candidate.py")),
            "scope_note": "CoveringHTTP's own urlencode(doseq=True) is not executed; the wire form is a disclosed "
                          "source inference also enforced natively by the peer's exact query check",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# CREDENTIAL-MEASUREMENT (behavioral, named ORM/token_crypto fakes)
# ---------------------------------------------------------------------------

CRED_MODULES = ("app", "app.models", "app.services", "app.services.token_crypto")
FAKE_SETTINGS = object()


class FakeCalendarAccount:
    pass


class FakeCredentialDB:
    def __init__(self, accounts: dict[Any, Any]) -> None:
        self.accounts = accounts
        self.gets: list[Any] = []

    def get(self, model: Any, key: Any) -> Any:
        require(model is FakeCalendarAccount, "credential:model")
        self.gets.append(key)
        return self.accounts.get(key)


def fake_decrypt(settings: Any, ciphertext: str) -> str:
    require(settings is FAKE_SETTINGS and ciphertext.startswith("enc:"), "credential:decrypt input")
    return ciphertext[4:]


def measure_credential(runner_text: str, transcript_text: str, account: Any, reference: datetime) -> Any:
    ns = runner_namespace(runner_text, ("_measure_google_credential_state",))
    key = uuid.UUID(int=7)
    db = FakeCredentialDB({key: account})

    def setup(box: Sandbox) -> None:
        mods = {name: box.put(name, types.ModuleType(name)) for name in CRED_MODULES}
        mods["app.models"].CalendarAccount = FakeCalendarAccount
        mods["app.services.token_crypto"].decrypt_token = fake_decrypt
        mods["app"].models = mods["app.models"]
        mods["app"].services = mods["app.services"]
        mods["app.services"].token_crypto = mods["app.services.token_crypto"]

    def action(_t: types.ModuleType) -> Any:
        try:
            return {"value": ns["_measure_google_credential_state"](db, settings=FAKE_SETTINGS, account_id=key,
                                                                     reference_instant=reference), "raised": None}
        except BaseException as exc:  # noqa: BLE001
            return {"value": None, "raised": exc}

    return with_transcript(transcript_text, action, CRED_MODULES, setup)


def account(access: str | None, refresh: str | None, expiry: datetime | None) -> Any:
    return types.SimpleNamespace(access_token_enc=None if access is None else "enc:" + access,
                                 refresh_token_enc=None if refresh is None else "enc:" + refresh,
                                 token_expires_at=expiry)


def oracle_credential(runner_text: str) -> dict[str, str]:
    cases = {}
    transcript = subject_text("transcript/candidate.py")
    ref = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
    got = measure_credential(runner_text, transcript, account(SEED_ACCESS, SEED_REFRESH,
                                                              datetime(2026, 11, 13, 11, 0, tzinfo=timezone.utc)), ref)
    require(got["raised"] is None and got["value"] == {
        "seed_access_match": True, "seed_refresh_match": True, "refreshed_access_match": False,
        "rotated_refresh_match": False, "expiry": "2026-11-13T11:00:00+00:00", "expiry_at_or_before_reference": True},
        "credential:seed state")
    cases["seed_state"] = "PASS"
    later = datetime(2026, 11, 13, 13, 0, tzinfo=timezone.utc)
    rows = [measure_credential(runner_text, transcript, account(a, r, later), ref)["value"]
            for a, r in ((REFRESHED, ROTATED), (REFRESHED, SEED_REFRESH), (SEED_ACCESS, ROTATED))]
    require(rows[0] == {"seed_access_match": False, "seed_refresh_match": False, "refreshed_access_match": True,
                        "rotated_refresh_match": True, "expiry": "2026-11-13T13:00:00+00:00",
                        "expiry_at_or_before_reference": False}
            and (rows[1]["refreshed_access_match"], rows[1]["rotated_refresh_match"]) == (True, False)
            and (rows[2]["refreshed_access_match"], rows[2]["rotated_refresh_match"]) == (False, True),
            "credential:refreshed state")
    cases["refreshed_state_each_field_independent"] = "PASS"
    naive = measure_credential(runner_text, transcript, account(SEED_ACCESS, None, datetime(2026, 11, 13, 12, 0)), ref)
    empty = measure_credential(runner_text, transcript, account(None, None, None), ref)
    missing = measure_credential(runner_text, transcript, None, ref)
    require(naive["value"]["expiry"] == "2026-11-13T12:00:00+00:00"
            and naive["value"]["expiry_at_or_before_reference"] is True
            and naive["value"]["seed_refresh_match"] is False
            and empty["value"]["expiry"] is None and empty["value"]["expiry_at_or_before_reference"] is False
            and type(missing["raised"]) is RuntimeError, "credential:naive and absent")
    cases["naive_utc_absent_and_missing_account"] = "PASS"
    text = json.dumps([rows, naive["value"]])
    require(all(set(r) == CREDENTIAL_KEYS for r in rows + [naive["value"]])
            and not any(s in text for s in (REFRESHED, ROTATED, SEED_ACCESS, SEED_REFRESH, "enc:"))
            and all(type(v) is bool or k == "expiry" for r in rows for k, v in r.items()), "credential:no secret")
    cases["no_plaintext_or_ciphertext_emitted"] = "PASS"
    seed = subject_text("fixture/np_auth_seed.py")
    consts = runner_namespace(runner_text, ())
    require(seed.count(f'account.access_token_enc = encrypt_token(settings, "{consts["GOOGLE_SEED_ACCESS_PLAINTEXT"]}")')
            == 1 and seed.count(
                f'account.refresh_token_enc = encrypt_token(settings, "{consts["GOOGLE_SEED_REFRESH_PLAINTEXT"]}")') == 1,
            "credential:seed literals")
    cases["seed_literals_match_auth_seed"] = "PASS"
    return cases


def check_credential() -> dict[str, Any]:
    return {"cases": oracle_credential(subject_text("runner/candidate.py")),
            "scope_note": "ORM session and token_crypto are named fakes; production encryption and persistence "
                          "are not exercised",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# EVENT-MEASUREMENT (behavioral, named ORM fakes)
# ---------------------------------------------------------------------------

EVENT_MODULES = ("app", "app.models")


class FakeColumn:
    def in_(self, values: list[Any]) -> tuple[str, tuple[Any, ...]]:
        return ("in", tuple(values))


class FakeExternalCalendarEvent:
    calendar_account_id = FakeColumn()


class FakeQuery:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def filter(self, predicate: Any) -> "FakeQuery":
        require(type(predicate) is tuple and predicate[0] == "in", "events:predicate")
        return FakeQuery([r for r in self.rows if r.calendar_account_id in predicate[1]])

    def all(self) -> list[Any]:
        return list(self.rows)


class FakeEventDB:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def query(self, model: Any) -> FakeQuery:
        require(model is FakeExternalCalendarEvent, "events:model")
        return FakeQuery(self.rows)


A1, A2, O1 = uuid.UUID(int=1), uuid.UUID(int=2), uuid.UUID(int=9)


def event_row(account_id: uuid.UUID, cal: str, eid: str, start: datetime, end: datetime, **over: Any) -> Any:
    fields = {"owner_id": O1, "calendar_account_id": account_id, "provider": types.SimpleNamespace(value="google"),
              "external_event_id": eid, "calendar_id": cal, "start_time": start, "end_time": end,
              "is_all_day": False, "transparency": "opaque", "free_busy_provenance": "provider_explicit",
              "is_provider_cancelled": False, "pending_deletion": False, "scheduled_block_id": None,
              "source_zone_missing": False}
    fields.update(over)
    return types.SimpleNamespace(**fields)


def measure_events(runner_text: str, rows: list[Any], account_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    ns = runner_namespace(runner_text, ("_measure_google_events",))
    with Sandbox(EVENT_MODULES) as box:
        app = box.put("app", types.ModuleType("app"))
        models = box.put("app.models", types.ModuleType("app.models"))
        models.ExternalCalendarEvent = FakeExternalCalendarEvent
        app.models = models
        return ns["_measure_google_events"](FakeEventDB(rows), account_ids=account_ids)


def oracle_events(runner_text: str) -> dict[str, str]:
    cases = {}
    utc = timezone.utc
    rows = [event_row(A1, "cal-b", "np-google-busy-2", datetime(2026, 11, 20, 12, tzinfo=utc),
                      datetime(2026, 11, 20, 13, tzinfo=utc)),
            event_row(A2, "cal-a", "other", datetime(2026, 11, 20, 9, tzinfo=utc), datetime(2026, 11, 20, 10, tzinfo=utc)),
            event_row(A1, "cal-a", "np-google-busy-1", datetime(2026, 11, 20, 10, tzinfo=utc),
                      datetime(2026, 11, 20, 11, tzinfo=utc))]
    got = measure_events(runner_text, rows, [A1])
    require([(g["calendar_id"], g["external_event_id"]) for g in got] == [("cal-a", "np-google-busy-1"),
                                                                           ("cal-b", "np-google-busy-2")]
            and all(g["calendar_account_id"] == str(A1) and g["owner_id"] == str(O1) and g["provider"] == "google"
                    for g in got) and measure_events(runner_text, rows, [A2])[0]["external_event_id"] == "other",
            "events:filter and sort")
    cases["account_filter_and_sort"] = "PASS"
    plus2 = timezone(timedelta(hours=2))
    odd = [event_row(A1, "cal-a", "x", datetime(2026, 11, 20, 10), datetime(2026, 11, 20, 13, tzinfo=plus2),
                     scheduled_block_id=uuid.UUID(int=5), pending_deletion=1, source_zone_missing=0)]
    got = measure_events(runner_text, odd, [A1])[0]
    expected_form = datetime.fromisoformat("2026-11-20T10:00:00Z".replace("Z", "+00:00")).isoformat()
    require(got["start_utc"] == "2026-11-20T10:00:00+00:00" == expected_form
            and got["end_utc"] == "2026-11-20T11:00:00+00:00"
            and got["scheduled_block_absent"] is False and got["pending_deletion"] is True
            and got["source_zone_missing"] is False
            and set(got) == {"owner_id", "calendar_account_id", "provider", "external_event_id", "calendar_id",
                             "start_utc", "end_utc", "is_all_day", "transparency", "free_busy_provenance",
                             "is_provider_cancelled", "pending_deletion", "scheduled_block_absent",
                             "source_zone_missing"}, "events:utc and flags")
    cases["utc_normalization_flags_and_expected_form"] = "PASS"
    return cases


def check_events() -> dict[str, Any]:
    return {"cases": oracle_events(subject_text("runner/candidate.py")),
            "scope_note": "the ORM query is a named fake; production import mapping (provenance, zone flags) is a "
                          "disclosed source inference, not proved here",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# PARENT-OBSERVER (behavioral, named CoveringParentAdapter fake)
# ---------------------------------------------------------------------------

PARENT_MODULES = ("app", "app.services", "app.services.covering_parent_adapter")


class FakeTerminal(enum.Enum):
    COMMIT_ACKNOWLEDGED = "commit"
    ROLLBACK_ACKNOWLEDGED = "rollback"


def run_parent(runner_text: str, behaviour: Callable[[Any, bool], Any]) -> dict[str, Any]:
    ns = runner_namespace(runner_text, ("_install_google_parent_observer",))

    class FakeAdapter:
        def finish_root(self, *, commit):
            return behaviour(self, commit)

    original = FakeAdapter.__dict__["finish_root"]
    terminals: list[dict[str, Any]] = []
    with Sandbox(PARENT_MODULES) as box:
        mods = {name: box.put(name, types.ModuleType(name)) for name in PARENT_MODULES}
        mods["app.services.covering_parent_adapter"].CoveringParentAdapter = FakeAdapter
        mods["app"].services = mods["app.services"]
        mods["app.services"].covering_parent_adapter = mods["app.services.covering_parent_adapter"]
        restore = ns["_install_google_parent_observer"](terminals)
        installed = FakeAdapter.__dict__["finish_root"] is not original
        outcome: dict[str, Any] = {"value": None, "raised": None}
        try:
            outcome["value"] = FakeAdapter().finish_root(commit=True)
        except BaseException as exc:  # noqa: BLE001
            outcome["raised"] = exc
        restore()
    return {**outcome, "terminals": terminals, "installed": installed,
            "restored": FakeAdapter.__dict__["finish_root"] is original}


def oracle_parent(runner_text: str) -> dict[str, str]:
    cases = {}
    got = run_parent(runner_text, lambda self, commit: FakeTerminal.COMMIT_ACKNOWLEDGED)
    require(got["value"] is FakeTerminal.COMMIT_ACKNOWLEDGED and got["raised"] is None
            and got["terminals"] == [{"terminal": "COMMIT_ACKNOWLEDGED", "commit_requested": True}],
            "parent:same return")
    cases["same_return_recorded"] = "PASS"
    boom = LookupError("fixture")

    def raising(self: Any, commit: bool) -> Any:
        raise boom

    got = run_parent(runner_text, raising)
    require(got["raised"] is boom and got["terminals"] == [{"raised": "LookupError", "commit_requested": True}],
            "parent:same exception")
    cases["same_exception_recorded"] = "PASS"
    require(got["installed"] is True and got["restored"] is True, "parent:restore")
    cases["installed_then_restored_identity"] = "PASS"
    return cases


def check_parent() -> dict[str, Any]:
    return {"cases": oracle_parent(subject_text("runner/candidate.py")),
            "scope_note": "the adapter is a named fake; the native PARENT sequence is a source-derived expectation",
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# CASE-WIRING (structural; the case body is not executed)
# ---------------------------------------------------------------------------

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


def _kw(call: ast.Call, name: str) -> ast.AST:
    return _single([k.value for k in call.keywords if k.arg == name], f"keyword {name}")


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


PEER_GUARD = """
    int(peer_state.get("connection_count_admitted") or 0) != GOOGLE_REFRESH_EXCHANGE_COUNT
    or int(peer_state.get("connection_count_served") or 0) != GOOGLE_REFRESH_EXCHANGE_COUNT
    or [row.get("method") for row in peer_exchanges] != ["POST", "GET", "GET"]
    or peer_exchanges[0].get("path") != "/token"
    or any(row.get("query_verified") is not True for row in peer_exchanges[1:])
    or any(row.get("close_mode_observed") != "orderly_close_notify" for row in peer_exchanges)
    or peer_state.get("bytes_sent") != expected_bytes_sent
"""
CREDENTIAL_GUARD = """
    cred_after["refreshed_access_match"] is not True
    or cred_after["rotated_refresh_match"] is not True
    or cred_after["seed_access_match"] is not False
    or cred_after["seed_refresh_match"] is not False
    or expiry_after is None
    or not expiry_after > datetime.now(timezone.utc) + timedelta(seconds=30)
"""


def oracle_wiring(runner_text: str) -> dict[str, str]:
    cases = {}
    fn = unit_node(runner_text, RUN_FN)
    implemented = ast.literal_eval(unit_node(runner_text, "IMPLEMENTED_CASE_IDS").value.args[0])
    mapper = unit_node(runner_text, "_make_implemented_case")
    require(implemented == {"NP-V-MS-NONEXPIRED", CASE_ID} and len(_calls(mapper, RUN_FN)) == 1
            and f'"{CASE_ID}"' in unit_text(runner_text, "_make_implemented_case"), "wiring:case mapping")
    cases["case_mapping_exact"] = "PASS"
    oracle_call = _single(_calls(fn, "check_oracles_immediate"), "oracle check")
    receipt = _single(_calls(fn, "case_result_receipt"), "receipt")
    declared = suite_oracles(subject_text("suite/candidate.py"), CASE_ID)
    require(declared == suite_oracles(subject_text("suite/source.py"), CASE_ID)
            == ["owning_google_refresh", "token_commit_not_ms_proof"]
            and _dict_keys(oracle_call.args[1]) == set(declared)
            and _dict_keys(_kw(receipt, "observations")) == {"owning_google_refresh"}, "wiring:oracle names")
    cases["oracle_names_equal_declarations"] = "PASS"
    build = _single(_calls(fn, "build_i01_asgi_app"), "asgi build")
    post = [c for c in _calls(fn, "post") if isinstance(c.func, ast.Attribute)
            and isinstance(c.func.value, ast.Name) and c.func.value.id == "client"]
    require(isinstance(_kw(build, "clock"), ast.Name) and _kw(build, "clock").id == "monotonic"
            and len(_calls(fn, "install_binding")) == 1 and len(_calls(fn, "CoveringReleasePlan")) == 1
            and len(post) == 1 and isinstance(post[0].args[0], ast.Name) and post[0].args[0].id == "COVERING_PATH"
            and "inspect.signature(CoveringHTTP.__init__).parameters[\"transport_factory\"].default is not JoinedTLS"
            in unit_text(runner_text, RUN_FN)
            and "if self.transport_factory is not JoinedTLS:" in unit_text(runner_text, RUN_FN)
            and not _calls(fn, "transport_factory"), "wiring:production ingress")
    cases["production_ingress_and_default_tls"] = "PASS"
    helper = _calls(fn, "_retire_selected_peer_then_observe")
    owned = _calls(fn, "retire_owned")
    final = [n for n in ast.walk(fn) if isinstance(n, ast.Try) and n.finalbody]
    guard = [n for t in final for n in ast.walk(ast.Module(body=t.finalbody, type_ignores=[]))
             if isinstance(n, ast.If) and ast.dump(n.test) == _expr(
                 "not retirement_attempted and peer._worker is not None and not peer.life.joined")]
    require(len(helper) == 1 and len(owned) == 1 and len(guard) == 1
            and owned[0] in list(ast.walk(guard[0])), "wiring:single retirement")
    cases["single_retirement_paths"] = "PASS"
    ns = runner_namespace(runner_text, ())
    require(ns["GOOGLE_CLIENT_PURPOSES"] == [("POST", "oauth"), ("GET", "event"), ("GET", "event")]
            and ns["GOOGLE_TOKEN_TERMINAL_SEQUENCE"] == [
                {"terminal": "COMMIT_ACKNOWLEDGED", "token_rollback_ack": False, "commit_requested": True},
                {"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True, "commit_requested": False}]
            and ns["GOOGLE_PARENT_TERMINAL_SEQUENCE"] == [{"terminal": "COMMIT_ACKNOWLEDGED",
                                                           "commit_requested": True}] * 2
            and ns["GOOGLE_ACTION_SUMMARY"] == {"requested": 2, "preflight_rejected": 0, "import_attempted": 2,
                                                "import_ok": 2, "import_failed": 0}
            and set(ns["GOOGLE_CREDENTIAL_SEMANTIC_KEYS"]) == CREDENTIAL_KEYS - {"expiry_at_or_before_reference"}
            and ns["GOOGLE_EVENT_IDS"] == ("np-google-busy-1", "np-google-busy-2"), "wiring:sequences")
    cases["sequences_and_summary_literal"] = "PASS"
    seed_fn = unit_node(subject_text("fixture/np_auth_seed.py"), "seed_browser_owner_with_subscriptions")
    params = {a.arg for a in seed_fn.args.args + seed_fn.args.kwonlyargs}
    browser = unit_node(subject_text("fixture/np_auth_seed.py"), "BrowserSeed")
    fields = {n.target.id for n in browser.body if isinstance(n, ast.AnnAssign)}
    used = {a.attr for a in ast.walk(fn) if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)
            and a.value.id in ("seed", "unrelated")}
    calls = _calls(fn, "seed_browser_owner_with_subscriptions")
    require(len(calls) == 2 and all({k.arg for k in c.keywords} <= params for c in calls) and used <= fields,
            "wiring:seed signature")
    cases["seed_arguments_match_signature"] = "PASS"
    unresolved = set()
    for name in RUNNER_ADDED - set(RUNNER_CONSTANT_UNITS):
        unresolved |= free_names(unit_node(runner_text, name)) - module_level_names(runner_text)
    require(not unresolved, f"wiring:free names:{sorted(unresolved)}")
    cases["free_names_resolve"] = "PASS"
    unrelated = guard_tests(fn, "unrelated owner/account data changed")
    unrelated_cred = guard_tests(fn, "unrelated account credential changed")
    require(unrelated == [_expr('after["unrelated_coverage"] != before["unrelated_coverage"] or after["unrelated_events"]')]
            and unrelated_cred == [_expr('any(after["unrelated_credential"][key] != before["unrelated_credential"][key] '
                                         'for key in GOOGLE_CREDENTIAL_SEMANTIC_KEYS)')]
            and guard_tests(fn, "imported Google events do not match the declared busy events exactly")
            == [_expr('after["events"] != expected_events')]
            and guard_tests(fn, "refreshed Google credential not persisted semantically with a future expiry")
            == [_expr(CREDENTIAL_GUARD)], "wiring:unrelated and semantic guards")
    cases["unrelated_and_semantic_guards_exact"] = "PASS"
    require(guard_tests(fn, "peer inventory is not token POST plus two exact one-page event GETs") == [_expr(PEER_GUARD)],
            "wiring:peer inventory guard")
    cases["peer_inventory_guard_exact"] = "PASS"
    wanted = ("restore_parent_observer()", "restore_worker_observer()", "CoveringHTTP.__init__ = real_init")
    restoring = [t for t in final if all(w in "\n".join(ast.unparse(s) for s in t.finalbody) for w in wanted)]
    require(len(restoring) == 1 and len(post) == 1
            and any(n is post[0] for s in restoring[0].body for n in ast.walk(s)), "wiring:observers restored")
    cases["observers_restored_in_finally"] = "PASS"
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
    in_memory = set(map(id, ast.walk(oracle_call)))
    keys = [k.value for node in ast.walk(fn) if isinstance(node, ast.Dict) and id(node) not in in_memory
            for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    for name in ("_measure_google_credential_state", "_measure_google_events", "_install_google_parent_observer"):
        keys += [k.value for node in ast.walk(unit_node(runner_text, name)) if isinstance(node, ast.Dict)
                 for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    consts = runner_namespace(runner_text, ())
    for seq in ("GOOGLE_TOKEN_TERMINAL_SEQUENCE", "GOOGLE_PARENT_TERMINAL_SEQUENCE"):
        keys += [k for row in consts[seq] for k in row]
    keys += list(consts["GOOGLE_ACTION_SUMMARY"])
    require(len(keys) > 40 and "token_terminal" in keys and not [k for k in keys if ns["_forbidden_key"](k)],
            "retention:no forbidden key")
    cases["every_emitted_key_survives"] = "PASS"
    sample = {"token_terminal": consts["GOOGLE_TOKEN_TERMINAL_SEQUENCE"], "oauth_request_count": 1,
              "parent_terminal_sequence": consts["GOOGLE_PARENT_TERMINAL_SEQUENCE"],
              "credential_state_after": {"refreshed_access_match": True, "rotated_refresh_match": True,
                                         "seed_access_match": False, "seed_refresh_match": False,
                                         "expiry": "2026-11-13T13:00:00+00:00"},
              "token_terminal_sequence": [1], "token_commit_not_ms_proof": "OBSERVED",
              "nested": {"refresh_token": "R", "ok": 1}}
    out = ns["redact_mapping"](sample)
    require(all(out[k] == sample[k] for k in ("token_terminal", "oauth_request_count", "parent_terminal_sequence",
                                               "credential_state_after"))
            and "token_terminal_sequence" not in out and "token_commit_not_ms_proof" not in out
            and out["nested"] == {"ok": 1}, "retention:typed evidence survives")
    cases["typed_evidence_survives_disclosed_drops"] = "PASS"
    return cases


def check_retention() -> dict[str, Any]:
    return {"cases": oracle_retention(subject_text("runner/candidate.py")),
            "disclosure": "token_commit_not_ms_proof is enforced in memory only; its evidence is retained under "
                          "the allowlisted token_terminal key",
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
            and src.get("launch_ready") is True and src.get("case_ids") == ["NP-V-MS-NONEXPIRED"]
            and {k: v for k, v in cfg.items() if k not in ("case_ids", "launch_ready")}
            == {k: v for k, v in src.items() if k not in ("case_ids", "launch_ready")}, "config:runner")
    cases["runner_config"] = "PASS"
    raw = subject_text("config/candidate-launch-config.json")
    launch, src_launch = json.loads(raw), json.loads(subject_text("config/source-launch-config.json"))
    note = str(launch.get("candidate_note"))
    require(launch.get("launch_ready") is False and launch.get("candidate_launch_ready_staged") is False
            and launch.get("launch_authorized") is False and launch.get("human_launch_authorized") is False
            and launch.get("case_ids") == [CASE_ID] and launch.get("batch_id") == "np-v-google-refresh-single-case"
            and launch.get("implementation_increment", {}).get("implemented_case_ids") == ["NP-V-MS-NONEXPIRED", CASE_ID]
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and OWN_ROOT in str(launch.get("docker_ops_config_path")) and OWN_ROOT in str(launch.get("receipt_directory"))
            and "host launch_ready=false" in note and "runner-config launch_ready=false" in note
            and SOURCE_ROOT not in str(launch.get("docker_ops_config_path"))
            and SOURCE_ROOT not in str(launch.get("receipt_directory"))
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
    cases["api_peer_seed_sanitizer_immutable"] = "PASS"
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


MUTANT_KINDS = {"refresh_token_omitted": "behavioral", "query_param_changed": "behavioral",
                "rotated_compared_to_access": "behavioral", "parent_exception_swallowed": "behavioral",
                "event_sort_dropped": "behavioral", "token_key_unallowlisted": "structural_with_actual_sanitizer",
                "second_retirement": "structural", "unrelated_events_check_dropped": "structural"}


def check_mutants() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    transcript = subject_text("transcript/candidate.py")
    mutants = {
        "refresh_token_omitted": (lambda: oracle_transcript(_mutate(transcript, M_REFRESH_OMITTED)),
                                  "transcript:token body"),
        "query_param_changed": (lambda: oracle_query(_mutate(runner, M_QUERY_WRONG)), "query:literal"),
        "rotated_compared_to_access": (lambda: oracle_credential(_mutate(runner, M_ROTATED_VS_ACCESS)),
                                       "credential:refreshed state"),
        "parent_exception_swallowed": (lambda: oracle_parent(_mutate(runner, M_PARENT_SWALLOW)),
                                       "parent:same exception"),
        "event_sort_dropped": (lambda: oracle_events(_mutate(runner, M_SORT_DROPPED)), "events:filter and sort"),
        "token_key_unallowlisted": (lambda: oracle_retention(_mutate(runner, M_KEY_UNALLOWLISTED)),
                                    "retention:no forbidden key"),
        "second_retirement": (lambda: oracle_wiring(_mutate(runner, M_SECOND_RETIRE)), "wiring:single retirement"),
        "unrelated_events_check_dropped": (lambda: oracle_wiring(_mutate(runner, M_UNRELATED_DROPPED)),
                                           "wiring:unrelated and semantic guards"),
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
    require(expected.get("kind") == "native-google-refresh-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "TRANSCRIPT-SCRIPTS": check_transcript,
        "ROUTES-AND-QUERY": check_query,
        "CREDENTIAL-MEASUREMENT": check_credential,
        "EVENT-MEASUREMENT": check_events,
        "PARENT-OBSERVER": check_parent,
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
