"""Finite exchange scripts for synthetic provider peer.

PREPARED ONLY. Host/path/method scripts — no live sockets in preparation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from np_auth_seed import (
    FIXTURE_MS_TENANT,
    MS_REFRESH_EXPIRES_IN_SECONDS,
    REFRESHED_MS_ACCESS_PLAINTEXT,
    ROTATED_MS_REFRESH_PLAINTEXT,
)


def ms_token_endpoint_path(tenant: str = FIXTURE_MS_TENANT) -> str:
    """Path of production microsoft_calendar._token_url for an already-normalized tenant.

    Production builds https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
    after _normalize_tenant. This fixture derives the path ONCE from the fixture
    tenant; the runner cross-checks it against the actual pinned production
    builder before any request. Refuse anything production would rewrite.
    """
    if (
        not isinstance(tenant, str)
        or not tenant
        or tenant != tenant.strip().strip("/")
        or not all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in tenant)
    ):
        raise ValueError("tenant must already be a normalized [A-Za-z0-9-] label")
    return f"/{tenant}/oauth2/v2.0/token"


MS_TOKEN_ENDPOINT_PATH = ms_token_endpoint_path()


CloseMode = Literal[
    "orderly_close_notify",
    "abrupt_truncate",
    "stall_pre_handshake",
    "stall_header",
    "stall_body",
    "partial_send_peer",
    "normal",
]

# Explicit response framing selection for the fixture serializer.
# "auto" (default) keeps the historical serializer exactly: Content-Length is
# appended when absent and a "PLACEHOLDER" value is rewritten. "close_delimited"
# sends neither Content-Length nor Transfer-Encoding; the body ends at connection
# close. Unknown modes and inconsistent header sets are refused before sending.
ResponseFraming = Literal["auto", "close_delimited"]


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
    framing: ResponseFraming = "auto"


@dataclass(frozen=True)
class ExchangeScript:
    script_id: str
    purpose: str
    steps: tuple[ExchangeStep, ...]


def ms_token_success_script() -> ExchangeScript:
    """Synthetic MS refresh success at the production-derived tenant path.

    Body carries the declared synthetic refreshed access + rotated refresh values
    (np_auth_seed) so the fixture can prove semantic persistence by decrypting the
    stored row. The peer sends body_template verbatim; it is never logged raw.
    """
    body = json.dumps(
        {
            "token_type": "Bearer",
            "expires_in": MS_REFRESH_EXPIRES_IN_SECONDS,
            "access_token": REFRESHED_MS_ACCESS_PLAINTEXT,
            "refresh_token": ROTATED_MS_REFRESH_PLAINTEXT,
        },
        separators=(",", ":"),
    )
    return ExchangeScript(
        script_id="MS-TOKEN-SUCCESS",
        purpose="microsoft_token_refresh_success",
        steps=(
            ExchangeStep("recv_request", method="POST", path=MS_TOKEN_ENDPOINT_PATH),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
                body_template=body,
                note="Declared synthetic refresh values; peer sends verbatim; never logged raw",
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def ms_token_invalid_grant_script() -> ExchangeScript:
    """Complete status-400 OAuth error object at the production-derived tenant path.

    The path must equal production microsoft_calendar._token_url for the fixture
    tenant (the peer enforces exact path equality); a tenant-less path would be
    refused by the peer as a transcript mismatch, not reach invalid_grant.
    """
    return ExchangeScript(
        script_id="MS-TOKEN-INVALID-GRANT",
        purpose="microsoft_token_invalid_grant",
        steps=(
            ExchangeStep("recv_request", method="POST", path=MS_TOKEN_ENDPOINT_PATH),
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
    """Observation (a): complete close-delimited accepted after orderly close_notify.

    No Content-Length and no Transfer-Encoding: the body is delimited only by the
    peer's orderly TLS close (close_notify), so the client must read to EOF.
    """
    return ExchangeScript(
        script_id="T05-ORDERLY-CLOSE-DELIMITED-COMPLETE",
        purpose="orderly_close_delimited_complete_accepted",
        steps=(
            ExchangeStep("recv_request", method="GET", path="/calendar/v3/calendars/primary/events"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"),),
                body_template="{}",
                note="Close-delimited: no Content-Length/Transfer-Encoding; complete body ends at orderly close",
                framing="close_delimited",
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def orderly_fixed_length_complete_script() -> ExchangeScript:
    """Observation (c): complete exact fixed-length accepted after orderly close_notify.

    Content-Length equals the exact body length (2 for "{}") and no Transfer-Encoding;
    the complete body precedes the peer's orderly TLS close (close_notify).
    """
    return ExchangeScript(
        script_id="T05-ORDERLY-FIXED-LENGTH-COMPLETE",
        purpose="orderly_fixed_length_complete_accepted",
        steps=(
            ExchangeStep("recv_request", method="GET", path="/calendar/v3/calendars/primary/events"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "2")),
                body_template="{}",
                note="Exact fixed length: Content-Length 2 equals the complete body; no Transfer-Encoding",
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


def ms_graph_identity_default_script() -> ExchangeScript:
    """GET /v1.0/me/calendar — identity purpose (not event)."""
    return ExchangeScript(
        script_id="MS-GRAPH-IDENTITY-DEFAULT",
        purpose="identity",
        steps=(
            ExchangeStep("recv_request", method="GET", path="/v1.0/me/calendar"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
                body_template='{"id":"cal-ms-default","name":"Calendar","isDefaultCalendar":true}',
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def ms_graph_identity_list_script(*, calendar_ids: tuple[str, ...] | list[str]) -> ExchangeScript:
    """GET /v1.0/me/calendars — identity purpose list."""
    entries = []
    for index, calendar_id in enumerate(calendar_ids):
        is_default = "true" if index == 0 else "false"
        entries.append(
            f'{{"id":"{calendar_id}","name":"Cal-{index}","isDefaultCalendar":{is_default},'
            f'"canEdit":true,"canShare":true,"canViewPrivateItems":true}}'
        )
    body = '{"value":[' + ",".join(entries) + "]}"
    return ExchangeScript(
        script_id="MS-GRAPH-IDENTITY-LIST",
        purpose="identity",
        steps=(
            ExchangeStep("recv_request", method="GET", path="/v1.0/me/calendars"),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
                body_template=body,
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def ms_graph_calendar_view_empty_script(*, calendar_id: str) -> ExchangeScript:
    """GET /v1.0/me/calendars/{id}/calendarView — event purpose empty page."""
    path = f"/v1.0/me/calendars/{calendar_id}/calendarView"
    return ExchangeScript(
        script_id=f"MS-GRAPH-CALENDARVIEW-EMPTY:{calendar_id}",
        purpose="event",
        steps=(
            ExchangeStep("recv_request", method="GET", path=path),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
                body_template='{"value":[]}',
                note="Empty calendarView; nonexpired vertical must not hit token endpoint",
            ),
            ExchangeStep("close", close_mode="orderly_close_notify"),
        ),
    )


def ms_graph_events_empty_script() -> ExchangeScript:
    """Legacy single-path helper retained; prefer ms_nonexpired_connection_inventory."""
    return ms_graph_calendar_view_empty_script(calendar_id="primary")


def ms_nonexpired_connection_inventory(
    *,
    calendar_ids: tuple[str, ...] | list[str],
    wire_calendar_ids: tuple[str, ...] | list[str] | None = None,
    identity_list_calendar_ids: tuple[str, ...] | list[str] | None = None,
) -> tuple[ExchangeScript, ...]:
    """Finite per-connection inventory for NP-V-MS-NONEXPIRED.

    Production CoveringHTTP/JoinedTLS opens Connection:close per exchange.
    Alias-Subset-Safe-Seed sequence: identity default, identity list
    (cal-ms-default default + cal-np-other nondefault), calendarView for
    cal-ms-default, calendarView for cal-np-other. After first requested-row
    rewrite no primary alias remains → no second identity fetch.
    Wire order must come from planted subscription→calendar mapping + production
    target sort — not inverted insertion order. No OAuth/token on nonexpired path.
    Steps tuples are fully delimited (no premature close).
    """
    ids = tuple(calendar_ids)
    if not ids:
        raise RuntimeError("calendar_ids required for MS nonexpired inventory")
    list_ids = tuple(identity_list_calendar_ids) if identity_list_calendar_ids is not None else ids
    view_ids = tuple(wire_calendar_ids) if wire_calendar_ids is not None else ids
    if not view_ids:
        raise RuntimeError("wire_calendar_ids required for MS nonexpired inventory")
    views = tuple(ms_graph_calendar_view_empty_script(calendar_id=cid) for cid in view_ids)
    return (
        ms_graph_identity_default_script(),
        ms_graph_identity_list_script(calendar_ids=list_ids),
    ) + views


T04_BODY_STALL_EXCHANGE_COUNT = 3
T04_BODY_STALL_BODY_TEMPLATE = '{"value":[]}'


def ms_graph_calendar_view_body_stall_script(*, calendar_id: str, exact_query: str) -> ExchangeScript:
    """GET /v1.0/me/calendars/{id}/calendarView?{exact_query} — headers only, then body stall.

    The declared request-target carries the exact seed-derived wire query, so the
    peer refuses any other query bytes. The response head declares a positive
    Content-Length (len of the empty-page template); the body is withheld and the
    stall ends only on the owning runner's stop (decision 4F2F3B3F) — a peer
    deadline remains an error.
    """
    if not exact_query or "?" in exact_query or "#" in exact_query:
        raise RuntimeError("body-stall script requires one exact non-empty wire query")
    path = f"/v1.0/me/calendars/{calendar_id}/calendarView?{exact_query}"
    return ExchangeScript(
        script_id=f"T04-BODY-STALL:MS-GRAPH-CALENDARVIEW:{calendar_id}",
        purpose="event",
        steps=(
            ExchangeStep("recv_request", method="GET", path=path),
            ExchangeStep(
                "send_response",
                status=200,
                headers=(("Content-Type", "application/json"), ("Content-Length", "PLACEHOLDER")),
                body_template=T04_BODY_STALL_BODY_TEMPLATE,
                note="Headers with positive Content-Length only; body withheld (stall_body)",
            ),
            ExchangeStep("close", close_mode="stall_body"),
        ),
    )


def ms_body_stall_connection_inventory(
    *,
    identity_list_calendar_ids: tuple[str, ...] | list[str],
    stall_calendar_id: str,
    exact_query: str,
) -> tuple[ExchangeScript, ...]:
    """Finite inventory for NP-T04-BODY-STALL: exactly three Connection:close exchanges.

    The two unchanged NONEXPIRED identity scripts, then the first event GET
    (calendarView for the first wire calendar) as a body stall. No fourth
    connection is scripted: the second target must be refused by the production
    work deadline before any provider admission.
    """
    list_ids = tuple(identity_list_calendar_ids)
    if len(list_ids) != 2:
        raise RuntimeError("body-stall inventory requires the two-calendar identity list")
    scripts = (
        ms_graph_identity_default_script(),
        ms_graph_identity_list_script(calendar_ids=list_ids),
        ms_graph_calendar_view_body_stall_script(calendar_id=stall_calendar_id, exact_query=exact_query),
    )
    if len(scripts) != T04_BODY_STALL_EXCHANGE_COUNT:
        raise RuntimeError("body-stall inventory must contain exactly three exchanges")
    return scripts


MS_REFRESH_EXCHANGE_COUNT = 5


def ms_refresh_connection_inventory(
    *,
    identity_list_calendar_ids: tuple[str, ...] | list[str],
    wire_calendar_ids: tuple[str, ...] | list[str],
) -> tuple[ExchangeScript, ...]:
    """Finite per-connection inventory for NP-V-MS-REFRESH (two subscriptions, one account).

    Exact production order: one OAuth refresh POST for the first str-sorted target
    (TOKEN COMMIT), then default identity, identity list, calendarView for each
    wire calendar. The second target re-reads the committed token (TOKEN ROLLBACK)
    and makes NO second OAuth request. Exactly five Connection:close exchanges.
    Reuses the unchanged NONEXPIRED Graph scripts after the token exchange.
    """
    list_ids = tuple(identity_list_calendar_ids)
    view_ids = tuple(wire_calendar_ids)
    if len(view_ids) != 2 or len(list_ids) != 2:
        raise RuntimeError("MS refresh inventory requires exactly two calendars")
    scripts = (ms_token_success_script(),) + ms_nonexpired_connection_inventory(
        calendar_ids=view_ids,
        identity_list_calendar_ids=list_ids,
        wire_calendar_ids=view_ids,
    )
    if len(scripts) != MS_REFRESH_EXCHANGE_COUNT:
        raise RuntimeError("MS refresh inventory must contain exactly five exchanges")
    return scripts


MS_INVALID_GRANT_EXCHANGE_COUNT = 1


def ms_invalid_grant_connection_inventory() -> tuple[ExchangeScript, ...]:
    """Finite per-connection inventory for NP-V-MS-INVALID (one subscription, one account).

    Exactly one OAuth refresh POST at the production-derived tenant path answered by
    a complete status-400 invalid_grant object, then orderly close. The token unit
    rolls back, the target is preflight-rejected, and no Graph request follows.
    """
    scripts = (ms_token_invalid_grant_script(),)
    if len(scripts) != MS_INVALID_GRANT_EXCHANGE_COUNT:
        raise RuntimeError("MS invalid_grant inventory must contain exactly one exchange")
    return scripts


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
        orderly_fixed_length_complete_script(),
        orderly_short_cl_valid_json_refuse_script(),
        abrupt_truncation_script(),
        *stall_scripts(),
        *oauth_ack_fault_scripts(),
    )


if __name__ == "__main__":
    raise SystemExit("HELD: np_provider_transcript preparation only; no exchange")
