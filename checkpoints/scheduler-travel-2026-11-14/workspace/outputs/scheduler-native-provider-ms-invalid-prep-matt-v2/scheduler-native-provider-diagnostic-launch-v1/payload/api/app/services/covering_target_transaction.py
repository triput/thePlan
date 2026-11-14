"""Root transaction orchestration for one admitted covering target."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime
from enum import Enum, auto
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.covering_refresh_failure import (
    CoveringFailurePersistResult,
    record_covering_refresh_failure_in_session,
)
from app.services.covering_refresh_import import ImportCoveringCacheResult, OUTCOME_FAILED
from app.services.covering_refresh_locks import CoveringUnitLockReceipt


class RootOutcome(Enum):
    COMMIT_ACKNOWLEDGED = auto()
    ROLLBACK_ACKNOWLEDGED = auto()
    COMMIT_DEADLINE_ROLLBACK_ACKNOWLEDGED = auto()
    UNKNOWN = auto()


class CoveringRootOutcomeUnknown(Exception):
    """The route must stop before any later target or assessment."""

    completed_results: tuple[ImportCoveringCacheResult, ...] = ()
    parent_acknowledgment: tuple[RootOutcome, ImportCoveringCacheResult] | None = None


class CoveringFailureAdmissionExpired(Exception):
    """The one-use recorder was refused before attempting checkout."""


class CoveringTargetConnections(Protocol):
    """A request-owned adapter bound to one captured parent root and driver."""

    def finish_root(self, *, commit: bool) -> RootOutcome:
        """Resolve the exact root. Reuse a captured flush-rollback acknowledgment.

        A savepoint, ORM state, connection close, or a driver idle status alone
        cannot establish the outcome. Once unknown, issue no subsequent SQL.
        """
        ...

    def retire_parent(self) -> bool:
        """Retire the exact parent locally and report whether retirement is proven."""
        ...

    def open_failure_session(self) -> AbstractContextManager[Session]:
        """Consume one permit after acknowledged rollback and retirement.

        Own the fresh failure connection and its deadline and transaction
        acknowledgments. Raise CoveringRootOutcomeUnknown on uncertainty.
        Raise CoveringFailureAdmissionExpired only before attempting checkout.
        """
        ...


class CoveringTargetTransaction:
    """Order one target's root, lock release, retirement and recorder."""

    def __init__(self, connections: CoveringTargetConnections) -> None:
        self._connections = connections
        self._used = False

    def run(
        self,
        *,
        owner_id: UUID,
        account_id: UUID,
        subscription_id: UUID,
        locks: AbstractContextManager[CoveringUnitLockReceipt],
        apply: Callable[[CoveringUnitLockReceipt], ImportCoveringCacheResult],
        now: datetime,
    ) -> tuple[ImportCoveringCacheResult, CoveringFailurePersistResult | None]:
        if self._used:
            raise RuntimeError("covering target transaction already used")
        self._used = True

        with locks as receipt:
            if (receipt.owner_id, receipt.account_id, receipt.subscription_id) != (
                owner_id, account_id, subscription_id
            ):
                raise RuntimeError("covering target lock identity mismatch")
            result = apply(receipt)
            if result.subscription_id != subscription_id or (
                result.commit_unit and result.rollback_required
            ):
                raise RuntimeError("covering target result mismatch")
            attempt = result.attempt
            cause = result.cause
            if result.needs_failure_unit and (
                result.outcome != OUTCOME_FAILED
                or not result.rollback_required
                or attempt is None
                or not cause
                or (attempt.owner_id, attempt.account_id, attempt.subscription_id)
                != (owner_id, account_id, subscription_id)
            ):
                raise RuntimeError("covering failure result is ineligible")
            expected = (
                RootOutcome.COMMIT_ACKNOWLEDGED
                if result.commit_unit
                else RootOutcome.ROLLBACK_ACKNOWLEDGED
            )
            terminal = self._connections.finish_root(commit=result.commit_unit)
            if (
                result.commit_unit
                and terminal is RootOutcome.COMMIT_DEADLINE_ROLLBACK_ACKNOWLEDGED
            ):
                expected = RootOutcome.ROLLBACK_ACKNOWLEDGED
                result = replace(
                    result,
                    outcome=OUTCOME_FAILED,
                    cause="CALENDAR_REFRESH_DEADLINE_EXCEEDED",
                    preflight_effects=(),
                    upserted=0,
                    commit_unit=False,
                    rollback_required=True,
                    needs_failure_unit=False,
                    coverage_generation_minted=None,
                    scheduling_revision_bumped=False,
                    scheduling_revision=None,
                )
            elif terminal is not expected:
                raise CoveringRootOutcomeUnknown()

        try:
            if not self._connections.retire_parent():
                raise CoveringRootOutcomeUnknown()
            if not result.needs_failure_unit:
                return result, None

            assert attempt is not None and cause
            try:
                with self._connections.open_failure_session() as failure_db:
                    failure = record_covering_refresh_failure_in_session(
                        failure_db, attempt=attempt, now=now, cause=cause
                    )
            except CoveringFailureAdmissionExpired:
                failure = CoveringFailurePersistResult(
                    subscription_id=subscription_id,
                    persisted=False,
                    refused=True,
                    refuse_reason="cleanup_deadline_exceeded",
                    scheduling_revision_bumped=False,
                    scheduling_revision=None,
                    cause=cause,
                )
        except CoveringRootOutcomeUnknown as exc:
            exc.parent_acknowledgment = (expected, result)
            raise
        return result, failure
