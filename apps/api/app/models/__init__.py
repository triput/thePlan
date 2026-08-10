import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import CalendarProvider, ReminderChannel, ScheduleStatus, TaskPriority


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    username: Mapped[str | None] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    settings: Mapped["UserSettings"] = relationship(back_populates="owner", uselist=False)
    saved_filters: Mapped[list["SavedFilter"]] = relationship(back_populates="owner")


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en-US")
    workday_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="480")
    workweek_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    inter_block_buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    ups_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default='{"Wp": 0.35, "Wu": 0.40, "Wd": 0.15, "We": 0.10, "k": 0.5}',
    )
    upcoming_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")

    owner: Mapped["User"] = relationship(back_populates="settings")


class Epic(Base, TimestampMixin):
    __tablename__ = "epics"
    __table_args__ = (
        Index("idx_epics_owner", "owner_id"),
        Index("idx_epics_owner_archived", "owner_id", "is_archived"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#6D3FC9")
    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    projects: Mapped[list["Project"]] = relationship(back_populates="epic")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        Index("idx_projects_owner", "owner_id"),
        Index("idx_projects_epic", "epic_id"),
        Index("idx_projects_owner_archived", "owner_id", "is_archived"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    epic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("epics.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#0A8558")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    epic: Mapped["Epic | None"] = relationship(back_populates="projects")
    sections: Mapped[list["Section"]] = relationship(back_populates="project")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Section(Base, TimestampMixin):
    __tablename__ = "sections"
    __table_args__ = (
        Index("idx_sections_project", "project_id"),
        Index("idx_sections_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    project: Mapped["Project"] = relationship(back_populates="sections")
    tasks: Mapped[list["Task"]] = relationship(back_populates="section")


class FocusWindow(Base, TimestampMixin):
    __tablename__ = "focus_windows"
    __table_args__ = (CheckConstraint("end_time > start_time", name="focus_window_time_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    days_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="31")
    is_hard: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


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
    status: Mapped[ScheduleStatus] = mapped_column(
        SAEnum(ScheduleStatus, name="schedule_status", native_enum=True),
        nullable=False,
        server_default="unscheduled",
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    completed_at: Mapped[datetime | None] = mapped_column()

    project: Mapped["Project | None"] = relationship(back_populates="tasks")
    section: Mapped["Section | None"] = relationship(back_populates="tasks")
    label_links: Mapped[list["TaskLabel"]] = relationship(back_populates="task")
    scheduled_blocks: Mapped[list["ScheduledBlock"]] = relationship(back_populates="task")
    recurrence_rule: Mapped["RecurrenceRule | None"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )

class Label(Base, TimestampMixin):
    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="labels_owner_name_unique"),
        CheckConstraint("name = lower(name)", name="labels_name_lowercase"),
        CheckConstraint("length(trim(name)) > 0", name="labels_name_nonempty"),
        Index("idx_labels_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#635F75")

    task_links: Mapped[list["TaskLabel"]] = relationship(back_populates="label")


class TaskLabel(Base):
    __tablename__ = "task_labels"
    __table_args__ = (
        Index("idx_task_labels_label", "label_id"),
        Index("idx_task_labels_task", "task_id"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    task: Mapped["Task"] = relationship(back_populates="label_links")
    label: Mapped["Label"] = relationship(back_populates="task_links")


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


class SavedFilter(Base, TimestampMixin):
    __tablename__ = "saved_filters"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="saved_filters_owner_slug_unique"),
        Index("idx_saved_filters_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    predicate_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    owner: Mapped["User"] = relationship(back_populates="saved_filters")


class CalendarAccount(Base, TimestampMixin):
    __tablename__ = "calendar_accounts"
    __table_args__ = (
        UniqueConstraint("owner_id", "provider", "account_email", name="calendar_accounts_owner_provider_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[CalendarProvider] = mapped_column(
        SAEnum(CalendarProvider, name="calendar_provider", native_enum=True), nullable=False
    )
    account_email: Mapped[str | None] = mapped_column(String(255))
    access_token_enc: Mapped[str | None] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column()
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class ExternalCalendarEvent(Base):
    __tablename__ = "external_calendar_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="unique_external_event"),
        Index("idx_external_events_account", "calendar_account_id"),
        Index("idx_external_events_time", "start_time", "end_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    calendar_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_accounts.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    scheduled_block_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_blocks.id", ondelete="SET NULL")
    )
    provider: Mapped[CalendarProvider] = mapped_column(
        SAEnum(CalendarProvider, name="calendar_provider", native_enum=True), nullable=False
    )
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sync_hash: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (Index("idx_schedule_runs_owner", "owner_id", desc("started_at")),)

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
