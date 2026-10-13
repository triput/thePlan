"""S1 CLI parity — settings, availability, progress, remaining patch, effective."""

from __future__ import annotations

import io
import json

import httpx
import pytest

from theplan.api_client import api_error_from_response
from theplan.commands.availability import run_availability
from theplan.commands.settings import run_settings
from theplan.commands.schedule import run_schedule
from theplan.commands.tasks import run_tasks, _optional_task_fields
from theplan.errors import CliError
from theplan.main import _build_parser
from theplan.output import set_output_format

TASK_ID = "00000000-0000-0000-0000-000000000020"
POLICY_REF = "work"
IDEM = "00000000-0000-0000-0000-000000000099"


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def _sample_settings() -> dict:
    return {
        "timezone": "America/Los_Angeles",
        "locale": "en-US",
        "workday_minutes": 480,
        "nominal_workday_minutes": 450,
        "workday_start_local": "09:00",
        "workweek_days": 5,
        "inter_block_buffer_minutes": 15,
        "ups_weights": {"urgency": 1.0},
        "upcoming_horizon_days": 14,
        "default_estimated_duration_minutes": 60,
        "default_min_block_duration_minutes": 30,
        "default_max_block_duration_minutes": 120,
        "default_max_block_unbounded": False,
        "default_schedule_style": "standalone",
        "auto_defer_enabled": True,
        "max_auto_schedule_minutes_per_project_per_day": 240,
        "scheduling_revision": 3,
    }


def _sample_policy(*, slug: str = POLICY_REF) -> dict:
    return {
        "id": "00000000-0000-0000-0000-000000000070",
        "slug": slug,
        "name": "Work",
        "sort_order": 1,
        "scheduling_effective": False,
        "scheduling_effective_note": "Saved for upcoming scheduling; current runs still use working hours / Time Maps.",
        "windows": [
            {
                "id": "00000000-0000-0000-0000-000000000071",
                "weekday": 1,
                "start_time": "09:00",
                "end_time": "17:00",
                "ends_next_day": False,
                "duration_minutes": 480,
                "sort_order": 0,
            }
        ],
    }


