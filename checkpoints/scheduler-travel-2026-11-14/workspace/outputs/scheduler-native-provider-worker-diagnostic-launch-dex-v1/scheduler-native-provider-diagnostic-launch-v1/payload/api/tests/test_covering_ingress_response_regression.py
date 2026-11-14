"""Focused fake-only response regressions; selected explicitly by v3 launcher."""
import asyncio
import json
import test_covering_production_boundary as boundary
from app.api.middleware.covering_ingress import CoveringIngressMiddleware, COVERING_PATH


def test_ingress_413_without_content_length():
    boundary.test_f1_streamed_limit_precedes_downstream(())


def test_ingress_413_with_underreported_content_length():
    boundary.test_f1_streamed_limit_precedes_downstream(((b"content-length", b"1"),))


def test_ingress_504_on_body_budget_expiry():
    boundary.test_f2_body_budget_expires_before_downstream()


def test_ingress_exact_limit_and_offroute_passthrough():
    boundary.test_exact_body_limit_and_offroute_passthrough()


def test_ingress_504_on_receive_timeout():
    async def run():
        sent=[]
        calls=[]
        async def forbidden(*args):
            calls.append("downstream")
            raise AssertionError("timed-out ingress admitted downstream")
        async def receive():
            raise asyncio.TimeoutError()
        async def send(message):
            sent.append(message)
        await CoveringIngressMiddleware(forbidden, boundary.Clock())(
            {"type":"http","method":"POST","path":COVERING_PATH},receive,send)
        return sent,calls
    sent,calls=asyncio.run(run())
    assert calls==[]
    assert [m["type"] for m in sent]==["http.response.start","http.response.body"]
    assert sent[0]["status"]==504
    assert json.loads(sent[1]["body"])=={
        "detail":"Calendar refresh deadline exceeded.",
        "code":"CALENDAR_REFRESH_DEADLINE_EXCEEDED",
    }
