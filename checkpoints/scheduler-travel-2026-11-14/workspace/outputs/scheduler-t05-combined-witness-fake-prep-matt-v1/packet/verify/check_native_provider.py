#!/usr/bin/env python3
"""HELD fake-only checker: T05-SHORT-LENGTH-INVALID-JSON combined witness.

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned copies of the peer-close staging payload, rows verified against
the pinned payload SHA256SUMS.txt 5F94DD7D...):
  - covering_http_transport.py  29CBD53C... (executed WHOLE as a sandboxed module)
  - covering_transport_policy.py 5F48FD7E... (executed WHOLE as a sandboxed module)
  - covering_joined_https.py     76017776... (structural reads only; never executed)

Runtime: the ACTUAL host CPython 3.11 http.client.HTTPResponse parser (via the actual
_GuardedHTTPResponse subclass) and the ACTUAL json.loads, reached through a counting
spy that delegates to it. Importing http.client transitively imports the stdlib
socket module and (inside a module-level try) ssl. This checker never constructs a
socket, SSL context or TLS connection: CoveringHTTP receives an injected byte-buffer
transport. Fake modules (exact sys.modules sandbox, restored after each scenario):
  app, app.services (packages), app.services.covering_request_budget
  (CoveringDeadlineExceeded only), app.services.covering_joined_https (JoinedTLS
  placeholder; the injected transport replaces it), app.services.covering_target_
  transaction (CoveringRootOutcomeUnknown placeholder), httpx (Request/Response
  recorders). No app or vendor package is imported from disk.

Proof scope: the actual current framing/request source on synthetic exact wire bytes
under the host parser. It does NOT prove native TLS closure (orderly versus abrupt),
captured-native parser behavior, close-delimited positives, or full T05 closure.
"""
from __future__ import annotations

import ast
import hashlib
import http.client
import json
import json.decoder
import json.scanner
import email.feedparser
import email.parser
import os
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
PACKET_NAME = "scheduler-t05-combined-witness-fake-prep-matt-v1"

SUBJECT_PINS = {
    "app/covering_http_transport.py": "29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368",
    "app/covering_transport_policy.py": "5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88",
    "app/covering_joined_https.py": "760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427",
    "payload-SHA256SUMS.txt": "5F94DD7D4FA34BC9FB16273F040AED7FD066CE768DAE26694DF4457B4B04CCD6",
}
LINEAGE_ROWS = {
    "transport_row": ("app/covering_http_transport.py", "api/app/services/covering_http_transport.py"),
    "policy_row": ("app/covering_transport_policy.py", "api/app/services/covering_transport_policy.py"),
    "joined_row": ("app/covering_joined_https.py", "api/app/services/covering_joined_https.py"),
}
# Host stdlib sources actually loaded by this process (checked by module __file__).
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
    "SOURCE-LINEAGE",
    "RUNTIME-PROVENANCE",
    "STRUCTURE",
    "SHORT-VALID-JSON",
    "SHORT-INVALID-JSON-COMBINED",
    "COMPLETE-INVALID-JSON",
    "COMPLETE-VALID-JSON",
    "LAYER-INDEPENDENCE",
    "INVENTORY-REJECTION",
    "ACTUAL-SOURCE-MUTANTS",
)

MOD_TRANSPORT = "app.services.covering_http_transport"
MOD_POLICY = "app.services.covering_transport_policy"
SANDBOX_NAMES = ("app", "app.services", "app.services.covering_request_budget", MOD_POLICY,
                 "app.services.covering_joined_https", "app.services.covering_target_transaction", "httpx",
                 MOD_TRANSPORT)
TRANSPORT_FILE = "<subject:covering_http_transport.py>"

URL = "https://graph.microsoft.com/v1.0/me/calendars"
ROUTE_PREFIX = "/v1.0/me/calendars"
AUTH = {"Authorization": "Bearer synthetic-token-0"}

# Exact mutation anchors (read statically; each occurs once in the transport text).
# The inner close+raise pair is removed together: HTTPResponse._close_conn() does
# `fp = self.fp; self.fp = None; fp.close()`, so leaving two consecutive calls would
# fail on None for an unrelated reason. The following unconditional close remains.
ANCHOR_READ_GUARD = ('                    self._close_conn()\n'
                     '                    raise http.client.IncompleteRead(b"", self.length)\n')
