"""W2a Slice 2: calendar subscriptions + mirror toggle.

Revision ID: 005_calendar_subscriptions
Revises: 004_recurrence_frame
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_calendar_subscriptions"
down_revision: Union[str, None] = "004_recurrence_frame"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

calendar_subscription_role = postgresql.ENUM(
    "primary",
    "informational",
    name="calendar_subscription_role",
    create_type=False,
)


def upgrade() -> None:
    calendar_subscription_role.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "calendar_accounts",
        sa.Column("mirror_blocks_to_google", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "calendar_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_calendar_id", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("role", calendar_subscription_role, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sync_cursor", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["calendar_account_id"], ["calendar_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("calendar_account_id", "external_calendar_id", name="calendar_subscriptions_account_calendar_unique"),
    )
    op.create_index("idx_calendar_subscriptions_account", "calendar_subscriptions", ["calendar_account_id"])


def downgrade() -> None:
    op.drop_index("idx_calendar_subscriptions_account", table_name="calendar_subscriptions")
    op.drop_table("calendar_subscriptions")
    op.drop_column("calendar_accounts", "last_synced_at")
    op.drop_column("calendar_accounts", "mirror_blocks_to_google")
    calendar_subscription_role.drop(op.get_bind(), checkfirst=True)
