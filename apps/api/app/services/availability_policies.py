"""Availability policy read/update (S2-V3 placer SoT + S2-V4 Personal unlock).

Working and General window writes bump ``scheduling_revision``. They do not
rewrite deprecated ``workweek_*`` mirrors. Split, gapped, and mixed-hours
Working patterns store. Personal window writes are unlocked for V4 assignment
consumption (revision-locked); policy-list ``scheduling_effective`` stays false
for Personal until a task assignment actually consumes it.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.models import AvailabilityPolicy, AvailabilityWindow, User
from app.models.enums import AvailabilityPolicySlug
from app.schemas.availability import (
    AvailabilityPolicyCreate,
    AvailabilityPolicyUpdate,
    AvailabilityWindowIn,
)
from app.services.availability_seed import derive_window_end
from app.services.availability_slug import policy_slug_str
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling


def list_policies(db: Session, user: User) -> list[AvailabilityPolicy]:
    return (
        db.query(AvailabilityPolicy)
        .options(joinedload(AvailabilityPolicy.windows))
        .filter(AvailabilityPolicy.owner_id == user.id)
        .order_by(AvailabilityPolicy.sort_order, AvailabilityPolicy.slug)
        .all()
    )


def _parse_policy_ref(ref: str) -> uuid.UUID | str:
    try:
        return uuid.UUID(ref)
    except ValueError:
        pass
    slug = ref.strip().lower()
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability policy not found",
        )
    return slug


def get_policy(db: Session, user: User, ref: str) -> AvailabilityPolicy:
    parsed = _parse_policy_ref(ref)
    query = (
        db.query(AvailabilityPolicy)
        .options(joinedload(AvailabilityPolicy.windows))
        .filter(AvailabilityPolicy.owner_id == user.id)
    )
    if isinstance(parsed, uuid.UUID):
        policy = query.filter(AvailabilityPolicy.id == parsed).one_or_none()
    else:
        policy = query.filter(AvailabilityPolicy.slug == str(parsed)).one_or_none()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability policy not found")
    return policy


def _build_windows(
    owner_id: uuid.UUID,
    policy_id: uuid.UUID,
    windows_in: list[AvailabilityWindowIn],
) -> list[AvailabilityWindow]:
    built: list[AvailabilityWindow] = []
    for row in windows_in:
        end_time, ends_next_day = derive_window_end(row.start_time, row.duration_minutes)
        built.append(
            AvailabilityWindow(
                owner_id=owner_id,
                policy_id=policy_id,
                weekday=row.weekday,
                start_time=row.start_time,
                end_time=end_time,
                ends_next_day=ends_next_day,
                duration_minutes=row.duration_minutes,
                sort_order=row.sort_order,
            )
        )
    return built


def _next_sort_order(db: Session, owner_id: uuid.UUID) -> int:
    current = (
        db.query(func.max(AvailabilityPolicy.sort_order))
        .filter(AvailabilityPolicy.owner_id == owner_id)
        .scalar()
    )
    if current is None:
        return 0
    return int(current) + 1


def create_policy(db: Session, user: User, body: AvailabilityPolicyCreate) -> AvailabilityPolicy:
    sort_order = body.sort_order if body.sort_order is not None else _next_sort_order(db, user.id)
    scheduling_settings = lock_owner_scheduling(db, user.id)
    policy = AvailabilityPolicy(
        owner_id=user.id,
        slug=body.slug,
        name=body.name,
        sort_order=sort_order,
    )
    conflict = (
        db.query(AvailabilityPolicy.id)
        .filter(
            AvailabilityPolicy.owner_id == user.id,
            AvailabilityPolicy.slug == body.slug,
        )
        .first()
    )
    if conflict is not None:
        raise ApiError(
            409,
            "An availability policy with this slug already exists for this owner",
            "AVAILABILITY_POLICY_SLUG_CONFLICT",
            slug=body.slug,
        )
    db.add(policy)
    db.flush()
    for window in _build_windows(user.id, policy.id, body.windows):
        policy.windows.append(window)
    db.flush()
    increment_scheduling_revision(db, scheduling_settings)
    db.flush()
    return policy


def update_policy(
    db: Session,
    user: User,
    policy: AvailabilityPolicy,
    body: AvailabilityPolicyUpdate,
) -> AvailabilityPolicy:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return policy

    revision_write = body.windows is not None
    scheduling_settings = lock_owner_scheduling(db, user.id) if revision_write else None

    if "name" in updates and updates["name"] is not None:
        policy.name = updates["name"].strip()

    if body.windows is not None:
        policy.windows.clear()
        db.flush()
        for window in _build_windows(user.id, policy.id, body.windows):
            policy.windows.append(window)

    if revision_write and scheduling_settings is not None:
        increment_scheduling_revision(db, scheduling_settings)

    db.flush()
    return policy


def effective_windows_for_date(policy: AvailabilityPolicy, on: date) -> tuple[list[AvailabilityWindow], list[str]]:
    weekday = on.weekday()
    windows = [window for window in policy.windows if window.weekday == weekday]
    windows.sort(key=lambda row: (row.sort_order, row.start_time))
    provenance = [
        (
            f"Policy '{policy_slug_str(policy.slug)}' windows whose weekday is {weekday} "
            f"on {on.isoformat()} (start-day rows; overnight tails stay on the start weekday)"
        ),
        "Placer eligibility uses the shared window materializer (Working clip or General for unclassified)",
    ]
    return windows, provenance
