"""Covering HTTP/1 JSON exchange over a joined, bounded TLS transport.

Framing acknowledgment candidate (workspace-authoring lane): covering-local
guarded HTTPResponse subclass + before-decode completeness/header gate.
Retains the 8192-byte collection loop and existing parser/budget caps.

PRIVATE PARSER COUPLING (disclose; requalify on runtime upgrade):
- Host CPython 3.11 http.client HTTPResponse helpers _get_chunk_left,
  _read_next_chunk_size, _read_and_discard_trailer, read/readinto, and the
  length/chunked attributes (host pin 3A752927A1257EDEBCABAD42CA9508AD532F91C15431755BFBE437A32AB13EB2).
- Captured native http/client.py.source
  C2C0694155837D72FC710A4138E5D1E53AE1A652B117A2E23A5B1B0DB527A0F9
  (interim/trailer caps differ; do not import captured bytes into host).
- Host email feedparser defect recording
  A3A309A212382FA3CA054DB3150C78B931D9E975FD55EDBC8D6230FDA91A5E6D
  (MissingHeaderBodySeparatorDefect prediction; not executed native claim).
No global monkeypatch, unbounded body read, or handwritten HTTP stack.
"""
import http.client
import io
import json
import re
from urllib.parse import urlencode
import httpx

from app.services.covering_joined_https import JoinedTLS
from app.services.covering_transport_policy import CoveringTransportRefused, CoveringReauthorizationRequired, admit_covering_path
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown

# Unsigned ASCII decimal Content-Length (leading zeros allowed). REVIEW CANDIDATE.
_CL_DECIMAL = re.compile(r"^[0-9]+$")
# Unsigned hex chunk-size token (no sign, no OWS). Extensions stripped before match.
_CHUNK_SIZE_HEX = re.compile(rb"^[0-9A-Fa-f]+$")
# HTTP OWS for CL value normalization only: SP / HTAB. Not full str.strip().
_OWS_CHARS = " \t"


def _ows_strip(value: str) -> str:
    """Strip only SP/HTAB (RFC OWS). Does not strip other Unicode whitespace."""
    return value.strip(_OWS_CHARS)


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


class _GuardedHTTPResponse(http.client.HTTPResponse):
    """Covering-only response: exact completion + chunk/trailer termination.

    Couples to private http.client helpers named in the module docstring.
    Host vs captured-native lanes remain separate verification obligations.
    """

    def read(self, amt=None):
        if self.fp is None:
            return b""
        if self._method == "HEAD":
            self._close_conn()
            return b""
        if self.chunked:
            return self._read_chunked(amt)
        if amt is not None and amt >= 0:
            if self.length is not None and amt > self.length:
                amt = self.length
            s = self.fp.read(amt)
            if not s and amt:
                # Fixed-length short body: refuse silent EOF acceptance.
                if self.length is not None and self.length > 0:
                    self._close_conn()
                    raise http.client.IncompleteRead(b"", self.length)
                self._close_conn()
            elif self.length is not None:
                self.length -= len(s)
                if not self.length:
                    self._close_conn()
            return s
        # Unbounded path retained for stdlib compatibility; CoveringHTTP never
        # calls read() without amt (keeps 8192 bounded collection).
        if self.length is None:
            s = self.fp.read()
        else:
            try:
                s = self._safe_read(self.length)
            except http.client.IncompleteRead:
                self._close_conn()
                raise
            self.length = 0
        self._close_conn()
        return s

    def readinto(self, b):
        if self.fp is None:
            return 0
        if self._method == "HEAD":
            self._close_conn()
            return 0
        if self.chunked:
            return self._readinto_chunked(b)
        if self.length is not None:
            if len(b) > self.length:
                b = memoryview(b)[0:self.length]
        n = self.fp.readinto(b)
        if not n and b:
            if self.length is not None and self.length > 0:
                self._close_conn()
                raise http.client.IncompleteRead(b"", self.length)
            self._close_conn()
        elif self.length is not None:
            self.length -= n
            if not self.length:
                self._close_conn()
        return n

    def _read_next_chunk_size(self):
        # Require CRLF-terminated size line (extensions stripped after check).
        # P2: admit only unsigned hex tokens before any inherited _safe_read/fp.read.
        # Signed/negative/nonhex sizes must not become chunk_left (avoids read(-1)).
        line = self.fp.readline(http.client._MAXLINE + 1)
        if len(line) > http.client._MAXLINE:
            raise http.client.LineTooLong("chunk size")
        if not line.endswith(b"\r\n"):
            self._close_conn()
            raise http.client.IncompleteRead(b"")
        size_token = line[:-2]
        i = size_token.find(b";")
        if i >= 0:
            size_token = size_token[:i]
        if not _CHUNK_SIZE_HEX.fullmatch(size_token):
            self._close_conn()
            raise CoveringTransportRefused("chunk size token refused")
        size = int(size_token, 16)
        if size < 0:
            # Unreachable under hex-only admission; retained as hard stop.
            self._close_conn()
            raise CoveringTransportRefused("negative chunk size refused")
        return size

    def _read_and_discard_trailer(self):
        # Final empty CRLF required; EOF without terminator is incomplete.
        # P1: retain captured-native trailers_read > _MAXHEADERS bound AND final CRLF.
        # Malformed trailer field lines (no colon) refused — REVIEW CANDIDATE.
        # Valid name:value trailers are discarded and not promoted to framing.
        trailers_read = 0
        while True:
            line = self.fp.readline(http.client._MAXLINE + 1)
            if len(line) > http.client._MAXLINE:
                raise http.client.LineTooLong("trailer line")
            if not line:
                self._close_conn()
                raise http.client.IncompleteRead(b"")
            if line == b"\r\n":
                return
            if not line.endswith(b"\r\n"):
                self._close_conn()
                raise http.client.IncompleteRead(b"")
            field = line[:-2]
            if b":" not in field:
                self._close_conn()
                raise CoveringTransportRefused("malformed trailer field line refused")
            trailers_read += 1
            if trailers_read > http.client._MAXHEADERS:
                raise http.client.HTTPException(
                    "got more than %d trailers" % http.client._MAXHEADERS
                )
            # Valid trailer field: discard only.

    def _get_chunk_left(self):
        chunk_left = self.chunk_left
        if not chunk_left:  # 0 or None
            if chunk_left is not None:
                sep = self._safe_read(2)
                if sep != b"\r\n":
                    self._close_conn()
                    raise http.client.IncompleteRead(b"")
            try:
                chunk_left = self._read_next_chunk_size()
            except ValueError:
                raise http.client.IncompleteRead(b"")
            if chunk_left == 0:
                self._read_and_discard_trailer()
                self._close_conn()
                chunk_left = None
            self.chunk_left = chunk_left
        return chunk_left


