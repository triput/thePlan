"""Fixture HTTPSPeer routes/trust only for native-provider prep.

PREPARED ONLY. Vendor host/port unchanged; numeric loopback dial; provider CA
under runner tmpfs /tmp/np-provider-tls — SEPARATE from DB /public-ca.
No DNS/public contact. No production route mutation.

Wrong-name stimulus: keep vendor URL/HTTPSPeer.hostname/SNI/check_hostname;
serve the distinct wrong-name leaf (serve_wrong_name_leaf=True). Do NOT rewrite
client server_hostname to wrong-name.fixture.invalid.
"""
from __future__ import annotations

from dataclasses import dataclass


# Vendor origins unchanged (URL host/port). Dial is numeric loopback inside isolation.
MS_GRAPH_HOST = "graph.microsoft.com"
MS_TOKEN_HOST = "login.microsoftonline.com"
GOOGLE_API_HOST = "www.googleapis.com"
GOOGLE_TOKEN_HOST = "oauth2.googleapis.com"

VENDOR_PORT = 443
LOOPBACK_DIAL = "127.0.0.1"

# Provider trust material — runner-owned private tmpfs. Never the DB /public-ca mount.
PROVIDER_TLS_DIR = "/tmp/np-provider-tls"
FIXTURE_CA_PATH = f"{PROVIDER_TLS_DIR}/ca.crt"
WRONG_CA_PATH = f"{PROVIDER_TLS_DIR}/wrong-ca.crt"
# DB public CA remains distinct (immutable DockerOps /public-ca/ca.crt).
DB_PUBLIC_CA_PATH = "/public-ca/ca.crt"


@dataclass(frozen=True)
class FixturePeerRoute:
    purpose: str
    url_host: str
    url_port: int
    dial_address: str
    dial_port: int
    server_hostname: str
    ca_path: str
    verify_full: bool = True
    # Server-served leaf selection only. Client hostname/SNI stays server_hostname.
    serve_wrong_name_leaf: bool = False


def microsoft_graph_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    # Client hostname always vendor origin — wrong-name changes the SERVER leaf only.
    return FixturePeerRoute(
        purpose="microsoft_graph",
        url_host=MS_GRAPH_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=MS_GRAPH_HOST,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
        serve_wrong_name_leaf=bool(wrong_name),
    )


def microsoft_token_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    return FixturePeerRoute(
        purpose="microsoft_token",
        url_host=MS_TOKEN_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=MS_TOKEN_HOST,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
        serve_wrong_name_leaf=bool(wrong_name),
    )


def google_api_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    return FixturePeerRoute(
        purpose="google_api",
        url_host=GOOGLE_API_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=GOOGLE_API_HOST,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
        serve_wrong_name_leaf=bool(wrong_name),
    )


def google_token_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    return FixturePeerRoute(
        purpose="google_token",
        url_host=GOOGLE_TOKEN_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=GOOGLE_TOKEN_HOST,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
        serve_wrong_name_leaf=bool(wrong_name),
    )


def tcp_refusal_route() -> FixturePeerRoute:
    """Numeric dial to a closed loopback port — typed connect failure stimulus."""
    return FixturePeerRoute(
        purpose="tcp_refusal",
        url_host=MS_GRAPH_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=9,  # closed discard; actual closed port chosen at launch card
        server_hostname=MS_GRAPH_HOST,
        ca_path=FIXTURE_CA_PATH,
        verify_full=True,
        serve_wrong_name_leaf=False,
    )


def reviewed_route_table() -> tuple[FixturePeerRoute, ...]:
    return (
        microsoft_graph_route(),
        microsoft_token_route(),
        google_api_route(),
        google_token_route(),
    )


if __name__ == "__main__":
    raise SystemExit("HELD: np_provider_routes preparation only; no dial or DNS")
