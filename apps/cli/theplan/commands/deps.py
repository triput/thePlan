from __future__ import annotations

import argparse

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.output import emit_ok


def register_deps(sub: argparse._SubParsersAction) -> None:
    deps = sub.add_parser("deps", help="Task dependency list/add/remove")
    deps_sub = deps.add_subparsers(dest="deps_command", required=True)

    list_p = deps_sub.add_parser("list", help="List dependencies touching a task")
    list_p.add_argument("--task-id", dest="task_id", required=True, metavar="UUID")

    add_p = deps_sub.add_parser("add", help="Add dependency (path task must be blocking or dependent)")
    add_p.add_argument("--task-id", dest="task_id", required=True, metavar="UUID")
    add_p.add_argument("--blocking-task-id", dest="blocking_task_id", required=True, metavar="UUID")
    add_p.add_argument("--dependent-task-id", dest="dependent_task_id", required=True, metavar="UUID")

    remove_p = deps_sub.add_parser("remove", help="Remove dependency by id")
    remove_p.add_argument("--task-id", dest="task_id", required=True, metavar="UUID")
    remove_p.add_argument("--dependency-id", dest="dependency_id", required=True, metavar="UUID")


def run_deps(args: argparse.Namespace) -> None:
    cmd = args.deps_command
    task_id = args.task_id
    if cmd == "list":
        body = api_json(
            "GET",
            f"/api/v1/tasks/{task_id}/dependencies",
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "add":
        payload = {
            "blocking_task_id": args.blocking_task_id,
            "dependent_task_id": args.dependent_task_id,
        }
        body = api_json(
            "POST",
            f"/api/v1/tasks/{task_id}/dependencies",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "remove":
        api_json(
            "DELETE",
            f"/api/v1/tasks/{task_id}/dependencies/{args.dependency_id}",
            persist_session=True,
        )
        emit_ok({})
        return
    raise CliError(code="INVALID_USAGE", message=f"Unknown deps command: {cmd}", exit_code=1)
