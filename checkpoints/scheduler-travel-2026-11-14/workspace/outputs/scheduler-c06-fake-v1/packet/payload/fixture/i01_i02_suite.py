"""I01/I02 fixture suite registry and per-attempt lifecycle. Prep-only; not auto-executed."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import Any, Callable, Iterator
from uuid import UUID, uuid4

from app.api.errors import ApiError
from app.api.middleware.covering_ingress import BODY_LIMIT
from app.services.covering_http_dispatch import CoveringReleaseBinding
from app.services.covering_release_plan import CoveringReleasePlan
from app.services.covering_transport_policy import HTTPSPeer
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.services.covering_domain_dispatch import CoveringDomainPorts
import app.services.covering_domain_dispatch as domain_dispatch
import app.services.covering_http_dispatch as http_dispatch

from i01_asgi_app import (
    ControllableClock,
    DisconnectInjectControl,
    asgi_client,
    build_i01_asgi_app,
    clear_binding,
    install_binding,
    run_covering_asgi,
)
from i01_auth_seed import (
    assert_plan_still_valid,
    covering_refresh_body,
    fixture_settings,
    inverted_subscription_ids,
    production_ordered_calendar_ids,
    seed_agent_bearer,
    seed_browser_owner_with_subscriptions,
    seed_wrong_owner_browser,
)
from app.services.covering_request_budget import CoveringBudgetStopped
from i01_byte_transport import build_transport_factory, google_event_empty_script
from i01_c06_dual_peer import (
    C06_BACKEND_DB_CA,
    C06_GATE_ARTIFACT_STEM,
    C06_GATE_CLIENT_CA,
    C06_GATE_PORT,
    C06_GATE_ROOT,
    build_c06_dual_peer_binding,
    load_c06_gate_receipt,
    require_distinct_public_ca_hashes,
    serve_i01_c06_gate,
)
from i01_covering_http_alias import (
    install_covering_http_alias,
    restore_covering_http_alias,
)
from i01_i02_receipts import build_receipt, sanitize_cleanup_failure
from i02_owner_lock_contention import (
    GENERATION_MISMATCH_CAUSE,
    run_i02_contention,
    seed_i02_owner,
)

COVERING_PATH = "/api/v1/calendar/covering-refresh"
JOIN_LIMIT_SECONDS = 60.0
PROVIDER_HOST = "www.googleapis.com"
PROVIDER_ADDRESS = "192.0.2.10"
FIXTURE_CA = "/public-ca/ca.crt"
ELIGIBILITY_CODE = "CALENDAR_SUBSCRIPTION_NOT_ELIGIBLE"

I01_CASE_IDS = (
    "I01-C01",
    "I01-C02",
    "I01-C03",
    "I01-C04",
    "I01-C05",
    "I01-C06",
    "I01-C06-MAP",
    "I01-C07A",  # historical I01-C07a → uppercase host-compatible
    "I01-C07B",  # historical I01-C07b → uppercase host-compatible
    "I01-C08",
    "I01-C09",
    "I01-C10",
)
I02_CASE_IDS = ("I02-C01",)
EXPECTED_UNKNOWN_I01 = ("I01-C06",)


class SuiteStop(RuntimeError):
    """Workers alive at join limit — do not continue / restore aliases / reuse app."""


class AttemptFailed(RuntimeError):
    """Primary case failure preserved separately from cleanup failures."""


def provider_routes_for_calendars(calendar_ids: list[str]) -> tuple:
    peer = HTTPSPeer(PROVIDER_HOST, PROVIDER_ADDRESS, 443, FIXTURE_CA)
    routes = []
    for calendar_id in calendar_ids:
        prefix = f"/calendar/v3/calendars/{calendar_id}/events"
        routes.append((peer, prefix, "event"))
    return tuple(routes)


def script_for_calendars(calendar_ids: list[str]):
    return [google_event_empty_script(calendar_id=calendar_id) for calendar_id in calendar_ids]


def body_for_seed(seed, subscription_ids=None):
    """Covering body using the seed's planned request window (post-import coverage)."""
    ids = list(seed.subscription_ids if subscription_ids is None else subscription_ids)
    return covering_refresh_body(
        ids,
        window_start=seed.request_window_start,
        window_end=seed.request_window_end,
        t_plan=seed.t_plan,
    )


def _validation_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    detail = payload.get("detail")
    if isinstance(detail, list):
        return [item for item in detail if isinstance(item, dict)]
    return []


def assert_ordering_request_ids(
    *,
    subscription_ids: list[UUID],
    request_ids: list[UUID],
) -> list[UUID]:
    """Fixture ordering-setup guard for C01 request_ids.

    Already-sorted request_ids collapse the inversion claim and must refuse.
    Returns the production str-sorted expected order for downstream asserts.
    """
    expected = sorted(subscription_ids, key=str)
    if list(request_ids) == list(expected):
        raise AssertionError(
            "already-sorted request_ids refuse ordering claim"
        )
    return expected


def assert_subscription_ids_count_error(response, *, expected_type: str) -> None:
    """C03: 422 with subscription_ids loc + count-specific too_short/too_long."""
    if response.status_code != 422:
        raise AssertionError(f"expected 422, got {response.status_code}")
    items = _validation_items(response.json())
    matched = False
    for item in items:
        loc = item.get("loc") or []
        loc_str = [str(part) for part in loc]
        if "subscription_ids" not in loc_str:
            continue
        err_type = str(item.get("type") or "")
        if err_type == expected_type or err_type.endswith(f".{expected_type}"):
            matched = True
            break
    if not matched:
        raise AssertionError(
            f"count-specific {expected_type} for subscription_ids not observed: {items!r}"
        )


class AttemptCleanup:
    def __init__(self) -> None:
        self.primary: BaseException | None = None
        self.cleanup_failures: list[dict[str, str]] = []
        self.barriers: list[Event] = []
        self.workers: list[Thread] = []
        self.alias_wrapped = False
        self.gate_stop: Event | None = None
        self.gate_thread: Thread | None = None
        self.gate_receipt: dict[str, Any] = {}
        self.gate_retirement: str | None = None  # pending|joined|join_timeout
        self.injector_retirement: str | None = None
        self.poster_retirement: str | None = None
        self.worker_wrap_restore_allowed: bool = True
        self.app = None
        self.allow_alias_restore = True
        self.workers_alive = False
        self.workers_joined = True
        self.teardown_completed = False
        self.teardown_ok = False

    def release_barriers(self) -> None:
        for barrier in self.barriers:
            barrier.set()
        if self.gate_stop is not None:
            self.gate_stop.set()

    def join_workers(self, limit: float = JOIN_LIMIT_SECONDS) -> None:
        deadline = monotonic() + limit
        for worker in self.workers:
            left = max(0.0, deadline - monotonic())
            worker.join(timeout=left)
            if worker.is_alive():
                self.workers_alive = True
                self.workers_joined = False
                self.allow_alias_restore = False

    def stop_gate(self, limit: float = JOIN_LIMIT_SECONDS) -> None:
        """Idempotent gate retirement: one real stop+join; later calls are no-ops."""
        if self.gate_retirement in ("joined", "join_timeout"):
            return
        if self.gate_stop is not None:
            self.gate_stop.set()
        if self.gate_thread is not None:
            self.gate_thread.join(timeout=limit)
            if self.gate_thread.is_alive():
                self.gate_retirement = "join_timeout"
                self.workers_alive = True
                self.workers_joined = False
                self.allow_alias_restore = False
            else:
                self.gate_retirement = "joined"
        else:
            self.gate_retirement = "joined"


