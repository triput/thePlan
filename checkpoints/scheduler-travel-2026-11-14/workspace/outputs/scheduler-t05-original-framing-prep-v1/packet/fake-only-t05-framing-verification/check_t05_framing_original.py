#!/usr/bin/env python3
"""Fake-only T05 original framing verification (AUTHORING ONLY — not executed).

Drives unchanged CoveringHTTP.request (and selected caller paths) via fake byte
transport while using the pinned host stdlib http.client.HTTPResponse parser.
No hand-written HTTP body/framing imitation replaces the parser loop.

Records observed outcome classes vs frozen EXPECTED-ORIGINAL predictions.
CORRECTED recommendations are not scored here. launch_ready=false.
"""
from __future__ import annotations

import ast
import hashlib
import http.client
import io
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAYLOAD = ROOT / "payload"
MANIFEST_PATH = HERE / "INPUT-MANIFEST.json"
EXPECTED_PATH = HERE / "EXPECTED-ORIGINAL.json"
RESULT_PATH = HERE / "FAKE-T05-RESULT.json"
WIRE_DIR = HERE / "wire_transcripts"

G_HOST = "www.googleapis.com"
G_ADDR = "203.0.113.10"
G_OAUTH_HOST = "oauth2.googleapis.com"
G_OAUTH_ADDR = "203.0.113.11"
CA_FILE = "synthetic-public-ca.pem"
EVENT_PREFIX = "/calendar/v3/calendars/"
TOKEN_EXACT = "/token"

OUTCOME_FIELDS = (
    "observed_outcome",
    "prediction_ok",
    "predicted_outcome",
    "exception_type",
    "http_status",
    "body_bytes_collected",
    "response_closed",
    "transport_closed",
    "contract_miss",
)


class WitnessFailure(Exception):
    pass


@dataclass
class WireRow:
    wire_id: str
    observed_outcome: str
    prediction_ok: bool
    evidence: dict[str, Any] = field(default_factory=dict)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def project_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
  out: dict[str, Any] = {}
  for key in OUTCOME_FIELDS:
      val = evidence.get(key)
      if val is not None and not isinstance(val, (str, int, float, bool, type(None))):
          raise WitnessFailure(f"evidence field {key!r} not JSON primitive")
      out[key] = val
  return out


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes().decode("utf-8"))


def resolve_source(rel: str) -> Path:
    rel = rel.replace("\\", "/")
    if rel.startswith("bases/"):
        return PAYLOAD / "bases" / rel[len("bases/") :]
    if rel.startswith("workspace/"):
        return PAYLOAD / rel
    return PAYLOAD / rel


def verify_source_hashes(manifest: dict[str, Any]) -> None:
    for rel, expected in manifest["source_extraction"]["sources"].items():
        path = resolve_source(rel)
        if sha256_file(path) != expected.upper():
            raise WitnessFailure(f"source hash mismatch for {rel}")
    stdlib_root = Path(manifest["stdlib_provenance"]["lib_root"])
    for rel, expected in manifest["stdlib_provenance"]["modules"].items():
        path = stdlib_root / rel.replace("\\", "/")
        if sha256_file(path) != expected.upper():
            raise WitnessFailure(f"stdlib hash mismatch for {rel}")


def extract_covering_http(manifest: dict[str, Any]) -> Any:
    rel = "workspace/apps/api/app/services/covering_http_transport.py"
    path = resolve_source(rel)
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    tree = ast.parse(text, filename=str(path))
    names = set(manifest["source_extraction"]["extracted_symbols"][rel])
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names:
            selected.append(node)
    if "CoveringHTTP" not in names or not selected:
        raise WitnessFailure("CoveringHTTP extraction failed")
    mod = types.ModuleType("covering_http_transport_extracted")
    mod.__dict__["__builtins__"] = __builtins__
    code = compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec")
    exec(code, mod.__dict__)  # noqa: S102 — bounded pinned extract only
    return mod.__dict__["CoveringHTTP"]


