"""Schedule run and explanation responses (F3 read API)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

StaleCategory = Literal[
    "duration",
    "deadline",
    "map_style",
    "deps",
    "pins",
    "project_daily_cap",
    "timezone_horizon_workweek",
    "lifecycle",
    "busy_external",
    "prerequisite_state",
    "due_at_soft_target",
    "time_map_overrides",
    "provenance",
]
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
            "v3 inputs captured at calculation: duration, deadline, map_style, deps, "
            "pins, project daily cap, timezone/horizon/workweek, lifecycle, external busy, "
            "prerequisite state, due_at and soft target, and time-map overrides on the "
            "effective map. Not in this snapshot: priority/UPS."
        ),
    )
    is_stale: bool
    stale_categories: list[StaleCategory] = Field(
        description=(
            "v3: duration, deadline, map_style, deps, pins, project_daily_cap, "
            "timezone_horizon_workweek, lifecycle, busy_external, prerequisite_state, "
            "due_at_soft_target, time_map_overrides. provenance means the stored "
            "snapshot is missing or another version (including v2). priority_ups "
            "is not compared and is never reported."
        )
    )


class ScheduleExplanationPage(BaseModel):
    items: list[ScheduleExplanationOut]
    total: int
    limit: int
    offset: int


class ScheduleRunStaleSummary(BaseModel):
    """Read-time stale aggregate for every explanation on one run.

    Covers the whole run. Not a page, and not capped at the explanations list limit.
    """

    stale_task_count: int = Field(
        description="Explanations on this run whose read-time compare is stale."
    )
    categories: list[StaleCategory] = Field(
        description=(
            "Sorted union of stale_categories across every stale explanation. "
            "Empty when nothing on the run is stale."
        )
    )
    total_explanations: int = Field(
        description="Explanation rows on the run, including fresh ones."
    )


class TaskScheduleExplanationOut(BaseModel):
    """Latest completed-run explanation, or never_evaluated when this task has no history."""

    task_id: UUID
    evaluation_state: EvaluationState
    summary_text: str
    is_stale: bool
    stale_categories: list[StaleCategory]
    explanation: ScheduleExplanationOut | None = None
