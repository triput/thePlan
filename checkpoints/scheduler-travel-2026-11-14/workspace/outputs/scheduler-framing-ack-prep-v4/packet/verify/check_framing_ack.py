#!/usr/bin/env python3
"""HELD framing-ack fake check. Authoring only — not executed in preparation.

Exercises AST-extracted candidate CoveringHTTP / _GuardedHTTPResponse /
_admit_framing_headers / JoinedTLS.open wrap_socket option against finite
byte-fake stimuli. Reuses immutable 57 T05 wire inputs as original evidence
pins; freezes candidate expectations under approved header-compatibility
policy (AEAE5343… / 1C932F1A…).

CALLER-* rows reuse aliased transcripts via the same direct CoveringHTTP
run_http_catch path as ordinary wire controls. They are labeled as direct
HTTP replay plus matched immutable original caller evidence — not as new
candidate owning-caller (_CoveringClient / refresh_access_token) proof.
Owning-caller obligation remains preserved/unproved in-candidate.

Result rows emit predicted_outcome dialect "PASS" at top level (launcher
gate) with nested OBSERVED_* candidate/observation fields. exact_predicate
mirrors emitted entry keys for validate_result_file.

policy_pending is frozen accepted-policy metadata on EXPECTED candidate rows
and is stamped into launcher emit via emit_wire_candidate; it is excluded
from assert_match's flat runtime observation whitelist (absent from
run_http_catch cand).

No live sockets/TLS/PKI/providers. executed preparation = false.
"""
from __future__ import annotations

import ast
import hashlib
import http.client
import io
import json
import ssl
import sys
import types
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULT = HERE / "FAKE-FRAMING-ACK-RESULT.json"
EXPECTED = HERE / "EXPECTED.json"
MANIFEST = HERE / "INPUT-MANIFEST.json"
WIRE_DIR = HERE / "wire_transcripts"
MAX_RESULT = 262144
T05_RESULT_PIN = "D29D4CFDDE2B6EA3A7D2A99366A7211AA4FE58C34EC66FF7C6A8945F4525BCFC"
T05_EXPECTED_PIN = "E67AB1B1A4D35F02A73255F313666DF8513EF0C55BAAFFF59EBD69B37926AF99"
HOST_HTTP_CLIENT_PIN = "3A752927A1257EDEBCABAD42CA9508AD532F91C15431755BFBE437A32AB13EB2"
NATIVE_HTTP_PIN = "C2C0694155837D72FC710A4138E5D1E53AE1A652B117A2E23A5B1B0DB527A0F9"
CANDIDATE_HTTP_PIN = "29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368"
CANDIDATE_TLS_PIN = "760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427"
ORIGINAL_HTTP_PIN = "E2FC2226318E1F2D052D220C4A28F5116D7BEFD1FFBB01E863CD0767A1B28F0F"
ORIGINAL_TLS_PIN = "2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B"
PROVIDER_CTX_PIN = "65529CBC072F34BD80D273C3D1480B23EDDF6BD877DF39886E56D90A18D848D2"
HEADER_POLICY_DECISION_PIN = "AEAE53432BDCCA6BB805E7EC5B4A2F7AA37370B2C358F5E7D8738A165F81A1D0"
HEADER_POLICY_APPROVAL_PIN = "1C932F1A569AD55DF9B86C8994946B052B5BCDDB21676B848EC7ACBF98464059"

G_HOST = "www.googleapis.com"
G_ADDR = "203.0.113.10"
G_GAUTH = "oauth2.googleapis.com"
G_GADDR = "203.0.113.11"
CA_FILE = "synthetic-public-ca.pem"
EVENT_PREFIX = "/calendar/v3/calendars/"
TOKEN_EXACT = "/token"
GOOGLE_TOKEN_URL = f"https://{G_GAUTH}{TOKEN_EXACT}"


class WitnessFailure(Exception):
    pass


@dataclass
class CloseProbe:
    response_close_calls: int = 0
    transport_close_calls: int = 0
    transport_bytes_received: int = 0
    receive_calls: int = 0
    receive_amts: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.receive_amts is None:
            self.receive_amts = []


class FakeHttpxRequest:
    def __init__(self, method: str, url: str):
        self.method = method
        self.url = url


class FakeHttpxResponse:
    def __init__(self, status_code: int, *, content: bytes, headers: dict, request: Any):
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self.request = request
        self.text = content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.content)


class FakeApiError(Exception):
    def __init__(self, status_code: int, detail: str, code: str, **extra: object) -> None:
        self.status_code = status_code
        self.content = {"detail": detail, "code": code, **extra}
        super().__init__(detail)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def new_module_namespace(module_name: str) -> dict[str, Any]:
    module = types.ModuleType(module_name)
    module.__dict__["__builtins__"] = __builtins__
    module.__dict__["__name__"] = module_name
    module.__dict__["__annotations__"] = {}
    sys.modules[module_name] = module
    return module.__dict__


