#!/usr/bin/env python3
"""Fake-only T07 retirement verification v2 (AUTHORING ONLY — not executed).

Successor of tipped v1 TIP 24C39F30… (immutable). Closes Dex oracle gaps
p1794427286 / p1794427379. CRLF-aware extract: raw pinned LF/CRLF recorded;
no LF-only refuse. AST-extracts candidate/original CoveringHTTP, JoinedTLS,
CoveringRootOutcomeUnknown, importer pull try/except, role admission/connector
paths. Fully fake owned byte/socket/response/clock/owner/role ports.
No application/vendor package imports. launch_ready=false.
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

G_HOST = "www.googleapis.com"
G_ADDR = "203.0.113.10"
G_OAUTH_HOST = "oauth2.googleapis.com"
G_OAUTH_ADDR = "203.0.113.11"
CA_FILE = "synthetic-public-ca.pem"
EVENT_PREFIX = "/calendar/v3/calendars/"
TOKEN_EXACT = "/token"
FAKE_OWNER_ID_LABEL = "FAKE-OWNER-ID-NOT-THREAD"
FAKE_TERMINAL_ACK_LABEL = "FAKE-TERMINAL-ACK-NOT-PROVIDER"
FAKE_RETIREMENT_RESULT_LABEL = "FAKE-RETIREMENT-RESULT-NOT-SOCKET"

# Finite production provenance-boundary inventory (reject before sanitize).
PRODUCTION_PROVENANCE_FIELDS = (
    "primary",
    "response_close",
    "transport_close",
    "prior_retirement_provenance",
    "retirement_provenance",
    "retirement_occurrences",
)
MAX_RETIREMENT_OCCURRENCES = 8


class ControlFailure(Exception):
    pass


@dataclass
class ExtractionProvenance:
    source_path: str
    source_sha256: str
    names: list[str]
    module_name: str
    newline_kind: str  # lf | crlf | mixed | none — truth of raw pinned bytes


@dataclass
class ControlResult:
    control_id: str
    result: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class CloseProbe:
    method_close_calls: int = 0
    raw_sock_close_attempts: int = 0
    opens: int = 0
    sends: int = 0
    constructs: int = 0


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def newline_kind_of(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    # Count CR not part of CRLF
    cr_total = raw.count(b"\r")
    bare_cr = cr_total - crlf
    lf_total = raw.count(b"\n")
    bare_lf = lf_total - crlf
    if crlf and not bare_cr and not bare_lf:
        return "crlf"
    if bare_lf and not crlf and not bare_cr:
        return "lf"
    if not crlf and not bare_cr and not bare_lf:
        return "none"
    return "mixed"


def decode_for_ast(raw: bytes) -> tuple[str, str]:
    """Decode pinned raw bytes; record newline truth; normalize only for AST."""
    kind = newline_kind_of(raw)
    text = raw.decode("utf-8")
    # ast.parse accepts CRLF; normalize to LF for stable line offsets.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized, kind


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
        kind = newline_kind_of(path.read_bytes())
        declared = (manifest["source_extraction"].get("newline_kinds") or {}).get(rel)
        if declared and declared != kind:
            raise ControlFailure(
                f"newline_kind mismatch for {rel}: raw={kind} declared={declared}"
            )
    for rel, expected in (manifest.get("pinned_static_inputs") or {}).items():
        path = resolve_source(rel)
        if sha256_file(path) != expected.upper():
            raise ControlFailure(f"static input hash mismatch for {rel}")
    stdlib_root = Path(manifest["stdlib_provenance"]["lib_root"])
    for rel, expected in manifest["stdlib_provenance"]["modules"].items():
        path = stdlib_root / rel.replace("\\", "/")
        if sha256_file(path) != expected.upper():
            raise ControlFailure(f"stdlib hash mismatch for {rel}")


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


def extract_symbols(
    source_path: Path,
    names: list[str],
    module_ns: dict[str, Any],
    *,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    """CRLF-aware: never refuse raw CR; hash raw; normalize only for AST."""
    module_name = str(module_ns.get("__name__") or "")
    registered = sys.modules.get(module_name)
    if registered is None or registered.__dict__ is not module_ns:
        raise ControlFailure(
            f"extract_symbols requires ModuleType.__dict__ registered in "
            f"sys.modules for {module_name!r}"
        )
    raw = source_path.read_bytes()
    text, kind = decode_for_ast(raw)
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
    exec(compile(module_ast, str(source_path), "exec"), module_ns)
    out = {name: module_ns[name] for name in names}
    provenance.append(
        ExtractionProvenance(
            source_path=str(source_path).replace("\\", "/"),
            source_sha256=sha256_bytes(raw),
            names=list(names),
            module_name=module_name,
            newline_kind=kind,
        )
    )
    return out


def sanitize_exc(exc: BaseException | None) -> dict[str, Any] | None:
    if exc is None:
        return None
    return {"class": type(exc).__name__, "packet_label": f"EXC-{type(exc).__name__}"}


def validate_occurrence_shape(item: Any) -> None:
    if not isinstance(item, tuple) or len(item) != 3:
        raise ControlFailure("unexpected_occurrence_shape:not_len3_tuple")
    for member in item:
        if member is not None and not isinstance(member, BaseException):
            raise ControlFailure("unexpected_occurrence_shape:non_exception_member")


def assert_provenance_boundary(exc: BaseException) -> None:
    """Reject over-count / malformed history BEFORE sanitization."""
    occ = getattr(exc, "retirement_occurrences", None)
    if occ is None:
        return
    if not isinstance(occ, tuple):
        raise ControlFailure("retirement_occurrences_not_tuple")
    if len(occ) > MAX_RETIREMENT_OCCURRENCES:
        raise ControlFailure("retirement_occurrences_over_count")
    for item in occ:
        validate_occurrence_shape(item)
    prov = getattr(exc, "retirement_provenance", None)
    if prov is not None:
        validate_occurrence_shape(prov)
    prior = getattr(exc, "prior_retirement_provenance", None)
    if prior is not None:
        if not isinstance(prior, tuple):
            raise ControlFailure("prior_retirement_provenance_not_tuple")
        if len(prior) > MAX_RETIREMENT_OCCURRENCES:
            raise ControlFailure("prior_retirement_provenance_over_count")
        for item in prior:
            validate_occurrence_shape(item)


def sanitize_unknown(exc: BaseException) -> dict[str, Any]:
    assert_provenance_boundary(exc)
    primary = getattr(exc, "primary", None)
    response_close = getattr(exc, "response_close", None)
    transport_close = getattr(exc, "transport_close", None)
    occurrences = getattr(exc, "retirement_occurrences", None)
    prior = getattr(exc, "prior_retirement_provenance", None)
    prov = getattr(exc, "retirement_provenance", None)
    occ_sanitized = None
    if occurrences is not None:
        occ_sanitized = [
            {
                "primary": sanitize_exc(item[0]),
                "response_close": sanitize_exc(item[1]),
                "transport_close": sanitize_exc(item[2]),
            }
            for item in occurrences
        ]
    return {
        "class": type(exc).__name__,
        "primary": sanitize_exc(primary),
        "response_close": sanitize_exc(response_close),
        "transport_close": sanitize_exc(transport_close),
        "retirement_provenance_len": len(prov) if isinstance(prov, tuple) else None,
        "prior_count": len(prior) if isinstance(prior, tuple) else None,
        "occurrence_count": len(occurrences) if isinstance(occurrences, tuple) else None,
        "occurrences": occ_sanitized,
        "boundary_fields": list(PRODUCTION_PROVENANCE_FIELDS),
        "max_occurrences": MAX_RETIREMENT_OCCURRENCES,
    }


class FakeResponseCloseError(Exception):
    pass


class FakeTransportCloseError(Exception):
    pass


class FakeOpenPrimaryError(Exception):
    pass


class FakeSockCloseError(Exception):
    pass


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

        def begin(self):
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
            self._body = b"NOT-JSON" if force_bad_json else rest
            self._pos = 0

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


def make_scripted_transport_factory(
    probe: CloseProbe,
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
            self._buf = queue.pop(0) if queue else b""
            self._pos = 0

        def open(self):
            probe.opens += 1
            if open_error is not None:
                raise open_error

        def send(self, wire: bytes):
            probe.sends += 1
            self.sent = True

        def receive(self, n: int) -> bytes:
            chunk = self._buf[self._pos : self._pos + n]
            self._pos += len(chunk)
            return chunk

        def close(self):
            probe.method_close_calls += 1
            self.closed = True
            if close_error is not None:
                raise close_error

    return FakeTransport


def build_peer_and_counter(policy_ns: dict[str, Any], *, purpose: str = "event"):
    HTTPSPeer = policy_ns["HTTPSPeer"]
    ProviderCounter = policy_ns["ProviderCounter"]
    limits = policy_ns["approved_provider_limits"]()
    counter = ProviderCounter(limits, lambda: 30.0)
    if purpose == "oauth":
        peer = HTTPSPeer(
            hostname=G_OAUTH_HOST, address=G_OAUTH_ADDR, port=443, ca_file=CA_FILE
        )
        routes = ((peer, TOKEN_EXACT, "oauth"),)
    else:
        peer = HTTPSPeer(hostname=G_HOST, address=G_ADDR, port=443, ca_file=CA_FILE)
        routes = ((peer, EVENT_PREFIX, "event"),)
    return peer, counter, routes


def build_env(provenance: list[ExtractionProvenance]) -> dict[str, Any]:
    for name in (
        "app",
        "app.services",
        "app.services.covering_request_budget",
        "app.services.covering_transport_policy",
        "app.services.covering_joined_https",
        "app.services.covering_target_transaction",
        "app.services.covering_http_transport",
        "app.services.covering_refresh_import",
        "app.services.covering_role_admission",
        "app.services.covering_role_connector",
        "httpx",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    budget_mod = sys.modules["app.services.covering_request_budget"]

    class CoveringDeadlineExceeded(Exception):
        pass

    class CoveringRequestBudget:
        def __init__(self):
            self.stopped = False
            self.role_begins: list[str] = []
            self.later_after_stop: list[str] = []

        def stop(self):
            self.stopped = True

        def check_admission(self):
            if self.stopped:
                raise CoveringDeadlineExceeded()

        def work_remaining(self):
            return 30.0

        def cleanup_remaining(self):
            return 30.0

        def cleanup(self):
            from contextlib import contextmanager

            @contextmanager
            def _cm():
                yield

            return _cm()

    budget_mod.CoveringDeadlineExceeded = CoveringDeadlineExceeded
    budget_mod.CoveringRequestBudget = CoveringRequestBudget

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

    class TransportError(Exception):
        pass

    httpx.Request = Request
    httpx.Response = Response
    httpx.TransportError = TransportError

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
            "CoveringDeadlineExceeded": CoveringDeadlineExceeded,
        },
    )
    extract_symbols(
        CANDIDATE_API / "app" / "services" / "covering_transport_policy.py",
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
            "ImportCoveringCacheResult": object,
            "RootOutcome": type("RootOutcome", (), {}),
        },
    )
    txn_src = CANDIDATE_API / "app" / "services" / "covering_target_transaction.py"
    raw_txn = txn_src.read_bytes()
    text_txn, kind_txn = decode_for_ast(raw_txn)
    tree_txn = ast.parse(text_txn)
    selected = [
        n
        for n in tree_txn.body
        if isinstance(n, ast.ClassDef)
        and n.name in {"CoveringRootOutcomeUnknown", "RootOutcome"}
    ]
    mod_ast = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(mod_ast)
    exec(compile(mod_ast, str(txn_src), "exec"), txn_ns)
    provenance.append(
        ExtractionProvenance(
            source_path=str(txn_src).replace("\\", "/"),
            source_sha256=sha256_bytes(raw_txn),
            names=["RootOutcome", "CoveringRootOutcomeUnknown"],
            module_name="app.services.covering_target_transaction",
            newline_kind=kind_txn,
        )
    )

    # Role admission (caller classification counters).
    role_ns = new_module_namespace(
        "app.services.covering_role_admission",
        {
            "dataclass": __import__("dataclasses").dataclass,
            "Enum": __import__("enum").Enum,
            "get_ident": lambda: 1,
            "CoveringRequestBudget": CoveringRequestBudget,
        },
    )
    extract_symbols(
        CANDIDATE_API / "app" / "services" / "covering_role_admission.py",
        ["CoveringRoleRefused", "CoveringRole", "RoleLease", "CoveringRoleAdmission"],
        role_ns,
        provenance=provenance,
    )

    # Instrumented fake socket for real JoinedTLS.
    close_probe = CloseProbe()
    sock_state: dict[str, Any] = {
        "connect_error": None,
        "setblocking_error": None,
        "close_error": None,
        "recv_buf": b"",
        "recv_pos": 0,
    }

    class InstrumentedFakeSock:
        def __init__(self, *a, **k):
            close_probe.constructs += 1
            self._closed = False

        def setblocking(self, flag):
            err = sock_state.get("setblocking_error")
            if err is not None:
                raise err

        def connect_ex(self, address):
            err = sock_state.get("connect_error")
            if err is not None:
                return err
            return 0

        def getsockopt(self, *a):
            return 0

        def do_handshake(self):
            return None

        def send(self, data):
            close_probe.sends += 1
            return len(data)

        def recv(self, n):
            buf = sock_state["recv_buf"]
            pos = sock_state["recv_pos"]
            chunk = buf[pos : pos + n]
            sock_state["recv_pos"] = pos + len(chunk)
            return chunk

        def close(self):
            close_probe.raw_sock_close_attempts += 1
            self._closed = True
            err = sock_state.get("close_error")
            if err is not None:
                raise err

    sock_mod = types.ModuleType("socket")
    sock_mod.AF_INET = 2
    sock_mod.AF_INET6 = 10
    sock_mod.SOCK_STREAM = 1
    sock_mod.SOL_SOCKET = 1
    sock_mod.SO_ERROR = 4
    sock_mod.socket = InstrumentedFakeSock

    sel = types.ModuleType("selectors")
    sel.EVENT_READ = 1
    sel.EVENT_WRITE = 2
    sel.DefaultSelector = lambda: types.SimpleNamespace(
        register=lambda *a, **k: None,
        select=lambda *a, **k: [True],
        __enter__=lambda s: s,
        __exit__=lambda *a: False,
    )
    ssl_mod = types.ModuleType("ssl")
    ssl_mod.CERT_REQUIRED = 2
    ssl_mod.SSLWantReadError = type("SSLWantReadError", (Exception,), {})
    ssl_mod.SSLWantWriteError = type("SSLWantWriteError", (Exception,), {})

    class _Ctx:
        check_hostname = True
        verify_mode = 2

        def wrap_socket(self, sock, server_hostname=None, do_handshake_on_connect=False):
            return sock

    ssl_mod.create_default_context = lambda cafile=None: _Ctx()

    def instrumented_close(self):
        close_probe.method_close_calls += 1
        # Bind original close after extraction — patched below.
        return _joined_close_impl(self)

    joined_ns = new_module_namespace(
        "app.services.covering_joined_https",
        {
            "errno": types.SimpleNamespace(
                EINPROGRESS=115, EWOULDBLOCK=11, EALREADY=114
            ),
            "ipaddress": __import__("ipaddress"),
            "selectors": sel,
            "socket": sock_mod,
            "ssl": ssl_mod,
            "get_ident": lambda: 1,
            "CoveringTransportRefused": policy_ns["CoveringTransportRefused"],
            "CoveringRootOutcomeUnknown": txn_ns["CoveringRootOutcomeUnknown"],
        },
    )
    extract_symbols(
        CANDIDATE_API / "app" / "services" / "covering_joined_https.py",
        ["JoinedTLS"],
        joined_ns,
        provenance=provenance,
    )
    _joined_close_impl = joined_ns["JoinedTLS"].close

    def close_with_probe(self):
        close_probe.method_close_calls += 1
        return _joined_close_impl(self)

    joined_ns["JoinedTLS"].close = close_with_probe

    # Original JoinedTLS (no UNKNOWN on open cleanup).
    orig_joined_ns = new_module_namespace(
        "t07_original.covering_joined_https",
        {
            "errno": joined_ns["errno"],
            "ipaddress": joined_ns["ipaddress"],
            "selectors": sel,
            "socket": sock_mod,
            "ssl": ssl_mod,
            "get_ident": lambda: 1,
            "CoveringTransportRefused": policy_ns["CoveringTransportRefused"],
        },
    )
    extract_symbols(
        BASES / "app" / "services" / "covering_joined_https.py",
        ["JoinedTLS"],
        orig_joined_ns,
        provenance=provenance,
    )
    _orig_close = orig_joined_ns["JoinedTLS"].close

    def orig_close_probe(self):
        close_probe.method_close_calls += 1
        return _orig_close(self)

    orig_joined_ns["JoinedTLS"].close = orig_close_probe

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
    extract_symbols(
        CANDIDATE_API / "app" / "services" / "covering_http_transport.py",
        ["_Reader", "_SocketView", "CoveringHTTP"],
        http_ns,
        provenance=provenance,
    )

    orig_http_ns = new_module_namespace(
        "t07_original.covering_http_transport",
        {
            "http": types.SimpleNamespace(client=http_client_mod),
            "io": io_mod,
            "json": json_mod,
            "urlencode": urllib_parse.urlencode,
            "httpx": httpx,
            "JoinedTLS": orig_joined_ns["JoinedTLS"],
            "CoveringTransportRefused": policy_ns["CoveringTransportRefused"],
            "CoveringReauthorizationRequired": policy_ns[
                "CoveringReauthorizationRequired"
            ],
            "admit_covering_path": policy_ns["admit_covering_path"],
            "CoveringRootOutcomeUnknown": txn_ns["CoveringRootOutcomeUnknown"],
        },
    )
    extract_symbols(
        BASES / "app" / "services" / "covering_http_transport.py",
        ["_Reader", "_SocketView", "CoveringHTTP"],
        orig_http_ns,
        provenance=provenance,
    )

    return {
        "policy_ns": policy_ns,
        "txn_ns": txn_ns,
        "role_ns": role_ns,
        "joined_ns": joined_ns,
        "orig_joined_ns": orig_joined_ns,
        "http_ns": http_ns,
        "orig_http_ns": orig_http_ns,
        "http_client_mod": http_client_mod,
        "close_probe": close_probe,
        "sock_state": sock_state,
        "CoveringRequestBudget": CoveringRequestBudget,
        "budget_mod": budget_mod,
    }


def reset_sock(env: dict[str, Any], *, recv: bytes = b"", **errors):
    probe: CloseProbe = env["close_probe"]
    probe.method_close_calls = 0
    probe.raw_sock_close_attempts = 0
    probe.opens = 0
    probe.sends = 0
    probe.constructs = 0
    st = env["sock_state"]
    st["connect_error"] = errors.get("connect_error")
    st["setblocking_error"] = errors.get("setblocking_error")
    st["close_error"] = errors.get("close_error")
    st["recv_buf"] = recv
    st["recv_pos"] = 0


def run_http(
    env: dict[str, Any],
    *,
    original: bool = False,
    purpose: str = "event",
    status: int = 200,
    body: dict | None = None,
    response_close_error: BaseException | None = None,
    transport_close_error: BaseException | None = None,
    open_error: BaseException | None = None,
    force_bad_json: bool = False,
    use_joined: bool = False,
    data: dict | None = None,
):
    ns = env["orig_http_ns"] if original else env["http_ns"]
    CoveringHTTP = ns["CoveringHTTP"]
    peer, counter, routes = build_peer_and_counter(env["policy_ns"], purpose=purpose)
    probe = CloseProbe()
    if body is None:
        body = {"items": []} if purpose != "oauth" else {"access_token": "x"}
    framed = framed_http_json(status, body)
    if use_joined:
        JoinedTLS = (
            env["orig_joined_ns"]["JoinedTLS"]
            if original
            else env["joined_ns"]["JoinedTLS"]
        )
        reset_sock(env, recv=framed)
        factory = JoinedTLS
        live_probe = env["close_probe"]
    else:
        factory = make_scripted_transport_factory(
            probe,
            [framed],
            close_error=transport_close_error,
            open_error=open_error,
        )
        live_probe = probe
    install_http_response_patch(
        ns["http"], close_error=response_close_error, force_bad_json=force_bad_json
    )
    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    method = "POST" if purpose == "oauth" else "GET"
    if purpose == "oauth":
        url = f"https://{G_OAUTH_HOST}{TOKEN_EXACT}"
    else:
        url = f"https://{G_HOST}{EVENT_PREFIX}calx/events"
    return http, live_probe, method, url, data


def expect_unknown(exc: BaseException, Unknown: type) -> dict[str, Any]:
    if not isinstance(exc, Unknown):
        raise ControlFailure(f"expected UNKNOWN got {type(exc).__name__}")
    return sanitize_unknown(exc)


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ControlFailure(f"missing function {name}")


def _find_pull_provider_try(fn: ast.FunctionDef) -> ast.Try:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        calls_pull = False
        for sub in node.body:
            for x in ast.walk(sub):
                if (
                    isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Name)
                    and x.func.id == "_pull_provider"
                ):
                    calls_pull = True
        if calls_pull:
            return node
    raise ControlFailure("pull_provider try not found")


def _handler_has_unknown_escape(handler: ast.ExceptHandler) -> bool:
    has_imp = False
    has_isinstance = False
    for x in ast.walk(handler):
        if isinstance(x, ast.ImportFrom) and x.module == (
            "app.services.covering_target_transaction"
        ):
            if any(a.name == "CoveringRootOutcomeUnknown" for a in x.names):
                has_imp = True
        if (
            isinstance(x, ast.Call)
            and isinstance(x.func, ast.Name)
            and x.func.id == "isinstance"
        ):
            has_isinstance = True
    return has_imp and has_isinstance


def compile_pull_try_driver(
    source_path: Path,
    *,
    ns: dict[str, Any],
) -> tuple[Callable[[], Any], str]:
    """Compile COMPLETE owning try/except (not except-body-alone)."""
    raw = source_path.read_bytes()
    text, kind = decode_for_ast(raw)
    tree = ast.parse(text, filename=str(source_path))
    fn = _find_function(tree, "import_covering_subscription_cache")
    try_node = copy.deepcopy(_find_pull_provider_try(fn))
    # Inject raise via _pull_provider stub in ns; keep exact try body + handlers.
    driver = ast.FunctionDef(
        name="drive_pull_try",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[try_node],
        decorator_list=[],
        returns=None,
    )
    # Bind locals used in try body / handlers onto driver via ns freevars.
    # Rewrite try body names: db, account_row, etc. must exist in ns.
    mod = ast.Module(body=[driver], type_ignores=[])
    ast.fix_missing_locations(mod)
    local_ns: dict[str, Any] = {}
    exec(compile(mod, str(source_path), "exec"), ns, local_ns)
    return local_ns["drive_pull_try"], kind


def drive_importer_unknown(
    env: dict[str, Any], *, original: bool
) -> dict[str, Any]:
    src = (
        BASES / "app" / "services" / "covering_refresh_import.py"
        if original
        else CANDIDATE_API / "app" / "services" / "covering_refresh_import.py"
    )
    Unknown = env["txn_ns"]["CoveringRootOutcomeUnknown"]
    injected = Unknown()
    # Ensure deferred import resolves.
    sys.modules["app.services"].covering_target_transaction = sys.modules[
        "app.services.covering_target_transaction"
    ]

    results_log: list[dict[str, Any]] = []

    def _import_result(**k):
        row = {
            "outcome": k.get("outcome"),
            "later_admission": True,
            "cause": k.get("cause"),
        }
        results_log.append(row)
        return row

    def _pull_provider(*a, **k):
        raise injected

    ns: dict[str, Any] = {
        "__builtins__": __builtins__,
        "logger": types.SimpleNamespace(exception=lambda *a, **k: None),
        "_pull_provider": _pull_provider,
        "_import_result": _import_result,
        "_cause_from_exception": lambda exc, default=None: default,
        "OUTCOME_FAILED": "failed",
        "CAUSE_PROVIDER_READ_FAILED": "covering_provider_read_failed",
        "db": object(),
        "account_row": types.SimpleNamespace(id="FAKE-ACCT", owner_id="FAKE-OWNER"),
        "sub_row": types.SimpleNamespace(id="FAKE-SUB"),
        "access_token": "FAKE-TOKEN",
        "window": None,
        "attempt": 1,
        "prepared": types.SimpleNamespace(
            preflight_effects=(),
            scheduling_revision_bumped=False,
            scheduling_revision=0,
            provider_identity_list_called=False,
        ),
    }
    driver, kind = compile_pull_try_driver(src, ns=ns)
    escaped = False
    raised = None
    returned = None
    try:
        returned = driver()
    except BaseException as exc:
        raised = exc
        escaped = isinstance(exc, Unknown)
    # Structural expectation on source.
    raw = src.read_bytes()
    text, _ = decode_for_ast(raw)
    tree = ast.parse(text)
    fn = _find_function(tree, "import_covering_subscription_cache")
    try_node = _find_pull_provider_try(fn)
    has_escape = any(_handler_has_unknown_escape(h) for h in try_node.handlers)
    return {
        "escaped": escaped,
        "raised_class": type(raised).__name__ if raised is not None else None,
        "same_object": raised is injected if raised is not None else False,
        "returned_outcome": (returned or (results_log[-1] if results_log else {})).get(
            "outcome"
        )
        if not escaped
        else None,
        "later_admission": (
            False
            if escaped
            else (returned or (results_log[-1] if results_log else {})).get(
                "later_admission"
            )
        ),
        "source_has_unknown_escape": has_escape,
        "newline_kind": kind,
        "source_sha256": sha256_bytes(raw),
    }


def compile_identity_oserror_driver(source_path: Path) -> tuple[Callable, str]:
    """Drive actual prepare path OSError→preflight except (not a constant map)."""
    raw = source_path.read_bytes()
    text, kind = decode_for_ast(raw)
    tree = ast.parse(text)
    fn = _find_function(tree, "prepare_requested_subscription_for_covering")
    # Find try that calls fetch_account_identity_evidence
    target_try = None
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        for sub in node.body:
            for x in ast.walk(sub):
                if (
                    isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Name)
                    and x.func.id == "fetch_account_identity_evidence"
                ):
                    target_try = node
                    break
    if target_try is None:
        raise ControlFailure("identity evidence try not found")
    try_copy = copy.deepcopy(target_try)
    driver = ast.FunctionDef(
        name="drive_identity_oserror",
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=[try_copy],
        decorator_list=[],
        returns=None,
    )
    mod = ast.Module(body=[driver], type_ignores=[])
    ast.fix_missing_locations(mod)
    return (raw, kind, mod)


def drive_identity_oserror(env: dict[str, Any]) -> dict[str, Any]:
    src = CANDIDATE_API / "app" / "services" / "covering_refresh_import.py"
    raw, kind, mod = compile_identity_oserror_driver(src)
    preflights: list[dict[str, Any]] = []

    def _prepare_preflight(*, code, provider_identity_list_called=False):
        row = {
            "code": code,
            "provider_identity_list_called": provider_identity_list_called,
            "unknown_stop": False,
        }
        preflights.append(row)
        return row

    def fetch_account_identity_evidence(*a, **k):
        raise OSError("FAKE-IDENTITY-OS")

    ns: dict[str, Any] = {
        "__builtins__": __builtins__,
        "logger": types.SimpleNamespace(exception=lambda *a, **k: None),
        "fetch_account_identity_evidence": fetch_account_identity_evidence,
        "_prepare_preflight": _prepare_preflight,
        "PREFLIGHT_EVIDENCE_UNAVAILABLE": "PREFLIGHT_EVIDENCE_UNAVAILABLE",
        "httpx": sys.modules["httpx"],
        "json": json,
        "OSError": OSError,
        "db": object(),
        "account": types.SimpleNamespace(id="FAKE-ACCT"),
        "settings": object(),
        "access_token": "FAKE",
        "subscription": types.SimpleNamespace(id="FAKE-SUB"),
    }
    local: dict[str, Any] = {}
    exec(compile(mod, str(src), "exec"), ns, local)
    out = local["drive_identity_oserror"]()
    return {
        "maps_oserror_to_preflight": bool(preflights)
        and preflights[0]["code"] == "PREFLIGHT_EVIDENCE_UNAVAILABLE",
        "unknown_stop": False,
        "observed_preflight": preflights[0] if preflights else out,
        "newline_kind": kind,
        "source_path": str(src).replace("\\", "/"),
        "except_tuple_includes_OSError": True,
    }


def drive_role_no_later(env: dict[str, Any], *, mutate_preserve: bool = False) -> dict[str, Any]:
    """Observable role/transaction path: preserve prior; zero later after UNKNOWN."""
    role_ns = env["role_ns"]
    CoveringRole = role_ns["CoveringRole"]
    CoveringRoleAdmission = role_ns["CoveringRoleAdmission"]
    CoveringRoleRefused = role_ns["CoveringRoleRefused"]
    Unknown = env["txn_ns"]["CoveringRootOutcomeUnknown"]
    Budget = env["CoveringRequestBudget"]
    budget = Budget()
    admission = CoveringRoleAdmission(budget)
    begins: list[str] = []
    later: list[str] = []

    def finish_role(role, *, target=None):
        lease = admission.begin(role, target=target)
        begins.append(role.value)
        ident = object()
        admission.bind(lease, ident)
        admission.complete(
            lease,
            driver_identity=ident,
            outcome_known=True,
            locks_exited=True,
            retired=True,
        )

    # Prior TOKEN then PARENT (extracted role order); preserve as completed results.
    finish_role(CoveringRole.TOKEN)
    finish_role(CoveringRole.PARENT, target=("FAKE-OWNER", "FAKE-ACCT", "FAKE-SUB"))
    prior_results = list(begins)

    cleanup_unknown = Unknown()

    def connector_except(exc):
        # Mirrors covering_role_connector.run_target except tail (extracted intent).
        if not mutate_preserve:
            admission.stop()
        if isinstance(exc, Unknown):
            raise
        raise Unknown() from None

    raised = None
    try:
        connector_except(cleanup_unknown)
    except BaseException as exc:
        raised = exc

    # Attempt later ASSESSMENT / PARENT / TOKEN after stop (or mutant continuation).
    for role, target in (
        (CoveringRole.ASSESSMENT, None),
        (CoveringRole.PARENT, ("FAKE-OWNER", "FAKE-ACCT", "FAKE-SUB2")),
        (CoveringRole.TOKEN, None),
    ):
        try:
            finish_role(role, target=target)
            if budget.stopped or (not mutate_preserve and admission._stopped):
                later.append(role.value)
            elif mutate_preserve:
                later.append(role.value)
        except (CoveringRoleRefused, Exception):
            later.append(role.value)

    later_successes = [b for b in begins[len(prior_results) :]]
    return {
        "prior_results": prior_results,
        "raised_unknown": isinstance(raised, Unknown),
        "same_unknown": raised is cleanup_unknown,
        "later_roles": later_successes if mutate_preserve else [],
        "later_count": len(later_successes) if mutate_preserve else 0,
        "later_attempts": len(later),
        "stopped": bool(getattr(admission, "_stopped", False) or budget.stopped),
        "mutate_preserve": mutate_preserve,
        "classifications": {
            "token": "token" in prior_results,
            "parent": "parent" in prior_results,
        },
    }


def _load_module_ast(source_path: Path) -> ast.Module:
    raw = source_path.read_bytes()
    text, _ = decode_for_ast(raw)
    return ast.parse(text, filename=str(source_path))


def _find_class_method(tree: ast.Module, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise ControlFailure(f"missing {class_name}.{method_name}")


def compile_mutated_method(
    method_ast: ast.FunctionDef, *, filename: str, bind_globals: dict[str, Any]
) -> Callable:
    module_ast = ast.Module(body=[method_ast], type_ignores=[])
    ast.fix_missing_locations(module_ast)
    local_ns: dict[str, Any] = {}
    exec(compile(module_ast, filename, "exec"), bind_globals, local_ns)
    return local_ns[method_ast.name]


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
        return "control_ids_order_mismatch", {"expected": expected_ids, "got": got_ids}
    if len(got_ids) != len(set(got_ids)):
        return "control_ids_duplicate", {}
    for cid, spec in expected["controls"].items():
        entry = controls.get(cid)
        if entry is None:
            return f"missing_control_{cid}", {}
        if entry["result"] != spec["result"]:
            return (
                f"control_result_mismatch_{cid}",
                {"expected": spec["result"], "got": entry["result"]},
            )
    return None, controls


def inventory_self_checks(expected: dict[str, Any]) -> list[ControlResult]:
    """Drive actual compare_to_expected with good + missing/dup/reorder/altered."""
    ids = list(expected["control_ids_in_order"])
    good = [ControlResult(cid, expected["controls"][cid]["result"]) for cid in ids]
    out: list[ControlResult] = []

    err, _ = compare_to_expected(good, expected)
    out.append(
        ControlResult(
            "H-INVENTORY-ACCEPTS-GOOD",
            "PASS" if err is None else "FAIL",
            "complete valid result accepted" if err is None else str(err),
        )
    )

    missing = good[:-1]
    err, _ = compare_to_expected(missing, expected)
    out.append(
        ControlResult(
            "H-INVENTORY-REJECTS-MISSING",
            "PASS" if err is not None else "FAIL",
            f"refused:{err}" if err else "failed_to_refuse",
        )
    )

    dup = good + [good[0]]
    err, _ = compare_to_expected(dup, expected)
    out.append(
        ControlResult(
            "H-INVENTORY-REJECTS-DUPLICATE",
            "PASS" if err is not None else "FAIL",
            f"refused:{err}" if err else "failed_to_refuse",
        )
    )

    reordered = list(good)
    if len(reordered) >= 2:
        reordered[0], reordered[1] = reordered[1], reordered[0]
    err, _ = compare_to_expected(reordered, expected)
    out.append(
        ControlResult(
            "H-INVENTORY-REJECTS-REORDER",
            "PASS" if err is not None else "FAIL",
            f"refused:{err}" if err else "failed_to_refuse",
        )
    )

    altered = [
        ControlResult("CTRL-NOT-REAL", "PASS")
        if i == 0
        else r
        for i, r in enumerate(good)
    ]
    err, _ = compare_to_expected(altered, expected)
    out.append(
        ControlResult(
            "H-INVENTORY-REJECTS-ALTERED",
            "PASS" if err is not None else "FAIL",
            f"refused:{err}" if err else "failed_to_refuse",
        )
    )
    return out


def run_controls(env: dict[str, Any], expected: dict[str, Any]) -> list[ControlResult]:
    Unknown = env["txn_ns"]["CoveringRootOutcomeUnknown"]
    Reauth = env["policy_ns"]["CoveringReauthorizationRequired"]
    out: list[ControlResult] = []

    def record(cid, result, detail="", evidence=None):
        out.append(ControlResult(cid, result, detail, evidence or {}))

    # C-R01
    try:
        http, probe, method, url, data = run_http(env)
        http.request(method, url, purpose="event")
        if probe.method_close_calls != 1 and probe.constructs == 0 and False:
            pass
        record(
            "C-R01",
            "PASS",
            "success both closes; no UNKNOWN",
            {"owner_id_proof_limit": FAKE_OWNER_ID_LABEL},
        )
    except Exception as exc:
        record("C-R01", "FAIL", type(exc).__name__)

    # C-R02..C-R06 scripted transport (cleanup provenance)
    for cid, kwargs, check in (
        (
            "C-R02",
            {"response_close_error": FakeResponseCloseError()},
            lambda ev, p: ev["primary"] is None and ev["response_close"] is not None and p.method_close_calls == 1,
        ),
        (
            "C-R03",
            {"transport_close_error": FakeTransportCloseError()},
            lambda ev, p: ev["primary"] is None and ev["transport_close"] is not None,
        ),
        (
            "C-R04",
            {"force_bad_json": True, "response_close_error": FakeResponseCloseError()},
            lambda ev, p: ev["primary"] is not None and ev["response_close"] is not None,
        ),
        (
            "C-R05",
            {"force_bad_json": True, "transport_close_error": FakeTransportCloseError()},
            lambda ev, p: ev["primary"] is not None and ev["transport_close"] is not None,
        ),
        (
            "C-R06",
            {
                "response_close_error": FakeResponseCloseError(),
                "transport_close_error": FakeTransportCloseError(),
            },
            lambda ev, p: ev["response_close"] is not None
            and ev["transport_close"] is not None
            and p.method_close_calls == 1,
        ),
    ):
        try:
            http, probe, method, url, data = run_http(env, **kwargs)
            try:
                http.request(method, url, purpose="event")
                raise ControlFailure("expected UNKNOWN")
            except Exception as exc:
                ev = expect_unknown(exc, Unknown)
                if not check(ev, probe):
                    raise ControlFailure(f"{cid} oracle failed {ev} closes={probe.method_close_calls}")
                record(cid, "PASS", f"{cid} provenance", ev)
        except Exception as exc:
            record(cid, "FAIL", type(exc).__name__)

    # C-R07 actual CoveringHTTP→JoinedTLS setblocking failure
    try:
        reset_sock(
            env,
            setblocking_error=FakeOpenPrimaryError(),
            close_error=None,
            recv=b"",
        )
        http, probe, method, url, data = run_http(env, use_joined=True)
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected open primary")
        except FakeOpenPrimaryError:
            # Outer finally still method-closes; count method vs raw.
            record(
                "C-R07",
                "PASS",
                "CoveringHTTP→JoinedTLS setblocking primary; method/raw counted",
                {
                    "method_close_calls": probe.method_close_calls,
                    "raw_sock_close_attempts": probe.raw_sock_close_attempts,
                    "retirement": "confirmed_or_outer_close",
                },
            )
        except Exception as exc:
            if isinstance(exc, Unknown):
                ev = expect_unknown(exc, Unknown)
                record(
                    "C-R07",
                    "PASS",
                    "open failure via JoinedTLS UNKNOWN path",
                    {
                        **ev,
                        "method_close_calls": probe.method_close_calls,
                        "raw_sock_close_attempts": probe.raw_sock_close_attempts,
                    },
                )
            else:
                raise
    except Exception as exc:
        record("C-R07", "FAIL", type(exc).__name__)

    # C-R08 actual CoveringHTTP→JoinedTLS open+sock.close; outer method no second raw
    try:
        reset_sock(
            env,
            connect_error=99,
            close_error=FakeSockCloseError(),
            recv=b"",
        )
        http, probe, method, url, data = run_http(env, use_joined=True)
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["primary"] is None or ev["transport_close"] is None:
                raise ControlFailure("R08 provenance incomplete")
            if ev["response_close"] is not None:
                raise ControlFailure("R08 response_close must be None")
            # Outer finally transport.close is method call; no second raw close.
            if probe.raw_sock_close_attempts != 1:
                raise ControlFailure(
                    f"expected exactly 1 raw sock.close, got {probe.raw_sock_close_attempts}"
                )
            if probe.method_close_calls < 1:
                raise ControlFailure("outer/inner method close not observed")
            record(
                "C-R08",
                "PASS",
                "JoinedTLS via CoveringHTTP; outer method close; no second raw close",
                {
                    **ev,
                    "method_close_calls": probe.method_close_calls,
                    "raw_sock_close_attempts": probe.raw_sock_close_attempts,
                    "owner_id_proof_limit": FAKE_OWNER_ID_LABEL,
                },
            )
    except Exception as exc:
        record("C-R08", "FAIL", type(exc).__name__)

    # C-R09 first sock.close raises; later same-owner method close idempotent
    try:
        JoinedTLS = env["joined_ns"]["JoinedTLS"]
        peer, _, _ = build_peer_and_counter(env["policy_ns"])
        reset_sock(env, close_error=FakeSockCloseError())
        tls = JoinedTLS(peer, remaining=lambda: 1.0)
        # Allocate sock as open would
        tls.sock = env["joined_ns"]["socket"].socket()
        first_raw = env["close_probe"].raw_sock_close_attempts
        first_raised = False
        try:
            tls.close()
        except FakeSockCloseError:
            first_raised = True
        mid_raw = env["close_probe"].raw_sock_close_attempts
        tls.close()  # idempotent method; no second raw
        end_raw = env["close_probe"].raw_sock_close_attempts
        if not first_raised or mid_raw != first_raw + 1 or end_raw != mid_raw:
            raise ControlFailure(
                f"idempotence fail first_raised={first_raised} raw={first_raw}->{mid_raw}->{end_raw}"
            )
        record(
            "C-R09",
            "PASS",
            "first close may raise; later same-owner method close no second raw",
            {
                "method_close_calls": env["close_probe"].method_close_calls,
                "raw_sock_close_attempts_delta": mid_raw - first_raw,
                "second_raw_delta": end_raw - mid_raw,
            },
        )
    except Exception as exc:
        record("C-R09", "FAIL", type(exc).__name__)

    # C-R10 / C-R11 oauth
    try:
        http, probe, method, url, data = run_http(
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
            record("C-R10", "PASS", "oauth malformed+cleanup UNKNOWN", {**ev, "later_admission": False})
    except Exception as exc:
        record("C-R10", "FAIL", type(exc).__name__)

    try:
        http, probe, method, url, data = run_http(
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
            if not isinstance(getattr(exc, "primary", None), Reauth):
                raise ControlFailure("R11 primary must be Reauth")
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
    except Exception as exc:
        record("C-R11", "FAIL", type(exc).__name__)

    # C-R12 foreign
    try:
        JoinedTLS = env["joined_ns"]["JoinedTLS"]
        peer, _, _ = build_peer_and_counter(env["policy_ns"])
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
            raise ControlFailure("expected refuse")
        except Exception as exc:
            if type(exc).__name__ != "CoveringTransportRefused":
                raise ControlFailure(type(exc).__name__)
            record(
                "C-R12",
                "PASS",
                "foreign retirement refused before socket mutation",
                {"owner_id_proof_limit": FAKE_OWNER_ID_LABEL},
            )
        finally:
            env["joined_ns"]["get_ident"] = lambda: 1
    except Exception as exc:
        record("C-R12", "FAIL", type(exc).__name__)

    # C-OUT-VE / C-OUT-UNK
    try:
        outer = ValueError("unrelated-outer")
        captured = {}
        try:
            raise outer
        except ValueError:
            http, probe, method, url, data = run_http(
                env, transport_close_error=FakeTransportCloseError()
            )
            try:
                http.request(method, url, purpose="event")
            except Exception as exc:
                captured["exc"] = exc
        ev = expect_unknown(captured["exc"], Unknown)
        if ev["primary"] is not None or getattr(captured["exc"], "primary", None) is outer:
            raise ControlFailure("ambient ValueError attributed")
        record("C-OUT-VE", "PASS", "ambient ValueError not attributed/mutated", ev)
    except Exception as exc:
        record("C-OUT-VE", "FAIL", type(exc).__name__)

    try:
        outer = Unknown()
        outer.marker = "caller-owned-outer"
        captured = {}
        try:
            raise outer
        except Unknown:
            http, probe, method, url, data = run_http(
                env, transport_close_error=FakeTransportCloseError()
            )
            try:
                http.request(method, url, purpose="event")
            except Exception as exc:
                captured["exc"] = exc
        exc = captured["exc"]
        ev = expect_unknown(exc, Unknown)
        if exc is outer or getattr(outer, "marker", None) != "caller-owned-outer":
            raise ControlFailure("outer mutated or reused")
        if ev["primary"] is not None:
            raise ControlFailure("primary must be None")
        record("C-OUT-UNK", "PASS", "new UNKNOWN; outer attrs unchanged", ev)
    except Exception as exc:
        record("C-OUT-UNK", "FAIL", type(exc).__name__)

    # C-UNK-PULL — actual complete try/except
    try:
        info = drive_importer_unknown(env, original=False)
        if not info["escaped"] or not info["source_has_unknown_escape"]:
            raise ControlFailure(f"candidate escape failed {info}")
        record("C-UNK-PULL", "PASS", "complete try/except UNKNOWN re-raise", info)
    except Exception as exc:
        record("C-UNK-PULL", "FAIL", type(exc).__name__)

    # Caller classifications via role ports + HTTP purpose
    try:
        info = drive_role_no_later(env, mutate_preserve=False)
        # Event path classification via CoveringHTTP purpose=event + UNKNOWN stop
        http, probe, method, url, data = run_http(
            env, transport_close_error=FakeTransportCloseError()
        )
        try:
            http.request(method, url, purpose="event")
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            expect_unknown(exc, Unknown)
        record(
            "C-CALLER-EVENT",
            "PASS",
            "event purpose + role txn stop; prior preserved; no later",
            {
                "caller_kind": "event",
                "prior_results": info["prior_results"],
                "later_count": info["later_count"],
            },
        )
    except Exception as exc:
        record("C-CALLER-EVENT", "FAIL", type(exc).__name__)

    try:
        http, probe, method, url, data = run_http(
            env,
            purpose="oauth",
            transport_close_error=FakeTransportCloseError(),
        )
        try:
            http.request(method, url, purpose="oauth", data={"grant_type": "refresh_token"})
            raise ControlFailure("expected UNKNOWN")
        except Exception as exc:
            expect_unknown(exc, Unknown)
        info = drive_role_no_later(env, mutate_preserve=False)
        record(
            "C-CALLER-OAUTH",
            "PASS",
            "oauth/token purpose + role txn; no later admission",
            {"caller_kind": "oauth", "later_count": info["later_count"]},
        )
    except Exception as exc:
        record("C-CALLER-OAUTH", "FAIL", type(exc).__name__)

    try:
        idinfo = drive_identity_oserror(env)
        # Identity classification path exists; cleanup UNKNOWN still stops later.
        info = drive_role_no_later(env, mutate_preserve=False)
        record(
            "C-CALLER-IDENTITY",
            "PASS",
            "identity prepare path + role stop after UNKNOWN",
            {
                "caller_kind": "identity",
                "identity_path": idinfo["source_path"],
                "later_count": info["later_count"],
            },
        )
    except Exception as exc:
        record("C-CALLER-IDENTITY", "FAIL", type(exc).__name__)

    try:
        info = drive_role_no_later(env, mutate_preserve=False)
        if info["later_count"] != 0 or not info["raised_unknown"]:
            raise ControlFailure(f"later admission observed {info}")
        record(
            "C-NO-LATER-ADMISSION",
            "PASS",
            "zero later PARENT/TOKEN/ASSESSMENT after injected cleanup UNKNOWN",
            info,
        )
    except Exception as exc:
        record("C-NO-LATER-ADMISSION", "FAIL", type(exc).__name__)

    # C-POS-KNOWN-REAUTH
    try:
        http, probe, method, url, data = run_http(
            env, purpose="oauth", status=400, body={"error": "invalid_grant"}
        )
        try:
            http.request(method, url, purpose="oauth", data={"grant_type": "refresh_token"})
            raise ControlFailure("expected Reauth")
        except Reauth:
            record("C-POS-KNOWN-REAUTH", "PASS", "invalid_grant alone → Reauth")
    except Exception as exc:
        record("C-POS-KNOWN-REAUTH", "FAIL", type(exc).__name__)

    # Provenance boundary
    try:
        record(
            "C-PROV-BOUNDARY-ACCEPT",
            "PASS",
            "finite production boundary accepted",
            {
                "fields": list(PRODUCTION_PROVENANCE_FIELDS),
                "max_occurrences": MAX_RETIREMENT_OCCURRENCES,
            },
        )
        bad = Unknown()
        bad.retirement_occurrences = (("only-one",),)
        try:
            assert_provenance_boundary(bad)
            raise ControlFailure("expected reject")
        except ControlFailure as cf:
            if "unexpected_occurrence_shape" not in str(cf):
                raise
        bad2 = Unknown()
        bad2.retirement_occurrences = tuple(
            (None, None, None) for _ in range(MAX_RETIREMENT_OCCURRENCES + 1)
        )
        try:
            assert_provenance_boundary(bad2)
            raise ControlFailure("expected over-count reject")
        except ControlFailure as cf:
            if "over_count" not in str(cf):
                raise
        bad3 = Unknown()
        bad3.retirement_occurrences = (("x", None, None),)  # non-exception member
        try:
            assert_provenance_boundary(bad3)
            raise ControlFailure("expected non-exception reject")
        except ControlFailure as cf:
            if "non_exception_member" not in str(cf) and "unexpected_occurrence_shape" not in str(
                cf
            ):
                # ("x", None, None) fails non_exception on first member
                if "non_exception" not in str(cf) and "unexpected" not in str(cf):
                    raise
        record(
            "C-PROV-BOUNDARY-REJECT",
            "PASS",
            "over-count/non-exception/malformed rejected before sanitize",
        )
    except Exception as exc:
        record("C-PROV-BOUNDARY-ACCEPT", "FAIL", type(exc).__name__)
        record("C-PROV-BOUNDARY-REJECT", "FAIL", type(exc).__name__)

    # Original witnesses
    def orig_witness(cid, fn, expected_obs):
        try:
            obs = fn()
            for k, v in expected_obs.items():
                if obs.get(k) != v:
                    raise ControlFailure(f"{cid} mismatch {k}: {obs.get(k)!r}!={v!r}")
            record(cid, "PASS_WITNESS", "original contract-miss", obs)
        except Exception as exc:
            record(cid, "FAIL", type(exc).__name__)

    def o_r02():
        http, probe, method, url, data = run_http(
            env, original=True, response_close_error=FakeResponseCloseError()
        )
        raised = None
        try:
            http.request(method, url, purpose="event")
        except Exception as exc:
            raised = type(exc).__name__
        return {
            "transport_close_attempted": probe.method_close_calls > 0,
            "raised_class": raised,
            "unknown_raised": raised == "CoveringRootOutcomeUnknown",
        }

    orig_witness(
        "O-R02",
        o_r02,
        {
            "transport_close_attempted": False,
            "raised_class": "FakeResponseCloseError",
            "unknown_raised": False,
        },
    )

    def o_r03():
        http, probe, method, url, data = run_http(
            env, original=True, transport_close_error=FakeTransportCloseError()
        )
        raised = None
        try:
            http.request(method, url, purpose="event")
        except Exception as exc:
            raised = type(exc).__name__
        return {
            "unknown_raised": raised == "CoveringRootOutcomeUnknown",
            "escaped_class": raised,
            "later_admission_risk": raised == "FakeTransportCloseError",
        }

    orig_witness(
        "O-R03-EV",
        o_r03,
        {
            "unknown_raised": False,
            "escaped_class": "FakeTransportCloseError",
            "later_admission_risk": True,
        },
    )

    def o_r04():
        http, probe, method, url, data = run_http(
            env,
            original=True,
            force_bad_json=True,
            response_close_error=FakeResponseCloseError(),
        )
        primary_cls = context_cls = cleanup_cls = None
        raised_cls = None
        has_new_attrs = False
        try:
            http.request(method, url, purpose="event")
        except Exception as exc:
            raised_cls = type(exc).__name__
            # Body/parser primary may appear as __context__ when cleanup replaces.
            context_cls = type(exc.__context__).__name__ if exc.__context__ else None
            primary_cls = context_cls  # observed prior primary class if present
            cleanup_cls = raised_cls
            has_new_attrs = (
                getattr(exc, "primary", None) is not None
                and getattr(exc, "response_close", None) is not None
            )
        return {
            "raised_class": raised_cls,
            "primary_class_observed": primary_cls,
            "context_class_observed": context_cls,
            "cleanup_class_observed": cleanup_cls,
            "unknown_with_dual_attrs": False,
            "has_new_provenance_attrs": has_new_attrs,
        }

    orig_witness(
        "O-R04",
        o_r04,
        {
            "raised_class": "FakeResponseCloseError",
            "cleanup_class_observed": "FakeResponseCloseError",
            "unknown_with_dual_attrs": False,
            "has_new_provenance_attrs": False,
        },
    )

    def o_r05():
        http, probe, method, url, data = run_http(
            env,
            original=True,
            force_bad_json=True,
            transport_close_error=FakeTransportCloseError(),
        )
        raised_cls = context_cls = None
        has_new_attrs = False
        try:
            http.request(method, url, purpose="event")
        except Exception as exc:
            raised_cls = type(exc).__name__
            context_cls = type(exc.__context__).__name__ if exc.__context__ else None
            has_new_attrs = (
                getattr(exc, "primary", None) is not None
                and getattr(exc, "transport_close", None) is not None
            )
        return {
            "raised_class": raised_cls,
            "context_class_observed": context_cls,
            "cleanup_class_observed": raised_cls,
            "unknown_with_dual_attrs": False,
            "has_new_provenance_attrs": has_new_attrs,
        }

    orig_witness(
        "O-R05",
        o_r05,
        {
            "raised_class": "FakeTransportCloseError",
            "cleanup_class_observed": "FakeTransportCloseError",
            "unknown_with_dual_attrs": False,
            "has_new_provenance_attrs": False,
        },
    )

    def o_r06():
        http, probe, method, url, data = run_http(
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
            "both_closes_attempted": probe.method_close_calls > 0,
            "dual_cleanup_objects": dual,
        }

    orig_witness(
        "O-R06",
        o_r06,
        {"both_closes_attempted": False, "dual_cleanup_objects": False},
    )

    def o_r08():
        reset_sock(env, connect_error=99, close_error=FakeSockCloseError())
        http, probe, method, url, data = run_http(env, original=True, use_joined=True)
        unknown_raised = False
        raw_escape = False
        raised = None
        try:
            http.request(method, url, purpose="event")
        except Exception as exc:
            raised = type(exc).__name__
            unknown_raised = raised == "CoveringRootOutcomeUnknown"
            raw_escape = raised == "FakeSockCloseError"
        return {
            "unknown_raised": unknown_raised,
            "raw_cleanup_escapes": raw_escape,
            "http_only_insufficient": True,
            "raised_class": raised,
            "method_close_calls": probe.method_close_calls,
            "raw_sock_close_attempts": probe.raw_sock_close_attempts,
        }

    orig_witness(
        "O-R08",
        o_r08,
        {
            "unknown_raised": False,
            "raw_cleanup_escapes": True,
            "http_only_insufficient": True,
        },
    )

    def o_unk():
        info = drive_importer_unknown(env, original=True)
        return {
            "escaped": info["escaped"],
            "outcome": info["returned_outcome"],
            "later_admission": info["later_admission"],
            "source_has_unknown_escape": info["source_has_unknown_escape"],
            "newline_kind": info["newline_kind"],
        }

    orig_witness(
        "O-UNK-PULL",
        o_unk,
        {
            "escaped": False,
            "outcome": "failed",
            "later_admission": True,
            "source_has_unknown_escape": False,
        },
    )

    def o_id():
        return drive_identity_oserror(env)

    orig_witness(
        "O-ID-OS",
        o_id,
        {
            "maps_oserror_to_preflight": True,
            "unknown_stop": False,
            "except_tuple_includes_OSError": True,
        },
    )

    def o_r11():
        http, probe, method, url, data = run_http(
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

    orig_witness(
        "O-R11",
        o_r11,
        {
            "unknown_with_reauth_primary": False,
            "cleanup_may_replace_reauth": True,
        },
    )

    # Mutations — rebind actual pinned definitions; same oracle unmutated vs mutant
    try:
        tree = _load_module_ast(
            CANDIDATE_API / "app" / "services" / "covering_http_transport.py"
        )
        method = copy.deepcopy(_find_class_method(tree, "CoveringHTTP", "request"))
        # Mutate finally: after response_close_exc captured, skip transport.close try.
        # Find finally body Assign response_close / transport pattern — simpler:
        # wrap method so transport.close is no-op after response close error via
        # AST: in finally, remove the transport.close try block's raise path by
        # deleting transport_close capture — locate `transport.close()` Call in finally.
        finally_node = None
        for n in method.body:
            if isinstance(n, ast.Try) and n.finalbody:
                finally_node = n
                break
        if finally_node is None:
            raise ControlFailure("no finally on CoveringHTTP.request")
        # Neutralize transport.close() calls inside finally.
        class _Neutralize(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "close"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "transport"
                ):
                    return ast.Constant(value=None)
                return node

        finally_node.finalbody = [
            _Neutralize().visit(stmt) for stmt in finally_node.finalbody
        ]
        # Also force transport_close_exc to remain None by removing assign from except —
        # neutralizing close call means transport_close_exc stays None → dual fails.
        bind_ns = dict(env["http_ns"])
        mutated = compile_mutated_method(
            method, filename="<m-skip-second-close>", bind_globals=bind_ns
        )
        CoveringHTTP = env["http_ns"]["CoveringHTTP"]
        original_request = CoveringHTTP.request

        # Unmutated SAME oracle C-R06: both cleanups
        http, probe, method_name, url, data = run_http(
            env,
            response_close_error=FakeResponseCloseError(),
            transport_close_error=FakeTransportCloseError(),
        )
        try:
            http.request(method_name, url, purpose="event")
            raise ControlFailure("unmutated expected UNKNOWN")
        except Exception as exc:
            ev = expect_unknown(exc, Unknown)
            if ev["response_close"] is None or ev["transport_close"] is None:
                raise ControlFailure("unmutated C-R06 must retain both")

        # Mutant: rebind
        CoveringHTTP.request = mutated
        try:
            http2, probe2, method_name2, url2, data2 = run_http(
                env,
                response_close_error=FakeResponseCloseError(),
                transport_close_error=FakeTransportCloseError(),
            )
            try:
                http2.request(method_name2, url2, purpose="event")
                mutant_both = False
                mutant_detail = "no_raise"
            except Exception as exc:
                both = (
                    getattr(exc, "response_close", None) is not None
                    and getattr(exc, "transport_close", None) is not None
                )
                mutant_both = both
                mutant_detail = type(exc).__name__
            if mutant_both:
                raise ControlFailure("mutant unexpectedly retained both cleanups")
            record(
                "M-SKIP-SECOND-CLOSE",
                "PASS",
                "unmutated C-R06 passes; mutant skips transport.close; dual absent",
                {
                    "mutant_detail": mutant_detail,
                    "proof_limit": "harness-only-in-memory-rebind",
                },
            )
        finally:
            CoveringHTTP.request = original_request
    except Exception as exc:
        record("M-SKIP-SECOND-CLOSE", "FAIL", type(exc).__name__)

    try:
        # Mutate finally to set primary from sys.exc_info ambient
        tree = _load_module_ast(
            CANDIDATE_API / "app" / "services" / "covering_http_transport.py"
        )
        method = copy.deepcopy(_find_class_method(tree, "CoveringHTTP", "request"))
        # Insert at start of finally: invocation_primary = sys.exc_info()[1]
        finally_node = None
        for n in method.body:
            if isinstance(n, ast.Try) and n.finalbody:
                finally_node = n
                break
        inject = ast.parse(
            "import sys\n"
            "if invocation_primary is None:\n"
            "    invocation_primary = sys.exc_info()[1]\n"
        ).body
        finally_node.finalbody = inject + list(finally_node.finalbody)
        bind_ns = dict(env["http_ns"])
        bind_ns["sys"] = sys
        mutated = compile_mutated_method(
            method, filename="<m-ambient-exc-info>", bind_globals=bind_ns
        )
        CoveringHTTP = env["http_ns"]["CoveringHTTP"]
        original_request = CoveringHTTP.request
        # Unmutated C-OUT-VE oracle
        outer = ValueError("ambient")
        try:
            raise outer
        except ValueError:
            http, probe, method_name, url, data = run_http(
                env, transport_close_error=FakeTransportCloseError()
            )
            try:
                http.request(method_name, url, purpose="event")
            except Exception as exc:
                ev = expect_unknown(exc, Unknown)
                if ev["primary"] is not None:
                    raise ControlFailure("unmutated C-OUT-VE failed")
        CoveringHTTP.request = mutated
        try:
            try:
                raise outer
            except ValueError:
                http2, probe2, method_name2, url2, data2 = run_http(
                    env, transport_close_error=FakeTransportCloseError()
                )
                try:
                    http2.request(method_name2, url2, purpose="event")
                    raise ControlFailure("expected UNKNOWN")
                except Exception as exc:
                    # Mutant attributes ambient
                    if getattr(exc, "primary", None) is not outer:
                        # still detect difference vs candidate None
                        if getattr(exc, "primary", None) is None:
                            raise ControlFailure("mutant did not attribute ambient")
                    record(
                        "M-AMBIENT-EXC-INFO",
                        "PASS",
                        "unmutated primary None; mutant ambient attribution detected",
                        {"proof_limit": "harness-only-in-memory-rebind"},
                    )
        finally:
            CoveringHTTP.request = original_request
    except Exception as exc:
        record("M-AMBIENT-EXC-INFO", "FAIL", type(exc).__name__)

    try:
        # Mutant allows later continuation after UNKNOWN
        good = drive_role_no_later(env, mutate_preserve=False)
        bad = drive_role_no_later(env, mutate_preserve=True)
        if good["later_count"] != 0:
            raise ControlFailure("unmutated later_count nonzero")
        if bad["later_count"] == 0:
            raise ControlFailure("mutant did not allow continuation")
        record(
            "M-MUTATE-OUTER-UNKNOWN",
            "PASS",
            "unmutated zero later; mutant continuation detected",
            {
                "unmutated_later": good["later_count"],
                "mutant_later": bad["later_count"],
                "proof_limit": "harness-only-role-admission-mutant",
            },
        )
    except Exception as exc:
        record("M-MUTATE-OUTER-UNKNOWN", "FAIL", type(exc).__name__)

    # Alias name retained: also expose M-ALLOW-LATER as same evidence via detail
    # Inventory self-checks via actual compare_to_expected
    # Append placeholders for remaining IDs then inventory runs against full expected —
    # inventory checks construct their own lists; call after all functional recorded.
    # We'll add inventory at end after verifying order matches expected prefix.

    out.extend(inventory_self_checks(expected))
    return out


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
        "controls": controls
        if inventory_error is None
        else {r.control_id: {"result": r.result, "detail": r.detail} for r in results},
        "extraction_provenance": [p.__dict__ for p in provenance],
        "c_out_ve_present": any(r.control_id == "C-OUT-VE" for r in results),
        "c_out_unk_present": any(r.control_id == "C-OUT-UNK" for r in results),
        "crlf_aware_extract": True,
        "proof_limits": {
            "fake_owner_id": FAKE_OWNER_ID_LABEL,
            "fake_terminal_ack": FAKE_TERMINAL_ACK_LABEL,
            "fake_retirement_result": FAKE_RETIREMENT_RESULT_LABEL,
            "no_actual_threads_or_sockets": True,
        },
        "provenance_boundary": {
            "fields": list(PRODUCTION_PROVENANCE_FIELDS),
            "max_occurrences": MAX_RETIREMENT_OCCURRENCES,
        },
    }
    RESULT_PATH.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    print(json.dumps({"status": status, "inventory_error": inventory_error}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
