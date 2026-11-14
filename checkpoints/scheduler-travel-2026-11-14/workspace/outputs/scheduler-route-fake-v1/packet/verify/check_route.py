"""HELD: extracted route classifiers and owning paginators; no live transport.

Only a separately authorized invocation may compile/exercise these definitions.
Raw application files are data, never package imports. Real stdlib HTTPResponse
reads finite complete frames through a memory-only transport. No TLS proof.
"""
from __future__ import annotations

import ast
import contextlib
import contextvars
import dataclasses
import datetime
import hashlib
import http.client
import io
import ipaddress
import json
import os
import sys
import types
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULT = HERE / "FAKE-ROUTE-RESULT.json"
MAX_RESULT = 262144
MS = "https://graph.microsoft.com"
GOOGLE = "https://www.googleapis.com"
LIST = "/v1.0/me/calendars"
EVENT = LIST + "/cal-fixture/calendarView"


class Deadline(Exception):
    pass


class Unknown(Exception):
    pass


class ApiError(Exception):
    pass


class Response:
    def __init__(self, status, *, content, headers, request):
        self.status_code = status
        self.content = content
        self.text = content.decode("utf-8")
        self.headers = headers
        self.request = request

    def json(self):
        return json.loads(self.content)


HTTPX = types.SimpleNamespace(
    Response=Response, Request=lambda method, url: (method, url),
    Client=lambda **kw: (_ for _ in ()).throw(AssertionError("ambient client")),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def verify_sources(rows):
    seen = set()
    for row in rows:
        rel = row["relative_path"]
        path = (ROOT / rel).resolve()
        if not path.is_relative_to(ROOT) or rel in seen:
            raise ValueError("invalid source inventory")
        seen.add(rel)
        if digest(path) != row["sha256"]:
            raise ValueError("source pin mismatch")
    actual = {p.relative_to(ROOT).as_posix() for v in ("original", "candidate")
              for p in (ROOT / v).rglob("*") if p.is_file()}
    if seen != actual or len(seen) != 468:
        raise ValueError("source inventory mismatch")


def extract(path, names, env, *, mutate=None):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if "\r" in text.replace("\r\n", ""):
        raise ValueError("bare CR source")
    tree = ast.parse(text, filename=str(path))
    picked = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            picked.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                picked.append(node)
    found = {n.name if hasattr(n, "name") else n.targets[0].id for n in picked}
    if found != set(names):
        raise ValueError("extraction inventory mismatch:" + str(set(names) - found))
    if mutate is not None:
        # Mutation controls operate only on this in-memory AST, never source files.
        hits = 0
        for node in ast.walk(ast.Module(body=picked, type_ignores=[])):
            if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                    and node.left.id == mutate and len(node.comparators) == 1
                    and isinstance(node.comparators[0], ast.Constant)
                    and node.comparators[0].value == "event"
                    and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq)):
                node.ops = [ast.NotEq()]
                node.comparators[0].value = "oauth"
                hits += 1
        if hits != 1:
            raise ValueError("mutation site mismatch")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future] + picked, type_ignores=[]))
    exec(compile(module, str(path), "exec"), env)