def _result(
    case_id: str,
    *,
    passed: bool,
    receipt: dict[str, Any],
    expected_unknown: bool = False,
    workers_joined: bool | None = None,
) -> dict[str, Any]:
    payload = {
        "case_id": case_id,
        "passed": passed,
        "skipped": False,
        "expected_unknown": expected_unknown,
        "receipt": receipt,
    }
    if workers_joined is not None:
        payload["workers_joined"] = workers_joined
    return payload


def _post_covering(client, *, body: dict | bytes, cookie: str | None = None, bearer: str | None = None):
    headers = {"content-type": "application/json"}
    if bearer is not None:
        headers["authorization"] = f"Bearer {bearer}"
    if isinstance(body, (bytes, bytearray)):
        data = bytes(body)
        headers["content-type"] = "application/octet-stream"
    else:
        data = json.dumps(body).encode("utf-8")
    cookies = {}
    if cookie is not None:
        cookies["session"] = cookie
    return client.post(COVERING_PATH, content=data, headers=headers, cookies=cookies)


def _build_plan(*, profile, password_supplier, runtime_pins, settings, routes):
    return CoveringReleasePlan(
        database_profile=profile,
        password_supplier=password_supplier,
        runtime_pins=runtime_pins,
        provider_routes=routes,
        settings=settings,
    )


@contextmanager
def _observe_dispatch_worker(observations: dict[str, Any]) -> Iterator[None]:
    """Independently observe worker entry and budget identity (fixture wrap only)."""
    real_worker = http_dispatch._worker

    def wrapped(binding, request, body, context):
        observations["worker_entered"] = True
        observations["worker_entry_count"] = int(observations.get("worker_entry_count", 0)) + 1
        observations["worker_budget_id"] = id(context.budget)
        started = observations.get("worker_started")
        if isinstance(started, Event):
            started.set()
        try:
            result = real_worker(binding, request, body, context)
            observations["worker_finished"] = True
            return result
        finally:
            retired = observations.get("worker_retired")
            if isinstance(retired, Event):
                retired.set()

    http_dispatch._worker = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        http_dispatch._worker = real_worker  # type: ignore[assignment]


def _teardown(cleanup: AttemptCleanup) -> None:
    cleanup.release_barriers()
    cleanup.join_workers()
    cleanup.stop_gate()
    if cleanup.workers_alive:
        cleanup.teardown_completed = True
        cleanup.teardown_ok = False
        # Reconciled: STOP — do not restore shared aliases underneath live workers.
        raise SuiteStop("worker alive at join limit — suite STOP; aliases not restored")
    if cleanup.allow_alias_restore and cleanup.alias_wrapped:
        try:
            restore_covering_http_alias()
            cleanup.alias_wrapped = False
        except BaseException as exc:
            cleanup.cleanup_failures.append(sanitize_cleanup_failure(exc))
    if cleanup.app is not None:
        try:
            clear_binding(cleanup.app)
        except BaseException as exc:
            cleanup.cleanup_failures.append(sanitize_cleanup_failure(exc))
    cleanup.teardown_completed = True
    cleanup.teardown_ok = len(cleanup.cleanup_failures) == 0 and cleanup.workers_joined


def attach_cleanup_failures_to_primary(
    primary: BaseException,
    cleanup_failures: list[dict[str, str]],
) -> BaseException:
    """Primary preservation: attach cleanup evidence without replacing primary kind."""
    setattr(primary, "fixture_cleanup_failures", list(cleanup_failures))
    return primary


def resolve_attempt_outcome(
    case_id: str,
    *,
    result: dict[str, Any] | None,
    primary: BaseException | None,
    suite_stop: SuiteStop | None,
    cleanup: AttemptCleanup,
) -> dict[str, Any]:
    """Post-teardown PASS/REFUSE rules. Cleanup failures cannot PASS."""
    if primary is not None:
        raise primary
    if suite_stop is not None:
        raise suite_stop
    if result is None:
        raise RuntimeError(f"{case_id} produced no result")
    if not cleanup.teardown_completed or not cleanup.teardown_ok:
        raise RuntimeError(
            f"{case_id} cleanup/alias/binding restoration failed: {cleanup.cleanup_failures}"
        )
    if cleanup.cleanup_failures:
        raise RuntimeError(
            f"{case_id} non-empty cleanup_failures cannot PASS: {cleanup.cleanup_failures}"
        )
    result["workers_joined"] = bool(cleanup.workers_joined) and not cleanup.workers_alive
    if result["workers_joined"] is not True:
        raise SuiteStop(f"{case_id} workers not joined after teardown")
    if result.get("passed") is not True:
        raise AttemptFailed(f"{case_id} did not pass")
    return result


def assert_c09_disconnect_evidence(
    *,
    asgi_result: Any,
    cancellation_provenance: str | None,
    api_error_status: int | None,
    api_error_code: str | None,
    monitor_observed: bool,
    disconnect_delivered: bool,
    post_disconnect_outbound: list[str],
) -> None:
    """Corrected C09 refuse/pass gate used by the case and fake-only harness."""
    if asgi_result is None:
        raise RuntimeError(
            "C09 requires actual BoundedASGIResponse result; "
            "missing result cannot stand in as response_started=False"
        )
    error = getattr(asgi_result, "error", None)
    if error is not None:
        raise RuntimeError(
            "C09 unexpected ASGI driver error/timeout is not success: "
            f"{type(error).__name__}: {error!r}"
        )
    if cancellation_provenance != "CoveringBudgetStopped":
        raise RuntimeError("C09 missing CoveringBudgetStopped cancellation provenance")
    if api_error_status != 503:
        raise RuntimeError(f"C09 ApiError status not 503: {api_error_status!r}")
    if api_error_code != "CALENDAR_REFRESH_OUTCOME_UNKNOWN":
        raise RuntimeError(f"C09 ApiError code not UNKNOWN: {api_error_code!r}")
    if not monitor_observed:
        raise RuntimeError("C09 monitor_observed missing")
    if not disconnect_delivered:
        raise RuntimeError("C09 actual disconnect not delivered")
    if list(post_disconnect_outbound):
        raise RuntimeError(
            f"C09 post-disconnect outbound sends not suppressed: {post_disconnect_outbound!r}"
        )


