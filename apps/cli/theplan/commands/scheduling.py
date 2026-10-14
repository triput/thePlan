# ==============================================================================
#  File: apps/cli/theplan/commands/scheduling.py
#  Description: CLI for S2-V4 assignment family replace/clear/revert + named rules.
#  Component: CLI
#  Version: 1.0
#  Created: 2026-10-13
#  Last Update: 2026-10-13
# ==============================================================================

from __future__ import annotations

import argparse
import json
from typing import Any

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format


def _scope_path(scope: str, scope_id: str, suffix: str = "") -> str:
    plural = {"task": "tasks", "project": "projects", "epic": "epics"}[scope]
    base = f"/api/v1/{plural}/{scope_id}/scheduling"
    return f"{base}{suffix}"


def register_scheduling(sub: argparse._SubParsersAction) -> None:
    help_text = (
        "Scheduling assignments (S2-V4): family-replace / clear / revert / named rules"
    )
    scheduling = sub.add_parser("scheduling", help=help_text, description=help_text)
    scheduling_sub = scheduling.add_subparsers(dest="scheduling_command", required=True)

    def _scope_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--scope",
            required=True,
            choices=("task", "project", "epic"),
            help="Assignment scope",
        )
        parser.add_argument("--id", required=True, dest="scope_id", help="Scope entity UUID")

    get_p = scheduling_sub.add_parser("get", help="Get local assignment at scope")
    _scope_args(get_p)

    put_p = scheduling_sub.add_parser(
        "put",
        help="Ordinary new-rule write (rejects on legacy collision)",
    )
    _scope_args(put_p)
    put_p.add_argument("--file", dest="file_path", default=None)
    put_p.add_argument("--stdin", action="store_true")

    replace_p = scheduling_sub.add_parser(
        "family-replace",
        help="Explicit family switch; preserves revert payload",
    )
    _scope_args(replace_p)
    replace_p.add_argument("--file", dest="file_path", default=None)
    replace_p.add_argument("--stdin", action="store_true")

    clear_p = scheduling_sub.add_parser(
        "clear",
        help="Clear local assignment (does not restore displaced prior)",
    )
    _scope_args(clear_p)
    clear_p.add_argument("--expected-revision", type=int, required=True)
    clear_p.add_argument("--file", dest="file_path", default=None)
    clear_p.add_argument("--stdin", action="store_true")

    revert_p = scheduling_sub.add_parser(
        "revert",
        help="Restore prior local state from an identified family-replace",
    )
    _scope_args(revert_p)
    revert_p.add_argument("--expected-revision", type=int, required=True)
    revert_p.add_argument("--replacement-id", required=True)
    revert_p.add_argument("--file", dest="file_path", default=None)
    revert_p.add_argument("--stdin", action="store_true")

    add_p = scheduling_sub.add_parser("rule-add", help="Named-rule addition (new-rule family)")
    _scope_args(add_p)
    add_p.add_argument("--file", dest="file_path", default=None)
    add_p.add_argument("--stdin", action="store_true")

    replace_named_p = scheduling_sub.add_parser(
        "rule-replace-named",
        help="Named-rule replacement exception",
    )
    _scope_args(replace_named_p)
    replace_named_p.add_argument("--file", dest="file_path", default=None)
    replace_named_p.add_argument("--stdin", action="store_true")

    waive_p = scheduling_sub.add_parser(
        "rule-waive-named",
        help="Named Must waiver exception",
    )
    _scope_args(waive_p)
    waive_p.add_argument("--file", dest="file_path", default=None)
    waive_p.add_argument("--stdin", action="store_true")


def _body_from_args(args: argparse.Namespace, *, require_body: bool) -> dict[str, Any]:
    if args.file_path or getattr(args, "stdin", False):
        return read_json_body(file_path=args.file_path, use_stdin=bool(args.stdin))
    if require_body:
        raise CliError(
            code="INVALID_USAGE",
            message="Provide --file or --stdin JSON body",
            exit_code=1,
        )
    return {}


def _summarize(row: dict[str, Any]) -> None:
    print(f"scope: {row.get('scope')} id={row.get('scope_id')}")
    if "family" in row:
        print(f"family: {row.get('family')}")
    if "scheduling_revision" in row:
        print(f"scheduling_revision: {row.get('scheduling_revision')}")
    if row.get("replacement_id"):
        print(f"replacement_id: {row.get('replacement_id')}")
    if row.get("revert_replacement_id"):
        print(f"revert_replacement_id: {row.get('revert_replacement_id')}")
    may = row.get("may")
    if isinstance(may, dict):
        print(f"may.presence: {may.get('presence')} rules={len(may.get('rules') or [])}")
    assignment = row.get("assignment")
    if isinstance(assignment, dict):
        print(f"assignment.family: {assignment.get('family')}")
        if assignment.get("may"):
            print(
                f"assignment.may.presence: {assignment['may'].get('presence')} "
                f"rules={len(assignment['may'].get('rules') or [])}"
            )


def run_scheduling(args: argparse.Namespace) -> None:
    cmd = args.scheduling_command
    scope = args.scope
    scope_id = args.scope_id

    if cmd == "get":
        data = api_json("GET", _scope_path(scope, scope_id))
        if get_output_format() == "text":
            assert isinstance(data, dict)
            _summarize(data)
            return
        emit_ok(data)
        return

    if cmd == "put":
        body = _body_from_args(args, require_body=True)
        data = api_json("PUT", _scope_path(scope, scope_id), json_body=body)
    elif cmd == "family-replace":
        body = _body_from_args(args, require_body=True)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, "/assignment/family-replace"),
            json_body=body,
        )
    elif cmd == "clear":
        body = _body_from_args(args, require_body=False)
        body.setdefault("expected_revision", args.expected_revision)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, "/assignment/clear"),
            json_body=body,
        )
    elif cmd == "revert":
        body = _body_from_args(args, require_body=False)
        body.setdefault("expected_revision", args.expected_revision)
        body.setdefault("replacement_id", args.replacement_id)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, "/assignment/revert"),
            json_body=body,
        )
    elif cmd == "rule-add":
        body = _body_from_args(args, require_body=True)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, "/rules/add"),
            json_body=body,
        )
    elif cmd == "rule-replace-named":
        body = _body_from_args(args, require_body=True)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, "/rules/replace-named"),
            json_body=body,
        )
    elif cmd == "rule-waive-named":
        body = _body_from_args(args, require_body=True)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, "/rules/waive-named"),
            json_body=body,
        )
    else:
        raise CliError(
            code="INVALID_USAGE",
            message=f"Unknown scheduling command: {cmd}",
            exit_code=1,
        )

    if get_output_format() == "text":
        assert isinstance(data, dict)
        _summarize(data)
        print(json.dumps(data, indent=2, default=str))
        return
    emit_ok(data)
