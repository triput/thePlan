"""DEF-014: schedule_style `manual` plus nullable inherit on epics/projects. ADR-006.

Postgres cannot easily drop an enum value; downgrade drops columns only.

Revision ID: 013_schedule_style_manual
Revises: 012_hierarchy_time_maps
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_schedule_style_manual"
down_revision: Union[str, None] = "012_hierarchy_time_maps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schedule_style = postgresql.ENUM(
    "standalone",
    "time_block",
    "bundle",
    "manual",
    name="schedule_style",
    create_type=False,
)


def upgrade() -> None:
    op.execute("ALTER TYPE schedule_style ADD VALUE IF NOT EXISTS 'manual'")
    op.add_column(
        "epics",
        sa.Column("schedule_style", schedule_style, nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("schedule_style", schedule_style, nullable=True),
    )


def downgrade() -> None:
    # Enum value `manual` is left in place; Postgres cannot drop it cheaply.
    op.drop_column("projects", "schedule_style")
    op.drop_column("epics", "schedule_style")
