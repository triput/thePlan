# ==============================================================================
#  File: apps/api/app/models/scheduling_day_scoped.py
#  Description: S2-V4b day-scoped ops storage (Change / Only-allow / scoped family+rules).
#  Component: Scheduling / Settings — S2-V4b
#  Version: 1.0
#  Created: 2026-10-14
#  Last Update: 2026-10-14
# ==============================================================================

"""Day-scoped scheduling ops — storage contract for writers and Tesla resolve.

Sibling table to ``scheduling_rule_exceptions``. **Not** ``time_map_overrides``,
**not** ``preferred_time_window_id``, **not** standing exception rows.

Tesla loads these rows to fold into effective windows **after** standing
``resolve_effective_composition`` and **before** May union / Must intersect /
Prefer rank (``composition_search_windows``). Jules owns writers; Tesla owns
resolution / fingerprint hashing.

Column contract
---------------
``id``
    Stable identity for targeted removal (``rule.remove_named_scoped``) and
    overlap which-replaces-which targets.

``owner_id``, ``scope_kind``, ``scope_id``
    One of task / project / epic. Same scope vocabulary as V4 assignments.

``op_kind``
    Stored kinds: ``change_selected``, ``only_allow``, ``family_replace_scoped``,
    ``clear_scoped``, ``add_scoped``, ``replace_named_scoped``,
    ``waive_named_scoped``. Discovery stubs map by stripping the ``day.`` /
    ``assignment.`` / ``rule.`` prefix and ``_scoped`` where already present.

``selector_kind`` + civil label columns
    Civil labels in the **configured schedule timezone** (R3). Not fixed
    instants. A schedule-timezone change re-reads these labels; it does not
    rebase through old UTC bounds.

    - ``one_date`` → ``civil_on_date`` only
    - ``weekday_standing`` → ``civil_weekdays`` (Mon=0 … Sun=6), until removal
      unless ``expires_at`` is set
    - ``date_range`` → ``civil_start_date`` / ``civil_end_date`` inclusive
      **last selected occurrence dates** (not lifetime end for Change; R1)

``expires_at``
    Optional **fixed UTC instant** (preserve-instant). Distinct from the last
    selected occurrence date. Only this clips an overnight Change tail. Two
    contradictory instant ends reject at write time (no row).

``payload_kind`` + content
    Distinct omit / empty / windows:

    - ``none`` — clear_scoped / waive_named_scoped (no windows)
    - ``empty`` — explicit empty set (active empty; no General fall-through)
    - ``policy`` — ``policy_id`` set (Change / Only-allow / named add windows)
    - ``family`` — ``family_payload`` JSONB for scoped family replace target

Named-rule fields
    ``rule_name`` / ``rule_kind`` for ``add_scoped``.
    ``target_rule_name`` / ``target_rule_kind`` (+ replacement_* for replace).

Family scoped
    ``target_family``, ``family_payload``, plus ``prior_*`` snapshot for
    ``assignment.revert_scoped`` (captured prior; not the clear-expiry path).

``clear_scoped``
    Suppression only. Does **not** delete standing local assignment. On
    expiry/removal Tesla lifts suppression and resolves the **complete current
    stack including current local** (R2: B→A→B2). Writers store/delete the row.

Overlap / precedence (V4b-P3)
    ``replaces_op_ids`` — explicit which-replaces-which (stable ids).
    ``addition_survives`` — explicit addition-over-replacement choice; null
    when not applicable. Missing choice on overlap → atomic reject, no write.

``assignment_id``
    Optional link to the new-rule assignment at write time (nullable SET NULL
    if assignment later cleared). Fingerprint / resolve may still key by scope.

Fingerprint note (Tesla)
    Civil label columns vs ``expires_at`` must stay distinguishable in the
    composition hash (R3). Do not fold these rows into ``time_map_overrides``
    or ``availability`` hours.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import (
    SchedulingAssignmentFamily,
    SchedulingDayPayloadKind,
    SchedulingDayScopedOpKind,
    SchedulingDaySelectorKind,
    SchedulingRuleKind,
    SchedulingScopeKind,
)
from app.models.mixins import TimestampMixin, _uuid


class SchedulingDayScopedOp(Base, TimestampMixin):
    __tablename__ = "scheduling_day_scoped_ops"
    __table_args__ = (
        ForeignKeyConstraint(
            ["policy_id"],
            ["availability_policies.id"],
            name="scheduling_day_scoped_ops_policy_fk",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["replacement_policy_id"],
            ["availability_policies.id"],
            name="scheduling_day_scoped_ops_replacement_policy_fk",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["prior_preferred_time_window_id"],
            ["focus_windows.id"],
            name="scheduling_day_scoped_ops_prior_map_fk",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["assignment_id"],
            ["scheduling_assignments.id"],
            name="scheduling_day_scoped_ops_assignment_fk",
            ondelete="SET NULL",
        ),
        CheckConstraint(
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
        CheckConstraint(
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
        CheckConstraint(
            """
            (op_kind = 'waive_named_scoped'
                AND target_rule_kind = 'must'
                AND payload_kind = 'none')
            OR (op_kind <> 'waive_named_scoped')
            """,
            name="scheduling_day_scoped_ops_waive_must_only",
        ),
        CheckConstraint(
            """
            (op_kind = 'clear_scoped' AND payload_kind = 'none')
            OR (op_kind <> 'clear_scoped')
            """,
            name="scheduling_day_scoped_ops_clear_none_payload",
        ),
        Index("idx_scheduling_day_scoped_ops_scope", "scope_kind", "scope_id"),
        Index("idx_scheduling_day_scoped_ops_owner", "owner_id"),
        Index("idx_scheduling_day_scoped_ops_kind", "op_kind"),
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
    op_kind: Mapped[SchedulingDayScopedOpKind] = mapped_column(
        SAEnum(
            SchedulingDayScopedOpKind,
            name="scheduling_day_scoped_op_kind",
            native_enum=True,
        ),
        nullable=False,
    )
    selector_kind: Mapped[SchedulingDaySelectorKind] = mapped_column(
        SAEnum(
            SchedulingDaySelectorKind,
            name="scheduling_day_selector_kind",
            native_enum=True,
        ),
        nullable=False,
    )
    civil_on_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    civil_weekdays: Mapped[list[int] | None] = mapped_column(
        ARRAY(SmallInteger), nullable=True
    )
    civil_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    civil_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload_kind: Mapped[SchedulingDayPayloadKind] = mapped_column(
        SAEnum(
            SchedulingDayPayloadKind,
            name="scheduling_day_payload_kind",
            native_enum=True,
        ),
        nullable=False,
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    rule_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rule_kind: Mapped[SchedulingRuleKind | None] = mapped_column(
        SAEnum(SchedulingRuleKind, name="scheduling_rule_kind", native_enum=True),
        nullable=True,
    )
    target_rule_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_rule_kind: Mapped[SchedulingRuleKind | None] = mapped_column(
        SAEnum(SchedulingRuleKind, name="scheduling_rule_kind", native_enum=True),
        nullable=True,
    )
    replacement_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replacement_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    replacement_empty_set: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    target_family: Mapped[SchedulingAssignmentFamily | None] = mapped_column(
        SAEnum(
            SchedulingAssignmentFamily,
            name="scheduling_assignment_family",
            native_enum=True,
        ),
        nullable=True,
    )
    family_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    prior_family: Mapped[SchedulingAssignmentFamily | None] = mapped_column(
        SAEnum(
            SchedulingAssignmentFamily,
            name="scheduling_assignment_family",
            native_enum=True,
        ),
        nullable=True,
    )
    prior_preferred_time_window_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    prior_new_rule_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    replaces_op_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    addition_survives: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
