"""Synthetic HTTPS peer — real socket/TLS lifecycle for native-provider prep.

PREPARATION AUTHORING ONLY. This module contains bind/accept/handshake/
request/response/close_notify/abrupt paths suitable for later native launch.
Preparation approval does NOT authorize invoking bind/listen/PKI generation.
Recipe prepare-np-provider-tls.sh remains unexecuted under prep.

Bounded owned peer/reader retirement is implemented in source; invocation and
fault-retirement authority = later launch card only. Unjoined → UNKNOWN.
Preserve ReleasePlan→Counter→CoveringHTTP→JoinedTLS on the client side;
this peer is the complementary server endpoint on numeric loopback.
"""
from __future__ import annotations

import select
import socket
import ssl
import threading
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any

from np_provider_routes import FixturePeerRoute
from np_provider_transcript import CloseMode, ExchangeScript, ExchangeStep


DEFAULT_PEER_TLS_DIR = "/tmp/np-provider-tls"
DEFAULT_SERVER_CERT = f"{DEFAULT_PEER_TLS_DIR}/server.crt"
DEFAULT_SERVER_KEY = f"{DEFAULT_PEER_TLS_DIR}/server.key"
DEFAULT_WRONG_NAME_CERT = f"{DEFAULT_PEER_TLS_DIR}/wrong-name.crt"
DEFAULT_WRONG_NAME_KEY = f"{DEFAULT_PEER_TLS_DIR}/wrong-name.key"
ACCEPT_POLL_SECONDS = 0.05
RECV_CHUNK = 8192
HEADER_TERMINATOR = b"\r\n\r\n"


@dataclass
class PeerLifecycle:
    peer_id: str
    route: FixturePeerRoute
    script: ExchangeScript
    bound: bool = False
    accepted: bool = False
    handshake_complete: bool = False
    request_received: bool = False
    response_sent: bool = False
    retired: bool = False
    joined: bool = False
    close_mode_observed: CloseMode | None = None
    phase_entered: str | None = None
    bytes_received: int = 0
    bytes_sent: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class PeerMaterial:
    """Server certificate material paths — generated only under later launch card."""

    cert_file: str = DEFAULT_SERVER_CERT
    key_file: str = DEFAULT_SERVER_KEY
    wrong_name_cert_file: str = DEFAULT_WRONG_NAME_CERT
    wrong_name_key_file: str = DEFAULT_WRONG_NAME_KEY


class PeerPreparationError(RuntimeError):
    pass


class PeerLifecycleError(RuntimeError):
    pass


class PeerRetirementUnknown(RuntimeError):
    """Unjoined/unconfirmed owned peer/reader retirement → UNKNOWN."""


def _build_server_context(*, cert_file: str, key_file: str) -> ssl.SSLContext:
    if not Path(cert_file).is_file() or not Path(key_file).is_file():
        raise PeerLifecycleError("server certificate material missing — generate under launch card only")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    return context


def _http_response_bytes(step: ExchangeStep) -> bytes:
    body = (step.body_template or "").encode("utf-8")
    headers = list(step.headers)
    has_cl = any(name.lower() == "content-length" for name, _ in headers)
    if not has_cl:
        headers.append(("Content-Length", str(len(body))))
    else:
        rewritten: list[tuple[str, str]] = []
        for name, value in headers:
            if name.lower() == "content-length" and value == "PLACEHOLDER":
                rewritten.append((name, str(len(body))))
            else:
                rewritten.append((name, value))
        headers = rewritten
    status = int(step.status or 200)
    lines = [f"HTTP/1.1 {status} OK"]
    for name, value in headers:
        lines.append(f"{name}: {value}")
    lines.append("Connection: close")
    lines.append("")
    head = ("\r\n".join(lines) + "\r\n").encode("ascii")
    # Short-CL scripts intentionally send fewer body bytes than Content-Length.
    declared = None
    for name, value in headers:
        if name.lower() == "content-length" and value.isdigit():
            declared = int(value)
            break
    if declared is not None and len(body) > declared:
        body = body[:declared]
    return head + body


def _parse_request_head(raw: bytes) -> tuple[str, str]:
    head, _, _ = raw.partition(HEADER_TERMINATOR)
    request_line = head.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
    parts = request_line.split(" ")
    if len(parts) < 2:
        raise PeerLifecycleError("malformed request line")
    return parts[0], parts[1]


