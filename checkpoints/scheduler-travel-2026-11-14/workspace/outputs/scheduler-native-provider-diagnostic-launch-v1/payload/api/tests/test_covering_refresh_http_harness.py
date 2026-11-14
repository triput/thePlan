"""Offline ASGI proofs for covering-refresh HTTP boundary (I3 / H1–H2 / H6).

Uses ``support.covering_refresh_asgi_harness`` — real calendar router + mirrored
middleware add-order, synthetic signed sessions / Bearer, fail-closed fakes.
Does **not** use disposable Postgres (``test_covering_refresh_d2``) and does
**not** start production lifespan.

Prefer the isolated entry
``tests/support/run_covering_refresh_http_harness_offline.py`` (plugin autoload
off, empty ``-c`` config, scrubbed synthetic settings / no dotenv, engine
tripwire, ``-x``, no bytecode/cache). Plain
``pytest tests/test_covering_refresh_http_harness.py`` still loads shared
``tests/conftest.py`` and is **not** the proposed fake-only command.

FINDINGS (R1 approved; baseline cannot yet produce — kept visible):
- F1: No streamed 16 KiB JSON ceiling → no 413 CALENDAR_REFRESH_REQUEST_TOO_LARGE
- F2: No ASGI-entry 240s/210s+30s deadline budget → no pre-ownership 504
      CALENDAR_REFRESH_DEADLINE_EXCEEDED from production code
- F3: Post-ownership deadline exhaustion typed-200 shape is encoded via fake
      orchestrator only; production ``run_covering_refresh`` does not yet mark
      unstarted targets with CALENDAR_REFRESH_DEADLINE_EXCEEDED
- F4: ``app.db`` still constructs ``create_engine`` at import (unbound profile
      hold — harness never dials; live SessionLocal + connect tripwire fail-closed)
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from support.covering_refresh_asgi_harness import (
    COVERING_PATH,
    OFF_ROUTE_PATH,
    PRODUCTION_COVERING_METHOD_PATHS,
    PRODUCTION_MIDDLEWARE_ADD_ORDER,
    FakeCoveringOrchestrator,
    HARNESS_SESSION_SECRET,
    HarnessIdentityStore,
    asgi_post_chunked_json,
    covering_method_paths,
    covering_refresh_asgi_client,
    middleware_add_order_names,
    mint_signed_session_cookie,
    refresh_body,
)

# ---------------------------------------------------------------------------
# Static parity vs production (not "mirror counts as proof")
# ---------------------------------------------------------------------------


def test_h1_static_covering_routes_and_middleware_match_production() -> None:
    """Compare harness registrations to frozen create_app constants + live create_app."""
    from app.main import create_app

    with covering_refresh_asgi_client() as harness:
        harness_mw = tuple(middleware_add_order_names(harness.app))
        harness_covering = covering_method_paths(harness.app)

    prod = create_app()  # constructs app only; lifespan not entered without ASGI startup
    try:
        prod_mw = tuple(middleware_add_order_names(prod))
        prod_covering = covering_method_paths(prod)
    finally:
        prod.dependency_overrides.clear()

    assert harness_mw == PRODUCTION_MIDDLEWARE_ADD_ORDER
    assert prod_mw == PRODUCTION_MIDDLEWARE_ADD_ORDER
    assert harness_mw == prod_mw

    assert harness_covering == PRODUCTION_COVERING_METHOD_PATHS
    assert prod_covering == PRODUCTION_COVERING_METHOD_PATHS
    assert harness_covering == prod_covering
    # No aliases beyond POST /api/v1/calendar/covering-refresh.
    assert harness_covering == {("POST", COVERING_PATH)}


# ---------------------------------------------------------------------------
# Browser signed session + gates
# ---------------------------------------------------------------------------


def test_h1_normal_browser_signed_session_reaches_orchestrator() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=3)
    orch = FakeCoveringOrchestrator(mode="success")
    sub_a, sub_b = uuid4(), uuid4()

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=3),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([sub_a, sub_b]))

    assert response.status_code == 200, response.text
    assert response.json()["overall_outcome"] == "success"
    assert orch.provider_admissions == 2
    assert orch.dispatched_subscription_ids == [sub_a, sub_b]
    assert h.touch_telemetry.credential_ids == []


def test_h1_stale_session_epoch_is_unauthenticated() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=5)
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=4),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert orch.provider_admissions == 0
    assert h.touch_telemetry.credential_ids == []


def test_h1_disabled_user_is_unauthenticated() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1, is_disabled=True)
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert orch.provider_admissions == 0


def test_h1_password_change_gate_blocks_before_orchestrator() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=2, must_change_password=True)
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=2),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([uuid4()]))

    assert response.status_code == 403
    assert response.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert orch.provider_admissions == 0
    assert h.touch_telemetry.credential_ids == []


# ---------------------------------------------------------------------------
# Bearer precedence / telemetry / password-gate 403 over Bearer
# ---------------------------------------------------------------------------


def test_h1_bearer_precedes_cookie_on_mixed_request_one_touch() -> None:
    store = HarnessIdentityStore()
    browser = store.add_browser_user(session_epoch=1)
    agent_owner = store.add_browser_user(session_epoch=9)
    cred, secret = store.add_agent_credential(agent_owner)
    orch = FakeCoveringOrchestrator(mode="success")
    target = uuid4()

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=browser.id, session_epoch=1),
        )
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([target]),
            headers={"Authorization": f"Bearer {secret}"},
        )

    assert response.status_code == 200, response.text
    assert orch.provider_admissions == 1
    assert orch.call_owner_ids == [agent_owner.id]
    assert orch.call_owner_ids[0] != browser.id
    # deps.touch_last_used alias — exactly one telemetry touch on valid Bearer.
    assert h.touch_telemetry.credential_ids == [cred.id]


def test_h1_malformed_bearer_refuses_without_cookie_fallback_no_touch() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([uuid4()]),
            headers={"Authorization": "Bearer not-a-valid-agent-secret"},
        )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert orch.provider_admissions == 0
    assert h.touch_telemetry.credential_ids == []


def test_h1_empty_bearer_token_refuses_without_cookie_fallback_no_touch() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
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
    assert orch.provider_admissions == 0
    assert h.touch_telemetry.credential_ids == []


def test_h1_password_change_cookie_precedes_valid_bearer_no_touch() -> None:
    """Real middleware order: PasswordChangeGate 403 before deps/Bearer telemetry."""
    store = HarnessIdentityStore()
    gated = store.add_browser_user(session_epoch=2, must_change_password=True)
    agent_owner = store.add_browser_user(session_epoch=9)
    _cred, secret = store.add_agent_credential(agent_owner)
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
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
    assert orch.provider_admissions == 0
    assert h.touch_telemetry.credential_ids == []


# ---------------------------------------------------------------------------
# Known ordered outcomes / caps
# ---------------------------------------------------------------------------


def test_h2_ordered_two_target_partial_returns_http_200() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    ordered = [uuid4(), uuid4()]
    orch = FakeCoveringOrchestrator(mode="partial_two")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body(ordered))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_outcome"] == "partial"
    assert [row["subscription_id"] for row in body["results"]] == [str(x) for x in ordered]
    assert body["results"][0]["status"] == "ok"
    assert body["results"][1]["status"] == "failed"
    assert orch.dispatched_subscription_ids == ordered


def test_h2_twenty_targets_accepted() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    ids = [uuid4() for _ in range(20)]
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body(ids))

    assert response.status_code == 200, response.text
    assert response.json()["action_summary"]["requested"] == 20
    assert orch.provider_admissions == 20


def test_h2_twenty_one_targets_rejected_before_orchestrator() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    ids = [uuid4() for _ in range(21)]
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body(ids))

    assert response.status_code == 422
    assert orch.provider_admissions == 0
    assert orch.call_bodies == []


# ---------------------------------------------------------------------------
# UNKNOWN 503 — HTTP mapping only (+ fake coordinator stop evidence)
# ---------------------------------------------------------------------------


def test_h2_unknown_outcome_sanitized_503_http_mapping_only() -> None:
    """Fake raises CoveringRootOutcomeUnknown → proves route→503 mapping only.

    Does **not** prove native root/ack UNKNOWN coordination. Separate evidence:
    fake coordinator stops further dispatch (second/third never admitted).
    """
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    first, second, third = uuid4(), uuid4(), uuid4()
    orch = FakeCoveringOrchestrator(mode="success", unknown_after_dispatch_count=1)

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(
            COVERING_PATH,
            json=refresh_body([first, second, third]),
        )

    assert response.status_code == 503, response.text
    payload = response.json()
    assert payload["code"] == "CALENDAR_REFRESH_OUTCOME_UNKNOWN"
    assert "Do not retry automatically" in payload["detail"]
    # Coordinator-stop evidence (fake): first admitted; later never dispatched.
    assert orch.dispatched_subscription_ids == [first]
    assert orch.provider_admissions == 1
    assert second not in orch.dispatched_subscription_ids
    assert third not in orch.dispatched_subscription_ids
    assert orch.unadmitted_subscription_ids == []


# ---------------------------------------------------------------------------
# Off-route control (H6)
# ---------------------------------------------------------------------------


def test_h6_off_route_control_middleware_sane_no_covering_leak() -> None:
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    orch = FakeCoveringOrchestrator(mode="success")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        bare = h.client.get(OFF_ROUTE_PATH)
        assert bare.status_code == 200
        assert bare.json()["route"] == "off-route-control"
        assert "CALENDAR_REFRESH" not in bare.text

        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        authed = h.client.post(OFF_ROUTE_PATH, json={})
        assert authed.status_code == 200
        assert authed.json()["user_id"] == str(user.id)
        assert authed.json().get("code") is None
        assert orch.provider_admissions == 0


def test_h6_health_does_not_invoke_covering_orchestrator() -> None:
    orch = FakeCoveringOrchestrator(mode="success")
    with covering_refresh_asgi_client(orchestrator=orch) as h:
        response = h.client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert orch.provider_admissions == 0


# ---------------------------------------------------------------------------
# R1 findings — approved limits not yet in baseline production path
# ---------------------------------------------------------------------------


def test_finding_f1_baseline_lacks_413_request_too_large() -> None:
    """FINDING F1: oversized JSON field is not sanitized 413 CALENDAR_REFRESH_REQUEST_TOO_LARGE."""
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    orch = FakeCoveringOrchestrator(mode="success")
    huge_label = "x" * (17 * 1024)
    payload = refresh_body([uuid4()], scheduling_horizon_label=huge_label)

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=payload)

    assert response.status_code != 413
    if response.headers.get("content-type", "").startswith("application/json"):
        assert response.json().get("code") != "CALENDAR_REFRESH_REQUEST_TOO_LARGE"
    assert orch.provider_admissions == 0


def test_finding_f1_fixed_length_raw_body_admits_without_413() -> None:
    """FINDING F1 (fixed-length): valid JSON + trailing whitespace is one-target admit.

    TestClient ``content=`` is a single buffer (not multi-chunk). Baseline has no
    body-size gate → HTTP 200 + one fake admission (not 413 / zero-admission).
    Future 413 acceptance stays separate (see skipped future marker below).
    """
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    orch = FakeCoveringOrchestrator(mode="success")
    noise = " " * (16 * 1024 + 128)
    raw = (json.dumps(refresh_body([uuid4()])) + noise).encode("utf-8")
    assert len(raw) > 16 * 1024

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(
            COVERING_PATH,
            content=raw,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["overall_outcome"] == "success"
    assert response.json().get("code") != "CALENDAR_REFRESH_REQUEST_TOO_LARGE"
    assert orch.provider_admissions == 1


def test_finding_f1_chunked_asgi_no_content_length_admits_without_413() -> None:
    """FINDING F1 (multi-chunk ASGI, no Content-Length): baseline admits one target.

    Valid refresh JSON + trailing whitespace remains a valid one-target body; with
    no streamed size gate the authenticated request reaches the fake orchestrator
    (HTTP 200, one admission). Not a disconnect-race measurement — receive waits
    for response completion before ``http.disconnect``.
    """
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    orch = FakeCoveringOrchestrator(mode="success")
    noise = " " * (16 * 1024 + 256)
    raw = (json.dumps(refresh_body([uuid4()])) + noise).encode("utf-8")
    assert len(raw) > 16 * 1024
    cookie = mint_signed_session_cookie(user_id=user.id, session_epoch=1)

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        status, body, _headers = asgi_post_chunked_json(
            h.app,
            path=COVERING_PATH,
            body=raw,
            cookie=cookie,
            chunk_size=2048,
        )

    assert status == 200, body[:500]
    parsed = json.loads(body.decode("utf-8"))
    assert parsed["overall_outcome"] == "success"
    assert parsed.get("code") != "CALENDAR_REFRESH_REQUEST_TOO_LARGE"
    assert orch.provider_admissions == 1


@pytest.mark.skip(
    reason=(
        "FUTURE F1 acceptance: once streamed 16 KiB gate lands, oversize bodies "
        "must return 413 CALENDAR_REFRESH_REQUEST_TOO_LARGE with zero provider "
        "admission — not baseline behavior today."
    )
)
def test_finding_f1_future_413_zero_admission_acceptance() -> None:
    raise AssertionError("unreachable until production 16 KiB admission gate lands")


@pytest.mark.skip(
    reason=(
        "FINDING F2: baseline has no ASGI-entry deadline budget; cannot produce "
        "pre-ownership sanitized 504 CALENDAR_REFRESH_DEADLINE_EXCEEDED without "
        "production admission seam (not applied in this packet)."
    )
)
def test_finding_f2_pre_ownership_deadline_504() -> None:
    raise AssertionError("unreachable until production deadline admission lands")


def test_finding_f3_post_ownership_exhaustion_typed_200_unadmitted_second() -> None:
    """Approved R1 post-ownership shape via fake only; second target counted unadmitted.

    FINDING F3: production ``run_covering_refresh`` does not yet emit this shape.
    Coordinator-stop (UNKNOWN) is separate — this path returns typed 200.
    """
    store = HarnessIdentityStore()
    user = store.add_browser_user(session_epoch=1)
    first, second = uuid4(), uuid4()
    orch = FakeCoveringOrchestrator(mode="post_ownership_deadline_exhaustion")

    with covering_refresh_asgi_client(store=store, orchestrator=orch) as h:
        h.client.cookies.set(
            "session",
            mint_signed_session_cookie(user_id=user.id, session_epoch=1),
        )
        response = h.client.post(COVERING_PATH, json=refresh_body([first, second]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_outcome"] == "partial"
    assert body["results"][0]["status"] == "ok"
    assert body["results"][1]["status"] == "preflight_rejected"
    assert body["results"][1]["preflight_code"] == "CALENDAR_REFRESH_DEADLINE_EXCEEDED"
    assert orch.dispatched_subscription_ids == [first]
    assert orch.provider_admissions == 1
    assert orch.unadmitted_subscription_ids == [second]
    assert second not in orch.dispatched_subscription_ids


def test_finding_f4_harness_session_secret_is_not_production_default() -> None:
    """Harness signs cookies with an offline secret; production default remains untouched."""
    assert HARNESS_SESSION_SECRET != "dev-insecure-session-secret-change-me"
    assert "harness" in HARNESS_SESSION_SECRET