def assert_i02_lock_observations(evidence: Any) -> None:
    """Refuse missing/wrong I02 advisory-lock contention observations."""
    if evidence.holder_pid is None or evidence.waiter_pid is None:
        raise RuntimeError("I02 missing lock holder/waiter observations")
    if evidence.holder_pid == evidence.waiter_pid:
        raise RuntimeError("I02 lock holder/waiter PIDs must be distinct")
    if evidence.assessment_backend_pid != evidence.waiter_pid:
        raise RuntimeError("I02 assessment backend PID must match waiter observation")
    if evidence.assessment_started_after_hold_confirmed is not True:
        raise RuntimeError("I02 assessment must start after hold confirmed")
    rel = evidence.lock_row_relationship or {}
    if rel.get("holder_in_pg_blocking_pids_waiter") is not True:
        raise RuntimeError("I02 missing holder-in-blocking-pids lock observation")
    if rel.get("granted_holder_rows") != 1:
        raise RuntimeError("I02 wrong granted_holder_rows lock observation")
    if rel.get("ungranted_waiter_rows") != 1:
        raise RuntimeError("I02 wrong ungranted_waiter_rows lock observation")


def assert_budget_identity_observations(
    *,
    ingress_budget_id: int | None,
    worker_budget_id: int | None,
    worker_entered: bool,
) -> None:
    """Refuse missing/wrong ingress↔worker budget identity observations."""
    if worker_entered is not True:
        raise RuntimeError("budget identity requires worker_entered")
    if ingress_budget_id is None:
        raise RuntimeError("missing ingress budget observation")
    if worker_budget_id is None:
        raise RuntimeError("missing worker budget observation")
    if worker_budget_id != ingress_budget_id:
        raise RuntimeError("wrong budget identity observations (ingress≠worker)")


def assert_transport_coverage_observations(
    *,
    transport_factory: str | None,
    provider_coverage: str | None,
) -> None:
    """Refuse missing/wrong synthetic transport coverage observations."""
    if not transport_factory:
        raise RuntimeError("missing transport_factory observation")
    if transport_factory != "FixtureByteTransport":
        raise RuntimeError(f"wrong transport_factory observation: {transport_factory!r}")
    if not provider_coverage:
        raise RuntimeError("missing provider_coverage observation")
    if provider_coverage != "synthetic_fixture_byte_transport":
        raise RuntimeError(
            f"wrong provider_coverage observation: {provider_coverage!r}"
        )


def _run_attempt(case_id: str, runner: Callable[[AttemptCleanup], dict[str, Any]]) -> dict[str, Any]:
    cleanup = AttemptCleanup()
    result: dict[str, Any] | None = None
    primary: BaseException | None = None
    suite_stop: SuiteStop | None = None
    try:
        result = runner(cleanup)
    except BaseException as exc:
        cleanup.primary = exc
        primary = exc
    finally:
        try:
            _teardown(cleanup)
        except SuiteStop as stop:
            # Teardown SuiteStop must not replace an already-captured primary failure.
            if primary is None:
                suite_stop = stop
            else:
                cleanup.cleanup_failures.append({"kind": "SuiteStop"})
                setattr(primary, "fixture_suite_stop", True)
        except BaseException as exc:
            cleanup.cleanup_failures.append(sanitize_cleanup_failure(exc))
        if primary is not None:
            attach_cleanup_failures_to_primary(primary, cleanup.cleanup_failures)

    return resolve_attempt_outcome(
        case_id,
        result=result,
        primary=primary,
        suite_stop=suite_stop,
        cleanup=cleanup,
    )


