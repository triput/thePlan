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


def duration_minutes_for_incomplete_members(
    db: Session,
    member_ids: list[uuid.UUID],
    user: User,
    *,
    exclude_ids: set[uuid.UUID] | None = None,
) -> int:
    """Sum estimates of live incomplete members; floor at ``_MIN_BUNDLE_MINUTES``.

    ``exclude_ids`` covers same-session completions that may not be visible to a
    fresh SELECT yet (unflushed ORM state or bulk UPDATE).
    """
    if not member_ids:
        return _MIN_BUNDLE_MINUTES
    skip = exclude_ids or set()
    rows = (
        db.query(Task)
        .filter(
            Task.owner_id == user.id,
            Task.id.in_(member_ids),
            Task.deleted_at.is_(None),
            Task.is_completed.is_(False),
        )
        .all()
    )
    total = sum(
        max(0, int(t.estimated_duration_minutes or 0))
        for t in rows
        if t.id not in skip
    )
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
    """True when the aggregate should gray (ADR-012).

    Grays when **any** live member is completed, or when no live incomplete
    members remain (all completed / trashed / missing). Calendar delete UX
    stays the same — gray is styling, not a gate.
    """
    member_ids = parse_member_ids(block.bundle_meta if isinstance(block.bundle_meta, dict) else None)
    if not member_ids:
        return bool(block.bundle_meta)
    rows = (
        db.query(Task)
        .filter(Task.owner_id == user.id, Task.id.in_(member_ids))
        .all()
    )
    by_id = {row.id: row for row in rows}
    has_live_incomplete = False
    for tid in member_ids:
        task = by_id.get(tid)
        if task is None or task.deleted_at is not None:
            continue
        if task.is_completed:
            return True
        has_live_incomplete = True
    return not has_live_incomplete


def shrink_bundle_blocks_for_completed_members(
    db: Session,
    user: User,
    completed_task_ids: list[uuid.UUID],
) -> None:
    """Shrink bundle ``end_time`` to remaining incomplete members' estimate sum.

    Only shortens (never expands). Floor is ``_MIN_BUNDLE_MINUTES``. No-op when
    none of the completed ids appear in a block's membership.
    """
    if not completed_task_ids:
        return
    completed_set = set(completed_task_ids)
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == user.id,
            ScheduledBlock.bundle_meta.isnot(None),
        )
        .all()
    )
    for block in blocks:
        meta = block.bundle_meta if isinstance(block.bundle_meta, dict) else None
        member_ids = parse_member_ids(meta)
        if not member_ids or completed_set.isdisjoint(member_ids):
            continue
        minutes = duration_minutes_for_incomplete_members(
            db, member_ids, user, exclude_ids=completed_set
        )
        start = _ensure_utc(block.start_time)
        old_end = _ensure_utc(block.end_time)
        new_end = start + timedelta(minutes=minutes)
        if new_end < old_end:
            block.end_time = new_end
