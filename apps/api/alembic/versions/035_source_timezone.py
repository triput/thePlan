"""Persist source timezone provenance (Track 1 T1-B).

Revision ID: 035_source_timezone
Revises: 034_external_event_free_busy
Create Date: 2026-10-19

Adds resolved IANA ``source_timezone`` on external events and optional
``provider_timezone`` on calendar subscriptions (owning-calendar default).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_source_timezone"
down_revision: Union[str, None] = "034_external_event_free_busy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema only — no data UPDATE. Pre-035 all-day rows keep the 034
    # source_zone_missing=false default; free_busy.source_zone_untrusted()
    # is the sole containment rule (all-day + null source_timezone).
    op.add_column(
        "external_calendar_events",
        sa.Column("source_timezone", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "calendar_subscriptions",
        sa.Column("provider_timezone", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("calendar_subscriptions", "provider_timezone")
    op.drop_column("external_calendar_events", "source_timezone")