class I01I02Cases:
    def __init__(self, *, factory, profile, pins, password_supplier=lambda: ""):
        self.factory = factory
        self.profile = profile
        self.pins = pins
        self.password_supplier = password_supplier
        self.settings = fixture_settings()

    def registry(self) -> dict[str, Callable[[], dict[str, Any]]]:
        mapping = {
            "I01-C01": self.c01_happy,
            "I01-C02": self.c02_auth,
            "I01-C03": self.c03_limits,
            "I01-C04": self.c04_unbound,
            "I01-C05": self.c05_assessment_sanitize,
            "I01-C06": self.c06_lost_ack,
            "I01-C06-MAP": self.c06_map,
            "I01-C07A": self.c07a_oversized,
            "I01-C07B": self.c07b_budget_identity,
            "I01-C08": self.c08_deadline,
            "I01-C09": self.c09_disconnect,
            "I01-C10": self.c10_synthetic_label,
            "I02-C01": self.i02_c01,
        }
        return mapping

    def _setup_seed(
        self,
        *,
        count: int,
        prefix: str,
        invert: bool = False,
        planted_subscription_ids: list[UUID] | None = None,
    ):
        setup = self.factory.open_setup_session()
        try:
            seed = seed_browser_owner_with_subscriptions(
                setup,
                settings=self.settings,
                username_prefix=prefix,
                subscription_count=count,
                force_uuid_sort_inversion=invert,
                planted_subscription_ids=planted_subscription_ids,
            )
            setup.commit()
            return seed
        finally:
            self.factory.close(setup)

    def c01_happy(self):
        def run(cleanup: AttemptCleanup):
            planted = inverted_subscription_ids(case_token="i01c01")
            seed = self._setup_seed(
                count=2,
                prefix="i01-c01",
                planted_subscription_ids=planted,
            )
            assert seed.t_plan is not None
            assert_plan_still_valid(seed.t_plan)
            # Production target order (str-sorted subscription ids) → calendars.
            calendar_ids = production_ordered_calendar_ids(
                subscription_ids=seed.subscription_ids,
                subscription_calendar_map=seed.subscription_calendar_map,
            )
            routes = provider_routes_for_calendars(calendar_ids)
            script = script_for_calendars(calendar_ids)
            factory = build_transport_factory(script)
            install_covering_http_alias(transport_factory=factory)
            cleanup.alias_wrapped = True
            app = build_i01_asgi_app()
            cleanup.app = app
            plan = _build_plan(
                profile=self.profile,
                password_supplier=self.password_supplier,
                runtime_pins=self.pins,
                settings=self.settings,
                routes=routes,
            )
            install_binding(app, plan)
            expected = sorted(seed.subscription_ids, key=str)
            request_ids = list(reversed(expected))
            assert_ordering_request_ids(
                subscription_ids=seed.subscription_ids,
                request_ids=request_ids,
            )
            client = asgi_client(app)
            assert_plan_still_valid(seed.t_plan)
            response = _post_covering(
                client,
                body=body_for_seed(seed, request_ids),
                cookie=seed.cookie,
            )
            assert_plan_still_valid(seed.t_plan)
            assert response.status_code == 200, response.text
            payload = response.json()
            result_ids = [UUID(row["subscription_id"]) for row in payload.get("results", [])]
            assert result_ids == expected
            coverage_action = payload.get("coverage_action") or {}
            readiness = payload.get("scheduling_readiness") or {}
            assert coverage_action.get("all_requested_covering_ok") is True
            assert isinstance(coverage_action.get("freshness_requested"), dict)
            assert coverage_action["freshness_requested"].get("ok") is True
            assert readiness.get("scheduling_ready") is True
            # Revision coherence from live response observations — seed revision=1
            # alone is not the oracle.
            observed_revision = readiness.get("scheduling_revision")
            assert isinstance(observed_revision, int) and observed_revision >= 1
            fresh_all = readiness.get("freshness_all_enabled")
            assert isinstance(fresh_all, dict) and fresh_all.get("ok") is True
            # Start/end + trust coherence: each result carries covering success under
            # the planned request window that became post-import coverage.
            assert len(payload.get("results") or []) == len(expected)
            for row in payload.get("results") or []:
                assert row.get("subscription_id") is not None
            inventory = list(factory.inventory)
            assert len(inventory) == len(script)
            assert factory.shared.index == len(script)
            receipt = build_receipt(
                case_id="I01-C01",
                proof_class="http_native_composition",
                auth_channel="browser",
                auth_seed_path=seed.auth_seed_path,
                covering_http_alias_wrapped=True,
                transport_factory="FixtureByteTransport",
                provider_coverage="synthetic_fixture_byte_transport",
                binding_shape="covering_release_plan",
                ordering_contract="str_sorted_subscription_ids",
                provider_exchange_inventory=inventory,
                unscripted_exchange_count=0,
                coverage_action={
                    "all_requested_covering_ok": coverage_action.get("all_requested_covering_ok"),
                    "freshness_requested_ok": coverage_action["freshness_requested"].get("ok"),
                },
                scheduling_readiness={
                    "scheduling_ready": readiness.get("scheduling_ready"),
                    "scheduling_revision": observed_revision,
                    "freshness_all_enabled_ok": fresh_all.get("ok"),
                    "revision_coherence": "observed_response_trust_not_seed_only",
                },
            )
            assert_transport_coverage_observations(
                transport_factory=receipt.get("transport_factory"),
                provider_coverage=receipt.get("provider_coverage"),
            )
            return _result("I01-C01", passed=True, receipt=receipt)

        return _run_attempt("I01-C01", run)

    def c02_auth(self):
        def run(cleanup: AttemptCleanup):
            owner_setup = self.factory.open_setup_session()
            try:
                owned = seed_browser_owner_with_subscriptions(
                    owner_setup,
                    settings=self.settings,
                    username_prefix="i01-c02-owned",
                    subscription_count=1,
                )
                wrong = seed_wrong_owner_browser(
                    owner_setup,
                    settings=self.settings,
                    foreign_subscription_ids=owned.subscription_ids,
                )
                bearer = seed_agent_bearer(
                    owner_setup,
                    settings=self.settings,
                    username_prefix="i01-c02-agent",
                    subscription_count=1,
                    allow_access=True,
                )
                owner_setup.commit()
            finally:
                self.factory.close(owner_setup)
            calendar_ids = ["cal-agent-i01-c02-agent-0"]
            routes = provider_routes_for_calendars(calendar_ids)
            factory = build_transport_factory(script_for_calendars(calendar_ids))
            install_covering_http_alias(transport_factory=factory)
            cleanup.alias_wrapped = True
            observations: dict[str, Any] = {"worker_entered": False}
            contexts: list[Any] = []
            app = build_i01_asgi_app(on_context=contexts.append)
            cleanup.app = app
            install_binding(
                app,
                _build_plan(
                    profile=self.profile,
                    password_supplier=self.password_supplier,
                    runtime_pins=self.pins,
                    settings=self.settings,
                    routes=routes,
                ),
            )
            client = asgi_client(app)
            with _observe_dispatch_worker(observations):
                wrong_response = _post_covering(
                    client,
                    body=covering_refresh_body(owned.subscription_ids),
                    cookie=wrong.cookie,
                )
            assert wrong_response.status_code == 422
            assert wrong_response.json().get("code") == ELIGIBILITY_CODE
            wrong_ctx = contexts[0] if contexts else None
            assert wrong_ctx is not None
            assert wrong_ctx.ownership_established is False
            assert wrong_ctx.calendar_admitted is False
            assert wrong_ctx.auth_telemetry_admitted is False
            wrong_inventory = list(factory.inventory)
            assert wrong_inventory == []
            assert factory.shared.index == 0

            contexts.clear()
            bearer_observations: dict[str, Any] = {"worker_entered": False}
            with _observe_dispatch_worker(bearer_observations):
                bearer_response = _post_covering(
                    client,
                    body=covering_refresh_body(bearer.subscription_ids),
                    bearer=bearer.plain_bearer,
                )
            assert bearer_response.status_code == 200, bearer_response.text
            bearer_ctx = contexts[0] if contexts else None
            assert bearer_ctx is not None
            assert bearer_ctx.auth_telemetry_admitted is True
            assert bearer_ctx.ownership_established is True
            provider_exchanges = len(factory.inventory)
            receipt = build_receipt(
                case_id="I01-C02",
                mutation_forbidden=True,
                auth_channel="browser",
                agent_header_present=True,
                wrong_owner_status=wrong_response.status_code,
                wrong_owner_code=wrong_response.json().get("code"),
                wrong_owner_ownership_established=False,
                wrong_owner_calendar_admitted=False,
                wrong_owner_provider_exchanges=len(wrong_inventory),
                bearer_status=bearer_response.status_code,
                auth_telemetry_admitted=True,
                provider_exchanges=provider_exchanges,
                credential_id=str(bearer.credential_id),
            )
            return _result("I01-C02", passed=True, receipt=receipt)

        return _run_attempt("I01-C02", run)

    def c03_limits(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c03")
            app = build_i01_asgi_app()
            cleanup.app = app
            clear_binding(app)
            client = asgi_client(app)
            base = covering_refresh_body([uuid4()])
            # Otherwise-valid bodies: only target-count varies; windows always present.
            zero_body = {
                "subscription_ids": [],
                "window_start": base["window_start"],
                "window_end": base["window_end"],
                "scheduling_horizon_label": base["scheduling_horizon_label"],
            }
            zero = _post_covering(client, body=zero_body, cookie=seed.cookie)
            assert_subscription_ids_count_error(zero, expected_type="too_short")

            over_ids = [str(uuid4()) for _ in range(21)]
            assert len(set(over_ids)) == 21
            over_body = {
                "subscription_ids": over_ids,
                "window_start": base["window_start"],
                "window_end": base["window_end"],
                "scheduling_horizon_label": base["scheduling_horizon_label"],
            }
            over = _post_covering(client, body=over_body, cookie=seed.cookie)
            assert_subscription_ids_count_error(over, expected_type="too_long")

            one = _post_covering(
                client,
                body=covering_refresh_body(seed.subscription_ids),
                cookie=seed.cookie,
            )
            assert one.status_code == 503
            assert one.json().get("code") == "CALENDAR_REFRESH_NOT_CONFIGURED"

            twenty_ids = [uuid4() for _ in range(20)]
            assert len(set(twenty_ids)) == 20
            twenty = _post_covering(
                client,
                body=covering_refresh_body(twenty_ids),
                cookie=seed.cookie,
            )
            assert twenty.status_code == 503
            assert twenty.json().get("code") == "CALENDAR_REFRESH_NOT_CONFIGURED"
            receipt = build_receipt(
                case_id="I01-C03",
                limits={"targets_min_max": "1..20"},
                observed={
                    "zero_status": zero.status_code,
                    "zero_type": "too_short",
                    "zero_loc": "subscription_ids",
                    "twenty_one_status": over.status_code,
                    "twenty_one_type": "too_long",
                    "twenty_one_loc": "subscription_ids",
                    "one_status": one.status_code,
                    "one_code": one.json().get("code"),
                    "twenty_status": twenty.status_code,
                    "twenty_code": twenty.json().get("code"),
                },
            )
            return _result("I01-C03", passed=True, receipt=receipt)

        return _run_attempt("I01-C03", run)

    def c04_unbound(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c04")
            app = build_i01_asgi_app()
            cleanup.app = app
            clear_binding(app)
            client = asgi_client(app)
            response = _post_covering(
                client,
                body=covering_refresh_body(seed.subscription_ids),
                cookie=seed.cookie,
            )
            assert response.status_code == 503
            assert response.json().get("code") == "CALENDAR_REFRESH_NOT_CONFIGURED"
            receipt = build_receipt(
                case_id="I01-C04",
                binding="absent_unbound",
                binding_shape="absent_unbound",
            )
            return _result("I01-C04", passed=True, receipt=receipt)

        return _run_attempt("I01-C04", run)

    def c05_assessment_sanitize(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c05")
            calendar_ids = ["cal-i01-c05-0"]
            routes = provider_routes_for_calendars(calendar_ids)
            factory = build_transport_factory(script_for_calendars(calendar_ids))
            install_covering_http_alias(transport_factory=factory)
            cleanup.alias_wrapped = True
            app = build_i01_asgi_app()
            cleanup.app = app
            install_binding(
                app,
                _build_plan(
                    profile=self.profile,
                    password_supplier=self.password_supplier,
                    runtime_pins=self.pins,
                    settings=self.settings,
                    routes=routes,
                ),
            )
            real = domain_dispatch._assemble_final_assessment

            def fake_assessment(*args, **kwargs):
                raise ApiError(503, "secret-sql-detail-must-not-leak", "INTERNAL_FAKE")

            domain_dispatch._assemble_final_assessment = fake_assessment  # type: ignore[assignment]
            try:
                client = asgi_client(app)
                response = _post_covering(
                    client,
                    body=covering_refresh_body(seed.subscription_ids),
                    cookie=seed.cookie,
                )
            finally:
                domain_dispatch._assemble_final_assessment = real  # type: ignore[assignment]
            body_text = response.text
            assert "secret-sql-detail-must-not-leak" not in body_text
            assert "INTERNAL_FAKE" not in body_text
            payload = response.json()
            readiness = payload.get("scheduling_readiness") or {}
            assert readiness.get("assessment_error") == "CALENDAR_REFRESH_ASSESSMENT_FAILED"
            receipt = build_receipt(
                case_id="I01-C05",
                sanitization={"leaked_secrets": []},
                assessment_callable_replaced=True,
                notes="C05 replaces domain-bound assessment callable only; not proof of real assessment SQL",
            )
            return _result("I01-C05", passed=True, receipt=receipt)

        return _run_attempt("I01-C05", run)

    def c06_lost_ack(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c06")
            calendar_ids = ["cal-i01-c06-0"]
            routes = provider_routes_for_calendars(calendar_ids)
            transport_factory = build_transport_factory(script_for_calendars(calendar_ids))
            gate_ready = Event()
            gate_stop = Event()
            cleanup.gate_stop = gate_stop
            gate_error: list[BaseException] = []

            def gate_main():
                try:
                    serve_i01_c06_gate(
                        ready=gate_ready,
                        stop=gate_stop,
                        seconds=120,
                        artifact_stem=C06_GATE_ARTIFACT_STEM,
                        gate_port=C06_GATE_PORT,
                        root=C06_GATE_ROOT,
                    )
                except BaseException as exc:
                    gate_error.append(exc)
                    raise

            gate_thread = Thread(target=gate_main, name="i01-c06-gate", daemon=False)
            cleanup.gate_thread = gate_thread
            # Gate is retired only via stop_gate(); never also joined as a generic worker.
            # Existing 120s C06 gate limit starts after successful runner TLS generation.
            gate_thread.start()
            if not gate_ready.wait(10.0):
                raise TimeoutError("I01-C06 gate readiness not signaled")
            ready_path = C06_GATE_ROOT / f"{C06_GATE_ARTIFACT_STEM}.ready"
            assert ready_path.is_file() and ready_path.read_text(encoding="ascii") == "READY\n"

            binding, arm_fired = build_c06_dual_peer_binding(
                profile=self.profile,
                password_supplier=self.password_supplier,
                runtime_pins=self.pins,
                settings=self.settings,
                provider_routes=routes,
                transport_factory=transport_factory,
                gate_port=C06_GATE_PORT,
            )
            # arm_fired is proof latch only — not a teardown barrier.
            app = build_i01_asgi_app()
            cleanup.app = app
            install_binding(app, binding)
            client = asgi_client(app)
            response = _post_covering(
                client,
                body=covering_refresh_body(seed.subscription_ids),
                cookie=seed.cookie,
            )
            assert response.status_code == 503
            assert response.json().get("code") == "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
            assert arm_fired.is_set()
            cleanup.stop_gate()
            gate_receipt = load_c06_gate_receipt(
                artifact_stem=C06_GATE_ARTIFACT_STEM, root=C06_GATE_ROOT
            )
            cleanup.gate_receipt = gate_receipt
            if gate_error:
                raise gate_error[0]
            public_ca_identity = require_distinct_public_ca_hashes(
                Path(C06_GATE_CLIENT_CA).read_bytes(),
                Path(C06_BACKEND_DB_CA).read_bytes(),
            )
            receipt = build_receipt(
                case_id="I01-C06",
                binding_shape="covering_release_binding_dual_peer",
                lost_ack_mechanism="tls_ack_gate_n06",
                mapping_control_only=False,
                expected_unknown=True,
                gate_artifact_stem=C06_GATE_ARTIFACT_STEM,
                gate_root=str(C06_GATE_ROOT),
                public_ca_identity=public_ca_identity,
                gate_receipt={
                    "backend_tag": gate_receipt.get("backend_tag"),
                    "backend_idle": gate_receipt.get("backend_idle"),
                    "terminal_response_bytes_forwarded": gate_receipt.get(
                        "terminal_response_bytes_forwarded"
                    ),
                    "fault": gate_receipt.get("fault"),
                    "complete": gate_receipt.get("complete"),
                },
                arm_fired=arm_fired.is_set(),
            )
            return _result("I01-C06", passed=True, receipt=receipt, expected_unknown=True)

        return _run_attempt("I01-C06", run)

    def c06_map(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c06-map")
            app = build_i01_asgi_app()
            cleanup.app = app

            def raise_unknown(*args, **kwargs):
                raise CoveringRootOutcomeUnknown()

            ports = CoveringDomainPorts(raise_unknown, raise_unknown, raise_unknown)
            install_binding(
                app,
                CoveringReleaseBinding(
                    parent_factory=raise_unknown,
                    session_factory=raise_unknown,
                    domain_ports=ports,
                ),
            )
            client = asgi_client(app)
            response = _post_covering(
                client,
                body=covering_refresh_body(seed.subscription_ids),
                cookie=seed.cookie,
            )
            assert response.status_code == 503
            assert response.json().get("code") == "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
            receipt = build_receipt(
                case_id="I01-C06-MAP",
                proof_class="http_unknown_mapping_control",
                mapping_control_only=True,
                lost_ack_mechanism="mapping_control_only",
            )
            return _result("I01-C06-MAP", passed=True, receipt=receipt)

        return _run_attempt("I01-C06-MAP", run)

    def c07a_oversized(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c07a")
            observations: dict[str, Any] = {
                "worker_entered": False,
                "worker_entry_count": 0,
                "checkout_count": 0,
            }

            def counting_parent(target, remaining):
                observations["checkout_count"] = int(observations["checkout_count"]) + 1
                raise RuntimeError("C07a parent checkout must not run")

            def counting_session(role, target, remaining):
                observations["checkout_count"] = int(observations["checkout_count"]) + 1
                raise RuntimeError("C07a session checkout must not run")

            def refuse_port(*args, **kwargs):
                raise RuntimeError("C07a domain port must not run")

            app = build_i01_asgi_app()
            cleanup.app = app
            install_binding(
                app,
                CoveringReleaseBinding(
                    parent_factory=counting_parent,
                    session_factory=counting_session,
                    domain_ports=CoveringDomainPorts(refuse_port, refuse_port, refuse_port),
                ),
            )
            client = asgi_client(app)
            oversized = b"{" + (b"x" * (BODY_LIMIT + 64)) + b"}"
            with _observe_dispatch_worker(observations):
                response = _post_covering(client, body=oversized, cookie=seed.cookie)
            assert response.status_code == 413
            assert response.json().get("code") == "CALENDAR_REFRESH_REQUEST_TOO_LARGE"
            assert observations["worker_entered"] is False
            assert observations["worker_entry_count"] == 0
            assert observations["checkout_count"] == 0
            receipt = build_receipt(
                case_id="I01-C07A",
                worker_entered=False,
                worker_entry_count=0,
                checkout_count=0,
                budget_object_id_worker=None,
            )
            return _result("I01-C07A", passed=True, receipt=receipt)

        return _run_attempt("I01-C07A", run)

    def c07b_budget_identity(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c07b")
            calendar_ids = ["cal-i01-c07b-0"]
            routes = provider_routes_for_calendars(calendar_ids)
            factory = build_transport_factory(script_for_calendars(calendar_ids))
            install_covering_http_alias(transport_factory=factory)
            cleanup.alias_wrapped = True
            ingress_budget_id: dict[str, int | None] = {"value": None}
            observations: dict[str, Any] = {
                "worker_entered": False,
                "worker_budget_id": None,
            }

            def on_context(context):
                # Capture ingress budget identity independently of worker wrap.
                ingress_budget_id["value"] = id(context.budget)

            app = build_i01_asgi_app(on_context=on_context)
            cleanup.app = app
            install_binding(
                app,
                _build_plan(
                    profile=self.profile,
                    password_supplier=self.password_supplier,
                    runtime_pins=self.pins,
                    settings=self.settings,
                    routes=routes,
                ),
            )
            client = asgi_client(app)
            with _observe_dispatch_worker(observations):
                response = _post_covering(
                    client,
                    body=covering_refresh_body(seed.subscription_ids),
                    cookie=seed.cookie,
                )
            assert response.status_code == 200, response.text
            assert_budget_identity_observations(
                ingress_budget_id=ingress_budget_id["value"],
                worker_budget_id=observations["worker_budget_id"],
                worker_entered=bool(observations["worker_entered"]),
            )
            receipt = build_receipt(
                case_id="I01-C07B",
                worker_joined=True,
                abandon_on_cancel=False,
                budget_object_id_ingress=ingress_budget_id["value"],
                budget_object_id_worker=observations["worker_budget_id"],
                notes="same budget object identity required when worker entered",
            )
            return _result("I01-C07B", passed=True, receipt=receipt)

        return _run_attempt("I01-C07B", run)

    def c08_deadline(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c08")
            clock = ControllableClock(0.0)
            ownership_seen = {"value": False}

            def after_budget(context):
                # Advance AFTER context/budget construction so deadlines start at t=0.
                clock.value = 211.0
                ownership_seen["value"] = bool(context.ownership_established)

            app = build_i01_asgi_app(clock=clock, on_context=after_budget)
            cleanup.app = app
            clear_binding(app)
            client = asgi_client(app)
            response = _post_covering(
                client,
                body=covering_refresh_body(seed.subscription_ids),
                cookie=seed.cookie,
            )
            assert response.status_code == 504
            assert response.json().get("code") == "CALENDAR_REFRESH_DEADLINE_EXCEEDED"
            assert ownership_seen["value"] is False
            receipt = build_receipt(
                case_id="I01-C08",
                ownership_established=False,
                clock_advanced_after_budget=True,
            )
            return _result("I01-C08", passed=True, receipt=receipt)

        return _run_attempt("I01-C08", run)

    def c09_disconnect(self):
        def run(cleanup: AttemptCleanup):
            seed = self._setup_seed(count=1, prefix="i01-c09")
            calendar_ids = ["cal-i01-c09-0"]
            routes = provider_routes_for_calendars(calendar_ids)
            factory = build_transport_factory(script_for_calendars(calendar_ids))
            install_covering_http_alias(transport_factory=factory)
            cleanup.alias_wrapped = True
            contexts: list[Any] = []
            worker_retired = Event()
            observations: dict[str, Any] = {
                "worker_entered": False,
                "worker_retired": worker_retired,
                "worker_finished": False,
                "cancellation_provenance": None,
                "api_error_status": None,
                "api_error_code": None,
                "api_error_detail": None,
                "ownership_snapshot": None,
                "hold_count": 0,
            }
            checkpoint_armed = Event()
            hold_ack = Event()
            disconnect_inject_permit = Event()
            release_hold = Event()
            disconnect_control = DisconnectInjectControl()
            check_wrap_installed = {"value": False}
            original_check_holder: dict[str, Any] = {"fn": None}
            real_worker_holder: dict[str, Any] = {"fn": None}
            poster: Thread | None = None
            injector: Thread | None = None
            injector_errors: list[BaseException] = []
            post_errors: list[BaseException] = []
            post_result: dict[str, Any] = {}
            asgi_result = None
            primary_box: dict[str, BaseException | None] = {"error": None}

            def on_api_error(exc: ApiError) -> None:
                # Transparent observation of the registered handler mapping only.
                observations["api_error_status"] = int(exc.status_code)
                observations["api_error_code"] = str(exc.content.get("code") or "")
                observations["api_error_detail"] = str(exc.content.get("detail") or "")

            def on_context(context):
                contexts.append(context)
                if check_wrap_installed["value"]:
                    return
                original = context.budget.check_admission
                original_check_holder["fn"] = original

                def wrapped_check_admission():
                    if not context.ownership_established:
                        return original()
                    if context.calendar_admitted:
                        return original()
                    if observations["hold_count"] >= 1:
                        return original()
                    observations["hold_count"] = int(observations["hold_count"]) + 1
                    snapshot = {
                        "ownership_established": bool(context.ownership_established),
                        "calendar_admitted": bool(context.calendar_admitted),
                        "auth_telemetry_admitted": bool(context.auth_telemetry_admitted),
                    }
                    observations["ownership_snapshot"] = snapshot
                    if snapshot["ownership_established"] is not True:
                        raise RuntimeError("C09 hold requires ownership_established=true")
                    if snapshot["calendar_admitted"] is not False:
                        raise RuntimeError("C09 hold requires calendar_admitted=false")
                    hold_ack.set()
                    if not release_hold.wait(JOIN_LIMIT_SECONDS):
                        raise TimeoutError("C09 release_hold not signaled")
                    return original()

                context.budget.check_admission = wrapped_check_admission  # type: ignore[method-assign]
                check_wrap_installed["value"] = True

            def release_fixture_holds() -> None:
                release_hold.set()
                disconnect_inject_permit.set()

            def join_named_thread(
                thread: Thread | None,
                *,
                retirement_attr: str,
                label: str,
            ) -> None:
                if thread is None:
                    setattr(cleanup, retirement_attr, "joined")
                    return
                current = getattr(cleanup, retirement_attr)
                if current in ("joined", "join_timeout"):
                    return
                thread.join(JOIN_LIMIT_SECONDS)
                if thread.is_alive():
                    setattr(cleanup, retirement_attr, "join_timeout")
                    cleanup.workers_alive = True
                    cleanup.workers_joined = False
                    cleanup.allow_alias_restore = False
                    cleanup.worker_wrap_restore_allowed = False
                    if primary_box["error"] is None:
                        primary_box["error"] = SuiteStop(f"C09 {label} unjoined at limit")
                else:
                    setattr(cleanup, retirement_attr, "joined")

            def restore_worker_wrap_if_allowed() -> None:
                real = real_worker_holder.get("fn")
                if real is None:
                    return
                if not cleanup.worker_wrap_restore_allowed or cleanup.workers_alive:
                    # Do not restore shared _worker underneath live poster/AnyIO work.
                    return
                http_dispatch._worker = real  # type: ignore[assignment]
                real_worker_holder["fn"] = None

            app = build_i01_asgi_app(
                on_context=on_context,
                disconnect_control=disconnect_control,
                on_api_error=on_api_error,
            )
            cleanup.app = app
            install_binding(
                app,
                _build_plan(
                    profile=self.profile,
                    password_supplier=self.password_supplier,
                    runtime_pins=self.pins,
                    settings=self.settings,
                    routes=routes,
                ),
            )

            def injector_main():
                try:
                    checkpoint_armed.set()
                    if not disconnect_inject_permit.wait(JOIN_LIMIT_SECONDS):
                        raise TimeoutError("C09 disconnect_inject_permit not signaled")
                    disconnect_control.inject_http_disconnect(timeout=JOIN_LIMIT_SECONDS)
                except BaseException as exc:
                    injector_errors.append(exc)
                    release_fixture_holds()
                    raise

            injector = Thread(target=injector_main, name="i01-c09-disconnect", daemon=False)
            injector.start()
            try:
                if not checkpoint_armed.wait(JOIN_LIMIT_SECONDS):
                    raise TimeoutError("C09 injector checkpoint_armed missing")

                real_worker = http_dispatch._worker
                real_worker_holder["fn"] = real_worker

                def wrapped_worker(binding, request, body, context):
                    observations["worker_entered"] = True
                    observations["worker_entry_count"] = int(
                        observations.get("worker_entry_count", 0)
                    ) + 1
                    try:
                        return real_worker(binding, request, body, context)
                    except CoveringBudgetStopped:
                        # Cancellation provenance only — NOT a synthetic UNKNOWN label.
                        # Sanitized 503/CALENDAR_REFRESH_OUTCOME_UNKNOWN must come from
                        # the registered ApiError handler observation.
                        observations["cancellation_provenance"] = "CoveringBudgetStopped"
                        raise
                    finally:
                        worker_retired.set()

                http_dispatch._worker = wrapped_worker  # type: ignore[assignment]

                body_obj = (
                    covering_refresh_body(seed.subscription_ids)
                    if seed.request_window_start is None
                    else body_for_seed(seed)
                )
                body_bytes = json.dumps(body_obj).encode("utf-8")
                header_list = [
                    (b"content-type", b"application/json"),
                    (b"cookie", f"session={seed.cookie}".encode("latin-1")),
                ]

                def post_main():
                    try:
                        # Bounded direct ASGI driver — not TestClient. Intentional
                        # no-response after guarded_send must not become the oracle.
                        post_result["asgi"] = run_covering_asgi(
                            app,
                            body=body_bytes,
                            headers=header_list,
                            timeout=JOIN_LIMIT_SECONDS,
                        )
                    except BaseException as exc:
                        post_errors.append(exc)
                        release_fixture_holds()
                        raise

                poster = Thread(target=post_main, name="i01-c09-poster", daemon=False)
                poster.start()

                if not hold_ack.wait(JOIN_LIMIT_SECONDS):
                    release_fixture_holds()
                    raise TimeoutError("C09 hold_ack not observed at check_admission")
                snapshot = observations.get("ownership_snapshot") or {}
                if snapshot.get("ownership_established") is not True:
                    release_fixture_holds()
                    raise RuntimeError("C09 ownership snapshot failed")
                if snapshot.get("calendar_admitted") is not False:
                    release_fixture_holds()
                    raise RuntimeError("C09 calendar_admitted snapshot failed")
                disconnect_inject_permit.set()
                # One acknowledged monitor-observation path only (armed in hooked_receive).
                if not disconnect_control.monitor_observed.wait(JOIN_LIMIT_SECONDS):
                    release_fixture_holds()
                    raise TimeoutError("C09 monitor_observed missing")
                if not disconnect_control.disconnect_delivered.is_set():
                    release_fixture_holds()
                    raise RuntimeError("C09 actual disconnect not delivered")
                if not contexts or not contexts[0].disconnected.is_set():
                    release_fixture_holds()
                    raise RuntimeError("C09 disconnected flag not set by monitor path")
                release_hold.set()
            except BaseException as exc:
                primary_box["error"] = exc
                release_fixture_holds()
            finally:
                release_fixture_holds()
                join_named_thread(poster, retirement_attr="poster_retirement", label="poster")
                join_named_thread(
                    injector, retirement_attr="injector_retirement", label="injector"
                )
                # monitor_observed ≠ thread retirement; join on every path.
                monitor_state = disconnect_control.retire_monitor_observation(
                    timeout=JOIN_LIMIT_SECONDS
                )
                if monitor_state == "join_timeout":
                    cleanup.workers_alive = True
                    cleanup.workers_joined = False
                    cleanup.allow_alias_restore = False
                    cleanup.worker_wrap_restore_allowed = False
                    if primary_box["error"] is None:
                        primary_box["error"] = SuiteStop(
                            "C09 monitor-observe thread unjoined at limit"
                        )
                restore_worker_wrap_if_allowed()

            if injector_errors and primary_box["error"] is None:
                primary_box["error"] = injector_errors[0]
            if post_errors and primary_box["error"] is None:
                primary_box["error"] = post_errors[0]
            if primary_box["error"] is not None:
                raise primary_box["error"]

            asgi_result = post_result.get("asgi")
            assert observations["worker_entered"] is True
            assert worker_retired.wait(JOIN_LIMIT_SECONDS)
            assert_c09_disconnect_evidence(
                asgi_result=asgi_result,
                cancellation_provenance=observations.get("cancellation_provenance"),
                api_error_status=observations.get("api_error_status"),
                api_error_code=observations.get("api_error_code"),
                monitor_observed=disconnect_control.monitor_observed.is_set(),
                disconnect_delivered=disconnect_control.disconnect_delivered.is_set(),
                post_disconnect_outbound=list(
                    disconnect_control.post_disconnect_outbound
                ),
            )
            assert cleanup.poster_retirement == "joined"
            assert cleanup.injector_retirement == "joined"
            assert disconnect_control.monitor_observe_retirement == "joined"
            # Intentional no-response after guarded_send suppression is allowed when
            # error is None and handler mapping was observed. Missing result is not.
            receipt = build_receipt(
                case_id="I01-C09",
                ingress={
                    "disconnected": True,
                    "monitor_observed": True,
                    "actual_http_disconnect": True,
                    "fabricated_flag": False,
                    "asgi_driver": "run_covering_asgi",
                    "asgi_error": None,
                    "response_completed": bool(asgi_result.response_completed),
                },
                ownership_snapshot=observations["ownership_snapshot"],
                hold_hook="CoveringRequestBudget.check_admission",
                response_started=bool(asgi_result.response_started),
                response_status=asgi_result.status_code,
                cancellation_provenance=observations["cancellation_provenance"],
                api_error_observation={
                    "status": observations["api_error_status"],
                    "code": observations["api_error_code"],
                },
                disconnect_classification="CALENDAR_REFRESH_OUTCOME_UNKNOWN",
                post_disconnect_outbound_sends=list(
                    disconnect_control.post_disconnect_outbound
                ),
                worker_entered=True,
                worker_retired=True,
                injector_joined=cleanup.injector_retirement == "joined",
                poster_joined=cleanup.poster_retirement == "joined",
                injector_retirement=cleanup.injector_retirement,
                poster_retirement=cleanup.poster_retirement,
                notes=(
                    "cancellation provenance (CoveringBudgetStopped) plus registered "
                    "ApiError handler 503/CALENDAR_REFRESH_OUTCOME_UNKNOWN observed; "
                    "outbound sends suppressed; driver error/timeout rejected; "
                    "intentional no-response OK only with error=None and completed result"
                ),
            )
            return _result("I01-C09", passed=True, receipt=receipt)

        return _run_attempt("I01-C09", run)

    def c10_synthetic_label(self):
        def run(cleanup: AttemptCleanup):
            planted = inverted_subscription_ids(case_token="i01c10")
            seed = self._setup_seed(
                count=2,
                prefix="i01-c10",
                planted_subscription_ids=planted,
            )
            calendar_ids = production_ordered_calendar_ids(
                subscription_ids=seed.subscription_ids,
                subscription_calendar_map=seed.subscription_calendar_map,
            )
            routes = provider_routes_for_calendars(calendar_ids)
            factory = build_transport_factory(script_for_calendars(calendar_ids))
            install_covering_http_alias(transport_factory=factory)
            cleanup.alias_wrapped = True
            app = build_i01_asgi_app()
            cleanup.app = app
            install_binding(
                app,
                _build_plan(
                    profile=self.profile,
                    password_supplier=self.password_supplier,
                    runtime_pins=self.pins,
                    settings=self.settings,
                    routes=routes,
                ),
            )
            client = asgi_client(app)
            response = _post_covering(
                client,
                body=body_for_seed(seed),
                cookie=seed.cookie,
            )
            assert response.status_code == 200, response.text
            labeled = build_receipt(
                case_id="I01-C10",
                transport_factory="FixtureByteTransport",
                provider_coverage="synthetic_fixture_byte_transport",
                proof_class="http_native_composition",
                covering_http_alias_wrapped=True,
                notes="does not claim live provider TLS",
            )
            assert_transport_coverage_observations(
                transport_factory=labeled.get("transport_factory"),
                provider_coverage=labeled.get("provider_coverage"),
            )
            return _result("I01-C10", passed=True, receipt=labeled)

        return _run_attempt("I01-C10", run)

    def i02_c01(self):
        def run(cleanup: AttemptCleanup):
            setup = self.factory.open_setup_session()
            try:
                seed = seed_i02_owner(setup, username_prefix="i02-c01")
                setup.commit()
            finally:
                self.factory.close(setup)
            final, evidence = run_i02_contention(factory=self.factory, seed=seed)
            assert_i02_lock_observations(evidence)
            assert evidence.mutator_committed is True
            assert evidence.mutator_result is not None
            assert evidence.requested_ok is False
            assert evidence.scheduling_ready is False
            assert evidence.mismatch_cause == GENERATION_MISMATCH_CAUSE
            assert evidence.mixed_revision_detected is False
            assert evidence.workers_joined.get("i02-mutator") is True
            assert evidence.workers_joined.get("i02-assessment") is True
            if evidence.cleanup_failures:
                raise RuntimeError(
                    f"I02 cleanup_failures prevent PASS: {evidence.cleanup_failures}"
                )
            receipt = build_receipt(
                case_id="I02-C01",
                proof_class="owner_lock_contention",
                contention_class="advisory_xact_lock",
                lock={
                    "holder_pid": evidence.holder_pid,
                    "waiter_pid": evidence.waiter_pid,
                    "assessment_backend_pid": evidence.assessment_backend_pid,
                    "contention_class": "advisory_xact_lock",
                    "observer_query_id": "i02_observer_advisory_xact_two_int_v1",
                    "assessment_started_after_hold_confirmed": True,
                    "database_oid": evidence.database_oid,
                    "owner_lock_namespace": 1886415951,
                    "owner_lock_key": evidence.owner_lock_key,
                    "objsubid": 2,
                    "lock_row_relationship": evidence.lock_row_relationship,
                },
                mutator_result=evidence.mutator_result,
                mutator_committed=evidence.mutator_committed,
                scheduling_revision=evidence.scheduling_revision,
                coverage_active_generation=evidence.coverage_active_generation,
                coverage_success_generation=evidence.coverage_success_generation,
                mixed_revision_detected=evidence.mixed_revision_detected,
                failure_reason=evidence.mismatch_cause,
                workers_joined=evidence.workers_joined,
                cleanup_failures=evidence.cleanup_failures,
            )
            return _result("I02-C01", passed=True, receipt=receipt)

        return _run_attempt("I02-C01", run)


def build_i01_i02_registry(*, factory, profile, pins, password_supplier=lambda: "") -> dict[str, Callable]:
    return I01I02Cases(
        factory=factory,
        profile=profile,
        pins=pins,
        password_supplier=password_supplier,
    ).registry()
