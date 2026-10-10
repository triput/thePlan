# ==============================================================================
#  File: apps/api/app/schemas/schedule_preview.py
#  Description: Pydantic models for F6 schedule preview API responses and apply receipts.
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SchedulePreviewDiffCounts(BaseModel):
    blocks_added: int
    blocks_removed: int
    blocks_moved: int
    blocks_unchanged: int


class SchedulePreviewApplyReceipt(BaseModel):
    receipt_id: UUID
    preview_id: UUID
    schedule_run_id: UUID
    applied_at: datetime
    blocks_created: int
    tasks_scheduled: int
    overbooked_count: int
    scheduling_revision: int


class SchedulePreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    expires_at: datetime | None
    evaluated_at: datetime | None
    algorithm_version: str | None
    input_fingerprint: str | None
    scheduling_revision: int
    error_message: str | None
    stats_json: dict[str, Any] | None
    diff_counts: SchedulePreviewDiffCounts
    proposal: dict[str, Any] | None = Field(
        default=None,
        description="Immutable calculation output when status is ready, stale, or expired.",
    )
