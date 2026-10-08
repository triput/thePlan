from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.tasks import TaskOut

class SearchLabelOut(BaseModel):
    id: UUID
    name: str
    color_hex: str


class SearchTaskOut(TaskOut):
    project_title: str | None = None
    labels: list[SearchLabelOut] = Field(default_factory=list)

