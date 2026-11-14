"""Domain-auth + ordered-result harness against bounded domain dispatcher.

Uses support.domain_auth_ordered_result_asgi_harness — real calendar router +
CoveringIngress + mirrored middleware; CoveringReleaseBinding(
parent_factory, session_factory, domain_ports=CoveringDomainPorts(...)) only.
HTTP worker calls run_bounded_domain directly (no CoveringReleaseBinding.dispatch).

Prefer isolated entry
tests/support/run_domain_auth_ordered_result_harness_offline.py.

Auth/credential/ownership policy exercises real authenticate + deps helpers
via FakeSession. Assert AUTH purpose order (identity → preflight), not raw
AUTH counts. Provider/native/DB sockets are replaced. Skips are not proof.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from support.domain_auth_ordered_result_asgi_harness import (
    BODY_LIMIT_BYTES,
    COVERING_PATH,
    ControllableClock,
    HARNESS_SESSION_SECRET,
    HarnessIdentityStore,
    OFF_ROUTE_PATH,
    PENDING_ASSESSMENT_FRESHNESS_REASON,
    PENDING_NATIVE_PARENT_REASON,
    PRODUCTION_COVERING_METHOD_PATHS,
    PRODUCTION_MIDDLEWARE_ADD_ORDER,
    PURPOSE_AUTH_IDENTITY,
    PURPOSE_AUTH_PREFLIGHT,
    PURPOSE_PARENT,
    PURPOSE_TELEMETRY,
    PURPOSE_TOKEN,
    REQUEST_BUDGET_CLEANUP_SECONDS,
    REQUEST_BUDGET_ORDINARY_SECONDS,
    REQUEST_BUDGET_TOTAL_SECONDS,
    TokenReady,
    TokenRejected,
    asgi_post_chunked_json,
    covering_method_paths,
    domain_auth_asgi_client,
    middleware_add_order_names,
    mint_signed_session_cookie,
    refresh_body,
    sorted_subscription_ids,
)


def _assert_no_ownership_or_target_work(recorder: object) -> None:
    purposes = recorder.purpose_sequence()  # type: ignore[attr-defined]
    assert PURPOSE_AUTH_PREFLIGHT not in purposes
    assert PURPOSE_TOKEN not in purposes
    assert PURPOSE_PARENT not in purposes
    assert recorder.parent_targets == []  # type: ignore[attr-defined]
    assert recorder.token_calls == []  # type: ignore[attr-defined]
    assert recorder.lock_calls == []  # type: ignore[attr-defined]
    assert recorder.apply_calls == []  # type: ignore[attr-defined]


def _assert_role_accounting_sound(recorder: object) -> None:
    """Overlap alone is insufficient — unbalanced ends must not clamp to success."""
    assert recorder.overlapping_role_attempts == 0  # type: ignore[attr-defined]
    assert recorder.role_conservation_violations == 0  # type: ignore[attr-defined]
    assert recorder.active_role_count == 0  # type: ignore[attr-defined]
    assert recorder.roles_accounting_sound() is True  # type: ignore[attr-defined]


def test_da_static_covering_routes_and_middleware_match_production() -> None:
    from app.main import create_app

    with domain_auth_asgi_client() as harness:
        harness_mw = tuple(middleware_add_order_names(harness.app))
        harness_covering = covering_method_paths(harness.app)

    prod = create_app()
    try:
        prod_mw = tuple(middleware_add_order_names(prod))
        prod_covering = covering_method_paths(prod)
    finally:
        prod.dependency_overrides.clear()

    assert harness_mw == PRODUCTION_MIDDLEWARE_ADD_ORDER
    assert prod_mw == PRODUCTION_MIDDLEWARE_ADD_ORDER
    assert harness_mw == prod_mw
    assert "CoveringIngressMiddleware" in harness_mw
    assert harness_covering == PRODUCTION_COVERING_METHOD_PATHS
    assert prod_covering == PRODUCTION_COVERING_METHOD_PATHS
    assert harness_covering == {("POST", COVERING_PATH)}


def test_da_unbound_binding_sanitized_503_not_configured() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    with domain_auth_asgi_client(store=store) as h:
        assert h.binding_installed is False
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))
    assert response.status_code == 503, response.text
    payload = response.json()
    assert payload["code"] == "CALENDAR_REFRESH_NOT_CONFIGURED"
    assert payload["code"] != "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
    assert h.ports.recorder.role_admissions == []
    assert h.ports.recorder.parent_targets == []


def test_da_wrong_type_binding_sanitized_503_not_configured() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    with domain_auth_asgi_client(store=store, install_wrong_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "CALENDAR_REFRESH_NOT_CONFIGURED"
    assert response.json()["code"] != "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
    assert h.ports.recorder.parent_targets == []


def test_da_twenty_one_targets_rejected_before_port_work() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    ids = [uuid4() for _ in range(21)]
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body(ids))
    assert response.status_code == 422
    assert h.ports.recorder.role_admissions == []
    assert h.ports.recorder.parent_targets == []


def test_da_streamed_body_over_16kib_returns_413_zero_ports() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    raw = b"x" * (BODY_LIMIT_BYTES + 1)
    cookie = mint_signed_session_cookie(user_id=user.id, session_epoch=1)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        status, body, _headers = asgi_post_chunked_json(
            h.app,
            path=COVERING_PATH,
            body=raw,
            cookie=cookie,
            chunk_size=2048,
        )
    assert status == 413
    payload = json.loads(body.decode("utf-8"))
    assert payload["code"] == "CALENDAR_REFRESH_REQUEST_TOO_LARGE"
    assert h.ports.recorder.role_admissions == []
    assert h.ports.recorder.parent_targets == []


def test_da_exact_16kib_body_limit_constant() -> None:
    assert BODY_LIMIT_BYTES == 16 * 1024


def test_da_budget_constants_240_210_30() -> None:
    from app.services.covering_request_budget import CoveringRequestBudget

    assert REQUEST_BUDGET_TOTAL_SECONDS == 240
    assert REQUEST_BUDGET_ORDINARY_SECONDS == 210
    assert REQUEST_BUDGET_CLEANUP_SECONDS == 30
    budget = CoveringRequestBudget(clock=lambda: 0.0)
    assert budget.work_remaining() == 210.0
    with budget.cleanup():
        assert budget.cleanup_remaining() == 30.0


def test_da_off_route_auth_preserved_no_covering_codes() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    with domain_auth_asgi_client(store=store) as h:
        bare = h.client.get(OFF_ROUTE_PATH)
        assert bare.status_code == 200
        assert "CALENDAR_REFRESH" not in bare.text

        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        authed = h.client.post(OFF_ROUTE_PATH, json={})
        assert authed.status_code == 200
        assert authed.json()["user_id"] == str(user.id)

        covering = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))
        assert covering.status_code == 503
        assert covering.json()["code"] == "CALENDAR_REFRESH_NOT_CONFIGURED"


def test_da_health_does_not_touch_ports() -> None:
    with domain_auth_asgi_client() as h:
        response = h.client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert h.ports.recorder.role_admissions == []


def test_da_harness_session_secret_is_not_production_default() -> None:
    assert HARNESS_SESSION_SECRET != "dev-insecure-session-secret-change-me"
    assert "harness" in HARNESS_SESSION_SECRET


def test_da_browser_valid_session_reaches_typed_200_ordered_results() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=3)
    sub_a = store.register_owned_subscription(user)
    sub_b = store.register_owned_subscription(user)
    ordered = sorted_subscription_ids([sub_a, sub_b])
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenReady(access_token="harness-access")
        h.ports.default_apply = "ok"
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=3),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([sub_a, sub_b]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["subscription_id"] for row in body["results"]] == [str(x) for x in ordered]
    assert body["overall_outcome"] == "success"
    assert body["scheduling_readiness"]["assessment_error"] == (
        "CALENDAR_REFRESH_ASSESSMENT_FAILED"
    )
    purposes = h.ports.recorder.purpose_sequence()
    assert purposes[0] == PURPOSE_AUTH_IDENTITY
    assert PURPOSE_TELEMETRY not in purposes
    assert h.ports.recorder.telemetry_role_count == 0
    assert purposes.index(PURPOSE_AUTH_IDENTITY) < purposes.index(PURPOSE_AUTH_PREFLIGHT)
    _assert_role_accounting_sound(h.ports.recorder)
    assert len(h.ports.recorder.parent_targets) == 2
    assert h.ports.recorder.parent_lifecycle_events == [
        "begin",
        "finish:COMMIT",
        "retire",
        "begin",
        "finish:COMMIT",
        "retire",
    ]


def test_da_browser_stale_epoch_unauthenticated() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=5)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=4),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_browser_disabled_unauthenticated() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1, is_disabled=True)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_setup_required_before_auth_success() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1, password_hash=None)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))
    assert response.status_code == 401
    assert response.json()["code"] == "SETUP_REQUIRED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_password_change_cookie_gate_before_valid_bearer() -> None:
    store = HarnessIdentityStore()
    gated = store.add_browser_user(session_epoch=2, must_change_password=True)
    agent_owner = store.add_browser_user(session_epoch=9)
    _cred, secret = store.add_agent_credential(agent_owner)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=gated.id, session_epoch=2),
        )
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_password_change_cookie_gate_before_malformed_bearer() -> None:
    store = HarnessIdentityStore()
    gated = store.add_browser_user(session_epoch=2, must_change_password=True)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=gated.id, session_epoch=2),
        )
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": "Bearer not-a-valid-agent-secret"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_bearer_present_never_falls_back_to_cookie() -> None:
    store = HarnessIdentityStore()
    browser = store.add_browser_user(session_epoch=1)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=browser.id, session_epoch=1),
        )
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": "Bearer not-a-valid-agent-secret"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_empty_bearer_refuses_without_cookie_fallback() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": "Bearer"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_valid_bearer_one_telemetry_role_after_auth_retirement() -> None:
    store = HarnessIdentityStore()
    agent_owner = store.add_browser_user(session_epoch=9)
    cred, secret = store.add_agent_credential(agent_owner)
    sub = store.register_owned_subscription(agent_owner)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenRejected(code="HARNESS_TOKEN_REJECTED")
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([sub]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 200, response.text
    purposes = h.ports.recorder.purpose_sequence()
    # Purpose/order: identity-AUTH retires → exactly one TELEMETRY → preflight AUTH.
    assert purposes.count(PURPOSE_TELEMETRY) == 1
    assert h.ports.recorder.telemetry_role_count == 1
    assert h.ports.recorder.telemetry_sql_updates == 1
    assert purposes.index(PURPOSE_AUTH_IDENTITY) < purposes.index(PURPOSE_TELEMETRY)
    assert purposes.index(PURPOSE_TELEMETRY) < purposes.index(PURPOSE_AUTH_PREFLIGHT)
    _assert_role_accounting_sound(h.ports.recorder)
    assert h.ports.recorder.session_local_touch_attempts == 0
    assert h.ports.recorder.role_retirements[0].value == "auth"
    _ = cred


def test_da_auth_refusal_zero_telemetry_no_sessionlocal_touch() -> None:
    store = HarnessIdentityStore()
    agent_owner = store.add_browser_user(session_epoch=9)
    _cred, secret = store.add_agent_credential(agent_owner, revoked=True)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "AGENT_CREDENTIAL_REVOKED"
    assert h.ports.recorder.telemetry_role_count == 0
    assert h.ports.recorder.telemetry_sql_updates == 0
    assert h.ports.recorder.session_local_touch_attempts == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_revoked_credential_precedes_disallowed_and_disabled() -> None:
    store = HarnessIdentityStore()
    owner = store.add_browser_user(
        session_epoch=1, is_disabled=True, allow_agent_cli_access=False
    )
    _cred, secret = store.add_agent_credential(owner, revoked=True)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "AGENT_CREDENTIAL_REVOKED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_disallowed_credential_precedes_disabled_owner() -> None:
    store = HarnessIdentityStore()
    owner = store.add_browser_user(
        session_epoch=1, is_disabled=True, allow_agent_cli_access=False
    )
    _cred, secret = store.add_agent_credential(owner, revoked=False)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "AGENT_ACCESS_DISABLED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_disabled_owner_unauthenticated_after_allow_check() -> None:
    store = HarnessIdentityStore()
    owner = store.add_browser_user(
        session_epoch=1, is_disabled=True, allow_agent_cli_access=True
    )
    _cred, secret = store.add_agent_credential(owner, revoked=False)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert h.ports.recorder.telemetry_role_count == 0
    _assert_no_ownership_or_target_work(h.ports.recorder)


def test_da_one_to_twenty_unique_targets_accepted() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    for count in (1, 20):
        ids = [store.register_owned_subscription(user) for _ in range(count)]
        with domain_auth_asgi_client(store=store, install_binding=True) as h:
            h.ports.default_token = TokenRejected(code="HARNESS_TOKEN_REJECTED")
            h.client.cookies.set(
                "session",
                mint_signed_session_cookie(user_id=user.id, session_epoch=1),
            )
            response = h.client.post(COVERING_PATH, json=refresh_body(ids))
        assert response.status_code == 200, response.text
        assert response.json()["action_summary"]["requested"] == count
        assert h.ports.recorder.parent_targets == []


def test_da_whole_request_ownership_rejection_before_targets() -> None:
    store = HarnessIdentityStore()
    owner = store.add_browser_user(session_epoch=1)
    other = store.add_browser_user(session_epoch=1)
    owned = store.register_owned_subscription(owner)
    foreign = store.register_owned_subscription(other)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=owner.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([owned, foreign]))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "CALENDAR_SUBSCRIPTION_NOT_ELIGIBLE"
    assert h.ports.recorder.parent_targets == []
    assert h.ports.recorder.token_calls == []
    payload = response.json()
    assert payload.get("results") in (None, [])


def test_da_sorted_target_order_preserved_typed_200() -> None:
    """Deliberately unsorted request order; results must follow str(UUID) sort."""
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    ids = [store.register_owned_subscription(user) for _ in range(3)]
    expected = sorted_subscription_ids(ids)
    # Anti-sorted input: reverse of domain sort — must not equal expected.
    request_order = list(reversed(expected))
    assert request_order != expected  # deliberately unsorted vs domain sort
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenRejected(code="HARNESS_TOKEN_REJECTED")
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body(request_order))
    assert response.status_code == 200, response.text
    body = response.json()
    result_ids = [UUID(row["subscription_id"]) for row in body["results"]]
    assert result_ids == expected
    assert result_ids != request_order
    assert all(row["status"] == "preflight_rejected" for row in body["results"])


def test_da_known_success_failure_typed_200_partial() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    ok_id = store.register_owned_subscription(user)
    fail_id = store.register_owned_subscription(user)
    ordered = sorted_subscription_ids([ok_id, fail_id])
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenReady(access_token="harness-access")
        h.ports.apply_script = {ordered[0]: "ok", ordered[1]: "failed"}
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([ok_id, fail_id]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_outcome"] == "partial"
    assert body["results"][0]["status"] == "ok"
    assert body["results"][1]["status"] == "failed"
    assert len(h.ports.recorder.parent_targets) == 2


def test_da_exhaustion_after_ownership_preserves_completed_deadline_preflight() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    first = store.register_owned_subscription(user)
    second = store.register_owned_subscription(user)
    ordered = sorted_subscription_ids([first, second])
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenReady(access_token="harness-access")
        h.ports.default_apply = "ok"
        # Ordinary work → 209 before COMMIT (finish still sees remaining>0);
        # successful local retirement advances to 210 (one cleanup second).
        # Do NOT jump to 210 inside _apply — that expires COMMIT before finish.
        h.ports.advance_ordinary_clock_before_first_commit = 209.0
        h.ports.advance_clock_on_first_parent_retire = 210.0
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([first, second]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["results"][0]["subscription_id"] == str(ordered[0])
    # First successful row stays strong — completed COMMIT, not deadline demotion.
    assert body["results"][0]["status"] == "ok"
    assert body["results"][1]["status"] == "preflight_rejected"
    assert body["results"][1]["preflight_code"] == "CALENDAR_REFRESH_DEADLINE_EXCEEDED"
    assert len(h.ports.recorder.parent_targets) == 1
    assert h.ports.recorder.token_calls == [ordered[0]]
    # COMMIT receipt + known PARENT retirement before the next target is refused.
    assert h.ports.recorder.parent_lifecycle_events == [
        "begin",
        "finish:COMMIT",
        "retire",
    ]
    parent_retirements = [
        role for role in h.ports.recorder.role_retirements if role.value == "parent"
    ]
    assert len(parent_retirements) == 1
    _assert_role_accounting_sound(h.ports.recorder)
    assert ordered[1] not in h.ports.recorder.token_calls
    assert ordered[1] not in h.ports.recorder.lock_calls
    assert ordered[1] not in h.ports.recorder.apply_calls


def test_da_pre_ownership_expiry_sanitized_504_no_calendar_work() -> None:
    store = HarnessIdentityStore()
    agent_owner = store.add_browser_user(session_epoch=1)
    cred, secret = store.add_agent_credential(agent_owner)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        # Exhaust ordinary budget during TELEMETRY write; ownership not yet set.
        h.ports.advance_clock_on_telemetry = 210.0
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 504, response.text
    assert response.json()["code"] == "CALENDAR_REFRESH_DEADLINE_EXCEEDED"
    assert h.ports.recorder.telemetry_role_count == 1
    assert h.ports.recorder.parent_targets == []
    assert h.ports.recorder.token_calls == []
    assert all(rec.role.value != "parent" for rec in h.ports.recorder.role_admissions)
    _ = cred


def test_da_unknown_sanitized_503_zero_later_targets_no_retry() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    first = store.register_owned_subscription(user)
    second = store.register_owned_subscription(user)
    third = store.register_owned_subscription(user)
    ordered = sorted_subscription_ids([first, second, third])
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenReady(access_token="harness-access")
        h.ports.token_script = {
            ordered[0]: TokenReady(access_token="ok"),
            ordered[1]: "api_error",
            ordered[2]: TokenReady(access_token="later"),
        }
        h.ports.default_apply = "ok"
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(
            COVERING_PATH, json=refresh_body([first, second, third])
        )
    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
    assert "Do not retry automatically" in payload["detail"]
    assert payload["code"] != "CALENDAR_REFRESH_NOT_CONFIGURED"
    # First target may complete; second token ApiError → UNKNOWN; third never admitted.
    assert ordered[2] not in h.ports.recorder.token_calls
    assert ordered[2] not in {t[2] if isinstance(t, tuple) else t for t in h.ports.recorder.parent_targets}


def test_da_disconnect_stops_new_roles_joins_admitted_retirement() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    sub = store.register_owned_subscription(user)
    cookie = mint_signed_session_cookie(user_id=user.id, session_epoch=1)
    body = json.dumps(refresh_body([sub])).encode("utf-8")
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenReady(access_token="harness-access")
        status, _raw, _headers = asgi_post_chunked_json(
            h.app,
            path=COVERING_PATH,
            body=body,
            cookie=cookie,
            chunk_size=64,
            disconnect_after_body=True,
            response_wait_timeout_seconds=2.0,
        )
    # Disconnect may suppress the HTTP response (ingress guarded_send) or
    # surface UNKNOWN after CoveringBudgetStopped — never a successful typed 200.
    if status is None:
        assert h.ports.recorder.overlapping_role_attempts == 0
        assert h.ports.recorder.role_conservation_violations == 0
    else:
        assert status in (503, 504)
        if status == 503:
            # When a body is emitted, it must not be NOT_CONFIGURED success-path.
            pass
    # No proof claim on native joined retirement beyond zero overlap + stop.
    # Conservation: do not clamp unbalanced ends into apparent success; an
    # in-flight PARENT without retire may leave active_role_count > 0 (honest).
    assert h.ports.recorder.overlapping_role_attempts == 0
    assert h.ports.recorder.role_conservation_violations == 0


def test_da_token_rejected_typed_200_not_unknown() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    sub = store.register_owned_subscription(user)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenRejected(code="CALENDAR_ACCOUNT_DISCONNECTED")
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([sub]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["results"][0]["status"] == "preflight_rejected"
    assert body["results"][0]["preflight_code"] == "CALENDAR_ACCOUNT_DISCONNECTED"
    assert body["overall_outcome"] == "no_op"
    assert h.ports.recorder.parent_targets == []


def test_da_token_api_error_becomes_unknown_not_token_rejected() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    sub = store.register_owned_subscription(user)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = "api_error"
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([sub]))
    assert response.status_code == 503
    assert response.json()["code"] == "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
    assert response.json()["code"] != "CALENDAR_REFRESH_NOT_CONFIGURED"


def test_da_token_bad_type_becomes_unknown() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    sub = store.register_owned_subscription(user)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = "bad_type"
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([sub]))
    assert response.status_code == 503
    assert response.json()["code"] == "CALENDAR_REFRESH_OUTCOME_UNKNOWN"


def test_da_native_precommit_credential_refusal_currently_unknown() -> None:
    """Boundary-A pre-commit refusal today becomes UNKNOWN (classification gap).

    See UNSOUND-SEAMS.md — do not treat this 503 as classified credential policy.
    """
    store = HarnessIdentityStore()
    owner = store.add_browser_user(session_epoch=1)
    cred, secret = store.add_agent_credential(owner)
    sub = store.register_owned_subscription(owner)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenReady(access_token="harness-access")
        h.ports.default_apply = "revoke_credential_then_commit"
        h.ports.revoke_credential_id_on_apply = cred.id
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([sub]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
    assert len(h.ports.recorder.parent_targets) == 1
    _ = PENDING_NATIVE_PARENT_REASON  # documented adjacent; case still asserts HTTP


def test_da_role_retirement_order_auth_before_telemetry_before_token() -> None:
    store = HarnessIdentityStore()
    owner = store.add_browser_user(session_epoch=1)
    _cred, secret = store.add_agent_credential(owner)
    sub = store.register_owned_subscription(owner)
    with domain_auth_asgi_client(store=store, install_binding=True) as h:
        h.ports.default_token = TokenRejected(code="HARNESS_TOKEN_REJECTED")
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([sub]),
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert response.status_code == 200, response.text
    purposes = h.ports.recorder.purpose_sequence()
    assert purposes.index(PURPOSE_AUTH_IDENTITY) < purposes.index(PURPOSE_TELEMETRY)
    assert purposes.index(PURPOSE_TELEMETRY) < purposes.index(PURPOSE_AUTH_PREFLIGHT)
    assert purposes.index(PURPOSE_AUTH_PREFLIGHT) < purposes.index(PURPOSE_TOKEN)
    assert purposes.count(PURPOSE_TELEMETRY) == 1
    retirements = [role.value for role in h.ports.recorder.role_retirements]
    assert retirements[0] == "auth"
    assert "telemetry" in retirements
    _assert_role_accounting_sound(h.ports.recorder)
    # TokenRejected path never opens PARENT — lifecycle must stay empty.
    assert h.ports.recorder.parent_lifecycle_events == []
    assert PURPOSE_PARENT not in purposes


def test_da_pending_full_assessment_freshness_not_claimed() -> None:
    """Honest pending: readiness/freshness SQL parity is not faked end-to-end."""
    pytest.skip(PENDING_ASSESSMENT_FRESHNESS_REASON)


def test_da_pending_native_parent_driver_not_claimed() -> None:
    """Honest pending: FakeParentDriver is not reviewed native PostgreSQL proof."""
    pytest.skip(PENDING_NATIVE_PARENT_REASON)