def extract_symbols(source_path: Path, names: list[str], module_ns: dict[str, Any]) -> dict[str, Any]:
    raw = source_path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    tree = ast.parse(text, filename=str(source_path))
    wanted = set(names)
    selected: list[ast.stmt] = []
    found: set[str] = set()
    for node in tree.body:
        hit = False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in wanted:
                hit = True
                found.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in wanted:
                    hit = True
                    found.add(t.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in wanted:
                hit = True
                found.add(node.target.id)
        if hit:
            selected.append(node)
    missing = sorted(wanted - found)
    if missing:
        raise WitnessFailure(f"AST names missing {source_path.name}: {missing}")
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"), module_ns)
    return {n: module_ns[n] for n in names}


def verify_sources(manifest: dict[str, Any]) -> None:
    seen: set[str] = set()
    for row in manifest["sources"]:
        rel = row["relative_path"]
        path = (ROOT / rel).resolve()
        if not path.is_relative_to(ROOT) or rel in seen:
            raise WitnessFailure("invalid source inventory")
        seen.add(rel)
        if sha256_file(path) != row["sha256"].upper():
            raise WitnessFailure(f"source pin mismatch:{rel}")
    actual = {
        p.relative_to(ROOT).as_posix()
        for v in ("original", "candidate")
        for p in (ROOT / v).rglob("*")
        if p.is_file()
    }
    if seen != actual or len(seen) != 468:
        raise WitnessFailure("source inventory mismatch")
    # Two-file application delta only.
    changed = []
    for row in manifest["sources"]:
        if not row["relative_path"].startswith("original/"):
            continue
        rel = row["relative_path"][len("original/") :]
        left = (ROOT / "original" / rel).read_bytes()
        right = (ROOT / "candidate" / rel).read_bytes()
        if left != right:
            changed.append(rel)
    if sorted(changed) != [
        "app/services/covering_http_transport.py",
        "app/services/covering_joined_https.py",
    ]:
        raise WitnessFailure(f"unexpected application delta:{changed}")
    if sha256_file(ROOT / "candidate/app/services/covering_http_transport.py") != CANDIDATE_HTTP_PIN:
        raise WitnessFailure("candidate http pin drift")
    if sha256_file(ROOT / "candidate/app/services/covering_joined_https.py") != CANDIDATE_TLS_PIN:
        raise WitnessFailure("candidate tls pin drift")
    if sha256_file(ROOT / "original/app/services/covering_http_transport.py") != ORIGINAL_HTTP_PIN:
        raise WitnessFailure("original http pin drift")
    if sha256_file(ROOT / "original/app/services/covering_joined_https.py") != ORIGINAL_TLS_PIN:
        raise WitnessFailure("original tls pin drift")
    if sha256_file(ROOT / "candidate/app/services/covering_provider_context.py") != PROVIDER_CTX_PIN:
        raise WitnessFailure("provider context must be unchanged")
    if sha256_file(ROOT / "original/app/services/covering_provider_context.py") != PROVIDER_CTX_PIN:
        raise WitnessFailure("provider context original drift")


def build_runtime(version: str) -> dict[str, Any]:
    for name in (
        "app",
        "app.services",
        "app.services.covering_transport_policy",
        "app.services.covering_target_transaction",
        "app.services.covering_joined_https",
        "app.services.covering_http_transport",
        "app.services.covering_provider_context",
        "app.services.google_calendar",
        "app.api",
        "app.api.errors",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    policy_ns = new_module_namespace(f"policy_{version}")
    policy_ns.update(
        {
            "dataclass": __import__("dataclasses").dataclass,
            "ip_address": ip_address,
            "unquote": unquote,
            "urlsplit": urlsplit,
            "CoveringDeadlineExceeded": type("CoveringDeadlineExceeded", (Exception,), {}),
            "__annotations__": {},
        }
    )
    services = ROOT / version / "app" / "services"
    policy_src = services / "covering_transport_policy.py"
    policy_tree = ast.parse(policy_src.read_bytes().decode("utf-8"))
    policy_names = [
        n.name for n in policy_tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
    ]
    policy_names.append("_PATH_INSPECT_STEP_BUDGET")
    policy = extract_symbols(policy_src, policy_names, policy_ns)

    txn_ns = new_module_namespace(f"txn_{version}")
    txn = extract_symbols(
        services / "covering_target_transaction.py",
        ["CoveringRootOutcomeUnknown"],
        txn_ns,
    )
    unknown_cls = txn["CoveringRootOutcomeUnknown"]
    policy["CoveringRootOutcomeUnknown"] = unknown_cls
    policy_ns["CoveringRootOutcomeUnknown"] = unknown_cls

    httpx_mod = types.ModuleType("httpx")
    httpx_mod.Request = FakeHttpxRequest  # type: ignore[attr-defined]
    httpx_mod.Response = FakeHttpxResponse  # type: ignore[attr-defined]
    httpx_mod.Client = lambda **kw: (_ for _ in ()).throw(AssertionError("ambient client"))  # type: ignore[attr-defined]
    sys.modules["httpx"] = httpx_mod

    join_ns = new_module_namespace(f"join_{version}")
    # Extract real JoinedTLS for TLS-option control; CoveringHTTP uses factory override.
    join_ns.update(
        {
            "errno": __import__("errno"),
            "ipaddress": __import__("ipaddress"),
            "selectors": __import__("selectors"),
            "socket": __import__("socket"),
            "ssl": ssl,
            "get_ident": __import__("threading").get_ident,
            "CoveringTransportRefused": policy["CoveringTransportRefused"],
            "CoveringRootOutcomeUnknown": unknown_cls,
        }
    )
    join = extract_symbols(services / "covering_joined_https.py", ["JoinedTLS"], join_ns)

    http_ns = new_module_namespace(f"http_{version}")
    http_pkg = sys.modules.setdefault("http", types.ModuleType("http"))
    http_pkg.client = http.client  # type: ignore[attr-defined]
    http_ns.update(
        {
            "io": io,
            "json": json,
            "re": __import__("re"),
            "http": http_pkg,
            "httpx": httpx_mod,
            "urlencode": urllib.parse.urlencode,
            "CoveringTransportRefused": policy["CoveringTransportRefused"],
            "CoveringReauthorizationRequired": policy["CoveringReauthorizationRequired"],
            "CoveringRootOutcomeUnknown": unknown_cls,
            "admit_covering_path": policy["admit_covering_path"],
            "JoinedTLS": join["JoinedTLS"],
        }
    )
    http_names = [
        "_Reader",
        "_SocketView",
        "_GuardedHTTPResponse",
        "_framing_header_occurrences",
        "_admit_framing_headers",
        "_admit_fixed_length_complete",
        "_ows_strip",
        "_CL_DECIMAL",
        "_CHUNK_SIZE_HEX",
        "_OWS_CHARS",
        "CoveringHTTP",
    ]
    # Original lacks guarded symbols — extract only what exists.
    raw_http = (services / "covering_http_transport.py").read_bytes().decode("utf-8")
    tree_http = ast.parse(raw_http)
    present = set()
    for node in tree_http.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            present.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    present.add(t.id)
    extract_names = [n for n in http_names if n in present]
    if "CoveringHTTP" not in extract_names or "_Reader" not in extract_names:
        raise WitnessFailure("CoveringHTTP/_Reader required")
    http_extract = extract_symbols(services / "covering_http_transport.py", extract_names, http_ns)

    ctx_ns = new_module_namespace(f"ctx_{version}")
    ctx_ns.update(
        {
            "contextmanager": contextmanager,
            "ContextVar": __import__("contextvars").ContextVar,
            "httpx": httpx_mod,
            "urlsplit": urlsplit,
            "CoveringTransportRefused": policy["CoveringTransportRefused"],
            "admit_covering_path": policy["admit_covering_path"],
        }
    )
    raw_ctx = (services / "covering_provider_context.py").read_bytes()
    tree_ctx = ast.parse(raw_ctx.decode("utf-8"))
    for node in tree_ctx.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_current":
                    exec(compile(ast.Module(body=[node], type_ignores=[]), "ctx", "exec"), ctx_ns)
    ctx = extract_symbols(
        services / "covering_provider_context.py",
        ["covering_provider_transport", "_CoveringClient", "calendar_client"],
        ctx_ns,
    )

    google_ns = new_module_namespace(f"google_{version}")
    errors_ns = new_module_namespace("app.api.errors")
    errors_ns["ApiError"] = FakeApiError
    google_ns.update(
        {
            "dataclass": __import__("dataclasses").dataclass,
            "Any": Any,
            "calendar_client": ctx["calendar_client"],
            "ApiError": FakeApiError,
            "__annotations__": {},
        }
    )
    google = extract_symbols(
        services / "google_calendar.py",
        ["refresh_access_token"],
        google_ns,
    )

    return {
        "policy": policy,
        "http": http_extract,
        "http_ns": http_ns,
        "join": join,
        "ctx": ctx,
        "google": google,
        "unknown": unknown_cls,
        "version": version,
    }


class FakeTransport:
    def __init__(
        self,
        wire: bytes,
        probe: CloseProbe,
        *,
        stall: bool = False,
        response_close_error: BaseException | None = None,
        transport_close_error: BaseException | None = None,
        sent_before_fail: bool = True,
    ):
        self.wire = wire
        self.pos = 0
        self.sent = False
        self.probe = probe
        self.stall = stall
        self.response_close_error = response_close_error
        self.transport_close_error = transport_close_error
        self.sent_before_fail = sent_before_fail
        self.closed = False

    def open(self) -> None:
        return None

    def send(self, _wire: bytes) -> None:
        if self.sent_before_fail:
            self.sent = True

    def receive(self, n: int) -> bytes:
        self.probe.receive_calls += 1
        self.probe.receive_amts.append(n)
        if n < 0:
            raise WitnessFailure(f"negative receive requested:{n}")
        if self.stall:
            return b""
        chunk = self.wire[self.pos : self.pos + n]
        self.pos += len(chunk)
        self.probe.transport_bytes_received += len(chunk)
        return chunk

    def close(self) -> None:
        self.probe.transport_close_calls += 1
        if self.transport_close_error is not None:
            raise self.transport_close_error


class ClosingResponseProxy:
    """Wraps real response to inject close failures while preserving reads."""

    def __init__(self, response: Any, probe: CloseProbe, close_error: BaseException | None):
        self._response = response
        self._probe = probe
        self._close_error = close_error

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)

    def read(self, amt: int | None = None) -> bytes:
        return self._response.read(amt)

    def begin(self) -> Any:
        return self._response.begin()

    def getheader(self, *a: Any, **k: Any) -> Any:
        return self._response.getheader(*a, **k)

    def getheaders(self) -> Any:
        return self._response.getheaders()

    def close(self) -> None:
        self._probe.response_close_calls += 1
        if self._close_error is not None:
            raise self._close_error
        return self._response.close()


def routes_for_purpose(policy: dict[str, Any], purpose: str) -> tuple:
    HTTPSPeer = policy["HTTPSPeer"]
    if purpose == "oauth":
        peer = HTTPSPeer(G_GAUTH, G_GADDR, 443, CA_FILE)
        return ((peer, TOKEN_EXACT, "oauth"),)
    if purpose == "identity":
        peer = HTTPSPeer(G_HOST, G_ADDR, 443, CA_FILE)
        return ((peer, "/v1.0/me", "identity"),)
    peer = HTTPSPeer(G_HOST, G_ADDR, 443, CA_FILE)
    return ((peer, EVENT_PREFIX, "event"),)


def request_args_for_purpose(purpose: str) -> tuple[str, str, dict[str, str] | None]:
    if purpose == "oauth":
        return "POST", GOOGLE_TOKEN_URL, {"grant_type": "refresh_token"}
    if purpose == "identity":
        return "GET", f"https://{G_HOST}/v1.0/me", None
    return "GET", f"https://{G_HOST}{EVENT_PREFIX}primary/events", None


def classify(exc: BaseException, policy: dict[str, Any]) -> str:
    if isinstance(exc, policy["CoveringReauthorizationRequired"]):
        return "OBSERVED_SUCCESS"
    if isinstance(exc, policy["CoveringRootOutcomeUnknown"]):
        return "OBSERVED_UNKNOWN"
    if isinstance(exc, policy["CoveringTransportRefused"]):
        return "OBSERVED_REFUSE"
    if isinstance(exc, json.JSONDecodeError):
        return "OBSERVED_PARSER_ERROR"
    if isinstance(exc, http.client.HTTPException):
        return "OBSERVED_PARSER_ERROR"
    if isinstance(exc, UnicodeDecodeError):
        return "OBSERVED_PARSER_ERROR"
    if isinstance(exc, WitnessFailure):
        raise exc
    return "OBSERVED_UNEXPECTED"


@contextmanager
def instrument_close(probe: CloseProbe):
    orig_close = http.client.HTTPResponse.close

    def patched_close(self: http.client.HTTPResponse) -> Any:
        probe.response_close_calls += 1
        return orig_close(self)

    http.client.HTTPResponse.close = patched_close  # type: ignore[method-assign]
    try:
        yield
    finally:
        http.client.HTTPResponse.close = orig_close  # type: ignore[method-assign]


def run_http_catch(
    env: dict[str, Any],
    *,
    wire_bytes: bytes,
    purpose: str,
    probe: CloseProbe | None = None,
    stall: bool = False,
    response_close_error: BaseException | None = None,
    transport_close_error: BaseException | None = None,
    limits: Any = None,
    wrap_response_close: bool = False,
) -> dict[str, Any]:
    probe = probe or CloseProbe()
    policy = env["policy"]
    CoveringHTTP = env["http"]["CoveringHTTP"]
    counter = policy["ProviderCounter"](
        limits or policy["approved_provider_limits"](), lambda: 240.0
    )
    routes = routes_for_purpose(policy, purpose)
    method, url, data = request_args_for_purpose(purpose)
    box: list[FakeTransport] = []

    def factory(_peer, _rem):
        t = FakeTransport(
            wire_bytes,
            probe,
            stall=stall,
            response_close_error=response_close_error,
            transport_close_error=transport_close_error,
        )
        box.append(t)
        return t

    http_obj = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    observed = "OBSERVED_UNEXPECTED"
    exc_type = None
    retirement = None
    http_status = None
    body_len = 0
    orig_close = http.client.HTTPResponse.close

    def counting_close(self):  # type: ignore[no-untyped-def]
        probe.response_close_calls += 1
        return orig_close(self)

    def raising_close(self):  # type: ignore[no-untyped-def]
        probe.response_close_calls += 1
        if response_close_error is not None:
            raise response_close_error
        return orig_close(self)

    http.client.HTTPResponse.close = (  # type: ignore[method-assign]
        raising_close if wrap_response_close and response_close_error is not None else counting_close
    )
    try:
        try:
            result = http_obj.request(method, url, purpose=purpose, data=data)
            observed = "OBSERVED_SUCCESS"
            http_status = getattr(result, "status_code", None)
            body_len = len(getattr(result, "content", b"") or b"")
        except BaseException as exc:
            if isinstance(exc, WitnessFailure):
                raise
            observed = classify(exc, policy)
            exc_type = type(exc).__name__
            if observed == "OBSERVED_UNEXPECTED":
                raise
            if isinstance(exc, policy["CoveringRootOutcomeUnknown"]):
                retirement = {
                    "primary": type(getattr(exc, "primary", None)).__name__
                    if getattr(exc, "primary", None) is not None
                    else None,
                    "response_close": type(getattr(exc, "response_close", None)).__name__
                    if getattr(exc, "response_close", None) is not None
                    else None,
                    "transport_close": type(getattr(exc, "transport_close", None)).__name__
                    if getattr(exc, "transport_close", None) is not None
                    else None,
                }
    finally:
        http.client.HTTPResponse.close = orig_close  # type: ignore[method-assign]

    transport = box[0] if box else None
    return {
        "purpose": purpose,
        "wire_sha256": sha256_bytes(wire_bytes),
        "wire_byte_length": len(wire_bytes),
        "tls_close_notify_proven": False,
        "byte_fake_eof_only": True,
        "observed_outcome": observed,
        "exception_type": exc_type,
        "http_status": http_status,
        "body_bytes_collected": body_len,
        "response_close_calls": probe.response_close_calls,
        "transport_close_calls": probe.transport_close_calls,
        "transport_bytes_received": probe.transport_bytes_received,
        "transport_sent_observed": bool(transport.sent) if transport else False,
        "receive_calls": probe.receive_calls,
        "negative_receive_requested": any(a < 0 for a in probe.receive_amts),
        "retirement": retirement,
        "counter_items": counter.items,
        "counter_bytes": counter.bytes,
        "counter_stopped": counter.stopped,
    }


def load_wire(wire_id: str) -> bytes:
    path = WIRE_DIR / f"{wire_id}.wire"
    # CALLER controls reuse base wires
    aliases = {
        "CALLER-CLIENT-EVENT-F01": "F01",
        "CALLER-CLIENT-OAUTH-F04": "F04-oauth",
        "CALLER-CLIENT-OAUTH-F05b": "F05b-oauth",
        "CALLER-REFRESH-TOKEN-F04": "F04-oauth",
    }
    if wire_id in aliases:
        path = WIRE_DIR / f"{aliases[wire_id]}.wire"
    if not path.is_file():
        # supplemental IDs use their own files
        path = WIRE_DIR / f"{wire_id}.wire"
    if not path.is_file():
        raise WitnessFailure(f"missing wire:{wire_id}")
    return path.read_bytes()


def purpose_for(wire_id: str, expected_row: dict[str, Any]) -> str:
    if "purpose" in expected_row:
        return expected_row["purpose"]
    if "oauth" in wire_id.lower() or wire_id.startswith("F03") or wire_id.startswith("F04") or wire_id.startswith("F05"):
        if "EVENT" in wire_id:
            return "event"
        if "IDENTITY" in wire_id:
            return "identity"
        return "oauth"
    if "IDENTITY" in wire_id:
        return "identity"
    return "event"


def assert_match(control_id: str, observed: dict[str, Any], expected_row: dict[str, Any]) -> None:
    pred = expected_row.get("exact_predicate")
    if not isinstance(pred, dict):
        # Flat candidate predicate (wire rows): only measured runtime fields.
        # policy_pending is frozen accepted-policy metadata on EXPECTED rows /
        # emit_wire_candidate output — not present on run_http_catch cand, so it
        # must not enter this runtime observation whitelist.
        pred = {
            k: v
            for k, v in expected_row.items()
            if k
            in {
                "observed_outcome",
                "exception_type",
                "response_close_calls",
                "transport_close_calls",
                "negative_receive_requested",
                "three_roles_present",
                "primary_role",
                "response_close_role",
                "transport_close_role",
                "suppress_ragged_eofs_forwarded_false",
                "wrap_exception_propagated",
                "native_tls_proven",
                "byte_excess_outcome",
                "byte_excess_exception",
                "item_excess_outcome",
                "item_excess_exception",
                "transport_sent_observed",
                "lineage",
            }
        }
    for key, want in pred.items():
        got = observed.get(key)
        if got != want:
            raise WitnessFailure(
                f"oracle mismatch:{control_id}:{key}:want={want!r}:got={got!r}"
            )


def observation_oracle(row: dict[str, Any]) -> dict[str, Any]:
    """Launcher exact_predicate nests specialized claims under observation."""
    pred = row.get("exact_predicate")
    if not isinstance(pred, dict) or not isinstance(pred.get("observation"), dict):
        raise WitnessFailure("missing_observation_exact_predicate")
    return pred["observation"]


def project_claimed(observed: dict[str, Any], claimed: dict[str, Any]) -> dict[str, Any]:
    """Emit only fields claimed by exact_predicate (exact launcher match)."""
    out: dict[str, Any] = {}
    for key in claimed:
        if key not in observed:
            raise WitnessFailure(f"missing_claimed_field:{key}")
        out[key] = observed[key]
    return out


def emit_wire_candidate(cand: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Stable candidate observation shape for launcher exact_predicate.candidate.

    Runtime outcome/exception/close counters come from measured cand.
    policy_pending is frozen accepted-policy metadata copied from the EXPECTED
    row (not asserted against cand; absent from run_http_catch observation).
    """
    return {
        "observed_outcome": cand["observed_outcome"],
        "exception_type": cand["exception_type"],
        "response_close_calls": cand["response_close_calls"],
        "transport_close_calls": cand["transport_close_calls"],
        "negative_receive_requested": cand["negative_receive_requested"],
        "policy_pending": row["candidate"].get("policy_pending", False),
    }


def tls_option_controls(env: dict[str, Any]) -> dict[str, Any]:
    """Fake wrap_socket option forwarding + exception propagation (not native TLS)."""
    JoinedTLS = env["join"]["JoinedTLS"]
    policy = env["policy"]
    peer = policy["HTTPSPeer"](G_HOST, G_ADDR, 443, CA_FILE)
    recorded: dict[str, Any] = {}

    class FakeSock:
        def __init__(self):
            self.blocking = True
            self.closed = False

        def setblocking(self, flag):
            self.blocking = flag

        def connect_ex(self, addr):
            return 0

        def getsockopt(self, *a):
            return 0

        def close(self):
            self.closed = True

        def do_handshake(self):
            return None

    class FakeCtx:
        def __init__(self):
            self.check_hostname = False
            self.verify_mode = None
            self.wrap_kwargs = None
            self.raise_on_wrap = None

        def wrap_socket(self, sock, **kwargs):
            self.wrap_kwargs = dict(kwargs)
            recorded["wrap_kwargs"] = dict(kwargs)
            if self.raise_on_wrap is not None:
                raise self.raise_on_wrap
            out = FakeSock()
            out.do_handshake = lambda: None
            return out

    # Patch ssl.create_default_context and socket.socket inside join module namespace
    join_mod_name = [k for k in sys.modules if k.startswith("join_")][-1]
    join_mod = sys.modules[join_mod_name]
    fake_ctx = FakeCtx()
    orig_cdc = join_mod.ssl.create_default_context
    orig_socket = join_mod.socket.socket

    def fake_cdc(*, cafile=None):
        return fake_ctx

    def fake_socket(*a, **k):
        return FakeSock()

    join_mod.ssl.create_default_context = fake_cdc
    join_mod.socket.socket = fake_socket
    try:
        tls = JoinedTLS(peer, lambda: 30.0)
        tls.open()
        forward_ok = recorded.get("wrap_kwargs", {}).get("suppress_ragged_eofs") is False
        # exception propagation
        fake_ctx.raise_on_wrap = OSError("wrap boom")
        tls2 = JoinedTLS(peer, lambda: 30.0)
        propagated = False
        try:
            tls2.open()
        except OSError as exc:
            propagated = str(exc) == "wrap boom"
        except Exception as exc:
            # open() may wrap into UNKNOWN on cleanup failure; still not silence
            propagated = type(exc).__name__ in ("OSError", "CoveringRootOutcomeUnknown")
    finally:
        join_mod.ssl.create_default_context = orig_cdc
        join_mod.socket.socket = orig_socket
    return {
        "suppress_ragged_eofs_forwarded_false": forward_ok,
        "wrap_exception_propagated": propagated,
        "native_tls_proven": False,
    }


def cleanup_combo(env: dict[str, Any], wire_id: str, combo: str) -> dict[str, Any]:
    """Reuse T07 five cleanup combinations with lineage labels (C-R02..C-R06)."""
    wire = load_wire(wire_id)
    class FakeResponseCloseError(Exception):
        pass

    class FakeTransportCloseError(Exception):
        pass

    kwargs: dict[str, Any] = {"wire_bytes": wire, "purpose": "event"}
    if combo == "C-R02":
        kwargs["response_close_error"] = FakeResponseCloseError()
        kwargs["wrap_response_close"] = True
    elif combo == "C-R03":
        kwargs["transport_close_error"] = FakeTransportCloseError()
    elif combo == "C-R04":
        kwargs["wire_bytes"] = load_wire("F12a-INVALID-JSON-EVENT")
        kwargs["response_close_error"] = FakeResponseCloseError()
        kwargs["wrap_response_close"] = True
    elif combo == "C-R05":
        kwargs["wire_bytes"] = load_wire("F12a-INVALID-JSON-EVENT")
        kwargs["transport_close_error"] = FakeTransportCloseError()
    elif combo == "C-R06":
        kwargs["response_close_error"] = FakeResponseCloseError()
        kwargs["transport_close_error"] = FakeTransportCloseError()
        kwargs["wrap_response_close"] = True
    else:
        raise WitnessFailure(f"unknown cleanup combo:{combo}")
    obs = run_http_catch(env, **kwargs)
    obs["cleanup_combo"] = combo
    obs["lineage"] = "T07-fake-v2 C-R02..C-R06"
    return obs


def excess_controls(env: dict[str, Any]) -> dict[str, Any]:
    """Item/byte excess inside an already-admitted response (not new-admission equality)."""
    policy = env["policy"]
    # Byte excess: tiny response_bytes limit; complete F01 body still charges via _Reader
    limits_bytes = policy["ProviderLimits"](20, 10, 10000, 8)
    probe_b = CloseProbe()
    byte_obs = run_http_catch(
        env,
        wire_bytes=load_wire("F01"),
        purpose="event",
        probe=probe_b,
        limits=limits_bytes,
    )
    # Item excess: admitted response with oversized items list
    body = json.dumps({"items": [{"id": str(i)} for i in range(5)]}, separators=(",", ":")).encode()
    wire = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
        + str(len(body)).encode("ascii")
        + b"\r\nContent-Encoding: identity\r\nConnection: close\r\n\r\n"
        + body
    )
    limits_items = policy["ProviderLimits"](20, 10, 3, 16 * 1024 * 1024)
    item_obs = run_http_catch(
        env, wire_bytes=wire, purpose="event", probe=CloseProbe(), limits=limits_items
    )
    return {
        "byte_excess_outcome": byte_obs["observed_outcome"],
        "byte_excess_exception": byte_obs["exception_type"],
        "item_excess_outcome": item_obs["observed_outcome"],
        "item_excess_exception": item_obs["exception_type"],
    }


def active_primary_both_closes(env: dict[str, Any]) -> dict[str, Any]:
    """Active framing primary + BOTH distinct close failures (3 roles preserved)."""

    class FakeResponseCloseError(Exception):
        pass

    class FakeTransportCloseError(Exception):
        pass

    # Use short-body F02 so candidate raises framing IncompleteRead as primary,
    # then both closes fail → UNKNOWN with primary + both cleanup objects.
    obs = run_http_catch(
        env,
        wire_bytes=load_wire("F02"),
        purpose="event",
        response_close_error=FakeResponseCloseError(),
        transport_close_error=FakeTransportCloseError(),
        wrap_response_close=True,
    )
    ret = obs.get("retirement") or {}
    return {
        "observed_outcome": obs["observed_outcome"],
        "primary_role": ret.get("primary"),
        "response_close_role": ret.get("response_close"),
        "transport_close_role": ret.get("transport_close"),
        "three_roles_present": bool(
            ret.get("primary") and ret.get("response_close") and ret.get("transport_close")
        ),
    }


def oauth_unknown_owned_retirement(env: dict[str, Any]) -> dict[str, Any]:
    """After-send OAuth UNKNOWN with owned retirement (transport close fail)."""

    class FakeTransportCloseError(Exception):
        pass

    obs = run_http_catch(
        env,
        wire_bytes=load_wire("F03-oauth"),
        purpose="oauth",
        transport_close_error=FakeTransportCloseError(),
    )
    return {
        "observed_outcome": obs["observed_outcome"],
        "exception_type": obs["exception_type"],
        "retirement": obs.get("retirement"),
        "transport_sent_observed": obs.get("transport_sent_observed"),
    }


def main() -> int:
    if RESULT.exists():
        raise WitnessFailure("preexisting result")
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        raise WitnessFailure("isolation")
    # Immutable T05 evidence pins (byte-identical reuse).
    if sha256_file(HERE / "FAKE-T05-RESULT-IMMUTABLE.json") != T05_RESULT_PIN:
        raise WitnessFailure("T05 result pin mismatch")
    if sha256_file(HERE / "EXPECTED-ORIGINAL-T05-IMMUTABLE.json") != T05_EXPECTED_PIN:
        raise WitnessFailure("T05 expected pin mismatch")
    host_client = Path(r"C:\Users\trish\AppData\Local\Programs\Python\Python311\Lib\http\client.py")
    if sha256_file(host_client) != HOST_HTTP_CLIENT_PIN:
        raise WitnessFailure("host http.client pin mismatch")

    manifest = json.loads(MANIFEST.read_bytes().decode("utf-8"))
    expected = json.loads(EXPECTED.read_bytes().decode("utf-8"))
    verify_sources(manifest)

    envs = {"original": build_runtime("original"), "candidate": build_runtime("candidate")}
    # Candidate must expose guarded symbols.
    for name in (
        "_GuardedHTTPResponse",
        "_admit_framing_headers",
        "_admit_fixed_length_complete",
        "_CHUNK_SIZE_HEX",
    ):
        if name not in envs["candidate"]["http"]:
            raise WitnessFailure(f"candidate missing {name}")

    observations: dict[str, Any] = {}
    for cid in expected["wire_ids_in_order"]:
        row = expected["inputs"][cid]
        kind = row.get("kind", "wire")
        if kind == "wire":
            purpose = purpose_for(cid, row)
            # CALLER-* aliases resolve inside load_wire; path remains direct CoveringHTTP.
            wire_bytes = load_wire(cid)
            cand = run_http_catch(
                envs["candidate"],
                wire_bytes=wire_bytes,
                purpose=purpose,
                stall=(cid == "CD-DEADLINE"),
            )
            # Internal oracle uses flat candidate fields; launcher uses exact_predicate.
            assert_match(cid + "/candidate", cand, row["candidate"])
            cand_emit = emit_wire_candidate(cand, row)
            if row.get("compare_original_to_t05"):
                t05 = json.loads((HERE / "EXPECTED-ORIGINAL-T05-IMMUTABLE.json").read_bytes())
                t05_row = t05["inputs"].get(cid)
                if t05_row is None:
                    raise WitnessFailure(f"missing T05 original:{cid}")
                # Pin immutable original evidence; do not re-score originals as new PASS.
                observations[cid] = {
                    "observed_outcome": "PASS",
                    "original_evidence": "T05-IMMUTABLE",
                    "t05_predicted": t05_row["predicted_outcome"],
                    "candidate": cand_emit,
                }
            else:
                observations[cid] = {
                    "observed_outcome": "PASS",
                    "candidate": cand_emit,
                }
        elif kind == "tls_option":
            obs = tls_option_controls(envs["candidate"])
            claimed = observation_oracle(row)
            assert_match(cid, obs, {"exact_predicate": claimed})
            observations[cid] = {
                "observed_outcome": "PASS",
                "observation": project_claimed(obs, claimed),
            }
        elif kind == "cleanup_combo":
            obs = cleanup_combo(envs["candidate"], row["wire_id"], row["combo"])
            claimed = observation_oracle(row)
            assert_match(cid, obs, {"exact_predicate": claimed})
            observations[cid] = {
                "observed_outcome": "PASS",
                "observation": project_claimed(obs, claimed),
            }
        elif kind == "excess":
            obs = excess_controls(envs["candidate"])
            claimed = observation_oracle(row)
            assert_match(cid, obs, {"exact_predicate": claimed})
            observations[cid] = {
                "observed_outcome": "PASS",
                "observation": project_claimed(obs, claimed),
            }
        elif kind == "primary_both_closes":
            obs = active_primary_both_closes(envs["candidate"])
            claimed = observation_oracle(row)
            assert_match(cid, obs, {"exact_predicate": claimed})
            observations[cid] = {
                "observed_outcome": "PASS",
                "observation": project_claimed(obs, claimed),
            }
        elif kind == "oauth_retirement":
            obs = oauth_unknown_owned_retirement(envs["candidate"])
            claimed = observation_oracle(row)
            assert_match(cid, obs, {"exact_predicate": claimed})
            observations[cid] = {
                "observed_outcome": "PASS",
                "observation": project_claimed(obs, claimed),
            }
        elif kind == "inventory":
            observations[cid] = {
                "observed_outcome": "PASS",
                "changed_files": [
                    "app/services/covering_http_transport.py",
                    "app/services/covering_joined_https.py",
                ],
                "source_count": 468,
                "dex_p1_p2_p3_addressed": True,
                "provisional_review_sha256": "87E24D1AE390CFDE11CD31E88F6F2D8E89777DE49FFB3EFCF78997ABC9CB30B9",
                "staged_read_hash_B04B3D6B_superseded_by": CANDIDATE_HTTP_PIN,
                "header_policy_approval_sha256": HEADER_POLICY_APPROVAL_PIN,
                "header_policy_decision_sha256": HEADER_POLICY_DECISION_PIN,
            }
        else:
            raise WitnessFailure(f"unknown kind:{kind}")

    verify_sources(manifest)
    payload = {
        "status": "PASS",
        "class": "FAKE-FRAMING-ACK",
        "executed": True,
        "preparation_executed": False,
        "source_hashes_verified": True,
        "wire_ids_in_order": list(observations),
        "inputs": observations,
        "limits": "byte fakes; no native TLS/provider proof",
        "policy_compatibility": "ACCEPTED_HEADER_COMPATIBILITY_POLICY",
        "header_policy_decision_sha256": HEADER_POLICY_DECISION_PIN,
        "header_policy_approval_sha256": HEADER_POLICY_APPROVAL_PIN,
        "dex_provisional_p1_p2_p3": "addressed_in_candidate_29CBD53C",
        "native_tls_orderly_vs_abrupt": "unproved",
    }
    raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_RESULT:
        raise WitnessFailure("result cap")
    with RESULT.open("xb") as stream:
        stream.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
