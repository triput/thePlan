#!/usr/bin/env python3
"""HELD fake-only checker for the native MS invalid_grant (NP-V-MS-INVALID) preparation.

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned): source = frozen T05 v3 roles (runner 4, suite 5, transcript 8,
runner-config, payload manifest), candidate = scheduler-native-provider-ms-invalid-prep-
matt-v1 roles, their unified diffs, role 10 np_auth_seed and role 7 peer (unchanged;
loading/serializer), the candidate launch-config, and the unchanged application
subjects covering_http_transport/policy/joined_https, microsoft_calendar,
covering_domain_adapters, covering_refresh_import, covering_refresh and
covering_domain_dispatch.

Execution surfaces (all fake; no socket, SSL context, TLS, DB or provider):
- BEHAVIORAL host parser: the whole actual covering policy/transport modules in an
  exact sys.modules sandbox with fake app/httpx imports and an injected byte-buffer
  transport, through the ACTUAL host http.client parser and ACTUAL json.loads.
  Importing http.client transitively loads socket and ssl; none is constructed.
- BEHAVIORAL extracted units with named fakes: microsoft_calendar refresh path,
  covering_domain_adapters token port, covering_refresh preflight row/outcome.
- STRUCTURAL source checks (AST/text only): JoinedTLS.send sent-marking order,
  dispatch TokenRejected skip, runner body wiring/observer restoration.
- Whole stdlib-only fixture modules np_auth_seed and np_provider_transcript.
Structural checks are reported as structural; they are not behavioral proof.

Proof scope: finite fixture/source properties of the invalid_grant classification,
token-port rollback request, no-write refresh path, preflight result shape and runner
wiring. NOT proved: native TLS, the native client exception at runtime, native
PostgreSQL ROLLBACK acknowledgement, persisted DB state, ASGI response, peer or
worker retirement, or any requirement beyond these finite fixture properties.
"""
from __future__ import annotations

import ast
import email.feedparser
import email.parser
import enum
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
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-native-ms-invalid-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/source.py": "1D70164C8EFD7D1CD0A9ED59F23D9F8A4ED9F68B806364B366E2E707259AAA7E",
    "runner/candidate.py": "ACD7F4493492DC01406558374E4B2EC46E8CDDA59FAE4FD2195FC0B154006FF1",
    "transcript/source.py": "562F61CDB9DEF3F35A1693E3C9CC13EB63D9F0535F9A0D3C190BF275E78751BF",
    "transcript/candidate.py": "BEDCCFD3C3E8F776C4EC0B3379F863E976C73AF350DD6AE8B308518AB4A47735",
    "suite/source.py": "9AED74EE4F00C5F88518A1B246D7B03D5E82C05DDF3596958D5483730C376792",
    "suite/candidate.py": "DAB88CB352189411EED6A2181417CB813D592406598D89192FF307E9081205A1",
    "config/source-runner-config.json": "96782CB425239BC6F121949DABE16B4B53528E249BE625DD25A9811DA7D07E71",
    "config/candidate-runner-config.json": "10106B8278033FC0DBC83D5841446F2D2B7476960C90DB654AF4AAF25549E004",
    "config/candidate-launch-config.json": "5ECEBDF37270C9ADBB46573C3507FA25354189188FEB79CF167E2155A95A3D4D",
    "manifest/source.txt": "D03EA0D671DF61AB3E66B2E3B96D34B72AC9BDAF6282676A8A1328DEF853B0C5",
    "manifest/candidate.txt": "8A1FCA71DBD9DB51293E36691DD8DAB1757BB4CCD1A84E1C2F3636CA3F5B880D",
    "diff/np_runner_entry.py.diff": "02BD2B24A662D1883CE59866722590088B3912B9804FE7406877BA436FD37EE6",
    "diff/np_provider_transcript.py.diff": "B5F064F528CDE6116DFE1FEA4E302A798892E17F5F3136BEFFAF7BC4A8A00A25",
    "diff/np_suite.py.diff": "E0527D3D5427B58C8F65D390C4C90114598CCA08DC7156A7BEC372F5678E921F",
    "diff/runner-config.json.diff": "5791715D4C3C1034A51F6B90FA42FCFD3916D9A32B4281FBD079802490547FFC",
    "fixture/np_auth_seed.py": "2ADFA3ADCFDA8DB4D9D32EDFC9950AF354CE29ADFA1B5A8162FD5182DC22ED05",
    "peer/source.py": "BFB271D770D08BC161E9613564ECA799B7E28884D8211E10228F5973A4A271BF",
    "app/covering_http_transport.py": "29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368",
    "app/covering_transport_policy.py": "5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88",
    "app/covering_joined_https.py": "760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427",
    "app/microsoft_calendar.py": "6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF",
    "app/covering_domain_adapters.py": "BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C",
    "app/covering_refresh_import.py": "84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339",
    "app/covering_refresh.py": "0605E983F728D99D90BD50CCB85A6FC71509FCFBC0ADF50B7C2E3280E3603E5E",
    "app/covering_domain_dispatch.py": "E73EFF6812A191F3F03431B98990BBF3C61D09D8398101AC804DBD2B2E7F6566",
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
    "SCRIPT-SELECTION",
    "CLIENT-OAUTH-CLASSIFICATION",
    "OWNING-REFRESH-UNITS",
    "PUBLIC-RESULT-CONTRACT",
    "RUNNER-WIRING",
    "BATCH-CONFIG",
    "PRIOR-FAKE-APPLICABILITY",
    "ACTUAL-SOURCE-MUTANTS",
)

CASE_ID = "NP-V-MS-INVALID"
INVALID_SCRIPT = "MS-TOKEN-INVALID-GRANT"
TENANTLESS_PATH = "/oauth2/v2.0/token"
TOKEN_HOST = "login.microsoftonline.com"
EXPECTED_INVALID_GRANT_WIRE = (b"HTTP/1.1 400 OK\r\nContent-Type: application/json\r\nContent-Length: 25\r\n"
                               b"Connection: close\r\n\r\n{\"error\":\"invalid_grant\"}")
