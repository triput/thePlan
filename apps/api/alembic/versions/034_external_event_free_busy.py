"""Persist Google transparency + free/busy provenance (Track 1 T1-A).

Revision ID: 034_external_event_free_busy
Revises: 033_custom_availability_slug
Create Date: 2026-10-19

Adds nullable free/busy columns on ``external_calendar_events``. Existing rows
stay null (``unknown_legacy`` at read time) — no invented opaque backfill.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034_external_event_free_busy"
down_revision: Union[str, None] = "033_custom_availability_slug"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "external_calendar_events",
        sa.Column("transparency", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("free_busy_provenance", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("provider_series_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("free_busy_prior_transparency", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("free_busy_prior_provenance", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("free_busy_sync_run_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("free_busy_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column(
            "source_zone_missing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column(
            "free_busy_pending_exception",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("external_calendar_events", "free_busy_pending_exception")
    op.drop_column("external_calendar_events", "source_zone_missing")
    op.drop_column("external_calendar_events", "free_busy_changed_at")
    op.drop_column("external_calendar_events", "free_busy_sync_run_id")
    op.drop_column("external_calendar_events", "free_busy_prior_provenance")
    op.drop_column("external_calendar_events", "free_busy_prior_transparency")
    op.drop_column("external_calendar_events", "provider_series_id")
    op.drop_column("external_calendar_events", "free_busy_provenance")
    op.drop_column("external_calendar_events", "transparency")
