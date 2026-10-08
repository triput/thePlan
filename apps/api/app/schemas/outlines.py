from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

class OutlineCreateEpicAction(BaseModel):
    type: Literal["create_epic"] = "create_epic"
    key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sort_order: int = 0


class OutlineCreateProjectAction(BaseModel):
    type: Literal["create_project"] = "create_project"
    key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sort_order: int = 0
    epic_key: str | None = Field(default=None, min_length=1, max_length=200)
    epic_id: UUID | None = None

    @model_validator(mode="after")
    def _epic_parent(self) -> "OutlineCreateProjectAction":
        if self.epic_key is None and self.epic_id is None:
            raise ValueError("create_project requires epic_key or epic_id")
        if self.epic_key is not None and self.epic_id is not None:
            raise ValueError("create_project accepts epic_key or epic_id, not both")
        return self


class OutlineCreateSectionAction(BaseModel):
    type: Literal["create_section"] = "create_section"
    key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sort_order: int = 0
    project_key: str | None = Field(default=None, min_length=1, max_length=200)
    project_id: UUID | None = None

    @model_validator(mode="after")
    def _project_parent(self) -> "OutlineCreateSectionAction":
        if self.project_key is None and self.project_id is None:
            raise ValueError("create_section requires project_key or project_id")
        if self.project_key is not None and self.project_id is not None:
            raise ValueError("create_section accepts project_key or project_id, not both")
        return self


class OutlineCreateTaskAction(BaseModel):
    type: Literal["create_task"] = "create_task"
    key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    sort_order: int = 0
    project_key: str | None = Field(default=None, min_length=1, max_length=200)
    project_id: UUID | None = None
    section_key: str | None = None
    section_id: UUID | None = None
    label_names: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    optional: bool = False
    outline_id: str | None = None

    @model_validator(mode="after")
    def _task_parents(self) -> "OutlineCreateTaskAction":
        if self.project_key is None and self.project_id is None:
            raise ValueError("create_task requires project_key or project_id")
        if self.project_key is not None and self.project_id is not None:
            raise ValueError("create_task accepts project_key or project_id, not both")
        if self.section_key is not None and self.section_id is not None:
            raise ValueError("create_task accepts section_key or section_id, not both")
        return self


OutlineAction = Annotated[
    OutlineCreateEpicAction
    | OutlineCreateProjectAction
    | OutlineCreateSectionAction
    | OutlineCreateTaskAction,
    Field(discriminator="type"),
]


class OutlineProposeSummary(BaseModel):
    epic_count: int = 0
    project_count: int = 0
    section_count: int = 0
    task_count: int = 0
    optional_skipped: int = 0


class OutlineAttachUnder(BaseModel):
    kind: Literal["epic", "project", "section"]
    id: UUID


class OutlineProposeRequest(BaseModel):
    template_id: str = "coursera_specialization"
    outline: dict[str, Any]
    skip_optional: bool = False
    attach_under: OutlineAttachUnder | None = None


class OutlineProposeResponse(BaseModel):
    actions: list[OutlineAction]
    template_id: str
    summary: OutlineProposeSummary


class OutlineApplyRequest(BaseModel):
    actions: list[OutlineAction] = Field(min_length=1)


class OutlineApplyResultItem(BaseModel):
    ok: bool
    action_type: str
    title: str | None = None
    key: str | None = None
    entity_id: UUID | None = None
    error: str | None = None
    created_labels: list[str] = Field(default_factory=list)


class OutlineApplyResponse(BaseModel):
    results: list[OutlineApplyResultItem]
