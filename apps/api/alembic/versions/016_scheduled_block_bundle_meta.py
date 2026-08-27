"""DEF-019: nullable bundle_meta JSONB on scheduled_blocks (ADR-012).

Revision ID: 016_scheduled_block_bundle_meta
Revises: 015_task_deleted_at
Create Date: 2026-08-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016_scheduled_block_bundle_meta"
down_revision: Union[str, None] = "015_task_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheduled_blocks",
        sa.Column("bundle_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scheduled_blocks", "bundle_meta")
