"""Covering-refresh import seam (Decision 2 §3, §4.2, §7).

``import_covering_subscription_cache`` is the only entry Justin should use to
pull one subscription. It does not commit. It does not acquire locks. It does
not call legacy ``sync_account_events``.

Caller protocol
---------------
1. ``read_covering_access_token`` — own session, §7 stack, commit only when
   OAuth credential columns changed. Finish it before opening the import
   transaction.
2. On the request session::

       with covering_unit_locks(db, owner_id=..., account_id=..., subscription_id=...) as receipt:
           result = import_covering_subscription_cache(..., lock_receipt=receipt)
           if result.commit_unit and not result.rollback_required:
               db.commit()
           else:
               db.rollback()

3. Leave the ``with`` block (drops the in-process lock; commit/rollback drops
   the advisory locks).
4. If ``result.needs_failure_unit``, call ``persist_covering_refresh_failure``
   with ``result.attempt``. That snapshot's generation was read **before**
   ``begin_subscription_refresh``. Do not substitute an in-memory increment.

This module never composes tombstone retry, provider event deletes, or primary
bootstrap. Local pending-deletion ids are read and passed into the existing
apply helpers as ``suppressed_external_ids``.

Google covering clears ``sync_cursor`` on the targeted subscription inside the
import transaction before the pull, so the existing full-window list path runs.
Microsoft uses the existing ``ms_view`` pull and apply. Neither path writes
``account.last_synced_at`` (that stamp means a legacy account-wide sync).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CalendarAccount, CalendarSubscription, ExternalCalendarEvent
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.services.calendar_alias_canonicalize import (
    account_needs_live_identity_evidence,
    canonicalize_calendar_account,
    fetch_account_identity_evidence,
    subscription_blocked_for_identity,
)
from app.services.calendar_coverage import begin_subscription_refresh
from app.services.covering_refresh_locks import (
    CoveringAttemptSnapshot,
    CoveringLockOrderError,
    CoveringUnitLockReceipt,
    commit_covering_revision_if_required,
    covering_identity_fingerprint,
    covering_unit_locks,
    require_covering_receipt,
    snapshot_covering_attempt,
)
from app.services.covering_refresh_window import (
    CoveringPullWindow,
    effective_covering_pull_window,
)
from app.services.scheduling_revision import (
    immovable_busy_signature,
    lock_owner_scheduling,
    trust_blocking_signature,
)

logger = logging.getLogger(__name__)

OUTCOME_OK = "ok"
OUTCOME_FAILED = "failed"
OUTCOME_PREFLIGHT = "preflight_rejected"
OUTCOME_PROCEED = "proceed"

PREFLIGHT_SUBSCRIPTION_DISABLED = "CALENDAR_SUBSCRIPTION_DISABLED"
PREFLIGHT_ACCOUNT_DISABLED = "CALENDAR_ACCOUNT_DISABLED"
PREFLIGHT_ACCOUNT_DISCONNECTED = "CALENDAR_ACCOUNT_DISCONNECTED"
PREFLIGHT_IDENTITY_BLOCKED = "CALENDAR_IDENTITY_BLOCKED"
PREFLIGHT_SUBSCRIPTION_NOT_FOUND = "CALENDAR_SUBSCRIPTION_NOT_FOUND"
PREFLIGHT_EVIDENCE_UNAVAILABLE = "CALENDAR_IDENTITY_EVIDENCE_UNAVAILABLE"
PREFLIGHT_SUBSET_UNSAFE = "CALENDAR_PREPARE_SUBSET_UNSAFE"
PREFLIGHT_ROLE_CHANGE = "CALENDAR_PREPARE_ROLE_CHANGE"
EFFECT_CANONICALIZE_IDENTITY = "canonicalize_identity"

CAUSE_POST_FETCH_DISABLED = "covering_post_fetch_disabled"
CAUSE_POST_FETCH_DISCONNECTED = "covering_post_fetch_disconnected"
CAUSE_POST_FETCH_IDENTITY = "covering_post_fetch_identity"
CAUSE_POST_FETCH_GENERATION = "covering_post_fetch_generation"
CAUSE_PROVIDER_READ_FAILED = "covering_provider_read_failed"
CAUSE_PAGINATION_INCOMPLETE = "calendar_pagination_incomplete"
CAUSE_GOOGLE_FULL_REQUIRED = "covering_google_full_required"
CAUSE_GOOGLE_APPLY_FAILED = "google_apply_full_failed"
CAUSE_MS_APPLY_FAILED = "microsoft_apply_ms_view_failed"

_GUARD_FIELDS = (
    "external_calendar_id",
    "role",
    "is_enabled",
    "sync_cursor",
    "summary",
    "provider_timezone",
    "coverage_last_failure_cause",
    "coverage_active_generation",
    "coverage_success_at",
    "coverage_success_generation",
    "coverage_window_start",
    "coverage_window_end",
    "coverage_mode",
)


@dataclass(frozen=True)
class PrepareMutationDecision:
    """Pure diff of prepare's subscription-row writes. ``allowed`` keeps them."""

    allowed: bool
    preflight_code: str | None
    effects: tuple[str, ...]
    eligibility_mutated: bool


