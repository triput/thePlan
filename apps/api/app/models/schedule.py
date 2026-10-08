import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, desc, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import _uuid

# One in-flight replan per owner. Non-running rows stay out of the index.
ONE_RUNNING_PER_OWNER_INDEX = "uq_schedule_runs_one_running_per_owner"


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        Index("idx_schedule_runs_owner", "owner_id", desc("started_at")),
        Index(
            ONE_RUNNING_PER_OWNER_INDEX,
            "owner_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="running")
    tasks_scheduled: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    blocks_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    overbooked_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    stats_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
