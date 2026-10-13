"""Chunking write gate until S2 placer + fingerprint + outcomes readers are live (§0.1)."""

from __future__ import annotations

from app.api.errors import ApiError
from app.models import Task, UserSettings
from app.services.chunking_effective import merged_task_bounds_after_patch

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
