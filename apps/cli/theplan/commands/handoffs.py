from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from theplan.api_client import api_json
from theplan.errors import CliError
from theplan.input_helpers import read_json_body
from theplan.output import emit_ok, get_output_format


def register_handoff(sub: argparse._SubParsersAction) -> None:
    handoff = sub.add_parser("handoff", help="F1 planning handoff propose/apply/receipt")
    handoff_sub = handoff.add_subparsers(dest="handoff_command", required=True)

    propose = handoff_sub.add_parser("propose", help="Propose handoff graph (defaults + warnings)")
    propose.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    propose.add_argument("--stdin", action="store_true", help="Read HandoffGraphPayload JSON from stdin")

    apply_p = handoff_sub.add_parser("apply", help="Apply handoff graph")
    apply_p.add_argument("--file", dest="file_path", default=None, metavar="PATH")
    apply_p.add_argument("--stdin", action="store_true")
    apply_p.add_argument(
        "--idempotency-key",
        dest="idempotency_key",
        metavar="UUID",
        help="Required unless present in JSON body",
    )

    receipt = handoff_sub.add_parser("receipt", help="Fetch apply receipt by id or idempotency key")
    receipt_id = receipt.add_mutually_exclusive_group(required=True)
    receipt_id.add_argument("--id", dest="receipt_id", metavar="UUID")
    receipt_id.add_argument("--idempotency-key", dest="idempotency_key", metavar="UUID")


def _summarize_propose(body: dict[str, Any]) -> None:
    payload = body.get("payload") or {}
    entities = payload.get("entities") or []
    by_key = {e["key"]: e for e in entities if isinstance(e, dict) and "key" in e}
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    roots: list[dict[str, Any]] = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        pk = ent.get("parent_key")
        if pk and pk in by_key:
            children[str(pk)].append(ent)
        else:
            roots.append(ent)

    def walk(ent: dict[str, Any], depth: int) -> list[str]:
        kind = ent.get("kind", "?")
        key = ent.get("key", "?")
        title = ent.get("title", "")
        lines = [f"{'  ' * depth}{kind} {key}: {title}"]
        for child in sorted(children.get(str(key), []), key=lambda c: c.get("sort_order", 0)):
            lines.extend(walk(child, depth + 1))
        return lines

    print("entities:")
    if not roots:
        for ent in entities:
            if isinstance(ent, dict):
                print(f"  {ent.get('kind', '?')} {ent.get('key', '?')}: {ent.get('title', '')}")
    else:
        for root in sorted(roots, key=lambda e: e.get("sort_order", 0)):
            for line in walk(root, 1):
                print(line)

    defaults = body.get("resolved_defaults") or []
    if defaults:
        print("resolved_defaults:")
        for item in defaults:
            if isinstance(item, dict):
                print(
                    f"  {item.get('entity_key')}.{item.get('field')} = {item.get('value')} "
                    f"({item.get('source', 'user_settings')})"
                )

    warnings = body.get("warnings") or []
    if warnings:
        print("warnings:")
        for w in warnings:
            print(f"  - {w}")


def _summarize_apply_result(result: dict[str, Any]) -> None:
    print(f"receipt_id: {result.get('receipt_id')}")
    print(f"idempotency_key: {result.get('idempotency_key')}")
    if result.get("replayed"):
        print("replayed: true")
    counts = result.get("created_counts") or {}
    if counts:
        print("created_counts:")
        for kind, n in sorted(counts.items()):
            print(f"  {kind}: {n}")
    deps = result.get("dependencies_created")
    if deps:
        print(f"dependencies_created: {deps}")
    entities = result.get("entities") or []
    if entities:
        print("entities:")
        for ref in entities:
            if isinstance(ref, dict):
                print(f"  {ref.get('kind')} {ref.get('key')} -> {ref.get('id')}")
    defaults = result.get("defaulted_fields") or []
    if defaults:
        print("defaulted_fields:")
        for item in defaults:
            if isinstance(item, dict):
                print(f"  {item.get('entity_key')}.{item.get('field')} = {item.get('value')}")
    warnings = result.get("warnings") or []
    if warnings:
        print("warnings:")
        for w in warnings:
            print(f"  - {w}")


def _summarize_receipt(body: dict[str, Any]) -> None:
    print(f"receipt_id: {body.get('id')}")
    print(f"idempotency_key: {body.get('idempotency_key')}")
    print(f"created_at: {body.get('created_at')}")
    receipt_json = body.get("receipt_json")
    if isinstance(receipt_json, dict):
        print("--- apply result ---")
        _summarize_apply_result(receipt_json)


def run_handoff(args: argparse.Namespace) -> None:
    cmd = args.handoff_command
    if cmd == "propose":
        payload = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        body = api_json(
            "POST",
            "/api/v1/handoffs/propose",
            json_body=payload,
            persist_session=True,
        )
        data = body or {}
        if get_output_format() == "text":
            _summarize_propose(data)
            return
        emit_ok(data)
        return

    if cmd == "apply":
        payload = read_json_body(file_path=args.file_path, use_stdin=args.stdin)
        key = args.idempotency_key or payload.get("idempotency_key")
        if not key:
            raise CliError(
                code="INVALID_USAGE",
                message="Apply requires --idempotency-key or idempotency_key in JSON",
                exit_code=1,
            )
        payload = dict(payload)
        payload["idempotency_key"] = str(key)
        body = api_json(
            "POST",
            "/api/v1/handoffs/apply",
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
        else:
            path = f"/api/v1/handoffs/receipts/by-key/{args.idempotency_key}"
        body = api_json("GET", path, persist_session=True)
        data = body or {}
        if get_output_format() == "text":
            _summarize_receipt(data)
            return
        emit_ok(data)
        return

    raise CliError(
        code="INVALID_USAGE",
        message=f"Unknown handoff command: {cmd}",
        exit_code=1,
    )
