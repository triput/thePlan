# ==============================================================================
#  File: apps/api/app/services/scheduling_revision.py
#  Description: Per-owner scheduling revision counter and advisory lock for F6 apply serialization.
#  Component: Replan Preview
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-12
# ==============================================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import UserSettings

_OWNER_LOCK_NAMESPACE = 1_886_415_951


def assert_scheduling_revision(settings_revision: int, expected: int | None) -> None:
    """Reject missing or stale scheduling_revision tokens (F6 / §1.2)."""
    if expected is None:
        raise ApiError(
            422,
            "expected_revision is required for this operation",
            "SCHEDULING_REVISION_REQUIRED",
        )
    if settings_revision != expected:
        raise ApiError(
            409,
            "Scheduling inputs changed since this action was prepared",
            "SCHEDULING_REVISION_CONFLICT",
            expected_revision=expected,
            current_revision=settings_revision,
        )


def owner_scheduling_lock_key(owner_id: UUID) -> int:
    folded = (owner_id.int ^ (owner_id.int >> 64)) & 0x7FFFFFFF
    return folded or 1


def lock_owner_scheduling(db: Session, owner_id: UUID) -> UserSettings:
    """Transaction-scoped advisory lock plus settings row FOR UPDATE.

    ``populate_existing()`` refreshes any identity-map copy so waiters see the
    post-lock ``scheduling_revision`` (same pattern as task row locks). Without
    it, a pre-loaded UserSettings can keep a stale revision and pass conflict
    checks that should 409.
    """
    db.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
        {"namespace": _OWNER_LOCK_NAMESPACE, "key": owner_scheduling_lock_key(owner_id)},
    )
    settings = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == owner_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    return settings


TASK_SCHEDULING_PATCH_FIELDS = frozenset(
    {
        "project_id",
        "section_id",
        "parent_task_id",
        "priority",
        "due_at",
        "deadline_at",
        "estimated_duration_minutes",
        "remaining_minutes",
        "min_block_duration_minutes",
        "max_block_duration_minutes",
        "max_block_unbounded",
        "keep_in_one_block",
        "preferred_time_window_id",
        "schedule_style",
    }
)

SETTINGS_SCHEDULING_FIELDS = frozenset(
    {
        "timezone",
        "workday_minutes",
        "workday_start_local",
        "workweek_days",
        "inter_block_buffer_minutes",
        "ups_weights",
        "upcoming_horizon_days",
        "default_estimated_duration_minutes",
        "default_min_block_duration_minutes",
        "default_schedule_style",
        "auto_defer_enabled",
        "max_auto_schedule_minutes_per_project_per_day",
    }
)


def task_patch_touches_scheduling(
    updates: dict[str, object],
    *,
    plan_touched: bool,
    soft_target_touched: bool,
) -> bool:
    if plan_touched or soft_target_touched:
        return True
    return bool(TASK_SCHEDULING_PATCH_FIELDS.intersection(updates))


def increment_scheduling_revision(db: Session, settings: UserSettings) -> int:
    """Bump revision; caller must already hold the owner scheduling lock."""
    settings.scheduling_revision = int(settings.scheduling_revision) + 1
    db.flush()
    return int(settings.scheduling_revision)


def bump_scheduling_revision(db: Session, owner_id: UUID) -> int:
    """Take the owner lock and increment scheduling revision."""
    settings = lock_owner_scheduling(db, owner_id)
    return increment_scheduling_revision(db, settings)


# Shared by project and epic patches. epic_id is project-only; target_date is epic-only.
_SHARED_PROJECT_EPIC_SCHEDULING_FIELDS = frozenset(
    {
        "preferred_time_window_id",
        "schedule_style",
        "is_archived",
    }
)

# Reparent and detach (epic_id present, including null) change inherited style,
# map, lifecycle, and UPS epic alignment.
PROJECT_SCHEDULING_FIELDS = _SHARED_PROJECT_EPIC_SCHEDULING_FIELDS | frozenset({"epic_id"})

# target_date feeds UPS epic alignment. Projects have no target_date column.
EPIC_SCHEDULING_FIELDS = _SHARED_PROJECT_EPIC_SCHEDULING_FIELDS | frozenset({"target_date"})


def project_patch_touches_scheduling(updates: dict[str, object]) -> bool:
    return bool(PROJECT_SCHEDULING_FIELDS.intersection(updates))


def epic_patch_touches_scheduling(updates: dict[str, object]) -> bool:
    return bool(EPIC_SCHEDULING_FIELDS.intersection(updates))


def immovable_busy_signature(db: Session, owner_id: UUID) -> tuple[tuple[str, str, str], ...]:
    """Normalized pin + non-mirror external intervals. Titles and sync cursors are ignored."""
    from app.scheduler.busy_map import busy_from_sources, load_immovable_busy_sources
    from app.scheduler.input_fingerprint import normalize_busy_intervals

    pinned, events = load_immovable_busy_sources(db, owner_id)
    normalized = normalize_busy_intervals(busy_from_sources(pinned, events))
    return tuple((row["source"], row["start"], row["end"]) for row in normalized)


def bump_scheduling_revision_if_busy_changed(
    db: Session,
    owner_id: UUID,
    before: tuple[tuple[str, str, str], ...],
) -> int | None:
    """Lock and bump when busy intervals differ from ``before``.

    The lock is taken only after the comparison. Writers that change busy rows
    must call ``lock_owner_scheduling`` before those writes; this helper does
    not cover mutations already staged in the transaction.
    """
    if immovable_busy_signature(db, owner_id) == before:
        return None
    return bump_scheduling_revision(db, owner_id)
