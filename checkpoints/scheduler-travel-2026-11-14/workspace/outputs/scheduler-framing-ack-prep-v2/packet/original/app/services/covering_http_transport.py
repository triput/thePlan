"""Covering HTTP/1 JSON exchange over a joined, bounded TLS transport."""
import http.client
import io
import json
from urllib.parse import urlencode
import httpx

from app.services.covering_joined_https import JoinedTLS
from app.services.covering_transport_policy import CoveringTransportRefused, CoveringReauthorizationRequired, admit_covering_path
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown


class _Reader(io.RawIOBase):
    def __init__(self, transport, counter):
        self.transport=transport
        self.counter=counter
    def readable(self):
        return True
    def readinto(self, buffer):
        left=self.counter.limits.response_bytes-self.counter.bytes
        data=self.transport.receive(min(len(buffer),8192,left+1))
        self.counter.body(len(data))
        buffer[:len(data)]=data
        return len(data)


class _SocketView:
    def __init__(self, transport, counter):
        self.transport=transport
        self.counter=counter
    def makefile(self, *args, **kwargs):
        return io.BufferedReader(_Reader(self.transport,self.counter),buffer_size=8192)


class CoveringHTTP:
    def __init__(self, *, counter, routes, transport_factory=JoinedTLS):
        # routes maps exact reviewed origin/path prefix and purpose to peer.
        # No ambient proxy, default client, DNS fallback or credentials.
        self.counter=counter
        self.routes=tuple(routes)
        self.transport_factory=transport_factory

    def request(self, method, url, *, purpose, headers=None, params=None, data=None):
        if method not in ("GET","POST") or (method=="POST")!=(purpose=="oauth"):
            raise CoveringTransportRefused("method/purpose refused")
        matched=None
        for peer,prefix,kind in self.routes:
            if kind!=purpose:
                continue
            try:
                parsed=peer.check_url(url)
            except CoveringTransportRefused:
                continue
            if parsed.path==prefix or (purpose=="event" and parsed.path.startswith(prefix.rstrip("/")+"/")):
                matched=(peer,parsed)
                break
        if matched is None:
            raise CoveringTransportRefused("provider route refused")
        peer,parsed=matched
        admit_covering_path(parsed.path or "/")
        if purpose!="oauth":
            self.counter.page(purpose)
        else:
            self.counter.admit()
        path=parsed.path or "/"
        query=parsed.query
        if params:
            query += ("&" if query else "")+urlencode(params,doseq=True)
        if query:
            path+="?"+query
        payload=urlencode(data or {}).encode("ascii") if method=="POST" else b""
        request_headers={"Host":peer.hostname if peer.port==443 else f"{peer.hostname}:{peer.port}",
                         "Connection":"close","Accept":"application/json",
                         "Accept-Encoding":"identity"}
        for key,value in (headers or {}).items():
            if key.lower() not in ("authorization","prefer","accept"):
                raise CoveringTransportRefused("unexpected request header")
            request_headers[key]=value
        if method=="POST":
            request_headers.update({"Content-Type":"application/x-www-form-urlencoded",
                                    "Content-Length":str(len(payload))})
        if any("\r" in str(v) or "\n" in str(v) for v in request_headers.values()):
            raise CoveringTransportRefused("header injection refused")
        wire=(f"{method} {path} HTTP/1.1\r\n"+
              "".join(f"{k}: {v}\r\n" for k,v in request_headers.items())+"\r\n").encode("ascii")+payload
        transport=self.transport_factory(peer,self.counter.remaining)
        response=None
        # This invocation's primary only — never ambient sys.exc_info().
        invocation_primary=None
        try:
            transport.open()
            transport.send(wire)
            response=http.client.HTTPResponse(_SocketView(transport,self.counter))
            response.begin()
            if 300<=response.status<400:
                raise CoveringTransportRefused("redirect refused")
            if response.getheader("Content-Encoding","identity").lower()!="identity":
                raise CoveringTransportRefused("encoded response refused")
            body=bytearray()
            while True:
                self.counter.check()
                part=response.read(8192)
                if not part:
                    break
                body.extend(part)
            decoded=json.loads(body)
            if not isinstance(decoded,dict):
                raise CoveringTransportRefused("JSON object required")
            if purpose=="oauth" and response.status>=400:
                if response.status!=400 or decoded.get("error")!="invalid_grant":
                    remapped=CoveringRootOutcomeUnknown()
                    invocation_primary=remapped
                    raise remapped
                remapped=CoveringReauthorizationRequired()
                invocation_primary=remapped
                raise remapped
            # Count returned collection elements across all targets before
            # passing any collection to importer/canonicalizer.
            for key in ("items","value"):
                if key in decoded:
                    self.counter.batch(decoded[key])
            return httpx.Response(response.status,content=bytes(body),
                headers=dict(response.getheaders()),request=httpx.Request(method,url))
        except CoveringReauthorizationRequired as exc:
            if invocation_primary is None:
                invocation_primary=exc
            raise
        except BaseException as exc:
            if purpose=="oauth" and transport.sent:
                # Token rotation may have occurred. No retry/replay.
                remapped=CoveringRootOutcomeUnknown()
                invocation_primary=remapped
                raise remapped from None
            invocation_primary=exc
            raise
        finally:
            # Independently owned retirement attempts. Retain each cleanup
            # exception explicitly; do not use sys.exc_info() for primary.
            response_close_exc=None
            transport_close_exc=None
            if response is not None:
                try:
                    response.close()
                except BaseException as exc:
                    response_close_exc=exc
            try:
                transport.close()
            except BaseException as exc:
                transport_close_exc=exc
            if response_close_exc is not None or transport_close_exc is not None:
                # Always raise a NEW UNKNOWN for this cleanup boundary.
                # Never mutate invocation_primary or any caller-owned object
                # (including an outer CoveringRootOutcomeUnknown).
                unknown=CoveringRootOutcomeUnknown()
                unknown.primary=invocation_primary
                unknown.response_close=response_close_exc
                unknown.transport_close=transport_close_exc
                current=(invocation_primary, response_close_exc, transport_close_exc)
                prior=[]
                if isinstance(invocation_primary, CoveringRootOutcomeUnknown):
                    earlier=getattr(invocation_primary, "retirement_occurrences", None)
                    if earlier:
                        prior.extend(earlier)
                    else:
                        snap=getattr(invocation_primary, "retirement_provenance", None)
                        if snap is not None:
                            prior.append(snap)
                unknown.prior_retirement_provenance=tuple(prior)
                unknown.retirement_provenance=current
                unknown.retirement_occurrences=tuple(prior)+(current,)
                raise unknown

