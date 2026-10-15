# ==============================================================================
#  File: apps/cli/theplan/commands/tasks.py
#  Description: Task CRUD, recurrence, progress, and scheduling-effective CLI.
#  Component: CLI
#  Version: 1.2
#  Created: 2026-10-09
#  Last Update: 2026-10-14 (DEF-044 recurrence + DEF-045 bounds; DEF-042 complete body)
# ==============================================================================

from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json, task_scheduling_effective_path
from theplan.duration_coerce import duration_json_value
from theplan.errors import CliError
from theplan.output import emit_ok, get_output_format

_SCHEDULE_STYLE_CHOICES = ("standalone", "time_block", "bundle", "manual")

_RECURRENCE_HELP = (
    "Server recurrence: --rrule (FREQ=…) or --recurrence-text "
    "(e.g. 'every monday, wednesday, friday' for three sessions/week). "
    "Optional --starts-on / --ends-on (YYYY-MM-DD), --timezone, --recurrence-fixed. "
    "Update/clear via: theplan tasks recurrence put|clear. "
    "Invalid rules are rejected by the API with no partial write."
)

_CREATE_EPILOG = (
    f"{_RECURRENCE_HELP}\n\n"
    "Scheduling bounds (optional): --min-block, --max-block, --max-block-unbounded "
    "(No limit), --keep-in-one-block, --preferred-time-window-id, --schedule-style.\n"
    "Discover windows: theplan focus-windows list; policies: theplan availability list.\n"
    "May/Must/Prefer writers: theplan scheduling --help. "
    "Revision token: theplan settings get → scheduling_revision."
)


def _add_recurrence_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rrule",
        default=None,
        metavar="RRULE",
        help="RRULE pattern without UNTIL/COUNT (mutually exclusive with --recurrence-text)",
    )
    parser.add_argument(
        "--recurrence-text",
        dest="recurrence_text",
        default=None,
        metavar="TEXT",
        help=(
            "Human recurrence text parsed by the server "
            "(e.g. 'every monday, wednesday, friday')"
        ),
    )
    parser.add_argument(
        "--starts-on",
        dest="starts_on",
        default=None,
        metavar="YYYY-MM-DD",
        help="Recurrence frame start (inclusive local date)",
    )
    parser.add_argument(
        "--ends-on",
        dest="ends_on",
        default=None,
        metavar="YYYY-MM-DD",
        help="Recurrence frame end (inclusive local date)",
    )
    parser.add_argument(
        "--timezone",
        dest="recurrence_timezone",
        default=None,
        metavar="IANA",
        help="Recurrence timezone (default: owner settings timezone)",
    )
    parser.add_argument(
        "--recurrence-fixed",
        dest="recurrence_fixed",
        action="store_true",
        help="Fixed cadence (Every! / is_fixed=true); ignored with --recurrence-text that sets every!",
    )


def _add_scheduling_bound_flags(parser: argparse.ArgumentParser, *, for_patch: bool) -> None:
    parser.add_argument(
        "--min-block",
        dest="min_block_duration_minutes",
        default=None,
        metavar="MINUTES",
        help="Minimum block duration (friendly durations ok)",
    )
    parser.add_argument(
        "--max-block",
        dest="max_block_duration_minutes",
        default=None,
        metavar="MINUTES",
        help="Maximum block duration (friendly durations ok)",
    )
    parser.add_argument(
        "--max-block-unbounded",
        dest="max_block_unbounded",
        action="store_true",
        default=None,
        help="No limit on max block (max_block_unbounded=true)",
    )
    parser.add_argument(
        "--no-max-block-unbounded",
        dest="max_block_unbounded",
        action="store_false",
        help="Clear No-limit flag (max_block_unbounded=false)",
    )
    parser.add_argument(
        "--keep-in-one-block",
        dest="keep_in_one_block",
        action="store_true",
        default=None,
        help="Prefer keeping the task in one contiguous block",
    )
    parser.add_argument(
        "--no-keep-in-one-block",
        dest="keep_in_one_block",
        action="store_false",
        help="Allow splitting across blocks",
    )
    parser.add_argument(
        "--preferred-time-window-id",
        dest="preferred_time_window_id",
        default=None,
        metavar="UUID",
        help="Legacy Time Map / focus window id (discover via focus-windows list)",
    )
    parser.add_argument(
        "--schedule-style",
        dest="schedule_style",
        choices=_SCHEDULE_STYLE_CHOICES,
        default=None,
    )
    if for_patch:
        parser.add_argument(
            "--clear-min-block",
            dest="clear_min_block",
            action="store_true",
            help="Inherit min block (send null)",
        )
        parser.add_argument(
            "--clear-max-block",
            dest="clear_max_block",
            action="store_true",
            help="Inherit max block (send null)",
        )
        parser.add_argument(
            "--clear-preferred-time-window",
            dest="clear_preferred_time_window",
            action="store_true",
            help="Clear preferred_time_window_id (send null)",
        )
    parser.set_defaults(
        max_block_unbounded=None,
        keep_in_one_block=None,
        clear_min_block=False,
        clear_max_block=False,
        clear_preferred_time_window=False,
    )


