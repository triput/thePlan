# ==============================================================================
#  File: apps/cli/theplan/commands/availability.py
#  Description: CLI for availability policies list/get/patch/effective (S1 config-only).
#  Component: CLI
#  Version: 1.0
#  Created: 2026-10-12
#  Last Update: 2026-10-12
# ==============================================================================

from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json, availability_policy_path, unwrap_api_list
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format


def register_availability(sub: argparse._SubParsersAction) -> None:
    _availability_help = "Availability policies (S1: saved config; not placer-effective yet)"
    availability = sub.add_parser(
        "availability",
        help=_availability_help,
        description=_availability_help,
    )
    availability_sub = availability.add_subparsers(dest="availability_command", required=True)

    list_p = availability_sub.add_parser("list", help="List availability policies")
    list_p.add_argument(
        "--slug",
        default=None,
        help="Filter by stable slug (general, work, personal)",
    )

    get_p = availability_sub.add_parser("get", help="Get one policy by slug or id")
    get_p.add_argument("--ref", required=True, metavar="SLUG|UUID", help="Policy slug or id")

    patch_p = availability_sub.add_parser("patch", help="Patch policy name and/or windows")
    patch_p.add_argument("--ref", required=True, metavar="SLUG|UUID")
    patch_p.add_argument("--name", default=None)
    patch_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    patch_p.add_argument(
        "--stdin",
        action="store_true",
        help="AvailabilityPolicyUpdate JSON (merged with --name)",
    )

    _effective_help = "Effective windows for a calendar date (config-only in S1)"
    effective_p = availability_sub.add_parser(
        "effective",
        help=_effective_help,
        description=_effective_help,
    )
    effective_p.add_argument("--ref", required=True, metavar="SLUG|UUID")
    effective_p.add_argument(
        "--on",
        required=True,
        metavar="YYYY-MM-DD",
        help="Local calendar date",
    )


def _scheduling_banner(row: dict[str, Any]) -> None:
    effective = row.get("scheduling_effective", False)
    note = row.get("scheduling_effective_note") or ""
    print(f"scheduling_effective: {effective}")
    if note:
        print(f"scheduling_effective_note: {note}")


def _summarize_windows(windows: list[Any]) -> None:
    if not windows:
        print("windows: (none)")
        return
    print(f"windows ({len(windows)}):")
    for window in windows:
        if not isinstance(window, dict):
            continue
        overnight = " +1d" if window.get("ends_next_day") else ""
        print(
            f"  weekday={window.get('weekday')} "
            f"{window.get('start_time')}-{window.get('end_time')}{overnight} "
            f"duration={window.get('duration_minutes')}m sort={window.get('sort_order')}"
        )


def _summarize_policy(row: dict[str, Any]) -> None:
    print(f"id: {row.get('id')}")
    print(f"slug: {row.get('slug')}")
    print(f"name: {row.get('name')}")
    print(f"sort_order: {row.get('sort_order')}")
    _scheduling_banner(row)
    _summarize_windows(list(row.get("windows") or []))


def _summarize_policy_list(rows: list[Any]) -> None:
    if not rows:
        print("(no availability policies)")
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        print(
            f"{row.get('slug')}  id={row.get('id')}  name={row.get('name')}  "
            f"scheduling_effective={row.get('scheduling_effective', False)}"
        )
        note = row.get("scheduling_effective_note")
        if note:
            print(f"  note: {note}")


def _summarize_effective(row: dict[str, Any]) -> None:
    print(f"policy_id: {row.get('policy_id')}")
    print(f"slug: {row.get('slug')}")
    print(f"on_date: {row.get('on_date')}")
    _scheduling_banner(row)
    provenance = row.get("provenance") or []
    if provenance:
        print("provenance:")
        for line in provenance:
            print(f"  {line}")
    _summarize_windows(list(row.get("windows") or []))


def _patch_payload(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if args.file_path or args.stdin:
        body = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
    if args.name is not None:
        body["name"] = args.name
    if not body:
        raise CliError(
            code="INVALID_USAGE",
            message="Provide --name and/or patch JSON via --file or --stdin",
            exit_code=1,
        )
    return body


def run_availability(args: argparse.Namespace) -> None:
    cmd = args.availability_command
    if cmd == "list":
        params: dict[str, Any] = {}
        if args.slug is not None:
            params["slug"] = args.slug
        raw = api_json(
            "GET",
            availability_policy_path(),
            params=params or None,
            persist_session=True,
        )
        rows = unwrap_api_list(raw)
        if get_output_format() == "text":
            _summarize_policy_list(rows)
            return
        emit_ok({"policies": rows})
        return

    policy_ref = args.ref
    if cmd == "get":
        body = api_json(
            "GET",
            availability_policy_path(policy_ref),
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_policy(body)
            return
        emit_ok(body)
        return

    if cmd == "patch":
        payload = _patch_payload(args)
        body = api_json(
            "PATCH",
            availability_policy_path(policy_ref),
            json_body=payload,
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_policy(body)
            return
        emit_ok(body)
        return

    if cmd == "effective":
        body = api_json(
            "GET",
            availability_policy_path(policy_ref, suffix="effective"),
            params={"on": args.on},
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_effective(body)
            return
        emit_ok(body)
        return

    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown availability command: {cmd}",
        exit_code=1,
    )
