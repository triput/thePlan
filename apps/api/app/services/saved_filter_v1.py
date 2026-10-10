# ==============================================================================
#  File: apps/api/app/services/saved_filter_v1.py
#  Description: Locked v1 predicate constants for system saved views (Inbox, Today, Upcoming).
#  Component: Saved Views
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

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
