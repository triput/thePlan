"""W2b Schedule refactor pass A: workday_start_local + task schedule_style.

Revision ID: 008_schedule_refactor
Revises: 007_plans
Create Date: 2026-08-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_schedule_refactor"
down_revision: Union[str, None] = "007_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schedule_style = postgresql.ENUM(
    "standalone",
    "time_block",
    "bundle",
    name="schedule_style",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "workday_start_local",
            sa.Time(),
            server_default=sa.text("'08:00:00'"),
            nullable=False,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("schedule_style", schedule_style, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "schedule_style")
    op.drop_column("user_settings", "workday_start_local")
