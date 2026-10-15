# ==============================================================================
#  File: apps/cli/theplan/commands/scheduling.py
#  Description: CLI for S2-V4/V4b assignment + day-scoped writers (body forward).
#  Component: CLI
#  Version: 1.1
#  Created: 2026-10-13
#  Last Update: 2026-10-14 (DEF-045 discoverability epilog)
# ==============================================================================

from __future__ import annotations

import argparse
import json
from typing import Any

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format

_SCHEDULING_EPILOG = """
Revision token
  theplan settings get  →  top-level scheduling_revision
  Pass as expected_revision in JSON bodies. Do not use board_revision.
  Refresh after any successful scheduling write that bumps the token.

Discover windows / policies
  theplan availability list|get|effective
  theplan focus-windows list|get
  theplan scheduling get --scope task|project|epic --id UUID
  theplan tasks scheduling-effective --id UUID

Writing scenario (Prefer afternoon, not Must)
  1) settings get → scheduling_revision
  2) availability create --slug afternoon --name "Afternoon hours" --stdin
     (windows JSON) OR availability list for an existing custom policy id
  3) If the task still has a legacy Time Map: scheduling family-replace
     --scope task --id TASK --stdin (target_family new_rule; prefer rules only)
     Else: scheduling put with may.presence=omit, prefer [{name, policy_id}], must []
  4) tasks create/patch --min-block / --max-block / --max-block-unbounded /
     --keep-in-one-block as needed
  5) tasks scheduling-effective --id TASK → inspect inheritance
  Config writes do not silently replan. Prefer must not become Must.
"""


def _scope_path(scope: str, scope_id: str, suffix: str = "") -> str:
    plural = {"task": "tasks", "project": "projects", "epic": "epics"}[scope]
    base = f"/api/v1/{plural}/{scope_id}/scheduling"
    return f"{base}{suffix}"


def register_scheduling(sub: argparse._SubParsersAction) -> None:
    help_text = (
        "Scheduling assignments (S2-V4/V4b): standing + day-scoped writers. "
        "JSON body is forwarded as-is (selectors/expiry not stripped). "
        "May/Must/Prefer stay distinct — Prefer is never coerced to Must."
    )
    scheduling = sub.add_parser(
        "scheduling",
        help=help_text,
        description=help_text,
        epilog=_SCHEDULING_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scheduling_sub = scheduling.add_subparsers(dest="scheduling_command", required=True)

    def _scope_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--scope",
            required=True,
            choices=("task", "project", "epic"),
            help="Assignment scope",
        )
        parser.add_argument("--id", required=True, dest="scope_id", help="Scope entity UUID")

    def _body_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--file", dest="file_path", default=None)
        parser.add_argument("--stdin", action="store_true")

    get_p = scheduling_sub.add_parser("get", help="Get local assignment at scope")
    _scope_args(get_p)

    put_p = scheduling_sub.add_parser(
        "put",
        help="Ordinary new-rule write (rejects on legacy collision)",
    )
    _scope_args(put_p)
    _body_args(put_p)

    replace_p = scheduling_sub.add_parser(
        "family-replace",
        help="Explicit family switch; preserves revert payload",
    )
    _scope_args(replace_p)
    _body_args(replace_p)

    clear_p = scheduling_sub.add_parser(
        "clear",
        help="Clear local assignment (does not restore displaced prior)",
    )
    _scope_args(clear_p)
    clear_p.add_argument("--expected-revision", type=int, required=True)
    _body_args(clear_p)

    revert_p = scheduling_sub.add_parser(
        "revert",
        help="Restore prior local state from an identified family-replace",
    )
    _scope_args(revert_p)
    revert_p.add_argument("--expected-revision", type=int, required=True)
    revert_p.add_argument("--replacement-id", required=True)
    _body_args(revert_p)

    add_p = scheduling_sub.add_parser("rule-add", help="Named-rule addition (new-rule family)")
    _scope_args(add_p)
    _body_args(add_p)

    replace_named_p = scheduling_sub.add_parser(
        "rule-replace-named",
        help="Named-rule replacement exception",
    )
    _scope_args(replace_named_p)
    _body_args(replace_named_p)

    waive_p = scheduling_sub.add_parser(
        "rule-waive-named",
        help="Named Must waiver exception",
    )
    _scope_args(waive_p)
    _body_args(waive_p)

    remove_p = scheduling_sub.add_parser(
        "rule-remove-named",
        help=(
            "Remove one standing named-rule addition or exception "
            "(restores that named underlying rule; siblings stay)"
        ),
    )
    _scope_args(remove_p)
    _body_args(remove_p)

    # ---- V4b day-scoped (body forwarded; API validates selectors) ----
    list_day = scheduling_sub.add_parser(
        "day-scoped-list",
        help="List day-scoped ops at scope",
    )
    _scope_args(list_day)

    for name, help_msg, suffix in (
        (
            "day-change-selected",
            "Change selected days (day.change_selected)",
            "/day/change-selected",
        ),
        (
            "day-only-allow",
            "Only-allow selected days/times (day.only_allow)",
            "/day/only-allow",
        ),
        (
            "family-replace-scoped",
            "Scoped family replace overlay",
            "/assignment/family-replace-scoped",
        ),
        (
            "clear-scoped",
            "Scoped clear (suppress local; standing kept)",
            "/assignment/clear-scoped",
        ),
        (
            "revert-scoped",
            "Revert scoped family-replace (captured prior)",
            "/assignment/revert-scoped",
        ),
        (
            "rule-add-scoped",
            "Named-rule addition with day/date selector",
            "/rules/add-scoped",
        ),
        (
            "rule-replace-named-scoped",
            "Named-rule replacement with day/date selector",
            "/rules/replace-named-scoped",
        ),
        (
            "rule-waive-named-scoped",
            "Named Must waiver with day/date selector",
            "/rules/waive-named-scoped",
        ),
        (
            "rule-remove-named-scoped",
            "Remove one day-scoped op by stable op_id",
            "/rules/remove-named-scoped",
        ),
    ):
        p = scheduling_sub.add_parser(name, help=help_msg)
        _scope_args(p)
        _body_args(p)
        p.set_defaults(_v4b_suffix=suffix)


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
    if row.get("op"):
        op = row["op"]
        print(f"op: {op.get('op_kind')} id={op.get('id')} selector={op.get('selector_kind')}")
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

    if cmd == "day-scoped-list":
        data = api_json("GET", _scope_path(scope, scope_id, "/day-scoped"))
        if get_output_format() == "text":
            print(json.dumps(data, indent=2, default=str))
            return
        emit_ok(data)
        return

    v4b_suffix = getattr(args, "_v4b_suffix", None)
    if v4b_suffix is not None:
        body = _body_from_args(args, require_body=True)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, v4b_suffix),
            json_body=body,
        )
    elif cmd == "put":
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
    elif cmd == "rule-remove-named":
        body = _body_from_args(args, require_body=True)
        data = api_json(
            "POST",
            _scope_path(scope, scope_id, "/rules/remove-named"),
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
