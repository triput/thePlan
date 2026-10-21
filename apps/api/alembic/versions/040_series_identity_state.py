"""Provider-aware series_identity_state on external_calendar_events (T1-4-MS).

Revision ID: 040_series_identity_state
Revises: 039_free_busy_series_policy
Create Date: 2026-10-20

Local / disposable DSN only in acceptance evidence. Does not authorize
household calendar DB migration.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040_series_identity_state"
down_revision: Union[str, None] = "039_free_busy_series_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "external_calendar_events",
        sa.Column(
            "series_identity_state",
            sa.String(length=32),
            nullable=False,
            server_default="incomplete",
        ),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column(
            "series_identity_incomplete_reason",
            sa.String(length=64),
            nullable=True,
        ),
    )

    # Provider-aware backfill (contract §4.8). Does not clear pending/latches.
    op.execute(
        """
        UPDATE external_calendar_events
        SET
            series_identity_state = 'verified_series',
            series_identity_incomplete_reason = NULL
        WHERE provider = 'google'
          AND provider_series_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE external_calendar_events
        SET
            series_identity_state = 'verified_non_recurring',
            series_identity_incomplete_reason = NULL
        WHERE provider = 'google'
          AND provider_series_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE external_calendar_events
        SET
            series_identity_state = 'incomplete',
            series_identity_incomplete_reason = 'legacy_ms_unverified'
        WHERE provider = 'microsoft'
          AND provider_series_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE external_calendar_events
        SET
            series_identity_state = 'incomplete',
            series_identity_incomplete_reason = 'legacy_ms_unverified_seeded'
        WHERE provider = 'microsoft'
          AND provider_series_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("external_calendar_events", "series_identity_incomplete_reason")
    op.drop_column("external_calendar_events", "series_identity_state")
