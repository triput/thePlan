from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.output import emit_ok, get_output_format


def register_schedule(sub: argparse._SubParsersAction) -> None:
    schedule = sub.add_parser("schedule", help="Schedule runs and task explanations (read-only)")
    schedule_sub = schedule.add_subparsers(dest="schedule_command", required=True)

    explain_p = schedule_sub.add_parser(
        "explain",
        help="Latest schedule explanation for a task (does not replan)",
    )
    explain_p.add_argument("--task-id", dest="task_id", required=True, metavar="UUID")

    runs = schedule_sub.add_parser("runs", help="Schedule run history")
    runs_sub = runs.add_subparsers(dest="runs_command", required=True)

    list_p = runs_sub.add_parser("list", help="List schedule runs, newest first")
    list_p.add_argument("--limit", type=int, default=None)
    list_p.add_argument("--offset", type=int, default=None)

    get_p = runs_sub.add_parser("get", help="Get one schedule run")
    get_p.add_argument("--id", dest="run_id", required=True, metavar="UUID")

    expl_p = runs_sub.add_parser(
        "explanations",
        help="Per-task explanations recorded for a run",
    )
    expl_p.add_argument("--id", dest="run_id", required=True, metavar="UUID")
    expl_p.add_argument("--task-id", dest="task_id", default=None, metavar="UUID")
    expl_p.add_argument("--limit", type=int, default=None)
    expl_p.add_argument("--offset", type=int, default=None)


def _pagination_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key in ("limit", "offset", "task_id"):
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    return params


def _emit_explain(body: dict[str, Any]) -> None:
    """JSON adds human_summary alias; text mode still prints summary_text via emit_ok."""
    payload = dict(body)
    if get_output_format() == "json":
        payload["human_summary"] = body.get("summary_text", "")
    emit_ok(payload)


def run_schedule(args: argparse.Namespace) -> None:
    cmd = args.schedule_command
    if cmd == "explain":
        body = api_json(
            "GET",
            f"/api/v1/tasks/{args.task_id}/schedule-explanation",
            persist_session=True,
        )
        _emit_explain(body or {})
        return
    if cmd == "runs":
        runs_cmd = args.runs_command
        if runs_cmd == "list":
            body = api_json(
                "GET",
                "/api/v1/schedule/runs",
                params=_pagination_params(args),
                persist_session=True,
            )
            emit_ok(body or {})
            return
        if runs_cmd == "get":
            body = api_json(
                "GET",
                f"/api/v1/schedule/runs/{args.run_id}",
                persist_session=True,
            )
            emit_ok(body or {})
            return
        if runs_cmd == "explanations":
            body = api_json(
                "GET",
                f"/api/v1/schedule/runs/{args.run_id}/explanations",
                params=_pagination_params(args),
                persist_session=True,
            )
            emit_ok(body or {})
            return
        raise CliError(
            code="INVALID_USAGE",
            message=f"Unknown schedule runs command: {runs_cmd}",
            exit_code=1,
        )
    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown schedule command: {cmd}",
        exit_code=1,
    )
