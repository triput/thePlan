"""W2b Slice 2: user_settings expansion (defaults, schedule style, auto-defer).

Revision ID: 006_settings_expansion
Revises: 005_calendar_subscriptions
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_settings_expansion"
down_revision: Union[str, None] = "005_calendar_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schedule_style = postgresql.ENUM(
    "standalone",
    "time_block",
    "bundle",
    name="schedule_style",
    create_type=False,
)


def upgrade() -> None:
    schedule_style.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "user_settings",
        sa.Column(
            "default_estimated_duration_minutes",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "default_min_block_duration_minutes",
            sa.Integer(),
            server_default="15",
            nullable=False,
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "default_schedule_style",
            schedule_style,
            server_default="standalone",
            nullable=False,
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "auto_defer_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "user_settings_default_estimated_duration_positive",
        "user_settings",
        "default_estimated_duration_minutes > 0",
    )
    op.create_check_constraint(
        "user_settings_default_min_block_duration_positive",
        "user_settings",
        "default_min_block_duration_minutes > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "user_settings_default_min_block_duration_positive",
        "user_settings",
        type_="check",
    )
    op.drop_constraint(
        "user_settings_default_estimated_duration_positive",
        "user_settings",
        type_="check",
    )
    op.drop_column("user_settings", "auto_defer_enabled")
    op.drop_column("user_settings", "default_schedule_style")
    op.drop_column("user_settings", "default_min_block_duration_minutes")
    op.drop_column("user_settings", "default_estimated_duration_minutes")
    schedule_style.drop(op.get_bind(), checkfirst=True)
