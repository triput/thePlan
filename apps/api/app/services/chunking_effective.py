"""Effective chunking bounds resolution for API reads and fingerprint v4 (S2-V1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models import Task, UserSettings

MinSource = Literal["task_explicit", "user_default"]
MaxSource = Literal["task_explicit", "user_default", "no_limit"]


@dataclass(frozen=True)
class ResolvedBlockBounds:
    """Scheduling-effective min/max after inherit and No limit resolution."""

    effective_min_minutes: int
    min_source: MinSource
    min_inherit: bool
    effective_max_minutes: int | None
    max_source: MaxSource
    max_inherit: bool
    max_unbounded: bool
    keep_in_one_block: bool

    def bounds_conflict(self) -> bool:
        if self.max_unbounded:
            return False
        if self.effective_max_minutes is None:
            return False
        return self.effective_min_minutes > self.effective_max_minutes


def resolve_block_bounds(task: Task, settings: UserSettings) -> ResolvedBlockBounds:
    raw_min = task.min_block_duration_minutes
    raw_max = task.max_block_duration_minutes
    min_inherit = raw_min is None
    max_inherit = raw_max is None

    if min_inherit:
        effective_min = int(settings.default_min_block_duration_minutes)
        min_source: MinSource = "user_default"
    else:
        effective_min = int(raw_min)
        min_source = "task_explicit"

    max_unbounded = bool(task.max_block_unbounded)
    if max_unbounded:
        return ResolvedBlockBounds(
            effective_min_minutes=effective_min,
            min_source=min_source,
            min_inherit=min_inherit,
            effective_max_minutes=None,
            max_source="no_limit",
            max_inherit=max_inherit,
            max_unbounded=True,
            keep_in_one_block=bool(task.keep_in_one_block),
        )

    if max_inherit:
        if settings.default_max_block_unbounded:
            return ResolvedBlockBounds(
                effective_min_minutes=effective_min,
                min_source=min_source,
                min_inherit=min_inherit,
                effective_max_minutes=None,
                max_source="no_limit",
                max_inherit=True,
                max_unbounded=True,
                keep_in_one_block=bool(task.keep_in_one_block),
            )
        effective_max = int(settings.default_max_block_duration_minutes)
        max_source: MaxSource = "user_default"
    else:
        effective_max = int(raw_max)
        max_source = "task_explicit"

    return ResolvedBlockBounds(
        effective_min_minutes=effective_min,
        min_source=min_source,
        min_inherit=min_inherit,
        effective_max_minutes=effective_max,
        max_source=max_source,
        max_inherit=max_inherit,
        max_unbounded=False,
        keep_in_one_block=bool(task.keep_in_one_block),
    )


def merged_task_bounds_after_patch(
    task: Task,
    settings: UserSettings,
    updates: dict[str, object],
) -> ResolvedBlockBounds:
    """Resolve bounds as if ``updates`` were applied (for A4 pre-write validation)."""

    class _View:
        __slots__ = (
            "min_block_duration_minutes",
            "max_block_duration_minutes",
            "max_block_unbounded",
            "keep_in_one_block",
        )

    view = _View()
    view.min_block_duration_minutes = (
        updates["min_block_duration_minutes"]
        if "min_block_duration_minutes" in updates
        else task.min_block_duration_minutes
    )
    view.max_block_duration_minutes = (
        updates["max_block_duration_minutes"]
        if "max_block_duration_minutes" in updates
        else task.max_block_duration_minutes
    )
    view.max_block_unbounded = (
        updates["max_block_unbounded"]
        if "max_block_unbounded" in updates
        else task.max_block_unbounded
    )
    view.keep_in_one_block = (
        updates["keep_in_one_block"]
        if "keep_in_one_block" in updates
        else task.keep_in_one_block
    )
    return resolve_block_bounds(view, settings)  # type: ignore[arg-type]
