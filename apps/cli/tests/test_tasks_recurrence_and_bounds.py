"""DEF-044 / DEF-045 — recurrence + scheduling bounds CLI wiring (no live API)."""

from __future__ import annotations

import argparse

import pytest

from theplan.commands.tasks import (
    _optional_task_fields,
    _recurrence_from_args,
    run_tasks,
)
from theplan.duration_coerce import duration_minutes_value
from theplan.errors import CliError
from theplan.main import _build_parser
from theplan.output import set_output_format

TASK_ID = "00000000-0000-0000-0000-000000000020"
WINDOW_ID = "00000000-0000-0000-0000-000000000070"


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def _create_ns(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "title": "Writing session",
        "project_id": None,
        "due_at": None,
        "priority": "p3",
        "estimated_duration_minutes": "60",
        "remaining_estimate_minutes": None,
        "expected_revision": None,
        "description": None,
        "rrule": None,
        "recurrence_text": None,
        "starts_on": None,
        "ends_on": None,
        "recurrence_timezone": None,
        "recurrence_fixed": False,
        "min_block_duration_minutes": None,
        "max_block_duration_minutes": None,
        "max_block_unbounded": None,
        "keep_in_one_block": None,
        "preferred_time_window_id": None,
        "schedule_style": None,
        "clear_min_block": False,
        "clear_max_block": False,
        "clear_preferred_time_window": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_three_sessions_week_via_recurrence_text() -> None:
    body = _optional_task_fields(
        _create_ns(recurrence_text="every monday, wednesday, friday"),
        for_create=True,
    )
    assert body["title"] == "Writing session"
    assert body["priority"] == "p3"
    assert body["estimated_duration_minutes"] == 60
    assert body["recurrence"] == {"text": "every monday, wednesday, friday"}


def test_fixed_text_flag_rewrites_ordinary_every() -> None:
    """DEF-044 residual — --recurrence-fixed + ordinary text → every! (API honors)."""
    body = _optional_task_fields(
        _create_ns(
            recurrence_text="every monday, wednesday, friday",
            recurrence_fixed=True,
        ),
        for_create=True,
    )
    assert body["recurrence"] == {
        "text": "every! monday, wednesday, friday",
    }
    assert "is_fixed" not in body["recurrence"]


def test_fixed_text_flag_leaves_every_bang_unchanged() -> None:
    body = _recurrence_from_args(
        _create_ns(
            recurrence_text="every! monday, wednesday, friday",
            recurrence_fixed=True,
        ),
        required=False,
    )
    assert body == {"text": "every! monday, wednesday, friday"}


def test_fixed_rrule_still_sends_is_fixed() -> None:
    body = _recurrence_from_args(
        _create_ns(rrule="FREQ=WEEKLY;BYDAY=MO,WE,FR", recurrence_fixed=True),
        required=False,
    )
    assert body == {
        "rrule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
        "is_fixed": True,
    }


def test_fixed_without_every_token_rejected() -> None:
    with pytest.raises(CliError) as exc:
        _recurrence_from_args(
            _create_ns(recurrence_text="daily on weekdays", recurrence_fixed=True),
            required=False,
        )
    assert exc.value.code == "INVALID_USAGE"
    assert "--recurrence-fixed" in exc.value.message


def test_create_rrule_with_frame_and_timezone() -> None:
    body = _optional_task_fields(
        _create_ns(
            rrule="FREQ=WEEKLY;BYDAY=MO,WE,FR",
            starts_on="2026-10-13",
            ends_on="2026-12-31",
            recurrence_timezone="America/Los_Angeles",
            recurrence_fixed=True,
            keep_in_one_block=True,
            min_block_duration_minutes="60",
            max_block_duration_minutes="60",
            preferred_time_window_id=WINDOW_ID,
        ),
        for_create=True,
    )
    assert body["recurrence"] == {
        "rrule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
        "starts_on": "2026-10-13",
        "ends_on": "2026-12-31",
        "timezone": "America/Los_Angeles",
        "is_fixed": True,
    }
    assert body["keep_in_one_block"] is True
    assert body["min_block_duration_minutes"] == 60
    assert body["max_block_duration_minutes"] == 60
    assert body["preferred_time_window_id"] == WINDOW_ID


def test_rrule_and_text_mutually_exclusive() -> None:
    with pytest.raises(CliError) as exc:
        _recurrence_from_args(
            _create_ns(rrule="FREQ=DAILY", recurrence_text="every day"),
            required=False,
        )
    assert exc.value.code == "INVALID_USAGE"


def test_frame_without_rule_rejected() -> None:
    with pytest.raises(CliError) as exc:
        _recurrence_from_args(_create_ns(starts_on="2026-10-13"), required=True)
    assert "rrule or --recurrence-text" in exc.value.message


def test_patch_clear_bounds_sends_null() -> None:
    body = _optional_task_fields(
        _create_ns(
            title=None,
            priority=None,
            estimated_duration_minutes=None,
            clear_min_block=True,
            clear_max_block=True,
            max_block_unbounded=True,
            clear_preferred_time_window=True,
        ),
        for_create=False,
    )
    assert body == {
        "min_block_duration_minutes": None,
        "max_block_duration_minutes": None,
        "max_block_unbounded": True,
        "preferred_time_window_id": None,
    }


def test_recurrence_put_and_clear_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def fake_api(method: str, path: str, json_body=None, **_kwargs):
        calls.append((method, path, json_body))
        if method == "DELETE":
            return None
        return {
            "rrule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
            "is_fixed": False,
            "timezone": "UTC",
            "starts_on": None,
            "ends_on": None,
            "display": "Every Mon, Wed, Fri",
        }

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_api)
    set_output_format("json")
    run_tasks(
        _parse(
            [
                "tasks",
                "recurrence",
                "put",
                "--id",
                TASK_ID,
                "--recurrence-text",
                "every monday, wednesday, friday",
            ]
        )
    )
    run_tasks(_parse(["tasks", "recurrence", "clear", "--id", TASK_ID]))
    run_tasks(_parse(["tasks", "recurrence", "get", "--id", TASK_ID]))

    assert calls[0][0] == "PUT"
    assert calls[0][1] == f"/api/v1/tasks/{TASK_ID}/recurrence"
    assert calls[0][2] == {"text": "every monday, wednesday, friday"}
    assert calls[1] == ("DELETE", f"/api/v1/tasks/{TASK_ID}/recurrence", None)
    assert calls[2][0] == "GET"


