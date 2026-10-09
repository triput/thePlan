"""Schedule run and explanation responses (F3 read API)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

StaleCategory = Literal["duration", "deadline", "map_style", "deps", "provenance"]
EvaluationState = Literal["evaluated", "never_evaluated"]


class ReasonFactOut(BaseModel):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)


class ScheduleExplanationOut(BaseModel):
    """One recorded task evaluation. ``is_stale`` is computed on read."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_run_id: UUID
    task_id: UUID
    evaluated_at: datetime
    outcome: str = Field(
        description="Coarse family: placed, unplaced, excluded, blocked, or recorded."
    )
    primary_reason_code: str
    requested_minutes: int
    pinned_minutes: int
    placed_minutes: int
    remaining_minutes: int
    reason_facts: list[ReasonFactOut]
    summary_text: str = Field(
        description="Human text from the same reason facts. Deterministic formatter, no LLM."
    )
    placement_facts: dict[str, Any] | None = None
    algorithm_version: str | None = None
    input_fingerprint: str | None = None
    input_snapshot: dict[str, Any] | None = Field(
        default=None,
        description=(
            "W1 inputs captured at calculation: duration, deadline, map_style, deps. "
            "Deferred and not in this snapshot: pins, project daily cap, timezone/horizon/"
            "workweek, priority/UPS, lifecycle, external busy, time-map overrides (F4), "
            "prerequisite state beyond the edge set, due_at and soft target."
        ),
    )
    is_stale: bool
    stale_categories: list[StaleCategory] = Field(
        description=(
            "W1: duration, deadline, map_style, deps. "
            "provenance means the stored snapshot is missing or an older version. "
            "Deferred categories are never reported here."
        )
    )


class ScheduleExplanationPage(BaseModel):
    items: list[ScheduleExplanationOut]
    total: int
    limit: int
    offset: int


class TaskScheduleExplanationOut(BaseModel):
    """Latest completed-run explanation, or never_evaluated when this task has no history."""

    task_id: UUID
    evaluation_state: EvaluationState
    summary_text: str
    is_stale: bool
    stale_categories: list[StaleCategory]
    explanation: ScheduleExplanationOut | None = None
