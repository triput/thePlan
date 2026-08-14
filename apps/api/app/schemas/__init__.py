from datetime import date, datetime, time
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
    model_validator,
)

from app.models.enums import CalendarSubscriptionRole, ReminderChannel, ScheduleStatus, ScheduleStyle, TaskPriority, TimeMapBandTier


def _parse_time_value(value: object) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        parts = value.strip().split(":")
        if len(parts) == 2:
            hour, minute = int(parts[0]), int(parts[1])
            return time(hour, minute)
        if len(parts) == 3:
            hour, minute, second = int(parts[0]), int(parts[1]), int(parts[2])
            return time(hour, minute, second)
    raise ValueError("Invalid time; use HH:MM or HH:MM:SS")


TimeField = Annotated[time, BeforeValidator(_parse_time_value)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None
    email: str
    display_name: str | None
    is_admin: bool = False
    must_change_password: bool = False


class AuthRegisterBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)


class AuthLoginBody(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AuthMeUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=12, max_length=128)
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "AuthMeUpdate":
        if self.password is None and self.email is None and self.display_name is None:
            raise ValueError("At least one field is required")
        return self


class AuthUserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None
    email: str
    display_name: str | None
    is_admin: bool
    is_disabled: bool
    must_change_password: bool = False


class AuthUserAdminCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)
    is_admin: bool = False


class AuthUserAdminUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_disabled: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=128)
    must_change_password: bool | None = None


class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timezone: str
    locale: str
    workday_minutes: int
    workday_start_local: time
    workweek_days: int
    inter_block_buffer_minutes: int
    ups_weights: dict[str, Any]
    upcoming_horizon_days: int
    default_estimated_duration_minutes: int
    default_min_block_duration_minutes: int
    default_schedule_style: ScheduleStyle
    auto_defer_enabled: bool

    @field_serializer("workday_start_local")
    def serialize_workday_start(self, value: time) -> str:
        return value.strftime("%H:%M")


