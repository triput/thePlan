from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

DispositionResolution = Literal["unresolved_held", "released", "skipped"]
DispositionEventType = Literal[
    "miss_detected",
    "leave_held",
    "duplicate_miss",
    "released",
    "skipped",
]


class DispositionEventOut(BaseModel):
    id: UUID
    event_type: DispositionEventType
    payload: dict[str, Any] | None = None
    preview_id: UUID | None = None
    created_at: datetime


class HeldDispositionOut(BaseModel):
    id: UUID
    task_id: UUID
    episode_key: str
    resolution: DispositionResolution
    bounds_snapshot: dict[str, Any]
    miss_reason_code: str | None = None
    miss_reason_params: dict[str, Any] | None = None
    updated_at: datetime
    events: list[DispositionEventOut] = Field(default_factory=list)


class LeaveHeldIn(BaseModel):
    expected_revision: int
    note: str | None = None


class ReleaseHeldIn(BaseModel):
    disposition_id: UUID
    expected_revision: int
    note: str | None = None
    start_no_earlier_at: datetime | None = None
    start_no_later_at: datetime | None = None
    deadline_at: datetime | None = None


class SkipHeldIn(BaseModel):
    disposition_id: UUID
    expected_revision: int
    note: str | None = None
