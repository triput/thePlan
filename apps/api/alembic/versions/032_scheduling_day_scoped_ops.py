"""S2-V4b day-scoped Change / Only-allow / scoped family and named ops.

Revision ID: 032_scheduling_day_scoped_ops
Revises: 031_scheduling_assignments
Create Date: 2026-10-14

Sibling table beside scheduling_rule_exceptions. Does not reuse
time_map_overrides, preferred_time_window_id, or tasks.source_refs.
Does not bump scheduling_revision or activate household.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032_scheduling_day_scoped_ops"
down_revision: Union[str, None] = "031_scheduling_assignments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

scheduling_scope_kind = postgresql.ENUM(
    "task",
    "project",
    "epic",
    name="scheduling_scope_kind",
    create_type=False,
)
scheduling_rule_kind = postgresql.ENUM(
    "may",
    "must",
    "prefer",
    name="scheduling_rule_kind",
    create_type=False,
)
scheduling_assignment_family = postgresql.ENUM(
    "none",
    "legacy",
    "new_rule",
    name="scheduling_assignment_family",
    create_type=False,
)
scheduling_day_scoped_op_kind = postgresql.ENUM(
    "change_selected",
    "only_allow",
    "family_replace_scoped",
    "clear_scoped",
    "add_scoped",
    "replace_named_scoped",
    "waive_named_scoped",
    name="scheduling_day_scoped_op_kind",
    create_type=False,
)
scheduling_day_selector_kind = postgresql.ENUM(
    "one_date",
    "weekday_standing",
    "date_range",
    name="scheduling_day_selector_kind",
    create_type=False,
)
scheduling_day_payload_kind = postgresql.ENUM(
    "none",
    "empty",
    "policy",
    "family",
    name="scheduling_day_payload_kind",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    scheduling_day_scoped_op_kind.create(bind, checkfirst=True)
    scheduling_day_selector_kind.create(bind, checkfirst=True)
    scheduling_day_payload_kind.create(bind, checkfirst=True)

    op.create_table(
        "scheduling_day_scoped_ops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_kind", scheduling_scope_kind, nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("op_kind", scheduling_day_scoped_op_kind, nullable=False),
        sa.Column("selector_kind", scheduling_day_selector_kind, nullable=False),
        # Civil labels (schedule-TZ). Not fixed instants — R3.
        sa.Column("civil_on_date", sa.Date(), nullable=True),
        sa.Column(
            "civil_weekdays",
            postgresql.ARRAY(sa.SmallInteger()),
            nullable=True,
        ),
        sa.Column("civil_start_date", sa.Date(), nullable=True),
        sa.Column("civil_end_date", sa.Date(), nullable=True),
        # Fixed instant expiry (preserve-instant UTC). Distinct from last
        # selected occurrence date (R1).
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_kind", scheduling_day_payload_kind, nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rule_name", sa.String(length=100), nullable=True),
        sa.Column("rule_kind", scheduling_rule_kind, nullable=True),
        sa.Column("target_rule_name", sa.String(length=100), nullable=True),
        sa.Column("target_rule_kind", scheduling_rule_kind, nullable=True),
        sa.Column("replacement_name", sa.String(length=100), nullable=True),
        sa.Column(
            "replacement_policy_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "replacement_empty_set",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("target_family", scheduling_assignment_family, nullable=True),
        sa.Column("family_payload", postgresql.JSONB(), nullable=True),
        sa.Column("prior_family", scheduling_assignment_family, nullable=True),
        sa.Column(
            "prior_preferred_time_window_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("prior_new_rule_payload", postgresql.JSONB(), nullable=True),
        # Overlap / precedence (V4b-P3). Stable op ids, not array position.
        sa.Column(
            "replaces_op_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("addition_survives", sa.Boolean(), nullable=True),
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
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
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["availability_policies.id"],
            name="scheduling_day_scoped_ops_policy_fk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replacement_policy_id"],
            ["availability_policies.id"],
            name="scheduling_day_scoped_ops_replacement_policy_fk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prior_preferred_time_window_id"],
            ["focus_windows.id"],
            name="scheduling_day_scoped_ops_prior_map_fk",
            ondelete="SET NULL",
        ),
        # Single-column FK: composite (assignment_id, owner_id) + ON DELETE
        # SET NULL would null owner_id too and violate NOT NULL.
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["scheduling_assignments.id"],
            name="scheduling_day_scoped_ops_assignment_fk",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            """
            (selector_kind = 'one_date'
                AND civil_on_date IS NOT NULL
                AND civil_weekdays IS NULL
                AND civil_start_date IS NULL
                AND civil_end_date IS NULL)
            OR
            (selector_kind = 'weekday_standing'
                AND civil_weekdays IS NOT NULL
                AND civil_on_date IS NULL
                AND civil_start_date IS NULL
                AND civil_end_date IS NULL)
            OR
            (selector_kind = 'date_range'
                AND civil_start_date IS NOT NULL
                AND civil_end_date IS NOT NULL
                AND civil_on_date IS NULL
                AND civil_weekdays IS NULL
                AND civil_end_date >= civil_start_date)
            """,
            name="scheduling_day_scoped_ops_selector_shape",
        ),
        sa.CheckConstraint(
            """
            (payload_kind = 'none'
                AND policy_id IS NULL
                AND family_payload IS NULL)
            OR
            (payload_kind = 'empty'
                AND policy_id IS NULL
                AND family_payload IS NULL)
            OR
            (payload_kind = 'policy'
                AND policy_id IS NOT NULL
                AND family_payload IS NULL)
            OR
            (payload_kind = 'family'
                AND family_payload IS NOT NULL
                AND policy_id IS NULL)
            """,
            name="scheduling_day_scoped_ops_payload_shape",
        ),
        sa.CheckConstraint(
            """
            (op_kind = 'waive_named_scoped'
                AND target_rule_kind = 'must'
                AND payload_kind = 'none')
            OR (op_kind <> 'waive_named_scoped')
            """,
            name="scheduling_day_scoped_ops_waive_must_only",
        ),
        sa.CheckConstraint(
            """
            (op_kind = 'clear_scoped' AND payload_kind = 'none')
            OR (op_kind <> 'clear_scoped')
            """,
            name="scheduling_day_scoped_ops_clear_none_payload",
        ),
    )
    op.create_index(
        "idx_scheduling_day_scoped_ops_scope",
        "scheduling_day_scoped_ops",
        ["scope_kind", "scope_id"],
    )
    op.create_index(
        "idx_scheduling_day_scoped_ops_owner",
        "scheduling_day_scoped_ops",
        ["owner_id"],
    )
    op.create_index(
        "idx_scheduling_day_scoped_ops_kind",
        "scheduling_day_scoped_ops",
        ["op_kind"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_scheduling_day_scoped_ops_kind",
        table_name="scheduling_day_scoped_ops",
    )
    op.drop_index(
        "idx_scheduling_day_scoped_ops_owner",
        table_name="scheduling_day_scoped_ops",
    )
    op.drop_index(
        "idx_scheduling_day_scoped_ops_scope",
        table_name="scheduling_day_scoped_ops",
    )
    op.drop_table("scheduling_day_scoped_ops")
    bind = op.get_bind()
    scheduling_day_payload_kind.drop(bind, checkfirst=True)
    scheduling_day_selector_kind.drop(bind, checkfirst=True)
    scheduling_day_scoped_op_kind.drop(bind, checkfirst=True)
