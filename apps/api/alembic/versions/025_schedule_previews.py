"""F6 replan preview store (immutable proposal + input fingerprint).

Revision ID: 025_schedule_previews
Revises: 024_time_map_overrides
Create Date: 2026-10-09

Preview rows are separate from schedule_runs (migration 018 one-running replan).
Apply path and scheduling_revision bumps land in F6-W2.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025_schedule_previews"
down_revision: Union[str, None] = "024_time_map_overrides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("scheduling_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "schedule_previews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("algorithm_version", sa.String(length=64), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("scheduling_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("proposal_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stats_json", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "idx_schedule_previews_owner",
        "schedule_previews",
        ["owner_id", sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_schedule_previews_owner", table_name="schedule_previews")
    op.drop_table("schedule_previews")
    op.drop_column("user_settings", "scheduling_revision")
