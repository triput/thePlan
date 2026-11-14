"""Prepared fake checks. No network, DB, lifespan or production binding."""
import asyncio
import json
from threading import Event
from types import SimpleNamespace

import pytest

from app.api.middleware.covering_ingress import (
    BODY_LIMIT, CONTEXT_KEY, COVERING_PATH, CoveringIngressMiddleware,
    CoveringRequestContext,
)
from app.services.covering_request_budget import (
    CoveringRequestBudget, CoveringDeadlineExceeded, CoveringBudgetStopped,
)
from app.services.covering_role_connector import (
    CoveringRoleConnector, SessionBinding, RoleCompletion,
)
from app.services.covering_role_admission import CoveringRole


class Clock:
    def __init__(self):
        self.value = 0.0
    def __call__(self):
        return self.value


async def ingress(messages, app, clock=None, headers=(), path=COVERING_PATH):
    source = asyncio.Queue()
    for message in messages:
        source.put_nowait(message)
    sent = []
    async def send(message):
        sent.append(message)
    scope = {"type": "http", "method": "POST", "path": path,
             "headers": list(headers), "state": {}}
    middleware = CoveringIngressMiddleware(app, clock=clock or Clock())
    await middleware(scope, source.get, send)
    return scope, sent


def chunk(body=b"", more=False):
    return {"type": "http.request", "body": body, "more_body": more}


@pytest.mark.parametrize("headers", [(), ((b"content-length", b"1"),)])
def test_f1_streamed_limit_precedes_downstream(headers):
    async def forbidden(*args):
        pytest.fail("oversize body admitted downstream")
    _, sent = asyncio.run(ingress(
        [chunk(b"x" * BODY_LIMIT, True), chunk(b"x")], forbidden, headers=headers))
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["code"] == "CALENDAR_REFRESH_REQUEST_TOO_LARGE"


def test_exact_body_limit_and_offroute_passthrough():
    seen = []
    async def app(scope, receive, send):
        seen.append((await receive())["body"])
    asyncio.run(ingress([chunk(b"x" * BODY_LIMIT)], app))
    asyncio.run(ingress([chunk(b"x" * (BODY_LIMIT + 1))], app, path="/other"))
    assert [len(x) for x in seen] == [BODY_LIMIT, BODY_LIMIT + 1]


def test_f2_body_budget_expires_before_downstream():
    clock = Clock()
    async def forbidden(*args):
        pytest.fail("expired body admitted downstream")
    async def run():
        sent = []
        async def receive():
            clock.value = 210
            return chunk(b"{}")
        async def send(message):
            sent.append(message)
        await CoveringIngressMiddleware(forbidden, clock)(
            {"type":"http", "method":"POST", "path":COVERING_PATH}, receive, send)
        return sent
    sent = asyncio.run(run())
    assert sent[0]["status"] == 504
    assert json.loads(sent[1]["body"])["code"] == "CALENDAR_REFRESH_DEADLINE_EXCEEDED"


def test_disconnect_before_body_admits_nothing():
    async def forbidden(*args):
        pytest.fail("disconnected body admitted downstream")
    _, sent = asyncio.run(ingress([{"type":"http.disconnect"}], forbidden))
    assert sent == []


def test_disconnect_after_body_stops_admission_suppresses_send():
    async def app(scope, receive, send):
        await receive()
        message = await receive()
        assert message["type"] == "http.disconnect"
        context = scope["state"][CONTEXT_KEY]
        with pytest.raises(CoveringBudgetStopped):
            context.budget.work_remaining()
        # Cleanup remains available for resources already admitted.
        with context.budget.cleanup():
            assert context.budget.cleanup_remaining() == 30
        await send({"type":"http.response.start", "status":200, "headers":[]})
    _, sent = asyncio.run(ingress([chunk(), {"type":"http.disconnect"}], app))
    assert sent == []


def test_bad_receive_wakes_waiter_and_stops_admission():
    async def app(scope, receive, send):
        await receive()
        await receive()
    with pytest.raises(RuntimeError, match="unexpected ASGI"):
        asyncio.run(ingress([chunk(), {"type":"websocket.receive"}], app))


def test_cleanup_is_cumulative_and_within_total_deadline():
    clock = Clock()
    budget = CoveringRequestBudget(clock)
    with budget.cleanup():
        clock.value = 12
    assert budget.work_remaining() == 198
    clock.value = 209
    with budget.cleanup():
        assert budget.cleanup_remaining() == 18
        clock.value = 226
    with budget.cleanup():
        assert budget.cleanup_remaining() == 1
        clock.value = 227
    with pytest.raises(CoveringBudgetStopped):
        budget.work_remaining()
    near_end = CoveringRequestBudget(clock)
    clock.value += 235
    with near_end.cleanup():
        assert near_end.cleanup_remaining() == 5