ANCHOR_GATE_CALL = "            _admit_fixed_length_complete(response)\n"
ANCHOR_GATE_COND = "    if remaining is not None and remaining > 0:\n"
READ_GUARD_BYPASS = (ANCHOR_READ_GUARD, "                    pass\n")
GATE_CALL_REMOVED = (ANCHOR_GATE_CALL, "")
GATE_COND_INVERTED = (ANCHOR_GATE_COND, "    if remaining is not None and remaining < 0:\n")
GATE_COND_WEAKENED = (ANCHOR_GATE_COND, "    if remaining is not None and remaining > 4:\n")


class WitnessFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WitnessFailure(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


# ---------------------------------------------------------------------------
# Subject loading (the only packet file reads, besides EXPECTED)
# ---------------------------------------------------------------------------

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
        # CRLF pairs admitted; bare CR refused. Predicate input only; raw bytes untouched.
        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
        _SUBJECT_TEXT[rel] = data.decode("utf-8")
        observed[rel] = digest
    return {"subjects": observed, "control_kind": "raw_pin", "observed": "PASS"}


def check_source_lineage() -> dict[str, Any]:
    rows: dict[str, str] = {}
    for line in subject_text("payload-SHA256SUMS.txt").splitlines():
        pin, sep, rel = line.partition("  ")
        require(sep == "  " and len(pin) == 64, "malformed payload manifest row")
        require(rel not in rows, "duplicate payload manifest row")
        rows[rel] = pin
    cases = {}
    for case, (subject, payload_rel) in LINEAGE_ROWS.items():
        require(rows.get(payload_rel) == SUBJECT_PINS[subject], f"lineage row mismatch:{payload_rel}")
        cases[case] = "PASS"
    return {"cases": cases, "control_kind": "raw_pin_lineage", "observed": "PASS"}


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
            "json_c_scanstring_present": json.decoder.c_scanstring is not None,
            "control_kind": "runtime_provenance_partial", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Structural reads (single parse per subject per check)
# ---------------------------------------------------------------------------

def _single(nodes: list[Any], what: str) -> Any:
    require(len(nodes) == 1, f"expected exactly one {what}, found {len(nodes)}")
    return nodes[0]


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    return _single([n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name], f"class {name}")


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    return _single([n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name], f"method {name}")


def check_structure() -> dict[str, Any]:
    cases = {}
    text = subject_text("app/covering_http_transport.py")
    tree = ast.parse(text)
    request = _method(_class(tree, "CoveringHTTP"), "request")
    opened = ast.dump(ast.parse("transport.open()").body[0])
    outer = _single([n for n in request.body if isinstance(n, ast.Try)
                     and any(ast.dump(s) == opened for s in n.body)], "request try")
    body = outer.body
    gate = ast.dump(ast.parse("_admit_fixed_length_complete(response)").body[0])
    decode = ast.dump(ast.parse("decoded=json.loads(body)").body[0])
    gate_idx = _single([i for i, s in enumerate(body) if ast.dump(s) == gate], "gate call")
    json_idx = _single([i for i, s in enumerate(body) if ast.dump(s) == decode], "json.loads")
    loop_idx = _single([i for i, s in enumerate(body) if isinstance(s, ast.While)], "read loop")
    require(loop_idx < gate_idx == json_idx - 1, "order is not read loop < gate < json.loads")
    cases["read_loop_then_gate_then_decode"] = "PASS"
    reads = [n for n in ast.walk(_method(_class(tree, "_GuardedHTTPResponse"), "read")) if isinstance(n, ast.Raise)
             and isinstance(n.exc, ast.Call) and isinstance(n.exc.func, ast.Attribute)
             and n.exc.func.attr == "IncompleteRead"]
    require(len(reads) == 1, "guarded read short-body raise not exactly one")
    cases["guarded_read_short_body_raise"] = "PASS"
    init = _method(_class(tree, "CoveringHTTP"), "__init__")
    defaults = [d for d in init.args.kw_defaults if d is not None]
    require(len(defaults) == 1 and isinstance(defaults[0], ast.Name) and defaults[0].id == "JoinedTLS",
            "default transport factory is not JoinedTLS")
    cases["default_factory_joined_tls"] = "PASS"
    joined = subject_text("app/covering_joined_https.py")
    jtree = ast.parse(joined)
    jcls = _class(jtree, "JoinedTLS")
    names = {n.name for n in jcls.body if isinstance(n, ast.FunctionDef)}
    require({"open", "send", "receive", "close"} <= names, "JoinedTLS interface changed")
    # AST calls only: the method's comment text mentions "unwrap", so text search is unsound.
    close_calls = [ast.dump(n.func) for n in ast.walk(_method(jcls, "close")) if isinstance(n, ast.Call)]
    sock_close = ast.dump(ast.parse("self.sock.close", mode="eval").body)
    require(sock_close in close_calls and not any("'unwrap'" in c for c in close_calls),
            "JoinedTLS close is not local-only")
    cases["joined_close_local_only"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Sandbox: whole-module execution of the actual policy and transport sources
# ---------------------------------------------------------------------------

class ModuleSandbox:
    def __init__(self) -> None:
        self.installed: list[str] = []

    def __enter__(self) -> "ModuleSandbox":
        require(all(name not in sys.modules for name in SANDBOX_NAMES), "sandbox precondition")
        return self

    def put(self, name: str, module: types.ModuleType) -> types.ModuleType:
        sys.modules[name] = module
        self.installed.append(name)
        return module

    def __exit__(self, *exc_info: Any) -> bool:
        for name in self.installed:
            sys.modules.pop(name, None)
        return False


def sandbox_clean() -> bool:
    return all(name not in sys.modules for name in SANDBOX_NAMES)


def mutate(source: str, mutations: tuple[tuple[str, str], ...]) -> str:
    for old, new in mutations:
        require(source.count(old) == 1, f"mutation anchor not unique:{old!r}")
        source = source.replace(old, new)
    return source


class FakeRootOutcomeUnknown(Exception):
    pass


class FakeDeadlineExceeded(Exception):
    pass


class FakeHttpxRequest:
    def __init__(self, method: str, url: str) -> None:
        self.method = method
        self.url = url


class FakeHttpxResponse:
    def __init__(self, status: int, *, content: bytes, headers: dict[str, str], request: FakeHttpxRequest) -> None:
        self.status_code = status
        self.content = content
        self.headers = headers
        self.request = request


class JsonSpy:
    """Delegates to the real json.loads; records calls, inputs and raised objects."""

    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.calls: list[bytes] = []
        self.raised: list[BaseException] = []

    def loads(self, data: Any, *args: Any, **kwargs: Any) -> Any:
        self.log.append("json")
        self.calls.append(bytes(data))
        try:
            return json.loads(data, *args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - recorded, then re-raised unchanged
            self.raised.append(exc)
            raise


class FakeTransport:
    """Mirrors the JoinedTLS open/send/receive/close/sent interface on exact bytes."""

    def __init__(self, response: bytes, log: list[str]) -> None:
        self.response = response
        self.offset = 0
        self.log = log
        self.opens = 0
        self.closes = 0
        self.sent = False
        self.wire = bytearray()

    def open(self) -> "FakeTransport":
        self.opens += 1
        return self

    def send(self, data: bytes) -> None:
        self.sent = True
        self.wire.extend(data)

    def receive(self, maximum: int) -> bytes:
        chunk = self.response[self.offset:self.offset + maximum]
        self.offset += len(chunk)
        return chunk

    def close(self) -> None:
        self.closes += 1
        self.log.append("transport_close")


def run_scenario(response: bytes, mutations: tuple[tuple[str, str], ...] = ()) -> dict[str, Any]:
    """Execute the actual policy+transport modules (optionally mutated) and one request."""
    log: list[str] = []
    transport_source = mutate(subject_text("app/covering_http_transport.py"), mutations)
    policy_source = subject_text("app/covering_transport_policy.py")
    with ModuleSandbox() as box:
        for name in ("app", "app.services"):
            package = box.put(name, types.ModuleType(name))
            package.__path__ = []
        budget = box.put("app.services.covering_request_budget", types.ModuleType("app.services.covering_request_budget"))
        budget.CoveringDeadlineExceeded = FakeDeadlineExceeded
        policy = box.put(MOD_POLICY, types.ModuleType(MOD_POLICY))
        exec(compile(policy_source, "<subject:covering_transport_policy.py>", "exec"), policy.__dict__)
        joined = box.put("app.services.covering_joined_https", types.ModuleType("app.services.covering_joined_https"))
        joined.JoinedTLS = type("JoinedTLS", (), {})
        target = box.put("app.services.covering_target_transaction",
                         types.ModuleType("app.services.covering_target_transaction"))
        target.CoveringRootOutcomeUnknown = FakeRootOutcomeUnknown
        httpx = box.put("httpx", types.ModuleType("httpx"))
        httpx.Request = FakeHttpxRequest
        httpx.Response = FakeHttpxResponse
        module = box.put(MOD_TRANSPORT, types.ModuleType(MOD_TRANSPORT))
        exec(compile(transport_source, TRANSPORT_FILE, "exec"), module.__dict__)
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
        peer = policy.HTTPSPeer(hostname="graph.microsoft.com", address="127.0.0.1", port=443, ca_file="/fake/ca.crt")
        transport = FakeTransport(response, log)
        client = module.CoveringHTTP(counter=counter, routes=((peer, ROUTE_PREFIX, "identity"),),
                                     transport_factory=lambda p, remaining: transport)
        escaped: BaseException | None = None
        result: Any = None
        try:
            result = client.request("GET", URL, purpose="identity", headers=AUTH)
        except BaseException as exc:  # noqa: BLE001 - classified by oracles below
            escaped = exc
        refused_type = policy.CoveringTransportRefused
    require(sandbox_clean(), "sandbox not restored")
    return {"escaped": escaped, "result": result, "spy": spy, "gate_calls": len(gate_calls), "log": log,
            "transport": transport, "counter": counter, "refused_type": refused_type}


def innermost(exc: BaseException) -> tuple[str, str]:
    tb = exc.__traceback__
    require(tb is not None, "exception without traceback")
    while tb.tb_next is not None:
        tb = tb.tb_next
    return tb.tb_frame.f_code.co_filename, tb.tb_frame.f_code.co_name


def wire_response(declared: int, body: bytes) -> bytes:
    return (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n"
            + f"Content-Length: {declared}\r\n\r\n".encode("ascii") + body)


REQ_PREFIX = b"GET /v1.0/me/calendars HTTP/1.1\r\n"


def common_cleanup(run: dict[str, Any], response: bytes, label: str) -> None:
    transport = run["transport"]
    require(transport.opens == 1 and transport.closes == 1, f"cleanup count:{label}")
    require(bytes(transport.wire).startswith(REQ_PREFIX), f"request wire:{label}")
    require(run["counter"].bytes == len(response) and run["counter"].pages["identity"] == 1, f"counters:{label}")


# ---------------------------------------------------------------------------
# Oracles (shared by controls and mutants)
# ---------------------------------------------------------------------------

def oracle_short_refused(declared: int, body: bytes, label: str,
                         mutations: tuple[tuple[str, str], ...] = ()) -> dict[str, str]:
    """Baseline: guarded read refuses with IncompleteRead before the gate and before JSON."""
    response = wire_response(declared, body)
    run = run_scenario(response, mutations)
    require(not run["spy"].calls, f"{label}: decoder invoked")
    exc = run["escaped"]
    require(type(exc) is http.client.IncompleteRead, f"{label}: refusal type")
    require(exc.partial == b"" and exc.expected == declared - len(body), f"{label}: refusal remaining")
    require(innermost(exc) == (TRANSPORT_FILE, "read"), f"{label}: refusal site")
    cases = {"refused_incomplete_read": "PASS", "decoder_not_invoked": "PASS"}
    require(run["gate_calls"] == 0, f"{label}: gate reached")
    cases["gate_not_reached"] = "PASS"
    common_cleanup(run, response, label)
    require(run["result"] is None, f"{label}: result returned")
    cases["cleanup_and_counters"] = "PASS"
    return cases


def oracle_gate_layer(label: str, mutations: tuple[tuple[str, str], ...]) -> str:
    """With the read guard bypassed, the completion gate alone must refuse before JSON."""
    response = wire_response(5, b"{")
    run = run_scenario(response, mutations)
    require(not run["spy"].calls, f"{label}: decoder invoked")
    exc = run["escaped"]
    require(type(exc) is run["refused_type"] and exc.args == ("incomplete fixed-length body refused",),
            f"{label}: gate refusal")
    require(innermost(exc) == (TRANSPORT_FILE, "_admit_fixed_length_complete") and run["gate_calls"] == 1,
            f"{label}: gate site")
    common_cleanup(run, response, label)
    return "PASS"


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def check_short_valid() -> dict[str, Any]:
    cases = oracle_short_refused(20, b'{"value":[]}', "short valid")
    return {"cases": cases, "declared": 20, "received_body": 12, "control_kind": "actual_source_host_parser",
            "observed": "PASS"}


def check_short_invalid_combined() -> dict[str, Any]:
    cases = oracle_short_refused(5, b"{", "combined witness")
    return {"cases": cases, "declared": 5, "received_body": 1, "control_kind": "actual_source_host_parser",
            "observed": "PASS"}


def check_complete_invalid() -> dict[str, Any]:
    cases = {}
    response = wire_response(1, b"{")
    run = run_scenario(response)
    require(run["gate_calls"] == 1, "complete invalid: gate not reached once")
    cases["gate_admits"] = "PASS"
    require(run["spy"].calls == [b"{"] and run["log"].index("gate") < run["log"].index("json"),
            "complete invalid: decoder call")
    cases["decoder_invoked_once"] = "PASS"
    exc = run["escaped"]
    require(len(run["spy"].raised) == 1 and exc is run["spy"].raised[0], "complete invalid: exact decoder object")
    require(type(exc) is json.JSONDecodeError and exc.pos == 1, "complete invalid: decoder error class/pos")
    require(not isinstance(exc, (http.client.HTTPException, run["refused_type"])),
            "complete invalid: decoder error misclassified as framing")
    require(Path(innermost(exc)[0]).name == "decoder.py", "complete invalid: decoder error site")
    cases["json_decode_error_propagates"] = "PASS"
    common_cleanup(run, response, "complete invalid")
    cases["cleanup_and_counters"] = "PASS"
    return {"cases": cases, "control_kind": "actual_source_host_parser", "observed": "PASS"}


def check_complete_valid() -> dict[str, Any]:
    cases = {}
    body = b'{"value":[]}'
    response = wire_response(len(body), body)
    run = run_scenario(response)
    require(run["escaped"] is None, "complete valid: exception")
    result = run["result"]
    require(type(result) is FakeHttpxResponse and result.status_code == 200, "complete valid: typed response")
    require(type(result.request) is FakeHttpxRequest and (result.request.method, result.request.url) == ("GET", URL),
            "complete valid: request echo")
    cases["typed_response"] = "PASS"
    require(result.content == body and result.headers.get("Content-Length") == str(len(body)),
            "complete valid: exact bytes/headers")
    cases["exact_bytes_and_headers"] = "PASS"
    require(run["gate_calls"] == 1 and run["spy"].calls == [body] and not run["spy"].raised
            and run["log"] == ["gate", "json", "transport_close"], "complete valid: gate/decode order")
    cases["decoder_and_gate_once_in_order"] = "PASS"
    common_cleanup(run, response, "complete valid")
    require(run["counter"].items == 0, "complete valid: item counter")
    cases["cleanup_and_counters"] = "PASS"
    return {"cases": cases, "control_kind": "actual_source_host_parser", "observed": "PASS"}


def check_layer_independence() -> dict[str, Any]:
    cases = {"read_guard_bypassed_gate_refuses": oracle_gate_layer("gate layer", (READ_GUARD_BYPASS,))}
    # Equivalent on this path: without the gate call the guarded read still refuses first.
    removed = oracle_short_refused(5, b"{", "gate call removed", (GATE_CALL_REMOVED,))
    require(set(removed.values()) == {"PASS"}, "gate call removed: read layer")
    cases["gate_call_removed_read_still_refuses"] = "PASS"
    return {"cases": cases, "equivalent_mutant_note":
            "gate-call removal alone is behaviorally equivalent on the short-body path; not counted as detection",
            "control_kind": "actual_source_layer_mutation", "observed": "PASS"}


def compare_inventory(expected: dict[str, list[str]], actual: dict[str, list[str]]) -> None:
    require(list(expected) == list(actual), "inventory control keys differ")
    for key, cases in expected.items():
        require(list(actual[key]) == list(cases), f"inventory cases differ:{key}")


def check_inventory_rejection() -> dict[str, Any]:
    nested = json.loads(EXPECTED.read_text(encoding="utf-8"))["nested_case_ids"]
    cases = {}

    def rejected(variant: dict[str, list[str]]) -> bool:
        try:
            compare_inventory(nested, variant)
        except WitnessFailure:
            return True
        return False

    key = "SHORT-INVALID-JSON-COMBINED"
    dropped = {k: list(v) for k, v in nested.items()}
    dropped[key] = dropped[key][:-1]
    require(rejected(dropped), "dropped case accepted")
    cases["dropped_case_rejected"] = "PASS"
    reordered = {k: list(v) for k, v in nested.items()}
    reordered[key] = list(reversed(reordered[key]))
    require(rejected(reordered), "reordered case accepted")
    cases["reordered_case_rejected"] = "PASS"
    extra = {k: list(v) for k, v in nested.items()}
    extra[key] = extra[key] + ["padding"]
    require(rejected(extra), "extra case accepted")
    cases["extra_case_rejected"] = "PASS"
    require(not rejected({k: list(v) for k, v in nested.items()}), "exact inventory rejected")
    cases["exact_inventory_accepted"] = "PASS"
    return {"cases": cases, "control_kind": "inventory_oracle", "observed": "PASS"}


def _expect_detected(name: str, action: Callable[[], Any], prefix: str) -> str:
    """A mutant counts as detected only by the specific oracle that targets it."""
    try:
        action()
    except WitnessFailure as exc:
        if not str(exc).startswith(prefix):
            raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
        return "DETECTED"
    except BaseException:  # noqa: BLE001
        raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
    raise WitnessFailure(f"mutant survived:{name}")


def check_actual_source_mutants() -> dict[str, Any]:
    mutants = {
        "both_layers_bypassed": (
            lambda: oracle_short_refused(5, b"{", "combined witness", (READ_GUARD_BYPASS, GATE_CALL_REMOVED)),
            "combined witness: decoder invoked"),
        "condition_inverted_under_read_bypass": (
            lambda: oracle_gate_layer("gate layer", (READ_GUARD_BYPASS, GATE_COND_INVERTED)),
            "gate layer: decoder invoked"),
        "condition_weakened_under_read_bypass": (
            lambda: oracle_gate_layer("gate layer", (READ_GUARD_BYPASS, GATE_COND_WEAKENED)),
            "gate layer: decoder invoked"),
    }
    results = {name: _expect_detected(name, action, prefix) for name, (action, prefix) in mutants.items()}
    require(sandbox_clean(), "sandbox not restored after mutants")
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


def run_checks() -> dict[str, Any]:
    if RESULT.exists():
        raise WitnessFailure("existing result; no replay")
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    require(expected.get("kind") == "t05-combined-witness-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "SOURCE-LINEAGE": check_source_lineage,
        "RUNTIME-PROVENANCE": check_runtime_provenance,
        "STRUCTURE": check_structure,
        "SHORT-VALID-JSON": check_short_valid,
        "SHORT-INVALID-JSON-COMBINED": check_short_invalid_combined,
        "COMPLETE-INVALID-JSON": check_complete_invalid,
        "COMPLETE-VALID-JSON": check_complete_valid,
        "LAYER-INDEPENDENCE": check_layer_independence,
        "INVENTORY-REJECTION": check_inventory_rejection,
        "ACTUAL-SOURCE-MUTANTS": check_actual_source_mutants,
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
