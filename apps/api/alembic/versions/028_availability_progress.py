"""S1 availability policies, progress columns, nominal workday, chunking flags.

Revision ID: 028_availability_progress
Revises: 027_saved_filter_presentation
Create Date: 2026-10-12

Additive only. Seeds Working / General / empty Personal from user_settings,
task progress (worked 0, remaining from estimate or 0 when completed), and
settings defaults. Does not modify scheduled_blocks, explanation or fingerprint
JSON, or user_settings.scheduling_revision.

Overnight flag matches app.services.availability_seed.derive_window_end:
ends_next_day when start + duration reaches or passes the next midnight.
Weekday 0 is Monday (date.weekday() / workweek_days).
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "028_availability_progress"
down_revision: Union[str, None] = "027_saved_filter_presentation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

availability_policy_slug = postgresql.ENUM(
    "general",
    "work",
    "personal",
    name="availability_policy_slug",
    create_type=False,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEPT_TASK_BOUND_CHECKS = {
    "tasks_min_block_duration_positive",
    "tasks_max_block_duration_positive",
    "tasks_block_bounds_order",
}

# Lockstep with derive_window_end and the availability_windows checks.
# The comparison must be parenthesized: Postgres treats = and >= as the same
# precedence and associates left, so `flag = expr >= 86400` is a syntax error.
_OVERNIGHT_SQL = (
    "((EXTRACT(EPOCH FROM start_time) + duration_minutes::bigint * 60) >= 86400)"
)
_END_SQL = "(start_time + make_interval(mins => duration_minutes))::time"


def _drop_legacy_task_bound_checks() -> None:
    """Drop pre-028 min/max checks so NULL inherit and No-limit can be stored.

    Existing rows keep their integers. The replacement checks still require
    a positive explicit bound and max >= min unless the unbounded flag is set.
    """
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            WHERE rel.relname = 'tasks'
              AND rel.relnamespace = 'public'::regnamespace
              AND con.contype = 'c'
            """
        )
    )
    for name, definition in rows:
        if name in _KEPT_TASK_BOUND_CHECKS:
            continue
        if not _IDENTIFIER.fullmatch(name):
            raise RuntimeError(f"unexpected tasks check constraint name: {name!r}")
        lowered = definition.lower()
        if (
            "min_block_duration_minutes" not in lowered
            and "max_block_duration_minutes" not in lowered
        ):
            continue
        conn.execute(sa.text(f'ALTER TABLE tasks DROP CONSTRAINT "{name}"'))


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("nominal_workday_minutes", sa.Integer(), nullable=True),
    )
    # Seed from the legacy workday length. Does not touch scheduling_revision.
    op.execute(
        sa.text(
            """
            UPDATE user_settings
            SET nominal_workday_minutes = workday_minutes
            WHERE nominal_workday_minutes IS NULL
            """
        )
    )
    op.alter_column(
        "user_settings",
        "nominal_workday_minutes",
        nullable=False,
        server_default="480",
    )
    op.create_check_constraint(
        "user_settings_nominal_workday_minutes_positive",
        "user_settings",
        "nominal_workday_minutes > 0",
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "default_max_block_duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
    )
    op.create_check_constraint(
        "user_settings_default_max_block_duration_positive",
        "user_settings",
        "default_max_block_duration_minutes > 0",
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "default_max_block_unbounded",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "max_block_unbounded",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "keep_in_one_block",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    _drop_legacy_task_bound_checks()
    # Keep server defaults 15/120 so an INSERT that omits the columns stays
    # explicit. Do not UPDATE existing min/max (no collapse to NULL).
    op.alter_column("tasks", "min_block_duration_minutes", nullable=True)
    op.alter_column("tasks", "max_block_duration_minutes", nullable=True)
    op.create_check_constraint(
        "tasks_min_block_duration_positive",
        "tasks",
        "min_block_duration_minutes IS NULL OR min_block_duration_minutes > 0",
    )
    op.create_check_constraint(
        "tasks_max_block_duration_positive",
        "tasks",
        "max_block_duration_minutes IS NULL OR max_block_duration_minutes > 0",
    )
    op.create_check_constraint(
        "tasks_block_bounds_order",
        "tasks",
        "min_block_duration_minutes IS NULL OR max_block_duration_minutes IS NULL "
        "OR max_block_unbounded OR max_block_duration_minutes >= min_block_duration_minutes",
    )

    op.add_column(
        "tasks",
        sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "tasks_worked_minutes_nonnegative",
        "tasks",
        "worked_minutes >= 0",
    )
    op.add_column(
        "tasks",
        sa.Column("remaining_minutes", sa.Integer(), nullable=True),
    )
    # Open remaining copies the original estimate. Completed remaining is 0.
    # worked stays 0. No effort-log rows. No block reads or writes.
    op.execute(
        sa.text(
            """
            UPDATE tasks
            SET remaining_minutes = CASE
                WHEN is_completed THEN 0
                ELSE estimated_duration_minutes
            END
            WHERE remaining_minutes IS NULL
            """
        )
    )
    op.create_check_constraint(
        "tasks_remaining_minutes_nonnegative",
        "tasks",
        "remaining_minutes IS NULL OR remaining_minutes >= 0",
    )

    availability_policy_slug.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "availability_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", availability_policy_slug, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "owner_id", "slug", name="availability_policies_owner_slug_unique"
        ),
        sa.UniqueConstraint("id", "owner_id", name="availability_policies_id_owner_unique"),
    )
    op.create_index(
        "idx_availability_policies_owner",
        "availability_policies",
        ["owner_id"],
    )

    op.create_table(
        "availability_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "ends_next_day",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id", "owner_id"],
            ["availability_policies.id", "availability_policies.owner_id"],
            name="availability_windows_policy_owner_fk",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="availability_windows_weekday",
        ),
        sa.CheckConstraint(
            "duration_minutes > 0",
            name="availability_windows_duration_positive",
        ),
        sa.CheckConstraint(
            f"ends_next_day = {_OVERNIGHT_SQL}",
            name="availability_windows_overnight_flag",
        ),
        sa.CheckConstraint(
            f"end_time = {_END_SQL}",
            name="availability_windows_end_matches_duration",
        ),
    )
    op.create_index(
        "idx_availability_windows_policy_day",
        "availability_windows",
        ["policy_id", "weekday", "sort_order"],
    )
    op.create_index(
        "idx_availability_windows_owner",
        "availability_windows",
        ["owner_id"],
    )

    # One policy row per owner per slug. Windows are an independent copy for
    # work and general (not a shared row). personal gets no windows.
    # Owners without settings fall back to Mon–Fri 09:00–17:00.
    op.execute(
        sa.text(
            """
            INSERT INTO availability_policies (id, owner_id, slug, name, sort_order)
            SELECT gen_random_uuid(), u.id, slug.slug::availability_policy_slug, slug.name, slug.sort_order
            FROM users u
            CROSS JOIN (
                VALUES
                    ('general', 'General', 0),
                    ('work', 'Working', 1),
                    ('personal', 'Personal', 2)
            ) AS slug(slug, name, sort_order)
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO availability_windows (
                id,
                policy_id,
                owner_id,
                weekday,
                start_time,
                end_time,
                ends_next_day,
                duration_minutes,
                sort_order
            )
            SELECT
                gen_random_uuid(),
                p.id,
                p.owner_id,
                gs.weekday::smallint,
                spec.start_time,
                (spec.start_time + make_interval(mins => spec.duration_minutes))::time,
                (
                    EXTRACT(EPOCH FROM spec.start_time)
                    + spec.duration_minutes::bigint * 60
                ) >= 86400,
                spec.duration_minutes,
                0
            FROM availability_policies p
            JOIN LATERAL (
                SELECT
                    COALESCE(s.workday_start_local, TIME '09:00:00') AS start_time,
                    COALESCE(s.workday_minutes, 480) AS duration_minutes,
                    COALESCE(s.workweek_days, 5) AS workweek_days
                FROM (SELECT 1) AS one
                LEFT JOIN user_settings s ON s.owner_id = p.owner_id
            ) AS spec ON TRUE
            JOIN LATERAL generate_series(0, spec.workweek_days - 1) AS gs(weekday) ON TRUE
            WHERE p.slug::text IN ('work', 'general')
              AND spec.workweek_days > 0
            """
        )
    )

    op.create_table(
        "task_progress_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("minutes_worked", sa.Integer(), nullable=False),
        sa.Column("remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("corrects_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_task_progress_entries_owner_idempotency",
        ),
        sa.UniqueConstraint(
            "id",
            "task_id",
            "owner_id",
            name="uq_task_progress_entries_id_task_owner",
        ),
        sa.ForeignKeyConstraint(
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
        sa.CheckConstraint(
            "minutes_worked > 0",
            name="task_progress_entries_minutes_positive",
        ),
        sa.CheckConstraint(
            "remaining_minutes >= 0",
            name="task_progress_entries_remaining_nonnegative",
        ),
    )
    op.create_index(
        "idx_task_progress_entries_owner",
        "task_progress_entries",
        ["owner_id"],
    )
    op.create_index(
        "idx_task_progress_entries_task_created",
        "task_progress_entries",
        ["task_id", "created_at"],
    )
    # Append-only: corrections insert a new row. DELETE stays legal so task
    # ON DELETE CASCADE can remove the log with the task.
    op.execute(
        sa.text(
            """
            CREATE FUNCTION task_progress_entries_append_only()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'task_progress_entries is append-only';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER task_progress_entries_append_only
            BEFORE UPDATE ON task_progress_entries
            FOR EACH ROW
            EXECUTE FUNCTION task_progress_entries_append_only()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS task_progress_entries_append_only "
            "ON task_progress_entries"
        )
    )
    op.drop_index(
        "idx_task_progress_entries_task_created", table_name="task_progress_entries"
    )
    op.drop_index("idx_task_progress_entries_owner", table_name="task_progress_entries")
    op.drop_table("task_progress_entries")
    op.execute(sa.text("DROP FUNCTION IF EXISTS task_progress_entries_append_only()"))

    op.drop_index("idx_availability_windows_owner", table_name="availability_windows")
    op.drop_index(
        "idx_availability_windows_policy_day", table_name="availability_windows"
    )
    op.drop_table("availability_windows")
    op.drop_index("idx_availability_policies_owner", table_name="availability_policies")
    op.drop_table("availability_policies")
    availability_policy_slug.drop(op.get_bind(), checkfirst=True)

    op.drop_constraint("tasks_remaining_minutes_nonnegative", "tasks", type_="check")
    op.drop_constraint("tasks_worked_minutes_nonnegative", "tasks", type_="check")
    op.drop_constraint("tasks_block_bounds_order", "tasks", type_="check")
    op.drop_constraint("tasks_max_block_duration_positive", "tasks", type_="check")
    op.drop_constraint("tasks_min_block_duration_positive", "tasks", type_="check")
    op.drop_column("tasks", "remaining_minutes")
    op.drop_column("tasks", "worked_minutes")
    op.drop_column("tasks", "keep_in_one_block")
    op.drop_column("tasks", "max_block_unbounded")
    op.alter_column("tasks", "min_block_duration_minutes", nullable=False)
    op.alter_column("tasks", "max_block_duration_minutes", nullable=False)
    # Restore the pre-028 names from 001 (tasks_check is the unnamed max>=min check).
    op.create_check_constraint(
        "tasks_min_block_duration_minutes_check",
        "tasks",
        "min_block_duration_minutes > 0",
    )
    op.create_check_constraint(
        "tasks_check",
        "tasks",
        "max_block_duration_minutes >= min_block_duration_minutes",
    )

    op.drop_constraint(
        "user_settings_default_max_block_duration_positive",
        "user_settings",
        type_="check",
    )
    op.drop_constraint(
        "user_settings_nominal_workday_minutes_positive",
        "user_settings",
        type_="check",
    )
    op.drop_column("user_settings", "default_max_block_unbounded")
    op.drop_column("user_settings", "default_max_block_duration_minutes")
    op.drop_column("user_settings", "nominal_workday_minutes")
