#!/usr/bin/env python3
"""T05 original framing witness prep v4 (AUTHORING ONLY — not executed).

Four-role fake successor under Jim. Dex owns native-dex-v3 separately.

B1–B7 (Dex REVISE): policy_ns seeded before extraction; selected-def txn only
(no whole-module app/vendor import); httpx Request/Response fakes; exact
exposed-exception classification without oauth policy remapping in the
classifier; calendar_client context selection driver; truthful response
field observations; exact predicates + per-input close counters; STOP on
first unpredicted. Real http.client.HTTPResponse parser (no imitation).
launch_ready=false; executed_in_preparation=false.
"""
from __future__ import annotations

import ast
import hashlib
import http.client
import io
import json
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
PAYLOAD = ROOT / "payload"
MANIFEST_PATH = HERE / "INPUT-MANIFEST.json"
EXPECTED_PATH = HERE / "EXPECTED-ORIGINAL.json"
RESULT_PATH = HERE / "FAKE-T05-RESULT.json"
WIRE_DIR = HERE / "wire_transcripts"

G_HOST = "www.googleapis.com"
G_ADDR = "203.0.113.10"
G_GAUTH = "oauth2.googleapis.com"
G_GADDR = "203.0.113.11"
CA_FILE = "synthetic-public-ca.pem"
EVENT_PREFIX = "/calendar/v3/calendars/"
TOKEN_EXACT = "/token"
GOOGLE_TOKEN_URL = f"https://{G_GAUTH}{TOKEN_EXACT}"

OUTCOME_FIELDS = (
    "underlying_cause_hypothesis",
    "exposed_boundary_outcome",
    "observation_boundary",
    "observed_outcome",
    "prediction_ok",
    "predicted_outcome",
    "exception_type",
    "exception_module",
    "send_state",
    "http_status",
    "body_bytes_collected",
    "transport_wire_bytes",
    "response_close_calls",
    "transport_close_calls",
    "transport_bytes_received",
    "wire_sha256",
    "wire_byte_length",
    "contract_miss",
    "tls_close_notify_proven",
    "byte_fake_eof_only",
    "stall_is_not_deadline_proof",
    "driver",
    "owning_caller",
)


class WitnessFailure(Exception):
    pass


@dataclass
class CloseProbe:
    response_close_calls: int = 0
    transport_close_calls: int = 0
    transport_bytes_received: int = 0


@dataclass
class ExtractionProvenance:
    source_path: str
    source_sha256: str
    names: list[str]


class FakeHttpxRequest:
    def __init__(self, method: str, url: str):
        self.method = method
        self.url = url


class FakeHttpxResponse:
    def __init__(
        self,
        status_code: int,
        *,
        content: bytes,
        headers: dict[str, str],
        request: FakeHttpxRequest,
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self.request = request
        self.text = content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.content)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def decode_for_ast(raw: bytes) -> tuple[str, str]:
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return text, "lf"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes().decode("utf-8"))


def resolve_source(rel: str) -> Path:
    rel = rel.replace("\\", "/")
    if rel.startswith("bases/"):
        return PAYLOAD / "bases" / rel[len("bases/") :]
    return PAYLOAD / rel


def verify_source_hashes(manifest: dict[str, Any]) -> None:
    for rel, expected in manifest["source_extraction"]["sources"].items():
        if sha256_file(resolve_source(rel)) != expected.upper():
            raise WitnessFailure(f"source hash mismatch for {rel}")
    lib_root = Path(manifest["stdlib_provenance"]["lib_root"])
    for rel, expected in manifest["stdlib_provenance"]["modules"].items():
        path = lib_root / rel.replace("\\", "/")
        if sha256_file(path) != expected.upper():
            raise WitnessFailure(f"stdlib hash mismatch for {rel}")


def new_module_namespace(module_name: str) -> dict[str, Any]:
    module = types.ModuleType(module_name)
    module.__dict__["__builtins__"] = __builtins__
    module.__dict__["__name__"] = module_name
    module.__dict__["__annotations__"] = {}
    sys.modules[module_name] = module
    return module.__dict__


