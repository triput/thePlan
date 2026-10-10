from __future__ import annotations

import json
import sys
from typing import Any

from theplan.errors import CliError

_format: str = "json"


def set_output_format(fmt: str) -> None:
    global _format
    _format = fmt


def get_output_format() -> str:
    return _format


def emit_ok(payload: dict[str, Any]) -> None:
    body = {"ok": True, **payload}
    _write(body)


def emit_error(
    *,
    code: str,
    message: str,
    exit_code: int = 1,
    extra: dict[str, Any] | None = None,
) -> None:
    body: dict[str, Any] = {"ok": False, "code": code, "message": message}
    if extra:
        body.update(extra)
    _write(body)
    raise SystemExit(exit_code)


def handle_cli_error(exc: CliError) -> None:
    emit_error(
        code=exc.code,
        message=exc.message,
        exit_code=exc.exit_code,
        extra=exc.extra,
    )


def _write(body: dict[str, Any]) -> None:
    if _format == "text":
        if body.get("ok"):
            for key, value in body.items():
                if key == "ok":
                    continue
                print(f"{key}: {value}")
        else:
            print(f"error [{body.get('code')}]: {body.get('message')}", file=sys.stderr)
            for key, value in body.items():
                if key in {"ok", "code", "message"}:
                    continue
                print(f"{key}: {value}", file=sys.stderr)
        return
    json.dump(body, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.stdout.flush()
