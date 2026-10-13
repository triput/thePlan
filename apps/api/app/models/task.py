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
    ForeignKeyConstraint,
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
        CheckConstraint(
            "min_block_duration_minutes IS NULL OR min_block_duration_minutes > 0",
            name="tasks_min_block_duration_positive",
        ),
        CheckConstraint(
            "max_block_duration_minutes IS NULL OR max_block_duration_minutes > 0",
            name="tasks_max_block_duration_positive",
        ),
        CheckConstraint(
            "min_block_duration_minutes IS NULL OR max_block_duration_minutes IS NULL "
            "OR max_block_unbounded OR max_block_duration_minutes >= min_block_duration_minutes",
            name="tasks_block_bounds_order",
        ),
        CheckConstraint("worked_minutes >= 0", name="tasks_worked_minutes_nonnegative"),
        CheckConstraint(
            "remaining_minutes IS NULL OR remaining_minutes >= 0",
            name="tasks_remaining_minutes_nonnegative",
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
    # NULL = inherit that bound (S2). Omitted inserts stay explicit via server defaults.
    # 028 does not rewrite stored 15/120 (or any other integer) to NULL.
    min_block_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="15"
    )
    max_block_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="120"
    )
    max_block_unbounded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    keep_in_one_block: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    worked_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # NULL only as a mid-deploy fallback. Seed and create set a real remaining.
    remaining_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    progress_entries: Mapped[list["TaskProgressEntry"]] = relationship(
        back_populates="task",
        order_by="TaskProgressEntry.created_at",
        passive_deletes=True,
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


class TaskProgressEntry(Base):
    """Append-only worked entry. A correction is a new row, not an update.

    ``028`` seeds zero rows. ``idempotency_key`` is a UUID, same as handoff
    receipts. Same key + submitted ``intent_hash`` replays; a different
    submitted payload conflicts. Resolved minutes remain the committed
    interpretation. ``corrects_entry_id`` points at the entry this row
    corrects and must be the same task and owner.
    """

    __tablename__ = "task_progress_entries"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_task_progress_entries_owner_idempotency",
        ),
        # Target for the composite correction FK. id is already the primary key;
        # Postgres still requires a unique constraint that covers every referenced column.
        UniqueConstraint(
            "id",
            "task_id",
            "owner_id",
            name="uq_task_progress_entries_id_task_owner",
        ),
        ForeignKeyConstraint(
            ["corrects_entry_id", "task_id", "owner_id"],
            [
                "task_progress_entries.id",
                "task_progress_entries.task_id",
                "task_progress_entries.owner_id",
            ],
            name="task_progress_entries_correction_same_task",
            ondelete="NO ACTION",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "minutes_worked > 0",
            name="task_progress_entries_minutes_positive",
        ),
        CheckConstraint(
            "remaining_minutes >= 0",
            name="task_progress_entries_remaining_nonnegative",
        ),
        Index("idx_task_progress_entries_owner", "owner_id"),
        Index("idx_task_progress_entries_task_created", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # SHA-256 of submitted (pre-resolution) intent; see task_progress.progress_intent_hash.
    intent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    minutes_worked: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    corrects_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    task: Mapped["Task"] = relationship(
        back_populates="progress_entries",
        foreign_keys="TaskProgressEntry.task_id",
    )
    corrects_entry: Mapped["TaskProgressEntry | None"] = relationship(
        remote_side="TaskProgressEntry.id",
        foreign_keys="TaskProgressEntry.corrects_entry_id",
    )
