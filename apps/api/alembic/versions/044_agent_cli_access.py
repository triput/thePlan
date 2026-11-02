"""Phase 1: agent/CLI credentials + allow_agent_cli_access grandfather.

Revision ID: 044_agent_cli_access
Revises: 043_recovery_epoch

Disposable-safe successor after 043. Do NOT apply to household (pinned at 042).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "044_agent_cli_access"
down_revision: Union[str, None] = "043_recovery_epoch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "allow_agent_cli_access",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "allow_agent_cli_access_grandfathered",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    # Existing accounts: one-time grandfather ON with auditable flag.
    op.execute(
        sa.text(
            "UPDATE user_settings SET "
            "allow_agent_cli_access = true, "
            "allow_agent_cli_access_grandfathered = true"
        )
    )

    op.create_table(
        "agent_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("secret_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_agent_credentials_owner", "agent_credentials", ["owner_id"])


def downgrade() -> None:
    op.drop_index("idx_agent_credentials_owner", table_name="agent_credentials")
    op.drop_table("agent_credentials")
    op.drop_column("user_settings", "allow_agent_cli_access_grandfathered")
    op.drop_column("user_settings", "allow_agent_cli_access")
