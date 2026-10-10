# ==============================================================================
#  File: apps/api/app/scheduler/preview_inputs.py
#  Description: Owner scheduling input snapshot and fingerprint helpers for F6 previews.
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.scheduler.collect import SchedulingInputs
from app.scheduler.input_fingerprint import SNAPSHOT_VERSION, fingerprint_snapshot


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def owner_input_snapshot(inputs: SchedulingInputs) -> dict[str, Any]:
    """Stable owner-wide inputs captured at collect time.

    UPS scores stay in the hash because priority, weights, and epic targets
    change them. They are recomputed at ``inputs.now_utc``. Callers that
    check staleness must replay the stored ``collected_at``; a later wall
    clock is expiry, not a new fingerprint.
    """
    task_fps: dict[str, str | None] = {}
    for task_id, snapshot in sorted(inputs.input_snapshots.items(), key=lambda item: str(item[0])):
        task_fps[str(task_id)] = fingerprint_snapshot(snapshot)

    edges: list[dict[str, str]] = []
    for dep in inputs.dependencies:
        edges.append(
            {
                "blocking_task_id": str(dep.blocking_task_id),
                "dependent_task_id": str(dep.dependent_task_id),
            }
        )
    edges.sort(key=lambda row: (row["blocking_task_id"], row["dependent_task_id"]))

    ups: dict[str, float] = {
        str(task_id): float(score)
        for task_id, score in sorted(inputs.ups_scores.items(), key=lambda item: str(item[0]))
    }

    return {
        "v": 1,
        "snapshot_version": SNAPSHOT_VERSION,
        "task_fingerprints": task_fps,
        "dependency_edges": edges,
        "ups_scores": ups,
    }


def owner_input_fingerprint(snapshot: dict[str, Any] | None) -> str | None:
    if snapshot is None:
        return None
    digest = hashlib.sha256(_canonical(snapshot).encode("utf-8")).hexdigest()
    return digest


def fingerprint_collected_inputs(inputs: SchedulingInputs) -> tuple[dict[str, Any], str]:
    snapshot = owner_input_snapshot(inputs)
    digest = owner_input_fingerprint(snapshot) or ""
    stored = dict(snapshot)
    # Replay clock only. Hashing it would make a later read look stale.
    stored["collected_at"] = _utc_iso(inputs.now_utc)
    # Full v3 snapshots are not hashed; apply uses them for PREVIEW_STALE categories.
    stored["task_snapshots"] = {
        str(task_id): snap for task_id, snap in sorted(inputs.input_snapshots.items(), key=lambda i: str(i[0]))
    }
    return stored, digest


def collected_at_from_snapshot(snapshot: dict[str, Any] | None) -> datetime | None:
    if not snapshot:
        return None
    raw = snapshot.get("collected_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def live_owner_fingerprint(db, owner_id: UUID, now_utc) -> tuple[dict[str, Any], str]:
    """Re-collect inputs for staleness checks (read-only)."""
    from app.scheduler.collect import collect_inputs

    inputs = collect_inputs(db, owner_id, now_utc)
    return fingerprint_collected_inputs(inputs)
