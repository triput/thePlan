"""DEF-018: epics/projects preferred_time_window_id → focus_windows.

Revision ID: 012_hierarchy_time_maps
Revises: 011_mirror_blocks
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012_hierarchy_time_maps"
down_revision: Union[str, None] = "011_mirror_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "epics",
        sa.Column("preferred_time_window_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "epics_preferred_time_window_id_fkey",
        "epics",
        "focus_windows",
        ["preferred_time_window_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "projects",
        sa.Column("preferred_time_window_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "projects_preferred_time_window_id_fkey",
        "projects",
        "focus_windows",
        ["preferred_time_window_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "projects_preferred_time_window_id_fkey", "projects", type_="foreignkey"
    )
    op.drop_column("projects", "preferred_time_window_id")
    op.drop_constraint(
        "epics_preferred_time_window_id_fkey", "epics", type_="foreignkey"
    )
    op.drop_column("epics", "preferred_time_window_id")
