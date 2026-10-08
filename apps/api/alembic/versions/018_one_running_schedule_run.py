"""One running schedule_runs row per owner.

Revision ID: 018_one_running_schedule_run
Revises: 017_session_epoch
Create Date: 2026-10-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018_one_running_schedule_run"
down_revision: Union[str, None] = "017_session_epoch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the earliest running row per owner so an in-flight replan continues.
    # Newer duplicates from the admit race are failed before the unique index.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY owner_id
                           ORDER BY started_at ASC, id ASC
                       ) AS rn
                FROM schedule_runs
                WHERE status = 'running'
            )
            UPDATE schedule_runs
            SET status = 'failed',
                error_message = 'superseded: one running schedule run per owner',
                finished_at = NOW()
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            """
        )
    )
    op.create_index(
        "uq_schedule_runs_one_running_per_owner",
        "schedule_runs",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_schedule_runs_one_running_per_owner",
        table_name="schedule_runs",
    )
