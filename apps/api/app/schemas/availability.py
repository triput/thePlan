from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.common import TimeField
from app.services.availability_slug import (
    RESERVED_AVAILABILITY_POLICY_SLUGS,
    normalize_custom_policy_slug,
)

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


class AvailabilityPolicyCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    windows: list[AvailabilityWindowIn] = Field(min_length=1)
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("slug")
    @classmethod
    def validate_create_slug(cls, value: str) -> str:
        slug = normalize_custom_policy_slug(value)
        if slug in RESERVED_AVAILABILITY_POLICY_SLUGS:
            raise ValueError(
                "Reserved slug; patch the default General, Working, or Personal policy instead"
            )
        return slug

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped


class AvailabilityPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
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
    slug: str
    on_date: date
    scheduling_effective: bool = False
    scheduling_effective_note: str = SCHEDULING_CONFIG_ONLY_COPY
    windows: list[AvailabilityWindowOut]
    provenance: list[str]
