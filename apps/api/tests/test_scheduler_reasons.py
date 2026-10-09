"""Unit tests for F3-W1 reason facts and summary formatter.

W2 families are not formatted here: completed/trashed/archived, dependency
cycle, time-map interval, red exclusion, busy/pinned conflict, deadline
limit, minimum contiguous block, and project daily cap.
"""

from __future__ import annotations

import pytest

from app.scheduler.reasons import (
    REASON_BLOCKED_PREREQUISITE,
    REASON_EXCLUDED_DURATION_COVERED_BY_PINS,
    REASON_EXCLUDED_MANUAL_OR_BUNDLE,
    REASON_PLACED,
    REASON_UNPLACED_HORIZON_EXHAUSTED,
    REASON_UNPLACED_NO_SLOT,
    ReasonFact,
    format_summary_text,
)


@pytest.mark.parametrize(
    ("fact", "expected"),
    [
        (
            ReasonFact(
                REASON_EXCLUDED_MANUAL_OR_BUNDLE,
                {"schedule_style": "manual", "style_source": "task"},
            ),
            "Excluded from auto-scheduling (manual via task).",
        ),
        (
            ReasonFact(
                REASON_EXCLUDED_DURATION_COVERED_BY_PINS,
                {"pinned_minutes": 60, "requested_minutes": 60},
            ),
            "Duration fully covered by pinned blocks (60 of 60 minutes).",
        ),
        (
            ReasonFact(
                REASON_BLOCKED_PREREQUISITE,
                {"blocking_task_ids": ["blocker-1"]},
            ),
            "Waiting on unfinished prerequisite(s): blocker-1.",
        ),
        (
            ReasonFact(
                REASON_PLACED,
                {
                    "placed_minutes": 30,
                    "tier": "green",
                    "time_window_source": "project",
                },
            ),
            "Placed 30 minute(s) in green tier (time map from project).",
        ),
        (
            ReasonFact(
                REASON_UNPLACED_HORIZON_EXHAUSTED,
                {"remaining_minutes": 90},
            ),
            "Could not place 90 remaining minute(s) within the horizon.",
        ),
        (
            ReasonFact(
                REASON_UNPLACED_NO_SLOT,
                {"remaining_minutes": 30},
            ),
            "No suitable slot found for 30 remaining minute(s).",
        ),
    ],
)
def test_w1_reason_code_summary(fact: ReasonFact, expected: str) -> None:
    assert format_summary_text([fact]) == expected


def test_empty_facts_say_no_evaluation() -> None:
    assert format_summary_text([]) == "No scheduling evaluation recorded."
