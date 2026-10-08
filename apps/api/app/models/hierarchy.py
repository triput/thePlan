import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, Enum as SAEnum, ForeignKey, Index, Integer, SmallInteger, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ScheduleStyle, TimeMapBandTier
from app.models.mixins import TimestampMixin, _uuid


class Epic(Base, TimestampMixin):
    __tablename__ = "epics"
    __table_args__ = (
        Index("idx_epics_owner", "owner_id"),
        Index("idx_epics_owner_archived", "owner_id", "is_archived"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#6D3FC9")
    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    preferred_time_window_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("focus_windows.id", ondelete="SET NULL")
    )
    schedule_style: Mapped[ScheduleStyle | None] = mapped_column(
        SAEnum(ScheduleStyle, name="schedule_style", native_enum=True),
        nullable=True,
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="epic")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        Index("idx_projects_owner", "owner_id"),
        Index("idx_projects_epic", "epic_id"),
        Index("idx_projects_owner_archived", "owner_id", "is_archived"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    epic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("epics.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#0A8558")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    preferred_time_window_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("focus_windows.id", ondelete="SET NULL")
    )
    schedule_style: Mapped[ScheduleStyle | None] = mapped_column(
        SAEnum(ScheduleStyle, name="schedule_style", native_enum=True),
        nullable=True,
    )

    epic: Mapped["Epic | None"] = relationship(back_populates="projects")
    sections: Mapped[list["Section"]] = relationship(back_populates="project")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Section(Base, TimestampMixin):
    __tablename__ = "sections"
    __table_args__ = (
        Index("idx_sections_project", "project_id"),
        Index("idx_sections_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    project: Mapped["Project"] = relationship(back_populates="sections")
    tasks: Mapped[list["Task"]] = relationship(back_populates="section")


class FocusWindow(Base, TimestampMixin):
    __tablename__ = "focus_windows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    strict_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    bands: Mapped[list["TimeMapBand"]] = relationship(
        back_populates="map",
        cascade="all, delete-orphan",
        order_by="TimeMapBand.sort_order",
    )


class TimeMapBand(Base):
    __tablename__ = "time_map_bands"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="time_map_band_time_order"),
        Index("idx_time_map_bands_map", "map_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("focus_windows.id", ondelete="CASCADE"), nullable=False
    )
    tier: Mapped[TimeMapBandTier] = mapped_column(
        SAEnum(TimeMapBandTier, name="time_map_band_tier", native_enum=True),
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    days_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="127")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    map: Mapped["FocusWindow"] = relationship(back_populates="bands")


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"
    __table_args__ = (
        Index("idx_plans_owner", "owner_id"),
        Index("idx_plans_owner_name", "owner_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    soft_target_at: Mapped[datetime | None] = mapped_column()
