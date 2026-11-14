#!/usr/bin/env python3
"""Fake-only D2 path-admission verification (AUTHORING ONLY — not executed).

AST-extracts candidate covering path/helper/HTTP/context plus Google pagination
builder and Microsoft Graph URL helpers (GRAPH_BASE / calendarView builders /
absolute-graph) from frozen payload bytes.
Exercises the corrected4+overlay functional inventory (41-row core, plus
named oracle-gap additions) under fully fake dependencies, plus separately
named inventory self-checks and narrowly scoped mutation controls that drive
functional CoveringHTTP / context oracles against in-memory mutants only.

Successor of frozen v2 tip 9794FE5B… — retains Dex oracle-gap closures from
v2 (p1794421374) and closes Dex named-control findings (p1794422024):
MS encoded-ID builder composition, DUP-SAME-PURPOSE first-peer selection,
and generic positive request-line no-normalize-and-forward observation.
v1 tip A91964DA… and v2 tip 9794FE5B… remain immutable.

Preparation card forbids invoking this file. launch_ready remains false.
No app package import, no real sockets/providers/credentials/TLS/DB, no pytest.
Instrument fake transport construct/open/send/close separately.
Hostnames in peer labels are names only — never dial authority.
This packet is NOT full provider transport proof and does NOT close T01–T08.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import http.client
import io
import json
import sys
import types
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode, urlsplit, unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAYLOAD = ROOT / "payload"
CANDIDATE_API = PAYLOAD / "workspace" / "apps" / "api"
BASES = PAYLOAD / "bases"
MANIFEST_PATH = HERE / "INPUT-MANIFEST.json"
EXPECTED_PATH = HERE / "EXPECTED-OUTPUT.json"
RESULT_PATH = HERE / "FAKE-D2-RESULT.json"

PASS_RESULTS = {"PASS", "REFUSE", "PASS_WITNESS"}

# Synthetic owned peers — numeric TEST-NET addresses; never dialed.
G_HOST = "www.googleapis.com"
G_ADDR = "203.0.113.10"
G_ADDR_DUP_SECOND = "203.0.113.12"
MS_HOST = "graph.microsoft.com"
MS_ADDR = "203.0.113.20"
G_OAUTH_HOST = "oauth2.googleapis.com"
G_OAUTH_ADDR = "203.0.113.11"
MS_OAUTH_HOST = "login.microsoftonline.com"
MS_OAUTH_ADDR = "203.0.113.21"
MS_SYNTH_CALENDAR_ID_RAW = "a=b+c"
MS_SYNTH_CALENDAR_ID_ENCODED = "a%3Db%2Bc"
FIXTURE_HOST = "fixture.covering.test"
FIXTURE_ADDR = "203.0.113.99"
FOREIGN_HOST = "foreign.example.invalid"
FOREIGN_ADDR = "203.0.113.50"
CA_FILE = "synthetic-public-ca.pem"

G_EVENTS_PREFIX = "/calendar/v3/calendars/"
G_CALENDARLIST_EXACT = "/calendar/v3/users/me/calendarList"
MS_CALENDARS_PREFIX = "/v1.0/me/calendars/"
MS_CALENDARS_EXACT = "/v1.0/me/calendars"
MS_DEFAULT_EXACT = "/v1.0/me/calendar"
G_TOKEN_EXACT = "/token"
MS_TENANT_TOKEN = "/11111111-2222-3333-4444-555555555555/oauth2/v2.0/token"
SYNTH_PREFIX = "/__fixture__/covering/admit/"

PAGE_TOKEN_OPAQUE = "https://example.invalid/next"
PAGE_TOKEN_QUERY = "pageToken=" + quote(PAGE_TOKEN_OPAQUE, safe="")
POS_PAGE_TOKEN_PATH = "/calendar/v3/calendars/cal%2Bendar%40x.com/events"
POS_PAGE_TOKEN_URL_PATH_QUERY = POS_PAGE_TOKEN_PATH + "?" + PAGE_TOKEN_QUERY
MS_NEXTLINK_URL = (
    "https://graph.microsoft.com/v1.0/me/calendars/a%3Db%2Bc/calendarView?$skiptoken=1"
)


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


@dataclass
class TransportProbe:
    constructs: int = 0
    opens: int = 0
    sends: int = 0
    closes: int = 0
    receives: int = 0
    wires: list[bytes] | None = None
    selected_peers: list[Any] | None = None

    def __post_init__(self) -> None:
        if self.wires is None:
            self.wires = []
        if self.selected_peers is None:
            self.selected_peers = []

    def reset(self) -> None:
        self.constructs = self.opens = self.sends = self.closes = self.receives = 0
        self.wires = []
        self.selected_peers = []


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
    if rel.startswith("stdlib/"):
        # Relative pin under the pinned interpreter Lib/ — resolved at verify time
        # via INPUT-MANIFEST.stdlib_root.
        raise ControlFailure("stdlib paths resolve via verify_source_hashes")
    if rel.startswith("payload/"):
        return ROOT / rel
    return PAYLOAD / rel


def verify_source_hashes(manifest: dict[str, Any]) -> None:
    sources = manifest["source_extraction"]["sources"]
    for rel, expected in sources.items():
        path = resolve_source(rel)
        actual = sha256_file(path)
        if actual != expected.upper():
            raise ControlFailure(
                f"source hash mismatch for {rel}: {actual} != {expected}"
            )
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
            raise ControlFailure(
                f"stdlib hash mismatch for {rel}: {actual} != {expected}"
            )


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
    module_name = str(module_ns.get("__name__") or "")
    registered = sys.modules.get(module_name)
    if registered is None or registered.__dict__ is not module_ns:
        raise ControlFailure(
            f"extract_symbols requires ModuleType.__dict__ registered in "
            f"sys.modules for {module_name!r}"
        )
    raw = source_path.read_bytes()
    text = raw.decode("utf-8")
    if "\r" in text:
        raise ControlFailure(f"CR bytes forbidden in extraction source: {source_path}")
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


def _load_module_ast(source_path: Path) -> ast.Module:
    raw = source_path.read_bytes()
    text = raw.decode("utf-8")
    if "\r" in text:
        raise ControlFailure(f"CR bytes forbidden in mutation source: {source_path}")
    return ast.parse(text, filename=str(source_path))


def _find_class_method(tree: ast.Module, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise ControlFailure(f"missing {class_name}.{method_name} in AST for mutation")


def _find_top_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ControlFailure(f"missing function {name} in AST for mutation")


def compile_mutated_method(
    method_ast: ast.FunctionDef,
    *,
    filename: str,
    bind_globals: dict[str, Any],
) -> Callable:
    module_ast = ast.Module(body=[method_ast], type_ignores=[])
    ast.fix_missing_locations(module_ast)
    code = compile(module_ast, filename, "exec")
    local_ns: dict[str, Any] = {}
    exec(code, bind_globals, local_ns)
    name = method_ast.name
    if name not in local_ns:
        raise ControlFailure(f"mutated method {name!r} did not bind")
    return local_ns[name]


def install_stubs() -> None:
    class CoveringDeadlineExceeded(Exception):
        pass

    class CoveringRootOutcomeUnknown(Exception):
        pass

    class ApiError(Exception):
        def __init__(self, status: int, detail: str, code: str, body: str | None = None):
            super().__init__(detail)
            self.status = status
            self.detail = detail
            self.code = code
            self.body = body

    for name in (
        "app",
        "app.services",
        "app.services.covering_request_budget",
        "app.services.covering_joined_https",
        "app.services.covering_target_transaction",
        "app.services.covering_transport_policy",
        "app.services.covering_http_transport",
        "app.services.covering_provider_context",
        "app.services.google_calendar",
        "app.services.microsoft_calendar",
        "app.api",
        "app.api.errors",
        "httpx",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    budget = sys.modules["app.services.covering_request_budget"]
    budget.CoveringDeadlineExceeded = CoveringDeadlineExceeded
    txn = sys.modules["app.services.covering_target_transaction"]
    txn.CoveringRootOutcomeUnknown = CoveringRootOutcomeUnknown
    errors = sys.modules["app.api.errors"]
    errors.ApiError = ApiError

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
            self.text = content.decode("utf-8", errors="replace")

        def json(self):
            return json.loads(self.content)

    class Client:
        def __init__(self, *a, **k):
            raise ControlFailure("ambient httpx.Client must not construct under covering")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    httpx.Request = Request
    httpx.Response = Response
    httpx.Client = Client

    joined = sys.modules["app.services.covering_joined_https"]

    class _JoinedTLSPlaceholder:
        def __init__(self, *a, **k):
            raise RuntimeError("JoinedTLS placeholder must be overridden by fake factory")

    joined.JoinedTLS = _JoinedTLSPlaceholder


def framed_http_json(status: int, obj: dict, *, location: str | None = None) -> bytes:
    payload = json.dumps(obj).encode("utf-8")
    reason = "OK" if status < 400 else "ERR"
    if 300 <= status < 400:
        reason = "Found"
    lines = [
        f"HTTP/1.1 {status} {reason}",
        "Content-Type: application/json",
        f"Content-Length: {len(payload)}",
        "Content-Encoding: identity",
        "Connection: close",
    ]
    if location is not None:
        lines.append(f"Location: {location}")
    head = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
    return head + payload


def make_scripted_transport_factory(probe: TransportProbe, bodies: list[bytes]):
    queue = list(bodies)

    class FakeTransport:
        def __init__(self, peer, remaining):
            probe.constructs += 1
            assert probe.selected_peers is not None
            probe.selected_peers.append(peer)
            self.peer = peer
            self.remaining = remaining
            self.sent = False
            self._opened = False
            self._closed = False
            if not queue:
                raise ControlFailure("fake transport body queue exhausted")
            self._buf = queue.pop(0)
            self._pos = 0

        def open(self):
            probe.opens += 1
            self._opened = True

        def send(self, wire: bytes):
            probe.sends += 1
            self.sent = True
            if not isinstance(wire, (bytes, bytearray)):
                raise TypeError("wire must be bytes")
            assert probe.wires is not None
            probe.wires.append(bytes(wire))

        def receive(self, n: int) -> bytes:
            probe.receives += 1
            chunk = self._buf[self._pos : self._pos + n]
            self._pos += len(chunk)
            return chunk

        def close(self):
            probe.closes += 1
            self._closed = True

    return FakeTransport


def build_policy_module(
    source: Path,
    module_name: str,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    import ipaddress

    budget = sys.modules["app.services.covering_request_budget"]
    ns = new_module_namespace(
        module_name,
        {
            "dataclass": dataclass,
            "ip_address": ipaddress.ip_address,
            "urlsplit": urlsplit,
            "unquote": unquote,
            "CoveringDeadlineExceeded": budget.CoveringDeadlineExceeded,
        },
    )
    names = [
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
    ]
    extracted = extract_symbols(source, names, ns, provenance=provenance)
    mod = sys.modules[module_name]
    for k, v in extracted.items():
        setattr(mod, k, v)
    return extracted | {"__ns__": ns}


def build_http_module(
    source: Path,
    module_name: str,
    policy_mod_name: str,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    import http as http_pkg

    policy = sys.modules[policy_mod_name]
    target_txn = sys.modules["app.services.covering_target_transaction"]
    joined = sys.modules["app.services.covering_joined_https"]
    ns = new_module_namespace(
        module_name,
        {
            "http": http_pkg,
            "io": io,
            "json": json,
            "urlencode": urlencode,
            "httpx": sys.modules["httpx"],
            "JoinedTLS": joined.JoinedTLS,
            "CoveringTransportRefused": policy.CoveringTransportRefused,
            "CoveringReauthorizationRequired": policy.CoveringReauthorizationRequired,
            "admit_covering_path": policy.admit_covering_path,
            "CoveringRootOutcomeUnknown": target_txn.CoveringRootOutcomeUnknown,
        },
    )
    extracted = extract_symbols(
        source,
        ["_Reader", "_SocketView", "CoveringHTTP"],
        ns,
        provenance=provenance,
    )
    mod = sys.modules[module_name]
    for k, v in extracted.items():
        setattr(mod, k, v)
    return extracted | {"__ns__": ns}


def build_context_module(
    source: Path,
    module_name: str,
    policy_mod_name: str,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    from contextvars import ContextVar

    policy = sys.modules[policy_mod_name]
    ns = new_module_namespace(
        module_name,
        {
            "contextmanager": contextmanager,
            "ContextVar": ContextVar,
            "httpx": sys.modules["httpx"],
            "urlsplit": urlsplit,
            "CoveringTransportRefused": policy.CoveringTransportRefused,
            "admit_covering_path": policy.admit_covering_path,
        },
    )
    # Module-level _current is required by extracted helpers.
    extracted_assign = extract_symbols(
        source,
        ["_current", "covering_provider_transport", "_CoveringClient", "calendar_client"],
        ns,
        provenance=provenance,
    )
    mod = sys.modules[module_name]
    for k, v in extracted_assign.items():
        setattr(mod, k, v)
    return extracted_assign | {"__ns__": ns}


def build_google_pagination(
    source: Path,
    module_name: str,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    errors = sys.modules["app.api.errors"]
    provider_ctx = sys.modules["app.services.covering_provider_context"]

    class GoogleSyncTokenExpired(Exception):
        pass

    ns = new_module_namespace(
        module_name,
        {
            "quote": quote,
            "urlencode": urlencode,
            "calendar_client": provider_ctx.calendar_client,
            "ApiError": errors.ApiError,
            "GoogleSyncTokenExpired": GoogleSyncTokenExpired,
            "pagination_max_pages": None,
            "_pull_pagination_complete": True,
            "Any": Any,
        },
    )
    # Bind annotations used by extracted defs.
    ns["dict"] = dict
    ns["list"] = list
    ns["str"] = str
    ns["tuple"] = tuple
    extracted = extract_symbols(
        source,
        ["_calendar_events_base", "_paginate_events"],
        ns,
        provenance=provenance,
    )
    mod = sys.modules[module_name]
    for k, v in extracted.items():
        setattr(mod, k, v)
    setattr(mod, "GoogleSyncTokenExpired", GoogleSyncTokenExpired)
    setattr(mod, "pagination_max_pages", None)
    setattr(mod, "_pull_pagination_complete", True)
    return extracted | {"__ns__": ns, "GoogleSyncTokenExpired": GoogleSyncTokenExpired}


def build_ms_absolute_url(
    source: Path,
    module_name: str,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    class MicrosoftDeltaExpired(Exception):
        pass

    ns = new_module_namespace(
        module_name,
        {
            "MicrosoftDeltaExpired": MicrosoftDeltaExpired,
            "quote": quote,
        },
    )
    extracted = extract_symbols(
        source,
        [
            "GRAPH_BASE",
            "_GRAPH_ORIGIN",
            "_calendar_view_url",
            "_calendar_view_delta_url",
            "_absolute_graph_url",
        ],
        ns,
        provenance=provenance,
    )
    mod = sys.modules[module_name]
    for k, v in extracted.items():
        setattr(mod, k, v)
    setattr(mod, "MicrosoftDeltaExpired", MicrosoftDeltaExpired)
    return extracted | {"__ns__": ns, "MicrosoftDeltaExpired": MicrosoftDeltaExpired}


def make_peer(HTTPSPeer, hostname: str, address: str):
    return HTTPSPeer(hostname, address, 443, CA_FILE)


def make_counter(ProviderLimits, ProviderCounter):
    limits = ProviderLimits(20, 10, 10_000, 16 * 1024 * 1024)

    def remaining():
        return None

    return ProviderCounter(limits, remaining)


def ok_body(extra: dict | None = None) -> bytes:
    obj = {"items": [], "value": []}
    if extra:
        obj.update(extra)
    return framed_http_json(200, obj)


def expected_control_ids(expected: dict[str, Any]) -> list[str]:
    controls_expected = expected.get("controls") or {}
    if not isinstance(controls_expected, dict) or not controls_expected:
        raise ControlFailure("EXPECTED-OUTPUT controls missing")
    expected_ids = list(controls_expected.keys())
    explicit = expected.get("control_ids_in_order")
    if explicit is None:
        raise ControlFailure("EXPECTED-OUTPUT.control_ids_in_order missing")
    if not isinstance(explicit, list) or [str(x) for x in explicit] != expected_ids:
        raise ControlFailure(
            "EXPECTED-OUTPUT.control_ids_in_order must equal controls key order"
        )
    if len(expected_ids) != len(set(expected_ids)):
        raise ControlFailure("EXPECTED-OUTPUT has duplicate control IDs")
    return expected_ids


def enforce_expected_inventory(
    results: list[ControlResult], expected: dict[str, Any]
) -> None:
    """Compare emitted control_id list DIRECTLY to expected control_ids_in_order."""
    controls_expected = expected.get("controls") or {}
    expected_ids = expected_control_ids(expected)
    actual_ids = [r.control_id for r in results]
    if len(actual_ids) != len(set(actual_ids)):
        dups = sorted({cid for cid in actual_ids if actual_ids.count(cid) > 1})
        raise ControlFailure(f"duplicate control results: {dups}")
    if actual_ids != expected_ids:
        raise ControlFailure(
            f"control inventory order mismatch emitted={actual_ids!r} "
            f"expected={expected_ids!r}"
        )
    by_id = {r.control_id: r for r in results}
    for cid, spec in controls_expected.items():
        want = spec["result"]
        got = by_id[cid].result
        if got != want:
            raise ControlFailure(
                f"control {cid} unexpected-outcome {got!r} != expected {want!r} "
                f"({by_id[cid].detail})"
            )
        if got not in PASS_RESULTS:
            raise ControlFailure(f"control {cid} not an accepted outcome: {got!r}")


def _assert_refuse(exc: BaseException, CoveringTransportRefused, message: str) -> None:
    if not isinstance(exc, CoveringTransportRefused):
        raise ControlFailure(f"expected CoveringTransportRefused, got {type(exc).__name__}: {exc!r}")
    if message not in str(exc):
        raise ControlFailure(f"refuse message mismatch: {exc!r} missing {message!r}")


def _assert_pre_send_zero(probe: TransportProbe, *, label: str) -> None:
    if probe.opens != 0 or probe.sends != 0:
        raise ControlFailure(
            f"{label} must be pre-send; opens={probe.opens} sends={probe.sends}"
        )
    if probe.constructs != 0:
        raise ControlFailure(
            f"{label} must not construct transport; constructs={probe.constructs}"
        )


def assert_wire_request_target_unchanged(
    probe: TransportProbe,
    reviewed_path_and_query: str,
    *,
    method: str = "GET",
) -> None:
    """Require captured first request-line target equals reviewed path[?query].

    Observes the no-normalize-and-forward boundary: opaque path/query bytes are
    not decoded or rewritten before the fake transport send.
    """
    if not probe.wires:
        raise ControlFailure("no wire captured for request-target assertion")
    line = probe.wires[0].split(b"\r\n", 1)[0]
    want_target = reviewed_path_and_query.encode("ascii")
    parts = line.split(b" ")
    if len(parts) < 3:
        raise ControlFailure(f"malformed request line: {line!r}")
    if parts[0] != method.encode("ascii"):
        raise ControlFailure(
            f"request method mismatch on wire: got {parts[0]!r} want {method!r}"
        )
    if parts[1] != want_target:
        raise ControlFailure(
            f"request-target changed on wire: got {parts[1]!r} want {want_target!r} "
            f"(no-normalize-and-forward)"
        )
    if parts[2] != b"HTTP/1.1":
        raise ControlFailure(f"unexpected HTTP version on request line: {line!r}")


def run_http_get(
    *,
    CoveringHTTP,
    HTTPSPeer,
    ProviderLimits,
    ProviderCounter,
    peer_host: str,
    peer_addr: str,
    prefix: str,
    purpose: str,
    url: str,
    probe: TransportProbe,
    bodies: list[bytes] | None = None,
    method: str = "GET",
    headers: dict | None = None,
    params: dict | None = None,
    data: dict | None = None,
    routes: tuple | None = None,
):
    peer = make_peer(HTTPSPeer, peer_host, peer_addr)
    if routes is None:
        routes = ((peer, prefix, purpose),)
    counter = make_counter(ProviderLimits, ProviderCounter)
    factory = make_scripted_transport_factory(probe, bodies or [ok_body()])
    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    return http.request(method, url, purpose=purpose, headers=headers, params=params, data=data)


def run_client_get(
    *,
    CoveringHTTP,
    covering_provider_transport,
    calendar_client,
    HTTPSPeer,
    ProviderLimits,
    ProviderCounter,
    peer_host: str,
    peer_addr: str,
    prefix: str,
    purpose: str,
    url: str,
    probe: TransportProbe,
    bodies: list[bytes] | None = None,
    routes: tuple | None = None,
    params: dict | None = None,
):
    peer = make_peer(HTTPSPeer, peer_host, peer_addr)
    if routes is None:
        routes = ((peer, prefix, purpose),)
    counter = make_counter(ProviderLimits, ProviderCounter)
    factory = make_scripted_transport_factory(probe, bodies or [ok_body()])
    transport = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    with covering_provider_transport(transport):
        with calendar_client(timeout=30.0) as client:
            return client.get(url, params=params, headers={"Authorization": "Bearer fake"})


def run_controls(bundle: dict[str, Any]) -> list[ControlResult]:
    results: list[ControlResult] = []

    def record(cid: str, result: str, detail: str = "") -> None:
        results.append(ControlResult(cid, result, detail))

    policy = bundle["policy"]
    http_mod = bundle["http"]
    ctx = bundle["ctx"]
    google = bundle["google"]
    ms = bundle["ms"]
    CoveringTransportRefused = policy["CoveringTransportRefused"]
    HTTPSPeer = policy["HTTPSPeer"]
    ProviderLimits = policy["ProviderLimits"]
    ProviderCounter = policy["ProviderCounter"]
    admit_covering_path = policy["admit_covering_path"]
    CoveringHTTP = http_mod["CoveringHTTP"]
    _CoveringClient = ctx["_CoveringClient"]
    covering_provider_transport = ctx["covering_provider_transport"]
    calendar_client = ctx["calendar_client"]
    _paginate_events = google["_paginate_events"]
    _calendar_events_base = google["_calendar_events_base"]
    _absolute_graph_url = ms["_absolute_graph_url"]
    _calendar_view_url = ms["_calendar_view_url"]
    _calendar_view_delta_url = ms["_calendar_view_delta_url"]
    GRAPH_BASE = ms["GRAPH_BASE"]

    def pos_get(cid: str, path: str, *, prefix: str = G_EVENTS_PREFIX, host=G_HOST, addr=G_ADDR, purpose="event"):
        probe = TransportProbe()
        url = f"https://{host}{path}"
        try:
            run_http_get(
                CoveringHTTP=CoveringHTTP,
                HTTPSPeer=HTTPSPeer,
                ProviderLimits=ProviderLimits,
                ProviderCounter=ProviderCounter,
                peer_host=host,
                peer_addr=addr,
                prefix=prefix,
                purpose=purpose,
                url=url,
                probe=probe,
            )
            if probe.opens != 1 or probe.sends != 1:
                raise ControlFailure(f"expected 1 open/send; got {probe.opens}/{probe.sends}")
            if probe.constructs != 1 or probe.closes != 1:
                raise ControlFailure("construct/close retirement mismatch")
            # Generic positive request-line: reviewed path/query bytes unchanged on wire.
            assert_wire_request_target_unchanged(probe, path, method="GET")
            record(
                cid,
                "PASS",
                f"admit opens={probe.opens} sends={probe.sends}; "
                f"request-target unchanged on wire",
            )
        except Exception as exc:
            record(cid, "FAIL", repr(exc))

    def assert_ctx_pre_delegate_refuse(
        path: str,
        *,
        prefix: str,
        host: str,
        addr: str,
        purpose: str,
        message: str,
        routes=None,
    ) -> None:
        """Real extracted _CoveringClient + sentinel transport.request.

        After unique route/purpose selection, admit_covering_path must refuse
        before any delegate call (ZERO transport.request increments).
        """
        peer = make_peer(HTTPSPeer, host, addr)
        if routes is None:
            routes = ((peer, prefix, purpose),)

        class _DelegateSentinel:
            def __init__(self) -> None:
                self.routes = routes
                self.delegate_calls = 0

            def request(self, *a, **k):
                self.delegate_calls += 1
                raise ControlFailure(
                    "context path refuse must precede transport.request delegate"
                )

        sentinel = _DelegateSentinel()
        client = _CoveringClient(sentinel)
        url = f"https://{host}{path}"
        try:
            client.get(url, headers={"Authorization": "Bearer fake"})
            raise ControlFailure("expected context path refuse before delegate")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, message)
        if sentinel.delegate_calls != 0:
            raise ControlFailure(
                f"context must refuse pre-delegate; "
                f"delegate_calls={sentinel.delegate_calls}"
            )

    def neg_path(
        cid: str,
        path: str,
        *,
        prefix: str = G_EVENTS_PREFIX,
        message="path admission refused",
        host=G_HOST,
        addr=G_ADDR,
        purpose="event",
        routes=None,
        also_ctx: bool = True,
    ):
        probe = TransportProbe()
        url = f"https://{host}{path}"
        try:
            try:
                run_http_get(
                    CoveringHTTP=CoveringHTTP,
                    HTTPSPeer=HTTPSPeer,
                    ProviderLimits=ProviderLimits,
                    ProviderCounter=ProviderCounter,
                    peer_host=host,
                    peer_addr=addr,
                    prefix=prefix,
                    purpose=purpose,
                    url=url,
                    probe=probe,
                    routes=routes,
                )
                raise ControlFailure("expected refuse, call admitted")
            except CoveringTransportRefused as exc:
                _assert_refuse(exc, CoveringTransportRefused, message)
            _assert_pre_send_zero(probe, label=cid)
            if also_ctx:
                assert_ctx_pre_delegate_refuse(
                    path,
                    prefix=prefix,
                    host=host,
                    addr=addr,
                    purpose=purpose,
                    message=message,
                    routes=routes,
                )
            detail = f"refused pre-send: {message}"
            if also_ctx:
                detail += "; context pre-delegate refuse (0 delegate calls)"
            record(cid, "PASS", detail)
        except Exception as exc:
            record(cid, "FAIL", repr(exc))

    # --- A. Positives (16) ---
    pos_get("CTRL-POS-G-PLUS-AT", "/calendar/v3/calendars/cal%2Bendar%40x.com/events")
    pos_get("CTRL-POS-G-PERCENT", "/calendar/v3/calendars/plain%25id/events")
    pos_get("CTRL-POS-G-INTERNAL-DOT", "/calendar/v3/calendars/a%2Eb/events")
    pos_get("CTRL-POS-G-UNICODE", "/calendar/v3/calendars/caf%C3%A9/events")
    pos_get("CTRL-POS-G-ID-LITERAL-CALENDARS", "/calendar/v3/calendars/calendars/events")
    # Exact-prefix: route prefix EQUALS full path (not a second descendant).
    pos_get(
        "CTRL-POS-G-EXACT-PREFIX",
        "/calendar/v3/calendars/calx/events",
        prefix="/calendar/v3/calendars/calx/events",
    )
    pos_get("CTRL-POS-G-CHILD", "/calendar/v3/calendars/calx/events")
    # MS VIEW / DELTA: drive extracted builders with raw synthetic calendar id;
    # assert wire carries quote(safe='') encoding (not a hardcoded URL string).
    try:
        if not str(GRAPH_BASE).startswith("https://"):
            raise ControlFailure(f"GRAPH_BASE unexpected: {GRAPH_BASE!r}")
        built = _calendar_view_url(MS_SYNTH_CALENDAR_ID_RAW)
        parsed = urlsplit(built)
        path = parsed.path or "/"
        if MS_SYNTH_CALENDAR_ID_ENCODED not in path:
            raise ControlFailure(
                f"_calendar_view_url did not encode opaque id: {built!r}"
            )
        if MS_SYNTH_CALENDAR_ID_RAW in path:
            raise ControlFailure(
                f"_calendar_view_url left raw id unescaped in path: {built!r}"
            )
        probe = TransportProbe()
        run_client_get(
            CoveringHTTP=CoveringHTTP,
            covering_provider_transport=covering_provider_transport,
            calendar_client=calendar_client,
            HTTPSPeer=HTTPSPeer,
            ProviderLimits=ProviderLimits,
            ProviderCounter=ProviderCounter,
            peer_host=MS_HOST,
            peer_addr=MS_ADDR,
            prefix=MS_CALENDARS_PREFIX,
            purpose="event",
            url=built,
            probe=probe,
        )
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure(
                f"MS-VIEW open/send mismatch: {probe.opens}/{probe.sends}"
            )
        if probe.constructs != 1 or probe.closes != 1:
            raise ControlFailure("MS-VIEW construct/close retirement mismatch")
        assert_wire_request_target_unchanged(probe, path, method="GET")
        line = (probe.wires or [b""])[0].split(b"\r\n", 1)[0]
        if MS_SYNTH_CALENDAR_ID_ENCODED.encode("ascii") not in line:
            raise ControlFailure(
                f"MS-VIEW wire missing encoded id {MS_SYNTH_CALENDAR_ID_ENCODED!r}: {line!r}"
            )
        if MS_SYNTH_CALENDAR_ID_RAW.encode("ascii") in line:
            raise ControlFailure(
                f"MS-VIEW wire contains unescaped raw id: {line!r}"
            )
        record(
            "CTRL-POS-MS-VIEW",
            "PASS",
            "builder _calendar_view_url(a=b+c) → context/client → CoveringHTTP; wire carries a%3Db%2Bc; "
            "native/provider proof boundary unchanged",
        )
    except Exception as exc:
        record("CTRL-POS-MS-VIEW", "FAIL", repr(exc))

    try:
        built = _calendar_view_delta_url(MS_SYNTH_CALENDAR_ID_RAW)
        parsed = urlsplit(built)
        path = parsed.path or "/"
        if MS_SYNTH_CALENDAR_ID_ENCODED not in path:
            raise ControlFailure(
                f"_calendar_view_delta_url did not encode opaque id: {built!r}"
            )
        if MS_SYNTH_CALENDAR_ID_RAW in path:
            raise ControlFailure(
                f"_calendar_view_delta_url left raw id unescaped in path: {built!r}"
            )
        if not path.endswith("/calendarView/delta"):
            raise ControlFailure(f"delta compat path unexpected: {path!r}")
        probe = TransportProbe()
        run_client_get(
            CoveringHTTP=CoveringHTTP,
            covering_provider_transport=covering_provider_transport,
            calendar_client=calendar_client,
            HTTPSPeer=HTTPSPeer,
            ProviderLimits=ProviderLimits,
            ProviderCounter=ProviderCounter,
            peer_host=MS_HOST,
            peer_addr=MS_ADDR,
            prefix=MS_CALENDARS_PREFIX,
            purpose="event",
            url=built,
            probe=probe,
        )
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure(
                f"MS-DELTA open/send mismatch: {probe.opens}/{probe.sends}"
            )
        if probe.constructs != 1 or probe.closes != 1:
            raise ControlFailure("MS-DELTA construct/close retirement mismatch")
        assert_wire_request_target_unchanged(probe, path, method="GET")
        line = (probe.wires or [b""])[0].split(b"\r\n", 1)[0]
        if MS_SYNTH_CALENDAR_ID_ENCODED.encode("ascii") not in line:
            raise ControlFailure(
                f"MS-DELTA wire missing encoded id {MS_SYNTH_CALENDAR_ID_ENCODED!r}: {line!r}"
            )
        if MS_SYNTH_CALENDAR_ID_RAW.encode("ascii") in line:
            raise ControlFailure(
                f"MS-DELTA wire contains unescaped raw id: {line!r}"
            )
        record(
            "CTRL-POS-MS-DELTA-COMPAT",
            "PASS",
            "builder _calendar_view_delta_url(a=b+c) → context/client → CoveringHTTP; wire carries a%3Db%2Bc; "
            "not ordinary-refresh invoke claim; native/provider proof boundary unchanged",
        )
    except Exception as exc:
        record("CTRL-POS-MS-DELTA-COMPAT", "FAIL", repr(exc))

    pos_get(
        "CTRL-POS-G-CALENDARLIST",
        G_CALENDARLIST_EXACT,
        prefix=G_CALENDARLIST_EXACT,
        purpose="identity",
    )
    pos_get(
        "CTRL-POS-MS-LIST",
        MS_CALENDARS_EXACT,
        prefix=MS_CALENDARS_EXACT,
        host=MS_HOST,
        addr=MS_ADDR,
        purpose="identity",
    )
    pos_get(
        "CTRL-POS-MS-DEFAULT",
        MS_DEFAULT_EXACT,
        prefix=MS_DEFAULT_EXACT,
        host=MS_HOST,
        addr=MS_ADDR,
        purpose="identity",
    )

    # OAuth positives (POST + oauth purpose)
    try:
        probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_OAUTH_HOST, G_OAUTH_ADDR)
        routes = ((peer, G_TOKEN_EXACT, "oauth"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(probe, [ok_body({"access_token": "x"})])
        http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        http.request(
            "POST",
            f"https://{G_OAUTH_HOST}{G_TOKEN_EXACT}",
            purpose="oauth",
            data={"grant_type": "refresh_token", "refresh_token": "x"},
        )
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure("oauth open/send mismatch")
        record("CTRL-POS-G-OAUTH", "PASS", "structural oauth POST admit")
    except Exception as exc:
        record("CTRL-POS-G-OAUTH", "FAIL", repr(exc))

    try:
        probe = TransportProbe()
        peer = make_peer(HTTPSPeer, MS_OAUTH_HOST, MS_OAUTH_ADDR)
        routes = ((peer, MS_TENANT_TOKEN, "oauth"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(probe, [ok_body({"access_token": "x"})])
        http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        http.request(
            "POST",
            f"https://{MS_OAUTH_HOST}{MS_TENANT_TOKEN}",
            purpose="oauth",
            data={"grant_type": "refresh_token", "refresh_token": "x"},
        )
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure("ms oauth open/send mismatch")
        record("CTRL-POS-MS-OAUTH", "PASS", "structural ms oauth POST admit; no profile bind")
    except Exception as exc:
        record("CTRL-POS-MS-OAUTH", "FAIL", repr(exc))

    pos_get("CTRL-POS-BUDGET-EQ-8", "/calendar/v3/calendars/%2525252525252561/events")

    # Restored direct-query pageToken positive (overlay; separate from CONT builder).
    try:
        probe = TransportProbe()
        url = f"https://{G_HOST}{POS_PAGE_TOKEN_URL_PATH_QUERY}"
        run_http_get(
            CoveringHTTP=CoveringHTTP,
            HTTPSPeer=HTTPSPeer,
            ProviderLimits=ProviderLimits,
            ProviderCounter=ProviderCounter,
            peer_host=G_HOST,
            peer_addr=G_ADDR,
            prefix=G_EVENTS_PREFIX,
            purpose="event",
            url=url,
            probe=probe,
        )
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure("pageToken positive open/send mismatch")
        wire = (probe.wires or [b""])[0]
        req_line = wire.split(b"\r\n", 1)[0]
        if PAGE_TOKEN_QUERY.encode("ascii") not in req_line:
            raise ControlFailure("pageToken query bytes not preserved on wire")
        # Exact request-target (path+query) unchanged; separate from CONT builder.
        assert_wire_request_target_unchanged(
            probe, POS_PAGE_TOKEN_URL_PATH_QUERY, method="GET"
        )
        if b"Location" in wire:
            raise ControlFailure("unexpected Location on request wire")
        record(
            "CTRL-POS-G-PAGE-TOKEN",
            "PASS",
            "direct-query admit; query opaque; 1 open/send; zero path-follow; "
            "request-target unchanged; separate from CONT builder continuation",
        )
    except Exception as exc:
        record("CTRL-POS-G-PAGE-TOKEN", "FAIL", repr(exc))

    # --- B. Negatives (18) ---
    neg_path("CTRL-NEG-ORD-SLASH", "/calendar/v3/calendars/ordinary%2Fid/events")
    neg_path("CTRL-NEG-ENC-SLASH-PCT2F-UPPER", "/calendar/v3/calendars/x%2Fy/events")
    neg_path("CTRL-NEG-ENC-SLASH-PCT2F-LOWER", "/calendar/v3/calendars/x%2fy/events")
    neg_path("CTRL-NEG-NEST-252F", "/calendar/v3/calendars/foo%252Fbar/events")
    neg_path("CTRL-NEG-NEST-25252F", "/calendar/v3/calendars/foo%25252Fbar/events")
    neg_path("CTRL-NEG-NEST-DOT", "/calendar/v3/calendars/%252e%252e/events")
    neg_path(
        "CTRL-NEG-RAW-DOT",
        "/calendar/v3/calendars/calx/events/../../outside",
        prefix="/calendar/v3/",
    )
    neg_path("CTRL-NEG-EMPTY", "/calendar/v3/calendars//events")
    neg_path("CTRL-NEG-TRAILING", "/calendar/v3/calendars/calx/events/")
    neg_path("CTRL-NEG-MALFORM-BARE", "/calendar/v3/calendars/foo%/events")
    neg_path("CTRL-NEG-MALFORM-G1", "/calendar/v3/calendars/foo%G1bar/events")
    neg_path("CTRL-NEG-MALFORM-TRUNC", "/calendar/v3/calendars/foo%2/events")
    neg_path("CTRL-NEG-UTF8-INVALID", "/calendar/v3/calendars/%80/events")

    # Synthetic already-matching prefix so helper is reached.
    try:
        probe = TransportProbe()
        peer = make_peer(HTTPSPeer, FIXTURE_HOST, FIXTURE_ADDR)
        routes = ((peer, SYNTH_PREFIX, "event"),)
        url = f"https://{FIXTURE_HOST}/__fixture__/covering/admit/enc%41bad"
        try:
            run_http_get(
                CoveringHTTP=CoveringHTTP,
                HTTPSPeer=HTTPSPeer,
                ProviderLimits=ProviderLimits,
                ProviderCounter=ProviderCounter,
                peer_host=FIXTURE_HOST,
                peer_addr=FIXTURE_ADDR,
                prefix=SYNTH_PREFIX,
                purpose="event",
                url=url,
                probe=probe,
                routes=routes,
            )
            raise ControlFailure("STRUCT-PCT-HELPER should refuse")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, "path admission refused")
        _assert_pre_send_zero(probe, label="STRUCT-PCT-HELPER")
        # Confirm helper path: structural % after route match.
        try:
            admit_covering_path("/__fixture__/covering/admit/enc%41bad")
            raise ControlFailure("helper alone should refuse structural %")
        except CoveringTransportRefused:
            pass
        assert_ctx_pre_delegate_refuse(
            "/__fixture__/covering/admit/enc%41bad",
            prefix=SYNTH_PREFIX,
            host=FIXTURE_HOST,
            addr=FIXTURE_ADDR,
            purpose="event",
            message="path admission refused",
            routes=routes,
        )
        record(
            "CTRL-NEG-STRUCT-PCT-HELPER",
            "PASS",
            "synthetic matching prefix reaches admit_covering_path; structural % refused; "
            "context pre-delegate refuse (0 delegate calls)",
        )
    except Exception as exc:
        record("CTRL-NEG-STRUCT-PCT-HELPER", "FAIL", repr(exc))

    neg_path("CTRL-NEG-BUDGET-EQ-9", "/calendar/v3/calendars/%252525252525252561/events")

    # Prefix boundary: no child match for calendars-other
    try:
        probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, "/calendar/v3/calendars", "event"),)
        url = f"https://{G_HOST}/calendar/v3/calendars-other/x/events"
        try:
            run_http_get(
                CoveringHTTP=CoveringHTTP,
                HTTPSPeer=HTTPSPeer,
                ProviderLimits=ProviderLimits,
                ProviderCounter=ProviderCounter,
                peer_host=G_HOST,
                peer_addr=G_ADDR,
                prefix="/calendar/v3/calendars",
                purpose="event",
                url=url,
                probe=probe,
                routes=routes,
            )
            raise ControlFailure("prefix boundary should refuse route")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, "provider route refused")
        if probe.opens != 0 or probe.sends != 0:
            raise ControlFailure("route refuse must be pre-send")
        record("CTRL-NEG-PREFIX-BOUNDARY", "PASS", "route refuse before helper")
    except Exception as exc:
        record("CTRL-NEG-PREFIX-BOUNDARY", "FAIL", repr(exc))

    # CoveringHTTP PATCH typed refuse
    try:
        probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, G_EVENTS_PREFIX, "event"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(probe, [ok_body()])
        http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        url = f"https://{G_HOST}/calendar/v3/calendars/calx/events/eid123"
        try:
            http.request("PATCH", url, purpose="event")
            raise ControlFailure("PATCH should typed-refuse at CoveringHTTP")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, "method/purpose refused")
        if probe.opens != 0 or probe.sends != 0:
            raise ControlFailure("PATCH typed refuse must be pre-send")
        record(
            "CTRL-NEG-COVERINGHTTP-PATCH-TYPED",
            "PASS",
            "CoveringHTTP.request PATCH → method/purpose refused; no PATCH support added",
        )
    except Exception as exc:
        record("CTRL-NEG-COVERINGHTTP-PATCH-TYPED", "FAIL", repr(exc))

    # _CoveringClient.patch AttributeError (distinct from typed CoveringHTTP refuse)
    try:
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, G_EVENTS_PREFIX, "event"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        probe = TransportProbe()
        factory = make_scripted_transport_factory(probe, [ok_body()])
        transport = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        client = _CoveringClient(transport)
        if hasattr(client, "patch"):
            raise ControlFailure("_CoveringClient unexpectedly has patch")
        try:
            client.patch("https://example.invalid/x")  # type: ignore[attr-defined]
            raise ControlFailure("expected AttributeError for missing patch")
        except AttributeError as exc:
            if "patch" not in str(exc).lower() and "has no attribute" not in str(exc):
                # AttributeError message varies; attribute absence is the claim.
                pass
            if hasattr(client, "patch"):
                raise ControlFailure("patch appeared after call")
        if probe.opens != 0 or probe.sends != 0:
            raise ControlFailure("absent patch must not open/send")
        record(
            "CTRL-NEG-COVERINGCLIENT-PATCH-ABSENT",
            "PASS",
            "AttributeError: _CoveringClient has no attribute patch; distinct from typed CoveringHTTP refuse",
        )
    except Exception as exc:
        record("CTRL-NEG-COVERINGCLIENT-PATCH-ABSENT", "FAIL", repr(exc))

    # --- B2. Context pre-delegate named controls (oracle-gap additions; not ceilings) ---
    try:
        assert_ctx_pre_delegate_refuse(
            "/calendar/v3/calendars/ordinary%2Fid/events",
            prefix=G_EVENTS_PREFIX,
            host=G_HOST,
            addr=G_ADDR,
            purpose="event",
            message="path admission refused",
        )
        record(
            "CTRL-NEG-CTX-ORD-SLASH",
            "PASS",
            "_CoveringClient ORD-SLASH: admit refuse before sentinel transport.request; 0 delegate calls",
        )
    except Exception as exc:
        record("CTRL-NEG-CTX-ORD-SLASH", "FAIL", repr(exc))

    try:
        assert_ctx_pre_delegate_refuse(
            "/calendar/v3/calendars/x%2Fy/events",
            prefix=G_EVENTS_PREFIX,
            host=G_HOST,
            addr=G_ADDR,
            purpose="event",
            message="path admission refused",
        )
        record(
            "CTRL-NEG-CTX-ENC-SLASH",
            "PASS",
            "_CoveringClient ENC-SLASH: admit refuse before sentinel transport.request; 0 delegate calls",
        )
    except Exception as exc:
        record("CTRL-NEG-CTX-ENC-SLASH", "FAIL", repr(exc))

    try:
        assert_ctx_pre_delegate_refuse(
            "/calendar/v3/calendars/foo%/events",
            prefix=G_EVENTS_PREFIX,
            host=G_HOST,
            addr=G_ADDR,
            purpose="event",
            message="path admission refused",
        )
        record(
            "CTRL-NEG-CTX-MALFORM",
            "PASS",
            "_CoveringClient MALFORM: admit refuse before sentinel transport.request; 0 delegate calls",
        )
    except Exception as exc:
        record("CTRL-NEG-CTX-MALFORM", "FAIL", repr(exc))

    # --- C. Collision (2) ---
    try:
        probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = (
            (peer, G_EVENTS_PREFIX, "event"),
            (peer, G_EVENTS_PREFIX, "identity"),
        )
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(probe, [ok_body()])
        transport = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        url = f"https://{G_HOST}/calendar/v3/calendars/calx/events"
        with covering_provider_transport(transport):
            with calendar_client(timeout=30.0) as client:
                try:
                    client.get(url, headers={"Authorization": "Bearer fake"})
                    raise ControlFailure("multi-purpose should refuse ambiguous")
                except CoveringTransportRefused as exc:
                    _assert_refuse(
                        exc, CoveringTransportRefused, "ambiguous/unapproved provider route"
                    )
        if probe.opens != 0 or probe.sends != 0:
            raise ControlFailure("ambiguous refuse must be pre-send")
        record("CTRL-COLLIDE-MULTI-PURPOSE", "PASS", "ambiguous/unapproved provider route")
    except Exception as exc:
        record("CTRL-COLLIDE-MULTI-PURPOSE", "FAIL", repr(exc))

    try:
        # Two distinguishable synthetic numeric peers; same hostname/prefix/purpose.
        # First-match selection must hand the FIRST peer identity/address to transport.
        # No real dial / profile bind / TLS claim.
        probe = TransportProbe()
        peer_first = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        peer_second = make_peer(HTTPSPeer, G_HOST, G_ADDR_DUP_SECOND)
        if peer_first.address == peer_second.address:
            raise ControlFailure("dup peers must be distinguishable by address")
        if peer_first.hostname != peer_second.hostname:
            raise ControlFailure("dup peers must share hostname")
        routes = (
            (peer_first, G_EVENTS_PREFIX, "event"),
            (peer_second, G_EVENTS_PREFIX, "event"),
        )
        url = f"https://{G_HOST}/calendar/v3/calendars/calx/events"
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(probe, [ok_body()])
        http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        http.request("GET", url, purpose="event")
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure("dup-same-purpose first-match should admit once")
        if probe.constructs != 1 or probe.closes != 1:
            raise ControlFailure("dup-same-purpose must retire one exchange")
        dup_count = sum(
            1 for _p, pref, kind in routes if pref == G_EVENTS_PREFIX and kind == "event"
        )
        if dup_count != 2:
            raise ControlFailure("fixture must present duplicate same-purpose mappings")
        selected = probe.selected_peers or []
        if len(selected) != 1:
            raise ControlFailure(
                f"expected exactly one selected peer for one exchange; got {len(selected)}"
            )
        selected_peer = selected[0]
        if selected_peer is not peer_first:
            raise ControlFailure(
                "first-peer selection failed: transport did not receive first peer object"
            )
        if getattr(selected_peer, "address", None) != G_ADDR:
            raise ControlFailure(
                f"first selected peer address mismatch: "
                f"got {getattr(selected_peer, 'address', None)!r} want {G_ADDR!r}"
            )
        if getattr(selected_peer, "address", None) == G_ADDR_DUP_SECOND:
            raise ControlFailure("second peer must not be selected under first-match")
        record(
            "CTRL-COLLIDE-DUP-SAME-PURPOSE",
            "PASS",
            f"first-match admit; selected peer address={G_ADDR} "
            f"(not {G_ADDR_DUP_SECOND}); one-exchange counts+retirement; "
            f"no dial/profile-bind/TLS claim",
        )
    except Exception as exc:
        record("CTRL-COLLIDE-DUP-SAME-PURPOSE", "FAIL", repr(exc))

    # --- D. Continuation / redirect (4) ---
    try:
        probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, G_EVENTS_PREFIX, "event"),)
        # Foreign absolute URL — peer not in reviewed routes.
        url = f"https://{FOREIGN_HOST}/calendar/v3/calendars/calx/events"
        try:
            run_http_get(
                CoveringHTTP=CoveringHTTP,
                HTTPSPeer=HTTPSPeer,
                ProviderLimits=ProviderLimits,
                ProviderCounter=ProviderCounter,
                peer_host=G_HOST,
                peer_addr=G_ADDR,
                prefix=G_EVENTS_PREFIX,
                purpose="event",
                url=url,
                probe=probe,
                routes=routes,
            )
            raise ControlFailure("foreign host should refuse before send")
        except CoveringTransportRefused as exc:
            # origin or route refuse — either is pre-send refusal
            if "refused" not in str(exc):
                raise ControlFailure(f"unexpected refuse text: {exc!r}")
        if probe.opens != 0 or probe.sends != 0:
            raise ControlFailure("foreign must be 0 opens/sends")
        record(
            "CTRL-CONT-FOREIGN-BEFORE-SEND",
            "PASS",
            "origin/route refuse before send; 0/0",
        )
    except Exception as exc:
        record("CTRL-CONT-FOREIGN-BEFORE-SEND", "FAIL", repr(exc))

    try:
        probe = TransportProbe()
        body = framed_http_json(
            302,
            {},
            location="https://www.googleapis.com/calendar/v3/calendars/calx/events",
        )
        url = f"https://{G_HOST}/calendar/v3/calendars/calx/events"
        try:
            run_http_get(
                CoveringHTTP=CoveringHTTP,
                HTTPSPeer=HTTPSPeer,
                ProviderLimits=ProviderLimits,
                ProviderCounter=ProviderCounter,
                peer_host=G_HOST,
                peer_addr=G_ADDR,
                prefix=G_EVENTS_PREFIX,
                purpose="event",
                url=url,
                probe=probe,
                bodies=[body],
            )
            raise ControlFailure("302 should refuse redirect")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, "redirect refused")
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure("redirect refuse after exactly one exchange")
        # Zero Location follow-ups: only one construct/open/send.
        if probe.constructs != 1:
            raise ControlFailure("Location follow would construct again")
        record(
            "CTRL-CONT-REDIRECT-3XX",
            "PASS",
            "1 open/send original; 0 follow-ups; redirect refused",
        )
    except Exception as exc:
        record("CTRL-CONT-REDIRECT-3XX", "FAIL", repr(exc))

    try:
        probe = TransportProbe()
        abs_url = _absolute_graph_url(MS_NEXTLINK_URL)
        if abs_url != MS_NEXTLINK_URL:
            raise ControlFailure(f"_absolute_graph_url altered absolute URL: {abs_url!r}")
        parsed = urlsplit(abs_url)
        run_http_get(
            CoveringHTTP=CoveringHTTP,
            HTTPSPeer=HTTPSPeer,
            ProviderLimits=ProviderLimits,
            ProviderCounter=ProviderCounter,
            peer_host=MS_HOST,
            peer_addr=MS_ADDR,
            prefix=MS_CALENDARS_PREFIX,
            purpose="event",
            url=abs_url,
            probe=probe,
        )
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure("MS nextLink path admit open/send mismatch")
        # Query $skiptoken remains opaque (on wire request-target).
        wire0 = (probe.wires or [b""])[0].split(b"\r\n", 1)[0]
        if b"$skiptoken=1" not in wire0 and b"%24skiptoken=1" not in wire0:
            # urlsplit path+query: CoveringHTTP rebuilds path?query from parsed
            if b"skiptoken" not in wire0:
                raise ControlFailure(f"skiptoken missing on wire: {wire0!r}")
        record(
            "CTRL-CONT-MS-NEXTLINK",
            "PASS",
            "admitted Graph nextLink path via _absolute_graph_url; target authz separate",
        )
    except Exception as exc:
        record("CTRL-CONT-MS-NEXTLINK", "FAIL", repr(exc))

    # Builder-continuation: extracted Google pagination, 2 scripted pages.
    try:
        probe = TransportProbe()
        page1 = ok_body({"items": [{"id": "e1"}], "nextPageToken": PAGE_TOKEN_OPAQUE})
        page2 = ok_body({"items": [{"id": "e2"}]})
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, G_EVENTS_PREFIX, "event"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(probe, [page1, page2])
        transport = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        # calendar_id that quotes to cal%2Bendar%40x.com
        cal_id = "cal+endar@x.com"
        base = _calendar_events_base(cal_id)
        if "cal%2Bendar%40x.com" not in base:
            raise ControlFailure(f"calendar base quote unexpected: {base}")
        with covering_provider_transport(transport):
            items, _sync, pages = _paginate_events(
                "fake-token",
                base,
                params={"maxResults": "2"},
            )
        if pages != 2:
            raise ControlFailure(f"expected 2 pages, got {pages}")
        if probe.opens != 2 or probe.sends != 2:
            raise ControlFailure(
                f"setup1+continuation1 must be 2 opens/sends; got {probe.opens}/{probe.sends}"
            )
        if probe.constructs != 2 or probe.closes != 2:
            raise ControlFailure("two complete scripted exchanges required")
        wires = probe.wires or []
        if len(wires) != 2:
            raise ControlFailure("expected two request wires")
        cont_line = wires[1].split(b"\r\n", 1)[0]
        # Continuation carries URL-shaped token as query (urlencoded).
        if b"pageToken=" not in cont_line:
            raise ControlFailure(f"continuation missing pageToken query: {cont_line!r}")
        if quote(PAGE_TOKEN_OPAQUE, safe="").encode("ascii") not in cont_line:
            raise ControlFailure("URL-shaped nextPageToken not on continuation wire")
        # Zero destination/redirect follow-ups: no third exchange; no Location follow.
        if probe.opens != 2:
            raise ControlFailure("redirect follow-up would add opens")
        if len(items) != 2:
            raise ControlFailure(f"expected 2 items across pages, got {len(items)}")
        record(
            "CTRL-CONT-G-PAGE-TOKEN",
            "PASS",
            "builder: setup1+continuation1=2 opens/sends; URL-shaped pageToken query; 0 redirect follow-ups",
        )
    except Exception as exc:
        record("CTRL-CONT-G-PAGE-TOKEN", "FAIL", repr(exc))

    policy_source = CANDIDATE_API / "app/services/covering_transport_policy.py"
    http_source = CANDIDATE_API / "app/services/covering_http_transport.py"

    # --- E. Separation (1) ---
    # Explicitly separate from native I01-C02. No manufactured auth proof; no
    # implementation-scope broaden. Observable pinned-source / interface evidence
    # that path admission alone cannot establish authorized calendar binding.
    try:
        probe = TransportProbe()
        path = "/calendar/v3/calendars/calx/events"
        admit_ret = admit_covering_path(path)  # helper success; returns None
        if admit_ret is not None:
            raise ControlFailure(
                "admit_covering_path must not return an authz-binding token/object"
            )
        run_http_get(
            CoveringHTTP=CoveringHTTP,
            HTTPSPeer=HTTPSPeer,
            ProviderLimits=ProviderLimits,
            ProviderCounter=ProviderCounter,
            peer_host=G_HOST,
            peer_addr=G_ADDR,
            prefix=G_EVENTS_PREFIX,
            purpose="event",
            url=f"https://{G_HOST}{path}",
            probe=probe,
        )
        if probe.opens != 1 or probe.sends != 1:
            raise ControlFailure("SEP path admit must still complete 1/1 exchange")

        # Interface evidence: extracted _CoveringClient exposes get/post/_request only —
        # no calendar-target-authz binder API.
        client_public = {
            n for n in dir(_CoveringClient) if not n.startswith("__")
        }
        authz_binder_names = {
            "bind_target",
            "bind_calendar",
            "authorize_calendar",
            "authorize_target",
            "set_target_authz",
            "target_authz_bind",
            "admit_target_authz",
            "bind_authorized_calendar",
        }
        overlap = sorted(client_public & authz_binder_names)
        if overlap:
            raise ControlFailure(
                f"_CoveringClient unexpectedly exposes authz binder APIs: {overlap}"
            )
        for required in ("get", "post", "_request"):
            if required not in client_public:
                raise ControlFailure(f"_CoveringClient missing expected surface {required}")

        # AST/source evidence on pinned policy: admit_covering_path body has no
        # calendar-target-authz binder call/name.
        policy_tree = _load_module_ast(policy_source)
        admit_fn = _find_top_function(policy_tree, "admit_covering_path")
        binder_hits: list[str] = []
        for node in ast.walk(admit_fn):
            if isinstance(node, ast.Name) and node.id in authz_binder_names:
                binder_hits.append(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in authz_binder_names:
                binder_hits.append(node.attr)
        if binder_hits:
            raise ControlFailure(
                f"admit_covering_path AST unexpectedly references authz binders: {binder_hits}"
            )
        # Confirm docstring/separation comment remains the separation claim surface
        # (path admission does not claim target authorization).
        admit_src = ast.get_source_segment(
            policy_source.read_text(encoding="utf-8"), admit_fn
        ) or ""
        if "Target authorization remains separate" not in admit_src and (
            "authorization remains separate" not in admit_src.lower()
        ):
            # Fall back to module-level docstring check on the function docstring.
            if not (admit_fn.body and isinstance(admit_fn.body[0], ast.Expr)):
                raise ControlFailure("admit_covering_path missing docstring separation claim")
            doc_node = admit_fn.body[0].value
            doc = ""
            if isinstance(doc_node, ast.Constant) and isinstance(doc_node.value, str):
                doc = doc_node.value
            if "separate" not in doc.lower():
                raise ControlFailure(
                    "admit_covering_path docstring must keep target-authz separation claim"
                )

        # Stimulus: path admits for concrete ID while no authz-binding API is
        # available/invoked on extracted surfaces (cannot establish authorized binding).
        client = _CoveringClient(
            CoveringHTTP(
                counter=make_counter(ProviderLimits, ProviderCounter),
                routes=((make_peer(HTTPSPeer, G_HOST, G_ADDR), G_EVENTS_PREFIX, "event"),),
                transport_factory=make_scripted_transport_factory(TransportProbe(), [ok_body()]),
            )
        )
        for name in authz_binder_names:
            if hasattr(client, name):
                raise ControlFailure(f"live _CoveringClient unexpectedly has {name}")
            if hasattr(admit_covering_path, name):
                raise ControlFailure(f"admit_covering_path unexpectedly has {name}")

        record(
            "CTRL-SEP-TARGET-AUTHZ",
            "PASS",
            "path admit 1/1 observed; extracted covering surface has no calendar-target-authz "
            "binder (AST+interface); admit returns no authz token; separate from native I01-C02; "
            "no auth proof manufactured",
        )
    except Exception as exc:
        record("CTRL-SEP-TARGET-AUTHZ", "FAIL", repr(exc))

    # --- Mutation controls (harness-only; narrowly scoped; never production) ---
    # Mutants are temporary/in-memory only; never edit candidate snapshot files.

    try:
        tree = _load_module_ast(policy_source)
        fn = copy.deepcopy(_find_top_function(tree, "admit_covering_path"))
        # MUTATION_PROVENANCE M-PATH-ADMIT-NOOP: body → bare return (skip helper).
        fn.body = [ast.Return(value=None)]
        ast.fix_missing_locations(fn)
        mutated_admit = compile_mutated_method(
            fn, filename="<m-path-admit-noop>", bind_globals=policy["__ns__"]
        )
        policy_ns = policy["__ns__"]
        http_ns = http_mod["__ns__"]
        policy_mod = sys.modules["fake_d2_cand_covering_transport_policy"]
        http_mod_obj = sys.modules["fake_d2_cand_covering_http_transport"]
        orig_admit = policy_ns["admit_covering_path"]
        witness_path = "/calendar/v3/calendars/ordinary%2Fid/events"
        witness_url = f"https://{G_HOST}{witness_path}"

        def _drive_ord_slash(label: str) -> TransportProbe:
            probe = TransportProbe()
            peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
            routes = ((peer, G_EVENTS_PREFIX, "event"),)
            counter = make_counter(ProviderLimits, ProviderCounter)
            factory = make_scripted_transport_factory(probe, [ok_body()])
            http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
            http.request("GET", witness_url, purpose="event")
            return probe

        # Rebind mutated admit into policy + CoveringHTTP globals actually used.
        policy_ns["admit_covering_path"] = mutated_admit
        setattr(policy_mod, "admit_covering_path", mutated_admit)
        http_ns["admit_covering_path"] = mutated_admit
        setattr(http_mod_obj, "admit_covering_path", mutated_admit)
        try:
            mut_probe = _drive_ord_slash("mutant")
            if mut_probe.opens < 1 or mut_probe.sends < 1:
                raise ControlFailure(
                    f"M-PATH-ADMIT-NOOP mutant must reach open/send; "
                    f"got {mut_probe.opens}/{mut_probe.sends}"
                )
            if mut_probe.constructs < 1:
                raise ControlFailure("M-PATH-ADMIT-NOOP mutant must construct transport")
        finally:
            policy_ns["admit_covering_path"] = orig_admit
            setattr(policy_mod, "admit_covering_path", orig_admit)
            http_ns["admit_covering_path"] = orig_admit
            setattr(http_mod_obj, "admit_covering_path", orig_admit)

        # Positive candidate control: SAME assertion shape refuses 0/0 unmutated.
        unmut_probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, G_EVENTS_PREFIX, "event"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(unmut_probe, [ok_body()])
        http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        try:
            http.request("GET", witness_url, purpose="event")
            raise ControlFailure("unmutated ORD-SLASH CoveringHTTP must refuse")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, "path admission refused")
        _assert_pre_send_zero(unmut_probe, label="M-PATH-ADMIT-NOOP-unmutated")
        record(
            "M-PATH-ADMIT-NOOP",
            "PASS",
            "MUTATION_PROVENANCE M-PATH-ADMIT-NOOP: extracted admit_covering_path→noop rebound "
            "into CoveringHTTP; ORD-SLASH mutant reaches open/send; unmutated SAME assertion "
            "refuses path admission 0/0; never in production snapshot",
        )
    except Exception as exc:
        record("M-PATH-ADMIT-NOOP", "FAIL", repr(exc))

    try:
        tree = _load_module_ast(http_source)
        method = copy.deepcopy(_find_class_method(tree, "CoveringHTTP", "request"))
        # MUTATION_PROVENANCE M-HTTP-ALLOW-PATCH: widen method gate to include PATCH.
        hits = 0
        for node in ast.walk(method):
            if isinstance(node, ast.Compare):
                if isinstance(node.left, ast.Name) and node.left.id == "method":
                    for comparator in node.comparators:
                        if isinstance(comparator, ast.Tuple):
                            elts = comparator.elts
                            if (
                                len(elts) == 2
                                and all(isinstance(e, ast.Constant) for e in elts)
                                and {e.value for e in elts} == {"GET", "POST"}
                            ):
                                comparator.elts = list(elts) + [ast.Constant(value="PATCH")]
                                hits += 1
        if hits != 1:
            raise ControlFailure(f"expected 1 method-tuple widen; got {hits}")
        bind_ns = dict(http_mod["__ns__"])
        mutated_request = compile_mutated_method(
            method, filename="<m-http-allow-patch>", bind_globals=bind_ns
        )
        patch_url = f"https://{G_HOST}/calendar/v3/calendars/calx/events/eid123"

        # Mutant: PATCH must reach observable transport construct/open/send.
        mut_probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, G_EVENTS_PREFIX, "event"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(mut_probe, [ok_body()])
        inst = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        mutated_request(inst, "PATCH", patch_url, purpose="event")
        if mut_probe.constructs < 1 or mut_probe.opens < 1 or mut_probe.sends < 1:
            raise ControlFailure(
                f"M-HTTP-ALLOW-PATCH mutant must reach construct/open/send; "
                f"got {mut_probe.constructs}/{mut_probe.opens}/{mut_probe.sends} "
                f"(non-method refuse alone is NOT success)"
            )

        # Positive candidate control: unmutated typed-refuse never reaches transport.
        unmut_probe = TransportProbe()
        counter2 = make_counter(ProviderLimits, ProviderCounter)
        factory2 = make_scripted_transport_factory(unmut_probe, [ok_body()])
        inst2 = CoveringHTTP(counter=counter2, routes=routes, transport_factory=factory2)
        try:
            inst2.request("PATCH", patch_url, purpose="event")
            raise ControlFailure("unmutated PATCH must typed-refuse")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, "method/purpose refused")
        _assert_pre_send_zero(unmut_probe, label="M-HTTP-ALLOW-PATCH-unmutated")
        record(
            "M-HTTP-ALLOW-PATCH",
            "PASS",
            "MUTATION_PROVENANCE M-HTTP-ALLOW-PATCH: CoveringHTTP.request method tuple +PATCH; "
            "mutant PATCH reaches construct/open/send; unmutated SAME typed-refuse assertion "
            "stays 0/0; never in production snapshot",
        )
    except Exception as exc:
        record("M-HTTP-ALLOW-PATCH", "FAIL", repr(exc))

    try:
        tree = _load_module_ast(policy_source)
        fn = copy.deepcopy(_find_top_function(tree, "_inspect_opaque_id_segment"))
        # MUTATION_PROVENANCE M-ENCODED-SLASH-BYPASS: neutralize BOTH encoded-slash
        # and decoded-literal-slash refuses inside _inspect_opaque_id_segment so
        # ENC-SLASH (%2F) actually changes admission when driven through CoveringHTTP.
        # (_has_encoded_slash alone is redundant with "/" in cur after decode.)
        cond_hits = 0
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            # Match: cur == "" or _is_dot_nav(cur) or "/" in cur or _has_encoded_slash(cur)
            if not isinstance(test, ast.BoolOp) or not isinstance(test.op, ast.Or):
                continue
            # Rewrite refuse predicate to empty/dot-nav only (keep malformed/budget intact).
            # Identify by presence of _has_encoded_slash Call and "/" in Compare.
            src_dump = ast.dump(test)
            if "_has_encoded_slash" not in src_dump or "In" not in src_dump:
                continue
            node.test = ast.BoolOp(
                op=ast.Or(),
                values=[
                    ast.Compare(
                        left=ast.Name(id="cur", ctx=ast.Load()),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value="")],
                    ),
                    ast.Call(
                        func=ast.Name(id="_is_dot_nav", ctx=ast.Load()),
                        args=[ast.Name(id="cur", ctx=ast.Load())],
                        keywords=[],
                    ),
                ],
            )
            cond_hits += 1
        if cond_hits != 1:
            raise ControlFailure(
                f"expected 1 encoded/literal-slash refuse neutralization; got {cond_hits}"
            )
        ast.fix_missing_locations(fn)
        mutated_inspect = compile_mutated_method(
            fn, filename="<m-encoded-slash-bypass>", bind_globals=policy["__ns__"]
        )
        policy_ns = policy["__ns__"]
        http_ns = http_mod["__ns__"]
        policy_mod = sys.modules["fake_d2_cand_covering_transport_policy"]
        orig_inspect = policy_ns["_inspect_opaque_id_segment"]
        enc_path = "/calendar/v3/calendars/x%2Fy/events"
        enc_url = f"https://{G_HOST}{enc_path}"

        policy_ns["_inspect_opaque_id_segment"] = mutated_inspect
        setattr(policy_mod, "_inspect_opaque_id_segment", mutated_inspect)
        try:
            mut_probe = TransportProbe()
            peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
            routes = ((peer, G_EVENTS_PREFIX, "event"),)
            counter = make_counter(ProviderLimits, ProviderCounter)
            factory = make_scripted_transport_factory(mut_probe, [ok_body()])
            http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
            http.request("GET", enc_url, purpose="event")
            if mut_probe.opens < 1 or mut_probe.sends < 1:
                raise ControlFailure(
                    f"M-ENCODED-SLASH-BYPASS mutant must admit ENC-SLASH with open/send; "
                    f"got {mut_probe.opens}/{mut_probe.sends}"
                )
            if mut_probe.constructs < 1:
                raise ControlFailure("mutant ENC-SLASH must construct transport")
        finally:
            policy_ns["_inspect_opaque_id_segment"] = orig_inspect
            setattr(policy_mod, "_inspect_opaque_id_segment", orig_inspect)

        # Positive candidate control: unmutated SAME CoveringHTTP assertion refuses 0/0.
        unmut_probe = TransportProbe()
        peer = make_peer(HTTPSPeer, G_HOST, G_ADDR)
        routes = ((peer, G_EVENTS_PREFIX, "event"),)
        counter = make_counter(ProviderLimits, ProviderCounter)
        factory = make_scripted_transport_factory(unmut_probe, [ok_body()])
        http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
        try:
            http.request("GET", enc_url, purpose="event")
            raise ControlFailure("unmutated ENC-SLASH CoveringHTTP must refuse")
        except CoveringTransportRefused as exc:
            _assert_refuse(exc, CoveringTransportRefused, "path admission refused")
        _assert_pre_send_zero(unmut_probe, label="M-ENCODED-SLASH-BYPASS-unmutated")
        record(
            "M-ENCODED-SLASH-BYPASS",
            "PASS",
            "MUTATION_PROVENANCE M-ENCODED-SLASH-BYPASS: neutralized encoded-slash AND "
            "decoded-literal-slash refuses inside extracted _inspect_opaque_id_segment; "
            "ENC-SLASH CoveringHTTP mutant reaches open/send; unmutated SAME assertion "
            "refuses 0/0; never in production snapshot",
        )
    except Exception as exc:
        record("M-ENCODED-SLASH-BYPASS", "FAIL", repr(exc))

    # --- Inventory self-checks (accept good; reject reorder/dup/missing/altered) ---
    expected = load_expected()
    expected_ids = expected_control_ids(expected)

    try:
        # Accept good ordered result for already-emitted prefix is not full inventory;
        # craft a complete synthetic GOOD matching EXPECTED ids/results, then enforce.
        good = [
            ControlResult(cid, expected["controls"][cid]["result"], "synthetic-good")
            for cid in expected_ids
        ]
        enforce_expected_inventory(good, expected)
        record(
            "H-INVENTORY-ACCEPTS-GOOD",
            "PASS",
            "enforce_expected_inventory accepts exact ordered good result",
        )
    except Exception as exc:
        record("H-INVENTORY-ACCEPTS-GOOD", "FAIL", repr(exc))

    try:
        good = [
            ControlResult(cid, expected["controls"][cid]["result"], "x")
            for cid in expected_ids
        ]
        wrong_order = list(reversed(good))
        if wrong_order == good:
            raise ControlFailure("cannot build reorder fixture")
        caught = False
        try:
            enforce_expected_inventory(wrong_order, expected)
        except ControlFailure as exc:
            if "order mismatch" not in str(exc):
                raise ControlFailure(f"reorder did not cite order: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted reorder")
        record("H-INVENTORY-REJECTS-REORDER", "PASS", "rejects reordered control_ids")
    except Exception as exc:
        record("H-INVENTORY-REJECTS-REORDER", "FAIL", repr(exc))

    try:
        good = [
            ControlResult(cid, expected["controls"][cid]["result"], "x")
            for cid in expected_ids
        ]
        dup = list(good) + [good[0]]
        caught = False
        try:
            enforce_expected_inventory(dup, expected)
        except ControlFailure as exc:
            if "duplicate" not in str(exc):
                raise ControlFailure(f"duplicate did not cite duplicate: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted duplicate")
        record("H-INVENTORY-REJECTS-DUPLICATE", "PASS", "rejects duplicate control_ids")
    except Exception as exc:
        record("H-INVENTORY-REJECTS-DUPLICATE", "FAIL", repr(exc))

    try:
        good = [
            ControlResult(cid, expected["controls"][cid]["result"], "x")
            for cid in expected_ids
        ]
        missing = good[:-1]
        caught = False
        try:
            enforce_expected_inventory(missing, expected)
        except ControlFailure as exc:
            if "order mismatch" not in str(exc):
                raise ControlFailure(f"missing did not cite mismatch: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted missing")
        record("H-INVENTORY-REJECTS-MISSING", "PASS", "rejects missing control_ids")
    except Exception as exc:
        record("H-INVENTORY-REJECTS-MISSING", "FAIL", repr(exc))

    try:
        altered = [
            ControlResult(
                cid,
                "FAIL" if expected["controls"][cid]["result"] != "FAIL" else "PASS",
                "deliberate-altered",
            )
            for cid in expected_ids
        ]
        caught = False
        try:
            enforce_expected_inventory(altered, expected)
        except ControlFailure as exc:
            if "unexpected-outcome" not in str(exc):
                raise ControlFailure(f"altered did not cite unexpected-outcome: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted altered outcomes")
        record(
            "H-INVENTORY-REJECTS-ALTERED",
            "PASS",
            "rejects altered/unexpected outcomes before PASS",
        )
    except Exception as exc:
        record("H-INVENTORY-REJECTS-ALTERED", "FAIL", repr(exc))

    return results


def main() -> int:
    provenance: list[ExtractionProvenance] = []
    inventory_error = None
    source_hashes_verified = False
    results: list[ControlResult] = []
    try:
        install_stubs()
        manifest = load_manifest()
        expected = load_expected()
        verify_source_hashes(manifest)
        source_hashes_verified = True

        policy = build_policy_module(
            CANDIDATE_API / "app/services/covering_transport_policy.py",
            "fake_d2_cand_covering_transport_policy",
            provenance,
        )
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            "fake_d2_cand_covering_transport_policy"
        ]
        http_mod = build_http_module(
            CANDIDATE_API / "app/services/covering_http_transport.py",
            "fake_d2_cand_covering_http_transport",
            "fake_d2_cand_covering_transport_policy",
            provenance,
        )
        sys.modules["app.services.covering_http_transport"] = sys.modules[
            "fake_d2_cand_covering_http_transport"
        ]
        ctx = build_context_module(
            CANDIDATE_API / "app/services/covering_provider_context.py",
            "fake_d2_cand_covering_provider_context",
            "fake_d2_cand_covering_transport_policy",
            provenance,
        )
        sys.modules["app.services.covering_provider_context"] = sys.modules[
            "fake_d2_cand_covering_provider_context"
        ]
        # Re-bind calendar_client into google extraction after context is live.
        google = build_google_pagination(
            CANDIDATE_API / "app/services/google_calendar.py",
            "fake_d2_cand_google_calendar_pagination",
            provenance,
        )
        ms = build_ms_absolute_url(
            CANDIDATE_API / "app/services/microsoft_calendar.py",
            "fake_d2_cand_microsoft_absolute_url",
            provenance,
        )

        bundle = {
            "policy": policy,
            "http": http_mod,
            "ctx": ctx,
            "google": google,
            "ms": ms,
            "provenance": provenance,
        }
        results = run_controls(bundle)
        enforce_expected_inventory(results, expected)
        status = "PASS"
        exit_code = 0
    except Exception as exc:
        inventory_error = f"{type(exc).__name__}:{exc}"
        status = "FAIL"
        exit_code = 1

    by_id = {r.control_id: r for r in results}
    ordered_ids = [r.control_id for r in results]
    payload = {
        "status": status,
        "class": "FAKE-D2-PATH-ADMISSION",
        "executed": True,
        "executed_in_preparation": False,
        "held_preparation_only": True,
        "source_hashes_verified": source_hashes_verified,
        "inventory_error": inventory_error,
        "control_ids_in_order": ordered_ids,
        "controls": {
            cid: {
                "result": by_id[cid].result if cid in by_id else "MISSING",
                "detail": by_id[cid].detail if cid in by_id else "",
            }
            for cid in ordered_ids
        },
        "extraction_provenance": [
            {
                "source_path": p.source_path,
                "source_sha256": p.source_sha256,
                "names": p.names,
                "module_name": p.module_name,
            }
            for p in provenance
        ],
        "functional_control_count": 44,
        "approved_core_functional_control_count": 41,
        "oracle_gap_added_functional_controls": [
            "CTRL-NEG-CTX-ORD-SLASH",
            "CTRL-NEG-CTX-ENC-SLASH",
            "CTRL-NEG-CTX-MALFORM",
        ],
        "named_inventory_and_mutation_controls": [
            "M-PATH-ADMIT-NOOP",
            "M-HTTP-ALLOW-PATCH",
            "M-ENCODED-SLASH-BYPASS",
            "H-INVENTORY-ACCEPTS-GOOD",
            "H-INVENTORY-REJECTS-REORDER",
            "H-INVENTORY-REJECTS-DUPLICATE",
            "H-INVENTORY-REJECTS-MISSING",
            "H-INVENTORY-REJECTS-ALTERED",
        ],
        "unresolved_native_obligations": [
            "real TLS / provider dial — NOT claimed",
            "endpoint/profile binding — NOT claimed",
            "target calendar authorization — separate oracle; NOT claimed here",
            "full provider transport proof — NOT claimed",
            "T01–T08 closure — NOT claimed (this packet is path-admission fake only)",
            "DB acknowledgment — NOT claimed",
        ],
        "does_not_import_app": True,
        "launch_ready": False,
        "diff_sha256": "CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4",
        "overlay_sha256": "CA51E2D8F40073C260942B5AF634229D253D9E2AA77177C45471037ED3C59B4D",
    }
    RESULT_PATH.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    print(json.dumps({"status": status, "inventory_error": inventory_error}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
