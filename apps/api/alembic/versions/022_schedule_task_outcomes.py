"""F3 schedule_task_outcomes per run/task.

Revision ID: 022_schedule_task_outcomes
Revises: 021_task_workflow
Create Date: 2026-10-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022_schedule_task_outcomes"
down_revision: Union[str, None] = "021_task_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedule_task_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "schedule_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schedule_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.Column("requested_minutes", sa.Integer(), nullable=False),
        sa.Column("pinned_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placed_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remaining_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("primary_reason_code", sa.String(length=64), nullable=False),
        sa.Column("reason_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_schedule_task_outcomes_run",
        "schedule_task_outcomes",
        ["schedule_run_id"],
    )
    op.create_index(
        "idx_schedule_task_outcomes_task",
        "schedule_task_outcomes",
        ["owner_id", "task_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "uq_schedule_task_outcomes_run_task",
        "schedule_task_outcomes",
        ["schedule_run_id", "task_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_schedule_task_outcomes_run_task", table_name="schedule_task_outcomes")
    op.drop_index("idx_schedule_task_outcomes_task", table_name="schedule_task_outcomes")
    op.drop_index("idx_schedule_task_outcomes_run", table_name="schedule_task_outcomes")
    op.drop_table("schedule_task_outcomes")
