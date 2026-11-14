"""Temporary Time Map overrides (F4) — Tesla owns CRUD/routes; scheduler reads these rows."""

from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import TimeMapBandTier
from app.models.mixins import TimestampMixin, _uuid


class TimeMapOverride(Base, TimestampMixin):
    __tablename__ = "time_map_overrides"
    __table_args__ = (
        CheckConstraint("local_end_date >= local_start_date", name="time_map_override_date_order"),
        Index("idx_time_map_overrides_map", "map_id"),
        Index("idx_time_map_overrides_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("focus_windows.id", ondelete="CASCADE"), nullable=False
    )
    local_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    local_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    strict_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    bands: Mapped[list["TimeMapOverrideBand"]] = relationship(
        back_populates="override",
        cascade="all, delete-orphan",
        order_by="TimeMapOverrideBand.sort_order",
    )


class TimeMapOverrideBand(Base):
    __tablename__ = "time_map_override_bands"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="time_map_override_band_time_order"),
        Index("idx_time_map_override_bands_override", "override_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    override_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("time_map_overrides.id", ondelete="CASCADE"), nullable=False
    )
    tier: Mapped[TimeMapBandTier] = mapped_column(
        SAEnum(
            TimeMapBandTier,
            name="time_map_band_tier",
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    days_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="127")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    override: Mapped["TimeMapOverride"] = relationship(back_populates="bands")
