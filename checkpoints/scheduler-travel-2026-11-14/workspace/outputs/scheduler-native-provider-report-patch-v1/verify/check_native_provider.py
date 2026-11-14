"""HELD report-boundary contribution; source preparation, not executed.

Exercises extracted proposed runner main and exact host attach method with fake
modules/streams/Docker objects only. No app/vendor imports, sockets or children.
This is not the complete native-provider verification packet or launch authority.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "payload/fixture/np_runner_entry.py"
HOST = ROOT / "original_inputs/np_supervisor.py.source"
RUNNER_PIN = "B910EC04CDA020BC68C2FC8A754E2D0D2EC693E4ECF74AAB1CD24D181CB1AFC1"
HOST_PIN = "28248F6E9BC67362AB22B66BAB7756BF5F61D6727C4808A4A2F0B8587A4FD81F"
RESULT = ROOT / "verify/REPORT-BOUNDARY-RESULT.json"
CASE = "NP-V-MS-NONEXPIRED"
SENTINEL = "fixture-console-observation"
IDS = (
    "REPORT-TOP-LEVEL-AND-CASE-EVIDENCE",
    "CONSOLE-HASH-ONLY",
    "SUCCESS-STREAM-RESTORATION",
    "FAILURE-STREAM-RESTORATION",
    "REPORT-BYTE-CAP",
    "SANITIZED-ENTRY-STOP",
    "ACTUAL-HOST-CONSUMER-ROUNDTRIP",
    "HOST-REFUSES-WRONG-RUNTIME",
    "HOST-REFUSES-WRONG-CA",
    "HOST-REFUSES-DAEMON-CLAIM",
    "HOST-REFUSES-RUNNER-OWNERSHIP",
    "HOST-REFUSES-MALFORMED-JSON",
    "HOST-REFUSES-OLD-NESTED-SCHEMA",
    "MUTANT-REPORT-IN-CONSOLE-DETECTED",
    "MUTANT-MISSING-RESTORATION-DETECTED",
)


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def admitted_source(path: Path, expected: str) -> str:
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest().upper() == expected, "source pin")
    return raw.decode("utf-8")


def suite_report() -> dict[str, Any]:
    return {
        "case_ids": [CASE], "passed": 1, "failed": 0, "skipped": 0,
        "joined_workers": True, "unexpected_unknown": 0,
        "expected_unknown_cases": [], "runtime_pins": {"fixture": "pinned"},
        "ca_sha256": "A" * 64, "docker_daemon_calls": 0,
        "host_docker_ownership": False,
    }


@contextmanager
def fake_modules(run_suite):
    replacements = {}
    old = {}
    integrated = types.ModuleType("np_integrated_runner")
    integrated.run_suite = run_suite
    receipts = types.ModuleType("np_receipts")
    # Isolate the producer/consumer schema; actual sanitizer is a separate gap.
    receipts.build_receipt = lambda **fields: dict(fields)
    replacements.update(np_integrated_runner=integrated, np_receipts=receipts)
    for name, module in replacements.items():
        old[name] = sys.modules.get(name)
        sys.modules[name] = module
    try:
        yield
    finally:
        for name in replacements:
            if old[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old[name]


def producer_env(source: str, *, cap: int = 1048576) -> dict[str, Any]:
    tree = ast.parse(source)
    selected = [copy.deepcopy(node) for node in tree.body if
                isinstance(node, (ast.ClassDef, ast.FunctionDef)) and
                node.name in {"RunnerEntryHeld", "BoundedOutput", "main"}]
    require(len(selected) == 3, "producer definition inventory")
    config = {"case_ids": [CASE], "runtime_pins": {"fixture": "pinned"}}
    env = {
        "hashlib": hashlib, "json": json, "sys": sys, "Any": Any,
        "ROOT": ROOT, "RUNNER_CONFIG_NAME": "unused-fake-config.json",
        "OUTPUT_BYTE_CAP": cap, "IMPLEMENTED_CASE_IDS": {CASE},
        "admit_runner_identity": lambda: None,
        "load_runner_config": lambda path: config,
        "implementation_status_map": lambda ids: {cid: "IMPLEMENTED" for cid in ids},
        "build_registry_from_suite": lambda ids: {cid: object() for cid in ids},
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), "<pinned-report-producer>", "exec"), env)
    return env


def invoke_producer(source: str, *, failure: bool = False, cap: int = 1048576):
    env = producer_env(source, cap=cap)
    out, err = io.StringIO(), io.StringIO()
    prior_out, prior_err = sys.stdout, sys.stderr
    observed = {"error": None, "restored": False, "exit": None}

    def fake_suite(**kwargs):
        print(SENTINEL)
        if failure:
            raise RuntimeError("fixture-primary-message-must-not-be-emitted")
        kwargs["record_case"](CASE, {"case_id": CASE, "passed": True})
        return suite_report()

    try:
        sys.stdout, sys.stderr = out, err
        with fake_modules(fake_suite):
            try:
                observed["exit"] = env["main"]()
            except BaseException as exc:
                observed["error"] = type(exc).__name__
        observed["restored"] = sys.stdout is out and sys.stderr is err
    finally:
        sys.stdout, sys.stderr = prior_out, prior_err
    observed.update(stdout=out.getvalue(), stderr=err.getvalue())
    return observed


def host_consumer(source: str):
    tree = ast.parse(source)
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ProviderDockerOps")
    node = copy.deepcopy(next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "run_attached"))
    node.name = "consume"
    env = {"json": json, "Any": Any}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<pinned-host-consumer>", "exec"), env)
    return env["consume"]


def consume(consumer, wire: bytes):
    events = []

    class Inner:
        c = {"runner_seconds": 600, "runner_runtime_pins": {"fixture": "pinned"}}
        ca_hash = "A" * 64

        def _id(self, identifier):
            require(identifier == "b" * 64, "owned identifier")

        def _cmd(self, args, deadline, *, cap):
            require(args == ["start", "--attach", "b" * 64], "exact fake attach")
            events.append("attach")
            return wire

    fake = types.SimpleNamespace(
        _inner=Inner(), reuse_legacy_gate_protocol=False,
        record=lambda event, data: events.append(event), ca_hash=None,
    )
    return consumer(fake, "b" * 64, deadline=100.0), events


def run_all() -> dict[str, Any]:
    runner = admitted_source(RUNNER, RUNNER_PIN)
    host = admitted_source(HOST, HOST_PIN)
    results = []

    def passed(identifier: str):
        results.append({"id": identifier, "outcome": "PASS"})

    baseline = invoke_producer(runner)
    require(baseline["exit"] == 0 and baseline["error"] is None, "producer normal exit")
    report = json.loads(baseline["stdout"])
    require(all(report[key] == value for key, value in suite_report().items()), "flat suite fields")
    require(report["case_results"] == [{"case_id": CASE, "result": {"case_id": CASE, "passed": True}}], "case evidence")
    require(report["executed"] is True and "launch_authorized" not in report, "observed execution versus human authority")
    passed(IDS[0])
    require(SENTINEL not in baseline["stdout"] and not baseline["stderr"], "console not emitted")
    require(report["console_sha256"] == hashlib.sha256((SENTINEL + "\n").encode()).hexdigest().upper(), "console digest")
    passed(IDS[1])
    require(baseline["restored"], "normal stream restoration")
    passed(IDS[2])
    failed = invoke_producer(runner, failure=True)
    require(failed["error"] == "RuntimeError" and failed["restored"] and not failed["stdout"] and not failed["stderr"], "exception restoration")
    passed(IDS[3])
    tiny = invoke_producer(runner, cap=64)
    require(tiny["error"] == "RunnerEntryHeld" and tiny["restored"] and not tiny["stdout"], "reduced report cap refusal")
    passed(IDS[4])

    # Exercise the exact proposed __main__ statements with a fake failing main.
    guard = next(n for n in ast.parse(runner).body if isinstance(n, ast.If) and
                 isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name) and n.test.left.id == "__name__")
    out, err = io.StringIO(), io.StringIO()
    prior_out, prior_err = sys.stdout, sys.stderr

    def failed_main():
        raise RuntimeError("fixture-message-must-not-cross-boundary")

    try:
        sys.stdout, sys.stderr = out, err
        try:
            exec(compile(ast.Module(body=copy.deepcopy(guard.body), type_ignores=[]), "<pinned-entry-guard>", "exec"), {"main": failed_main, "sys": sys, "json": json})
        except SystemExit as exc:
            require(exc.code == 125, "entry STOP exit")
    finally:
        sys.stdout, sys.stderr = prior_out, prior_err
    require(not out.getvalue() and json.loads(err.getvalue()) == {"status": "STOP", "kind": "RuntimeError"}, "sanitized entry metadata")
    passed(IDS[5])

    consumer = host_consumer(host)
    observed, events = consume(consumer, baseline["stdout"].encode())
    require(observed == report and events == ["attach", "provider_attach_report"], "producer to actual consumer")
    passed(IDS[6])
    for identifier, key, value in (
        (IDS[7], "runtime_pins", {"fixture": "wrong"}),
        (IDS[8], "ca_sha256", "C" * 64),
        (IDS[9], "docker_daemon_calls", 1),
        (IDS[10], "host_docker_ownership", True),
    ):
        bad = copy.deepcopy(report)
        bad[key] = value
        refused = False
        try:
            consume(consumer, json.dumps(bad).encode())
        except RuntimeError:
            refused = True
        require(refused, identifier)
        passed(identifier)
    for identifier, wire in ((IDS[11], b"not-json"), (IDS[12], json.dumps({"report": report}).encode())):
        refused = False
        try:
            consume(consumer, wire)
        except (RuntimeError, json.JSONDecodeError):
            refused = True
        require(refused, identifier)
        passed(identifier)

    require(runner.count("machine_stdout.write(payload)") == 1, "mutation target")
    mutant = invoke_producer(runner.replace("machine_stdout.write(payload)", "console.write(payload)"))
    require(not mutant["stdout"], "swallowed-report mutant distinguished")
    passed(IDS[13])
    target = "sys.stdout, sys.stderr = machine_stdout, machine_stderr"
    require(runner.count(target) == 1, "restoration mutation target")
    mutant = invoke_producer(runner.replace(target, "pass  # mutation: omit restoration"), failure=True)
    require(not mutant["restored"], "missing-restoration mutant distinguished")
    passed(IDS[14])
    require(tuple(row["id"] for row in results) == IDS, "exact control inventory")
    return {
        "status": "PASS", "scope": "extracted report-boundary/fake-consumer controls only",
        "controls": results, "passed": len(results),
        "runner_sha256": RUNNER_PIN, "host_sha256": HOST_PIN,
        "actual_sanitizer_verified": False, "native_or_app_behavior_verified": False,
        "endpoint": "unbound",
    }


if __name__ == "__main__":
    if RESULT.exists():
        raise SystemExit("STOP: existing evidence; no replay")
    output = run_all()
    payload = (json.dumps(output, indent=2) + "\n").encode()
    require(len(payload) <= 262144, "result cap")
    with RESULT.open("xb") as handle:
        handle.write(payload)
