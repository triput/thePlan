"""DEF-024 thin: nullable deleted_at on tasks (soft-delete column only).

Revision ID: 015_task_deleted_at
Revises: 014_project_daily_schedule_cap
Create Date: 2026-08-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_task_deleted_at"
down_revision: Union[str, None] = "014_project_daily_schedule_cap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "deleted_at")
