"""Calendar conflict detection (W2a Slice 3).

Detects overlaps between external busy events (not mirrored push rows) and local
scheduled blocks, plus block↔block overlaps. Read-only flags — no task.status mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ExternalCalendarEvent, ScheduledBlock
from app.services.busy_intervals import overlap_interval


class ConflictKind(str, Enum):
    block_busy = "block_busy"
    block_block = "block_block"


@dataclass(frozen=True)
class Conflict:
    kind: ConflictKind
    block_id: UUID
    other_block_id: UUID | None
    external_event_id: UUID | None
    external_title: str | None
    start_time: datetime
    end_time: datetime
    is_pinned: bool


def find_conflicts(
    db: Session,
    owner_id: UUID,
    start: datetime,
    end: datetime,
) -> list[Conflict]:
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.start_time < end,
            ScheduledBlock.end_time > start,
        )
        .order_by(ScheduledBlock.start_time)
        .all()
    )

    busy_events = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner_id,
            ExternalCalendarEvent.scheduled_block_id.is_(None),
            ExternalCalendarEvent.start_time < end,
            ExternalCalendarEvent.end_time > start,
        )
        .order_by(ExternalCalendarEvent.start_time)
        .all()
    )

    conflicts: list[Conflict] = []

    for block in blocks:
        for event in busy_events:
            overlap = overlap_interval(
                block.start_time,
                block.end_time,
                event.start_time,
                event.end_time,
            )
            if overlap is None:
                continue
            conflicts.append(
                Conflict(
                    kind=ConflictKind.block_busy,
                    block_id=block.id,
                    other_block_id=None,
                    external_event_id=event.id,
                    external_title=event.title,
                    start_time=overlap[0],
                    end_time=overlap[1],
                    is_pinned=block.is_pinned,
                )
            )

    for i, block_a in enumerate(blocks):
        for block_b in blocks[i + 1 :]:
            overlap = overlap_interval(
                block_a.start_time,
                block_a.end_time,
                block_b.start_time,
                block_b.end_time,
            )
            if overlap is None:
                continue
            conflicts.append(
                Conflict(
                    kind=ConflictKind.block_block,
                    block_id=block_a.id,
                    other_block_id=block_b.id,
                    external_event_id=None,
                    external_title=None,
                    start_time=overlap[0],
                    end_time=overlap[1],
                    is_pinned=block_a.is_pinned,
                )
            )

    return conflicts
