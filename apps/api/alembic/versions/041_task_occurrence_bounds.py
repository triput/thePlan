"""T2-S1: nullable start occurrence bounds on tasks.

Revision ID: 041_task_occurrence_bounds
Revises: 040_series_identity_state
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041_task_occurrence_bounds"
down_revision: Union[str, None] = "040_series_identity_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("start_no_earlier_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("start_no_later_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "start_no_later_at")
    op.drop_column("tasks", "start_no_earlier_at")
