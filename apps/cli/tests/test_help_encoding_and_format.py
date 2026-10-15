"""DEF-046 / DEF-047 — Windows help encoding + --format placement (no live API)."""

from __future__ import annotations

import argparse
import io
import json
from typing import Any

import pytest

from theplan.cli_argv import hoist_global_options
from theplan.errors import CliError
from theplan.main import _build_parser, main
from theplan.safe_help import install_safe_argparse_help, write_help_text


def _cp1252_buffer() -> tuple[io.TextIOWrapper, io.BytesIO]:
    raw = io.BytesIO()
    # errors=strict reproduces Windows console / redirected cp1252 crash.
    text = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="\n")
    return text, raw


def _subcommand_parser(root: argparse.ArgumentParser, *names: str) -> argparse.ArgumentParser:
    current = root
    for name in names:
        action = next(a for a in current._actions if isinstance(a, argparse._SubParsersAction))
        current = action.choices[name]
    return current


def test_write_help_text_cp1252_arrows_do_not_crash() -> None:
    stream, raw = _cp1252_buffer()
    write_help_text("settings get  →  scheduling_revision\nPrefer — not Must\n", stream)
    stream.flush()
    decoded = raw.getvalue().decode("cp1252")
    assert "->" in decoded
    assert "scheduling_revision" in decoded
    assert "Prefer" in decoded


def test_write_help_text_utf8_keeps_arrows() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict", newline="\n")
    write_help_text("settings get  →  scheduling_revision\n", stream)
    stream.flush()
    assert "→" in raw.getvalue().decode("utf-8")


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("scheduling",),
        ("tasks", "create"),
        ("focus-windows",),
        ("settings", "get"),
    ],
)
def test_help_under_cp1252_redirect(path: tuple[str, ...]) -> None:
    install_safe_argparse_help()
    parser = _build_parser()
    target = _subcommand_parser(parser, *path) if path else parser
    stream, raw = _cp1252_buffer()
    target.print_help(stream)
    stream.flush()
    text = raw.getvalue().decode("cp1252")
    assert len(text) > 20
    # Must not leave raw arrows that cp1252 cannot store.
    assert "→" not in text


def test_scheduling_help_epilog_readable_on_cp1252() -> None:
    install_safe_argparse_help()
    parser = _build_parser()
    scheduling = _subcommand_parser(parser, "scheduling")
    stream, raw = _cp1252_buffer()
    scheduling.print_help(stream)
    stream.flush()
    text = raw.getvalue().decode("cp1252")
    assert "scheduling_revision" in text
    assert "->" in text
    assert "Prefer" in text


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--format", "text", "version"], ["--format", "text", "version"]),
        (["version", "--format", "text"], ["--format", "text", "version"]),
        (["tasks", "list", "--format=json"], ["--format", "json", "tasks", "list"]),
        (
            ["--format", "json", "tasks", "list", "--format", "json"],
            ["--format", "json", "tasks", "list"],
        ),
        (
            ["settings", "get", "--interactive", "--format", "text"],
            ["--format", "text", "--interactive", "settings", "get"],
        ),
    ],
)
def test_hoist_format_before_or_after(argv: list[str], expected: list[str]) -> None:
    assert hoist_global_options(argv) == expected


def test_hoist_conflicting_format_raises() -> None:
    with pytest.raises(CliError) as excinfo:
        hoist_global_options(["tasks", "list", "--format", "json", "--format", "text"])
    assert "Conflicting --format" in excinfo.value.message
    assert "before or after" in excinfo.value.message


def test_main_accepts_format_after_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _capture(args: Any) -> None:
        from theplan.output import get_output_format

        seen["format"] = get_output_format()
        seen["command"] = args.command

    monkeypatch.setattr("theplan.main._dispatch", _capture)
    main(["version", "--format", "text"])
    assert seen["format"] == "text"
    assert seen["command"] == "version"


def test_main_format_after_nested(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _capture(args: Any) -> None:
        from theplan.output import get_output_format

        seen["format"] = get_output_format()
        seen["command"] = args.command

    monkeypatch.setattr("theplan.main._dispatch", _capture)
    main(["tasks", "list", "--format", "json"])
    assert seen["format"] == "json"
    assert seen["command"] == "tasks"


def test_main_conflicting_format_emits_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["version", "--format", "json", "--format", "text"])
    assert excinfo.value.code == 1
    err_body = json.loads(capsys.readouterr().out)
    assert err_body["ok"] is False
    assert err_body["code"] == "INVALID_USAGE"
    assert "Conflicting --format" in err_body["message"]