def _framing_header_occurrences(headers):
    """Raw Content-Length / Transfer-Encoding occurrences before dict collapse."""
    get_all = getattr(headers, "get_all", None)
    if get_all is None:
        cl = headers.get("content-length")
        te = headers.get("transfer-encoding")
        return ([cl] if cl is not None else []), ([te] if te is not None else [])
    return list(get_all("content-length") or []), list(get_all("transfer-encoding") or [])


def _admit_framing_headers(response):
    """Before-decode header gate. Compatibility policy = REVIEW CANDIDATE.

    Accepted under this candidate proposal:
    - Exactly one Content-Length field whose value, after SP/HTAB-only OWS
      strip, matches unsigned ASCII decimal (leading zeros OK), when
      length-delimited. Other Unicode whitespace is NOT stripped and fails.
    - Exactly one Transfer-Encoding field whose raw value lowercases to
      exactly "chunked" with NO surrounding whitespace — matching pinned
      begin()'s `tr_enc.lower() == "chunked"` (no strip). P3 coherence:
      gate-accepted TE spelling must imply response.chunked is True.
    - Neither CL nor TE for close-delimited positives (subject to later
      orderly-TLS proof).
    - Parser Message.defects empty (refuse recorded malformed-header defects).

    Refused under this candidate proposal (not accepted contract):
    - Repeated Content-Length fields (identical or conflicting).
    - Comma-list Content-Length values.
    - Signed / negative / empty / nondecimal Content-Length spellings.
    - Transfer-Encoding together with Content-Length.
    - Unsupported, repeated, mixed, comma-list, or whitespace-padded TE
      (including "chunked "/" chunked" — not reported as chunked positives).
    - Any parser-reported header defect on the Message.
    - TE declared chunked while response.chunked is false (incoherent).
    """
    headers = response.headers
    defects = getattr(headers, "defects", None) or ()
    if defects:
        raise CoveringTransportRefused("malformed response header defect refused")
    cl_values, te_values = _framing_header_occurrences(headers)
    if te_values and cl_values:
        raise CoveringTransportRefused("transfer-encoding with content-length refused")
    if len(te_values) > 1:
        raise CoveringTransportRefused("repeated transfer-encoding refused")
    if len(te_values) == 1:
        raw_te = te_values[0]
        if "," in raw_te:
            raise CoveringTransportRefused("transfer-encoding list refused")
        # P3: no strip — must match begin() recognition exactly.
        if raw_te.lower() != "chunked":
            raise CoveringTransportRefused("unsupported transfer-encoding refused")
        if not getattr(response, "chunked", False):
            raise CoveringTransportRefused("transfer-encoding chunked mode incoherent")
    if len(cl_values) > 1:
        raise CoveringTransportRefused("repeated content-length refused")
    if len(cl_values) == 1:
        raw_cl = cl_values[0]
        if "," in raw_cl:
            raise CoveringTransportRefused("content-length list refused")
        token = _ows_strip(raw_cl)
        if not _CL_DECIMAL.fullmatch(token):
            raise CoveringTransportRefused("invalid content-length refused")


def _admit_fixed_length_complete(response):
    """Exact fixed-length completion before JSON/OAuth classification."""
    remaining = getattr(response, "length", None)
    if remaining is not None and remaining > 0:
        raise CoveringTransportRefused("incomplete fixed-length body refused")


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
            response=_GuardedHTTPResponse(_SocketView(transport,self.counter))
            response.begin()
            if 300<=response.status<400:
                raise CoveringTransportRefused("redirect refused")
            if response.getheader("Content-Encoding","identity").lower()!="identity":
                raise CoveringTransportRefused("encoded response refused")
            # Header inventory / defect gate before body decode classification.
            _admit_framing_headers(response)
            body=bytearray()
            while True:
                self.counter.check()
                part=response.read(8192)
                if not part:
                    break
                body.extend(part)
            _admit_fixed_length_complete(response)
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
