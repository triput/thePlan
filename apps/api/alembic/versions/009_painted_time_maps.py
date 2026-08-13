"""Painted Time Maps: time_map_bands + slim focus_windows header.

Revision ID: 009_painted_time_maps
Revises: 008_schedule_refactor
Create Date: 2026-08-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_painted_time_maps"
down_revision: Union[str, None] = "008_schedule_refactor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

time_map_band_tier = postgresql.ENUM(
    "green",
    "yellow",
    "red",
    name="time_map_band_tier",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    time_map_band_tier.create(bind, checkfirst=True)

    op.create_table(
        "time_map_bands",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("map_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tier", time_map_band_tier, nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("days_of_week", sa.SmallInteger(), server_default="127", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["map_id"], ["focus_windows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_time > start_time", name="time_map_band_time_order"),
    )
    op.create_index("idx_time_map_bands_map", "time_map_bands", ["map_id"])

    op.execute(
        """
        INSERT INTO time_map_bands (id, map_id, tier, start_time, end_time, days_of_week, sort_order)
        SELECT uuid_generate_v4(), id, 'green', start_time, end_time, days_of_week, 0
        FROM focus_windows
        """
    )

    op.add_column(
        "focus_windows",
        sa.Column("strict_mode", sa.Boolean(), server_default="false", nullable=False),
    )
    op.execute("UPDATE focus_windows SET strict_mode = is_hard")

    op.drop_constraint("focus_window_time_order", "focus_windows", type_="check")
    op.drop_column("focus_windows", "start_time")
    op.drop_column("focus_windows", "end_time")
    op.drop_column("focus_windows", "days_of_week")
    op.drop_column("focus_windows", "is_hard")


def downgrade() -> None:
    op.add_column("focus_windows", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("focus_windows", sa.Column("end_time", sa.Time(), nullable=True))
    op.add_column(
        "focus_windows",
        sa.Column("days_of_week", sa.SmallInteger(), server_default="127", nullable=True),
    )
    op.add_column(
        "focus_windows",
        sa.Column("is_hard", sa.Boolean(), server_default="false", nullable=True),
    )

    op.execute(
        """
        UPDATE focus_windows fw
        SET
            start_time = b.start_time,
            end_time = b.end_time,
            days_of_week = b.days_of_week,
            is_hard = fw.strict_mode
        FROM (
            SELECT DISTINCT ON (map_id)
                map_id, start_time, end_time, days_of_week
            FROM time_map_bands
            WHERE tier = 'green'
            ORDER BY map_id, sort_order, start_time
        ) b
        WHERE fw.id = b.map_id
        """
    )

    op.execute(
        """
        UPDATE focus_windows
        SET
            start_time = COALESCE(start_time, '08:00:00'::time),
            end_time = COALESCE(end_time, '17:00:00'::time),
            days_of_week = COALESCE(days_of_week, 127),
            is_hard = COALESCE(is_hard, false)
        """
    )

    op.alter_column("focus_windows", "start_time", nullable=False)
    op.alter_column("focus_windows", "end_time", nullable=False)
    op.alter_column("focus_windows", "days_of_week", nullable=False)
    op.alter_column("focus_windows", "is_hard", nullable=False)

    op.drop_column("focus_windows", "strict_mode")

    op.drop_index("idx_time_map_bands_map", table_name="time_map_bands")
    op.drop_table("time_map_bands")

    bind = op.get_bind()
    time_map_band_tier.drop(bind, checkfirst=True)

    op.create_check_constraint(
        "focus_window_time_order",
        "focus_windows",
        "end_time > start_time",
    )
