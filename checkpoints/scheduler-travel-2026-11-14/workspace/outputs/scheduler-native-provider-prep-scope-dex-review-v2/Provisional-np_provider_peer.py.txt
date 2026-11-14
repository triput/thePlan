"""Synthetic HTTPS peer implementation for native-provider prep.

PREPARED ONLY. Declares peer lifecycle and close modes; does not bind sockets
or generate certificates under preparation approval.
Bounded owned peer/reader retirement may be implemented in source; invocation
and fault-retirement authority = later launch card only. Unjoined → UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from np_provider_routes import FixturePeerRoute
from np_provider_transcript import ExchangeScript, CloseMode


@dataclass
class PeerLifecycle:
    peer_id: str
    route: FixturePeerRoute
    script: ExchangeScript
    bound: bool = False
    accepted: bool = False
    handshake_complete: bool = False
    retired: bool = False
    joined: bool = False
    close_mode_observed: CloseMode | None = None
    notes: list[str] = field(default_factory=list)


class PeerPreparationError(RuntimeError):
    pass


class SyntheticProviderPeer:
    """In-process synthetic peer controller — preparation scaffold.

    Launch card must authorize bind/listen/PKI. Preparation does not open ports.
    """

    def __init__(self, *, peer_id: str, route: FixturePeerRoute, script: ExchangeScript):
        self.life = PeerLifecycle(peer_id=peer_id, route=route, script=script)

    def declare_bind_intent(self) -> dict[str, Any]:
        """Record intended bind: unchanged-isolation nonroot :443 first."""
        if self.life.route.dial_port != 443 and self.life.route.purpose != "tcp_refusal":
            raise PeerPreparationError("non-:443 peer requires separately labeled launch")
        return {
            "peer_id": self.life.peer_id,
            "bind_intent": "unchanged_isolation_nonroot_443",
            "dial_address": self.life.route.dial_address,
            "dial_port": self.life.route.dial_port,
            "server_hostname": self.life.route.server_hostname,
            "ca_path": self.life.route.ca_path,
            "verify_full": self.life.route.verify_full,
            "bound": False,
            "execution_authorized": False,
        }

    def declare_close_mode(self, mode: CloseMode) -> None:
        self.life.close_mode_observed = mode
        self.life.notes.append(f"close_mode_declared:{mode}")

    def declare_owned_retirement_intent(self) -> dict[str, Any]:
        """Bounded owned peer/reader retirement — authority later launch card only."""
        return {
            "peer_id": self.life.peer_id,
            "retirement_kind": "owned_peer_reader",
            "authority": "later_launch_card_only",
            "failed_container_shutdown": "separately_gated",
            "unjoined_disposition": "UNKNOWN",
            "retired": self.life.retired,
            "joined": self.life.joined,
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
            "bound": self.life.bound,
            "accepted": self.life.accepted,
            "handshake_complete": self.life.handshake_complete,
            "retired": self.life.retired,
            "joined": self.life.joined,
            "close_mode_observed": self.life.close_mode_observed,
            "notes": list(self.life.notes),
        }


def peer_for_script(*, peer_id: str, route: FixturePeerRoute, script: ExchangeScript) -> SyntheticProviderPeer:
    return SyntheticProviderPeer(peer_id=peer_id, route=route, script=script)


if __name__ == "__main__":
    raise SystemExit("HELD: np_provider_peer preparation only; no bind/listen/TLS")
