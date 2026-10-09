"""Owner-scoped idempotency receipts for bulk handoff apply (F1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import _uuid

HANDOFF_APPLY_KIND = "handoff_apply"
TEMPLATE_APPLY_KIND = "template_apply"


class HandoffReceipt(Base):
    __tablename__ = "handoff_receipts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "operation_kind",
            "idempotency_key",
            name="uq_handoff_receipts_owner_op_key",
        ),
        Index("idx_handoff_receipts_owner", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    operation_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
