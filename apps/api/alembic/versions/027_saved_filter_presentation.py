"""F7 saved views: presentation_json + system predicate v1 backfill.

Revision ID: 027_saved_filter_presentation
Revises: 026_pending_deletion
Create Date: 2026-10-10
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "027_saved_filter_presentation"
down_revision: Union[str, None] = "026_pending_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INBOX_V1 = {
    "v": 1,
    "dimensions": {"inbox": True, "completion": "open"},
}
_TODAY_V1 = {
    "v": 1,
    "dimensions": {
        "due": {"kind": "rolling", "rolling": "today"},
        "completion": "open",
    },
}
_UPCOMING_V1 = {
    "v": 1,
    "dimensions": {
        "due": {"kind": "rolling", "rolling": "within_days", "days": 7},
        "completion": "open",
    },
}
_BACKFILL_BY_SLUG = {
    "inbox": _INBOX_V1,
    "today": _TODAY_V1,
    "upcoming": _UPCOMING_V1,
}


def upgrade() -> None:
    op.add_column(
        "saved_filters",
        sa.Column(
            "presentation_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    conn = op.get_bind()
    for slug, predicate in _BACKFILL_BY_SLUG.items():
        conn.execute(
            sa.text(
                """
                UPDATE saved_filters
                SET predicate_json = CAST(:pred AS jsonb)
                WHERE is_system = true AND slug = :slug
                """
            ),
            {"pred": json.dumps(predicate), "slug": slug},
        )


def downgrade() -> None:
    op.drop_column("saved_filters", "presentation_json")
