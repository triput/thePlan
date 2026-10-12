from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.enums import AvailabilityPolicySlug
from app.schemas.common import TimeField

SCHEDULING_CONFIG_ONLY_COPY = (
    "Saved for upcoming scheduling; current runs still use working hours / Time Maps."
)


class AvailabilityWindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    weekday: int
    start_time: time
    end_time: time
    ends_next_day: bool
    duration_minutes: int
    sort_order: int

    @field_serializer("start_time", "end_time")
    def serialize_time(self, value: time) -> str:
        return value.strftime("%H:%M")


class AvailabilityWindowIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: TimeField
    duration_minutes: int = Field(gt=0)
    sort_order: int = 0


class AvailabilityPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: AvailabilityPolicySlug
    name: str
    sort_order: int
    scheduling_effective: bool = False
    scheduling_effective_note: str = SCHEDULING_CONFIG_ONLY_COPY
    windows: list[AvailabilityWindowOut] = Field(default_factory=list)


class AvailabilityPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    windows: list[AvailabilityWindowIn] | None = None


class AvailabilityPolicyEffectiveOut(BaseModel):
    policy_id: UUID
    slug: AvailabilityPolicySlug
    on_date: date
    scheduling_effective: bool = False
    scheduling_effective_note: str = SCHEDULING_CONFIG_ONLY_COPY
    windows: list[AvailabilityWindowOut]
    provenance: list[str]
