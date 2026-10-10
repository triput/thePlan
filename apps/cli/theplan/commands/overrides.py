# ==============================================================================
#  File: apps/cli/theplan/commands/overrides.py
#  Description: CLI commands for temporary Time Map override CRUD (F4).
#  Component: Time Map Overrides
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json, focus_window_overrides_path, unwrap_api_list
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format


def register_overrides(sub: argparse._SubParsersAction) -> None:
    overrides = sub.add_parser(
        "overrides",
        help="Temporary Time Map overrides on a focus window (F4)",
    )
    overrides_sub = overrides.add_subparsers(dest="overrides_command", required=True)

    list_p = overrides_sub.add_parser(
        "list",
        help="List overrides for one Time Map (includes expired rows)",
    )
    list_p.add_argument(
        "--map-id",
        required=True,
        dest="map_id",
        metavar="UUID",
        help="Focus window / Time Map id",
    )

    get_p = overrides_sub.add_parser("get", help="Get one override by id")
    get_p.add_argument("--map-id", required=True, dest="map_id", metavar="UUID")
    get_p.add_argument("--id", required=True, dest="override_id", metavar="UUID")

    create_p = overrides_sub.add_parser(
        "create",
        help="Create override (TimeMapOverrideCreate JSON body)",
    )
    create_p.add_argument("--map-id", required=True, dest="map_id", metavar="UUID")
    create_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    create_p.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON from stdin",
    )

    edit_p = overrides_sub.add_parser(
        "edit",
        help="Patch override dates, timezone, strict_mode, and/or bands (JSON body)",
    )
    edit_p.add_argument("--map-id", required=True, dest="map_id", metavar="UUID")
    edit_p.add_argument("--id", required=True, dest="override_id", metavar="UUID")
    edit_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    edit_p.add_argument("--stdin", action="store_true")

    delete_p = overrides_sub.add_parser("delete", help="Delete one override")
    delete_p.add_argument("--map-id", required=True, dest="map_id", metavar="UUID")
    delete_p.add_argument("--id", required=True, dest="override_id", metavar="UUID")


def _summarize_override_list(rows: list[Any]) -> None:
    if not rows:
        print("(no overrides)")
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        bands = row.get("bands") or []
        band_note = f"{len(bands)} band(s)" if bands else "no bands"
        strict = "strict" if row.get("strict_mode") else "non-strict"
        print(
            f"{row.get('id')}  {row.get('local_start_date')}..{row.get('local_end_date')}  "
            f"{row.get('timezone')}  {strict}  {band_note}"
        )


def _summarize_override_detail(row: dict[str, Any]) -> None:
    print(f"id: {row.get('id')}")
    print(f"map_id: {row.get('map_id')}")
    print(f"local_start_date: {row.get('local_start_date')}")
    print(f"local_end_date: {row.get('local_end_date')}")
    print(f"timezone: {row.get('timezone')}")
    print(f"strict_mode: {row.get('strict_mode')}")
    bands = row.get("bands") or []
    print(f"bands ({len(bands)}):")
    for band in bands:
        if not isinstance(band, dict):
            continue
        print(
            f"  {band.get('tier')} {band.get('start_time')}-{band.get('end_time')}  "
            f"days={band.get('days_of_week')} sort={band.get('sort_order')}"
        )


def run_overrides(args: argparse.Namespace) -> None:
    cmd = args.overrides_command
    map_id = args.map_id

    if cmd == "list":
        raw = api_json(
            "GET",
            focus_window_overrides_path(map_id),
            persist_session=True,
        )
        rows = unwrap_api_list(raw)
        if get_output_format() == "text":
            _summarize_override_list(rows)
            return
        emit_ok({"overrides": rows})
        return

    if cmd == "get":
        body = api_json(
            "GET",
            focus_window_overrides_path(map_id, args.override_id),
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_override_detail(body)
            return
        emit_ok(body)
        return

    if cmd == "create":
        payload = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        body = api_json(
            "POST",
            focus_window_overrides_path(map_id),
            json_body=payload,
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_override_detail(body)
            return
        emit_ok(body)
        return

    if cmd == "edit":
        payload = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        if not payload:
            raise CliError(
                code="INVALID_USAGE",
                message="Edit JSON must include at least one field",
                exit_code=1,
            )
        body = api_json(
            "PATCH",
            focus_window_overrides_path(map_id, args.override_id),
            json_body=payload,
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_override_detail(body)
            return
        emit_ok(body)
        return

    if cmd == "delete":
        api_json(
            "DELETE",
            focus_window_overrides_path(map_id, args.override_id),
            persist_session=True,
        )
        if get_output_format() == "text":
            print(f"deleted override {args.override_id} on map {map_id}")
            return
        emit_ok({"deleted": True, "id": str(args.override_id), "map_id": str(map_id)})
        return

    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown overrides command: {cmd}",
        exit_code=1,
    )
