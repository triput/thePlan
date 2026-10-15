"""Availability policies — S1 config-only (§0.3)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.availability import (
    AvailabilityPolicyCreate,
    AvailabilityPolicyEffectiveOut,
    AvailabilityPolicyOut,
    AvailabilityPolicyUpdate,
    AvailabilityWindowOut,
)
from app.services.availability_policies import (
    create_policy,
    effective_windows_for_date,
    get_policy,
    list_policies,
    update_policy,
)
from app.services.availability_slug import policy_slug_str
from app.services.s2_v3_availability_guard import (
    policy_scheduling_effective_for_slug,
    scheduling_effective_note_for_policy_slug,
)

router = APIRouter(prefix="/availability-policies", tags=["availability"])


def _policy_out(policy) -> AvailabilityPolicyOut:
    slug_value = policy_slug_str(policy.slug)
    return AvailabilityPolicyOut.model_validate(
        {
            "id": policy.id,
            "slug": policy.slug,
            "name": policy.name,
            "sort_order": policy.sort_order,
            "scheduling_effective": policy_scheduling_effective_for_slug(slug_value),
            "scheduling_effective_note": scheduling_effective_note_for_policy_slug(slug_value),
            "windows": [AvailabilityWindowOut.model_validate(window) for window in policy.windows],
        }
    )


@router.get("", response_model=list[AvailabilityPolicyOut])
def availability_policies_list(
    slug: str | None = Query(default=None, description="Optional filter by stable slug"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AvailabilityPolicyOut]:
    rows = list_policies(db, user)
    if slug is not None:
        needle = slug.strip().lower()
        rows = [row for row in rows if policy_slug_str(row.slug) == needle]
    return [_policy_out(row) for row in rows]


@router.post("", response_model=AvailabilityPolicyOut, status_code=status.HTTP_201_CREATED)
def availability_policy_create(
    body: AvailabilityPolicyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AvailabilityPolicyOut:
    policy = create_policy(db, user, body)
    db.commit()
    refreshed = get_policy(db, user, str(policy.id))
    return _policy_out(refreshed)


@router.get("/{policy_ref}", response_model=AvailabilityPolicyOut)
def availability_policy_get(
    policy_ref: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AvailabilityPolicyOut:
    return _policy_out(get_policy(db, user, policy_ref))


@router.patch("/{policy_ref}", response_model=AvailabilityPolicyOut)
def availability_policy_patch(
    policy_ref: str,
    body: AvailabilityPolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AvailabilityPolicyOut:
    policy = get_policy(db, user, policy_ref)
    updated = update_policy(db, user, policy, body)
    db.commit()
    refreshed = get_policy(db, user, str(updated.id))
    return _policy_out(refreshed)


@router.get("/{policy_ref}/effective", response_model=AvailabilityPolicyEffectiveOut)
def availability_policy_effective(
    policy_ref: str,
    on: date = Query(..., description="Local calendar date (owner timezone semantics)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AvailabilityPolicyEffectiveOut:
    policy = get_policy(db, user, policy_ref)
    windows, provenance = effective_windows_for_date(policy, on)
    slug_value = policy_slug_str(policy.slug)
    return AvailabilityPolicyEffectiveOut(
        policy_id=policy.id,
        slug=slug_value,
        on_date=on,
        scheduling_effective=policy_scheduling_effective_for_slug(slug_value),
        scheduling_effective_note=scheduling_effective_note_for_policy_slug(slug_value),
        windows=[AvailabilityWindowOut.model_validate(window) for window in windows],
        provenance=provenance,
    )
