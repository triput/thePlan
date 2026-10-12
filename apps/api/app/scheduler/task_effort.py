"""S1 placement effort read shim (§0.2 migration contract).

Placer and candidate selection use remaining unfinished estimate, falling back to
legacy ``estimated_duration_minutes`` only when ``remaining_minutes`` is unset
(mid-deploy). Fingerprint v3 keeps hashing explicit stored bounds and legacy
estimate fields until S2 v4 cutover.
"""

from __future__ import annotations

from app.models import Task


def placement_effort_minutes(task: Task) -> int:
    remaining = task.remaining_minutes
    if remaining is not None:
        return remaining
    return task.estimated_duration_minutes
