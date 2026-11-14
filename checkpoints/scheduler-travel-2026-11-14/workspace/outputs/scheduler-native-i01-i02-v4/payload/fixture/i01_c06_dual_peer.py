"""I01-C06 dual-peer CoveringReleaseBinding + post-flush commit arm wrap + gate."""
from __future__ import annotations

import hashlib
import json
import socket
import ssl
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic
from types import MethodType
from typing import Callable

from app.services.covering_domain_adapters import make_domain_ports
from app.services.covering_http_dispatch import CoveringReleaseBinding
from app.services.covering_http_transport import CoveringHTTP
from app.services.covering_native_orm_factory import CoveringORMConnection, NativeORMFactories
from app.services.covering_parent_adapter import RootCommand
from app.services.covering_role_connector import ParentBinding
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.services.covering_transport_policy import ProviderCounter, approved_provider_limits
from tls_ack_gate import serve_one

# Case-owned artifacts — must not collide with baseline N06.ready / N06.result.json.
# Runner-owned root is distinct from DB /fixture-tls and from backend public CA.
C06_GATE_ARTIFACT_STEM = "I01-C06"
C06_GATE_PORT = 15432
C06_GATE_ROOT = Path("/tmp/c06-gate-tls")
C06_GATE_CLIENT_CA = "/tmp/c06-gate-tls/ca.crt"
C06_BACKEND_DB_CA = "/public-ca/ca.crt"


def c06_artifact_paths(
    *,
    artifact_stem: str = C06_GATE_ARTIFACT_STEM,
    root: Path | None = None,
) -> tuple[Path, Path]:
    base = root if root is not None else C06_GATE_ROOT
    return base / f"{artifact_stem}.ready", base / f"{artifact_stem}.result.json"


def require_distinct_public_ca_hashes(gate_ca: bytes, db_ca: bytes) -> dict:
    """Public material only. Never hash or transfer DB/gate private keys."""
    if not gate_ca or not db_ca:
        raise C06GateError("public CA material missing")
    gate_h = hashlib.sha256(gate_ca).hexdigest().upper()
    db_h = hashlib.sha256(db_ca).hexdigest().upper()
    if gate_h == db_h:
        raise C06GateError("public gate CA hash must be distinct from DB public CA hash")
    return {
        "gate_ca_path": C06_GATE_CLIENT_CA,
        "gate_ca_sha256": gate_h,
        "db_public_ca_path": C06_BACKEND_DB_CA,
        "db_public_ca_sha256": db_h,
        "distinct": True,
    }


class C06ArmError(RuntimeError):
    pass


class C06GateError(RuntimeError):
    pass


def wrap_parent_factory_for_lost_ack(parent_factory: Callable, *, arm_fired: Event) -> Callable:
    """Wrap parent_factory so the gate-peer driver's commit arms after ORM flush.

    Reconciled override: after marker send/drain, call the SAVED ORIGINAL
    CoveringORMConnection.commit bound method — never psycopg.Connection.commit
    directly. Production commit guard / terminal / budget paths stay untouched.
    """

    def wrapped(target, remaining):
        binding = parent_factory(target, remaining)
        if type(binding) is not ParentBinding:
            raise C06ArmError("parent_factory did not return ParentBinding")
        driver = binding.driver
        if type(driver) is not CoveringORMConnection:
            raise C06ArmError("selected driver identity is not CoveringORMConnection")
        # Save the real bound method before instance replacement.
        original_commit = driver.commit
        if not isinstance(original_commit, MethodType):
            original_commit = MethodType(CoveringORMConnection.commit, driver)

        def armed_commit(self_driver=driver):
            if arm_fired.is_set():
                return original_commit()
            operation = self_driver.operation
            if operation is None or operation.command is not RootCommand.COMMIT:
                return original_commit()
            # Validate: no prior terminal/cutoff/busy; cursor admission still legal.
            if self_driver.terminal is not None or self_driver._cutoff or self_driver._busy:
                raise C06ArmError("driver not eligible for lost-ack arm")
            self_driver._guard()
            orm = self_driver.orm
            if orm is not None:
                if orm.new or orm.dirty or orm.deleted:
                    raise C06ArmError("pending ORM work before arm refused")
            # One-time arming after ORM flush, before terminal COMMIT bytes.
            with self_driver.cursor() as cur:
                cur.execute("SELECT 1 /* dex-arm-lost-ack */", prepare=False, binary=False)
                row = cur.fetchone()
                if row != (1,):
                    raise C06ArmError("arm marker response mismatch")
                if cur.fetchone() is not None:
                    raise C06ArmError("arm marker trailing row")
            arm_fired.set()
            # Retain production commit guard by invoking the saved original method.
            return original_commit()

        def commit_wrapper():
            return armed_commit()

        driver.commit = commit_wrapper  # type: ignore[method-assign]
        return binding

    return wrapped