def build(version, *, mutation=None):
    name = "route_fixture_" + version + "_" + str(mutation)
    module = types.ModuleType(name)
    sys.modules[name] = module
    env = module.__dict__
    env.update(dataclass=dataclasses.dataclass, ip_address=ipaddress.ip_address,
               unquote=urllib.parse.unquote, urlsplit=urllib.parse.urlsplit,
               quote=urllib.parse.quote, urlencode=urllib.parse.urlencode,
               contextmanager=contextlib.contextmanager, ContextVar=contextvars.ContextVar,
               CoveringDeadlineExceeded=Deadline, CoveringRootOutcomeUnknown=Unknown,
               http=http, httpx=HTTPX, io=io, json=json, ApiError=ApiError,
               JoinedTLS=lambda *a: (_ for _ in ()).throw(AssertionError("live TLS")),
               datetime=datetime.datetime, timezone=datetime.timezone,
               GRAPH_BASE=MS + "/v1.0", _GRAPH_ORIGIN=MS + "/",
               GOOGLE_CALENDAR_LIST_URL=GOOGLE + "/calendar/v3/users/me/calendarList",
               pagination_max_pages=None, MicrosoftDeltaExpired=type("MicrosoftDeltaExpired", (Exception,), {}),
               GoogleSyncTokenExpired=type("GoogleSyncTokenExpired", (Exception,), {}))
    services = ROOT / version / "app" / "services"
    policy = ast.parse((services / "covering_transport_policy.py").read_bytes())
    names = [n.name for n in policy.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
    names.append("_PATH_INSPECT_STEP_BUDGET")
    extract(services / "covering_transport_policy.py", names, env)
    env["_current"] = contextvars.ContextVar(name + "_transport", default=None)
    extract(services / "covering_provider_context.py",
            ["covering_provider_transport", "_CoveringClient", "calendar_client"], env,
            mutate="kind" if mutation == "client" else None)
    extract(services / "covering_http_transport.py", ["_Reader", "_SocketView", "CoveringHTTP"], env,
            mutate="purpose" if mutation == "http" else None)
    extract(services / "microsoft_calendar.py", [
        "GraphPageStats", "_calendar_view_url", "_calendar_view_delta_url", "_graph_headers",
        "_ensure_aware", "_iso_z", "_decode_json_object", "_odata_link", "_graph_collection_page",
        "_absolute_graph_url", "_graph_collect", "_graph_access_role", "list_microsoft_calendars",
        "microsoft_event_list_window_params", "microsoft_calendar_view_list_params",
        "list_calendar_view", "_fetch_default_calendar"], env)
    extract(services / "google_calendar.py", ["_calendar_events_base", "_paginate_events",
                                              "list_google_calendars"], env)
    return env


class MemoryTLS:
    """No socket/TLS operation; exchange count and sent bytes are observations."""
    def __init__(self, payload, log):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.buffer = io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                                 + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
        self.sent = False
        self.close_calls = 0
        self.log = log

    def open(self):
        pass

    def send(self, wire):
        self.sent = True
        self.log.append(wire.decode("ascii"))

    def receive(self, count):
        return self.buffer.read(count)

    def close(self):
        self.close_calls += 1


class Harness:
    def __init__(self, env, routes, payloads, *, limits=None):
        self.env = env
        self.wires = []
        self.transports = []
        self.pending = list(payloads)
        self.deadline_calls = 0
        def remaining():
            self.deadline_calls += 1
            return 200.0
        self.counter = env["ProviderCounter"](limits or env["ProviderLimits"](20, 10, 10000, 16777216), remaining)
        peers = {}
        configured = []
        for origin, path, kind in routes:
            host = urllib.parse.urlsplit(origin).hostname
            if host not in peers:
                peers[host] = env["HTTPSPeer"](host, "127.0.0.1", 443, "not-opened.pem")
            configured.append((peers[host], path, kind))
        def factory(peer, callback):
            if callback != self.counter.remaining:
                raise AssertionError("deadline callback replaced")
            if not self.pending:
                raise AssertionError("unexpected transport allocation")
            obj = MemoryTLS(self.pending.pop(0), self.wires)
            self.transports.append(obj)
            return obj
        self.http = env["CoveringHTTP"](counter=self.counter, routes=configured, transport_factory=factory)
        self.client = env["_CoveringClient"](self.http)

    def outcome(self, fn):
        try:
            result = fn()
        except self.env["CoveringTransportRefused"]:
            result = None
            kind = "REFUSE"
        else:
            kind = "OK"
        # Unexpected exceptions propagate and fail the verification immediately.
        return kind, result

    def observed(self, outcome):
        if any(t.close_calls != 1 for t in self.transports):
            raise AssertionError("transport retirement mismatch")
        return {"outcome": outcome, "identity": self.counter.pages["identity"],
                "event": self.counter.pages["event"], "sends": len(self.wires)}


def routes():
    return [(MS, LIST, "identity"), (MS, "/v1.0/me/calendar", "identity"), (MS, EVENT, "event")]


def direct(env, cfg, url, *, purpose=None, method="GET"):
    h = Harness(env, cfg, [{"value": []}])
    fn = (lambda: h.http.request(method, url, purpose=purpose)) if purpose else (
        lambda: h.client._request(method, url))
    outcome, _ = h.outcome(fn)
    return h.observed(outcome)


def scenario(cid, env):
    if cid == "ROUTE-MS-LIST":
        return direct(env, routes(), MS + LIST)
    if cid == "ROUTE-MS-EVENT-OVERLAP":
        return direct(env, routes(), MS + EVENT)
    if cid == "ROUTE-MS-DEFAULT":
        h = Harness(env, routes(), [{"id": "cal-fixture", "name": "fixture"}])
        with env["covering_provider_transport"](h.http):
            outcome, result = h.outcome(lambda: env["_fetch_default_calendar"]("synthetic-token"))
        if result != ("cal-fixture", "fixture"):
            raise AssertionError("default caller result")
        return h.observed(outcome)
    if cid in ("ROUTE-MS-LIST-CONTINUATION-ABS", "ROUTE-MS-LIST-CONTINUATION-ROOT"):
        link = LIST + "?$skiptoken=opaque%2F%25+token"
        if cid.endswith("ABS"):
            link = MS + link
        h = Harness(env, routes(), [{"value": [{"id": "one"}], "@odata.nextLink": link},
                                    {"value": [{"id": "two"}]}])
        with env["covering_provider_transport"](h.http):
            outcome, result = h.outcome(lambda: env["list_microsoft_calendars"]("synthetic-token"))
        if [x["id"] for x in result] != ["one", "two"]:
            raise AssertionError("list items")
        if h.wires[1].split("\r\n")[0] != "GET " + LIST + "?$skiptoken=opaque%2F%25+token HTTP/1.1":
            raise AssertionError("continuation query/initial params")
        return h.observed(outcome)
    if cid == "ROUTE-MS-EVENT-CONTINUATION":
        h = Harness(env, routes(), [{"value": [{"id": "one"}], "@odata.nextLink": EVENT + "?$skiptoken=opaque%2F%25"},
                                    {"value": [{"id": "two"}]}])
        with env["covering_provider_transport"](h.http):
            outcome, result = h.outcome(lambda: env["list_calendar_view"](
                "synthetic-token", "cal-fixture", time_min=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
                time_max=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)))
        if outcome == "OK":
            if [x["id"] for x in result[0]] != ["one", "two"] or result[1:] != (2, True):
                raise AssertionError("event pagination result")
            if h.wires[1].split("\r\n")[0] != "GET " + EVENT + "?$skiptoken=opaque%2F%25 HTTP/1.1":
                raise AssertionError("event continuation query")
        return h.observed(outcome)
    if cid == "ROUTE-IDENTITY-DESCENDANT":
        return direct(env, [(MS, LIST, "identity")], MS + LIST + "/unlisted")
    if cid == "ROUTE-HTTP-IDENTITY-DESCENDANT":
        return direct(env, [(MS, LIST, "identity")], MS + LIST + "/unlisted", purpose="identity")
    if cid == "ROUTE-EXPLICIT-SECOND-IDENTITY":
        cfg = [(MS, LIST, "identity"), (MS, LIST + "/continuation", "identity")]
        return {"exact": direct(env, cfg, MS + LIST + "/continuation"),
                "unlisted": direct(env, cfg, MS + LIST + "/continuation/unlisted")}
    if cid == "ROUTE-EVENT-DESCENDANT":
        return direct(env, [(MS, EVENT, "event")], MS + EVENT + "/delta")
    if cid == "ROUTE-EQUAL-PATH-CONFLICT":
        return direct(env, [(MS, LIST, "identity"), (MS, LIST, "event")], MS + LIST)
    if cid == "ROUTE-GOOGLE-LIST":
        path = "/calendar/v3/users/me/calendarList"
        h = Harness(env, [(GOOGLE, path, "identity")],
                    [{"items": [{"id": "one"}], "nextPageToken": "opaque/%+"}, {"items": [{"id": "two"}]}])
        with env["covering_provider_transport"](h.http):
            outcome, result = h.outcome(lambda: env["list_google_calendars"]("synthetic-token"))
        if [x["id"] for x in result] != ["one", "two"]:
            raise AssertionError("Google list result")
        if "pageToken=opaque%2F%25%2B" not in h.wires[1].split("\r\n")[0]:
            raise AssertionError("Google opaque query")
        return h.observed(outcome)
    if cid == "ROUTE-GOOGLE-EVENT":
        url = env["_calendar_events_base"]("cal+endar@x.com")
        if url != GOOGLE + "/calendar/v3/calendars/cal%2Bendar%40x.com/events":
            raise AssertionError("actual Google URL builder")
        h = Harness(env, [(GOOGLE, urllib.parse.urlsplit(url).path, "event")],
                    [{"items": [{"id": "one"}], "nextPageToken": "opaque/%+"},
                     {"items": [{"id": "two"}], "nextSyncToken": "end"}])
        with env["covering_provider_transport"](h.http):
            outcome, result = h.outcome(lambda: env["_paginate_events"]("synthetic-token", url, params={"maxResults": "100"}))
        if result != ([{"id": "one"}, {"id": "two"}], "end", 2):
            raise AssertionError("Google events result")
        if "pageToken=opaque%2F%25%2B" not in h.wires[1].split("\r\n")[0]:
            raise AssertionError("Google event query")
        return h.observed(outcome)
    if cid == "ROUTE-OAUTH-EXACT":
        result = {}
        for label, origin, path in (("google", "https://oauth2.googleapis.com", "/token"),
                                    ("ms", "https://login.microsoftonline.com", "/common/oauth2/v2.0/token")):
            cfg = [(origin, path, "oauth")]
            result[label] = {"exact": direct(env, cfg, origin + path, method="POST"),
                             "descendant": direct(env, cfg, origin + path + "/unlisted", method="POST")}
        return result
    if cid == "ROUTE-D2-PRESERVATION":
        cfg = [(GOOGLE, "/calendar/v3/calendars", "event")]
        return {label: direct(env, cfg, GOOGLE + path) for label, path in (
            ("traversal", "/calendar/v3/calendars/cal/events/../other"),
            ("encoded_slash", "/calendar/v3/calendars/a%2Fb/events"),
            ("unicode", "/calendar/v3/calendars/caf%C3%A9/events?opaque=%2F%25"))}
    if cid == "ROUTE-REQUEST-SHARING":
        h = Harness(env, routes(), [{"value": [{"id": "one"}]}], limits=env["ProviderLimits"](20, 1, 10000, 16777216))
        first, _ = h.outcome(lambda: h.client.get(MS + LIST))
        # Direct HTTP purpose isolates cumulative admission from original client overlap.
        second, _ = h.outcome(lambda: h.http.request("GET", MS + EVENT, purpose="event"))
        obs = h.observed(second)
        obs.update(first=first, stopped=h.counter.stopped, items=h.counter.items,
                   counted_bytes=h.counter.bytes == sum(len(t.buffer.getvalue()) for t in h.transports),
                   deadline_used=h.deadline_calls > 0)
        return obs
    raise ValueError("unknown control")


