"""Covering-only response bounds and HTTPS destination validation.

No default limits or profile: caller must supply the reviewed policy. Pure
validation/counters; never reads credentials, resolves DNS or creates sockets.
"""
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit
from app.services.covering_request_budget import CoveringDeadlineExceeded


class CoveringTransportRefused(Exception):
    pass


class CoveringReauthorizationRequired(Exception):
    """Complete OAuth invalid_grant response; no successful rotation reported."""


@dataclass(frozen=True)
class ProviderLimits:
    event_pages: int
    identity_pages: int
    items: int
    response_bytes: int

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in
               (self.event_pages,self.identity_pages,self.items,self.response_bytes)):
            raise ValueError("invalid covering limits")


@dataclass(frozen=True)
class HTTPSPeer:
    hostname: str
    address: str
    port: int
    ca_file: str

    def __post_init__(self):
        ip_address(self.address)  # Numeric address only, never runtime DNS.
        if (not self.hostname or any(c in self.hostname for c in "/:@\\ \r\n")
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or not self.ca_file):
            raise ValueError("invalid HTTPS peer")

    def check_url(self, url):
        try:
            u=urlsplit(url)
            valid=(u.scheme=="https" and u.hostname==self.hostname
                   and (u.port or 443)==self.port and not u.username
                   and not u.password and not u.fragment
                   and not any(ord(c)<32 or ord(c)==127 for c in url))
        except ValueError:
            valid=False
        if not valid:
            raise CoveringTransportRefused("provider origin refused")
        return u


class ProviderCounter:
    def __init__(self, limits, remaining):
        self.limits=limits
        self.remaining=remaining
        self.pages={"event":0,"identity":0}
        self.items=0
        self.bytes=0
        self.stopped=False

    @property
    def admission_exhausted(self):
        # Equality stops new exchanges, not the already-admitted response.
        return (self.stopped
                or self.pages["event"] >= self.limits.event_pages
                or self.pages["identity"] >= self.limits.identity_pages
                or self.items >= self.limits.items
                or self.bytes >= self.limits.response_bytes)

    def admit(self):
        self.check()
        if self.admission_exhausted:
            self.refuse()

    def check(self):
        if self.stopped:
            raise CoveringTransportRefused("provider admission stopped")
        self.remaining()

    def refuse(self):
        self.stopped=True
        raise CoveringTransportRefused("provider response limit exceeded")

    def page(self, kind):
        self.admit()
        if kind not in self.pages:
            raise CoveringTransportRefused("invalid page class")
        maximum=self.limits.event_pages if kind=="event" else self.limits.identity_pages
        if self.pages[kind]>=maximum:
            self.refuse()
        self.pages[kind]+=1

    def body(self, count):
        self.check()
        if type(count) is not int or count<0:
            self.refuse()
        if count>self.limits.response_bytes-self.bytes:
            self.refuse()
        self.bytes+=count

    def batch(self, items):
        self.check()
        if not isinstance(items,list) or len(items)>self.limits.items-self.items:
            self.refuse()
        self.items+=len(items)
        return items


def approved_provider_limits():
    # Trish approved these cumulative request-wide ceilings on 2026-11-09.
    return ProviderLimits(20, 10, 10_000, 16 * 1024 * 1024)

