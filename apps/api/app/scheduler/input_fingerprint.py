"""Input fingerprint for scheduler explanations.

Compared on read against live effective inputs. A mismatch sets ``is_stale``
and names the category. This does not replan.

Snapshot version 3 (S1) and **4** (S2 chunking cutover). Placement
``ALGORITHM_VERSION`` stays ``f3-w2``; ``v`` is the fingerprint contract, not
the placer. A stored snapshot whose ``v`` is not the live version (including
F3 v2 or cross-version v3↔v4) is ``provenance`` — categories are not guessed
across versions.

Compared:
- ``duration`` — v3: estimated, min-block, and max-block minutes. v4: also
  original / worked / remaining, inherit vs explicit vs No limit, keep-in-one
- ``deadline`` — ``deadline_at`` only
- ``map_style`` — effective schedule style, effective time-map id, strict mode,
  and band contents (tier, times, days, sort). Inheritance source is not part
  of the fingerprint; a source change that keeps the same effective values is
  not stale.
- ``deps`` — sorted blocking task ids for this task (the edge set)
- ``pins`` — pinned minutes and pin intervals for this task
- ``project_daily_cap`` — ``max_auto_schedule_minutes_per_project_per_day``
- ``timezone_horizon_workweek`` — timezone, horizon days, and inter-block
  buffer. Workday start, length, and ``workweek_days`` moved to
  ``availability`` at S2-V3. Absolute horizon instants are not stored; a
  sliding ``now`` is not itself stale.
- ``availability`` — stored Working and General policy windows (weekday,
  start, duration, ``ends_next_day``, sort). Not ``map_style``, not Time Map
  overrides, not ``nominal_workday_minutes``. The effective map id stays on
  ``map_style``.
- ``lifecycle`` — completed, trashed (``deleted_at``), project/epic archived
- ``busy_external`` — owner immovable busy (pinned blocks and non-mirror
  external events), not horizon-clipped and not auto-placed blocks
- ``prerequisite_state`` — each blocker's estimated duration, completion, and
  trash timestamp. Edge add/remove stays on ``deps``; this is the blocker row.
- ``due_at_soft_target`` — ``due_at``, ``soft_target_at``, and ``auto_defer_enabled``
- ``time_map_overrides`` — every override on the task's effective map (id,
  inclusive local dates, stored IANA timezone, strict mode, bands). Not
  horizon-clipped, so a sliding ``now`` is not itself stale. Unbound tasks
  have none. An override on another map is not included. Inheritance source
  is not stored; the effective map's rows are. F4-W2 (the F3 note that called
  this W3 is retired for this category).

Not compared (a fresh v3 fingerprint is not proof this held still):
- ``priority_ups`` — priority and UPS weights

``provenance`` is returned when the stored snapshot is missing or from another
snapshot version, so the read cannot name a live category.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from typing import Any
from uuid import UUID

SNAPSHOT_VERSION = 3
SNAPSHOT_VERSION_V4 = 4

# Concrete invalidation tokens (S2-P3). Later semantic activations append here.
# A stored v4 snapshot missing a token is stale on ``scheduling_activation``
# even when the other category hashes would still match. v3 rows stay
# ``provenance`` via the version check and are not rewritten.
SCHEDULING_ACTIVATIONS: tuple[str, ...] = (
    "s2-v1-duration-bounds",
    "s2-v2-pin-reservation",
    "s2-v3-working-general-availability",
)

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
STALE_TIME_MAP_OVERRIDES = "time_map_overrides"
STALE_AVAILABILITY = "availability"
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

F4_W2_STALE_CATEGORIES: tuple[str, ...] = (STALE_TIME_MAP_OVERRIDES,)

S2_V3_STALE_CATEGORIES: tuple[str, ...] = (STALE_AVAILABILITY,)

STALE_SCHEDULING_ACTIVATION = "scheduling_activation"

COMPARED_STALE_CATEGORIES: tuple[str, ...] = (
    W1_STALE_CATEGORIES
    + W2_STALE_CATEGORIES
    + F4_W2_STALE_CATEGORIES
    + S2_V3_STALE_CATEGORIES
    + (STALE_SCHEDULING_ACTIVATION,)
)

# Not compared in v3. Do not treat a matching fingerprint as proof these held still.
DEFERRED_STALE_CATEGORIES: tuple[str, ...] = ("priority_ups",)

ALGORITHM_VERSION = "f3-w2"


def live_snapshot_version() -> int:
    """Task snapshot ``v`` for new collects.

    v4 is live with the placer/resolver, not with Jules's write-guard flip.
    Stored v3 rows compare as ``provenance``. Historical explanation JSON is
    not rewritten.
    """
    return SNAPSHOT_VERSION_V4


def owner_snapshot_predates_activation(snapshot: dict[str, Any] | None) -> bool:
    """True when a preview was captured before the current scheduling activations.

    v3 owner snapshots and v4 snapshots missing a later activation token are
    included. This does not rewrite the stored JSON.
    """
    if not isinstance(snapshot, dict):
        return True
    raw = snapshot.get("snapshot_version")
    if raw is None:
        return True
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return True
    if version < SNAPSHOT_VERSION_V4:
        return True
    payload = snapshot.get("scheduling_activation")
    present = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(present, list):
        return True
    return any(token not in present for token in SCHEDULING_ACTIVATIONS)


def normalize_duration_category_v4(
    *,
    original_minutes: int,
    worked_minutes: int,
    remaining_minutes: int,
    stored_min: int | None,
    stored_max: int | None,
    max_unbounded: bool,
    keep_in_one_block: bool,
    effective_min_minutes: int | None = None,
    effective_max_minutes: int | None = None,
    min_block_source: str | None = None,
    max_block_source: str | None = None,
) -> dict[str, Any]:
    """S0 §5 duration category after S2-V1 activation.

    Inherit vs explicit vs No limit is hashed beside the effective minutes so a
    user-default change stales inheriting tasks. Buffers are not in this category.
    """
    eff_min = effective_min_minutes if effective_min_minutes is not None else stored_min
    if max_unbounded:
        eff_max = None
    elif effective_max_minutes is not None:
        eff_max = effective_max_minutes
    else:
        eff_max = stored_max
    if min_block_source is None:
        min_block_source = "user_default" if stored_min is None else "task_explicit"
    if max_block_source is None:
        if max_unbounded:
            max_block_source = "no_limit"
        elif stored_max is None:
            max_block_source = "user_default"
        else:
            max_block_source = "task_explicit"
    return {
        "original_minutes": int(original_minutes),
        "estimated_duration_minutes": int(original_minutes),
        "worked_minutes": int(worked_minutes),
        "remaining_minutes": int(remaining_minutes),
        "min_block_duration_minutes": int(stored_min) if stored_min is not None else None,
        "max_block_duration_minutes": (
            None if max_unbounded else (int(stored_max) if stored_max is not None else None)
        ),
        "effective_min_minutes": int(eff_min) if eff_min is not None else None,
        "effective_max_minutes": int(eff_max) if eff_max is not None else None,
        "min_inherit": stored_min is None,
        "max_inherit": stored_max is None and not max_unbounded,
        "min_block_source": min_block_source,
        "max_block_source": max_block_source,
        "max_block_unbounded": bool(max_unbounded),
        "keep_in_one_block": bool(keep_in_one_block),
    }


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


def normalize_availability_windows(windows: list[Any] | None) -> list[dict[str, Any]]:
    """Stable Working or General rows. Ids are omitted; hours are the input."""
    rows: list[dict[str, Any]] = []
    for item in windows or []:
        if isinstance(item, dict):
            start = item.get("start_time")
            weekday = item.get("weekday")
            duration = item.get("duration_minutes")
            ends = item.get("ends_next_day")
            sort_order = item.get("sort_order") or 0
        else:
            start = getattr(item, "start_time", None)
            weekday = getattr(item, "weekday", None)
            duration = getattr(item, "duration_minutes", None)
            ends = getattr(item, "ends_next_day", False)
            sort_order = getattr(item, "sort_order", 0) or 0
        if start is None or weekday is None or duration is None:
            continue
        rows.append(
            {
                "weekday": int(weekday),
                "start_time": _iso_time(start),
                "duration_minutes": int(duration),
                "ends_next_day": bool(ends),
                "sort_order": int(sort_order),
            }
        )
    rows.sort(
        key=lambda row: (
            row["weekday"],
            row["sort_order"],
            row["start_time"],
            row["duration_minutes"],
            row["ends_next_day"],
        )
    )
    return rows


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


def _iso_date(value: date | datetime | str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def normalize_time_map_overrides(overrides: list[Any] | None) -> list[dict[str, Any]]:
    """Stable override rows for the effective map. Band row ids are omitted.

    Not horizon-clipped. ``id`` distinguishes a delete-and-recreate that keeps
    the same dates and bands. List order does not change the fingerprint.
    """
    rows: list[dict[str, Any]] = []
    for item in overrides or []:
        if isinstance(item, dict):
            raw_bands = list(item.get("bands") or [])
            override_id = item.get("id")
            map_id = item.get("map_id")
            timezone_name = item.get("timezone")
            strict_mode = bool(item.get("strict_mode"))
            start_date = item.get("local_start_date")
            end_date = item.get("local_end_date")
        else:
            raw_bands = []
            for band in list(getattr(item, "bands", []) or []):
                tier = band.tier.value if hasattr(band.tier, "value") else str(band.tier)
                raw_bands.append(
                    {
                        "tier": tier,
                        "start": band.start_time,
                        "end": band.end_time,
                        "days_of_week": band.days_of_week,
                        "sort_order": band.sort_order,
                    }
                )
            override_id = item.id
            map_id = item.map_id
            timezone_name = item.timezone
            strict_mode = bool(item.strict_mode)
            start_date = item.local_start_date
            end_date = item.local_end_date
        rows.append(
            {
                "id": str(override_id) if override_id else None,
                "map_id": str(map_id) if map_id else None,
                "local_start_date": _iso_date(start_date) if start_date is not None else None,
                "local_end_date": _iso_date(end_date) if end_date is not None else None,
                "timezone": timezone_name,
                "strict_mode": strict_mode,
                "bands": normalize_bands(raw_bands),
            }
        )
    rows.sort(key=lambda row: (row["local_start_date"] or "", row["id"] or ""))
    return rows


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
    min_block_duration_minutes: int | None,
    max_block_duration_minutes: int | None,
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
    time_map_overrides: list[Any] | None = None,
    worked_minutes: int = 0,
    remaining_minutes: int | None = None,
    max_block_unbounded: bool = False,
    keep_in_one_block: bool = False,
    snapshot_version: int | None = None,
    effective_min_minutes: int | None = None,
    effective_max_minutes: int | None = None,
    min_block_source: str | None = None,
    max_block_source: str | None = None,
    working_windows: list[Any] | None = None,
    general_windows: list[Any] | None = None,
) -> dict[str, Any]:
    """Canonical task input snapshot (v3 or v4). Callers pass the effective map.

    ``workday_start_local``, ``workday_minutes``, and ``workweek_days`` are
    accepted and ignored. Eligibility hours live on ``availability``.

    Omitted W2 inputs use empty defaults so two default assemblies still match.
    Collect and live reads must pass the real values; defaults are not a claim
    that the owner has no settings. ``time_map_overrides`` defaults to empty,
    which is the unbound-task value — a bound map's rows must be passed in.

    v3 ``duration`` uses **scheduling-effective** min/max integers (resolved
    inherit / No limit). v4 stores stored-layer bounds plus progress fields.
    """
    del workday_start_local, workday_minutes, workweek_days
    version = snapshot_version if snapshot_version is not None else live_snapshot_version()
    window = str(time_window_id) if time_window_id else None
    blockers = sorted({str(task_id) for task_id in blocking_task_ids})
    pins = list(pin_intervals or [])
    remaining = (
        int(remaining_minutes)
        if remaining_minutes is not None
        else int(estimated_duration_minutes)
    )
    if version == SNAPSHOT_VERSION_V4:
        duration = normalize_duration_category_v4(
            original_minutes=int(estimated_duration_minutes),
            worked_minutes=int(worked_minutes),
            remaining_minutes=remaining,
            stored_min=min_block_duration_minutes,
            stored_max=max_block_duration_minutes,
            max_unbounded=max_block_unbounded,
            keep_in_one_block=keep_in_one_block,
            effective_min_minutes=effective_min_minutes,
            effective_max_minutes=effective_max_minutes,
            min_block_source=min_block_source,
            max_block_source=max_block_source,
        )
    else:
        if min_block_duration_minutes is None or max_block_duration_minutes is None:
            raise ValueError(
                "v3 duration snapshots require scheduling-effective min/max integers; "
                "resolve inherit / No limit before assemble_snapshot"
            )
        duration = {
            "estimated_duration_minutes": int(estimated_duration_minutes),
            "min_block_duration_minutes": int(min_block_duration_minutes),
            "max_block_duration_minutes": int(max_block_duration_minutes),
        }
    snapshot = {
        "v": version,
        "duration": duration,
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
            "inter_block_buffer_minutes": inter_block_buffer_minutes,
        },
        "availability": {
            "working": normalize_availability_windows(working_windows),
            "general": normalize_availability_windows(general_windows),
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
        "time_map_overrides": {
            "overrides": normalize_time_map_overrides(time_map_overrides),
        },
    }
    if version == SNAPSHOT_VERSION_V4:
        snapshot["scheduling_activation"] = {"ids": list(SCHEDULING_ACTIVATIONS)}
    return snapshot


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def fingerprint_snapshot(snapshot: dict[str, Any] | None) -> str | None:
    if snapshot is None:
        return None
    digest = hashlib.sha256(_canonical(snapshot).encode("utf-8")).hexdigest()
    return digest


def diff_stale_categories(stored: dict[str, Any] | None, live: dict[str, Any]) -> list[str]:
    """Category names that differ. Empty means the compared inputs still match.

    ``priority_ups`` is ignored even if a caller stuffs it into the dict.
    ``time_map_overrides`` is compared on v3+ snapshots. Cross-version pairs
    (v3 stored vs v4 live, etc.) return ``provenance`` only.
    """
    if not isinstance(stored, dict) or not isinstance(live, dict):
        return [STALE_PROVENANCE]
    stored_v = stored.get("v")
    live_v = live.get("v")
    if stored_v not in (SNAPSHOT_VERSION, SNAPSHOT_VERSION_V4):
        return [STALE_PROVENANCE]
    if live_v not in (SNAPSHOT_VERSION, SNAPSHOT_VERSION_V4):
        return [STALE_PROVENANCE]
    if stored_v != live_v:
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
