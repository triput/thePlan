"""Per-subscription calendar coverage evidence + provider cancellation (T1-C).

Revision ID: 036_calendar_coverage_freshness
Revises: 035_source_timezone
Create Date: 2026-10-19

Schema only — no data backfill.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036_calendar_coverage_freshness"
down_revision: Union[str, None] = "035_source_timezone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_window_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_window_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_mode", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_success_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_pagination_complete", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_active_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_success_generation", sa.Integer(), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_show_deleted", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_single_events", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_page_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_item_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_token_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_last_failure_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("coverage_last_failure_cause", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column(
            "is_provider_cancelled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("external_calendar_events", "is_provider_cancelled")
    for col in (
        "coverage_last_failure_cause",
        "coverage_last_failure_at",
        "coverage_token_fingerprint",
        "coverage_item_count",
        "coverage_page_count",
        "coverage_single_events",
        "coverage_show_deleted",
        "coverage_success_generation",
        "coverage_active_generation",
        "coverage_pagination_complete",
        "coverage_fetched_at",
        "coverage_success_at",
        "coverage_mode",
        "coverage_window_end",
        "coverage_window_start",
    ):
        op.drop_column("calendar_subscriptions", col)
