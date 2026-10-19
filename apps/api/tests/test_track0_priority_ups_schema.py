# ==============================================================================
#  File: apps/api/tests/test_track0_priority_ups_schema.py
#  Description: Track 0 — response schema accepts compared priority_ups (and composition).
#  Component: Schedule explanations
#  Version: 1.0
#  Created: 2026-10-19
# ==============================================================================

"""Isolated regression: stale-summary / explanation response Literals include
categories the fingerprint compare already emits. Omitting them caused HTTP 500
validation errors when priority_ups drifted (Cabinet investigation Oct 19).
"""

from __future__ import annotations

from typing import get_args
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.schedule import (
    ScheduleExplanationOut,
    ScheduleRunStaleSummary,
    StaleCategory,
    TaskScheduleExplanationOut,
)
from app.scheduler.input_fingerprint import COMPARED_STALE_CATEGORIES


def test_compared_categories_are_valid_stale_category_literals() -> None:
    allowed = set(get_args(StaleCategory))
    missing = [c for c in COMPARED_STALE_CATEGORIES if c not in allowed]
    assert missing == [], f"response Literal omits compared categories: {missing}"


def test_stale_summary_accepts_priority_ups_category() -> None:
    summary = ScheduleRunStaleSummary(
        stale_task_count=1,
        categories=["priority_ups"],
        total_explanations=3,
    )
    assert summary.categories == ["priority_ups"]


def test_stale_summary_accepts_composition_category() -> None:
    summary = ScheduleRunStaleSummary(
        stale_task_count=1,
        categories=["composition"],
        total_explanations=1,
    )
    assert summary.categories == ["composition"]


def test_task_explanation_out_accepts_priority_ups() -> None:
    body = TaskScheduleExplanationOut(
        task_id=uuid4(),
        evaluation_state="never_evaluated",
        summary_text="not evaluated",
        is_stale=True,
        stale_categories=["priority_ups"],
        explanation=None,
    )
    assert body.stale_categories == ["priority_ups"]


def test_stale_summary_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        ScheduleRunStaleSummary(
            stale_task_count=1,
            categories=["not_a_real_category"],  # type: ignore[list-item]
            total_explanations=1,
        )


def test_explanation_out_field_allows_priority_ups_in_list() -> None:
    """Field annotation alone must not strip priority_ups on model_validate."""
    payload = {
        "id": str(uuid4()),
        "schedule_run_id": str(uuid4()),
        "task_id": str(uuid4()),
        "evaluated_at": "2026-10-15T18:06:00Z",
        "outcome": "placed",
        "primary_reason_code": "placed",
        "requested_minutes": 30,
        "pinned_minutes": 0,
        "placed_minutes": 30,
        "remaining_minutes": 0,
        "reason_facts": [],
        "summary_text": "placed",
        "is_stale": True,
        "stale_categories": ["priority_ups"],
    }
    out = ScheduleExplanationOut.model_validate(payload)
    assert out.stale_categories == ["priority_ups"]
