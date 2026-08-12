"""W2b Plans: named soft time frames + task.plan_id.

Revision ID: 007_plans
Revises: 006_settings_expansion
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_plans"
down_revision: Union[str, None] = "006_settings_expansion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("soft_target_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_plans_owner", "plans", ["owner_id"])
    op.create_index("idx_plans_owner_name", "plans", ["owner_id", "name"])

    op.add_column(
        "tasks",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "tasks_plan_id_fkey",
        "tasks",
        "plans",
        ["plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_tasks_owner_plan", "tasks", ["owner_id", "plan_id"])


def downgrade() -> None:
    op.drop_index("idx_tasks_owner_plan", table_name="tasks")
    op.drop_constraint("tasks_plan_id_fkey", "tasks", type_="foreignkey")
    op.drop_column("tasks", "plan_id")
    op.drop_index("idx_plans_owner_name", table_name="plans")
    op.drop_index("idx_plans_owner", table_name="plans")
    op.drop_table("plans")
