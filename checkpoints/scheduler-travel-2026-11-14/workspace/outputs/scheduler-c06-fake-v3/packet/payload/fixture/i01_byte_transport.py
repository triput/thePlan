"""Fixture byte transport for CoveringHTTP transport_factory injection."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock, get_ident
from typing import Callable

from app.services.covering_transport_policy import CoveringTransportRefused


@dataclass(frozen=True)
class ScriptedExchange:
    """One reviewed provider exchange. Bodies are response JSON objects only."""
    purpose: str
    method: str
    url_prefix: str
    status: int
    body: dict
    request_body_contains: tuple[str, ...] = ()


@dataclass
class SharedTransportScript:
    """One reviewed script + inventory consumed across connections for a case."""

    script: list[ScriptedExchange]
    inventory: list[dict] = field(default_factory=list)
    index: int = 0
    lock: Lock = field(default_factory=Lock)

    def take(self, method: str, url: str, body_text: str) -> ScriptedExchange:
        with self.lock:
            if self.index >= len(self.script):
                raise CoveringTransportRefused("unscripted provider exchange")
            expected = self.script[self.index]
            if method != expected.method:
                raise CoveringTransportRefused("unscripted provider method")
            if expected.purpose not in ("oauth", "event", "identity"):
                raise CoveringTransportRefused("unscripted provider purpose")
            if not url.startswith(expected.url_prefix) and expected.url_prefix not in url:
                raise CoveringTransportRefused("unscripted provider url")
            for fragment in expected.request_body_contains:
                if fragment not in body_text:
                    raise CoveringTransportRefused("unscripted provider body")
            self.index += 1
            return expected

    def record(self, entry: dict) -> None:
        with self.lock:
            self.inventory.append(entry)


@dataclass
class FixtureByteTransport:
    """In-memory HTTP/1 peer substitute. No sockets, no TLS, no live providers."""

    peer: object
    remaining: Callable[[], float]
    shared: SharedTransportScript
    owner: int = field(default_factory=get_ident)
    closed: bool = False
    sent: bool = False
    _response_wire: bytes = b""
    _read_offset: int = 0

    def check(self) -> float:
        if get_ident() != self.owner or self.closed:
            raise CoveringTransportRefused("transport ownership refused")
        return self.remaining()

    def open(self):
        if self._response_wire:
            raise CoveringTransportRefused("connection reuse refused")
        self.check()
        return self

    def send(self, data: bytes) -> None:
        self.check()
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise CoveringTransportRefused("non-byte request refused")
        wire = bytes(data)
        self.sent = True
        # Minimal HTTP/1 request parse for method/path matching only.
        try:
            head, _, rest = wire.partition(b"\r\n\r\n")
            request_line = head.split(b"\r\n", 1)[0].decode("ascii")
            method, path, _ = request_line.split(" ", 2)
        except Exception as exc:
            raise CoveringTransportRefused("request framing refused") from exc
        host = self.peer.hostname if self.peer.port == 443 else f"{self.peer.hostname}:{self.peer.port}"
        url = f"https://{host}{path}"
        body_text = rest.decode("ascii", errors="replace")
        matched = self.shared.take(method, url, body_text)
        payload = _json_bytes(matched.body)
        self._response_wire = (
            f"HTTP/1.1 {matched.status} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"Connection: close\r\n"
            f"Content-Encoding: identity\r\n"
            f"\r\n"
        ).encode("ascii") + payload
        self._read_offset = 0
        self.shared.record({
            "purpose": matched.purpose,
            "method": matched.method,
            "url_prefix": matched.url_prefix,
            "status": matched.status,
            "request_bytes": len(wire),
            "response_bytes": len(self._response_wire),
        })

    def receive(self, size: int) -> bytes:
        self.check()
        if size <= 0:
            raise CoveringTransportRefused("receive size refused")
        if self._read_offset >= len(self._response_wire):
            return b""
        end = min(len(self._response_wire), self._read_offset + size)
        chunk = self._response_wire[self._read_offset:end]
        self._read_offset = end
        return chunk

    def close(self) -> None:
        self.closed = True


def _json_bytes(body: dict) -> bytes:
    import json
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")


def google_event_empty_script(*, calendar_id: str, host: str = "www.googleapis.com") -> ScriptedExchange:
    prefix = f"https://{host}/calendar/v3/calendars/{calendar_id}/events"
    return ScriptedExchange(
        purpose="event",
        method="GET",
        url_prefix=prefix,
        status=200,
        body={"items": []},
    )


def build_transport_factory(script: list[ScriptedExchange]):
    """Return a CoveringHTTP-compatible transport_factory closing over one shared script."""

    shared = SharedTransportScript(script=list(script))

    def factory(peer, remaining):
        # Each connection shares the same script cursor and inventory; do not reset.
        return FixtureByteTransport(peer=peer, remaining=remaining, shared=shared)

    factory.shared = shared  # type: ignore[attr-defined]
    factory.inventory = shared.inventory  # type: ignore[attr-defined]
    factory.script = shared.script  # type: ignore[attr-defined]
    return factory
