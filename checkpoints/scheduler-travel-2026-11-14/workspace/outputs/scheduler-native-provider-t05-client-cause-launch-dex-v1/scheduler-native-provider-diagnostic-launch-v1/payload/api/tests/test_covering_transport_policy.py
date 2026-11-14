"""Prepared transport policy cases. No real DNS, sockets, TLS or database."""
import pytest
from app.services.covering_transport_policy import (
    HTTPSPeer, ProviderCounter, ProviderLimits, CoveringTransportRefused,
    approved_provider_limits,
)


def test_request_limits_are_cumulative_across_targets():
    c=ProviderCounter(ProviderLimits(2,1,3,10),lambda:100)
    c.page("event"); c.batch([1,2]); c.body(4)
    c.page("event"); c.batch([3]); c.body(6)
    with pytest.raises(CoveringTransportRefused):
        c.page("event")
    assert c.stopped
    with pytest.raises(CoveringTransportRefused):
        c.page("identity")


def test_byte_overflow_is_rejected_before_buffer_growth():
    c=ProviderCounter(ProviderLimits(2,2,3,4),lambda:100)
    c.body(4)
    with pytest.raises(CoveringTransportRefused):
        c.body(1)
    assert c.bytes==4 and c.stopped


def test_item_overflow_does_not_admit_partial_batch():
    c=ProviderCounter(ProviderLimits(2,2,3,4),lambda:100)
    c.batch([1,2])
    with pytest.raises(CoveringTransportRefused):
        c.batch([3,4])
    assert c.items==2 and c.stopped


@pytest.mark.parametrize("url", [
    "http://graph.example.test/v1/events",
    "https://foreign.example.test/v1/events",
    "https://graph.example.test:444/v1/events",
    "https://user@graph.example.test/v1/events",
    "https://graph.example.test/v1/events#fragment",
])
def test_unapproved_origin_refused(url):
    peer=HTTPSPeer("graph.example.test","192.0.2.1",443,"synthetic-ca.pem")
    with pytest.raises(CoveringTransportRefused):
        peer.check_url(url)


def test_numeric_dial_address_required():
    with pytest.raises(ValueError):
        HTTPSPeer("graph.example.test","resolve-me.example.test",443,"synthetic-ca.pem")


def test_approved_limits_exact():
    assert approved_provider_limits()==ProviderLimits(20,10,10_000,16*1024*1024)


def test_provider_limit_preflight_needs_no_token_terminal():
    from types import SimpleNamespace
    from app.services.covering_domain_adapters import make_domain_ports
    transport=SimpleNamespace(counter=SimpleNamespace(admission_exhausted=True))
    ports=make_domain_ports(settings=None,transport=transport)
    result=ports.token(SimpleNamespace(info={}),object(),lambda:100)
    assert result.code=="CALENDAR_REFRESH_PROVIDER_LIMIT_EXCEEDED"

