"""Persisted free/busy series exception policy (T1-4a)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import CalendarProvider
from app.models.mixins import TimestampMixin, _uuid


class FreeBusySeriesPolicy(Base, TimestampMixin):
    __tablename__ = "free_busy_series_policies"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "provider",
            "calendar_id",
            "provider_series_id",
            name="uq_free_busy_series_policies_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[CalendarProvider] = mapped_column(
        SAEnum(CalendarProvider, name="calendar_provider", native_enum=True), nullable=False
    )
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_series_id: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    decision_source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual_resolve")
    acknowledged_calendar_id: Mapped[str | None] = mapped_column(String(255))
    acknowledged_series_id: Mapped[str | None] = mapped_column(String(255))
    acknowledged_provider_transparency: Mapped[str | None] = mapped_column(String(32))
    acknowledged_provider_provenance: Mapped[str | None] = mapped_column(String(64))
    conflict_pending_latched: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    latch_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    decisions: Mapped[list["FreeBusySeriesPolicyDecision"]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
    )


class FreeBusySeriesPolicyDecision(Base):
    __tablename__ = "free_busy_series_policy_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("free_busy_series_policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    decided_at: Mapped[datetime] = mapped_column(nullable=False)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    mapping: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_source: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    supersedes_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("free_busy_series_policy_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    policy: Mapped["FreeBusySeriesPolicy"] = relationship(back_populates="decisions")


class FreeBusyOccurrenceBaseline(Base):
    __tablename__ = "free_busy_occurrence_baselines"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "provider",
            "external_event_id",
            name="uq_free_busy_occurrence_baselines_event",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[CalendarProvider] = mapped_column(
        SAEnum(CalendarProvider, name="calendar_provider", native_enum=True), nullable=False
    )
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    transparency: Mapped[str | None] = mapped_column(String(32))
    free_busy_provenance: Mapped[str | None] = mapped_column(String(64))
    occupancy_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