def register_tasks(sub: argparse._SubParsersAction) -> None:
    tasks = sub.add_parser("tasks", help="Task CRUD via API")
    tasks_sub = tasks.add_subparsers(dest="tasks_command", required=True)

    list_p = tasks_sub.add_parser("list", help="List tasks")
    list_p.add_argument("--project-id", dest="project_id", metavar="UUID")
    list_p.add_argument("--section-id", dest="section_id", metavar="UUID")
    list_p.add_argument("--parent-task-id", dest="parent_task_id", metavar="UUID")
    list_p.add_argument("--label-id", dest="label_id", metavar="UUID")
    list_p.add_argument("--epic-id", dest="epic_id", metavar="UUID")
    list_p.add_argument("--inbox", action="store_true", help="Tasks with no project")
    list_p.add_argument("--trashed", action="store_true", help="Soft-deleted tasks only")
    completed = list_p.add_mutually_exclusive_group()
    completed.add_argument(
        "--completed",
        action="store_true",
        help="Only completed tasks (maps to is_completed=true)",
    )
    completed.add_argument(
        "--incomplete",
        action="store_true",
        help="Only open tasks (maps to is_completed=false)",
    )
    list_p.add_argument("--due-from", dest="due_from", metavar="ISO8601")
    list_p.add_argument("--due-to", dest="due_to", metavar="ISO8601")
    list_p.add_argument(
        "--id",
        dest="ids",
        action="append",
        metavar="UUID",
        help="Filter to task id (repeatable)",
    )
    list_p.add_argument("--limit", type=int, default=None)
    list_p.add_argument("--offset", type=int, default=None)
    list_p.add_argument(
        "--workflow",
        choices=("ready", "in_progress", "waiting", "done"),
        default=None,
        help="Kanban column filter",
    )
    list_p.add_argument(
        "--board-order",
        action="store_true",
        help="Order by board_rank (default when --workflow is set)",
    )

    get_p = tasks_sub.add_parser("get", help="Get one task")
    get_p.add_argument("--id", required=True, dest="task_id", metavar="UUID")

    _duration_help = (
        "Friendly durations: 90m, 1h 30m, 1.5h; bare number = minutes. "
        "Workday units use nominal_workday_minutes from settings get."
    )
    create_p = tasks_sub.add_parser(
        "create",
        help="Create task (sets original=remaining estimate)",
        description=(
            "Create task. estimated-duration sets the original estimate "
            "(stored as estimated_duration_minutes). "
            f"{_duration_help}"
        ),
        epilog=_CREATE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create_p.add_argument("--title", required=True)
    create_p.add_argument("--project-id", dest="project_id", metavar="UUID")
    create_p.add_argument("--due-at", dest="due_at", metavar="ISO8601")
    create_p.add_argument(
        "--priority",
        choices=("p1", "p2", "p3", "p4"),
        default=None,
    )
    create_p.add_argument(
        "--estimated-duration-minutes",
        dest="estimated_duration_minutes",
        default=None,
        metavar="MINUTES",
        help=f"Original estimate. {_duration_help}",
    )
    create_p.add_argument("--description", default=None)
    _add_recurrence_flags(create_p)
    _add_scheduling_bound_flags(create_p, for_patch=False)

    patch_p = tasks_sub.add_parser(
        "patch",
        help="Patch task",
        description=(
            "Patch task fields. Recurrence is not on patch — use "
            "`theplan tasks recurrence put|clear`. "
            f"{_duration_help}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    patch_p.add_argument("--id", required=True, dest="task_id", metavar="UUID")
    patch_p.add_argument("--title", default=None)
    patch_p.add_argument("--project-id", dest="project_id", default=None, metavar="UUID")
    patch_p.add_argument("--due-at", dest="due_at", default=None, metavar="ISO8601")
    patch_p.add_argument(
        "--priority",
        choices=("p1", "p2", "p3", "p4"),
        default=None,
    )
    patch_p.add_argument(
        "--estimated-duration-minutes",
        dest="estimated_duration_minutes",
        default=None,
        metavar="MINUTES",
        help="Original estimate (immutable unless repeating the same value).",
    )
    patch_p.add_argument("--description", default=None)
    patch_p.add_argument(
        "--remaining-estimate-minutes",
        dest="remaining_estimate_minutes",
        default=None,
        metavar="MINUTES",
        help=f"Remaining effort only; original unchanged. {_duration_help}",
    )
    patch_p.add_argument(
        "--expected-revision",
        dest="expected_revision",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Required with --remaining-estimate-minutes: owner scheduling_revision "
            "from `theplan settings get` (not board_revision)"
        ),
    )
    _add_scheduling_bound_flags(patch_p, for_patch=True)

    recurrence = tasks_sub.add_parser(
        "recurrence",
        help="Get, put, or clear task recurrence",
        description=_RECURRENCE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    recurrence_sub = recurrence.add_subparsers(dest="recurrence_command", required=True)

    rec_get = recurrence_sub.add_parser("get", help="Get recurrence for a task")
    rec_get.add_argument("--id", required=True, dest="task_id", metavar="UUID")

    rec_put = recurrence_sub.add_parser(
        "put",
        help="Create or replace recurrence (rejects invalid rules; no partial write)",
        description=_RECURRENCE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rec_put.add_argument("--id", required=True, dest="task_id", metavar="UUID")
    _add_recurrence_flags(rec_put)

    rec_clear = recurrence_sub.add_parser("clear", help="Remove recurrence from a task")
    rec_clear.add_argument("--id", required=True, dest="task_id", metavar="UUID")

    progress = tasks_sub.add_parser("progress", help="Record task progress")
    progress_sub = progress.add_subparsers(dest="progress_command", required=True)
    progress_add = progress_sub.add_parser("add", help="Append a progress entry")
    progress_add.add_argument("--id", required=True, dest="task_id", metavar="UUID")
    progress_add.add_argument(
        "--idempotency-key",
        dest="idempotency_key",
        required=True,
        metavar="UUID",
    )
    progress_add.add_argument(
        "--minutes-worked",
        dest="minutes_worked",
        required=True,
        metavar="MINUTES",
        help=_duration_help,
    )
    progress_add.add_argument(
        "--remaining-minutes",
        dest="remaining_minutes",
        required=True,
        metavar="MINUTES",
        help=f"Remaining after this entry. {_duration_help}",
    )
    progress_add.add_argument(
        "--expected-revision",
        dest="expected_revision",
        type=int,
        required=True,
        metavar="N",
        help=(
            "Owner scheduling_revision from `theplan settings get` "
            "(not board_revision from tasks get)"
        ),
    )
    progress_add.add_argument("--note", default=None)

    _scheduling_effective_help = (
        "Show placer inputs for one task (S1: legacy working hours and Time Maps; "
        "General and Working policies are not scheduling-effective)"
    )
    sched_eff_p = tasks_sub.add_parser(
        "scheduling-effective",
        help=_scheduling_effective_help,
        description=_scheduling_effective_help,
    )
    sched_eff_p.add_argument("--id", required=True, dest="task_id", metavar="UUID")
    sched_eff_p.add_argument(
        "--on",
        dest="on_date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Scheduling day in operator timezone for dated Time Map override resolution",
    )

    complete_p = tasks_sub.add_parser(
        "complete",
        help="Mark task complete (sends JSON body; advances recurrence when applicable)",
    )
    complete_p.add_argument("--id", required=True, dest="task_id", metavar="UUID")
    complete_p.add_argument(
        "--bulk-children",
        dest="bulk_children",
        action="store_true",
        help="Bulk-complete open descendants when open children exist",
    )
    complete_p.add_argument(
        "--force-parent-only",
        dest="force_parent_only",
        action="store_true",
        help="Complete parent only when open children exist",
    )

    uncomplete_p = tasks_sub.add_parser("uncomplete", help="Mark task incomplete")
    uncomplete_p.add_argument("--id", required=True, dest="task_id", metavar="UUID")

    workflow_p = tasks_sub.add_parser("workflow", help="Kanban column transition")
    workflow_p.add_argument("--id", required=True, dest="task_id", metavar="UUID")
    workflow_p.add_argument(
        "--column",
        required=True,
        choices=("ready", "in_progress", "waiting", "done"),
    )
    workflow_p.add_argument(
        "--expected-revision",
        dest="expected_revision",
        type=int,
        required=True,
        metavar="N",
    )
    workflow_p.add_argument("--waiting-note", dest="waiting_note", default=None)
    workflow_p.add_argument("--board-rank", dest="board_rank", type=int, default=None, metavar="N")
    workflow_p.add_argument(
        "--insert-before-id",
        dest="insert_before_id",
        default=None,
        metavar="UUID",
    )
    workflow_p.add_argument(
        "--insert-after-id",
        dest="insert_after_id",
        default=None,
        metavar="UUID",
    )
    workflow_p.add_argument(
        "--bulk-children",
        dest="bulk_children",
        action="store_true",
        help="When completing (Done), bulk-complete open descendants",
    )
    workflow_p.add_argument(
        "--force-parent-only",
        dest="force_parent_only",
        action="store_true",
        help="When completing (Done), complete parent only",
    )


def _list_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key in (
        "project_id",
        "section_id",
        "parent_task_id",
        "label_id",
        "epic_id",
        "due_from",
        "due_to",
        "limit",
        "offset",
        "workflow",
    ):
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    if getattr(args, "board_order", False) or getattr(args, "workflow", None):
        params["board_order"] = True
    if getattr(args, "inbox", False):
        params["inbox"] = True
    if getattr(args, "trashed", False):
        params["trashed"] = True
    if getattr(args, "completed", False):
        params["is_completed"] = True
    if getattr(args, "incomplete", False):
        params["is_completed"] = False
    ids = getattr(args, "ids", None)
    if ids:
        params["ids"] = ids
    return params


def _recurrence_from_args(args: argparse.Namespace, *, required: bool) -> dict[str, Any] | None:
    rrule = getattr(args, "rrule", None)
    text = getattr(args, "recurrence_text", None)
    starts_on = getattr(args, "starts_on", None)
    ends_on = getattr(args, "ends_on", None)
    timezone = getattr(args, "recurrence_timezone", None)
    is_fixed = bool(getattr(args, "recurrence_fixed", False))

    wants = any(
        (
            rrule is not None,
            text is not None,
            starts_on is not None,
            ends_on is not None,
            timezone is not None,
            is_fixed,
        )
    )
    if not wants:
        if required:
            raise CliError(
                code="INVALID_USAGE",
                message="Provide --rrule or --recurrence-text (plus optional frame/timezone flags)",
                exit_code=1,
            )
        return None
    if rrule and text:
        raise CliError(
            code="INVALID_USAGE",
            message="Use either --rrule or --recurrence-text, not both",
            exit_code=1,
        )
    if not rrule and not text:
        raise CliError(
            code="INVALID_USAGE",
            message="--rrule or --recurrence-text is required when setting recurrence",
            exit_code=1,
        )
    body: dict[str, Any] = {}
    if rrule is not None:
        body["rrule"] = rrule.strip()
    if text is not None:
        body["text"] = text.strip()
    if starts_on is not None:
        body["starts_on"] = starts_on
    if ends_on is not None:
        body["ends_on"] = ends_on
    if timezone is not None:
        body["timezone"] = timezone
    if is_fixed:
        body["is_fixed"] = True
    return body


def _apply_scheduling_bounds(args: argparse.Namespace, body: dict[str, Any]) -> None:
    if getattr(args, "clear_min_block", False):
        if getattr(args, "min_block_duration_minutes", None) is not None:
            raise CliError(
                code="INVALID_USAGE",
                message="Use either --min-block or --clear-min-block, not both",
                exit_code=1,
            )
        body["min_block_duration_minutes"] = None
    elif getattr(args, "min_block_duration_minutes", None) is not None:
        body["min_block_duration_minutes"] = duration_json_value(args.min_block_duration_minutes)

    if getattr(args, "clear_max_block", False):
        if getattr(args, "max_block_duration_minutes", None) is not None:
            raise CliError(
                code="INVALID_USAGE",
                message="Use either --max-block or --clear-max-block, not both",
                exit_code=1,
            )
        body["max_block_duration_minutes"] = None
    elif getattr(args, "max_block_duration_minutes", None) is not None:
        body["max_block_duration_minutes"] = duration_json_value(args.max_block_duration_minutes)

    unbounded = getattr(args, "max_block_unbounded", None)
    if unbounded is not None:
        body["max_block_unbounded"] = bool(unbounded)

    keep = getattr(args, "keep_in_one_block", None)
    if keep is not None:
        body["keep_in_one_block"] = bool(keep)

    if getattr(args, "clear_preferred_time_window", False):
        if getattr(args, "preferred_time_window_id", None) is not None:
            raise CliError(
                code="INVALID_USAGE",
                message=(
                    "Use either --preferred-time-window-id or "
                    "--clear-preferred-time-window, not both"
                ),
                exit_code=1,
            )
        body["preferred_time_window_id"] = None
    elif getattr(args, "preferred_time_window_id", None) is not None:
        body["preferred_time_window_id"] = args.preferred_time_window_id

    style = getattr(args, "schedule_style", None)
    if style is not None:
        body["schedule_style"] = style


def _optional_task_fields(args: argparse.Namespace, *, for_create: bool) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if for_create:
        body["title"] = args.title.strip()
    field_map = (
        ("title", "title"),
        ("project_id", "project_id"),
        ("due_at", "due_at"),
        ("priority", "priority"),
        ("estimated_duration_minutes", "estimated_duration_minutes"),
        ("remaining_estimate_minutes", "remaining_estimate_minutes"),
        ("expected_revision", "expected_revision"),
        ("description", "description"),
    )
    for arg_name, json_key in field_map:
        if for_create and arg_name == "title":
            continue
        value = getattr(args, arg_name, None)
        if value is not None:
            if isinstance(value, str) and arg_name == "title":
                value = value.strip()
            if isinstance(value, str) and arg_name in (
                "estimated_duration_minutes",
                "remaining_estimate_minutes",
            ):
                value = duration_json_value(value)
            body[json_key] = value

    _apply_scheduling_bounds(args, body)

    if for_create:
        recurrence = _recurrence_from_args(args, required=False)
        if recurrence is not None:
            body["recurrence"] = recurrence

    if for_create and not body.get("title"):
        raise CliError(code="INVALID_USAGE", message="--title is required", exit_code=1)
    if not for_create and not body:
        raise CliError(
            code="INVALID_USAGE",
            message="Provide at least one field to patch",
            exit_code=1,
        )
    remaining = body.get("remaining_estimate_minutes")
    expected = body.get("expected_revision")
    if remaining is not None and expected is None:
        raise CliError(
            code="INVALID_USAGE",
            message="--expected-revision is required when patching --remaining-estimate-minutes",
            exit_code=1,
        )
    if expected is not None and remaining is None:
        body.pop("expected_revision", None)
        if not for_create and not body:
            raise CliError(
                code="INVALID_USAGE",
                message=(
                    "--expected-revision applies only with --remaining-estimate-minutes; "
                    "provide a field to patch"
                ),
                exit_code=1,
            )
    return body


def _progress_line(task: dict[str, Any]) -> str:
    return (
        f"progress: original={task.get('original_estimate_minutes')} "
        f"worked={task.get('time_worked_minutes')} "
        f"remaining={task.get('remaining_estimate_minutes')}"
    )


def _summarize_recurrence(task: dict[str, Any]) -> None:
    recurrence = task.get("recurrence")
    if not isinstance(recurrence, dict):
        if task.get("recurrence_advanced"):
            print("recurrence_advanced: true")
        return
    print(
        f"recurrence: {recurrence.get('display')} "
        f"rrule={recurrence.get('rrule')} "
        f"tz={recurrence.get('timezone')} "
        f"fixed={recurrence.get('is_fixed')} "
        f"starts_on={recurrence.get('starts_on')} "
        f"ends_on={recurrence.get('ends_on')}"
    )
    if task.get("recurrence_advanced"):
        print(f"recurrence_advanced: {task.get('recurrence_advanced')}")
    if task.get("previous_due_at") is not None:
        print(f"previous_due_at: {task.get('previous_due_at')}")


def _summarize_task(task: dict[str, Any]) -> None:
    print(f"id: {task.get('id')}")
    print(f"title: {task.get('title')}")
    print(_progress_line(task))
    alias = task.get("estimated_duration_minutes")
    if alias is not None:
        print(
            f"estimated_duration_minutes (original alias): {alias} "
            f"(remaining={task.get('remaining_estimate_minutes')})"
        )
    note = task.get("duration_conversion_note")
    if note:
        print(f"duration_conversion_note: {note}")
    for key in (
        "is_completed",
        "priority",
        "due_at",
        "estimated_duration_minutes",
        "board_column",
        "workflow_state",
        "preferred_time_window_id",
        "schedule_style",
    ):
        if key in task:
            print(f"{key}: {task.get(key)}")
    _summarize_recurrence(task)


def _summarize_task_list(body: dict[str, Any]) -> None:
    total = body.get("total", 0)
    print(f"total: {total}  limit: {body.get('limit')}  offset: {body.get('offset')}")
    items = body.get("items") or []
    if not items:
        print("(no tasks)")
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title", "")
        tid = item.get("id", "?")
        print(f"{tid}: {title}")
        print(f"  {_progress_line(item)}")
        rec = item.get("recurrence")
        if isinstance(rec, dict) and rec.get("display"):
            print(f"  recurrence: {rec.get('display')}")


def _summarize_scheduling_effective(body: dict[str, Any]) -> None:
    print(f"task_id: {body.get('task_id')}")
    print(f"placement_effort_minutes: {body.get('placement_effort_minutes')}")
    note = body.get("scheduling_effective_note")
    if note:
        print(f"scheduling_effective_note: {note}")
    print(f"working_hours_placer_active: {body.get('working_hours_placer_active')}")
    print(
        f"general_policy_scheduling_effective: {body.get('general_policy_scheduling_effective')}"
    )

    time_map = body.get("time_map") or {}
    if time_map:
        print(
            f"time_map: status={time_map.get('assignment_status')} "
            f"map_id={time_map.get('effective_map_id')} "
            f"origin={ (time_map.get('origin') or {}).get('effective_source') } "
            f"empty_kind={time_map.get('empty_kind')} strict={time_map.get('strict_mode')}"
        )

    working_active = body.get("working_hours_active") or {}
    if working_active:
        print(
            "working_hours_active (placer): "
            f"workweek_days={working_active.get('workweek_days')} "
            f"start={working_active.get('workday_start_local')} "
            f"minutes={working_active.get('workday_minutes')} "
            f"tz={working_active.get('timezone')}"
        )

    working_saved = body.get("working_policy_saved") or {}
    if working_saved:
        diverges = working_saved.get("diverges_from_legacy")
        print(
            f"working_policy_saved (inactive): diverges_from_legacy={diverges} "
            f"windows={len(working_saved.get('windows') or [])}"
        )
        div_note = working_saved.get("divergence_note")
        if div_note:
            print(f"  divergence_note: {div_note}")

    dated = body.get("dated_resolution") or {}
    if dated:
        print(
            f"dated_resolution: performed={dated.get('performed')} "
            f"on={dated.get('on')} tz={dated.get('operator_timezone')}"
        )
        dated_note = dated.get("note")
        if dated_note:
            print(f"  note: {dated_note}")
        override = dated.get("override")
        if isinstance(override, dict) and override.get("override_id"):
            print(f"  override_id: {override.get('override_id')}")

    duration = body.get("duration") or {}
    if duration:
        print(
            "duration: "
            f"original={duration.get('original_estimate_minutes')} "
            f"(alias estimated_duration_minutes={duration.get('estimated_duration_minutes')}) "
            f"worked={duration.get('time_worked_minutes')} "
            f"remaining={duration.get('remaining_estimate_minutes')} "
            f"placement_effort={duration.get('placement_effort_minutes')}"
        )
        inherited = duration.get("inherited_bounds_preview")
        if isinstance(inherited, dict):
            print(
                "  inherited_bounds_preview: "
                f"min={inherited.get('min_block_duration_minutes')} "
                f"max={inherited.get('max_block_duration_minutes')} "
                f"unbounded={inherited.get('max_block_unbounded')}"
            )
        dur_note = duration.get("note")
        if dur_note:
            print(f"  note: {dur_note}")

    sources = body.get("sources") or []
    if sources:
        print("sources:")
        for source in sources:
            if not isinstance(source, dict):
                continue
            active = "active" if source.get("placer_active") else "inactive"
            detail = source.get("detail")
            line = f"  {source.get('kind')} ({active}): {source.get('label')}"
            if detail:
                line = f"{line} — {detail}"
            print(line)


def _run_recurrence(args: argparse.Namespace) -> None:
    cmd = args.recurrence_command
    task_id = args.task_id
    if cmd == "get":
        body = api_json(
            "GET",
            f"/api/v1/tasks/{task_id}/recurrence",
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "put":
        payload = _recurrence_from_args(args, required=True)
        assert payload is not None
        body = api_json(
            "PUT",
            f"/api/v1/tasks/{task_id}/recurrence",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "clear":
        api_json(
            "DELETE",
            f"/api/v1/tasks/{task_id}/recurrence",
            persist_session=True,
        )
        emit_ok({"cleared": True, "task_id": task_id})
        return
    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown recurrence command: {cmd}",
        exit_code=1,
    )


def run_tasks(args: argparse.Namespace) -> None:
    cmd = args.tasks_command
    if cmd == "list":
        body = api_json(
            "GET",
            "/api/v1/tasks",
            params=_list_params(args),
            persist_session=True,
        )
        payload = body or {}
        if get_output_format() == "text":
            _summarize_task_list(payload)
            return
        emit_ok(payload)
        return
    if cmd == "get":
        body = api_json(
            "GET",
            f"/api/v1/tasks/{args.task_id}",
            persist_session=True,
        )
        payload = body or {}
        if get_output_format() == "text":
            _summarize_task(payload)
            return
        emit_ok(payload)
        return
    if cmd == "create":
        payload = _optional_task_fields(args, for_create=True)
        body = api_json(
            "POST",
            "/api/v1/tasks",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "patch":
        payload = _optional_task_fields(args, for_create=False)
        body = api_json(
            "PATCH",
            f"/api/v1/tasks/{args.task_id}",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "recurrence":
        _run_recurrence(args)
        return
    if cmd == "progress":
        if args.progress_command != "add":
            raise CliError(
                code="INVALID_USAGE",
                message=f"Unknown progress command: {args.progress_command}",
                exit_code=1,
            )
        payload = {
            "idempotency_key": args.idempotency_key,
            "minutes_worked": duration_json_value(args.minutes_worked),
            "remaining_minutes": duration_json_value(args.remaining_minutes),
            "expected_revision": args.expected_revision,
        }
        if args.note is not None:
            payload["note"] = args.note
        body = api_json(
            "POST",
            f"/api/v1/tasks/{args.task_id}/progress-entries",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "scheduling-effective":
        params: dict[str, Any] = {}
        on_date = getattr(args, "on_date", None)
        if on_date is not None:
            params["on"] = on_date
        body = api_json(
            "GET",
            task_scheduling_effective_path(args.task_id),
            params=params or None,
            persist_session=True,
        )
        payload = body or {}
        if get_output_format() == "text":
            _summarize_scheduling_effective(payload)
            return
        emit_ok(payload)
        return
    if cmd == "complete":
        # DEF-042: endpoint requires TaskCompleteBody; send at least {}.
        payload: dict[str, Any] = {}
        if getattr(args, "bulk_children", False):
            payload["bulk_children"] = True
        if getattr(args, "force_parent_only", False):
            payload["force_parent_only"] = True
        body = api_json(
            "POST",
            f"/api/v1/tasks/{args.task_id}/complete",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "uncomplete":
        body = api_json(
            "POST",
            f"/api/v1/tasks/{args.task_id}/uncomplete",
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "workflow":
        payload = {
            "column": args.column,
            "expected_revision": args.expected_revision,
        }
        if args.waiting_note is not None:
            payload["waiting_note"] = args.waiting_note
        if args.board_rank is not None:
            payload["board_rank"] = args.board_rank
        if args.insert_before_id is not None:
            payload["insert_before_id"] = args.insert_before_id
        if args.insert_after_id is not None:
            payload["insert_after_id"] = args.insert_after_id
        if args.bulk_children:
            payload["bulk_children"] = True
        if args.force_parent_only:
            payload["force_parent_only"] = True
        body = api_json(
            "POST",
            f"/api/v1/tasks/{args.task_id}/workflow",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown tasks command: {cmd}",
        exit_code=1,
    )
