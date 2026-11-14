"""Fixture HTTPSPeer routes/trust only for native-provider prep.

PREPARED ONLY. Vendor host/port unchanged; numeric loopback dial; fixture CA.
No DNS/public contact. No production route mutation.
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
FIXTURE_CA_PATH = "/public-ca/ca.crt"
WRONG_CA_PATH = "/public-ca/wrong-ca.crt"


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


def microsoft_graph_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    hostname = "wrong-name.fixture.invalid" if wrong_name else MS_GRAPH_HOST
    return FixturePeerRoute(
        purpose="microsoft_graph",
        url_host=MS_GRAPH_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=hostname,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
    )


def microsoft_token_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    hostname = "wrong-name.fixture.invalid" if wrong_name else MS_TOKEN_HOST
    return FixturePeerRoute(
        purpose="microsoft_token",
        url_host=MS_TOKEN_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=hostname,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
    )


def google_api_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    hostname = "wrong-name.fixture.invalid" if wrong_name else GOOGLE_API_HOST
    return FixturePeerRoute(
        purpose="google_api",
        url_host=GOOGLE_API_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=hostname,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
    )


def google_token_route(*, wrong_ca: bool = False, wrong_name: bool = False) -> FixturePeerRoute:
    hostname = "wrong-name.fixture.invalid" if wrong_name else GOOGLE_TOKEN_HOST
    return FixturePeerRoute(
        purpose="google_token",
        url_host=GOOGLE_TOKEN_HOST,
        url_port=VENDOR_PORT,
        dial_address=LOOPBACK_DIAL,
        dial_port=VENDOR_PORT,
        server_hostname=hostname,
        ca_path=WRONG_CA_PATH if wrong_ca else FIXTURE_CA_PATH,
        verify_full=True,
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
