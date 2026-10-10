"""Tombstone mirrored events when the provider delete fails.

Revision ID: 026_pending_deletion
Revises: 025_schedule_previews
Create Date: 2026-10-09

DEF-028: a failed horizon-wipe delete must keep provider identity so a later
sync can retry and must not reimport the remote event as anonymous busy.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026_pending_deletion"
down_revision: Union[str, None] = "025_schedule_previews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "external_calendar_events",
        sa.Column(
            "pending_deletion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("external_calendar_events", "pending_deletion")
