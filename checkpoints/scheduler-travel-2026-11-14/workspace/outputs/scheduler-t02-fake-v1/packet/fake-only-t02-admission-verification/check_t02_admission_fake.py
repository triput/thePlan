#!/usr/bin/env python3
"""Fake-only T02 provider-limit admission verification (AUTHORING ONLY — not executed).

AST-extracts original (base) and candidate covering transport/admission sources from
frozen packet bytes. Exercises named witnesses, positive control, mutation
controls, and counter/token controls under fully fake dependencies.

CORRECTED1 (Dex T02-Preparation-v1-Independent-Review REVISE): mutations are
built from pinned extracted candidate definitions (admit/check/stopped/
drainage only); W-TOKEN uses a deliberate downstream sentinel; counter identity
and ordered results observe CoveringReleasePlan.for_request composition and/or
covering_domain_dispatch ordered path with fully fake deps; approved item/byte
N-1/equality controls added; emitted inventory order enforced before PASS.

CORRECTED2 (Dex mid-flight provisional notes A–D / Slack p1794383509,
p1794383631, p1794383742, p1794383896 + T02-Corrected1-Provisional-Review.md):
W-TOKEN/M-C use instrumented db.info.get("covering_token_terminal") sentinel
immediately downstream of preflight (candidate at equality → zero lookups);
W-COUNTER-IDENTITY uses approved 16 MiB byte budget + composed wiring proof
(domain_ports transport.counter identity + second for_request freshness);
W-ORDERED-RESULTS budget exposes check_admission; exact cardinality/order +
token/run_target counts; item/byte equality ALL-PURPOSES use a fresh counter
per purpose with stopped=False asserted before each call.

No app imports, no real sockets/providers/credentials/TLS/DB, no pytest.
Instrument fake transport construct/open/send/close separately.
launch_ready remains false; this file is held pending a later execution card.
"""
from __future__ import annotations

import ast
import hashlib
import http.client
import io
import json
import sys
import types
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAYLOAD = ROOT / "payload"
CANDIDATE_API = PAYLOAD / "workspace" / "apps" / "api"
BASES = PAYLOAD / "bases"
MANIFEST_PATH = HERE / "INPUT-MANIFEST.json"
EXPECTED_PATH = HERE / "EXPECTED-OUTPUT.json"
RESULT_PATH = HERE / "FAKE-T02-RESULT.json"

PASS_RESULTS = {"PASS", "REFUSE", "PASS_WITNESS"}

# Approved ceilings (Trish 2026-11-09) — boundary cases must use these.
APPROVED_EVENT_PAGES = 20
APPROVED_IDENTITY_PAGES = 10
APPROVED_ITEMS = 10_000
APPROVED_RESPONSE_BYTES = 16 * 1024 * 1024

# Convenience limits for unit-shaped controls ONLY — labeled; not full
# integration/transport proof substitutes.
CONVENIENCE_EVENT_PAGES = 2
CONVENIENCE_IDENTITY_PAGES = 1
CONVENIENCE_ITEMS = 3
CONVENIENCE_RESPONSE_BYTES = 64


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
    """Instrument construct/open/send/close separately (no real sockets)."""

    constructs: int = 0
    opens: int = 0
    sends: int = 0
    closes: int = 0
    receives: int = 0

    def reset(self) -> None:
        self.constructs = self.opens = self.sends = self.closes = self.receives = 0


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_bytes().decode("utf-8"))


def load_expected() -> dict[str, Any]:
    return json.loads(EXPECTED_PATH.read_bytes().decode("utf-8"))


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


def resolve_source(rel: str) -> Path:
    rel = rel.replace("\\", "/")
    if rel.startswith("bases/"):
        return BASES / rel[len("bases/") :]
    if rel.startswith("workspace/"):
        return PAYLOAD / rel
    if rel.startswith("payload/"):
        return ROOT / rel
    return PAYLOAD / rel


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


def _find_nested_function(fn: ast.FunctionDef, name: str) -> ast.FunctionDef:
    for node in ast.walk(fn):
        if isinstance(node, ast.FunctionDef) and node.name == name and node is not fn:
            return node
    raise ControlFailure(f"missing nested function {name!r} for mutation")


def compile_mutated_method(
    method_ast: ast.FunctionDef,
    *,
    filename: str,
    bind_globals: dict[str, Any],
) -> Callable:
    """Compile a (possibly mutated) function AST against coherent registered globals."""
    module_ast = ast.Module(body=[method_ast], type_ignores=[])
    ast.fix_missing_locations(module_ast)
    code = compile(module_ast, filename, "exec")
    local_ns: dict[str, Any] = {}
    exec(code, bind_globals, local_ns)
    name = method_ast.name
    if name not in local_ns:
        raise ControlFailure(f"mutated method {name!r} did not bind")
    return local_ns[name]


def mutate_attr_call(method_ast: ast.FunctionDef, *, from_attr: str, to_attr: str, expected: int) -> None:
    """Rename Attribute.attr on Call funcs (e.g. self.counter.admit -> check)."""
    hits = 0
    for node in ast.walk(method_ast):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == from_attr:
            func.attr = to_attr
            hits += 1
    if hits != expected:
        raise ControlFailure(
            f"mutation expected {expected} {from_attr!r}-> {to_attr!r} call(s); got {hits}"
        )


def mutate_attribute_name(method_ast: ast.FunctionDef, *, from_attr: str, to_attr: str, expected: int) -> None:
    """Rename Attribute.attr loads (e.g. counter.admission_exhausted -> stopped)."""
    hits = 0
    for node in ast.walk(method_ast):
        if isinstance(node, ast.Attribute) and node.attr == from_attr:
            node.attr = to_attr
            hits += 1
    if hits != expected:
        raise ControlFailure(
            f"mutation expected {expected} attr {from_attr!r}->{to_attr!r}; got {hits}"
        )


class AdmissionPassedSentinel(Exception):
    """Deliberate downstream sentinel past token preflight (harness-only)."""


SENTINEL_LOCATION_DB_INFO_GET = "db.info.get:covering_token_terminal"


class CoveringTokenTerminalInfoSentinel:
    """Instrumented db.info whose .get raises AdmissionPassedSentinel.

    Dex narrow option (CORRECTED2): exact key covering_token_terminal only —
    immediately downstream of admission_exhausted preflight; no ORM/lock path.
    """

    def __init__(self, state: dict[str, Any]):
        self._state = state

    def get(self, key, default=None):
        if key != "covering_token_terminal":
            raise ControlFailure(
                f"token sentinel info.get unexpected key {key!r}; "
                "only covering_token_terminal is instrumented"
            )
        self._state["count"] = int(self._state.get("count", 0)) + 1
        self._state["location"] = SENTINEL_LOCATION_DB_INFO_GET
        raise AdmissionPassedSentinel(
            "original passed admission_exhausted into db.info.get("
            "covering_token_terminal)"
        )


class CoveringTokenTerminalInfoProbe:
    """Records db.info.get lookups; candidate at equality must make zero."""

    def __init__(self, state: dict[str, Any]):
        self._state = state

    def get(self, key, default=None):
        self._state["count"] = int(self._state.get("count", 0)) + 1
        keys = self._state.setdefault("keys", [])
        keys.append(key)
        return default


