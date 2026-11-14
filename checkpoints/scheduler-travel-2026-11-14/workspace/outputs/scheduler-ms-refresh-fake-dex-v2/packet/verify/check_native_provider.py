#!/usr/bin/env python3
"""HELD fake-only checker for the NP-V-MS-REFRESH fixture increment (Matt prep v1).

AUTHORING ONLY. This file has not been imported, parsed, compiled or run. Each
later run needs Trish's explicit one-shot approval of the exact reviewed command
and hashes. The file name is kept so the byte-identical reviewed launcher
(launch_check.py D22C37E3...) and outer admission (verify_admission.py 7DCA32E2...)
can be reused unchanged.

Scope: the ACTUAL authored fixture helpers (candidate subjects) and the pinned
production URL builder (microsoft_calendar.py) are exercised against in-memory
fakes for app models, token crypto and HTTPSPeer. Standard library only. No
app/vendor imports, sockets, TLS, PKI, Docker, database, processes or network.
The only write is the exclusive result file.

Proof layers are labeled per control: raw_pin, extracted_text_identity,
extracted_behavior_fake, structural_source, actual_source_mutant. Nothing here
proves native OAuth, TLS, database persistence, or the shared-peer assumption.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import textwrap
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-ms-refresh-fake-prep-matt-v1"

SUBJECT_PINS = {
    "candidate/np_runner_entry.py": "CC4D49E758F22E5E34C0D6093946CA390BC95A4C320C3D92B24AD723FA8634FF",
    "candidate/np_auth_seed.py": "2ADFA3ADCFDA8DB4D9D32EDFC9950AF354CE29ADFA1B5A8162FD5182DC22ED05",
    "candidate/np_provider_transcript.py": "0AA3BC093711B7EEBADD1F23A80BF86F2B5AEAB4C1224014537BB051FDDCE52E",
    "candidate/np_receipts.py": "7F27A3C2CBCA73C27DCEC6C9DCF6277C7F131ACC3A561C4170636EAB5D5E24C7",
    "candidate/np_suite.py": "46C9443D13E4CA526DEE4BEF5747D65AA0549CA0FFA963A8F8EB44595485370D",
    "candidate/np_provider_peer.py": "5568AF73DD42FEB5B8E2FE4D723AD4FB0339CBF4B889F5472995ABC628F72A55",
    "source/np_runner_entry.py": "40A1BA8E9C3E320DD7DF9E06102CC29C0E1AFAAD4213EC0FECF9FE34455BF73F",
    "source/np_auth_seed.py": "66FEEA815C7B196A78117229F80769ADDF8428CB073A586B59E2D81491419150",
    "source/np_provider_transcript.py": "CFAB2D060BF03779A5B7BB7AF546F57124D5AF501CED6B93FFAAB76ED86AB6A3",
    "source/np_receipts.py": "69F59AF10FF5A6FAED469E4C93DCB128F741C50444CC31E37737EC4889B708FD",
    "source/np_suite.py": "AEC59FCDA058124FDF7265D41B8A660C4AD139CE13417F88FA637542CF9C1673",
    "production/microsoft_calendar.py": "6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF",
}

CONTROL_IDS = (
    "SUBJECT-PINS",
    "NONEXPIRED-AND-DIAGNOSTIC-PRESERVED",
    "TENANT-PATH-AGREEMENT",
    "OAUTH-ROUTE-TABLE",
    "REFRESH-INVENTORY-ORDER",
    "SEMANTIC-PERSISTENCE-ADMISSION",
    "SECRET-EXCLUSION-PROJECTION",
    "REGISTRY-MAPPING",
    "REFRESH-BODY-SHAPE",
    "ACTUAL-SOURCE-MUTANTS",
)

GRAPH_HOST = "graph.microsoft.com"
LOGIN_HOST = "login.microsoftonline.com"
EXPECTED_TOKEN_PATH = "/common/oauth2/v2.0/token"


class WitnessFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WitnessFailure(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


_TEXT: dict[str, str] = {}


def text(rel: str) -> str:
    if rel not in _TEXT:
        raise WitnessFailure(f"subject not admitted:{rel}")
    return _TEXT[rel]


# ---------------------------------------------------------------------------
# Extraction and isolated module loading (sys.modules saved AND restored)
# ---------------------------------------------------------------------------

def _single(nodes: list[Any], what: str) -> Any:
    require(len(nodes) == 1, f"expected exactly one {what}, found {len(nodes)}")
    return nodes[0]


def function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = _single([n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name],
                   f"function {name}")
    segment = ast.get_source_segment(source, node, padded=True)
    require(segment is not None, f"no source segment:{name}")
    return textwrap.dedent(segment)


def assign_source(source: str, name: str) -> str:
    """Module-level plain OR annotated assignment (e.g. NATIVE_CASES: tuple[...] = ...)."""
    tree = ast.parse(source)
    node = _single([n for n in tree.body
                    if (isinstance(n, ast.Assign) and len(n.targets) == 1
                        and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name)
                    or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                        and n.target.id == name and n.value is not None)],
                   f"assignment {name}")
    segment = ast.get_source_segment(source, node)
    require(segment is not None, f"no source segment:{name}")
    return segment


def exec_functions(source: str, names: tuple[str, ...], namespace: dict[str, Any], label: str,
                   mutation: tuple[str, str] | None = None) -> dict[str, Any]:
    code = "\n\n".join(function_source(source, name) for name in names)
    if mutation is not None:
        old, new = mutation
        require(code.count(old) == 1, f"mutation anchor not unique:{old!r}")
        code = code.replace(old, new)
    exec(compile(code, f"<extracted:{label}>", "exec"), namespace)
    for name in names:
        require(isinstance(namespace.get(name), types.FunctionType), f"extracted {name} not a function")
    return namespace


class ModuleSandbox:
    """Install fake modules temporarily; restore exact prior sys.modules entries."""

    def __init__(self) -> None:
        self._saved: dict[str, Any] = {}
        self._missing: set[str] = set()

    def put(self, name: str, module: types.ModuleType) -> None:
        if name not in self._saved and name not in self._missing:
            if name in sys.modules:
                self._saved[name] = sys.modules[name]
            else:
                self._missing.add(name)
        sys.modules[name] = module

    def restore(self) -> None:
        for name, module in self._saved.items():
            sys.modules[name] = module
        for name in self._missing:
            sys.modules.pop(name, None)
        self._saved.clear()
        self._missing.clear()


def load_module(name: str, source: str, sandbox: ModuleSandbox, mutation: tuple[str, str] | None = None
                ) -> types.ModuleType:
    """Execute a whole stdlib-only fixture module from its pinned subject text."""
    if mutation is not None:
        old, new = mutation
        require(source.count(old) == 1, f"mutation anchor not unique:{old!r}")
        source = source.replace(old, new)
    module = types.ModuleType(name)
    module.__file__ = f"<subject:{name}>"
    sandbox.put(name, module)
    exec(compile(source, f"<subject:{name}>", "exec"), module.__dict__)
    return module


def load_seed_and_transcript(transcript_mutation: tuple[str, str] | None = None
                             ) -> tuple[types.ModuleType, types.ModuleType, ModuleSandbox]:
    sandbox = ModuleSandbox()
    seed = load_module("np_auth_seed", text("candidate/np_auth_seed.py"), sandbox)
    transcript = load_module("np_provider_transcript", text("candidate/np_provider_transcript.py"),
                             sandbox, transcript_mutation)
    return seed, transcript, sandbox


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def check_subject_pins() -> dict[str, Any]:
    for rel, pin in SUBJECT_PINS.items():
        data = (SUBJECTS / rel).read_bytes()
        require(sha256_bytes(data) == pin, f"subject pin mismatch:{rel}")
        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
        _TEXT[rel] = data.decode("utf-8")
    return {"subjects": len(SUBJECT_PINS), "control_kind": "raw_pin", "observed": "PASS"}


def check_preserved() -> dict[str, Any]:
    preserved = (
        ("np_runner_entry.py", ("_run_np_v_ms_nonexpired", "_ms_provider_routes", "stop_payload",
                                "_install_token_terminal_observer", "_extract_token_rollback_ack",
                                "provision_disposable_schema", "build_registry_from_suite")),
        ("np_auth_seed.py", ("seed_browser_owner_with_subscriptions", "measure_subscription_coverage_state",
                             "fixture_settings", "derive_production_target_calendar_order")),
        ("np_provider_transcript.py", ("ms_nonexpired_connection_inventory", "ms_graph_identity_default_script",
                                       "ms_graph_identity_list_script", "ms_graph_calendar_view_empty_script",
                                       "ms_token_invalid_grant_script")),
        ("np_receipts.py", ("redact_mapping", "build_receipt", "case_result_receipt")),
        ("np_suite.py", ("check_oracles_immediate", "validate_inventory_counts", "registry_by_id")),
    )
    cases = {}
    for filename, names in preserved:
        for name in names:
            src = function_source(text(f"source/{filename}"), name)
            cand = function_source(text(f"candidate/{filename}"), name)
            require(src == cand, f"preserved function changed:{filename}:{name}")
            cases[f"{filename}:{name}"] = "PASS"
    native_src = assign_source(text("source/np_suite.py"), "NATIVE_CASES")
    native_cand = assign_source(text("candidate/np_suite.py"), "NATIVE_CASES")
    require(native_src == native_cand, "NATIVE_CASES registry changed")
    cases["np_suite.py:NATIVE_CASES"] = "PASS"
    seed_src = function_source(text("candidate/np_auth_seed.py"), "seed_browser_owner_with_subscriptions")
    require('encrypt_token(settings, "fixture-access-plaintext-not-for-receipt")' in seed_src,
            "seed access literal moved")
    require('encrypt_token(settings, "fixture-refresh-plaintext-not-for-receipt")' in seed_src,
            "seed refresh literal moved")
    cases["seed_literals_unchanged"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_text_identity", "observed": "PASS"}


def _production_token_url(tenant: str, mutation: tuple[str, str] | None = None) -> str:
    source = text("production/microsoft_calendar.py")
    namespace: dict[str, Any] = {}
    exec(compile(assign_source(source, "_LOGIN_BASE"), "<extracted:prod:_LOGIN_BASE>", "exec"), namespace)
    exec_functions(source, ("_normalize_tenant", "_token_url"), namespace, "prod", mutation)
    return namespace["_token_url"](namespace["_normalize_tenant"](tenant))


def check_tenant_path_agreement() -> dict[str, Any]:
    from urllib.parse import urlsplit

    seed, transcript, sandbox = load_seed_and_transcript()
    try:
        tenant = seed.FIXTURE_MS_TENANT
        fixture_path = transcript.MS_TOKEN_ENDPOINT_PATH
        prod = urlsplit(_production_token_url(tenant))
        require(prod.scheme == "https" and prod.hostname == LOGIN_HOST and prod.port is None,
                "production token URL host/scheme")
        require(prod.path == fixture_path == EXPECTED_TOKEN_PATH, "fixture path != production path")
        script = transcript.ms_token_success_script()
        require(script.steps[0].method == "POST" and script.steps[0].path == fixture_path,
                "success script path not derived")
        refused = 0
        for bad in (" common", "common/", "bad tenant!", "", "cömmon"):
            try:
                transcript.ms_token_endpoint_path(bad)
            except ValueError:
                refused += 1
        require(refused == 5, "fixture path builder accepted a non-normalized tenant")
        require(transcript.ms_token_endpoint_path("contoso-1") == "/contoso-1/oauth2/v2.0/token",
                "fixture path builder normalized-tenant shape")
        require(urlsplit(_production_token_url("contoso-1")).path == "/contoso-1/oauth2/v2.0/token",
                "production builder normalized-tenant shape")
    finally:
        sandbox.restore()
    return {"path": EXPECTED_TOKEN_PATH, "refused_tenants": 5,
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


class FakeHTTPSPeer:
    def __init__(self, *, hostname: str, address: str, port: int, ca_file: str) -> None:
        self.hostname, self.address, self.port, self.ca_file = hostname, address, port, ca_file


def _route_functions(mutation: tuple[str, str] | None = None) -> dict[str, Any]:
    sandbox = ModuleSandbox()
    policy = types.ModuleType("app.services.covering_transport_policy")
    policy.HTTPSPeer = FakeHTTPSPeer
    for name in ("app", "app.services"):
        sandbox.put(name, types.ModuleType(name))
    sandbox.put("app.services.covering_transport_policy", policy)
    namespace: dict[str, Any] = {"Any": Any}
    try:
        exec_functions(text("candidate/np_runner_entry.py"),
                       ("_ms_provider_routes", "_ms_refresh_provider_routes"), namespace, "routes", mutation)
        routes = namespace["_ms_refresh_provider_routes"](
            graph_hostname=GRAPH_HOST, token_hostname=LOGIN_HOST, dial_address="127.0.0.1",
            dial_port=443, ca_file="/tmp/np-provider-tls/ca.crt", token_path=EXPECTED_TOKEN_PATH)
        graph_only = namespace["_ms_provider_routes"](
            peer_hostname=GRAPH_HOST, dial_address="127.0.0.1", dial_port=443,
            ca_file="/tmp/np-provider-tls/ca.crt")
    finally:
        sandbox.restore()
    return {"routes": routes, "graph_only": graph_only}


def check_oauth_route_table() -> dict[str, Any]:
    out = _route_functions()
    routes, graph_only = out["routes"], out["graph_only"]
    shape = [(peer.hostname, prefix, kind) for peer, prefix, kind in routes]
    require(shape == [
        (GRAPH_HOST, "/v1.0/me/calendar", "identity"),
        (GRAPH_HOST, "/v1.0/me/calendars", "identity"),
        (GRAPH_HOST, "/v1.0/me/calendars/", "event"),
        (LOGIN_HOST, EXPECTED_TOKEN_PATH, "oauth"),
    ], f"refresh route table shape:{shape!r}")
    require([(p.hostname, x, k) for p, x, k in graph_only] == shape[:3], "graph-only table changed")
    token_peer = routes[3][0]
    require((token_peer.address, token_peer.port, token_peer.ca_file)
            == (routes[0][0].address, routes[0][0].port, routes[0][0].ca_file),
            "token peer must share address/port/CA")
    require(token_peer is not routes[0][0], "token route must use a distinct HTTPSPeer")
    require(sum(1 for _p, _x, k in routes if k == "oauth") == 1, "exactly one oauth route")
    return {"routes": len(shape), "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def _peer_response_bytes(step: Any, exchange_step_cls: Any) -> bytes:
    # Extracted code is compiled standalone (no __future__ annotations), so the
    # ExchangeStep annotation must resolve in the namespace.
    namespace: dict[str, Any] = {"ExchangeStep": exchange_step_cls}
    exec_functions(text("candidate/np_provider_peer.py"), ("_http_response_bytes",), namespace, "peer")
    return namespace["_http_response_bytes"](step)


def check_refresh_inventory_order() -> dict[str, Any]:
    seed, transcript, sandbox = load_seed_and_transcript()
    try:
        ids = ("cal-ms-default", "cal-np-other")
        scripts = transcript.ms_refresh_connection_inventory(identity_list_calendar_ids=ids, wire_calendar_ids=ids)
        script_ids = [s.script_id for s in scripts]
        require(script_ids == ["MS-TOKEN-SUCCESS", "MS-GRAPH-IDENTITY-DEFAULT", "MS-GRAPH-IDENTITY-LIST",
                               "MS-GRAPH-CALENDARVIEW-EMPTY:cal-ms-default",
                               "MS-GRAPH-CALENDARVIEW-EMPTY:cal-np-other"], f"inventory order:{script_ids!r}")
        heads = [(s.steps[0].method, s.steps[0].path) for s in scripts]
        require(heads == [("POST", EXPECTED_TOKEN_PATH), ("GET", "/v1.0/me/calendar"), ("GET", "/v1.0/me/calendars"),
                          ("GET", "/v1.0/me/calendars/cal-ms-default/calendarView"),
                          ("GET", "/v1.0/me/calendars/cal-np-other/calendarView")], f"request heads:{heads!r}")
        require(transcript.MS_REFRESH_EXCHANGE_COUNT == 5 == len(scripts), "exchange count")
        nonexpired = transcript.ms_nonexpired_connection_inventory(
            calendar_ids=ids, identity_list_calendar_ids=ids, wire_calendar_ids=ids)
        require(tuple(scripts[1:]) == tuple(nonexpired), "graph scripts must equal the NONEXPIRED inventory")
        body_step = scripts[0].steps[1]
        body = json.loads(body_step.body_template)
        require(body == {"token_type": "Bearer", "expires_in": seed.MS_REFRESH_EXPIRES_IN_SECONDS,
                         "access_token": seed.REFRESHED_MS_ACCESS_PLAINTEXT,
                         "refresh_token": seed.ROTATED_MS_REFRESH_PLAINTEXT}, "token body fields/values")
        wire = _peer_response_bytes(body_step, transcript.ExchangeStep)
        head, _sep, sent_body = wire.partition(b"\r\n\r\n")
        require(sent_body == body_step.body_template.encode("utf-8"), "peer must send body verbatim")
        require(f"Content-Length: {len(sent_body)}".encode("ascii") in head, "placeholder length rewrite")
        for bad in ((), ("only-one",)):
            try:
                transcript.ms_refresh_connection_inventory(identity_list_calendar_ids=ids, wire_calendar_ids=bad)
            except RuntimeError:
                continue
            raise WitnessFailure("inventory accepted a non-two calendar list")
    finally:
        sandbox.restore()
    return {"exchanges": 5, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


class FakeAccount:
    def __init__(self, access_enc: str | None, refresh_enc: str | None, expires: datetime | None) -> None:
        self.access_token_enc, self.refresh_token_enc, self.token_expires_at = access_enc, refresh_enc, expires


class FakeDB:
    def __init__(self, account: FakeAccount | None) -> None:
        self.account = account

    def get(self, model: Any, key: Any) -> Any:
        return self.account


_NONCE = [0]


def fake_encrypt(plain: str) -> str:
    """Randomized fake ciphertext (like Fernet): same plaintext, different bytes each time."""
    _NONCE[0] += 1
    return f"fk{_NONCE[0]:04d}:{plain.encode('utf-8').hex()}"


def fake_decrypt(_settings: Any, ciphertext: str) -> str:
    _prefix, _colon, hexed = ciphertext.partition(":")
    return bytes.fromhex(hexed).decode("utf-8")


def _measure_function(mutation: tuple[str, str] | None = None):
    sandbox = ModuleSandbox()
    for name in ("app", "app.services"):
        sandbox.put(name, types.ModuleType(name))
    models = types.ModuleType("app.models")
    models.CalendarAccount = FakeAccount
    crypto = types.ModuleType("app.services.token_crypto")
    crypto.decrypt_token = fake_decrypt
    sandbox.put("app.models", models)
    sandbox.put("app.services.token_crypto", crypto)
    seed = load_module("np_auth_seed", text("candidate/np_auth_seed.py"), sandbox,
                       mutation if mutation is not None else None)
    return seed, sandbox


def check_semantic_persistence() -> dict[str, Any]:
    seed, sandbox = _measure_function()
    cases = {}
    try:
        measure = seed.measure_account_credential_state
        t_plan = datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)
        t_check = t_plan + timedelta(minutes=2)
        refreshed_expiry = t_check + timedelta(seconds=3540)

        def run(access: str, refresh: str, expires: datetime | None, ref: datetime) -> dict[str, Any]:
            return measure(FakeDB(FakeAccount(fake_encrypt(access), fake_encrypt(refresh), expires)),
                           settings=None, account_id="acct", reference_instant=ref)

        before = run(seed.SEED_MS_ACCESS_PLAINTEXT, seed.SEED_MS_REFRESH_PLAINTEXT, t_plan - timedelta(minutes=5), t_plan)
        require(before["seed_access_match"] and before["seed_refresh_match"], "before seed match")
        require(not before["refreshed_access_match"] and not before["rotated_refresh_match"], "before refreshed")
        require(before["expiry_at_or_before_reference"] is True, "before expiry stale")
        cases["before_seed_state"] = "PASS"

        after = run(seed.REFRESHED_MS_ACCESS_PLAINTEXT, seed.ROTATED_MS_REFRESH_PLAINTEXT, refreshed_expiry, t_check)
        require(after["refreshed_access_match"] and after["rotated_refresh_match"], "after refreshed match")
        require(not after["seed_access_match"] and not after["seed_refresh_match"], "after seed cleared")
        require(after["expiry_after_reference_plus_skew"] is True, "after expiry advanced")
        cases["after_refreshed_state"] = "PASS"

        reencrypted = run(seed.SEED_MS_ACCESS_PLAINTEXT, seed.SEED_MS_REFRESH_PLAINTEXT, refreshed_expiry, t_check)
        require(reencrypted["access_ciphertext_sha16"] != before["access_ciphertext_sha16"],
                "fake must randomize ciphertext")
        require(not reencrypted["refreshed_access_match"] and reencrypted["seed_access_match"],
                "changed ciphertext with unchanged plaintext must NOT admit")
        cases["changed_ciphertext_unchanged_plaintext_refused"] = "PASS"

        wrong = run("wrong-access-synthetic", "wrong-refresh-synthetic", refreshed_expiry, t_check)
        require(not any(wrong[k] for k in ("seed_access_match", "seed_refresh_match",
                                           "refreshed_access_match", "rotated_refresh_match")), "wrong token")
        cases["wrong_token_refused"] = "PASS"

        no_rotation = run(seed.REFRESHED_MS_ACCESS_PLAINTEXT, seed.SEED_MS_REFRESH_PLAINTEXT, refreshed_expiry, t_check)
        require(no_rotation["refreshed_access_match"] and not no_rotation["rotated_refresh_match"],
                "missing rotation detected")
        cases["missing_rotation_refused"] = "PASS"

        short = run(seed.REFRESHED_MS_ACCESS_PLAINTEXT, seed.ROTATED_MS_REFRESH_PLAINTEXT,
                    t_check + timedelta(seconds=30), t_check)
        require(short["expiry_after_reference_plus_skew"] is False, "expiry at check+30s must not pass")
        naive = run(seed.REFRESHED_MS_ACCESS_PLAINTEXT, seed.ROTATED_MS_REFRESH_PLAINTEXT,
                    refreshed_expiry.replace(tzinfo=None), t_check)
        require(naive["expiry_after_reference_plus_skew"] is True, "naive UTC expiry treated as UTC")
        cases["invalid_expiry_refused"] = "PASS"

        for label, account, ref in (
            ("missing_expiry", FakeAccount(fake_encrypt("a"), fake_encrypt("b"), None), t_check),
            ("missing_ciphertext", FakeAccount(None, fake_encrypt("b"), refreshed_expiry), t_check),
            ("missing_account", None, t_check),
            ("naive_reference", FakeAccount(fake_encrypt("a"), fake_encrypt("b"), refreshed_expiry),
             t_check.replace(tzinfo=None)),
        ):
            try:
                measure(FakeDB(account), settings=None, account_id="acct", reference_instant=ref)
            except RuntimeError:
                cases[f"refuses_{label}"] = "PASS"
                continue
            raise WitnessFailure(f"measurement accepted {label}")
        cases["projection_has_no_plaintext"] = "PASS" if not any(
            isinstance(v, str) and (seed.REFRESHED_MS_ACCESS_PLAINTEXT in v or seed.SEED_MS_ACCESS_PLAINTEXT in v)
            for v in after.values()) else "FAIL"
        require(cases["projection_has_no_plaintext"] == "PASS", "measurement projected plaintext")
    finally:
        sandbox.restore()
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_secret_exclusion() -> dict[str, Any]:
    sandbox = ModuleSandbox()
    try:
        receipts = load_module("np_receipts", text("candidate/np_receipts.py"), sandbox)
        seed = load_module("np_auth_seed", text("candidate/np_auth_seed.py"), sandbox)
        state = {"seed_access_match": False, "seed_refresh_match": False, "refreshed_access_match": True,
                 "rotated_refresh_match": True, "access_ciphertext_sha16": "A" * 16,
                 "refresh_ciphertext_sha16": "B" * 16, "expiry": "2026-11-12T21:00:00+00:00",
                 "reference_instant": "2026-11-12T20:02:00+00:00", "expiry_at_or_before_reference": False,
                 "expiry_after_reference_plus_skew": True}
        receipt = receipts.case_result_receipt(
            case_id="NP-V-MS-REFRESH", passed=True, workers_joined=True, expected_unknown=False,
            observations={"owning_ms_refresh_joinedtls": "OBSERVED", "token_commit": "OBSERVED",
                          "persistence": "OBSERVED", "ms_oauth_endpoint_path": EXPECTED_TOKEN_PATH},
            t_plan_iso="t0", t_check_iso="t1",
            measured={"credential_state_before": dict(state), "credential_state_after": dict(state),
                      "token_terminal_sequence": [{"terminal": "COMMIT_ACKNOWLEDGED", "commit_requested": True},
                                                  {"terminal": "ROLLBACK_ACKNOWLEDGED", "commit_requested": False}],
                      "oauth_request_count": 1,
                      "access_token": seed.REFRESHED_MS_ACCESS_PLAINTEXT,
                      "refresh_token": seed.ROTATED_MS_REFRESH_PLAINTEXT,
                      "client_secret": "fixture-ms-client-secret-not-live"})
        serialized = json.dumps(receipt, sort_keys=True)
        for secret in (seed.REFRESHED_MS_ACCESS_PLAINTEXT, seed.ROTATED_MS_REFRESH_PLAINTEXT,
                       seed.SEED_MS_ACCESS_PLAINTEXT, "fixture-ms-client-secret-not-live"):
            require(secret not in serialized, "receipt projected a declared secret value")
        measured = receipt["measured"]
        require("credential_state_before" in measured and "credential_state_after" in measured,
                "credential state dropped")
        require(measured.get("token_terminal_sequence", [None])[0] == {"terminal": "COMMIT_ACKNOWLEDGED",
                                                                       "commit_requested": True},
                "terminal sequence dropped")
        require(receipt["observations"].get("token_commit") == "OBSERVED", "token_commit oracle dropped")
        require(receipt["observations"].get("ms_oauth_endpoint_path") == EXPECTED_TOKEN_PATH, "endpoint path dropped")
        require("access_token" not in measured and "refresh_token" not in measured, "raw token keys kept")
    finally:
        sandbox.restore()
    return {"control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_registry_mapping() -> dict[str, Any]:
    runner = text("candidate/np_runner_entry.py")
    tree = ast.parse(runner)
    node = _single([n for n in tree.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                    and n.target.id == "IMPLEMENTED_CASE_IDS"], "IMPLEMENTED_CASE_IDS")
    value = ast.get_source_segment(runner, node.value) or ""
    require(value == 'frozenset({"NP-V-MS-NONEXPIRED", "NP-V-MS-REFRESH"})', "implemented id set")
    mapper = function_source(runner, "_make_implemented_case")
    require('if case_id == "NP-V-MS-REFRESH":' in mapper and "return _run_np_v_ms_refresh()" in mapper,
            "REFRESH mapper binding")
    require('if case_id == "NP-V-MS-NONEXPIRED":' in mapper and "return _run_np_v_ms_nonexpired()" in mapper,
            "NONEXPIRED mapper binding")
    suite = text("candidate/np_suite.py")
    require('_o("owning_ms_refresh_joinedtls", "T06-SUCCESS-MICROSOFT"), _o("token_commit"), _o("persistence")'
            in suite, "REFRESH oracle declaration")
    require('"NP-V-MS-REFRESH": (' in suite, "REFRESH implementation note")
    return {"control_kind": "structural_source", "observed": "PASS"}


def check_refresh_body_shape() -> dict[str, Any]:
    body = function_source(text("candidate/np_runner_entry.py"), "_run_np_v_ms_refresh")
    required = (
        'case_id = "NP-V-MS-REFRESH"', "expired=True", "_require_production_ms_token_path(",
        "_ms_refresh_provider_routes(", "ms_refresh_connection_inventory(",
        'if overall_outcome != "success":', 'row.get("status") != "ok" or row.get("phase") != "import"',
        "_actual_token_terminals(native_terminals)", "RootOutcome.COMMIT_ACKNOWLEDGED.name",
        "RootOutcome.ROLLBACK_ACKNOWLEDGED.name", "if oauth_requests != 1:",
        '("POST", "oauth"),', "credential_after[\"refreshed_access_match\"] is not True",
        "expiry_after_reference_plus_skew", "is not CoveringRequestBudget.work_remaining",
        "if self.transport_factory is not JoinedTLS:", "retire_owned(join_seconds=5.0)",
        "first.get(\"path\") != MS_TOKEN_ENDPOINT_PATH",
    )
    for token in required:
        require(body.count(token) >= 1, f"refresh body missing:{token}")
    for banned in ("transport_factory=", "ControllableClock", "FixtureByteTransport", "ciphertext_sha16\"] !="):
        require(banned not in body, f"refresh body contains banned construct:{banned}")
    require(body.count("peer.retire_owned(join_seconds=5.0)") == 2, "one primary + one guarded cleanup retirement")
    return {"control_kind": "structural_source", "observed": "PASS"}


def _expect_detected(name: str, action, expected: type[BaseException], prefix: str | None) -> str:
    try:
        action()
    except expected as exc:
        if prefix is not None and not str(exc).startswith(prefix):
            raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
        return "DETECTED"
    except Exception:
        raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
    raise WitnessFailure(f"mutant survived:{name}")


def check_actual_source_mutants() -> dict[str, Any]:
    results = {}

    def ciphertext_only_mutant() -> None:
        seed, sandbox = _measure_function(
            ("\"refreshed_access_match\": access_plain == REFRESHED_MS_ACCESS_PLAINTEXT,",
             "\"refreshed_access_match\": bool(access_enc),"))
        try:
            state = seed.measure_account_credential_state(
                FakeDB(FakeAccount(fake_encrypt(seed.SEED_MS_ACCESS_PLAINTEXT), fake_encrypt("r"),
                                   datetime(2026, 11, 13, tzinfo=timezone.utc))),
                settings=None, account_id="acct", reference_instant=datetime(2026, 11, 12, tzinfo=timezone.utc))
            require(state["refreshed_access_match"] is False, "semantic oracle")
        finally:
            sandbox.restore()

    def legacy_path_mutant() -> None:
        _seed, transcript, sandbox = load_seed_and_transcript(
            ('return f"/{tenant}/oauth2/v2.0/token"', 'return "/oauth2/v2.0/token"'))
        try:
            from urllib.parse import urlsplit
            require(urlsplit(_production_token_url("common")).path == transcript.MS_TOKEN_ENDPOINT_PATH,
                    "path agreement")
        finally:
            sandbox.restore()

    def missing_token_script_mutant() -> None:
        _seed, transcript, sandbox = load_seed_and_transcript(
            ("scripts = (ms_token_success_script(),) + ms_nonexpired_connection_inventory(",
             "scripts = ms_nonexpired_connection_inventory("))
        try:
            ids = ("cal-ms-default", "cal-np-other")
            transcript.ms_refresh_connection_inventory(identity_list_calendar_ids=ids, wire_calendar_ids=ids)
        finally:
            sandbox.restore()

    def graph_only_route_mutant() -> None:
        out = _route_functions(("return tuple(graph_routes) + ((token_peer, token_path, \"oauth\"),)",
                                "return tuple(graph_routes)"))
        require(sum(1 for _p, _x, k in out["routes"] if k == "oauth") == 1, "oauth route")

    for name, action, expected, prefix in (
        ("ciphertext_only_persistence", ciphertext_only_mutant, WitnessFailure, "semantic oracle"),
        ("legacy_token_path", legacy_path_mutant, WitnessFailure, "path agreement"),
        ("missing_token_script", missing_token_script_mutant, RuntimeError, "MS refresh inventory must contain"),
        ("graph_only_routes", graph_only_route_mutant, WitnessFailure, "oauth route"),
    ):
        results[name] = _expect_detected(name, action, expected, prefix)
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
    require(expected.get("kind") == "ms-refresh-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "NONEXPIRED-AND-DIAGNOSTIC-PRESERVED": check_preserved,
        "TENANT-PATH-AGREEMENT": check_tenant_path_agreement,
        "OAUTH-ROUTE-TABLE": check_oauth_route_table,
        "REFRESH-INVENTORY-ORDER": check_refresh_inventory_order,
        "SEMANTIC-PERSISTENCE-ADMISSION": check_semantic_persistence,
        "SECRET-EXCLUSION-PROJECTION": check_secret_exclusion,
        "REGISTRY-MAPPING": check_registry_mapping,
        "REFRESH-BODY-SHAPE": check_refresh_body_shape,
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
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    nested = sum(len(v.get("cases") or v.get("mutants") or {"_": 1}) for v in controls.values())
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
