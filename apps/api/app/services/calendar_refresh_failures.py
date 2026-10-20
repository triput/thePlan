"""Shared calendar refresh failure persistence (T1-C Google; T1-E Microsoft reuse).

Commits durable unreadiness without committing or discarding unrelated caller
work: sidecar INSERT first (KEY SHARE beside a flushed row lock), then a
separate subscription-column UPDATE with lock_timeout. Callers expire only
coverage attributes this path writes so pending unflushed edits survive.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import CalendarSubscription

logger = logging.getLogger(__name__)

# Attr stamped on exceptions after failure evidence is committed so outer
# handlers do not double-persist the same failure.
_FAILURE_COMMITTED_ATTR = "_t1c_failure_committed"

# Columns this persist path may write. begin_subscription_refresh clears success
# evidence; record_subscription_refresh_failure sets the two failure markers.
# summary and sync_cursor are not among them and must not be expired.
FAILURE_PERSIST_EXPIRE_ATTRS = (
    "coverage_active_generation",
    "coverage_success_at",
    "coverage_fetched_at",
    "coverage_success_generation",
    "coverage_pagination_complete",
    "coverage_window_start",
    "coverage_window_end",
    "coverage_mode",
    "coverage_show_deleted",
    "coverage_single_events",
    "coverage_page_count",
    "coverage_item_count",
    "coverage_token_fingerprint",
    "coverage_last_failure_at",
    "coverage_last_failure_cause",
)


@dataclass(frozen=True)
class FailurePersistOutcome:
    committed_ids: frozenset[UUID]
    settled_ids: frozenset[UUID]
    unseen_ids: frozenset[UUID]


def failure_committed(exc: BaseException) -> bool:
    return bool(getattr(exc, _FAILURE_COMMITTED_ATTR, False))


def mark_failure_committed(exc: BaseException) -> None:
    setattr(exc, _FAILURE_COMMITTED_ATTR, True)


def failure_marker_applies(
    *,
    coverage_success_at: datetime | None,
    coverage_last_failure_at: datetime | None,
) -> bool:
    if coverage_success_at is not None:
        return True
    return coverage_last_failure_at is None


def apply_subscription_failure_marker(
    subscription: CalendarSubscription,
    *,
    now: datetime,
    cause: str,
) -> bool:
    from app.services.calendar_coverage import (
        begin_subscription_refresh,
        record_subscription_refresh_failure,
    )

    if not failure_marker_applies(
        coverage_success_at=subscription.coverage_success_at,
        coverage_last_failure_at=subscription.coverage_last_failure_at,
    ):
        return False
    if subscription.coverage_success_at is not None:
        begin_subscription_refresh(subscription, now=now)
    record_subscription_refresh_failure(subscription, now=now, cause=cause)
    return True


def commit_refresh_failure_sidecar(
    subscription_ids: set[UUID],
    *,
    now: datetime,
    cause: str,
) -> tuple[frozenset[UUID], frozenset[UUID]]:
    """Commit sidecar rows. Returns (written_ids, unseen_ids).

    INSERT only — no UPDATE of calendar_subscriptions — so the foreign key's
    FOR KEY SHARE can land beside a caller's flushed row lock. Lock timeout
    returns empty sets; the caller still attempts the column update.
    """
    from app.db import SessionLocal
    from app.models.calendar import CalendarSubscriptionRefreshFailure

    independent = SessionLocal()
    try:
        independent.execute(text("SET LOCAL lock_timeout = '2s'"))
        found = independent.execute(
            select(
                CalendarSubscription.id,
                CalendarSubscription.coverage_success_at,
                CalendarSubscription.coverage_last_failure_at,
            ).where(CalendarSubscription.id.in_(subscription_ids))
        ).all()
        seen_ids = {row.id for row in found}
        unseen_ids = frozenset(subscription_ids - seen_ids)
        needed = [
            row.id
            for row in found
            if failure_marker_applies(
                coverage_success_at=row.coverage_success_at,
                coverage_last_failure_at=row.coverage_last_failure_at,
            )
        ]
        if not needed:
            independent.rollback()
            return frozenset(), unseen_ids
        cause_s = cause[:128]
        stmt = pg_insert(CalendarSubscriptionRefreshFailure).values(
            [
                {
                    "id": uuid4(),
                    "subscription_id": subscription_id,
                    "failure_at": now,
                    "cause": cause_s,
                }
                for subscription_id in needed
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["subscription_id"],
            set_={
                "failure_at": stmt.excluded.failure_at,
                "cause": stmt.excluded.cause,
            },
        )
        independent.execute(stmt)
        independent.commit()
        return frozenset(needed), unseen_ids
    except OperationalError:
        independent.rollback()
        logger.warning(
            "calendar refresh failure sidecar insert hit lock_timeout",
            exc_info=True,
        )
        return frozenset(), frozenset()
    finally:
        independent.close()


def commit_subscription_failure_columns(
    subscription_ids: set[UUID],
    *,
    now: datetime,
    cause: str,
) -> FailurePersistOutcome | None:
    """Mirror failure columns onto calendar_subscriptions.

    Returns None when the UPDATE hits lock_timeout. That transaction is rolled
    back and does not undo a sidecar commit from the previous transaction.
    """
    from app.db import SessionLocal

    independent = SessionLocal()
    try:
        independent.execute(text("SET LOCAL lock_timeout = '2s'"))
        rows = (
            independent.query(CalendarSubscription)
            .filter(CalendarSubscription.id.in_(subscription_ids))
            .all()
        )
        seen_ids = {row.id for row in rows}
        unseen_ids = frozenset(subscription_ids - seen_ids)
        committed: set[UUID] = set()
        settled: set[UUID] = set()
        for subscription in rows:
            if apply_subscription_failure_marker(subscription, now=now, cause=cause):
                committed.add(subscription.id)
            else:
                settled.add(subscription.id)
        if committed:
            independent.commit()
        else:
            independent.rollback()
        return FailurePersistOutcome(
            frozenset(committed),
            frozenset(settled),
            unseen_ids,
        )
    except OperationalError:
        independent.rollback()
        logger.warning(
            "calendar subscription failure UPDATE hit lock_timeout; sidecar remains",
            exc_info=True,
        )
        return None
    finally:
        independent.close()


def persist_subscription_refresh_failures_autonomous(
    subscription_ids: set[UUID],
    *,
    now: datetime,
    cause: str,
) -> FailurePersistOutcome:
    """Commit failure evidence in separate transactions (sole production path).

    Sidecar INSERT commits first (KEY SHARE, compatible with a flushed caller
    row lock). The subscription UPDATE is a second transaction with
    lock_timeout 2s. On lock wait that transaction rolls back and the sidecar
    stays. Neither transaction commits or reverts the caller session.
    """
    empty = FailurePersistOutcome(frozenset(), frozenset(), frozenset())
    if not subscription_ids:
        return empty

    _sidecar_ids, sidecar_unseen = commit_refresh_failure_sidecar(
        subscription_ids,
        now=now,
        cause=cause,
    )
    row_outcome = commit_subscription_failure_columns(
        subscription_ids,
        now=now,
        cause=cause,
    )
    if row_outcome is None:
        # Column UPDATE timed out. Sidecar (if it committed) is the durable
        # signal; do not report committed_ids or the caller would expire.
        if not _sidecar_ids:
            logger.warning(
                "calendar failure UPDATE hit lock_timeout and sidecar did not commit"
            )
        return FailurePersistOutcome(frozenset(), frozenset(), sidecar_unseen)
    return row_outcome


def persist_subscription_refresh_failures(
    db: Session,
    subscriptions: list[CalendarSubscription],
    *,
    now: datetime,
    cause: str,
) -> None:
    """Persist failure markers via autonomous SessionLocal only.

    Caller session is never committed or reverted. Rows whose failure columns
    committed are expired only on the coverage attributes this path writes, so
    a later flush cannot restore stale success evidence and unflushed caller
    attributes (summary, sync_cursor) stay put. Unseen (uncommitted) rows get
    an in-memory marker only. Lock-timeout leaves instances alone; the sidecar
    is what the trust gate reads after the caller rolls back.
    """
    if not subscriptions:
        return

    subscription_ids = {subscription.id for subscription in subscriptions}
    outcome = persist_subscription_refresh_failures_autonomous(
        subscription_ids,
        now=now,
        cause=cause,
    )
    for subscription in subscriptions:
        if subscription.id in outcome.committed_ids:
            db.expire(subscription, list(FAILURE_PERSIST_EXPIRE_ATTRS))
        elif subscription.id in outcome.unseen_ids:
            apply_subscription_failure_marker(subscription, now=now, cause=cause)


def commit_pre_pull_refresh_failure(
    db: Session,
    subscriptions: list[CalendarSubscription],
    *,
    now: datetime,
    cause: str,
) -> None:
    """Persist not-ready evidence when auth fails before any subscription pull.

    Does not clear cache rows or sync cursors — only failure markers are committed.
    """
    persist_subscription_refresh_failures(db, subscriptions, now=now, cause=cause)


def commit_refresh_failure(
    db: Session,
    subscription: CalendarSubscription,
    *,
    now: datetime,
    cause: str,
) -> None:
    """Persist not-ready evidence for one subscription after a failed refresh.

    Cache writes for the failed attempt live in a savepoint that has already
    been rolled back. Failure markers are committed in an isolated transaction
    so they survive caller rollback without unrelated caller state.
    """
    persist_subscription_refresh_failures(db, [subscription], now=now, cause=cause)
