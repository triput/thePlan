"""§7 lock stack and durable attempt tokens for covering-refresh.

Caller protocol (import unit)
-----------------------------
``import_covering_subscription_cache`` does **not** acquire locks and does
**not** commit. Justin acquires this stack, calls import, then commits or
rolls back before leaving the ``with`` block:

1. ``lock_calendar_account_for_identity`` (txn advisory + account ``FOR UPDATE``)
2. ``lock_owner_scheduling`` (txn advisory + settings ``FOR UPDATE``)
3. ``subscription_refresh_lock`` (in-process, after 1–2)

That is the same total order as legacy ``prepare_subscriptions_for_sync``
(account identity lock) followed by ``sync_account_events`` (owner lock, then
the in-process subscription lock). Do not take the owner lock and then the
account lock. Do not take the in-process subscription lock and then a DB lock.

``pg_advisory_xact_lock`` is reentrant inside one transaction, so import may
call ``lock_owner_scheduling`` again while this context is active. It is **not**
a second owner. The in-process lock is a ``threading.Lock`` and is **not**
reentrant. Failure and token units open their own sessions and acquire this
same stack; call them only after this ``with`` block has exited and the import
transaction has committed or rolled back. Calling them on the same thread
while this block still holds the advisory locks deadlocks.

No new schema. The identity fingerprint is a hash of columns that already
exist on ``calendar_subscriptions``.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator
from uuid import UUID

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from app.models import CalendarAccount, CalendarSubscription, UserSettings
from app.models.enums import CalendarSubscriptionRole
from app.services.calendar_alias_canonicalize import lock_calendar_account_for_identity
from app.services.calendar_coverage import subscription_refresh_lock
from app.services.scheduling_revision import (
    increment_scheduling_revision,
    increment_scheduling_revision_if_busy_or_trust_changed,
    lock_owner_scheduling,
)

_RECEIPT_MINT = object()


class CoveringLockOrderError(Exception):
    """Caller skipped the §7 stack, or the row triple does not match."""

    def __init__(self, detail: str) -> None:
        self.code = "CALENDAR_COVERING_LOCK_ORDER"
        self.detail = detail
        super().__init__(detail)


class CoveringAccountMissing(Exception):
    """Account row was gone when the identity lock was taken (disconnect/delete)."""

    def __init__(self, account_id: UUID) -> None:
        self.account_id = account_id
        self.code = "CALENDAR_ACCOUNT_MISSING"
        self.detail = "Calendar account row is gone"
        super().__init__(self.detail)


@dataclass(frozen=True)
class CoveringUnitLockReceipt:
    """Proof that ``covering_unit_locks`` acquired the §7 stack.

    Constructed only inside that context manager. Import refuses a receipt
    whose ids do not match the subscription it was asked to pull.
    """

    owner_id: UUID
    account_id: UUID
    subscription_id: UUID
    account_identity_locked: bool
    _mint: object


@dataclass(frozen=True)
class CoveringAttemptSnapshot:
    """Durable pre-attempt tokens, copied off the ORM before this attempt mutates.

    ``durable_coverage_active_generation`` is the generation read from the
    database under the §7 locks **before** ``begin_subscription_refresh``.
    A generation increment that later rolls back is not a persisted token and
    must not be written into this snapshot.

    ``durable_identity_fingerprint`` covers the pull identity and enablement
    stored on the subscription row (external calendar id, role, is_enabled),
    not an in-transaction rewrite that has not committed.
    """

    subscription_id: UUID
    account_id: UUID
    owner_id: UUID
    durable_identity_fingerprint: str
    durable_coverage_active_generation: int
    durable_coverage_success_generation: int | None


def covering_identity_fingerprint(subscription: CalendarSubscription) -> str:
    """Stable fingerprint of stored pull identity. No extra column."""
    role = subscription.role
    role_token = role.value if isinstance(role, CalendarSubscriptionRole) else str(role)
    enabled = "1" if bool(subscription.is_enabled) else "0"
    material = "\n".join(
        (
            str(subscription.id),
            str(subscription.calendar_account_id),
            str(subscription.external_calendar_id),
            role_token,
            enabled,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def snapshot_covering_attempt(
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
) -> CoveringAttemptSnapshot:
    """Copy durable identity and generation off rows already refreshed under locks.

    Call this before prepare rewrites and before ``begin_subscription_refresh``.
    """
    if subscription.calendar_account_id != account.id:
        raise CoveringLockOrderError(
            "subscription does not belong to the locked calendar account"
        )
    if subscription.owner_id != account.owner_id:
        raise CoveringLockOrderError("subscription owner does not match the account owner")
    success_generation = subscription.coverage_success_generation
    return CoveringAttemptSnapshot(
        subscription_id=subscription.id,
        account_id=account.id,
        owner_id=account.owner_id,
        durable_identity_fingerprint=covering_identity_fingerprint(subscription),
        durable_coverage_active_generation=int(subscription.coverage_active_generation or 0),
        durable_coverage_success_generation=(
            None if success_generation is None else int(success_generation)
        ),
    )


def receipt_is_live(receipt: object) -> bool:
    return (
        isinstance(receipt, CoveringUnitLockReceipt)
        and receipt._mint is _RECEIPT_MINT
        and receipt.account_identity_locked is True
    )


def require_covering_receipt(
    receipt: object,
    *,
    owner_id: UUID,
    account_id: UUID,
    subscription_id: UUID,
) -> CoveringUnitLockReceipt:
    """Reject a missing, forged, or mismatched lock receipt."""
    if not receipt_is_live(receipt):
        raise CoveringLockOrderError(
            "covering import requires covering_unit_locks "
            "(account identity → owner → subscription_refresh_lock)"
        )
    assert isinstance(receipt, CoveringUnitLockReceipt)
    if (
        receipt.owner_id != owner_id
        or receipt.account_id != account_id
        or receipt.subscription_id != subscription_id
    ):
        raise CoveringLockOrderError(
            "lock receipt does not match the subscription unit being imported"
        )
    return receipt


@contextmanager
def covering_unit_locks(
    db: Session,
    *,
    owner_id: UUID,
    account_id: UUID,
    subscription_id: UUID,
) -> Iterator[CoveringUnitLockReceipt]:
    """Acquire account-identity → owner → in-process subscription lock.

    Does not commit. Transaction-scoped locks release when the caller commits
    or rolls back. The caller must do that before invoking a token or failure
    durable unit, and must exit this block first so the in-process lock drops.
    """
    try:
        account = lock_calendar_account_for_identity(db, account_id)
    except NoResultFound as exc:
        raise CoveringAccountMissing(account_id) from exc
    if account.owner_id != owner_id:
        raise CoveringLockOrderError("calendar account belongs to a different owner")
    lock_owner_scheduling(db, owner_id)
    with subscription_refresh_lock(subscription_id):
        subscription = (
            db.query(CalendarSubscription)
            .filter(CalendarSubscription.id == subscription_id)
            .with_for_update()
            .populate_existing()
            .one_or_none()
        )
        if subscription is not None:
            if subscription.owner_id != owner_id:
                raise CoveringLockOrderError("subscription belongs to a different owner")
            if subscription.calendar_account_id != account_id:
                raise CoveringLockOrderError(
                    "subscription belongs to a different calendar account"
                )
        yield CoveringUnitLockReceipt(
            owner_id=owner_id,
            account_id=account_id,
            subscription_id=subscription_id,
            account_identity_locked=True,
            _mint=_RECEIPT_MINT,
        )


def commit_covering_revision_if_required(
    db: Session,
    settings: UserSettings,
    owner_id: UUID,
    *,
    before_busy: tuple[tuple[str, str, str], ...],
    before_trust: tuple[tuple[str, str, str, str], ...],
    horizon_start: datetime,
    horizon_end: datetime,
    force: bool,
) -> tuple[bool, int]:
    """Bump scheduling revision inside the caller's owner-locked transaction.

    Uses the legacy busy/trust signature compare. ``force`` covers covering
    mutations that signature does not see: failure-state writes and requested
    pull-identity / eligibility changes (§4.2). At most one increment per call.
    Does not commit.
    """
    bumped_to = increment_scheduling_revision_if_busy_or_trust_changed(
        db,
        settings,
        owner_id,
        before_busy=before_busy,
        before_trust=before_trust,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    if bumped_to is None and force:
        bumped_to = increment_scheduling_revision(db, settings)
    return bumped_to is not None, int(settings.scheduling_revision)
