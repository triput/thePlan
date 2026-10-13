"""Chunking write gate until S2 placer + fingerprint + outcomes readers are live (§0.1)."""

from __future__ import annotations

from app.api.errors import ApiError
from app.models import Task, UserSettings
from app.services.chunking_effective import (
    merged_settings_default_bounds_after_patch,
    merged_task_bounds_after_patch,
    settings_patch_touches_default_bounds,
)

# ---------------------------------------------------------------------------
# Write unlock (S2-V1 + S2-V2). Tesla readers are live; flip tracks release.
# Set False only for emergency rollback in dev — tests assume True at tip.
# ---------------------------------------------------------------------------
CHUNKING_CUTOVER_WRITERS_LIVE: bool = True

_CHUNKING_MSG = (
    "Chunking inherit, No limit, and keep-in-one are not writable until the "
    "0.7 S2 scheduling cutover. Use explicit numeric min/max block minutes."
)

_BOUNDS_CONFLICT_MSG = (
    "Effective min and max block bounds conflict. Adjust min, max, inherit, "
    "or No limit so the effective minimum does not exceed the effective maximum."
)


def chunking_cutover_writes_unlocked() -> bool:
    return CHUNKING_CUTOVER_WRITERS_LIVE


def reject_chunking_cutover_writes(updates: dict[str, object]) -> None:
    if chunking_cutover_writes_unlocked():
        return
    if updates.get("min_block_duration_minutes") is None and "min_block_duration_minutes" in updates:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
    if updates.get("max_block_duration_minutes") is None and "max_block_duration_minutes" in updates:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
    if "max_block_unbounded" in updates and updates.get("max_block_unbounded") is True:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
    if "keep_in_one_block" in updates and updates.get("keep_in_one_block") is True:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
    if "default_max_block_unbounded" in updates and updates.get("default_max_block_unbounded") is True:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")


def validate_effective_chunking_bounds_after_patch(
    task: Task,
    settings: UserSettings,
    updates: dict[str, object],
) -> None:
    """A4: conflicting effective min/max → correction error; no partial write."""
    if not chunking_cutover_writes_unlocked():
        return
    touches = {
        "min_block_duration_minutes",
        "max_block_duration_minutes",
        "max_block_unbounded",
        "keep_in_one_block",
    }
    if not touches.intersection(updates):
        return
    resolved = merged_task_bounds_after_patch(task, settings, updates)
    if resolved.bounds_conflict():
        raise ApiError(422, _BOUNDS_CONFLICT_MSG, "CHUNKING_BOUNDS_CONFLICT")


def validate_effective_settings_defaults_after_patch(
    settings: UserSettings,
    updates: dict[str, object],
) -> None:
    """Reject inverted user default min/max before settings commit (S2-D1)."""
    if not chunking_cutover_writes_unlocked():
        return
    if not settings_patch_touches_default_bounds(updates):
        return
    resolved = merged_settings_default_bounds_after_patch(settings, updates)
    if resolved.bounds_conflict():
        raise ApiError(422, _BOUNDS_CONFLICT_MSG, "CHUNKING_BOUNDS_CONFLICT")


_CHUNKING_BOUND_FIELDS = frozenset(
    {
        "min_block_duration_minutes",
        "max_block_duration_minutes",
        "max_block_unbounded",
        "keep_in_one_block",
    }
)


def _chunking_subset(explicit_fields: dict[str, object]) -> dict[str, object]:
    return {k: explicit_fields[k] for k in _CHUNKING_BOUND_FIELDS if k in explicit_fields}


def validate_effective_chunking_bounds_on_create(
    settings: UserSettings,
    explicit_fields: dict[str, object],
    *,
    fields_set: frozenset[str] | set[str] | None = None,
) -> None:
    """A4-style check for explicit bounds on task create."""
    if not chunking_cutover_writes_unlocked():
        return
    if fields_set is not None:
        updates = {k: explicit_fields[k] for k in _CHUNKING_BOUND_FIELDS if k in fields_set}
    else:
        updates = _chunking_subset(explicit_fields)
    if not updates:
        return

    class _FreshTask:
        min_block_duration_minutes = None
        max_block_duration_minutes = None
        max_block_unbounded = False
        keep_in_one_block = False

    resolved = merged_task_bounds_after_patch(_FreshTask(), settings, updates)  # type: ignore[arg-type]
    if resolved.bounds_conflict():
        raise ApiError(422, _BOUNDS_CONFLICT_MSG, "CHUNKING_BOUNDS_CONFLICT")


def chunking_bounds_kwargs_for_create(
    *,
    explicit_fields: dict[str, object],
    fields_set: frozenset[str] | set[str] | None = None,
) -> dict[str, object]:
    """Kwargs for ``Task(...)`` so INSERT sends NULL inherit, not DB server_default."""
    if not chunking_cutover_writes_unlocked():
        return {}
    if fields_set is not None:
        updates = {k: explicit_fields[k] for k in _CHUNKING_BOUND_FIELDS if k in fields_set}
    else:
        updates = _chunking_subset(explicit_fields)
    if updates:
        out: dict[str, object] = {}
        if "min_block_duration_minutes" in updates:
            out["min_block_duration_minutes"] = updates["min_block_duration_minutes"]
        if "max_block_duration_minutes" in updates:
            out["max_block_duration_minutes"] = updates["max_block_duration_minutes"]
        if "max_block_unbounded" in updates:
            out["max_block_unbounded"] = bool(updates["max_block_unbounded"])
        if "keep_in_one_block" in updates:
            out["keep_in_one_block"] = bool(updates["keep_in_one_block"])
        return out
    return {
        "min_block_duration_minutes": None,
        "max_block_duration_minutes": None,
        "max_block_unbounded": False,
    }


def initialize_task_chunking_bounds_on_create(
    task: Task,
    *,
    explicit_fields: dict[str, object],
    fields_set: frozenset[str] | set[str] | None = None,
) -> None:
    """ORM create paths: inherit (NULL) when cutover live; legacy server defaults otherwise."""
    for key, value in chunking_bounds_kwargs_for_create(
        explicit_fields=explicit_fields, fields_set=fields_set
    ).items():
        setattr(task, key, value)
