#!/usr/bin/env python3
"""Fake-only behavioral harness for I01/I02 REVISE2-corrected6.

AST-extracts corrected fixture helpers from frozen workspace-payload bytes and
exercises negative/positive controls under fake dependencies. No app/vendor
imports, Docker, provider/DNS/proxy/app network, or database access.

Windows asyncio internal socket scope (Choice B — Dex p1794366344): N11's
three sequential asyncio.run calls use the default
WindowsProactorEventLoopPolicy. BaseProactorEventLoop._make_self_pipe creates
real internal wakeup sockets via socket.socketpair (or AF_INET loopback
bind/listen/connect/accept fallback). This is stdlib event-loop plumbing,
loopback-only, retired on loop.close — not app/provider sockets. Concurrent
bound: 2 connected sockets per live loop (ssock/csock); fallback may briefly
hold a third listening socket during pair construction. Sequential bound:
3 asyncio.run create/retire cycles in N11 (not stacked). No socket inventory
was executed during preparation. Fake PASS cannot waive native SQL/TLS/timing
proof.

Extraction rules (fail closed):
- required AST names missing → ControlFailure (preexisting globals do not satisfy)
- Lock and dataclass deps supplied BEFORE SharedTransportScript compile
- synthetic modules registered as real ModuleType in sys.modules; exec uses
  that exact module.__dict__ (dataclass _is_type needs
  sys.modules.get(cls.__module__).__dict__)
- per-module coherent __globals__; patches apply to that namespace
- SharedTransportScript is a class — patch visibility uses method
  SharedTransportScript.take.__globals__ (classes have no __globals__)
- class module identity is a separate __module__/sys.modules check
- synthetic __name__ kept for dataclass annotation module identity
- exact source path + symbol + sha256 provenance recorded
- emitted inventory order == EXPECTED.controls key order /
  EXPECTED.control_ids_in_order (run_controls may record N7 first)
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import tempfile
import threading
import time
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAYLOAD = ROOT / "workspace-payload"
FIXTURE = PAYLOAD / "fixture"
MANIFEST_PATH = HERE / "INPUT-MANIFEST.json"
EXPECTED_PATH = HERE / "EXPECTED-OUTPUT.json"
RESULT_PATH = HERE / "FAKE-BEHAVIORAL-RESULT.json"

PERMITTED = {
    "ast", "dataclasses", "hashlib", "json", "pathlib", "re", "sys",
    "threading", "time", "types", "typing", "uuid", "datetime", "copy",
    "tempfile", "__future__", "builtins",
}

PASS_RESULTS = {"PASS", "PASS_CONSTRUCT", "REFUSE", "REFUSE_OR_IDEMPOTENT"}


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_expected() -> dict[str, Any]:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def resolve_source(rel: str) -> Path:
    if rel == "runner-config.json":
        return PAYLOAD / "runner-config.json"
    if rel.startswith("fixture/"):
        return FIXTURE / Path(rel).name
    return PAYLOAD / rel


def verify_source_hashes(manifest: dict[str, Any]) -> None:
    for rel, expected in manifest["source_extraction"]["sources"].items():
        path = resolve_source(rel)
        actual = sha256_file(path)
        if actual != expected.upper():
            raise ControlFailure(f"source hash mismatch for {rel}: {actual} != {expected}")


def install_fake_modules() -> None:
    class CoveringTransportRefused(Exception):
        pass

    transport_policy = types.ModuleType("app.services.covering_transport_policy")
    transport_policy.CoveringTransportRefused = CoveringTransportRefused

    for name in (
        "app",
        "app.api",
        "app.api.deps",
        "app.api.errors",
        "app.api.middleware",
        "app.api.middleware.covering_ingress",
        "app.models",
        "app.models.enums",
        "app.scheduler",
        "app.scheduler.calendar_freshness",
        "app.services",
        "app.services.agent_credentials",
        "app.services.passwords",
        "app.services.token_crypto",
        "app.services.covering_http_dispatch",
        "app.services.covering_release_plan",
        "app.services.covering_transport_policy",
        "app.services.covering_target_transaction",
        "app.services.covering_domain_dispatch",
        "app.services.covering_request_budget",
        "app.services.covering_http_transport",
        "app.services.covering_native_orm_factory",
        "app.services.covering_parent_adapter",
        "app.services.covering_role_connector",
        "app.services.covering_domain_adapters",
        "app.services.scheduling_revision",
        "app.services.covering_refresh",
        "app.config",
        "tests",
        "tests.support",
        "tests.support.assessment_sql_fixture",
        "itsdangerous",
        "sqlalchemy",
        "sqlalchemy.orm",
        "fastapi",
        "fastapi.middleware",
        "fastapi.middleware.cors",
        "fastapi.responses",
        "starlette",
        "starlette.middleware",
        "starlette.middleware.sessions",
        "starlette.testclient",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    sys.modules["app.services.covering_transport_policy"] = transport_policy

    errors = sys.modules["app.api.errors"]

    class ApiError(Exception):
        def __init__(self, status_code: int, detail: str, code: str, **extra: object) -> None:
            self.status_code = status_code
            self.content: dict[str, object] = {"detail": detail, "code": code, **extra}

    errors.ApiError = ApiError  # type: ignore[attr-defined]
    errors.register_exception_handlers = lambda app: None  # type: ignore[attr-defined]


def new_module_namespace(module_name: str, shared: dict[str, Any]) -> dict[str, Any]:
    """Register a real ModuleType at the synthetic name; return module.__dict__.

    Dataclass ``_is_type`` resolves annotations via
    ``sys.modules.get(cls.__module__).__dict__`` — an ordinary dict alone is
    insufficient. Extracted functions close over this exact ``module.__dict__``
    so later patches to the namespace remain visible to those callables.
    """
    module = types.ModuleType(module_name)
    module.__dict__.update(shared)
    module.__dict__["__name__"] = module_name
    module.__dict__["__builtins__"] = __builtins__
    sys.modules[module_name] = module
    # Identity check: callers must exec against this exact dict object.
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
    """Parse source AST and exec selected top-level defs into module_ns.

    FAIL CLOSED: every requested name must appear as a top-level def/assign in
    the AST. Preexisting keys in module_ns do NOT satisfy missing AST names.
    ``module_ns`` must be the ``__dict__`` of the ModuleType registered under
    ``module_ns['__name__']`` in ``sys.modules``.
    """
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
    # Execute against the exact registered ModuleType.__dict__.
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
            source_path=str(source_path.relative_to(PAYLOAD)).replace("\\", "/"),
            source_sha256=sha256_bytes(raw),
            names=list(names),
            module_name=module_name,
        )
    )
    return out


def host_case_id_ok(case_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_-]{1,79}", case_id))


def expected_control_ids(expected: dict[str, Any]) -> list[str]:
    """Single deterministic ordered contract from EXPECTED-OUTPUT metadata."""
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
    results: list[ControlResult],
    expected: dict[str, Any],
) -> None:
    """Exact control inventory: IDs, no duplicates, all pos/neg present, outcomes.

    Order of *emission* may differ from EXPECTED (run_controls records N7 first);
    membership and per-ID results are gated here. Ordered contract is frozen on
    the emitted result payload (reordered to EXPECTED) and launcher result gate.
    """
    controls_expected = expected.get("controls") or {}
    expected_ids = expected_control_ids(expected)
    actual_ids = [r.control_id for r in results]
    if len(actual_ids) != len(set(actual_ids)):
        dups = sorted({cid for cid in actual_ids if actual_ids.count(cid) > 1})
        raise ControlFailure(f"duplicate control results: {dups}")
    missing = [cid for cid in expected_ids if cid not in actual_ids]
    extra = [cid for cid in actual_ids if cid not in expected_ids]
    if missing or extra:
        raise ControlFailure(
            f"control inventory mismatch missing={missing!r} extra={extra!r}"
        )
    by_id = {r.control_id: r for r in results}
    for cid, spec in controls_expected.items():
        want = spec["result"]
        got = by_id[cid].result
        if got != want:
            raise ControlFailure(
                f"control {cid} outcome {got!r} != expected {want!r} "
                f"({by_id[cid].detail})"
            )
        if got == "FAIL" or got not in PASS_RESULTS:
            raise ControlFailure(f"control {cid} not an accepted outcome: {got!r}")


def run_controls(extracted: dict[str, Any], modules: dict[str, dict[str, Any]]) -> list[ControlResult]:
    results: list[ControlResult] = []

    def record(cid: str, result: str, detail: str = "") -> None:
        results.append(ControlResult(cid, result, detail))

    inverted = extracted["inverted_subscription_ids"]
    production_ordered = extracted["production_ordered_calendar_ids"]
    SharedTransportScript = extracted["SharedTransportScript"]
    google_event_empty_script = extracted["google_event_empty_script"]
    AttemptCleanup = extracted["AttemptCleanup"]
    assert_subscription_ids_count_error = extracted["assert_subscription_ids_count_error"]
    assert_ordering_request_ids = extracted["assert_ordering_request_ids"]
    attach_cleanup_failures_to_primary = extracted["attach_cleanup_failures_to_primary"]
    resolve_attempt_outcome = extracted["resolve_attempt_outcome"]
    assert_c09_disconnect_evidence = extracted["assert_c09_disconnect_evidence"]
    I02Barriers = extracted["I02Barriers"]
    GENERATION_MISMATCH_CAUSE = extracted["GENERATION_MISMATCH_CAUSE"]
    await_mutation_admission = extracted["await_mutation_admission"]
    assert_intended_subscription_diagnostic = extracted[
        "assert_intended_subscription_diagnostic"
    ]
    load_c06_gate_receipt = extracted["load_c06_gate_receipt"]
    C06GateError = extracted["C06GateError"]
    DisconnectInjectControl = extracted["DisconnectInjectControl"]
    BoundedASGIResponse = extracted["BoundedASGIResponse"]
    CoveringTransportRefused = extracted["CoveringTransportRefused"]
    SuiteStop = extracted["SuiteStop"]

    # --- P / N7 UUID actual tokens via extracted inverted_subscription_ids ---
    try:
        c01 = inverted(case_token="i01c01")
        c10 = inverted(case_token="i01c10")
        assert len(c01) == 2 and len(c10) == 2
        assert c01[0] != c01[1] and c10[0] != c10[1]
        assert set(map(str, c01)).isdisjoint(set(map(str, c10)))
        assert sorted(c01, key=str) != c01
        for item in c01 + c10:
            text = str(item)
            assert all(ch in "0123456789abcdef-" for ch in text)
        record("N7", "PASS_CONSTRUCT", "i01c01/i01c10 hex-safe inverted pairs")
        record("P_UUID_actual_tokens", "PASS")
    except Exception as exc:
        record("N7", "FAIL", repr(exc))
        record("P_UUID_actual_tokens", "FAIL", repr(exc))

    # --- N8 / P script order via extracted SharedTransportScript ---
    try:
        planted = inverted(case_token="i01c01")
        smap = {str(planted[0]): "cal-i01-c01-0", str(planted[1]): "cal-i01-c01-1"}
        ordered = production_ordered(subscription_ids=planted, subscription_calendar_map=smap)
        assert ordered[0] == "cal-i01-c01-1"
        assert ordered[1] == "cal-i01-c01-0"
        script = [google_event_empty_script(calendar_id=c) for c in ordered]
        shared = SharedTransportScript(script=script)
        shared.take(
            "GET",
            f"https://www.googleapis.com/calendar/v3/calendars/{ordered[0]}/events",
            "",
        )
        refused = False
        try:
            shared.take(
                "GET",
                f"https://www.googleapis.com/calendar/v3/calendars/{ordered[0]}/events",
                "",
            )
        except CoveringTransportRefused:
            refused = True
        if not refused:
            raise ControlFailure("expected wrong-order refuse")
        shared2 = SharedTransportScript(script=list(script))
        bad = False
        try:
            shared2.take(
                "GET",
                f"https://www.googleapis.com/calendar/v3/calendars/{ordered[1]}/events",
                "",
            )
        except CoveringTransportRefused:
            bad = True
        if not bad:
            raise ControlFailure("expected initial wrong-order refuse")
        record("N8", "REFUSE", "wrong script order refused by SharedTransportScript")
        record("P_script_production_order", "PASS")
    except Exception as exc:
        record("N8", "FAIL", repr(exc))
        record("P_script_production_order", "FAIL", repr(exc))

    # --- N9 / P C07 IDs ---
    try:
        assert host_case_id_ok("I01-C07A") and host_case_id_ok("I01-C07B")
        assert not host_case_id_ok("I01-C07a")
        assert not host_case_id_ok("I01-C07b")
        cfg = json.loads((PAYLOAD / "runner-config.json").read_text(encoding="utf-8"))
        assert "I01-C07A" in cfg["case_ids"] and "I01-C07B" in cfg["case_ids"]
        assert "I01-C07a" not in cfg["case_ids"] and "I01-C07b" not in cfg["case_ids"]
        record("N9", "REFUSE", "legacy lowercase rejected; uppercase accepted")
        record("P_C07_uppercase_ids", "PASS")
    except Exception as exc:
        record("N9", "FAIL", repr(exc))
        record("P_C07_uppercase_ids", "FAIL", repr(exc))

    # --- N12 / P C03 count types via extracted assert_subscription_ids_count_error ---
    class FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    try:
        good_short = FakeResp(
            422, {"detail": [{"type": "too_short", "loc": ["body", "subscription_ids"]}]}
        )
        assert_subscription_ids_count_error(good_short, expected_type="too_short")
        good_long = FakeResp(
            422, {"detail": [{"type": "too_long", "loc": ["body", "subscription_ids"]}]}
        )
        assert_subscription_ids_count_error(good_long, expected_type="too_long")
        unrelated = FakeResp(
            422, {"detail": [{"type": "missing", "loc": ["body", "window_start"]}]}
        )
        refused = False
        try:
            assert_subscription_ids_count_error(unrelated, expected_type="too_short")
        except AssertionError:
            refused = True
        if not refused:
            raise ControlFailure("unrelated 422 was accepted")
        dup = FakeResp(
            422, {"detail": [{"type": "value_error", "loc": ["body", "subscription_ids"]}]}
        )
        refused2 = False
        try:
            assert_subscription_ids_count_error(dup, expected_type="too_short")
        except AssertionError:
            refused2 = True
        if not refused2:
            raise ControlFailure("wrong-type 422 accepted as too_short")
        record("N12", "REFUSE", "unrelated 422 rejected by extracted count assert")
        record("P_C03_count_types", "PASS")
    except Exception as exc:
        record("N12", "FAIL", repr(exc))
        record("P_C03_count_types", "FAIL", repr(exc))

    # --- N6 / P gate idempotent via extracted AttemptCleanup.stop_gate ---
    try:
        cleanup = AttemptCleanup()
        cleanup.gate_stop = threading.Event()
        cleanup.stop_gate(limit=0.1)
        first = cleanup.gate_retirement
        cleanup.stop_gate(limit=0.1)
        second = cleanup.gate_retirement
        assert first == "joined" and second == "joined"
        record("N6", "REFUSE_OR_IDEMPOTENT", "second stop_gate no-op")
        record("P_gate_idempotent_second_stop", "PASS")
    except Exception as exc:
        record("N6", "FAIL", repr(exc))
        record("P_gate_idempotent_second_stop", "FAIL", repr(exc))

    # --- N1 dual fault primary preservation via extracted attach + resolve ---
    try:
        primary = RuntimeError("primary-boom")
        cleanup = AttemptCleanup()
        cleanup.cleanup_failures = [{"kind": "AliasRestoreError"}]
        cleanup.teardown_completed = True
        cleanup.teardown_ok = False
        attach_cleanup_failures_to_primary(primary, cleanup.cleanup_failures)
        refused = False
        try:
            resolve_attempt_outcome(
                "N1",
                result={"passed": True},
                primary=primary,
                suite_stop=None,
                cleanup=cleanup,
            )
        except RuntimeError as exc:
            if exc is primary and getattr(primary, "fixture_cleanup_failures", None):
                refused = True
            else:
                raise
        if not refused:
            raise ControlFailure("primary was not preserved/raised")
        assert type(primary).__name__ == "RuntimeError"
        assert getattr(primary, "fixture_cleanup_failures") == [
            {"kind": "AliasRestoreError"}
        ]
        record("N1", "REFUSE", "primary preserved with cleanup attached via extract")
    except Exception as exc:
        record("N1", "FAIL", repr(exc))

    # --- N2 actual I02 close/error-finalization (not AttemptCleanup stand-in) ---
    try:
        select_i02_primary = extracted["select_i02_primary"]
        record_observer_close_failure = extracted["record_observer_close_failure"]
        close_preserving_primary = extracted["close_preserving_primary"]
        run_verification_query_with_close = extracted["run_verification_query_with_close"]
        I02Evidence = extracted["I02Evidence"]

        # Dual-fault A: assessment worker primary + observer.close failure.
        evidence_a = I02Evidence()
        assessment_boom = RuntimeError("assessment-worker-boom")
        record_observer_close_failure(evidence_a, RuntimeError("ObserverCloseError"))
        primary_a = select_i02_primary(
            owner_primary=RuntimeError("I02 mutator result/commit missing"),
            mutator_errors=[],
            assessment_errors=[assessment_boom],
            cleanup_failures=list(evidence_a.cleanup_failures),
        )
        if primary_a is not assessment_boom:
            raise ControlFailure("assessment worker primary not preserved over cleanup/owner")
        if not getattr(assessment_boom, "fixture_cleanup_failures", None):
            raise ControlFailure("observer cleanup secondary not attached to worker primary")

        # Dual-fault B: mutator worker primary wins over owner result/commit missing.
        mutator_boom = RuntimeError("mutator-worker-boom")
        primary_b = select_i02_primary(
            owner_primary=RuntimeError("I02 mutator result/commit missing"),
            mutator_errors=[mutator_boom],
            assessment_errors=[],
            cleanup_failures=[],
        )
        if primary_b is not mutator_boom:
            raise ControlFailure("mutator worker primary not preserved over owner generic")

        # Cleanup-only still rejects PASS.
        evidence_c = I02Evidence()
        record_observer_close_failure(evidence_c, RuntimeError("ObserverCloseOnly"))
        primary_c = select_i02_primary(
            owner_primary=None,
            mutator_errors=[],
            assessment_errors=[],
            cleanup_failures=list(evidence_c.cleanup_failures),
        )
        if primary_c is None or "cleanup_failures" not in str(primary_c):
            raise ControlFailure("cleanup-only observer close incorrectly PASSed")

        # Dual-fault D: verification query + close via actual helper + fake factory.
        class _FakeSubQuery:
            def filter(self, *_a, **_k):
                return self

            def populate_existing(self):
                return self

            def one(self):
                raise RuntimeError("verify-query-boom")

        class _FakeSession:
            def query(self, *_a, **_k):
                return _FakeSubQuery()

        class _FakeFactory:
            def __init__(self) -> None:
                self.closed = False

            def open_setup_session(self):
                return _FakeSession()

            def close(self, _session):
                self.closed = True
                raise RuntimeError("verify-close-boom")

        class _FakeModel:
            id = "sub-1"

        fake_factory = _FakeFactory()
        sub, verify_primary = run_verification_query_with_close(
            factory=fake_factory,
            subscription_id="sub-1",
            subscription_model=_FakeModel,
        )
        if sub is not None:
            raise ControlFailure("dual-fault verify unexpectedly returned subscription")
        if verify_primary is None or "verify-query-boom" not in str(verify_primary):
            raise ControlFailure("verify query primary lost to close failure")
        attached = getattr(verify_primary, "fixture_cleanup_failures", None) or []
        if not any(item.get("kind") == "RuntimeError" for item in attached):
            raise ControlFailure("verify close secondary not attached")

        # Close-only via close_preserving_primary still rejects.
        close_only = close_preserving_primary(
            lambda: (_ for _ in ()).throw(RuntimeError("close-only-boom")),
            primary=None,
        )
        if close_only is None or "cleanup/close failure" not in str(close_only):
            raise ControlFailure("close-only failure incorrectly PASSed")

        # Negative E: owner-primary + worker-close cleanup only → preserve owner.
        # Worker factory.close must land in cleanup_failures, not mutator_errors.
        owner_independent = RuntimeError(
            "I02 observer failed to capture holder/waiter/blocking evidence"
        )
        primary_e = select_i02_primary(
            owner_primary=owner_independent,
            mutator_errors=[],
            assessment_errors=[],
            cleanup_failures=[
                {"kind": "RuntimeError", "message": "mutator-factory-close-boom"}
            ],
        )
        if primary_e is not owner_independent:
            raise ControlFailure(
                "owner-primary replaced by worker-close cleanup secondary"
            )
        attached_e = getattr(owner_independent, "fixture_cleanup_failures", None) or []
        if not any(
            item.get("message") == "mutator-factory-close-boom" for item in attached_e
        ):
            raise ControlFailure("worker-close cleanup not attached to owner primary")

        # Negative F: worker operational primary + observer-close (cleanup secondary).
        worker_op = RuntimeError("mutator-operational-boom")
        evidence_f = I02Evidence()
        record_observer_close_failure(evidence_f, RuntimeError("ObserverCloseSecondary"))
        primary_f = select_i02_primary(
            owner_primary=RuntimeError("I02 mutator result/commit missing"),
            mutator_errors=[worker_op],
            assessment_errors=[],
            cleanup_failures=list(evidence_f.cleanup_failures),
        )
        if primary_f is not worker_op:
            raise ControlFailure(
                "worker operational primary not preserved with observer-close"
            )
        if not getattr(worker_op, "fixture_cleanup_failures", None):
            raise ControlFailure("observer-close secondary missing on worker primary")

        record(
            "N2",
            "REFUSE",
            "I02 select operational-vs-cleanup; owner+worker-close; worker+observer-close; verify-close dual-faults",
        )
    except Exception as exc:
        record("N2", "FAIL", repr(exc))

    # --- N3 failure release without commit via extracted await_mutation_admission ---
    try:
        barriers = I02Barriers()
        committed = {"value": False}

        def mutator():
            admitted = await_mutation_admission(barriers, join_limit=2.0)
            if admitted:
                committed["value"] = True
            barriers.mutation_committed.set()

        t = threading.Thread(target=mutator)
        t.start()
        barriers.retire_mutator.set()
        barriers.release_hold.set()
        t.join(2.0)
        assert committed["value"] is False
        record("N3", "REFUSE", "failure wake-up did not commit via await_mutation_admission")
    except Exception as exc:
        record("N3", "FAIL", repr(exc))

    # --- P admit mutation commits via same extracted path ---
    try:
        barriers = I02Barriers()
        committed = {"value": False}

        def mutator():
            admitted = await_mutation_admission(barriers, join_limit=2.0)
            if admitted:
                committed["value"] = True
            barriers.mutation_committed.set()

        t = threading.Thread(target=mutator)
        t.start()
        barriers.admit_mutation.set()
        t.join(2.0)
        assert committed["value"] is True
        record("P_admit_mutation_commits", "PASS")
    except Exception as exc:
        record("P_admit_mutation_commits", "FAIL", repr(exc))

    # --- N4 / N5 via extracted assert_intended_subscription_diagnostic oracle ---
    try:
        intended = "aaaaaaaa-0000-4000-8000-000000000001"
        db_cause = GENERATION_MISMATCH_CAUSE

        class Diag:
            def __init__(self, cause: str, event_id: str) -> None:
                self.cause = cause
                self.event_id = event_id

        # N4 missing intended diagnostic — must refuse; db_cause not a substitute
        refused_n4 = False
        try:
            assert_intended_subscription_diagnostic(
                intended_subscription_id=intended,
                blocking_diagnostics=[],
                db_mismatch_observation=db_cause,
            )
        except RuntimeError as exc:
            if "missing/wrong intended-subscription final diagnostic" in str(exc):
                refused_n4 = True
            else:
                raise
        if not refused_n4:
            raise ControlFailure("N4 missing diagnostic incorrectly accepted")
        record("N4", "REFUSE", "missing final diagnostic refused by extracted oracle")

        # N5 wrong cause — refuse even if DB matches required cause
        refused_n5 = False
        try:
            assert_intended_subscription_diagnostic(
                intended_subscription_id=intended,
                blocking_diagnostics=[
                    Diag("calendar_coverage_stale", intended),
                ],
                db_mismatch_observation=db_cause,
            )
        except RuntimeError as exc:
            if "missing/wrong intended-subscription final diagnostic" in str(exc):
                refused_n5 = True
            else:
                raise
        if not refused_n5:
            raise ControlFailure("N5 wrong cause incorrectly accepted")
        record("N5", "REFUSE", "wrong final diagnostic refused by extracted oracle")
    except Exception as exc:
        record("N4", "FAIL", repr(exc))
        record("N5", "FAIL", repr(exc))

    # --- N10 missing/wrong observations: gate + lock/budget/transport guards ---
    try:
        assert_i02_lock_observations = extracted["assert_i02_lock_observations"]
        assert_budget_identity_observations = extracted[
            "assert_budget_identity_observations"
        ]
        assert_transport_coverage_observations = extracted[
            "assert_transport_coverage_observations"
        ]
        I02Evidence = extracted["I02Evidence"]

        def _write_gate(root: Path, stem: str, payload: dict) -> None:
            path = root / f"{stem}.result.json"
            path.write_text(json.dumps(payload, sort_keys=True), encoding="ascii")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = {
                "complete": True,
                "backend_tag": "COMMIT",
                "backend_idle": True,
                "terminal_response_bytes_forwarded": 0,
                "fault": "acknowledgment_withheld",
            }
            _write_gate(root, "I01-C06-OK", good)
            loaded = load_c06_gate_receipt(artifact_stem="I01-C06-OK", root=root)
            if loaded.get("complete") is not True:
                raise ControlFailure("positive gate receipt not accepted")

            # Identifiable negative subcases for gate fields.
            for stem, payload, needle in (
                (
                    "I01-C06-INCOMPLETE",
                    {**good, "complete": False, "mapping_only": True},
                    "incomplete",
                ),
                (
                    "I01-C06-TAG",
                    {**good, "backend_tag": "WRONG"},
                    "backend_tag",
                ),
                (
                    "I01-C06-IDLE",
                    {**good, "backend_idle": False},
                    "backend_idle",
                ),
                (
                    "I01-C06-BYTES",
                    {**good, "terminal_response_bytes_forwarded": 1},
                    "terminal bytes",
                ),
                (
                    "I01-C06-FAULT",
                    {**good, "fault": "other"},
                    "fault",
                ),
            ):
                _write_gate(root, stem, payload)
                refused = False
                try:
                    load_c06_gate_receipt(artifact_stem=stem, root=root)
                except C06GateError as exc:
                    if needle not in str(exc):
                        raise ControlFailure(
                            f"gate subcase {stem} wrong error: {exc!r}"
                        )
                    refused = True
                if not refused:
                    raise ControlFailure(f"gate subcase {stem} incorrectly accepted")

        # Lock observation positives + negatives via actual suite guard.
        good_lock = I02Evidence(
            holder_pid=11,
            waiter_pid=22,
            assessment_backend_pid=22,
            assessment_started_after_hold_confirmed=True,
            lock_row_relationship={
                "holder_in_pg_blocking_pids_waiter": True,
                "granted_holder_rows": 1,
                "ungranted_waiter_rows": 1,
            },
        )
        assert_i02_lock_observations(good_lock)
        for label, bad_evidence in (
            ("missing_holder", I02Evidence(waiter_pid=22, assessment_backend_pid=22)),
            (
                "same_pid",
                I02Evidence(
                    holder_pid=7,
                    waiter_pid=7,
                    assessment_backend_pid=7,
                    assessment_started_after_hold_confirmed=True,
                    lock_row_relationship={
                        "holder_in_pg_blocking_pids_waiter": True,
                        "granted_holder_rows": 1,
                        "ungranted_waiter_rows": 1,
                    },
                ),
            ),
            (
                "wrong_blocking",
                I02Evidence(
                    holder_pid=11,
                    waiter_pid=22,
                    assessment_backend_pid=22,
                    assessment_started_after_hold_confirmed=True,
                    lock_row_relationship={
                        "holder_in_pg_blocking_pids_waiter": False,
                        "granted_holder_rows": 1,
                        "ungranted_waiter_rows": 1,
                    },
                ),
            ),
        ):
            refused = False
            try:
                assert_i02_lock_observations(bad_evidence)
            except RuntimeError:
                refused = True
            if not refused:
                raise ControlFailure(f"lock subcase {label} incorrectly accepted")

        # Budget identity positives + negatives.
        assert_budget_identity_observations(
            ingress_budget_id=101,
            worker_budget_id=101,
            worker_entered=True,
        )
        for label, kwargs in (
            ("missing_ingress", {"ingress_budget_id": None, "worker_budget_id": 1, "worker_entered": True}),
            ("missing_worker", {"ingress_budget_id": 1, "worker_budget_id": None, "worker_entered": True}),
            ("wrong_identity", {"ingress_budget_id": 1, "worker_budget_id": 2, "worker_entered": True}),
            ("worker_not_entered", {"ingress_budget_id": 1, "worker_budget_id": 1, "worker_entered": False}),
        ):
            refused = False
            try:
                assert_budget_identity_observations(**kwargs)
            except RuntimeError:
                refused = True
            if not refused:
                raise ControlFailure(f"budget subcase {label} incorrectly accepted")

        # Transport coverage positives + negatives.
        assert_transport_coverage_observations(
            transport_factory="FixtureByteTransport",
            provider_coverage="synthetic_fixture_byte_transport",
        )
        for label, kwargs in (
            ("missing_factory", {"transport_factory": None, "provider_coverage": "synthetic_fixture_byte_transport"}),
            ("wrong_factory", {"transport_factory": "JoinedTLS", "provider_coverage": "synthetic_fixture_byte_transport"}),
            ("missing_coverage", {"transport_factory": "FixtureByteTransport", "provider_coverage": None}),
            ("wrong_coverage", {"transport_factory": "FixtureByteTransport", "provider_coverage": "live"}),
        ):
            refused = False
            try:
                assert_transport_coverage_observations(**kwargs)
            except RuntimeError:
                refused = True
            if not refused:
                raise ControlFailure(f"transport subcase {label} incorrectly accepted")

        record(
            "N10",
            "REFUSE",
            "gate+lock+budget+transport missing/wrong observations refused with positives",
        )
    except Exception as exc:
        record("N10", "FAIL", repr(exc))

    # --- N11 C09 negatives via extracted DisconnectInjectControl + evidence gate ---
    try:
        control = DisconnectInjectControl()
        # Checkpoint/receive path refuse: inject without bind.
        inject_refused = False
        try:
            control.inject_http_disconnect(timeout=0.05)
        except RuntimeError as exc:
            if "not bound" in str(exc):
                inject_refused = True
            else:
                raise
        if not inject_refused:
            raise ControlFailure("unbound inject did not refuse")

        # Fabricated/missing evidence refused by assert_c09_disconnect_evidence.
        fabricated_refused = False
        try:
            assert_c09_disconnect_evidence(
                asgi_result=None,
                cancellation_provenance="covering_budget_stopped_unknown",
                api_error_status=None,
                api_error_code=None,
                monitor_observed=False,
                disconnect_delivered=False,
                post_disconnect_outbound=[],
            )
        except RuntimeError:
            fabricated_refused = True
        if not fabricated_refused:
            raise ControlFailure("fabricated C09 evidence not refused")

        # Driver error must refuse (not success).
        err_result = BoundedASGIResponse(error=TimeoutError("asgi-timeout"))
        error_refused = False
        try:
            assert_c09_disconnect_evidence(
                asgi_result=err_result,
                cancellation_provenance="CoveringBudgetStopped",
                api_error_status=503,
                api_error_code="CALENDAR_REFRESH_OUTCOME_UNKNOWN",
                monitor_observed=True,
                disconnect_delivered=True,
                post_disconnect_outbound=[],
            )
        except RuntimeError as exc:
            if "error/timeout" in str(exc):
                error_refused = True
            else:
                raise
        if not error_refused:
            raise ControlFailure("ASGI error result incorrectly accepted")

        # Post-disconnect outbound send refuse.
        ok_result = BoundedASGIResponse(error=None, response_started=False)
        send_refused = False
        try:
            assert_c09_disconnect_evidence(
                asgi_result=ok_result,
                cancellation_provenance="CoveringBudgetStopped",
                api_error_status=503,
                api_error_code="CALENDAR_REFRESH_OUTCOME_UNKNOWN",
                monitor_observed=True,
                disconnect_delivered=True,
                post_disconnect_outbound=["http.response.start"],
            )
        except RuntimeError as exc:
            if "outbound" in str(exc):
                send_refused = True
            else:
                raise
        if not send_refused:
            raise ControlFailure("post-disconnect outbound not refused")

        # Late-peer timing via extracted _next_receive_message: inject wins first;
        # receive completes successfully during finally retirement (after selection)
        # → explicit refusal (not silent discard). Cancel-then-return models the
        # late successful peer without a wall-clock race against finally.
        _next_receive_message = extracted["_next_receive_message"]
        asyncio = __import__("asyncio")

        async def _late_success_peer_case() -> None:
            inject_queue: asyncio.Queue = asyncio.Queue()

            async def late_success_on_cancel_receive():
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    return {
                        "type": "http.request",
                        "body": b"late-after-cancel",
                        "more_body": False,
                    }

            await inject_queue.put({"type": "http.disconnect"})
            refused = False
            try:
                await _next_receive_message(
                    late_success_on_cancel_receive, inject_queue
                )
            except RuntimeError as exc:
                text = str(exc)
                if (
                    "late peer outcome after selection" in text
                    or "concurrent upstream receive while inject delivered" in text
                ):
                    refused = True
                else:
                    raise
            if not refused:
                raise ControlFailure(
                    "late successful receive peer after inject selection was discarded"
                )

        async def _peer_error_secondary_under_primary() -> None:
            """When inject delivers and receive errors, primary is set; peer error
            must remain attached as secondary (not dropped because primary exists).
            """
            inject_queue: asyncio.Queue = asyncio.Queue()

            async def boom_receive():
                raise RuntimeError("peer-recv-boom")

            await inject_queue.put({"type": "http.disconnect"})
            try:
                await _next_receive_message(boom_receive, inject_queue)
            except RuntimeError as exc:
                cause = exc.__cause__
                if cause is None or "peer-recv-boom" not in str(cause):
                    if "peer-recv-boom" not in str(exc):
                        raise ControlFailure(
                            "peer receive error not preserved as primary cause"
                        )
                retirement = getattr(exc, "fixture_receive_retirement_errors", None)
                if not retirement:
                    raise ControlFailure(
                        "peer error dropped under primary "
                        "(missing fixture_receive_retirement_errors)"
                    )
                return
            raise ControlFailure("expected concurrent inject/receive refusal")

        asyncio.run(_late_success_peer_case())
        asyncio.run(_peer_error_secondary_under_primary())

        # Cancellation-before-selection: owner CancelledError during wait after
        # peer already done with non-cancel error; peer must remain secondary
        # and must not replace cancellation (source stays None path).
        async def _cancellation_before_selection_peer_secondary() -> None:
            inject_queue: asyncio.Queue = asyncio.Queue()
            asgi_mod = modules["i01_asgi_app"]
            real_asyncio = asgi_mod["asyncio"]
            real_wait = real_asyncio.wait

            async def boom_receive():
                raise RuntimeError("peer-preselect-boom")

            async def wait_then_owner_cancel(fs, *a, **kw):
                await real_wait(fs, *a, **kw)
                # Peer already done; raise owner cancellation before selection
                # assigns source (source remains None).
                raise real_asyncio.CancelledError()

            proxy = types.SimpleNamespace()
            for name in dir(real_asyncio):
                if name.startswith("_"):
                    continue
                setattr(proxy, name, getattr(real_asyncio, name))
            proxy.wait = wait_then_owner_cancel
            asgi_mod["asyncio"] = proxy
            try:
                try:
                    await _next_receive_message(boom_receive, inject_queue)
                except real_asyncio.CancelledError as exc:
                    retirement = getattr(
                        exc, "fixture_receive_retirement_errors", None
                    )
                    if not retirement:
                        raise ControlFailure(
                            "cancellation-before-selection dropped already-done "
                            "peer error (missing fixture_receive_retirement_errors)"
                        )
                    if not any(
                        "peer-preselect-boom" in str(item.get("message", ""))
                        for item in retirement
                    ):
                        raise ControlFailure(
                            "cancellation-before-selection peer secondary missing "
                            f"boom detail: {retirement!r}"
                        )
                    # Cancellation retained as primary (we caught CancelledError).
                    return
                except RuntimeError as exc:
                    if "peer-preselect-boom" in str(exc):
                        raise ControlFailure(
                            "cancellation-before-selection replaced cancellation "
                            "with peer error as primary"
                        ) from exc
                    raise
                raise ControlFailure(
                    "expected CancelledError primary for cancellation-before-selection"
                )
            finally:
                asgi_mod["asyncio"] = real_asyncio

        asyncio.run(_cancellation_before_selection_peer_secondary())

        record(
            "N11",
            "REFUSE",
            "C09 unbound inject / fabricated / error / outbound / late-peer / "
            "cancel-before-selection peer-secondary refused via extract",
        )

        # Positive snapshot shape (hold contract)
        snapshot = {
            "ownership_established": True,
            "calendar_admitted": False,
            "auth_telemetry_admitted": False,
        }
        assert snapshot["ownership_established"] is True
        assert snapshot["calendar_admitted"] is False
        # Positive evidence shape with intentional no-response (error=None)
        assert_c09_disconnect_evidence(
            asgi_result=ok_result,
            cancellation_provenance="CoveringBudgetStopped",
            api_error_status=503,
            api_error_code="CALENDAR_REFRESH_OUTCOME_UNKNOWN",
            monitor_observed=True,
            disconnect_delivered=True,
            post_disconnect_outbound=[],
        )
        record("P_C09_hold_snapshot_shape", "PASS")
    except Exception as exc:
        record("N11", "FAIL", repr(exc))
        record("P_C09_hold_snapshot_shape", "FAIL", repr(exc))

    # --- N14 synthetic ModuleType registration + dataclass _is_type + patch + refuse ---
    try:
        # Setup coverage: every extracted module must be a real ModuleType in
        # sys.modules whose __dict__ is the exec namespace.
        for mod_key, ns in modules.items():
            name = str(ns.get("__name__") or "")
            registered = sys.modules.get(name)
            if registered is None:
                raise ControlFailure(f"synthetic module {name!r} missing from sys.modules")
            if not isinstance(registered, types.ModuleType):
                raise ControlFailure(
                    f"synthetic module {name!r} is not ModuleType: {type(registered)!r}"
                )
            if registered.__dict__ is not ns:
                raise ControlFailure(
                    f"synthetic module {name!r} __dict__ is not extract namespace"
                )
            # Dataclass _is_type resolution path: sys.modules.get(cls.__module__).__dict__
            probe = sys.modules.get(name)
            if probe is None or probe.__dict__ is not ns:
                raise ControlFailure(
                    f"dataclass _is_type probe failed for {name!r} ({mod_key})"
                )

        # Per-module global patch visibility: SharedTransportScript is a class
        # (no __globals__). Check an actual method against byte_ns and use that
        # same method globals dict for the sentinel assertion.
        byte_ns = modules["i01_byte_transport"]
        SharedTransportScript = extracted["SharedTransportScript"]
        take_globals = SharedTransportScript.take.__globals__
        if take_globals is not byte_ns:
            raise ControlFailure(
                "SharedTransportScript.take __globals__ is not module.__dict__"
            )
        sentinel_key = "_fixture_patch_sentinel"
        byte_ns[sentinel_key] = "visible"
        if take_globals.get(sentinel_key) != "visible":
            raise ControlFailure(
                "per-module global patch not visible to extracted callable"
            )
        del byte_ns[sentinel_key]

        # Class module identity remains a separate __module__/sys.modules check.
        expected_mod_name = str(byte_ns.get("__name__") or "")
        if SharedTransportScript.__module__ != expected_mod_name:
            raise ControlFailure(
                "SharedTransportScript.__module__ "
                f"{SharedTransportScript.__module__!r} != {expected_mod_name!r}"
            )
        class_mod = sys.modules.get(SharedTransportScript.__module__)
        if class_mod is None or class_mod.__dict__ is not byte_ns:
            raise ControlFailure(
                "SharedTransportScript module identity not resolvable via sys.modules"
            )

        # Missing-symbol refusal preserved (preexisting globals do not satisfy).
        refused_missing = False
        try:
            extract_symbols(
                FIXTURE / "i01_auth_seed.py",
                ["definitely_missing_symbol_zz"],
                modules["i01_auth_seed"],
                provenance=[],
            )
        except ControlFailure as exc:
            if "required AST names missing" in str(exc):
                refused_missing = True
            else:
                raise
        if not refused_missing:
            raise ControlFailure("missing-symbol refusal regressed")

        # Dataclass constructed under synthetic module name resolves via sys.modules.
        probe_name = "extracted_probe_dataclass_module"
        probe_ns = new_module_namespace(probe_name, {"dataclass": dataclass, "field": field})
        exec(
            "@dataclass\n"
            "class Probe:\n"
            "    value: int = 0\n",
            probe_ns,
        )
        Probe = probe_ns["Probe"]
        if Probe.__module__ != probe_name:
            raise ControlFailure(
                f"Probe.__module__={Probe.__module__!r} != {probe_name!r}"
            )
        resolved = sys.modules.get(Probe.__module__)
        if resolved is None or resolved.__dict__ is not probe_ns:
            raise ControlFailure("dataclass module dict not resolvable via sys.modules")
        inst = Probe(value=3)
        if inst.value != 3:
            raise ControlFailure("dataclass instance under synthetic module failed")

        record(
            "N14",
            "REFUSE",
            "synthetic ModuleType registration / _is_type probe / patch visibility / "
            "missing-symbol refuse covered",
        )
        record("P_synthetic_module_registration", "PASS")
    except Exception as exc:
        record("N14", "FAIL", repr(exc))
        record("P_synthetic_module_registration", "FAIL", repr(exc))

    # --- N13 via extracted assert_ordering_request_ids guard ---
    try:
        planted = inverted(case_token="i01c01")
        already_sorted = sorted(planted, key=str)
        refused = False
        try:
            assert_ordering_request_ids(
                subscription_ids=planted,
                request_ids=already_sorted,
            )
        except AssertionError as exc:
            if "already-sorted request_ids refuse ordering claim" in str(exc):
                refused = True
            else:
                raise
        if not refused:
            raise ControlFailure("ordering collapse not detected by fixture guard")
        record("N13", "REFUSE", "already-sorted refused by assert_ordering_request_ids")
    except Exception as exc:
        record("N13", "FAIL", repr(exc))

    # Silence unused-modules lint for provenance callers
    _ = modules
    _ = SuiteStop
    return results


def build_extractions(provenance: list[ExtractionProvenance]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    install_fake_modules()
    import datetime as datetime_mod

    shared_base: dict[str, Any] = {
        "Any": Any,
        "Callable": Callable,
        "UUID": UUID,
        "Path": Path,
        "Event": threading.Event,
        "Thread": threading.Thread,
        "Lock": threading.Lock,
        "field": field,
        "dataclass": dataclass,
        "annotations": True,
        "JOIN_LIMIT_SECONDS": 60.0,
        "datetime": datetime_mod.datetime,
        "timedelta": datetime_mod.timedelta,
        "timezone": datetime_mod.timezone,
        "hashlib": hashlib,
        "json": json,
        "re": re,
        "time": time,
        "threading": threading,
        "monotonic": time.monotonic,
    }
    CoveringTransportRefused = sys.modules[
        "app.services.covering_transport_policy"
    ].CoveringTransportRefused
    shared_base["CoveringTransportRefused"] = CoveringTransportRefused
    ApiError = sys.modules["app.api.errors"].ApiError
    shared_base["ApiError"] = ApiError
    shared_base["SuiteStop"] = type("SuiteStop", (RuntimeError,), {})
    shared_base["AttemptFailed"] = type("AttemptFailed", (RuntimeError,), {})
    shared_base["build_receipt"] = lambda **kwargs: kwargs
    shared_base["sanitize_cleanup_failure"] = lambda exc: {"kind": type(exc).__name__}
    shared_base["Iterator"] = Any
    shared_base["contextmanager"] = lambda f: f
    shared_base["C06_GATE_ARTIFACT_STEM"] = "I01-C06"
    shared_base["C06GateError"] = type("C06GateError", (RuntimeError,), {})

    modules: dict[str, dict[str, Any]] = {}
    extracted: dict[str, Any] = {
        "CoveringTransportRefused": CoveringTransportRefused,
        "SuiteStop": shared_base["SuiteStop"],
    }

    # auth_seed module ns
    auth_ns = new_module_namespace("extracted_i01_auth_seed", shared_base)
    modules["i01_auth_seed"] = auth_ns
    extracted.update(
        extract_symbols(
            FIXTURE / "i01_auth_seed.py",
            [
                "_token_hex_prefix",
                "inverted_subscription_ids",
                "production_ordered_calendar_ids",
                "ATTEMPT_VALIDITY_SECONDS",
                "PULL_WINDOW_MAX",
                "PlanValidityExpired",
                "REQUEST_END_HEADROOM",
                "TOKEN_HORIZON",
            ],
            auth_ns,
            provenance=provenance,
        )
    )

    # byte transport — Lock MUST already be in ns before SharedTransportScript compiles
    byte_ns = new_module_namespace("extracted_i01_byte_transport", shared_base)
    if "Lock" not in byte_ns:
        raise ControlFailure("Lock must be supplied before SharedTransportScript extract")
    modules["i01_byte_transport"] = byte_ns
    extracted.update(
        extract_symbols(
            FIXTURE / "i01_byte_transport.py",
            ["ScriptedExchange", "SharedTransportScript", "google_event_empty_script"],
            byte_ns,
            provenance=provenance,
        )
    )

    # receipts helpers used by suite extract
    receipts_ns = new_module_namespace("extracted_i01_i02_receipts", shared_base)
    modules["i01_i02_receipts"] = receipts_ns
    extracted.update(
        extract_symbols(
            FIXTURE / "i01_i02_receipts.py",
            ["build_receipt", "sanitize_cleanup_failure", "RECEIPT_VERSION"],
            receipts_ns,
            provenance=provenance,
        )
    )
    shared_base["build_receipt"] = receipts_ns["build_receipt"]
    shared_base["sanitize_cleanup_failure"] = receipts_ns["sanitize_cleanup_failure"]

    # c06 gate receipt validator
    c06_ns = new_module_namespace("extracted_i01_c06_dual_peer", shared_base)
    c06_ns["C06GateError"] = shared_base["C06GateError"]
    c06_ns["C06_GATE_ARTIFACT_STEM"] = "I01-C06"
    modules["i01_c06_dual_peer"] = c06_ns
    extracted.update(
        extract_symbols(
            FIXTURE / "i01_c06_dual_peer.py",
            ["load_c06_gate_receipt", "C06GateError", "C06_GATE_ARTIFACT_STEM"],
            c06_ns,
            provenance=provenance,
        )
    )

    # asgi disconnect + bounded response
    asgi_ns = new_module_namespace("extracted_i01_asgi_app", shared_base)
    asgi_ns["asyncio"] = __import__("asyncio")
    modules["i01_asgi_app"] = asgi_ns
    extracted.update(
        extract_symbols(
            FIXTURE / "i01_asgi_app.py",
            [
                "DisconnectInjectControl",
                "BoundedASGIResponse",
                "MONITOR_OBSERVE_JOIN_SECONDS",
                "_next_receive_message",
            ],
            asgi_ns,
            provenance=provenance,
        )
    )

    # suite helpers
    suite_ns = new_module_namespace("extracted_i01_i02_suite", shared_base)
    suite_ns["SuiteStop"] = shared_base["SuiteStop"]
    suite_ns["AttemptFailed"] = shared_base["AttemptFailed"]
    suite_ns["JOIN_LIMIT_SECONDS"] = 60.0
    modules["i01_i02_suite"] = suite_ns
    extracted.update(
        extract_symbols(
            FIXTURE / "i01_i02_suite.py",
            [
                "AttemptCleanup",
                "assert_subscription_ids_count_error",
                "assert_ordering_request_ids",
                "attach_cleanup_failures_to_primary",
                "resolve_attempt_outcome",
                "assert_c09_disconnect_evidence",
                "assert_i02_lock_observations",
                "assert_budget_identity_observations",
                "assert_transport_coverage_observations",
                "_validation_items",
                "I01_CASE_IDS",
                "JOIN_LIMIT_SECONDS",
                "SuiteStop",
            ],
            suite_ns,
            provenance=provenance,
        )
    )

    # i02 diagnostic + admission oracle
    i02_ns = new_module_namespace("extracted_i02_owner_lock_contention", shared_base)
    modules["i02_owner_lock_contention"] = i02_ns
    extracted.update(
        extract_symbols(
            FIXTURE / "i02_owner_lock_contention.py",
            [
                "I02Barriers",
                "I02Evidence",
                "GENERATION_MISMATCH_CAUSE",
                "await_mutation_admission",
                "assert_intended_subscription_diagnostic",
                "record_observer_close_failure",
                "select_i02_primary",
                "close_preserving_primary",
                "run_verification_query_with_close",
                "JOIN_LIMIT_SECONDS",
            ],
            i02_ns,
            provenance=provenance,
        )
    )

    return extracted, modules


def main() -> int:
    manifest = load_manifest()
    expected = load_expected()
    verify_source_hashes(manifest)
    provenance: list[ExtractionProvenance] = []
    extracted, modules = build_extractions(provenance)
    results = run_controls(extracted, modules)

    inventory_error: str | None = None
    try:
        enforce_expected_inventory(results, expected)
        status = "PASS"
    except ControlFailure as exc:
        inventory_error = str(exc)
        status = "FAIL"

    if any(r.result == "FAIL" for r in results):
        status = "FAIL"

    # Emit inventory in EXPECTED-OUTPUT key order (not execution record order) so
    # launcher result gate can require exact IDs + order without depending on
    # run_controls sequencing (N7 may record first; EXPECTED starts N1,N2,...).
    try:
        expected_ids = expected_control_ids(expected)
    except ControlFailure:
        expected_ids = list((expected.get("controls") or {}).keys())
    by_id = {r.control_id: r for r in results}
    ordered_controls: dict[str, dict[str, str]] = {}
    for cid in expected_ids:
        if cid in by_id:
            ordered_controls[cid] = {
                "result": by_id[cid].result,
                "detail": by_id[cid].detail,
            }
    for r in results:
        if r.control_id not in ordered_controls:
            ordered_controls[r.control_id] = {"result": r.result, "detail": r.detail}

    payload = {
        "status": status,
        "class": "FAKE-BEHAVIORAL",
        "controls": ordered_controls,
        "control_ids_in_order": list(ordered_controls.keys()),
        "expected_control_ids": expected_ids,
        "ordered_contract": (
            "EXPECTED.controls key order == EXPECTED.control_ids_in_order "
            "== result.control_ids_in_order == result.controls key order"
        ),
        "inventory_error": inventory_error,
        "extraction_provenance": [
            {
                "source_path": p.source_path,
                "source_sha256": p.source_sha256,
                "names": p.names,
                "module_name": p.module_name,
            }
            for p in provenance
        ],
        "source_hashes_verified": True,
        "executed": True,
        "cannot_waive": [
            "native SQL contention",
            "real TLS terminal",
            "integrated ingress timing under Docker",
        ],
    }
    RESULT_PATH.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "controls": list(payload["controls"]),
                "inventory_error": inventory_error,
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
