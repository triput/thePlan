"""Request-local covering client; ordinary calendar calls retain their client."""
from contextlib import contextmanager
from contextvars import ContextVar
import httpx
from urllib.parse import urlsplit
from app.services.covering_transport_policy import CoveringTransportRefused, admit_covering_path

_current=ContextVar("covering_provider_transport",default=None)


@contextmanager
def covering_provider_transport(transport):
    if _current.get() is not None:
        raise CoveringTransportRefused("nested provider transport refused")
    token=_current.set(transport)
    try:
        yield
    finally:
        _current.reset(token)


class _CoveringClient:
    def __init__(self, transport):
        self.transport=transport
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def _request(self, method, url, **kwargs):
        purposes=set()
        for peer,prefix,kind in self.transport.routes:
            try:
                parsed=peer.check_url(url)
            except CoveringTransportRefused:
                continue
            if parsed.path==prefix or (kind!="oauth" and parsed.path.startswith(prefix.rstrip("/")+"/")):
                purposes.add(kind)
        if len(purposes)!=1:
            raise CoveringTransportRefused("ambiguous/unapproved provider route")
        admit_covering_path(urlsplit(url).path or "/")
        return self.transport.request(method,url,purpose=purposes.pop(),**kwargs)
    def get(self,url,**kwargs):
        return self._request("GET",url,**kwargs)
    def post(self,url,**kwargs):
        return self._request("POST",url,**kwargs)


def calendar_client(*, timeout):
    transport=_current.get()
    if transport is None:
        return httpx.Client(timeout=timeout)
    return _CoveringClient(transport)

