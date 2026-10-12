from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskProgressEntryCreate(BaseModel):
    idempotency_key: UUID
    minutes_worked: int = Field(gt=0)
    remaining_minutes: int = Field(ge=0)
    expected_revision: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=2000)


class TaskProgressEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    idempotency_key: UUID
    minutes_worked: int
    remaining_minutes: int
    note: str | None
    created_at: datetime


class TaskProgressApplyResult(BaseModel):
    entry: TaskProgressEntryOut
    original_estimate_minutes: int
    time_worked_minutes: int
    remaining_estimate_minutes: int
    scheduling_revision: int
    replayed: bool = False
