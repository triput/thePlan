"""Reject inherit / No limit / keep-in-one writes until S2 placer cutover (§0.1)."""

from __future__ import annotations

from app.api.errors import ApiError

_CHUNKING_MSG = (
    "Chunking inherit, No limit, and keep-in-one are not writable until the "
    "0.7 S2 scheduling cutover. Use explicit numeric min/max block minutes."
)


def reject_chunking_cutover_writes(updates: dict[str, object]) -> None:
    if updates.get("min_block_duration_minutes") is None and "min_block_duration_minutes" in updates:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
    if updates.get("max_block_duration_minutes") is None and "max_block_duration_minutes" in updates:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
    if "max_block_unbounded" in updates and updates.get("max_block_unbounded") is True:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
    if "keep_in_one_block" in updates and updates.get("keep_in_one_block") is True:
        raise ApiError(422, _CHUNKING_MSG, "CHUNKING_CUTOVER_PENDING")
