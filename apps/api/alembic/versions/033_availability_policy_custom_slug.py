"""Custom availability policy slugs (DEF-040 Prefer path).

Revision ID: 033_custom_availability_slug
Revises: 032_scheduling_day_scoped_ops
Create Date: 2026-10-15

Replace Postgres enum ``availability_policy_slug`` with a varchar column so
owners can create additional policies (e.g. afternoon) under unique
(owner_id, slug). Seeded general/work/personal rows are unchanged.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033_custom_availability_slug"
down_revision: Union[str, None] = "032_scheduling_day_scoped_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SLUG_CHECK = "slug ~ '^[a-z][a-z0-9_]*$' AND char_length(slug) <= 64"


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE availability_policies "
            "ALTER COLUMN slug TYPE varchar(64) USING slug::text"
        )
    )
    op.create_check_constraint(
        "availability_policies_slug_format",
        "availability_policies",
        _SLUG_CHECK,
    )
    op.execute(sa.text("DROP TYPE IF EXISTS availability_policy_slug"))


def downgrade() -> None:
    op.drop_constraint(
        "availability_policies_slug_format",
        "availability_policies",
        type_="check",
    )
    op.execute(
        sa.text(
            "CREATE TYPE availability_policy_slug AS ENUM ('general', 'work', 'personal')"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE availability_policies "
            "ALTER COLUMN slug TYPE availability_policy_slug "
            "USING slug::availability_policy_slug"
        )
    )
