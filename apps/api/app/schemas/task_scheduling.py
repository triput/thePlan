from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY


class SchedulingSourceOut(BaseModel):
    kind: str
    label: str
    placer_active: bool
    detail: str | None = None


class TaskSchedulingEffectiveOut(BaseModel):
    task_id: UUID
    scheduling_effective_note: str = SCHEDULING_CONFIG_ONLY_COPY
    placement_effort_minutes: int
    sources: list[SchedulingSourceOut] = Field(default_factory=list)
    legacy_time_map_id: UUID | None = None
    legacy_time_map_source: str | None = None
    unclassified_future_policy_slug: str = "general"
    general_policy_scheduling_effective: bool = False
    working_hours_placer_active: bool = True
