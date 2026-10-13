import uuid
from datetime import time
from typing import Any

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ScheduleStyle
from app.models.mixins import TimestampMixin, _uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    username: Mapped[str | None] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Bumped to revoke every session cookie minted at an older epoch.
    session_epoch: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )

    settings: Mapped["UserSettings"] = relationship(back_populates="owner", uselist=False)
    saved_filters: Mapped[list["SavedFilter"]] = relationship(back_populates="owner")
    availability_policies: Mapped[list["AvailabilityPolicy"]] = relationship(
        back_populates="owner",
        order_by="AvailabilityPolicy.sort_order",
    )


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en-US")
    workday_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="480")
    # Nominal effort conversion. Not an availability window and not a fingerprint input.
    nominal_workday_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=480, server_default="480"
    )
    workday_start_local: Mapped[time] = mapped_column(
        Time, nullable=False, server_default="08:00:00"
    )
    # Monday-first count, 0–7. Zero is an empty Working policy: no Working days.
    workweek_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    inter_block_buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    ups_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default='{"Wp": 0.35, "Wu": 0.40, "Wd": 0.15, "We": 0.10, "k": 0.5}',
    )
    upcoming_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    default_estimated_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )
    default_min_block_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="15"
    )
    default_max_block_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120, server_default="120"
    )
    # User-level No limit. Distinct from a null task max (inherit) and from 0.
    default_max_block_unbounded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    default_schedule_style: Mapped[ScheduleStyle] = mapped_column(
        SAEnum(ScheduleStyle, name="schedule_style", native_enum=True),
        nullable=False,
        server_default="standalone",
    )
    auto_defer_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    max_auto_schedule_minutes_per_project_per_day: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # Bumped when schedule-affecting domain rows commit (F6 apply + direct replan).
    scheduling_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    owner: Mapped["User"] = relationship(back_populates="settings")


class SavedFilter(Base, TimestampMixin):
    __tablename__ = "saved_filters"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="saved_filters_owner_slug_unique"),
        Index("idx_saved_filters_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    predicate_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    presentation_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    owner: Mapped["User"] = relationship(back_populates="saved_filters")
