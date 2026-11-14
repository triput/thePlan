# ==============================================================================
#  File: apps/api/app/models/scheduling_assignment.py
#  Description: S2-V4 new-rule assignment, named exceptions, revert payload.
#  Component: Scheduling / Settings — S2-V4
#  Version: 1.0
#  Created: 2026-10-13
#  Last Update: 2026-10-13
# ==============================================================================

"""Owner-scoped new-rule scheduling assignments. Not preferred_time_window_id."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import (
    SchedulingAssignmentFamily,
    SchedulingExceptionOp,
    SchedulingMayPresence,
    SchedulingRuleKind,
    SchedulingScopeKind,
)
from app.models.mixins import TimestampMixin, _uuid


class SchedulingAssignment(Base, TimestampMixin):
    __tablename__ = "scheduling_assignments"
    __table_args__ = (
        UniqueConstraint(
            "scope_kind",
            "scope_id",
            name="scheduling_assignments_scope_unique",
        ),
        UniqueConstraint(
            "id",
            "owner_id",
            name="scheduling_assignments_id_owner_unique",
        ),
        Index("idx_scheduling_assignments_owner", "owner_id"),
        Index("idx_scheduling_assignments_scope", "scope_kind", "scope_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scope_kind: Mapped[SchedulingScopeKind] = mapped_column(
        SAEnum(SchedulingScopeKind, name="scheduling_scope_kind", native_enum=True),
        nullable=False,
    )
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    may_presence: Mapped[SchedulingMayPresence] = mapped_column(
        SAEnum(SchedulingMayPresence, name="scheduling_may_presence", native_enum=True),
        nullable=False,
        server_default="omit",
    )

    rules: Mapped[list["SchedulingAssignmentRule"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by=lambda: (
            SchedulingAssignmentRule.sort_order,
            SchedulingAssignmentRule.name,
        ),
        foreign_keys="SchedulingAssignmentRule.assignment_id",
    )


class SchedulingAssignmentRule(Base, TimestampMixin):
    __tablename__ = "scheduling_assignment_rules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "owner_id"],
            ["scheduling_assignments.id", "scheduling_assignments.owner_id"],
            name="scheduling_assignment_rules_assignment_owner_fk",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["policy_id"],
            ["availability_policies.id"],
            name="scheduling_assignment_rules_policy_fk",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "assignment_id",
            "name",
            name="scheduling_assignment_rules_assignment_name_unique",
        ),
        CheckConstraint(
            "(empty_set AND policy_id IS NULL) OR (NOT empty_set AND policy_id IS NOT NULL)",
            name="scheduling_assignment_rules_content_xor",
        ),
        Index(
            "idx_scheduling_assignment_rules_assignment",
            "assignment_id",
            "sort_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[SchedulingRuleKind] = mapped_column(
        SAEnum(SchedulingRuleKind, name="scheduling_rule_kind", native_enum=True),
        nullable=False,
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    empty_set: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    assignment: Mapped[SchedulingAssignment] = relationship(
        back_populates="rules",
        foreign_keys=[assignment_id],
    )


class SchedulingRuleException(Base, TimestampMixin):
    __tablename__ = "scheduling_rule_exceptions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["replacement_policy_id"],
            ["availability_policies.id"],
            name="scheduling_rule_exceptions_policy_fk",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "scope_kind",
            "scope_id",
            "operation",
            "target_rule_name",
            name="scheduling_rule_exceptions_scope_op_target_unique",
        ),
        CheckConstraint(
            "(operation <> 'waive_named') OR (target_rule_kind = 'must')",
            name="scheduling_rule_exceptions_waive_must_only",
        ),
        CheckConstraint(
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
        Index("idx_scheduling_rule_exceptions_scope", "scope_kind", "scope_id"),
        Index("idx_scheduling_rule_exceptions_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scope_kind: Mapped[SchedulingScopeKind] = mapped_column(
        SAEnum(SchedulingScopeKind, name="scheduling_scope_kind", native_enum=True),
        nullable=False,
    )
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[SchedulingExceptionOp] = mapped_column(
        SAEnum(SchedulingExceptionOp, name="scheduling_exception_op", native_enum=True),
        nullable=False,
    )
    target_rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_rule_kind: Mapped[SchedulingRuleKind] = mapped_column(
        SAEnum(SchedulingRuleKind, name="scheduling_rule_kind", native_enum=True),
        nullable=False,
    )
    replacement_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replacement_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    replacement_empty_set: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class SchedulingAssignmentRevert(Base):
    """Prior local assignment captured by one identified family replace (V4-P2)."""

    __tablename__ = "scheduling_assignment_reverts"
    __table_args__ = (
        UniqueConstraint(
            "scope_kind",
            "scope_id",
            name="scheduling_assignment_reverts_scope_unique",
        ),
        Index("idx_scheduling_assignment_reverts_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scope_kind: Mapped[SchedulingScopeKind] = mapped_column(
        SAEnum(SchedulingScopeKind, name="scheduling_scope_kind", native_enum=True),
        nullable=False,
    )
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prior_family: Mapped[SchedulingAssignmentFamily] = mapped_column(
        SAEnum(
            SchedulingAssignmentFamily,
            name="scheduling_assignment_family",
            native_enum=True,
        ),
        nullable=False,
    )
    prior_preferred_time_window_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("focus_windows.id", ondelete="SET NULL"),
        nullable=True,
    )
    prior_new_rule_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
