"""W3 Slice 1: users.must_change_password for forced password reset.

Revision ID: 010_must_change_password
Revises: 009_painted_time_maps
Create Date: 2026-08-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_must_change_password"
down_revision: Union[str, None] = "009_painted_time_maps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
