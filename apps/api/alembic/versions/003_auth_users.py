"""Wave 1.5 auth: username, is_admin, is_disabled on users.

Revision ID: 003_auth_users
Revises: 002_e10_parity
Create Date: 2026-08-10

Baseline DDL in docs/sql/001_baseline.sql is historical; schema changes are
applied via Alembic only (see ADR-003 / Wave 1.5).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_auth_users"
down_revision: Union[str, None] = "002_e10_parity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("is_disabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_unique_constraint("users_username_key", "users", ["username"])


def downgrade() -> None:
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.drop_column("users", "is_disabled")
    op.drop_column("users", "is_admin")
    op.drop_column("users", "username")
