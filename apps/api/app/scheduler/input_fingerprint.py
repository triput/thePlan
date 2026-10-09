"""W1 input fingerprint for scheduler explanations.

Compared on read against live effective inputs. A mismatch sets ``is_stale``
and names the category. This does not replan.

W1 categories:
- ``duration`` — estimated, min-block, and max-block minutes
- ``deadline`` — ``deadline_at`` only
- ``map_style`` — effective schedule style, effective time-map id, strict mode,
  and band contents (tier, times, days, sort). Inheritance source is not part
  of the fingerprint; a source change that keeps the same effective values is
  not stale.
- ``deps`` — sorted blocking task ids for this task (the edge set)

Deferred (not compared in W1; do not treat a fresh W1 fingerprint as proof
these are unchanged):
- ``pins`` — pinned minutes and pin intervals
- ``project_daily_cap``
- ``timezone_horizon_workweek`` — timezone, horizon, workday, workweek, buffers
- ``priority_ups`` — priority and UPS weights
- ``lifecycle`` — completed, trashed, archived
- ``busy_external`` — external busy and pinned conflicts
- ``time_map_overrides`` — F4 dated overrides
- ``prerequisite_state`` — blocker duration or completion, beyond the edge set
- ``due_at_soft_target`` — due date and soft target

``provenance`` is returned when the stored snapshot is missing or from another
snapshot version, so the read cannot name a live category.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timezone
from typing import Any
from uuid import UUID

SNAPSHOT_VERSION = 1

STALE_DURATION = "duration"
STALE_DEADLINE = "deadline"
STALE_MAP_STYLE = "map_style"
STALE_DEPS = "deps"
STALE_PROVENANCE = "provenance"

W1_STALE_CATEGORIES: tuple[str, ...] = (
    STALE_DURATION,
    STALE_DEADLINE,
    STALE_MAP_STYLE,
    STALE_DEPS,
)

DEFERRED_STALE_CATEGORIES: tuple[str, ...] = (
    "pins",
    "project_daily_cap",
    "timezone_horizon_workweek",
    "priority_ups",
    "lifecycle",
    "busy_external",
    "time_map_overrides",
    "prerequisite_state",
    "due_at_soft_target",
)

ALGORITHM_VERSION = "f3-w1"


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
) -> dict[str, Any]:
    """Canonical W1 snapshot. Callers pass effective style and map, not raw overrides."""
    window = str(time_window_id) if time_window_id else None
    blockers = sorted({str(task_id) for task_id in blocking_task_ids})
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
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def fingerprint_snapshot(snapshot: dict[str, Any] | None) -> str | None:
    if snapshot is None:
        return None
    digest = hashlib.sha256(_canonical(snapshot).encode("utf-8")).hexdigest()
    return digest


def diff_stale_categories(stored: dict[str, Any] | None, live: dict[str, Any]) -> list[str]:
    """Category names that differ. Empty means the W1 inputs still match."""
    if not isinstance(stored, dict) or stored.get("v") != SNAPSHOT_VERSION:
        return [STALE_PROVENANCE]
    if not isinstance(live, dict) or live.get("v") != SNAPSHOT_VERSION:
        return [STALE_PROVENANCE]
    changed: list[str] = []
    for key in W1_STALE_CATEGORIES:
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
    if code.startswith("blocked") or code == "blocked_prerequisite":
        return "blocked"
    if code.startswith("unplaced"):
        return "unplaced"
    return "recorded"
