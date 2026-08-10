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


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    epic_id: UUID | None
    color_hex: str
    sort_order: int
    is_archived: bool


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    project_id: UUID | None = None
    section_id: UUID | None = None
    parent_task_id: UUID | None = None
    priority: TaskPriority = TaskPriority.p4
    due_at: datetime | None = None
    estimated_duration_minutes: int = 30
    label_ids: list[UUID] = Field(default_factory=list)


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


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color_hex: str = "#635F75"


class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color_hex: str


class PaginatedResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int
