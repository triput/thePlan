"""T2-S2 B-auto: durable occurrence miss dispositions and event history.

Revision ID: 042_task_occurrence_dispositions
Revises: 041_task_occurrence_bounds
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "042_task_occurrence_dispositions"
down_revision: Union[str, None] = "041_task_occurrence_bounds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_occurrence_dispositions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("episode_key", sa.String(128), nullable=False),
        sa.Column("resolution", sa.String(32), nullable=False),
        sa.Column("bounds_snapshot", JSONB, nullable=False),
        sa.Column("miss_reason_code", sa.String(64), nullable=True),
        sa.Column("miss_reason_params", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "owner_id",
            "task_id",
            "episode_key",
            name="uq_task_occurrence_dispositions_episode",
        ),
    )
    op.create_index(
        "idx_task_occurrence_dispositions_owner_resolution",
        "task_occurrence_dispositions",
        ["owner_id", "resolution"],
    )

    op.create_table(
        "disposition_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "disposition_id",
            UUID(as_uuid=True),
            sa.ForeignKey("task_occurrence_dispositions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "preview_id",
            UUID(as_uuid=True),
            sa.ForeignKey("schedule_previews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_disposition_events_disposition",
        "disposition_events",
        ["disposition_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_disposition_events_disposition", table_name="disposition_events")
    op.drop_table("disposition_events")
    op.drop_index(
        "idx_task_occurrence_dispositions_owner_resolution",
        table_name="task_occurrence_dispositions",
    )
    op.drop_table("task_occurrence_dispositions")