def build_c06_dual_peer_binding(
    *,
    profile,
    password_supplier,
    runtime_pins,
    settings,
    provider_routes,
    transport_factory,
    gate_port: int = C06_GATE_PORT,
    arm_fired: Event | None = None,
) -> tuple[CoveringReleaseBinding, Event]:
    """Exact-type CoveringReleaseBinding: direct sessions + gate parent only."""
    latch = arm_fired if arm_fired is not None else Event()
    if profile.ca_file != C06_BACKEND_DB_CA:
        raise C06ArmError("direct profile must retain backend DB CA")
    direct = NativeORMFactories(
        profile=profile,
        password_supplier=password_supplier,
        runtime_pins=runtime_pins,
    )
    gate_profile = replace(profile, port=gate_port, ca_file=C06_GATE_CLIENT_CA)
    if gate_profile.ca_file == profile.ca_file or gate_profile.port == profile.port:
        raise C06ArmError("gate client CA and port must be distinct from backend DB")
    gate = NativeORMFactories(
        profile=gate_profile,
        password_supplier=password_supplier,
        runtime_pins=runtime_pins,
    )
    counter = ProviderCounter(approved_provider_limits(), lambda: 210.0)
    transport = CoveringHTTP(
        counter=counter,
        routes=provider_routes,
        transport_factory=transport_factory,
    )
    domain_ports = make_domain_ports(settings=settings, transport=transport)
    parent_factory = wrap_parent_factory_for_lost_ack(gate.parent_factory, arm_fired=latch)
    binding = CoveringReleaseBinding(
        parent_factory=parent_factory,
        session_factory=direct.session_factory,
        domain_ports=domain_ports,
    )
    if type(binding) is not CoveringReleaseBinding:
        raise CoveringRootOutcomeUnknown()
    return binding, latch


def serve_i01_c06_gate(
    *,
    ready: Event,
    stop: Event,
    seconds: int = 120,
    artifact_stem: str = C06_GATE_ARTIFACT_STEM,
    gate_port: int = C06_GATE_PORT,
    root: Path | None = None,
) -> dict:
    """Case-owned N06-equivalent gate; unique ready/result names; stop closes listener.

    Reuses reviewed tls_ack_gate.serve_one. Does not call gate_service.serve_case
    (which exclusively creates baseline N06.* evidence files).
    """
    if type(seconds) is not int or not 1 <= seconds <= 240:
        raise C06GateError("explicit bounded gate deadline required")
    base = root if root is not None else C06_GATE_ROOT
    ready_path, result_path = c06_artifact_paths(artifact_stem=artifact_stem, root=base)
    end = monotonic() + seconds
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = ssl.TLSVersion.TLSv1_2
    server.load_cert_chain(base / "server.crt", base / "server.key")
    backend = ssl.create_default_context(cafile=C06_BACKEND_DB_CA)
    backend.minimum_version = ssl.TLSVersion.TLSv1_2
    armed = Event()
    evidence: dict = {
        "case_id": artifact_stem,
        "complete": False,
        "terminal": "COMMIT",
    }
    listener: socket.socket | None = None

    def _close_listener() -> None:
        nonlocal listener
        sock = listener
        listener = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", gate_port))
        except OSError as exc:
            raise C06GateError("occupied gate port") from exc
        listener.listen(1)
        listener.settimeout(0.2)
        with ready_path.open("x", encoding="ascii") as handle:
            handle.write("READY\n")
        ready.set()
        client = None
        while monotonic() < end:
            if stop.is_set():
                raise C06GateError("gate stopped before accept")
            try:
                client, _ = listener.accept()
                break
            except socket.timeout:
                continue
        if client is None:
            raise C06GateError("gate accept deadline")
        with client:
            _close_listener()
            serve_one(
                client,
                server_context=server,
                backend_context=backend,
                backend_port=5432,
                deadline=end,
                terminal=b"COMMIT",
                armed=armed,
                receipt=evidence,
            )
        evidence["complete"] = True
    except BaseException as error:
        evidence["failure_type"] = type(error).__name__
        raise
    finally:
        _close_listener()
        with result_path.open("x", encoding="ascii") as handle:
            json.dump(evidence, handle, sort_keys=True)
    return evidence


def load_c06_gate_receipt(
    *,
    artifact_stem: str = C06_GATE_ARTIFACT_STEM,
    root: Path | None = None,
) -> dict:
    base = root if root is not None else C06_GATE_ROOT
    _ready_path, path = c06_artifact_paths(artifact_stem=artifact_stem, root=base)
    if not path.is_file():
        raise C06GateError("gate result file missing")
    receipt = json.loads(path.read_text(encoding="ascii"))
    if receipt.get("complete") is not True:
        raise C06GateError("gate receipt incomplete")
    if receipt.get("backend_tag") != "COMMIT":
        raise C06GateError("gate backend_tag mismatch")
    if receipt.get("backend_idle") is not True:
        raise C06GateError("gate backend_idle mismatch")
    if receipt.get("terminal_response_bytes_forwarded") != 0:
        raise C06GateError("gate terminal bytes forwarded mismatch")
    if receipt.get("fault") != "acknowledgment_withheld":
        raise C06GateError("gate fault mismatch")
    return receipt
