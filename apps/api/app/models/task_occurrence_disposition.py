"""Durable occurrence miss dispositions (T2-S2 B-auto)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, _uuid

RESOLUTION_UNRESOLVED_HELD = "unresolved_held"
RESOLUTION_RELEASED = "released"
RESOLUTION_SKIPPED = "skipped"

EVENT_MISS_DETECTED = "miss_detected"
EVENT_LEAVE_HELD = "leave_held"
EVENT_DUPLICATE_MISS = "duplicate_miss"
EVENT_RELEASED = "released"
EVENT_SKIPPED = "skipped"


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

    events: Mapped[list["DispositionEvent"]] = relationship(
        "DispositionEvent",
        back_populates="disposition",
        cascade="all, delete-orphan",
        order_by="DispositionEvent.created_at",
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
