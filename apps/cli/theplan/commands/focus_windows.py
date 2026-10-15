# ==============================================================================
#  File: apps/cli/theplan/commands/focus_windows.py
#  Description: Read-only focus window / Time Map discovery (DEF-045).
#  Component: CLI
#  Version: 1.0
#  Created: 2026-10-14
#  Last Update: 2026-10-14
# ==============================================================================

from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json, unwrap_api_list
from theplan.errors import CliError
from theplan.output import emit_ok, get_output_format

_FOCUS_WINDOWS_PATH = "/api/v1/focus-windows"

_HELP = (
    "List and inspect focus windows (Time Maps). Read-only discovery for "
    "preferred_time_window_id and afternoon/evening names. "
    "Does not create or edit maps (DEF-040). "
    "For May/Must/Prefer assignment writers use: theplan scheduling --help. "
    "Revision token: theplan settings get → scheduling_revision."
)


def register_focus_windows(sub: argparse._SubParsersAction) -> None:
    focus = sub.add_parser(
        "focus-windows",
        help="Discover focus windows / Time Maps (read-only)",
        description=_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    focus_sub = focus.add_subparsers(dest="focus_windows_command", required=True)

    focus_sub.add_parser("list", help="List owned focus windows")

    get_p = focus_sub.add_parser("get", help="Get one focus window by id")
    get_p.add_argument("--id", required=True, dest="window_id", metavar="UUID")


def _summarize_window(row: dict[str, Any]) -> None:
    print(f"id: {row.get('id')}")
    print(f"name: {row.get('name')}")
    print(f"strict_mode: {row.get('strict_mode')}")
    bands = row.get("bands") or []
    print(f"bands ({len(bands)}):")
    for band in bands:
        if not isinstance(band, dict):
            continue
        print(
            f"  tier={band.get('tier')} "
            f"{band.get('start_time')}-{band.get('end_time')} "
            f"days_of_week={band.get('days_of_week')}"
        )


def _summarize_list(rows: list[Any]) -> None:
    if not rows:
        print("(no focus windows)")
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        bands = row.get("bands") or []
        print(
            f"{row.get('name')}  id={row.get('id')}  "
            f"strict={row.get('strict_mode')}  bands={len(bands)}"
        )


def run_focus_windows(args: argparse.Namespace) -> None:
    cmd = args.focus_windows_command
    if cmd == "list":
        raw = api_json("GET", _FOCUS_WINDOWS_PATH, persist_session=True)
        rows = unwrap_api_list(raw)
        if get_output_format() == "text":
            _summarize_list(rows)
            return
        emit_ok({"focus_windows": rows})
        return
    if cmd == "get":
        body = api_json(
            "GET",
            f"{_FOCUS_WINDOWS_PATH}/{args.window_id}",
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_window(body)
            return
        emit_ok(body)
        return
    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown focus-windows command: {cmd}",
        exit_code=1,
    )
