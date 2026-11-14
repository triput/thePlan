#!/usr/bin/env python3
"""HELD fake-only checker for the native-provider runner STOP diagnostic successor.

Matt, 2026-11-12. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so that the byte-identical,
previously reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

The controls exercise ACTUAL extracted source text from raw-pinned subject copies:
  - candidate stop_payload (np_runner_entry.py 40A1BA8E...)
  - original and candidate __main__ STOP handlers (7FBDCAEE... / 40A1BA8E...)
  - immutable host validator DockerOps._record_runner_stop + _id + digest
    (docker_transport.py 7F7EA820...)
All of them run against an in-memory fake filesystem, fake traceback chains and fake
exception objects.

Imports are standard library only. There are no app or vendor imports, no sockets,
TLS, PKI, Docker, database, child processes or network, and no real fixture
filesystem access inside controls. Subject bytes are read once from this packet and
hash-verified. The only write is the exclusive result file.

Proof scope: fake behavior of the extracted blocks only. Native runner attach, real
traceback paths in the container, the real host Docker failure path and the stopped
v3 raise-site attribution all remain unproved.
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
from typing import Any


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-native-provider-runner-diagnostic-fake-prep-matt-v1"

SUBJECT_PINS = {
    "original/np_runner_entry.py": "7FBDCAEE078CDBE3F695191ABBED93B827A31EB6FED55DCD839AB43A84355FF5",
    "candidate/np_runner_entry.py": "40A1BA8E9C3E320DD7DF9E06102CC29C0E1AFAAD4213EC0FECF9FE34455BF73F",
    "host/docker_transport.py": "7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53",
    "producer/runner_entry.py": "2A4602CCDFA68787697ED4FD472B3BEA41FD9FC31F8F808C409339140C81FA3E",
    "diff/V3-Proposed-Runner-Diagnostic.diff": "F6135717D3DC46EB1082A19B69ECDB3602F246EFFF47FFA562E9AB1A6ECF9832",
}

CONTROL_IDS = (
    "SUBJECT-PINS",
    "DIFF-REDERIVATION",
    "PRODUCER-PRECEDENT-IDENTITY",
    "DECLARATION-MATCHES-BEHAVIOR",
    "ORIGINAL-STATUS-KIND-ONLY",
    "CANDIDATE-HAPPY-PATH",
    "CAUSE-CONTEXT-CYCLE",
    "OWNED-FRAME-REJECTIONS",
    "BOUNDS-AND-TRUNCATION",
    "DIAGNOSTIC-FALLBACK",
    "PRIVACY-ENVELOPE",
    "UNCHANGED-STOP-EXIT",
    "HOST-VALIDATOR-EXTRACTED",
    "MUTANT-DETECTION",
)

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
        require(b"\r" not in data, f"subject not LF:{rel}")
        _SUBJECT_TEXT[rel] = data.decode("utf-8")
        observed[rel] = digest
    return {"subjects": observed, "control_kind": "raw_pin", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Literal unified-diff re-derivation (pure text; no patch tool)
# ---------------------------------------------------------------------------

_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*")


def apply_unified(original: str, diff: str) -> tuple[str, list[str], int]:
    src = original.split("\n")
    lines = diff.split("\n")
    out: list[str] = []
    files: list[str] = []
    pos = 0
    i = 0
    hunks = 0
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
            elif tag == "+":
                out.append(body)
                seen_new += 1
            else:
                raise WitnessFailure("unexpected hunk line")
            i += 1
        require((seen_old, seen_new) == (old_len, new_len), "hunk length mismatch")
        hunks += 1
    out.extend(src[pos:])
    return "\n".join(out), files, hunks


def check_diff_rederivation() -> dict[str, Any]:
    original = subject_text("original/np_runner_entry.py")
    candidate = subject_text("candidate/np_runner_entry.py")
    diff = subject_text("diff/V3-Proposed-Runner-Diagnostic.diff")
    derived, files, hunks = apply_unified(original, diff)
    require(files == ["a/payload/fixture/np_runner_entry.py", "b/payload/fixture/np_runner_entry.py"],
            "diff touches unexpected files")
    require(hunks == 3, "expected exactly three hunks")
    require(derived == candidate, "candidate bytes differ from original + approved diff")
    return {"hunks": hunks, "files": files, "derived_sha256": sha256_bytes(derived.encode("utf-8")),
            "control_kind": "literal_text", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Source extraction helpers (AST used only to locate exact source segments)
# ---------------------------------------------------------------------------

def _single(nodes: list[ast.AST], what: str) -> ast.AST:
    require(len(nodes) == 1, f"expected exactly one {what}, found {len(nodes)}")
    return nodes[0]


def extract_function(text: str, name: str, class_name: str | None = None) -> str:
    tree = ast.parse(text)
    body = tree.body
    if class_name is not None:
        cls = _single([n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name],
                      f"class {class_name}")
        body = cls.body
    node = _single([n for n in body if isinstance(n, ast.FunctionDef) and n.name == name],
                   f"function {name}")
    require(not node.decorator_list, f"unexpected decorator on {name}")
    segment = ast.get_source_segment(text, node, padded=True)
    require(segment is not None, f"no source segment for {name}")
    return textwrap.dedent(segment)


def main_guard(text: str) -> ast.If:
    tree = ast.parse(text)
    guards = []
    for node in tree.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"):
            guards.append(node)
    return _single(guards, "__main__ guard")  # type: ignore[return-value]


def compile_function(source: str, name: str, namespace: dict[str, Any], label: str):
    code = compile(source, f"<extracted:{label}:{name}>", "exec")
    exec(code, namespace)
    function = namespace.get(name)
    require(isinstance(function, types.FunctionType), f"extracted {name} is not a function")
    return function


# ---------------------------------------------------------------------------
# Fake filesystem, paths, tracebacks and exceptions
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


def make_fs(owned: dict[str, bytes], *, manifest_rows: list[str] | None = None,
            extra: dict[str, bytes] | None = None, manifest: bool = True) -> dict[str, bytes]:
    fs: dict[str, bytes] = {}
    rows = []
    for rel, data in owned.items():
        fs[FAKE_ROOT + "/" + rel] = data
        rows.append(f"{sha256_bytes(data)}  {rel}")
    if manifest_rows is not None:
        rows.extend(manifest_rows)
    if extra:
        fs.update(extra)
    if manifest:
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


class CountingTraceback:
    def __init__(self, index: int, visits: set[int], filename: str, nxt: "CountingTraceback | None") -> None:
        self._index = index
        self._visits = visits
        self._frame = FakeFrame(filename)
        self.tb_lineno = 1
        self.tb_next = nxt

    @property
    def tb_frame(self) -> FakeFrame:
        self._visits.add(self._index)
        return self._frame


def build_tb(frames: list[tuple[str, int]], locals_: dict[str, Any] | None = None):
    tb = None
    for filename, lineno in reversed(frames):
        tb = FakeTraceback(filename, lineno, tb, locals_)
    return tb


def make_exc(name: str, frames: list[tuple[str, int]], *, cause: Any = None, context: Any = None,
             args: tuple = (), locals_: dict[str, Any] | None = None) -> Any:
    cls = type(name, (), {})
    obj = cls()
    obj.args = args
    obj.__traceback__ = build_tb(frames, locals_)
    obj.__cause__ = cause
    obj.__context__ = context
    return obj


def owned(rel: str) -> str:
    return FAKE_ROOT + "/" + rel


# ---------------------------------------------------------------------------
# Extracted candidate producer and host validator under fakes
# ---------------------------------------------------------------------------

def stop_payload_source(mutation: tuple[str, str] | None = None) -> str:
    source = extract_function(subject_text("candidate/np_runner_entry.py"), "stop_payload")
    if mutation is not None:
        old, new = mutation
        require(source.count(old) == 1, f"mutation anchor not unique:{old!r}")
        source = source.replace(old, new)
    return source


def producer(fs: dict[str, bytes], mutation: tuple[str, str] | None = None):
    path_cls = make_path_class(fs)
    namespace: dict[str, Any] = {"ROOT": path_cls(FAKE_ROOT), "Path": path_cls,
                                 "hashlib": hashlib, "json": json}
    return compile_function(stop_payload_source(mutation), "stop_payload", namespace, "candidate")


def envelope(payload: dict[str, Any]) -> bytes:
    # Mirrors the candidate handler expression verified in UNCHANGED-STOP-EXIT.
    return (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")


def host(fs: dict[str, bytes]):
    text = subject_text("host/docker_transport.py")
    path_cls = make_path_class(fs)
    namespace: dict[str, Any] = {"Path": path_cls, "re": re, "json": json, "hashlib": hashlib}
    compile_function(extract_function(text, "digest"), "digest", namespace, "host")
    record_fn = compile_function(extract_function(text, "_record_runner_stop", "DockerOps"),
                                 "_record_runner_stop", namespace, "host")
    id_fn = compile_function(extract_function(text, "_id", "DockerOps"), "_id", namespace, "host")
    ops_cls = type("FakeDockerOps", (), {"_record_runner_stop": record_fn, "_id": id_fn})
    ops = ops_cls()
    ops.c = {"source_directory": FAKE_ROOT, "manifest": FAKE_MANIFEST}
    ops.ids = {"runner": RUNNER_ID}
    records: list[tuple[str, Any]] = []
    ops.record = lambda event, data: records.append((event, data))
    return ops, records


def host_outcome(fs: dict[str, bytes], data: bytes, returncode: Any = 125,
                 args: list[str] | None = None) -> list[tuple[str, Any]]:
    ops, records = host(fs)
    ops._record_runner_stop(OWNED_ARGS if args is None else args, data, returncode)
    return records


def host_accepts(fs: dict[str, bytes], payload: dict[str, Any]) -> dict[str, Any]:
    records = host_outcome(fs, envelope(payload))
    require(len(records) == 1 and records[0][0] == "runner_stop", f"host did not accept:{records!r}")
    safe = records[0][1]
    require(safe["status"] == "STOP" and safe["kind"] == payload["kind"] and safe["cli_exit_code"] == 125,
            "host safe record mismatch")
    if "diagnostic" in payload:
        require(safe.get("diagnostic") == payload["diagnostic"], "host did not retain exact diagnostic")
        require("diagnostic_unavailable" not in safe, "unexpected diagnostic_unavailable")
    else:
        require(safe.get("diagnostic_unavailable") is True, "host must mark diagnostic_unavailable")
    return safe


def host_refuses(fs: dict[str, bytes], data: bytes, returncode: Any = 125) -> None:
    records = host_outcome(fs, data, returncode)
    require(records == [("runner_stop_diagnostic_refused", {"code": "INVALID_OR_UNAVAILABLE_STOP_METADATA"})],
            f"host did not refuse:{records!r}")


def diag(payload: dict[str, Any]) -> dict[str, Any]:
    require(set(payload) == {"status", "kind", "diagnostic"}, f"diagnostic envelope expected:{sorted(payload)}")
    require(payload["status"] == "STOP", "status must be STOP")
    d = payload["diagnostic"]
    require(set(d) == {"version", "exceptions", "truncated"} and d["version"] == 1, "diagnostic schema")
    return d


def standard_fs() -> dict[str, bytes]:
    return make_fs({"fixture/owned_a.py": source_lines(20, "a"), "fixture/owned_b.py": source_lines(20, "b")})


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def check_producer_precedent_identity() -> dict[str, Any]:
    candidate = extract_function(subject_text("candidate/np_runner_entry.py"), "stop_payload")
    precedent = extract_function(subject_text("producer/runner_entry.py"), "stop_payload")
    require(candidate == precedent, "candidate stop_payload differs from passed I01/I02 producer")
    return {"stop_payload_sha256": sha256_bytes(candidate.encode("utf-8")),
            "control_kind": "extracted_text_identity", "observed": "PASS"}


def _failure_limits(text: str) -> dict[str, Any]:
    tree = ast.parse(text)
    found = [kw.value for node in ast.walk(tree) if isinstance(node, ast.Call)
             for kw in node.keywords if kw.arg == "failure_evidence_limits"]
    value = _single(found, "failure_evidence_limits keyword")
    return ast.literal_eval(value)


def check_declaration_matches_behavior() -> dict[str, Any]:
    original = _failure_limits(subject_text("original/np_runner_entry.py"))
    candidate = _failure_limits(subject_text("candidate/np_runner_entry.py"))
    require(original["stop_schema"] == ["status", "kind"] and original["includes_traceback"] is False,
            "original declaration changed")
    expected = {
        "stop_schema": ["status", "kind", "diagnostic_optional"],
        "includes_raw_traceback": False,
        "includes_packet_owned_source_locations": True,
        "diagnostic_byte_cap": 4096,
        "diagnostic_exception_cap": 3,
        "diagnostic_frames_per_exception_cap": 8,
        "diagnostic_fallback": "original_status_kind",
        "includes_key_cert_body_credential_bytes": False,
        "provider_pki_summary_on_stop": False,
        "note": "STOP does not inherit success PKI summary; no inferred success",
    }
    require(candidate == expected, "candidate failure_evidence_limits mismatch")
    source = stop_payload_source()
    for literal in ("len(exceptions) < 3", "walked < 128", "len(frames) > 8", "> 4096",
                    "return original"):
        require(source.count(literal) == 1, f"declared bound not found once in producer:{literal}")
    return {"declared": candidate, "control_kind": "static_declaration", "observed": "PASS"}


class FakeStream:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.flushes = 0

    def write(self, value: str) -> int:
        self.writes.append(value)
        return len(value)

    def flush(self) -> None:
        self.flushes += 1


def run_handler(which: str, outcome: Any) -> tuple[Any, FakeStream]:
    """Run the ACTUAL extracted __main__ handler body with a fake main and fake sys."""
    guard = main_guard(subject_text(f"{which}/np_runner_entry.py"))
    module = ast.Module(body=guard.body, type_ignores=[])
    code = compile(module, f"<extracted:{which}:__main__>", "exec")
    stream = FakeStream()

    def fake_main() -> int:
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    namespace: dict[str, Any] = {"main": fake_main, "json": json,
                                 "sys": types.SimpleNamespace(stderr=stream)}
    if which == "candidate":
        namespace["stop_payload"] = producer(standard_fs())
    try:
        exec(code, namespace)
    except SystemExit as exc:
        return exc.code, stream
    raise WitnessFailure("handler did not raise SystemExit")


def check_original_status_kind_only() -> dict[str, Any]:
    code, stream = run_handler("original", RuntimeError(SECRET))
    require(code == 125 and stream.flushes == 1 and len(stream.writes) == 1, "original STOP shape")
    data = stream.writes[0].encode("utf-8")
    require(json.loads(data) == {"status": "STOP", "kind": "RuntimeError"}, "original envelope")
    require(SECRET.encode() not in data, "original leaked message")
    safe = host_accepts(standard_fs(), json.loads(data))
    return {"exit": code, "host_diagnostic_unavailable": safe["diagnostic_unavailable"],
            "control_kind": "extracted_original_handler_plus_host", "observed": "PASS"}


def check_candidate_happy_path() -> dict[str, Any]:
    fs = standard_fs()
    exc = make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 3), (owned("fixture/owned_b.py"), 7)])
    payload = producer(fs)(exc)
    d = diag(payload)
    require(payload["kind"] == "SuiteStop", "primary kind")
    require(d["exceptions"] == [{"kind": "SuiteStop", "frames": [
        {"path": "fixture/owned_a.py", "line": 3}, {"path": "fixture/owned_b.py", "line": 7}]}],
        "happy frames")
    require(d["truncated"] is False, "happy path must not be truncated")
    host_accepts(fs, payload)
    return {"frames": 2, "truncated": False, "host_retained": True,
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_cause_context_cycle() -> dict[str, Any]:
    fs = standard_fs()
    sp = producer(fs)
    cases = {}

    inner = make_exc("ProviderTransportError", [(owned("fixture/owned_b.py"), 5)])
    outer = make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 2)], cause=inner)
    d = diag(sp(outer))
    require([e["kind"] for e in d["exceptions"]] == ["SuiteStop", "ProviderTransportError"], "cause chain")
    require(d["truncated"] is False, "cause chain truncated")
    host_accepts(fs, sp(outer))
    cases["cause"] = "PASS"

    inner = make_exc("KeyError", [(owned("fixture/owned_b.py"), 6)])
    outer = make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 2)], context=inner)
    d = diag(sp(outer))
    require([e["kind"] for e in d["exceptions"]] == ["SuiteStop", "KeyError"], "context-only chain")
    cases["context_only"] = "PASS"

    by_cause = make_exc("ValueError", [(owned("fixture/owned_b.py"), 1)])
    by_context = make_exc("OSError", [(owned("fixture/owned_b.py"), 2)])
    outer = make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 2)], cause=by_cause, context=by_context)
    d = diag(sp(outer))
    require([e["kind"] for e in d["exceptions"]] == ["SuiteStop", "ValueError"], "cause preferred over context")
    cases["cause_preferred"] = "PASS"

    first = make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 4)])
    second = make_exc("RuntimeError", [(owned("fixture/owned_b.py"), 4)], cause=first)
    first.__context__ = second
    d = diag(sp(first))
    require([e["kind"] for e in d["exceptions"]] == ["SuiteStop", "RuntimeError"], "cycle entries")
    require(d["truncated"] is True, "cycle must report truncation")
    host_accepts(fs, sp(first))
    cases["cycle"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def _rejected(fs: dict[str, bytes], frames: list[tuple[str, int]], name: str = "SuiteStop") -> dict[str, Any]:
    payload = producer(fs)(make_exc(name, frames))
    d = diag(payload)
    require(d["exceptions"] == [{"kind": payload["kind"], "frames": []}], "rejected frame retained")
    require(d["truncated"] is True, "rejection must set truncated")
    host_accepts(fs, payload)
    return payload


def check_owned_frame_rejections() -> dict[str, Any]:
    base = {"fixture/owned_a.py": source_lines(10, "a")}
    cases = {}
    fs = make_fs(base, extra={"/elsewhere/fixture/owned_a.py": source_lines(10, "a")})
    _rejected(fs, [("/elsewhere/fixture/owned_a.py", 2)])
    cases["path_outside_root"] = "PASS"

    fs = make_fs(base, extra={owned("fixture/unlisted.py"): source_lines(10, "u")})
    _rejected(fs, [(owned("fixture/unlisted.py"), 2)])
    cases["rel_not_in_manifest"] = "PASS"

    fs = make_fs(base)
    fs[owned("fixture/owned_a.py")] = source_lines(10, "changed")
    _rejected(fs, [(owned("fixture/owned_a.py"), 2)])
    cases["source_hash_mismatch"] = "PASS"

    fs = make_fs(base)
    _rejected(fs, [(owned("fixture/owned_a.py"), 0)])
    cases["line_zero"] = "PASS"
    _rejected(fs, [(owned("fixture/owned_a.py"), 11)])
    cases["line_past_end"] = "PASS"

    data = source_lines(10, "l")
    fs = make_fs({}, manifest_rows=[f"{sha256_bytes(data).lower()}  fixture/lower.py"],
                 extra={owned("fixture/lower.py"): data})
    _rejected(fs, [(owned("fixture/lower.py"), 2)])
    cases["manifest_lowercase_pin"] = "PASS"

    data = source_lines(10, "d")
    fs = make_fs({}, manifest_rows=[f"{sha256_bytes(data)}  fixture/../fixture/dot.py"],
                 extra={owned("fixture/dot.py"): data})
    _rejected(fs, [(owned("fixture/dot.py"), 2)])
    cases["manifest_non_canonical_path"] = "PASS"

    data = source_lines(10, "t")
    fs = make_fs({}, manifest_rows=[f"{sha256_bytes(data)}  fixture/notes.txt"],
                 extra={owned("fixture/notes.txt"): data})
    _rejected(fs, [(owned("fixture/notes.txt"), 2)])
    cases["manifest_non_python"] = "PASS"

    fs = standard_fs()
    for name in ("Weird-Name", "N" * 81, "9Leading"):
        payload = producer(fs)(make_exc(name, [(owned("fixture/owned_a.py"), 1)]))
        d = diag(payload)
        require(payload["kind"] == "Exception" and d["exceptions"][0]["kind"] == "Exception",
                "identifier not sanitized")
        host_accepts(fs, payload)
    cases["identifier_sanitized"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_bounds_and_truncation() -> dict[str, Any]:
    cases = {}
    fs = standard_fs()
    sp = producer(fs)

    chain = None
    for n in range(5):
        chain = make_exc(f"Level{n}", [(owned("fixture/owned_a.py"), n + 1)], cause=chain)
    d = diag(sp(chain))
    require([e["kind"] for e in d["exceptions"]] == ["Level4", "Level3", "Level2"], "exception cap 3")
    require(d["truncated"] is True, "exception cap truncation")
    host_accepts(fs, sp(chain))
    cases["exceptions_gt_3"] = "PASS"

    exc = make_exc("SuiteStop", [(owned("fixture/owned_a.py"), n) for n in range(1, 13)])
    d = diag(sp(exc))
    require([f["line"] for f in d["exceptions"][0]["frames"]] == list(range(5, 13)), "newest 8 frames kept")
    require(d["truncated"] is True, "frame cap truncation")
    host_accepts(fs, sp(exc))
    cases["frames_gt_8"] = "PASS"

    visits: set[int] = set()
    tb = None
    for index in reversed(range(200)):
        tb = CountingTraceback(index, visits, owned("fixture/owned_a.py"), tb)
    exc = make_exc("SuiteStop", [])
    exc.__traceback__ = tb
    d = diag(sp(exc))
    require(visits == set(range(128)), f"walk bound not 128:{len(visits)}")
    require(d["truncated"] is True, "walk cap truncation")
    cases["traceback_walk_gt_128"] = "PASS"

    long_files = {f"fixture/{'p' * 200}{n}.py": source_lines(10, f"p{n}") for n in range(8)}
    fs_long = make_fs(long_files)
    frames = [(owned(rel), 1) for rel in long_files]
    chain = None
    for name in ("Inner", "Middle", "SuiteStop"):
        chain = make_exc(name, frames, cause=chain)
    payload = producer(fs_long)(chain)
    d = diag(payload)
    data = envelope(payload)
    require(len(data) <= 4096, "envelope over 4096 bytes")
    counts = [len(e["frames"]) for e in d["exceptions"]]
    require(len(counts) == 3 and counts[0] < 8 and counts[1:] == [8, 8], f"trim order:{counts}")
    require(d["truncated"] is True, "byte cap truncation")
    host_accepts(fs_long, payload)
    cases["envelope_gt_4096"] = "PASS"
    return {"cases": cases, "frames_after_trim": counts, "control_kind": "extracted_behavior_fake",
            "observed": "PASS"}


def check_diagnostic_fallback() -> dict[str, Any]:
    cases = {}
    fs = make_fs({"fixture/owned_a.py": source_lines(10, "a")}, manifest=False)
    payload = producer(fs)(make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 1)]))
    require(payload == {"status": "STOP", "kind": "SuiteStop"}, "missing manifest fallback")
    host_accepts(fs, payload)
    cases["manifest_missing"] = "PASS"

    fs = make_fs({"fixture/owned_a.py": source_lines(10, "a")}, manifest_rows=["NOSEPARATOR"])
    payload = producer(fs)(make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 1)]))
    require(payload == {"status": "STOP", "kind": "SuiteStop"}, "malformed row fallback")
    cases["manifest_row_malformed"] = "PASS"

    fs = make_fs({}, manifest=False)
    payload = producer(fs)(make_exc("Bad-Name", []))
    require(payload == {"status": "STOP", "kind": "Bad-Name"}, "fallback keeps unsanitized primary kind")
    host_refuses(fs, envelope(payload))
    cases["inherited_exotic_fallback_host_refusal_expected"] = "PASS"
    return {"cases": cases, "inherited_asymmetry_preserved": True,
            "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def check_privacy_envelope() -> dict[str, Any]:
    fs = make_fs({"fixture/owned_a.py": (f"password = '{SECRET}'\n" * 5).encode("utf-8")})
    secret_locals = {"token": SECRET, "sql": f"SELECT {SECRET}"}
    inner = make_exc("OperationalError", [(owned("fixture/owned_a.py"), 2)], args=(f"SELECT {SECRET}",),
                     locals_=secret_locals)
    outer = make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 1)], cause=inner, args=(SECRET,),
                     locals_=secret_locals)
    payload = producer(fs)(outer)
    data = envelope(payload)
    require(SECRET.encode() not in data and b"SELECT" not in data and b"password" not in data,
            "sensitive content in envelope")
    d = diag(payload)
    for entry in d["exceptions"]:
        require(set(entry) == {"kind", "frames"}, "exception keys")
        for frame in entry["frames"]:
            require(set(frame) == {"path", "line"} and type(frame["line"]) is int, "frame keys")
    host_accepts(fs, payload)
    return {"envelope_bytes": len(data), "control_kind": "extracted_behavior_fake", "observed": "PASS"}


def _handler_without_stop(guard: ast.If) -> tuple[str, str]:
    require(len(guard.body) == 2 and isinstance(guard.body[0], ast.Try), "handler layout")
    try_node = guard.body[0]
    require(len(try_node.handlers) == 1, "single except handler")
    handler = try_node.handlers[0]
    stops = [n for n in handler.body if isinstance(n, ast.Assign)
             and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "_stop"]
    stop = _single(stops, "_stop assignment")
    rest = [n for n in handler.body if n is not stop]
    shape = ast.dump(ast.Module(body=[*try_node.body, *rest, guard.body[1]], type_ignores=[]))
    shape += ast.dump(handler.type) + str(handler.name) + ast.dump(guard.test)
    return shape, ast.dump(stop.value)


def check_unchanged_stop_exit() -> dict[str, Any]:
    original_shape, original_stop = _handler_without_stop(main_guard(subject_text("original/np_runner_entry.py")))
    candidate_shape, candidate_stop = _handler_without_stop(main_guard(subject_text("candidate/np_runner_entry.py")))
    require(original_shape == candidate_shape, "handler changed beyond the STOP envelope expression")
    expect_original = ast.dump(ast.parse(
        'json.dumps({"status": "STOP", "kind": type(exc).__name__}, sort_keys=True) + "\\n"', mode="eval").body)
    expect_candidate = ast.dump(ast.parse(
        'json.dumps(stop_payload(exc), sort_keys=True) + "\\n"', mode="eval").body)
    require(original_stop == expect_original and candidate_stop == expect_candidate, "STOP expression mismatch")

    runs = {}
    for which in ("original", "candidate"):
        for label, outcome in (("runtime_error", RuntimeError(SECRET)), ("keyboard_interrupt", KeyboardInterrupt())):
            code, stream = run_handler(which, outcome)
            require(code == 125, f"{which} {label} exit")
            require(len(stream.writes) == 1 and stream.flushes == 1, f"{which} {label} single write")
            line = stream.writes[0]
            require(line.endswith("\n") and line.count("\n") == 1 and "\r" not in line, f"{which} {label} line")
            value = json.loads(line)
            require(value["status"] == "STOP" and value["kind"] == type(outcome).__name__, f"{which} {label} kind")
            require(SECRET not in line and "pki" not in line.lower(), f"{which} {label} content")
            if which == "candidate":
                d = diag(value)
                require(d["truncated"] is True and d["exceptions"][0]["frames"] == [],
                        "real checker frames must be non-owned")
            host_accepts(standard_fs(), value)
            runs[f"{which}:{label}"] = "PASS"
        code, stream = run_handler(which, 0)
        require(code == 0 and stream.writes == [] and stream.flushes == 0, f"{which} success path")
        runs[f"{which}:success_no_stop"] = "PASS"
    return {"runs": runs, "control_kind": "extracted_handler_fake", "observed": "PASS"}


def check_host_validator_extracted() -> dict[str, Any]:
    fs = standard_fs()
    good = producer(fs)(make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 3)]))
    cases = {}
    host_accepts(fs, good)
    host_accepts(fs, {"status": "STOP", "kind": "SuiteStop"})
    cases["accepts_candidate_and_original"] = "PASS"

    require(host_outcome(fs, envelope(good), args=["start", "--attach", "b" * 64]) == [], "unowned args recorded")
    cases["ignores_unowned_attach"] = "PASS"

    def mutated(change) -> bytes:
        value = json.loads(envelope(good))
        change(value)
        return envelope(value)

    refusals = {
        "carriage_return": envelope(good).replace(b"\n", b"\r\n"),
        "two_lines": envelope(good) + b"\n",
        "over_4096": (json.dumps({"status": "STOP", "kind": "S" * 5000}) + "\n").encode(),
        "duplicate_key": b'{"kind": "SuiteStop", "kind": "SuiteStop", "status": "STOP"}\n',
        "primary_kind_mismatch": mutated(lambda v: v["diagnostic"]["exceptions"][0].update(kind="Other")),
        "frame_not_owned": mutated(lambda v: v["diagnostic"]["exceptions"][0]["frames"][0].update(
            path="fixture/unlisted.py")),
        "frame_line_oob": mutated(lambda v: v["diagnostic"]["exceptions"][0]["frames"][0].update(line=999)),
        "version_2": mutated(lambda v: v["diagnostic"].update(version=2)),
        "four_exceptions": mutated(lambda v: v["diagnostic"]["exceptions"].extend(
            [{"kind": "SuiteStop", "frames": []}] * 3)),
        "nine_frames": mutated(lambda v: v["diagnostic"]["exceptions"][0].update(
            frames=[{"path": "fixture/owned_a.py", "line": 1}] * 9)),
        "extra_top_key": mutated(lambda v: v.update(message=SECRET)),
    }
    for name, data in refusals.items():
        host_refuses(fs, data)
        cases[f"refuses_{name}"] = "PASS"
    host_refuses(fs, envelope(good), returncode="125")
    cases["refuses_non_int_exit"] = "PASS"
    return {"cases": cases, "control_kind": "extracted_host_validator_fake", "observed": "PASS"}


def _expect_detected(name: str, action, expected: type[BaseException], message_prefix: str | None) -> str:
    """A mutant counts as detected only by the specific oracle that targets it."""
    try:
        action()
    except expected as exc:
        if message_prefix is not None and not str(exc).startswith(message_prefix):
            raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
        return "DETECTED"
    except Exception:
        raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
    raise WitnessFailure(f"mutant survived:{name}")


def check_mutant_detection() -> dict[str, Any]:
    fs = standard_fs()
    results = {}

    def frame_cap_mutant() -> None:
        sp = producer(fs, ("if len(frames) > 8:", "if len(frames) > 9:"))
        payload = sp(make_exc("SuiteStop", [(owned("fixture/owned_a.py"), n) for n in range(1, 13)]))
        require(len(diag(payload)["exceptions"][0]["frames"]) == 8, "frame cap")
        host_accepts(fs, payload)

    def fallback_mutant() -> None:
        sp = producer(make_fs({}, manifest=False),
                      ("return original  # Diagnostic failure must not replace the primary kind.", "raise"))
        require(sp(make_exc("SuiteStop", [])) == {"status": "STOP", "kind": "SuiteStop"}, "fallback")

    def context_mutant() -> None:
        sp = producer(fs, ("current = current.__cause__ if current.__cause__ is not None else current.__context__",
                           "current = current.__cause__"))
        inner = make_exc("KeyError", [(owned("fixture/owned_b.py"), 6)])
        d = diag(sp(make_exc("SuiteStop", [(owned("fixture/owned_a.py"), 2)], context=inner)))
        require(len(d["exceptions"]) == 2, "context")

    def walk_mutant() -> None:
        sp = producer(fs, ("walked < 128", "walked < 129"))
        visits: set[int] = set()
        tb = None
        for index in reversed(range(200)):
            tb = CountingTraceback(index, visits, owned("fixture/owned_a.py"), tb)
        exc = make_exc("SuiteStop", [])
        exc.__traceback__ = tb
        sp(exc)
        require(visits == set(range(128)), "walk")

    for name, action, expected, prefix in (
            ("frame_cap_9", frame_cap_mutant, WitnessFailure, "frame cap"),
            ("fallback_removed", fallback_mutant, FileNotFoundError, None),
            ("context_ignored", context_mutant, WitnessFailure, "context"),
            ("walk_129", walk_mutant, WitnessFailure, "walk")):
        results[name] = _expect_detected(name, action, expected, prefix)
    return {"mutants": results, "control_kind": "mutation_fake", "observed": "PASS"}


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
    require(expected.get("kind") == "runner-diagnostic-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "DIFF-REDERIVATION": check_diff_rederivation,
        "PRODUCER-PRECEDENT-IDENTITY": check_producer_precedent_identity,
        "DECLARATION-MATCHES-BEHAVIOR": check_declaration_matches_behavior,
        "ORIGINAL-STATUS-KIND-ONLY": check_original_status_kind_only,
        "CANDIDATE-HAPPY-PATH": check_candidate_happy_path,
        "CAUSE-CONTEXT-CYCLE": check_cause_context_cycle,
        "OWNED-FRAME-REJECTIONS": check_owned_frame_rejections,
        "BOUNDS-AND-TRUNCATION": check_bounds_and_truncation,
        "DIAGNOSTIC-FALLBACK": check_diagnostic_fallback,
        "PRIVACY-ENVELOPE": check_privacy_envelope,
        "UNCHANGED-STOP-EXIT": check_unchanged_stop_exit,
        "HOST-VALIDATOR-EXTRACTED": check_host_validator_extracted,
        "MUTANT-DETECTION": check_mutant_detection,
    }
    require(tuple(functions) == CONTROL_IDS, "internal control order")
    controls = {}
    for control_id, function in functions.items():
        try:
            controls[control_id] = function()
        except WitnessFailure:
            raise
        except Exception as exc:
            raise WitnessFailure(f"{control_id}:{type(exc).__name__}") from None
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    nested = sum(len(v.get("cases") or v.get("runs") or v.get("mutants") or {"_": 1}) for v in controls.values())
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
