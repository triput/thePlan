"""Availability policy read/update (S2-V3 placer SoT).

Working and General window writes bump ``scheduling_revision``. They do not
rewrite deprecated ``workweek_*`` mirrors. Split, gapped, and mixed-hours
Working patterns store. Personal window writes stay locked.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.models import AvailabilityPolicy, AvailabilityWindow, User
from app.models.enums import AvailabilityPolicySlug
from app.schemas.availability import AvailabilityPolicyUpdate, AvailabilityWindowIn
from app.services.availability_seed import derive_window_end
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling


def list_policies(db: Session, user: User) -> list[AvailabilityPolicy]:
    return (
        db.query(AvailabilityPolicy)
        .options(joinedload(AvailabilityPolicy.windows))
        .filter(AvailabilityPolicy.owner_id == user.id)
        .order_by(AvailabilityPolicy.sort_order, AvailabilityPolicy.slug)
        .all()
    )


def _parse_policy_ref(ref: str) -> uuid.UUID | AvailabilityPolicySlug:
    try:
        return uuid.UUID(ref)
    except ValueError:
        pass
    try:
        return AvailabilityPolicySlug(ref.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability policy not found",
        ) from exc


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
        policy = query.filter(AvailabilityPolicy.slug == parsed).one_or_none()
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


_ELIGIBILITY_SLUGS = frozenset(
    {AvailabilityPolicySlug.work, AvailabilityPolicySlug.general}
)


def update_policy(
    db: Session,
    user: User,
    policy: AvailabilityPolicy,
    body: AvailabilityPolicyUpdate,
) -> AvailabilityPolicy:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return policy

    if policy.slug == AvailabilityPolicySlug.personal and body.windows is not None:
        raise ApiError(
            422,
            "Personal availability stays empty in S1; edit General or Working instead",
            "PERSONAL_WINDOWS_LOCKED",
        )

    eligibility_write = body.windows is not None and policy.slug in _ELIGIBILITY_SLUGS
    scheduling_settings = lock_owner_scheduling(db, user.id) if eligibility_write else None

    if "name" in updates and updates["name"] is not None:
        policy.name = updates["name"].strip()

    if body.windows is not None:
        policy.windows.clear()
        db.flush()
        for window in _build_windows(user.id, policy.id, body.windows):
            policy.windows.append(window)

    if eligibility_write and scheduling_settings is not None:
        increment_scheduling_revision(db, scheduling_settings)

    db.flush()
    return policy


def effective_windows_for_date(policy: AvailabilityPolicy, on: date) -> tuple[list[AvailabilityWindow], list[str]]:
    weekday = on.weekday()
    windows = [window for window in policy.windows if window.weekday == weekday]
    windows.sort(key=lambda row: (row.sort_order, row.start_time))
    provenance = [
        (
            f"Policy '{policy.slug.value}' windows whose weekday is {weekday} "
            f"on {on.isoformat()} (start-day rows; overnight tails stay on the start weekday)"
        ),
        "Placer eligibility uses the shared window materializer (Working clip or General for unclassified)",
    ]
    return windows, provenance
