"""F1 handoff receipts and source_refs on hierarchy roots.

Revision ID: 019_handoff_receipts
Revises: 018_one_running_schedule_run
Create Date: 2026-10-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019_handoff_receipts"
down_revision: Union[str, None] = "018_one_running_schedule_run"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "handoff_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_kind", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("receipt_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "owner_id",
            "operation_kind",
            "idempotency_key",
            name="uq_handoff_receipts_owner_op_key",
        ),
    )
    op.create_index(
        "idx_handoff_receipts_owner",
        "handoff_receipts",
        ["owner_id"],
    )
    op.add_column(
        "epics",
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "source_refs")
    op.drop_column("epics", "source_refs")
    op.drop_index("idx_handoff_receipts_owner", table_name="handoff_receipts")
    op.drop_table("handoff_receipts")
