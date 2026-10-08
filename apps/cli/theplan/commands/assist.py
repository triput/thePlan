from __future__ import annotations

import argparse

from theplan.api_client import api_json
from theplan.input_helpers import read_json_body, resolve_text
from theplan.output import emit_ok


def register_assist(sub: argparse._SubParsersAction) -> None:
    assist = sub.add_parser("assist", help="SLM assist propose/apply")
    assist_sub = assist.add_subparsers(dest="assist_command", required=True)

    propose = assist_sub.add_parser("propose", help="Propose assist actions from text")
    propose.add_argument("--text", default=None)
    propose.add_argument("--text-stdin", action="store_true")

    apply_p = assist_sub.add_parser("apply", help="Apply assist proposal JSON")
    apply_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    apply_p.add_argument("--stdin", action="store_true", help="Read AssistApplyRequest JSON from stdin")


def run_assist(args: argparse.Namespace) -> None:
    cmd = args.assist_command
    if cmd == "propose":
        text = resolve_text(text=args.text, text_stdin=args.text_stdin, flag="--text")
        body = api_json(
            "POST",
            "/api/v1/assist/propose",
            json_body={"text": text},
            persist_session=True,
        )
        emit_ok(body or {})
        return
    if cmd == "apply":
        payload = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        body = api_json(
            "POST",
            "/api/v1/assist/apply",
            json_body=payload,
            persist_session=True,
        )
        emit_ok(body or {})
        return
