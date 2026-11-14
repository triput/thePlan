#!/usr/bin/env python3
"""T05 original framing witness prep v3 (AUTHORING ONLY — not executed).

B1–B7: selected AST extraction with wired module globals; fake target_transaction
exception only; purpose-exact predicates; caller-path drivers; bounded observations;
STOP on first unpredicted. Real http.client.HTTPResponse parser (no imitation).
launch_ready=false.
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
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

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
    "http_status",
    "body_bytes_collected",
    "response_close_calls",
    "transport_close_calls",
    "transport_bytes_received",
    "wire_sha256",
    "wire_byte_length",
    "contract_miss",
    "tls_close_notify_proven",
    "byte_fake_eof_only",
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
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"), module_ns)  # noqa: S102
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
        "httpx",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    policy_ns = new_module_namespace("app.services.covering_transport_policy")
    policy_syms = manifest["source_extraction"]["extracted_symbols"][
        "workspace/apps/api/app/services/covering_transport_policy.py"
    ]
    policy = extract_symbols(
        resolve_source("workspace/apps/api/app/services/covering_transport_policy.py"),
        policy_syms,
        policy_ns,
        provenance=provenance,
    )

    txn_ns = new_module_namespace("app.services.covering_target_transaction")
    txn_syms = manifest["source_extraction"]["extracted_symbols"][
        "workspace/apps/api/app/services/covering_target_transaction.py"
    ]
    txn = extract_symbols(
        resolve_source("workspace/apps/api/app/services/covering_target_transaction.py"),
        txn_syms,
        txn_ns,
        provenance=provenance,
    )

    join_ns = new_module_namespace("app.services.covering_joined_https")
    join_ns["JoinedTLS"] = type("JoinedTLS", (), {})  # unused when factory injected

    httpx_mod = sys.modules["httpx"]
    httpx_mod.Client = type("Client", (), {})  # unreachable in covering context path

    http_ns = new_module_namespace("app.services.covering_http_transport")
    http_ns.update(
        {
            "io": io,
            "json": json,
            "http": http,
            "httpx": httpx_mod,
            "urlencode": urllib.parse.urlencode,
            "CoveringTransportRefused": policy["CoveringTransportRefused"],
            "CoveringReauthorizationRequired": policy["CoveringReauthorizationRequired"],
            "CoveringRootOutcomeUnknown": txn["CoveringRootOutcomeUnknown"],
            "admit_covering_path": policy["admit_covering_path"],
            "JoinedTLS": join_ns["JoinedTLS"],
        }
    )
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
    ctx_ns["httpx"] = httpx_mod
    ctx_ns["CoveringTransportRefused"] = policy["CoveringTransportRefused"]
    ctx_ns["admit_covering_path"] = policy["admit_covering_path"]
    ctx_ns["urlsplit"] = urllib.parse.urlsplit
    ctx_syms = manifest["source_extraction"]["extracted_symbols"][
        "workspace/apps/api/app/services/covering_provider_context.py"
    ]
    ctx = extract_symbols(
        resolve_source("workspace/apps/api/app/services/covering_provider_context.py"),
        ctx_syms,
        ctx_ns,
        provenance=provenance,
    )

    return CoveringHTTP, policy, ctx, txn, provenance


class FakeTransport:
    def __init__(self, wire: bytes, probe: CloseProbe):
        self.wire = wire
        self.pos = 0
        self.sent = False
        self.probe = probe

    def open(self) -> None:
        return None

    def send(self, _wire: bytes) -> None:
        self.sent = True

    def receive(self, n: int) -> bytes:
        chunk = self.wire[self.pos : self.pos + n]
        self.pos += len(chunk)
        self.probe.transport_bytes_received += len(chunk)
        return chunk

    def close(self) -> None:
        self.probe.transport_close_calls += 1


def classify_exposed_exception(
    exc: BaseException, policy: dict[str, Any], *, purpose: str
) -> str | None:
    if isinstance(exc, policy["CoveringReauthorizationRequired"]):
        return "OBSERVED_SUCCESS"
    if isinstance(exc, policy["CoveringRootOutcomeUnknown"]):
        return "OBSERVED_UNKNOWN"
    if isinstance(exc, policy["CoveringTransportRefused"]):
        return "OBSERVED_REFUSE" if purpose != "oauth" else "OBSERVED_UNKNOWN"
    if isinstance(exc, json.JSONDecodeError):
        return "OBSERVED_PARSER_ERROR" if purpose != "oauth" else "OBSERVED_UNKNOWN"
    if isinstance(exc, http.client.HTTPException):
        return "OBSERVED_PARSER_ERROR"
    if isinstance(exc, (UnicodeDecodeError, ValueError)):
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


def contract_miss_for_success(
    wire_id: str,
    *,
    policy: dict[str, Any],
    exc: BaseException | None,
    decoded_success: bool,
) -> bool:
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


def run_covering_http_request(
    CoveringHTTP: Any,
    policy: dict[str, Any],
    *,
    wire_id: str,
    wire_bytes: bytes,
    purpose: str,
    probe: CloseProbe,
) -> tuple[str, dict[str, Any]]:
    HTTPSPeer = policy["HTTPSPeer"]
    ProviderCounter = policy["ProviderCounter"]
    approved_provider_limits = policy["approved_provider_limits"]
    limits = approved_provider_limits()
    counter = ProviderCounter(limits, lambda: 240.0)
    if purpose == "oauth":
        peer = HTTPSPeer(G_GAUTH, G_GADDR, 443, CA_FILE)
        routes = ((peer, TOKEN_EXACT, "oauth"),)
        method, url, data = "POST", GOOGLE_TOKEN_URL, {"grant_type": "refresh_token"}
    elif purpose == "identity":
        peer = HTTPSPeer(G_HOST, G_ADDR, 443, CA_FILE)
        routes = ((peer, "/v1.0/me", "identity"),)
        method, url, data = "GET", f"https://{G_HOST}/v1.0/me", None
    else:
        peer = HTTPSPeer(G_HOST, G_ADDR, 443, CA_FILE)
        routes = ((peer, EVENT_PREFIX, "event"),)
        method, url, data = (
            "GET",
            f"https://{G_HOST}{EVENT_PREFIX}primary/events",
            None,
        )

    def factory(_peer, _rem):
        return FakeTransport(wire_bytes, probe)

    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    evidence: dict[str, Any] = {
        "wire_id": wire_id,
        "purpose": purpose,
        "observation_boundary": "CoveringHTTP.request",
        "wire_sha256": sha256_bytes(wire_bytes),
        "wire_byte_length": len(wire_bytes),
        "tls_close_notify_proven": False,
        "byte_fake_eof_only": wire_id in {"CD-ORDERLY", "CD-ABRUPT"},
    }
    observed = "OBSERVED_UNKNOWN"
    exc_obj: BaseException | None = None
    http_status: int | None = None
    body_len = 0
    with instrument_response_close(probe):
        try:
            result = http.request(method, url, purpose=purpose, data=data)
            observed = "OBSERVED_SUCCESS"
            if isinstance(result, dict):
                body_len = len(json.dumps(result).encode("utf-8"))
            evidence["contract_miss"] = contract_miss_for_success(
                wire_id, policy=policy, exc=None, decoded_success=True
            )
        except BaseException as exc:
            exc_obj = exc
            classified = classify_exposed_exception(exc, policy, purpose=purpose)
            if classified is None:
                raise WitnessFailure(
                    f"UNEXPECTED_EXCEPTION:{wire_id}:{type(exc).__name__}"
                )
            observed = classified
            evidence["exception_type"] = type(exc).__name__
            evidence["contract_miss"] = contract_miss_for_success(
                wire_id, policy=policy, exc=exc, decoded_success=False
            )
    evidence["http_status"] = http_status
    evidence["body_bytes_collected"] = body_len
    evidence["response_close_calls"] = probe.response_close_calls
    evidence["transport_close_calls"] = probe.transport_close_calls
    evidence["transport_bytes_received"] = probe.transport_bytes_received
    evidence["observed_outcome"] = observed
    return observed, evidence


def run_caller_client(
    CoveringHTTP: Any,
    policy: dict[str, Any],
    ctx: dict[str, Any],
    *,
    wire_id: str,
    wire_bytes: bytes,
    purpose: str,
    probe: CloseProbe,
) -> tuple[str, dict[str, Any]]:
    limits = policy["approved_provider_limits"]()
    counter = policy["ProviderCounter"](limits, lambda: 240.0)
    peer = policy["HTTPSPeer"](G_HOST, G_ADDR, 443, CA_FILE)
    if purpose == "oauth":
        peer = policy["HTTPSPeer"](G_GAUTH, G_GADDR, 443, CA_FILE)
        routes = ((peer, TOKEN_EXACT, "oauth"),)
    else:
        routes = ((peer, EVENT_PREFIX, "event"),)
    transport = FakeTransport(wire_bytes, probe)

    def factory(_p, _r):
        return transport

    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=factory)
    covering_provider_transport = ctx["covering_provider_transport"]
    _CoveringClient = ctx["_CoveringClient"]
    observed = "OBSERVED_UNKNOWN"
    evidence: dict[str, Any] = {
        "wire_id": wire_id,
        "purpose": purpose,
        "observation_boundary": "_CoveringClient",
        "wire_sha256": sha256_bytes(wire_bytes),
        "wire_byte_length": len(wire_bytes),
    }
    with covering_provider_transport(http):
        client = _CoveringClient(http)
        with instrument_response_close(probe):
            try:
                if purpose == "oauth":
                    client.post(
                        GOOGLE_TOKEN_URL,
                        data={"grant_type": "refresh_token", "refresh_token": "x"},
                    )
                else:
                    client.get(f"https://{G_HOST}{EVENT_PREFIX}primary/events")
                observed = "OBSERVED_SUCCESS"
            except BaseException as exc:
                classified = classify_exposed_exception(exc, policy, purpose=purpose)
                if classified is None:
                    raise WitnessFailure(
                        f"UNEXPECTED_EXCEPTION:{wire_id}:{type(exc).__name__}"
                    )
                observed = classified
                evidence["exception_type"] = type(exc).__name__
    evidence.update(
        {
            "observed_outcome": observed,
            "response_close_calls": probe.response_close_calls,
            "transport_close_calls": probe.transport_close_calls,
            "transport_bytes_received": probe.transport_bytes_received,
        }
    )
    return observed, evidence


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
        if sha256_bytes(live) != meta["sha256"]:
            inventory_error = f"wire_hash_mismatch:{wire_id}"
            break
        if len(live) != meta["byte_size"]:
            inventory_error = f"wire_length_mismatch:{wire_id}"
            break

        purpose = meta.get("purpose") or spec.get("purpose") or "event"
        probe = CloseProbe()
        driver = meta.get("driver") or "covering_http"
        try:
            if driver == "covering_client":
                observed, evidence = run_caller_client(
                    CoveringHTTP,
                    policy,
                    ctx,
                    wire_id=wire_id,
                    wire_bytes=live,
                    purpose=purpose,
                    probe=probe,
                )
            else:
                observed, evidence = run_covering_http_request(
                    CoveringHTTP,
                    policy,
                    wire_id=wire_id,
                    wire_bytes=live,
                    purpose=purpose,
                    probe=probe,
                )
        except WitnessFailure as wf:
            inventory_error = str(wf)
            break

        allowed = spec.get("allowed_outcomes") or [spec["predicted_outcome"]]
        prediction_ok = observed in allowed
        evidence["predicted_outcome"] = spec["predicted_outcome"]
        evidence["underlying_cause_hypothesis"] = spec.get("underlying_cause_hypothesis")
        evidence["exposed_boundary_outcome"] = observed
        evidence["observation_boundary"] = spec.get(
            "observation_boundary", evidence.get("observation_boundary")
        )
        evidence["prediction_ok"] = prediction_ok
        rows[wire_id] = project_evidence(evidence)
        if not prediction_ok:
            unpredicted = wire_id
            inventory_error = f"unpredicted_outcome:{wire_id}:{observed}"
            break

    status = "PASS" if inventory_error is None else "FAIL"
    RESULT_PATH.write_bytes(
        (
            json.dumps(
                {
                    "status": status,
                    "class": "FAKE-T05-FRAMING-ORIGINAL",
                    "prep_version": "v3",
                    "wire_ids_in_order": wire_ids[: len(rows)],
                    "inputs": rows,
                    "inventory_error": inventory_error,
                    "unpredicted_wire_id": unpredicted,
                    "source_hashes_verified": True,
                    "executed": True,
                    "launch_ready": False,
                    "execution_authorized": False,
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
