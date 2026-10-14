"""Apply-time revalidation when a lifetime ends or A14c order moves, with no settings write."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.scheduler.day_scoped import (
    DayScopedDeclaration,
    lifetime_end_instant,
    only_allow_bounds,
)
from app.scheduler.ups import PRIORITY_SCORES, compute_urgency, slack_due_at


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return _as_utc(parsed)


def lifetime_crossed(
    declarations: Any,
    *,
    preview_at: datetime,
    apply_at: datetime,
    tz: ZoneInfo,
) -> bool:
    """True when a declaration's exclusive end falls after preview and at or before apply."""
    preview_at = _as_utc(preview_at)
    apply_at = _as_utc(apply_at)
    if apply_at <= preview_at:
        return False
    for item in declarations or []:
        if not isinstance(item, DayScopedDeclaration):
            continue
        end = lifetime_end_instant(item, tz)
        if end is None:
            continue
        end = _as_utc(end)
        if preview_at < end <= apply_at:
            return True
    return False


def _block_task_ids(proposal: dict[str, Any]) -> dict[str, list[tuple[datetime, datetime]]]:
    grouped: dict[str, list[tuple[datetime, datetime]]] = {}
    for row in proposal.get("proposed_blocks") or []:
        task_id = str(row.get("task_id") or "")
        if not task_id:
            continue
        grouped.setdefault(task_id, []).append(
            (_parse_utc(row["start_time"]), _parse_utc(row["end_time"]))
        )
    return grouped


def _block_inside_lifetime(
    blocks: list[tuple[datetime, datetime]],
    decl: DayScopedDeclaration,
    tz: ZoneInfo,
) -> bool:
    end = lifetime_end_instant(decl, tz)
    if end is None:
        return False
    end = _as_utc(end)
    start, _only_end = only_allow_bounds(decl, tz) if decl.operation.value == "day.only_allow" else (None, None)
    for block_start, block_end in blocks:
        if block_end <= block_start:
            continue
        if start is not None and block_end <= start:
            continue
        if block_start < end:
            return True
    return False


def proposal_lifetime_stale(
    *,
    composition_by_task: dict[Any, Any],
    proposal: dict[str, Any],
    preview_at: datetime,
    apply_at: datetime,
    tz: ZoneInfo,
) -> bool:
    """Reject when a proposal block depended on a lifetime that has since ended."""
    blocks = _block_task_ids(proposal)
    if not lifetime_crossed(
        [
            item
            for composition in composition_by_task.values()
            for item in getattr(composition, "day_scoped", ()) or ()
        ],
        preview_at=preview_at,
        apply_at=apply_at,
        tz=tz,
    ):
        return False
    for task_id, composition in composition_by_task.items():
        task_blocks = blocks.get(str(task_id)) or []
        if not task_blocks:
            continue
        for item in getattr(composition, "day_scoped", ()) or ():
            if not isinstance(item, DayScopedDeclaration):
                continue
            end = lifetime_end_instant(item, tz)
            if end is None:
                continue
            end = _as_utc(end)
            if not (_as_utc(preview_at) < end <= _as_utc(apply_at)):
                continue
            if _block_inside_lifetime(task_blocks, item, tz):
                return True
    return False


def _prefer_tasks(inputs: Any) -> list[Any]:
    tasks = []
    for candidate in getattr(inputs, "candidates", ()) or ():
        composition = (getattr(inputs, "composition_by_task", {}) or {}).get(candidate.task.id)
        if composition is not None and getattr(composition, "prefer_rules", ()):
            tasks.append(candidate.task)
    return tasks


def ranking_order_changed(inputs: Any, *, preview_at: datetime, apply_at: datetime) -> bool:
    """True when wall-clock UPS movement reorders two Prefer tasks. No settings write."""
    tasks = _prefer_tasks(inputs)
    if len(tasks) < 2:
        return False
    settings = inputs.user_settings
    weights = settings.ups_weights or {}
    k = float(weights.get("k", 0.5))

    def sort_key(task: Any, now: datetime) -> tuple:
        remaining = task.remaining_minutes
        if remaining is None:
            remaining = task.estimated_duration_minutes
        urgency = compute_urgency(
            due_at=slack_due_at(task),
            now_utc=now,
            remaining_minutes=int(remaining or 0),
            k=k,
        )
        priority = PRIORITY_SCORES.get(task.priority, 25.0)
        return (-priority, -urgency, str(task.id))

    preview_order = [task.id for task in sorted(tasks, key=lambda task: sort_key(task, preview_at))]
    apply_order = [task.id for task in sorted(tasks, key=lambda task: sort_key(task, apply_at))]
    return preview_order != apply_order


def temporal_stale_categories(
    inputs: Any,
    proposal: dict[str, Any] | None,
    *,
    preview_at: datetime,
    apply_at: datetime,
) -> list[str]:
    """Categories to reject on apply when fingerprints still match."""
    if proposal is None:
        return []
    tz = ZoneInfo(inputs.user_settings.timezone)
    categories: list[str] = []
    if proposal_lifetime_stale(
        composition_by_task=getattr(inputs, "composition_by_task", {}) or {},
        proposal=proposal,
        preview_at=preview_at,
        apply_at=apply_at,
        tz=tz,
    ):
        categories.append("composition")
    if ranking_order_changed(inputs, preview_at=preview_at, apply_at=apply_at):
        categories.append("priority_ups")
    return categories