def inventory_control(manifest):
    changed = []
    for row in manifest["sources"]:
        if not row["relative_path"].startswith("original/"):
            continue
        rel = row["relative_path"][len("original/"):]
        left = (ROOT / "original" / rel).read_bytes()
        right = (ROOT / "candidate" / rel).read_bytes()
        if left != right:
            changed.append(rel)
            old = b'kind!="oauth" and parsed.path.startswith' if rel.endswith("covering_provider_context.py") else b'purpose!="oauth" and parsed.path.startswith'
            new = b'kind=="event" and parsed.path.startswith' if rel.endswith("covering_provider_context.py") else b'purpose=="event" and parsed.path.startswith'
            if left.count(old) != 1 or left.replace(old, new) != right:
                raise AssertionError("non-approved application change")
    if sorted(changed) != ["app/services/covering_http_transport.py", "app/services/covering_provider_context.py"]:
        raise AssertionError("application diff inventory")
    http_source = (ROOT / "candidate/app/services/covering_http_transport.py").read_bytes()
    if http_source.count(b'if purpose!="oauth":') != 1:
        raise AssertionError("page branch changed")
    bad = [dict(row) for row in manifest["sources"]]
    bad[0]["sha256"] = "0" * 64
    try:
        verify_sources(bad)
    except ValueError:
        rejected = True
    else:
        rejected = False
    return {"changed_files": changed, "bad_pin_rejected": rejected, "source_count": len(bad)}


