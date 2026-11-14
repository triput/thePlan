"""In-process ASGI app for I01. Mirrors production middleware add-order. No host bind."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from threading import Event, Thread
from time import monotonic
from typing import Any, Callable

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.testclient import TestClient

from app.api.errors import ApiError, register_exception_handlers
from app.api.middleware import PasswordChangeGateMiddleware
from app.api.middleware.agent_boundary_a import AgentBoundaryAMiddleware
from app.api.middleware.covering_ingress import CONTEXT_KEY, CoveringIngressMiddleware, is_covering
from app.api.routes import calendar as calendar_routes
from app.config import get_settings
from i01_auth_seed import FIXTURE_SESSION_SECRET


PRODUCTION_MIDDLEWARE_ADD_ORDER: tuple[str, ...] = (
    "PasswordChangeGateMiddleware",
    "AgentBoundaryAMiddleware",
    "SessionMiddleware",
    "CoveringIngressMiddleware",
    "CORSMiddleware",
)

COVERING_PATH = "/api/v1/calendar/covering-refresh"
MONITOR_OBSERVE_JOIN_SECONDS = 60.0


class ControllableClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = float(value)

    def __call__(self) -> float:
        return self.value


@dataclass
class DisconnectInjectControl:
    """Fixture-owned actual ASGI http.disconnect injector for C09.

    Does not call CoveringRequestContext.disconnected.set(). Production monitor
    must observe the injected http.disconnect on the live receive stream.
    Delivery and monitor-observation are armed on the single hooked_receive path.
    """

    loop: asyncio.AbstractEventLoop | None = None
    inject_queue: asyncio.Queue | None = None
    disconnect_delivered: Event = field(default_factory=Event)
    monitor_observed: Event = field(default_factory=Event)
    post_disconnect_outbound: list[str] = field(default_factory=list)
    _bound: bool = False
    _observe_armed: bool = False
    _monitor_thread: Thread | None = None
    monitor_observe_retirement: str | None = None  # pending|joined|join_timeout|idle

    def bind(self, *, loop: asyncio.AbstractEventLoop, inject_queue: asyncio.Queue) -> None:
        self.loop = loop
        self.inject_queue = inject_queue
        self._bound = True

    def inject_http_disconnect(self, *, timeout: float = 60.0) -> None:
        """Enqueue actual ASGI http.disconnect. Delivery flag is set on consume path."""
        if not self._bound or self.loop is None or self.inject_queue is None:
            raise RuntimeError("DisconnectInjectControl not bound to live receive stream")
        future = asyncio.run_coroutine_threadsafe(
            self.inject_queue.put({"type": "http.disconnect"}),
            self.loop,
        )
        future.result(timeout)

    def note_injected_disconnect_for_monitor(self, disconnected: Event) -> None:
        """Common-path arming: mark delivered, then wait for production Event.set.

        Uses Event.wait (condition wait), not a busy/monotonic spin loop.
        Must be called on the hooked_receive path before returning the message
        to production monitor(). Retains the observe thread for explicit join.
        Does not fabricate disconnected.set() to wake failure cleanup.
        """
        self.disconnect_delivered.set()
        if self._observe_armed:
            return
        self._observe_armed = True
        self.monitor_observe_retirement = "pending"

        def watch() -> None:
            # Production monitor calls disconnected.set() after consuming http.disconnect.
            if disconnected.wait(timeout=MONITOR_OBSERVE_JOIN_SECONDS):
                if self.disconnect_delivered.is_set():
                    self.monitor_observed.set()

        thread = Thread(target=watch, name="i01-c09-monitor-observe", daemon=False)
        self._monitor_thread = thread
        thread.start()

    def retire_monitor_observation(
        self, *, timeout: float = MONITOR_OBSERVE_JOIN_SECONDS
    ) -> str:
        """Join the monitor-observe thread on every path. monitor_observed ≠ retired."""
        thread = self._monitor_thread
        if thread is None:
            if self.monitor_observe_retirement is None:
                self.monitor_observe_retirement = "idle"
            return self.monitor_observe_retirement
        if self.monitor_observe_retirement in ("joined", "join_timeout"):
            return self.monitor_observe_retirement
        thread.join(timeout)
        if thread.is_alive():
            self.monitor_observe_retirement = "join_timeout"
        else:
            self.monitor_observe_retirement = "joined"
            self._monitor_thread = None
        return self.monitor_observe_retirement


async def _next_receive_message(
    receive,
    inject_queue: asyncio.Queue,
) -> tuple[dict[str, Any], str]:
    """One common receive/inject path with deterministic retirement and dual-completion handling."""
    recv_task = asyncio.create_task(receive(), name="i01-asgi-recv")
    inj_task = asyncio.create_task(inject_queue.get(), name="i01-asgi-inject")
    chosen: dict[str, Any] | None = None
    source: str | None = None
    accounted: set[asyncio.Task] = set()
    inj_value: dict[str, Any] | None = None
    inj_exc: BaseException | None = None
    recv_value: dict[str, Any] | None = None
    recv_exc: BaseException | None = None
    primary: BaseException | None = None
    secondary: list[BaseException] = []

    def _account(task: asyncio.Task, *, is_inject: bool) -> None:
        nonlocal inj_value, inj_exc, recv_value, recv_exc
        if task in accounted or not task.done():
            return
        accounted.add(task)
        try:
            value = task.result()
        except BaseException as exc:
            if is_inject:
                inj_exc = exc
            else:
                recv_exc = exc
            return
        if is_inject:
            inj_value = value
        else:
            recv_value = value

    try:
        await asyncio.wait(
            {recv_task, inj_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Re-check both children: a peer may complete after the wait snapshot.
        _account(inj_task, is_inject=True)
        _account(recv_task, is_inject=False)

        # Prefer injected disconnect when both complete; never silently discard the other.
        if inj_value is not None:
            chosen = inj_value
            source = "inject"
            if recv_value is not None:
                raise RuntimeError(
                    f"concurrent upstream receive while inject delivered: {recv_value!r}"
                )
            if recv_exc is not None and not isinstance(recv_exc, asyncio.CancelledError):
                raise RuntimeError(
                    "concurrent upstream receive error while inject delivered"
                ) from recv_exc
        elif recv_value is not None:
            chosen = recv_value
            source = "receive"
            if inj_exc is not None and not isinstance(inj_exc, asyncio.CancelledError):
                raise RuntimeError(
                    "concurrent inject error while receive delivered"
                ) from inj_exc
        elif inj_exc is not None:
            raise inj_exc
        elif recv_exc is not None:
            raise recv_exc
        else:
            raise RuntimeError("receive/inject wait completed without value or error")

        return chosen, source
    except BaseException as exc:
        primary = exc
        raise
    finally:
        # Account for every created child. Cancel only still-pending tasks; never
        # skip a late-completing peer because task.done() became true after wait.
        for task, is_inject in ((recv_task, False), (inj_task, True)):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    secondary.append(exc)
            _account(task, is_inject=is_inject)
            if task.done() and task not in accounted:
                # Defensive: result() already consumed elsewhere.
                accounted.add(task)
        # Late successful peer values after selection are simultaneous-completion
        # refusals — same contract as both visible in the try body. Do not discard.
        if source == "inject" and recv_value is not None:
            secondary.append(
                RuntimeError(
                    f"concurrent upstream receive while inject delivered: {recv_value!r}"
                )
            )
        if source == "receive" and inj_value is not None:
            secondary.append(
                RuntimeError(
                    f"concurrent inject while receive delivered: {inj_value!r}"
                )
            )
        # Late / peer errors: always account. Under an independent primary they
        # are secondary evidence (do not drop when primary is already set).
        # Cancellation or error during wait *before* selection leaves
        # source is None; a peer already done with a non-cancel error must
        # still be retained as secondary — never require source is not None
        # (that silently drops the peer and can erase the only non-cancel fault).
        for label, exc in (
            ("inject", inj_exc),
            ("receive", recv_exc),
        ):
            if exc is None or isinstance(exc, asyncio.CancelledError):
                continue
            if exc is primary:
                continue
            if source is None:
                # Pre-selection owner cancellation/error: retain peer fault.
                secondary.append(exc)
            elif (label == "inject" and source == "receive") or (
                label == "receive" and source == "inject"
            ):
                secondary.append(exc)
        if secondary:
            if primary is not None:
                setattr(
                    primary,
                    "fixture_receive_retirement_errors",
                    [
                        {
                            "kind": type(exc).__name__,
                            "message": str(exc)[:200],
                        }
                        for exc in secondary
                    ],
                )
            else:
                # Successful selection path must not silently accept late peer
                # success or late peer failure — refuse explicitly.
                raise RuntimeError(
                    "receive/inject late peer outcome after selection"
                ) from secondary[0]


class ContextCapturingIngress(CoveringIngressMiddleware):
    """Production ingress with fixture-visible context stash + optional disconnect inject."""

    def __init__(
        self,
        app,
        clock=None,
        on_context: Callable[[Any], None] | None = None,
        disconnect_control: DisconnectInjectControl | None = None,
    ):
        super().__init__(app, clock=clock if clock is not None else monotonic)
        self._on_context = on_context
        self._disconnect_control = disconnect_control

    async def __call__(self, scope, receive, send):
        if not is_covering(scope) or (
            self._on_context is None and self._disconnect_control is None
        ):
            return await super().__call__(scope, receive, send)

        inject_queue: asyncio.Queue = asyncio.Queue()
        if self._disconnect_control is not None:
            self._disconnect_control.bind(
                loop=asyncio.get_running_loop(),
                inject_queue=inject_queue,
            )

        seen = {"done": False}
        context_box: dict[str, Any] = {"context": None}

        async def hooked_receive():
            # Single common path: no empty-queue fast-path that skips observation.
            if self._disconnect_control is None:
                message = await receive()
                source = "receive"
            else:
                message, source = await _next_receive_message(receive, inject_queue)

            if not seen["done"]:
                context = (scope.get("state") or {}).get(CONTEXT_KEY)
                if context is not None:
                    context_box["context"] = context
                    if self._on_context is not None:
                        self._on_context(context)
                    seen["done"] = True

            if (
                self._disconnect_control is not None
                and source == "inject"
                and message.get("type") == "http.disconnect"
            ):
                context = context_box.get("context") or (scope.get("state") or {}).get(
                    CONTEXT_KEY
                )
                if context is None:
                    raise RuntimeError(
                        "injected disconnect requires CoveringRequestContext"
                    )
                # Arm delivery + monitor observation BEFORE returning to production monitor.
                self._disconnect_control.note_injected_disconnect_for_monitor(
                    context.disconnected
                )

            return message

        async def observed_send(message):
            control = self._disconnect_control
            context = context_box.get("context") or (scope.get("state") or {}).get(
                CONTEXT_KEY
            )
            if (
                control is not None
                and context is not None
                and context.disconnected.is_set()
                and control.monitor_observed.is_set()
            ):
                msg_type = str(message.get("type") or "")
                if msg_type.startswith("http.response"):
                    control.post_disconnect_outbound.append(msg_type)
            await send(message)

        return await super().__call__(scope, hooked_receive, observed_send)


@dataclass
class BoundedASGIResponse:
    """Result of a bounded direct ASGI drive. Absence of response is valid evidence."""

    status_code: int | None = None
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body: bytes = b""
    response_started: bool = False
    response_completed: bool = False
    error: BaseException | None = None


def run_covering_asgi(
    app: FastAPI,
    *,
    path: str = COVERING_PATH,
    body: bytes,
    headers: list[tuple[bytes, bytes]] | None = None,
    timeout: float = 60.0,
) -> BoundedASGIResponse:
    """Bounded direct ASGI driver (no TestClient).

    Preserves real ingress/dispatch. Tolerates intentional no HTTP response after
    production guarded_send suppression — does not treat missing response as an
    automatic transport assertion failure or the C09 operation oracle.
    """
    result = BoundedASGIResponse()
    header_list = list(headers or [])
    if not any(name.lower() == b"content-length" for name, _ in header_list):
        header_list.append((b"content-length", str(len(body)).encode("ascii")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": header_list,
        "client": ("127.0.0.1", 0),
        "server": ("fixture", 80),
        "state": {},
    }

    body_sent = {"done": False}
    chunks: list[bytes] = []

    async def receive():
        if not body_sent["done"]:
            body_sent["done"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        # Park until cancelled / disconnect inject consumed by ingress monitor.
        await asyncio.Future()
        return {"type": "http.disconnect"}

    async def send(message):
        msg_type = message.get("type")
        if msg_type == "http.response.start":
            result.response_started = True
            result.status_code = int(message.get("status") or 0) or None
            result.headers = list(message.get("headers") or [])
        elif msg_type == "http.response.body":
            chunk = message.get("body") or b""
            if chunk:
                chunks.append(bytes(chunk))
            if not message.get("more_body", False):
                result.response_completed = True
                result.body = b"".join(chunks)

    async def main():
        try:
            await asyncio.wait_for(app(scope, receive, send), timeout=timeout)
        except asyncio.TimeoutError as exc:
            # Unexpected timeout is driver failure evidence — not C09 success.
            result.error = exc
        except BaseException as exc:
            # Unexpected ASGI errors are retained on result.error and must not PASS.
            result.error = exc

    try:
        asyncio.run(main())
    except BaseException as exc:
        if result.error is None:
            result.error = exc
    if chunks and not result.body:
        result.body = b"".join(chunks)
    return result


def install_api_error_observation(
    app: FastAPI,
    on_api_error: Callable[[ApiError], None],
) -> None:
    """Transparent delegate around the registered ApiError handler.

    Observes allowlisted status/code from the real handler path without replacing
    the production mapping. Must be installed after register_exception_handlers
    and before middleware construction.
    """
    original = app.exception_handlers.get(ApiError)
    if original is None:
        raise RuntimeError("ApiError handler missing after register_exception_handlers")

    async def delegated_api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        on_api_error(exc)
        result = original(request, exc)
        if hasattr(result, "__await__"):
            return await result  # type: ignore[misc]
        return result  # type: ignore[return-value]

    app.add_exception_handler(ApiError, delegated_api_error_handler)


def build_i01_asgi_app(
    *,
    clock: ControllableClock | None = None,
    session_secret: str = FIXTURE_SESSION_SECRET,
    on_context: Callable[[Any], None] | None = None,
    disconnect_control: DisconnectInjectControl | None = None,
    on_api_error: Callable[[ApiError], None] | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="I01/I02 covering fixture ASGI", version="0.0-i01-fixture")
    register_exception_handlers(app)
    if on_api_error is not None:
        install_api_error_observation(app, on_api_error)

    app.add_middleware(PasswordChangeGateMiddleware)
    app.add_middleware(AgentBoundaryAMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(
        ContextCapturingIngress,
        clock=clock or ControllableClock(0.0),
        on_context=on_context,
        disconnect_control=disconnect_control,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(calendar_routes.router)
    app.include_router(api_router)
    app.state.covering_release_binding = None
    app.state.last_covering_context = None
    app.state.disconnect_control = disconnect_control
    return app


def install_binding(app: FastAPI, binding: object) -> None:
    app.state.covering_release_binding = binding


def clear_binding(app: FastAPI) -> None:
    app.state.covering_release_binding = None


def asgi_client(app: FastAPI) -> TestClient:
    # In-process only: TestClient never opens a host listener / published port.
    # C09 disconnect uses run_covering_asgi instead — TestClient may assert on
    # intentional no-response after guarded_send suppression.
    return TestClient(app)


def middleware_add_order_names(app: FastAPI) -> list[str]:
    stored = [middleware.cls.__name__ for middleware in app.user_middleware]
    return list(reversed(stored))
