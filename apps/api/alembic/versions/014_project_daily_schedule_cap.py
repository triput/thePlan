"""DEF-017: optional per-project daily auto-schedule cap on user_settings.

Revision ID: 014_project_daily_schedule_cap
Revises: 013_schedule_style_manual
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_project_daily_schedule_cap"
down_revision: Union[str, None] = "013_schedule_style_manual"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("max_auto_schedule_minutes_per_project_per_day", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_settings_project_daily_cap_positive",
        "user_settings",
        "max_auto_schedule_minutes_per_project_per_day IS NULL "
        "OR max_auto_schedule_minutes_per_project_per_day > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_settings_project_daily_cap_positive",
        "user_settings",
        type_="check",
    )
    op.drop_column("user_settings", "max_auto_schedule_minutes_per_project_per_day")
