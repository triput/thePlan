from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