class UserSettingsUpdate(BaseModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    locale: str | None = Field(default=None, min_length=1, max_length=16)
    workday_minutes: int | None = Field(default=None, gt=0)
    workday_start_local: TimeField | None = None
    workweek_days: int | None = Field(default=None, ge=1, le=7)
    inter_block_buffer_minutes: int | None = Field(default=None, ge=0)
    ups_weights: dict[str, Any] | None = None
    upcoming_horizon_days: int | None = Field(default=None, ge=1)
    default_estimated_duration_minutes: int | None = Field(default=None, gt=0)
    default_min_block_duration_minutes: int | None = Field(default=None, gt=0)
    default_schedule_style: ScheduleStyle | None = None
    auto_defer_enabled: bool | None = None


class EpicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    color_hex: str = "#6D3FC9"
    start_date: date | None = None
    target_date: date | None = None


class EpicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    color_hex: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    sort_order: int | None = None
    is_archived: bool | None = None


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


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    epic_id: UUID | None = None
    color_hex: str = "#0A8558"


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    epic_id: UUID | None = None
    color_hex: str | None = None
    sort_order: int | None = None
    is_archived: bool | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    epic_id: UUID | None
    color_hex: str
    sort_order: int
    is_archived: bool


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


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    project_id: UUID | None = None
    section_id: UUID | None = None
    parent_task_id: UUID | None = None
    priority: TaskPriority = TaskPriority.p4
    due_at: datetime | None = None
    deadline_at: datetime | None = None
    soft_target_at: datetime | None = None
    # Omit or null to use user_settings.default_estimated_duration_minutes; explicit value wins.
    estimated_duration_minutes: int | None = None
    preferred_time_window_id: UUID | None = None
    plan_id: UUID | None = None
    schedule_style: ScheduleStyle | None = None
    label_ids: list[UUID] = Field(default_factory=list)
    recurrence: "RecurrenceUpsert | None" = None


class RecurrenceOut(BaseModel):
    rrule: str
    is_fixed: bool
    timezone: str
    starts_on: date | None = None
    ends_on: date | None = None
    display: str


class RecurrenceUpsert(BaseModel):
    rrule: str | None = None
    is_fixed: bool = False
    timezone: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    text: str | None = Field(default=None, min_length=1, max_length=255)


class ReminderCreate(BaseModel):
    fire_at: datetime
    channel: ReminderChannel = ReminderChannel.in_app


class ReminderUpdate(BaseModel):
    fire_at: datetime | None = None
    channel: ReminderChannel | None = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    fire_at: datetime
    channel: ReminderChannel
    is_fired: bool
    created_at: datetime


class ReminderDueOut(ReminderOut):
    task_title: str


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    project_id: UUID | None = None
    section_id: UUID | None = None
    parent_task_id: UUID | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    deadline_at: datetime | None = None
    soft_target_at: datetime | None = None
    estimated_duration_minutes: int | None = None
    preferred_time_window_id: UUID | None = None
    plan_id: UUID | None = None
    schedule_style: ScheduleStyle | None = None
    sort_order: int | None = None
    label_ids: list[UUID] | None = None


class TaskCompleteBody(BaseModel):
    # None = unspecified (409 OPEN_CHILDREN when open kids exist).
    # False = complete parent only; True = bulk-complete descendants.
    # force_parent_only remains supported for the current web client.
    bulk_children: bool | None = None
    force_parent_only: bool = False


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    project_id: UUID | None
    section_id: UUID | None
    parent_task_id: UUID | None
    nesting_level: int
    priority: TaskPriority
    due_at: datetime | None
    deadline_at: datetime | None
    soft_target_at: datetime | None
    estimated_duration_minutes: int
    preferred_time_window_id: UUID | None = None
    plan_id: UUID | None = None
    plan_name: str | None = None
    schedule_style: ScheduleStyle | None = None
    is_completed: bool
    completed_at: datetime | None
    status: ScheduleStatus
    sort_order: int
    label_ids: list[UUID] = Field(default_factory=list)
    open_subtask_count: int = 0
    recurrence: RecurrenceOut | None = None
    recurrence_advanced: bool = False
    previous_due_at: datetime | None = None


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color_hex: str = "#635F75"


class LabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color_hex: str | None = None


class LabelDeleteBody(BaseModel):
    reassign_to: list[UUID] = Field(default_factory=list)


class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color_hex: str
    task_count: int = 0


class LabelBatchCreateItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color_hex: str = "#635F75"


class LabelBatchCreate(BaseModel):
    labels: list[LabelBatchCreateItem] = Field(min_length=1)


class LabelBatchSkipped(BaseModel):
    name: str
    reason: str


class LabelBatchCreateResponse(BaseModel):
    items: list[LabelOut]
    skipped: list[LabelBatchSkipped] = Field(default_factory=list)


class QuickAddParseRequest(BaseModel):
    text: str = Field(min_length=1)


class QuickAddParseResponse(BaseModel):
    title: str
    priority: TaskPriority | None = None
    estimated_duration_minutes: int | None = None
    due_at: datetime | None = None
    epic_id: UUID | None = None
    project_id: UUID | None = None
    section_id: UUID | None = None
    preferred_time_window_id: UUID | None = None
    unresolved: list[str] = Field(default_factory=list)
    recurrence: RecurrenceOut | None = None


class ReorderItem(BaseModel):
    id: UUID
    sort_order: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(default_factory=list)


class ScheduledBlockCreate(BaseModel):
    task_id: UUID
    start_time: datetime
    end_time: datetime
    is_pinned: bool = False


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


class SearchLabelOut(BaseModel):
    id: UUID
    name: str
    color_hex: str


class SearchTaskOut(TaskOut):
    project_title: str | None = None
    labels: list[SearchLabelOut] = Field(default_factory=list)


class PaginatedResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int