class SyntheticProviderPeer:
    """Real synthetic HTTPS peer controller for later native run.

    Methods bind/accept/handshake/serve when invoked under launch authority.
    Preparation must not call serve_once / bind_listen.
    """

    def __init__(
        self,
        *,
        peer_id: str,
        route: FixturePeerRoute,
        script: ExchangeScript | None = None,
        connection_scripts: tuple[ExchangeScript, ...] | None = None,
        material: PeerMaterial | None = None,
        bind_host: str | None = None,
        bind_port: int | None = None,
    ):
        # Single-connection script OR finite Connection:close inventory.
        if connection_scripts is not None:
            scripts = tuple(connection_scripts)
            if not scripts:
                raise PeerPreparationError("connection_scripts empty")
            primary = scripts[0]
        elif script is not None:
            scripts = (script,)
            primary = script
        else:
            raise PeerPreparationError("script or connection_scripts required")
        self.life = PeerLifecycle(peer_id=peer_id, route=route, script=primary)
        self.connection_scripts = scripts
        self.material = material or PeerMaterial()
        self.bind_host = bind_host if bind_host is not None else route.dial_address
        self.bind_port = bind_port if bind_port is not None else route.dial_port
        self._listener: socket.socket | None = None
        self._client: socket.socket | None = None
        self._tls: ssl.SSLSocket | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._lock = threading.Lock()
        self._exchange_inventory: list[dict[str, Any]] = []

    def declare_bind_intent(self) -> dict[str, Any]:
        """Record intended bind: unchanged-isolation nonroot :443 first."""
        if self.life.route.dial_port != 443 and self.life.route.purpose != "tcp_refusal":
            raise PeerPreparationError("non-:443 peer requires separately labeled launch")
        return {
            "peer_id": self.life.peer_id,
            "bind_intent": "unchanged_isolation_nonroot_443",
            "dial_address": self.life.route.dial_address,
            "dial_port": self.life.route.dial_port,
            "bind_host": self.bind_host,
            "bind_port": self.bind_port,
            "server_hostname": self.life.route.server_hostname,
            "ca_path": self.life.route.ca_path,
            "verify_full": self.life.route.verify_full,
            "bound": self.life.bound,
            "execution_authorized": False,
        }

    def _select_cert_paths(self) -> tuple[str, str]:
        # Wrong-name: serve distinct wrong-name leaf; client hostname/SNI stays vendor.
        if getattr(self.life.route, "serve_wrong_name_leaf", False):
            return self.material.wrong_name_cert_file, self.material.wrong_name_key_file
        return self.material.cert_file, self.material.key_file

    def bind_listen(self) -> dict[str, Any]:
        """Bind numeric loopback and listen. Launch-card invocation only."""
        if self.life.route.purpose == "tcp_refusal":
            raise PeerLifecycleError("tcp_refusal peer must remain unbound")
        if self._listener is not None:
            raise PeerLifecycleError("listener already bound")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((self.bind_host, self.bind_port))
        except OSError as exc:
            listener.close()
            raise PeerLifecycleError("bind failed") from exc
        listener.listen(1)
        listener.settimeout(ACCEPT_POLL_SECONDS)
        self._listener = listener
        self.life.bound = True
        self.life.phase_entered = "bound"
        self.life.notes.append(f"bound:{self.bind_host}:{self.bind_port}")
        return {
            "peer_id": self.life.peer_id,
            "bound": True,
            "bind_host": self.bind_host,
            "bind_port": self.bind_port,
        }

    def _close_listener(self) -> None:
        sock = self._listener
        self._listener = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _close_client(self) -> None:
        tls = self._tls
        self._tls = None
        client = self._client
        self._client = None
        if tls is not None:
            try:
                tls.close()
            except OSError:
                pass
        elif client is not None:
            try:
                client.close()
            except OSError:
                pass

    def _accept_once(self, *, deadline: float, keep_listener: bool = False) -> socket.socket:
        if self._listener is None:
            raise PeerLifecycleError("listener not bound")
        while monotonic() < deadline:
            if self._stop.is_set():
                raise PeerLifecycleError("peer stopped before accept")
            try:
                client, _addr = self._listener.accept()
                self.life.accepted = True
                self.life.phase_entered = "accepted"
                if not keep_listener:
                    self._close_listener()
                return client
            except socket.timeout:
                continue
        raise PeerLifecycleError("accept deadline")

    def _handshake(self, client: socket.socket, *, deadline: float) -> ssl.SSLSocket:
        close_mode = self._script_close_mode()
        if close_mode == "stall_pre_handshake":
            self.life.phase_entered = "stall_pre_handshake"
            self.life.close_mode_observed = "stall_pre_handshake"
            # Hold the accepted TCP socket without TLS handshake until deadline.
            while monotonic() < deadline and not self._stop.is_set():
                select.select([client], [], [], ACCEPT_POLL_SECONDS)
            raise PeerLifecycleError("handshake stall held to deadline")
        cert_file, key_file = self._select_cert_paths()
        context = _build_server_context(cert_file=cert_file, key_file=key_file)
        client.settimeout(max(0.05, deadline - monotonic()))
        tls = context.wrap_socket(client, server_side=True, do_handshake_on_connect=False)
        self._tls = tls
        while True:
            if monotonic() >= deadline or self._stop.is_set():
                raise PeerLifecycleError("handshake deadline")
            try:
                tls.do_handshake()
                self.life.handshake_complete = True
                self.life.phase_entered = "handshake_complete"
                return tls
            except ssl.SSLWantReadError:
                select.select([tls], [], [], ACCEPT_POLL_SECONDS)
            except ssl.SSLWantWriteError:
                select.select([], [tls], [], ACCEPT_POLL_SECONDS)

    def _script_close_mode(self) -> CloseMode | None:
        for step in self.life.script.steps:
            if step.direction == "close" and step.close_mode is not None:
                return step.close_mode
        return None

    def _recv_request(self, tls: ssl.SSLSocket, *, deadline: float, step: ExchangeStep) -> bytes:
        self.life.phase_entered = "recv_request"
        buf = bytearray()
        while HEADER_TERMINATOR not in buf:
            if monotonic() >= deadline or self._stop.is_set():
                raise PeerLifecycleError("request header deadline")
            try:
                chunk = tls.recv(RECV_CHUNK)
            except ssl.SSLWantReadError:
                select.select([tls], [], [], ACCEPT_POLL_SECONDS)
                continue
            except ssl.SSLWantWriteError:
                select.select([], [tls], [], ACCEPT_POLL_SECONDS)
                continue
            if not chunk:
                break
            buf.extend(chunk)
            self.life.bytes_received += len(chunk)
        if HEADER_TERMINATOR not in buf:
            raise PeerLifecycleError("incomplete request headers")
        method, path = _parse_request_head(bytes(buf))
        # Exact request-target inventory proof: compare path before '?' only.
        # Broad startswith matching is not completion proof for the first vertical.
        request_path = path.split("?", 1)[0]
        if step.method is not None and method != step.method:
            raise PeerLifecycleError(f"method mismatch:{method}")
        if step.path is not None and request_path != step.path:
            raise PeerLifecycleError(f"path mismatch:{request_path}")
        # Drain any already-buffered body prefix; do not invent Content-Length proof here.
        self.life.request_received = True
        self.life.notes.append(f"exact_request:{method}:{request_path}")
        return bytes(buf)

    def _send_response(self, tls: ssl.SSLSocket, *, deadline: float, step: ExchangeStep) -> None:
        close_mode = self._script_close_mode()
        if close_mode == "stall_header":
            self.life.phase_entered = "stall_header"
            self.life.close_mode_observed = "stall_header"
            while monotonic() < deadline and not self._stop.is_set():
                select.select([], [], [], ACCEPT_POLL_SECONDS)
            raise PeerLifecycleError("header stall held to deadline")
        wire = _http_response_bytes(step)
        if close_mode == "stall_body":
            # Send status/headers only (through first CRLFCRLF), then stall.
            head, sep, _ = wire.partition(HEADER_TERMINATOR)
            partial = head + sep
            self._send_all(tls, partial, deadline=deadline)
            self.life.response_sent = True
            self.life.phase_entered = "stall_body"
            self.life.close_mode_observed = "stall_body"
            while monotonic() < deadline and not self._stop.is_set():
                select.select([], [], [], ACCEPT_POLL_SECONDS)
            raise PeerLifecycleError("body stall held to deadline")
        if close_mode == "partial_send_peer":
            # Peer-side truncated response — not proof of client JoinedTLS partial send.
            # Observation aid: peer prefix ≠ sender partial-completion proof.
            self.life.notes.append("partial_send_peer:prefix_only_not_client_partial_proof")
            wire = wire[: max(1, len(wire) // 2)]
        self._send_all(tls, wire, deadline=deadline)
        self.life.response_sent = True
        self.life.phase_entered = "response_sent"

    def _send_all(self, tls: ssl.SSLSocket, data: bytes, *, deadline: float) -> None:
        view = memoryview(data)
        while view:
            if monotonic() >= deadline or self._stop.is_set():
                raise PeerLifecycleError("response send deadline")
            try:
                sent = tls.send(view)
            except ssl.SSLWantWriteError:
                select.select([], [tls], [], ACCEPT_POLL_SECONDS)
                continue
            except ssl.SSLWantReadError:
                select.select([tls], [], [], ACCEPT_POLL_SECONDS)
                continue
            if sent <= 0:
                raise PeerLifecycleError("response send incomplete")
            self.life.bytes_sent += sent
            view = view[sent:]

    def _close_connection(self, tls: ssl.SSLSocket) -> None:
        mode = self._script_close_mode() or "normal"
        self.life.close_mode_observed = mode
        self.life.phase_entered = f"close:{mode}"
        if mode == "orderly_close_notify":
            # Orderly TLS close_notify via unwrap; distinct from abrupt stream drop.
            try:
                tls.unwrap()
            except ssl.SSLError:
                # Still mark attempted orderly path; abrupt fallback is separately scripted.
                self.life.notes.append("close_notify_unwrap_ssl_error")
            finally:
                try:
                    tls.close()
                except OSError:
                    pass
            self.life.notes.append("orderly_close_notify_attempted")
            return
        if mode == "abrupt_truncate":
            # Abrupt TCP/TLS drop without close_notify / unwrap exchange.
            try:
                import struct

                tls.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            except OSError:
                pass
            try:
                # Shutdown RDWR without unwrap = abrupt from peer perspective.
                tls.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                tls.close()
            except OSError:
                pass
            self.life.notes.append("abrupt_truncate_without_close_notify")
            return
        try:
            tls.close()
        except OSError:
            pass
        self.life.notes.append(f"close_mode:{mode}")

    def _run_one_connection(
        self,
        *,
        script: ExchangeScript,
        deadline: float,
        keep_listener: bool,
        connection_index: int,
    ) -> dict[str, Any]:
        self.life.script = script
        client = self._accept_once(deadline=deadline, keep_listener=keep_listener)
        self._client = client
        exchange: dict[str, Any] = {
            "connection_index": connection_index,
            "script_id": script.script_id,
            "purpose": script.purpose,
            "connection_close": True,
        }
        try:
            close_mode = None
            for step in script.steps:
                if step.direction == "close" and step.close_mode is not None:
                    close_mode = step.close_mode
                    break
            if close_mode == "stall_pre_handshake":
                self._handshake(client, deadline=deadline)
                exchange["phase"] = "stall_pre_handshake"
                return exchange
            tls = self._handshake(client, deadline=deadline)
            for step in script.steps:
                if step.direction == "recv_request":
                    self._recv_request(tls, deadline=deadline, step=step)
                    exchange["method"] = step.method
                    exchange["path"] = step.path
                elif step.direction == "send_response":
                    self._send_response(tls, deadline=deadline, step=step)
                elif step.direction == "close":
                    self._close_connection(tls)
                    self._tls = None
                    self._client = None
            exchange["handshake_complete"] = self.life.handshake_complete
            exchange["request_received"] = self.life.request_received
            exchange["response_sent"] = self.life.response_sent
            exchange["close_mode_observed"] = self.life.close_mode_observed
            return exchange
        finally:
            self._close_client()

    def execute_script(self, *, seconds: int) -> dict[str, Any]:
        """Accept finite Connection:close inventory and run each exchange. Launch-card only."""
        if type(seconds) is not int or not 1 <= seconds <= 240:
            raise PeerLifecycleError("explicit peer deadline required")
        deadline = monotonic() + seconds
        self._exchange_inventory = []
        multi = len(self.connection_scripts) > 1
        try:
            for index, script in enumerate(self.connection_scripts):
                keep = multi and index < len(self.connection_scripts) - 1
                row = self._run_one_connection(
                    script=script,
                    deadline=deadline,
                    keep_listener=keep,
                    connection_index=index,
                )
                self._exchange_inventory.append(row)
            return self.sanitized_state()
        finally:
            self._close_client()
            self._close_listener()

    def start_background(self, *, seconds: int) -> None:
        """Start owned peer worker thread. Launch-card invocation only."""
        if self._worker is not None:
            raise PeerLifecycleError("peer worker already started")
        self.bind_listen()
        self._ready.clear()
        self._stop.clear()
        self._error = None

        def _run() -> None:
            try:
                self._ready.set()
                self.execute_script(seconds=seconds)
            except BaseException as exc:
                self._error = exc
                self.life.notes.append(f"worker_error:{type(exc).__name__}")
            finally:
                self._close_client()
                self._close_listener()

        worker = threading.Thread(target=_run, name=f"np-peer-{self.life.peer_id}", daemon=True)
        self._worker = worker
        worker.start()
        # Wait briefly for bind readiness signal from worker path.
        if not self._ready.wait(timeout=2.0):
            raise PeerLifecycleError("peer worker ready signal missing")

    def retire_owned(self, *, join_seconds: float = 5.0) -> dict[str, Any]:
        """Bounded owned peer/reader retirement. Fault authority = later launch card.

        Close owned sockets BEFORE join so blocked SSL recv/handshake/unwrap and
        accept polls observe interruption within the join allowance. Unjoined
        remains honest UNKNOWN — never a fabricated PASS. One retirement path.
        """
        self._stop.set()
        self.life.retired = True
        # Interrupt blocked I/O first; then bounded join.
        self._close_client()
        self._close_listener()
        worker = self._worker
        joined = True
        if worker is not None:
            worker.join(timeout=join_seconds)
            if worker.is_alive():
                joined = False
                self.life.joined = False
                self.life.notes.append("unjoined_peer_worker_UNKNOWN")
                self._worker = None
                raise PeerRetirementUnknown("owned peer worker unjoined — UNKNOWN")
        self.life.joined = joined
        self._worker = None
        return {
            "peer_id": self.life.peer_id,
            "retirement_kind": "owned_peer_reader",
            "retired": True,
            "joined": joined,
            "unjoined_disposition": "UNKNOWN",
            "authority": "later_launch_card_only",
            "failed_container_shutdown": "separately_gated",
            "interruption": "stop_event_plus_owned_socket_close_before_join",
            "worker_error_kind": type(self._error).__name__ if self._error else None,
        }

    def declare_owned_retirement_intent(self) -> dict[str, Any]:
        return {
            "peer_id": self.life.peer_id,
            "retirement_kind": "owned_peer_reader",
            "authority": "later_launch_card_only",
            "failed_container_shutdown": "separately_gated",
            "unjoined_disposition": "UNKNOWN",
            "retired": self.life.retired,
            "joined": self.life.joined,
            "implementation": "retire_owned",
        }

    def mark_joined_retirement(self) -> None:
        if not self.life.retired:
            raise PeerPreparationError("retirement not declared")
        self.life.joined = True

    def sanitized_state(self) -> dict[str, Any]:
        return {
            "peer_id": self.life.peer_id,
            "purpose": self.life.route.purpose,
            "script_id": self.life.script.script_id,
            "connection_count_admitted": len(self.connection_scripts),
            "connection_count_served": len(self._exchange_inventory),
            "exchange_inventory": list(self._exchange_inventory),
            "serve_wrong_name_leaf": bool(
                getattr(self.life.route, "serve_wrong_name_leaf", False)
            ),
            "server_hostname": self.life.route.server_hostname,
            "ca_path": self.life.route.ca_path,
            "bound": self.life.bound,
            "accepted": self.life.accepted,
            "handshake_complete": self.life.handshake_complete,
            "request_received": self.life.request_received,
            "response_sent": self.life.response_sent,
            "phase_entered": self.life.phase_entered,
            "bytes_received": self.life.bytes_received,
            "bytes_sent": self.life.bytes_sent,
            "retired": self.life.retired,
            "joined": self.life.joined,
            "close_mode_observed": self.life.close_mode_observed,
            "notes": list(self.life.notes),
        }


def peer_for_script(
    *,
    peer_id: str,
    route: FixturePeerRoute,
    script: ExchangeScript,
    material: PeerMaterial | None = None,
) -> SyntheticProviderPeer:
    return SyntheticProviderPeer(peer_id=peer_id, route=route, script=script, material=material)


def serve_once(
    *,
    peer_id: str,
    route: FixturePeerRoute,
    script: ExchangeScript,
    seconds: int,
    material: PeerMaterial | None = None,
) -> dict[str, Any]:
    """Foreground one-shot peer serve. Launch-card invocation only."""
    peer = peer_for_script(peer_id=peer_id, route=route, script=script, material=material)
    peer.bind_listen()
    try:
        return peer.execute_script(seconds=seconds)
    finally:
        try:
            peer.retire_owned(join_seconds=1.0)
        except PeerRetirementUnknown:
            raise


if __name__ == "__main__":
    raise SystemExit(
        "HELD: np_provider_peer preparation only; "
        "socket/TLS lifecycle authored but bind/listen/serve not authorized under prep"
    )
