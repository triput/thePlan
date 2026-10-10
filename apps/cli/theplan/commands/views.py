from __future__ import annotations

import argparse
from typing import Any

from theplan.api_client import api_json, unwrap_api_list
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format


def register_views(sub: argparse._SubParsersAction) -> None:
    views = sub.add_parser("views", help="Saved views CRUD and predicate-backed task query (F7)")
    views_sub = views.add_subparsers(dest="views_command", required=True)

    views_sub.add_parser("list", help="List system and user saved views")

    get_p = views_sub.add_parser("get", help="Get one saved view by id")
    get_p.add_argument("--id", required=True, dest="view_id", metavar="UUID")

    create_p = views_sub.add_parser("create", help="Create user saved view (JSON body)")
    create_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    create_p.add_argument("--stdin", action="store_true", help="Read SavedViewCreate JSON from stdin")

    patch_p = views_sub.add_parser("patch", help="Patch user saved view (JSON body)")
    patch_p.add_argument("--id", required=True, dest="view_id", metavar="UUID")
    patch_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    patch_p.add_argument("--stdin", action="store_true")

    delete_p = views_sub.add_parser("delete", help="Delete user saved view (tasks unchanged)")
    delete_p.add_argument("--id", required=True, dest="view_id", metavar="UUID")

    query_p = views_sub.add_parser("query", help="List tasks matching a saved view")
    target = query_p.add_mutually_exclusive_group(required=True)
    target.add_argument("--id", dest="view_id", metavar="UUID")
    target.add_argument("--slug", dest="slug", help="System or user slug (e.g. inbox)")
    query_p.add_argument("--limit", type=int, default=None)
    query_p.add_argument("--offset", type=int, default=None)
    query_p.add_argument(
        "--board-order",
        action="store_true",
        help="Order by board_rank then created_at",
    )


def _summarize_view_list(rows: list[Any]) -> None:
    if not rows:
        print("(no views)")
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        system = " [system]" if row.get("is_system") else ""
        print(
            f"{row.get('name', '?')}{system}  id={row.get('id')}  slug={row.get('slug')}  "
            f"sort_order={row.get('sort_order')}"
        )


def _summarize_view_detail(row: dict[str, Any]) -> None:
    print(f"id: {row.get('id')}")
    print(f"name: {row.get('name')}")
    print(f"slug: {row.get('slug')}")
    print(f"is_system: {row.get('is_system')}")
    print(f"sort_order: {row.get('sort_order')}")
    print(f"predicate_json: {row.get('predicate_json')}")
    pres = row.get("presentation_json")
    if pres:
        print(f"presentation_json: {pres}")


def _summarize_view_tasks(body: dict[str, Any]) -> None:
    total = body.get("total", 0)
    limit = body.get("limit", 0)
    offset = body.get("offset", 0)
    print(f"total: {total}  limit: {limit}  offset: {offset}")
    invalid = body.get("invalid_references")
    if invalid:
        print("invalid_references:")
        for ref in invalid:
            if isinstance(ref, dict):
                print(f"  {ref.get('kind')}: {ref.get('id')}")
    items = body.get("items") or []
    print(f"items ({len(items)} on this page):")
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title", "")
        tid = item.get("id", "?")
        completed = " [done]" if item.get("is_completed") else ""
        print(f"  {tid}{completed}: {title}")


def _query_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key in ("limit", "offset"):
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    if getattr(args, "board_order", False):
        params["board_order"] = True
    return params


def _query_path(args: argparse.Namespace) -> str:
    if args.view_id:
        return f"/api/v1/views/{args.view_id}/tasks"
    slug = (args.slug or "").strip()
    if not slug:
        raise CliError(code="INVALID_USAGE", message="--slug must be non-empty", exit_code=1)
    return f"/api/v1/views/by-slug/{slug}/tasks"


def run_views(args: argparse.Namespace) -> None:
    cmd = args.views_command
    if cmd == "list":
        raw = api_json("GET", "/api/v1/views", persist_session=True)
        rows = unwrap_api_list(raw)
        if get_output_format() == "text":
            _summarize_view_list(rows)
            return
        emit_ok({"views": rows})
        return

    if cmd == "get":
        body = api_json("GET", f"/api/v1/views/{args.view_id}", persist_session=True) or {}
        if get_output_format() == "text":
            _summarize_view_detail(body)
            return
        emit_ok(body)
        return

    if cmd == "create":
        payload = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        body = api_json("POST", "/api/v1/views", json_body=payload, persist_session=True) or {}
        if get_output_format() == "text":
            _summarize_view_detail(body)
            return
        emit_ok(body)
        return

    if cmd == "patch":
        payload = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        if not payload:
            raise CliError(
                code="INVALID_USAGE",
                message="Patch JSON must include at least one field",
                exit_code=1,
            )
        body = api_json(
            "PATCH",
            f"/api/v1/views/{args.view_id}",
            json_body=payload,
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_view_detail(body)
            return
        emit_ok(body)
        return

    if cmd == "delete":
        api_json("DELETE", f"/api/v1/views/{args.view_id}", persist_session=True)
        if get_output_format() == "text":
            print(f"deleted view {args.view_id}")
            return
        emit_ok({"deleted": True, "id": str(args.view_id)})
        return

    if cmd == "query":
        body = api_json(
            "GET",
            _query_path(args),
            params=_query_params(args),
            persist_session=True,
        ) or {}
        if get_output_format() == "text":
            _summarize_view_tasks(body)
            return
        emit_ok(body)
        return

    raise CliError(code="INVALID_USAGE", message=f"Unknown views command: {cmd}", exit_code=1)
