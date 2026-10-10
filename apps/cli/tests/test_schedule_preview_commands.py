"""F6 schedule preview CLI — no live API."""

from __future__ import annotations

import json

import pytest

from theplan.commands.schedule import run_schedule
from theplan.errors import CliError
from theplan.main import _build_parser
from theplan.output import handle_cli_error, set_output_format

PREVIEW_ID = "00000000-0000-0000-0000-000000000040"


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def test_preview_commands_call_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, str]] = []

    def fake_api(method: str, path: str, **kwargs: object) -> dict:
        calls.append((method, path))
        assert kwargs.get("persist_session") is True
        if path.endswith("/apply"):
            return {"receipt_id": "r1", "preview_id": PREVIEW_ID, "blocks_created": 2}
        if method == "POST":
            return {"id": PREVIEW_ID, "status": "pending"}
        return {"id": PREVIEW_ID, "status": "ready", "diff_counts": {"blocks_added": 1}}

    monkeypatch.setattr("theplan.commands.schedule.api_json", fake_api)

    run_schedule(_parse(["schedule", "preview", "create"]))
    created = json.loads(capsys.readouterr().out)
    assert created["ok"] is True
    assert created["status"] == "pending"

    run_schedule(_parse(["schedule", "preview", "get", "--id", PREVIEW_ID]))
    got = json.loads(capsys.readouterr().out)
    assert got["status"] == "ready"

    run_schedule(_parse(["schedule", "preview", "apply", "--id", PREVIEW_ID]))
    applied = json.loads(capsys.readouterr().out)
    assert applied["blocks_created"] == 2

    assert calls == [
        ("POST", "/api/v1/schedule/previews"),
        ("GET", f"/api/v1/schedule/previews/{PREVIEW_ID}"),
        ("POST", f"/api/v1/schedule/previews/{PREVIEW_ID}/apply"),
    ]


def test_apply_stale_and_expired_errors_stay_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_stale(method: str, path: str, **kwargs: object) -> dict:
        raise CliError(
            code="PREVIEW_STALE",
            message="Scheduling inputs changed since this preview was calculated",
            exit_code=5,
            extra={"stale_categories": ["duration"]},
        )

    monkeypatch.setattr("theplan.commands.schedule.api_json", raise_stale)
    with pytest.raises(CliError) as stale:
        run_schedule(_parse(["schedule", "preview", "apply", "--id", PREVIEW_ID]))
    assert stale.value.code == "PREVIEW_STALE"
    assert stale.value.exit_code == 5
    assert stale.value.extra == {"stale_categories": ["duration"]}
    assert "duration" in stale.value.message
    assert "Create a fresh preview." in stale.value.message

    def raise_expired(method: str, path: str, **kwargs: object) -> dict:
        raise CliError(
            code="PREVIEW_EXPIRED",
            message="Preview expired before apply",
            exit_code=5,
        )

    monkeypatch.setattr("theplan.commands.schedule.api_json", raise_expired)
    with pytest.raises(CliError) as expired:
        run_schedule(_parse(["schedule", "preview", "apply", "--id", PREVIEW_ID]))
    assert expired.value.code == "PREVIEW_EXPIRED"
    assert expired.value.exit_code == 5
    assert expired.value.message == "Preview expired before apply. Create a fresh preview."


def test_apply_not_applicable_stale_status_names_the_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_status(method: str, path: str, **kwargs: object) -> dict:
        raise CliError(
            code="PREVIEW_NOT_APPLICABLE",
            message="Preview cannot be applied while status is expired",
            exit_code=5,
        )

    monkeypatch.setattr("theplan.commands.schedule.api_json", raise_status)
    with pytest.raises(CliError) as err:
        run_schedule(_parse(["schedule", "preview", "apply", "--id", PREVIEW_ID]))
    assert err.value.code == "PREVIEW_NOT_APPLICABLE"
    assert err.value.message.endswith("Create a fresh preview.")


@pytest.mark.parametrize("fmt", ["json", "text"])
def test_stale_error_surfaces_categories(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fmt: str,
) -> None:
    set_output_format(fmt)
    err = CliError(
        code="PREVIEW_STALE",
        message="Scheduling inputs changed since this preview was calculated (duration). Create a fresh preview.",
        exit_code=5,
        extra={"stale_categories": ["duration"]},
    )
    with pytest.raises(SystemExit) as exc:
        handle_cli_error(err)
    assert exc.value.code == 5
    captured = capsys.readouterr()
    if fmt == "json":
        body = json.loads(captured.out)
        assert body["ok"] is False
        assert body["code"] == "PREVIEW_STALE"
        assert body["stale_categories"] == ["duration"]
        assert "Create a fresh preview." in body["message"]
    else:
        assert "PREVIEW_STALE" in captured.err
        assert "duration" in captured.err
        assert "stale_categories:" in captured.err
