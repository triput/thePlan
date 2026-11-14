"""Finite exchange scripts for synthetic provider peer.

PREPARED ONLY. Host/path/method scripts — no live sockets in preparation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CloseMode = Literal[
    "orderly_close_notify",
    "abrupt_truncate",
    "stall_pre_handshake",
    "stall_header",
    "stall_body",
    "partial_send_peer",
    "normal",
]


@dataclass(frozen=True)
class ExchangeStep:
    direction: Literal["recv_request", "send_response", "close"]
    method: str | None = None
    path: str | None = None
    status: int | None = None
    headers: tuple[tuple[str, str], ...] = ()
    body_template: str | None = None
    close_mode: CloseMode | None = None
    note: str = ""


@dataclass(frozen=True)
class ExchangeScript:
    script_id: str
    purpose: str
    steps: tuple[ExchangeStep, ...]


def ms_token_success_script() -> ExchangeScript:
    return ExchangeScript(
        script_id="MS-TOKEN-SUCCESS",
        purpose="microsoft_token_refresh_success",
        steps=(
            ExchangeStep("recv_request", method="POST", path="/oauth2/v2.0/token"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
                body_template='{"token_type":"Bearer","expires_in":3600,"access_token":"fixture","refresh_token":"fixture"}',
                note="Body substituted at launch; never logged raw",
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def ms_token_invalid_grant_script() -> ExchangeScript:
    return ExchangeScript(
        script_id="MS-TOKEN-INVALID-GRANT",
        purpose="microsoft_token_invalid_grant",
        steps=(
            ExchangeStep("recv_request", method="POST", path="/oauth2/v2.0/token"),
            ExchangeStep(
                "send_response",
                status=400,
                headers=(("Content-Type", "application/json"),),
                body_template='{"error":"invalid_grant"}',
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def google_token_success_script() -> ExchangeScript:
    return ExchangeScript(
        script_id="GOOGLE-TOKEN-SUCCESS",
        purpose="google_token_refresh_success",
        steps=(
            ExchangeStep("recv_request", method="POST", path="/token"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"),),
                body_template='{"token_type":"Bearer","expires_in":3600,"access_token":"fixture","refresh_token":"fixture"}',
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def google_token_invalid_grant_script() -> ExchangeScript:
    return ExchangeScript(
        script_id="GOOGLE-TOKEN-INVALID-GRANT",
        purpose="google_token_invalid_grant",
        steps=(
            ExchangeStep("recv_request", method="POST", path="/token"),
            ExchangeStep(
                "send_response",
                status=400,
                headers=(("Content-Type", "application/json"),),
                body_template='{"error":"invalid_grant"}',
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def orderly_close_delimited_complete_script() -> ExchangeScript:
    """Observation (a): complete close-delimited accepted after orderly close_notify."""
    return ExchangeScript(
        script_id="T05-ORDERLY-CLOSE-DELIMITED-COMPLETE",
        purpose="orderly_close_delimited_complete_accepted",
        steps=(
            ExchangeStep("recv_request", method="GET", path="/calendar/v3/calendars/primary/events"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "2")),
                body_template="{}",
                note="Exact Content-Length match; complete body",
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def orderly_short_cl_valid_json_refuse_script() -> ExchangeScript:
    """Observation (b): valid-JSON prefix shorter than Content-Length refused after orderly close_notify."""
    return ExchangeScript(
        script_id="T05-ORDERLY-SHORT-CL-VALID-JSON",
        purpose="orderly_short_cl_valid_json_prefix_refused",
        steps=(
            ExchangeStep("recv_request", method="GET", path="/calendar/v3/calendars/primary/events"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "20")),
                body_template="{}",
                note="Valid JSON prefix shorter than declared Content-Length",
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def ms_graph_events_empty_script() -> ExchangeScript:
    """Graph events empty body for NP-V-MS-NONEXPIRED (no OAuth exchange)."""
    return ExchangeScript(
        script_id="MS-GRAPH-EVENTS-EMPTY",
        purpose="microsoft_graph_events_empty",
        steps=(
            ExchangeStep(
                "recv_request",
                method="GET",
                path="/v1.0/me/calendar/events",
            ),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
                body_template='{"value":[]}',
                note="Empty event page; nonexpired vertical must not hit token endpoint",
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def abrupt_truncation_script() -> ExchangeScript:
    return ExchangeScript(
        script_id="T05-ABRUPT-TRUNCATION",
        purpose="abrupt_tls_truncate_without_close_notify",
        steps=(
            ExchangeStep("recv_request", method="GET", path="/calendar/v3/calendars/primary/events"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "20")),
                body_template="{",
            ),
            ExchangeStep("close", close_mode="abrupt_truncate"),
        ),
    )


def stall_scripts() -> tuple[ExchangeScript, ...]:
    return (
        ExchangeScript(
            "T03-HANDSHAKE-STALL",
            "stall_pre_handshake",
            (ExchangeStep("close", close_mode="stall_pre_handshake"),),
        ),
        ExchangeScript(
            "T04-HEADER-STALL",
            "stall_header",
            (
                ExchangeStep("recv_request", method="GET", path="/"),
                ExchangeStep("close", close_mode="stall_header"),
            ),
        ),
        ExchangeScript(
            "T04-BODY-STALL",
            "stall_body",
            (
                ExchangeStep("recv_request", method="GET", path="/"),
                ExchangeStep(
                    "send_response",
                    status=200,
                    headers=(("Content-Type", "application/json"), ("Content-Length", "100")),
                    body_template="{",
                ),
                ExchangeStep("close", close_mode="stall_body"),
            ),
        ),
    )


def oauth_ack_fault_scripts() -> tuple[ExchangeScript, ...]:
    return (
        ExchangeScript(
            "T06-MALFORMED-ACK",
            "malformed_oauth_ack",
            (
                ExchangeStep("recv_request", method="POST", path="/token"),
                ExchangeStep(
                    "send_response",
                    status=200,
                    headers=(("Content-Type", "application/json"),),
                    body_template="{not-json",
                ),
                ExchangeStep("close", close_mode="orderly_close_notify"),
            ),
        ),
        ExchangeScript(
            "T06-TRUNCATED-ACK",
            "truncated_oauth_ack",
            (
                ExchangeStep("recv_request", method="POST", path="/token"),
                ExchangeStep(
                    "send_response",
                    status=200,
                    headers=(("Content-Type", "application/json"), ("Content-Length", "80")),
                    body_template='{"access_token":"',
                ),
                ExchangeStep("close", close_mode="orderly_close_notify"),
            ),
        ),
        ExchangeScript(
            "T06-OTHER-ERROR",
            "other_oauth_error",
            (
                ExchangeStep("recv_request", method="POST", path="/token"),
                ExchangeStep(
                    "send_response",
                    status=400,
                    headers=(("Content-Type", "application/json"),),
                    body_template='{"error":"temporarily_unavailable"}',
                ),
                ExchangeStep("close", close_mode="orderly_close_notify"),
            ),
        ),
    )


def finite_script_catalog() -> tuple[ExchangeScript, ...]:
    return (
        ms_token_success_script(),
        ms_token_invalid_grant_script(),
        google_token_success_script(),
        google_token_invalid_grant_script(),
        ms_graph_events_empty_script(),
        orderly_close_delimited_complete_script(),
        orderly_short_cl_valid_json_refuse_script(),
        abrupt_truncation_script(),
        *stall_scripts(),
        *oauth_ack_fault_scripts(),
    )


if __name__ == "__main__":
    raise SystemExit("HELD: np_provider_transcript preparation only; no exchange")
