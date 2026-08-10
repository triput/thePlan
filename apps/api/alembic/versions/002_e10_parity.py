"""E10 parity: reminder fire_at partial index + schedule_runs DESC.

Revision ID: 002_e10_parity
Revises: 001_baseline
Create Date: 2026-08-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_e10_parity"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_reminders_fire_at",
        "reminders",
        ["owner_id", "fire_at"],
        postgresql_where=sa.text("is_fired = FALSE"),
    )
    op.drop_index("idx_schedule_runs_owner", table_name="schedule_runs")
    op.create_index(
        "idx_schedule_runs_owner",
        "schedule_runs",
        ["owner_id", "started_at"],
        postgresql_ops={"started_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_schedule_runs_owner", table_name="schedule_runs")
    op.create_index(
        "idx_schedule_runs_owner",
        "schedule_runs",
        ["owner_id", "started_at"],
    )
    op.drop_index("idx_reminders_fire_at", table_name="reminders")