def build_policy_stack() -> dict[str, Any]:
    for name in (
        "app",
        "app.services",
        "app.services.covering_transport_policy",
        "app.services.covering_target_transaction",
        "app.services.covering_http_transport",
        "app.services.covering_joined_https",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    policy_path = resolve_source("workspace/apps/api/app/services/covering_transport_policy.py")
    target_path = resolve_source("workspace/apps/api/app/services/covering_target_transaction.py")
    for mod_name, path in (
        ("app.services.covering_transport_policy", policy_path),
        ("app.services.covering_target_transaction", target_path),
    ):
        raw = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
        tree = ast.parse(raw, filename=str(path))
        exec(compile(tree, str(path), "exec"), sys.modules[mod_name].__dict__)  # noqa: S102
    return {
        "CoveringTransportRefused": sys.modules[
            "app.services.covering_transport_policy"
        ].__dict__["CoveringTransportRefused"],
        "CoveringReauthorizationRequired": sys.modules[
            "app.services.covering_transport_policy"
        ].__dict__["CoveringReauthorizationRequired"],
        "HTTPSPeer": sys.modules["app.services.covering_transport_policy"].__dict__["HTTPSPeer"],
        "ProviderCounter": sys.modules[
            "app.services.covering_transport_policy"
        ].__dict__["ProviderCounter"],
        "approved_provider_limits": sys.modules[
            "app.services.covering_transport_policy"
        ].__dict__["approved_provider_limits"],
        "CoveringRootOutcomeUnknown": sys.modules[
            "app.services.covering_target_transaction"
        ].__dict__["CoveringRootOutcomeUnknown"],
    }


class FakeTransport:
    def __init__(self, wire: bytes, *, stall: bool = False):
        self.wire = wire
        self.pos = 0
        self.sent = False
        self.stall = stall
        self._closed = False

    def open(self) -> None:
        return None

    def send(self, _wire: bytes) -> None:
        self.sent = True

    def receive(self, n: int) -> bytes:
        if self.stall and self.pos >= len(self.wire):
            return b""
        chunk = self.wire[self.pos : self.pos + n]
        self.pos += len(chunk)
        return chunk

    def close(self) -> None:
        self._closed = True


def classify_exception(exc: BaseException, policy: dict[str, Any]) -> str:
    if isinstance(exc, policy["CoveringReauthorizationRequired"]):
        return "OBSERVED_SUCCESS"
    if isinstance(exc, policy["CoveringTransportRefused"]):
        return "OBSERVED_REFUSE"
    if isinstance(exc, policy["CoveringRootOutcomeUnknown"]):
        return "OBSERVED_UNKNOWN"
    if isinstance(exc, (http.client.HTTPException, json.JSONDecodeError, UnicodeDecodeError, ValueError)):
        return "OBSERVED_PARSER_ERROR"
    name = type(exc).__name__
    if "Deadline" in name or "timeout" in name.lower():
        return "OBSERVED_STOP_GUARD"
    return "OBSERVED_PARSER_ERROR"


def observe_wire(
    CoveringHTTP: Any,
    policy: dict[str, Any],
    *,
    wire_id: str,
    wire_bytes: bytes,
    purpose: str,
    stall: bool,
) -> WireRow:
    CoveringTransportRefused = policy["CoveringTransportRefused"]
    ProviderCounter = policy["ProviderCounter"]
    approved_provider_limits = policy["approved_provider_limits"]
    HTTPSPeer = policy["HTTPSPeer"]

    limits = approved_provider_limits()
    counter = ProviderCounter(limits, lambda: 240.0)
    if purpose == "oauth":
        peer = HTTPSPeer(G_OAUTH_HOST, G_OAUTH_ADDR, 443, CA_FILE)
        routes = ((peer, TOKEN_EXACT, "oauth"),)
        method = "POST"
        url = f"https://{G_OAUTH_HOST}{TOKEN_EXACT}"
        data = {"grant_type": "refresh_token", "refresh_token": "x"}
    elif purpose == "event":
        peer = HTTPSPeer(G_HOST, G_ADDR, 443, CA_FILE)
        routes = ((peer, EVENT_PREFIX, "event"),)
        method = "GET"
        url = f"https://{G_HOST}{EVENT_PREFIX}primary/events"
        data = None
    else:
        peer = HTTPSPeer(G_HOST, G_ADDR, 443, CA_FILE)
        routes = ((peer, "/v1.0/me", "identity"),)
        method = "GET"
        url = f"https://{G_HOST}/v1.0/me"
        data = None

    transport_holder: dict[str, Any] = {}

    def transport_factory(_peer, _remaining):
        t = FakeTransport(wire_bytes, stall=stall)
        transport_holder["transport"] = t
        return t

    http = CoveringHTTP(counter=counter, routes=routes, transport_factory=transport_factory)
    evidence: dict[str, Any] = {
        "wire_id": wire_id,
        "purpose": purpose,
        "wire_sha256": sha256_file(WIRE_DIR / f"{wire_id}.wire"),
    }
    observed = "OBSERVED_UNKNOWN"
    try:
        http.request(method, url, purpose=purpose, data=data)
        observed = "OBSERVED_SUCCESS"
        evidence["contract_miss"] = wire_id in {"F02", "F03-oauth", "F05-oauth"}  # hypothesis flag
    except BaseException as exc:
        observed = classify_exception(exc, policy)
        evidence["exception_type"] = type(exc).__name__
        if observed == "OBSERVED_SUCCESS" and wire_id in {
            "F03-oauth",
            "F04-oauth",
            "F05b-oauth",
        }:
            evidence["contract_miss"] = False
        elif observed == "OBSERVED_SUCCESS" and wire_id in {"F02", "F05-oauth", "C-SEP-WRONG", "C-TRAILER-EOF"}:
            evidence["contract_miss"] = True
        else:
            evidence["contract_miss"] = False

    transport = transport_holder.get("transport")
    if isinstance(transport, FakeTransport):
        evidence["transport_closed"] = transport._closed
        evidence["bytes_returned"] = transport.pos
    expected = load_json(EXPECTED_PATH)["inputs"][wire_id]
    allowed = expected.get("allowed_outcomes") or [expected["predicted_outcome"]]
    prediction_ok = observed in allowed
    evidence["observed_outcome"] = observed
    evidence["predicted_outcome"] = expected["predicted_outcome"]
    evidence["prediction_ok"] = prediction_ok
    evidence.update(project_evidence(evidence))
    return WireRow(wire_id=wire_id, observed_outcome=observed, prediction_ok=prediction_ok, evidence=evidence)


def main() -> int:
    manifest = load_json(MANIFEST_PATH)
    expected = load_json(EXPECTED_PATH)
    verify_source_hashes(manifest)
    if http.client.HTTPResponse.__module__ != "http.client":
        raise WitnessFailure("HTTPResponse must be stdlib http.client")
    policy = build_policy_stack()
    CoveringHTTP = extract_covering_http(manifest)
    # Inject extracted module deps expected by CoveringHTTP source contract.
    jh = resolve_source("workspace/apps/api/app/services/covering_joined_https.py")
    join_mod = types.ModuleType("app.services.covering_joined_https")
    join_raw = jh.read_bytes().decode("utf-8").replace("\r\n", "\n")
    exec(compile(ast.parse(join_raw), str(jh), "exec"), join_mod.__dict__)  # noqa: S102
    sys.modules["app.services.covering_joined_https"] = join_mod
    for imp_name, imp_val in (
        ("CoveringTransportRefused", policy["CoveringTransportRefused"]),
        ("CoveringReauthorizationRequired", policy["CoveringReauthorizationRequired"]),
        ("CoveringRootOutcomeUnknown", policy["CoveringRootOutcomeUnknown"]),
        ("admit_covering_path", lambda _p: None),
        ("JoinedTLS", join_mod.__dict__["JoinedTLS"]),
    ):
        sys.modules["app.services.covering_http_transport"].__dict__.setdefault(imp_name, imp_val)

    wire_ids: list[str] = expected["wire_ids_in_order"]
    rows: dict[str, Any] = {}
    inventory_error: str | None = None
    unpredicted: list[str] = []
    for wire_id in wire_ids:
        meta = manifest["wire_inventory"]["by_id"][wire_id]
        purpose = meta.get("purpose") or "event"
        wire_path = HERE / meta["path"]
        stall = bool(meta.get("stall_stimulus"))
        try:
            row = observe_wire(
                CoveringHTTP,
                policy,
                wire_id=wire_id,
                wire_bytes=wire_path.read_bytes(),
                purpose=purpose,
                stall=stall,
            )
        except WitnessFailure as wf:
            inventory_error = str(wf)
            break
        rows[wire_id] = row.evidence
        if not row.prediction_ok:
            unpredicted.append(wire_id)

    status = "PASS" if inventory_error is None and not unpredicted else "FAIL"
    payload = {
        "status": status,
        "class": "FAKE-T05-FRAMING-ORIGINAL",
        "wire_ids_in_order": wire_ids,
        "inputs": rows,
        "inventory_error": inventory_error,
        "unpredicted_wire_ids": unpredicted or None,
        "source_hashes_verified": True,
        "executed": True,
        "parser": {
            "class": "http.client.HTTPResponse",
            "module": http.client.HTTPResponse.__module__,
            "host_parser_not_native": True,
        },
        "launch_ready": False,
        "execution_authorized": False,
    }
    RESULT_PATH.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
