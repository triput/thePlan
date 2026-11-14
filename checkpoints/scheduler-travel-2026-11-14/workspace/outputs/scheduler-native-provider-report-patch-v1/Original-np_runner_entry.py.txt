"""In-runner entry for native-provider prep.

PREPARATION AUTHORING ONLY. Real case dispatch/registry wiring lives here.
PKI child generation and peer bind require later launch authorization
(launch_ready must be true on runner-config). Incomplete cases are explicit
named HOLDs — never fabricated PASS. Unjoined/unconfirmed retirement → UNKNOWN.
No Docker daemon access from this seat.

First reviewable increment (Dex Incremental-Handback-Order): functional peer +
NP-V-MS-NONEXPIRED through production CoveringReleasePlan → ProviderCounter →
CoveringHTTP → default JoinedTLS (no transport_factory injection).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import threading
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
RUNNER_CONFIG_NAME = "runner-config.json"
OUTPUT_BYTE_CAP = 1048576
REQUIRED_UID = 65534
PEER_SECONDS_DEFAULT = 120

# Cases with authored runnable bodies under this prep successor.
IMPLEMENTED_CASE_IDS: frozenset[str] = frozenset({"NP-V-MS-NONEXPIRED"})


class RunnerEntryHeld(RuntimeError):
    """Admission / configuration HOLD — not a fabricated case PASS."""


class CaseBodyHold(RuntimeError):
    """Explicit named HOLD for an incomplete case body. Never emit as PASS."""

    def __init__(self, case_id: str, reason: str):
        self.case_id = case_id
        self.reason = reason
        super().__init__(f"HOLD:{case_id}:{reason}")


class BoundedOutput:
    def __init__(self) -> None:
        self.length = 0
        self.sha = hashlib.sha256()

    def write(self, value: str) -> int:
        data = value.encode("utf-8", errors="replace")
        self.length += len(data)
        if self.length > OUTPUT_BYTE_CAP:
            raise RuntimeError("runner console cap")
        self.sha.update(data)
        return len(value)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def load_runner_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RunnerEntryHeld("runner-config missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("launch_ready") is not True:
        raise RunnerEntryHeld("runner-config launch_ready is false — external operator gate")
    required = ("case_ids", "expected_unknown_cases", "runner_seconds", "runtime_pins")
    for key in required:
        if key not in data:
            raise RunnerEntryHeld(f"runner-config missing {key}")
    if type(data["runner_seconds"]) is not int or not 1 <= data["runner_seconds"] <= 3600:
        raise RunnerEntryHeld("runner_seconds must be frozen int on launch card")
    return data


def admit_runner_identity() -> None:
    if os.getuid() != REQUIRED_UID:
        raise RunnerEntryHeld("runner uid mismatch")
    if os.getuid() == 0:
        raise RunnerEntryHeld("root refused")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hold_reason(case_id: str) -> str:
    return (
        f"case body not yet authored for execution-ready path; "
        f"obligation retained in np_suite registry; "
        f"first increment implements {sorted(IMPLEMENTED_CASE_IDS)}; "
        f"incomplete cases are HOLD not PASS"
    )


def _run_np_v_ms_nonexpired() -> dict[str, Any]:
    """Production vertical: nonexpired MS seed; no OAuth; TOKEN ROLLBACK ack.

    Chain: CoveringReleasePlan.for_request → ProviderCounter(approved_provider_limits,
    budget.work_remaining) → CoveringHTTP (default JoinedTLS) — no injected transport.
    Synthetic peer serves Graph event empty body on numeric loopback :443.
    Observation aids: measure from ASGI budget admission; supervisor kill ≠ app
    deadline; ASGI disconnect ≠ provider EOF ≠ task cancellation.
    """
    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_auth_seed import (
        assert_plan_still_valid,
        fresh_attempt_plan,
        PlanValidityExpired,
        seed_token_plan,
        disposable_ms_settings,
    )
    from np_alias_seed import microsoft_primary_alias_seed, sanitized_alias_receipt
    from np_receipts import case_result_receipt
    from np_provider_routes import microsoft_graph_route
    from np_provider_transcript import ms_graph_events_empty_script
    from np_provider_peer import SyntheticProviderPeer, PeerMaterial, PeerRetirementUnknown

    case_id = "NP-V-MS-NONEXPIRED"
    decl = registry_by_id(include_cf=True)[case_id]
    plan = fresh_attempt_plan(case_id)
    t_plan_iso = plan.t_plan.isoformat()
    token_seed = seed_token_plan(case_id=case_id, provider="microsoft", expired=False)
    alias = microsoft_primary_alias_seed(case_id=case_id)
    settings_labels = disposable_ms_settings()

    # --- Production composition (imports only when launch_ready path runs) ---
    from app.services.covering_release_plan import CoveringReleasePlan
    from app.services.covering_transport_policy import HTTPSPeer
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_request_budget import CoveringRequestBudget
    from app.core.config import get_settings
    import inspect

    # Default JoinedTLS must remain the CoveringHTTP transport_factory.
    sig = inspect.signature(CoveringHTTP.__init__)
    transport_default = sig.parameters["transport_factory"].default
    if transport_default is not JoinedTLS:
        raise SuiteStop("production CoveringHTTP default is not JoinedTLS")

    route = microsoft_graph_route()
    script = ms_graph_events_empty_script()
    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}",
        route=route,
        script=script,
        material=PeerMaterial(),
    )
    observations: dict[str, str] = {}
    workers_joined = False
    oauth_requests = 0
    inventory: list[dict[str, Any]] = []
    held_transport: list[Any] = []

    try:
        assert_plan_still_valid(plan.t_plan)
        peer.start_background(seconds=PEER_SECONDS_DEFAULT)

        # Build production release plan — for_request constructs Counter+CoveringHTTP
        # without injected transport_factory (preserves JoinedTLS default chain).
        settings = get_settings()
        # Fixture overlays — disposable labels only; never live credentials.
        for key, value in settings_labels.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        database_profile = _fixture_database_profile()
        runtime_pins = _runtime_pins_from_config()

        provider_peer = HTTPSPeer(
            hostname=route.url_host,
            address=route.dial_address,
            port=route.dial_port,
            ca_file=route.ca_path,
        )
        # Route table: Graph events path; purpose event (not oauth) for nonexpired path.
        # server_hostname may differ for wrong-name cases; URL host stays vendor origin.
        routes = (
            (provider_peer, "/v1.0/me/calendar/events", "event"),
            (provider_peer, "/v1.0/me/calendars", "event"),
        )
        release_plan = CoveringReleasePlan(
            database_profile=database_profile,
            password_supplier=lambda: "",
            runtime_pins=runtime_pins,
            provider_routes=routes,
            settings=settings,
        )

        # ASGI budget admission clock — CoveringRequestBudget captures start once
        # (work +210 / request +240). Not interchangeable with a case-local clock.
        budget = CoveringRequestBudget()
        # Capture the CoveringHTTP instance constructed inside for_request without
        # injecting a transport_factory (wrap CoveringHTTP.__new__/__init__ briefly).
        binding = _for_request_capturing_transport(release_plan, budget, held_transport)
        if len(held_transport) != 1 or type(held_transport[0]) is not CoveringHTTP:
            raise SuiteStop("for_request did not construct exactly one CoveringHTTP")
        transport = held_transport[0]
        if transport.transport_factory is not JoinedTLS:
            raise SuiteStop("transport_factory injection refused — require default JoinedTLS")

        from np_auth_seed import inverted_subscription_ids

        sub_ids = inverted_subscription_ids(case_token=plan.attempt_token)
        before_state = {
            "token_expired": token_seed.expired,
            "alias_hash": alias.seed_hash,
            "subscription_ids": [str(x) for x in sub_ids],
            "coverage_fresh": False,
            "assessment_ready": False,
        }

        app_result = _drive_ms_nonexpired_covering(
            binding=binding,
            budget=budget,
            transport=transport,
            token_seed=token_seed,
            alias=alias,
            inventory=inventory,
            oauth_counter_out=inventory,  # oauth count returned in app_result
        )

        after_state = {
            "coverage_fresh": bool(app_result.get("coverage_fresh")),
            "assessment_ready": bool(app_result.get("assessment_ready")),
            "token_rollback_acked": bool(app_result.get("token_rollback_acked")),
            "oauth_requests": int(app_result.get("oauth_requests", 0)),
        }
        oauth_requests = after_state["oauth_requests"]

        if before_state["coverage_fresh"] == after_state["coverage_fresh"] and not after_state["assessment_ready"]:
            raise SuiteStop("before/after coverage/assessment not distinguishable")
        if oauth_requests != 0:
            raise SuiteStop("nonexpired path must not perform OAuth exchange")
        if not after_state["token_rollback_acked"]:
            raise SuiteStop("TOKEN ROLLBACK acknowledgment missing")

        observations = {
            "no_oauth_request": "OBSERVED",
            "token_rollback_ack": "OBSERVED",
            "identity_event_assessment_separate": "OBSERVED",
        }
        # Alias/canonicalization observation retained for this Microsoft vertical.
        _ = sanitized_alias_receipt(alias)
        check_oracles_immediate(decl, observations)
        t_check_iso = _iso_now()
        assert_plan_still_valid(plan.t_plan)
        peer_state = peer.sanitized_state()
        retirement = peer.retire_owned(join_seconds=5.0)
        workers_joined = retirement.get("joined") is True
        if not workers_joined:
            raise SuiteStop("peer worker unjoined — UNKNOWN")
        # Unexpected threads beyond main → STOP (integrated_runner also checks).
        unexpected = [
            t
            for t in threading.enumerate()
            if t is not threading.main_thread() and t.name.startswith("np-peer-")
        ]
        if unexpected:
            raise SuiteStop("unjoined np-peer worker after retirement")

        return case_result_receipt(
            case_id=case_id,
            passed=True,
            workers_joined=True,
            expected_unknown=False,
            observations=observations,
            t_plan_iso=t_plan_iso,
            t_check_iso=t_check_iso,
        )
    except PlanValidityExpired:
        raise
    except PeerRetirementUnknown:
        raise SuiteStop("owned peer retirement UNKNOWN")
    except CaseBodyHold:
        raise
    except SuiteStop:
        raise
    except BaseException as exc:
        # Fixture/framework failure remains STOP — never remap to expected UNKNOWN.
        raise SuiteStop(f"framework_stop:{case_id}:{type(exc).__name__}") from exc
    finally:
        if peer._worker is not None and not peer.life.joined:  # noqa: SLF001 — bounded retire
            try:
                peer.retire_owned(join_seconds=2.0)
            except PeerRetirementUnknown:
                pass


def _fixture_database_profile() -> Any:
    from app.services.covering_native_checkout import PostgreSQLPeer

    # Paths/labels match disposable fixture layout used by immutable helpers.
    return PostgreSQLPeer(
        hostname="db",
        address="127.0.0.1",
        port=5432,
        database="scheduler",
        username="scheduler",
        ca_file="/public-ca/ca.crt",
        absent_passfile="/tmp/np-absent-pgpass",
        client_cert="/tmp/np-absent-client.crt",
        client_key="/tmp/np-absent-client.key",
    )


def _runtime_pins_from_config() -> Any:
    from app.services.covering_native_orm_factory import NativeRuntimePins

    config_path = ROOT / RUNNER_CONFIG_NAME
    data = json.loads(config_path.read_text(encoding="utf-8"))
    pins = data.get("runtime_pins") or {}
    if not isinstance(pins, dict) or pins.get("python") is None:
        raise RunnerEntryHeld("runtime_pins.python must be frozen on launch card before run")
    return NativeRuntimePins(
        python=tuple(pins["python"]),
        psycopg=str(pins["psycopg"]),
        sqlalchemy=str(pins["sqlalchemy"]),
        pq_implementation=str(pins["pq_implementation"]),
        pq_runtime=int(pins["pq_runtime"]),
        pq_build=int(pins["pq_build"]),
    )


def _for_request_capturing_transport(release_plan: Any, budget: Any, held: list[Any]) -> Any:
    """Call CoveringReleasePlan.for_request while capturing the CoveringHTTP instance.

    Does not inject transport_factory — only observes the production constructor.
    """
    from app.services.covering_http_transport import CoveringHTTP

    real_init = CoveringHTTP.__init__

    def capturing_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        held.append(self)

    CoveringHTTP.__init__ = capturing_init  # type: ignore[method-assign]
    try:
        return release_plan.for_request(budget)
    finally:
        CoveringHTTP.__init__ = real_init  # type: ignore[method-assign]


def _drive_ms_nonexpired_covering(
    *,
    binding: Any,
    budget: Any,
    transport: Any,
    token_seed: Any,
    alias: Any,
    inventory: list[dict[str, Any]],
    oauth_counter_out: list[dict[str, Any]],
) -> dict[str, Any]:
    """Drive the selected native covering path for nonexpired MS vertical.

    Uses production dispatch worker when available. Records oauth inventory.
    """
    del oauth_counter_out  # oauth count returned in result; inventory retained
    from np_suite import SuiteStop
    from app.services import covering_http_dispatch as http_dispatch

    oauth_counter = {"n": 0}
    real_request = transport.request

    def counted_request(method, url, *, purpose, **kwargs):
        if purpose == "oauth":
            oauth_counter["n"] += 1
        inventory.append({"method": method, "purpose": purpose, "url_host_present": True})
        return real_request(method, url, purpose=purpose, **kwargs)

    transport.request = counted_request  # type: ignore[method-assign]
    try:
        body = {
            "command": "calendar.refresh",
            "provider": "microsoft",
            "mode": "nonexpired_token_vertical",
            "alias_seed_hash": alias.seed_hash,
            "token_expired": False,
            "token_label_hash": token_seed.label_hash,
        }
        if hasattr(http_dispatch, "_worker"):
            request = _FixtureRequest()
            context = _FixtureContext(budget=budget)
            result = http_dispatch._worker(binding, request, body, context)
        elif hasattr(http_dispatch, "dispatch"):
            result = http_dispatch.dispatch(binding, body)
        else:
            raise SuiteStop("covering_http_dispatch worker entry missing")

        readiness = result if isinstance(result, dict) else getattr(result, "__dict__", {})
        return {
            "coverage_fresh": bool(readiness.get("coverage_fresh") or readiness.get("freshness_updated")),
            "assessment_ready": bool(
                readiness.get("assessment_ready")
                or readiness.get("assessment")
                or readiness.get("final_assessment")
            ),
            "token_rollback_acked": bool(
                readiness.get("token_rollback_acked")
                or readiness.get("token_terminal") == "ROLLBACK"
                or readiness.get("token_outcome") == "ROLLBACK"
            ),
            "oauth_requests": oauth_counter["n"],
            "raw_keys": sorted(str(k) for k in readiness.keys()) if isinstance(readiness, dict) else [],
        }
    finally:
        transport.request = real_request  # type: ignore[method-assign]


class _FixtureRequest:
    """Minimal ASGI-adjacent request stand-in for production worker signature."""

    def __init__(self) -> None:
        self.headers = []
        self.cookies = {}
        self.client = ("127.0.0.1", 0)
        self.url = type("U", (), {"path": "/covering"})()


class _FixtureContext:
    def __init__(self, *, budget: Any) -> None:
        self.budget = budget
        self.cancel = threading.Event()


def _make_implemented_case(case_id: str) -> Callable[[], dict[str, Any]]:
    if case_id == "NP-V-MS-NONEXPIRED":
        def _run() -> dict[str, Any]:
            return _run_np_v_ms_nonexpired()

        _run.__name__ = f"run_{case_id}"
        return _run
    raise CaseBodyHold(case_id, "no implemented body mapper")


def _make_hold_case(case_id: str, decl: Any) -> Callable[[], dict[str, Any]]:
    reason = _hold_reason(case_id)

    def _run() -> dict[str, Any]:
        raise CaseBodyHold(case_id, reason)

    _run.__name__ = f"hold_{case_id}"
    _run.decl = decl  # type: ignore[attr-defined]
    _run.hold_reason = reason  # type: ignore[attr-defined]
    _run.implementation_status = "HOLD"  # type: ignore[attr-defined]
    return _run


def build_registry_from_suite(case_ids: list[str]) -> dict[str, Callable[[], dict[str, Any]]]:
    """Bind finite declared cases to callables.

    Implemented cases get production/native bodies. Incomplete cases get explicit
    CaseBodyHold callables — never silent omission, never fabricated PASS.
    """
    from np_suite import registry_by_id

    decls = registry_by_id(include_cf=True)
    if set(case_ids) - set(decls):
        raise RunnerEntryHeld("case_ids not in finite suite registry")

    registry: dict[str, Callable[[], dict[str, Any]]] = {}
    for case_id in case_ids:
        decl = decls[case_id]
        if case_id in IMPLEMENTED_CASE_IDS:
            fn = _make_implemented_case(case_id)
            fn.decl = decl  # type: ignore[attr-defined]
            fn.implementation_status = "IMPLEMENTED"  # type: ignore[attr-defined]
            registry[case_id] = fn
        else:
            registry[case_id] = _make_hold_case(case_id, decl)
    return registry


def implementation_status_map(case_ids: list[str] | None = None) -> dict[str, str]:
    from np_suite import case_ids as suite_case_ids

    ids = list(case_ids) if case_ids is not None else list(suite_case_ids(include_cf=True))
    return {
        case_id: ("IMPLEMENTED" if case_id in IMPLEMENTED_CASE_IDS else "HOLD")
        for case_id in ids
    }


def main() -> int:
    """Admit identity + launch_ready config, bind registry, run serial suite.

    External gate: launch_ready must be true. Incomplete HOLD cases in an
    admitted batch cause CaseBodyHold → non-zero STOP (never PASS).
    Prefer incremental batches that only admit IMPLEMENTED_CASE_IDS until
    remaining bodies are authored.
    """
    from np_integrated_runner import run_suite
    from np_receipts import build_receipt

    admit_runner_identity()
    config_path = ROOT / RUNNER_CONFIG_NAME
    config = load_runner_config(config_path)
    case_ids = list(config["case_ids"])
    status = implementation_status_map(case_ids)
    held = [cid for cid, st in status.items() if st == "HOLD"]
    if held:
        # Honest gate: do not run a batch that would fabricate PASS for HOLDs.
        # Operator must admit only implemented IDs (or author remaining bodies).
        raise RunnerEntryHeld(
            "admitted case_ids include explicit HOLD bodies: "
            + ",".join(held)
            + "; narrow batch to implemented "
            + ",".join(sorted(IMPLEMENTED_CASE_IDS))
            + " or complete HOLD bodies before launch_ready run"
        )

    registry = build_registry_from_suite(case_ids)
    if set(registry) != set(case_ids):
        raise RunnerEntryHeld("registry binding mismatch")

    console = BoundedOutput()
    sys.stdout = console  # type: ignore[assignment]
    sys.stderr = console  # type: ignore[assignment]

    case_results: list[dict[str, Any]] = []

    def record_case(case_id: str, result: dict[str, Any]) -> None:
        case_results.append({"case_id": case_id, "result": result})

    report = run_suite(
        config=config,
        registry=registry,
        runtime_pins=config["runtime_pins"],
        record_case=record_case,
    )
    receipt = build_receipt(
        kind="runner_suite_report",
        report=report,
        implementation_status=status,
        console_sha256=console.sha.hexdigest().upper(),
        console_bytes=console.length,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CaseBodyHold as exc:
        print(
            json.dumps({"status": "STOP", "kind": "CaseBodyHold", "case_id": exc.case_id, "reason": exc.reason}),
            file=sys.stderr,
        )
        raise SystemExit(125)
    except RunnerEntryHeld as exc:
        print(f"HELD: {exc}", file=sys.stderr)
        raise SystemExit(125)
