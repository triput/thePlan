"""Request and response models for temporary Time Map overrides (F4)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.hierarchy import TimeMapBandIn, TimeMapBandOut


class TimeMapOverrideCreate(BaseModel):
    local_start_date: date
    local_end_date: date
    timezone: str = Field(min_length=1, max_length=64)
    strict_mode: bool
    bands: list[TimeMapBandIn] = Field(default_factory=list)


class TimeMapOverrideUpdate(BaseModel):
    local_start_date: date | None = None
    local_end_date: date | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    strict_mode: bool | None = None
    bands: list[TimeMapBandIn] | None = None


class TimeMapOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    map_id: UUID
    local_start_date: date
    local_end_date: date
    timezone: str
    strict_mode: bool
    bands: list[TimeMapBandOut]
    created_at: datetime
    updated_at: datetime
