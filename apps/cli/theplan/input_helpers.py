from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from theplan.errors import CliError


def _interactive_allowed() -> bool:
    return os.environ.get("THEPLAN_CLI_INTERACTIVE") == "1"


def _strip_one_trailing_newline(raw: str) -> str:
    if raw.endswith("\n"):
        raw = raw[:-1]
    if raw.endswith("\r"):
        raw = raw[:-1]
    return raw


def read_secret_stdin(*, label: str = "password") -> str:
    """Read a secret from stdin.

    Piped/redirected stdin: read until EOF (agents/scripts).
    TTY: only with ``--interactive`` (getpass); otherwise fail fast instead of
    hanging forever waiting for EOF after a typed line + Enter.
    """
    if sys.stdin.isatty():
        if not _interactive_allowed():
            raise CliError(
                code="INVALID_USAGE",
                message=(
                    f"--password-stdin needs a pipe/redirect, or pass --interactive "
                    f"for a hidden prompt. PowerShell example: "
                    f'"your passphrase here" | theplan auth … --password-stdin'
                ),
                exit_code=1,
            )
        import getpass

        raw = getpass.getpass(f"{label}: ")
    else:
        raw = _strip_one_trailing_newline(sys.stdin.read())
    if not raw:
        raise CliError(
            code="INVALID_PASSWORD",
            message=f"Empty {label} on stdin",
            exit_code=1,
        )
    return raw


def resolve_password(*, password: str | None, password_stdin: bool) -> str:
    if password is not None and password_stdin:
        raise CliError(
            code="INVALID_USAGE",
            message="Specify at most one of --password and --password-stdin",
            exit_code=1,
        )
    if password_stdin:
        return read_secret_stdin()
    if password is None:
        raise CliError(
            code="INVALID_USAGE",
            message="Specify --password or --password-stdin",
            exit_code=1,
        )
    return password


def resolve_text(*, text: str | None, text_stdin: bool, flag: str = "--text") -> str:
    if text is not None and text_stdin:
        raise CliError(
            code="INVALID_USAGE",
            message=f"Specify at most one of {flag} and {flag}-stdin",
            exit_code=1,
        )
    if text_stdin:
        raw = sys.stdin.read()
        if raw.endswith("\n"):
            raw = raw[:-1]
        if not raw.strip():
            raise CliError(
                code="INVALID_USAGE",
                message=f"Empty input on stdin; provide {flag}-stdin content",
                exit_code=1,
            )
        return raw
    if text is None or not str(text).strip():
        raise CliError(
            code="INVALID_USAGE",
            message=f"{flag} is required (or use {flag}-stdin)",
            exit_code=1,
        )
    return text.strip()


def read_json_body(*, file_path: str | None, use_stdin: bool) -> dict[str, Any]:
    if file_path and use_stdin:
        raise CliError(
            code="INVALID_USAGE",
            message="Specify at most one of --file and --stdin",
            exit_code=1,
        )
    if use_stdin:
        raw = sys.stdin.read()
    elif file_path:
        try:
            raw = Path(file_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise CliError(
                code="INVALID_USAGE",
                message=f"Could not read {file_path}: {exc}",
                exit_code=1,
            ) from exc
    else:
        raise CliError(
            code="INVALID_USAGE",
            message="Specify --file or --stdin",
            exit_code=1,
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_USAGE",
            message=f"Invalid JSON: {exc}",
            exit_code=1,
        ) from exc
    if not isinstance(parsed, dict):
        raise CliError(
            code="INVALID_USAGE",
            message="JSON body must be an object",
            exit_code=1,
        )
    return parsed
