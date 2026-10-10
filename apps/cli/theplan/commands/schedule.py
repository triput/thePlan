from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.output import emit_ok, get_output_format


def register_schedule(sub: argparse._SubParsersAction) -> None:
    schedule = sub.add_parser(
        "schedule",
        help="Schedule explanations, run history, and replan previews",
    )
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

    preview = schedule_sub.add_parser(
        "preview",
        help="Replan previews (create, inspect, apply)",
    )
    preview_sub = preview.add_subparsers(dest="preview_command", required=True)

    preview_sub.add_parser(
        "create",
        help="Start an async replan preview (does not change the live schedule)",
    )

    get_preview = preview_sub.add_parser("get", help="Get one schedule preview")
    get_preview.add_argument("--id", dest="preview_id", required=True, metavar="UUID")

    apply_preview = preview_sub.add_parser(
        "apply",
        help="Apply a ready preview (stale or expired exits 5)",
    )
    apply_preview.add_argument("--id", dest="preview_id", required=True, metavar="UUID")


_FRESH_PREVIEW = "Create a fresh preview."


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


def _clarify_preview_error(exc: CliError) -> CliError:
    """Keep PREVIEW_STALE / PREVIEW_EXPIRED actionable without hiding the API code."""
    categories = (exc.extra or {}).get("stale_categories")
    message = exc.message
    if exc.code == "PREVIEW_STALE" and isinstance(categories, list) and categories:
        shown = ", ".join(str(item) for item in categories)
        message = f"{message} ({shown})"
    stale_or_expired = exc.code in {"PREVIEW_STALE", "PREVIEW_EXPIRED"} or (
        exc.code == "PREVIEW_NOT_APPLICABLE"
        and ("status is stale" in message or "status is expired" in message)
    )
    if not stale_or_expired:
        return exc
    if _FRESH_PREVIEW not in message:
        message = f"{message}. {_FRESH_PREVIEW}"
    return CliError(
        code=exc.code,
        message=message,
        exit_code=exc.exit_code,
        extra=exc.extra,
    )


def _preview_json(method: str, path: str) -> dict[str, Any] | None:
    try:
        return api_json(method, path, persist_session=True)
    except CliError as exc:
        raise _clarify_preview_error(exc) from exc


def _run_preview(args: argparse.Namespace) -> None:
    cmd = args.preview_command
    if cmd == "create":
        body = _preview_json("POST", "/api/v1/schedule/previews")
        emit_ok(body or {})
        return
    if cmd == "get":
        body = _preview_json("GET", f"/api/v1/schedule/previews/{args.preview_id}")
        emit_ok(body or {})
        return
    if cmd == "apply":
        body = _preview_json("POST", f"/api/v1/schedule/previews/{args.preview_id}/apply")
        emit_ok(body or {})
        return
    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown schedule preview command: {cmd}",
        exit_code=1,
    )


def run_schedule(args: argparse.Namespace) -> None:
    cmd = args.schedule_command
    if cmd == "preview":
        _run_preview(args)
        return
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