def install_budget_stub() -> None:
    class CoveringDeadlineExceeded(Exception):
        pass

    mod = types.ModuleType("app.services.covering_request_budget")
    mod.CoveringDeadlineExceeded = CoveringDeadlineExceeded
    for name in (
        "app",
        "app.services",
        "app.services.covering_request_budget",
        "app.services.covering_joined_https",
        "app.services.covering_target_transaction",
        "app.services.covering_transport_policy",
        "app.services.covering_domain_dispatch",
        "app.services.covering_http_dispatch",
        "app.services.covering_release_plan",
        "app.services.covering_http_transport",
        "app.services.covering_domain_adapters",
        "app.services.covering_native_checkout",
        "app.services.covering_native_orm_factory",
        "app.services.covering_refresh_import",
        "app.services.covering_refresh_locks",
        "app.services.covering_provider_context",
        "app.services.agent_auth_context",
        "app.services.agent_credentials",
        "app.models",
        "httpx",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    sys.modules["app.services.covering_request_budget"] = mod


def make_httpx_stub() -> None:
    httpx = sys.modules["httpx"]

    class Request:
        def __init__(self, method: str, url: str) -> None:
            self.method = method
            self.url = url

    class Response:
        def __init__(self, status_code: int, content: bytes, headers=None, request=None) -> None:
            self.status_code = status_code
            self.content = content
            self.headers = headers or {}
            self.request = request

    httpx.Request = Request
    httpx.Response = Response


def make_fake_transport_factory(probe: TransportProbe, body: bytes):
    class FakeTransport:
        def __init__(self, peer, remaining):
            probe.constructs += 1
            self.peer = peer
            self.remaining = remaining
            self.sent = False
            self._buf = body
            self._pos = 0
            self._opened = False
            self._closed = False

        def open(self):
            probe.opens += 1
            self._opened = True

        def send(self, wire: bytes):
            probe.sends += 1
            self.sent = True
            if not isinstance(wire, (bytes, bytearray)):
                raise TypeError("wire must be bytes")

        def receive(self, n: int) -> bytes:
            probe.receives += 1
            chunk = self._buf[self._pos : self._pos + n]
            self._pos += len(chunk)
            return chunk

        def close(self):
            probe.closes += 1
            self._closed = True

    return FakeTransport


def framed_http_json(status: int, obj: dict) -> bytes:
    payload = json.dumps(obj).encode("utf-8")
    head = (
        f"HTTP/1.1 {status} OK\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        f"Content-Encoding: identity\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("ascii")
    return head + payload


def build_policy_module(
    source: Path,
    module_name: str,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    ns = new_module_namespace(
        module_name,
        {
            "dataclass": dataclass,
            # stdlib already imported at top of source; provide names used
        },
    )
    # Provide imports the extracted module body expects as globals when we
    # extract classes only — supply dataclass module pieces + ipaddress helpers.
    import ipaddress
    from urllib.parse import urlsplit

    budget = sys.modules["app.services.covering_request_budget"]
    ns.update(
        {
            "dataclass": dataclass,
            "ip_address": ipaddress.ip_address,
            "urlsplit": urlsplit,
            "CoveringDeadlineExceeded": budget.CoveringDeadlineExceeded,
        }
    )
    extracted = extract_symbols(
        source,
        [
            "CoveringTransportRefused",
            "CoveringReauthorizationRequired",
            "ProviderLimits",
            "HTTPSPeer",
            "ProviderCounter",
            "approved_provider_limits",
        ],
        ns,
        provenance=provenance,
    )
    # Register as covering_transport_policy under a variant-aware alias; callers
    # that need the policy module for CoveringHTTP should point sys.modules.
    return extracted | {"__ns__": ns}


def build_http_module(
    source: Path,
    module_name: str,
    policy_mod_name: str,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    policy = sys.modules[policy_mod_name]
    target_txn = sys.modules["app.services.covering_target_transaction"]
    if not hasattr(target_txn, "CoveringRootOutcomeUnknown"):

        class CoveringRootOutcomeUnknown(Exception):
            pass

        target_txn.CoveringRootOutcomeUnknown = CoveringRootOutcomeUnknown

    joined = sys.modules["app.services.covering_joined_https"]
    # Placeholder; per-request factory overrides in CoveringHTTP.__init__.
    class _JoinedTLSPlaceholder:
        def __init__(self, *a, **k):
            raise RuntimeError("JoinedTLS placeholder must be overridden")

    joined.JoinedTLS = _JoinedTLSPlaceholder

    ns = new_module_namespace(
        module_name,
        {
            "http": http,
            "io": io,
            "json": json,
            "urlencode": urlencode,
            "httpx": sys.modules["httpx"],
            "JoinedTLS": joined.JoinedTLS,
            "CoveringTransportRefused": policy.CoveringTransportRefused,
            "CoveringReauthorizationRequired": policy.CoveringReauthorizationRequired,
            "CoveringRootOutcomeUnknown": target_txn.CoveringRootOutcomeUnknown,
        },
    )
    # http.client needs the http package
    import http as http_pkg

    ns["http"] = http_pkg
    extracted = extract_symbols(
        source,
        ["_Reader", "_SocketView", "CoveringHTTP"],
        ns,
        provenance=provenance,
    )
    return extracted | {"__ns__": ns}


# late import binding for http package name used above
import http  # noqa: E402


def build_domain_token_port(
    source: Path,
    module_name: str,
    policy_mod_name: str,
    provenance: list[ExtractionProvenance],
) -> Callable:
    """Extract make_domain_ports; return only the token callable with fakes."""
    policy = sys.modules[policy_mod_name]

    # Domain-dispatch fakes
    dispatch = sys.modules["app.services.covering_domain_dispatch"]

    @dataclass(frozen=True)
    class TokenReady:
        access_token: str

    @dataclass(frozen=True)
    class TokenRejected:
        code: str

    @dataclass(frozen=True)
    class CoveringDomainPorts:
        token: Callable
        locks: Callable
        apply: Callable

    dispatch.TokenReady = TokenReady
    dispatch.TokenRejected = TokenRejected
    dispatch.CoveringDomainPorts = CoveringDomainPorts

    models = sys.modules["app.models"]

    class CalendarAccount:
        pass

    class CalendarSubscription:
        pass

    models.CalendarAccount = CalendarAccount
    models.CalendarSubscription = CalendarSubscription

    refresh_import = sys.modules["app.services.covering_refresh_import"]
    refresh_import._refresh_provider_access_token = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("token refresh must not run in fake preflight-exhausted path")
    )
    refresh_import.covering_import_eligibility_code = lambda *a, **k: None
    refresh_import.import_covering_subscription_cache = lambda *a, **k: None
    refresh_import.PREFLIGHT_ACCOUNT_DISCONNECTED = "PREFLIGHT_ACCOUNT_DISCONNECTED"

    from contextlib import nullcontext

    locks_mod = sys.modules["app.services.covering_refresh_locks"]
    locks_mod.covering_unit_locks = lambda *a, **k: nullcontext()

    provider_ctx = sys.modules["app.services.covering_provider_context"]

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    provider_ctx.covering_provider_transport = lambda transport: _Ctx()

    target_txn = sys.modules["app.services.covering_target_transaction"]

    class CoveringRootOutcomeUnknown(Exception):
        pass

    class RootOutcome:
        COMMIT_ACKNOWLEDGED = "COMMIT_ACKNOWLEDGED"
        ROLLBACK_ACKNOWLEDGED = "ROLLBACK_ACKNOWLEDGED"

    target_txn.CoveringRootOutcomeUnknown = CoveringRootOutcomeUnknown
    target_txn.RootOutcome = RootOutcome

    agent_auth = sys.modules["app.services.agent_auth_context"]
    agent_auth.resolve_session_agent_credential = lambda db: None
    agent_creds = sys.modules["app.services.agent_credentials"]
    agent_creds.assert_agent_write_still_authorized = lambda *a, **k: None

    ns = new_module_namespace(
        module_name,
        {
            "CalendarAccount": CalendarAccount,
            "CalendarSubscription": CalendarSubscription,
            "CoveringDomainPorts": CoveringDomainPorts,
            "TokenReady": TokenReady,
            "TokenRejected": TokenRejected,
            "_refresh_provider_access_token": refresh_import._refresh_provider_access_token,
            "covering_import_eligibility_code": refresh_import.covering_import_eligibility_code,
            "import_covering_subscription_cache": refresh_import.import_covering_subscription_cache,
            "covering_unit_locks": locks_mod.covering_unit_locks,
            "covering_provider_transport": provider_ctx.covering_provider_transport,
            "CoveringRootOutcomeUnknown": CoveringRootOutcomeUnknown,
            "RootOutcome": RootOutcome,
            "resolve_session_agent_credential": agent_auth.resolve_session_agent_credential,
            "assert_agent_write_still_authorized": agent_creds.assert_agent_write_still_authorized,
            "CoveringReauthorizationRequired": policy.CoveringReauthorizationRequired,
            "PREFLIGHT_ACCOUNT_DISCONNECTED": refresh_import.PREFLIGHT_ACCOUNT_DISCONNECTED,
        },
    )
    extracted = extract_symbols(
        source, ["make_domain_ports"], ns, provenance=provenance
    )
    return extracted["make_domain_ports"]


def build_release_plan_for_request(
    *,
    ProviderCounter: Any,
    approved_provider_limits: Callable,
    CoveringHTTP: Any,
    make_domain_ports: Callable,
    provider_routes: tuple,
    provenance: list[ExtractionProvenance],
    captured_counters: list[Any],
) -> Callable:
    """Extract CoveringReleasePlan.for_request with fully fake native deps.

    Observes request-wide counter identity via the composed ProviderCounter
    shared by CoveringHTTP and domain_ports. Fake transaction acknowledgments
    only — NOT native/DB-ack proof.
    """
    http_dispatch = sys.modules["app.services.covering_http_dispatch"]

    @dataclass(frozen=True)
    class CoveringReleaseBinding:
        parent_factory: Callable
        session_factory: Callable
        domain_ports: Any
        FAKE_TRANSACTION_ACKNOWLEDGMENT: str = "FAKE_NOT_NATIVE_DB_ACK"

    http_dispatch.CoveringReleaseBinding = CoveringReleaseBinding

    class _FakeNativeORMFactories:
        def __init__(self, **kwargs):
            self.parent_factory = lambda: ("FAKE_PARENT_FACTORY", kwargs)
            self.session_factory = lambda: ("FAKE_SESSION_FACTORY", kwargs)

    class _CapturingProviderCounter(ProviderCounter):
        def __init__(self, limits, remaining):
            super().__init__(limits, remaining)
            captured_counters.append(self)

    release_ns = new_module_namespace(
        "fake_t02_cand_covering_release_plan",
        {
            "dataclass": dataclass,
            "Callable": Callable,
            "PostgreSQLPeer": types.SimpleNamespace,
            "NativeORMFactories": _FakeNativeORMFactories,
            "NativeRuntimePins": types.SimpleNamespace,
            "ProviderCounter": _CapturingProviderCounter,
            "approved_provider_limits": approved_provider_limits,
            "CoveringHTTP": CoveringHTTP,
            "make_domain_ports": make_domain_ports,
        },
    )
    # Ensure inner import resolves to our fake binding.
    sys.modules["app.services.covering_http_dispatch"] = http_dispatch
    extracted = extract_symbols(
        CANDIDATE_API / "app/services/covering_release_plan.py",
        ["CoveringReleasePlan"],
        release_ns,
        provenance=provenance,
    )
    Plan = extracted["CoveringReleasePlan"]

    def compose(budget, *, settings=None):
        plan = Plan(
            database_profile=types.SimpleNamespace(
                FAKE_TRANSACTION_ACKNOWLEDGMENT="FAKE_NOT_NATIVE_DB_ACK"
            ),
            password_supplier=lambda: "FAKE_PASSWORD_NOT_USED",
            runtime_pins=types.SimpleNamespace(
                FAKE_TRANSACTION_ACKNOWLEDGMENT="FAKE_NOT_NATIVE_DB_ACK"
            ),
            provider_routes=provider_routes,
            settings=settings,
        )
        return plan.for_request(budget)

    return compose


def build_ordered_domain_dispatch(
    *,
    provenance: list[ExtractionProvenance],
) -> Callable:
    """Extract covering_domain_dispatch.run_bounded_domain with fully fake deps.

    Returns the extracted ordered path. Fake transaction acknowledgments are
    labeled FAKE_NOT_NATIVE_DB_ACK — NOT native/DB-ack proof.
    Boundary note: sqlalchemy/ApiError/schemas/covering_refresh production
    stacks are stubbed here; only run_bounded_domain is AST-extracted.
    """
    dispatch_mod = sys.modules["app.services.covering_domain_dispatch"]

    @dataclass(frozen=True)
    class Identity:
        owner_id: Any
        credential_id: Any

    @dataclass(frozen=True)
    class Target:
        owner_id: Any
        account_id: Any
        subscription_id: Any
        preflight_code: Any

    class CoveringRole:
        AUTH = "AUTH"
        TELEMETRY = "TELEMETRY"
        TOKEN = "TOKEN"
        ASSESSMENT = "ASSESSMENT"

    class ApiError(Exception):
        def __init__(self, status, detail, code):
            self.status = status
            self.detail = detail
            self.code = code

    class CoveringSubscriptionNotEligible(Exception):
        detail = "ineligible"
        code = "INELIGIBLE"

    class CoveringWindowError(Exception):
        detail = "window"
        code = "WINDOW"

    class CoveringDeadlineExceeded(Exception):
        pass

    TokenReady = dispatch_mod.TokenReady
    TokenRejected = dispatch_mod.TokenRejected

    def _classified_role(connector, role, operation):
        error = None
        value = None
        with connector.session_scope(role) as session:
            try:
                value = operation(session)
            except (ApiError, CoveringSubscriptionNotEligible) as exc:
                error = exc
        if error is not None:
            raise error
        return value

    def authenticate(request, session):
        return Identity(uuid.UUID(int=1), None)

    def _guard(session, identity):
        return None

    def _preflight(session, identity, body):
        targets = tuple(
            Target(identity.owner_id, uuid.UUID(int=10 + i), sid, None)
            for i, sid in enumerate(body.subscription_ids)
        )
        return targets, 1

    def _static_preflight_result(*, subscription_id, window, preflight_code):
        return types.SimpleNamespace(
            subscription_id=subscription_id,
            status="preflight",
            phase="preflight",
            preflight_code=preflight_code,
            provider_event_read_attempted=False,
            FAKE_TRANSACTION_ACKNOWLEDGMENT="FAKE_NOT_NATIVE_DB_ACK",
        )

    def _response(body, window, results, revision, final=None, assessment_error=None):
        return types.SimpleNamespace(
            results=list(results),
            revision=revision,
            final=final,
            assessment_error=assessment_error,
            FAKE_TRANSACTION_ACKNOWLEDGMENT="FAKE_NOT_NATIVE_DB_ACK",
        )

    def effective_covering_pull_window(start, end):
        return types.SimpleNamespace(
            effective_start=start,
            effective_end=end,
            widened=False,
            reason=None,
        )

    def _assemble_final_assessment(*a, **k):
        raise CoveringDeadlineExceeded()

    # Populate dispatch module attrs used by extracted body / type checks.
    for name, value in (
        ("Identity", Identity),
        ("Target", Target),
        ("CoveringRole", CoveringRole),
        ("ApiError", ApiError),
        ("CoveringSubscriptionNotEligible", CoveringSubscriptionNotEligible),
        ("CoveringWindowError", CoveringWindowError),
        ("CoveringDeadlineExceeded", CoveringDeadlineExceeded),
        ("_classified_role", _classified_role),
        ("authenticate", authenticate),
        ("_guard", _guard),
        ("_preflight", _preflight),
        ("_static_preflight_result", _static_preflight_result),
        ("_response", _response),
        ("effective_covering_pull_window", effective_covering_pull_window),
        ("_assemble_final_assessment", _assemble_final_assessment),
        ("DEADLINE", "CALENDAR_REFRESH_DEADLINE_EXCEEDED"),
        ("datetime", datetime),
        ("timezone", timezone),
        ("assert_agent_write_still_authorized", lambda *a, **k: None),
        ("text", lambda *a, **k: None),
    ):
        setattr(dispatch_mod, name, value)

    ns = dispatch_mod.__dict__
    # Ensure CoveringRootOutcomeUnknown exists for the except path.
    target_txn = sys.modules["app.services.covering_target_transaction"]
    if not hasattr(target_txn, "CoveringRootOutcomeUnknown"):

        class CoveringRootOutcomeUnknown(Exception):
            pass

        target_txn.CoveringRootOutcomeUnknown = CoveringRootOutcomeUnknown
    ns["CoveringRootOutcomeUnknown"] = target_txn.CoveringRootOutcomeUnknown
    ns["TokenReady"] = TokenReady
    ns["TokenRejected"] = TokenRejected

    extracted = extract_symbols(
        CANDIDATE_API / "app/services/covering_domain_dispatch.py",
        ["run_bounded_domain"],
        ns,
        provenance=provenance,
    )
    return extracted["run_bounded_domain"]


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
    """Compare emitted control_id list DIRECTLY to expected control_ids_in_order.

    Exact sequence required before PASS. Does not reorder/repair results.
    """
    controls_expected = expected.get("controls") or {}
    expected_ids = expected_control_ids(expected)
    actual_ids = [r.control_id for r in results]
    if len(actual_ids) != len(set(actual_ids)):
        dups = sorted({cid for cid in actual_ids if actual_ids.count(cid) > 1})
        raise ControlFailure(f"duplicate control results: {dups}")
    # Exact emitted order vs expected — no membership-only soft match.
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


def peer_and_routes(HTTPSPeer, purpose_prefix="/v1/events"):
    peer = HTTPSPeer("graph.example.test", "192.0.2.1", 443, "synthetic-ca.pem")
    routes = (
        (peer, "/v1/events", "event"),
        (peer, "/v1/me", "identity"),
        (peer, "/oauth2/token", "oauth"),
    )
    return peer, routes


def set_pages(counter, *, event: int, identity: int = 0) -> None:
    counter.pages["event"] = event
    counter.pages["identity"] = identity


def run_controls(bundle: dict[str, Any]) -> list[ControlResult]:
    results: list[ControlResult] = []

    def record(cid: str, result: str, detail: str = "") -> None:
        results.append(ControlResult(cid, result, detail))

    orig_policy = bundle["orig_policy"]
    cand_policy = bundle["cand_policy"]
    OrigHTTP = bundle["OrigHTTP"]
    CandHTTP = bundle["CandHTTP"]
    orig_policy_mod = bundle["orig_policy_mod"]
    cand_policy_mod = bundle["cand_policy_mod"]
    make_token_orig = bundle["make_token_orig"]
    make_token_cand = bundle["make_token_cand"]
    CoveringTransportRefused = cand_policy["CoveringTransportRefused"]
    ProviderLimits = cand_policy["ProviderLimits"]
    ProviderCounter = cand_policy["ProviderCounter"]
    HTTPSPeer = cand_policy["HTTPSPeer"]
    OrigProviderCounter = orig_policy["ProviderCounter"]
    OrigProviderLimits = orig_policy["ProviderLimits"]
    OrigHTTPSPeer = orig_policy["HTTPSPeer"]
    OrigRefused = orig_policy["CoveringTransportRefused"]

    # --- W-CROSS-PURPOSE-PAGE ---
    # Event pages at equality, stopped=false; identity/new purpose must refuse
    # on candidate; original admits.
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        o_limits = OrigProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        o = OrigProviderCounter(o_limits, lambda: 100)
        c = ProviderCounter(limits, lambda: 100)
        set_pages(o, event=APPROVED_EVENT_PAGES)
        set_pages(c, event=APPROVED_EVENT_PAGES)
        assert o.stopped is False and c.stopped is False
        orig_admitted = False
        try:
            o.page("identity")
            orig_admitted = True
        except OrigRefused:
            orig_admitted = False
        cand_refused = False
        try:
            c.page("identity")
        except CoveringTransportRefused:
            cand_refused = True
        if not (orig_admitted and cand_refused):
            raise ControlFailure(
                f"cross-purpose oracle failed orig_admitted={orig_admitted} "
                f"cand_refused={cand_refused}"
            )
        record(
            "W-CROSS-PURPOSE-PAGE",
            "PASS_WITNESS",
            "original admits identity at event equality; candidate refuses",
        )
    except Exception as exc:
        record("W-CROSS-PURPOSE-PAGE", "FAIL", repr(exc))

    # --- W-OAUTH-AT-EQUALITY ---
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        o_limits = OrigProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        o_counter = OrigProviderCounter(o_limits, lambda: 100)
        c_counter = ProviderCounter(limits, lambda: 100)
        set_pages(o_counter, event=APPROVED_EVENT_PAGES)
        set_pages(c_counter, event=APPROVED_EVENT_PAGES)
        o_probe = TransportProbe()
        c_probe = TransportProbe()
        body = framed_http_json(200, {"access_token": "x", "token_type": "Bearer"})
        o_peer, o_routes = peer_and_routes(OrigHTTPSPeer)
        c_peer, c_routes = peer_and_routes(HTTPSPeer)
        # Ensure policy modules visible for any nested refs
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            orig_policy_mod
        ]
        o_http = OrigHTTP(
            counter=o_counter,
            routes=o_routes,
            transport_factory=make_fake_transport_factory(o_probe, body),
        )
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        c_http = CandHTTP(
            counter=c_counter,
            routes=c_routes,
            transport_factory=make_fake_transport_factory(c_probe, body),
        )
        oauth_url = "https://graph.example.test/oauth2/token"
        orig_admitted = False
        try:
            o_http.request("POST", oauth_url, purpose="oauth", data={"grant_type": "refresh_token"})
            orig_admitted = True
        except OrigRefused:
            orig_admitted = False
        cand_refused = False
        cand_exc = None
        try:
            c_http.request("POST", oauth_url, purpose="oauth", data={"grant_type": "refresh_token"})
        except CoveringTransportRefused as exc:
            cand_refused = True
            cand_exc = exc
        # Candidate must refuse BEFORE transport construct/open/send
        if not (orig_admitted and cand_refused and c_probe.constructs == 0
                and c_probe.opens == 0 and c_probe.sends == 0):
            raise ControlFailure(
                f"oauth equality oracle failed orig_admitted={orig_admitted} "
                f"cand_refused={cand_refused} c_probe={c_probe} o_probe={o_probe} "
                f"cand_exc={cand_exc!r}"
            )
        if o_probe.constructs < 1 or o_probe.opens < 1 or o_probe.sends < 1:
            raise ControlFailure(
                f"original oauth check()-only should construct/open/send; probe={o_probe}"
            )
        record(
            "W-OAUTH-AT-EQUALITY",
            "PASS_WITNESS",
            "original check()-only admits OAuth at equality; candidate admit refuses pre-construct",
        )
    except Exception as exc:
        record("W-OAUTH-AT-EQUALITY", "FAIL", repr(exc))

    # --- W-TOKEN-AT-EQUALITY ---
    # Dex CORRECTED2 narrow option: instrumented db.info.get("covering_token_terminal")
    # raises AdmissionPassedSentinel immediately downstream of preflight.
    # Catch ONLY that sentinel. Candidate at equality must make ZERO info lookups.
    # No invented ORM/lock path; bare object() target is fine (locks never reached).
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        o_limits = OrigProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        o_counter = OrigProviderCounter(o_limits, lambda: 100)
        c_counter = ProviderCounter(limits, lambda: 100)
        set_pages(o_counter, event=APPROVED_EVENT_PAGES)
        set_pages(c_counter, event=APPROVED_EVENT_PAGES)
        assert o_counter.stopped is False and c_counter.stopped is False

        class T:
            def __init__(self, counter):
                self.counter = counter

        sentinel_state = {"count": 0, "location": None}
        cand_lookup_state = {"count": 0, "keys": []}

        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            orig_policy_mod
        ]
        o_ports = make_token_orig(settings=None, transport=T(o_counter))
        orig_passed_admission = False
        try:
            o_ports.token(
                types.SimpleNamespace(
                    info=CoveringTokenTerminalInfoSentinel(sentinel_state)
                ),
                object(),
                lambda: 100,
            )
            raise ControlFailure(
                "original token returned without hitting AdmissionPassedSentinel"
            )
        except AdmissionPassedSentinel:
            if sentinel_state["count"] != 1:
                raise ControlFailure(
                    f"sentinel call count {sentinel_state['count']} != 1"
                )
            if sentinel_state["location"] != SENTINEL_LOCATION_DB_INFO_GET:
                raise ControlFailure(
                    f"sentinel location {sentinel_state['location']!r} != "
                    f"{SENTINEL_LOCATION_DB_INFO_GET!r}"
                )
            orig_passed_admission = True
        # Broad catches removed: any other exception propagates as control FAIL.

        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        c_ports = make_token_cand(settings=None, transport=T(c_counter))
        cand_result = c_ports.token(
            types.SimpleNamespace(info=CoveringTokenTerminalInfoProbe(cand_lookup_state)),
            object(),
            lambda: 100,
        )
        cand_code = cand_result.code
        if cand_lookup_state["count"] != 0:
            raise ControlFailure(
                "candidate at equality must make ZERO db.info.get lookups; "
                f"got count={cand_lookup_state['count']} keys={cand_lookup_state['keys']}"
            )
        if not (
            orig_passed_admission
            and cand_code == "CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED"
        ):
            raise ControlFailure(
                f"token equality oracle failed orig_passed={orig_passed_admission} "
                f"sentinel={sentinel_state} cand_code={cand_code!r}"
            )
        record(
            "W-TOKEN-AT-EQUALITY",
            "PASS_WITNESS",
            "candidate LIMIT_EXCEEDED at equality with zero db.info.get lookups; "
            "original hit AdmissionPassedSentinel count=1 "
            f"location={SENTINEL_LOCATION_DB_INFO_GET}",
        )
    except Exception as exc:
        record("W-TOKEN-AT-EQUALITY", "FAIL", repr(exc))

    # --- W-FINAL-RESPONSE-COMPLETES ---
    # Final admitted page at equality drains via check/body/batch; must not abort.
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        set_pages(c, event=APPROVED_EVENT_PAGES - 1)
        probe = TransportProbe()
        items = [{"id": "1"}]
        body = framed_http_json(200, {"value": items})
        peer, routes = peer_and_routes(HTTPSPeer)
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        http_client = CandHTTP(
            counter=c,
            routes=routes,
            transport_factory=make_fake_transport_factory(probe, body),
        )
        resp = http_client.request(
            "GET", "https://graph.example.test/v1/events", purpose="event"
        )
        assert resp.status_code == 200
        assert c.pages["event"] == APPROVED_EVENT_PAGES
        assert c.items == 1
        assert probe.constructs == 1 and probe.opens == 1 and probe.sends == 1
        assert probe.closes == 1
        # New exchange after completion must refuse
        refused = False
        try:
            http_client.request(
                "GET", "https://graph.example.test/v1/events", purpose="event"
            )
        except CoveringTransportRefused:
            refused = True
        if not refused:
            raise ControlFailure("post-final new exchange must refuse")
        record(
            "W-FINAL-RESPONSE-COMPLETES",
            "PASS",
            "final page at ceiling-minus-one drains; later new exchange refuses",
        )
    except Exception as exc:
        record("W-FINAL-RESPONSE-COMPLETES", "FAIL", repr(exc))

    # --- M-A OAuth calls check instead of admit → must fail W-OAUTH-AT-EQUALITY ---
    # MUTATION_PROVENANCE M-A: extracted CandHTTP.request; ONLY oauth
    # self.counter.admit() -> self.counter.check(); harness-only; never in production.
    try:
        http_src = CANDIDATE_API / "app/services/covering_http_transport.py"
        tree = _load_module_ast(http_src)
        req_ast = _find_class_method(tree, "CoveringHTTP", "request")
        mutate_attr_call(req_ast, from_attr="admit", to_attr="check", expected=1)
        cand_http_mod = sys.modules["fake_t02_cand_covering_http_transport"]
        mut_request = compile_mutated_method(
            req_ast,
            filename=str(http_src) + "::M-A",
            bind_globals=cand_http_mod.__dict__,
        )
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        set_pages(c, event=APPROVED_EVENT_PAGES)
        probe = TransportProbe()
        body = framed_http_json(200, {"access_token": "x", "token_type": "Bearer"})
        peer, routes = peer_and_routes(HTTPSPeer)
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        mutated = CandHTTP(
            counter=c,
            routes=routes,
            transport_factory=make_fake_transport_factory(probe, body),
        )
        mutated.request = types.MethodType(mut_request, mutated)  # type: ignore[method-assign]
        # SAME behavioral witness as W-OAUTH-AT-EQUALITY (probe construct/open/send).
        oracle_failed = False
        try:
            mutated.request(
                "POST",
                "https://graph.example.test/oauth2/token",
                purpose="oauth",
                data={"grant_type": "refresh_token"},
            )
            # Mutant check()-only admits at equality and reaches transport.
            if probe.constructs >= 1 and probe.opens >= 1 and probe.sends >= 1:
                oracle_failed = True
        except CoveringTransportRefused:
            oracle_failed = False
        if not oracle_failed:
            raise ControlFailure(
                f"M-A mutation did not break oauth equality oracle probe={probe}"
            )
        record(
            "M-A-OAUTH-CHECK-NOT-ADMIT",
            "PASS",
            "MUTATION_PROVENANCE M-A extracted CandHTTP.request admit→check; "
            "same W-OAUTH-AT-EQUALITY witness fails (construct/open/send at equality)",
        )
    except Exception as exc:
        record("M-A-OAUTH-CHECK-NOT-ADMIT", "FAIL", repr(exc))

    # --- M-B page calls check instead of admit ---
    # MUTATION_PROVENANCE M-B: extracted ProviderCounter.page; ONLY self.admit()
    # -> self.check(); harness-only; never in production.
    try:
        policy_src = CANDIDATE_API / "app/services/covering_transport_policy.py"
        tree = _load_module_ast(policy_src)
        page_ast = _find_class_method(tree, "ProviderCounter", "page")
        mutate_attr_call(page_ast, from_attr="admit", to_attr="check", expected=1)
        cand_pol_mod = sys.modules[cand_policy_mod]
        mut_page = compile_mutated_method(
            page_ast,
            filename=str(policy_src) + "::M-B",
            bind_globals=cand_pol_mod.__dict__,
        )
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        set_pages(c, event=APPROVED_EVENT_PAGES)
        c.page = types.MethodType(mut_page, c)  # type: ignore[method-assign]
        # SAME cross-purpose witness as W-CROSS-PURPOSE-PAGE.
        oracle_failed = False
        try:
            c.page("identity")
            oracle_failed = True
        except CoveringTransportRefused:
            oracle_failed = False
        if not oracle_failed:
            raise ControlFailure("M-B mutation did not break cross-purpose oracle")
        record(
            "M-B-PAGE-CHECK-NOT-ADMIT",
            "PASS",
            "MUTATION_PROVENANCE M-B extracted ProviderCounter.page admit→check; "
            "same W-CROSS-PURPOSE-PAGE witness fails",
        )
    except Exception as exc:
        record("M-B-PAGE-CHECK-NOT-ADMIT", "FAIL", repr(exc))

    # --- M-C token tests only stopped ---
    # MUTATION_PROVENANCE M-C: extracted make_domain_ports.token preflight;
    # admission_exhausted -> stopped; token_mut MUST be invoked; harness-only.
    try:
        adapters_src = CANDIDATE_API / "app/services/covering_domain_adapters.py"
        tree = _load_module_ast(adapters_src)
        make_ports_ast = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "make_domain_ports":
                make_ports_ast = node
                break
        if make_ports_ast is None:
            raise ControlFailure("make_domain_ports missing for M-C")
        token_ast = _find_nested_function(make_ports_ast, "token")
        mutate_attribute_name(
            token_ast, from_attr="admission_exhausted", to_attr="stopped", expected=1
        )
        # Recompile mutated make_domain_ports with nested mutated token.
        adapters_mod = sys.modules["fake_t02_cand_covering_domain_adapters"]
        mut_make = compile_mutated_method(
            make_ports_ast,
            filename=str(adapters_src) + "::M-C",
            bind_globals=adapters_mod.__dict__,
        )
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        set_pages(c, event=APPROVED_EVENT_PAGES)
        assert c.admission_exhausted is True and c.stopped is False

        class T:
            def __init__(self, counter):
                self.counter = counter

        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        # Baseline candidate still exhausts at equality.
        real = make_token_cand(settings=None, transport=T(c)).token(
            types.SimpleNamespace(info={}), object(), lambda: 100
        )
        if real.code != "CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED":
            raise ControlFailure("candidate token baseline broken")
        # INVOKE token_mut (mutated extracted ports.token) — same W-TOKEN witness.
        token_mut_ports = mut_make(settings=None, transport=T(c))
        token_mut = token_mut_ports.token
        # Stopped-only at equality (stopped=False) misses LIMIT_EXCEEDED and
        # reaches the deliberate db.info.get sentinel (must be invoked).
        sentinel_state = {"count": 0, "location": None}
        mut_missed_equality = False
        try:
            token_mut(
                types.SimpleNamespace(
                    info=CoveringTokenTerminalInfoSentinel(sentinel_state)
                ),
                object(),
                lambda: 100,
            )
            raise ControlFailure(
                "M-C token_mut returned without LIMIT_EXCEEDED or sentinel"
            )
        except AdmissionPassedSentinel:
            mut_missed_equality = (
                sentinel_state["count"] == 1
                and sentinel_state["location"] == SENTINEL_LOCATION_DB_INFO_GET
            )
        if not mut_missed_equality:
            raise ControlFailure(
                f"M-C token_mut did not miss equality exhaustion sentinel={sentinel_state}"
            )
        record(
            "M-C-TOKEN-STOPPED-ONLY",
            "PASS",
            "MUTATION_PROVENANCE M-C extracted token admission_exhausted→stopped; "
            "token_mut invoked; same W-TOKEN-AT-EQUALITY witness fails via "
            f"AdmissionPassedSentinel location={SENTINEL_LOCATION_DB_INFO_GET}",
        )
    except Exception as exc:
        record("M-C-TOKEN-STOPPED-ONLY", "FAIL", repr(exc))

    # --- M-D drainage calls admit → aborts final page ---
    # MUTATION_PROVENANCE M-D: extracted CandHTTP.request drainage
    # self.counter.check() -> self.counter.admit(); framed fake response through
    # mutated extracted HTTP path; harness-only; never in production. No sockets.
    try:
        http_src = CANDIDATE_API / "app/services/covering_http_transport.py"
        tree = _load_module_ast(http_src)
        req_ast = _find_class_method(tree, "CoveringHTTP", "request")
        mutate_attr_call(req_ast, from_attr="check", to_attr="admit", expected=1)
        cand_http_mod = sys.modules["fake_t02_cand_covering_http_transport"]
        mut_request = compile_mutated_method(
            req_ast,
            filename=str(http_src) + "::M-D",
            bind_globals=cand_http_mod.__dict__,
        )
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        set_pages(c, event=APPROVED_EVENT_PAGES - 1)
        probe = TransportProbe()
        items = [{"id": "1"}]
        body = framed_http_json(200, {"value": items})
        peer, routes = peer_and_routes(HTTPSPeer)
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        mutated = CandHTTP(
            counter=c,
            routes=routes,
            transport_factory=make_fake_transport_factory(probe, body),
        )
        mutated.request = types.MethodType(mut_request, mutated)  # type: ignore[method-assign]
        aborted = False
        try:
            mutated.request(
                "GET", "https://graph.example.test/v1/events", purpose="event"
            )
            # If drainage admit did not refuse, final page wrongly completed.
            aborted = False
        except CoveringTransportRefused:
            aborted = True
        if not aborted:
            raise ControlFailure(
                "M-D mutated drainage admit did not abort final permitted page"
            )
        # Page was admitted (counter advanced) before drainage abort.
        if c.pages["event"] != APPROVED_EVENT_PAGES:
            raise ControlFailure(
                f"M-D expected page admitted before drain abort; pages={c.pages}"
            )
        if probe.constructs < 1 or probe.opens < 1 or probe.sends < 1:
            raise ControlFailure(
                f"M-D must pass framed fake response into mutated HTTP path; probe={probe}"
            )
        record(
            "M-D-DRAINAGE-CALLS-ADMIT",
            "PASS",
            "MUTATION_PROVENANCE M-D extracted CandHTTP.request drainage check→admit; "
            "framed fake response through mutated path; final-page completion fails",
        )
    except Exception as exc:
        record("M-D-DRAINAGE-CALLS-ADMIT", "FAIL", repr(exc))

    # --- R1 test-stub compatibility ---
    try:
        # Candidate test stub uses admission_exhausted=True
        stub = types.SimpleNamespace(
            counter=types.SimpleNamespace(admission_exhausted=True)
        )
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        ports = make_token_cand(settings=None, transport=stub)
        result = ports.token(types.SimpleNamespace(info={}), object(), lambda: 100)
        if result.code != "CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED":
            raise ControlFailure(f"R1 stub mismatch code={result.code!r}")
        # Static pin: candidate test file contains admission_exhausted=True
        test_src = (CANDIDATE_API / "tests" / "test_covering_transport_policy.py").read_text(
            encoding="utf-8"
        )
        if "admission_exhausted=True" not in test_src:
            raise ControlFailure("candidate test stub missing admission_exhausted=True")
        marker = "def test_provider_limit_preflight_needs_no_token_terminal"
        if marker not in test_src:
            raise ControlFailure("candidate missing no-token-terminal test")
        stub_region = test_src.split(marker, 1)[1][:500]
        if "stopped=True" in stub_region:
            raise ControlFailure("candidate test stub still uses stopped=True")
        if "admission_exhausted=True" not in stub_region:
            raise ControlFailure("candidate stub region missing admission_exhausted=True")
        record(
            "R1-TEST-STUB-ADMISSION-EXHAUSTED",
            "PASS",
            "SimpleNamespace(admission_exhausted=True) matches candidate token port",
        )
    except Exception as exc:
        record("R1-TEST-STUB-ADMISSION-EXHAUSTED", "FAIL", repr(exc))

    # --- Request-wide counter identity via CoveringReleasePlan.for_request ---
    # CORRECTED2 / Dex B: framed HTTP exceeds convenience response_bytes=64 due to
    # header/framing accounting in production _Reader. Use approved 16 MiB bytes
    # for this control (page/item convenience values remain explicitly labeled).
    # Do NOT change production byte accounting. Wiring proof must observe that
    # composed domain_ports transport.counter and HTTP path share the same object
    # across purposes; a second independent for_request gets a fresh counter.
    # Mere id(local)==id(local) is not wiring proof.
    try:
        peer, routes = peer_and_routes(HTTPSPeer)
        captured: list[Any] = []
        observed_transport_counters: list[Any] = []

        def approved_limits_for_counter_identity():
            # Page/item: CONVENIENCE_LIMITS_LABELED. Bytes: APPROVED 16 MiB
            # (framed responses exceed convenience 64; production accounting untouched).
            return ProviderLimits(
                CONVENIENCE_EVENT_PAGES,
                CONVENIENCE_IDENTITY_PAGES,
                CONVENIENCE_ITEMS,
                APPROVED_RESPONSE_BYTES,
            )

        def observing_make_domain_ports(*, settings, transport):
            observed_transport_counters.append(transport.counter)
            return make_token_cand(settings=settings, transport=transport)

        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        compose = build_release_plan_for_request(
            ProviderCounter=ProviderCounter,
            approved_provider_limits=approved_limits_for_counter_identity,
            CoveringHTTP=CandHTTP,
            make_domain_ports=observing_make_domain_ports,
            provider_routes=routes,
            provenance=bundle["provenance"],
            captured_counters=captured,
        )

        class _Budget:
            def work_remaining(self):
                return 100

        binding = compose(_Budget(), settings=None)
        if len(captured) != 1:
            raise ControlFailure(
                f"for_request expected exactly 1 ProviderCounter; got {len(captured)}"
            )
        if len(observed_transport_counters) != 1:
            raise ControlFailure(
                "make_domain_ports was not observed with a transport.counter"
            )
        counter = captured[0]
        composed_transport_counter = observed_transport_counters[0]
        # Wiring: for_request-constructed counter IS the transport.counter closed
        # over by composed domain_ports (not a local-vs-local tautology).
        if composed_transport_counter is not counter:
            raise ControlFailure(
                "composed domain_ports transport.counter is not the for_request "
                "ProviderCounter object"
            )
        ports = binding.domain_ports
        # HTTP path under the SAME counter object across event + identity purposes.
        # Fake transport_factory seam only — production byte accounting unchanged.
        probe_a = TransportProbe()
        body = framed_http_json(200, {"value": [{"id": "a"}]})
        http_client = CandHTTP(
            counter=composed_transport_counter,
            routes=routes,
            transport_factory=make_fake_transport_factory(probe_a, body),
        )
        http_client.request(
            "GET", "https://graph.example.test/v1/events", purpose="event"
        )
        probe_b = TransportProbe()
        body_b = framed_http_json(200, {"value": [{"id": "b"}]})
        http_client.transport_factory = make_fake_transport_factory(probe_b, body_b)
        http_client.request(
            "GET", "https://graph.example.test/v1/me", purpose="identity"
        )
        if counter.pages["event"] != 1 or counter.pages["identity"] != 1:
            raise ControlFailure(f"page counters wrong on shared object: {counter.pages}")
        if composed_transport_counter.pages is not counter.pages:
            raise ControlFailure("HTTP path did not mutate the composed counter object")
        # Domain ports from for_request composition must observe that same object.
        set_pages(
            counter,
            event=CONVENIENCE_EVENT_PAGES,
            identity=CONVENIENCE_IDENTITY_PAGES,
        )
        tok = ports.token(types.SimpleNamespace(info={}), object(), lambda: 100)
        if tok.code != "CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED":
            raise ControlFailure("composed domain_ports did not see shared counter")
        pages_after_first = dict(counter.pages)
        # Second independent for_request must construct a FRESH counter object.
        binding2 = compose(_Budget(), settings=None)
        if len(captured) != 2 or len(observed_transport_counters) != 2:
            raise ControlFailure(
                f"second for_request did not yield a fresh counter; "
                f"captured={len(captured)} observed={len(observed_transport_counters)}"
            )
        counter2 = captured[1]
        if counter2 is counter:
            raise ControlFailure(
                "second for_request reused the first request's ProviderCounter"
            )
        if observed_transport_counters[1] is not counter2:
            raise ControlFailure(
                "second for_request domain_ports transport.counter is not its "
                "fresh ProviderCounter"
            )
        if observed_transport_counters[1] is counter:
            raise ControlFailure(
                "second for_request domain_ports still closed over first counter"
            )
        if dict(counter.pages) != pages_after_first:
            raise ControlFailure(
                "second for_request mutated the first request's counter pages"
            )
        if getattr(binding, "FAKE_TRANSACTION_ACKNOWLEDGMENT", None) != (
            "FAKE_NOT_NATIVE_DB_ACK"
        ):
            pass  # labeled on stub class default
        record(
            "W-COUNTER-IDENTITY-REQUEST-WIDE",
            "PASS",
            "CONVENIENCE_LIMITS_LABELED pages/items; APPROVED_RESPONSE_BYTES=16MiB "
            "for framed HTTP (convenience 64 insufficient; production accounting "
            "untouched); for_request ProviderCounter is domain_ports "
            "transport.counter; HTTP event/identity mutate that object; second "
            "for_request yields a fresh counter; "
            "FAKE_TRANSACTION_ACKNOWLEDGMENT=FAKE_NOT_NATIVE_DB_ACK; "
            "not full integration proof",
        )
    except Exception as exc:
        record("W-COUNTER-IDENTITY-REQUEST-WIDE", "FAIL", repr(exc))

    # --- Ordered completed-results + later LIMIT_EXCEEDED via extracted dispatch ---
    # CORRECTED2 / Dex C: fake budget must expose check_admission() (extracted
    # run_bounded_domain calls it). Assert exact response cardinality and
    # subscription-ID order against body.subscription_ids; assert token/run_target
    # call counts. FAKE_NOT_NATIVE_DB_ACK labeling retained — NOT native/DB-ack.
    try:
        run_bounded = bundle["run_bounded_domain"]
        peer, routes = peer_and_routes(HTTPSPeer)
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        counter = ProviderCounter(limits, lambda: 100)
        # First target completes; apply exhausts pages so second token hits limit.

        class _Transport:
            def __init__(self, c):
                self.counter = c

        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        ports = make_token_cand(settings=None, transport=_Transport(counter))
        call_count = {"token": 0, "run_target": 0}

        real_token = ports.token

        def token_probe(db, target, remaining):
            call_count["token"] += 1
            if call_count["token"] == 1:
                # Eligible first target — return TokenReady without provider I/O.
                dispatch = sys.modules["app.services.covering_domain_dispatch"]
                return dispatch.TokenReady(access_token="FAKE_TOKEN_NOT_PROVIDER")
            return real_token(db, target, remaining)

        ports = types.SimpleNamespace(
            token=token_probe,
            locks=ports.locks,
            apply=ports.apply,
        )

        class _SessionCM:
            def __enter__(self):
                return types.SimpleNamespace(info={}, execute=lambda *a, **k: None)

            def __exit__(self, *exc):
                return False

        class _Connector:
            def set_authenticated_credential(self, cred):
                return None

            def session_scope(self, role):
                return _SessionCM()

            def run_target(self, **kwargs):
                # FAKE completed target result — NOT native commit/rollback ack.
                # Exhaust shared counter so the next target hits provider-limit preflight.
                call_count["run_target"] += 1
                set_pages(counter, event=APPROVED_EVENT_PAGES)
                result = types.SimpleNamespace(
                    subscription_id=kwargs["subscription_id"],
                    status="ok",
                    phase="import",
                    provider_event_read_attempted=True,
                    FAKE_TRANSACTION_ACKNOWLEDGMENT="FAKE_NOT_NATIVE_DB_ACK",
                )
                return result, None

        class _Budget:
            def __init__(self):
                self._n = 0

            def check_admission(self):
                # Extracted run_bounded_domain calls check_admission per target.
                return None

            def check_deadline(self):
                return None

            def work_remaining(self):
                # After both targets, force assessment path into deadline (fake).
                self._n += 1
                if self._n > 4:
                    raise sys.modules[
                        "app.services.covering_domain_dispatch"
                    ].CoveringDeadlineExceeded()
                return 100

        context = types.SimpleNamespace(
            budget=_Budget(),
            ownership_established=False,
            calendar_admitted=False,
            auth_telemetry_admitted=False,
            completed=[],
        )
        body = types.SimpleNamespace(
            subscription_ids=(uuid.UUID(int=101), uuid.UUID(int=102)),
            window_start=None,
            window_end=None,
            scheduling_horizon_label=None,
        )
        response = run_bounded(
            request=types.SimpleNamespace(),
            body=body,
            context=context,
            connector=_Connector(),
            ports=ports,
        )
        ordered = list(response.results)
        expected_ids = list(body.subscription_ids)
        if len(ordered) != len(expected_ids):
            raise ControlFailure(
                f"exact cardinality required: len(results)={len(ordered)} != "
                f"len(subscription_ids)={len(expected_ids)}; got {ordered!r}"
            )
        first, second = ordered[0], ordered[1]
        if getattr(first, "subscription_id", None) != expected_ids[0]:
            raise ControlFailure(
                f"first subscription_id order mismatch: "
                f"{getattr(first, 'subscription_id', None)!r} != {expected_ids[0]!r}"
            )
        if getattr(second, "subscription_id", None) != expected_ids[1]:
            raise ControlFailure(
                f"second subscription_id order mismatch: "
                f"{getattr(second, 'subscription_id', None)!r} != {expected_ids[1]!r}"
            )
        if getattr(first, "status", None) != "ok":
            raise ControlFailure(f"first ordered result not completed: {first!r}")
        if getattr(first, "FAKE_TRANSACTION_ACKNOWLEDGMENT", None) != (
            "FAKE_NOT_NATIVE_DB_ACK"
        ):
            raise ControlFailure("first result missing FAKE_TRANSACTION_ACKNOWLEDGMENT label")
        if getattr(second, "preflight_code", None) != (
            "CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED"
        ):
            raise ControlFailure(
                f"later target missing LIMIT_EXCEEDED; second={second!r}"
            )
        if call_count["token"] != 2:
            raise ControlFailure(
                f"token call count {call_count['token']} != 2 "
                "(first TokenReady, second LIMIT_EXCEEDED preflight)"
            )
        if call_count["run_target"] != 1:
            raise ControlFailure(
                f"run_target call count {call_count['run_target']} != 1 "
                "(only first completed target should run_target)"
            )
        if getattr(response, "FAKE_TRANSACTION_ACKNOWLEDGMENT", None) != (
            "FAKE_NOT_NATIVE_DB_ACK"
        ):
            raise ControlFailure("response missing FAKE_TRANSACTION_ACKNOWLEDGMENT")
        record(
            "W-ORDERED-RESULTS-LATER-LIMIT",
            "PASS",
            "FAKE_TRANSACTION_ACKNOWLEDGMENT=FAKE_NOT_NATIVE_DB_ACK: extracted "
            "run_bounded_domain; budget.check_admission present; exact cardinality=2 "
            "subscription_id order matches body.subscription_ids; token_calls=2 "
            "run_target_calls=1; first completed; later "
            "CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED; NOT native/DB-ack proof",
        )
    except Exception as exc:
        record("W-ORDERED-RESULTS-LATER-LIMIT", "FAIL", repr(exc))

    # --- Ceiling-minus-one admits next exchange ---
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        set_pages(c, event=APPROVED_EVENT_PAGES - 1)
        c.page("event")  # must admit
        assert c.pages["event"] == APPROVED_EVENT_PAGES
        # identity ceiling minus one
        c2 = ProviderCounter(limits, lambda: 100)
        set_pages(c2, event=0, identity=APPROVED_IDENTITY_PAGES - 1)
        c2.page("identity")
        assert c2.pages["identity"] == APPROVED_IDENTITY_PAGES
        record(
            "W-CEILING-MINUS-ONE-ADMITS",
            "PASS",
            "approved ceilings: count N-1 admits Nth event/identity page",
        )
    except Exception as exc:
        record("W-CEILING-MINUS-ONE-ADMITS", "FAIL", repr(exc))

    # --- Approved ceiling boundary event=20 ---
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        for _ in range(APPROVED_EVENT_PAGES):
            c.page("event")
        refused = False
        try:
            c.page("event")
        except CoveringTransportRefused:
            refused = True
        if not refused:
            raise ControlFailure("21st event page must refuse at approved ceiling 20")
        # approved_provider_limits pin
        ap = cand_policy["approved_provider_limits"]()
        if ap != limits:
            raise ControlFailure("approved_provider_limits mismatch")
        record(
            "W-APPROVED-CEILING-EVENT-BOUNDARY",
            "PASS",
            "approved event ceiling 20: 20 admit, 21st refuses",
        )
    except Exception as exc:
        record("W-APPROVED-CEILING-EVENT-BOUNDARY", "FAIL", repr(exc))

    # --- Approved ceiling boundary identity=10 ---
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        for _ in range(APPROVED_IDENTITY_PAGES):
            c.page("identity")
        refused = False
        try:
            c.page("identity")
        except CoveringTransportRefused:
            refused = True
        if not refused:
            raise ControlFailure("11th identity page must refuse at approved ceiling 10")
        record(
            "W-APPROVED-CEILING-IDENTITY-BOUNDARY",
            "PASS",
            "approved identity ceiling 10: 10 admit, 11th refuses",
        )
    except Exception as exc:
        record("W-APPROVED-CEILING-IDENTITY-BOUNDARY", "FAIL", repr(exc))

    # --- Approved items N-1 admits ---
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        # INJECTED_COUNTER_STATE: items = APPROVED_ITEMS - 1
        c.items = APPROVED_ITEMS - 1
        c.batch([{"id": "n"}])  # must admit Nth item
        if c.items != APPROVED_ITEMS:
            raise ControlFailure(f"items N-1 did not admit Nth; items={c.items}")
        record(
            "W-APPROVED-CEILING-ITEMS-N-MINUS-ONE",
            "PASS",
            "INJECTED_COUNTER_STATE items=9999; approved items ceiling N-1 admits Nth",
        )
    except Exception as exc:
        record("W-APPROVED-CEILING-ITEMS-N-MINUS-ONE", "FAIL", repr(exc))

    # --- Approved items equality: refuse before transport for all purposes ---
    # CORRECTED2 / Dex D: FRESH counter per purpose. Inject only the exact item
    # ceiling. Assert stopped=False immediately before each call. Do not share one
    # counter across the purpose loop (first refuse sets stopped and pollutes later).
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        peer, routes = peer_and_routes(HTTPSPeer)
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        body = framed_http_json(200, {"value": []})
        refusals = {}
        for purpose, method, url, data in (
            ("event", "GET", "https://graph.example.test/v1/events", None),
            ("identity", "GET", "https://graph.example.test/v1/me", None),
            (
                "oauth",
                "POST",
                "https://graph.example.test/oauth2/token",
                {"grant_type": "refresh_token"},
            ),
        ):
            c = ProviderCounter(limits, lambda: 100)
            # INJECTED_COUNTER_STATE: items at approved equality (this purpose only)
            c.items = APPROVED_ITEMS
            if c.stopped is not False:
                raise ControlFailure(
                    f"items equality precondition failed for {purpose}: stopped must be False"
                )
            if c.admission_exhausted is not True:
                raise ControlFailure(
                    f"items equality precondition failed for {purpose}: "
                    "admission_exhausted must be True"
                )
            probe = TransportProbe()
            http_client = CandHTTP(
                counter=c,
                routes=routes,
                transport_factory=make_fake_transport_factory(probe, body),
            )
            refused = False
            try:
                kw = {"purpose": purpose}
                if data is not None:
                    kw["data"] = data
                http_client.request(method, url, **kw)
            except CoveringTransportRefused:
                refused = True
            if not (
                refused
                and probe.constructs == 0
                and probe.opens == 0
                and probe.sends == 0
            ):
                raise ControlFailure(
                    f"items equality must refuse pre-construct for {purpose}; "
                    f"refused={refused} probe={probe}"
                )
            refusals[purpose] = True
        record(
            "W-APPROVED-CEILING-ITEMS-EQUALITY-ALL-PURPOSES",
            "PASS",
            "INJECTED_COUNTER_STATE items=10000 per purpose (fresh counter each); "
            "stopped=False asserted pre-call; event/identity/oauth refuse before "
            f"transport construct (zero constructs/opens/sends); purposes={sorted(refusals)}",
        )
    except Exception as exc:
        record("W-APPROVED-CEILING-ITEMS-EQUALITY-ALL-PURPOSES", "FAIL", repr(exc))

    # --- Approved bytes N-1 admits ---
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        c = ProviderCounter(limits, lambda: 100)
        # INJECTED_COUNTER_STATE: bytes = APPROVED_RESPONSE_BYTES - 1
        c.bytes = APPROVED_RESPONSE_BYTES - 1
        c.body(1)  # must admit final byte
        if c.bytes != APPROVED_RESPONSE_BYTES:
            raise ControlFailure(f"bytes N-1 did not admit Nth; bytes={c.bytes}")
        record(
            "W-APPROVED-CEILING-BYTES-N-MINUS-ONE",
            "PASS",
            "INJECTED_COUNTER_STATE bytes=16777215; approved 16MiB N-1 admits Nth byte",
        )
    except Exception as exc:
        record("W-APPROVED-CEILING-BYTES-N-MINUS-ONE", "FAIL", repr(exc))

    # --- Approved bytes equality: refuse before transport for all purposes ---
    # Equality must not abort an already-admitted response (W-FINAL-RESPONSE-COMPLETES
    # preserved separately). This control covers NEW exchanges only.
    # CORRECTED2 / Dex D: FRESH counter per purpose. Inject only the exact byte
    # ceiling. Assert stopped=False immediately before each call. Do not share one
    # counter across the purpose loop.
    try:
        limits = ProviderLimits(
            APPROVED_EVENT_PAGES,
            APPROVED_IDENTITY_PAGES,
            APPROVED_ITEMS,
            APPROVED_RESPONSE_BYTES,
        )
        peer, routes = peer_and_routes(HTTPSPeer)
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            cand_policy_mod
        ]
        body = framed_http_json(200, {"value": []})
        refusals = {}
        for purpose, method, url, data in (
            ("event", "GET", "https://graph.example.test/v1/events", None),
            ("identity", "GET", "https://graph.example.test/v1/me", None),
            (
                "oauth",
                "POST",
                "https://graph.example.test/oauth2/token",
                {"grant_type": "refresh_token"},
            ),
        ):
            c = ProviderCounter(limits, lambda: 100)
            # INJECTED_COUNTER_STATE: bytes at approved equality (this purpose only)
            c.bytes = APPROVED_RESPONSE_BYTES
            if c.stopped is not False:
                raise ControlFailure(
                    f"bytes equality precondition failed for {purpose}: stopped must be False"
                )
            if c.admission_exhausted is not True:
                raise ControlFailure(
                    f"bytes equality precondition failed for {purpose}: "
                    "admission_exhausted must be True"
                )
            probe = TransportProbe()
            http_client = CandHTTP(
                counter=c,
                routes=routes,
                transport_factory=make_fake_transport_factory(probe, body),
            )
            refused = False
            try:
                kw = {"purpose": purpose}
                if data is not None:
                    kw["data"] = data
                http_client.request(method, url, **kw)
            except CoveringTransportRefused:
                refused = True
            if not (
                refused
                and probe.constructs == 0
                and probe.opens == 0
                and probe.sends == 0
            ):
                raise ControlFailure(
                    f"bytes equality must refuse pre-construct for {purpose}; "
                    f"refused={refused} probe={probe}"
                )
            refusals[purpose] = True
        record(
            "W-APPROVED-CEILING-BYTES-EQUALITY-ALL-PURPOSES",
            "PASS",
            "INJECTED_COUNTER_STATE bytes=16777216 per purpose (fresh counter each); "
            "stopped=False asserted pre-call; event/identity/oauth refuse before "
            f"transport construct (zero constructs/opens/sends); purposes={sorted(refusals)}; "
            "does not interrupt W-FINAL-RESPONSE-COMPLETES",
        )
    except Exception as exc:
        record("W-APPROVED-CEILING-BYTES-EQUALITY-ALL-PURPOSES", "FAIL", repr(exc))

    # --- Convenience-limit disclosure control ---
    try:
        # Documents that convenience limits were used only where labeled and
        # cannot substitute for full integration proof.
        if CONVENIENCE_EVENT_PAGES >= APPROVED_EVENT_PAGES:
            raise ControlFailure("convenience limits must be smaller and labeled")
        record(
            "L-CONVENIENCE-LIMITS-LABELED",
            "PASS",
            "convenience 2/1/3/64 labeled; cannot substitute approved 20/10/10000/16MiB integration proof",
        )
    except Exception as exc:
        record("L-CONVENIENCE-LIMITS-LABELED", "FAIL", repr(exc))

    # --- Harness-only: inventory enforcer rejects bad order/dup/missing/outcome ---
    try:
        expected = load_expected()
        # Synthetic gate fixtures only: never count these as executed suite results.
        # First prove this complete baseline is accepted, including this control's ID.
        expected_ids = expected_control_ids(expected)
        if len(expected_ids) < 2:
            raise ControlFailure("inventory self-check requires at least two IDs")
        baseline = [
            ControlResult(cid, expected["controls"][cid]["result"], "synthetic gate baseline")
            for cid in expected_ids
        ]
        enforce_expected_inventory(baseline, expected)
        # Wrong order only: same complete inventory and outcomes.
        wrong_order = list(baseline)
        wrong_order[0], wrong_order[1] = wrong_order[1], wrong_order[0]
        caught = False
        try:
            enforce_expected_inventory(wrong_order, expected)
        except ControlFailure as exc:
            if "order mismatch" not in str(exc):
                raise ControlFailure(f"wrong-order did not cite order: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted wrong order")
        # Duplicate
        dup = list(baseline) + [baseline[0]]
        caught = False
        try:
            enforce_expected_inventory(dup, expected)
        except ControlFailure as exc:
            if "duplicate" not in str(exc):
                raise ControlFailure(f"duplicate did not cite duplicate: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted duplicate")
        # Missing only: remove one ID from the accepted complete baseline.
        missing = list(baseline[:-1])
        caught = False
        try:
            enforce_expected_inventory(missing, expected)
        except ControlFailure as exc:
            if "order mismatch" not in str(exc) and "missing" not in str(exc):
                raise ControlFailure(f"missing did not cite mismatch: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted missing inventory")
        # Unexpected outcome
        # Wrong outcome only: keep the complete accepted ID order.
        synth = list(baseline)
        synth[0] = ControlResult(
            baseline[0].control_id, "UNEXPECTED_OUTCOME", "deliberate unexpected-outcome"
        )
        caught = False
        try:
            enforce_expected_inventory(synth, expected)
        except ControlFailure as exc:
            if "unexpected-outcome" not in str(exc):
                raise ControlFailure(f"bad outcome did not cite unexpected-outcome: {exc}")
            caught = True
        if not caught:
            raise ControlFailure("enforcer accepted unexpected outcome")
        record(
            "H-INVENTORY-ENFORCER-REJECTS-BAD",
            "PASS",
            "harness-only: full synthetic baseline accepted; single-dimension "
            "wrong-order, duplicate, missing, and unexpected-outcome fixtures refused; "
            "synthetic baseline is not an executed suite result",
        )
    except Exception as exc:
        record("H-INVENTORY-ENFORCER-REJECTS-BAD", "FAIL", repr(exc))

    return results


