"""T2-REC: recovery epoch membership, disposition recovery fields, correction audit.

Revision ID: 043_recovery_epoch
Revises: 042_task_occurrence_dispositions
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "043_recovery_epoch"
down_revision: Union[str, None] = "042_task_occurrence_dispositions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_occurrence_dispositions",
        sa.Column("catch_up_task_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "task_occurrence_dispositions",
        sa.Column("miss_era_worked_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_occurrence_dispositions",
        sa.Column("miss_era_remaining_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_occurrence_dispositions",
        sa.Column("miss_era_estimated_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_occurrence_dispositions",
        sa.Column("miss_era_entry_ids", JSONB, nullable=True),
    )
    op.add_column(
        "task_occurrence_dispositions",
        sa.Column("authorize_instant", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_task_occurrence_dispositions_catch_up_task",
        "task_occurrence_dispositions",
        "tasks",
        ["catch_up_task_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "task_occurrence_dispositions_catch_up_ne_task",
        "task_occurrence_dispositions",
        "catch_up_task_id IS NULL OR catch_up_task_id <> task_id",
    )
    op.create_check_constraint(
        "task_occurrence_dispositions_recovered_implies_snapshot",
        "task_occurrence_dispositions",
        "resolution <> 'recovered' OR ("
        "catch_up_task_id IS NOT NULL AND "
        "miss_era_worked_minutes IS NOT NULL AND "
        "miss_era_estimated_minutes IS NOT NULL AND "
        "miss_era_entry_ids IS NOT NULL"
        ")",
    )

    op.create_table(
        "progress_epoch_membership",
        sa.Column("progress_entry_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "disposition_id",
            UUID(as_uuid=True),
            sa.ForeignKey("task_occurrence_dispositions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["progress_entry_id", "task_id", "owner_id"],
            [
                "task_progress_entries.id",
                "task_progress_entries.task_id",
                "task_progress_entries.owner_id",
            ],
            name="fk_progress_epoch_membership_entry_task_owner",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_progress_epoch_membership_disposition",
        "progress_epoch_membership",
        ["disposition_id"],
    )

    op.create_table(
        "disposition_correction_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "disposition_id",
            UUID(as_uuid=True),
            sa.ForeignKey("task_occurrence_dispositions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("task_progress_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "new_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("task_progress_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Append-only: corrections insert a new audit row. DELETE stays legal so
    # disposition ON DELETE CASCADE can remove audits with the disposition.
    op.execute(
        sa.text(
            """
            CREATE FUNCTION disposition_correction_audits_append_only()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'disposition_correction_audits is append-only';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER disposition_correction_audits_append_only
            BEFORE UPDATE ON disposition_correction_audits
            FOR EACH ROW
            EXECUTE FUNCTION disposition_correction_audits_append_only()
            """
        )
    )

    op.drop_constraint(
        "task_progress_entries_minutes_positive",
        "task_progress_entries",
        type_="check",
    )
    op.create_check_constraint(
        "task_progress_entries_minutes_positive",
        "task_progress_entries",
        "(corrects_entry_id IS NULL AND minutes_worked > 0) OR "
        "(corrects_entry_id IS NOT NULL AND minutes_worked >= 0)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "task_progress_entries_minutes_positive",
        "task_progress_entries",
        type_="check",
    )
    op.create_check_constraint(
        "task_progress_entries_minutes_positive",
        "task_progress_entries",
        "minutes_worked > 0",
    )

    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS disposition_correction_audits_append_only "
            "ON disposition_correction_audits"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS disposition_correction_audits_append_only()")
    )
    op.drop_table("disposition_correction_audits")

    op.drop_index(
        "idx_progress_epoch_membership_disposition",
        table_name="progress_epoch_membership",
    )
    op.drop_table("progress_epoch_membership")

    op.drop_constraint(
        "task_occurrence_dispositions_recovered_implies_snapshot",
        "task_occurrence_dispositions",
        type_="check",
    )
    op.drop_constraint(
        "task_occurrence_dispositions_catch_up_ne_task",
        "task_occurrence_dispositions",
        type_="check",
    )
    op.drop_constraint(
        "fk_task_occurrence_dispositions_catch_up_task",
        "task_occurrence_dispositions",
        type_="foreignkey",
    )
    op.drop_column("task_occurrence_dispositions", "authorize_instant")
    op.drop_column("task_occurrence_dispositions", "miss_era_entry_ids")
    op.drop_column("task_occurrence_dispositions", "miss_era_estimated_minutes")
    op.drop_column("task_occurrence_dispositions", "miss_era_remaining_minutes")
    op.drop_column("task_occurrence_dispositions", "miss_era_worked_minutes")
    op.drop_column("task_occurrence_dispositions", "catch_up_task_id")
