from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json, task_scheduling_effective_path
from theplan.duration_coerce import duration_json_value
from theplan.errors import CliError
from theplan.output import emit_ok, get_output_format


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

    patch_p = tasks_sub.add_parser("patch", help="Patch task")
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

    complete_p = tasks_sub.add_parser("complete", help="Mark task complete")
    complete_p.add_argument("--id", required=True, dest="task_id", metavar="UUID")

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
    ):
        if key in task:
            print(f"{key}: {task.get(key)}")


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
        body = api_json(
            "POST",
            f"/api/v1/tasks/{args.task_id}/complete",
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
        payload: dict[str, Any] = {
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
