from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import CalendarSubscriptionRole

class ScheduledBlockCreate(BaseModel):
    task_id: UUID
    start_time: datetime
    end_time: datetime
    is_pinned: bool = False


class ScheduledBlockBundleCreate(BaseModel):
    """Manual calendar bundle (ADR-012). Duration = sum of member estimates when end omitted."""

    start_time: datetime
    end_time: datetime | None = None
    is_pinned: bool = False
    member_task_ids: list[UUID] | None = None
    parent_task_id: UUID | None = None

    @model_validator(mode="after")
    def _require_source(self) -> "ScheduledBlockBundleCreate":
        if self.parent_task_id is not None and self.member_task_ids:
            raise ValueError("Provide either parent_task_id or member_task_ids, not both")
        if self.parent_task_id is None and not self.member_task_ids:
            raise ValueError("Provide parent_task_id or member_task_ids")
        return self


class BundleMetaOut(BaseModel):
    kind: Literal["bundle"] = "bundle"
    member_task_ids: list[UUID]
    source: Literal["selection", "parent_subtree"]


class ScheduledBlockUpdate(BaseModel):
    task_id: UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_pinned: bool | None = None


class ScheduledBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    start_time: datetime
    end_time: datetime
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
    bundle_meta: BundleMetaOut | None = None
    bundle_inactive: bool = False


class ReleaseRemainderBody(BaseModel):
    at: datetime | None = None


class ReleaseRemainderOut(BaseModel):
    block: ScheduledBlockOut | None = None
    deleted: bool = False


class ClearUnpinnedBlocksBody(BaseModel):
    start: datetime
    end: datetime


class ClearUnpinnedBlocksOut(BaseModel):
    deleted_count: int


class ScheduleRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    tasks_scheduled: int
    blocks_created: int
    overbooked_count: int
    error_message: str | None
    stats_json: dict[str, Any] | None


class CalendarAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    account_email: str | None
    is_enabled: bool
    mirror_blocks: bool
    sync_cursor: str | None
    last_synced_at: datetime | None
    token_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CalendarAccountUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mirror_blocks: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("mirror_blocks", "mirror_blocks_to_google"),
    )
    is_enabled: bool | None = None


class GoogleCalendarListItem(BaseModel):
    id: str
    summary: str | None = None
    primary: bool = False
    access_role: str | None = None


class CalendarSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    calendar_account_id: UUID
    external_calendar_id: str
    summary: str | None
    role: CalendarSubscriptionRole
    is_enabled: bool
    sync_cursor: str | None = None


class CalendarSubscriptionPutItem(BaseModel):
    external_calendar_id: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=255)
    role: CalendarSubscriptionRole
    is_enabled: bool = True


class CalendarSubscriptionsPut(BaseModel):
    items: list[CalendarSubscriptionPutItem] = Field(min_length=1)


class ExternalCalendarEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    calendar_account_id: UUID
    provider: str
    external_event_id: str
    calendar_id: str
    title: str | None
    start_time: datetime
    end_time: datetime
    is_all_day: bool
    last_synced_at: datetime


class CalendarSyncResult(BaseModel):
    account_id: UUID
    upserted: int


class CalendarConflictOut(BaseModel):
    kind: Literal["block_busy", "block_block"]
    block_id: UUID
    other_block_id: UUID | None = None
    external_event_id: UUID | None = None
    external_title: str | None = None
    start_time: datetime
    end_time: datetime
    is_pinned: bool


class CalendarConflictsResult(BaseModel):
    items: list[CalendarConflictOut]
    count: int

