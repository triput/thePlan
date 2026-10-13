from datetime import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.enums import ScheduleStyle

from app.schemas.common import TimeField

class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timezone: str
    locale: str
    workday_minutes: int
    nominal_workday_minutes: int
    workday_start_local: time
    workweek_days: int
    inter_block_buffer_minutes: int
    ups_weights: dict[str, Any]
    upcoming_horizon_days: int
    default_estimated_duration_minutes: int
    default_min_block_duration_minutes: int
    default_max_block_duration_minutes: int
    default_max_block_unbounded: bool
    default_schedule_style: ScheduleStyle
    auto_defer_enabled: bool
    max_auto_schedule_minutes_per_project_per_day: int | None = None
    # Owner-scoped SoT for progress / remaining-only expected_revision (not board_revision).
    scheduling_revision: int

    @field_serializer("workday_start_local")
    def serialize_workday_start(self, value: time) -> str:
        return value.strftime("%H:%M")


class UserSettingsUpdate(BaseModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    locale: str | None = Field(default=None, min_length=1, max_length=16)
    workday_minutes: int | None = Field(default=None, gt=0)
    nominal_workday_minutes: int | None = Field(default=None, gt=0)
    workday_start_local: TimeField | None = None
    workweek_days: int | None = Field(default=None, ge=0, le=7)
    inter_block_buffer_minutes: int | None = Field(default=None, ge=0)
    ups_weights: dict[str, Any] | None = None
    upcoming_horizon_days: int | None = Field(default=None, ge=1)
    default_estimated_duration_minutes: int | None = Field(default=None, gt=0)
    default_min_block_duration_minutes: int | None = Field(default=None, gt=0)
    default_max_block_duration_minutes: int | None = Field(default=None, gt=0)
    default_max_block_unbounded: bool | None = None
    default_schedule_style: ScheduleStyle | None = None
    auto_defer_enabled: bool | None = None
    max_auto_schedule_minutes_per_project_per_day: int | None = Field(default=None, gt=0)
