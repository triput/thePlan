import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import _uuid

# One in-flight replan per owner. Non-running rows stay out of the index.
ONE_RUNNING_PER_OWNER_INDEX = "uq_schedule_runs_one_running_per_owner"


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        Index("idx_schedule_runs_owner", "owner_id", desc("started_at")),
        Index(
            ONE_RUNNING_PER_OWNER_INDEX,
            "owner_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="running")
    tasks_scheduled: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    blocks_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    overbooked_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    stats_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ScheduleTaskOutcome(Base):
    """Per-task scheduling result for one schedule run (F3 explanations).

    Jules writes reason facts from apply. Tesla stamps provenance via
    ``app.scheduler.outcomes.persist_calculation_outcomes`` (fingerprint,
    snapshot, algorithm version). Reads compare the snapshot and never replan.
    """

    __tablename__ = "schedule_task_outcomes"
    __table_args__ = (
        Index("idx_schedule_task_outcomes_run", "schedule_run_id"),
        Index("idx_schedule_task_outcomes_task", "owner_id", "task_id", desc("created_at")),
        Index(
            "idx_schedule_task_outcomes_latest",
            "owner_id",
            "task_id",
            desc("evaluated_at"),
        ),
        UniqueConstraint(
            "schedule_run_id",
            "task_id",
            name="uq_schedule_task_outcomes_run_task",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    schedule_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedule_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    requested_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    pinned_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    placed_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    remaining_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    primary_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_facts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Calculation time. Distinct from created_at so a later edit of the row
    # does not pretend the schedule was recomputed.
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Family label (placed, unplaced, excluded, blocked, recorded). Nullable so
    # direct inserts that only set primary_reason_code still land; reads derive it.
    outcome: Mapped[str | None] = mapped_column(String(32))
    placement_facts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    algorithm_version: Mapped[str | None] = mapped_column(String(64))


class SchedulePreview(Base):
    """Owner-scoped replan preview (F6). Never writes live blocks or task status."""

    __tablename__ = "schedule_previews"
    __table_args__ = (Index("idx_schedule_previews_owner", "owner_id", desc("started_at")),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column()
    expires_at: Mapped[datetime | None] = mapped_column()
    evaluated_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="running")
    algorithm_version: Mapped[str | None] = mapped_column(String(64))
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scheduling_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    proposal_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    stats_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
