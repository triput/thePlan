# ==============================================================================
#  File: apps/cli/theplan/commands/settings.py
#  Description: CLI for user settings GET/PATCH (S1).
#  Component: CLI
#  Version: 1.1
#  Created: 2026-10-12
#  Last Update: 2026-10-12 (S1-D4: expose scheduling_revision on settings get)
# ==============================================================================

from __future__ import annotations

import argparse
import json
from typing import Any

from theplan.api_client import api_json
from theplan.duration_coerce import duration_json_value
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format

_SETTINGS_PATH = "/api/v1/settings"

# Mirrors app.services.scheduling_revision.SETTINGS_SCHEDULING_FIELDS (help only).
_SCHEDULING_REVISION_FIELDS = (
    "timezone",
    "workday_minutes",
    "workday_start_local",
    "workweek_days",
    "inter_block_buffer_minutes",
    "ups_weights",
    "upcoming_horizon_days",
    "default_estimated_duration_minutes",
    "default_min_block_duration_minutes",
    "default_schedule_style",
    "auto_defer_enabled",
    "max_auto_schedule_minutes_per_project_per_day",
)

_GET_EPILOG = (
    "Includes owner-scoped scheduling_revision (integer token for "
    "tasks progress add --expected-revision and remaining-only "
    "tasks patch --remaining-estimate-minutes --expected-revision). "
    "Do not substitute board_revision from tasks get."
)

_PATCH_EPILOG = (
    "Patch fields mirror UserSettingsUpdate. "
    "Changing scheduling-related fields bumps the owner's scheduling_revision "
    f"(next replan / progress token): {', '.join(_SCHEDULING_REVISION_FIELDS)}. "
    "nominal_workday_minutes and default_max_block_* do not bump revision. "
    "Read the current token with: theplan settings get"
)


