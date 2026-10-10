from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.output import emit_ok


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

    create_p = tasks_sub.add_parser("create", help="Create task")
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
        type=int,
        metavar="N",
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
        type=int,
        default=None,
        metavar="N",
    )
    patch_p.add_argument("--description", default=None)

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
        ("description", "description"),
    )
    for arg_name, json_key in field_map:
        if for_create and arg_name == "title":
            continue
        value = getattr(args, arg_name, None)
        if value is not None:
            if isinstance(value, str) and arg_name == "title":
                value = value.strip()
            body[json_key] = value
    if for_create and not body.get("title"):
        raise CliError(code="INVALID_USAGE", message="--title is required", exit_code=1)
    if not for_create and not body:
        raise CliError(
            code="INVALID_USAGE",
            message="Provide at least one field to patch",
            exit_code=1,
        )
    return body


def run_tasks(args: argparse.Namespace) -> None:
    cmd = args.tasks_command
    if cmd == "list":
        body = api_json(
            "GET",
            "/api/v1/tasks",
            params=_list_params(args),
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "get":
        body = api_json(
            "GET",
            f"/api/v1/tasks/{args.task_id}",
            persist_session=True,
        )
        emit_ok(body or {})
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
