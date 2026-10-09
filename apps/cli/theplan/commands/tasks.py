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
    ):
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
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
    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown tasks command: {cmd}",
        exit_code=1,
    )
