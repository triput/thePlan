"""Store submitted progress intent hash for idempotent replay.

Revision ID: 030_progress_intent_hash
Revises: 029_workweek_days_allow_zero
Create Date: 2026-10-12

Progress retries must compare the submitted payload (including workday
strings), not a re-parse against the current nominal_workday_minutes.
``intent_hash`` fingerprints the pre-resolution request so exact retries
replay after a nominal change while changed payloads still conflict.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_progress_intent_hash"
down_revision: Union[str, None] = "029_workweek_days_allow_zero"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_progress_entries",
        sa.Column("intent_hash", sa.String(length=64), nullable=True),
    )
    # Pre-030 rows (if any) get a sentinel so NOT NULL can apply; runtime falls
    # back to resolved-minutes comparison when intent_hash is this sentinel.
    op.execute(
        sa.text(
            """
            UPDATE task_progress_entries
            SET intent_hash = 'legacy-resolved-only'
            WHERE intent_hash IS NULL
            """
        )
    )
    op.alter_column(
        "task_progress_entries",
        "intent_hash",
        existing_type=sa.String(length=64),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("task_progress_entries", "intent_hash")
