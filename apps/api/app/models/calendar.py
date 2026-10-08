import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.models.mixins import TimestampMixin, _uuid


class CalendarAccount(Base, TimestampMixin):
    __tablename__ = "calendar_accounts"
    __table_args__ = (
        UniqueConstraint("owner_id", "provider", "account_email", name="calendar_accounts_owner_provider_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[CalendarProvider] = mapped_column(
        SAEnum(CalendarProvider, name="calendar_provider", native_enum=True), nullable=False
    )
    account_email: Mapped[str | None] = mapped_column(String(255))
    access_token_enc: Mapped[str | None] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column()
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    mirror_blocks: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_synced_at: Mapped[datetime | None] = mapped_column()

    subscriptions: Mapped[list["CalendarSubscription"]] = relationship(
        back_populates="calendar_account",
        cascade="all, delete-orphan",
    )


class CalendarSubscription(Base, TimestampMixin):
    __tablename__ = "calendar_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "calendar_account_id",
            "external_calendar_id",
            name="calendar_subscriptions_account_calendar_unique",
        ),
        Index("idx_calendar_subscriptions_account", "calendar_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    calendar_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_accounts.id", ondelete="CASCADE"), nullable=False
    )
    external_calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[CalendarSubscriptionRole] = mapped_column(
        SAEnum(CalendarSubscriptionRole, name="calendar_subscription_role", native_enum=True),
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sync_cursor: Mapped[str | None] = mapped_column(Text)

    calendar_account: Mapped["CalendarAccount"] = relationship(back_populates="subscriptions")


class ExternalCalendarEvent(Base):
    __tablename__ = "external_calendar_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="unique_external_event"),
        Index("idx_external_events_account", "calendar_account_id"),
        Index("idx_external_events_time", "start_time", "end_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    calendar_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_accounts.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    scheduled_block_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_blocks.id", ondelete="SET NULL")
    )
    provider: Mapped[CalendarProvider] = mapped_column(
        SAEnum(CalendarProvider, name="calendar_provider", native_enum=True), nullable=False
    )
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sync_hash: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime] = mapped_column(server_default=func.now())
