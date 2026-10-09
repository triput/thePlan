from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    ReminderChannel,
    ScheduleStatus,
    ScheduleStyle,
    TaskBoardColumn,
    TaskPriority,
    TaskWorkflowState,
)

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


class TaskWorkflowTransition(BaseModel):
    column: TaskBoardColumn
    expected_revision: int = Field(ge=0)
    waiting_note: str | None = Field(default=None, max_length=500)
    board_rank: int | None = None
    insert_before_id: UUID | None = None
    insert_after_id: UUID | None = None
    bulk_children: bool | None = None
    force_parent_only: bool = False


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
    source_refs: list[dict[str, Any]] | None = None
    is_completed: bool
    completed_at: datetime | None
    deleted_at: datetime | None = None
    status: ScheduleStatus
    sort_order: int
    workflow_state: TaskWorkflowState
    board_column: TaskBoardColumn
    waiting_note: str | None = None
    board_rank: int
    board_revision: int
    label_ids: list[UUID] = Field(default_factory=list)
    open_subtask_count: int = 0
    recurrence: RecurrenceOut | None = None
    recurrence_advanced: bool = False
    previous_due_at: datetime | None = None


class TaskBatchUpdate(BaseModel):
    """Apply the same partial patch (and/or attach labels) to many owned tasks."""

    task_ids: list[UUID] = Field(min_length=1, max_length=500)
    patch: TaskUpdate = Field(default_factory=TaskUpdate)
    add_label_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def require_patch_or_labels(self) -> "TaskBatchUpdate":
        if not self.patch.model_dump(exclude_unset=True) and not self.add_label_ids:
            raise ValueError("Provide patch fields and/or add_label_ids")
        return self


class TaskBatchUpdateResponse(BaseModel):
    items: list[TaskOut]
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