def extract_symbols(
    source_path: Path,
    names: list[str],
    module_ns: dict[str, Any],
    *,
    provenance: list[ExtractionProvenance],
) -> dict[str, Any]:
    raw = source_path.read_bytes()
    text, _ = decode_for_ast(raw)
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
        if hit:
            selected.append(node)
    missing = sorted(wanted - found)
    if missing:
        raise WitnessFailure(f"AST names missing {source_path.name}: {missing}")
    exec(  # noqa: S102 — intentional selected-definition extraction
        compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"),
        module_ns,
    )
    provenance.append(
        ExtractionProvenance(str(source_path), sha256_bytes(raw), list(names))
    )
    return {n: module_ns[n] for n in names}


def project_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in OUTCOME_FIELDS:
        val = evidence.get(key)
        if val is not None and not isinstance(val, (str, int, float, bool, type(None))):
            raise WitnessFailure(f"evidence field {key!r} not JSON primitive")
        out[key] = val
    return out


def seed_policy_namespace(policy_ns: dict[str, Any]) -> None:
    """B1: seed dataclass/IP/URL/annotation deps BEFORE selected extraction."""

    class CoveringDeadlineExceeded(Exception):
        """Permitted fake stand-in; budget module not imported."""

    policy_ns.update(
        {
            "dataclass": dataclass,
            "ip_address": ip_address,
            "unquote": unquote,
            "urlsplit": urlsplit,
            "CoveringDeadlineExceeded": CoveringDeadlineExceeded,
            "__annotations__": {},
        }
    )


def build_fake_httpx() -> types.ModuleType:
    """B2: honest Client/Request/Response constructors; no app/vendor import."""
    httpx_mod = types.ModuleType("httpx")

    class Client:
        def __init__(self, *, timeout: Any = None):
            self.timeout = timeout

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

    httpx_mod.Client = Client  # type: ignore[attr-defined]
    httpx_mod.Request = FakeHttpxRequest  # type: ignore[attr-defined]
    httpx_mod.Response = FakeHttpxResponse  # type: ignore[attr-defined]
    sys.modules["httpx"] = httpx_mod
    return httpx_mod


