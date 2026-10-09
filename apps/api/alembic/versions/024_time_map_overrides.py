"""F4 temporary Time Map overrides (dated replacement bands).

Revision ID: 024_time_map_overrides
Revises: 023_schedule_outcome_provenance
Create Date: 2026-10-09

Scheduler collect reads rows intersecting the replan horizon. CRUD/routes
and overlap validation are Tesla's slice; no auto-replan on override write.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "024_time_map_overrides"
down_revision: Union[str, None] = "023_schedule_outcome_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "time_map_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("focus_windows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("local_start_date", sa.Date(), nullable=False),
        sa.Column("local_end_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("strict_mode", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "local_end_date >= local_start_date",
            name="time_map_override_date_order",
        ),
    )
    op.create_index("idx_time_map_overrides_map", "time_map_overrides", ["map_id"])
    op.create_index("idx_time_map_overrides_owner", "time_map_overrides", ["owner_id"])

    op.create_table(
        "time_map_override_bands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "override_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("time_map_overrides.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tier",
            postgresql.ENUM(
                "green",
                "yellow",
                "red",
                name="time_map_band_tier",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("days_of_week", sa.SmallInteger(), nullable=False, server_default="127"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "end_time > start_time",
            name="time_map_override_band_time_order",
        ),
    )
    op.create_index(
        "idx_time_map_override_bands_override",
        "time_map_override_bands",
        ["override_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_time_map_override_bands_override", table_name="time_map_override_bands")
    op.drop_table("time_map_override_bands")
    op.drop_index("idx_time_map_overrides_owner", table_name="time_map_overrides")
    op.drop_index("idx_time_map_overrides_map", table_name="time_map_overrides")
    op.drop_table("time_map_overrides")
