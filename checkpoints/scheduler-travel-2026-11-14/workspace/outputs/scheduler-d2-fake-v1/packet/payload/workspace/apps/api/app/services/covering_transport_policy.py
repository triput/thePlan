"""Covering-only response bounds and HTTPS destination validation.

No default limits or profile: caller must supply the reviewed policy. Pure
validation/counters; never reads credentials, resolves DNS or creates sockets.
"""
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import unquote, urlsplit
from app.services.covering_request_budget import CoveringDeadlineExceeded


class CoveringTransportRefused(Exception):
    pass



def _one_unquote(segment: str) -> str:
    # Inspection-only percent-decode. UTF-8 strict: invalid UTF-8 after a well-formed
    # percent sequence refuses via UnicodeDecodeError at the caller. This is not
    # urllib's default errors="replace" behavior. Never rewrites send targets.
    return unquote(segment, encoding="utf-8", errors="strict")


# Max successful decode transitions per opaque segment. Changing this number is a
# disclosed compatibility parameter, not an identical-outcome tweak.
_PATH_INSPECT_STEP_BUDGET = 8


def _refuse_path_admission() -> None:
    raise CoveringTransportRefused("path admission refused")


def _is_dot_nav(segment: str) -> bool:
    return segment in (".", "..")


def _has_encoded_slash(segment: str) -> bool:
    return "%2f" in segment.lower()


def _original_wire_percent_malformed(segment: str) -> bool:
    """True when original wire bytes contain a '%' not followed by two hex digits.

    Applies to the original segment only. Intermediate literals such as the '%'
    produced by decoding plain%25id are intentionally not re-tested here.
    """
    i = 0
    while i < len(segment):
        if segment[i] != "%":
            i += 1
            continue
        if i + 2 >= len(segment):
            return True
        if not (segment[i + 1] in "0123456789abcdefABCDEF" and segment[i + 2] in "0123456789abcdefABCDEF"):
            return True
        i += 3
    return False


def _inspect_opaque_id_segment(segment: str) -> None:
    """Bounded decode-inspect for calendar-ID opaque slots at skeleton positions.

    Original wire: refuse malformed/truncated percent escapes.
    Every intermediate: refuse empty, whole-segment dot-nav, literal '/', or
    encoded-slash. Each successful decode transition counts toward
    _PATH_INSPECT_STEP_BUDGET; exceeding the budget refuses (exhaustion).
    Invalid UTF-8 after a well-formed percent sequence refuses (strict).

    Preserves cal%2Bendar%40x.com, a%3Db%2Bc, plain%25id, a%2Eb, and valid
    UTF-8 calendar IDs such as caf%C3%A9. Never rewrites send bytes.
    """
    if _original_wire_percent_malformed(segment):
        _refuse_path_admission()
    cur = segment
    steps = 0
    while True:
        if cur == "" or _is_dot_nav(cur) or "/" in cur or _has_encoded_slash(cur):
            _refuse_path_admission()
        try:
            nxt = _one_unquote(cur)
        except UnicodeDecodeError:
            _refuse_path_admission()
        if nxt == cur:
            return
        steps += 1
        if steps > _PATH_INSPECT_STEP_BUDGET:
            _refuse_path_admission()
        cur = nxt


def _admit_structural_segment(segment: str) -> None:
    """Structural path tokens under an already-matched covering route.

    Refuse empty, whole-segment dot-nav, any '%', literal '/', or encoded-slash.
    Internal non-navigation dots in literals such as v1.0 remain admitted.
    """
    if segment == "" or _is_dot_nav(segment) or "/" in segment or "%" in segment or _has_encoded_slash(segment):
        _refuse_path_admission()


def _opaque_calendar_id_indices(segments: list) -> set:
    """Opaque calendar-ID indices from reviewed covering-refresh skeletons only.

    Positions are fixed by structural prefix shape. Opaque values are never
    scanned as grammar markers (a calendar ID equal to the literal 'calendars'
    does not open a further opaque slot). Exact route/purpose matching remains
    a separate prerequisite; this is not a live endpoint allowlist.
    """
    opaque = set()
    # Google full events collection: /calendar/v3/calendars/{id}/events...
    if (
        len(segments) >= 5
        and segments[0] == ""
        and segments[1] == "calendar"
        and segments[2] == "v3"
        and segments[3] == "calendars"
    ):
        opaque.add(4)
    # Microsoft ordinary calendarView (+ optional /delta): /v1.0/me/calendars/{id}/...
    if (
        len(segments) >= 5
        and segments[0] == ""
        and segments[1] == "v1.0"
        and segments[2] == "me"
        and segments[3] == "calendars"
    ):
        opaque.add(4)
    return opaque


def admit_covering_path(path: str) -> None:
    """Refuse structural traversal / ambiguous encoded routing before send.

    Splits on raw '/' only. Query/fragment must not appear in path (caller
    passes urlsplit().path). Query tokens stay opaque data at the URL layer.
    Does not normalize-and-forward. Target authorization remains separate.
    """
    raw = path if path else "/"
    if "?" in raw or "#" in raw:
        _refuse_path_admission()
    segments = raw.split("/")
    opaque = _opaque_calendar_id_indices(segments)
    for i, seg in enumerate(segments):
        if i == 0 and seg == "":
            continue
        if i in opaque:
            _inspect_opaque_id_segment(seg)
        else:
            _admit_structural_segment(seg)


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

