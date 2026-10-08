from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.models.enums import ScheduleStyle, TimeMapBandTier

from app.schemas.common import TimeField
from app.schemas.tasks import TaskOut

class EpicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    color_hex: str = "#6D3FC9"
    start_date: date | None = None
    target_date: date | None = None
    preferred_time_window_id: UUID | None = None
    schedule_style: ScheduleStyle | None = None


class EpicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    color_hex: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    sort_order: int | None = None
    is_archived: bool | None = None
    preferred_time_window_id: UUID | None = None
    schedule_style: ScheduleStyle | None = None


class EpicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    color_hex: str
    start_date: date | None
    target_date: date | None
    sort_order: int
    is_archived: bool
    preferred_time_window_id: UUID | None
    schedule_style: ScheduleStyle | None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    epic_id: UUID | None = None
    color_hex: str = "#0A8558"
    preferred_time_window_id: UUID | None = None
    schedule_style: ScheduleStyle | None = None


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    epic_id: UUID | None = None
    color_hex: str | None = None
    sort_order: int | None = None
    is_archived: bool | None = None
    preferred_time_window_id: UUID | None = None
    schedule_style: ScheduleStyle | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    epic_id: UUID | None
    color_hex: str
    sort_order: int
    is_archived: bool
    preferred_time_window_id: UUID | None
    schedule_style: ScheduleStyle | None

class ProjectPromoteToEpicOut(BaseModel):
    """DEF-023: project kept as sole child under a new epic cloned from its meta."""

    epic: EpicOut
    project: ProjectOut


class EpicDemoteToProjectBody(BaseModel):
    """Optional parent for the new project shell after demoting an epic."""

    target_epic_id: UUID | None = None


class EpicDemoteToProjectOut(BaseModel):
    """DEF-023: epic folded into a project; former child projects orphaned."""

    project: ProjectOut
    orphaned_project_ids: list[UUID]


class TaskPromoteToProjectBody(BaseModel):
    include_descendants: bool = True
    epic_id: UUID | None = None


class SectionCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=255)
    sort_order: int = 0


class SectionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = None


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    sort_order: int

class TimeMapBandIn(BaseModel):
    tier: TimeMapBandTier
    start_time: TimeField
    end_time: TimeField
    days_of_week: int = Field(default=127, ge=1, le=127)
    sort_order: int = 0


class TimeMapBandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tier: TimeMapBandTier
    start_time: time
    end_time: time
    days_of_week: int
    sort_order: int

    @field_serializer("start_time", "end_time")
    def serialize_time(self, value: time) -> str:
        return value.strftime("%H:%M")


class FocusWindowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    strict_mode: bool = False
    bands: list[TimeMapBandIn] | None = None
    # Legacy optional fields — synthesize one green band when bands is omitted.
    start_time: TimeField | None = None
    end_time: TimeField | None = None
    days_of_week: int | None = Field(default=None, ge=1, le=127)
    is_hard: bool | None = None


class FocusWindowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    strict_mode: bool | None = None
    bands: list[TimeMapBandIn] | None = None
    # Legacy optional fields for partial band updates via single green band.
    start_time: TimeField | None = None
    end_time: TimeField | None = None
    days_of_week: int | None = Field(default=None, ge=1, le=127)
    is_hard: bool | None = None


class FocusWindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    strict_mode: bool
    bands: list[TimeMapBandOut]
    created_at: datetime
    updated_at: datetime


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    soft_target_at: datetime | None = None


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    soft_target_at: datetime | None = None


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    soft_target_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskPromoteToProjectOut(BaseModel):
    """DEF-023: task (+ optional subtree) moved into a new project."""

    project: ProjectOut
    task: TaskOut