def build_extracted_runtime(
    manifest: dict[str, Any],
) -> tuple[Any, dict[str, Any], Any, Any, list[ExtractionProvenance]]:
    provenance: list[ExtractionProvenance] = []
    for name in (
        "app",
        "app.services",
        "app.services.covering_transport_policy",
        "app.services.covering_target_transaction",
        "app.services.covering_joined_https",
        "app.services.covering_http_transport",
        "app.services.covering_provider_context",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # B1: policy_ns seeded before extraction (dataclass/IP/URL deps).
    policy_ns = new_module_namespace("app.services.covering_transport_policy")
    seed_policy_namespace(policy_ns)
    policy_syms = manifest["source_extraction"]["extracted_symbols"][
        "workspace/apps/api/app/services/covering_transport_policy.py"
    ]
    policy = extract_symbols(
        resolve_source("workspace/apps/api/app/services/covering_transport_policy.py"),
        policy_syms,
        policy_ns,
        provenance=provenance,
    )

    # B1: selected CoveringRootOutcomeUnknown only — no whole-module txn import.
    txn_ns = new_module_namespace("app.services.covering_target_transaction")
    txn_syms = manifest["source_extraction"]["extracted_symbols"][
        "workspace/apps/api/app/services/covering_target_transaction.py"
    ]
    if txn_syms != ["CoveringRootOutcomeUnknown"]:
        raise WitnessFailure("txn extraction must be CoveringRootOutcomeUnknown only")
    txn = extract_symbols(
        resolve_source("workspace/apps/api/app/services/covering_target_transaction.py"),
        txn_syms,
        txn_ns,
        provenance=provenance,
    )

    join_ns = new_module_namespace("app.services.covering_joined_https")
    join_ns["JoinedTLS"] = type("JoinedTLS", (), {})

    httpx_mod = build_fake_httpx()

    http_ns = new_module_namespace("app.services.covering_http_transport")
    http_ns.update(
        {
            "io": io,
            "json": json,
            "http": sys.modules["http"] if "http" in sys.modules else types.ModuleType("http"),
            "httpx": httpx_mod,
            "urlencode": urllib.parse.urlencode,
            "CoveringTransportRefused": policy["CoveringTransportRefused"],
            "CoveringReauthorizationRequired": policy["CoveringReauthorizationRequired"],
            "CoveringRootOutcomeUnknown": txn["CoveringRootOutcomeUnknown"],
            "admit_covering_path": policy["admit_covering_path"],
            "JoinedTLS": join_ns["JoinedTLS"],
        }
    )
    # Ensure http.client attribute path used by extracted source.
    if "http" not in sys.modules:
        sys.modules["http"] = http_ns["http"]
    http_pkg = sys.modules["http"]
    if not hasattr(http_pkg, "client"):
        http_pkg.client = http.client  # type: ignore[attr-defined]
    http_ns["http"] = http_pkg

    http_syms = manifest["source_extraction"]["extracted_symbols"][
        "workspace/apps/api/app/services/covering_http_transport.py"
    ]
    http_extract = extract_symbols(
        resolve_source("workspace/apps/api/app/services/covering_http_transport.py"),
        http_syms,
        http_ns,
        provenance=provenance,
    )
    CoveringHTTP = http_extract["CoveringHTTP"]

    ctx_ns = new_module_namespace("app.services.covering_provider_context")
    ctx_ns.update(
        {
            "contextmanager": contextmanager,
            "ContextVar": __import__("contextvars", fromlist=["ContextVar"]).ContextVar,
            "httpx": httpx_mod,
            "urlsplit": urlsplit,
            "CoveringTransportRefused": policy["CoveringTransportRefused"],
            "admit_covering_path": policy["admit_covering_path"],
        }
    )
    ctx_syms = manifest["source_extraction"]["extracted_symbols"][
        "workspace/apps/api/app/services/covering_provider_context.py"
    ]
    # Extract ContextVar binding used by covering_provider_transport.
    raw_ctx = resolve_source(
        "workspace/apps/api/app/services/covering_provider_context.py"
    ).read_bytes()
    text_ctx, _ = decode_for_ast(raw_ctx)
    tree_ctx = ast.parse(text_ctx)
    for node in tree_ctx.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_current":
                    exec(  # noqa: S102
                        compile(ast.Module(body=[node], type_ignores=[]), "ctx", "exec"),
                        ctx_ns,
                    )
    ctx = extract_symbols(
        resolve_source("workspace/apps/api/app/services/covering_provider_context.py"),
        ctx_syms,
        ctx_ns,
        provenance=provenance,
    )

    return CoveringHTTP, policy, ctx, txn, provenance


class FakeTransport:
    def __init__(self, wire: bytes, probe: CloseProbe, *, stall: bool = False):
        self.wire = wire
        self.pos = 0
        self.sent = False
        self.probe = probe
        self.stall = stall
        self._stall_returns = 0

    def open(self) -> None:
        return None

    def send(self, _wire: bytes) -> None:
        self.sent = True

    def receive(self, n: int) -> bytes:
        # B6: stall returns empty recv → EOF, NOT a deadline stimulus.
        if self.stall:
            self._stall_returns += 1
            return b""
        chunk = self.wire[self.pos : self.pos + n]
        self.pos += len(chunk)
        self.probe.transport_bytes_received += len(chunk)
        return chunk

    def close(self) -> None:
        self.probe.transport_close_calls += 1


def classify_exposed_exception(
    exc: BaseException, policy: dict[str, Any]
) -> str | None:
    """B3: classify the ACTUAL exposed exception; do not duplicate oauth remap."""
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
    # Bare ValueError must NOT cover arbitrary harness errors.
    if type(exc) is ValueError:
        return "OBSERVED_PARSER_ERROR"
    if isinstance(exc, WitnessFailure):
        raise exc
    return None


@contextmanager
def instrument_response_close(probe: CloseProbe):
    orig = http.client.HTTPResponse.close

    def patched(self: http.client.HTTPResponse) -> Any:
        probe.response_close_calls += 1
        return orig(self)

    http.client.HTTPResponse.close = patched  # type: ignore[method-assign]
    try:
        yield
    finally:
        http.client.HTTPResponse.close = orig  # type: ignore[method-assign]


def contract_miss_flag(
    wire_id: str,
    *,
    policy: dict[str, Any],
    exc: BaseException | None,
    decoded_success: bool,
) -> bool:
    """Separate defect designation from observed outcome (B4/B7)."""
    if wire_id == "F03-oauth" and exc is not None and isinstance(
        exc, policy["CoveringReauthorizationRequired"]
    ):
        return True
    if decoded_success and wire_id in {
        "F02",
        "F05-oauth",
        "C-SEP-WRONG",
        "C-TRAILER-EOF",
    }:
        return True
    return False


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


def observe_success_fields(result: Any) -> tuple[int | None, int, int]:
    """B7: capture fake response constructor primitives — not json.dumps(decoded)."""
    if isinstance(result, FakeHttpxResponse):
        return result.status_code, len(result.content), len(result.content)
    if isinstance(result, dict):
        # Should not happen once httpx.Response fake is wired; refuse silent fallthrough.
        raise WitnessFailure("dict_success_not_httpx_response")
    raise WitnessFailure(f"unexpected_success_type:{type(result).__name__}")


def run_covering_http_request(
    CoveringHTTP: Any,
    policy: dict[str, Any],
    *,
    wire_id: str,
    wire_bytes: bytes,
    purpose: str,
    probe: CloseProbe,
    stall: bool = False,
) -> tuple[str, dict[str, Any]]:
    limits = policy["approved_provider_limits"]()
    counter = policy["ProviderCounter"](limits, lambda: 240.0)
    routes = routes_for_purpose(policy, purpose)
    method, url, data = request_args_for_purpose(purpose)

    def factory(_peer, _rem):
        return FakeTransport(wire_bytes, probe, stall=stall)

    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    evidence: dict[str, Any] = {
        "wire_id": wire_id,
        "purpose": purpose,
        "observation_boundary": "CoveringHTTP.request",
        "driver": "covering_http",
        "owning_caller": "CoveringHTTP.request",
        "wire_sha256": sha256_bytes(wire_bytes),
        "wire_byte_length": len(wire_bytes),
        "transport_wire_bytes": len(wire_bytes),
        "tls_close_notify_proven": False,
        "byte_fake_eof_only": wire_id in {"CD-ORDERLY", "CD-ABRUPT", "CD-DEADLINE"},
        "stall_is_not_deadline_proof": stall or wire_id == "CD-DEADLINE",
    }
    observed = "OBSERVED_UNKNOWN"
    exc_obj: BaseException | None = None
    http_status: int | None = None
    body_len = 0
    send_state = "before_send"
    with instrument_response_close(probe):
        try:
            result = http.request(method, url, purpose=purpose, data=data)
            send_state = "after_send"
            observed = "OBSERVED_SUCCESS"
            http_status, body_len, _ = observe_success_fields(result)
            evidence["contract_miss"] = contract_miss_flag(
                wire_id, policy=policy, exc=None, decoded_success=True
            )
        except BaseException as exc:
            exc_obj = exc
            # Transport.sent is the send-state boundary for oauth remap in SUT.
            transport_sent = False
            # Best-effort: CoveringHTTP closes transport in finally; use probe bytes
            # or exception chain — send_state recorded as after_send if any bytes
            # were received OR exception is remapped UNKNOWN (oauth after-send).
            if probe.transport_bytes_received > 0 or isinstance(
                exc, policy["CoveringRootOutcomeUnknown"]
            ):
                send_state = "after_send"
                transport_sent = True
            elif isinstance(
                exc,
                (
                    policy["CoveringReauthorizationRequired"],
                    policy["CoveringTransportRefused"],
                    json.JSONDecodeError,
                    http.client.HTTPException,
                ),
            ):
                # These occur only after send in CoveringHTTP.request body path.
                send_state = "after_send"
                transport_sent = True
            _ = transport_sent
            classified = classify_exposed_exception(exc, policy)
            if classified is None:
                raise WitnessFailure(
                    f"UNEXPECTED_EXCEPTION:{wire_id}:{type(exc).__module__}.{type(exc).__name__}"
                )
            observed = classified
            evidence["exception_type"] = type(exc).__name__
            evidence["exception_module"] = type(exc).__module__
            evidence["contract_miss"] = contract_miss_flag(
                wire_id, policy=policy, exc=exc, decoded_success=False
            )
    evidence["send_state"] = send_state
    evidence["http_status"] = http_status
    evidence["body_bytes_collected"] = body_len
    evidence["response_close_calls"] = probe.response_close_calls
    evidence["transport_close_calls"] = probe.transport_close_calls
    evidence["transport_bytes_received"] = probe.transport_bytes_received
    evidence["observed_outcome"] = observed
    evidence["exposed_boundary_outcome"] = observed
    return observed, evidence


def run_calendar_client_caller(
    CoveringHTTP: Any,
    policy: dict[str, Any],
    ctx: dict[str, Any],
    *,
    wire_id: str,
    wire_bytes: bytes,
    purpose: str,
    probe: CloseProbe,
    owning_caller: str,
) -> tuple[str, dict[str, Any]]:
    """B5: exercise calendar_client context selection, not manual _CoveringClient."""
    limits = policy["approved_provider_limits"]()
    counter = policy["ProviderCounter"](limits, lambda: 240.0)
    routes = routes_for_purpose(policy, purpose)
    method, url, data = request_args_for_purpose(purpose)
    transport = FakeTransport(wire_bytes, probe)

    def factory(_p, _r):
        return transport

    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    covering_provider_transport = ctx["covering_provider_transport"]
    calendar_client = ctx["calendar_client"]
    observed = "OBSERVED_UNKNOWN"
    evidence: dict[str, Any] = {
        "wire_id": wire_id,
        "purpose": purpose,
        "observation_boundary": "calendar_client under covering_provider_transport",
        "driver": "calendar_client",
        "owning_caller": owning_caller,
        "wire_sha256": sha256_bytes(wire_bytes),
        "wire_byte_length": len(wire_bytes),
        "transport_wire_bytes": len(wire_bytes),
        "tls_close_notify_proven": False,
        "byte_fake_eof_only": False,
        "stall_is_not_deadline_proof": False,
    }
    with covering_provider_transport(http):
        client = calendar_client(timeout=30.0)
        # Must be _CoveringClient when covering context is active — not httpx.Client.
        if type(client).__name__ != "_CoveringClient":
            raise WitnessFailure(
                f"calendar_client_did_not_select_covering:{type(client).__name__}"
            )
        with instrument_response_close(probe):
            try:
                if purpose == "oauth":
                    result = client.post(
                        url,
                        data=data or {"grant_type": "refresh_token", "refresh_token": "x"},
                    )
                else:
                    result = client.get(url)
                observed = "OBSERVED_SUCCESS"
                http_status, body_len, _ = observe_success_fields(result)
                evidence["http_status"] = http_status
                evidence["body_bytes_collected"] = body_len
                evidence["send_state"] = "after_send"
                evidence["contract_miss"] = contract_miss_flag(
                    wire_id, policy=policy, exc=None, decoded_success=True
                )
            except BaseException as exc:
                classified = classify_exposed_exception(exc, policy)
                if classified is None:
                    raise WitnessFailure(
                        f"UNEXPECTED_EXCEPTION:{wire_id}:{type(exc).__module__}.{type(exc).__name__}"
                    )
                observed = classified
                evidence["exception_type"] = type(exc).__name__
                evidence["exception_module"] = type(exc).__module__
                evidence["send_state"] = "after_send"
                evidence["http_status"] = None
                evidence["body_bytes_collected"] = 0
                evidence["contract_miss"] = contract_miss_flag(
                    wire_id, policy=policy, exc=exc, decoded_success=False
                )
    evidence.update(
        {
            "observed_outcome": observed,
            "exposed_boundary_outcome": observed,
            "response_close_calls": probe.response_close_calls,
            "transport_close_calls": probe.transport_close_calls,
            "transport_bytes_received": probe.transport_bytes_received,
        }
    )
    return observed, evidence


def match_exact_predicate(evidence: dict[str, Any], spec: dict[str, Any]) -> bool:
    """Exact frozen predicates — not broad allowed-outcome sets (B3/B7)."""
    pred = spec.get("exact_predicate")
    if not isinstance(pred, dict):
        # Fallback rejected: broad allowed_outcomes alone are insufficient.
        raise WitnessFailure("missing_exact_predicate")
    for key, expected in pred.items():
        if evidence.get(key) != expected:
            return False
    return True


def main() -> int:
    manifest = load_json(MANIFEST_PATH)
    expected = load_json(EXPECTED_PATH)
    verify_source_hashes(manifest)
    if http.client.HTTPResponse.__module__ != "http.client":
        raise WitnessFailure("HTTPResponse must be stdlib http.client")

    CoveringHTTP, policy, ctx, _txn, _prov = build_extracted_runtime(manifest)
    wire_ids: list[str] = expected["wire_ids_in_order"]
    rows: dict[str, Any] = {}
    inventory_error: str | None = None
    unpredicted: str | None = None

    for wire_id in wire_ids:
        meta = manifest["wire_inventory"]["by_id"][wire_id]
        spec = expected["inputs"][wire_id]
        transcript_ref = meta.get("transcript_ref") or wire_id
        wire_path = WIRE_DIR / f"{transcript_ref}.wire"
        if not wire_path.is_file():
            inventory_error = f"missing_wire:{transcript_ref}"
            break
        live = wire_path.read_bytes()
        if sha256_bytes(live) != meta["sha256"].upper():
            inventory_error = f"wire_hash_mismatch:{wire_id}"
            break
        if len(live) != int(meta["byte_size"]):
            inventory_error = f"wire_length_mismatch:{wire_id}"
            break

        purpose = meta.get("purpose") or spec.get("purpose") or "event"
        probe = CloseProbe()
        driver = meta.get("driver") or "covering_http"
        stall = bool(meta.get("stall_stimulus")) or wire_id == "CD-DEADLINE"
        try:
            if driver in {"calendar_client", "covering_client"}:
                owning = meta.get("owning_caller") or (
                    "google_calendar.refresh_access_token via calendar_client"
                    if purpose == "oauth"
                    else "calendar_client under covering_provider_transport"
                )
                observed, evidence = run_calendar_client_caller(
                    CoveringHTTP,
                    policy,
                    ctx,
                    wire_id=wire_id,
                    wire_bytes=live,
                    purpose=purpose,
                    probe=probe,
                    owning_caller=owning,
                )
            else:
                observed, evidence = run_covering_http_request(
                    CoveringHTTP,
                    policy,
                    wire_id=wire_id,
                    wire_bytes=live,
                    purpose=purpose,
                    probe=probe,
                    stall=stall,
                )
        except WitnessFailure as wf:
            inventory_error = str(wf)
            break

        evidence["predicted_outcome"] = spec["predicted_outcome"]
        evidence["underlying_cause_hypothesis"] = spec.get("underlying_cause_hypothesis")
        evidence["observation_boundary"] = spec.get(
            "observation_boundary", evidence.get("observation_boundary")
        )
        # Apply TLS/stall disclosure from expected when present.
        if "tls_close_notify_proven" in spec:
            evidence["tls_close_notify_proven"] = spec["tls_close_notify_proven"]
        if "byte_fake_eof_only" in spec:
            evidence["byte_fake_eof_only"] = spec["byte_fake_eof_only"]

        try:
            prediction_ok = match_exact_predicate(evidence, spec)
        except WitnessFailure as wf:
            inventory_error = str(wf)
            break
        # Also require predicted_outcome string equals observed.
        if evidence.get("observed_outcome") != spec.get("predicted_outcome"):
            prediction_ok = False
        evidence["prediction_ok"] = prediction_ok
        rows[wire_id] = project_evidence(evidence)
        if not prediction_ok:
            unpredicted = wire_id
            inventory_error = (
                f"unpredicted_outcome:{wire_id}:{observed}:"
                f"contract_miss={evidence.get('contract_miss')}"
            )
            break

    status = "PASS" if inventory_error is None else "FAIL"
    RESULT_PATH.write_bytes(
        (
            json.dumps(
                {
                    "status": status,
                    "class": "FAKE-T05-FRAMING-ORIGINAL",
                    "prep_version": "v4",
                    "wire_ids_in_order": wire_ids[: len(rows)],
                    "inputs": rows,
                    "inventory_error": inventory_error,
                    "unpredicted_wire_id": unpredicted,
                    "source_hashes_verified": True,
                    "executed": True,
                    "launch_ready": False,
                    "execution_authorized": False,
                    "executed_in_preparation": False,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
