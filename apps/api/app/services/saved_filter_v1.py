"""Locked v1 predicate shapes for system saved views (F7)."""

from __future__ import annotations

from typing import Any

INBOX_PREDICATE_V1: dict[str, Any] = {
    "v": 1,
    "dimensions": {
        "inbox": True,
        "completion": "open",
    },
}

TODAY_PREDICATE_V1: dict[str, Any] = {
    "v": 1,
    "dimensions": {
        "due": {"kind": "rolling", "rolling": "today"},
        "completion": "open",
    },
}

UPCOMING_PREDICATE_V1: dict[str, Any] = {
    "v": 1,
    "dimensions": {
        "due": {"kind": "rolling", "rolling": "within_days", "days": 7},
        "completion": "open",
    },
}

SYSTEM_PREDICATE_BY_SLUG: dict[str, dict[str, Any]] = {
    "inbox": INBOX_PREDICATE_V1,
    "today": TODAY_PREDICATE_V1,
    "upcoming": UPCOMING_PREDICATE_V1,
}
