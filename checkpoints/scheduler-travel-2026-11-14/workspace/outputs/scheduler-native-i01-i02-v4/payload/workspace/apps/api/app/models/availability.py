"""Owner-scoped availability policies. Not focus_windows / Time Maps.

Weekday is Python ``date.weekday()`` (Monday = 0), the same index as
``workweek_days``. Window times are wall-clock in ``user_settings.timezone``;
there is no per-policy zone column. ``duration_minutes`` is the half-open
length ``[start_time, start_time + duration)``. ``ends_next_day`` is true when
that interval reaches or passes the next midnight, including a 24h span whose
clock times match. Equal clock times with ``ends_next_day`` false are rejected.
"""

from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, _uuid

# Lockstep with 028_availability_progress INSERT/CHECK expressions.
# Extra parentheses keep `ends_next_day = (expr >= 86400)` valid in Postgres.
_OVERNIGHT_SQL = (
    "((EXTRACT(EPOCH FROM start_time) + duration_minutes::bigint * 60) >= 86400)"
)
_END_SQL = "(start_time + make_interval(mins => duration_minutes))::time"


class AvailabilityPolicy(Base, TimestampMixin):
    __tablename__ = "availability_policies"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="availability_policies_owner_slug_unique"),
        # Composite target so a window cannot pair this policy with another owner.
        UniqueConstraint("id", "owner_id", name="availability_policies_id_owner_unique"),
        Index("idx_availability_policies_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    owner: Mapped["User"] = relationship(back_populates="availability_policies")
    windows: Mapped[list[AvailabilityWindow]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by=lambda: (AvailabilityWindow.weekday, AvailabilityWindow.sort_order),
        foreign_keys="AvailabilityWindow.policy_id",
    )


class AvailabilityWindow(Base, TimestampMixin):
    __tablename__ = "availability_windows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["policy_id", "owner_id"],
            ["availability_policies.id", "availability_policies.owner_id"],
            name="availability_windows_policy_owner_fk",
            ondelete="CASCADE",
        ),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="availability_windows_weekday"),
        CheckConstraint(
            "duration_minutes > 0",
            name="availability_windows_duration_positive",
        ),
        CheckConstraint(
            f"ends_next_day = {_OVERNIGHT_SQL}",
            name="availability_windows_overnight_flag",
        ),
        CheckConstraint(
            f"end_time = {_END_SQL}",
            name="availability_windows_end_matches_duration",
        ),
        Index("idx_availability_windows_policy_day", "policy_id", "weekday", "sort_order"),
        Index("idx_availability_windows_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # policy_id has no single-column FK. The composite constraint below is the
    # only cascade path (policy delete -> windows) so Postgres does not see two
    # ON DELETE CASCADE routes to the same row.
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    ends_next_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    policy: Mapped[AvailabilityPolicy] = relationship(
        back_populates="windows",
        foreign_keys="AvailabilityWindow.policy_id",
    )
