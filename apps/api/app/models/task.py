import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import (
    ReminderChannel,
    ScheduleStatus,
    ScheduleStyle,
    TaskPriority,
    TaskWorkflowState,
)
from app.models.mixins import TimestampMixin, _uuid


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("nesting_level BETWEEN 0 AND 2", name="tasks_nesting_level_check"),
        CheckConstraint(
            "section_id IS NULL OR project_id IS NOT NULL",
            name="task_section_project_consistency",
        ),
        Index("idx_tasks_owner", "owner_id"),
        Index("idx_tasks_project", "project_id"),
        Index("idx_tasks_section", "section_id"),
        Index("idx_tasks_parent", "parent_task_id"),
        Index("idx_tasks_nesting", "nesting_level"),
        Index("idx_tasks_owner_due_at", "owner_id", "due_at"),
        Index("idx_tasks_owner_deadline_at", "owner_id", "deadline_at"),
        Index("idx_tasks_owner_is_completed", "owner_id", "is_completed"),
        Index("idx_tasks_owner_project_sort", "owner_id", "project_id", "sort_order"),
        Index("idx_tasks_owner_plan", "owner_id", "plan_id"),
        Index("idx_tasks_owner_workflow", "owner_id", "workflow_state"),
        Index("idx_tasks_owner_board_rank", "owner_id", "board_rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id", ondelete="SET NULL")
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(TaskPriority, name="task_priority", native_enum=True), nullable=False, server_default="p4"
    )
    nesting_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    min_block_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    max_block_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="120")
    due_at: Mapped[datetime | None] = mapped_column()
    deadline_at: Mapped[datetime | None] = mapped_column()
    soft_target_at: Mapped[datetime | None] = mapped_column()
    preferred_time_window_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("focus_windows.id", ondelete="SET NULL")
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL")
    )
    schedule_style: Mapped[ScheduleStyle | None] = mapped_column(
        SAEnum(ScheduleStyle, name="schedule_style", native_enum=True),
        nullable=True,
    )
    source_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        SAEnum(ScheduleStatus, name="schedule_status", native_enum=True),
        nullable=False,
        server_default="unscheduled",
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    completed_at: Mapped[datetime | None] = mapped_column()
    deleted_at: Mapped[datetime | None] = mapped_column()
    workflow_state: Mapped[TaskWorkflowState] = mapped_column(
        SAEnum(TaskWorkflowState, name="task_workflow_state", native_enum=True),
        nullable=False,
        server_default="ready",
    )
    waiting_note: Mapped[str | None] = mapped_column(Text)
    board_rank: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    board_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    project: Mapped["Project | None"] = relationship(back_populates="tasks")
    section: Mapped["Section | None"] = relationship(back_populates="tasks")
    label_links: Mapped[list["TaskLabel"]] = relationship(back_populates="task")
    scheduled_blocks: Mapped[list["ScheduledBlock"]] = relationship(back_populates="task")
    recurrence_rule: Mapped["RecurrenceRule | None"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("blocking_task_id", "dependent_task_id", name="unique_dependency"),
        CheckConstraint("blocking_task_id <> dependent_task_id", name="no_self_dependency"),
        Index("idx_task_dependencies_blocking", "blocking_task_id"),
        Index("idx_task_dependencies_dependent", "dependent_task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blocking_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    dependent_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ScheduledBlock(Base, TimestampMixin):
    __tablename__ = "scheduled_blocks"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="scheduled_block_time_order"),
        Index("idx_scheduled_blocks_task", "task_id"),
        Index("idx_scheduled_blocks_owner", "owner_id"),
        Index("idx_scheduled_blocks_time", "start_time", "end_time"),
        Index("idx_scheduled_blocks_owner_time", "owner_id", "start_time", "end_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # ADR-012 / DEF-019: nullable JSONB aggregate membership; null = ordinary block.
    bundle_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="scheduled_blocks")


class RecurrenceRule(Base, TimestampMixin):
    __tablename__ = "recurrence_rules"
    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on",
            name="recurrence_rules_frame_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    rrule: Mapped[str] = mapped_column(Text, nullable=False)
    is_fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)

    task: Mapped["Task"] = relationship(back_populates="recurrence_rule")


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"
    __table_args__ = (
        Index("idx_reminders_task", "task_id"),
        Index(
            "idx_reminders_fire_at",
            "owner_id",
            "fire_at",
            postgresql_where=text("is_fired = FALSE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    fire_at: Mapped[datetime] = mapped_column(nullable=False)
    channel: Mapped[ReminderChannel] = mapped_column(
        SAEnum(ReminderChannel, name="reminder_channel", native_enum=True),
        nullable=False,
        server_default="in_app",
    )
    is_fired: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    task: Mapped["Task"] = relationship(back_populates="reminders")
