"""Input fingerprint for scheduler explanations.

Compared on read against live effective inputs. A mismatch sets ``is_stale``
and names the category. This does not replan.

Snapshot version 2 (``ALGORITHM_VERSION`` ``f3-w2``). A stored snapshot whose
``v`` is not 2 is ``provenance`` — categories are not guessed across versions.

Compared:
- ``duration`` — estimated, min-block, and max-block minutes
- ``deadline`` — ``deadline_at`` only
- ``map_style`` — effective schedule style, effective time-map id, strict mode,
  and band contents (tier, times, days, sort). Inheritance source is not part
  of the fingerprint; a source change that keeps the same effective values is
  not stale.
- ``deps`` — sorted blocking task ids for this task (the edge set)
- ``pins`` — pinned minutes and pin intervals for this task
- ``project_daily_cap`` — ``max_auto_schedule_minutes_per_project_per_day``
- ``timezone_horizon_workweek`` — timezone, horizon days, workday start and
  length, workweek length, inter-block buffer. Absolute horizon instants are
  not stored; a sliding ``now`` is not itself stale.
- ``lifecycle`` — completed, trashed (``deleted_at``), project/epic archived
- ``busy_external`` — owner immovable busy (pinned blocks and non-mirror
  external events), not horizon-clipped and not auto-placed blocks
- ``prerequisite_state`` — each blocker's estimated duration, completion, and
  trash timestamp. Edge add/remove stays on ``deps``; this is the blocker row.
- ``due_at_soft_target`` — ``due_at``, ``soft_target_at``, and ``auto_defer_enabled``

Deferred to W3 (not compared; a fresh v2 fingerprint is not proof these are
unchanged):
- ``priority_ups`` — priority and UPS weights
- ``time_map_overrides`` — F4 dated overrides

``provenance`` is returned when the stored snapshot is missing or from another
snapshot version, so the read cannot name a live category.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timezone
from typing import Any
from uuid import UUID

SNAPSHOT_VERSION = 2

STALE_DURATION = "duration"
STALE_DEADLINE = "deadline"
STALE_MAP_STYLE = "map_style"
STALE_DEPS = "deps"
STALE_PINS = "pins"
STALE_PROJECT_DAILY_CAP = "project_daily_cap"
STALE_TIMEZONE_HORIZON_WORKWEEK = "timezone_horizon_workweek"
STALE_LIFECYCLE = "lifecycle"
STALE_BUSY_EXTERNAL = "busy_external"
STALE_PREREQUISITE_STATE = "prerequisite_state"
STALE_DUE_AT_SOFT_TARGET = "due_at_soft_target"
STALE_PROVENANCE = "provenance"

W1_STALE_CATEGORIES: tuple[str, ...] = (
    STALE_DURATION,
    STALE_DEADLINE,
    STALE_MAP_STYLE,
    STALE_DEPS,
)

W2_STALE_CATEGORIES: tuple[str, ...] = (
    STALE_PINS,
    STALE_PROJECT_DAILY_CAP,
    STALE_TIMEZONE_HORIZON_WORKWEEK,
    STALE_LIFECYCLE,
    STALE_BUSY_EXTERNAL,
    STALE_PREREQUISITE_STATE,
    STALE_DUE_AT_SOFT_TARGET,
)

COMPARED_STALE_CATEGORIES: tuple[str, ...] = W1_STALE_CATEGORIES + W2_STALE_CATEGORIES

# Not compared in v2. Do not treat a matching fingerprint as proof these held still.
DEFERRED_STALE_CATEGORIES: tuple[str, ...] = (
    "priority_ups",
    "time_map_overrides",
)

ALGORITHM_VERSION = "f3-w2"


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _iso_time(value: time | str) -> str:
    if isinstance(value, str):
        return value
    return value.isoformat()


def normalize_bands(bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable band list. Row ids are omitted; they are not scheduling inputs."""
    normalized: list[dict[str, Any]] = []
    for band in bands:
        tier = band.get("tier")
        if hasattr(tier, "value"):
            tier = tier.value
        normalized.append(
            {
                "tier": str(tier),
                "start": _iso_time(band["start"]),
                "end": _iso_time(band["end"]),
                "days_of_week": int(band["days_of_week"]),
                "sort_order": int(band["sort_order"]),
            }
        )
    normalized.sort(
        key=lambda item: (
            item["sort_order"],
            item["start"],
            item["end"],
            item["tier"],
            item["days_of_week"],
        )
    )
    return normalized


