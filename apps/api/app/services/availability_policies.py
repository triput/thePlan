"""Availability policy read/update (S1 config-only).

Working windows update deprecated ``workweek_*`` mirrors only when the pattern
is Monday-first and same-hours. A shifted contiguous pattern is stored on the
policy and does not retarget the legacy placer. ``scheduling_effective`` stays
false either way. Ambiguous, gapped, and mixed-hours patterns are still rejected.
"""

from __future__ import annotations

import uuid
from datetime import date, time

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.models import AvailabilityPolicy, AvailabilityWindow, User, UserSettings
from app.models.enums import AvailabilityPolicySlug
from app.schemas.availability import AvailabilityPolicyUpdate, AvailabilityWindowIn
from app.services.auth_users import get_or_provision_user_settings
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


def _sync_workweek_from_working_windows(settings: UserSettings, windows: list[AvailabilityWindow]) -> bool:
    """Update deprecated workweek_* only for a Monday-first same-hours pattern.

    ``is_workday`` treats ``workweek_days`` as Monday through N (``weekday() < N``).
    A Tuesday–Saturday block is contiguous and same-hours, but writing ``N = 5``
    would make Monday eligible and Saturday excluded. That pattern is stored on
    the Working policy and left config-only: this returns False and does not
    change ``workweek_days``, ``workday_start_local``, or ``workday_minutes``.

    Ambiguous, noncontiguous, and heterogeneous patterns still reject. Those
    writes roll back with the request, so legacy eligibility is unchanged.
    """
    if not windows:
        settings.workweek_days = 0
        return True
    by_weekday: dict[int, AvailabilityWindow] = {}
    for window in windows:
        if window.weekday in by_weekday:
            raise ApiError(
                422,
                "Working policy must have at most one window per weekday for S1 mirror sync",
                "WORKING_POLICY_AMBIGUOUS",
            )
        by_weekday[window.weekday] = window
    weekdays = sorted(by_weekday)
    if weekdays != list(range(weekdays[0], weekdays[0] + len(weekdays))):
        raise ApiError(
            422,
            "Working policy weekdays must be a contiguous block for S1 workweek mirror sync",
            "WORKING_POLICY_NONCONTIGUOUS",
        )
    durations = {window.duration_minutes for window in by_weekday.values()}
    starts = {window.start_time for window in by_weekday.values()}
    if len(durations) != 1 or len(starts) != 1:
        raise ApiError(
            422,
            "Working policy must use the same start and duration on each day for S1 mirror sync",
            "WORKING_POLICY_HETEROGENEOUS",
        )
    # Legacy mirror is Monday-first only. Contiguous blocks that start later
    # (Tue–Sat, weekend-only) cannot round-trip through workweek_days.
    if weekdays != list(range(len(weekdays))):
        return False
    anchor = by_weekday[weekdays[0]]
    settings.workweek_days = len(weekdays)
    settings.workday_start_local = anchor.start_time
    settings.workday_minutes = anchor.duration_minutes
    return True


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

    scheduling_settings: UserSettings | None = None
    if policy.slug == AvailabilityPolicySlug.work and body.windows is not None:
        scheduling_settings = lock_owner_scheduling(db, user.id)

    if "name" in updates and updates["name"] is not None:
        policy.name = updates["name"].strip()

    if body.windows is not None:
        policy.windows.clear()
        db.flush()
        for window in _build_windows(user.id, policy.id, body.windows):
            policy.windows.append(window)

    if policy.slug == AvailabilityPolicySlug.work and body.windows is not None:
        settings = get_or_provision_user_settings(db, user)
        mirrored = _sync_workweek_from_working_windows(settings, list(policy.windows))
        if mirrored and scheduling_settings is not None:
            increment_scheduling_revision(db, scheduling_settings)

    db.flush()
    return policy


def effective_windows_for_date(policy: AvailabilityPolicy, on: date) -> tuple[list[AvailabilityWindow], list[str]]:
    weekday = on.weekday()
    windows = [window for window in policy.windows if window.weekday == weekday]
    windows.sort(key=lambda row: (row.sort_order, row.start_time))
    provenance = [
        f"Config-only policy '{policy.slug.value}' windows for weekday {weekday} on {on.isoformat()}",
        "Placer does not consume availability policies until S2 cutover",
    ]
    return windows, provenance
