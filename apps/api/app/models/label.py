import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, _uuid


class Label(Base, TimestampMixin):
    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="labels_owner_name_unique"),
        CheckConstraint("name = lower(name)", name="labels_name_lowercase"),
        CheckConstraint("length(trim(name)) > 0", name="labels_name_nonempty"),
        Index("idx_labels_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#635F75")

    task_links: Mapped[list["TaskLabel"]] = relationship(
        back_populates="label",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TaskLabel(Base):
    __tablename__ = "task_labels"
    __table_args__ = (
        Index("idx_task_labels_label", "label_id"),
        Index("idx_task_labels_task", "task_id"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    task: Mapped["Task"] = relationship(back_populates="label_links")
    label: Mapped["Label"] = relationship(back_populates="task_links")
