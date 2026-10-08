"""DEF-027: users.session_epoch for session revocation.

Revision ID: 017_session_epoch
Revises: 016_scheduled_block_bundle_meta
Create Date: 2026-10-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_session_epoch"
down_revision: Union[str, None] = "016_scheduled_block_bundle_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_epoch", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "session_epoch")
