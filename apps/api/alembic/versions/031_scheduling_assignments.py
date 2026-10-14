"""S2-V4 new-rule scheduling assignments, named exceptions, revert payload.

Revision ID: 031_scheduling_assignments
Revises: 030_progress_intent_hash
Create Date: 2026-10-13

Additive only. Does not reuse tasks.source_refs, preferred_time_window_id, or
time_map_overrides. Does not bump scheduling_revision or activate household.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "031_scheduling_assignments"
down_revision: Union[str, None] = "030_progress_intent_hash"
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
scheduling_may_presence = postgresql.ENUM(
    "omit",
    "explicit",
    name="scheduling_may_presence",
    create_type=False,
)
scheduling_assignment_family = postgresql.ENUM(
    "none",
    "legacy",
    "new_rule",
    name="scheduling_assignment_family",
    create_type=False,
)
scheduling_exception_op = postgresql.ENUM(
    "replace_named",
    "waive_named",
    name="scheduling_exception_op",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    scheduling_scope_kind.create(bind, checkfirst=True)
    scheduling_rule_kind.create(bind, checkfirst=True)
    scheduling_may_presence.create(bind, checkfirst=True)
    scheduling_assignment_family.create(bind, checkfirst=True)
    scheduling_exception_op.create(bind, checkfirst=True)

    op.create_table(
        "scheduling_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_kind", scheduling_scope_kind, nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "may_presence",
            scheduling_may_presence,
            nullable=False,
            server_default="omit",
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
        sa.UniqueConstraint(
            "scope_kind",
            "scope_id",
            name="scheduling_assignments_scope_unique",
        ),
        sa.UniqueConstraint(
            "id",
            "owner_id",
            name="scheduling_assignments_id_owner_unique",
        ),
    )
    op.create_index(
        "idx_scheduling_assignments_owner",
        "scheduling_assignments",
        ["owner_id"],
    )
    op.create_index(
        "idx_scheduling_assignments_scope",
        "scheduling_assignments",
        ["scope_kind", "scope_id"],
    )

    op.create_table(
        "scheduling_assignment_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", scheduling_rule_kind, nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "empty_set",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
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
            ["assignment_id", "owner_id"],
            ["scheduling_assignments.id", "scheduling_assignments.owner_id"],
            name="scheduling_assignment_rules_assignment_owner_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["availability_policies.id"],
            name="scheduling_assignment_rules_policy_fk",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "name",
            name="scheduling_assignment_rules_assignment_name_unique",
        ),
        sa.CheckConstraint(
            "(empty_set AND policy_id IS NULL) OR (NOT empty_set AND policy_id IS NOT NULL)",
            name="scheduling_assignment_rules_content_xor",
        ),
    )
    op.create_index(
        "idx_scheduling_assignment_rules_assignment",
        "scheduling_assignment_rules",
        ["assignment_id", "sort_order"],
    )

    op.create_table(
        "scheduling_rule_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_kind", scheduling_scope_kind, nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", scheduling_exception_op, nullable=False),
        sa.Column("target_rule_name", sa.String(length=100), nullable=False),
        sa.Column("target_rule_kind", scheduling_rule_kind, nullable=False),
        sa.Column("replacement_name", sa.String(length=100), nullable=True),
        sa.Column("replacement_policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "replacement_empty_set",
            sa.Boolean(),
            nullable=False,
            server_default="false",
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
            ["replacement_policy_id"],
            ["availability_policies.id"],
            name="scheduling_rule_exceptions_policy_fk",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "scope_kind",
            "scope_id",
            "operation",
            "target_rule_name",
            name="scheduling_rule_exceptions_scope_op_target_unique",
        ),
        sa.CheckConstraint(
            "(operation <> 'waive_named') OR (target_rule_kind = 'must')",
            name="scheduling_rule_exceptions_waive_must_only",
        ),
        sa.CheckConstraint(
            """
            (operation = 'waive_named'
                AND replacement_name IS NULL
                AND replacement_policy_id IS NULL
                AND replacement_empty_set = false)
            OR
            (operation = 'replace_named'
                AND replacement_name IS NOT NULL
                AND (
                    (replacement_empty_set AND replacement_policy_id IS NULL)
                    OR (NOT replacement_empty_set AND replacement_policy_id IS NOT NULL)
                ))
            """,
            name="scheduling_rule_exceptions_op_payload",
        ),
    )
    op.create_index(
        "idx_scheduling_rule_exceptions_scope",
        "scheduling_rule_exceptions",
        ["scope_kind", "scope_id"],
    )
    op.create_index(
        "idx_scheduling_rule_exceptions_owner",
        "scheduling_rule_exceptions",
        ["owner_id"],
    )

    op.create_table(
        "scheduling_assignment_reverts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_kind", scheduling_scope_kind, nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prior_family", scheduling_assignment_family, nullable=False),
        sa.Column(
            "prior_preferred_time_window_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("focus_windows.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prior_new_rule_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "scope_kind",
            "scope_id",
            name="scheduling_assignment_reverts_scope_unique",
        ),
    )
    op.create_index(
        "idx_scheduling_assignment_reverts_owner",
        "scheduling_assignment_reverts",
        ["owner_id"],
    )


def downgrade() -> None:
    op.drop_table("scheduling_assignment_reverts")
    op.drop_table("scheduling_rule_exceptions")
    op.drop_table("scheduling_assignment_rules")
    op.drop_table("scheduling_assignments")
    bind = op.get_bind()
    scheduling_exception_op.drop(bind, checkfirst=True)
    scheduling_assignment_family.drop(bind, checkfirst=True)
    scheduling_may_presence.drop(bind, checkfirst=True)
    scheduling_rule_kind.drop(bind, checkfirst=True)
    scheduling_scope_kind.drop(bind, checkfirst=True)
