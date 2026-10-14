"""S2-V4b CLI forwards day-scoped bodies. It does not strip dated or overlap keys."""

from __future__ import annotations

import pytest

from theplan.commands.scheduling import run_scheduling
from theplan.main import _build_parser
from theplan.output import set_output_format

TASK_ID = "00000000-0000-0000-0000-000000000020"


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def _capture(monkeypatch: pytest.MonkeyPatch, argv: list[str], body: dict) -> dict:
    captured: dict = {}

    def fake_api(method: str, path: str, json_body=None):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json_body
        return {
            "scope": "task",
            "scope_id": TASK_ID,
            "scheduling_revision": 4,
            "op": {"id": "op-1", "op_kind": "change_selected", "selector_kind": "one_date"},
        }

    monkeypatch.setattr("theplan.commands.scheduling.api_json", fake_api)
    monkeypatch.setattr("theplan.commands.scheduling.read_json_body", lambda **_kwargs: body)
    set_output_format("json")
    run_scheduling(_parse(argv))
    return captured


def test_day_change_selected_forwards_selectors_overlap_and_reject_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {
        "expected_revision": 3,
        "on_date": "2026-10-13",
        "weekdays": [0],
        "date_range": {"start": "2026-10-13", "end": "2026-10-13"},
        "expires_at": "2026-10-14T01:00:00+00:00",
        "replaces_op_ids": ["00000000-0000-0000-0000-000000000099"],
        "addition_survives": True,
        "empty_set": False,
        "context": "home",
        "ignore_all": True,
    }
    captured = _capture(
        monkeypatch,
        [
            "scheduling",
            "day-change-selected",
            "--scope",
            "task",
            "--id",
            TASK_ID,
            "--stdin",
        ],
        body,
    )
    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/v1/tasks/{TASK_ID}/scheduling/day/change-selected"
    assert captured["body"] == body


def test_day_only_allow_and_add_scoped_keep_the_same_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {
        "expected_revision": 8,
        "on_date": "2026-10-12",
        "expires_at": "2026-10-13T00:00:00+00:00",
        "addition_survives": False,
        "context_id": "office",
        "ignore_all_restrictions": True,
    }
    only = _capture(
        monkeypatch,
        [
            "scheduling",
            "day-only-allow",
            "--scope",
            "task",
            "--id",
            TASK_ID,
            "--stdin",
        ],
        body,
    )
    assert only["path"] == f"/api/v1/tasks/{TASK_ID}/scheduling/day/only-allow"
    assert only["body"]["addition_survives"] is False
    assert only["body"]["context_id"] == "office"
    assert only["body"]["ignore_all_restrictions"] is True
    assert "on_date" in only["body"]

    added = _capture(
        monkeypatch,
        [
            "scheduling",
            "rule-add-scoped",
            "--scope",
            "epic",
            "--id",
            TASK_ID,
            "--stdin",
        ],
        body,
    )
    assert added["path"] == f"/api/v1/epics/{TASK_ID}/scheduling/rules/add-scoped"
    assert added["body"] == body