def register_settings(sub: argparse._SubParsersAction) -> None:
    settings = sub.add_parser(
        "settings",
        help="User settings GET/PATCH",
    )
    settings_sub = settings.add_subparsers(dest="settings_command", required=True)

    settings_sub.add_parser(
        "get",
        help="Get current user settings (includes scheduling_revision)",
        epilog=_GET_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    patch_p = settings_sub.add_parser(
        "patch",
        help="Patch user settings (flags and/or JSON body)",
        epilog=_PATCH_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    patch_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    patch_p.add_argument(
        "--stdin",
        action="store_true",
        help="Read UserSettingsUpdate JSON from stdin (merged with flags)",
    )
    patch_p.add_argument("--timezone", default=None)
    patch_p.add_argument("--locale", default=None)
    patch_p.add_argument("--workday-minutes", dest="workday_minutes", type=int, default=None)
    patch_p.add_argument(
        "--nominal-workday-minutes",
        dest="nominal_workday_minutes",
        default=None,
        metavar="MINUTES",
        help="Effort conversion day length (not legacy workday_minutes placement hours). "
        "Accepts friendly hours/minutes (8h, 480, 7h 30m).",
    )
    patch_p.add_argument(
        "--workday-start-local",
        dest="workday_start_local",
        default=None,
        metavar="HH:MM",
    )
    patch_p.add_argument("--workweek-days", dest="workweek_days", type=int, default=None)
    patch_p.add_argument(
        "--inter-block-buffer-minutes",
        dest="inter_block_buffer_minutes",
        type=int,
        default=None,
    )
    patch_p.add_argument(
        "--upcoming-horizon-days",
        dest="upcoming_horizon_days",
        type=int,
        default=None,
    )
    patch_p.add_argument(
        "--default-estimated-duration-minutes",
        dest="default_estimated_duration_minutes",
        default=None,
        metavar="MINUTES",
        help="Default original estimate for new tasks; friendly parse supported.",
    )
    patch_p.add_argument(
        "--default-min-block-duration-minutes",
        dest="default_min_block_duration_minutes",
        type=int,
        default=None,
    )
    patch_p.add_argument(
        "--default-max-block-duration-minutes",
        dest="default_max_block_duration_minutes",
        type=int,
        default=None,
    )
    patch_p.add_argument(
        "--default-max-block-unbounded",
        dest="default_max_block_unbounded",
        action="store_true",
        default=None,
        help="Set default max block to unbounded",
    )
    patch_p.add_argument(
        "--no-default-max-block-unbounded",
        dest="default_max_block_unbounded",
        action="store_false",
        help="Clear default max block unbounded flag",
    )
    patch_p.add_argument(
        "--default-schedule-style",
        dest="default_schedule_style",
        choices=("standalone", "time_block", "bundle", "manual"),
        default=None,
    )
    patch_p.add_argument(
        "--auto-defer-enabled",
        dest="auto_defer_enabled",
        action="store_true",
        default=None,
    )
    patch_p.add_argument(
        "--no-auto-defer-enabled",
        dest="auto_defer_enabled",
        action="store_false",
    )
    patch_p.add_argument(
        "--max-auto-schedule-minutes-per-project-per-day",
        dest="max_auto_schedule_minutes_per_project_per_day",
        type=int,
        default=None,
    )
    patch_p.add_argument(
        "--ups-weights",
        dest="ups_weights",
        default=None,
        metavar="JSON",
        help="UPS weights object as JSON string",
    )
    patch_p.set_defaults(
        default_max_block_unbounded=None,
        auto_defer_enabled=None,
    )


def _patch_from_flags(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {}
    scalar_fields = (
        "timezone",
        "locale",
        "workday_minutes",
        "nominal_workday_minutes",
        "workday_start_local",
        "workweek_days",
        "inter_block_buffer_minutes",
        "upcoming_horizon_days",
        "default_estimated_duration_minutes",
        "default_min_block_duration_minutes",
        "default_max_block_duration_minutes",
        "default_schedule_style",
        "max_auto_schedule_minutes_per_project_per_day",
    )
    duration_fields = {
        "nominal_workday_minutes",
        "default_estimated_duration_minutes",
    }
    for key in scalar_fields:
        value = getattr(args, key, None)
        if value is not None:
            if key in duration_fields and isinstance(value, str):
                value = duration_json_value(value)
            body[key] = value
    for bool_key in ("default_max_block_unbounded", "auto_defer_enabled"):
        value = getattr(args, bool_key, None)
        if value is not None:
            body[bool_key] = value
    ups_raw = getattr(args, "ups_weights", None)
    if ups_raw is not None:
        try:
            parsed = json.loads(ups_raw)
        except json.JSONDecodeError as exc:
            raise CliError(
                code="INVALID_USAGE",
                message=f"--ups-weights must be valid JSON: {exc}",
                exit_code=1,
            ) from exc
        if not isinstance(parsed, dict):
            raise CliError(
                code="INVALID_USAGE",
                message="--ups-weights must be a JSON object",
                exit_code=1,
            )
        body["ups_weights"] = parsed
    return body


def _merge_patch_body(args: argparse.Namespace) -> dict[str, Any]:
    from_file: dict[str, Any] = {}
    if args.file_path or args.stdin:
        from_file = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
    body = {**from_file, **_patch_from_flags(args)}
    if not body:
        raise CliError(
            code="INVALID_USAGE",
            message="Provide at least one setting to patch (flags or --file/--stdin)",
            exit_code=1,
        )
    return body


def _summarize_settings(row: dict[str, Any]) -> None:
    for key in (
        "scheduling_revision",
        "timezone",
        "locale",
        "workday_minutes",
        "nominal_workday_minutes",
        "workday_start_local",
        "workweek_days",
        "inter_block_buffer_minutes",
        "upcoming_horizon_days",
        "default_estimated_duration_minutes",
        "default_min_block_duration_minutes",
        "default_max_block_duration_minutes",
        "default_max_block_unbounded",
        "default_schedule_style",
        "auto_defer_enabled",
        "max_auto_schedule_minutes_per_project_per_day",
    ):
        if key in row:
            print(f"{key}: {row.get(key)}")
    ups = row.get("ups_weights")
    if ups is not None:
        print(f"ups_weights: {json.dumps(ups, sort_keys=True)}")
    note = row.get("duration_conversion_note")
    if note:
        print(f"duration_conversion_note: {note}")


def run_settings(args: argparse.Namespace) -> None:
    cmd = args.settings_command
    if cmd == "get":
        body = api_json("GET", _SETTINGS_PATH, persist_session=True) or {}
        if get_output_format() == "text":
            _summarize_settings(body)
            return
        emit_ok(body)
        return
    if cmd == "patch":
        payload = _merge_patch_body(args)
        body = api_json(
            "PATCH",
            _SETTINGS_PATH,
            json_body=payload,
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_settings(body)
            return
        emit_ok(body)
        return
    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown settings command: {cmd}",
        exit_code=1,
    )
