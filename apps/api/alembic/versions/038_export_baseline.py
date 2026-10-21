"""Per-event export comparison baseline columns (Track 1 T1-11).

Revision ID: 038_export_baseline
Revises: 037_refresh_failure_sidecar
Create Date: 2026-10-20

Nullable export-only baseline on external_calendar_events. sync_hash untouched.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038_export_baseline"
down_revision: Union[str, None] = "037_refresh_failure_sidecar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "external_calendar_events",
        sa.Column("export_baseline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("export_baseline_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("export_calendar_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("export_baseline_etag", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("export_baseline_change_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("export_baseline_updated", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("export_baseline_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "external_calendar_events",
        sa.Column("export_baseline_schema_version", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_calendar_events", "export_baseline_schema_version")
    op.drop_column("external_calendar_events", "export_baseline_fingerprint")
    op.drop_column("external_calendar_events", "export_baseline_updated")
    op.drop_column("external_calendar_events", "export_baseline_change_key")
    op.drop_column("external_calendar_events", "export_baseline_etag")
    op.drop_column("external_calendar_events", "export_calendar_id")
    op.drop_column("external_calendar_events", "export_baseline_source")
    op.drop_column("external_calendar_events", "export_baseline_at")
