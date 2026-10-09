"""Parser registration smoke — no live API."""

from __future__ import annotations

import pytest

from theplan.main import _build_parser


@pytest.mark.parametrize(
    "argv",
    [
        ["handoff", "propose", "--stdin"],
        ["handoff", "apply", "--stdin", "--idempotency-key", "00000000-0000-0000-0000-000000000001"],
        ["handoff", "receipt", "--idempotency-key", "00000000-0000-0000-0000-000000000001"],
        ["epics", "list"],
        ["projects", "create", "--title", "CLI test"],
        ["sections", "list", "--project-id", "00000000-0000-0000-0000-000000000010"],
        ["tasks", "complete", "--id", "00000000-0000-0000-0000-000000000020"],
        ["deps", "list", "--task-id", "00000000-0000-0000-0000-000000000020"],
        ["schedule", "explain", "--task-id", "00000000-0000-0000-0000-000000000020"],
        ["schedule", "runs", "list"],
        ["schedule", "runs", "get", "--id", "00000000-0000-0000-0000-000000000030"],
        [
            "schedule",
            "runs",
            "explanations",
            "--id",
            "00000000-0000-0000-0000-000000000030",
            "--task-id",
            "00000000-0000-0000-0000-000000000020",
        ],
    ],
)
def test_parser_accepts_f1_commands(argv: list[str]) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    assert args.command == argv[0]