def normalize_pin_intervals(blocks: list[Any]) -> tuple[int, list[dict[str, Any]]]:
    """Pinned minutes plus stable intervals. ``id`` distinguishes equal times."""
    intervals: list[dict[str, Any]] = []
    minutes = 0
    for block in blocks:
        start = getattr(block, "start_time", None)
        end = getattr(block, "end_time", None)
        block_id = getattr(block, "id", None)
        if isinstance(block, dict):
            start = block.get("start", block.get("start_time"))
            end = block.get("end", block.get("end_time"))
            block_id = block.get("id")
        if start is None or end is None:
            continue
        if not isinstance(start, datetime):
            start = datetime.fromisoformat(str(start))
        if not isinstance(end, datetime):
            end = datetime.fromisoformat(str(end))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        minutes += int((end - start).total_seconds() // 60)
        intervals.append(
            {
                "id": str(block_id) if block_id else None,
                "start": start.astimezone(timezone.utc).isoformat(),
                "end": end.astimezone(timezone.utc).isoformat(),
            }
        )
    intervals.sort(key=lambda item: (item["start"], item["end"], item["id"] or ""))
    return minutes, intervals


def normalize_busy_intervals(intervals: list[Any]) -> list[dict[str, str]]:
    """Immovable busy only. Auto-placed ``scheduled`` intervals are outputs."""
    rows: list[dict[str, str]] = []
    for item in intervals:
        if isinstance(item, dict):
            source = str(item.get("source") or "external")
            start = item.get("start", item.get("start_time"))
            end = item.get("end", item.get("end_time"))
        else:
            source = str(getattr(item, "source", "external") or "external")
            start = getattr(item, "start", None)
            end = getattr(item, "end", None)
        if source not in {"external", "pinned"} or start is None or end is None:
            continue
        if not isinstance(start, datetime):
            start = datetime.fromisoformat(str(start))
        if not isinstance(end, datetime):
            end = datetime.fromisoformat(str(end))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        rows.append(
            {
                "source": source,
                "start": start.astimezone(timezone.utc).isoformat(),
                "end": end.astimezone(timezone.utc).isoformat(),
            }
        )
    rows.sort(key=lambda item: (item["start"], item["end"], item["source"]))
    return rows


def normalize_prerequisite_states(
    blocking_task_ids: list[UUID | str],
    tasks_by_id: dict[Any, Any] | None,
) -> list[dict[str, Any]]:
    """Blocker duration, completion, and trash. Missing rows stay explicit."""
    lookup = tasks_by_id or {}
    states: list[dict[str, Any]] = []
    for task_id in sorted({str(item) for item in blocking_task_ids}):
        task = lookup.get(task_id)
        if task is None:
            for key, value in lookup.items():
                if str(key) == task_id:
                    task = value
                    break
        if task is None:
            states.append({"task_id": task_id, "missing": True})
            continue
        deleted = getattr(task, "deleted_at", None)
        if isinstance(task, dict):
            states.append(
                {
                    "task_id": task_id,
                    "estimated_duration_minutes": int(task["estimated_duration_minutes"]),
                    "is_completed": bool(task.get("is_completed")),
                    "deleted_at": task.get("deleted_at"),
                }
            )
            continue
        states.append(
            {
                "task_id": task_id,
                "estimated_duration_minutes": int(task.estimated_duration_minutes),
                "is_completed": bool(task.is_completed),
                "deleted_at": _iso_datetime(deleted),
            }
        )
    return states


def assemble_snapshot(
    *,
    estimated_duration_minutes: int,
    min_block_duration_minutes: int,
    max_block_duration_minutes: int,
    deadline_at: datetime | None,
    schedule_style: str | None,
    time_window_id: UUID | str | None,
    strict_mode: bool | None,
    bands: list[dict[str, Any]],
    blocking_task_ids: list[UUID | str],
    pinned_minutes: int = 0,
    pin_intervals: list[dict[str, Any]] | None = None,
    project_daily_cap_minutes: int | None = None,
    timezone_name: str | None = None,
    upcoming_horizon_days: int | None = None,
    workday_start_local: time | str | None = None,
    workday_minutes: int | None = None,
    workweek_days: int | None = None,
    inter_block_buffer_minutes: int | None = None,
    is_completed: bool = False,
    deleted_at: datetime | None = None,
    project_archived: bool = False,
    epic_archived: bool = False,
    busy_intervals: list[dict[str, Any]] | None = None,
    prerequisite_states: list[dict[str, Any]] | None = None,
    due_at: datetime | None = None,
    soft_target_at: datetime | None = None,
    auto_defer_enabled: bool | None = None,
) -> dict[str, Any]:
    """Canonical v2 snapshot. Callers pass effective style and map, not raw overrides.

    Omitted W2 inputs use empty defaults so two default assemblies still match.
    Collect and live reads must pass the real values; defaults are not a claim
    that the owner has no settings.
    """
    window = str(time_window_id) if time_window_id else None
    blockers = sorted({str(task_id) for task_id in blocking_task_ids})
    pins = list(pin_intervals or [])
    return {
        "v": SNAPSHOT_VERSION,
        "duration": {
            "estimated_duration_minutes": int(estimated_duration_minutes),
            "min_block_duration_minutes": int(min_block_duration_minutes),
            "max_block_duration_minutes": int(max_block_duration_minutes),
        },
        "deadline": {"deadline_at": _iso_datetime(deadline_at)},
        "map_style": {
            "schedule_style": schedule_style,
            "time_window_id": window,
            "strict_mode": strict_mode,
            "bands": normalize_bands(bands),
        },
        "deps": {"blocking_task_ids": blockers},
        "pins": {
            "pinned_minutes": int(pinned_minutes),
            "intervals": pins,
        },
        "project_daily_cap": {
            "max_auto_schedule_minutes_per_project_per_day": project_daily_cap_minutes,
        },
        "timezone_horizon_workweek": {
            "timezone": timezone_name,
            "upcoming_horizon_days": upcoming_horizon_days,
            "workday_start_local": _iso_time(workday_start_local) if workday_start_local else None,
            "workday_minutes": workday_minutes,
            "workweek_days": workweek_days,
            "inter_block_buffer_minutes": inter_block_buffer_minutes,
        },
        "lifecycle": {
            "is_completed": bool(is_completed),
            "deleted_at": _iso_datetime(deleted_at),
            "project_archived": bool(project_archived),
            "epic_archived": bool(epic_archived),
        },
        "busy_external": {"intervals": list(busy_intervals or [])},
        "prerequisite_state": {"blockers": list(prerequisite_states or [])},
        "due_at_soft_target": {
            "due_at": _iso_datetime(due_at),
            "soft_target_at": _iso_datetime(soft_target_at),
            "auto_defer_enabled": auto_defer_enabled,
        },
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def fingerprint_snapshot(snapshot: dict[str, Any] | None) -> str | None:
    if snapshot is None:
        return None
    digest = hashlib.sha256(_canonical(snapshot).encode("utf-8")).hexdigest()
    return digest


def diff_stale_categories(stored: dict[str, Any] | None, live: dict[str, Any]) -> list[str]:
    """Category names that differ. Empty means the compared inputs still match.

    W3 keys (``priority_ups``, ``time_map_overrides``) are ignored even if a
    caller stuffs them into the dict.
    """
    if not isinstance(stored, dict) or stored.get("v") != SNAPSHOT_VERSION:
        return [STALE_PROVENANCE]
    if not isinstance(live, dict) or live.get("v") != SNAPSHOT_VERSION:
        return [STALE_PROVENANCE]
    changed: list[str] = []
    for key in COMPARED_STALE_CATEGORIES:
        if _canonical(stored.get(key)) != _canonical(live.get(key)):
            changed.append(key)
    return changed


def outcome_family(primary_reason_code: str | None) -> str:
    """Coarse outcome stored beside Jules' primary reason code."""
    code = primary_reason_code or ""
    if code == "placed" or code.startswith("placed"):
        return "placed"
    if code.startswith("excluded"):
        return "excluded"
    if code.startswith("blocked") or code in {
        "blocked_prerequisite",
        "blocked_dependency_cycle",
    }:
        return "blocked"
    if code.startswith("unplaced"):
        return "unplaced"
    return "recorded"
