"""Allow workweek_days = 0 (empty Working, no Working days).

Revision ID: 029_workweek_days_allow_zero
Revises: 028_availability_progress
Create Date: 2026-10-12

S0 stores an empty Working policy as ``workweek_days = 0``. The 001 check
``workweek_days BETWEEN 1 AND 7`` (Postgres name
``user_settings_workweek_days_check``) rejected that write with IntegrityError.
This replaces that check with ``BETWEEN 0 AND 7``. Existing 1–7 rows stay.
Downgrade refuses to restore 1–7 while any row still holds 0.
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_workweek_days_allow_zero"
down_revision: Union[str, None] = "028_availability_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CHECK_NAME = "user_settings_workweek_days_check"


def _workweek_check_names() -> list[str]:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            WHERE rel.relname = 'user_settings'
              AND rel.relnamespace = 'public'::regnamespace
              AND con.contype = 'c'
            """
        )
    ).all()
    names: list[str] = []
    for name, definition in rows:
        if "workweek_days" not in definition.lower() and name != _CHECK_NAME:
            continue
        if not _IDENTIFIER.fullmatch(name):
            raise RuntimeError(f"unexpected user_settings check constraint name: {name!r}")
        names.append(name)
    return names


def upgrade() -> None:
    names = _workweek_check_names()
    if not names:
        raise RuntimeError(
            "user_settings has no workweek_days check to replace; "
            f"expected {_CHECK_NAME} from 001"
        )
    for name in names:
        op.drop_constraint(name, "user_settings", type_="check")
    op.create_check_constraint(
        _CHECK_NAME,
        "user_settings",
        "workweek_days BETWEEN 0 AND 7",
    )


def downgrade() -> None:
    conn = op.get_bind()
    zeros = conn.execute(
        sa.text("SELECT COUNT(*) FROM user_settings WHERE workweek_days = 0")
    ).scalar()
    if zeros:
        raise RuntimeError(
            "cannot restore workweek_days BETWEEN 1 AND 7 while "
            f"{zeros} user_settings row(s) store 0"
        )
    names = _workweek_check_names()
    for name in names:
        op.drop_constraint(name, "user_settings", type_="check")
    op.create_check_constraint(
        _CHECK_NAME,
        "user_settings",
        "workweek_days BETWEEN 1 AND 7",
    )
