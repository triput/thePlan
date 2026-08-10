"""001 baseline schema

Revision ID: 001_baseline
Revises:
Create Date: 2026-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_priority = postgresql.ENUM("p1", "p2", "p3", "p4", name="task_priority", create_type=False)
schedule_status = postgresql.ENUM(
    "unscheduled", "scheduled", "pinned", "completed", "cancelled", "overbooked",
    name="schedule_status", create_type=False,
)
calendar_provider = postgresql.ENUM("google", "microsoft", name="calendar_provider", create_type=False)
reminder_channel = postgresql.ENUM("in_app", "browser", name="reminder_channel", create_type=False)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    task_priority.create(op.get_bind(), checkfirst=True)
    schedule_status.create(op.get_bind(), checkfirst=True)
    calendar_provider.create(op.get_bind(), checkfirst=True)
    reminder_channel.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("locale", sa.String(length=16), server_default="en-US", nullable=False),
        sa.Column("workday_minutes", sa.Integer(), server_default="480", nullable=False),
        sa.Column("workweek_days", sa.Integer(), server_default="5", nullable=False),
        sa.Column("inter_block_buffer_minutes", sa.Integer(), server_default="5", nullable=False),
        sa.Column("ups_weights", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{\"Wp\": 0.35, \"Wu\": 0.40, \"Wd\": 0.15, \"We\": 0.10, \"k\": 0.5}'::jsonb"), nullable=False),
        sa.Column("upcoming_horizon_days", sa.Integer(), server_default="7", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id"),
        sa.CheckConstraint("workday_minutes > 0"),
        sa.CheckConstraint("workweek_days BETWEEN 1 AND 7"),
        sa.CheckConstraint("inter_block_buffer_minutes >= 0"),
        sa.CheckConstraint("upcoming_horizon_days > 0"),
    )
    op.create_table(
        "epics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color_hex", sa.String(length=7), server_default="#6D3FC9", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_epics_owner", "epics", ["owner_id"])
    op.create_index("idx_epics_owner_archived", "epics", ["owner_id", "is_archived"])

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("epic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color_hex", sa.String(length=7), server_default="#0A8558", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["epic_id"], ["epics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_projects_owner", "projects", ["owner_id"])
    op.create_index("idx_projects_epic", "projects", ["epic_id"])
    op.create_index("idx_projects_owner_archived", "projects", ["owner_id", "is_archived"])

    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sections_project", "sections", ["project_id"])
    op.create_index("idx_sections_owner", "sections", ["owner_id"])

    op.create_table(
        "focus_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("days_of_week", sa.SmallInteger(), server_default="31", nullable=False),
        sa.Column("is_hard", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_time > start_time", name="focus_window_time_order"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", task_priority, server_default="p4", nullable=False),
        sa.Column("nesting_level", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_duration_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("min_block_duration_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("max_block_duration_minutes", sa.Integer(), server_default="120", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("soft_target_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferred_time_window_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", schedule_status, server_default="unscheduled", nullable=False),
        sa.Column("is_completed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["preferred_time_window_id"], ["focus_windows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("nesting_level BETWEEN 0 AND 2"),
        sa.CheckConstraint("section_id IS NULL OR project_id IS NOT NULL", name="task_section_project_consistency"),
        sa.CheckConstraint("estimated_duration_minutes > 0"),
        sa.CheckConstraint("min_block_duration_minutes > 0"),
        sa.CheckConstraint("max_block_duration_minutes >= min_block_duration_minutes"),
    )
    op.create_index("idx_tasks_owner", "tasks", ["owner_id"])
    op.create_index("idx_tasks_project", "tasks", ["project_id"])
    op.create_index("idx_tasks_section", "tasks", ["section_id"])
    op.create_index("idx_tasks_parent", "tasks", ["parent_task_id"])
    op.create_index("idx_tasks_nesting", "tasks", ["nesting_level"])
    op.create_index("idx_tasks_owner_due_at", "tasks", ["owner_id", "due_at"])
    op.create_index("idx_tasks_owner_deadline_at", "tasks", ["owner_id", "deadline_at"])
    op.create_index("idx_tasks_owner_is_completed", "tasks", ["owner_id", "is_completed"])
    op.create_index("idx_tasks_owner_project_sort", "tasks", ["owner_id", "project_id", "sort_order"])

    op.create_table(
        "labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color_hex", sa.String(length=7), server_default="#635F75", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="labels_owner_name_unique"),
        sa.CheckConstraint("name = lower(name)", name="labels_name_lowercase"),
        sa.CheckConstraint("length(trim(name)) > 0", name="labels_name_nonempty"),
    )
    op.create_index("idx_labels_owner", "labels", ["owner_id"])

    op.create_table(
        "task_labels",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["labels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "label_id"),
    )
    op.create_index("idx_task_labels_label", "task_labels", ["label_id"])
    op.create_index("idx_task_labels_task", "task_labels", ["task_id"])

    op.create_table(
        "task_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blocking_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependent_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocking_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dependent_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocking_task_id", "dependent_task_id", name="unique_dependency"),
        sa.CheckConstraint("blocking_task_id <> dependent_task_id", name="no_self_dependency"),
    )
    op.create_index("idx_task_dependencies_blocking", "task_dependencies", ["blocking_task_id"])
    op.create_index("idx_task_dependencies_dependent", "task_dependencies", ["dependent_task_id"])

    op.create_table(
        "scheduled_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_time > start_time", name="scheduled_block_time_order"),
    )
    op.create_index("idx_scheduled_blocks_task", "scheduled_blocks", ["task_id"])
    op.create_index("idx_scheduled_blocks_owner", "scheduled_blocks", ["owner_id"])
    op.create_index("idx_scheduled_blocks_time", "scheduled_blocks", ["start_time", "end_time"])
    op.create_index("idx_scheduled_blocks_owner_time", "scheduled_blocks", ["owner_id", "start_time", "end_time"])

    op.create_table(
        "recurrence_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rrule", sa.Text(), nullable=False),
        sa.Column("is_fixed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )

    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", reminder_channel, server_default="in_app", nullable=False),
        sa.Column("is_fired", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_reminders_task", "reminders", ["task_id"])

    op.create_table(
        "saved_filters",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("predicate_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "slug", name="saved_filters_owner_slug_unique"),
    )
    op.create_index("idx_saved_filters_owner", "saved_filters", ["owner_id"])

    op.create_table(
        "calendar_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", calendar_provider, nullable=False),
        sa.Column("account_email", sa.String(length=255), nullable=True),
        sa.Column("access_token_enc", sa.Text(), nullable=True),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_cursor", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "provider", "account_email", name="calendar_accounts_owner_provider_unique"),
    )

    op.create_table(
        "schedule_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="running", nullable=False),
        sa.Column("tasks_scheduled", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocks_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("overbooked_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stats_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_schedule_runs_owner", "schedule_runs", ["owner_id", "started_at"])

    op.create_table(
        "external_calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scheduled_block_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", calendar_provider, nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_all_day", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sync_hash", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["calendar_account_id"], ["calendar_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scheduled_block_id"], ["scheduled_blocks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_event_id", name="unique_external_event"),
    )
    op.create_index("idx_external_events_account", "external_calendar_events", ["calendar_account_id"])
    op.create_index("idx_external_events_time", "external_calendar_events", ["start_time", "end_time"])


def downgrade() -> None:
    op.drop_table("external_calendar_events")
    op.drop_table("schedule_runs")
    op.drop_table("calendar_accounts")
    op.drop_table("saved_filters")
    op.drop_table("reminders")
    op.drop_table("recurrence_rules")
    op.drop_table("scheduled_blocks")
    op.drop_table("task_dependencies")
    op.drop_table("task_labels")
    op.drop_table("labels")
    op.drop_table("tasks")
    op.drop_table("focus_windows")
    op.drop_table("sections")
    op.drop_table("projects")
    op.drop_table("epics")
    op.drop_table("user_settings")
    op.drop_table("users")

    reminder_channel.drop(op.get_bind(), checkfirst=True)
    calendar_provider.drop(op.get_bind(), checkfirst=True)
    schedule_status.drop(op.get_bind(), checkfirst=True)
    task_priority.drop(op.get_bind(), checkfirst=True)
