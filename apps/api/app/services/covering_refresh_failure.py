"""Covering-refresh failure durable unit (Decision 2 §4.2 / V38 same-sub).

Do not call ``persist_subscription_refresh_failures_autonomous`` from this
path. That helper commits on a side ``SessionLocal`` with no owner lock, no
account-identity lock, and no compare against the pre-attempt generation. It
can ``begin_subscription_refresh`` and clear a success that a later attempt
already minted. Legacy sync keeps using it. Covering does not.

This unit opens its own session and commits or rolls back that session.

Caller must already have rolled back or committed the import transaction and
left ``covering_unit_locks`` (same-thread deadlock otherwise).

V38 same-sub
------------
1. Import reads ``durable_coverage_active_generation`` and
   ``durable_identity_fingerprint`` under locks **before**
   ``begin_subscription_refresh``, and returns them on
   ``ImportCoveringCacheResult.attempt``.
2. The import transaction rolls back. An in-memory generation increment from
   ``begin_subscription_refresh`` dies with that transaction. It is not the
   token this unit compares.
3. A newer covering success on the same subscription commits its own bumped
   generation, identity, and ``coverage_success_*``.
4. This unit reacquires account-identity → owner → ``subscription_refresh_lock``,
   ``populate_existing``-reads the row, and refuses to write when the durable
   generation or identity fingerprint differs from the snapshot, when a newer
   success generation is stored, or when the account/subscription was disabled
   or deleted.
5. When the durable tokens still match, the failure sidecar, failure columns,
   and any required scheduling revision bump commit in this same transaction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    UserSettings,
)
from app.scheduler.horizon import compute_horizon
from app.services.calendar_coverage import (
    begin_subscription_refresh,
    record_subscription_refresh_failure,
)
from app.services.covering_refresh_locks import (
    CoveringAccountMissing,
    CoveringAttemptSnapshot,
    CoveringLockOrderError,
    commit_covering_revision_if_required,
    covering_identity_fingerprint,
    covering_unit_locks,
)
from app.services.scheduling_revision import (
    immovable_busy_signature,
    lock_owner_scheduling,
    trust_blocking_signature,
)

logger = logging.getLogger(__name__)

REFUSE_SUBSCRIPTION_MISSING = "subscription_missing"
REFUSE_ACCOUNT_MISSING = "account_missing"
REFUSE_ACCOUNT_DISABLED = "account_disabled"
REFUSE_SUBSCRIPTION_DISABLED = "subscription_disabled"
REFUSE_SUPERSEDED_GENERATION = "superseded_generation"
REFUSE_SUPERSEDED_IDENTITY = "superseded_identity"
REFUSE_SUPERSEDED_SUCCESS = "superseded_success"


@dataclass(frozen=True)
class CoveringFailurePersistResult:
    subscription_id: UUID
    persisted: bool
    refused: bool
    refuse_reason: str | None
    scheduling_revision_bumped: bool
    scheduling_revision: int | None
    cause: str | None


def covering_failure_overwrite_refusal(
    subscription: CalendarSubscription | None,
    account: CalendarAccount | None,
    attempt: CoveringAttemptSnapshot,
) -> str | None:
    """Return a refuse reason when a late failure must not overwrite durable state.

    ``None`` means the durable row still matches the pre-attempt snapshot and
    a failure write is allowed. Comparison uses the snapshot's durable
    generation, never a rolled-back in-memory increment.
    """
    if subscription is None or subscription.id != attempt.subscription_id:
        return REFUSE_SUBSCRIPTION_MISSING
    if account is None or account.id != attempt.account_id:
        return REFUSE_ACCOUNT_MISSING
    if subscription.owner_id != attempt.owner_id or account.owner_id != attempt.owner_id:
        return REFUSE_SUPERSEDED_IDENTITY
    if not bool(account.is_enabled):
        return REFUSE_ACCOUNT_DISABLED
    if not bool(subscription.is_enabled):
        return REFUSE_SUBSCRIPTION_DISABLED
    durable_generation = int(subscription.coverage_active_generation or 0)
    if durable_generation != int(attempt.durable_coverage_active_generation):
        return REFUSE_SUPERSEDED_GENERATION
    if covering_identity_fingerprint(subscription) != attempt.durable_identity_fingerprint:
        return REFUSE_SUPERSEDED_IDENTITY
    if subscription.coverage_success_at is not None:
        current_success = subscription.coverage_success_generation
        current_success_int = None if current_success is None else int(current_success)
        if current_success_int != attempt.durable_coverage_success_generation:
            return REFUSE_SUPERSEDED_SUCCESS
    return None


def _ensure_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _upsert_failure_sidecar(
    db: Session,
    *,
    subscription_id: UUID,
    now: datetime,
    cause: str,
) -> None:
    stmt = pg_insert(CalendarSubscriptionRefreshFailure).values(
        id=uuid4(),
        subscription_id=subscription_id,
        failure_at=now,
        cause=cause,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["subscription_id"],
        set_={
            "failure_at": stmt.excluded.failure_at,
            "cause": stmt.excluded.cause,
        },
    )
    db.execute(stmt)


def _write_failure_state(
    db: Session,
    subscription: CalendarSubscription,
    *,
    now: datetime,
    cause: str,
) -> None:
    """Clear a still-current prior success, then write columns and the sidecar.

    ``begin_subscription_refresh`` deletes any sidecar row. The upsert runs
    after that so this transaction's sidecar survives the supersede.
    """
    if subscription.coverage_success_at is not None:
        begin_subscription_refresh(subscription, now=now)
    record_subscription_refresh_failure(subscription, now=now, cause=cause)
    db.flush()
    _upsert_failure_sidecar(
        db,
        subscription_id=subscription.id,
        now=now,
        cause=cause,
    )


def _refused(
    *,
    subscription_id: UUID,
    reason: str,
    revision: int | None,
    cause: str,
) -> CoveringFailurePersistResult:
    return CoveringFailurePersistResult(
        subscription_id=subscription_id,
        persisted=False,
        refused=True,
        refuse_reason=reason,
        scheduling_revision_bumped=False,
        scheduling_revision=revision,
        cause=cause,
    )


def persist_covering_refresh_failure(
    *,
    attempt: CoveringAttemptSnapshot,
    now: datetime,
    cause: str,
) -> CoveringFailurePersistResult:
    """Reacquire §7 locks and commit failure state, or refuse.

    Lock order: account-identity → owner → in-process subscription lock.
    The generation compared is the row's persisted ``coverage_active_generation``
    after ``populate_existing``, against ``attempt.durable_coverage_active_generation``.
    """
    if attempt.subscription_id is None:
        raise CoveringLockOrderError("failure unit requires a subscription id on the snapshot")
    cause_s = (cause or "covering_refresh_failed")[:128]
    now_utc = _ensure_utc(now)
    db = SessionLocal()
    try:
        return _persist_in_session(
            db,
            attempt=attempt,
            now=now_utc,
            cause=cause_s,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _persist_in_session(
    db: Session,
    *,
    attempt: CoveringAttemptSnapshot,
    now: datetime,
    cause: str,
) -> CoveringFailurePersistResult:
    try:
        with covering_unit_locks(
            db,
            owner_id=attempt.owner_id,
            account_id=attempt.account_id,
            subscription_id=attempt.subscription_id,
        ):
            account = (
                db.query(CalendarAccount)
                .filter(CalendarAccount.id == attempt.account_id)
                .populate_existing()
                .one_or_none()
            )
            subscription = (
                db.query(CalendarSubscription)
                .filter(CalendarSubscription.id == attempt.subscription_id)
                .populate_existing()
                .one_or_none()
            )
            settings = lock_owner_scheduling(db, attempt.owner_id)
            revision_now = int(settings.scheduling_revision)
            refusal = covering_failure_overwrite_refusal(subscription, account, attempt)
            if refusal is not None:
                logger.info(
                    "covering failure unit refused subscription=%s reason=%s",
                    attempt.subscription_id,
                    refusal,
                )
                db.rollback()
                return _refused(
                    subscription_id=attempt.subscription_id,
                    reason=refusal,
                    revision=revision_now,
                    cause=cause,
                )
            assert subscription is not None
            assert account is not None
            return _commit_failure(
                db,
                settings=settings,
                subscription=subscription,
                attempt=attempt,
                now=now,
                cause=cause,
            )
    except CoveringAccountMissing:
        db.rollback()
        return _refused(
            subscription_id=attempt.subscription_id,
            reason=REFUSE_ACCOUNT_MISSING,
            revision=None,
            cause=cause,
        )


def _commit_failure(
    db: Session,
    *,
    settings: UserSettings,
    subscription: CalendarSubscription,
    attempt: CoveringAttemptSnapshot,
    now: datetime,
    cause: str,
) -> CoveringFailurePersistResult:
    horizon_start, horizon_end = compute_horizon(settings, now)
    before_busy = immovable_busy_signature(db, attempt.owner_id)
    before_trust = trust_blocking_signature(
        db,
        attempt.owner_id,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    _write_failure_state(db, subscription, now=now, cause=cause)
    # Failure-state is durable in this transaction. Force the revision bump
    # when the busy/trust signature helper does not already bump (§4.2, V39).
    bumped, revision = commit_covering_revision_if_required(
        db,
        settings,
        attempt.owner_id,
        before_busy=before_busy,
        before_trust=before_trust,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        force=True,
    )
    db.commit()
    logger.info(
        "covering failure unit persisted subscription=%s cause=%s revision_bumped=%s",
        attempt.subscription_id,
        cause,
        bumped,
    )
    return CoveringFailurePersistResult(
        subscription_id=attempt.subscription_id,
        persisted=True,
        refused=False,
        refuse_reason=None,
        scheduling_revision_bumped=bumped,
        scheduling_revision=revision,
        cause=cause,
    )
