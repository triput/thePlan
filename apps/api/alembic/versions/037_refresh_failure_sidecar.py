"""Sidecar for calendar refresh failures that must survive a row lock.

Revision ID: 037_refresh_failure_sidecar
Revises: 036_calendar_coverage_freshness
Create Date: 2026-10-20

One open failure per subscription. INSERT references calendar_subscriptions
with FOR KEY SHARE so a caller's flushed non-key UPDATE does not block it.
Schema only — no data backfill.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "037_refresh_failure_sidecar"
down_revision: Union[str, None] = "036_calendar_coverage_freshness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_subscription_refresh_failures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("failure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cause", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["calendar_subscriptions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            name="calendar_subscription_refresh_failures_sub_unique",
        ),
    )


def downgrade() -> None:
    op.drop_table("calendar_subscription_refresh_failures")
