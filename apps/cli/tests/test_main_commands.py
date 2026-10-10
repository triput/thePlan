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
        ["templates", "list"],
        ["templates", "get", "coursera_specialization"],
        ["templates", "propose", "coursera_course", "--stdin"],
        [
            "templates",
            "apply",
            "coursera_course",
            "--stdin",
            "--idempotency-key",
            "00000000-0000-0000-0000-000000000002",
        ],
        ["templates", "receipt", "--idempotency-key", "00000000-0000-0000-0000-000000000002"],
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
        ["schedule", "preview", "create"],
        ["schedule", "preview", "get", "--id", "00000000-0000-0000-0000-000000000040"],
        ["schedule", "preview", "apply", "--id", "00000000-0000-0000-0000-000000000040"],
        ["views", "list"],
        ["views", "get", "--id", "00000000-0000-0000-0000-000000000050"],
        ["views", "create", "--stdin"],
        ["views", "patch", "--id", "00000000-0000-0000-0000-000000000050", "--stdin"],
        ["views", "delete", "--id", "00000000-0000-0000-0000-000000000050"],
        ["views", "query", "--slug", "inbox"],
        ["views", "query", "--id", "00000000-0000-0000-0000-000000000050", "--limit", "10"],
    ],
)
def test_parser_accepts_f1_commands(argv: list[str]) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    assert args.command == argv[0]