@dataclass(frozen=True)
class PrepareCoveringResult:
    outcome: str
    preflight_code: str | None
    preflight_effects: tuple[str, ...]
    eligibility_mutated: bool
    provider_identity_list_called: bool
    scheduling_revision_bumped: bool
    scheduling_revision: int | None


@dataclass(frozen=True)
class CoveringAccessTokenResult:
    access_token: str
    credentials_persisted: bool
    account_id: UUID
    subscription_id: UUID


@dataclass(frozen=True)
class ImportCoveringCacheResult:
    """Import unit result. Commit only when ``commit_unit`` and not ``rollback_required``.

    ``attempt`` is the durable pre-mutation snapshot. ``coverage_generation_minted``
    is set only for ``outcome=ok`` and becomes durable only if the caller commits.
    A rolled-back ``begin_subscription_refresh`` increment is never returned here.
    """

    subscription_id: UUID
    outcome: str
    preflight_code: str | None
    preflight_effects: tuple[str, ...]
    cause: str | None
    upserted: int
    rollback_required: bool
    commit_unit: bool
    needs_failure_unit: bool
    attempt: CoveringAttemptSnapshot | None
    window_effective_start: datetime
    window_effective_end: datetime
    window_widened: bool
    window_widen_reason: str
    coverage_generation_minted: int | None
    scheduling_revision_bumped: bool
    scheduling_revision: int | None
    provider_identity_list_called: bool
    provider_event_read_attempted: bool


@dataclass(frozen=True)
class _ProviderPull:
    events: list[dict[str, Any]]
    next_sync_token: str | None
    page_count: int
    pagination_complete: bool
    is_full: bool
    mode: str
    event_fetch_context: Any | None


def subscription_guard_view(subscription: CalendarSubscription) -> dict[str, object]:
    """Columns prepare must not silently change on a non-requested row."""
    role = subscription.role
    role_token = role.value if isinstance(role, CalendarSubscriptionRole) else str(role)
    success_generation = subscription.coverage_success_generation
    return {
        "external_calendar_id": subscription.external_calendar_id,
        "role": role_token,
        "is_enabled": bool(subscription.is_enabled),
        "sync_cursor": subscription.sync_cursor,
        "summary": subscription.summary,
        "provider_timezone": subscription.provider_timezone,
        "coverage_last_failure_cause": subscription.coverage_last_failure_cause,
        "coverage_active_generation": int(subscription.coverage_active_generation or 0),
        "coverage_success_at": subscription.coverage_success_at,
        "coverage_success_generation": (
            None if success_generation is None else int(success_generation)
        ),
        "coverage_window_start": subscription.coverage_window_start,
        "coverage_window_end": subscription.coverage_window_end,
        "coverage_mode": subscription.coverage_mode,
    }


