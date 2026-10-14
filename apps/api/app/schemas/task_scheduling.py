from datetime import date, datetime, time
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY, AvailabilityWindowOut
from app.schemas.hierarchy import TimeMapBandOut
from app.schemas.scheduling_assignment import ResolvedSchedulingOut


class SchedulingSourceOut(BaseModel):
    kind: str
    label: str
    placer_active: bool
    detail: str | None = None


class TimeMapEmptyKind(str, Enum):
    not_applicable = "not_applicable"
    assigned_empty_strict = "assigned_empty_strict"
    assigned_empty_nonstrict = "assigned_empty_nonstrict"
    no_assignment_fallback = "no_assignment_fallback"


class TimeMapOriginOut(BaseModel):
    effective_source: str | None = None
    task_preferred_time_window_id: UUID | None = None
    project_preferred_time_window_id: UUID | None = None
    epic_preferred_time_window_id: UUID | None = None


class TimeMapEffectiveOut(BaseModel):
    assignment_status: str
    origin: TimeMapOriginOut
    effective_map_id: UUID | None = None
    map_name: str | None = None
    strict_mode: bool | None = None
    band_count: int = 0
    bands: list[TimeMapBandOut] = Field(default_factory=list)
    empty_kind: TimeMapEmptyKind
    placer_active: bool = True


class LegacyWorkweekActiveOut(BaseModel):
    workweek_days: int
    workday_start_local: time
    workday_minutes: int
    timezone: str
    placer_active: bool = True


class SavedAvailabilityPolicyOut(BaseModel):
    policy_id: UUID | None = None
    slug: str
    name: str | None = None
    windows: list[AvailabilityWindowOut] = Field(default_factory=list)
    placer_active: bool = False
    saved_but_unsupported: bool = True
    note: str | None = None
    diverges_from_legacy: bool | None = None
    divergence_note: str | None = None


class DatedSchedulingSegmentOut(BaseModel):
    """UTC half-open interval where one map layer applies (V3-D2 / A11f)."""

    start: datetime
    end: datetime
    source: Literal["base_map", "override"]
    override_id: UUID | None = None
    strict_mode: bool
    day_bands: list[TimeMapBandOut] = Field(default_factory=list)


class DatedOverrideReplacesOut(BaseModel):
    scope: str = "day_bands_and_strict_mode"
    base_map_id: UUID
    inheritance_source: str | None = None
    operator_scheduling_day: date
    weekday_uses_operator_on: bool = True
    base_strict_mode: bool
    effective_strict_mode: bool
    base_day_band_count: int
    effective_day_band_count: int
    base_day_bands: list[TimeMapBandOut] = Field(default_factory=list)
    effective_day_bands: list[TimeMapBandOut] = Field(default_factory=list)
    note: str = (
        "Override replaces this scheduling day's Time Map bands and strict_mode only "
        "(not workweek settings or the base map row)."
    )


class DatedOverrideDetailOut(BaseModel):
    override_id: UUID
    map_id: UUID
    local_start_date: date
    local_end_date: date
    timezone: str
    strict_mode: bool
    effective_local_date: date
    payload: dict = Field(default_factory=dict)


class DatedResolutionOut(BaseModel):
    performed: bool
    on: date | None = None
    operator_timezone: str
    override: DatedOverrideDetailOut | None = None
    replaces: DatedOverrideReplacesOut | None = None
    segments: list[DatedSchedulingSegmentOut] = Field(default_factory=list)
    note: str | None = None


class InheritedBlockBoundsPreview(BaseModel):
    min_block_duration_minutes: int | None = None
    max_block_duration_minutes: int | None = None
    max_block_unbounded: bool
    source: str = "user_settings"
    note: str = (
        "Preview only when task bounds are unset (NULL); inherit writes stay S2-pending."
    )


class KeepInOneSchedulingConflictOut(BaseModel):
    code: str
    message: str
    detail: dict | None = None


class DurationEffectiveOut(BaseModel):
    original_estimate_minutes: int
    time_worked_minutes: int
    remaining_estimate_minutes: int
    estimated_duration_minutes: int
    placement_effort_minutes: int
    min_block_duration_minutes: int | None = None
    max_block_duration_minutes: int | None = None
    max_block_unbounded: bool
    keep_in_one_block: bool
    inherited_bounds_preview: InheritedBlockBoundsPreview | None = None
    chunking_scheduling_effective: bool = False
    effective_min_block_duration_minutes: int | None = None
    effective_max_block_duration_minutes: int | None = None
    min_block_source: str | None = None
    max_block_source: str | None = None
    effective_bounds_conflict: bool = False
    keep_in_one_scheduling_conflicts: list[KeepInOneSchedulingConflictOut] = Field(
        default_factory=list
    )
    note: str = (
        "estimated_duration_minutes is the original-estimate alias. "
        "placement_effort_minutes follows remaining estimate when set, else that alias. "
        "Pin-adjusted placement effort is not computed on this read."
    )


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
    time_map: TimeMapEffectiveOut
    working_hours_active: LegacyWorkweekActiveOut
    working_policy_saved: SavedAvailabilityPolicyOut
    general_policy_saved: SavedAvailabilityPolicyOut
    personal_policy_saved: SavedAvailabilityPolicyOut
    # S2-V4 resolved family + May/Must/Prefer (Tesla wires placer against this).
    new_rule_assignment: ResolvedSchedulingOut | None = None
    dated_resolution: DatedResolutionOut
    duration: DurationEffectiveOut
