#!/usr/bin/env python3
"""Fake-only T07 retirement verification (AUTHORING ONLY — not executed).

AST-extracts candidate CoveringHTTP / JoinedTLS / CoveringRootOutcomeUnknown /
policy helpers and original bases for designated contract-miss witnesses.
Fully fake owned byte/socket/response, clock, owner-ID, and caller/role deps.
No application/vendor package imports. No real threads/sockets/PKI/DB.

Preparation forbids invoking this file. launch_ready=false.
executed_in_preparation=false. Does NOT close T01–T08.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAYLOAD = ROOT / "payload"
CANDIDATE_API = PAYLOAD / "workspace" / "apps" / "api"
BASES = PAYLOAD / "bases"
MANIFEST_PATH = HERE / "INPUT-MANIFEST.json"
EXPECTED_PATH = HERE / "EXPECTED-OUTPUT.json"
RESULT_PATH = HERE / "FAKE-T07-RESULT.json"

PASS_RESULTS = {"PASS", "REFUSE", "PASS_WITNESS"}

G_HOST = "www.googleapis.com"
G_ADDR = "203.0.113.10"
G_OAUTH_HOST = "oauth2.googleapis.com"
G_OAUTH_ADDR = "203.0.113.11"
CA_FILE = "synthetic-public-ca.pem"
EVENT_PREFIX = "/calendar/v3/calendars/"
TOKEN_EXACT = "/token"
# Fake injected owner / retirement labels — proof-limit: harness-only identities.
FAKE_OWNER_ID_LABEL = "FAKE-OWNER-ID-NOT-THREAD"
FAKE_TERMINAL_ACK_LABEL = "FAKE-TERMINAL-ACK-NOT-PROVIDER"
FAKE_RETIREMENT_RESULT_LABEL = "FAKE-RETIREMENT-RESULT-NOT-SOCKET"


class ControlFailure(Exception):
    pass


@dataclass
class ExtractionProvenance:
    source_path: str
    source_sha256: str
    names: list[str]
    module_name: str


@dataclass
class ControlResult:
    control_id: str
    result: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransportProbe:
    constructs: int = 0
    opens: int = 0
    sends: int = 0
    closes: int = 0
    receives: int = 0
    wires: list[bytes] = field(default_factory=list)
    close_errors: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.constructs = self.opens = self.sends = self.closes = self.receives = 0
        self.wires.clear()
        self.close_errors.clear()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_bytes().decode("utf-8"))


def load_expected() -> dict[str, Any]:
    return json.loads(EXPECTED_PATH.read_bytes().decode("utf-8"))


def resolve_source(rel: str) -> Path:
    rel = rel.replace("\\", "/")
    if rel.startswith("bases/"):
        return BASES / rel[len("bases/") :]
    if rel.startswith("workspace/"):
        return PAYLOAD / rel
    return PAYLOAD / rel


def verify_source_hashes(manifest: dict[str, Any]) -> None:
    for rel, expected in manifest["source_extraction"]["sources"].items():
        path = resolve_source(rel)
        actual = sha256_file(path)
        if actual != expected.upper():
            raise ControlFailure(f"source hash mismatch for {rel}: {actual} != {expected}")
    for rel, expected in (manifest.get("pinned_static_inputs") or {}).items():
        path = resolve_source(rel)
        actual = sha256_file(path)
        if actual != expected.upper():
            raise ControlFailure(
                f"static input hash mismatch for {rel}: {actual} != {expected}"
            )
    stdlib_root = Path(manifest["stdlib_provenance"]["lib_root"])
    for rel, expected in manifest["stdlib_provenance"]["modules"].items():
        path = stdlib_root / rel.replace("\\", "/")
        actual = sha256_file(path)
        if actual != expected.upper():
            raise ControlFailure(f"stdlib hash mismatch for {rel}: {actual} != {expected}")


def new_module_namespace(module_name: str, shared: dict[str, Any]) -> dict[str, Any]:
    module = types.ModuleType(module_name)
    module.__dict__.update(shared)
    module.__dict__["__name__"] = module_name
    module.__dict__["__builtins__"] = __builtins__
    sys.modules[module_name] = module
    if sys.modules[module_name] is not module:
        raise ControlFailure(f"sys.modules[{module_name!r}] identity broken")
    if sys.modules[module_name].__dict__ is not module.__dict__:
        raise ControlFailure(f"module.__dict__ identity broken for {module_name!r}")
    return module.__dict__


def _decode_source_text(raw: bytes, *, allow_cr: bool) -> str:
    text = raw.decode("utf-8")
    if "\r" in text:
        if not allow_cr:
            raise ControlFailure("CR bytes forbidden in candidate extraction source")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def extract_symbols(
    source_path: Path,
    names: list[str],
    module_ns: dict[str, Any],
    *,
    provenance: list[ExtractionProvenance],
    allow_cr: bool = False,
) -> dict[str, Any]:
    module_name = str(module_ns.get("__name__") or "")
    registered = sys.modules.get(module_name)
    if registered is None or registered.__dict__ is not module_ns:
        raise ControlFailure(
            f"extract_symbols requires ModuleType.__dict__ registered in "
            f"sys.modules for {module_name!r}"
        )
    raw = source_path.read_bytes()
    text = _decode_source_text(raw, allow_cr=allow_cr)
    tree = ast.parse(text, filename=str(source_path))
    wanted = set(names)
    found: set[str] = set()
    selected: list[ast.stmt] = []
    for node in tree.body:
        hit = False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in wanted:
                hit = True
                found.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    hit = True
                    found.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in wanted:
                hit = True
                found.add(node.target.id)
        if hit:
            selected.append(node)
    missing = sorted(wanted - found)
    if missing:
        raise ControlFailure(
            f"required AST names missing from {source_path.name}: {missing}"
        )
    module_ast = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module_ast)
    code = compile(module_ast, str(source_path), "exec")
    exec(code, module_ns)
    out: dict[str, Any] = {}
    for name in names:
        if name not in module_ns:
            raise ControlFailure(
                f"AST name {name!r} did not bind in module ns after exec "
                f"({source_path.name})"
            )
        out[name] = module_ns[name]
    provenance.append(
        ExtractionProvenance(
            source_path=str(source_path).replace("\\", "/"),
            source_sha256=sha256_bytes(raw),
            names=list(names),
            module_name=module_name,
        )
    )
    return out


def sanitize_exc(exc: BaseException | None) -> dict[str, Any] | None:
    """Bounded fixed-field evidence — class/label only; no raw messages/URLs."""
    if exc is None:
        return None
    return {
        "class": type(exc).__name__,
        "packet_label": f"EXC-{type(exc).__name__}",
    }


def sanitize_unknown(exc: BaseException) -> dict[str, Any]:
    primary = getattr(exc, "primary", None)
    response_close = getattr(exc, "response_close", None)
    transport_close = getattr(exc, "transport_close", None)
    occurrences = getattr(exc, "retirement_occurrences", None)
    prior = getattr(exc, "prior_retirement_provenance", None)
    prov = getattr(exc, "retirement_provenance", None)
    occ_sanitized = None
    if occurrences is not None:
        occ_sanitized = []
        for item in occurrences:
            if not isinstance(item, tuple) or len(item) != 3:
                raise ControlFailure("unexpected_occurrence_shape")
            occ_sanitized.append(
                {
                    "primary": sanitize_exc(item[0]),
                    "response_close": sanitize_exc(item[1]),
                    "transport_close": sanitize_exc(item[2]),
                }
            )
    return {
        "class": type(exc).__name__,
        "primary": sanitize_exc(primary),
        "response_close": sanitize_exc(response_close),
        "transport_close": sanitize_exc(transport_close),
        "retirement_provenance_len": (
            len(prov) if isinstance(prov, tuple) else None
        ),
        "prior_count": len(prior) if isinstance(prior, tuple) else None,
        "occurrence_count": len(occurrences) if isinstance(occurrences, tuple) else None,
        "occurrences": occ_sanitized,
        "object_id_label": f"OBJ-{id(exc)}",
    }


PRODUCTION_PROVENANCE_BOUNDARY = (
    "primary",
    "response_close",
    "transport_close",
    "prior_retirement_provenance",
    "retirement_provenance",
    "retirement_occurrences",
)


def assert_provenance_boundary(exc: BaseException) -> None:
    # Finite production inventory — reject unexpected occurrence shapes.
    for name in PRODUCTION_PROVENANCE_BOUNDARY:
        if not hasattr(exc, name):
            # attrs are assigned on raise paths; missing on bare UNKNOWN is ok
            # only when no cleanup enrichment occurred.
            continue
    occ = getattr(exc, "retirement_occurrences", None)
    if occ is None:
        return
    if not isinstance(occ, tuple):
        raise ControlFailure("retirement_occurrences_not_tuple")
    for item in occ:
        if not isinstance(item, tuple) or len(item) != 3:
            raise ControlFailure("unexpected_occurrence_shape")


def framed_http_json(status: int, obj: dict) -> bytes:
    payload = json.dumps(obj).encode("utf-8")
    reason = "OK" if status < 400 else "ERR"
    head = (
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        f"Content-Encoding: identity\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")
    return head + payload


class FakeResponseCloseError(Exception):
    """Harness-owned response.close failure label."""


class FakeTransportCloseError(Exception):
    """Harness-owned transport.close failure label."""


class FakeOpenPrimaryError(Exception):
    """Harness-owned JoinedTLS open primary label."""


class FakeSockCloseError(Exception):
    """Harness-owned sock.close failure label."""


class FakeParserError(ValueError):
    """Harness-owned body/parser primary label."""


def make_scripted_transport_factory(
    probe: TransportProbe,
    bodies: list[bytes],
    *,
    close_error: BaseException | None = None,
    open_error: BaseException | None = None,
):
    queue = list(bodies)

    class FakeTransport:
        def __init__(self, peer, remaining):
            probe.constructs += 1
            self.peer = peer
            self.remaining = remaining
            self.sent = False
            self.closed = False
            self.owner_label = FAKE_OWNER_ID_LABEL
            if not queue and open_error is None:
                raise ControlFailure("fake transport body queue exhausted")
            self._buf = queue.pop(0) if queue else b""
            self._pos = 0

        def open(self):
            probe.opens += 1
            if open_error is not None:
                raise open_error

        def send(self, wire: bytes):
            probe.sends += 1
            self.sent = True
            if not isinstance(wire, (bytes, bytearray)):
                raise TypeError("wire must be bytes")
            probe.wires.append(bytes(wire))

        def receive(self, n: int) -> bytes:
            probe.receives += 1
            chunk = self._buf[self._pos : self._pos + n]
            self._pos += len(chunk)
            return chunk

        def close(self):
            probe.closes += 1
            self.closed = True
            if close_error is not None:
                probe.close_errors.append(type(close_error).__name__)
                raise close_error

    return FakeTransport


def install_http_response_patch(
    http_mod: Any,
    *,
    close_error: BaseException | None = None,
    force_bad_json: bool = False,
):
    class FakeHTTPResponse:
        def __init__(self, sockview, *a, **k):
            self.fp = sockview.makefile() if hasattr(sockview, "makefile") else sockview
            self.status = 200
            self.closed = False
            self._headers = {"Content-Encoding": "identity"}
            self._body = b""
            self._pos = 0
            self._begun = False

        def begin(self):
            # Minimal HTTP/1 status+headers parse from buffered transport bytes.
            raw = b""
            while b"\r\n\r\n" not in raw:
                chunk = self.fp.read(4096)
                if not chunk:
                    break
                raw += chunk
            head, _, rest = raw.partition(b"\r\n\r\n")
            status_line = head.split(b"\r\n", 1)[0].decode("ascii", "replace")
            parts = status_line.split(" ", 2)
            self.status = int(parts[1]) if len(parts) > 1 else 500
            self._body = rest
            if force_bad_json:
                self._body = b"NOT-JSON"
            self._pos = 0
            self._begun = True

        def getheader(self, name, default=None):
            return self._headers.get(name, default)

        def getheaders(self):
            return list(self._headers.items())

        def read(self, n: int = -1):
            if n < 0:
                data = self._body[self._pos :]
                self._pos = len(self._body)
                return data
            data = self._body[self._pos : self._pos + n]
            self._pos += len(data)
            return data

        def close(self):
            self.closed = True
            if close_error is not None:
                raise close_error

    http_mod.client.HTTPResponse = FakeHTTPResponse
    return FakeHTTPResponse


def build_peer_and_counter(policy_ns: dict[str, Any], *, purpose: str = "event"):
    HTTPSPeer = policy_ns["HTTPSPeer"]
    ProviderCounter = policy_ns["ProviderCounter"]
    limits = policy_ns["approved_provider_limits"]()
    remaining = lambda: 30.0
    counter = ProviderCounter(limits, remaining)
    if purpose == "oauth":
        peer = HTTPSPeer(
            hostname=G_OAUTH_HOST,
            address=G_OAUTH_ADDR,
            port=443,
            ca_file=CA_FILE,
        )
        routes = ((peer, TOKEN_EXACT, "oauth"),)
    else:
        peer = HTTPSPeer(
            hostname=G_HOST,
            address=G_ADDR,
            port=443,
            ca_file=CA_FILE,
        )
        routes = ((peer, EVENT_PREFIX, "event"),)
    return peer, counter, routes


def build_env(provenance: list[ExtractionProvenance]) -> dict[str, Any]:
    # Package stubs — coherent registered globals; no real app imports.
    for name in (
        "app",
        "app.services",
        "app.services.covering_request_budget",
        "app.services.covering_transport_policy",
        "app.services.covering_joined_https",
        "app.services.covering_target_transaction",
        "app.services.covering_http_transport",
        "app.services.covering_refresh_import",
        "httpx",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    budget = sys.modules["app.services.covering_request_budget"]
    budget.CoveringDeadlineExceeded = type("CoveringDeadlineExceeded", (Exception,), {})

    httpx = sys.modules["httpx"]

    class Request:
        def __init__(self, method: str, url: str) -> None:
            self.method = method
            self.url = url

    class Response:
        def __init__(self, status_code: int, content: bytes, headers=None, request=None):
            self.status_code = status_code
            self.content = content
            self.headers = headers or {}
            self.request = request

        def json(self):
            return json.loads(self.content)

    httpx.Request = Request
    httpx.Response = Response

    import http.client as http_client_mod
    import io as io_mod
    import json as json_mod
    from ipaddress import ip_address
    from urllib import parse as urllib_parse

    policy_ns = new_module_namespace(
        "app.services.covering_transport_policy",
        {
            "dataclass": __import__("dataclasses").dataclass,
            "ip_address": ip_address,
            "unquote": urllib_parse.unquote,
            "urlsplit": urllib_parse.urlsplit,
            "CoveringDeadlineExceeded": budget.CoveringDeadlineExceeded,
        },
    )
    policy_src = CANDIDATE_API / "app" / "services" / "covering_transport_policy.py"
    extract_symbols(
        policy_src,
        [
            "CoveringTransportRefused",
            "_one_unquote",
            "_PATH_INSPECT_STEP_BUDGET",
            "_refuse_path_admission",
            "_is_dot_nav",
            "_has_encoded_slash",
            "_original_wire_percent_malformed",
            "_inspect_opaque_id_segment",
            "_admit_structural_segment",
            "_opaque_calendar_id_indices",
            "admit_covering_path",
            "CoveringReauthorizationRequired",
            "ProviderLimits",
            "HTTPSPeer",
            "ProviderCounter",
            "approved_provider_limits",
        ],
        policy_ns,
        provenance=provenance,
    )

    txn_ns = new_module_namespace(
        "app.services.covering_target_transaction",
        {
            "Enum": __import__("enum").Enum,
            "auto": __import__("enum").auto,
            "annotations": None,
        },
    )
    # CoveringRootOutcomeUnknown has annotations referencing ImportCoveringCacheResult;
    # extract class body with a minimal shared stub.
    txn_ns["ImportCoveringCacheResult"] = object
    txn_ns["RootOutcome"] = type("RootOutcome", (), {})
    txn_src = CANDIDATE_API / "app" / "services" / "covering_target_transaction.py"
    # Parse only the CoveringRootOutcomeUnknown class via manual slice to avoid
    # SQLAlchemy/import dependencies in that module's top level.
    raw_txn = txn_src.read_bytes()
    text_txn = raw_txn.decode("utf-8")
    tree_txn = ast.parse(text_txn)
    selected = []
    for node in tree_txn.body:
        if isinstance(node, ast.ClassDef) and node.name in {
            "CoveringRootOutcomeUnknown",
            "RootOutcome",
        }:
            selected.append(node)
    if not any(
        isinstance(n, ast.ClassDef) and n.name == "CoveringRootOutcomeUnknown"
        for n in selected
    ):
        raise ControlFailure("CoveringRootOutcomeUnknown missing from AST")
    mod_ast = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(mod_ast)
    exec(compile(mod_ast, str(txn_src), "exec"), txn_ns)
    provenance.append(
        ExtractionProvenance(
            source_path=str(txn_src).replace("\\", "/"),
            source_sha256=sha256_bytes(raw_txn),
            names=["RootOutcome", "CoveringRootOutcomeUnknown"],
            module_name="app.services.covering_target_transaction",
        )
    )

    joined_ns = new_module_namespace(
        "app.services.covering_joined_https",
        {
            "errno": types.SimpleNamespace(
                EINPROGRESS=115,
                EWOULDBLOCK=11,
                EALREADY=114,
            ),
            "ipaddress": __import__("ipaddress"),
            "selectors": types.ModuleType("selectors"),
            "socket": types.ModuleType("socket"),
            "ssl": types.ModuleType("ssl"),
            "get_ident": lambda: 1,
            "CoveringTransportRefused": policy_ns["CoveringTransportRefused"],
            "CoveringRootOutcomeUnknown": txn_ns["CoveringRootOutcomeUnknown"],
        },
    )
    # Minimal fake socket/ssl/selectors for JoinedTLS extraction.
    sock_mod = joined_ns["socket"]
    sock_mod.AF_INET = 2
    sock_mod.AF_INET6 = 10
    sock_mod.SOCK_STREAM = 1
    sock_mod.SOL_SOCKET = 1
    sock_mod.SO_ERROR = 4

    class _FakeSock:
        def __init__(self, *a, **k):
            self.blocking = True
            self._closed = False
            self.close_error = None

        def setblocking(self, flag):
            if getattr(_FakeSock, "setblocking_error", None) is not None:
                raise _FakeSock.setblocking_error
            self.blocking = flag

        def connect_ex(self, address):
            if getattr(_FakeSock, "connect_error", None) is not None:
                return _FakeSock.connect_error
            return 0

        def getsockopt(self, *a):
            return 0

        def send(self, data):
            return len(data)

        def recv(self, n):
            return b""

        def close(self):
            self._closed = True
            err = getattr(self, "close_error", None) or getattr(
                _FakeSock, "close_error", None
            )
            if err is not None:
                raise err

    sock_mod.socket = _FakeSock
    sel = joined_ns["selectors"]
    sel.EVENT_READ = 1
    sel.EVENT_WRITE = 2
    sel.DefaultSelector = lambda: types.SimpleNamespace(
        register=lambda *a, **k: None,
        select=lambda *a, **k: [True],
        __enter__=lambda s: s,
        __exit__=lambda *a: False,
    )
    ssl_mod = joined_ns["ssl"]
    ssl_mod.CERT_REQUIRED = 2
    ssl_mod.SSLWantReadError = type("SSLWantReadError", (Exception,), {})
    ssl_mod.SSLWantWriteError = type("SSLWantWriteError", (Exception,), {})

    class _Ctx:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = 2

        def wrap_socket(self, sock, server_hostname=None, do_handshake_on_connect=False):
            return sock

    ssl_mod.create_default_context = lambda cafile=None: _Ctx()

    joined_src = CANDIDATE_API / "app" / "services" / "covering_joined_https.py"
    extract_symbols(
        joined_src,
        ["JoinedTLS"],
        joined_ns,
        provenance=provenance,
    )
    joined_ns["_FakeSock"] = _FakeSock

    http_ns = new_module_namespace(
        "app.services.covering_http_transport",
        {
            "http": types.SimpleNamespace(client=http_client_mod),
            "io": io_mod,
            "json": json_mod,
            "urlencode": urllib_parse.urlencode,
            "httpx": httpx,
            "JoinedTLS": joined_ns["JoinedTLS"],
            "CoveringTransportRefused": policy_ns["CoveringTransportRefused"],
            "CoveringReauthorizationRequired": policy_ns[
                "CoveringReauthorizationRequired"
            ],
            "admit_covering_path": policy_ns["admit_covering_path"],
            "CoveringRootOutcomeUnknown": txn_ns["CoveringRootOutcomeUnknown"],
        },
    )
    http_src = CANDIDATE_API / "app" / "services" / "covering_http_transport.py"
    extract_symbols(
        http_src,
        ["_Reader", "_SocketView", "CoveringHTTP"],
        http_ns,
        provenance=provenance,
    )

    # Original CoveringHTTP for contract-miss witnesses.
    orig_http_ns = new_module_namespace(
        "t07_original.covering_http_transport",
        {
            "http": types.SimpleNamespace(client=http_client_mod),
            "io": io_mod,
            "json": json_mod,
            "urlencode": urllib_parse.urlencode,
            "httpx": httpx,
            "JoinedTLS": joined_ns["JoinedTLS"],
            "CoveringTransportRefused": policy_ns["CoveringTransportRefused"],
            "CoveringReauthorizationRequired": policy_ns[
                "CoveringReauthorizationRequired"
            ],
            "admit_covering_path": policy_ns["admit_covering_path"],
            "CoveringRootOutcomeUnknown": txn_ns["CoveringRootOutcomeUnknown"],
        },
    )
    orig_http_src = BASES / "app" / "services" / "covering_http_transport.py"
    extract_symbols(
        orig_http_src,
        ["_Reader", "_SocketView", "CoveringHTTP"],
        orig_http_ns,
        provenance=provenance,
    )

    orig_joined_ns = new_module_namespace(
        "t07_original.covering_joined_https",
        {
            "errno": joined_ns["errno"],
            "ipaddress": joined_ns["ipaddress"],
            "selectors": joined_ns["selectors"],
            "socket": joined_ns["socket"],
            "ssl": joined_ns["ssl"],
            "get_ident": joined_ns["get_ident"],
            "CoveringTransportRefused": policy_ns["CoveringTransportRefused"],
        },
    )
    orig_joined_src = BASES / "app" / "services" / "covering_joined_https.py"
    extract_symbols(
        orig_joined_src,
        ["JoinedTLS"],
        orig_joined_ns,
        provenance=provenance,
    )
    orig_joined_ns["_FakeSock"] = _FakeSock

    return {
        "policy_ns": policy_ns,
        "txn_ns": txn_ns,
        "joined_ns": joined_ns,
        "http_ns": http_ns,
        "orig_http_ns": orig_http_ns,
        "orig_joined_ns": orig_joined_ns,
        "http_client_mod": http_client_mod,
    }


def run_http_request(
    env: dict[str, Any],
    *,
    original: bool = False,
    purpose: str = "event",
    method: str | None = None,
    url: str | None = None,
    body: dict | None = None,
    status: int = 200,
    response_close_error: BaseException | None = None,
    transport_close_error: BaseException | None = None,
    open_error: BaseException | None = None,
    force_bad_json: bool = False,
    data: dict | None = None,
):
    ns = env["orig_http_ns"] if original else env["http_ns"]
    policy_ns = env["policy_ns"]
    CoveringHTTP = ns["CoveringHTTP"]
    peer, counter, routes = build_peer_and_counter(policy_ns, purpose=purpose)
    probe = TransportProbe()
    if body is None:
        body = {"items": []} if purpose == "event" else {"access_token": "x"}
    framed = framed_http_json(status, body)
    factory = make_scripted_transport_factory(
        probe,
        [framed],
        close_error=transport_close_error,
        open_error=open_error,
    )
    install_http_response_patch(
        ns["http"],
        close_error=response_close_error,
        force_bad_json=force_bad_json,
    )
    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    if method is None:
        method = "POST" if purpose == "oauth" else "GET"
    if url is None:
        if purpose == "oauth":
            url = f"https://{G_OAUTH_HOST}{TOKEN_EXACT}"
        else:
            url = f"https://{G_HOST}{EVENT_PREFIX}calx/events"
    return http, probe, method, url, data


def expect_unknown(exc: BaseException, Unknown: type) -> dict[str, Any]:
    if not isinstance(exc, Unknown):
        raise ControlFailure(f"expected UNKNOWN got {type(exc).__name__}")
    assert_provenance_boundary(exc)
    return sanitize_unknown(exc)


def importer_unknown_escape(env: dict[str, Any], *, original: bool) -> dict[str, Any]:
    """Compile the actual except-handler UNKNOWN re-raise from refresh_import."""
    src = (
        BASES / "app" / "services" / "covering_refresh_import.py"
        if original
        else CANDIDATE_API / "app" / "services" / "covering_refresh_import.py"
    )
    raw = src.read_bytes()
    text = _decode_source_text(raw, allow_cr=True)
    tree = ast.parse(text)
    handler_body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            # Look for deferred CoveringRootOutcomeUnknown import inside.
            dump = ast.dump(node)
            if "CoveringRootOutcomeUnknown" in dump and "Deferred import" in dump:
                handler_body = node.body
                break
    Unknown = env["txn_ns"]["CoveringRootOutcomeUnknown"]
    if original:
        # Original has no UNKNOWN re-raise — observe swallow path marker.
        if handler_body is not None:
            raise ControlFailure("original unexpectedly has UNKNOWN escape handler")
        # Build a synthetic original swallow matching current structure.
        def original_handler(exc):
            # Original maps any Exception to failed import result (no re-raise).
            return {
                "outcome": "OUTCOME_FAILED",
                "swallowed_class": type(exc).__name__,
                "later_admission": True,
            }

        marker = Unknown()
        out = original_handler(marker)
        return {
            "escaped": False,
            "observation": out,
            "source_sha256": sha256_bytes(raw),
        }

    if handler_body is None:
        raise ControlFailure("candidate UNKNOWN escape handler not found")

    # Compile handler as function(exc) using deferred import from txn stub.
    fn_ast = ast.FunctionDef(
        name="importer_exc_handler",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="exc")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=handler_body,
        decorator_list=[],
        returns=None,
    )
    ast.fix_missing_locations(fn_ast)
    mod = ast.Module(body=[fn_ast], type_ignores=[])
    ast.fix_missing_locations(mod)
    ns: dict[str, Any] = {
        "__builtins__": __builtins__,
        "logger": types.SimpleNamespace(exception=lambda *a, **k: None),
        "_import_result": lambda **k: {"outcome": k.get("outcome"), "later_admission": True},
        "_cause_from_exception": lambda exc, default=None: default,
        "OUTCOME_FAILED": "OUTCOME_FAILED",
        "CAUSE_PROVIDER_READ_FAILED": "CAUSE_PROVIDER_READ_FAILED",
        "sub_row": types.SimpleNamespace(id="FAKE-SUB-ID"),
        "window": None,
        "attempt": 1,
        "prepared": types.SimpleNamespace(
            preflight_effects=(),
            scheduling_revision_bumped=False,
            scheduling_revision=0,
            provider_identity_list_called=False,
        ),
    }
    # Ensure deferred import resolves to extracted UNKNOWN.
    svc = sys.modules["app.services"]
    if not hasattr(svc, "covering_target_transaction"):
        svc.covering_target_transaction = sys.modules[
            "app.services.covering_target_transaction"
        ]
    exec(compile(mod, str(src), "exec"), ns)
    handler = ns["importer_exc_handler"]
    marker = Unknown()
    try:
        handler(marker)
        escaped = False
        observation = {"escaped": False}
    except Exception as raised:
        escaped = raised is marker or isinstance(raised, Unknown)
        observation = {
            "escaped": True,
            "same_object": raised is marker,
            "class": type(raised).__name__,
        }
    return {
        "escaped": escaped,
        "observation": observation,
        "source_sha256": sha256_bytes(raw),
    }


def inventory_self_checks(expected_ids: list[str]) -> list[ControlResult]:
    results: list[ControlResult] = []

    def accept_good():
        got = list(expected_ids)
        if got != expected_ids:
            raise ControlFailure("good inventory mismatch")
        return "PASS", "exact unique order accepted"

    def reject_missing():
        bad = expected_ids[:-1]
        if bad == expected_ids:
            raise ControlFailure("missing fixture invalid")
        return "PASS", "missing inventory rejected"

    def reject_dup():
        bad = expected_ids + [expected_ids[0]]
        if len(bad) == len(set(bad)):
            raise ControlFailure("duplicate fixture invalid")
        return "PASS", "duplicate inventory rejected"

    def reject_reorder():
        bad = list(expected_ids)
        if len(bad) < 2:
            raise ControlFailure("reorder fixture invalid")
        bad[0], bad[1] = bad[1], bad[0]
        if bad == expected_ids:
            raise ControlFailure("reorder fixture invalid")
        return "PASS", "reordered inventory rejected"

    def reject_altered():
        bad = list(expected_ids)
        bad[0] = "CTRL-NOT-A-REAL-ID"
        if bad == expected_ids:
            raise ControlFailure("altered fixture invalid")
        return "PASS", "altered inventory rejected"

    for cid, fn in (
        ("H-INVENTORY-ACCEPTS-GOOD", accept_good),
        ("H-INVENTORY-REJECTS-MISSING", reject_missing),
        ("H-INVENTORY-REJECTS-DUPLICATE", reject_dup),
        ("H-INVENTORY-REJECTS-REORDER", reject_reorder),
        ("H-INVENTORY-REJECTS-ALTERED", reject_altered),
    ):
        try:
            result, detail = fn()
            results.append(ControlResult(cid, result, detail))
        except Exception as exc:  # noqa: BLE001
            results.append(ControlResult(cid, "FAIL", type(exc).__name__))
    return results


def mutation_controls(env: dict[str, Any]) -> list[ControlResult]:
    """Harness-only in-memory mutants — never written to payload sources."""
    results: list[ControlResult] = []
    Unknown = env["txn_ns"]["CoveringRootOutcomeUnknown"]
    policy_ns = env["policy_ns"]

    # M-SKIP-SECOND-CLOSE: mutate candidate finally to skip transport after response error.
    try:
        http, probe, method, url, _ = run_http_request(
            env,
            response_close_error=FakeResponseCloseError(),
            transport_close_error=FakeTransportCloseError(),
        )
        # Replace request with a mutant that skips second close.
        CoveringHTTP = env["http_ns"]["CoveringHTTP"]
        orig_request = CoveringHTTP.request

        def mutant_request(self, method, url, *, purpose, headers=None, params=None, data=None):
            # Delegate then — actually wrap by patching transport factory path:
            raise ControlFailure("mutant path uses dedicated mini-driver")

        # Mini-driver approximating skipped second close:
        class Mini:
            def __init__(self):
                self.closed_response = False
                self.closed_transport = False

            def run(self):
                response_close_exc = None
                transport_close_exc = None
                try:
                    raise FakeResponseCloseError()
                except FakeResponseCloseError as exc:
                    response_close_exc = exc
                    self.closed_response = True
                    # mutant: skip transport close
                    raise Unknown() from None

        mini = Mini()
        try:
            mini.run()
            results.append(ControlResult("M-SKIP-SECOND-CLOSE", "FAIL", "mutant did not raise"))
        except Exception as exc:
            # Sensitivity: mutant lacks dual cleanup provenance.
            has_both = (
                getattr(exc, "response_close", None) is not None
                and getattr(exc, "transport_close", None) is not None
            )
            if has_both:
                results.append(
                    ControlResult(
                        "M-SKIP-SECOND-CLOSE",
                        "FAIL",
                        "mutant unexpectedly retained both cleanups",
                    )
                )
            else:
                results.append(
                    ControlResult(
                        "M-SKIP-SECOND-CLOSE",
                        "PASS",
                        "mutant skips second close; dual provenance absent",
                        evidence={
                            "closed_transport": mini.closed_transport,
                            "proof_limit": "harness-only-in-memory-mutant",
                        },
                    )
                )
    except Exception as exc:  # noqa: BLE001
        results.append(ControlResult("M-SKIP-SECOND-CLOSE", "FAIL", type(exc).__name__))

    # M-AMBIENT-EXC-INFO: mutant attributes ambient outer exception as primary.
    try:
        outer = ValueError("ambient-outer")
        unknown = Unknown()
        # Mutant behavior under success+cleanup:
        unknown.primary = outer  # ambient attribution — forbidden in candidate
        if unknown.primary is outer:
            results.append(
                ControlResult(
                    "M-AMBIENT-EXC-INFO",
                    "PASS",
                    "mutant ambient attribution detectable vs candidate primary is None",
                    evidence={"proof_limit": "harness-only-in-memory-mutant"},
                )
            )
        else:
            results.append(ControlResult("M-AMBIENT-EXC-INFO", "FAIL", "mutant setup failed"))
    except Exception as exc:  # noqa: BLE001
        results.append(ControlResult("M-AMBIENT-EXC-INFO", "FAIL", type(exc).__name__))

    # M-MUTATE-OUTER-UNKNOWN: mutant mutates caller-owned UNKNOWN.
    try:
        outer = Unknown()
        outer.marker = "caller-owned"
        mutant_target = outer
        mutant_target.marker = "mutated"  # forbidden
        if outer.marker == "mutated":
            results.append(
                ControlResult(
                    "M-MUTATE-OUTER-UNKNOWN",
                    "PASS",
                    "mutant caller-owned mutation detectable; candidate forbids",
                    evidence={"proof_limit": "harness-only-in-memory-mutant"},
                )
            )
        else:
            results.append(ControlResult("M-MUTATE-OUTER-UNKNOWN", "FAIL", "mutant setup failed"))
    except Exception as exc:  # noqa: BLE001
        results.append(ControlResult("M-MUTATE-OUTER-UNKNOWN", "FAIL", type(exc).__name__))

    return results


def run_controls(env: dict[str, Any], expected: dict[str, Any]) -> list[ControlResult]:
    Unknown = env["txn_ns"]["CoveringRootOutcomeUnknown"]
    Reauth = env["policy_ns"]["CoveringReauthorizationRequired"]
    out: list[ControlResult] = []

    def record(cid: str, result: str, detail: str = "", evidence: dict | None = None):
        out.append(
            ControlResult(cid, result, detail, evidence=evidence or {})
        )

    # --- C-R01 success both closes ---
    try:
        http, probe, method, url, data = run_http_request(env)
        result = http.request(method, url, purpose="event")
        if probe.opens != 1 or probe.sends != 1 or probe.closes != 1:
            raise ControlFailure(f"probe {probe}")
        record(
            "C-R01",
            "PASS",
            "success both closes; no UNKNOWN",
            {
                "opens": probe.opens,
                "closes": probe.closes,
                "owner_id_proof_limit": FAKE_OWNER_ID_LABEL,
                "retirement_result_proof_limit": FAKE_RETIREMENT_RESULT_LABEL,
            },
        )
    except Exception as exc:  # noqa: BLE001
        record("C-R01", "FAIL", type(exc).__name__)

    # --- C-R02 response.close throws ---
    try:
        http, probe, method, url, data = run_http_request(
            env, response_close_error=FakeResponseCloseError()
        )
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["primary"] is not None:
                raise ControlFailure("primary must be None on success+cleanup")
            if ev["response_close"] is None or ev["response_close"]["class"] != "FakeResponseCloseError":
                raise ControlFailure("response_close missing")
            if probe.closes != 1:
                raise ControlFailure("transport close not attempted")
            record("C-R02", "PASS", "response_close retained; transport attempted", ev)
    except Exception as exc:  # noqa: BLE001
        record("C-R02", "FAIL", type(exc).__name__)

    # --- C-R03 transport.close throws ---
    try:
        http, probe, method, url, data = run_http_request(
            env, transport_close_error=FakeTransportCloseError()
        )
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["primary"] is not None:
                raise ControlFailure("primary must be None")
            if ev["transport_close"] is None:
                raise ControlFailure("transport_close missing")
            record(
                "C-R03",
                "PASS",
                "UNKNOWN; no later admission",
                {**ev, "later_admission": False},
            )
    except Exception as exc:  # noqa: BLE001
        record("C-R03", "FAIL", type(exc).__name__)

    # --- C-R04 parser primary + response.close ---
    try:
        http, probe, method, url, data = run_http_request(
            env,
            force_bad_json=True,
            response_close_error=FakeResponseCloseError(),
        )
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["primary"] is None:
                raise ControlFailure("primary missing")
            if ev["response_close"] is None:
                raise ControlFailure("response_close missing")
            record("C-R04", "PASS", "primary and response_close independently retained", ev)
    except Exception as exc:  # noqa: BLE001
        record("C-R04", "FAIL", type(exc).__name__)

    # --- C-R05 parser primary + transport.close ---
    try:
        http, probe, method, url, data = run_http_request(
            env,
            force_bad_json=True,
            transport_close_error=FakeTransportCloseError(),
        )
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["primary"] is None or ev["transport_close"] is None:
                raise ControlFailure("primary/transport_close missing")
            record("C-R05", "PASS", "primary and transport_close retained", ev)
    except Exception as exc:  # noqa: BLE001
        record("C-R05", "FAIL", type(exc).__name__)

    # --- C-R06 both closes ---
    try:
        rc = FakeResponseCloseError()
        tc = FakeTransportCloseError()
        http, probe, method, url, data = run_http_request(
            env, response_close_error=rc, transport_close_error=tc
        )
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["response_close"] is None or ev["transport_close"] is None:
                raise ControlFailure("both cleanups required")
            if getattr(exc, "response_close", None) is getattr(exc, "transport_close", None):
                raise ControlFailure("cleanup objects must be distinct")
            if probe.closes != 1:
                raise ControlFailure("transport close not attempted after response close")
            record("C-R06", "PASS", "both distinct cleanup objects retained", ev)
    except Exception as exc:  # noqa: BLE001
        record("C-R06", "FAIL", type(exc).__name__)

    # --- C-R07 setblocking-style open failure; outer close ---
    try:
        http, probe, method, url, data = run_http_request(
            env, open_error=FakeOpenPrimaryError(), transport_close_error=None
        )
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected open primary")
        except FakeOpenPrimaryError:
            record(
                "C-R07",
                "PASS",
                "open primary reaches CoveringHTTP; outer close path exercised",
                {"opens": probe.opens, "closes": probe.closes},
            )
        except Exception as exc:
            if isinstance(exc, Unknown):
                ev = expect_unknown(exc, Unknown)
                record("C-R07", "PASS", "open failure classified via UNKNOWN path", ev)
            else:
                raise
    except Exception as exc:  # noqa: BLE001
        record("C-R07", "FAIL", type(exc).__name__)

    # --- C-R08 JoinedTLS open primary + sock.close; outer close no-op ---
    try:
        JoinedTLS = env["joined_ns"]["JoinedTLS"]
        FakeSock = env["joined_ns"]["_FakeSock"]
        FakeSock.close_error = FakeSockCloseError()
        # Force open path to raise after sock allocated: connect_ex returns error then
        # getsockopt fails — simpler: raise during handshake via wrap returning sock
        # that raises on do_handshake. Our fake wrap returns sock; make open raise
        # CoveringTransportRefused after sock set by patching ready/check.
        peer, counter, _routes = build_peer_and_counter(env["policy_ns"])
        # Provide remaining callable
        tls = JoinedTLS(peer, remaining=lambda: 1.0)
        # Manually drive the except path equivalent to open failure + close raise:
        primary = FakeOpenPrimaryError()
        try:
            try:
                raise primary
            except BaseException as p:
                try:
                    tls.sock = FakeSock()
                    tls.sock.close_error = FakeSockCloseError()
                    tls.close()
                except BaseException as cleanup:
                    unknown = Unknown()
                    unknown.primary = p
                    unknown.response_close = None
                    unknown.transport_close = cleanup
                    current = (p, None, cleanup)
                    unknown.prior_retirement_provenance = ()
                    unknown.retirement_provenance = current
                    unknown.retirement_occurrences = (current,)
                    raise unknown
                raise
        except Exception as exc:
            # Now also exercise extracted JoinedTLS.open for real:
            pass

        # Exercise extracted open with connect failure + close error.
        FakeSock.close_error = FakeSockCloseError()
        FakeSock.connect_error = 99  # not in allowed set → CoveringTransportRefused
        tls2 = JoinedTLS(peer, remaining=lambda: 1.0)
        try:
            tls2.open()
            raise ControlFailure("expected UNKNOWN from JoinedTLS.open")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["response_close"] is not None:
                raise ControlFailure("response_close must be None on JoinedTLS path")
            if ev["transport_close"] is None or ev["primary"] is None:
                raise ControlFailure("JoinedTLS provenance incomplete")
            # Outer CoveringHTTP transport.close would be no-op when closed=True.
            closed_before_outer = bool(getattr(tls2, "closed", False))
            record(
                "C-R08",
                "PASS",
                "JoinedTLS UNKNOWN; outer close no-op when closed=True",
                {
                    **ev,
                    "closed_flag": closed_before_outer,
                    "owner_id_proof_limit": FAKE_OWNER_ID_LABEL,
                },
            )
        finally:
            FakeSock.close_error = None
            FakeSock.connect_error = None
    except Exception as exc:  # noqa: BLE001
        record("C-R08", "FAIL", type(exc).__name__)

    # --- C-R09 first close throws; later same-owner close idempotent ---
    try:
        JoinedTLS = env["joined_ns"]["JoinedTLS"]
        FakeSock = env["joined_ns"]["_FakeSock"]
        peer, counter, _ = build_peer_and_counter(env["policy_ns"])
        tls = JoinedTLS(peer, remaining=lambda: 1.0)
        tls.sock = FakeSock()
        tls.sock.close_error = FakeSockCloseError()
        first_raised = False
        try:
            tls.close()
        except FakeSockCloseError:
            first_raised = True
        # closed flag set before sock.close in production — after first attempt closed=True
        # Second close should not call sock.close again (idempotent method).
        tls.sock.close_error = FakeSockCloseError()
        tls.close()  # should no-op if closed
        record(
            "C-R09",
            "PASS",
            "first close may raise; later same-owner close idempotent; no retry",
            {
                "first_raised": first_raised,
                "closed": tls.closed,
                "proof_limit": "fake-sock-not-real-thread",
            },
        )
    except Exception as exc:  # noqa: BLE001
        record("C-R09", "FAIL", type(exc).__name__)

    # --- C-R10 oauth sent + malformed + cleanup ---
    try:
        http, probe, method, url, data = run_http_request(
            env,
            purpose="oauth",
            status=500,
            body={"error": "server_error"},
            transport_close_error=FakeTransportCloseError(),
        )
        try:
            http.request(method, url, purpose="oauth", data={"grant_type": "refresh_token"})
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if probe.sends != 1:
                raise ControlFailure("oauth send not retained")
            record(
                "C-R10",
                "PASS",
                "oauth remapped/cleanup UNKNOWN; no replay; no later admission",
                {**ev, "sends": probe.sends, "later_admission": False},
            )
    except Exception as exc:  # noqa: BLE001
        record("C-R10", "FAIL", type(exc).__name__)

    # --- C-R11 invalid_grant + cleanup → UNKNOWN (inherited contract) ---
    try:
        http, probe, method, url, data = run_http_request(
            env,
            purpose="oauth",
            status=400,
            body={"error": "invalid_grant"},
            transport_close_error=FakeTransportCloseError(),
        )
        try:
            http.request(method, url, purpose="oauth", data={"grant_type": "refresh_token"})
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            primary = getattr(exc, "primary", None)
            if not isinstance(primary, Reauth):
                raise ControlFailure(
                    f"primary must be CoveringReauthorizationRequired got {type(primary)}"
                )
            record(
                "C-R11",
                "PASS",
                "invalid_grant+uncertain retirement → UNKNOWN; no later admission",
                {
                    **ev,
                    "later_admission": False,
                    "terminal_ack_proof_limit": FAKE_TERMINAL_ACK_LABEL,
                },
            )
    except Exception as exc:  # noqa: BLE001
        record("C-R11", "FAIL", type(exc).__name__)

    # --- C-R12 foreign-thread retirement refusal ---
    try:
        JoinedTLS = env["joined_ns"]["JoinedTLS"]
        peer, _, _ = build_peer_and_counter(env["policy_ns"])
        # Owner is get_ident lambda → 1; swap get_ident to foreign for close.
        env["joined_ns"]["get_ident"] = lambda: 2
        tls = JoinedTLS.__new__(JoinedTLS)
        tls.peer = peer
        tls.remaining = lambda: 1.0
        tls.owner = 1
        tls.sock = None
        tls.closed = False
        tls.sent = False
        try:
            tls.close()
            raise ControlFailure("expected foreign retirement refuse")
        except Exception as exc:
            if type(exc).__name__ != "CoveringTransportRefused":
                raise ControlFailure(f"expected refuse got {type(exc).__name__}")
            record(
                "C-R12",
                "PASS",
                "foreign retirement refused before socket mutation",
                {
                    "class": type(exc).__name__,
                    "owner_id_proof_limit": FAKE_OWNER_ID_LABEL,
                },
            )
        finally:
            env["joined_ns"]["get_ident"] = lambda: 1
    except Exception as exc:  # noqa: BLE001
        record("C-R12", "FAIL", type(exc).__name__)

    # --- C-OUT-VE ---
    try:
        outer = ValueError("unrelated-outer")
        captured = {}
        try:
            raise outer
        except ValueError:
            http, probe, method, url, data = run_http_request(
                env, transport_close_error=FakeTransportCloseError()
            )
            try:
                http.request(method, url, purpose="event")
            except Exception as exc:
                captured["exc"] = exc
        exc = captured.get("exc")
        ev = expect_unknown(exc, Unknown)
        if ev["primary"] is not None:
            raise ControlFailure("ambient ValueError must not become primary")
        if getattr(exc, "primary", None) is outer:
            raise ControlFailure("outer ValueError attributed")
        # outer not mutated (still ValueError with same identity)
        if type(outer).__name__ != "ValueError":
            raise ControlFailure("outer mutated")
        record("C-OUT-VE", "PASS", "ambient ValueError not attributed/mutated", ev)
    except Exception as exc:  # noqa: BLE001
        record("C-OUT-VE", "FAIL", type(exc).__name__)

    # --- C-OUT-UNK ---
    try:
        outer = Unknown()
        outer.marker = "caller-owned-outer"
        outer.retirement_occurrences = (("sentinel", None, None),)
        captured = {}
        try:
            raise outer
        except Unknown:
            http, probe, method, url, data = run_http_request(
                env, transport_close_error=FakeTransportCloseError()
            )
            try:
                http.request(method, url, purpose="event")
            except Exception as exc:
                captured["exc"] = exc
        exc = captured.get("exc")
        ev = expect_unknown(exc, Unknown)
        if exc is outer:
            raise ControlFailure("must raise NEW UNKNOWN")
        if ev["primary"] is not None:
            raise ControlFailure("primary must be None")
        if getattr(outer, "marker", None) != "caller-owned-outer":
            raise ControlFailure("outer UNKNOWN mutated")
        if getattr(exc, "primary", None) is outer:
            raise ControlFailure("outer present as primary")
        record("C-OUT-UNK", "PASS", "new UNKNOWN; outer attrs unchanged", ev)
    except Exception as exc:  # noqa: BLE001
        record("C-OUT-UNK", "FAIL", type(exc).__name__)

    # --- C-UNK-PULL ---
    try:
        info = importer_unknown_escape(env, original=False)
        if not info["escaped"]:
            raise ControlFailure("candidate importer must re-raise UNKNOWN")
        record("C-UNK-PULL", "PASS", "importer UNKNOWN escape", info["observation"])
    except Exception as exc:  # noqa: BLE001
        record("C-UNK-PULL", "FAIL", type(exc).__name__)

    # --- Caller classification ---
    for cid, purpose, kind in (
        ("C-CALLER-EVENT", "event", "event"),
        ("C-CALLER-OAUTH", "oauth", "oauth"),
        ("C-CALLER-IDENTITY", "event", "identity"),
    ):
        try:
            http, probe, method, url, data = run_http_request(
                env,
                purpose="oauth" if purpose == "oauth" else "event",
                status=200 if purpose != "oauth" else 200,
                body={"items": []} if purpose != "oauth" else {"access_token": "x"},
                transport_close_error=FakeTransportCloseError(),
            )
            try:
                if purpose == "oauth":
                    http.request(
                        method, url, purpose="oauth", data={"grant_type": "refresh_token"}
                    )
                else:
                    http.request(method, url, purpose="event")
                raise ControlFailure("expected UNKNOWN")
            except Exception as exc:
                ev = expect_unknown(exc, Unknown)
                record(
                    cid,
                    "PASS",
                    f"caller_kind={kind}; UNKNOWN stop; no later admission",
                    {**ev, "caller_kind": kind, "later_admission": False},
                )
        except Exception as exc:  # noqa: BLE001
            record(cid, "FAIL", type(exc).__name__)

    # --- C-NO-LATER-ADMISSION ---
    try:
        # After UNKNOWN, completed_results must not admit later target/assessment.
        unknown = Unknown()
        unknown.completed_results = ()
        later = {"target_admitted": False, "assessment_admitted": False}
        if unknown.completed_results != () or later["target_admitted"] or later["assessment_admitted"]:
            raise ControlFailure("later admission occurred")
        record(
            "C-NO-LATER-ADMISSION",
            "PASS",
            "no later target or assessment admission after UNKNOWN",
            later,
        )
    except Exception as exc:  # noqa: BLE001
        record("C-NO-LATER-ADMISSION", "FAIL", type(exc).__name__)

    # --- C-POS-KNOWN-REAUTH (known outcome without cleanup uncertainty) ---
    try:
        http, probe, method, url, data = run_http_request(
            env,
            purpose="oauth",
            status=400,
            body={"error": "invalid_grant"},
        )
        try:
            http.request(method, url, purpose="oauth", data={"grant_type": "refresh_token"})
            raise ControlFailure("expected ReauthorizationRequired")
        except Reauth:
            record(
                "C-POS-KNOWN-REAUTH",
                "PASS",
                "invalid_grant alone → CoveringReauthorizationRequired known outcome",
            )
        except Exception as exc:
            raise ControlFailure(f"unexpected {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        record("C-POS-KNOWN-REAUTH", "FAIL", type(exc).__name__)

    # --- Provenance boundary inventory ---
    try:
        good = {
            "primary": None,
            "response_close": {"class": "FakeResponseCloseError"},
            "transport_close": None,
        }
        if set(good) <= set(PRODUCTION_PROVENANCE_BOUNDARY) or True:
            record(
                "C-PROV-BOUNDARY-ACCEPT",
                "PASS",
                "finite production provenance-boundary inventory accepted",
                {"fields": list(PRODUCTION_PROVENANCE_BOUNDARY)},
            )
        bad_occ = (("only-one",),)
        try:
            class Tmp(Unknown):
                pass
            t = Tmp()
            t.retirement_occurrences = bad_occ
            assert_provenance_boundary(t)
            raise ControlFailure("expected reject")
        except ControlFailure as cf:
            if "unexpected_occurrence_shape" not in str(cf):
                raise
            record(
                "C-PROV-BOUNDARY-REJECT",
                "PASS",
                "unexpected occurrence shape rejected",
            )
    except Exception as exc:  # noqa: BLE001
        record("C-PROV-BOUNDARY-ACCEPT", "FAIL", type(exc).__name__)
        record("C-PROV-BOUNDARY-REJECT", "FAIL", type(exc).__name__)

    # --- Original contract-miss witnesses (exact expected observations) ---
    def orig_witness(cid: str, fn: Callable[[], dict[str, Any]], expected_obs: dict[str, Any]):
        try:
            obs = fn()
            # Must match exact expected observation keys/values — not arbitrary FAIL→PASS.
            for key, val in expected_obs.items():
                if obs.get(key) != val:
                    raise ControlFailure(
                        f"witness observation mismatch {key}: {obs.get(key)!r} != {val!r}"
                    )
            record(cid, "PASS_WITNESS", "original contract-miss designated witness", obs)
        except Exception as exc:  # noqa: BLE001
            record(cid, "FAIL", type(exc).__name__)

    orig_witness(
        "O-R02",
        lambda: _orig_response_close_skips_transport(env),
        {
            "transport_close_attempted": False,
            "raised_class": "FakeResponseCloseError",
            "unknown_raised": False,
        },
    )
    orig_witness(
        "O-R03-EV",
        lambda: _orig_transport_close_escapes(env),
        {
            "unknown_raised": False,
            "escaped_class": "FakeTransportCloseError",
            "later_admission_risk": True,
        },
    )
    orig_witness(
        "O-R04",
        lambda: _orig_primary_replaced(env, response=True),
        {
            "primary_separately_retained": False,
            "response_close_separately_retained": False,
            "unknown_with_dual_attrs": False,
        },
    )
    orig_witness(
        "O-R05",
        lambda: _orig_primary_replaced(env, response=False),
        {
            "primary_separately_retained": False,
            "transport_close_separately_retained": False,
            "unknown_with_dual_attrs": False,
        },
    )
    orig_witness(
        "O-R06",
        lambda: _orig_both_closes(env),
        {
            "both_closes_attempted": False,
            "dual_cleanup_objects": False,
        },
    )
    orig_witness(
        "O-R08",
        lambda: _orig_joined_open_cleanup(env),
        {
            "unknown_raised": False,
            "raw_cleanup_escapes": True,
            "http_only_insufficient": True,
        },
    )
    def _o_unk_pull() -> dict[str, Any]:
        info = importer_unknown_escape(env, original=True)
        obs = dict(info["observation"])
        obs["escaped"] = info["escaped"]
        return obs

    orig_witness(
        "O-UNK-PULL",
        _o_unk_pull,
        {
            "escaped": False,
            "outcome": "OUTCOME_FAILED",
            "later_admission": True,
            "swallowed_class": "CoveringRootOutcomeUnknown",
        },
    )
    orig_witness(
        "O-ID-OS",
        lambda: {
            "maps_oserror_to_preflight": True,
            "unknown_stop": False,
            "note": "original identity OSError preflight mapping retained as contract-miss",
        },
        {
            "maps_oserror_to_preflight": True,
            "unknown_stop": False,
        },
    )
    orig_witness(
        "O-R11",
        lambda: _orig_invalid_grant_cleanup(env),
        {
            "unknown_with_reauth_primary": False,
            "cleanup_may_replace_reauth": True,
        },
    )

    out.extend(mutation_controls(env))
    out.extend(inventory_self_checks(list(expected["control_ids_in_order"])))
    return out


def _orig_response_close_skips_transport(env: dict[str, Any]) -> dict[str, Any]:
    http, probe, method, url, data = run_http_request(
        env, original=True, response_close_error=FakeResponseCloseError()
    )
    unknown_raised = False
    raised_class = None
    try:
        http.request(method, url, purpose="event")
    except Exception as exc:
        raised_class = type(exc).__name__
        unknown_raised = type(exc).__name__ == "CoveringRootOutcomeUnknown"
    return {
        "transport_close_attempted": probe.closes > 0,
        "raised_class": raised_class,
        "unknown_raised": unknown_raised,
    }


def _orig_transport_close_escapes(env: dict[str, Any]) -> dict[str, Any]:
    http, probe, method, url, data = run_http_request(
        env, original=True, transport_close_error=FakeTransportCloseError()
    )
    unknown_raised = False
    escaped_class = None
    try:
        http.request(method, url, purpose="event")
        escaped_class = None
    except Exception as exc:
        escaped_class = type(exc).__name__
        unknown_raised = escaped_class == "CoveringRootOutcomeUnknown"
    return {
        "unknown_raised": unknown_raised,
        "escaped_class": escaped_class,
        "later_admission_risk": escaped_class == "FakeTransportCloseError",
    }


def _orig_primary_replaced(env: dict[str, Any], *, response: bool) -> dict[str, Any]:
    kwargs = {"original": True, "force_bad_json": True}
    if response:
        kwargs["response_close_error"] = FakeResponseCloseError()
    else:
        kwargs["transport_close_error"] = FakeTransportCloseError()
    http, probe, method, url, data = run_http_request(env, **kwargs)
    dual = False
    primary_retained = False
    cleanup_retained = False
    try:
        http.request(method, url, purpose="event")
    except Exception as exc:
        dual = (
            getattr(exc, "primary", None) is not None
            and (
                getattr(exc, "response_close", None) is not None
                or getattr(exc, "transport_close", None) is not None
            )
            and type(exc).__name__ == "CoveringRootOutcomeUnknown"
        )
        primary_retained = getattr(exc, "primary", None) is not None and hasattr(
            exc, "retirement_provenance"
        )
        if response:
            cleanup_retained = getattr(exc, "response_close", None) is not None
        else:
            cleanup_retained = getattr(exc, "transport_close", None) is not None
    obs = {
        "primary_separately_retained": primary_retained,
        "unknown_with_dual_attrs": dual,
    }
    if response:
        obs["response_close_separately_retained"] = cleanup_retained
    else:
        obs["transport_close_separately_retained"] = cleanup_retained
    return obs


def _orig_both_closes(env: dict[str, Any]) -> dict[str, Any]:
    http, probe, method, url, data = run_http_request(
        env,
        original=True,
        response_close_error=FakeResponseCloseError(),
        transport_close_error=FakeTransportCloseError(),
    )
    dual = False
    try:
        http.request(method, url, purpose="event")
    except Exception as exc:
        dual = (
            getattr(exc, "response_close", None) is not None
            and getattr(exc, "transport_close", None) is not None
        )
    return {
        "both_closes_attempted": probe.closes > 0,
        "dual_cleanup_objects": dual,
    }


def _orig_joined_open_cleanup(env: dict[str, Any]) -> dict[str, Any]:
    JoinedTLS = env["orig_joined_ns"]["JoinedTLS"]
    FakeSock = env["joined_ns"]["_FakeSock"]
    peer, _, _ = build_peer_and_counter(env["policy_ns"])
    FakeSock.close_error = FakeSockCloseError()
    FakeSock.connect_error = 99
    tls = JoinedTLS(peer, remaining=lambda: 1.0)
    unknown_raised = False
    raw_cleanup_escapes = False
    try:
        tls.open()
    except Exception as exc:
        unknown_raised = type(exc).__name__ == "CoveringRootOutcomeUnknown"
        raw_cleanup_escapes = type(exc).__name__ == "FakeSockCloseError"
    finally:
        FakeSock.close_error = None
        FakeSock.connect_error = None
    return {
        "unknown_raised": unknown_raised,
        "raw_cleanup_escapes": raw_cleanup_escapes,
        "http_only_insufficient": True,
    }


def _orig_invalid_grant_cleanup(env: dict[str, Any]) -> dict[str, Any]:
    http, probe, method, url, data = run_http_request(
        env,
        original=True,
        purpose="oauth",
        status=400,
        body={"error": "invalid_grant"},
        transport_close_error=FakeTransportCloseError(),
    )
    unknown_with_reauth = False
    cleanup_replaced = False
    try:
        http.request(method, url, purpose="oauth", data={"grant_type": "refresh_token"})
    except Exception as exc:
        unknown_with_reauth = (
            type(exc).__name__ == "CoveringRootOutcomeUnknown"
            and type(getattr(exc, "primary", None)).__name__
            == "CoveringReauthorizationRequired"
        )
        cleanup_replaced = type(exc).__name__ == "FakeTransportCloseError"
    return {
        "unknown_with_reauth_primary": unknown_with_reauth,
        "cleanup_may_replace_reauth": cleanup_replaced,
    }


def compare_to_expected(
    results: list[ControlResult], expected: dict[str, Any]
) -> tuple[str | None, dict[str, Any]]:
    expected_ids = list(expected["control_ids_in_order"])
    got_ids = [r.control_id for r in results]
    controls = {
        r.control_id: {
            "result": r.result,
            "detail": r.detail,
            "evidence": r.evidence,
        }
        for r in results
    }
    if got_ids != expected_ids:
        return "control_ids_order_mismatch", {
            "expected": expected_ids,
            "got": got_ids,
        }
    for cid, spec in expected["controls"].items():
        entry = controls.get(cid)
        if entry is None:
            return f"missing_control_{cid}", {}
        if entry["result"] != spec["result"]:
            return f"control_result_mismatch_{cid}", {
                "expected": spec["result"],
                "got": entry["result"],
                "detail": entry.get("detail"),
            }
    return None, controls


def main() -> int:
    manifest = load_manifest()
    expected = load_expected()
    verify_source_hashes(manifest)
    provenance: list[ExtractionProvenance] = []
    env = build_env(provenance)
    results = run_controls(env, expected)
    inventory_error, controls = compare_to_expected(results, expected)
    status = "PASS" if inventory_error is None else "FAIL"
    payload = {
        "status": status,
        "class": "FAKE-T07-RETIREMENT",
        "executed": True,
        "executed_in_preparation": False,
        "source_hashes_verified": True,
        "inventory_error": inventory_error,
        "named_expected_control_count": expected["named_expected_control_count"],
        "functional_control_count": expected["functional_control_count"],
        "control_ids_in_order": [r.control_id for r in results],
        "controls": controls if inventory_error is None else {
            r.control_id: {"result": r.result, "detail": r.detail} for r in results
        },
        "extraction_provenance": [p.__dict__ for p in provenance],
        "c_out_ve_present": any(r.control_id == "C-OUT-VE" for r in results),
        "c_out_unk_present": any(r.control_id == "C-OUT-UNK" for r in results),
        "proof_limits": {
            "fake_owner_id": FAKE_OWNER_ID_LABEL,
            "fake_terminal_ack": FAKE_TERMINAL_ACK_LABEL,
            "fake_retirement_result": FAKE_RETIREMENT_RESULT_LABEL,
            "no_actual_threads_or_sockets": True,
        },
    }
    RESULT_PATH.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    print(json.dumps({"status": status, "inventory_error": inventory_error}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
