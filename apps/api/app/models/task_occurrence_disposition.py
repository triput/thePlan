"""Durable occurrence miss dispositions (T2-S2 B-auto + T2-REC recovery)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, _uuid

RESOLUTION_UNRESOLVED_HELD = "unresolved_held"
RESOLUTION_RELEASED = "released"
RESOLUTION_SKIPPED = "skipped"
RESOLUTION_RECOVERED = "recovered"

EVENT_MISS_DETECTED = "miss_detected"
EVENT_LEAVE_HELD = "leave_held"
EVENT_DUPLICATE_MISS = "duplicate_miss"
EVENT_RELEASED = "released"
EVENT_SKIPPED = "skipped"
EVENT_RECOVERED = "recovered"


class TaskOccurrenceDisposition(Base, TimestampMixin):
    __tablename__ = "task_occurrence_dispositions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "task_id",
            "episode_key",
            name="uq_task_occurrence_dispositions_episode",
        ),
        Index("idx_task_occurrence_dispositions_owner_resolution", "owner_id", "resolution"),
        CheckConstraint(
            "catch_up_task_id IS NULL OR catch_up_task_id <> task_id",
            name="task_occurrence_dispositions_catch_up_ne_task",
        ),
        CheckConstraint(
            "resolution <> 'recovered' OR ("
            "catch_up_task_id IS NOT NULL AND "
            "miss_era_worked_minutes IS NOT NULL AND "
            "miss_era_estimated_minutes IS NOT NULL AND "
            "miss_era_entry_ids IS NOT NULL"
            ")",
            name="task_occurrence_dispositions_recovered_implies_snapshot",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    episode_key: Mapped[str] = mapped_column(String(128), nullable=False)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False)
    bounds_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    miss_reason_code: Mapped[str | None] = mapped_column(String(64))
    miss_reason_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Recovery authorize snapshot (nullable until authorize; then immutable).
    catch_up_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT")
    )
    miss_era_worked_minutes: Mapped[int | None] = mapped_column(Integer)
    # NULL stays NULL — distinguish unset from 0.
    miss_era_remaining_minutes: Mapped[int | None] = mapped_column(Integer)
    miss_era_estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    miss_era_entry_ids: Mapped[list[Any] | None] = mapped_column(JSONB)
    authorize_instant: Mapped[datetime | None] = mapped_column()

    events: Mapped[list["DispositionEvent"]] = relationship(
        "DispositionEvent",
        back_populates="disposition",
        cascade="all, delete-orphan",
        order_by="DispositionEvent.created_at",
    )
    epoch_memberships: Mapped[list["ProgressEpochMembership"]] = relationship(
        "ProgressEpochMembership",
        back_populates="disposition",
        cascade="all, delete-orphan",
    )
    correction_audits: Mapped[list["DispositionCorrectionAudit"]] = relationship(
        "DispositionCorrectionAudit",
        back_populates="disposition",
        cascade="all, delete-orphan",
        order_by="DispositionCorrectionAudit.created_at",
    )


class DispositionEvent(Base):
    __tablename__ = "disposition_events"
    __table_args__ = (Index("idx_disposition_events_disposition", "disposition_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    disposition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_occurrence_dispositions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    preview_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schedule_previews.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    disposition: Mapped[TaskOccurrenceDisposition] = relationship(
        "TaskOccurrenceDisposition", back_populates="events"
    )


class ProgressEpochMembership(Base):
    """Closed miss-era epoch assignment for a progress ledger row (T2-REC)."""

    __tablename__ = "progress_epoch_membership"
    __table_args__ = (
        ForeignKeyConstraint(
            ["progress_entry_id", "task_id", "owner_id"],
            [
                "task_progress_entries.id",
                "task_progress_entries.task_id",
                "task_progress_entries.owner_id",
            ],
            name="fk_progress_epoch_membership_entry_task_owner",
            ondelete="CASCADE",
        ),
        Index("idx_progress_epoch_membership_disposition", "disposition_id"),
    )

    progress_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    disposition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_occurrence_dispositions.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    disposition: Mapped[TaskOccurrenceDisposition] = relationship(
        "TaskOccurrenceDisposition", back_populates="epoch_memberships"
    )


class DispositionCorrectionAudit(Base):
    """Append-only historical correction audit onto a closed miss-era epoch."""

    __tablename__ = "disposition_correction_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    disposition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_occurrence_dispositions.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_progress_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    new_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_progress_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    disposition: Mapped[TaskOccurrenceDisposition] = relationship(
        "TaskOccurrenceDisposition", back_populates="correction_audits"
    )
