"""F3 explanation provenance: fingerprint, snapshot, evaluated_at.

Revision ID: 023_schedule_outcome_provenance
Revises: 022_schedule_task_outcomes
Create Date: 2026-10-08

Additive on Jules' schedule_task_outcomes (022). Reads compare
input_snapshot to live inputs and do not replan.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "023_schedule_outcome_provenance"
down_revision: Union[str, None] = "022_schedule_task_outcomes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schedule_task_outcomes",
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE schedule_task_outcomes
        SET evaluated_at = created_at
        WHERE evaluated_at IS NULL
        """
    )
    op.alter_column(
        "schedule_task_outcomes",
        "evaluated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.add_column(
        "schedule_task_outcomes",
        sa.Column("outcome", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "schedule_task_outcomes",
        sa.Column("placement_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "schedule_task_outcomes",
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "schedule_task_outcomes",
        sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "schedule_task_outcomes",
        sa.Column("algorithm_version", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "idx_schedule_task_outcomes_latest",
        "schedule_task_outcomes",
        ["owner_id", "task_id", sa.text("evaluated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_schedule_task_outcomes_latest",
        table_name="schedule_task_outcomes",
    )
    op.drop_column("schedule_task_outcomes", "algorithm_version")
    op.drop_column("schedule_task_outcomes", "input_fingerprint")
    op.drop_column("schedule_task_outcomes", "input_snapshot")
    op.drop_column("schedule_task_outcomes", "placement_facts")
    op.drop_column("schedule_task_outcomes", "outcome")
    op.drop_column("schedule_task_outcomes", "evaluated_at")