def main():
    if RESULT.exists():
        raise ValueError("preexisting result")
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        raise ValueError("isolation")
    manifest = json.loads((HERE / "INPUT-MANIFEST.json").read_bytes())
    expected = json.loads((HERE / "EXPECTED.json").read_bytes())
    verify_sources(manifest["sources"])
    envs = {v: build(v) for v in ("original", "candidate")}
    observations = {}
    for cid in expected["wire_ids_in_order"]:
        if cid == "ROUTE-SOURCE-INVENTORY":
            observation = inventory_control(manifest)
        elif cid == "ROUTE-MUTATION-CLIENT":
            observation = direct(build("candidate", mutation="client"), routes(), MS + EVENT)
        elif cid == "ROUTE-MUTATION-HTTP":
            observation = direct(build("candidate", mutation="http"), [(MS, LIST, "identity")],
                                 MS + LIST + "/unlisted", purpose="identity")
        else:
            observation = {v: scenario(cid, envs[v]) for v in ("original", "candidate")}
        # Strict canonical JSON equality also distinguishes booleans from integers.
        if json.dumps(observation, sort_keys=True) != json.dumps(expected["inputs"][cid]["observation"], sort_keys=True):
            raise AssertionError("control mismatch:" + cid + ":" + json.dumps(observation, sort_keys=True))
        observations[cid] = {"observed_outcome": "PASS", "observation": observation}
    verify_sources(manifest["sources"])
    payload = {"status": "PASS", "class": "FAKE-ROUTE", "executed": True,
               "source_hashes_verified": True, "inventory_error": None,
               "wire_ids_in_order": list(observations), "inputs": observations,
               "limits": "byte fakes; no TLS/native/provider proof"}
    raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_RESULT:
        raise ValueError("result cap")
    with RESULT.open("xb") as stream:
        stream.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
