from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import TaskPriority

class AssistCreateTaskAction(BaseModel):
    type: Literal["create_task"] = "create_task"
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    project_name: str | None = None
    section_name: str | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    label_names: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


class AssistCreateProjectAction(BaseModel):
    type: Literal["create_project"] = "create_project"
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    epic_name: str | None = None
    epic_id: UUID | None = None
    color_hex: str | None = None

    @model_validator(mode="after")
    def epic_ref_exclusive(self) -> "AssistCreateProjectAction":
        if self.epic_name and self.epic_id is not None:
            raise ValueError("create_project accepts epic_name or epic_id, not both")
        return self


AssistAction = Annotated[
    AssistCreateTaskAction | AssistCreateProjectAction,
    Field(discriminator="type"),
]


class AssistProposeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class AssistProposeResponse(BaseModel):
    actions: list[AssistAction]
    model: str


class AssistApplyRequest(BaseModel):
    actions: list[AssistAction] = Field(min_length=1)


class AssistApplyResultItem(BaseModel):
    ok: bool
    action_type: str
    title: str | None = None
    task_id: UUID | None = None
    project_id: UUID | None = None
    error: str | None = None
    created_labels: list[str] = Field(default_factory=list)


class AssistApplyResponse(BaseModel):
    results: list[AssistApplyResultItem]


class AssistStatusOut(BaseModel):
    reachable: bool
    base_url: str
    model: str
    detail: str | None = None
    enabled: bool = True
