from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ScheduleStatus, TaskPriority


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None


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
    estimated_duration_minutes: int = 30
    label_ids: list[UUID] = Field(default_factory=list)


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
    is_completed: bool
    completed_at: datetime | None
    status: ScheduleStatus
    sort_order: int
    label_ids: list[UUID] = Field(default_factory=list)
    open_subtask_count: int = 0


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color_hex: str = "#635F75"


class LabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color_hex: str | None = None


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
