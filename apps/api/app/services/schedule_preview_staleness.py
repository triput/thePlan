# ==============================================================================
#  File: apps/api/app/services/schedule_preview_staleness.py
#  Description: Apply-time F6 preview staleness checks against live owner input fingerprint.
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import (
    STALE_PROVENANCE,
    diff_stale_categories,
    fingerprint_snapshot,
    owner_snapshot_predates_activation,
)
from app.scheduler.preview_inputs import collected_at_from_snapshot, owner_input_fingerprint


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def preview_stale_categories(
    db: Session,
    *,
    owner_id: UUID,
    input_snapshot: dict[str, Any] | None,
    scheduling_revision: int,
    settings_revision: int,
) -> list[str]:
    """F3-shaped category list when a preview no longer matches live inputs.

    Previews captured before the current chunking/pin activation are
    ``provenance`` and are not category-diffed against v4. Stored JSON is
    left as written.
    """
    if not isinstance(input_snapshot, dict):
        return [STALE_PROVENANCE]
    if owner_snapshot_predates_activation(input_snapshot):
        return [STALE_PROVENANCE]

    replay = collected_at_from_snapshot(input_snapshot) or datetime.now(timezone.utc)
    inputs = collect_inputs(db, owner_id, replay)
    live_snapshot, live_fingerprint = _live_owner_snapshot(inputs)
    stored_fingerprint = owner_input_fingerprint(input_snapshot)
    if stored_fingerprint == live_fingerprint:
        # Direct replan bumps revision while leaving input fingerprints alone
        # (auto-placed blocks are outputs). Still name the conflict.
        if settings_revision != scheduling_revision:
            return [STALE_PROVENANCE]
        return []

    categories: set[str] = set()
    stored_snaps = input_snapshot.get("task_snapshots") or {}
    stored_fps = input_snapshot.get("task_fingerprints") or {}
    for task_id, live_task_snap in inputs.input_snapshots.items():
        key = str(task_id)
        live_fp = fingerprint_snapshot(live_task_snap)
        if stored_fps.get(key) == live_fp:
            continue
        stored_task_snap = stored_snaps.get(key)
        for cat in diff_stale_categories(stored_task_snap, live_task_snap):
            categories.add(cat)

    if _canonical(input_snapshot.get("dependency_edges")) != _canonical(
        live_snapshot.get("dependency_edges")
    ):
        categories.add("deps")

    if settings_revision != scheduling_revision:
        categories.add(STALE_PROVENANCE)
    if not categories and stored_fingerprint != live_fingerprint:
        categories.add(STALE_PROVENANCE)
    return sorted(categories)


def _live_owner_snapshot(inputs) -> tuple[dict[str, Any], str]:
    from app.scheduler.preview_inputs import fingerprint_collected_inputs

    return fingerprint_collected_inputs(inputs)
