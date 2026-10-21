"""Persisted free/busy series policy + per-occurrence baselines (T1-4a).

Revision ID: 039_free_busy_series_policy
Revises: 038_export_baseline
Create Date: 2026-10-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

_calendar_provider = postgresql.ENUM(
    "google",
    "microsoft",
    name="calendar_provider",
    create_type=False,
)

revision: str = "039_free_busy_series_policy"
down_revision: Union[str, None] = "038_export_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "free_busy_series_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", _calendar_provider, nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("provider_series_id", sa.String(length=255), nullable=False),
        sa.Column("mapping", sa.String(length=16), nullable=False, server_default="free"),
        sa.Column(
            "resolved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decision_source", sa.String(length=64), nullable=False, server_default="manual_resolve"),
        sa.Column("acknowledged_calendar_id", sa.String(length=255), nullable=True),
        sa.Column("acknowledged_series_id", sa.String(length=255), nullable=True),
        sa.Column("acknowledged_provider_transparency", sa.String(length=32), nullable=True),
        sa.Column("acknowledged_provider_provenance", sa.String(length=64), nullable=True),
        sa.Column(
            "conflict_pending_latched",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("latch_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("mapping = 'free'", name="ck_free_busy_series_policies_mapping_free"),
        sa.UniqueConstraint(
            "owner_id",
            "provider",
            "calendar_id",
            "provider_series_id",
            name="uq_free_busy_series_policies_identity",
        ),
    )
    op.create_index(
        "idx_free_busy_series_policies_owner",
        "free_busy_series_policies",
        ["owner_id"],
    )

    op.create_table(
        "free_busy_series_policy_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("free_busy_series_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("mapping", sa.String(length=16), nullable=False),
        sa.Column("decision_source", sa.String(length=64), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "supersedes_decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("free_busy_series_policy_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "mapping = 'free'",
            name="ck_free_busy_series_policy_decisions_mapping_free",
        ),
    )
    op.create_index(
        "idx_free_busy_series_policy_decisions_policy",
        "free_busy_series_policy_decisions",
        ["policy_id"],
    )

    op.create_table(
        "free_busy_occurrence_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", _calendar_provider, nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("transparency", sa.String(length=32), nullable=True),
        sa.Column("free_busy_provenance", sa.String(length=64), nullable=True),
        sa.Column("occupancy_kind", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "owner_id",
            "provider",
            "external_event_id",
            name="uq_free_busy_occurrence_baselines_event",
        ),
    )


def downgrade() -> None:
    op.drop_table("free_busy_occurrence_baselines")
    op.drop_table("free_busy_series_policy_decisions")
    op.drop_table("free_busy_series_policies")
