"""S2-V4 CLI forwards assignment bodies, including deferred-form keys."""

from __future__ import annotations

import pytest

from theplan.commands.scheduling import run_scheduling
from theplan.main import _build_parser
from theplan.output import set_output_format

TASK_ID = "00000000-0000-0000-0000-000000000020"


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def test_family_replace_forwards_deferred_and_forbidden_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_api(method: str, path: str, json_body=None):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json_body
        return {
            "scope": "task",
            "scope_id": TASK_ID,
            "family": "new_rule",
            "scheduling_revision": 4,
        }

    body = {
        "expected_revision": 3,
        "target_family": "new_rule",
        "on": "2026-10-13",
        "weekdays": [0],
        "context": "home",
        "ignore_all_restrictions": True,
    }
    monkeypatch.setattr("theplan.commands.scheduling.api_json", fake_api)
    monkeypatch.setattr(
        "theplan.commands.scheduling.read_json_body",
        lambda **_kwargs: body,
    )
    set_output_format("json")
    run_scheduling(
        _parse(
            [
                "scheduling",
                "family-replace",
                "--scope",
                "task",
                "--id",
                TASK_ID,
                "--stdin",
            ]
        )
    )
    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/v1/tasks/{TASK_ID}/scheduling/assignment/family-replace"
    assert captured["body"]["on"] == "2026-10-13"
    assert captured["body"]["weekdays"] == [0]
    assert captured["body"]["context"] == "home"
    assert captured["body"]["ignore_all_restrictions"] is True


def test_rule_remove_named_forwards_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI ``rule-remove-named`` → POST …/rules/remove-named (V4-D4)."""
    captured: dict = {}

    def fake_api(method: str, path: str, json_body=None):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json_body
        return {
            "scope": "project",
            "scope_id": TASK_ID,
            "scheduling_revision": 9,
            "rule": None,
            "exception": {
                "id": "00000000-0000-0000-0000-000000000099",
                "operation": "waive_named",
                "target_rule_name": "office",
                "target_rule_kind": "must",
            },
        }

    body = {
        "expected_revision": 8,
        "operation": "waive_named",
        "target_rule_name": "office",
    }
    monkeypatch.setattr("theplan.commands.scheduling.api_json", fake_api)
    monkeypatch.setattr(
        "theplan.commands.scheduling.read_json_body",
        lambda **_kwargs: body,
    )
    set_output_format("json")
    run_scheduling(
        _parse(
            [
                "scheduling",
                "rule-remove-named",
                "--scope",
                "project",
                "--id",
                TASK_ID,
                "--stdin",
            ]
        )
    )
    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/v1/projects/{TASK_ID}/scheduling/rules/remove-named"
    assert captured["body"]["operation"] == "waive_named"
    assert captured["body"]["target_rule_name"] == "office"
    assert captured["body"]["expected_revision"] == 8