def classify_covering_prepare_mutation(
    *,
    requested_id: UUID,
    before: Mapping[UUID, Mapping[str, object]],
    after: Mapping[UUID, Mapping[str, object]],
) -> PrepareMutationDecision:
    """Abort when prepare would touch another row, role, or enablement.

    A requested-row pull-identity rewrite (external calendar id and the
    coverage/cursor fields that travel with it) is allowed. Role and
    ``is_enabled`` on the requested row are not. Any column change on any
    other subscription row is not. Membership of the account's subscription
    id set must stay the same.
    """
    if requested_id not in before or requested_id not in after or set(before) != set(after):
        return PrepareMutationDecision(
            allowed=False,
            preflight_code=PREFLIGHT_SUBSET_UNSAFE,
            effects=(),
            eligibility_mutated=False,
        )
    for sub_id, prior in before.items():
        if sub_id == requested_id:
            continue
        if _view_dict(prior) != _view_dict(after[sub_id]):
            return PrepareMutationDecision(
                allowed=False,
                preflight_code=PREFLIGHT_SUBSET_UNSAFE,
                effects=(),
                eligibility_mutated=False,
            )
    prior_req = _view_dict(before[requested_id])
    after_req = _view_dict(after[requested_id])
    if prior_req.get("role") != after_req.get("role"):
        return PrepareMutationDecision(
            allowed=False,
            preflight_code=PREFLIGHT_ROLE_CHANGE,
            effects=(),
            eligibility_mutated=False,
        )
    if prior_req.get("is_enabled") != after_req.get("is_enabled"):
        return PrepareMutationDecision(
            allowed=False,
            preflight_code=PREFLIGHT_SUBSET_UNSAFE,
            effects=(),
            eligibility_mutated=False,
        )
    effects: tuple[str, ...] = ()
    if prior_req.get("external_calendar_id") != after_req.get("external_calendar_id"):
        effects = (EFFECT_CANONICALIZE_IDENTITY,)
    return PrepareMutationDecision(
        allowed=True,
        preflight_code=None,
        effects=effects,
        eligibility_mutated=prior_req != after_req,
    )


def _view_dict(view: Mapping[str, object]) -> dict[str, object]:
    return {field: view.get(field) for field in _GUARD_FIELDS}


def collect_suppressed_external_ids(
    db: Session,
    *,
    account: CalendarAccount,
) -> frozenset[str]:
    """Local pending-deletion external ids for this account. Does not delete.

    Same population legacy tombstone retry would suppress, without a provider
    delete and without removing the tombstone rows.
    """
    rows = (
        db.query(ExternalCalendarEvent.external_event_id)
        .filter(
            ExternalCalendarEvent.calendar_account_id == account.id,
            ExternalCalendarEvent.provider == account.provider,
            ExternalCalendarEvent.pending_deletion.is_(True),
        )
        .all()
    )
    return frozenset(row[0] for row in rows if row[0])


def _ensure_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _account_subscriptions(db: Session, account_id: UUID) -> list[CalendarSubscription]:
    return (
        db.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account_id)
        .all()
    )


def _prepare_preflight(
    *,
    code: str,
    effects: tuple[str, ...] = (),
    eligibility_mutated: bool = False,
    provider_identity_list_called: bool = False,
    scheduling_revision_bumped: bool = False,
    scheduling_revision: int | None = None,
) -> PrepareCoveringResult:
    return PrepareCoveringResult(
        outcome=OUTCOME_PREFLIGHT,
        preflight_code=code,
        preflight_effects=effects,
        eligibility_mutated=eligibility_mutated,
        provider_identity_list_called=provider_identity_list_called,
        scheduling_revision_bumped=scheduling_revision_bumped,
        scheduling_revision=scheduling_revision,
    )


def _bump_eligibility(
    db: Session,
    *,
    owner_id: UUID,
    now: datetime,
) -> tuple[bool, int]:
    from app.scheduler.horizon import compute_horizon

    settings = lock_owner_scheduling(db, owner_id)
    horizon_start, horizon_end = compute_horizon(settings, now)
    # Captured after the eligibility write. Signature compare sees no delta;
    # ``force`` still invalidates revision in this same transaction (§4.2).
    before_busy = immovable_busy_signature(db, owner_id)
    before_trust = trust_blocking_signature(
        db,
        owner_id,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )
    return commit_covering_revision_if_required(
        db,
        settings,
        owner_id,
        before_busy=before_busy,
        before_trust=before_trust,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        force=True,
    )