def test_ordinary_retirement_uses_cleanup_after_disconnect():
    clock, cancelled, calls = Clock(), Event(), []
    budget = CoveringRequestBudget(clock, cancelled=cancelled.is_set)
    def factory(role, target, remaining):
        identity = object()
        def close(cleanup_remaining):
            calls.append(cleanup_remaining())
            return RoleCompletion(identity, True, True, True)
        return SessionBinding(object(), identity, close,
                              lambda: pytest.fail("unexpected quarantine"))
    connector = CoveringRoleConnector(budget=budget, parent_factory=None,
                                      session_factory=factory)
    with connector.session_scope(CoveringRole.AUTH):
        clock.value = 211
        cancelled.set()
    assert calls == [29]
    with pytest.raises(CoveringBudgetStopped):
        with connector.session_scope(CoveringRole.TOKEN):
            pytest.fail("new role after disconnect")


def test_no_fallback_without_release_binding():
    from app.api.errors import ApiError
    from app.services.covering_http_dispatch import dispatch_covering_http
    event = Event()
    context = CoveringRequestContext(CoveringRequestBudget(), event)
    request = SimpleNamespace(scope={"state":{CONTEXT_KEY:context}},
                              app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(ApiError) as caught:
        asyncio.run(dispatch_covering_http(request, object()))
    assert caught.value.content["code"] == "CALENDAR_REFRESH_NOT_CONFIGURED"


def test_joined_worker_uses_ingress_budget_and_thread(monkeypatch):
    import threading
    from app.services.covering_http_dispatch import (
        CoveringReleaseBinding, dispatch_covering_http,
    )
    context = CoveringRequestContext(CoveringRequestBudget(), Event())
    caller_thread = threading.get_ident()
    def dispatch(request, body, ctx, connector):
        assert threading.get_ident() != caller_thread
        assert connector.budget is context.budget
        assert ctx is context
        return "joined"
    binding = boundary_binding(monkeypatch, dispatch)
    request = SimpleNamespace(scope={"state":{CONTEXT_KEY:context}},
        app=SimpleNamespace(state=SimpleNamespace(covering_release_binding=binding)))
    assert asyncio.run(dispatch_covering_http(request, object())) == "joined"


def test_f2_auth_telemetry_is_not_calendar_admission(monkeypatch):
    from app.api.errors import ApiError
    from app.services.covering_http_dispatch import (
        CoveringReleaseBinding, dispatch_covering_http,
    )
    context = CoveringRequestContext(CoveringRequestBudget(), Event())
    def dispatch(request, body, ctx, connector):
        ctx.auth_telemetry_admitted = True
        raise CoveringDeadlineExceeded()
    request = SimpleNamespace(scope={"state":{CONTEXT_KEY:context}},
        app=SimpleNamespace(state=SimpleNamespace(
            covering_release_binding=boundary_binding(monkeypatch, dispatch))))
    with pytest.raises(ApiError) as caught:
        asyncio.run(dispatch_covering_http(request, object()))
    assert caught.value.content["code"] == "CALENDAR_REFRESH_DEADLINE_EXCEEDED"


def test_cancellation_joins_admitted_worker(monkeypatch):
    import anyio
    from app.services.covering_http_dispatch import CoveringReleaseBinding, dispatch_covering_http
    started, release, finished = Event(), Event(), Event()
    context = CoveringRequestContext(CoveringRequestBudget(), Event())
    def dispatch(request, body, ctx, connector):
        started.set()
        assert release.wait(2), "fixture release was not delivered"
        finished.set()
        return "retired"
    request = SimpleNamespace(scope={"state":{CONTEXT_KEY:context}},
        app=SimpleNamespace(state=SimpleNamespace(
            covering_release_binding=boundary_binding(monkeypatch, dispatch))))
    async def run():
        async with anyio.create_task_group() as group:
            group.start_soon(dispatch_covering_http, request, object())
            assert await anyio.to_thread.run_sync(started.wait, 2)
            context.disconnected.set()
            group.cancel_scope.cancel()
            release.set()
        assert finished.is_set(), "admitted worker detached on cancellation"
    anyio.run(run)


def boundary_binding(monkeypatch, dispatch):
    # Boundary-only worker/cancellation probe; domain checks use real dispatch.
    from app.services import covering_http_dispatch as module
    from app.services.covering_domain_dispatch import CoveringDomainPorts
    monkeypatch.setattr(module, "run_bounded_domain",
                        lambda request, body, ctx, connector, ports:
                            dispatch(request, body, ctx, connector))
    return module.CoveringReleaseBinding(None, None, CoveringDomainPorts(None,None,None))
