"""UNEXECUTED contribution: extracted mapped-coverage helper controls.

Integrate into Jim's complete admitted fake packet before requesting a run.
This file is not an invocation or launch authority. No application imports occur:
the extracted helper's app.models import resolves only to a locally installed fake.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "payload" / "fixture" / "np_auth_seed.py"
SOURCE_SHA256 = "9EEF50BCAC923E43F9C7FED767DB541210E185A3B41E58DEEC612E77E5A38C7C"
CONTROL_IDS = (
    "COVERAGE-MAPPED-BEFORE",
    "COVERAGE-MAPPED-AFTER",
    "COVERAGE-MAPPED-MIXED",
    "COVERAGE-MISSING-ROW-REFUSES",
    "COVERAGE-MISSING-ATTRIBUTE-REFUSES",
    "COVERAGE-INVENTED-SUCCESS-MUTANT-REJECTED",
    "COVERAGE-INVENTED-GENERATION-MUTANT-REJECTED",
)


def require(value, label):
    if value is not True:
        raise AssertionError(label)


def load_definition():
    raw = SOURCE.read_bytes()
    require(hashlib.sha256(raw).hexdigest().upper() == SOURCE_SHA256, "source pin")
    tree = ast.parse(raw.decode("utf-8"), filename="np_auth_seed.py")
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == "measure_subscription_coverage_state"]
    require(len(matches) == 1, "exact source definition")
    return matches[0]


def extracted(definition):
    module = ast.Module(body=[copy.deepcopy(definition)], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"__builtins__": __builtins__}
    # Annotation names are intentionally fake; only the selected function executes.
    namespace.update(UUID=object, Any=object)
    exec(compile(module, "extracted_measurement", "exec"), namespace)
    return namespace["measure_subscription_coverage_state"]


class FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def get(self, model, row_id):
        require(model is FakeSubscription, "fake model identity")
        return self.rows.get(row_id)


class FakeSubscription:
    pass


STAMP = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
END = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def row(row_id, *, success):
    # Deliberately expose only the real mapped attribute names used by this helper.
    return SimpleNamespace(id=row_id, coverage_active_generation=1 if success else 0,
        coverage_success_generation=1 if success else None,
        coverage_window_start=STAMP if success else None,
        coverage_window_end=END if success else None,
        coverage_success_at=STAMP if success else None)


def call(fn, rows):
    return fn(FakeDB(rows), subscription_ids=list(rows))


def assert_before(fn):
    result = call(fn, {"a": row("a", success=False)})
    expected = {"subscriptions": [{"subscription_id": "a",
        "coverage_active_generation": 0, "coverage_success_generation": None,
        "coverage_window_start": None, "coverage_window_end": None,
        "coverage_success_at": None, "has_covering_success": False}],
        "any_covering_success": False, "all_covering_success": False}
    require(result == expected, "exact before fields")


def assert_after(fn):
    result = call(fn, {"a": row("a", success=True)})
    expected = {"subscriptions": [{"subscription_id": "a",
        "coverage_active_generation": 1, "coverage_success_generation": 1,
        "coverage_window_start": STAMP.isoformat(), "coverage_window_end": END.isoformat(),
        "coverage_success_at": STAMP.isoformat(), "has_covering_success": True}],
        "any_covering_success": True, "all_covering_success": True}
    require(result == expected, "exact after fields")
    measured = result["subscriptions"][0]
    require(type(measured["coverage_active_generation"]) is int, "active generation type")
    require(type(measured["coverage_success_generation"]) is int, "success generation type")


def refuses(fn, expected_type):
    try:
        fn()
    except expected_type:
        return
    raise AssertionError("expected refusal missing")


def main():
    if "app" in sys.modules or "app.models" in sys.modules:
        raise RuntimeError("ambient app import refused")
    app_fake = ModuleType("app")
    app_fake.__path__ = []
    models_fake = ModuleType("app.models")
    models_fake.CalendarSubscription = FakeSubscription
    sys.modules["app"] = app_fake
    sys.modules["app.models"] = models_fake
    try:
        definition = load_definition()
        fn = extracted(definition)
        completed = []
        assert_before(fn)
        completed.append(CONTROL_IDS[0])
        assert_after(fn)
        completed.append(CONTROL_IDS[1])
        mixed = call(fn, {"a": row("a", success=False), "b": row("b", success=True)})
        require(mixed["any_covering_success"] is True, "mixed any")
        require(mixed["all_covering_success"] is False, "mixed all")
        completed.append(CONTROL_IDS[2])
        refuses(lambda: fn(FakeDB({}), subscription_ids=["absent"]), RuntimeError)
        completed.append(CONTROL_IDS[3])
        broken = row("a", success=True)
        del broken.coverage_success_at
        refuses(lambda: call(fn, {"a": broken}), AttributeError)
        completed.append(CONTROL_IDS[4])
        for control_id, actual, invented in (
            (CONTROL_IDS[5], "coverage_success_at", "last_covering_success_at"),
            (CONTROL_IDS[6], "coverage_active_generation", "covering_generation"),
        ):
            mutant = copy.deepcopy(definition)
            changed = 0
            for node in ast.walk(mutant):
                if isinstance(node, ast.Attribute) and node.attr == actual:
                    node.attr = invented
                    changed += 1
            require(changed > 0, "actual-source mutation reached")
            mutant_fn = extracted(mutant)
            refuses(lambda: assert_after(mutant_fn), (AttributeError, AssertionError))
            completed.append(control_id)
        require(tuple(completed) == CONTROL_IDS, "exact control inventory")
        print(json.dumps({"status": "PASS", "control_count": len(completed),
            "control_ids": completed, "source_sha256": SOURCE_SHA256}, sort_keys=True))
    finally:
        del sys.modules["app.models"]
        del sys.modules["app"]


if __name__ == "__main__":
    main()