def prepare_requested_subscription_for_covering(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    settings: Settings,
    access_token: str,
    now: datetime,
    lock_receipt: CoveringUnitLockReceipt,
) -> PrepareCoveringResult:
    """Identity-prepare one requested subscription under caller-held §7 locks.

    Does not bootstrap a primary. Does not change who is enabled. If the
    account canonicalizer would mutate a non-requested row, or would change
    role or enablement on the requested row, the savepoint rolls back and
    this returns an explicit preflight code with no durable write.

    A requested-only pull-identity rewrite or identity-block mark is kept in
    the caller's transaction and bumps scheduling revision here.
    """
    require_covering_receipt(
        lock_receipt,
        owner_id=account.owner_id,
        account_id=account.id,
        subscription_id=subscription.id,
    )
    now_utc = _ensure_utc(now)
    if not bool(account.is_enabled):
        return _prepare_preflight(code=PREFLIGHT_ACCOUNT_DISABLED)
    if not bool(subscription.is_enabled):
        return _prepare_preflight(code=PREFLIGHT_SUBSCRIPTION_DISABLED)
    if subscription_blocked_for_identity(subscription):
        return _prepare_preflight(code=PREFLIGHT_IDENTITY_BLOCKED)

    all_subs = _account_subscriptions(db, account.id)
    enabled = [row for row in all_subs if row.is_enabled]
    needs_evidence = account_needs_live_identity_evidence(account, enabled)
    evidence = None
    list_called = False
    if needs_evidence:
        if not access_token:
            return _prepare_preflight(code=PREFLIGHT_ACCOUNT_DISCONNECTED)
        list_called = True
        try:
            evidence = fetch_account_identity_evidence(
                db,
                account,
                settings=settings,
                access_token=access_token,
            )
        except (httpx.TransportError, json.JSONDecodeError, OSError):
            logger.exception(
                "covering identity list failed account=%s subscription=%s",
                account.id,
                subscription.id,
            )
            return _prepare_preflight(
                code=PREFLIGHT_EVIDENCE_UNAVAILABLE,
                provider_identity_list_called=True,
            )

    before = {row.id: subscription_guard_view(row) for row in all_subs}
    savepoint = db.begin_nested()
    try:
        canonicalize_calendar_account(db, account, evidence=evidence, now=now_utc)
        db.flush()
        after_rows = _account_subscriptions(db, account.id)
        after = {row.id: subscription_guard_view(row) for row in after_rows}
        decision = classify_covering_prepare_mutation(
            requested_id=subscription.id,
            before=before,
            after=after,
        )
        if not decision.allowed:
            savepoint.rollback()
            db.expire_all()
            return _prepare_preflight(
                code=decision.preflight_code or PREFLIGHT_SUBSET_UNSAFE,
                provider_identity_list_called=list_called,
            )
        savepoint.commit()
    except Exception:
        if savepoint.is_active:
            savepoint.rollback()
        db.expire_all()
        raise

    db.refresh(subscription)
    blocked = subscription_blocked_for_identity(subscription)
    bumped = False
    revision: int | None = None
    if decision.eligibility_mutated or blocked:
        if decision.eligibility_mutated:
            bumped, revision = _bump_eligibility(db, owner_id=account.owner_id, now=now_utc)
        else:
            locked = lock_owner_scheduling(db, account.owner_id)
            revision = int(locked.scheduling_revision)
    if blocked:
        return PrepareCoveringResult(
            outcome=OUTCOME_PREFLIGHT,
            preflight_code=PREFLIGHT_IDENTITY_BLOCKED,
            preflight_effects=decision.effects,
            eligibility_mutated=decision.eligibility_mutated,
            provider_identity_list_called=list_called,
            scheduling_revision_bumped=bumped,
            scheduling_revision=revision,
        )
    return PrepareCoveringResult(
        outcome=OUTCOME_PROCEED,
        preflight_code=None,
        preflight_effects=decision.effects,
        eligibility_mutated=decision.eligibility_mutated,
        provider_identity_list_called=list_called,
        scheduling_revision_bumped=bumped,
        scheduling_revision=revision,
    )


