from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DispositionEventOut(BaseModel):
    id: UUID
    event_type: str
    payload: dict[str, Any] | None = None
    preview_id: UUID | None = None
    created_at: datetime


class HeldDispositionOut(BaseModel):
    id: UUID
    task_id: UUID
    episode_key: str
    resolution: str
    bounds_snapshot: dict[str, Any]
    miss_reason_code: str | None = None
    miss_reason_params: dict[str, Any] | None = None
    updated_at: datetime
    events: list[DispositionEventOut] = Field(default_factory=list)


class LeaveHeldIn(BaseModel):
    expected_revision: int
    note: str | None = None
