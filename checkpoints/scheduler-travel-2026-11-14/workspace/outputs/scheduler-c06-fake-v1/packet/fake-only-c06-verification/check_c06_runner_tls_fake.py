#!/usr/bin/env python3
"""Held fake-only C06 runner-TLS verification. DO NOT RUN under this preparation card.

AST-extracts C06 helpers from the fresh-copy payload and exercises refuse/pass
controls with fake processes, fake TLS context recording, and an in-memory FS.
No app/vendor imports, real child processes, sockets, or PKI generation.

Synthetic modules are registered in sys.modules before exec into that same
module.__dict__. Required AST names fail closed. Source pins are enforced
against INPUT-MANIFEST.json (four fixture sources plus a separate pinned
launch-config static input, before controls). FakeOS.path.join is
posixpath.join (POSIX in-memory; host os.path.join is not used for FakeFS
keys). A later authorized run must set executed=True.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import posixpath
import stat
import subprocess
import sys
import types
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
PAYLOAD = PACKET / "payload"
FIXTURE = PAYLOAD / "fixture"
EXPECTED_PATH = HERE / "EXPECTED-OUTPUT.json"
RESULT_PATH = HERE / "FAKE-C06-RESULT.json"
MANIFEST_PATH = HERE / "INPUT-MANIFEST.json"

PERMITTED_IMPORT_ROOTS = {
    "ast", "hashlib", "json", "os", "posixpath", "stat", "subprocess", "sys",
    "types", "dataclasses", "pathlib", "typing", "__future__", "builtins",
    "copy", "re", "threading", "time",
}

LAUNCH_CONFIG_REL = "payload/launch-config.json"
LAUNCH_CONFIG_PATH = PAYLOAD / "launch-config.json"
LAUNCH_CONFIG_SHA256 = (
    "B94DEFE32C2C25B22D0AFBCBA0CC5E2365CBB5AD8FEE291C83667DC51145B4A9"
)

# Narrow fake Linux signal namespace. POSIX SIGTERM=15 / SIGKILL=9 — the
# exact constants used by extracted runner killpg paths. Host Windows
# Python311 has no SIGKILL; do not import or call the real signal module.
linux_signal = types.SimpleNamespace(SIGTERM=15, SIGKILL=9)

RUNNER_NAMES = {
    "C06_GATE_TLS_DIR", "C06_GATE_CLIENT_CA", "C06_BACKEND_DB_CA",
    "C06_PREPARE_SCRIPT", "C06_SH_ABS", "C06_OPENSSL_ABS",
    "C06_GEN_SECONDS", "C06_REAP_SECONDS", "C06_READER_JOIN_SECONDS",
    "C06_DISCLOSED_RETIREMENT_SECONDS", "C06_WAIT_POLL_SECONDS",
    "C06_CAPTURE_CAP", "C06_ARTIFACT_CEILING", "C06_REQUIRED_UID",
    "C06_CHILD_ENV", "C06_RUNNER_BUDGET_SECONDS", "C06_SUITE_BUDGET_SECONDS",
    "C06RunnerTlsError", "C06CaptureSink", "exclusive_create_c06_gate_tls_dir",
    "_c06_capture_reader", "_c06_owned_pgid", "_c06_group_probe",
    "_c06_retire_process_group", "_c06_join_started_readers",
    "_c06_close_owned_pipes", "_c06_attach_secondary",
    "_c06_public_provenance", "_c06_sanitized_status", "prepare_c06_runner_tls",
}

DUAL_NAMES = {
    "C06_GATE_ARTIFACT_STEM", "C06_GATE_PORT", "C06_GATE_ROOT",
    "C06_GATE_CLIENT_CA", "C06_BACKEND_DB_CA", "C06ArmError", "C06GateError",
    "c06_artifact_paths", "require_distinct_public_ca_hashes",
    "build_c06_dual_peer_binding", "serve_i01_c06_gate",
}


class ControlFailure(Exception):
    pass


@dataclass
class ControlResult:
    control_id: str
    result: str
    detail: str = ""
    kind: str = "behavioral"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_expected() -> dict[str, Any]:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def verify_source_pins(manifest: dict[str, Any]) -> None:
    sources = (manifest.get("source_extraction") or {}).get("sources") or {}
    required = {
        "fixture/prepare-c06-runner-tls.sh": FIXTURE / "prepare-c06-runner-tls.sh",
        "fixture/runner_entry.py": FIXTURE / "runner_entry.py",
        "fixture/i01_c06_dual_peer.py": FIXTURE / "i01_c06_dual_peer.py",
        "fixture/i01_i02_suite.py": FIXTURE / "i01_i02_suite.py",
    }
    if set(sources) != set(required):
        raise ControlFailure(f"manifest source set mismatch: {sorted(sources)}")
    for rel, path in required.items():
        expected = sources[rel]
        if not isinstance(expected, str) or not expected.strip():
            raise ControlFailure(f"empty pin:{rel}")
        live = sha256_file(path)
        if live != expected.strip().upper():
            raise ControlFailure(f"source pin mismatch:{rel}")


def verify_launch_config_pin(manifest: dict[str, Any]) -> None:
    """Consumed launch-config is a separate pinned static input, not a fifth fixture source."""
    static_inputs = manifest.get("pinned_static_inputs") or {}
    if set(static_inputs) != {LAUNCH_CONFIG_REL}:
        raise ControlFailure(f"pinned static input set mismatch: {sorted(static_inputs)}")
    expected = static_inputs[LAUNCH_CONFIG_REL]
    if not isinstance(expected, str) or not expected.strip():
        raise ControlFailure("empty pin:payload/launch-config.json")
    live = sha256_file(LAUNCH_CONFIG_PATH)
    if live != expected.strip().upper() or live != LAUNCH_CONFIG_SHA256:
        raise ControlFailure("launch-config pin mismatch")


def verify_fakeos_posix_join() -> None:
    """FakeOS.path.join is POSIX-only in-memory; no host os.path.join / no OS mutation."""
    if "posixpath" not in PERMITTED_IMPORT_ROOTS:
        raise ControlFailure("posixpath must remain an explicit permitted stdlib import")
    fs = FakeFS()
    fake_os = FakeOS(fs)
    if fake_os.path.join is not posixpath.join:
        raise ControlFailure("FakeOS.path.join must be posixpath.join")
    joined = fake_os.path.join("/tmp/c06-gate-tls", "ca.crt")
    if joined != "/tmp/c06-gate-tls/ca.crt":
        raise ControlFailure(f"posix join drifted: {joined!r}")
    if "\\" in joined:
        raise ControlFailure("posix join produced a backslash")


def _register_and_exec(source: str, path: Path, names: set[str], extras: dict[str, Any], module_name: str) -> types.ModuleType:
    tree = ast.parse(source, filename=str(path))
    keep: list[ast.stmt] = []
    found: set[str] = set()
    for node in tree.body:
        hit = False
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            hit = True
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    hit = True
                    found.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in names:
            hit = True
            found.add(node.target.id)
        if hit:
            keep.append(node)
    missing = sorted(names - found)
    if missing:
        raise ControlFailure(f"required AST names missing from {path.name}: {missing}")
    module = types.ModuleType(module_name)
    module.__dict__.update(extras)
    module.__dict__["__name__"] = module_name
    module.__dict__["__file__"] = str(path)
    module.__dict__["__builtins__"] = __builtins__
    sys.modules[module_name] = module
    if sys.modules[module_name] is not module:
        raise ControlFailure(f"sys.modules[{module_name!r}] identity broken")
    if sys.modules[module_name].__dict__ is not module.__dict__:
        raise ControlFailure(f"module.__dict__ identity broken for {module_name!r}")
    module_ast = ast.Module(body=keep, type_ignores=[])
    ast.fix_missing_locations(module_ast)
    compiled = compile(module_ast, str(path), "exec")
    exec(compiled, module.__dict__)
    if module.__dict__ is not sys.modules[module_name].__dict__:
        raise ControlFailure("exec namespace is not registered module.__dict__")
    for name in names:
        if name not in module.__dict__:
            raise ControlFailure(f"required symbol {name!r} missing after exec")
    return module


def extract_runner_c06(os_mod, subprocess_mod, thread_cls, path_cls) -> types.ModuleType:
    source = (FIXTURE / "runner_entry.py").read_text(encoding="utf-8")
    extras = {
        "os": os_mod,
        "subprocess": subprocess_mod,
        "signal": linux_signal,
        "stat": stat,
        "hashlib": hashlib,
        "Thread": thread_cls,
        "Path": path_cls,
        "monotonic": lambda: os_mod.now,
        "ROOT": path_cls("/packet"),
    }
    return _register_and_exec(
        source, FIXTURE / "runner_entry.py", RUNNER_NAMES, extras, "c06_fake_runner"
    )


class FakeStat:
    def __init__(self, uid: int, mode: int):
        self.st_uid = uid
        self.st_mode = stat.S_IFDIR | mode


class FakePath:
    def __init__(self, fs: "FakeFS", *parts: Any):
        self._fs = fs
        joined = []
        for part in parts:
            text = part._p if isinstance(part, FakePath) else str(part)
            joined.append(text.replace("\\", "/"))
        path = joined[0] if joined else ""
        for piece in joined[1:]:
            path = path.rstrip("/") + "/" + piece.lstrip("/")
        self._p = path

    def __truediv__(self, other: Any) -> "FakePath":
        return FakePath(self._fs, self._p, other)

    def __str__(self) -> str:
        return self._p

    def __fspath__(self) -> str:
        return self._p

    def is_file(self) -> bool:
        return self._p in self._fs.files

    def resolve(self) -> "FakePath":
        return self

    def as_posix(self) -> str:
        return self._p

    def read_bytes(self) -> bytes:
        if self._p not in self._fs.files:
            raise FileNotFoundError(self._p)
        return self._fs.files[self._p]

    def read_text(self, encoding: str = "utf-8") -> str:
        return self.read_bytes().decode(encoding)

    def open(self, mode: str = "r", encoding: str | None = None):
        fs = self._fs
        path = self._p

        class Handle:
            def write(self, data: Any) -> int:
                raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
                fs.files[path] = fs.files.get(path, b"") + raw
                return len(raw)

            def __enter__(self) -> "Handle":
                if "x" in mode and path in fs.files:
                    raise FileExistsError(path)
                if "w" in mode or "x" in mode:
                    fs.files[path] = b""
                return self

            def __exit__(self, *args: Any) -> bool:
                return False

        return Handle()


class FakePipe:
    def __init__(self, data: bytes, raise_on_read: bool = False):
        self._data = data
        self._off = 0
        self.closed = False
        self.raise_on_read = raise_on_read
        self.close_calls = 0

    def read(self, n: int = -1) -> bytes:
        if self.raise_on_read:
            raise RuntimeError("late-reader")
        if self._off >= len(self._data):
            return b""
        if n < 0:
            chunk = self._data[self._off:]
            self._off = len(self._data)
            return chunk
        chunk = self._data[self._off:self._off + n]
        self._off += len(chunk)
        return chunk

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        FakePopen.close_calls.append(self)


class FakePopen:
    last: "FakePopen | None" = None
    mode = "success"
    stdout_payload = b"verify OK\n"
    stderr_payload = b""
    openssl_child_alive = False
    clock: Any = None
    close_calls: list[Any] = []
    stdout_raise = False
    stderr_raise = False
    setup_advance_s = 0.0
    wait_advanced = 0.0

    def __init__(self, argv, executable=None, stdin=None, stdout=None, stderr=None,
                 env=None, cwd=None, start_new_session=None, close_fds=None):
        self.argv = list(argv)
        self.executable = executable
        self.env = dict(env or {})
        self.cwd = cwd
        self.start_new_session = start_new_session
        self.close_fds = close_fds
        self.pid = 4242
        self.signals: list[int] = []
        self.pg_signals: list[int] = []
        self.stdout = FakePipe(self.stdout_payload, raise_on_read=self.stdout_raise)
        self.stderr = FakePipe(self.stderr_payload, raise_on_read=self.stderr_raise)
        if self.mode == "success":
            self.returncode = 0
        elif self.mode == "refuse":
            self.returncode = 1
        else:
            self.returncode = None
        self.__class__.last = self
        self.__class__.openssl_child_alive = True
        # Advance after prepare_c06_runner_tls has already captured admission_deadline.
        if self.clock is not None and self.setup_advance_s:
            self.clock.now += float(self.setup_advance_s)

    def wait(self, timeout=None):
        if self.clock is not None and timeout:
            added = float(timeout)
            self.clock.now += added
            self.__class__.wait_advanced += added
        if self.returncode is not None:
            return self.returncode
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(self.argv, timeout)
        self.returncode = 0
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.signals.append(linux_signal.SIGKILL)
        self.returncode = -linux_signal.SIGKILL


class FakeOS:
    def __init__(self, fs: "FakeFS"):
        self.fs = fs
        self.now = 0.0
        self.uid = 65534
        self.mkdirs: list[str] = []
        self.killed_pg: list[tuple[int, int]] = []
        self.descendant_alive = False
        self.sigterm_ignored = False
        self.leader_exits_on_sigterm = True
        self.sigterm_kills_group = True
        self.path = types.SimpleNamespace(lexists=self.lexists, join=posixpath.join)
        self.environ = {}

    def getuid(self) -> int:
        return self.uid

    def lexists(self, path: str) -> bool:
        return path in self.fs.dirs or path in self.fs.files

    def umask(self, mask: int) -> int:
        previous = self.fs.umask
        self.fs.umask = mask
        return previous

    def mkdir(self, path: str, mode: int = 0o777) -> None:
        if path in self.fs.dirs or path in self.fs.files:
            raise FileExistsError(path)
        self.fs.dirs[path] = mode & ~self.fs.umask
        self.fs.owners[path] = self.uid
        self.mkdirs.append(path)

    def chmod(self, path: str, mode: int) -> None:
        if path in self.fs.dirs:
            self.fs.dirs[path] = mode
        elif path in self.fs.files:
            self.fs.file_modes[path] = mode
        else:
            raise FileNotFoundError(path)

    def stat(self, path: str):
        if path in self.fs.dirs:
            return types.SimpleNamespace(
                st_uid=self.fs.owners.get(path, self.uid),
                st_mode=stat.S_IFDIR | self.fs.dirs[path],
            )
        if path in self.fs.files:
            return types.SimpleNamespace(
                st_uid=self.fs.owners.get(path, self.uid),
                st_mode=stat.S_IFREG | self.fs.file_modes.get(path, 0o600),
            )
        raise FileNotFoundError(path)

    def listdir(self, path: str):
        prefix = path.rstrip("/") + "/"
        names = set()
        for key in list(self.fs.dirs) + list(self.fs.files):
            if key.startswith(prefix):
                rest = key[len(prefix):]
                if rest and "/" not in rest:
                    names.add(rest)
        return sorted(names)

    def getpgid(self, pid: int) -> int:
        if FakePopen.last is not None and FakePopen.last.pid == pid:
            return pid
        raise ProcessLookupError(pid)

    def killpg(self, pid: int, sig: int) -> None:
        self.killed_pg.append((pid, sig))
        last = FakePopen.last
        if sig == 0:
            present = self.descendant_alive or (last is not None and last.returncode is None)
            if present:
                return
            raise ProcessLookupError(pid)
        if last is not None:
            last.pg_signals.append(sig)
        if sig == linux_signal.SIGTERM:
            if self.leader_exits_on_sigterm and last is not None:
                last.returncode = -linux_signal.SIGTERM
            if self.sigterm_ignored or not self.sigterm_kills_group:
                return
            self.descendant_alive = False
            FakePopen.openssl_child_alive = False
            return
        if sig == linux_signal.SIGKILL:
            if last is not None:
                last.returncode = -linux_signal.SIGKILL
            self.descendant_alive = False
            FakePopen.openssl_child_alive = False


class FakeFS:
    def __init__(self):
        self.dirs: dict[str, int] = {"/tmp": 0o1777, "/packet": 0o755, "/packet/fixture": 0o755}
        self.files: dict[str, bytes] = {
            "/packet/fixture/prepare-c06-runner-tls.sh": b"#!/bin/sh\n# fake recipe bytes\n",
        }
        self.file_modes: dict[str, int] = {
            "/packet/fixture/prepare-c06-runner-tls.sh": 0o644,
        }
        self.owners: dict[str, int] = {}
        self.umask = 0o022


class ImmediateThread:
    def __init__(self, target=None, args=(), name=None, daemon=None):
        self.target = target
        self.args = args
        self.name = name
        self._alive = False
        self.hold = False
        self.join_raises = False
        self.defer_run = False

    def start(self) -> None:
        if self.hold or self.defer_run:
            self._alive = True
            return
        if self.target is not None:
            self.target(*self.args)
        self._alive = False

    def join(self, timeout=None) -> None:
        if self.join_raises:
            raise RuntimeError("join-fail")
        if self.hold:
            return
        if self.defer_run and self.target is not None:
            self.target(*self.args)
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive


def expect_raise(fn: Callable, token: str) -> BaseException:
    try:
        fn()
    except BaseException as error:
        text = str(error)
        if token not in text and token not in type(error).__name__:
            raise ControlFailure(f"expected {token!r} in {type(error).__name__}:{text!r}")
        return error
    raise ControlFailure(f"expected raise containing {token!r}")


def seed_public_material(fs: FakeFS, *, gate: bytes, db: bytes, mode: int = 0o600, uid: int = 65534) -> None:
    fs.files["/tmp/c06-gate-tls/ca.crt"] = gate
    fs.files["/tmp/c06-gate-tls/server.crt"] = b"-----BEGIN CERTIFICATE-----\nLEAF\n-----END CERTIFICATE-----\n"
    fs.files["/tmp/c06-gate-tls/ca.key"] = b"FAKE-NOT-A-KEY"
    fs.files["/tmp/c06-gate-tls/server.key"] = b"FAKE-NOT-A-KEY"
    for path in (
        "/tmp/c06-gate-tls/ca.crt",
        "/tmp/c06-gate-tls/server.crt",
        "/tmp/c06-gate-tls/ca.key",
        "/tmp/c06-gate-tls/server.key",
    ):
        fs.file_modes[path] = mode
        fs.owners[path] = uid
    fs.files["/public-ca/ca.crt"] = db
    fs.file_modes["/public-ca/ca.crt"] = 0o644
    fs.owners["/public-ca/ca.crt"] = 0


def make_runtime(
    mode: str = "success",
    hold_readers: bool = False,
    stdout: bytes | None = None,
    defer_readers: bool = False,
    stdout_raise: bool = False,
):
    fs = FakeFS()
    fake_os = FakeOS(fs)
    FakePopen.mode = mode
    FakePopen.stdout_payload = b"verify OK\n" if stdout is None else stdout
    FakePopen.stderr_payload = b""
    FakePopen.last = None
    FakePopen.openssl_child_alive = False
    FakePopen.clock = fake_os
    FakePopen.close_calls = []
    FakePopen.stdout_raise = stdout_raise
    FakePopen.stderr_raise = False
    FakePopen.setup_advance_s = 0.0
    FakePopen.wait_advanced = 0.0
    fake_os.descendant_alive = True
    sub = types.ModuleType("subprocess")
    sub.Popen = FakePopen
    sub.PIPE = subprocess.PIPE
    sub.DEVNULL = subprocess.DEVNULL
    sub.TimeoutExpired = subprocess.TimeoutExpired
    thread_cls: type[ImmediateThread] = ImmediateThread
    if hold_readers:
        class Held(ImmediateThread):
            def start(self) -> None:
                self.hold = True
                self._alive = True
        thread_cls = Held
    elif defer_readers:
        class Deferred(ImmediateThread):
            def start(self) -> None:
                self.defer_run = True
                self._alive = True
        thread_cls = Deferred
    path_cls = lambda *parts: FakePath(fs, *parts)
    path_cls.__name__ = "FakePath"
    mod = extract_runner_c06(fake_os, sub, thread_cls, path_cls)
    return mod, fake_os, fs


def extract_dual(fs: FakeFS | None = None) -> types.ModuleType:
    source = (FIXTURE / "i01_c06_dual_peer.py").read_text(encoding="utf-8")
    fs = fs if fs is not None else FakeFS()

    @dataclass
    class Prof:
        port: int = 5432
        ca_file: str = "/public-ca/ca.crt"

    class NativeORMFactories:
        def __init__(self, profile, password_supplier=None, runtime_pins=None):
            self.profile = profile
            self.parent_factory = lambda *a, **k: object()
            self.session_factory = object()

    class CoveringHTTP:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class CoveringReleaseBinding:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class ProviderCounter:
        def __init__(self, *args: Any) -> None:
            pass

    class CoveringRootOutcomeUnknown(Exception):
        pass

    class FakeSSLContext:
        last_cafile = None
        last_server = None

        def __init__(self, protocol=None):
            self.protocol = protocol
            self.minimum_version = None
            self.cafile = None
            self.chain = None

        def load_cert_chain(self, *args: Any, **kwargs: Any) -> None:
            self.chain = args
            FakeSSLContext.last_server = args

        @staticmethod
        def create_default_context(cafile=None):
            ctx = FakeSSLContext()
            ctx.cafile = cafile
            FakeSSLContext.last_cafile = cafile
            return ctx

    ssl_mod = types.SimpleNamespace(
        SSLContext=FakeSSLContext,
        create_default_context=FakeSSLContext.create_default_context,
        PROTOCOL_TLS_SERVER=1,
        TLSVersion=types.SimpleNamespace(TLSv1_2=1),
    )

    class FakeListener:
        occupied = False
        last_bind = None
        retired_clients: list[Any] = []
        AF_INET = 2
        SOCK_STREAM = 1
        SOL_SOCKET = 1
        SO_REUSEADDR = 2

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.role = "listener"
            self._retired = False

        def setsockopt(self, *args: Any, **kwargs: Any) -> None:
            pass

        def bind(self, addr: Any) -> None:
            FakeListener.last_bind = addr
            if FakeListener.occupied:
                raise OSError("occupied")

        def listen(self, backlog: int) -> None:
            pass

        def settimeout(self, value: float) -> None:
            pass

        def accept(self) -> tuple[Any, Any]:
            client = FakeListener()
            client.role = "client"
            return (client, ("127.0.0.1", 1))

        def __enter__(self) -> "FakeListener":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            self.close()
            return False

        def close(self) -> None:
            if self._retired:
                return
            self._retired = True
            FakeListener.retired_clients.append(self)

    socket_mod = types.SimpleNamespace(
        socket=FakeListener,
        AF_INET=FakeListener.AF_INET,
        SOCK_STREAM=FakeListener.SOCK_STREAM,
        SOL_SOCKET=FakeListener.SOL_SOCKET,
        SO_REUSEADDR=FakeListener.SO_REUSEADDR,
        timeout=TimeoutError,
    )

    recorded: dict[str, Any] = {}

    def serve_one(client, **kwargs: Any) -> None:
        recorded["backend_cafile"] = getattr(kwargs.get("backend_context"), "cafile", None)
        recorded["backend_port"] = kwargs.get("backend_port")

    class Event:
        def __init__(self) -> None:
            self._set = False

        def set(self) -> None:
            self._set = True

        def is_set(self) -> bool:
            return self._set

    extras = {
        "hashlib": hashlib,
        "Path": (lambda *parts: FakePath(fs, *parts)),
        "replace": replace,
        "json": json,
        "ssl": ssl_mod,
        "socket": socket_mod,
        "Event": Event,
        "monotonic": lambda: 0.0,
        "MethodType": types.MethodType,
        "Callable": Callable,
        "NativeORMFactories": NativeORMFactories,
        "CoveringHTTP": CoveringHTTP,
        "CoveringReleaseBinding": CoveringReleaseBinding,
        "make_domain_ports": lambda **kw: object(),
        "ProviderCounter": ProviderCounter,
        "approved_provider_limits": lambda: object(),
        "CoveringRootOutcomeUnknown": CoveringRootOutcomeUnknown,
        "wrap_parent_factory_for_lost_ack": lambda factory, arm_fired=None: factory,
        "serve_one": serve_one,
        "Prof": Prof,
    }
    mod = _register_and_exec(
        source, FIXTURE / "i01_c06_dual_peer.py", DUAL_NAMES, extras, "c06_fake_dual"
    )
    mod.FakeSSLContext = FakeSSLContext  # type: ignore[attr-defined]
    mod.FakeListener = FakeListener  # type: ignore[attr-defined]
    mod.Prof = Prof  # type: ignore[attr-defined]
    mod.recorded = recorded  # type: ignore[attr-defined]
    mod._fs = fs  # type: ignore[attr-defined]
    return mod


def main_call_prepare_before_audit(runner_src: str) -> None:
    tree = ast.parse(runner_src)
    main = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"),
        None,
    )
    if main is None:
        raise ControlFailure("runner_entry main missing")

    class CallVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name):
                    name = f"{func.value.id}.{func.attr}"
                else:
                    name = func.attr
            if name:
                self.calls.append(name)
            self.generic_visit(node)

    visitor = CallVisitor()
    visitor.visit(main)
    if "prepare_c06_runner_tls" not in visitor.calls:
        raise ControlFailure("main does not call prepare_c06_runner_tls")
    if "sys.addaudithook" not in visitor.calls:
        raise ControlFailure("main does not call sys.addaudithook")
    if visitor.calls.index("prepare_c06_runner_tls") >= visitor.calls.index("sys.addaudithook"):
        raise ControlFailure("prepare_c06_runner_tls call is not before addaudithook in main")


def run_controls() -> list[ControlResult]:
    results: list[ControlResult] = []
    dual = extract_dual()
    runner_src = (FIXTURE / "runner_entry.py").read_text(encoding="utf-8")
    suite_src = (FIXTURE / "i01_i02_suite.py").read_text(encoding="utf-8")
    script_src = (FIXTURE / "prepare-c06-runner-tls.sh").read_text(encoding="utf-8")
    launch = json.loads((PAYLOAD / "launch-config.json").read_text(encoding="utf-8"))

    def rec(control_id: str, result: str, detail: str = "", kind: str = "behavioral") -> None:
        results.append(ControlResult(control_id, result, detail, kind))

    mod, fake_os, fs = make_runtime("success")
    fake_os.lexists = lambda path: True
    err = expect_raise(mod.exclusive_create_c06_gate_tls_dir, "pre-exists")
    rec("C06_N_PREEXIST", "REFUSE", type(err).__name__)

    mod, fake_os, fs = make_runtime("success")
    original_mkdir = fake_os.mkdir

    def mkdir_then_dirty(path, mode=0o777):
        original_mkdir(path, mode)
        fs.files[path + "/stale"] = b"x"
        fs.file_modes[path + "/stale"] = 0o600

    fake_os.mkdir = mkdir_then_dirty
    err = expect_raise(mod.exclusive_create_c06_gate_tls_dir, "nonempty")
    rec("C06_N_NONEMPTY", "REFUSE", type(err).__name__)

    mod, fake_os, fs = make_runtime("success")
    fake_os.uid = 1000
    err = expect_raise(mod.exclusive_create_c06_gate_tls_dir, "c06 uid")
    rec("C06_N_UID", "REFUSE", type(err).__name__)

    mod, fake_os, fs = make_runtime("success")

    def chmod_then_world(path, mode):
        fake_os.fs.dirs[path] = 0o777

    fake_os.chmod = chmod_then_world
    err = expect_raise(mod.exclusive_create_c06_gate_tls_dir, "ownership")
    rec("C06_N_MODE", "REFUSE", type(err).__name__)

    same = b"-----BEGIN CERTIFICATE-----\nSAME\n-----END CERTIFICATE-----\n"
    err = expect_raise(lambda: dual.require_distinct_public_ca_hashes(same, same), "distinct")
    rec("C06_N_TRUST_SAME_CA", "REFUSE", type(err).__name__)

    parent_err = expect_raise(
        lambda: dual.build_c06_dual_peer_binding(
            profile=dual.Prof(port=5432, ca_file=dual.C06_GATE_CLIENT_CA),
            password_supplier=lambda: "",
            runtime_pins=object(),
            settings=object(),
            provider_routes={},
            transport_factory=object(),
        ),
        "direct profile must retain backend DB CA",
    )
    rec("C06_N_TRUST_PARENT_DB_CA", "REFUSE", type(parent_err).__name__)

    dual.FakeListener.occupied = False
    dual.FakeSSLContext.last_cafile = None
    fs_gate = FakeFS()
    fs_gate.dirs["/tmp/c06-gate-tls"] = 0o700
    fs_gate.files["/tmp/c06-gate-tls/server.crt"] = b"CRT"
    fs_gate.files["/tmp/c06-gate-tls/server.key"] = b"KEY"
    dual_serve = extract_dual(fs_gate)
    dual_serve.FakeListener.occupied = False
    class ReadyEvent:
        def __init__(self) -> None:
            self._set = False
        def set(self) -> None:
            self._set = True
        def is_set(self) -> bool:
            return self._set
    dual_serve.serve_i01_c06_gate(ready=ReadyEvent(), stop=ReadyEvent(), seconds=1)
    if dual_serve.FakeSSLContext.last_cafile != dual_serve.C06_BACKEND_DB_CA:
        raise ControlFailure(f"backend cafile {dual_serve.FakeSSLContext.last_cafile!r}")
    if dual_serve.FakeSSLContext.last_cafile == dual_serve.C06_GATE_CLIENT_CA:
        raise ControlFailure("backend still trusts gate CA")
    if not any(
        getattr(item, "role", None) == "client" and getattr(item, "_retired", False)
        for item in dual_serve.FakeListener.retired_clients
    ):
        raise ControlFailure("owned FakeListener client context did not record retirement")
    rec("C06_N_TRUST_BACKEND_GATE_CA", "REFUSE", "extracted serve_i01_c06_gate uses DB CA")

    if dual.C06_GATE_ROOT.as_posix() == "/fixture-tls":
        raise ControlFailure("default root is /fixture-tls")
    ready_default, _ = dual.c06_artifact_paths()
    if "/fixture-tls" in ready_default.as_posix():
        raise ControlFailure("default artifacts still under /fixture-tls")
    rec(
        "C06_N_ROOT_FIXTURE_TLS",
        "PASS",
        "STATIC: default C06_GATE_ROOT path is not /fixture-tls",
        kind="static",
    )

    dual.FakeListener.occupied = True
    dual.FakeListener.last_bind = None
    order_err = expect_raise(
        lambda: dual.serve_i01_c06_gate(ready=ReadyEvent(), stop=ReadyEvent(), seconds=1),
        "occupied gate port",
    )
    rec("C06_N_ORDER_C06_BEFORE_N06", "REFUSE", type(order_err).__name__)

    mod, fake_os, fs = make_runtime("refuse")
    err = expect_raise(mod.prepare_c06_runner_tls, "refused")
    rec("C06_N_GEN_REFUSE", "REFUSE", str(err))

    mod, fake_os, fs = make_runtime("timeout")
    err = expect_raise(mod.prepare_c06_runner_tls, "timeout")
    if not any(sig != 0 for _, sig in fake_os.killed_pg):
        raise ControlFailure("timeout must signal owned group")
    rec("C06_N_GEN_TIMEOUT", "REFUSE", "shared deadline then group retire")

    mod, fake_os, fs = make_runtime("success", stdout=b"X" * 70000)
    err = expect_raise(mod.prepare_c06_runner_tls, "capture cap")
    rec("C06_N_CAP", "REFUSE", type(err).__name__)

    FakePopen.openssl_child_alive = True
    child = FakePopen(["/bin/sh"], executable="/bin/sh", env={}, cwd="/tmp", start_new_session=True)
    child.returncode = None
    child.kill()
    if not FakePopen.openssl_child_alive:
        raise ControlFailure("shell-only kill unexpectedly retired openssl child")
    mod, fake_os, fs = make_runtime("timeout")
    fake_os.sigterm_kills_group = True
    expect_raise(mod.prepare_c06_runner_tls, "timeout")
    if FakePopen.openssl_child_alive:
        raise ControlFailure("process-group retire did not own openssl child")
    rec("C06_N_SHELL_ONLY_KILL", "REFUSE", "killpg owns openssl children")

    mod, fake_os, fs = make_runtime("timeout")
    fake_os.sigterm_kills_group = False
    fake_os.leader_exits_on_sigterm = True
    fake_os.descendant_alive = True
    err = expect_raise(mod.prepare_c06_runner_tls, "timeout")
    extra = getattr(err, "fixture_c06_tls", {})
    if extra.get("leader_exited") is not True:
        raise ControlFailure("leader-exited state not recorded")
    if linux_signal.SIGKILL not in [sig for _, sig in fake_os.killed_pg]:
        raise ControlFailure("descendant-alive after leader exit must escalate SIGKILL")
    rec("C06_N_GROUP_LEADER_EXITED_DESCENDANT_ALIVE", "REFUSE", "group probe independent of leader poll")

    mod, fake_os, fs = make_runtime("timeout")
    fake_os.sigterm_ignored = True
    fake_os.leader_exits_on_sigterm = False
    fake_os.sigterm_kills_group = False
    fake_os.descendant_alive = True
    expect_raise(mod.prepare_c06_runner_tls, "timeout")
    if linux_signal.SIGKILL not in [sig for _, sig in fake_os.killed_pg]:
        raise ControlFailure("SIGTERM-ignored group must escalate SIGKILL")
    rec("C06_N_GROUP_SIGTERM_IGNORED", "REFUSE", "SIGTERM-ignored independent of leader-exit case")

    mod, fake_os, fs = make_runtime("success", hold_readers=True)
    err = expect_raise(mod.prepare_c06_runner_tls, "c06 reader eof unknown")
    if str(err) != "c06 reader eof unknown":
        raise ControlFailure(f"primary replaced: {err!r}")
    extra = getattr(err, "fixture_c06_tls", {})
    if extra.get("readers_joined") is not False:
        raise ControlFailure("held started readers must record unjoined")
    if extra.get("pipes_unretired", 0) < 1:
        raise ControlFailure("held readers must leave pipes unretired")
    if FakePopen.close_calls:
        raise ControlFailure("must not close buffered pipes under live readers")
    rec("C06_N_READER_JOIN", "REFUSE", "primary eof unknown; unjoined + pipes_unretired attached")

    mod, fake_os, fs = make_runtime("success", defer_readers=True, stdout_raise=True)
    err = expect_raise(mod.prepare_c06_runner_tls, "capture reader")
    extra = getattr(err, "fixture_c06_tls", {})
    if extra.get("kind") == "C06RunnerTlsPrepared":
        raise ControlFailure("late reader error reached prepared")
    rec("C06_N_LATE_READER_ERROR", "REFUSE", "post-wait reader throw rechecked after join")

    mod, fake_os, fs = make_runtime("success", hold_readers=True)
    err = expect_raise(mod.prepare_c06_runner_tls, "c06 reader eof unknown")
    if str(err) != "c06 reader eof unknown":
        raise ControlFailure(f"primary replaced: {err!r}")
    extra = getattr(err, "fixture_c06_tls", {})
    if extra.get("readers_joined") is not False:
        raise ControlFailure("live-reader join fact missing")
    if extra.get("pipes_unretired", 0) < 1:
        raise ControlFailure("live-reader pipes_unretired missing")
    if extra.get("pipes_closed") is True:
        raise ControlFailure("live-reader pipes marked closed")
    rec("C06_N_PIPE_UNRETIRED_UNDER_LIVE_READER", "REFUSE", extra.get("pipes_unretired"))

    many = b"Y" * 70000
    mod, fake_os, fs = make_runtime("success", stdout=many)
    err = expect_raise(mod.prepare_c06_runner_tls, "capture cap")
    extra = getattr(err, "fixture_c06_tls", {})
    if extra.get("stdout_cap_observations") != 1:
        raise ControlFailure(f"cap evidence unbounded: {extra.get('stdout_cap_observations')}")
    if extra.get("stdout_observed_bytes", 0) <= extra.get("stdout_retained_bytes", 0):
        raise ControlFailure("observed must exceed retained after overflow")
    if extra.get("stdout_retained_bytes", 0) > 65536:
        raise ControlFailure("retained exceeded cap")
    rec("C06_N_BOUNDED_CAP_EVIDENCE", "REFUSE", "overflow flag+counter; observed vs retained")

    class Partial(ImmediateThread):
        starts = 0

        def start(self) -> None:
            Partial.starts += 1
            if Partial.starts >= 2:
                raise RuntimeError("start-fail")
            super().start()

    Partial.starts = 0
    fs = FakeFS()
    fake_os = FakeOS(fs)
    FakePopen.mode = "success"
    FakePopen.stdout_payload = b"ok\n"
    FakePopen.stderr_payload = b""
    FakePopen.last = None
    FakePopen.clock = fake_os
    FakePopen.close_calls = []
    FakePopen.stdout_raise = False
    FakePopen.setup_advance_s = 0.0
    FakePopen.wait_advanced = 0.0
    sub = types.ModuleType("subprocess")
    sub.Popen = FakePopen
    sub.PIPE = subprocess.PIPE
    sub.DEVNULL = subprocess.DEVNULL
    sub.TimeoutExpired = subprocess.TimeoutExpired
    path_cls = lambda *parts: FakePath(fs, *parts)
    path_cls.__name__ = "FakePath"
    mod = extract_runner_c06(fake_os, sub, Partial, path_cls)
    err = expect_raise(mod.prepare_c06_runner_tls, "reader start")
    extra = getattr(err, "fixture_c06_tls", {})
    if extra.get("readers_started") != 1 or extra.get("readers_constructed") != 2:
        raise ControlFailure(f"partial start accounting {extra}")
    rec("C06_N_PARTIAL_START_RETIRE", "REFUSE", "started-only join; remaining retirement attempted")

    class ConstructFail(ImmediateThread):
        constructs = 0

        def __init__(self, target=None, args=(), name=None, daemon=None):
            ConstructFail.constructs += 1
            if ConstructFail.constructs >= 2:
                raise RuntimeError("construct-fail")
            super().__init__(target=target, args=args, name=name, daemon=daemon)

    ConstructFail.constructs = 0
    fs = FakeFS()
    fake_os = FakeOS(fs)
    FakePopen.mode = "success"
    FakePopen.stdout_payload = b"ok\n"
    FakePopen.stderr_payload = b""
    FakePopen.last = None
    FakePopen.clock = fake_os
    FakePopen.close_calls = []
    FakePopen.stdout_raise = False
    FakePopen.setup_advance_s = 0.0
    FakePopen.wait_advanced = 0.0
    sub = types.ModuleType("subprocess")
    sub.Popen = FakePopen
    sub.PIPE = subprocess.PIPE
    sub.DEVNULL = subprocess.DEVNULL
    sub.TimeoutExpired = subprocess.TimeoutExpired
    path_cls = lambda *parts: FakePath(fs, *parts)
    path_cls.__name__ = "FakePath"
    mod = extract_runner_c06(fake_os, sub, ConstructFail, path_cls)
    err = expect_raise(mod.prepare_c06_runner_tls, "RuntimeError")
    if str(err) != "RuntimeError":
        raise ControlFailure(f"constructor primary replaced: {err!r}")
    extra = getattr(err, "fixture_c06_tls", {})
    if extra.get("status") != "STOP":
        raise ControlFailure(f"constructor fail status {extra.get('status')!r}")
    if extra.get("readers_constructed") != 1 or extra.get("readers_started") != 0:
        raise ControlFailure(f"constructor accounting {extra}")
    if extra.get("owned_pipes") != 2:
        raise ControlFailure(f"constructor owned_pipes {extra.get('owned_pipes')}")
    if len(FakePopen.close_calls) != 2:
        raise ControlFailure(f"constructor close attempts {len(FakePopen.close_calls)}")
    rec("C06_N_PARTIAL_CONSTRUCT_RETIRE", "REFUSE", "two pipe closes; one constructed; zero started; primary preserved; STOP")

    mod, fake_os, fs = make_runtime("timeout", hold_readers=True)
    err = expect_raise(mod.prepare_c06_runner_tls, "timeout")
    extra = getattr(err, "fixture_c06_tls", {})
    if str(err) != "c06 generation timeout":
        raise ControlFailure(f"primary replaced: {err!r}")
    if extra.get("readers_joined") is not False:
        raise ControlFailure("dual fault missing reader retirement evidence")
    rec("C06_N_PRIMARY_PRESERVE", "REFUSE", "generation primary kept; secondary retirement attached")
    rec("C06_N_DUAL_FAULT_PRIMARY", "REFUSE", "timeout primary + unjoined secondary")

    mod, fake_os, fs = make_runtime("timeout")
    fake_os.now = 29.0
    entry = fake_os.now
    setup_advance = 12.0
    FakePopen.setup_advance_s = setup_advance
    FakePopen.wait_advanced = 0.0
    err = expect_raise(mod.prepare_c06_runner_tls, "timeout")
    elapsed = fake_os.now - entry
    gen_s = float(mod.C06_GEN_SECONDS)
    disclosed_total_s = float(mod.C06_DISCLOSED_RETIREMENT_SECONDS)
    reap_s = float(mod.C06_REAP_SECONDS)
    join_s = float(mod.C06_READER_JOIN_SECONDS)
    if disclosed_total_s != 45.0:
        raise ControlFailure(f"disclosed total must be 45: {disclosed_total_s}")
    if disclosed_total_s != gen_s + reap_s + join_s + join_s:
        raise ControlFailure(
            f"disclosed {disclosed_total_s} is not gen+reap+join+join ({gen_s}+{reap_s}+{join_s}+{join_s})"
        )
    additional_retire_s = disclosed_total_s - gen_s
    remaining_after_setup = gen_s - setup_advance
    if FakePopen.wait_advanced > remaining_after_setup + 0.05:
        raise ControlFailure(
            f"fresh wait after setup: wait_advanced={FakePopen.wait_advanced} remaining={remaining_after_setup}"
        )
    if elapsed < gen_s:
        raise ControlFailure(f"30s phase not consumed from entry: elapsed={elapsed}")
    if elapsed > disclosed_total_s:
        raise ControlFailure(
            f"elapsed {elapsed} exceeded disclosed total {disclosed_total_s}s "
            f"(gen {gen_s}s + additional retirement {additional_retire_s}s, not gen+45)"
        )
    rec("C06_N_SHARED_DEADLINE", "REFUSE", "shared 30s from entry; setup after deadline; disclosed total 45")

    rec("C06_N_OBSERVED_VS_RETAINED", "REFUSE", "observed/retained distinguished on cap extra")

    identity = dual.require_distinct_public_ca_hashes(
        b"-----BEGIN CERTIFICATE-----\nGATE\n-----END CERTIFICATE-----\n",
        b"-----BEGIN CERTIFICATE-----\nDB\n-----END CERTIFICATE-----\n",
    )
    if identity["distinct"] is not True or identity["gate_ca_sha256"] == identity["db_public_ca_sha256"]:
        raise ControlFailure("distinct public CA evidence failed")
    rec("C06_P_DISTINCT_CA", "PASS", "distinct hashes recorded")

    main_call_prepare_before_audit(runner_src)
    rec("C06_P_HOOK_ORDER", "PASS", "STATIC: AST main() prepare before addaudithook", kind="static")

    registered = sys.modules.get("c06_fake_runner")
    if registered is None or registered.__dict__ is not getattr(mod, "__dict__"):
        raise ControlFailure("synthetic runner module not registered for last extract")
    rec("C06_P_SYNTHETIC_MODULE", "PASS", "ModuleType registered; exec uses module.__dict__")

    if "mapping_control_only=True" not in suite_src or 'case_id="I01-C06-MAP"' not in suite_src:
        raise ControlFailure("C06-MAP not separate")
    rec("C06_P_MAP_SEPARATE", "PASS", "STATIC: C06-MAP remains mapping control", kind="static")

    unknown = tuple(launch["expected_unknown_cases"])
    if unknown != ("N06", "N07", "I01-C06"):
        raise ControlFailure(f"UNKNOWN inventory changed: {unknown}")
    rec("C06_P_UNKNOWN_INVENTORY", "PASS", "STATIC: N06 N07 I01-C06", kind="static")

    dual.FakeListener.occupied = True
    port_err = expect_raise(
        lambda: dual.serve_i01_c06_gate(ready=ReadyEvent(), stop=ReadyEvent(), seconds=1, gate_port=15432),
        "occupied gate port",
    )
    if dual.C06_GATE_PORT != 15432:
        raise ControlFailure("port constant changed")
    rec("C06_P_PORT_15432", "PASS", type(port_err).__name__)

    if "/bin/sh" not in runner_src or "/usr/bin/openssl" not in runner_src:
        raise ControlFailure("absolute binaries missing in runner")
    if script_src.count("/usr/bin/openssl") < 4:
        raise ControlFailure("script must call absolute openssl")
    rec("C06_P_ABS_BINARIES", "PASS", "STATIC: fixed /bin/sh and /usr/bin/openssl", kind="static")

    required = (
        "Dex-Disposable-C06-Gate-CA",
        "native-fixture.invalid",
        "rsa:3072",
        "-days 2",
        "subjectAltName=DNS:native-fixture.invalid",
        "extendedKeyUsage=serverAuth",
        "verify_hostname native-fixture.invalid",
        "umask 077",
        "TMPDIR=/tmp",
    )
    missing = [item for item in required if item not in script_src]
    if missing:
        raise ControlFailure(f"recipe literals missing: {missing}")
    if "Dex-Untrusted-Fixture-CA" in script_src:
        raise ControlFailure("untrusted CA must not be on C06 recipe")
    rec("C06_P_RECIPE_LITERALS", "PASS", "STATIC: RSA3072 CN SAN serverAuth days2", kind="static")

    if launch.get("launch_ready") is not False:
        raise ControlFailure("launch_ready is not false")
    rec("C06_P_LAUNCH_READY_FALSE", "PASS", "STATIC: false", kind="static")

    ready, result = dual.c06_artifact_paths(root=dual.C06_GATE_ROOT)
    if ready.as_posix() != "/tmp/c06-gate-tls/I01-C06.ready":
        raise ControlFailure(str(ready))
    wrong = dual.c06_artifact_paths(root=Path("/fixture-tls"))
    if wrong[0].as_posix() == ready.as_posix():
        raise ControlFailure("wrong root collapsed onto runner root")
    rec(
        "C06_N_WRONG_READY_ROOT",
        "PASS",
        "STATIC: extracted c06_artifact_paths honors explicit root (path inventory)",
        kind="static",
    )

    if "start_new_session=True" not in runner_src:
        raise ControlFailure("owned session missing")
    rec("C06_P_CHILD_ENV_PATH", "PASS", "STATIC: minimal env + new session", kind="static")

    if "public_ca_identity" not in suite_src or "require_distinct_public_ca_hashes" not in suite_src:
        raise ControlFailure("suite public CA evidence missing")
    rec("C06_P_SUITE_CA_EVIDENCE", "PASS", "STATIC: distinct hashes in C06 receipt", kind="static")

    if "load_c06_gate_receipt" not in suite_src or "root=C06_GATE_ROOT" not in suite_src:
        raise ControlFailure("receipt load root not explicit")
    rec("C06_P_EXPLICIT_ROOT_WIRING", "PASS", "STATIC: serve/ready/receipt same root", kind="static")

    if launch.get("runner_seconds") != 600 or launch.get("suite_seconds") != 900:
        raise ControlFailure("600/900 budgets changed")
    rec("C06_P_BUDGETS_UNCHANGED", "PASS", "STATIC: runner 600 suite 900", kind="static")

    return results


def verify_no_app_imports() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in PERMITTED_IMPORT_ROOTS:
                    raise ControlFailure(f"unpermitted import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root not in PERMITTED_IMPORT_ROOTS:
                raise ControlFailure(f"unpermitted from-import {node.module}")


def verify_parent_isolation() -> None:
    missing = []
    if not bool(getattr(sys.flags, "isolated", 0)):
        missing.append("-I")
    if not bool(getattr(sys.flags, "no_site", 0)):
        missing.append("-S")
    if not bool(getattr(sys.flags, "dont_write_bytecode", 0)):
        missing.append("-B")
    if missing:
        raise ControlFailure(f"parent_isolation_flags_missing:{missing}")


def main() -> int:
    verify_parent_isolation()
    verify_no_app_imports()
    expected = load_expected()
    manifest = load_manifest()
    try:
        verify_source_pins(manifest)
        verify_launch_config_pin(manifest)
        verify_fakeos_posix_join()
        controls = run_controls()
        inventory_error = None
        source_hashes_verified = True
    except ControlFailure as error:
        payload = {
            "status": "STOP",
            "class": "FAKE-C06-RUNNER-TLS",
            "kind": "ControlFailure",
            "detail": str(error),
            "executed": True,
            "held": False,
            "source_hashes_verified": False,
            "inventory_error": str(error),
        }
        RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload))
        return 1
    ordered = [item.control_id for item in controls]
    if ordered != expected["control_ids_in_order"]:
        payload = {
            "status": "STOP",
            "class": "FAKE-C06-RUNNER-TLS",
            "kind": "order_mismatch",
            "actual": ordered,
            "expected": expected["control_ids_in_order"],
            "executed": True,
            "held": False,
            "source_hashes_verified": True,
            "inventory_error": "order_mismatch",
        }
        RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload))
        return 1
    by_id = {item.control_id: item for item in controls}
    for control_id, spec in expected["controls"].items():
        actual = by_id[control_id].result
        if actual != spec["result"]:
            payload = {
                "status": "STOP",
                "class": "FAKE-C06-RUNNER-TLS",
                "kind": "result_mismatch",
                "control_id": control_id,
                "actual": actual,
                "expected": spec["result"],
                "executed": True,
                "held": False,
                "source_hashes_verified": True,
                "inventory_error": f"result_mismatch:{control_id}",
            }
            RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(payload))
            return 1
        expected_kind = spec.get("kind")
        if expected_kind and by_id[control_id].kind != expected_kind:
            payload = {
                "status": "STOP",
                "class": "FAKE-C06-RUNNER-TLS",
                "kind": "kind_mismatch",
                "control_id": control_id,
                "actual": by_id[control_id].kind,
                "expected": expected_kind,
                "executed": True,
                "held": False,
                "source_hashes_verified": True,
                "inventory_error": f"kind_mismatch:{control_id}",
            }
            RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(payload))
            return 1
    payload = {
        "status": expected["status"],
        "class": "FAKE-C06-RUNNER-TLS",
        "executed": True,
        "held": False,
        "source_hashes_verified": True,
        "inventory_error": None,
        "control_ids_in_order": ordered,
        "controls": {
            item.control_id: {
                "result": item.result,
                "detail": item.detail,
                "kind": item.kind,
            }
            for item in controls
        },
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "controls": len(ordered), "executed": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