PREFLIGHT_CODE = "CALENDAR_ACCOUNT_DISCONNECTED"
STEP_FIELDS = ("direction", "method", "path", "status", "headers", "body_template", "close_mode", "note")
OWN_ROOT = "scheduler-native-provider-ms-invalid-prep-matt-v1"
FOREIGN_ROOTS = ("t05-prep-matt-v1", "t05-prep-matt-v2", "t05-prep-matt-v3", "ms-merge-nonexpired-prep-matt-v1",
                 "ms-merge-refresh-prep-matt-v1", "peer-close-prep-matt-v1", "peer-close-launch-dex-v1",
                 "scheduler-ms-refresh-prep-matt-v1")
CHANGED_PAYLOAD_ROWS = {
    "fixture/np_runner_entry.py": "runner/candidate.py",
    "fixture/np_provider_transcript.py": "transcript/candidate.py",
    "fixture/np_suite.py": "suite/candidate.py",
    "runner-config.json": "config/candidate-runner-config.json",
}
EXPECTED_CONSTANTS = {
    "MS_INVALID_CLIENT_OUTCOME": ("exception", "CoveringReauthorizationRequired",
                                  "app.services.covering_transport_policy"),
    "MS_INVALID_TOKEN_TERMINAL_ROWS": [{"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True,
                                        "commit_requested": False}],
    "MS_INVALID_TERMINAL_OBSERVER_ROWS": [{"observer": "CoveringORMConnection.token_terminal", "terminal": None}],
    "MS_INVALID_PREFLIGHT_CODE": PREFLIGHT_CODE,
    "MS_INVALID_ACTION_SUMMARY": {"requested": 1, "preflight_rejected": 1, "import_attempted": 0,
                                  "import_ok": 0, "import_failed": 0},
    "MS_INVALID_CREDENTIAL_SEMANTIC_KEYS": ("seed_access_match", "seed_refresh_match", "refreshed_access_match",
                                            "rotated_refresh_match", "expiry"),
}
RESTORES = ("CoveringHTTP.__init__ = real_init", "CoveringORMConnection.token_terminal = real_terminal",
            "CoveringRoleConnector.run_target = real_run_target")
SAVES = ("real_init = CoveringHTTP.__init__", "real_terminal = CoveringORMConnection.token_terminal",
         "real_run_target = CoveringRoleConnector.run_target")

# Mutation anchors (statically read; each unique within the text it edits).
M_PATH_REVERTED = ('        purpose="microsoft_token_invalid_grant",\n        steps=(\n'
                   '            ExchangeStep("recv_request", method="POST", path=MS_TOKEN_ENDPOINT_PATH),',
                   '        purpose="microsoft_token_invalid_grant",\n        steps=(\n'
                   '            ExchangeStep("recv_request", method="POST", path="/oauth2/v2.0/token"),')
M_ANY_400 = ('                if response.status!=400 or decoded.get("error")!="invalid_grant":\n',
             '                if response.status!=400:\n')
M_SEND_STATE = ('            if purpose=="oauth" and transport.sent:\n', '            if purpose=="oauth":\n')
M_ADAPTER_CHANGED = ('                except CoveringReauthorizationRequired:\n                    changed=False\n',
                     '                except CoveringReauthorizationRequired:\n                    changed=True\n')
M_ADAPTER_REMOVED = ('                except CoveringReauthorizationRequired:\n                    changed=False\n',
                     '                except ZeroDivisionError:\n                    changed=False\n')
M_JOINED_ORDER = ('                self.sent=True\n                count=self.sock.send(data)\n',
                  '                count=self.sock.send(data)\n                self.sent=True\n')
M_TERMINAL_COMMIT = ('{"terminal": "ROLLBACK_ACKNOWLEDGED", "token_rollback_ack": True, "commit_requested": False},',
                     '{"terminal": "COMMIT_ACKNOWLEDGED", "token_rollback_ack": False, "commit_requested": True},')
M_RESTORE_REMOVED = ('    finally:\n        CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]\n'
                     '        CoveringORMConnection.token_terminal = real_terminal  # type: ignore[method-assign]\n',
                     '    finally:\n        CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]\n')
M_SWALLOW = ('                    client_outcomes.append(\n'
             '                        ("exception", type(exc).__name__, type(exc).__module__)\n'
             '                    )\n                    raise\n',
             '                    client_outcomes.append(\n'
             '                        ("exception", type(exc).__name__, type(exc).__module__)\n'
             '                    )\n                    return None\n')
M_TWO_SUBS = ('            username_prefix="np-ms-invalid",\n            subscription_count=1,\n',
              '            username_prefix="np-ms-invalid",\n            subscription_count=2,\n')


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
        "transcript": ("transcript/source.py", "transcript/candidate.py", "diff/np_provider_transcript.py.diff",
                       "payload/fixture/np_provider_transcript.py", 2),
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
    segment = ast.get_source_segment(text, unit_node(text, name), padded=True)
    require(segment is not None, f"no segment:{name}")
    return textwrap.dedent(segment)


def exec_units(text: str, names: tuple[str, ...], namespace: dict[str, Any], label: str) -> dict[str, Any]:
    """Compile each extracted unit with postponed annotations (annotations stay strings)."""
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


def dump_expr(snippet: str) -> str:
    return ast.dump(ast.parse(snippet, mode="eval").body)


def dump_stmt(snippet: str) -> str:
    return ast.dump(_single(ast.parse(textwrap.dedent(snippet)).body, "snippet"))


def _mutate(text: str, mutation: tuple[str, str]) -> str:
    require(text.count(mutation[0]) == 1, f"mutation anchor not unique:{mutation[0]!r}")
    return text.replace(*mutation)