def test_settings_get_and_patch(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    sample = _sample_settings()
    calls: list[tuple[str, str, dict | None]] = []

    def fake_api(method, path, *, json_body=None, **kwargs):
        calls.append((method, path, json_body))
        if method == "GET" and path == "/api/v1/settings":
            return sample
        if method == "PATCH" and path == "/api/v1/settings":
            assert json_body == {"nominal_workday_minutes": 460, "default_max_block_unbounded": True}
            return {**sample, **json_body}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr("theplan.commands.settings.api_json", fake_api)

    run_settings(_parse(["settings", "get"]))
    got = json.loads(capsys.readouterr().out)
    assert got["ok"] is True
    assert got["nominal_workday_minutes"] == 450
    assert got["scheduling_revision"] == 3

    set_output_format("text")
    try:
        run_settings(_parse(["settings", "get"]))
        text_out = capsys.readouterr().out
        assert "scheduling_revision: 3" in text_out.splitlines()
    finally:
        set_output_format("json")

    run_settings(
        _parse(
            [
                "settings",
                "patch",
                "--nominal-workday-minutes",
                "460",
                "--default-max-block-unbounded",
            ]
        )
    )
    patched = json.loads(capsys.readouterr().out)
    assert patched["default_max_block_unbounded"] is True
    assert patched["scheduling_revision"] == 3
    assert calls[-1][0] == "PATCH"
    assert calls[-1][2]["nominal_workday_minutes"] == 460


def test_availability_commands(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    policy = _sample_policy()
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_api(method, path, *, json_body=None, params=None, **kwargs):
        calls.append((method, path, json_body, params))
        base = "/api/v1/availability-policies"
        if method == "GET" and path == base:
            return {"data": [policy]}
        if method == "GET" and path == f"{base}/{POLICY_REF}":
            return policy
        if method == "PATCH" and path == f"{base}/{POLICY_REF}":
            return {**policy, **json_body}
        if method == "GET" and path == f"{base}/{POLICY_REF}/effective":
            assert params == {"on": "2026-10-12"}
            return {
                "policy_id": policy["id"],
                "slug": POLICY_REF,
                "on_date": "2026-10-12",
                "scheduling_effective": False,
                "scheduling_effective_note": policy["scheduling_effective_note"],
                "windows": policy["windows"],
                "provenance": ["policy windows"],
            }
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr("theplan.commands.availability.api_json", fake_api)

    run_availability(_parse(["availability", "list"]))
    listed = json.loads(capsys.readouterr().out)
    assert listed["policies"][0]["scheduling_effective"] is False

    run_availability(_parse(["availability", "get", "--ref", POLICY_REF]))
    got = json.loads(capsys.readouterr().out)
    assert got["slug"] == POLICY_REF

    run_availability(_parse(["availability", "patch", "--ref", POLICY_REF, "--name", "Work hours"]))
    patched = json.loads(capsys.readouterr().out)
    assert patched["name"] == "Work hours"

    run_availability(_parse(["availability", "effective", "--ref", POLICY_REF, "--on", "2026-10-12"]))
    effective = json.loads(capsys.readouterr().out)
    assert effective["scheduling_effective"] is False
    assert "Time Maps" in effective["scheduling_effective_note"]


def test_availability_patch_forwards_empty_working_windows(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    policy = _sample_policy()
    seen: dict[str, object] = {}

    def fake_api(method, path, *, json_body=None, **kwargs):
        seen["method"] = method
        seen["path"] = path
        seen["body"] = json_body
        return {**policy, "windows": []}

    monkeypatch.setattr("theplan.commands.availability.api_json", fake_api)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"windows": []}'))
    set_output_format("text")
    try:
        run_availability(_parse(["availability", "patch", "--ref", POLICY_REF, "--stdin"]))
        out = capsys.readouterr().out
    finally:
        set_output_format("json")
    assert seen["method"] == "PATCH"
    assert seen["path"] == f"/api/v1/availability-policies/{POLICY_REF}"
    assert seen["body"] == {"windows": []}
    assert "windows: (none)" in out


def test_settings_patch_forwards_zero_workweek_days(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = _sample_settings()
    seen: dict[str, object] = {}

    def fake_api(method, path, *, json_body=None, **kwargs):
        seen["body"] = json_body
        return {**sample, "workweek_days": 0}

    monkeypatch.setattr("theplan.commands.settings.api_json", fake_api)
    run_settings(_parse(["settings", "patch", "--workweek-days", "0"]))
    patched = json.loads(capsys.readouterr().out)
    assert seen["body"] == {"workweek_days": 0}
    assert patched["workweek_days"] == 0


def test_availability_text_surfaces_scheduling_note(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    policy = _sample_policy()
    monkeypatch.setattr(
        "theplan.commands.availability.api_json",
        lambda *a, **k: policy,
    )
    set_output_format("text")
    run_availability(_parse(["availability", "get", "--ref", POLICY_REF]))
    out = capsys.readouterr().out
    assert "scheduling_effective: False" in out
    assert "scheduling_effective_note:" in out


def test_tasks_progress_and_scheduling_effective(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_api(method, path, *, json_body=None, **kwargs):
        calls.append((method, path))
        if method == "POST" and path == f"/api/v1/tasks/{TASK_ID}/progress-entries":
            assert json_body == {
                "idempotency_key": IDEM,
                "minutes_worked": 25,
                "remaining_minutes": 35,
                "expected_revision": 7,
                "note": "deep work",
            }
            return {
                "entry": {"id": IDEM, "task_id": TASK_ID},
                "original_estimate_minutes": 60,
                "time_worked_minutes": 25,
                "remaining_estimate_minutes": 35,
                "scheduling_revision": 8,
                "replayed": False,
            }
        if method == "GET" and path == f"/api/v1/tasks/{TASK_ID}/scheduling/effective":
            return {
                "task_id": TASK_ID,
                "placement_effort_minutes": 35,
                "scheduling_effective_note": "Saved for upcoming scheduling; current runs still use working hours / Time Maps.",
                "general_policy_scheduling_effective": False,
                "working_hours_placer_active": True,
                "sources": [],
            }
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_api)

    run_tasks(
        _parse(
            [
                "tasks",
                "progress",
                "add",
                "--id",
                TASK_ID,
                "--idempotency-key",
                IDEM,
                "--minutes-worked",
                "25",
                "--remaining-minutes",
                "35",
                "--expected-revision",
                "7",
                "--note",
                "deep work",
            ]
        )
    )
    progress = json.loads(capsys.readouterr().out)
    assert progress["scheduling_revision"] == 8

    run_tasks(_parse(["tasks", "scheduling-effective", "--id", TASK_ID]))
    effective = json.loads(capsys.readouterr().out)
    assert effective["general_policy_scheduling_effective"] is False

    monkeypatch.setattr("theplan.commands.schedule.api_json", fake_api)
    run_schedule(_parse(["schedule", "effective", "--task-id", TASK_ID]))
    sched = json.loads(capsys.readouterr().out)
    assert sched["task_id"] == TASK_ID

    assert ("POST", f"/api/v1/tasks/{TASK_ID}/progress-entries") in calls
    assert ("GET", f"/api/v1/tasks/{TASK_ID}/scheduling/effective") in calls


def test_tasks_list_includes_progress_fields(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    body = {
        "total": 1,
        "limit": 50,
        "offset": 0,
        "items": [
            {
                "id": TASK_ID,
                "title": "Lab",
                "original_estimate_minutes": 60,
                "time_worked_minutes": 10,
                "remaining_estimate_minutes": 50,
            }
        ],
    }
    monkeypatch.setattr("theplan.commands.tasks.api_json", lambda *a, **k: body)
    run_tasks(_parse(["tasks", "list"]))
    listed = json.loads(capsys.readouterr().out)
    assert listed["items"][0]["remaining_estimate_minutes"] == 50


def test_patch_remaining_requires_expected_revision() -> None:
    import argparse

    ns = argparse.Namespace(
        title=None,
        project_id=None,
        due_at=None,
        priority=None,
        estimated_duration_minutes=None,
        remaining_estimate_minutes=40,
        expected_revision=None,
        description=None,
    )
    with pytest.raises(CliError) as exc:
        _optional_task_fields(ns, for_create=False)
    assert exc.value.code == "INVALID_USAGE"


def test_patch_remaining_payload(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    captured: dict | None = None

    def fake_api(method, path, *, json_body=None, **kwargs):
        nonlocal captured
        captured = json_body
        return {"id": TASK_ID, "remaining_estimate_minutes": 40}

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_api)
    run_tasks(
        _parse(
            [
                "tasks",
                "patch",
                "--id",
                TASK_ID,
                "--remaining-estimate-minutes",
                "40",
                "--expected-revision",
                "12",
            ]
        )
    )
    assert captured == {"remaining_estimate_minutes": 40, "expected_revision": 12}
    json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    ("status", "code", "exit_code", "extra"),
    [
        (422, "ORIGINAL_ESTIMATE_IMMUTABLE", 1, None),
        (422, "CHUNKING_CUTOVER_PENDING", 1, None),
        (
            409,
            "SCHEDULING_REVISION_CONFLICT",
            5,
            {"expected_revision": 7, "current_revision": 8},
        ),
    ],
)
def test_s1_api_error_bodies_keep_code_and_exit(
    status: int,
    code: str,
    exit_code: int,
    extra: dict | None,
) -> None:
    """API JSON shape is {detail, code, ...}; 422 → exit 1, 409 → exit 5."""
    body: dict = {"detail": f"{code} from API", "code": code}
    if extra:
        body.update(extra)
    err = api_error_from_response(httpx.Response(status, json=body))
    assert err.code == code
    assert err.message == f"{code} from API"
    assert err.exit_code == exit_code
    if extra:
        assert err.extra == extra


def test_tasks_commands_reraise_mapped_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    mapped = api_error_from_response(
        httpx.Response(
            422,
            json={
                "detail": "original estimate is immutable",
                "code": "ORIGINAL_ESTIMATE_IMMUTABLE",
            },
        )
    )

    def fake_api(*args, **kwargs):
        raise mapped

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_api)
    with pytest.raises(CliError) as exc:
        run_tasks(
            _parse(
                [
                    "tasks",
                    "patch",
                    "--id",
                    TASK_ID,
                    "--estimated-duration-minutes",
                    "90",
                ]
            )
        )
    assert exc.value is mapped
    assert exc.value.code == "ORIGINAL_ESTIMATE_IMMUTABLE"
    assert exc.value.exit_code == 1

    conflict = api_error_from_response(
        httpx.Response(
            409,
            json={
                "detail": "Scheduling inputs changed since this action was prepared",
                "code": "SCHEDULING_REVISION_CONFLICT",
                "expected_revision": 7,
                "current_revision": 9,
            },
        )
    )

    def fake_progress(*args, **kwargs):
        raise conflict

    monkeypatch.setattr("theplan.commands.tasks.api_json", fake_progress)
    with pytest.raises(CliError) as progress_exc:
        run_tasks(
            _parse(
                [
                    "tasks",
                    "progress",
                    "add",
                    "--id",
                    TASK_ID,
                    "--idempotency-key",
                    IDEM,
                    "--minutes-worked",
                    "25",
                    "--remaining-minutes",
                    "35",
                    "--expected-revision",
                    "7",
                ]
            )
        )
    assert progress_exc.value.code == "SCHEDULING_REVISION_CONFLICT"
    assert progress_exc.value.exit_code == 5
    assert progress_exc.value.extra == {"expected_revision": 7, "current_revision": 9}


def test_settings_patch_omits_unset_bools(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict | None = None

    def fake_api(method, path, *, json_body=None, **kwargs):
        nonlocal captured
        captured = json_body
        return _sample_settings()

    monkeypatch.setattr("theplan.commands.settings.api_json", fake_api)
    run_settings(_parse(["settings", "patch", "--nominal-workday-minutes", "460"]))
    assert captured == {"nominal_workday_minutes": 460}
    capsys.readouterr()


def test_availability_list_passes_slug(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict | None = None

    def fake_api(method, path, *, params=None, **kwargs):
        nonlocal seen
        seen = params
        return {"data": [_sample_policy()]}

    monkeypatch.setattr("theplan.commands.availability.api_json", fake_api)
    run_availability(_parse(["availability", "list", "--slug", "work"]))
    assert seen == {"slug": "work"}
    listed = json.loads(capsys.readouterr().out)
    assert listed["policies"][0]["scheduling_effective"] is False


def test_help_says_policies_are_not_scheduling_effective(
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = {
        "tasks scheduling-effective": "not scheduling-effective",
        "schedule effective": "not scheduling-effective",
        "availability": "not placer-effective",
        "availability effective": "config-only in S1",
    }
    for argv, needle in (
        (["tasks", "scheduling-effective", "--help"], expected["tasks scheduling-effective"]),
        (["schedule", "effective", "--help"], expected["schedule effective"]),
        (["availability", "--help"], expected["availability"]),
        (["availability", "effective", "--help"], expected["availability effective"]),
    ):
        with pytest.raises(SystemExit) as exc:
            _parse(argv)
        assert exc.value.code in (0, None)
        out = " ".join(capsys.readouterr().out.split())
        assert needle in out


def test_scheduling_effective_text_keeps_policies_inactive(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    body = {
        "task_id": TASK_ID,
        "placement_effort_minutes": 35,
        "scheduling_effective_note": (
            "Saved for upcoming scheduling; current runs still use working hours / Time Maps."
        ),
        "general_policy_scheduling_effective": False,
        "working_hours_placer_active": True,
        "sources": [
            {
                "kind": "legacy_workweek",
                "label": "Working hours (legacy workweek settings)",
                "placer_active": True,
            },
            {
                "kind": "availability_general",
                "label": "General availability policy",
                "placer_active": False,
            },
            {
                "kind": "availability_work",
                "label": "Working availability policy",
                "placer_active": False,
            },
        ],
    }
    monkeypatch.setattr("theplan.commands.tasks.api_json", lambda *a, **k: body)
    monkeypatch.setattr("theplan.commands.schedule.api_json", lambda *a, **k: body)
    set_output_format("text")
    run_tasks(_parse(["tasks", "scheduling-effective", "--id", TASK_ID]))
    tasks_out = capsys.readouterr().out
    run_schedule(_parse(["schedule", "effective", "--task-id", TASK_ID]))
    schedule_out = capsys.readouterr().out
    for out in (tasks_out, schedule_out):
        assert "general_policy_scheduling_effective: False" in out
        assert "availability_general (inactive):" in out
        assert "availability_work (inactive):" in out
        assert "legacy_workweek (active):" in out
        assert "Time Maps" in out
        assert "availability_general (active)" not in out
        assert "availability_work (active)" not in out
