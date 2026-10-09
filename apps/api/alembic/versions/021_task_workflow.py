"""F2 Kanban workflow_state, board_rank, board_revision.

Revision ID: 021_task_workflow
Revises: 020_task_source_refs
Create Date: 2026-10-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021_task_workflow"
down_revision: Union[str, None] = "020_task_source_refs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_workflow_state = postgresql.ENUM(
    "ready",
    "in_progress",
    "waiting",
    name="task_workflow_state",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE task_workflow_state AS ENUM ('ready', 'in_progress', 'waiting');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.add_column(
        "tasks",
        sa.Column(
            "workflow_state",
            task_workflow_state,
            nullable=False,
            server_default="ready",
        ),
    )
    op.add_column("tasks", sa.Column("waiting_note", sa.Text(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("board_rank", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tasks",
        sa.Column("board_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill board_rank from outline/list sort_order (stable gaps for inserts).
    op.execute(
        """
        UPDATE tasks
        SET board_rank = (sort_order::bigint * 1000000)
        WHERE board_rank = 0
        """
    )
    op.execute(
        """
        UPDATE tasks t
        SET board_rank = sub.rn * 1000000
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY owner_id ORDER BY created_at, id) AS rn
            FROM tasks
        ) sub
        WHERE t.id = sub.id AND t.board_rank = 0
        """
    )
    op.create_index(
        "idx_tasks_owner_workflow",
        "tasks",
        ["owner_id", "workflow_state"],
    )
    op.create_index(
        "idx_tasks_owner_board_rank",
        "tasks",
        ["owner_id", "board_rank"],
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_owner_board_rank", table_name="tasks")
    op.drop_index("idx_tasks_owner_workflow", table_name="tasks")
    op.drop_column("tasks", "board_revision")
    op.drop_column("tasks", "board_rank")
    op.drop_column("tasks", "waiting_note")
    op.drop_column("tasks", "workflow_state")
    op.execute("DROP TYPE IF EXISTS task_workflow_state")
