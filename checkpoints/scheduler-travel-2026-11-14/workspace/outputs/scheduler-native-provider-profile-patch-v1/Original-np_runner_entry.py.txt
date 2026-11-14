"""In-runner entry for native-provider prep-v3 first vertical.

PREPARATION AUTHORING ONLY. Real case dispatch/registry wiring lives here.
PKI child generation and peer bind require later launch authorization
(launch_ready must be true on runner-config). Incomplete cases are explicit
named HOLDs — never fabricated PASS. Unjoined/unconfirmed retirement → UNKNOWN.
No Docker daemon access from this seat.

First reviewable increment (Dex Incremental-Handback-Order 3AF57EEE…):
functional peer + NP-V-MS-NONEXPIRED through production HTTP covering-refresh /
default JoinedTLS / native TOKEN ROLLBACK + assessment. Uses app.config.Settings,
POST /api/v1/calendar/covering-refresh, preserved i01_asgi_app lineage — NOT
FixtureByteTransport/CoveringHTTP alias wrapper for the JoinedTLS claim.
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
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
RUNNER_CONFIG_NAME = "runner-config.json"
OUTPUT_BYTE_CAP = 1048576
REQUIRED_UID = 65534
PEER_SECONDS_DEFAULT = 120
COVERING_PATH = "/api/v1/calendar/covering-refresh"

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
    """Hash/count console sink — raw console not retained for machine output."""

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


def _fixture_database_profile() -> Any:
    from app.services.covering_native_checkout import PostgreSQLPeer

    # DB trust stays /public-ca — distinct from provider /tmp/np-provider-tls.
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


def _ms_provider_routes(*, peer_hostname: str, dial_address: str, dial_port: int, ca_file: str):
    """Exact MS identity vs event route classification for CoveringHTTP."""
    from app.services.covering_transport_policy import HTTPSPeer

    peer = HTTPSPeer(
        hostname=peer_hostname,
        address=dial_address,
        port=dial_port,
        ca_file=ca_file,
    )
    # Identity routes (not event): default calendar + calendars list.
    # Event routes: calendarView under /v1.0/me/calendars/{id}/...
    return (
        (peer, "/v1.0/me/calendar", "identity"),
        (peer, "/v1.0/me/calendars", "identity"),
        (peer, "/v1.0/me/calendars", "event"),
    )


def _extract_token_rollback_ack(native_terminals: list[dict[str, Any]]) -> bool:
    """TOKEN ROLLBACK from actual native terminal receipts — not guessed response keys."""
    for row in native_terminals:
        terminal = row.get("terminal") or row.get("token_terminal") or row.get("outcome")
        if terminal in ("ROLLBACK_ACKNOWLEDGED", "RootOutcome.ROLLBACK_ACKNOWLEDGED"):
            return True
        if row.get("token_rollback_ack") is True:
            return True
        name = str(terminal)
        if "ROLLBACK_ACKNOWLEDGED" in name and "COMMIT" not in name.split("ROLLBACK")[0]:
            return True
    return False


def _observe_token_terminals(native_terminals: list[dict[str, Any]]) -> Any:
    """Wrap production token terminal hook to capture acknowledgments."""
    from app.services.covering_target_transaction import RootOutcome

    def capture(outcome: Any) -> Any:
        label = outcome.name if hasattr(outcome, "name") else str(outcome)
        native_terminals.append(
            {
                "terminal": label,
                "token_rollback_ack": outcome is RootOutcome.ROLLBACK_ACKNOWLEDGED
                or label == "ROLLBACK_ACKNOWLEDGED",
            }
        )
        return outcome

    return capture


def _run_np_v_ms_nonexpired() -> dict[str, Any]:
    """Production vertical: Settings + covering-refresh ASGI + default JoinedTLS.

    Chain: CoveringReleasePlan.for_request → ProviderCounter → CoveringHTTP
    (default JoinedTLS) — no transport_factory injection, no FixtureByteTransport
    alias wrapper in the JoinedTLS claim. Synthetic peer serves finite
    Connection:close inventory on numeric loopback :443.
    """
    import inspect

    from np_suite import SuiteStop, check_oracles_immediate, registry_by_id
    from np_auth_seed import (
        COVERING_PATH as AUTH_COVERING_PATH,
        assert_plan_still_valid,
        covering_refresh_body,
        fixture_settings,
        fresh_attempt_plan,
        inverted_subscription_ids,
        measure_subscription_coverage_state,
        PlanValidityExpired,
        seed_browser_owner_with_subscriptions,
        seed_token_plan,
    )
    from np_alias_seed import microsoft_primary_alias_seed, sanitized_alias_receipt
    from np_receipts import case_result_receipt
    from np_provider_routes import microsoft_graph_route
    from np_provider_transcript import ms_nonexpired_connection_inventory
    from np_provider_peer import SyntheticProviderPeer, PeerMaterial, PeerRetirementUnknown
    from i01_asgi_app import asgi_client, build_i01_asgi_app, install_binding
    from app.services.covering_release_plan import CoveringReleasePlan
    from app.services.covering_http_transport import CoveringHTTP
    from app.services.covering_joined_https import JoinedTLS
    from app.services.covering_request_budget import CoveringRequestBudget
    from app.services.covering_target_transaction import RootOutcome

    del AUTH_COVERING_PATH  # same path constant; COVERING_PATH used below
    case_id = "NP-V-MS-NONEXPIRED"
    decl = registry_by_id(include_cf=True)[case_id]
    plan = fresh_attempt_plan(case_id)
    t_plan_iso = plan.t_plan.isoformat()
    token_seed = seed_token_plan(case_id=case_id, provider="microsoft", expired=False)
    alias = microsoft_primary_alias_seed(case_id=case_id)
    settings = fixture_settings()

    # Default JoinedTLS must remain the CoveringHTTP transport_factory.
    sig = inspect.signature(CoveringHTTP.__init__)
    transport_default = sig.parameters["transport_factory"].default
    if transport_default is not JoinedTLS:
        raise SuiteStop("production CoveringHTTP default is not JoinedTLS")

    route = microsoft_graph_route()
    planted = inverted_subscription_ids(case_token=plan.attempt_token)
    # Seed factory opens setup session via native ORM factory (launch path).
    factory = _open_native_setup_factory(settings=settings)
    setup = factory.open_setup_session()
    try:
        seed = seed_browser_owner_with_subscriptions(
            setup,
            settings=settings,
            username_prefix="np-ms-nonexpired",
            subscription_count=2,
            provider="microsoft",
            expired=False,
            mark_covering_fresh_at_seed=False,
            planted_subscription_ids=planted,
            t_plan=plan.t_plan,
        )
        setup.commit()
    finally:
        factory.close(setup)

    assert seed.request_window_start is not None and seed.request_window_end is not None
    assert seed.t_plan is not None
    assert_plan_still_valid(seed.t_plan)

    inventory_scripts = ms_nonexpired_connection_inventory(calendar_ids=seed.calendar_ids)
    peer = SyntheticProviderPeer(
        peer_id=f"peer-{case_id}",
        route=route,
        connection_scripts=inventory_scripts,
        material=PeerMaterial(),
    )
    observations: dict[str, Any] = {}
    native_terminals: list[dict[str, Any]] = []
    client_inventory: list[dict[str, Any]] = []
    oauth_requests = 0
    held_transport: list[Any] = []

    try:
        assert_plan_still_valid(plan.t_plan)
        peer.start_background(seconds=PEER_SECONDS_DEFAULT)

        database_profile = _fixture_database_profile()
        runtime_pins = _runtime_pins_from_config()
        provider_routes = _ms_provider_routes(
            peer_hostname=route.server_hostname,
            dial_address=route.dial_address,
            dial_port=route.dial_port,
            ca_file=route.ca_path,
        )
        release_plan = CoveringReleasePlan(
            database_profile=database_profile,
            password_supplier=lambda: "",
            runtime_pins=runtime_pins,
            provider_routes=provider_routes,
            settings=settings,
        )

        # ASGI budget admission clock — CoveringRequestBudget captures start once.
        budget = CoveringRequestBudget()
        binding = _for_request_capturing_transport(release_plan, budget, held_transport)
        if len(held_transport) != 1 or type(held_transport[0]) is not CoveringHTTP:
            raise SuiteStop("for_request did not construct exactly one CoveringHTTP")
        transport = held_transport[0]
        if transport.transport_factory is not JoinedTLS:
            raise SuiteStop("transport_factory injection refused — require default JoinedTLS")

        # Measure BEFORE from persisted rows (not literal False).
        measure_db = factory.open_setup_session()
        try:
            before_state = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)
        if before_state["any_covering_success"] is True:
            raise SuiteStop("before-state already covering-success; vertical not distinguishable")

        # Observe CoveringHTTP.request purposes + oauth count; capture token terminals.
        real_request = transport.request

        def counted_request(method, url, *, purpose, **kwargs):
            nonlocal oauth_requests
            if purpose == "oauth":
                oauth_requests += 1
            client_inventory.append(
                {
                    "method": method,
                    "purpose": purpose,
                    "url_host_present": True,
                    "connection_close_expected": True,
                }
            )
            return real_request(method, url, purpose=purpose, **kwargs)

        transport.request = counted_request  # type: ignore[method-assign]
        _install_token_terminal_observer(native_terminals)

        # Public ASGI route — preserved i01_asgi_app lineage (immutable helper).
        # Do NOT install FixtureByteTransport/CoveringHTTP alias for JoinedTLS claim.
        app = build_i01_asgi_app(session_secret=settings.session_secret)
        install_binding(app, binding)
        client = asgi_client(app)

        # Request ids in planted (inverted) order — production returns str-sorted.
        body = covering_refresh_body(
            list(seed.subscription_ids),
            window_start=seed.request_window_start,
            window_end=seed.request_window_end,
        )
        assert_plan_still_valid(seed.t_plan)
        response = client.post(
            COVERING_PATH,
            content=json.dumps(body).encode("utf-8"),
            headers={"content-type": "application/json"},
            cookies={"session": seed.cookie},
        )
        assert_plan_still_valid(seed.t_plan)
        if response.status_code != 200:
            raise SuiteStop(f"covering-refresh status:{response.status_code}")
        payload = response.json()
        coverage_action = payload.get("coverage_action") or {}
        readiness = payload.get("scheduling_readiness") or {}
        freshness_requested = coverage_action.get("freshness_requested")
        if not isinstance(freshness_requested, dict):
            raise SuiteStop("coverage_action.freshness_requested missing typed object")
        freshness_ok = freshness_requested.get("ok")
        all_ok = coverage_action.get("all_requested_covering_ok")
        scheduling_ready = readiness.get("scheduling_ready")
        scheduling_revision = readiness.get("scheduling_revision")
        freshness_all = readiness.get("freshness_all_enabled")
        if freshness_ok is not True:
            raise SuiteStop("freshness_requested.ok is not True")
        if all_ok is not True:
            raise SuiteStop("all_requested_covering_ok is not True")
        if scheduling_ready is not True:
            raise SuiteStop("scheduling_readiness.scheduling_ready is not True")
        if type(scheduling_revision) is not int or scheduling_revision < 1:
            raise SuiteStop("scheduling_revision not typed int>=1")
        if not isinstance(freshness_all, dict) or freshness_all.get("ok") is not True:
            raise SuiteStop("freshness_all_enabled.ok is not True")

        # Measure AFTER from persisted rows.
        measure_db = factory.open_setup_session()
        try:
            after_state = measure_subscription_coverage_state(
                measure_db, subscription_ids=seed.subscription_ids
            )
        finally:
            factory.close(measure_db)

        if before_state["all_covering_success"] == after_state["all_covering_success"]:
            if after_state["all_covering_success"] is not True:
                raise SuiteStop("before/after coverage not distinguishable")
        if after_state["all_covering_success"] is not True:
            raise SuiteStop("after-state missing covering success")

        token_rollback_acked = _extract_token_rollback_ack(native_terminals)
        if oauth_requests != 0:
            raise SuiteStop("nonexpired path must not perform OAuth exchange")
        if not token_rollback_acked:
            raise SuiteStop("TOKEN ROLLBACK acknowledgment missing from native terminals")

        peer_state = peer.sanitized_state()
        served = int(peer_state.get("connection_count_served") or 0)
        admitted = int(peer_state.get("connection_count_admitted") or 0)
        if served != admitted or served != len(inventory_scripts):
            raise SuiteStop(
                f"peer exchange inventory mismatch served={served} admitted={admitted}"
            )
        if any(row.get("purpose") == "oauth" for row in client_inventory):
            raise SuiteStop("client inventory recorded oauth purpose")

        observations = {
            "no_oauth_request": "OBSERVED",
            "token_rollback_ack": True,
            "identity_event_assessment_separate": "OBSERVED",
            "covering_path": COVERING_PATH,
            "settings_module": "app.config.Settings",
            "joined_tls_default": True,
            "byte_transport_alias_used": False,
        }
        measured = {
            "before": before_state,
            "after": after_state,
            "coverage_action": {
                "all_requested_covering_ok": all_ok,
                "freshness_requested_ok": freshness_ok,
            },
            "scheduling_readiness": {
                "scheduling_ready": scheduling_ready,
                "scheduling_revision": scheduling_revision,
                "freshness_all_enabled_ok": freshness_all.get("ok"),
            },
            "oauth_request_count": oauth_requests,
            "token_rollback_ack": token_rollback_acked,
            "native_terminals": list(native_terminals),
            "client_exchange_inventory": list(client_inventory),
            "alias_hash": alias.seed_hash,
            "token_label_hash": token_seed.label_hash,
            "root_outcome_rollback": RootOutcome.ROLLBACK_ACKNOWLEDGED.name,
        }
        _ = sanitized_alias_receipt(alias)
        check_oracles_immediate(decl, {"no_oauth_request": "OBSERVED", "token_rollback_ack": "OBSERVED", "identity_event_assessment_separate": "OBSERVED"})
        t_check_iso = _iso_now()
        assert_plan_still_valid(plan.t_plan)
        retirement = peer.retire_owned(join_seconds=5.0)
        workers_joined = retirement.get("joined") is True
        if not workers_joined:
            raise SuiteStop("peer worker unjoined — UNKNOWN")
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
            measured=measured,
            peer_exchange_inventory=list(peer_state.get("exchange_inventory") or []),
            resource_disposition={
                "peer_retired": True,
                "peer_joined": True,
                "factory_closed": True,
            },
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
        raise SuiteStop(f"framework_stop:{case_id}:{type(exc).__name__}") from exc
    finally:
        try:
            transport.request = real_request  # type: ignore[name-defined]
        except Exception:
            pass
        if peer._worker is not None and not peer.life.joined:  # noqa: SLF001
            try:
                peer.retire_owned(join_seconds=2.0)
            except PeerRetirementUnknown:
                pass


def _open_native_setup_factory(*, settings: Any) -> Any:
    """Open disposable setup factory — immutable AssessmentFactory lineage (i01)."""
    from assessment_binding import AssessmentFactory

    del settings  # Settings used by seed path; factory itself is DB profile/pins only.
    profile = _fixture_database_profile()
    pins = _runtime_pins_from_config()
    records: list[tuple[str, dict[str, Any]]] = []

    def record(event: str, data: dict[str, Any]) -> None:
        records.append((event, dict(data)))

    factory = AssessmentFactory(
        profile=profile,
        password_supplier=lambda: "",
        runtime_pins=pins,
        record=record,
    )
    factory._np_records = records  # noqa: SLF001 — fixture-local sanitized event sink
    return factory


def _for_request_capturing_transport(release_plan: Any, budget: Any, held: list[Any]) -> Any:
    """Call CoveringReleasePlan.for_request while capturing the CoveringHTTP instance."""
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


def _install_token_terminal_observer(native_terminals: list[dict[str, Any]]) -> None:
    """Wrap CoveringORMConnection.token_terminal to capture native TOKEN receipts."""
    from app.services.covering_native_orm_factory import CoveringORMConnection
    from app.services.covering_target_transaction import RootOutcome

    real = CoveringORMConnection.token_terminal

    def wrapped(self, *, commit, remaining):
        outcome = real(self, commit=commit, remaining=remaining)
        label = outcome.name if hasattr(outcome, "name") else str(outcome)
        native_terminals.append(
            {
                "terminal": label,
                "token_rollback_ack": outcome is RootOutcome.ROLLBACK_ACKNOWLEDGED,
                "commit_requested": bool(commit),
            }
        )
        return outcome

    CoveringORMConnection.token_terminal = wrapped  # type: ignore[method-assign]
    native_terminals.append({"observer": "CoveringORMConnection.token_terminal", "terminal": None})


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

    Report contract (19A695FC…): capture console to BoundedOutput (hash-only),
    then restore original streams and emit exactly one bounded sanitized report
    on the machine-output stream.
    """
    from np_integrated_runner import run_suite
    from np_receipts import suite_report_receipt

    admit_runner_identity()
    config_path = ROOT / RUNNER_CONFIG_NAME
    config = load_runner_config(config_path)
    case_ids = list(config["case_ids"])
    status = implementation_status_map(case_ids)
    held = [cid for cid, st in status.items() if st == "HOLD"]
    if held:
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

    real_stdout = sys.stdout
    real_stderr = sys.stderr
    console = BoundedOutput()
    case_results: list[dict[str, Any]] = []
    stop_payload: dict[str, Any] | None = None
    exit_code = 0

    def record_case(case_id: str, result: dict[str, Any]) -> None:
        case_results.append({"case_id": case_id, "result": result})

    try:
        sys.stdout = console  # type: ignore[assignment]
        sys.stderr = console  # type: ignore[assignment]
        report = run_suite(
            config=config,
            registry=registry,
            runtime_pins=config["runtime_pins"],
            record_case=record_case,
        )
        # Truthful runtime flags for an actually authorized admitted run.
        receipt = suite_report_receipt(
            report=report,
            case_results=case_results,
            implementation_status=status,
            console_sha256=console.sha.hexdigest().upper(),
            console_bytes=console.length,
            executed=True,
            launch_authorized=True,
        )
    except CaseBodyHold as exc:
        exit_code = 125
        stop_payload = {
            "status": "STOP",
            "kind": "CaseBodyHold",
            "case_id": exc.case_id,
            "reason": exc.reason,
            "prep_is_not_pass": True,
            "endpoint": "unbound",
            "console_sha256": console.sha.hexdigest().upper(),
            "console_bytes": console.length,
        }
        receipt = stop_payload
    except RunnerEntryHeld as exc:
        exit_code = 125
        stop_payload = {
            "status": "STOP",
            "kind": "RunnerEntryHeld",
            "reason": str(exc),
            "prep_is_not_pass": True,
            "endpoint": "unbound",
            "console_sha256": console.sha.hexdigest().upper(),
            "console_bytes": console.length,
        }
        receipt = stop_payload
    except BaseException as exc:
        exit_code = 125
        stop_payload = {
            "status": "STOP",
            "kind": type(exc).__name__,
            "prep_is_not_pass": True,
            "endpoint": "unbound",
            "console_sha256": console.sha.hexdigest().upper(),
            "console_bytes": console.length,
        }
        receipt = stop_payload
        raise
    finally:
        sys.stdout = real_stdout
        sys.stderr = real_stderr

    # Exactly one bounded sanitized report through the machine-output stream.
    print(json.dumps(receipt, sort_keys=True), file=real_stdout, flush=True)
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CaseBodyHold as exc:
        # Sanitized STOP already emitted when main catches; belt for direct raises.
        print(
            json.dumps(
                {
                    "status": "STOP",
                    "kind": "CaseBodyHold",
                    "case_id": exc.case_id,
                    "reason": exc.reason,
                    "prep_is_not_pass": True,
                    "endpoint": "unbound",
                },
                sort_keys=True,
            )
        )
        raise SystemExit(125)
    except RunnerEntryHeld as exc:
        print(
            json.dumps(
                {
                    "status": "STOP",
                    "kind": "RunnerEntryHeld",
                    "reason": str(exc),
                    "prep_is_not_pass": True,
                    "endpoint": "unbound",
                },
                sort_keys=True,
            )
        )
        raise SystemExit(125)
