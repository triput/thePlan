"""Joined nonblocking HTTPS byte transport. Prepared; never installed.

One approved numeric peer, verified TLS hostname, no DNS/proxy/redirect/retry.
Higher HTTP framing adapter must charge every response body through its counter.
"""
import errno
import ipaddress
import selectors
import socket
import ssl
from threading import get_ident

from app.services.covering_transport_policy import CoveringTransportRefused
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown


class JoinedTLS:
    def __init__(self, peer, remaining):
        self.peer=peer
        self.remaining=remaining
        self.owner=get_ident()
        self.sock=None
        self.closed=False
        self.sent=False

    def check(self):
        if get_ident()!=self.owner or self.closed:
            raise CoveringTransportRefused("transport ownership refused")
        return self.remaining()

    def ready(self, mask):
        with selectors.DefaultSelector() as poll:
            poll.register(self.sock,mask)
            while True:
                events=poll.select(min(self.check(),0.05))
                if events:
                    self.check()
                    return

    def open(self):
        if self.sock is not None:
            raise CoveringTransportRefused("connection reuse refused")
        self.check()
        family=socket.AF_INET6 if ipaddress.ip_address(self.peer.address).version==6 else socket.AF_INET
        self.sock=socket.socket(family,socket.SOCK_STREAM)
        self.sock.setblocking(False)
        try:
            address=(self.peer.address,self.peer.port)
            error=self.sock.connect_ex(address)
            if error not in (0,errno.EINPROGRESS,errno.EWOULDBLOCK,errno.EALREADY,
                             10035,10036,10037):
                raise CoveringTransportRefused("connect refused")
            if error:
                self.ready(selectors.EVENT_WRITE)
                if self.sock.getsockopt(socket.SOL_SOCKET,socket.SO_ERROR):
                    raise CoveringTransportRefused("connect refused")
            self.check()
            context=ssl.create_default_context(cafile=self.peer.ca_file)
            context.check_hostname=True
            context.verify_mode=ssl.CERT_REQUIRED
            self.sock=context.wrap_socket(self.sock,server_hostname=self.peer.hostname,
                                          do_handshake_on_connect=False)
            while True:
                self.check()
                try:
                    self.sock.do_handshake()
                    self.check()
                    return self
                except ssl.SSLWantReadError:
                    self.ready(selectors.EVENT_READ)
                except ssl.SSLWantWriteError:
                    self.ready(selectors.EVENT_WRITE)
        except BaseException as primary:
            # Required for T07-R08: close sets closed=True before sock.close.
            # If sock.close raises, CoveringHTTP.finally transport.close is a
            # no-op and will not raise. Raise a NEW UNKNOWN; do not mutate
            # any caller-owned exception object.
            try:
                self.close()
            except BaseException as cleanup:
                unknown=CoveringRootOutcomeUnknown()
                unknown.primary=primary
                unknown.response_close=None
                unknown.transport_close=cleanup
                current=(primary, None, cleanup)
                unknown.prior_retirement_provenance=()
                unknown.retirement_provenance=current
                unknown.retirement_occurrences=(current,)
                raise unknown
            raise

    def send(self, data):
        data=memoryview(data)
        while data:
            self.check()
            try:
                # Mark before the call: a failure can follow accepted bytes.
                self.sent=True
                count=self.sock.send(data)
                if count<=0:
                    raise CoveringTransportRefused("send incomplete")
                data=data[count:]
            except (ssl.SSLWantWriteError,BlockingIOError):
                self.ready(selectors.EVENT_WRITE)
            except ssl.SSLWantReadError:
                self.ready(selectors.EVENT_READ)

    def receive(self, maximum):
        while True:
            self.check()
            try:
                data=self.sock.recv(maximum)
                self.check()
                return data
            except (ssl.SSLWantReadError,BlockingIOError):
                self.ready(selectors.EVENT_READ)
            except ssl.SSLWantWriteError:
                self.ready(selectors.EVENT_WRITE)

    def close(self):
        if get_ident()!=self.owner:
            raise CoveringTransportRefused("foreign retirement refused")
        if not self.closed:
            self.closed=True
            if self.sock is not None:
                # Local close only, no TLS unwrap or second network exchange.
                self.sock.close()