def check_preserved_outside_change() -> dict[str, Any]:
    expected = {
        "runner": ({"IMPLEMENTED_CASE_IDS", "MS_INVALID_CLIENT_OUTCOME", "MS_INVALID_TOKEN_TERMINAL_ROWS",
                    "MS_INVALID_TERMINAL_OBSERVER_ROWS", "MS_INVALID_PREFLIGHT_CODE", "MS_INVALID_ACTION_SUMMARY",
                    "MS_INVALID_CREDENTIAL_SEMANTIC_KEYS", "_run_np_v_ms_invalid", "_make_implemented_case"},
                   {"IMPLEMENTED_CASE_IDS", "_make_implemented_case"}),
        "transcript": ({"ms_token_invalid_grant_script", "MS_INVALID_GRANT_EXCHANGE_COUNT",
                        "ms_invalid_grant_connection_inventory"}, {"ms_token_invalid_grant_script"}),
        "suite": ({"CASE_IMPLEMENTATION_NOTES"}, {"CASE_IMPLEMENTATION_NOTES"}),
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


FIXTURE_NAMES = ("np_auth_seed", "np_provider_transcript")


def load_transcript(text: str, label: str) -> dict[str, Any]:
    with Sandbox(FIXTURE_NAMES) as box:
        box.load("np_auth_seed", subject_text("fixture/np_auth_seed.py"), "<subject:np_auth_seed>")
        module = box.load("np_provider_transcript", text, f"<subject:transcript:{label}>")
        result = {
            "token_path": module.MS_TOKEN_ENDPOINT_PATH,
            "invalid": module.ms_token_invalid_grant_script(),
            "catalog": list(module.finite_script_catalog()),
            "inventory": (list(module.ms_invalid_grant_connection_inventory())
                          if hasattr(module, "ms_invalid_grant_connection_inventory") else None),
            "inventory_count": getattr(module, "MS_INVALID_GRANT_EXCHANGE_COUNT", None),
        }
    require(all(name not in sys.modules for name in FIXTURE_NAMES), "fixture sandbox restored")
    return result


class PeerLifecycleError(RuntimeError):
    pass


def serializer() -> Callable[[Any], bytes]:
    text = subject_text("peer/source.py")
    namespace: dict[str, Any] = {"PeerLifecycleError": PeerLifecycleError, "Any": Any, "ExchangeStep": object}
    exec(compile(unit_text(text, "RESPONSE_FRAMING_MODES"), "<extracted:peer:modes>", "exec"), namespace)
    exec(compile(unit_text(text, "_http_response_bytes"), "<extracted:peer:_http_response_bytes>", "exec"),
         namespace)
    return namespace["_http_response_bytes"]


def step_fields(step: Any) -> tuple[Any, ...]:
    return tuple(getattr(step, name) for name in STEP_FIELDS) + (getattr(step, "framing", "auto"),)


def by_direction(script: Any, direction: str) -> Any:
    return _single([s for s in script.steps if s.direction == direction], f"{direction} step")


# ---------------------------------------------------------------------------
# SCRIPT-SELECTION (whole transcript module; extracted unchanged peer serializer)
# ---------------------------------------------------------------------------

def oracle_selection(cand_text: str) -> dict[str, str]:
    cases = {}
    src, cand = load_transcript(subject_text("transcript/source.py"), "source"), load_transcript(cand_text, "candidate")
    c_req, s_req = by_direction(cand["invalid"], "recv_request"), by_direction(src["invalid"], "recv_request")
    require(c_req.path == cand["token_path"] and c_req.path != TENANTLESS_PATH and c_req.method == "POST"
            and s_req.path == TENANTLESS_PATH and cand["token_path"] == src["token_path"],
            "selection:tenant path")
    cases["tenant_path_fix"] = "PASS"
    require(cand["invalid"].script_id == src["invalid"].script_id == INVALID_SCRIPT
            and cand["invalid"].purpose == src["invalid"].purpose
            and [s.direction for s in cand["invalid"].steps] == ["recv_request", "send_response", "close"]
            and all(step_fields(c) == step_fields(s) for c, s in zip(cand["invalid"].steps, src["invalid"].steps)
                    if c.direction != "recv_request")
            and step_fields(c_req)[:2] == step_fields(s_req)[:2] and step_fields(c_req)[3:] == step_fields(s_req)[3:],
            "selection:only request path changed")
    cases["only_request_path_changed"] = "PASS"
    ser = serializer()
    c_send, s_send = by_direction(cand["invalid"], "send_response"), by_direction(src["invalid"], "send_response")
    wire = ser(c_send)
    require(wire == EXPECTED_INVALID_GRANT_WIRE and wire == ser(s_send) and c_send.status == 400
            and by_direction(cand["invalid"], "close").close_mode == "orderly_close_notify",
            "selection:exact wire")
    cases["exact_wire"] = "PASS"
    require(cand["inventory"] is not None and [s.script_id for s in cand["inventory"]] == [INVALID_SCRIPT]
            and cand["inventory_count"] == 1, "selection:one exchange inventory")
    cases["one_exchange_inventory"] = "PASS"
    require([s.script_id for s in cand["catalog"]] == [s.script_id for s in src["catalog"]]
            and all([step_fields(x) for x in c.steps] == [step_fields(y) for y in s.steps]
                    for c, s in zip(cand["catalog"], src["catalog"]) if c.script_id != INVALID_SCRIPT),
            "selection:catalog other scripts unchanged")
    cases["catalog_other_scripts_unchanged"] = "PASS"
    return cases


def check_selection() -> dict[str, Any]:
    return {"cases": oracle_selection(subject_text("transcript/candidate.py")), "control_kind": "whole_module_fake",
            "observed": "PASS"}


# ---------------------------------------------------------------------------
# CLIENT-OAUTH-CLASSIFICATION: actual policy/transport over the host parser
# ---------------------------------------------------------------------------

APP_NAMES = ("app", "app.services", "app.services.covering_request_budget", "app.services.covering_transport_policy",
             "app.services.covering_joined_https", "app.services.covering_target_transaction", "httpx",
             "app.services.covering_http_transport")
TRANSPORT_FILE = "<subject:covering_http_transport.py>"
EVENT_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


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

    sent is False until send() is entered; send() marks sent=True BEFORE any failure,
    mirroring the actual JoinedTLS.send order (checked structurally). After the bytes,
    receive returns b"" (client-observed orderly EOF) or raises the injected object.
    """

    def __init__(self, response: bytes, after: BaseException | None, log: list[str], *,
                 open_exc: BaseException | None = None, send_exc: BaseException | None = None,
                 close_exc: BaseException | None = None) -> None:
        self.response, self.after, self.log = response, after, log
        self.open_exc, self.send_exc, self.close_exc = open_exc, send_exc, close_exc
        self.offset = 0
        self.opens = self.closes = 0
        self.sent = False

    def open(self) -> "FakeTransport":
        self.opens += 1
        if self.open_exc is not None:
            raise self.open_exc
        return self

    def send(self, data: bytes) -> None:
        self.sent = True
        if self.send_exc is not None:
            raise self.send_exc

    def receive(self, maximum: int) -> bytes:
        chunk = self.response[self.offset:self.offset + maximum]
        self.offset += len(chunk)
        if not chunk and self.after is not None:
            raise self.after
        return chunk

    def close(self) -> None:
        self.closes += 1
        self.log.append("transport_close")
        if self.close_exc is not None:
            raise self.close_exc


def token_path() -> str:
    return load_transcript(subject_text("transcript/candidate.py"), "candidate")["token_path"]


def run_client(response: bytes, *, purpose: str = "oauth", after: BaseException | None = None,
               open_exc: BaseException | None = None, send_exc: BaseException | None = None,
               close_exc: BaseException | None = None, transport_text: str | None = None) -> dict[str, Any]:
    log: list[str] = []
    path = token_path()
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
        httpx.Request, httpx.Response = FakeHttpxRequest, FakeHttpxResponse
        module = box.load("app.services.covering_http_transport",
                          transport_text if transport_text is not None else subject_text("app/covering_http_transport.py"),
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
        transport = FakeTransport(response, after, log, open_exc=open_exc, send_exc=send_exc, close_exc=close_exc)
        if purpose == "oauth":
            peer = policy.HTTPSPeer(hostname=TOKEN_HOST, address="127.0.0.1", port=443, ca_file="/fake/ca.crt")
            routes = ((peer, path, "oauth"),)
            method, url, kwargs = "POST", f"https://{TOKEN_HOST}{path}", {"data": {"grant_type": "refresh_token"}}
        else:
            peer = policy.HTTPSPeer(hostname="www.googleapis.com", address="127.0.0.1", port=443,
                                    ca_file="/fake/ca.crt")
            routes = ((peer, "/calendar/v3/calendars/", "event"),)
            method, url, kwargs = "GET", EVENT_URL, {}
        client = module.CoveringHTTP(counter=counter, routes=routes, transport_factory=lambda p, remaining: transport)
        escaped: BaseException | None = None
        result: Any = None
        try:
            result = client.request(method, url, purpose=purpose, **kwargs)
        except BaseException as exc:  # noqa: BLE001
            escaped = exc
        reauth_type = policy.CoveringReauthorizationRequired
    require(all(name not in sys.modules for name in APP_NAMES), "app sandbox restored")
    return {"escaped": escaped, "result": result, "spy": spy, "gate_calls": len(gate_calls), "log": log,
            "transport": transport, "reauth_type": reauth_type}


def wire_for(status: int, body: str, headers: tuple[tuple[str, str], ...] = (("Content-Type", "application/json"),)) -> bytes:
    step = types.SimpleNamespace(direction="send_response", status=status, headers=headers, body_template=body,
                                 framing="auto")
    return serializer()(step)


def _unknown(run: dict[str, Any]) -> bool:
    exc = run["escaped"]
    return type(exc) is FakeRootOutcomeUnknown and exc.__cause__ is None and run["transport"].closes == 1


def oracle_invalid_grant_typed(transport_text: str | None = None) -> str:
    run = run_client(EXPECTED_INVALID_GRANT_WIRE, transport_text=transport_text)
    require(type(run["escaped"]) is run["reauth_type"] and run["spy"].calls == [b'{"error":"invalid_grant"}']
            and run["gate_calls"] == 1 and run["log"] == ["gate", "json", "transport_close"]
            and run["transport"].sent is True and run["transport"].closes == 1, "client:invalid grant typed")
    return "PASS"


def oracle_other_error(transport_text: str | None = None) -> str:
    run = run_client(wire_for(400, '{"error":"invalid_request"}'), transport_text=transport_text)
    require(_unknown(run) and run["spy"].calls == [b'{"error":"invalid_request"}'] and run["gate_calls"] == 1,
            "client:other error unknown")
    return "PASS"


def oracle_open_failure(transport_text: str | None = None) -> str:
    opened = OSError("injected-open-failure")
    run = run_client(EXPECTED_INVALID_GRANT_WIRE, open_exc=opened, transport_text=transport_text)
    require(run["escaped"] is opened and run["transport"].sent is False and run["transport"].closes == 1
            and not run["spy"].calls and run["gate_calls"] == 0, "client:open failure original")
    return "PASS"


def oracle_joined_send_order(joined_text: str) -> str:
    cls = _single([n for n in ast.parse(joined_text).body if isinstance(n, ast.ClassDef) and n.name == "JoinedTLS"],
                  "JoinedTLS")
    send = _single([n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "send"], "JoinedTLS.send")
    tries = [n for n in ast.walk(send) if isinstance(n, ast.Try)]
    ok = False
    for node in tries:
        dumps = [ast.dump(s) for s in node.body]
        marks = [i for i, d in enumerate(dumps) if d == dump_stmt("self.sent=True")]
        sends = [i for i, s in enumerate(node.body) if any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "send"
            and isinstance(c.func.value, ast.Attribute) and c.func.value.attr == "sock" for c in ast.walk(s))]
        if len(marks) == 1 and len(sends) == 1 and marks[0] < sends[0]:
            ok = True
    require(ok, "client:joined send marks sent")
    return "PASS"


def check_client() -> dict[str, Any]:
    cases = {}
    cases["invalid_grant_typed"] = oracle_invalid_grant_typed()
    cases["other_error_unknown"] = oracle_other_error()
    run = run_client(wire_for(401, '{"error":"invalid_grant"}'))
    require(_unknown(run) and run["gate_calls"] == 1, "client:status 401 unknown")
    cases["status_401_unknown"] = "PASS"
    run = run_client(wire_for(400, '["invalid_grant"]'))
    require(_unknown(run) and run["spy"].calls == [b'["invalid_grant"]'], "client:nonobject unknown")
    cases["nonobject_unknown"] = "PASS"
    run = run_client(wire_for(400, '{"error":'))
    require(_unknown(run) and len(run["spy"].raised) == 1 and type(run["spy"].raised[0]) is json.JSONDecodeError,
            "client:malformed unknown")
    cases["malformed_unknown"] = "PASS"
    run = run_client(wire_for(400, '{"error":"invalid_grant"}',
                              (("Content-Type", "application/json"), ("Content-Length", "40"))))
    require(_unknown(run) and not run["spy"].calls and run["gate_calls"] == 0, "client:truncated unknown")
    cases["truncated_unknown"] = "PASS"
    run = run_client(b"", after=type("SSLEOFError", (OSError,), {})("injected-eof"))
    require(_unknown(run) and run["transport"].sent is True and not run["spy"].calls, "client:eof after send unknown")
    cases["eof_after_send_unknown"] = "PASS"
    run = run_client(EXPECTED_INVALID_GRANT_WIRE, send_exc=OSError("injected-send-failure"))
    require(_unknown(run) and run["transport"].sent is True and not run["spy"].calls and run["gate_calls"] == 0,
            "client:send failure sets sent unknown")
    cases["send_failure_sets_sent_unknown"] = "PASS"
    cases["open_failure_before_send_original"] = oracle_open_failure()
    closing = OSError("injected-close-failure")
    run = run_client(EXPECTED_INVALID_GRANT_WIRE, close_exc=closing)
    exc = run["escaped"]
    require(type(exc) is FakeRootOutcomeUnknown and type(getattr(exc, "primary", None)) is run["reauth_type"]
            and getattr(exc, "transport_close", None) is closing, "client:close failure after invalid grant unknown")
    cases["close_failure_after_invalid_grant_unknown"] = "PASS"
    run = run_client(EXPECTED_INVALID_GRANT_WIRE, purpose="event")
    require(run["escaped"] is None and type(run["result"]) is FakeHttpxResponse and run["result"].status_code == 400,
            "client:event purpose not classified")
    cases["event_purpose_not_classified"] = "PASS"
    cases["joined_send_marks_sent_before_socket_send"] = oracle_joined_send_order(subject_text("app/covering_joined_https.py"))
    return {"cases": cases, "eof_model": "fake b'' after bytes models a client-observed orderly EOF; not native TLS",
            "structural_cases": ["joined_send_marks_sent_before_socket_send"],
            "control_kind": "actual_source_host_parser", "observed": "PASS"}


# ---------------------------------------------------------------------------
# OWNING-REFRESH-UNITS: extracted production units with named fakes
# ---------------------------------------------------------------------------

_REAUTH: dict[str, type] = {}


def reauth_class() -> type:
    """The extracted policy class, built once so every unit shares one class object."""
    if "cls" not in _REAUTH:
        namespace: dict[str, Any] = {}
        exec_units(subject_text("app/covering_transport_policy.py"), ("CoveringReauthorizationRequired",), namespace,
                   "policy")
        _REAUTH["cls"] = namespace["CoveringReauthorizationRequired"]
    return _REAUTH["cls"]


class FakeApiError(Exception):
    pass


class RecordingAccount:
    def __init__(self) -> None:
        object.__setattr__(self, "writes", [])
        object.__setattr__(self, "access_token_enc", "seed-access-ciphertext")
        object.__setattr__(self, "refresh_token_enc", "seed-refresh-ciphertext")
        object.__setattr__(self, "token_expires_at", datetime.now(timezone.utc) - timedelta(hours=1))

    def __setattr__(self, name: str, value: Any) -> None:
        self.writes.append(name)
        object.__setattr__(self, name, value)


def oracle_ms_refresh_no_write() -> str:
    reauth = reauth_class()
    raised = reauth()
    calls: dict[str, list[Any]] = {"post": [], "flush": [], "validate": [], "encrypt": [], "decode": []}

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

        def post(self, url: str, **kwargs: Any) -> Any:
            calls["post"].append((url, dict(kwargs.get("data") or {})))
            raise raised

    namespace: dict[str, Any] = {
        "Any": Any, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "ApiError": FakeApiError,
        "decrypt_token": lambda settings, enc: f"plain:{enc}",
        "encrypt_token": lambda settings, value: calls["encrypt"].append(1),
        "load_microsoft_oauth_config": lambda settings: types.SimpleNamespace(
            tenant_id="np-fixture-tenant", client_id="cid", client_secret="secret", scopes="scope"),
        "calendar_client": lambda *, timeout: FakeClient(),
        "_decode_json_object": lambda *a, **k: calls["decode"].append(1),
        "_validated_oauth_token_fields": lambda *a, **k: calls["validate"].append(1),
    }
    exec_units(subject_text("app/microsoft_calendar.py"),
               ("_LOGIN_BASE", "_token_url", "refresh_access_token", "get_valid_access_token"), namespace, "ms")
    account = RecordingAccount()
    db = types.SimpleNamespace(flush=lambda: calls["flush"].append(1))
    escaped: BaseException | None = None
    try:
        namespace["get_valid_access_token"](db, settings=types.SimpleNamespace(), account=account)
    except BaseException as exc:  # noqa: BLE001
        escaped = exc
    require(escaped is raised and account.writes == [] and calls["flush"] == [] and calls["validate"] == []
            and calls["encrypt"] == [] and calls["decode"] == []
            and calls["post"] == [(f"https://{TOKEN_HOST}/np-fixture-tenant/oauth2/v2.0/token",
                                   {"client_id": "cid", "client_secret": "secret",
                                    "refresh_token": "plain:seed-refresh-ciphertext",
                                    "grant_type": "refresh_token", "scope": "scope"})],
            "units:ms refresh raises before any write")
    return "PASS"


class FakeRootOutcome(enum.Enum):
    COMMIT_ACKNOWLEDGED = enum.auto()
    ROLLBACK_ACKNOWLEDGED = enum.auto()


@dataclass(frozen=True)
class FakeTokenReady:
    access_token: str


@dataclass(frozen=True)
class FakeTokenRejected:
    code: str


def run_adapter(adapter_text: str, *, terminal_mode: str, refresh_raises: BaseException) -> dict[str, Any]:
    terminal_calls: list[bool] = []
    transport_entries: list[int] = []
    agent_writes: list[int] = []

    def terminal(*, commit: bool, remaining: Any) -> Any:
        terminal_calls.append(commit)
        if terminal_mode == "exact":
            return FakeRootOutcome.COMMIT_ACKNOWLEDGED if commit else FakeRootOutcome.ROLLBACK_ACKNOWLEDGED
        return FakeRootOutcome.COMMIT_ACKNOWLEDGED

    @contextmanager
    def locks(db: Any, **kwargs: Any) -> Any:
        yield None

    @contextmanager
    def provider_transport(transport: Any) -> Any:
        transport_entries.append(1)
        yield

    def refresh(db: Any, *, settings: Any, account: Any) -> str:
        raise refresh_raises

    target = types.SimpleNamespace(owner_id="owner", account_id="account", subscription_id="subscription")
    account = types.SimpleNamespace(owner_id="owner", access_token_enc="a", refresh_token_enc="r",
                                    token_expires_at="t")
    sub = types.SimpleNamespace(owner_id="owner", calendar_account_id="account")

    class Query:
        def __init__(self, cls: Any) -> None:
            self.cls = cls

        def filter(self, *args: Any) -> "Query":
            return self

        def populate_existing(self) -> "Query":
            return self

        def one(self) -> Any:
            return account

        def one_or_none(self) -> Any:
            return sub

    db = types.SimpleNamespace(info={"covering_token_terminal": terminal}, query=lambda cls: Query(cls))
    namespace: dict[str, Any] = {
        "CalendarAccount": type("CalendarAccount", (), {"id": object()}),
        "CalendarSubscription": type("CalendarSubscription", (), {"id": object()}),
        "CoveringDomainPorts": lambda token, locks_port, apply: types.SimpleNamespace(token=token),
        "TokenReady": FakeTokenReady, "TokenRejected": FakeTokenRejected,
        "_refresh_provider_access_token": refresh,
        "covering_import_eligibility_code": lambda account, sub, check_missing_credentials: None,
        "import_covering_subscription_cache": None,
        "covering_unit_locks": locks,
        "covering_provider_transport": provider_transport,
        "CoveringRootOutcomeUnknown": FakeRootOutcomeUnknown, "RootOutcome": FakeRootOutcome,
        "resolve_session_agent_credential": lambda db: None,
        "assert_agent_write_still_authorized": lambda db, credential: agent_writes.append(1),
        "CoveringReauthorizationRequired": reauth_class(),
    }
    exec_units(subject_text("app/covering_refresh_import.py"), ("PREFLIGHT_ACCOUNT_DISCONNECTED",), namespace,
               "refresh_import")
    exec_units(adapter_text, ("make_domain_ports",), namespace, "adapters")
    ports = namespace["make_domain_ports"](
        settings=types.SimpleNamespace(),
        transport=types.SimpleNamespace(counter=types.SimpleNamespace(admission_exhausted=False)))
    escaped: BaseException | None = None
    result: Any = None
    try:
        result = ports.token(db, target, lambda: 100.0)
    except BaseException as exc:  # noqa: BLE001
        escaped = exc
    return {"result": result, "escaped": escaped, "terminal_calls": terminal_calls,
            "transport_entries": transport_entries, "agent_writes": agent_writes}


def oracle_adapter_rollback(adapter_text: str) -> str:
    run = run_adapter(adapter_text, terminal_mode="exact", refresh_raises=reauth_class()())
    require(run["escaped"] is None and type(run["result"]) is FakeTokenRejected
            and run["result"].code == PREFLIGHT_CODE and run["terminal_calls"] == [False]
            and run["transport_entries"] == [1] and run["agent_writes"] == [], "units:adapter rejected rollback")
    return "PASS"


def check_units() -> dict[str, Any]:
    cases = {"ms_refresh_raises_before_any_write": oracle_ms_refresh_no_write()}
    adapter = subject_text("app/covering_domain_adapters.py")
    cases["adapter_rejected_rollback"] = oracle_adapter_rollback(adapter)
    run = run_adapter(adapter, terminal_mode="wrong", refresh_raises=reauth_class()())
    require(type(run["escaped"]) is FakeRootOutcomeUnknown and run["terminal_calls"] == [False],
            "units:adapter wrong terminal unknown")
    cases["adapter_wrong_terminal_unknown"] = "PASS"
    other = FakeRootOutcomeUnknown()
    run = run_adapter(adapter, terminal_mode="exact", refresh_raises=other)
    require(run["escaped"] is other and run["terminal_calls"] == [], "units:adapter other exception propagates")
    cases["adapter_other_exception_propagates"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# PUBLIC-RESULT-CONTRACT
# ---------------------------------------------------------------------------

def check_public() -> dict[str, Any]:
    cases = {}
    namespace: dict[str, Any] = {
        "ImportCoveringCacheResult": lambda **kw: types.SimpleNamespace(**kw),
        "CoveringRefreshResultRow": lambda **kw: types.SimpleNamespace(**kw),
    }
    exec_units(subject_text("app/covering_refresh_import.py"), ("OUTCOME_PREFLIGHT", "PREFLIGHT_ACCOUNT_DISCONNECTED"),
               namespace, "refresh_import")
    exec_units(subject_text("app/covering_refresh.py"),
               ("_static_preflight_result", "_result_row", "_derive_overall_outcome"), namespace, "refresh")
    window = types.SimpleNamespace(effective_start="s", effective_end="e", widened=False, reason=None)
    result = namespace["_static_preflight_result"](subscription_id="sub-1", window=window,
                                                   preflight_code=namespace["PREFLIGHT_ACCOUNT_DISCONNECTED"])
    row = namespace["_result_row"](result)
    require(namespace["PREFLIGHT_ACCOUNT_DISCONNECTED"] == PREFLIGHT_CODE and row.phase == "preflight"
            and row.status == "preflight_rejected" and row.preflight_code == PREFLIGHT_CODE
            and row.preflight_effects == [] and row.cause is None and row.upserted == 0
            and result.provider_event_read_attempted is False and result.commit_unit is False,
            "public:preflight row shape")
    cases["preflight_row_shape"] = "PASS"
    derive = namespace["_derive_overall_outcome"]
    require(derive([row], import_attempted=0, import_ok=0) == "no_op", "public:overall no_op")
    cases["overall_no_op"] = "PASS"
    require(derive([row], import_attempted=1, import_ok=0) == "failed", "public:overall failed distinct")
    cases["overall_failed_distinct"] = "PASS"
    fn = unit_node(subject_text("app/covering_domain_dispatch.py"), "run_bounded_domain")
    ok = False
    for loop in [n for n in ast.walk(fn) if isinstance(n, ast.For)]:
        ifs = [i for i, s in enumerate(loop.body) if isinstance(s, ast.If)
               and ast.dump(s.test) == dump_expr("type(token) is TokenRejected")]
        runs = [i for i, s in enumerate(loop.body) if any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "run_target"
            for c in ast.walk(s))]
        if len(ifs) == 1 and len(runs) == 1 and ifs[0] < runs[0]:
            body = loop.body[ifs[0]].body
            calls = [c for c in ast.walk(body[0]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                     and c.func.id == "_static_preflight_result"]
            ok = (len(body) == 2 and isinstance(body[1], ast.Continue) and len(calls) == 1
                  and any(k.arg == "preflight_code" and ast.dump(k.value) == dump_expr("token.code")
                          for k in calls[0].keywords))
    require(ok, "public:dispatch rejected skips run_target")
    cases["dispatch_rejected_skips_run_target"] = "PASS"
    return {"cases": cases, "structural_cases": ["dispatch_rejected_skips_run_target"],
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


# ---------------------------------------------------------------------------
# RUNNER-WIRING (structural AST/text on the candidate body; never executed)
# ---------------------------------------------------------------------------

def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [c for c in ast.walk(node) if isinstance(c, ast.Call) and (
        (isinstance(c.func, ast.Name) and c.func.id == name)
        or (isinstance(c.func, ast.Attribute) and c.func.attr == name))]


def _inner_fn(fn: ast.AST, name: str) -> ast.FunctionDef:
    return _single([n for n in ast.walk(fn) if isinstance(n, ast.FunctionDef) and n.name == name], name)


def oracle_wiring(runner_text: str) -> dict[str, str]:
    cases = {}
    fn = unit_node(runner_text, "_run_np_v_ms_invalid")
    capturing = _inner_fn(fn, "capturing_init")
    require(any(isinstance(n, ast.Compare) and ast.dump(n) == dump_expr(
                'sig.parameters["transport_factory"].default is not JoinedTLS') for n in ast.walk(fn))
            and any(isinstance(n, ast.If) and ast.dump(n.test) == dump_expr("self.transport_factory is not JoinedTLS")
                    for n in ast.walk(capturing))
            and not any(k.arg == "transport_factory" for c in ast.walk(fn) if isinstance(c, ast.Call)
                        for k in c.keywords), "wiring:default joined tls")
    cases["default_joined_tls"] = "PASS"
    top_tries = [i for i, s in enumerate(fn.body) if isinstance(s, ast.Try)]
    require(len(top_tries) >= 1, "wiring:observers saved")
    main = top_tries[-1]
    save_idx = [i for i, s in enumerate(fn.body) if ast.dump(s) in {dump_stmt(x) for x in SAVES}]
    require(len(save_idx) == 3 and all(i < main for i in save_idx), "wiring:observers saved")
    cases["observers_saved_before_install"] = "PASS"
    main_try = fn.body[main]
    inner = [n for n in ast.walk(main_try) if isinstance(n, ast.Try) and n is not main_try
             and any(isinstance(c.func, ast.Attribute) and c.func.attr == "post"
                     and isinstance(c.func.value, ast.Name) and c.func.value.id == "client"
                     for s in n.body for c in ast.walk(s) if isinstance(c, ast.Call))]
    restores = [dump_stmt(x) for x in RESTORES]
    require(len(inner) == 1 and [ast.dump(s) for s in inner[0].finalbody[:3]] == restores
            and [ast.dump(s) for s in main_try.finalbody[:3]] == restores
            and any(ast.dump(s) == dump_stmt("CoveringRoleConnector.run_target = counted_run_target")
                    for s in main_try.body)
            and any(_calls(s, "_install_token_terminal_observer") for s in main_try.body),
            "wiring:observers restored")
    cases["observers_restored_in_finally"] = "PASS"
    counted = _inner_fn(fn, "counted_request")
    handlers = [h for t in ast.walk(counted) if isinstance(t, ast.Try) for h in t.handlers]
    run_target = _inner_fn(fn, "counted_run_target")
    require(len(handlers) == 1 and handlers[0].name == "exc"
            and ast.dump(handlers[0].type) == dump_expr("BaseException")
            and isinstance(handlers[0].body[-1], ast.Raise) and handlers[0].body[-1].exc is None
            and isinstance(counted.body[-1], ast.Return) and ast.dump(counted.body[-1].value) == dump_expr("result")
            and isinstance(run_target.body[-1], ast.Return)
            and ast.dump(run_target.body[-1].value) == dump_expr("real_run_target(self, *args, **kwargs)"),
            "wiring:wrappers preserve identity")
    cases["wrappers_preserve_identity"] = "PASS"
    namespace: dict[str, Any] = {"Any": Any}
    exec_units(runner_text, tuple(EXPECTED_CONSTANTS), namespace, "runner")
    require(all(namespace[k] == v for k, v in EXPECTED_CONSTANTS.items()), "wiring:oracle constants")
    cases["oracle_constants_exact"] = "PASS"
    check_line = _single(_calls(fn, "check_oracles_immediate"), "check_oracles_immediate").lineno
    receipt = _single(_calls(fn, "case_result_receipt"), "case_result_receipt")
    kw = {k.arg: k.value for k in receipt.keywords}
    uses = {name: [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == name]
            for name in tuple(EXPECTED_CONSTANTS) + ("run_target_calls",)}
    require(check_line < receipt.lineno and all(lines and max(lines) < check_line for lines in uses.values())
            and all(isinstance(kw.get(k), ast.Constant) and kw[k].value is v
                    for k, v in (("passed", True), ("workers_joined", True), ("expected_unknown", False))),
            "wiring:stops before receipt")
    cases["stops_before_receipt"] = "PASS"
    seed = _single(_calls(fn, "seed_browser_owner_with_subscriptions"), "seed call")
    skw = {k.arg: k.value for k in seed.keywords}
    require(all(isinstance(skw.get(k), ast.Constant) and skw[k].value == v for k, v in (
        ("subscription_count", 1), ("expired", True), ("provider", "microsoft"),
        ("mark_covering_fresh_at_seed", False))), "wiring:single subscription seed")
    cases["single_subscription_seed"] = "PASS"
    require(len(_calls(fn, "open_setup_session")) == 3 and len(_calls(fn, "measure_account_credential_state")) == 2
            and len(_calls(fn, "measure_subscription_coverage_state")) == 2
            and any(isinstance(n, ast.Compare) and ast.dump(n) == dump_expr("coverage_after != coverage_before")
                    for n in ast.walk(fn)), "wiring:separate measure sessions")
    cases["separate_measure_sessions"] = "PASS"
    ids = unit_text(runner_text, "IMPLEMENTED_CASE_IDS")
    mapper = unit_text(runner_text, "_make_implemented_case")
    require(ids.count('"NP-') == 5 and f'"{CASE_ID}"' in ids and "return _run_np_v_ms_invalid()" in mapper,
            "wiring:mapper and implemented")
    cases["mapper_and_implemented"] = "PASS"
    return cases


def check_wiring() -> dict[str, Any]:
    return {"cases": oracle_wiring(subject_text("runner/candidate.py")), "control_kind": "structural_source",
            "observed": "PASS"}


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
            and cfg.get("launch_ready") is False
            and {k: v for k, v in cfg.items() if k != "case_ids"} == {k: v for k, v in src_cfg.items() if k != "case_ids"},
            "batch:runner config")
    cases["runner_config"] = "PASS"
    raw = subject_text("config/candidate-launch-config.json")
    launch = json.loads(raw)
    require(launch.get("case_ids") == [CASE_ID] and launch.get("expected_unknown_cases") == []
            and launch.get("batch_id") == "np-v-ms-invalid" and launch.get("launch_ready") is False
            and launch.get("candidate_launch_ready_staged") is False and launch.get("human_launch_authorized") is False
            and launch.get("endpoint") == "unbound"
            and launch.get("manifest_sha256") == SUBJECT_PINS["manifest/candidate.txt"]
            and CASE_ID in (launch.get("implementation_increment") or {}).get("implemented_case_ids", [])
            and all(launch.get(k) == v for k, v in (("suite_seconds", 900), ("runner_seconds", 600),
                                                     ("command_count_cap", 32), ("output_byte_cap", 1048576),
                                                     ("peer_seconds", 120), ("peer_retire_join_seconds", 5.0),
                                                     ("provider_pki_retirement_total_seconds", 45),
                                                     ("static_success_docker_command_count", 22)))
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
    src, cand = subject_text("runner/source.py"), subject_text("runner/candidate.py")
    t05 = ("T05_SHORT_CL_REFUSAL_CLASS", "T05_ABRUPT_CLIENT_CLASSES", "T05_SCRIPTED_WIRE_FRAMINGS",
           "_t05_classify_client_outcome", "_t05_scripted_wire_framing", "_t05_response_outcome", "_t05_observe",
           "_run_np_t05_orderly_close", "_run_np_t05_abrupt_truncation")
    require(all(unit_text(src, n) == unit_text(cand, n) for n in t05), "applicability:t05 units")
    cases["t05_units_identical"] = "PASS"
    refresh = ("_run_np_v_ms_refresh", "_ms_refresh_provider_routes", "_require_production_ms_token_path",
               "_actual_token_terminals", "_install_token_terminal_observer", "_run_np_v_ms_nonexpired",
               "_install_worker_exception_observer", "stop_payload")
    require(all(unit_text(src, n) == unit_text(cand, n) for n in refresh), "applicability:refresh units")
    cases["refresh_units_identical"] = "PASS"
    s_rows, c_rows = rows(subject_text("manifest/source.txt")), rows(subject_text("manifest/candidate.txt"))
    require(s_rows.get("fixture/np_provider_peer.py") == c_rows.get("fixture/np_provider_peer.py")
            == SUBJECT_PINS["peer/source.py"]
            and s_rows.get("fixture/np_auth_seed.py") == c_rows.get("fixture/np_auth_seed.py")
            == SUBJECT_PINS["fixture/np_auth_seed.py"], "applicability:peer and seed")
    cases["peer_and_seed_unchanged"] = "PASS"
    return {"cases": cases, "not_transferred": [
        "T05 fixture fake v2 PASS 14/74 (C4771F53): applies to the T05 units only (text-identical); it does not "
        "cover the changed MS invalid_grant script or _run_np_v_ms_invalid.",
        "Peer-close fake v2 PASS 11/35 (911AC7A0): applies to the unchanged peer BFB271D7 close path only.",
        "MS-refresh helper fake PASS 10: finite helper scope only; no native refresh success or invalid_grant claim.",
        "No native JoinedTLS/OAuth/refresh PASS exists; nothing here is native proof."],
        "control_kind": "applicability_map", "observed": "PASS"}


# ---------------------------------------------------------------------------
# ACTUAL-SOURCE-MUTANTS (behavioral and structural, each by its targeted oracle)
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
    "path_fix_reverted": "behavioral",
    "transport_accepts_any_400": "behavioral",
    "send_state_ignored": "behavioral",
    "adapter_except_sets_changed": "behavioral",
    "adapter_except_removed": "behavioral",
    "joined_marks_sent_after_send": "structural",
    "terminal_row_commit": "structural",
    "observer_restore_removed": "structural",
    "counted_request_swallows": "structural",
    "two_subscriptions_seed": "structural",
}


def check_mutants() -> dict[str, Any]:
    runner = subject_text("runner/candidate.py")
    transport = subject_text("app/covering_http_transport.py")
    adapter = subject_text("app/covering_domain_adapters.py")
    mutants = {
        "path_fix_reverted": (lambda: oracle_selection(_mutate(subject_text("transcript/candidate.py"),
                                                               M_PATH_REVERTED)), "selection:tenant path"),
        "transport_accepts_any_400": (lambda: oracle_other_error(_mutate(transport, M_ANY_400)),
                                      "client:other error unknown"),
        "send_state_ignored": (lambda: oracle_open_failure(_mutate(transport, M_SEND_STATE)),
                               "client:open failure original"),
        "adapter_except_sets_changed": (lambda: oracle_adapter_rollback(_mutate(adapter, M_ADAPTER_CHANGED)),
                                        "units:adapter rejected rollback"),
        "adapter_except_removed": (lambda: oracle_adapter_rollback(_mutate(adapter, M_ADAPTER_REMOVED)),
                                   "units:adapter rejected rollback"),
        "joined_marks_sent_after_send": (lambda: oracle_joined_send_order(
            _mutate(subject_text("app/covering_joined_https.py"), M_JOINED_ORDER)), "client:joined send marks sent"),
        "terminal_row_commit": (lambda: oracle_wiring(_mutate(runner, M_TERMINAL_COMMIT)), "wiring:oracle constants"),
        "observer_restore_removed": (lambda: oracle_wiring(_mutate(runner, M_RESTORE_REMOVED)),
                                     "wiring:observers restored"),
        "counted_request_swallows": (lambda: oracle_wiring(_mutate(runner, M_SWALLOW)),
                                     "wiring:wrappers preserve identity"),
        "two_subscriptions_seed": (lambda: oracle_wiring(_mutate(runner, M_TWO_SUBS)), "wiring:single subscription seed"),
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
    require(expected.get("kind") == "native-ms-invalid-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "SCRIPT-SELECTION": check_selection,
        "CLIENT-OAUTH-CLASSIFICATION": check_client,
        "OWNING-REFRESH-UNITS": check_units,
        "PUBLIC-RESULT-CONTRACT": check_public,
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