def read_covering_access_token(
    *,
    settings: Settings,
    owner_id: UUID,
    account_id: UUID,
    subscription_id: UUID,
) -> CoveringAccessTokenResult:
    """Token durable unit. Own session. Lock order account → owner → sub.

    Commits only when access/refresh/expiry columns change. Does not bump
    scheduling revision (credential columns are not busy, trust, failure-state,
    or pull identity). Does not call calendar event endpoints.

    Finish this unit before the import transaction. OAuth errors from the
    provider token endpoint propagate (``ApiError``).
    """
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        with covering_unit_locks(
            db,
            owner_id=owner_id,
            account_id=account_id,
            subscription_id=subscription_id,
        ):
            account = (
                db.query(CalendarAccount)
                .filter(CalendarAccount.id == account_id)
                .populate_existing()
                .one()
            )
            subscription = (
                db.query(CalendarSubscription)
                .filter(CalendarSubscription.id == subscription_id)
                .one_or_none()
            )
            if subscription is None:
                raise CoveringLockOrderError("token unit subscription row is missing")
            if subscription.calendar_account_id != account.id:
                raise CoveringLockOrderError(
                    "token unit subscription does not belong to the account"
                )
            before_access = account.access_token_enc
            before_refresh = account.refresh_token_enc
            before_expires = account.token_expires_at
            access = _refresh_provider_access_token(db, settings=settings, account=account)
            changed = (
                account.access_token_enc != before_access
                or account.refresh_token_enc != before_refresh
                or account.token_expires_at != before_expires
            )
            if changed:
                db.commit()
            else:
                db.rollback()
            return CoveringAccessTokenResult(
                access_token=access,
                credentials_persisted=changed,
                account_id=account_id,
                subscription_id=subscription_id,
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _refresh_provider_access_token(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
) -> str:
    if account.provider == CalendarProvider.google:
        from app.services.google_calendar import get_valid_access_token as google_token

        return google_token(db, settings=settings, account=account)
    if account.provider == CalendarProvider.microsoft:
        from app.services.microsoft_calendar import get_valid_access_token as microsoft_token

        return microsoft_token(db, settings=settings, account=account)
    raise CoveringLockOrderError(f"unsupported calendar provider {account.provider!r}")


def _reload_pair(
    db: Session,
    *,
    account_id: UUID,
    subscription_id: UUID,
) -> tuple[CalendarAccount | None, CalendarSubscription | None]:
    account = (
        db.query(CalendarAccount)
        .filter(CalendarAccount.id == account_id)
        .populate_existing()
        .one_or_none()
    )
    subscription = (
        db.query(CalendarSubscription)
        .filter(CalendarSubscription.id == subscription_id)
        .populate_existing()
        .one_or_none()
    )
    return account, subscription


def _post_fetch_cause(
    account: CalendarAccount | None,
    subscription: CalendarSubscription | None,
    *,
    pull_generation: int,
    pull_fingerprint: str,
) -> str | None:
    if account is None or subscription is None:
        return CAUSE_POST_FETCH_DISCONNECTED
    if not bool(account.is_enabled) or not account.access_token_enc:
        return CAUSE_POST_FETCH_DISCONNECTED
    if not bool(subscription.is_enabled):
        return CAUSE_POST_FETCH_DISABLED
    if subscription_blocked_for_identity(subscription):
        return CAUSE_POST_FETCH_IDENTITY
    if int(subscription.coverage_active_generation or 0) != pull_generation:
        return CAUSE_POST_FETCH_GENERATION
    if covering_identity_fingerprint(subscription) != pull_fingerprint:
        return CAUSE_POST_FETCH_IDENTITY
    return None


def _cause_from_exception(exc: BaseException, *, default: str) -> str:
    from app.api.errors import ApiError

    if isinstance(exc, ApiError):
        code = exc.content.get("code")
        if isinstance(code, str) and code:
            return code[:128]
    return default[:128]


def _pull_provider(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    access_token: str,
    window: CoveringPullWindow,
) -> _ProviderPull:
    if account.provider == CalendarProvider.google:
        # Cursor clear is the forced full-window switch. Do this in the import
        # transaction so a rollback restores the previous cursor.
        subscription.sync_cursor = None
        db.flush()
        from app.services import google_calendar

        events, next_sync_token, is_full, page_count = google_calendar._pull_subscription_changes(
            db,
            access=access_token,
            subscription=subscription,
            time_min=window.effective_start,
            time_max=window.effective_end,
        )
        return _ProviderPull(
            events=list(events or []),
            next_sync_token=next_sync_token,
            page_count=int(page_count),
            pagination_complete=bool(google_calendar._pull_pagination_complete),
            is_full=bool(is_full),
            mode="full",
            event_fetch_context=None,
        )
    if account.provider == CalendarProvider.microsoft:
        from app.services.microsoft_calendar import _pull_subscription_changes as pull_ms

        view = pull_ms(
            db,
            access=access_token,
            subscription=subscription,
            time_min=window.effective_start,
            time_max=window.effective_end,
        )
        return _ProviderPull(
            events=list(view.events or []),
            next_sync_token=None,
            page_count=int(view.page_count),
            pagination_complete=bool(view.pagination_complete),
            is_full=True,
            mode=str(view.mode),
            event_fetch_context=view.event_fetch_context,
        )
    raise CoveringLockOrderError(f"unsupported calendar provider {account.provider!r}")


def _apply_provider(
    db: Session,
    *,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    pulled: _ProviderPull,
    window: CoveringPullWindow,
    now: datetime,
    generation: int,
    suppressed: set[str],
) -> int:
    if account.provider == CalendarProvider.google:
        from app.services.google_calendar import _apply_subscription_full

        return _apply_subscription_full(
            db,
            account=account,
            subscription=subscription,
            events=pulled.events,
            next_sync_token=pulled.next_sync_token,
            time_min=window.effective_start,
            time_max=window.effective_end,
            now=now,
            coverage_generation=generation,
            page_count=pulled.page_count,
            pagination_complete=True,
            suppressed_external_ids=suppressed,
        )
    from app.services.microsoft_calendar import _apply_subscription_ms_view

    return _apply_subscription_ms_view(
        db,
        account=account,
        subscription=subscription,
        events=pulled.events,
        time_min=window.effective_start,
        time_max=window.effective_end,
        now=now,
        mode=pulled.mode,
        coverage_generation=generation,
        page_count=pulled.page_count,
        pagination_complete=True,
        suppressed_external_ids=suppressed,
        event_fetch_context=pulled.event_fetch_context,
    )


def _import_result(
    *,
    subscription_id: UUID,
    outcome: str,
    window: CoveringPullWindow,
    attempt: CoveringAttemptSnapshot | None,
    preflight_code: str | None = None,
    preflight_effects: tuple[str, ...] = (),
    cause: str | None = None,
    upserted: int = 0,
    rollback_required: bool = False,
    commit_unit: bool = False,
    needs_failure_unit: bool = False,
    coverage_generation_minted: int | None = None,
    scheduling_revision_bumped: bool = False,
    scheduling_revision: int | None = None,
    provider_identity_list_called: bool = False,
    provider_event_read_attempted: bool = False,
) -> ImportCoveringCacheResult:
    return ImportCoveringCacheResult(
        subscription_id=subscription_id,
        outcome=outcome,
        preflight_code=preflight_code,
        preflight_effects=preflight_effects,
        cause=cause,
        upserted=upserted,
        rollback_required=rollback_required,
        commit_unit=commit_unit,
        needs_failure_unit=needs_failure_unit,
        attempt=attempt,
        window_effective_start=window.effective_start,
        window_effective_end=window.effective_end,
        window_widened=window.widened,
        window_widen_reason=window.reason,
        coverage_generation_minted=coverage_generation_minted,
        scheduling_revision_bumped=scheduling_revision_bumped,
        scheduling_revision=scheduling_revision,
        provider_identity_list_called=provider_identity_list_called,
        provider_event_read_attempted=provider_event_read_attempted,
    )


def _from_prepare_preflight(
    *,
    subscription_id: UUID,
    window: CoveringPullWindow,
    attempt: CoveringAttemptSnapshot | None,
    prepared: PrepareCoveringResult,
) -> ImportCoveringCacheResult:
    # Identity-block marks stay in this transaction and must commit.
    # Subset-unsafe / already-blocked / disabled leaves nothing new to commit.
    commit_unit = prepared.outcome == OUTCOME_PREFLIGHT and prepared.eligibility_mutated
    return _import_result(
        subscription_id=subscription_id,
        outcome=OUTCOME_PREFLIGHT,
        window=window,
        attempt=attempt,
        preflight_code=prepared.preflight_code,
        preflight_effects=prepared.preflight_effects,
        rollback_required=False,
        commit_unit=commit_unit,
        needs_failure_unit=False,
        scheduling_revision_bumped=prepared.scheduling_revision_bumped,
        scheduling_revision=prepared.scheduling_revision,
        provider_identity_list_called=prepared.provider_identity_list_called,
    )


def import_covering_subscription_cache(
    db: Session,
    *,
    settings: Settings,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    access_token: str,
    window_start: datetime,
    window_end: datetime,
    lock_receipt: CoveringUnitLockReceipt,
    now: datetime | None = None,
) -> ImportCoveringCacheResult:
    """Read one subscription's provider window into the local cache.

    Requires ``lock_receipt`` from ``covering_unit_locks`` on ``db``. Does not
    commit or roll back ``db``. On ``rollback_required``, the caller rolls back
    the whole unit (prepare rewrite, cursor clear, and any generation bump).

    Provider work is list/calendarView read plus, when identity evidence is
    required, calendar-list read. No event create/update/delete HTTP.
    """
    window = effective_covering_pull_window(window_start, window_end)
    require_covering_receipt(
        lock_receipt,
        owner_id=account.owner_id,
        account_id=account.id,
        subscription_id=subscription.id,
    )
    now_utc = _ensure_utc(now or datetime.now(timezone.utc))
    account_row, sub_row = _reload_pair(
        db,
        account_id=account.id,
        subscription_id=subscription.id,
    )
    if account_row is None or sub_row is None:
        missing = PREFLIGHT_SUBSCRIPTION_NOT_FOUND if sub_row is None else PREFLIGHT_ACCOUNT_DISCONNECTED
        return _import_result(
            subscription_id=subscription.id,
            outcome=OUTCOME_PREFLIGHT,
            window=window,
            attempt=None,
            preflight_code=missing,
        )
    if sub_row.owner_id != account_row.owner_id or sub_row.calendar_account_id != account_row.id:
        raise CoveringLockOrderError("reloaded subscription does not match the locked account")

    # Before prepare and before the generation bump. This is the token
    # the failure unit compares after rollback.
    attempt = snapshot_covering_attempt(account=account_row, subscription=sub_row)

    if not access_token or not account_row.access_token_enc:
        return _import_result(
            subscription_id=sub_row.id,
            outcome=OUTCOME_PREFLIGHT,
            window=window,
            attempt=attempt,
            preflight_code=PREFLIGHT_ACCOUNT_DISCONNECTED,
        )
    if not bool(account_row.is_enabled):
        return _import_result(
            subscription_id=sub_row.id,
            outcome=OUTCOME_PREFLIGHT,
            window=window,
            attempt=attempt,
            preflight_code=PREFLIGHT_ACCOUNT_DISABLED,
        )
    if not bool(sub_row.is_enabled):
        return _import_result(
            subscription_id=sub_row.id,
            outcome=OUTCOME_PREFLIGHT,
            window=window,
            attempt=attempt,
            preflight_code=PREFLIGHT_SUBSCRIPTION_DISABLED,
        )
    if subscription_blocked_for_identity(sub_row):
        return _import_result(
            subscription_id=sub_row.id,
            outcome=OUTCOME_PREFLIGHT,
            window=window,
            attempt=attempt,
            preflight_code=PREFLIGHT_IDENTITY_BLOCKED,
        )

    prepared = prepare_requested_subscription_for_covering(
        db,
        account=account_row,
        subscription=sub_row,
        settings=settings,
        access_token=access_token,
        now=now_utc,
        lock_receipt=lock_receipt,
    )
    if prepared.outcome != OUTCOME_PROCEED:
        return _from_prepare_preflight(
            subscription_id=sub_row.id,
            window=window,
            attempt=attempt,
            prepared=prepared,
        )

    db.refresh(sub_row)
    db.refresh(account_row)
    if (
        not bool(sub_row.is_enabled)
        or not bool(account_row.is_enabled)
        or subscription_blocked_for_identity(sub_row)
    ):
        code = PREFLIGHT_IDENTITY_BLOCKED
        if not bool(account_row.is_enabled):
            code = PREFLIGHT_ACCOUNT_DISABLED
        elif not bool(sub_row.is_enabled):
            code = PREFLIGHT_SUBSCRIPTION_DISABLED
        return _import_result(
            subscription_id=sub_row.id,
            outcome=OUTCOME_PREFLIGHT,
            window=window,
            attempt=attempt,
            preflight_code=code,
            preflight_effects=prepared.preflight_effects,
            rollback_required=prepared.eligibility_mutated,
            commit_unit=False,
            scheduling_revision_bumped=prepared.scheduling_revision_bumped,
            scheduling_revision=prepared.scheduling_revision,
            provider_identity_list_called=prepared.provider_identity_list_called,
        )

    pull_generation = int(sub_row.coverage_active_generation or 0)
    pull_fingerprint = covering_identity_fingerprint(sub_row)
    settings_row = lock_owner_scheduling(db, account_row.owner_id)
    from app.scheduler.horizon import compute_horizon

    horizon_start, horizon_end = compute_horizon(settings_row, now_utc)
    before_busy = immovable_busy_signature(db, account_row.owner_id)
    before_trust = trust_blocking_signature(
        db,
        account_row.owner_id,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )

    try:
        pulled = _pull_provider(
            db,
            account=account_row,
            subscription=sub_row,
            access_token=access_token,
            window=window,
        )
    except Exception as exc:
        logger.exception(
            "covering provider read failed subscription=%s",
            sub_row.id,
        )
        return _import_result(
            subscription_id=sub_row.id,
            outcome=OUTCOME_FAILED,
            window=window,
            attempt=attempt,
            preflight_effects=prepared.preflight_effects,
            cause=_cause_from_exception(exc, default=CAUSE_PROVIDER_READ_FAILED),
            rollback_required=True,
            needs_failure_unit=True,
            scheduling_revision_bumped=prepared.scheduling_revision_bumped,
            scheduling_revision=prepared.scheduling_revision,
            provider_identity_list_called=prepared.provider_identity_list_called,
            provider_event_read_attempted=True,
        )

    db.flush()
    re_account, re_sub = _reload_pair(
        db,
        account_id=account_row.id,
        subscription_id=sub_row.id,
    )
    post_cause = _post_fetch_cause(
        re_account,
        re_sub,
        pull_generation=pull_generation,
        pull_fingerprint=pull_fingerprint,
    )
    if post_cause is not None or re_account is None or re_sub is None:
        return _import_result(
            subscription_id=sub_row.id,
            outcome=OUTCOME_FAILED,
            window=window,
            attempt=attempt,
            preflight_effects=prepared.preflight_effects,
            cause=post_cause or CAUSE_POST_FETCH_DISCONNECTED,
            rollback_required=True,
            needs_failure_unit=True,
            scheduling_revision_bumped=prepared.scheduling_revision_bumped,
            scheduling_revision=prepared.scheduling_revision,
            provider_identity_list_called=prepared.provider_identity_list_called,
            provider_event_read_attempted=True,
        )

    if account_row.provider == CalendarProvider.google and not pulled.is_full:
        return _import_result(
            subscription_id=re_sub.id,
            outcome=OUTCOME_FAILED,
            window=window,
            attempt=attempt,
            preflight_effects=prepared.preflight_effects,
            cause=CAUSE_GOOGLE_FULL_REQUIRED,
            rollback_required=True,
            needs_failure_unit=True,
            scheduling_revision_bumped=prepared.scheduling_revision_bumped,
            scheduling_revision=prepared.scheduling_revision,
            provider_identity_list_called=prepared.provider_identity_list_called,
            provider_event_read_attempted=True,
        )
    if not pulled.pagination_complete:
        return _import_result(
            subscription_id=re_sub.id,
            outcome=OUTCOME_FAILED,
            window=window,
            attempt=attempt,
            preflight_effects=prepared.preflight_effects,
            cause=CAUSE_PAGINATION_INCOMPLETE,
            rollback_required=True,
            needs_failure_unit=True,
            scheduling_revision_bumped=prepared.scheduling_revision_bumped,
            scheduling_revision=prepared.scheduling_revision,
            provider_identity_list_called=prepared.provider_identity_list_called,
            provider_event_read_attempted=True,
        )

    suppressed = set(
        collect_suppressed_external_ids(db, account=re_account)
    )
    # In-transaction generation only. Caller rollback drops it; the failure
    # unit must keep using ``attempt``, not this value.
    generation = begin_subscription_refresh(re_sub, now=now_utc)
    db.flush()
    apply_cause = (
        CAUSE_GOOGLE_APPLY_FAILED
        if re_account.provider == CalendarProvider.google
        else CAUSE_MS_APPLY_FAILED
    )
    try:
        upserted = _apply_provider(
            db,
            account=re_account,
            subscription=re_sub,
            pulled=pulled,
            window=window,
            now=now_utc,
            generation=generation,
            suppressed=suppressed,
        )
    except Exception as exc:
        logger.exception(
            "covering apply failed subscription=%s",
            re_sub.id,
        )
        return _import_result(
            subscription_id=re_sub.id,
            outcome=OUTCOME_FAILED,
            window=window,
            attempt=attempt,
            preflight_effects=prepared.preflight_effects,
            cause=_cause_from_exception(exc, default=apply_cause),
            rollback_required=True,
            needs_failure_unit=True,
            scheduling_revision_bumped=prepared.scheduling_revision_bumped,
            scheduling_revision=prepared.scheduling_revision,
            provider_identity_list_called=prepared.provider_identity_list_called,
            provider_event_read_attempted=True,
        )

    bumped, revision = commit_covering_revision_if_required(
        db,
        settings_row,
        re_account.owner_id,
        before_busy=before_busy,
        before_trust=before_trust,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        force=False,
    )
    if prepared.scheduling_revision_bumped:
        bumped = True
        revision = int(settings_row.scheduling_revision)
    db.flush()
    return _import_result(
        subscription_id=re_sub.id,
        outcome=OUTCOME_OK,
        window=window,
        attempt=attempt,
        preflight_effects=prepared.preflight_effects,
        upserted=int(upserted),
        rollback_required=False,
        commit_unit=True,
        needs_failure_unit=False,
        coverage_generation_minted=generation,
        scheduling_revision_bumped=bumped,
        scheduling_revision=revision,
        provider_identity_list_called=prepared.provider_identity_list_called,
        provider_event_read_attempted=True,
    )
