"""DEF-019 / ADR-012: manual calendar bundle blocks (aggregate face, member ids in JSONB)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import ScheduledBlock, Task, User
from app.services.task_helpers import collect_live_descendant_ids

BundleSource = Literal["selection", "parent_subtree"]

_MIN_BUNDLE_MINUTES = 15


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _owned_live_tasks(db: Session, task_ids: list[uuid.UUID], user: User) -> list[Task]:
    if not task_ids:
        return []
    rows = (
        db.query(Task)
        .filter(
            Task.owner_id == user.id,
            Task.id.in_(task_ids),
            Task.deleted_at.is_(None),
        )
        .all()
    )
    by_id = {row.id: row for row in rows}
    missing = [tid for tid in task_ids if tid not in by_id]
    if missing:
        raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
    # Preserve caller order
    return [by_id[tid] for tid in task_ids]


def build_bundle_meta(
    *,
    member_task_ids: list[uuid.UUID],
    source: BundleSource,
) -> dict[str, Any]:
    return {
        "kind": "bundle",
        "member_task_ids": [str(tid) for tid in member_task_ids],
        "source": source,
    }


def resolve_bundle_membership(
    db: Session,
    user: User,
    *,
    member_task_ids: list[uuid.UUID] | None,
    parent_task_id: uuid.UUID | None,
) -> tuple[uuid.UUID, list[uuid.UUID], BundleSource]:
    """Return (anchor_task_id, member_ids, source)."""
    if parent_task_id is not None and member_task_ids:
        raise ApiError(
            422,
            "Provide either parent_task_id or member_task_ids, not both",
            "BUNDLE_SOURCE_CONFLICT",
        )
    if parent_task_id is None and not member_task_ids:
        raise ApiError(
            422,
            "Provide parent_task_id or member_task_ids",
            "BUNDLE_MEMBERS_REQUIRED",
        )

    if parent_task_id is not None:
        parent = db.get(Task, parent_task_id)
        if parent is None or parent.owner_id != user.id or parent.deleted_at is not None:
            raise ApiError(404, "Task not found", "TASK_NOT_FOUND")
        descendants = collect_live_descendant_ids(db, parent.id, user.id)
        if not descendants:
            raise ApiError(
                422,
                "Parent has no live descendants to bundle",
                "BUNDLE_EMPTY_SUBTREE",
            )
        return parent.id, descendants, "parent_subtree"

    # selection path — dedupe while preserving order
    seen: set[uuid.UUID] = set()
    ordered: list[uuid.UUID] = []
    for tid in member_task_ids or []:
        if tid not in seen:
            seen.add(tid)
            ordered.append(tid)
    if not ordered:
        raise ApiError(422, "Provide at least one member task", "BUNDLE_MEMBERS_REQUIRED")
    _owned_live_tasks(db, ordered, user)
    return ordered[0], ordered, "selection"


def duration_minutes_for_members(db: Session, member_ids: list[uuid.UUID], user: User) -> int:
    tasks = _owned_live_tasks(db, member_ids, user)
    total = sum(max(0, int(t.estimated_duration_minutes or 0)) for t in tasks)
    return max(_MIN_BUNDLE_MINUTES, total if total > 0 else _MIN_BUNDLE_MINUTES)


def create_bundle_block(
    db: Session,
    user: User,
    *,
    start_time: datetime,
    end_time: datetime | None,
    is_pinned: bool,
    member_task_ids: list[uuid.UUID] | None,
    parent_task_id: uuid.UUID | None,
) -> ScheduledBlock:
    start = _ensure_utc(start_time)
    anchor_id, members, source = resolve_bundle_membership(
        db,
        user,
        member_task_ids=member_task_ids,
        parent_task_id=parent_task_id,
    )
    if end_time is None:
        minutes = duration_minutes_for_members(db, members, user)
        end = start + timedelta(minutes=minutes)
    else:
        end = _ensure_utc(end_time)
    if end <= start:
        raise ApiError(422, "end_time must be after start_time", "INVALID_TIME_RANGE")

    block = ScheduledBlock(
        owner_id=user.id,
        task_id=anchor_id,
        start_time=start,
        end_time=end,
        is_pinned=is_pinned,
        bundle_meta=build_bundle_meta(member_task_ids=members, source=source),
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def parse_member_ids(meta: dict[str, Any] | None) -> list[uuid.UUID]:
    if not meta or meta.get("kind") != "bundle":
        return []
    raw = meta.get("member_task_ids") or []
    out: list[uuid.UUID] = []
    for item in raw:
        try:
            out.append(uuid.UUID(str(item)))
        except (ValueError, TypeError):
            continue
    return out


def is_bundle_inactive(db: Session, block: ScheduledBlock, user: User) -> bool:
    """True when every member is completed, trashed, or missing (gray + easy delete)."""
    member_ids = parse_member_ids(block.bundle_meta if isinstance(block.bundle_meta, dict) else None)
    if not member_ids:
        return bool(block.bundle_meta)
    rows = (
        db.query(Task)
        .filter(Task.owner_id == user.id, Task.id.in_(member_ids))
        .all()
    )
    by_id = {row.id: row for row in rows}
    for tid in member_ids:
        task = by_id.get(tid)
        if task is None or task.deleted_at is not None:
            continue
        if not task.is_completed:
            return False
    return True
