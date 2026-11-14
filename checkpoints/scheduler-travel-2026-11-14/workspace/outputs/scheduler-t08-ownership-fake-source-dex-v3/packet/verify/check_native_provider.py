"""HELD source preparation: finite T08 ownership properties, no execution authority.

Extract the unchanged production JoinedTLS class. Supply a numeric owner identity,
budget callback and already-owned byte socket as named fakes. No socket, TLS context,
thread, application package or vendor package is constructed/imported. Native fixture
wiring is structural only; this does not execute the native case or prove real ownership.
Requires independent review, a bounded admission packet and Trish's exact run approval.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBJECTS = HERE.parent / "subjects"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
PINS = {
    "covering_joined_https.py": "760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427",
    "np_runner_entry.py": "C7A0D2DCC8BB50165D825FC05653AF2A0BDE0F0975075C81C40E16C369CC831C",
}


class WitnessFailure(Exception):
    pass


class Refused(Exception):
    """Named fake for the production policy exception, never an application import."""


def require(condition, label):
    if not condition:
        raise WitnessFailure(label)


class OwnedSocket:
    def __init__(self):
        self.closes = 0
        self.sent = bytearray()
        self.incoming = bytearray(b"owner-response")

    def fileno(self):
        return -1 if self.closes else 17

    def close(self):
        self.closes += 1

    def send(self, data):
        self.sent.extend(data)
        return len(data)

    def recv(self, maximum):
        data = bytes(self.incoming[:maximum])
        del self.incoming[:maximum]
        return data


def extract_class(source):
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "JoinedTLS"]
    require(len(nodes) == 1, "source:unique class")
    return ast.get_source_segment(source, nodes[0])


def instance(source):
    state = {"identity": 101, "budget_calls": 0, "socket_factory_calls": 0}

    def remaining():
        state["budget_calls"] += 1
        return 123.0

    def refused_socket_factory(*args):
        state["socket_factory_calls"] += 1
        raise Refused()

    # The factory is a named fake, never a real socket. A removed reuse guard
    # reaches it and is detected by the changed budget/factory observations,
    # rather than by an unrelated missing-name exception.
    namespace = {"get_ident": lambda: state["identity"], "CoveringTransportRefused": Refused,
                 "ipaddress": types.SimpleNamespace(ip_address=lambda value: types.SimpleNamespace(version=4)),
                 "socket": types.SimpleNamespace(AF_INET=2, AF_INET6=10, SOCK_STREAM=1,
                                                  socket=refused_socket_factory),
                 "ssl": types.SimpleNamespace(SSLWantReadError=type("WantRead", (Exception,), {}),
                                               SSLWantWriteError=type("WantWrite", (Exception,), {}))}
    exec(compile(extract_class(source), "<extracted:JoinedTLS>", "exec"), namespace)
    peer = types.SimpleNamespace(address="127.0.0.1", port=443,
                                 hostname="synthetic.invalid", ca_file="fake-ca-path")
    transport = namespace["JoinedTLS"](peer, remaining)
    sock = OwnedSocket()
    transport.sock = sock  # Explicit named fake for a previously opened owned resource.
    return transport, sock, state


def refused(action, label):
    try:
        action()
    except BaseException as exc:
        require(type(exc) is Refused, label)
    else:
        raise WitnessFailure(label)


def foreign_check(source):
    transport, sock, state = instance(source)
    state["identity"] = 202
    refused(transport.check, "foreign-check:refusal")
    require(state["budget_calls"] == 0 and not transport.closed and sock.closes == 0,
            "foreign-check:no side effect")


def foreign_close(source):
    transport, sock, state = instance(source)
    state["identity"] = 202
    refused(transport.close, "foreign-close:refusal")
    require(transport.sock is sock and not transport.closed and sock.fileno() == 17
            and sock.closes == 0 and state["budget_calls"] == 0, "foreign-close:preserved")


def owner_use_close(source):
    transport, sock, state = instance(source)
    require(transport.check() == 123.0, "owner:check")
    transport.send(b"owner-request")
    require(transport.receive(5) == b"owner" and transport.receive(100) == b"-response"
            and bytes(sock.sent) == b"owner-request" and transport.sent is True,
            "owner:finite byte use")
    transport.close()
    transport.close()
    require(transport.closed is True and sock.closes == 1 and sock.fileno() == -1,
            "owner:single retirement")
    calls = state["budget_calls"]
    refused(transport.check, "owner:closed refusal")
    require(state["budget_calls"] == calls, "owner:closed no budget call")


def reuse(source):
    transport, sock, state = instance(source)
    refused(transport.open, "reuse:live refusal")
    require(transport.sock is sock and not transport.closed and sock.closes == 0
            and state["budget_calls"] == 0 and state["socket_factory_calls"] == 0,
            "reuse:live resource preserved")
    transport.close()
    refused(transport.open, "reuse:retired refusal")
    require(transport.sock is sock and sock.closes == 1 and sock.fileno() == -1,
            "reuse:retired resource preserved")


def native_wiring(source):
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_run_np_t08_ownership"]
    require(len(nodes) == 1, "wiring:unique case")
    fn = nodes[0]
    text = ast.get_source_segment(source, fn)
    require("from app.services.covering_joined_https import JoinedTLS" in text
            and "from app.services.covering_request_budget import CoveringRequestBudget" in text
            and "daemon=False" in text and "foreign.join(timeout=5.0)" in text
            and "not foreign_join_attempted" in text and "not peer_retirement_attempted" in text,
            "wiring:actual transport and bounded ownership")
    require("transport.sock is not owned_socket" in text and "owned_socket.fileno() != owned_fd" in text
            and "bytes(received) != expected_wire" in text and "owned_socket.fileno() != -1" in text
            and "_retire_selected_peer_then_observe(peer, join_seconds=5.0)" in text,
            "wiring:resource guards")
    require(not any(isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                    and n.attr in ("owner", "sock") for n in ast.walk(fn)), "wiring:no ownership rewrite")


def mutants(source):
    proposals = (
        ("foreign_check_guard", "        if get_ident()!=self.owner or self.closed:\n",
         "        if self.closed:\n", foreign_check, "foreign-check:refusal"),
        ("foreign_close_guard", "        if get_ident()!=self.owner:\n",
         "        if False:\n", foreign_close, "foreign-close:refusal"),
        ("reuse_guard", "    def open(self):\n        if self.sock is not None:\n",
         "    def open(self):\n        if False:\n", reuse, "reuse:live resource preserved"),
    )
    outcomes = {}
    for name, before, after, oracle, prefix in proposals:
        require(source.count(before) == 1, "mutant:unique anchor:" + name)
        try:
            oracle(source.replace(before, after))
        except WitnessFailure as exc:
            require(str(exc).startswith(prefix), "mutant:unrelated failure:" + name)
        except BaseException:
            raise WitnessFailure("mutant:unrelated exception:" + name) from None
        else:
            raise WitnessFailure("mutant:survived:" + name)
        outcomes[name] = "DETECTED"
    return outcomes


def run():
    require(not RESULT.exists(), "result:existing output")
    subjects = {}
    for name, pin in PINS.items():
        raw = (SUBJECTS / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest().upper() == pin, "source:pin:" + name)
        subjects[name] = raw.decode("utf-8")
    production = subjects["covering_joined_https.py"]
    controls = {"SUBJECT-PINS": "PASS"}
    for name, oracle in (("FOREIGN-CHECK", foreign_check), ("FOREIGN-CLOSE", foreign_close),
                         ("OWNER-USE-CLOSE", owner_use_close), ("SAME-INSTANCE-REUSE", reuse)):
        oracle(production)
        controls[name] = "PASS"
    native_wiring(subjects["np_runner_entry.py"])
    controls["NATIVE-WIRING-STRUCTURAL"] = "PASS"
    mutation_results = mutants(production)
    controls["ACTUAL-SOURCE-MUTANTS"] = "PASS"
    result = {"kind": "t08-ownership-finite-fake", "executed": True, "native_proof": False,
              "controls": controls, "mutants": mutation_results, "endpoint": "unbound",
              "limitations": ["Fake owner identity and already-owned socket; no real thread or TLS",
                              "Native case wiring is structural; case body and retirement paths unexecuted"]}
    encoded = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    require(len(encoded) <= 262144, "result:byte cap")
    with RESULT.open("xb") as stream:
        stream.write(encoded)


if __name__ == "__main__":
    try:
        run()
    except BaseException as exc:
        print("STOP:" + type(exc).__name__, file=sys.stderr)
        raise SystemExit(125)
