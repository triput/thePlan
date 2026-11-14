"""Covering-only ingress: bounded body, one budget, observed disconnect."""
import asyncio
from dataclasses import dataclass, field
from threading import Event
from time import monotonic
from starlette.responses import JSONResponse
from app.services.covering_request_budget import CoveringRequestBudget, CoveringDeadlineExceeded

COVERING_PATH = "/api/v1/calendar/covering-refresh"
CONTEXT_KEY = "covering_request_context"
BODY_LIMIT = 16 * 1024


def is_covering(scope):
    return scope.get("type") == "http" and scope.get("method") == "POST" and scope.get("path", "").rstrip("/") == COVERING_PATH


@dataclass
class CoveringRequestContext:
    budget: CoveringRequestBudget
    disconnected: Event
    ownership_established: bool = False
    calendar_admitted: bool = False
    auth_telemetry_admitted: bool = False
    completed: list = field(default_factory=list)


async def error(scope, receive, send, status, code, detail):
    response = JSONResponse({"detail": detail, "code": code}, status_code=status)
    # Preserve the HTTP scope required by Starlette's response protocol.
    await response(scope, receive, send)


class CoveringIngressMiddleware:
    def __init__(self, app, clock=monotonic):
        self.app = app
        self.clock = clock

    async def __call__(self, scope, receive, send):
        if not is_covering(scope):
            return await self.app(scope, receive, send)
        disconnected = Event()
        context = CoveringRequestContext(CoveringRequestBudget(self.clock, cancelled=disconnected.is_set), disconnected)
        scope.setdefault("state", {})[CONTEXT_KEY] = context
        body = bytearray()
        try:
            while True:
                message = await asyncio.wait_for(receive(), timeout=context.budget.work_remaining())
                if message["type"] == "http.disconnect":
                    disconnected.set()
                    return
                if message["type"] != "http.request":
                    raise RuntimeError("unexpected ASGI body message")
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > BODY_LIMIT:
                    return await error(scope, receive, send, 413, "CALENDAR_REFRESH_REQUEST_TOO_LARGE", "Calendar refresh request is too large.")
                body.extend(chunk)
                context.budget.work_remaining()
                if not message.get("more_body", False):
                    break
        except (CoveringDeadlineExceeded, asyncio.TimeoutError):
            return await error(scope, receive, send, 504, "CALENDAR_REFRESH_DEADLINE_EXCEEDED", "Calendar refresh deadline exceeded.")
        queue = asyncio.Queue()
        queue.put_nowait({"type": "http.request", "body": bytes(body), "more_body": False})
        async def monitor():
            try:
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        disconnected.set()
                        await queue.put(message)
                        return
                    raise RuntimeError("unexpected ASGI message after complete request")
            except Exception as exc:
                disconnected.set()
                await queue.put(exc)
                raise
        task = asyncio.create_task(monitor())
        async def guarded_receive():
            message = await queue.get()
            if isinstance(message, Exception):
                raise message
            return message
        async def guarded_send(message):
            if not disconnected.is_set():
                await send(message)
        try:
            await self.app(scope, guarded_receive, guarded_send)
            if task.done() and not task.cancelled() and task.exception() is not None:
                raise task.exception()
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
