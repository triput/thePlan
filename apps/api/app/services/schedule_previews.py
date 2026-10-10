"""Read and normalize schedule preview rows for API responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SchedulePreview, UserSettings
from app.scheduler.preview_inputs import collected_at_from_snapshot, live_owner_fingerprint


def _mark_expired_if_needed(preview: SchedulePreview, now: datetime) -> None:
    if preview.status != "ready" or preview.expires_at is None:
        return
    if now >= preview.expires_at:
        preview.status = "expired"
        preview.finished_at = preview.finished_at or now


def refresh_preview_staleness(db: Session, preview: SchedulePreview) -> None:
    """Promote ready → stale/expired on read when inputs or time moved."""
    now = datetime.now(timezone.utc)
    _mark_expired_if_needed(preview, now)
    if preview.status not in {"ready", "stale"}:
        return
    if preview.input_fingerprint is None:
        return

    settings = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == preview.owner_id)
        .one_or_none()
    )
    if settings is None:
        return

    if settings.scheduling_revision != preview.scheduling_revision:
        preview.status = "stale"
        return

    # Wall clock expires a preview above. Fingerprints replay collected_at so
    # UPS scores do not go stale just because the read is a few minutes later.
    # This flush is not committed by get_db; apply must re-check on its own.
    replay_now = collected_at_from_snapshot(preview.input_snapshot) or now
    _, live_fp = live_owner_fingerprint(db, preview.owner_id, replay_now)
    if live_fp != preview.input_fingerprint:
        preview.status = "stale"


def summarize_diff(proposal: dict[str, Any] | None) -> dict[str, int]:
    """Identity-based block diff counts (F6-E foundation)."""
    if not proposal:
        return {
            "blocks_added": 0,
            "blocks_removed": 0,
            "blocks_moved": 0,
            "blocks_unchanged": 0,
        }

    def block_key(row: dict[str, Any]) -> tuple[str, str, str]:
        return (row["task_id"], row["start_time"], row["end_time"])

    before_unpinned = [
        row for row in proposal.get("before_blocks", []) if not row.get("is_pinned")
    ]
    proposed = list(proposal.get("proposed_blocks") or [])

    before_set = {block_key(row) for row in before_unpinned}
    after_set = {block_key(row) for row in proposed}

    before_by_task: dict[str, list[dict[str, Any]]] = {}
    for row in before_unpinned:
        before_by_task.setdefault(row["task_id"], []).append(row)

    after_by_task: dict[str, list[dict[str, Any]]] = {}
    for row in proposed:
        after_by_task.setdefault(row["task_id"], []).append(row)

    moved_pairs: list[tuple[str, str, str, str]] = []
    counts = {"unchanged": 0, "moved": 0, "added": 0, "removed": 0}

    for task_id, after_rows in after_by_task.items():
        before_for_task = list(before_by_task.get(task_id, []))
        for after in after_rows:
            key = block_key(after)
            if key in before_set:
                counts["unchanged"] += 1
                continue
            matched = next(
                (
                    before
                    for before in before_for_task
                    if block_key(before) not in after_set
                ),
                None,
            )
            if matched is not None:
                counts["moved"] += 1
                moved_pairs.append(
                    (task_id, matched["start_time"], matched["end_time"], after["start_time"]),
                )
                before_for_task.remove(matched)
            else:
                counts["added"] += 1

    for row in before_unpinned:
        key = block_key(row)
        if key in after_set:
            continue
        already_moved = any(
            task_id == row["task_id"]
            and before_start == row["start_time"]
            and before_end == row["end_time"]
            for task_id, before_start, before_end, _after_start in moved_pairs
        )
        if not already_moved:
            counts["removed"] += 1

    return {
        "blocks_added": counts["added"],
        "blocks_removed": counts["removed"],
        "blocks_moved": counts["moved"],
        "blocks_unchanged": counts["unchanged"],
    }


def preview_to_dict(preview: SchedulePreview) -> dict[str, Any]:
    proposal = preview.proposal_json
    diff = summarize_diff(proposal)
    return {
        "id": preview.id,
        "status": preview.status,
        "started_at": preview.started_at,
        "finished_at": preview.finished_at,
        "expires_at": preview.expires_at,
        "evaluated_at": preview.evaluated_at,
        "algorithm_version": preview.algorithm_version,
        "input_fingerprint": preview.input_fingerprint,
        "scheduling_revision": preview.scheduling_revision,
        "error_message": preview.error_message,
        "stats_json": preview.stats_json,
        "diff_counts": diff,
        "proposal": proposal if preview.status in {"ready", "stale", "expired"} else None,
    }