def test_recurrence_put_fixed_ordinary_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEF-044 residual — put path honors --recurrence-fixed with ordinary text."""
    captured: dict = {}

    def fake_api(method: str, path: str, json_body=None, **_kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json_body
        return {
            "rrule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
            "is_fixed": True,
            "timezone": "UTC",
            "starts_on": None,
            "ends_on": None,
            "display": "Every! Mon, Wed, Fri",
        }

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_api)
    set_output_format("json")
    run_tasks(
        _parse(
            [
                "tasks",
                "recurrence",
                "put",
                "--id",
                TASK_ID,
                "--recurrence-text",
                "every monday, wednesday, friday",
                "--recurrence-fixed",
            ]
        )
    )
    assert captured["method"] == "PUT"
    assert captured["body"] == {"text": "every! monday, wednesday, friday"}


def test_friendly_block_bounds_create() -> None:
    """DEF-045 residual — --min-block 1h --max-block 2h → int minutes."""
    body = _optional_task_fields(
        _create_ns(
            min_block_duration_minutes="1h",
            max_block_duration_minutes="2h",
        ),
        for_create=True,
    )
    assert body["min_block_duration_minutes"] == 60
    assert body["max_block_duration_minutes"] == 120
    assert isinstance(body["min_block_duration_minutes"], int)
    assert isinstance(body["max_block_duration_minutes"], int)


def test_friendly_block_bounds_patch() -> None:
    body = _optional_task_fields(
        _create_ns(
            title=None,
            priority=None,
            estimated_duration_minutes=None,
            min_block_duration_minutes="1h 30m",
            max_block_duration_minutes="90",
        ),
        for_create=False,
    )
    assert body == {
        "min_block_duration_minutes": 90,
        "max_block_duration_minutes": 90,
    }


def test_invalid_block_bounds_reject_before_write() -> None:
    with pytest.raises(CliError) as exc:
        _optional_task_fields(
            _create_ns(min_block_duration_minutes="2d"),
            for_create=True,
        )
    assert exc.value.code == "INVALID_USAGE"
    assert "Ambiguous" in exc.value.message or "hours/minutes" in exc.value.message


def test_workday_block_bounds_rejected_without_nominal() -> None:
    """Block bounds are wall-clock; workday effort units need hours/minutes."""
    with pytest.raises(CliError) as exc:
        duration_minutes_value(
            "1 workday",
            field_label="--min-block",
            allow_workdays=False,
        )
    assert "Workday" in exc.value.message


def test_duration_minutes_nominal_workday_when_allowed() -> None:
    assert (
        duration_minutes_value(
            "0.5 workdays",
            field_label="estimate",
            allow_workdays=True,
            nominal_workday_minutes=480,
        )
        == 240
    )


def test_complete_sends_empty_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """DEF-042 — complete must send JSON body (at least {})."""
    captured: dict = {}

    def fake_api(method: str, path: str, json_body=None, **_kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json_body
        return {
            "id": TASK_ID,
            "is_completed": False,
            "recurrence_advanced": True,
            "board_column": "ready",
        }

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_api)
    set_output_format("json")
    run_tasks(_parse(["tasks", "complete", "--id", TASK_ID]))
    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/v1/tasks/{TASK_ID}/complete"
    assert captured["body"] == {}


def test_complete_bulk_children_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_api(method: str, path: str, json_body=None, **_kwargs):
        captured["body"] = json_body
        return {"id": TASK_ID, "is_completed": True, "board_column": "done"}

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_api)
    set_output_format("json")
    run_tasks(
        _parse(["tasks", "complete", "--id", TASK_ID, "--bulk-children"])
    )
    assert captured["body"] == {"bulk_children": True}


def test_parser_accepts_writing_create_flags() -> None:
    args = _parse(
        [
            "tasks",
            "create",
            "--title",
            "Writing",
            "--priority",
            "p3",
            "--estimated-duration-minutes",
            "60",
            "--recurrence-text",
            "every monday, wednesday, friday",
            "--timezone",
            "America/Los_Angeles",
            "--keep-in-one-block",
            "--min-block",
            "60",
            "--max-block",
            "60",
            "--preferred-time-window-id",
            WINDOW_ID,
        ]
    )
    assert args.recurrence_text == "every monday, wednesday, friday"
    assert args.recurrence_timezone == "America/Los_Angeles"
    assert args.keep_in_one_block is True
    assert args.min_block_duration_minutes == "60"
