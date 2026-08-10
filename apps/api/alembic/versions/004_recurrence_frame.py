"""Add starts_on/ends_on frame bounds to recurrence_rules.

Revision ID: 004_recurrence_frame
Revises: 003_auth_users
Create Date: 2026-08-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_recurrence_frame"
down_revision: Union[str, None] = "003_auth_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recurrence_rules", sa.Column("starts_on", sa.Date(), nullable=True))
    op.add_column("recurrence_rules", sa.Column("ends_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        "recurrence_rules_frame_order",
        "recurrence_rules",
        "ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on",
    )


def downgrade() -> None:
    op.drop_constraint("recurrence_rules_frame_order", "recurrence_rules", type_="check")
    op.drop_column("recurrence_rules", "ends_on")
    op.drop_column("recurrence_rules", "starts_on")
