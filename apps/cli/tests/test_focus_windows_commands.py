"""DEF-045 — focus-windows list/get discovery (no live API)."""

from __future__ import annotations

import pytest

from theplan.commands.focus_windows import run_focus_windows
from theplan.main import _build_parser
from theplan.output import set_output_format

WINDOW_ID = "00000000-0000-0000-0000-000000000070"


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def test_focus_windows_list_and_get(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    sample = {
        "id": WINDOW_ID,
        "name": "Afternoon",
        "strict_mode": False,
        "bands": [
            {
                "tier": "green",
                "start_time": "13:00:00",
                "end_time": "17:00:00",
                "days_of_week": 31,
            }
        ],
    }

    def fake_api(method: str, path: str, **_kwargs):
        calls.append((method, path))
        if path.endswith("/focus-windows"):
            return {"data": [sample]}
        return sample

    monkeypatch.setattr("theplan.commands.focus_windows.api_json", fake_api)
    set_output_format("json")
    run_focus_windows(_parse(["focus-windows", "list"]))
    run_focus_windows(_parse(["focus-windows", "get", "--id", WINDOW_ID]))
    assert calls == [
        ("GET", "/api/v1/focus-windows"),
        ("GET", f"/api/v1/focus-windows/{WINDOW_ID}"),
    ]


def test_parser_registers_focus_windows() -> None:
    args = _parse(["focus-windows", "list"])
    assert args.command == "focus-windows"
    assert args.focus_windows_command == "list"
