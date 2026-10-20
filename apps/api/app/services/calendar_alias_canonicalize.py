# ==============================================================================
#  File: apps/api/app/services/calendar_alias_canonicalize.py
#  Description: T1-F calendar subscription identity / alias canonicalization.
#  Component: Scheduler / calendar ingest
#  Version: 1.0
#  Created: 2026-10-20
#  Last Update: 2026-10-20
# ==============================================================================
"""Canonical calendar identity per account (T1-10 / T1-F).

Serialization: ``pg_advisory_xact_lock`` on a calendar-account namespace plus
``SELECT … FOR UPDATE`` on ``calendar_accounts`` (same pattern as
``lock_owner_scheduling``). Callers must run canonicalization inside an open
transaction before PUT commit or the pre-sync subscription loop.

Cache-only collect/Apply must not call identity fetch helpers here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    ExternalCalendarEvent,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.services.calendar_coverage import invalidate_subscription_coverage

_ACCOUNT_LOCK_NAMESPACE = 1_886_415_952

T1F_BASELINE_SHA = "7992650577f78ca528892498421ac4539276e0a5"

IDENTITY_UNRESOLVED_CAUSE = "calendar_identity_unresolved"
IDENTITY_AMBIGUOUS_CAUSE = "calendar_identity_ambiguous"
IDENTITY_MERGE_CAUSE = "calendar_identity_merged"
IDENTITY_KEY_REWRITE_CAUSE = "calendar_identity_key_rewritten"

GOOGLE_PRIMARY_ALIAS = "primary"
MS_LEGACY_PRIMARY_ALIAS = "primary"


class IdentityOutcome(str, Enum):
    resolved = "resolved"
    unresolved = "unresolved"
    ambiguous = "ambiguous"


@dataclass(frozen=True)
class CanonicalIdentityResult:
    outcome: IdentityOutcome
    canonical_id: str | None = None


@dataclass
class AccountIdentityEvidence:
    provider: CalendarProvider
    fetch_succeeded: bool
    google_primary_id: str | None = None
    google_ambiguous: bool = False
    microsoft_default_id: str | None = None
    microsoft_ambiguous: bool = False
    microsoft_list_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CanonicalizeOutcome:
    merged: bool
    identity_blocked: frozenset[UUID]


def _account_lock_key(account_id: UUID) -> int:
    folded = (account_id.int ^ (account_id.int >> 64)) & 0x7FFFFFFF
    return folded or 1


def lock_calendar_account_for_identity(db: Session, account_id: UUID) -> CalendarAccount:
    db.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
        {"namespace": _ACCOUNT_LOCK_NAMESPACE, "key": _account_lock_key(account_id)},
    )
    return (
        db.query(CalendarAccount)
        .filter(CalendarAccount.id == account_id)
        .with_for_update()
        .populate_existing()
        .one()
    )


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _google_primary_entries(items: Sequence[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for entry in items:
        if entry.get("primary") or entry.get("isDefaultCalendar"):
            cid = entry.get("id")
            if cid:
                ids.append(str(cid))
    return ids


def _microsoft_default_entries(items: Sequence[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for entry in items:
        if entry.get("primary") or entry.get("isDefaultCalendar"):
            cid = entry.get("id")
            if cid:
                ids.append(str(cid))
    return ids


def fetch_account_identity_evidence(
    db: Session,
    account: CalendarAccount,
    *,
    settings: Settings,
    access_token: str,
) -> AccountIdentityEvidence:
    """Authoritative provider list/default fetch for this account only."""
    _ = db
    if account.provider == CalendarProvider.google:
        from app.services.google_calendar import list_google_calendars

        try:
            raw = list_google_calendars(access_token)
        except ApiError:
            return AccountIdentityEvidence(
                provider=account.provider,
                fetch_succeeded=False,
            )
        primaries = _google_primary_entries(raw)
        if len(primaries) > 1:
            return AccountIdentityEvidence(
                provider=account.provider,
                fetch_succeeded=True,
                google_ambiguous=True,
            )
        primary_id = primaries[0] if primaries else None
        return AccountIdentityEvidence(
            provider=account.provider,
            fetch_succeeded=True,
            google_primary_id=primary_id,
        )

    from app.services.microsoft_calendar import (
        _fetch_default_calendar,
        list_microsoft_calendars,
    )

    try:
        default_id, _summary = _fetch_default_calendar(access_token)
        listed = list_microsoft_calendars(access_token)
    except ApiError:
        return AccountIdentityEvidence(
            provider=account.provider,
            fetch_succeeded=False,
        )
    defaults = _microsoft_default_entries(listed)
    ambiguous = len(defaults) > 1
    list_ids = frozenset(str(entry.get("id")) for entry in listed if entry.get("id"))
    return AccountIdentityEvidence(
        provider=account.provider,
        fetch_succeeded=True,
        microsoft_default_id=str(default_id),
        microsoft_ambiguous=ambiguous,
        microsoft_list_ids=list_ids,
    )


def resolve_canonical_id(
    *,
    provider: CalendarProvider,
    external_calendar_id: str,
    evidence: AccountIdentityEvidence | None,
) -> CanonicalIdentityResult:
    if provider == CalendarProvider.google:
        if external_calendar_id == GOOGLE_PRIMARY_ALIAS:
            if evidence is None or not evidence.fetch_succeeded:
                return CanonicalIdentityResult(IdentityOutcome.unresolved)
            if evidence.google_ambiguous:
                return CanonicalIdentityResult(IdentityOutcome.ambiguous)
            if not evidence.google_primary_id:
                return CanonicalIdentityResult(IdentityOutcome.unresolved)
            return CanonicalIdentityResult(
                IdentityOutcome.resolved,
                canonical_id=evidence.google_primary_id,
            )
        if evidence and evidence.fetch_succeeded and not evidence.google_ambiguous:
            if evidence.google_primary_id and external_calendar_id == evidence.google_primary_id:
                return CanonicalIdentityResult(
                    IdentityOutcome.resolved,
                    canonical_id=evidence.google_primary_id,
                )
        return CanonicalIdentityResult(
            IdentityOutcome.resolved,
            canonical_id=external_calendar_id,
        )

    # Microsoft
    if external_calendar_id == MS_LEGACY_PRIMARY_ALIAS:
        if evidence is None or not evidence.fetch_succeeded:
            return CanonicalIdentityResult(IdentityOutcome.unresolved)
        if evidence.microsoft_ambiguous:
            return CanonicalIdentityResult(IdentityOutcome.ambiguous)
        if not evidence.microsoft_default_id:
            return CanonicalIdentityResult(IdentityOutcome.unresolved)
        return CanonicalIdentityResult(
            IdentityOutcome.resolved,
            canonical_id=evidence.microsoft_default_id,
        )
    return CanonicalIdentityResult(
        IdentityOutcome.resolved,
        canonical_id=external_calendar_id,
    )


def _is_stable_external_id(provider: CalendarProvider, external_calendar_id: str) -> bool:
    if provider == CalendarProvider.google:
        return external_calendar_id != GOOGLE_PRIMARY_ALIAS
    return external_calendar_id != MS_LEGACY_PRIMARY_ALIAS


def _survivor_rank(
    sub: CalendarSubscription,
    *,
    provider: CalendarProvider,
) -> tuple[int, int, datetime, UUID]:
    stable = 0 if _is_stable_external_id(provider, sub.external_calendar_id) else 1
    primary_role = 0 if sub.role == CalendarSubscriptionRole.primary else 1
    created = sub.created_at or datetime.min.replace(tzinfo=timezone.utc)
    return (stable, primary_role, created, sub.id)


def _pick_survivor(
    group: list[CalendarSubscription],
    *,
    provider: CalendarProvider,
) -> CalendarSubscription:
    return min(group, key=lambda sub: _survivor_rank(sub, provider=provider))


def _sidecar_for(
    db: Session, subscription_id: UUID
) -> CalendarSubscriptionRefreshFailure | None:
    return (
        db.query(CalendarSubscriptionRefreshFailure)
        .filter(CalendarSubscriptionRefreshFailure.subscription_id == subscription_id)
        .one_or_none()
    )


def _failure_sort_key(
    subscription_id: UUID,
    *,
    failure_at: datetime | None,
    cause: str | None,
) -> tuple[int, datetime, int, str, UUID]:
    if failure_at is None:
        return (0, datetime.min.replace(tzinfo=timezone.utc), 0, "", subscription_id)
    cause_key = 1 if (cause or "").strip() else 0
    return (1, _ensure_utc(failure_at), cause_key, cause or "", -subscription_id.int)


def _failure_snapshots(
    db: Session, subscriptions: Sequence[CalendarSubscription]
) -> list[tuple[UUID, datetime | None, str | None]]:
    snaps: list[tuple[UUID, datetime | None, str | None]] = []
    for sub in subscriptions:
        sidecar = _sidecar_for(db, sub.id)
        snaps.append(
            (
                sub.id,
                sidecar.failure_at if sidecar else sub.coverage_last_failure_at,
                sidecar.cause if sidecar else sub.coverage_last_failure_cause,
            )
        )
    return snaps


def _apply_latest_blocking_failure_to_survivor(
    db: Session,
    *,
    survivor: CalendarSubscription,
    snapshots: Sequence[tuple[UUID, datetime | None, str | None]],
    now: datetime,
) -> None:
    winner_id, winner_at, winner_cause = max(
        snapshots,
        key=lambda row: _failure_sort_key(
            row[0],
            failure_at=row[1],
            cause=row[2],
        ),
    )
    if winner_at is None or not winner_cause:
        return
    cause = winner_cause[:128]
    failure_at = _ensure_utc(winner_at)
    existing = _sidecar_for(db, survivor.id)
    if existing is None:
        db.add(
            CalendarSubscriptionRefreshFailure(
                subscription_id=survivor.id,
                failure_at=failure_at,
                cause=cause,
            )
        )
    else:
        if _failure_sort_key(survivor.id, failure_at=failure_at, cause=cause) >= _failure_sort_key(
            survivor.id,
            failure_at=existing.failure_at,
            cause=existing.cause,
        ):
            existing.failure_at = failure_at
            existing.cause = cause
    from app.services.calendar_coverage import record_subscription_refresh_failure

    record_subscription_refresh_failure(survivor, now=now, cause=cause)
    _ = winner_id


def rewrite_account_calendar_id_references(
    db: Session,
    *,
    calendar_account_id: UUID,
    old_calendar_id: str,
    new_calendar_id: str,
) -> None:
    if old_calendar_id == new_calendar_id:
        return
    (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.calendar_account_id == calendar_account_id,
            ExternalCalendarEvent.calendar_id == old_calendar_id,
        )
        .update({"calendar_id": new_calendar_id}, synchronize_session=False)
    )


def _rewrite_subscription_key(
    db: Session,
    subscription: CalendarSubscription,
    *,
    new_external_id: str,
    now: datetime,
    invalidate_cause: str,
) -> None:
    old_id = subscription.external_calendar_id
    if old_id == new_external_id:
        return
    rewrite_account_calendar_id_references(
        db,
        calendar_account_id=subscription.calendar_account_id,
        old_calendar_id=old_id,
        new_calendar_id=new_external_id,
    )
    subscription.external_calendar_id = new_external_id
    subscription.sync_cursor = None
    invalidate_subscription_coverage(
        subscription,
        now=now,
        cause=invalidate_cause,
        clear_sync_cursor=True,
    )


def _merge_alias_into_survivor(
    db: Session,
    *,
    survivor: CalendarSubscription,
    alias: CalendarSubscription,
    provider: CalendarProvider,
    canonical_id: str,
    now: datetime,
) -> None:
    if alias.provider_timezone and not survivor.provider_timezone:
        survivor.provider_timezone = alias.provider_timezone
    if alias.summary and not survivor.summary:
        survivor.summary = alias.summary

    failure_snaps = _failure_snapshots(db, [survivor, alias])

    target_id = canonical_id if _is_stable_external_id(provider, canonical_id) else survivor.external_calendar_id
    if provider == CalendarProvider.google and target_id != GOOGLE_PRIMARY_ALIAS:
        if survivor.external_calendar_id != target_id:
            _rewrite_subscription_key(
                db,
                survivor,
                new_external_id=target_id,
                now=now,
                invalidate_cause=IDENTITY_MERGE_CAUSE,
            )
        elif alias.external_calendar_id != target_id:
            rewrite_account_calendar_id_references(
                db,
                calendar_account_id=survivor.calendar_account_id,
                old_calendar_id=alias.external_calendar_id,
                new_calendar_id=target_id,
            )
            invalidate_subscription_coverage(
                survivor,
                now=now,
                cause=IDENTITY_MERGE_CAUSE,
                clear_sync_cursor=True,
            )
    else:
        if survivor.external_calendar_id != alias.external_calendar_id:
            rewrite_account_calendar_id_references(
                db,
                calendar_account_id=survivor.calendar_account_id,
                old_calendar_id=alias.external_calendar_id,
                new_calendar_id=survivor.external_calendar_id,
            )
        invalidate_subscription_coverage(
            survivor,
            now=now,
            cause=IDENTITY_MERGE_CAUSE,
            clear_sync_cursor=True,
        )

    alias.is_enabled = False
    _apply_latest_blocking_failure_to_survivor(
        db, survivor=survivor, snapshots=failure_snaps, now=now
    )


def _mark_identity_failure(
    subscription: CalendarSubscription,
    *,
    now: datetime,
    cause: str,
) -> None:
    from app.services.calendar_coverage import record_subscription_refresh_failure

    record_subscription_refresh_failure(subscription, now=now, cause=cause)


def _clear_identity_unresolved_markers(subscriptions: Iterable[CalendarSubscription]) -> None:
    for sub in subscriptions:
        if sub.coverage_last_failure_cause in {
            IDENTITY_UNRESOLVED_CAUSE,
            IDENTITY_AMBIGUOUS_CAUSE,
        }:
            sub.coverage_last_failure_cause = None
            sub.coverage_last_failure_at = None


def _enabled_subscriptions(db: Session, account_id: UUID) -> list[CalendarSubscription]:
    return (
        db.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account_id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .order_by(CalendarSubscription.created_at)
        .all()
    )


def _group_by_canonical(
    subscriptions: Sequence[CalendarSubscription],
    *,
    provider: CalendarProvider,
    evidence: AccountIdentityEvidence | None,
) -> tuple[dict[str, list[CalendarSubscription]], list[CalendarSubscription]]:
    by_canonical: dict[str, list[CalendarSubscription]] = {}
    blocked: list[CalendarSubscription] = []
    for sub in subscriptions:
        resolved = resolve_canonical_id(
            provider=provider,
            external_calendar_id=sub.external_calendar_id,
            evidence=evidence,
        )
        if resolved.outcome == IdentityOutcome.ambiguous:
            blocked.append(sub)
            continue
        if resolved.outcome == IdentityOutcome.unresolved:
            blocked.append(sub)
            continue
        assert resolved.canonical_id is not None
        by_canonical.setdefault(resolved.canonical_id, []).append(sub)
    return by_canonical, blocked


def _google_unresolved_pair_candidates(enabled: Sequence[CalendarSubscription]) -> bool:
    has_primary = any(sub.external_calendar_id == GOOGLE_PRIMARY_ALIAS for sub in enabled)
    if not has_primary:
        return False
    return len(enabled) > 1


def _microsoft_unresolved_pair_candidates(enabled: Sequence[CalendarSubscription]) -> bool:
    has_legacy = any(sub.external_calendar_id == MS_LEGACY_PRIMARY_ALIAS for sub in enabled)
    if not has_legacy:
        return False
    return len(enabled) > 1


def _proposed_enabled_put_items(
    items: Sequence[Any],
    existing: Sequence[CalendarSubscription],
) -> list[Any]:
    enabled: list[Any] = []
    for item in items:
        if item.is_enabled:
            enabled.append(item)
    return enabled


def validate_put_subscription_items(
    *,
    account: CalendarAccount,
    items: Sequence[Any],
    existing: Sequence[CalendarSubscription],
    evidence: AccountIdentityEvidence | None,
) -> None:
    """Reject entire PUT when enabled items collide on canonical identity."""
    enabled_items = _proposed_enabled_put_items(items, existing)
    canonical_map: dict[str, list[Any]] = {}
    for item in enabled_items:
        resolved = resolve_canonical_id(
            provider=account.provider,
            external_calendar_id=item.external_calendar_id,
            evidence=evidence,
        )
        if resolved.outcome == IdentityOutcome.ambiguous:
            raise ApiError(
                422,
                "Calendar identity evidence is ambiguous; subscription update rejected",
                "CALENDAR_IDENTITY_AMBIGUOUS",
            )
        if resolved.outcome == IdentityOutcome.unresolved:
            if account.provider == CalendarProvider.google and item.external_calendar_id != GOOGLE_PRIMARY_ALIAS:
                if evidence is None or not evidence.fetch_succeeded:
                    raise ApiError(
                        422,
                        "Cannot enable calendar without verified identity evidence",
                        "CALENDAR_IDENTITY_EVIDENCE_REQUIRED",
                    )
            if (
                account.provider == CalendarProvider.microsoft
                and item.external_calendar_id == MS_LEGACY_PRIMARY_ALIAS
                and (evidence is None or not evidence.fetch_succeeded)
            ):
                raise ApiError(
                    422,
                    "Cannot enable legacy primary alias without verified identity evidence",
                    "CALENDAR_IDENTITY_EVIDENCE_REQUIRED",
                )
            canonical_key = f"unresolved:{item.external_calendar_id}"
        else:
            canonical_key = resolved.canonical_id or item.external_calendar_id
        canonical_map.setdefault(canonical_key, []).append(item)

    for _canonical, group in canonical_map.items():
        if len(group) < 2:
            continue
        roles = {item.role for item in group}
        if len(roles) > 1:
            raise ApiError(
                422,
                "Conflicting roles for the same calendar identity",
                "CALENDAR_SUBSCRIPTION_ALIAS_CONFLICT",
            )
        ext_ids = {item.external_calendar_id for item in group}
        if len(ext_ids) > 1:
            raise ApiError(
                422,
                "Multiple enabled aliases for the same calendar identity",
                "CALENDAR_SUBSCRIPTION_ALIAS_CONFLICT",
            )


def canonicalize_calendar_account(
    db: Session,
    account: CalendarAccount,
    *,
    evidence: AccountIdentityEvidence | None,
    now: datetime,
) -> CanonicalizeOutcome:
    """Merge duplicate enabled aliases; rewrite keys; mark unresolved pairs blocked."""
    now = _ensure_utc(now)
    enabled = _enabled_subscriptions(db, account.id)
    if not enabled:
        return CanonicalizeOutcome(merged=False, identity_blocked=frozenset())

    if evidence and evidence.fetch_succeeded and not evidence.google_ambiguous and not evidence.microsoft_ambiguous:
        all_on_account = (
            db.query(CalendarSubscription)
            .filter(CalendarSubscription.calendar_account_id == account.id)
            .all()
        )
        _clear_identity_unresolved_markers(all_on_account)

    if evidence and evidence.fetch_succeeded:
        if account.provider == CalendarProvider.google and evidence.google_ambiguous:
            for sub in enabled:
                _mark_identity_failure(sub, now=now, cause=IDENTITY_AMBIGUOUS_CAUSE)
            return CanonicalizeOutcome(
                merged=False,
                identity_blocked=frozenset(sub.id for sub in enabled),
            )
        if account.provider == CalendarProvider.microsoft and evidence.microsoft_ambiguous:
            for sub in enabled:
                _mark_identity_failure(sub, now=now, cause=IDENTITY_AMBIGUOUS_CAUSE)
            return CanonicalizeOutcome(
                merged=False,
                identity_blocked=frozenset(sub.id for sub in enabled),
            )

    merged_any = False
    identity_blocked: set[UUID] = set()

    if evidence is None or not evidence.fetch_succeeded:
        pair = False
        if account.provider == CalendarProvider.google:
            pair = _google_unresolved_pair_candidates(enabled)
        elif account.provider == CalendarProvider.microsoft:
            pair = _microsoft_unresolved_pair_candidates(enabled)
        if pair:
            for sub in enabled:
                _mark_identity_failure(sub, now=now, cause=IDENTITY_UNRESOLVED_CAUSE)
                identity_blocked.add(sub.id)
            return CanonicalizeOutcome(merged=False, identity_blocked=frozenset(identity_blocked))

    by_canonical, unresolved_blocked = _group_by_canonical(
        enabled,
        provider=account.provider,
        evidence=evidence,
    )
    for sub in unresolved_blocked:
        _mark_identity_failure(sub, now=now, cause=IDENTITY_AMBIGUOUS_CAUSE)
        identity_blocked.add(sub.id)

    for canonical_id, group in by_canonical.items():
        if len(group) == 1:
            sub = group[0]
            if (
                account.provider == CalendarProvider.google
                and sub.external_calendar_id == GOOGLE_PRIMARY_ALIAS
                and evidence
                and evidence.fetch_succeeded
                and evidence.google_primary_id
            ):
                _rewrite_subscription_key(
                    db,
                    sub,
                    new_external_id=evidence.google_primary_id,
                    now=now,
                    invalidate_cause=IDENTITY_KEY_REWRITE_CAUSE,
                )
                merged_any = True
            continue

        survivor = _pick_survivor(group, provider=account.provider)
        aliases = [sub for sub in group if sub.id != survivor.id]
        for alias in aliases:
            _merge_alias_into_survivor(
                db,
                survivor=survivor,
                alias=alias,
                provider=account.provider,
                canonical_id=canonical_id,
                now=now,
            )
            merged_any = True

    if merged_any and not identity_blocked:
        _clear_identity_unresolved_markers(
            _enabled_subscriptions(db, account.id)
            + db.query(CalendarSubscription)
            .filter(
                CalendarSubscription.calendar_account_id == account.id,
                CalendarSubscription.is_enabled.is_(False),
            )
            .all()
        )

    return CanonicalizeOutcome(
        merged=merged_any,
        identity_blocked=frozenset(identity_blocked),
    )


def account_needs_live_identity_evidence(
    account: CalendarAccount, enabled: Sequence[CalendarSubscription]
) -> bool:
    """True when provider list/default fetch is required before sync or merge."""
    if len(enabled) <= 1:
        return False
    if account.provider == CalendarProvider.google:
        return any(sub.external_calendar_id == GOOGLE_PRIMARY_ALIAS for sub in enabled)
    if account.provider == CalendarProvider.microsoft:
        return any(sub.external_calendar_id == MS_LEGACY_PRIMARY_ALIAS for sub in enabled)
    return False


def subscription_blocked_for_identity(subscription: CalendarSubscription) -> bool:
    return subscription.coverage_last_failure_cause in {
        IDENTITY_UNRESOLVED_CAUSE,
        IDENTITY_AMBIGUOUS_CAUSE,
    }


def prepare_subscriptions_for_sync(
    db: Session,
    account: CalendarAccount,
    *,
    settings: Settings,
    access_token: str,
    now: datetime,
) -> list[CalendarSubscription]:
    """Lock, fetch evidence, canonicalize, return enabled subs eligible to pull."""
    lock_calendar_account_for_identity(db, account.id)
    enabled_before = _enabled_subscriptions(db, account.id)
    evidence: AccountIdentityEvidence | None = None
    if account_needs_live_identity_evidence(account, enabled_before):
        evidence = fetch_account_identity_evidence(
            db, account, settings=settings, access_token=access_token
        )
    canonicalize_calendar_account(db, account, evidence=evidence, now=now)
    db.flush()
    enabled = _enabled_subscriptions(db, account.id)
    return [sub for sub in enabled if not subscription_blocked_for_identity(sub)]


def prepare_put_calendar_subscriptions(
    db: Session,
    account: CalendarAccount,
    *,
    settings: Settings,
    items: Sequence[Any],
    now: datetime,
) -> AccountIdentityEvidence | None:
    """Lock account and validate PUT payload against identity evidence."""
    lock_calendar_account_for_identity(db, account.id)
    existing = (
        db.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .all()
    )
    proposed_enabled = _proposed_enabled_put_items(items, existing)
    evidence: AccountIdentityEvidence | None = None
    needs_evidence = len(proposed_enabled) > 1 or any(
        account.provider == CalendarProvider.google
        and item.external_calendar_id == GOOGLE_PRIMARY_ALIAS
        for item in proposed_enabled
    )
    if needs_evidence:
        from app.services.google_calendar import get_valid_access_token as google_token
        from app.services.microsoft_calendar import get_valid_access_token as ms_token

        try:
            if account.provider == CalendarProvider.google:
                token = google_token(db, settings=settings, account=account)
            else:
                token = ms_token(db, settings=settings, account=account)
            evidence = fetch_account_identity_evidence(
                db, account, settings=settings, access_token=token
            )
        except ApiError:
            evidence = AccountIdentityEvidence(
                provider=account.provider,
                fetch_succeeded=False,
            )
    if evidence and evidence.fetch_succeeded:
        if evidence.google_ambiguous or evidence.microsoft_ambiguous:
            raise ApiError(
                422,
                "Calendar identity evidence is ambiguous; subscription update rejected",
                "CALENDAR_IDENTITY_AMBIGUOUS",
            )
    validate_put_subscription_items(
        account=account,
        items=items,
        existing=existing,
        evidence=evidence,
    )
    if evidence and not evidence.fetch_succeeded:
        if account.provider == CalendarProvider.google and len(proposed_enabled) > 1:
            raise ApiError(
                422,
                "Cannot update subscriptions without verified calendar identity evidence",
                "CALENDAR_IDENTITY_EVIDENCE_REQUIRED",
            )
        if account.provider == CalendarProvider.microsoft and any(
            item.external_calendar_id == MS_LEGACY_PRIMARY_ALIAS for item in proposed_enabled
        ):
            raise ApiError(
                422,
                "Cannot update subscriptions without verified calendar identity evidence",
                "CALENDAR_IDENTITY_EVIDENCE_REQUIRED",
            )
    return evidence
