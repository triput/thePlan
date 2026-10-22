from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

DispositionResolution = Literal["unresolved_held", "released", "skipped", "recovered"]
DispositionEventType = Literal[
    "miss_detected",
    "leave_held",
    "duplicate_miss",
    "released",
    "skipped",
    "recovered",
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
    catch_up_task_id: UUID | None = None


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


class RecoverHeldIn(BaseModel):
    """Authorize reviewed recovery for a named held recurring miss (T2-REC)."""

    disposition_id: UUID
    expected_revision: int
    authorize_instant: datetime
    # Successor choice (fixed past landing): exactly one when a choice is required.
    accept_past_ack: bool = False
    step_count: int | None = Field(default=None, ge=1)
    abort: bool = False
    # Catch-up usable dates (full release gate; never accept-past).
    catch_up_due_at: datetime | None = None
    catch_up_start_no_earlier_at: datetime | None = None
    catch_up_start_no_later_at: datetime | None = None
    catch_up_deadline_at: datetime | None = None
    # Optional override of catch-up remaining default (last confirmed remaining).
    catch_up_remaining_minutes: int | None = Field(default=None, ge=0)
    note: str | None = None

    @model_validator(mode="after")
    def _successor_choice_exclusive(self) -> Self:
        chosen = sum(
            [
                bool(self.accept_past_ack),
                self.step_count is not None,
                bool(self.abort),
            ]
        )
        if chosen > 1:
            raise ValueError(
                "Specify at most one of accept_past_ack, step_count, or abort"
            )
        return self


class RecoverHeldOut(HeldDispositionOut):
    catch_up_task_id: UUID
