from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json
from theplan.commands.handoffs import (
    _summarize_apply_result,
    _summarize_propose,
    _summarize_receipt,
)
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format


def register_templates(sub: argparse._SubParsersAction) -> None:
    templates = sub.add_parser("templates", help="F5 Coursera templates list/get/propose/apply/receipt")
    templates_sub = templates.add_subparsers(dest="templates_command", required=True)

    templates_sub.add_parser("list", help="List built-in Coursera templates")

    get_p = templates_sub.add_parser("get", help="Template detail + example outline JSON")
    get_p.add_argument("template_id", metavar="ID", help="e.g. coursera_specialization")

    propose = templates_sub.add_parser("propose", help="Propose outline → handoff graph + summary")
    propose.add_argument("template_id", metavar="ID")
    propose.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    propose.add_argument("--stdin", action="store_true", help="Read outline or TemplateProposeRequest JSON")
    propose.add_argument(
        "--skip-optional",
        action="store_true",
        help="Exclude optional tasks (default: include optional items)",
    )
    propose.add_argument(
        "--attach-kind",
        choices=("epic", "project", "section"),
        default=None,
        help="Graft under an existing epic, project, or section",
    )
    propose.add_argument(
        "--attach-id",
        dest="attach_id",
        default=None,
        metavar="UUID",
        help="Target id for --attach-kind",
    )

    apply_p = templates_sub.add_parser("apply", help="Apply a proposed handoff graph")
    apply_p.add_argument("template_id", metavar="ID")
    apply_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    apply_p.add_argument("--stdin", action="store_true")
    apply_p.add_argument(
        "--idempotency-key",
        dest="idempotency_key",
        metavar="UUID",
        help="Required unless present in JSON body",
    )

    receipt = templates_sub.add_parser("receipt", help="Fetch template apply receipt")
    receipt_id = receipt.add_mutually_exclusive_group(required=True)
    receipt_id.add_argument("--id", dest="receipt_id", metavar="UUID")
    receipt_id.add_argument("--idempotency-key", dest="idempotency_key", metavar="UUID")


def _summarize_template_list(items: list[dict[str, Any]]) -> None:
    for row in items:
        if not isinstance(row, dict):
            continue
        tid = row.get("id", "?")
        ver = row.get("version", "?")
        title = row.get("title", "")
        modes = row.get("attach_modes") or []
        print(f"{tid} (v{ver}): {title}")
        if modes:
            print(f"  attach_modes: {', '.join(str(m) for m in modes)}")


def _summarize_template_detail(body: dict[str, Any]) -> None:
    print(f"id: {body.get('id')}")
    print(f"version: {body.get('version')}")
    print(f"title: {body.get('title')}")
    desc = body.get("description")
    if desc:
        print(f"description: {desc}")
    modes = body.get("attach_modes") or []
    if modes:
        print(f"attach_modes: {', '.join(str(m) for m in modes)}")
    print(f"outline_pack: {body.get('outline_pack')}")
    print(f"is_scaffold: {body.get('is_scaffold')}")
    print("(example_outline included in JSON output; use --format json to export)")


def _summarize_template_propose(body: dict[str, Any]) -> None:
    print(f"template_id: {body.get('template_id')}")
    print(f"template_version: {body.get('template_version')}")
    if body.get("is_scaffold"):
        print("is_scaffold: true")
    summary = body.get("summary") or {}
    if summary:
        print("summary:")
        for field in ("epic_count", "project_count", "section_count", "task_count", "optional_skipped"):
            if field in summary:
                print(f"  {field}: {summary[field]}")
    _summarize_propose(
        {
            "payload": body.get("payload") or {},
            "resolved_defaults": body.get("resolved_defaults") or [],
            "warnings": body.get("warnings") or [],
        }
    )


def _build_propose_request(raw: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if "outline" in raw:
        body = dict(raw)
    else:
        body = {"outline": raw}
    if args.skip_optional:
        body["skip_optional"] = True
    if args.attach_kind or args.attach_id:
        if not args.attach_kind or not args.attach_id:
            raise CliError(
                code="INVALID_USAGE",
                message="--attach-kind and --attach-id must be used together",
                exit_code=1,
            )
        body["attach_under"] = {"kind": args.attach_kind, "id": str(args.attach_id)}
    return body


def _build_apply_request(raw: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
    key = idempotency_key or raw.get("idempotency_key")
    graph: dict[str, Any]
    if isinstance(raw.get("payload"), dict) and "entities" in raw["payload"]:
        graph = raw["payload"]
    elif "entities" in raw:
        graph = raw
    else:
        raise CliError(
            code="INVALID_USAGE",
            message=(
                "Apply JSON must be a handoff graph (entities, …) or a template propose response "
                "with a payload object"
            ),
            exit_code=1,
        )
    if not key:
        raise CliError(
            code="INVALID_USAGE",
            message="Apply requires --idempotency-key or idempotency_key in JSON",
            exit_code=1,
        )
    return {
        "idempotency_key": str(key),
        "source_refs": graph.get("source_refs") or [],
        "schedule_policy": graph.get("schedule_policy") or "manual",
        "entities": graph["entities"],
        "dependencies": graph.get("dependencies") or [],
    }


def run_templates(args: argparse.Namespace) -> None:
    cmd = args.templates_command
    if cmd == "list":
        body = api_json("GET", "/api/v1/templates", persist_session=True)
        data = body if isinstance(body, list) else []
        if get_output_format() == "text":
            _summarize_template_list(data)
            return
        emit_ok({"templates": data})
        return

    if cmd == "get":
        body = api_json(
            "GET",
            f"/api/v1/templates/{args.template_id}",
            persist_session=True,
        )
        data = body or {}
        if get_output_format() == "text":
            _summarize_template_detail(data)
            return
        emit_ok(data)
        return

    if cmd == "propose":
        raw = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        payload = _build_propose_request(raw, args)
        body = api_json(
            "POST",
            f"/api/v1/templates/{args.template_id}/propose",
            json_body=payload,
            persist_session=True,
        )
        data = body or {}
        if get_output_format() == "text":
            _summarize_template_propose(data)
            return
        emit_ok(data)
        return

    if cmd == "apply":
        raw = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        payload = _build_apply_request(raw, args.idempotency_key)
        body = api_json(
            "POST",
            f"/api/v1/templates/{args.template_id}/apply",
            json_body=payload,
            persist_session=True,
        )
        data = body or {}
        if get_output_format() == "text":
            _summarize_apply_result(data)
            return
        emit_ok(data)
        return

    if cmd == "receipt":
        if args.receipt_id:
            path = f"/api/v1/handoffs/receipts/{args.receipt_id}"
            body = api_json("GET", path, persist_session=True)
            data = body or {}
            if get_output_format() == "text":
                _summarize_receipt(data)
                return
            emit_ok(data)
            return
        path = f"/api/v1/templates/receipts/by-key/{args.idempotency_key}"
        body = api_json("GET", path, persist_session=True)
        data = body or {}
        if get_output_format() == "text":
            _summarize_apply_result(data)
            return
        emit_ok(data)
        return

    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown templates command: {cmd}",
        exit_code=1,
    )
