from datetime import date, time
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY, AvailabilityWindowOut
from app.schemas.hierarchy import TimeMapBandOut


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
    note: str | None = None


class DurationEffectiveOut(BaseModel):
    original_estimate_minutes: int
    worked_minutes: int
    remaining_minutes: int | None = None
    placement_effort_minutes: int
    min_block_duration_minutes: int | None = None
    max_block_duration_minutes: int | None = None
    max_block_unbounded: bool
    keep_in_one_block: bool
    note: str = (
        "placement_effort_minutes follows remaining estimate when set, else legacy "
        "estimated_duration_minutes. Pin-adjusted placement effort is not computed on this read."
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
    dated_resolution: DatedResolutionOut
    duration: DurationEffectiveOut