def main() -> int:
    provenance: list[ExtractionProvenance] = []
    inventory_error = None
    source_hashes_verified = False
    results: list[ControlResult] = []
    try:
        install_budget_stub()
        make_httpx_stub()
        manifest = load_manifest()
        expected = load_expected()
        verify_source_hashes(manifest)
        source_hashes_verified = True

        # Build original + candidate extraction bundles
        orig_policy = build_policy_module(
            BASES / "app/services/covering_transport_policy.py",
            "fake_t02_orig_covering_transport_policy",
            provenance,
        )
        cand_policy = build_policy_module(
            CANDIDATE_API / "app/services/covering_transport_policy.py",
            "fake_t02_cand_covering_transport_policy",
            provenance,
        )
        # Publish class attributes onto ModuleType for CoveringHTTP imports
        for mod_name, extracted in (
            ("fake_t02_orig_covering_transport_policy", orig_policy),
            ("fake_t02_cand_covering_transport_policy", cand_policy),
        ):
            mod = sys.modules[mod_name]
            for k, v in extracted.items():
                if k != "__ns__":
                    setattr(mod, k, v)

        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            "fake_t02_orig_covering_transport_policy"
        ]
        orig_http = build_http_module(
            BASES / "app/services/covering_http_transport.py",
            "fake_t02_orig_covering_http_transport",
            "fake_t02_orig_covering_transport_policy",
            provenance,
        )
        sys.modules["app.services.covering_transport_policy"] = sys.modules[
            "fake_t02_cand_covering_transport_policy"
        ]
        cand_http = build_http_module(
            CANDIDATE_API / "app/services/covering_http_transport.py",
            "fake_t02_cand_covering_http_transport",
            "fake_t02_cand_covering_transport_policy",
            provenance,
        )

        make_token_orig = build_domain_token_port(
            BASES / "app/services/covering_domain_adapters.py",
            "fake_t02_orig_covering_domain_adapters",
            "fake_t02_orig_covering_transport_policy",
            provenance,
        )
        make_token_cand = build_domain_token_port(
            CANDIDATE_API / "app/services/covering_domain_adapters.py",
            "fake_t02_cand_covering_domain_adapters",
            "fake_t02_cand_covering_transport_policy",
            provenance,
        )
        run_bounded_domain = build_ordered_domain_dispatch(provenance=provenance)

        bundle = {
            "orig_policy": orig_policy,
            "cand_policy": cand_policy,
            "OrigHTTP": orig_http["CoveringHTTP"],
            "CandHTTP": cand_http["CoveringHTTP"],
            "orig_policy_mod": "fake_t02_orig_covering_transport_policy",
            "cand_policy_mod": "fake_t02_cand_covering_transport_policy",
            "make_token_orig": make_token_orig,
            "make_token_cand": make_token_cand,
            "run_bounded_domain": run_bounded_domain,
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

    expected = load_expected()
    by_id = {r.control_id: r for r in results}
    # Do NOT reorder/repair emitted results into EXPECTED order in serialization.
    # Emitted order is the authority; enforce_expected_inventory already compared
    # it directly to control_ids_in_order before PASS.
    ordered_ids = [r.control_id for r in results]
    payload = {
        "status": status,
        "class": "FAKE-T02-ADMISSION",
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
        "limits": {
            "approved_event_pages": APPROVED_EVENT_PAGES,
            "approved_identity_pages": APPROVED_IDENTITY_PAGES,
            "approved_items": APPROVED_ITEMS,
            "approved_response_bytes": APPROVED_RESPONSE_BYTES,
            "convenience_limits_labeled_not_integration_proof": {
                "event_pages": CONVENIENCE_EVENT_PAGES,
                "identity_pages": CONVENIENCE_IDENTITY_PAGES,
                "items": CONVENIENCE_ITEMS,
                "response_bytes": CONVENIENCE_RESPONSE_BYTES,
            },
        },
        "unresolved_native_obligations": [
            "known-rollback vs UNKNOWN classification — NOT claimed",
            "provider/socket retirement — NOT claimed",
            "real TLS — NOT claimed",
            "DB acknowledgment — NOT claimed (W-ORDERED-RESULTS is fake token port only)",
            "T02 runtime proof — NOT closed",
            "T01-T08 other obligations — NOT closed",
        ],
        "does_not_import_app": True,
        "launch_ready": False,
    }
    RESULT_PATH.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    print(json.dumps({"status": status, "inventory_error": inventory_error}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
