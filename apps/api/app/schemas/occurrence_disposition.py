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

RECOVER_REVIEW_CONTRACT_VERSION = "t2-rec-ui-v1"


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


class _RecoverIntentBase(BaseModel):
    """Shared successor choice + catch-up fields (review and authorize)."""

    accept_past_ack: bool = False
    step_count: int | None = Field(default=None, ge=1)
    abort: bool = False
    catch_up_due_at: datetime | None = None
    catch_up_start_no_earlier_at: datetime | None = None
    catch_up_start_no_later_at: datetime | None = None
    catch_up_deadline_at: datetime | None = None
    catch_up_remaining_minutes: int | None = Field(default=None, ge=0)

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


class RecoverHeldReviewIn(_RecoverIntentBase):
    """True read-only recovery review (T2-REC-UI). Server issues authorize_instant."""

    disposition_id: UUID
    expected_revision: int


class RecoverHeldCadenceOut(BaseModel):
    is_fixed: bool
    timezone: str
    rrule_summary: str | None = None


class RecoverHeldEligibilityOut(BaseModel):
    recurring: bool
    one_off_use_release: bool


class RecoverHeldNextNormalOut(BaseModel):
    due_at: datetime | None = None
    start_no_earlier_at: datetime | None = None
    start_no_later_at: datetime | None = None
    deadline_at: datetime | None = None
    landing_is_past: bool = False
    accept_past_required: bool = False


class RecoverHeldEffortOut(BaseModel):
    worked_minutes: int
    remaining_minutes: int


class RecoverHeldCatchUpOut(BaseModel):
    remaining_minutes_default: int
    remaining_minutes: int
    due_at: datetime | None = None
    start_no_earlier_at: datetime | None = None
    start_no_later_at: datetime | None = None
    deadline_at: datetime | None = None
    usable_dates_ok: bool
    reject_code: str | None = None


class RecoverHeldHistoricalWorkOut(BaseModel):
    worked_minutes: int
    remaining_minutes: int | None = None
    estimated_duration_minutes: int
    ledger_retained_on_series: bool = True
    progress_entry_count: int


class RecoverHeldC2Out(BaseModel):
    blocks_prevent_next_normal: bool
    code: Literal["BLOCKS_PREVENT_NEXT_NORMAL"] | None = None
    detail: str | None = None


class RecoverHeldSuccessorChoiceOut(BaseModel):
    status: str
    accept_past_applied_if_authorized: bool = False


class RecoverHeldReviewOut(BaseModel):
    disposition_id: UUID
    task_id: UUID
    episode_key: str
    expected_revision: int
    authorize_instant: datetime
    review_binding: str
    contract_version: str = RECOVER_REVIEW_CONTRACT_VERSION
    cadence: RecoverHeldCadenceOut
    eligibility: RecoverHeldEligibilityOut
    next_normal: RecoverHeldNextNormalOut
    next_normal_effort: RecoverHeldEffortOut
    catch_up: RecoverHeldCatchUpOut
    historical_work: RecoverHeldHistoricalWorkOut
    c2: RecoverHeldC2Out
    successor_choice: RecoverHeldSuccessorChoiceOut
    review_ok_for_authorize: bool


class RecoverHeldIn(_RecoverIntentBase):
    """Authorize reviewed recovery for a named held recurring miss (T2-REC + binding)."""

    disposition_id: UUID
    expected_revision: int
    review_binding: str = Field(min_length=1)
    # Optional echo of the server-issued review instant; if set must match binding.
    authorize_instant: datetime | None = None
    note: str | None = None


class RecoverHeldOut(HeldDispositionOut):
    catch_up_task_id: UUID
