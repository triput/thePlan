"""W3 Slice 2: rename calendar_accounts.mirror_blocks_to_google → mirror_blocks.

Revision ID: 011_mirror_blocks
Revises: 010_must_change_password
Create Date: 2026-08-14
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "011_mirror_blocks"
down_revision: Union[str, None] = "010_must_change_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "calendar_accounts",
        "mirror_blocks_to_google",
        new_column_name="mirror_blocks",
    )


def downgrade() -> None:
    op.alter_column(
        "calendar_accounts",
        "mirror_blocks",
        new_column_name="mirror_blocks_to_google",
    )
