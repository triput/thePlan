#!/usr/bin/env python3
"""HELD fake-only checker for the worker-exception observer diagnostic successor.

Matt, 2026-11-12. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

The controls exercise ACTUAL extracted source text from raw-pinned subject copies:
  - candidate runner np_runner_entry.py (341074AE...): the new
    _install_worker_exception_observer helper, the restore wiring and the non-200
    chaining block inside _run_np_v_ms_nonexpired, and the unchanged stop_payload
  - source runner np_runner_entry.py (40A1BA8E..., the executed dex-v1 role 4)
  - immutable host validator DockerOps._record_runner_stop + _id + digest
    (docker_transport.py 7F7EA820...)
  - production covering_http_dispatch.py (5160780F...) and
    covering_role_connector.py (C5BA15CD..., CRLF), structural reads only
All behavior runs against fake modules (installed and removed through an exact
sys.modules sandbox), an in-memory fake filesystem and fake exception chains.

Imports are standard library only. There are no app or vendor imports, no sockets,
TLS, PKI, Docker, database, child processes or network, and no real fixture
filesystem access inside controls. Subject bytes are read once from this packet and
hash-verified. The only write is the exclusive result file.

Proof scope: fake behavior of the extracted blocks only. Whether the native worker
actually raises through run_bounded_domain, the real exception classes, frames and
paths in the container, and the native host path all remain unproved.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import posixpath
import re
import sys
import textwrap
import types
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-native-worker-diagnostic-fake-prep-matt-v1"

SUBJECT_PINS = {
    "candidate/np_runner_entry.py": "341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645",
    "source/np_runner_entry.py": "40A1BA8E9C3E320DD7DF9E06102CC29C0E1AFAAD4213EC0FECF9FE34455BF73F",
    "host/docker_transport.py": "7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53",
    "production/covering_http_dispatch.py": "5160780F4F13E450F19515560CF85EDCDCB5A7906FED99A7027AE8C93071D1FF",
    "production/covering_role_connector.py": "C5BA15CDE276586CFFA2DE24A51E79F40CC6479D3A5A1D6663D23A20D930B288",
    "diff/Worker-Observer.diff": "2023F97B5695BF690F50186C56B4DD3FCFF1A2BAFB3CA637B1051F400F3F2468",
}

CONTROL_IDS = (
    "SUBJECT-PINS",
    "DIFF-REDERIVATION",
    "PRESERVED-OUTSIDE-CHANGE",
    "PRODUCTION-BOUNDARY-STRUCTURE",
    "OBSERVER-SUCCESS-IDENTITY",
    "OBSERVER-EXCEPTION-IDENTITY",
    "RESTORE-WIRING",
    "CHAINING-WIRING",
    "PRODUCER-HOST-END-TO-END",
    "ACTUAL-SOURCE-MUTANTS",
)

CASE_FUNCTION = "_run_np_v_ms_nonexpired"
HELPER = "_install_worker_exception_observer"
DISPATCH_MODULE = "app.services.covering_http_dispatch"
SANDBOX_NAMES = ("app", "app.services", DISPATCH_MODULE)

FAKE_ROOT = "/packet"
FAKE_MANIFEST = FAKE_ROOT + "/SHA256SUMS.txt"
RUNNER_ID = "a" * 64
OWNED_ARGS = ["start", "--attach", RUNNER_ID]
SECRET = "SECRET-SENTINEL-7Q"


class WitnessFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WitnessFailure(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


# ---------------------------------------------------------------------------
# Subject loading (the only real file reads, besides EXPECTED)
# ---------------------------------------------------------------------------

_SUBJECT_TEXT: dict[str, str] = {}


def subject_text(rel: str) -> str:
    if rel not in _SUBJECT_TEXT:
        raise WitnessFailure(f"subject not admitted:{rel}")
    return _SUBJECT_TEXT[rel]


def check_subject_pins() -> dict[str, Any]:
    observed = {}
    for rel, pin in SUBJECT_PINS.items():
        data = (SUBJECTS / rel).read_bytes()
        digest = sha256_bytes(data)
        require(digest == pin, f"subject pin mismatch:{rel}")
        # CRLF pairs are admitted (covering_role_connector.py is CRLF); bare CR is not.
        # The replace result is a predicate input only; raw bytes are never rewritten.
        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
        _SUBJECT_TEXT[rel] = data.decode("utf-8")
        observed[rel] = digest
    return {"subjects": observed, "control_kind": "raw_pin", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Literal unified-diff re-derivation (pure text; no patch tool)
# ---------------------------------------------------------------------------

_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*")


def apply_unified(original: str, diff: str) -> tuple[str, list[str], int, int, int]:
    src = original.split("\n")
    lines = diff.split("\n")
    out: list[str] = []
    files: list[str] = []
    pos = 0
    i = 0
    hunks = 0
    added = 0
    removed = 0
    while i < len(lines) and not lines[i].startswith("@@"):
        line = lines[i]
        if line.startswith("--- ") or line.startswith("+++ "):
            files.append(line[4:])
        elif line != "":
            raise WitnessFailure("unexpected diff header line")
        i += 1
    while i < len(lines):
        header = lines[i]
        if header == "" and i == len(lines) - 1:
            break
        match = _HUNK.fullmatch(header)
        require(match is not None, "malformed hunk header")
        old_start = int(match.group(1))
        old_len = int(match.group(2) or "1")
        new_len = int(match.group(4) or "1")
        start = old_start - 1
        require(start >= pos, "overlapping or unordered hunks")
        out.extend(src[pos:start])
        pos = start
        seen_old = 0
        seen_new = 0
        i += 1
        while i < len(lines) and not lines[i].startswith("@@"):
            line = lines[i]
            if line == "" and i == len(lines) - 1:
                break
            tag, body = line[:1], line[1:]
            if tag == " ":
                require(pos < len(src) and src[pos] == body, f"context mismatch at {pos + 1}")
                out.append(body)
                pos += 1
                seen_old += 1
                seen_new += 1
            elif tag == "-":
                require(pos < len(src) and src[pos] == body, f"removal mismatch at {pos + 1}")
                pos += 1
                seen_old += 1
                removed += 1
            elif tag == "+":
                out.append(body)
                seen_new += 1
                added += 1
            else:
                raise WitnessFailure("unexpected hunk line")
            i += 1
        require((seen_old, seen_new) == (old_len, new_len), "hunk length mismatch")
        hunks += 1
    out.extend(src[pos:])
    return "\n".join(out), files, hunks, added, removed


_DIFF_STATS: dict[str, int] = {}


def check_diff_rederivation() -> dict[str, Any]:
    source = subject_text("source/np_runner_entry.py")
    candidate = subject_text("candidate/np_runner_entry.py")
    diff = subject_text("diff/Worker-Observer.diff")
    derived, files, hunks, added, removed = apply_unified(source, diff)
    require(files == ["a/payload/fixture/np_runner_entry.py", "b/payload/fixture/np_runner_entry.py"],
            "diff touches unexpected files")
    require(hunks == 5, "expected exactly five hunks")
    require(derived == candidate, "candidate bytes differ from source + diff")
    _DIFF_STATS.update(added=added, removed=removed)
    return {"hunks": hunks, "files": files, "lines_added": added, "lines_removed": removed,
            "derived_sha256": sha256_bytes(derived.encode("utf-8")),
            "control_kind": "literal_text", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Source extraction helpers (AST used only to locate exact source segments)
# ---------------------------------------------------------------------------

def _single(nodes: list[Any], what: str) -> Any:
    require(len(nodes) == 1, f"expected exactly one {what}, found {len(nodes)}")
    return nodes[0]


def top_function(text: str, name: str, class_name: str | None = None) -> ast.FunctionDef:
    body = ast.parse(text).body
    if class_name is not None:
        cls = _single([n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name],
                      f"class {class_name}")
        body = cls.body
    return _single([n for n in body if isinstance(n, ast.FunctionDef) and n.name == name],
                   f"function {name}")


def extract_function(text: str, name: str, class_name: str | None = None) -> str:
    node = top_function(text, name, class_name)
    require(not node.decorator_list, f"unexpected decorator on {name}")
    segment = ast.get_source_segment(text, node, padded=True)
    require(segment is not None, f"no source segment for {name}")
    return textwrap.dedent(segment)


def segment_of(text: str, node: ast.AST, what: str) -> str:
    segment = ast.get_source_segment(text, node, padded=True)
    require(segment is not None, f"no source segment for {what}")
    return textwrap.dedent(segment)


def main_guard(text: str) -> ast.If:
    guards = []
    for node in ast.parse(text).body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"):
            guards.append(node)
    return _single(guards, "__main__ guard")


def compile_function(source: str, name: str, namespace: dict[str, Any], label: str):
    code = compile(source, f"<extracted:{label}:{name}>", "exec")
    exec(code, namespace)
    function = namespace.get(name)
    require(isinstance(function, types.FunctionType), f"extracted {name} is not a function")
    return function


def dump_stmt(snippet: str) -> str:
    return ast.dump(_single(ast.parse(textwrap.dedent(snippet)).body, "snippet statement"))


def dump_expr(snippet: str) -> str:
    return ast.dump(ast.parse(snippet, mode="eval").body)


# ---------------------------------------------------------------------------
# Candidate fragments
# ---------------------------------------------------------------------------

def case_function(which: str = "candidate") -> ast.FunctionDef:
    return top_function(subject_text(f"{which}/np_runner_entry.py"), CASE_FUNCTION)


def observer_try() -> ast.Try:
    fn = case_function()
    tries = [n for n in ast.walk(fn) if isinstance(n, ast.Try)
             and any(isinstance(s, ast.Assign) and len(s.targets) == 1
                     and isinstance(s.targets[0], ast.Name) and s.targets[0].id == "restore_worker_observer"
                     for s in n.body)]
    return _single(tries, "observer try")


def status_block(which: str = "candidate") -> ast.If:
    fn = case_function(which)
    want = dump_expr("response.status_code != 200")
    blocks = [n for n in ast.walk(fn) if isinstance(n, ast.If) and ast.dump(n.test) == want]
    return _single(blocks, f"{which} non-200 block")


def chaining_source(which: str = "candidate", mutation: tuple[str, str] | None = None) -> str:
    source = segment_of(subject_text(f"{which}/np_runner_entry.py"), status_block(which), "non-200 block")
    return mutate(source, mutation)


def helper_source(mutation: tuple[str, str] | None = None) -> str:
    return mutate(extract_function(subject_text("candidate/np_runner_entry.py"), HELPER), mutation)


def mutate(source: str, mutation: tuple[str, str] | None) -> str:
    if mutation is not None:
        old, new = mutation
        require(source.count(old) == 1, f"mutation anchor not unique:{old!r}")
        source = source.replace(old, new)
    return source


def install_fn(mutation: tuple[str, str] | None = None):
    # Any/Callable are supplied so annotations resolve whether or not they are deferred.
    namespace: dict[str, Any] = {"Any": Any, "Callable": Callable}
    return compile_function(helper_source(mutation), HELPER, namespace, "candidate")


# ---------------------------------------------------------------------------
# Exact sys.modules sandbox for the fake dispatch module
# ---------------------------------------------------------------------------

class ModuleSandbox:
    """Install fake app/app.services/dispatch modules; restore exact prior entries."""

    def __init__(self, run_bounded_domain: Callable[..., Any]) -> None:
        self._saved: dict[str, Any] = {}
        self._missing: set[str] = set()
        self.dispatch = types.ModuleType(DISPATCH_MODULE)
        self.dispatch.run_bounded_domain = run_bounded_domain

    def __enter__(self) -> types.ModuleType:
        for name in SANDBOX_NAMES:
            if name in sys.modules:
                self._saved[name] = sys.modules[name]
            else:
                self._missing.add(name)
        app = types.ModuleType("app")
        services = types.ModuleType("app.services")
        app.__path__ = []
        services.__path__ = []
        app.services = services
        services.covering_http_dispatch = self.dispatch
        sys.modules["app"] = app
        sys.modules["app.services"] = services
        sys.modules[DISPATCH_MODULE] = self.dispatch
        return self.dispatch

    def __exit__(self, *exc_info: Any) -> bool:
        for name, module in self._saved.items():
            sys.modules[name] = module
        for name in self._missing:
            sys.modules.pop(name, None)
        self._saved.clear()
        self._missing.clear()
        return False


def sandbox_clean() -> bool:
    return all(name not in sys.modules for name in SANDBOX_NAMES)


# ---------------------------------------------------------------------------
# Fake production exception classes (render calls are recorded, never expected)
# ---------------------------------------------------------------------------

RENDERS: list[str] = []


class _Rendered(Exception):
    def __str__(self) -> str:
        RENDERS.append(type(self).__name__)
        return ""

    def __repr__(self) -> str:
        RENDERS.append(type(self).__name__)
        return ""


class JoinedTLSVerifyFault(_Rendered):
    pass


class CleanupNoise(_Rendered):
    pass


class CoveringRootOutcomeUnknown(_Rendered):
    pass


class OperatorAbort(BaseException):
    def __str__(self) -> str:
        RENDERS.append("OperatorAbort")
        return ""


class SuiteStop(Exception):
    pass


def connector_shaped_domain(record: dict[str, list[Any]]) -> Callable[..., Any]:
    """Fake run_bounded_domain shaped like covering_role_connector's conversion:
    original fault -> swallowed teardown noise -> CoveringRootOutcomeUnknown() from None."""

    def fake_run_bounded_domain(*args: Any, **kwargs: Any) -> Any:
        token = SECRET  # noqa: F841 - a secret local that must never be exported
        try:
            fault = JoinedTLSVerifyFault(f"verify failed {SECRET}")
            record["faults"].append(fault)
            raise fault
        except JoinedTLSVerifyFault:
            try:
                raise CleanupNoise(SECRET)
            except CleanupNoise:
                pass
            unknown = CoveringRootOutcomeUnknown()
            record["unknowns"].append(unknown)
            raise unknown from None

    return fake_run_bounded_domain


# ---------------------------------------------------------------------------
# Oracles over the ACTUAL extracted helper (shared by controls and mutants)
# ---------------------------------------------------------------------------

def oracle_success(install: Callable[..., Any]) -> dict[str, str]:
    cases = {}
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    sentinel = object()

    def original(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return sentinel

    a, b, c = object(), object(), object()
    require(sandbox_clean(), "sandbox precondition")
    with ModuleSandbox(original) as dispatch:
        captured: list[BaseException] = []
        restore = install(captured)
        require(dispatch.run_bounded_domain is not original and callable(dispatch.run_bounded_domain),
                "installed observer")
        cases["installed"] = "PASS"
        result = dispatch.run_bounded_domain(a, b, port=c)
        require(result is sentinel, "result identity")
        cases["result_identity"] = "PASS"
        require(len(calls) == 1 and len(calls[0][0]) == 2 and calls[0][0][0] is a and calls[0][0][1] is b
                and set(calls[0][1]) == {"port"} and calls[0][1]["port"] is c, "argument identity")
        cases["argument_identity"] = "PASS"
        require(captured == [], "nothing captured on success")
        cases["nothing_captured"] = "PASS"
        restore()
        require(dispatch.run_bounded_domain is original, "restore identity")
        cases["restore_identity"] = "PASS"
        restore()
        require(dispatch.run_bounded_domain is original, "restore idempotent")
        cases["restore_idempotent"] = "PASS"
    require(sandbox_clean(), "sandbox restored")
    cases["sandbox_restored"] = "PASS"
    return cases


def oracle_exception(install: Callable[..., Any]) -> dict[str, str]:
    cases = {}
    record: dict[str, list[Any]] = {"faults": [], "unknowns": []}
    connector = connector_shaped_domain(record)
    abort = OperatorAbort()

    def raise_abort() -> Any:
        raise abort

    queue: list[Callable[[], Any]] = [connector, raise_abort]

    def original(*args: Any, **kwargs: Any) -> Any:
        return queue.pop(0)()

    del RENDERS[:]
    require(sandbox_clean(), "sandbox precondition")
    with ModuleSandbox(original) as dispatch:
        captured: list[BaseException] = []
        restore = install(captured)
        got: BaseException | None = None
        try:
            dispatch.run_bounded_domain("request", "body")
        except BaseException as exc:  # noqa: BLE001 - identity is the point
            got = exc
        require(got is not None, "exception swallowed")
        require(got is record["unknowns"][0], "exception identity")
        cases["exception_identity"] = "PASS"
        require(len(captured) == 1 and captured[0] is got, "captured identity")
        cases["captured_identity"] = "PASS"
        require(got.__cause__ is None and got.__suppress_context__ is True
                and got.__context__ is record["faults"][0], "chain unchanged")
        cases["chain_unchanged"] = "PASS"
        got2: BaseException | None = None
        try:
            dispatch.run_bounded_domain()
        except BaseException as exc:  # noqa: BLE001
            got2 = exc
        require(got2 is abort, "base exception identity")
        cases["base_exception_reraised"] = "PASS"
        require(len(captured) == 1 and captured[0] is got, "bound one")
        cases["bound_one"] = "PASS"
        restore()
        require(dispatch.run_bounded_domain is original, "restore identity")
        cases["restore_identity"] = "PASS"
    require(RENDERS == [], "observer rendered an exception")
    cases["no_formatting"] = "PASS"
    require(sandbox_clean(), "sandbox restored")
    cases["sandbox_restored"] = "PASS"
    return cases


def run_status_block(code: Any, status: int, captured: list[BaseException]) -> BaseException | None:
    namespace: dict[str, Any] = {"response": types.SimpleNamespace(status_code=status),
                                 "worker_exceptions": captured, "SuiteStop": SuiteStop}
    try:
        exec(code, namespace)
    except SuiteStop as stop:
        return stop
    return None


def oracle_chaining(source: str) -> dict[str, str]:
    cases = {}
    code = compile(source, "<extracted:candidate:non-200>", "exec")
    w1, w2 = CoveringRootOutcomeUnknown(), CoveringRootOutcomeUnknown()
    stop = run_status_block(code, 503, [w1])
    require(stop is not None and stop.__cause__ is w1 and stop.__suppress_context__ is True,
            "cause not the captured worker exception")
    require(stop.args == ("covering-refresh status:503",), "message changed")
    cases["chained_cause"] = "PASS"
    stop = run_status_block(code, 503, [w1, w2])
    require(stop is not None and stop.__cause__ is w1, "cause not the first captured")
    cases["first_captured_only"] = "PASS"
    stop = run_status_block(code, 401, [])
    require(stop is not None and stop.__cause__ is None and stop.__suppress_context__ is False
            and stop.__context__ is None, "fallback chained")
    require(stop.args == ("covering-refresh status:401",), "fallback message changed")
    cases["unchained_fallback"] = "PASS"
    require(run_status_block(code, 200, []) is None and run_status_block(code, 200, [w1]) is None,
            "status 200 raised")
    cases["status_200_no_raise"] = "PASS"
    return cases


# ---------------------------------------------------------------------------
# Fake filesystem, tracebacks and exceptions for the producer and host validator
# ---------------------------------------------------------------------------

class FakePathBase:
    _fs: dict[str, bytes] = {}

    def __init__(self, value: Any) -> None:
        if isinstance(value, FakePathBase):
            value = value._p
        if not isinstance(value, str):
            raise TypeError("fake path requires str")
        self._p = value

    def _new(self, value: str) -> "FakePathBase":
        return type(self)(value)

    def resolve(self) -> "FakePathBase":
        value = self._p
        if not value.startswith("/"):
            value = "/cwd/" + value
        value = posixpath.normpath(value)
        while value.startswith("//"):
            value = value[1:]
        return self._new(value)

    def __truediv__(self, other: Any) -> "FakePathBase":
        if not isinstance(other, str):
            raise TypeError("fake path join requires str")
        return self._new(self._p.rstrip("/") + "/" + other)

    def _read(self) -> bytes:
        key = posixpath.normpath(self._p)
        if key not in self._fs:
            raise FileNotFoundError("fake path absent")
        return self._fs[key]

    def read_bytes(self) -> bytes:
        return self._read()

    def read_text(self, *args: Any, **kwargs: Any) -> str:
        return self._read().decode("utf-8")

    def is_relative_to(self, other: "FakePathBase") -> bool:
        base = other._p.rstrip("/")
        return self._p == base or self._p.startswith(base + "/")

    def relative_to(self, other: "FakePathBase") -> "FakePathBase":
        if not self.is_relative_to(other):
            raise ValueError("fake path not relative")
        base = other._p.rstrip("/")
        rest = self._p[len(base):].lstrip("/")
        return self._new(rest or ".")

    def as_posix(self) -> str:
        return self._p

    def __str__(self) -> str:
        return self._p


def make_path_class(fs: dict[str, bytes]) -> type:
    return type("FakePath", (FakePathBase,), {"_fs": fs})


def source_lines(count: int, marker: str = "owned") -> bytes:
    return "".join(f"x_{marker}_{n} = {n}\n" for n in range(1, count + 1)).encode("utf-8")


def make_fs(owned_files: dict[str, bytes]) -> dict[str, bytes]:
    fs: dict[str, bytes] = {}
    rows = []
    for rel, data in owned_files.items():
        fs[FAKE_ROOT + "/" + rel] = data
        rows.append(f"{sha256_bytes(data)}  {rel}")
    fs[FAKE_MANIFEST] = ("\n".join(rows) + "\n").encode("utf-8")
    return fs


class FakeCode:
    def __init__(self, filename: str) -> None:
        self.co_filename = filename


class FakeFrame:
    def __init__(self, filename: str, locals_: dict[str, Any] | None = None) -> None:
        self.f_code = FakeCode(filename)
        self.f_locals = locals_ or {}


class FakeTraceback:
    def __init__(self, filename: str, lineno: int, nxt: "FakeTraceback | None",
                 locals_: dict[str, Any] | None = None) -> None:
        self.tb_frame = FakeFrame(filename, locals_)
        self.tb_lineno = lineno
        self.tb_next = nxt


def build_tb(frames: list[tuple[str, int]], locals_: dict[str, Any] | None = None):
    tb = None
    for filename, lineno in reversed(frames):
        tb = FakeTraceback(filename, lineno, tb, locals_)
    return tb


def make_exc(name: str, frames: list[tuple[str, int]], *, cause: Any = None, context: Any = None,
             suppress: bool = False, args: tuple = (), locals_: dict[str, Any] | None = None) -> Any:
    obj = type(name, (), {})()
    obj.args = args
    obj.__traceback__ = build_tb(frames, locals_)
    obj.__cause__ = cause
    obj.__context__ = context
    obj.__suppress_context__ = suppress
    return obj


def owned(rel: str) -> str:
    return FAKE_ROOT + "/" + rel


def producer(fs: dict[str, bytes]):
    path_cls = make_path_class(fs)
    namespace: dict[str, Any] = {"ROOT": path_cls(FAKE_ROOT), "Path": path_cls,
                                 "hashlib": hashlib, "json": json}
    source = extract_function(subject_text("candidate/np_runner_entry.py"), "stop_payload")
    return compile_function(source, "stop_payload", namespace, "candidate")


def envelope(payload: dict[str, Any]) -> bytes:
    # The unchanged candidate __main__ handler expression (guard identity in PRESERVED).
    return (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")


def host_accepts(fs: dict[str, bytes], payload: dict[str, Any]) -> dict[str, Any]:
    text = subject_text("host/docker_transport.py")
    path_cls = make_path_class(fs)
    namespace: dict[str, Any] = {"Path": path_cls, "re": re, "json": json, "hashlib": hashlib}
    compile_function(extract_function(text, "digest"), "digest", namespace, "host")
    record_fn = compile_function(extract_function(text, "_record_runner_stop", "DockerOps"),
                                 "_record_runner_stop", namespace, "host")
    id_fn = compile_function(extract_function(text, "_id", "DockerOps"), "_id", namespace, "host")
    ops = type("FakeDockerOps", (), {"_record_runner_stop": record_fn, "_id": id_fn})()
    ops.c = {"source_directory": FAKE_ROOT, "manifest": FAKE_MANIFEST}
    ops.ids = {"runner": RUNNER_ID}
    records: list[tuple[str, Any]] = []
    ops.record = lambda event, data: records.append((event, data))
    ops._record_runner_stop(OWNED_ARGS, envelope(payload), 125)
    require(len(records) == 1 and records[0][0] == "runner_stop", "host did not accept")
    safe = records[0][1]
    require(safe["status"] == "STOP" and safe["kind"] == payload["kind"] and safe["cli_exit_code"] == 125,
            "host safe record mismatch")
    require(safe.get("diagnostic") == payload.get("diagnostic"), "host did not retain exact diagnostic")
    return safe


def diag(payload: dict[str, Any]) -> dict[str, Any]:
    require(set(payload) == {"status", "kind", "diagnostic"}, "diagnostic envelope expected")
    require(payload["status"] == "STOP", "status must be STOP")
    d = payload["diagnostic"]
    require(set(d) == {"version", "exceptions", "truncated"} and d["version"] == 1, "diagnostic schema")
    return d


def private(data: bytes) -> bool:
    return all(marker not in data for marker in
               (SECRET.encode(), b"verify failed", b"covering-refresh", b"status:", b"503", b"token"))


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def check_preserved_outside_change() -> dict[str, Any]:
    cases = {}
    source_text = subject_text("source/np_runner_entry.py")
    candidate_text = subject_text("candidate/np_runner_entry.py")
    source_nodes = ast.parse(source_text).body
    candidate_nodes = ast.parse(candidate_text).body

    def named(node: ast.AST, name: str) -> bool:
        return isinstance(node, ast.FunctionDef) and node.name == name

    helpers = [i for i, n in enumerate(candidate_nodes) if named(n, HELPER)]
    index = _single(helpers, "new helper")
    require(named(candidate_nodes[index + 1], "_install_token_terminal_observer"), "helper placement")
    kept_source = [ast.dump(n) for n in source_nodes if not named(n, CASE_FUNCTION)]
    kept_candidate = [ast.dump(n) for n in candidate_nodes
                      if not named(n, CASE_FUNCTION) and not named(n, HELPER)]
    require(len(source_nodes) + 1 == len(candidate_nodes), "top-level node count")
    require(kept_source == kept_candidate, "top-level nodes changed outside the case function")
    cases["top_level_nodes_identical"] = "PASS"
    require(extract_function(source_text, "stop_payload") == extract_function(candidate_text, "stop_payload"),
            "stop_payload changed")
    cases["stop_payload_identical"] = "PASS"
    require(ast.dump(main_guard(source_text)) == ast.dump(main_guard(candidate_text)), "__main__ guard changed")
    cases["main_guard_identical"] = "PASS"
    require(_DIFF_STATS.get("removed") == 0 and _DIFF_STATS.get("added") == 41, "diff not purely additive +41")
    cases["diff_purely_additive"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_text_identity", "observed": "PASS"}


def check_production_boundary_structure() -> dict[str, Any]:
    cases = {}
    dispatch_text = subject_text("production/covering_http_dispatch.py")
    tree = ast.parse(dispatch_text)
    worker = top_function(dispatch_text, "_worker")
    last = worker.body[-1]
    require(isinstance(last, ast.Return) and isinstance(last.value, ast.Call)
            and isinstance(last.value.func, ast.Name) and last.value.func.id == "run_bounded_domain",
            "worker does not return run_bounded_domain(...) by global name")
    local_bindings = [n for n in ast.walk(worker)
                      if (isinstance(n, ast.Name) and n.id == "run_bounded_domain" and isinstance(n.ctx, ast.Store))
                      or (isinstance(n, ast.alias) and (n.asname or n.name) == "run_bounded_domain")
                      or (isinstance(n, ast.Global))]
    require(local_bindings == [], "worker binds run_bounded_domain locally")
    cases["worker_global_lookup"] = "PASS"
    imports = [n for n in tree.body if isinstance(n, ast.ImportFrom)
               and any((a.asname or a.name) == "run_bounded_domain" for a in n.names)]
    imp = _single(imports, "run_bounded_domain import")
    require(imp.module == "app.services.covering_domain_dispatch" and imp.level == 0, "import source")
    other = [n for n in tree.body
             if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == "run_bounded_domain")
             or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "run_bounded_domain"
                                                   for t in n.targets))]
    require(other == [], "second module-level binding")
    cases["module_level_import"] = "PASS"

    connector_text = subject_text("production/covering_role_connector.py")
    raises = [n for n in ast.walk(ast.parse(connector_text)) if isinstance(n, ast.Raise)
              and isinstance(n.exc, ast.Call) and isinstance(n.exc.func, ast.Name)
              and n.exc.func.id == "CoveringRootOutcomeUnknown" and not n.exc.args
              and isinstance(n.cause, ast.Constant) and n.cause.value is None]
    require(sorted(n.lineno for n in raises) == [74, 106, 150, 204], "connector from-None conversions changed")
    cases["connector_from_none_conversions"] = "PASS"

    dispatcher = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "dispatch_covering_http"]
    dispatcher_node = _single(dispatcher, "dispatch_covering_http")
    handlers = [h for h in ast.walk(dispatcher_node) if isinstance(h, ast.ExceptHandler)
                and isinstance(h.type, ast.Tuple)
                and any(isinstance(e, ast.Name) and e.id == "CoveringRootOutcomeUnknown" for e in h.type.elts)]
    handler = _single(handlers, "unknown handler")
    raise_node = _single([s for s in handler.body if isinstance(s, ast.Raise)], "unknown raise")
    require(isinstance(raise_node.exc, ast.Call) and isinstance(raise_node.exc.func, ast.Name)
            and raise_node.exc.func.id == "ApiError" and isinstance(raise_node.exc.args[0], ast.Constant)
            and raise_node.exc.args[0].value == 503 and isinstance(raise_node.cause, ast.Constant)
            and raise_node.cause.value is None, "unknown not mapped to 503 from None")
    cases["dispatch_maps_unknown_to_503"] = "PASS"

    helper = top_function(subject_text("candidate/np_runner_entry.py"), HELPER)
    froms = [n for n in ast.walk(helper) if isinstance(n, ast.ImportFrom)]
    target = _single(froms, "helper import")
    require(target.module == "app.services" and target.level == 0
            and [(a.name, a.asname) for a in target.names] == [("covering_http_dispatch", "dispatch_module")],
            "helper import target")
    stores = [n for n in ast.walk(helper) if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)]
    require(len(stores) == 2 and all(isinstance(s.value, ast.Name) and s.value.id == "dispatch_module"
                                     and s.attr == "run_bounded_domain" for s in stores),
            "helper swaps anything other than dispatch_module.run_bounded_domain")
    cases["observer_targets_dispatch_global"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


def check_observer_success_identity() -> dict[str, Any]:
    cases = oracle_success(install_fn())
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_observer_exception_identity() -> dict[str, Any]:
    cases = oracle_exception(install_fn())
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_restore_wiring() -> dict[str, Any]:
    cases = {}
    text = subject_text("candidate/np_runner_entry.py")
    fn = case_function()
    node = observer_try()
    outer = _single([s for s in fn.body if isinstance(s, ast.Try) and any(n is node for n in ast.walk(s))],
                    "outer case try")
    want_locals = {dump_stmt("worker_exceptions: list[BaseException] = []"),
                   dump_stmt("restore_worker_observer: Callable[[], None] | None = None")}
    positions = [i for i, s in enumerate(fn.body) if isinstance(s, ast.AnnAssign) and ast.dump(s) in want_locals]
    require(len(positions) == 2 and max(positions) < fn.body.index(outer), "locals not initialized before try")
    cases["locals_initialized"] = "PASS"
    require(ast.dump(node.body[0]) == dump_stmt(
        "restore_worker_observer = _install_worker_exception_observer(worker_exceptions)"),
        "install not first in try")
    cases["install_first_in_try"] = "PASS"
    restore_if = ("if restore_worker_observer is not None:\n"
                  "    restore_worker_observer()\n"
                  "    restore_worker_observer = None\n")
    require(not node.handlers and not node.orelse and len(node.finalbody) >= 2, "try shape")
    require(ast.dump(node.finalbody[0]) == dump_stmt(restore_if), "restore not first in finally")
    require(ast.dump(node.finalbody[1]) == dump_stmt("CoveringHTTP.__init__ = real_init"), "finally order")
    cases["restore_first_in_finally"] = "PASS"
    calls = [n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == HELPER]
    require(len(calls) == 1, "install called other than once")
    cases["single_install_call"] = "PASS"
    code = compile(segment_of(text, node.finalbody[0], "restore block"), "<extracted:candidate:restore>", "exec")
    count: list[int] = []
    namespace: dict[str, Any] = {"restore_worker_observer": lambda: count.append(1)}
    exec(code, namespace)
    require(count == [1] and namespace["restore_worker_observer"] is None, "restore block behavior")
    exec(code, namespace)
    require(count == [1], "restore block reran")
    cases["restore_block_behavior"] = "PASS"
    require(status_block().lineno > node.end_lineno, "non-200 block not after restore")
    cases["chaining_after_restore"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source_plus_extracted_block", "observed": "PASS"}


def check_chaining_wiring() -> dict[str, Any]:
    cases = oracle_chaining(chaining_source())
    candidate_block = status_block()
    source_block = status_block("source")
    require(len(source_block.body) == 1 and ast.dump(candidate_block.body[-1]) == ast.dump(source_block.body[0]),
            "fallback raise differs from the executed source raise")
    stop = run_status_block(compile(chaining_source("source"), "<extracted:source:non-200>", "exec"), 503, [])
    require(stop is not None and stop.args == ("covering-refresh status:503",), "source message")
    cases["fallback_raise_unchanged"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_producer_host_end_to_end() -> dict[str, Any]:
    cases = {}
    # 1. Real exception objects through the ACTUAL observer and ACTUAL non-200 block.
    record: dict[str, list[Any]] = {"faults": [], "unknowns": []}
    require(sandbox_clean(), "sandbox precondition")
    with ModuleSandbox(connector_shaped_domain(record)) as dispatch:
        captured: list[BaseException] = []
        restore = install_fn()(captured)
        try:
            dispatch.run_bounded_domain("request", "body")
        except CoveringRootOutcomeUnknown:
            pass
        restore()
    require(sandbox_clean(), "sandbox restored")
    stop = run_status_block(compile(chaining_source(), "<extracted:candidate:non-200>", "exec"), 503, captured)
    require(stop is not None, "no SuiteStop")
    fs = make_fs({"fixture/np_runner_entry.py": source_lines(20, "r")})
    payload = producer(fs)(stop)
    d = diag(payload)
    require([e["kind"] for e in d["exceptions"]] == ["SuiteStop", "CoveringRootOutcomeUnknown",
                                                      "JoinedTLSVerifyFault"], "real chain kinds")
    require(all(e["frames"] == [] for e in d["exceptions"]) and d["truncated"] is True,
            "checker frames must be non-owned")
    data = envelope(payload)
    require(private(data), "real chain leaked content")
    host_accepts(fs, payload)
    cases["real_chain_through_observer"] = "PASS"

    # 2. Owned production frames via suppressed context, through producer and host.
    rels = {"fixture/np_runner_entry.py": 1000, "api/app/services/covering_role_connector.py": 200,
            "api/app/services/covering_joined_https.py": 60, "api/app/services/covering_http_transport.py": 30}
    fs = make_fs({rel: source_lines(n, rel.rsplit("/", 1)[-1][:-3]) for rel, n in rels.items()})
    secret_locals = {"token": SECRET, "body": f"refresh_token={SECRET}"}

    def chain(fault_frames: list[tuple[str, int]], fault_context: Any = None) -> Any:
        fault = make_exc("JoinedTLSVerifyFault", fault_frames, context=fault_context,
                         args=(f"verify failed {SECRET}",), locals_=secret_locals)
        unknown = make_exc("CoveringRootOutcomeUnknown",
                           [(owned("api/app/services/covering_role_connector.py"), 150)],
                           context=fault, suppress=True, locals_=secret_locals)
        return make_exc("SuiteStop", [(owned("fixture/np_runner_entry.py"), 981)], cause=unknown,
                        args=("covering-refresh status:503",), locals_=secret_locals)

    payload = producer(fs)(chain([(owned("api/app/services/covering_http_transport.py"), 12),
                                  (owned("api/app/services/covering_joined_https.py"), 40)]))
    d = diag(payload)
    require(d["exceptions"] == [
        {"kind": "SuiteStop", "frames": [{"path": "fixture/np_runner_entry.py", "line": 981}]},
        {"kind": "CoveringRootOutcomeUnknown",
         "frames": [{"path": "api/app/services/covering_role_connector.py", "line": 150}]},
        {"kind": "JoinedTLSVerifyFault",
         "frames": [{"path": "api/app/services/covering_http_transport.py", "line": 12},
                    {"path": "api/app/services/covering_joined_https.py", "line": 40}]},
    ] and d["truncated"] is False, "owned production frames")
    host_accepts(fs, payload)
    cases["owned_production_frames"] = "PASS"

    payload = producer(fs)(chain([("/usr/lib/python3.11/ssl.py", 900),
                                  (owned("api/app/services/covering_joined_https.py"), 40)]))
    d = diag(payload)
    require(d["exceptions"][2]["frames"] == [{"path": "api/app/services/covering_joined_https.py", "line": 40}]
            and d["truncated"] is True, "unowned frame not dropped")
    host_accepts(fs, payload)
    cases["unowned_frames_dropped"] = "PASS"

    deeper = make_exc("OSError", [(owned("api/app/services/covering_joined_https.py"), 7)])
    payload = producer(fs)(chain([(owned("api/app/services/covering_joined_https.py"), 40)], deeper))
    d = diag(payload)
    require(len(d["exceptions"]) == 3 and d["truncated"] is True, "deeper chain not capped at 3")
    host_accepts(fs, payload)
    cases["deeper_chain_capped"] = "PASS"

    data = envelope(payload)
    require(private(data) and len(data) <= 4096, "privacy envelope")
    for entry in d["exceptions"]:
        require(set(entry) == {"kind", "frames"}, "exception keys")
        for frame in entry["frames"]:
            require(set(frame) == {"path", "line"} and type(frame["line"]) is int, "frame keys")
    cases["privacy_envelope"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_producer_and_host_fake", "observed": "PASS"}


def _expect_detected(name: str, action: Callable[[], Any], message_prefix: str) -> str:
    """A mutant counts as detected only by the specific oracle that targets it."""
    try:
        action()
    except WitnessFailure as exc:
        if not str(exc).startswith(message_prefix):
            raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
        return "DETECTED"
    except BaseException:  # noqa: BLE001
        raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
    raise WitnessFailure(f"mutant survived:{name}")


def check_actual_source_mutants() -> dict[str, Any]:
    reraise = "                captured.append(exc)\n            raise\n"
    mutants = {
        "replacement_reraise": (lambda: oracle_exception(install_fn((reraise, reraise.replace(
            "raise\n", "raise RuntimeError(\"observer\") from exc\n"))))), "exception identity"),
        "swallowed": (lambda: oracle_exception(install_fn((reraise, reraise.replace(
            "raise\n", "return None\n"))))), "exception swallowed"),
        "no_restore": (lambda: oracle_success(install_fn((
            "    def restore() -> None:\n        dispatch_module.run_bounded_domain = original\n",
            "    def restore() -> None:\n        pass\n")))), "restore identity"),
        "unbounded_capture": (lambda: oracle_exception(install_fn(("if not captured:", "if True:")))),
                              "bound one"),
        "chaining_removed": (lambda: oracle_chaining(chaining_source(mutation=(
            ") from worker_failure", ")")))), "cause not the captured worker exception"),
    }
    results = {name: _expect_detected(name, action, prefix) for name, (action, prefix) in mutants.items()}
    require(sandbox_clean(), "sandbox restored after mutants")
    return {"mutants": results, "control_kind": "actual_source_mutant", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

def exclusive_write_result(payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > MAX_RESULT:
        raise WitnessFailure("result exceeds byte cap")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(str(RESULT), flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
    finally:
        os.close(fd)


def run_checks() -> dict[str, Any]:
    if RESULT.exists():
        raise WitnessFailure("existing result; no replay")
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    require(expected.get("kind") == "worker-observer-diagnostic-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRESERVED-OUTSIDE-CHANGE": check_preserved_outside_change,
        "PRODUCTION-BOUNDARY-STRUCTURE": check_production_boundary_structure,
        "OBSERVER-SUCCESS-IDENTITY": check_observer_success_identity,
        "OBSERVER-EXCEPTION-IDENTITY": check_observer_exception_identity,
        "RESTORE-WIRING": check_restore_wiring,
        "CHAINING-WIRING": check_chaining_wiring,
        "PRODUCER-HOST-END-TO-END": check_producer_host_end_to_end,
        "ACTUAL-SOURCE-MUTANTS": check_actual_source_mutants,
    }
    require(tuple(functions) == CONTROL_IDS, "internal control order")
    nested_expected = expected.get("nested_case_ids") or {}
    controls = {}
    for control_id, function in functions.items():
        try:
            controls[control_id] = function()
        except WitnessFailure:
            raise
        except Exception as exc:
            raise WitnessFailure(f"{control_id}:{type(exc).__name__}") from None
        inner = controls[control_id].get("cases") or controls[control_id].get("mutants")
        if control_id in nested_expected:
            require(inner is not None and list(inner) == list(nested_expected[control_id]),
                    f"nested inventory mismatch:{control_id}")
    require(set(nested_expected) <= set(CONTROL_IDS), "EXPECTED nested keys")
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    nested = sum(len(v.get("cases") or v.get("mutants") or {"_": 1}) for v in controls.values())
    return {
        "kind": "fake-native-provider-structural-result",
        "packet": PACKET_NAME,
        "executed": True,
        "launch_authorized": False,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        "native_proof": False,
        "controls": controls,
        "control_ids_in_order": list(controls.keys()),
        "passed": len(controls) - len(failed),
        "failed": len(failed),
        "failed_controls": failed,
        "nested_predicates": nested,
    }


def main() -> int:
    try:
        payload = run_checks()
    except WitnessFailure as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 125
    exclusive_write_result(payload)
    if payload["failed"] != 0:
        print(f"STOP: controls failed:{payload['failed_controls']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
