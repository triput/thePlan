#!/usr/bin/env python3
"""HELD fake-only checker for the synthetic peer close_notify correction.

Matt, 2026-11-12. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Subjects (raw-pinned copies):
  - source    np_provider_peer.py 5568AF73... (orderly unwrap tolerates ssl.SSLError)
  - candidate np_provider_peer.py 17EA148E... (orderly unwrap tolerates OSError)
  - diff      Peer-Close-Notify.diff 023303AC...
ACTUAL SyntheticProviderPeer methods (_close_connection, _script_close_mode,
_close_client, _close_listener, _accept_once, _handshake, _recv_request,
_send_response, _send_all, _run_one_connection, execute_script, sanitized_state,
_select_cert_paths) and module helpers (_http_response_bytes, _parse_request_head)
are extracted from each subject and run against fake listener/client/TLS byte
objects, a fake `ssl` namespace (SSLError subclasses OSError, as in CPython), a fake
`socket` namespace (constants and timeout=TimeoutError only) and a no-op `select`.
_build_server_context (certificate loading) is the one substituted function; it
returns a fake context. PeerLifecycle is represented by a fake with the same field
names (checked structurally against the source dataclass).

Standard library only. No sockets are created; no ssl, app or vendor imports; no
PKI, Docker, database, network or child processes. The only write is the exclusive
result file.

Proof scope: the extracted peer close/inventory source mechanism under fakes. It does
NOT prove the actual native runtime cause (the peer's real exception was not
retained), real CPython/OpenSSL/kernel behavior, or native TLS closure.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import textwrap
import threading
import types
from pathlib import Path
from time import monotonic
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-native-peer-close-fake-prep-matt-v1"

SUBJECT_PINS = {
    "source/np_provider_peer.py": "5568AF73DD42FEB5B8E2FE4D723AD4FB0339CBF4B889F5472995ABC628F72A55",
    "candidate/np_provider_peer.py": "17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039",
    "diff/Peer-Close-Notify.diff": "023303AC81AC8F3F3460CBDE9E2AFAFFB4A3EA85D97FE547AD5C78E60B54B30D",
}

CONTROL_IDS = (
    "SUBJECT-PINS",
    "DIFF-REDERIVATION",
    "PRESERVED-OUTSIDE-CHANGE",
    "CLOSE-UNWRAP-SUCCESS",
    "CLOSE-OSERROR-RESET-PIPE-TIMEOUT",
    "CLOSE-SSL-ALREADY-TOLERATED",
    "CLOSE-NON-OSERROR-PROPAGATES",
    "CLOSE-CLEANUP-GUARD",
    "OTHER-CLOSE-MODES-UNCHANGED",
    "COMPOSITION-INVENTORY",
    "ACTUAL-SOURCE-MUTANTS",
)

PEER_CLASS = "SyntheticProviderPeer"
METHODS = (
    "_select_cert_paths", "_close_listener", "_close_client", "_accept_once", "_handshake",
    "_script_close_mode", "_recv_request", "_send_response", "_send_all", "_close_connection",
    "_run_one_connection", "execute_script", "sanitized_state",
)
HELPERS = ("_http_response_bytes", "_parse_request_head")
CAUGHT_NOTE = "close_notify_unwrap_ssl_error"
ATTEMPTED_NOTE = "orderly_close_notify_attempted"
ORDERLY = "orderly_close_notify"

# Static anchors in the CANDIDATE source (dedented method text); each must occur once.
ANCHOR_HANDLER = "            tls.unwrap()\n        except OSError:"
ANCHOR_CLEANUP = "        finally:\n            try:\n                tls.close()"
ANCHOR_KEEP = "keep = multi and index < len(self.connection_scripts) - 1"


class WitnessFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WitnessFailure(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


# ---------------------------------------------------------------------------
# Subject loading (the only real file reads, besides EXPECTED)
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
        # CRLF pairs are admitted; bare CR is not. Predicate input only; raw bytes untouched.
        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
        _SUBJECT_TEXT[rel] = data.decode("utf-8")
        observed[rel] = digest
    return {"subjects": observed, "control_kind": "raw_pin", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Literal unified-diff re-derivation (pure text; no patch tool)
# ---------------------------------------------------------------------------

_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*")


def apply_unified(original: str, diff: str) -> tuple[str, list[str], int, int, int]:
    src = original.split("\n")
    lines = diff.split("\n")
    out: list[str] = []
    files: list[str] = []
    pos = 0
    i = 0
    hunks = 0
    added = 0
    removed = 0
    while i < len(lines) and not lines[i].startswith("@@"):
        line = lines[i]
        if line.startswith("--- ") or line.startswith("+++ "):
            files.append(line[4:])
        elif line != "":
            raise WitnessFailure("unexpected diff header line")
        i += 1
    while i < len(lines):
        header = lines[i]
        if header == "" and i == len(lines) - 1:
            break
        match = _HUNK.fullmatch(header)
        require(match is not None, "malformed hunk header")
        old_start = int(match.group(1))
        old_len = int(match.group(2) or "1")
        new_len = int(match.group(4) or "1")
        start = old_start - 1
        require(start >= pos, "overlapping or unordered hunks")
        out.extend(src[pos:start])
        pos = start
        seen_old = 0
        seen_new = 0
        i += 1
        while i < len(lines) and not lines[i].startswith("@@"):
            line = lines[i]
            if line == "" and i == len(lines) - 1:
                break
            tag, body = line[:1], line[1:]
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
                removed += 1
            elif tag == "+":
                out.append(body)
                seen_new += 1
                added += 1
            else:
                raise WitnessFailure("unexpected hunk line")
            i += 1
        require((seen_old, seen_new) == (old_len, new_len), "hunk length mismatch")
        hunks += 1
    out.extend(src[pos:])
    return "\n".join(out), files, hunks, added, removed


def check_diff_rederivation() -> dict[str, Any]:
    source = subject_text("source/np_provider_peer.py")
    candidate = subject_text("candidate/np_provider_peer.py")
    derived, files, hunks, added, removed = apply_unified(source, subject_text("diff/Peer-Close-Notify.diff"))
    require(files == ["a/payload/fixture/np_provider_peer.py", "b/payload/fixture/np_provider_peer.py"],
            "diff touches unexpected files")
    require((hunks, added, removed) == (1, 1, 1), "diff is not exactly one changed line")
    require(derived == candidate, "candidate bytes differ from source + diff")
    changed = [n + 1 for n, (a, b) in enumerate(zip(source.split("\n"), candidate.split("\n"))) if a != b]
    require(changed == [394] and len(source.split("\n")) == len(candidate.split("\n")), "changed line is not 394")
    require(source.split("\n")[393] == "            except ssl.SSLError:"
            and candidate.split("\n")[393] == "            except OSError:", "changed line content")
    return {"hunks": hunks, "lines_added": added, "lines_removed": removed, "changed_line": 394,
            "control_kind": "literal_text", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Source extraction helpers (AST used only to locate exact source segments)
# ---------------------------------------------------------------------------

def _single(nodes: list[Any], what: str) -> Any:
    require(len(nodes) == 1, f"expected exactly one {what}, found {len(nodes)}")
    return nodes[0]


def class_node(text: str, name: str) -> ast.ClassDef:
    return _single([n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == name],
                   f"class {name}")


def extract_function(text: str, name: str, class_name: str | None = None) -> str:
    body = ast.parse(text).body if class_name is None else class_node(text, class_name).body
    node = _single([n for n in body if isinstance(n, ast.FunctionDef) and n.name == name], f"function {name}")
    require(not node.decorator_list, f"unexpected decorator on {name}")
    segment = ast.get_source_segment(text, node, padded=True)
    require(segment is not None, f"no source segment for {name}")
    return textwrap.dedent(segment)


def compile_function(source: str, name: str, namespace: dict[str, Any], label: str):
    code = compile(source, f"<extracted:{label}:{name}>", "exec")
    exec(code, namespace)
    function = namespace.get(name)
    require(isinstance(function, types.FunctionType), f"extracted {name} is not a function")
    return function


def mutate(source: str, mutation: tuple[str, str] | None) -> str:
    if mutation is not None:
        old, new = mutation
        require(source.count(old) == 1, f"mutation anchor not unique:{old!r}")
        source = source.replace(old, new)
    return source


# ---------------------------------------------------------------------------
# Fakes: ssl/socket/select namespaces, listener, client, TLS, scripts, lifecycle
# ---------------------------------------------------------------------------

class FakeSSLError(OSError):
    pass


class FakeSSLEOFError(FakeSSLError):
    pass


class FakeSSLWantReadError(FakeSSLError):
    pass


class FakeSSLWantWriteError(FakeSSLError):
    pass


FAKE_SSL = types.SimpleNamespace(SSLError=FakeSSLError, SSLEOFError=FakeSSLEOFError,
                                 SSLWantReadError=FakeSSLWantReadError,
                                 SSLWantWriteError=FakeSSLWantWriteError, SSLSocket=object)
FAKE_SOCKET = types.SimpleNamespace(timeout=TimeoutError, socket=object, SOL_SOCKET=1, SO_LINGER=13,
                                    SHUT_RDWR=2)


class FakeSelect:
    def __init__(self) -> None:
        self.calls = 0

    def select(self, *args: Any) -> tuple[list[Any], list[Any], list[Any]]:
        self.calls += 1
        return [], [], []


class FakeTLS:
    def __init__(self, request: bytes, *, unwrap_exc: BaseException | None = None,
                 close_exc: BaseException | None = None) -> None:
        self.request = request
        self.unwrap_exc = unwrap_exc
        self.close_exc = close_exc
        self.delivered = False
        self.sent = bytearray()
        self.handshakes = 0
        self.unwraps = 0
        self.closes = 0
        self.sockopts: list[tuple[Any, ...]] = []
        self.shutdowns: list[Any] = []

    def do_handshake(self) -> None:
        self.handshakes += 1

    def recv(self, maximum: int) -> bytes:
        if self.delivered:
            return b""
        self.delivered = True
        return self.request[:maximum]

    def send(self, view: Any) -> int:
        data = bytes(view)
        self.sent.extend(data)
        return len(data)

    def unwrap(self) -> None:
        self.unwraps += 1
        if self.unwrap_exc is not None:
            raise self.unwrap_exc

    def close(self) -> None:
        self.closes += 1
        if self.close_exc is not None:
            raise self.close_exc

    def setsockopt(self, *args: Any) -> None:
        self.sockopts.append(args)

    def shutdown(self, how: Any) -> None:
        self.shutdowns.append(how)


class FakeClient:
    def __init__(self, tls: FakeTLS) -> None:
        self.tls = tls
        self.timeouts: list[float] = []
        self.closes = 0

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)

    def close(self) -> None:
        self.closes += 1


class FakeContext:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def wrap_socket(self, client: FakeClient, *, server_side: bool, do_handshake_on_connect: bool) -> FakeTLS:
        require(server_side is True and do_handshake_on_connect is False, "wrap_socket flags")
        self.log.append("wrap")
        return client.tls


class FakeListener:
    def __init__(self, clients: list[FakeClient], log: list[str]) -> None:
        self.pending = list(clients)
        self.log = log
        self.accepts = 0
        self.closed = False

    def accept(self) -> tuple[FakeClient, tuple[str, int]]:
        if self.closed:
            raise OSError("listener closed")
        if not self.pending:
            raise TimeoutError()
        self.accepts += 1
        self.log.append("accept")
        return self.pending.pop(0), ("127.0.0.1", 50000 + self.accepts)

    def close(self) -> None:
        self.closed = True
        self.log.append("listener_close")


class Step:
    def __init__(self, direction: str, *, method: str | None = None, path: str | None = None,
                 status: int | None = None, headers: tuple = (), body_template: str | None = None,
                 close_mode: str | None = None) -> None:
        self.direction = direction
        self.method = method
        self.path = path
        self.status = status
        self.headers = headers
        self.body_template = body_template
        self.close_mode = close_mode


def script(script_id: str, path: str, body: str, close_mode: str | None = ORDERLY) -> types.SimpleNamespace:
    return types.SimpleNamespace(script_id=script_id, purpose="identity", steps=(
        Step("recv_request", method="GET", path=path),
        Step("send_response", status=200,
             headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
             body_template=body),
        Step("close", close_mode=close_mode),
    ))


LIFE_FIELDS = ("peer_id", "route", "script", "bound", "accepted", "handshake_complete", "request_received",
               "response_sent", "retired", "joined", "close_mode_observed", "phase_entered", "bytes_received",
               "bytes_sent", "notes")


def fake_life(script_obj: Any) -> types.SimpleNamespace:
    route = types.SimpleNamespace(purpose="microsoft_graph", server_hostname="graph.microsoft.com",
                                  ca_path="/fixture-ca/ca.crt", serve_wrong_name_leaf=False)
    return types.SimpleNamespace(peer_id="peer-fake", route=route, script=script_obj, bound=True,
                                 accepted=False, handshake_complete=False, request_received=False,
                                 response_sent=False, retired=False, joined=False, close_mode_observed=None,
                                 phase_entered="bound", bytes_received=0, bytes_sent=0, notes=[])


REQ0 = b"GET /v1.0/me/calendar?%24select=id HTTP/1.1\r\nHost: graph.microsoft.com\r\nConnection: close\r\n\r\n"
REQ1 = b"GET /v1.0/me/calendars?%24top=100 HTTP/1.1\r\nHost: graph.microsoft.com\r\nConnection: close\r\n\r\n"
SCRIPT0 = ("S0", "/v1.0/me/calendar", '{"id":"cal-ms-default","isDefaultCalendar":true}')
SCRIPT1 = ("S1", "/v1.0/me/calendars", '{"value":[]}')
# _recv_request appends exact_request:<method>:<path without query> on each accepted request.
EXACT0 = "exact_request:GET:/v1.0/me/calendar"
EXACT1 = "exact_request:GET:/v1.0/me/calendars"


# ---------------------------------------------------------------------------
# Extracted peer class per subject (optionally mutated)
# ---------------------------------------------------------------------------

def build_peer_class(which: str, mutations: dict[str, tuple[str, str]] | None = None,
                     log: list[str] | None = None) -> tuple[type, dict[str, Any]]:
    text = subject_text(f"{which}/np_provider_peer.py")
    log = log if log is not None else []
    select_fake = FakeSelect()

    class PeerLifecycleError(RuntimeError):
        pass

    namespace: dict[str, Any] = {
        "Any": Any, "ssl": FAKE_SSL, "socket": FAKE_SOCKET, "select": select_fake, "monotonic": monotonic,
        "PeerLifecycleError": PeerLifecycleError, "ACCEPT_POLL_SECONDS": 0.05, "RECV_CHUNK": 8192,
        "HEADER_TERMINATOR": b"\r\n\r\n", "CloseMode": str, "ExchangeScript": object, "ExchangeStep": object,
        "_build_server_context": lambda *, cert_file, key_file: (log.append(f"context:{cert_file}:{key_file}"),
                                                                   FakeContext(log))[1],
    }
    for name in HELPERS:
        compile_function(extract_function(text, name), name, namespace, which)
    methods = {}
    for name in METHODS:
        source = mutate(extract_function(text, name, PEER_CLASS), (mutations or {}).get(name))
        methods[name] = compile_function(source, name, namespace, which)
    return type(f"Extracted{which.title()}Peer", (), methods), namespace


def new_peer(cls: type, scripts: tuple[Any, ...], listener: Any = None) -> Any:
    peer = cls.__new__(cls)
    peer.life = fake_life(scripts[0])
    peer.connection_scripts = tuple(scripts)
    peer.material = types.SimpleNamespace(cert_file="/fake/server.crt", key_file="/fake/server.key",
                                          wrong_name_cert_file="/fake/wrong.crt",
                                          wrong_name_key_file="/fake/wrong.key")
    peer._listener = listener
    peer._client = None
    peer._tls = None
    peer._stop = threading.Event()
    peer._exchange_inventory = []
    return peer


def close_once(cls: type, unwrap_exc: BaseException | None = None, close_exc: BaseException | None = None,
               mode: str | None = ORDERLY) -> tuple[BaseException | None, Any, FakeTLS]:
    s = script("U", "/x", "{}", close_mode=mode)
    peer = new_peer(cls, (s,))
    tls = FakeTLS(b"", unwrap_exc=unwrap_exc, close_exc=close_exc)
    escaped: BaseException | None = None
    result: Any = None
    try:
        result = peer._close_connection(tls)
    except BaseException as exc:  # noqa: BLE001 - identity is asserted by callers
        escaped = exc
    require(result is None, "close_connection returned a value")
    return escaped, peer, tls


# ---------------------------------------------------------------------------
# Oracles (shared by controls and mutants)
# ---------------------------------------------------------------------------

def oracle_success(cls: type, label: str) -> str:
    escaped, peer, tls = close_once(cls)
    require(escaped is None, f"success propagated:{label}")
    require(tls.unwraps == 1 and tls.closes == 1, f"cleanup count:{label}")
    require(peer.life.notes == [ATTEMPTED_NOTE], f"success notes:{label}")
    require(peer.life.close_mode_observed == ORDERLY and peer.life.phase_entered == f"close:{ORDERLY}",
            f"success phase:{label}")
    return "PASS"


def oracle_original_propagates(cls: type, exc: BaseException, label: str) -> str:
    escaped, peer, tls = close_once(cls, unwrap_exc=exc)
    require(escaped is exc, f"original exact propagation:{label}")
    require(tls.closes == 1, f"original cleanup count:{label}")
    require(peer.life.notes == [], f"original notes:{label}")
    return "PASS"


def oracle_candidate_tolerates(cls: type, exc: BaseException, label: str) -> str:
    escaped, peer, tls = close_once(cls, unwrap_exc=exc)
    require(escaped is None, f"candidate tolerance:{label}")
    require(tls.closes == 1, f"candidate cleanup count:{label}")
    require(peer.life.notes == [CAUGHT_NOTE, ATTEMPTED_NOTE], f"candidate notes:{label}")
    return "PASS"


def oracle_both_tolerate(cls: type, exc: BaseException, label: str) -> str:
    escaped, peer, tls = close_once(cls, unwrap_exc=exc)
    require(escaped is None, f"ssl tolerance:{label}")
    require(tls.closes == 1 and peer.life.notes == [CAUGHT_NOTE, ATTEMPTED_NOTE], f"ssl cleanup/notes:{label}")
    return "PASS"


def oracle_non_oserror(cls: type, label: str) -> str:
    exc = ValueError("non-oserror-sentinel")
    escaped, peer, tls = close_once(cls, unwrap_exc=exc)
    require(escaped is exc, f"non-oserror selectivity:{label}")
    require(tls.closes == 1 and peer.life.notes == [], f"non-oserror cleanup/notes:{label}")
    return "PASS"


def oracle_cleanup_guard(cls: type, label: str) -> dict[str, str]:
    cases = {}
    escaped, peer, tls = close_once(cls, close_exc=ConnectionResetError("close-reset"))
    require(escaped is None and tls.closes == 1 and peer.life.notes == [ATTEMPTED_NOTE],
            f"close oserror guarded:{label}")
    cases["close_oserror"] = "PASS"
    exc = ValueError("close-value")
    escaped, peer, tls = close_once(cls, close_exc=exc)
    require(escaped is exc and tls.closes == 1 and peer.life.notes == [], f"close non-oserror propagates:{label}")
    cases["close_value_error"] = "PASS"
    return cases


def run_composition(cls: type, first_unwrap_exc: BaseException | None) -> dict[str, Any]:
    log: list[str] = []
    tls0 = FakeTLS(REQ0, unwrap_exc=first_unwrap_exc)
    tls1 = FakeTLS(REQ1)
    clients = [FakeClient(tls0), FakeClient(tls1)]
    listener = FakeListener(clients, log)
    scripts = (script(*SCRIPT0), script(*SCRIPT1))
    peer = new_peer(cls, scripts, listener)
    escaped: BaseException | None = None
    state = None
    try:
        state = peer.execute_script(seconds=1)
    except BaseException as exc:  # noqa: BLE001
        escaped = exc
    return {"peer": peer, "state": state, "escaped": escaped, "log": log, "listener": listener,
            "tls": (tls0, tls1), "clients": clients}


def expected_row(index: int, script_id: str, path: str) -> dict[str, Any]:
    return {"connection_index": index, "script_id": script_id, "purpose": "identity", "connection_close": True,
            "method": "GET", "path": path, "query_present": True, "query_verified": False,
            "handshake_complete": True, "request_received": True, "response_sent": True,
            "close_mode_observed": ORDERLY}


def oracle_candidate_inventory(cls: type, label: str) -> str:
    reset = ConnectionResetError("first-close-reset")
    run = run_composition(cls, reset)
    require(run["escaped"] is None, f"full inventory not served:{label}")
    state = run["state"]
    require(state["connection_count_admitted"] == 2 and state["connection_count_served"] == 2,
            f"full inventory counts:{label}")
    require(state["exchange_inventory"] == [expected_row(0, "S0", "/v1.0/me/calendar"),
                                            expected_row(1, "S1", "/v1.0/me/calendars")],
            f"full inventory rows:{label}")
    require(run["listener"].accepts == 2 and run["log"].count("accept") == 2
            and run["log"][-1] == "listener_close" and run["log"].count("listener_close") == 1,
            f"full inventory listener:{label}")
    tls0, tls1 = run["tls"]
    require(tls0.closes == 1 and tls1.closes == 1 and tls0.unwraps == 1 and tls1.unwraps == 1,
            f"full inventory cleanup:{label}")
    require(state["notes"] == [EXACT0, CAUGHT_NOTE, ATTEMPTED_NOTE, EXACT1, ATTEMPTED_NOTE],
            f"full inventory notes:{label}")
    return "PASS"


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def check_preserved_outside_change() -> dict[str, Any]:
    cases = {}
    source = subject_text("source/np_provider_peer.py")
    candidate = subject_text("candidate/np_provider_peer.py")
    s_nodes, c_nodes = ast.parse(source).body, ast.parse(candidate).body
    require(len(s_nodes) == len(c_nodes), "top-level count")
    for a, b in zip(s_nodes, c_nodes):
        if isinstance(a, ast.ClassDef) and a.name == PEER_CLASS:
            continue
        require(ast.dump(a) == ast.dump(b), "top-level node changed")
    cases["top_level_nodes_identical"] = "PASS"
    s_cls, c_cls = class_node(source, PEER_CLASS), class_node(candidate, PEER_CLASS)
    require(len(s_cls.body) == len(c_cls.body), "class body count")
    differing = [a.name for a, b in zip(s_cls.body, c_cls.body)
                 if ast.dump(a) != ast.dump(b) and isinstance(a, ast.FunctionDef)]
    require(differing == ["_close_connection"], f"methods changed:{differing}")
    cases["class_methods_identical_except_close"] = "PASS"
    s_fn = _single([n for n in s_cls.body if isinstance(n, ast.FunctionDef) and n.name == "_close_connection"], "s")
    c_fn = _single([n for n in c_cls.body if isinstance(n, ast.FunctionDef) and n.name == "_close_connection"], "c")
    s_handlers = [n for n in ast.walk(s_fn) if isinstance(n, ast.ExceptHandler)]
    c_handlers = [n for n in ast.walk(c_fn) if isinstance(n, ast.ExceptHandler)]
    changed = [(ast.dump(a.type), ast.dump(b.type)) for a, b in zip(s_handlers, c_handlers)
               if ast.dump(a) != ast.dump(b)]
    require(len(s_handlers) == len(c_handlers) and changed == [
        (ast.dump(ast.parse("ssl.SSLError", mode="eval").body), ast.dump(ast.parse("OSError", mode="eval").body))],
        "close_connection change is not the single handler type")
    life = class_node(source, "PeerLifecycle")
    fields = tuple(n.target.id for n in life.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name))
    require(fields == LIFE_FIELDS, "fake lifecycle fields differ from PeerLifecycle")
    cases["close_connection_single_handler_change"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_text_identity", "observed": "PASS"}


def check_close_unwrap_success() -> dict[str, Any]:
    cases = {}
    for which in ("source", "candidate"):
        cls, _ = build_peer_class(which)
        cases[which] = oracle_success(cls, which)
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_close_oserror() -> dict[str, Any]:
    cases = {}
    makers: tuple[tuple[str, Callable[[], BaseException]], ...] = (
        ("reset", lambda: ConnectionResetError("reset-sentinel")),
        ("broken_pipe", lambda: BrokenPipeError("pipe-sentinel")),
        ("timeout", lambda: TimeoutError("timeout-sentinel")),
    )
    src, _ = build_peer_class("source")
    for label, make in makers:
        cases[f"source_{label}"] = oracle_original_propagates(src, make(), label)
    cand, _ = build_peer_class("candidate")
    for label, make in makers:
        cases[f"candidate_{label}"] = oracle_candidate_tolerates(cand, make(), label)
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_close_ssl_tolerated() -> dict[str, Any]:
    cases = {}
    for which in ("source", "candidate"):
        cls, _ = build_peer_class(which)
        cases[f"{which}_ssl_eof"] = oracle_both_tolerate(cls, FakeSSLEOFError("eof"), f"{which}_eof")
        cases[f"{which}_ssl_error"] = oracle_both_tolerate(cls, FakeSSLError("ssl"), f"{which}_ssl")
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_close_non_oserror() -> dict[str, Any]:
    cases = {}
    for which in ("source", "candidate"):
        cls, _ = build_peer_class(which)
        cases[f"{which}_value_error"] = oracle_non_oserror(cls, which)
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_close_cleanup_guard() -> dict[str, Any]:
    cases = {}
    for which in ("source", "candidate"):
        cls, _ = build_peer_class(which)
        for key, value in oracle_cleanup_guard(cls, which).items():
            cases[f"{which}_{key}"] = value
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_other_close_modes() -> dict[str, Any]:
    cases = {}
    for which in ("source", "candidate"):
        cls, _ = build_peer_class(which)
        escaped, peer, tls = close_once(cls, mode="abrupt_truncate")
        require(escaped is None and tls.unwraps == 0 and tls.closes == 1 and tls.shutdowns == [2]
                and len(tls.sockopts) == 1 and peer.life.notes == ["abrupt_truncate_without_close_notify"],
                f"abrupt mode:{which}")
        cases[f"abrupt_{which}"] = "PASS"
        escaped, peer, tls = close_once(cls, mode=None)
        require(escaped is None and tls.unwraps == 0 and tls.closes == 1
                and peer.life.notes == ["close_mode:normal"], f"normal mode:{which}")
        cases[f"normal_{which}"] = "PASS"
    s_src = extract_function(subject_text("source/np_provider_peer.py"), "_close_connection", PEER_CLASS)
    c_src = extract_function(subject_text("candidate/np_provider_peer.py"), "_close_connection", PEER_CLASS)
    marker = '    if mode == "abrupt_truncate":'
    require(s_src.count(marker) == 1 and s_src.split(marker)[1] == c_src.split(marker)[1],
            "abrupt/normal branch text changed")
    cases["branches_text_identical"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_composition_inventory() -> dict[str, Any]:
    cases = {}
    src, _ = build_peer_class("source")
    reset = ConnectionResetError("first-close-reset")
    run = run_composition(src, reset)
    require(run["escaped"] is reset, "source composition exact propagation")
    require(run["listener"].accepts == 1 and run["log"] == ["accept", "listener_close"],
            "source second accept occurred")
    require(run["listener"].closed is True and len(run["listener"].pending) == 1, "source listener not closed")
    require(run["peer"]._exchange_inventory == [], "source inventory recorded")
    require(run["peer"].life.notes == [EXACT0], "source attempted note present")
    tls0, tls1 = run["tls"]
    # One close inside _close_connection.finally plus one from _run_one_connection.finally/_close_client.
    require(tls0.unwraps == 1 and tls0.closes == 2 and tls1.handshakes == 0, "source cleanup sequence")
    cases["source_reset_stops_inventory"] = "PASS"
    cand, _ = build_peer_class("candidate")
    cases["candidate_reset_serves_all"] = oracle_candidate_inventory(cand, "candidate")
    clean = [run_composition(build_peer_class(which)[0], None)["state"] for which in ("source", "candidate")]
    require(clean[0] == clean[1] and clean[0]["connection_count_served"] == 2
            and clean[0]["notes"] == [EXACT0, ATTEMPTED_NOTE, EXACT1, ATTEMPTED_NOTE], "clean states differ")
    cases["clean_states_identical"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_composition_fake", "observed": "PASS"}


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
    def mutant(name: str, old: str, new: str) -> type:
        return build_peer_class("candidate", {name: (old, new)})[0]

    reverted = (ANCHOR_HANDLER, "            tls.unwrap()\n        except ssl.SSLError:")
    broadened = (ANCHOR_HANDLER, "            tls.unwrap()\n        except Exception:")
    no_cleanup = (ANCHOR_CLEANUP, "        finally:\n            try:\n                pass")
    keep_dropped = (ANCHOR_KEEP, "keep = False")
    mutants = {
        "tolerance_reverted": (lambda: oracle_candidate_tolerates(
            mutant("_close_connection", *reverted), ConnectionResetError("m"), "m"), "candidate tolerance"),
        "selectivity_broadened": (lambda: oracle_non_oserror(
            mutant("_close_connection", *broadened), "m"), "non-oserror selectivity"),
        "cleanup_removed": (lambda: oracle_success(
            mutant("_close_connection", *no_cleanup), "m"), "cleanup count"),
        "keep_listener_dropped": (lambda: oracle_candidate_inventory(
            mutant("execute_script", *keep_dropped), "m"), "full inventory not served"),
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


def run_checks() -> dict[str, Any]:
    if RESULT.exists():
        raise WitnessFailure("existing result; no replay")
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    require(expected.get("kind") == "peer-close-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "CLOSE-UNWRAP-SUCCESS": check_close_unwrap_success,
        "CLOSE-OSERROR-RESET-PIPE-TIMEOUT": check_close_oserror,
        "CLOSE-SSL-ALREADY-TOLERATED": check_close_ssl_tolerated,
        "CLOSE-NON-OSERROR-PROPAGATES": check_close_non_oserror,
        "CLOSE-CLEANUP-GUARD": check_close_cleanup_guard,
        "OTHER-CLOSE-MODES-UNCHANGED": check_other_close_modes,
        "COMPOSITION-INVENTORY": check_composition_inventory,
        "ACTUAL-SOURCE-MUTANTS": check_actual_source_mutants,
    }
    require(tuple(functions) == CONTROL_IDS, "internal control order")
    nested_expected = expected.get("nested_case_ids") or {}
    require(set(nested_expected) <= set(CONTROL_IDS), "EXPECTED nested keys")
    controls = {}
    for control_id, function in functions.items():
        try:
            controls[control_id] = function()
        except WitnessFailure:
            raise
        except Exception as exc:
            raise WitnessFailure(f"{control_id}:{type(exc).__name__}") from None
        inner = controls[control_id].get("cases") or controls[control_id].get("mutants")
        if control_id in nested_expected:
            require(inner is not None and list(inner) == list(nested_expected[control_id]),
                    f"nested inventory mismatch:{control_id}")
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
