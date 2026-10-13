"""Placement effort read (§0.2).

Placer and candidate selection use remaining unfinished estimate, falling back to
legacy ``estimated_duration_minutes`` only when ``remaining_minutes`` is unset
(mid-deploy). Future-tail pin reservation is applied by the placement budget,
not here. Fingerprint v4 hashes original, worked, and remaining separately.
"""

from __future__ import annotations

from app.models import Task


def placement_effort_minutes(task: Task) -> int:
    remaining = task.remaining_minutes
    if remaining is not None:
        return remaining
    return task.estimated_duration_minutes
