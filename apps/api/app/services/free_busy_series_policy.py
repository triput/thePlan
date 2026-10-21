# ==============================================================================
#  File: apps/api/app/services/free_busy_series_policy.py
#  Description: T1-4a persisted series policy, resolve POST, ingest compare/latch.
# ==============================================================================

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import ExternalCalendarEvent, User
from app.models.enums import CalendarProvider
from app.models.free_busy_policy import (
    FreeBusyOccurrenceBaseline,
    FreeBusySeriesPolicy,
    FreeBusySeriesPolicyDecision,
)
from app.scheduler.free_busy import (
    ExceptionIdentity,
    FreeBusyKind,
    _event_identity,
    effective_free_busy_kind,
    source_zone_untrusted,
)
from app.services.free_busy_resolver_allowlist import user_may_resolve

_logger = logging.getLogger(__name__)

_FREE_BUSY_IDENTITY_NAMESPACE = 1_886_415_953
_AUTOMATIC_BASELINE_SOURCE = "automatic_first_trustworthy_observation"


class GoogleUpsertPostLockIdentityDriftError(Exception):
    """Post-lock identity drift during Google ingest; rollback and retry in a new transaction."""
_CONFLICT_REVISION_SECRET = b"theplan-t1-4a-conflict-revision-v1"

IdentityKey = tuple[str, str, str, str]


@dataclass(frozen=True)
class ConflictAcknowledgment:
    external_event_id: str
    conflict_revision: str


@dataclass(frozen=True)
class ResolveSeriesPolicyRequest:
    external_event_id: str
    conflict_acknowledgments: tuple[ConflictAcknowledgment, ...]
    reason: str


def identity_key_from_row(row: ExternalCalendarEvent) -> IdentityKey | None:
    ident = _event_identity(row)
    if ident is None:
        return None
    return ident.key()


def sort_identity_keys(keys: Iterable[IdentityKey]) -> list[IdentityKey]:
    return sorted(set(keys), key=lambda k: (k[0], k[1], k[2], k[3]))


def free_busy_identity_lock_key(
    owner_id: str, provider: str, calendar_id: str, series_id: str
) -> int:
    raw = f"{owner_id}:{provider}:{calendar_id}:{series_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF or 1


def acquire_identity_advisory_locks(db: Session, keys: Sequence[IdentityKey]) -> None:
    for owner_id, provider, calendar_id, series_id in sort_identity_keys(keys):
        db.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
            {
                "namespace": _FREE_BUSY_IDENTITY_NAMESPACE,
                "key": free_busy_identity_lock_key(
                    owner_id, provider, calendar_id, series_id
                ),
            },
        )


def load_series_policies_for_owner(
    db: Session, owner_id: UUID
) -> dict[IdentityKey, FreeBusyKind]:
    rows = (
        db.query(FreeBusySeriesPolicy)
        .filter(FreeBusySeriesPolicy.owner_id == owner_id)
        .all()
    )
    out: dict[IdentityKey, FreeBusyKind] = {}
    for row in rows:
        provider_s = getattr(row.provider, "value", None) or str(row.provider)
        key: IdentityKey = (
            str(row.owner_id),
            str(provider_s),
            str(row.calendar_id),
            str(row.provider_series_id),
        )
        if row.mapping == "free":
            out[key] = "free"
    return out


def provider_trust_blocker(
    *,
    transparency: str | None,
    provenance: str | None,
    row: ExternalCalendarEvent,
) -> bool:
    if source_zone_untrusted(row):
        return True
    kind = effective_free_busy_kind(
        transparency=transparency,
        provenance=provenance,
        identity=None,
        pending_exception=False,
    )
    return kind == "unknown"


def occupancy_kind_from_stored(
    transparency: str | None, provenance: str | None
) -> FreeBusyKind:
    return effective_free_busy_kind(
        transparency=transparency,
        provenance=provenance,
        identity=None,
        pending_exception=False,
    )


def _provider_evidence_dict(row: ExternalCalendarEvent) -> dict[str, str | bool | None]:
    return {
        "transparency": row.transparency,
        "provenance": row.free_busy_provenance,
        "occupancy_kind": occupancy_kind_from_stored(
            row.transparency, row.free_busy_provenance
        ),
        "source_zone_untrusted": source_zone_untrusted(row),
    }


def get_occurrence_baseline(
    db: Session, row: ExternalCalendarEvent
) -> FreeBusyOccurrenceBaseline | None:
    return (
        db.query(FreeBusyOccurrenceBaseline)
        .filter(
            FreeBusyOccurrenceBaseline.owner_id == row.owner_id,
            FreeBusyOccurrenceBaseline.provider == row.provider,
            FreeBusyOccurrenceBaseline.external_event_id == row.external_event_id,
        )
        .one_or_none()
    )


def get_decision_baseline_for_event(
    db: Session, policy_id: UUID, external_event_id: str
) -> dict[str, Any] | None:
    """Latest manual-resolve snapshot for an occurrence from decision history."""
    decisions = (
        db.query(FreeBusySeriesPolicyDecision)
        .filter(FreeBusySeriesPolicyDecision.policy_id == policy_id)
        .order_by(FreeBusySeriesPolicyDecision.decided_at.desc())
        .all()
    )
    for decision in decisions:
        acks = decision.snapshot.get("conflict_acknowledgments") or []
        for item in acks:
            if str(item.get("external_event_id")) == external_event_id:
                return item.get("provider_evidence")
    return None


def comparison_baseline_for_row(
    db: Session,
    row: ExternalCalendarEvent,
    policy: FreeBusySeriesPolicy | None,
) -> dict[str, Any] | None:
    baseline_row = get_occurrence_baseline(db, row)
    if baseline_row is not None:
        return {
            "transparency": baseline_row.transparency,
            "provenance": baseline_row.free_busy_provenance,
            "occupancy_kind": baseline_row.occupancy_kind,
            "source": baseline_row.source,
        }
    if policy is not None:
        manual = get_decision_baseline_for_event(db, policy.id, row.external_event_id)
        if manual is not None:
            return manual
    return None


def compute_conflict_revision(
    *,
    identity: IdentityKey,
    external_event_id: str,
    transparency: str | None,
    provenance: str | None,
    pending: bool,
    latch_generation: int,
    source_zone_untrusted: bool,
) -> str:
    payload = "|".join(
        [
            identity[0],
            identity[1],
            identity[2],
            identity[3],
            external_event_id,
            str(transparency),
            str(provenance),
            "1" if source_zone_untrusted else "0",
            "1" if pending else "0",
            str(latch_generation),
        ]
    )
    digest = hmac.new(
        _CONFLICT_REVISION_SECRET,
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def authoritative_pending_events(
    db: Session,
    *,
    owner_id: UUID,
    provider: CalendarProvider,
    calendar_id: str,
    provider_series_id: str,
) -> list[ExternalCalendarEvent]:
    return (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner_id,
            ExternalCalendarEvent.provider == provider,
            ExternalCalendarEvent.calendar_id == calendar_id,
            ExternalCalendarEvent.provider_series_id == provider_series_id,
            ExternalCalendarEvent.free_busy_pending_exception.is_(True),
        )
        .order_by(ExternalCalendarEvent.external_event_id.asc())
        .all()
    )


def lock_events_for_update(
    db: Session, events: Sequence[ExternalCalendarEvent]
) -> list[ExternalCalendarEvent]:
    ids = sorted({str(e.id) for e in events})
    if not ids:
        return []
    uuid_ids = [UUID(i) for i in ids]
    return (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.id.in_(uuid_ids))
        .order_by(ExternalCalendarEvent.external_event_id.asc())
        .with_for_update()
        .populate_existing()
        .all()
    )


def get_or_create_policy_for_identity(
    db: Session,
    *,
    owner_id: UUID,
    provider: CalendarProvider,
    calendar_id: str,
    provider_series_id: str,
) -> FreeBusySeriesPolicy:
    existing = (
        db.query(FreeBusySeriesPolicy)
        .filter(
            FreeBusySeriesPolicy.owner_id == owner_id,
            FreeBusySeriesPolicy.provider == provider,
            FreeBusySeriesPolicy.calendar_id == calendar_id,
            FreeBusySeriesPolicy.provider_series_id == provider_series_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if existing is not None:
        return existing
    row = FreeBusySeriesPolicy(
        owner_id=owner_id,
        provider=provider,
        calendar_id=calendar_id,
        provider_series_id=provider_series_id,
        mapping="free",
    )
    db.add(row)
    db.flush()
    return row


def upsert_manual_baseline(
    db: Session,
    row: ExternalCalendarEvent,
    *,
    transparency: str | None,
    provenance: str | None,
    occupancy_kind: str,
) -> None:
    existing = get_occurrence_baseline(db, row)
    if existing is not None:
        existing.transparency = transparency
        existing.free_busy_provenance = provenance
        existing.occupancy_kind = occupancy_kind
        existing.source = "manual_resolve"
        return
    db.add(
        FreeBusyOccurrenceBaseline(
            owner_id=row.owner_id,
            provider=row.provider,
            external_event_id=row.external_event_id,
            transparency=transparency,
            free_busy_provenance=provenance,
            occupancy_kind=occupancy_kind,
            source="manual_resolve",
        )
    )


def seed_automatic_baseline_if_needed(
    db: Session,
    row: ExternalCalendarEvent,
    policy: FreeBusySeriesPolicy,
) -> bool:
    """First trustworthy observation seeds baseline; returns True if seeded."""
    if get_occurrence_baseline(db, row) is not None:
        return False
    if provider_trust_blocker(
        transparency=row.transparency,
        provenance=row.free_busy_provenance,
        row=row,
    ):
        return False
    occ = occupancy_kind_from_stored(row.transparency, row.free_busy_provenance)
    db.add(
        FreeBusyOccurrenceBaseline(
            owner_id=row.owner_id,
            provider=row.provider,
            external_event_id=row.external_event_id,
            transparency=row.transparency,
            free_busy_provenance=row.free_busy_provenance,
            occupancy_kind=occ,
            source=_AUTOMATIC_BASELINE_SOURCE,
        )
    )
    db.flush()
    return True


def occupancy_disagreement(
    baseline: dict[str, Any] | None,
    *,
    transparency: str | None,
    provenance: str | None,
    series_mapping: str | None = None,
) -> bool:
    if baseline is None:
        return False
    base_t = baseline.get("transparency")
    base_p = baseline.get("provenance")
    if transparency == base_t and provenance == base_p:
        return False
    base_kind = baseline.get("occupancy_kind") or occupancy_kind_from_stored(
        base_t, base_p
    )
    current_kind = occupancy_kind_from_stored(transparency, provenance)
    # Transparency flip before raw kind mismatch (T3/T4 / Q1 free alignment).
    if (base_t or "") != (transparency or ""):
        if base_t == "transparent" and transparency != "transparent":
            return True  # T3 transparent → opaque
        if base_t != "transparent" and transparency == "transparent":
            if current_kind == "free" and (
                series_mapping == "free" or base_kind != "free"
            ):
                return False
            return base_kind != "free" and current_kind == "free"
    if base_kind != current_kind:
        return True
    return False


def is_identity_drift(policy: FreeBusySeriesPolicy, row: ExternalCalendarEvent) -> bool:
    if policy.acknowledged_calendar_id is None and policy.acknowledged_series_id is None:
        return False
    return (
        policy.acknowledged_calendar_id != row.calendar_id
        or policy.acknowledged_series_id != row.provider_series_id
    )


def apply_post_transparency_policy_effects(
    db: Session,
    row: ExternalCalendarEvent,
    *,
    identity_keys: Sequence[IdentityKey],
    old_calendar_id: str | None,
    old_series_id: str | None,
) -> None:
    """Google ingest path after transparency persisted (under identity locks)."""
    key = identity_key_from_row(row)
    if key is None:
        return
    policy = (
        db.query(FreeBusySeriesPolicy)
        .filter(
            FreeBusySeriesPolicy.owner_id == row.owner_id,
            FreeBusySeriesPolicy.provider == row.provider,
            FreeBusySeriesPolicy.calendar_id == key[2],
            FreeBusySeriesPolicy.provider_series_id == key[3],
        )
        .with_for_update()
        .one_or_none()
    )

    # Identity drift from calendar/series change (§3.4) — retain explicit pending on row.
    if old_series_id and (
        old_series_id != row.provider_series_id
        or (old_calendar_id and old_calendar_id != row.calendar_id)
    ):
        row.free_busy_pending_exception = True
        if policy is not None and is_identity_drift(policy, row):
            row.free_busy_pending_exception = True
        return

    if policy is None:
        return

    if is_identity_drift(policy, row):
        row.free_busy_pending_exception = True
        return

    if provider_trust_blocker(
        transparency=row.transparency,
        provenance=row.free_busy_provenance,
        row=row,
    ):
        # T0b — loss of trust reopens dispute until explicit resolve.
        row.free_busy_pending_exception = True
        policy.conflict_pending_latched = True
        policy.latch_generation = int(policy.latch_generation) + 1
        return

    baseline = comparison_baseline_for_row(db, row, policy)
    if baseline is None:
        seed_automatic_baseline_if_needed(db, row, policy)
        return

    if row.free_busy_pending_exception and policy.conflict_pending_latched:
        # T8 — latched; ingest must not clear on matching refresh.
        return

    if occupancy_disagreement(
        baseline,
        transparency=row.transparency,
        provenance=row.free_busy_provenance,
        series_mapping=policy.mapping if policy is not None else None,
    ):
        row.free_busy_pending_exception = True
        policy.conflict_pending_latched = True
        policy.latch_generation = int(policy.latch_generation) + 1


def resolve_series_policy(
    db: Session,
    *,
    user: User,
    body: ResolveSeriesPolicyRequest,
    allowlist_path: str | None,
) -> dict[str, Any]:
    if not user_may_resolve(user.id, allowlist_path):
        raise ApiError(
            403,
            "Not authorized to resolve free/busy series policy",
            "FREE_BUSY_RESOLVE_FORBIDDEN",
        )
    if not body.reason or not str(body.reason).strip():
        raise ApiError(422, "reason is required", "FREE_BUSY_RESOLVE_INVALID")
    if not body.conflict_acknowledgments:
        raise ApiError(
            422,
            "conflict_acknowledgments required",
            "FREE_BUSY_RESOLVE_INVALID",
        )

    trigger = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.external_event_id == body.external_event_id,
            ExternalCalendarEvent.owner_id == user.id,
        )
        .one_or_none()
    )
    if trigger is None:
        raise ApiError(404, "Event not found", "FREE_BUSY_EVENT_NOT_FOUND")
    if trigger.owner_id != user.id:
        raise ApiError(
            403,
            "Not authorized to resolve free/busy series policy",
            "FREE_BUSY_RESOLVE_FORBIDDEN",
        )
    if not trigger.provider_series_id:
        raise ApiError(
            422,
            "Event has no verified series identity",
            "FREE_BUSY_RESOLVE_INVALID",
        )

    key = identity_key_from_row(trigger)
    if key is None:
        raise ApiError(422, "Invalid series identity", "FREE_BUSY_RESOLVE_INVALID")

    trigger_id = trigger.id
    acquire_identity_advisory_locks(db, [key])

    trigger_refreshed = (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.id == trigger_id)
        .populate_existing()
        .one()
    )
    key_locked = identity_key_from_row(trigger_refreshed)
    if key_locked is None:
        raise ApiError(422, "Invalid series identity", "FREE_BUSY_RESOLVE_INVALID")
    if key_locked != key:
        raise ApiError(
            409,
            "Series identity changed; retry resolve",
            "FREE_BUSY_IDENTITY_DRIFT",
        )

    pending_all = authoritative_pending_events(
        db,
        owner_id=user.id,
        provider=trigger_refreshed.provider,
        calendar_id=key_locked[2],
        provider_series_id=key_locked[3],
    )
    events_to_lock: list[ExternalCalendarEvent] = list(pending_all)
    if trigger_id not in {e.id for e in events_to_lock}:
        events_to_lock.append(trigger_refreshed)
    locked_events = lock_events_for_update(db, events_to_lock)
    locked_by_id = {e.id: e for e in locked_events}
    trigger = locked_by_id[trigger_id]
    key_after_row_lock = identity_key_from_row(trigger)
    if key_after_row_lock is None:
        raise ApiError(422, "Invalid series identity", "FREE_BUSY_RESOLVE_INVALID")
    if key_after_row_lock != key_locked:
        raise ApiError(
            409,
            "Series identity changed; retry resolve",
            "FREE_BUSY_IDENTITY_DRIFT",
        )
    key = key_locked
    locked_pending = [e for e in locked_events if e.free_busy_pending_exception]
    pending_by_ext = {e.external_event_id: e for e in locked_pending}

    policy = get_or_create_policy_for_identity(
        db,
        owner_id=user.id,
        provider=trigger.provider,
        calendar_id=key[2],
        provider_series_id=key[3],
    )

    ack_payload: list[dict[str, Any]] = []
    ack_ids = {a.external_event_id for a in body.conflict_acknowledgments}
    for ack in body.conflict_acknowledgments:
        row = pending_by_ext.get(ack.external_event_id)
        if row is None:
            raise ApiError(
                422,
                f"Unknown or non-pending conflict: {ack.external_event_id}",
                "FREE_BUSY_RESOLVE_INVALID",
            )
        expected = compute_conflict_revision(
            identity=key,
            external_event_id=row.external_event_id,
            transparency=row.transparency,
            provenance=row.free_busy_provenance,
            pending=True,
            latch_generation=int(policy.latch_generation),
            source_zone_untrusted=source_zone_untrusted(row),
        )
        if not hmac.compare_digest(expected, ack.conflict_revision):
            raise ApiError(
                409,
                "Conflict revision stale; refresh diagnostics and retry",
                "FREE_BUSY_CONFLICT_STALE",
            )
        evidence = _provider_evidence_dict(row)
        ack_payload.append(
            {
                "external_event_id": row.external_event_id,
                "conflict_revision": ack.conflict_revision,
                "provider_evidence": evidence,
            }
        )
        upsert_manual_baseline(
            db,
            row,
            transparency=row.transparency,
            provenance=row.free_busy_provenance,
            occupancy_kind=str(evidence["occupancy_kind"]),
        )

    now = datetime.now(timezone.utc)
    decision = FreeBusySeriesPolicyDecision(
        policy_id=policy.id,
        decided_at=now,
        decided_by_user_id=user.id,
        reason=body.reason.strip(),
        mapping="free",
        decision_source="manual_resolve",
        snapshot={
            "trigger_external_event_id": trigger.external_event_id,
            "conflict_acknowledgments": ack_payload,
        },
    )
    db.add(decision)
    db.flush()

    policy.mapping = "free"
    policy.resolved_by_user_id = user.id
    policy.resolved_at = now
    policy.reason = body.reason.strip()
    policy.decision_source = "manual_resolve"
    policy.acknowledged_calendar_id = key[2]
    policy.acknowledged_series_id = key[3]
    policy.acknowledged_provider_transparency = trigger.transparency
    policy.acknowledged_provider_provenance = trigger.free_busy_provenance

    for row in locked_pending:
        if row.external_event_id in ack_ids:
            row.free_busy_pending_exception = False

    if set(ack_ids) >= {e.external_event_id for e in pending_all}:
        policy.conflict_pending_latched = False
    else:
        policy.conflict_pending_latched = True

    db.flush()
    return {
        "policy_id": str(policy.id),
        "decision_id": str(decision.id),
        "mapping": policy.mapping,
        "conflict_pending_latched": policy.conflict_pending_latched,
    }


def policy_diagnostic_enrichment(
    db: Session,
    event: ExternalCalendarEvent,
    *,
    policy_map: Mapping[IdentityKey, FreeBusyKind] | None = None,
) -> dict[str, Any] | None:
    key = identity_key_from_row(event)
    if key is None or not event.free_busy_pending_exception:
        return None
    policy = (
        db.query(FreeBusySeriesPolicy)
        .filter(
            FreeBusySeriesPolicy.owner_id == event.owner_id,
            FreeBusySeriesPolicy.provider == event.provider,
            FreeBusySeriesPolicy.calendar_id == key[2],
            FreeBusySeriesPolicy.provider_series_id == key[3],
        )
        .one_or_none()
    )
    latch_gen = int(policy.latch_generation) if policy else 0
    revision = compute_conflict_revision(
        identity=key,
        external_event_id=event.external_event_id,
        transparency=event.transparency,
        provenance=event.free_busy_provenance,
        pending=True,
        latch_generation=latch_gen,
        source_zone_untrusted=source_zone_untrusted(event),
    )
    if policy is None:
        retained = "no manual series policy decision yet"
    elif policy.resolved_at:
        retained = (
            f"free — last resolve {policy.resolved_at.isoformat()} "
            f"by {policy.resolved_by_user_id}"
        )
    else:
        retained = "free (series policy)"
    cause = "policy_occupancy_disagreement"
    if policy and policy.conflict_pending_latched:
        cause = "policy_conflict_latched"
    return {
        "external_event_id": event.external_event_id,
        "cause": cause,
        "retained_manual_choice": retained,
        "current_provider_evidence": _provider_evidence_dict(event),
        "conflict_revision": revision,
        "recovery": "POST /api/v1/calendar/resolve-series-policy with conflict_acknowledgments",
    }


def google_upsert_identity_keys_for_lock(
    *,
    row: ExternalCalendarEvent | None,
    new_calendar_id: str,
    new_series_id: str | None,
    old_calendar_id: str | None,
    old_series_id: str | None,
    owner_id: UUID,
) -> list[IdentityKey]:
    keys: list[IdentityKey] = []
    provider = CalendarProvider.google.value

    def _add(cal: str, series: str | None) -> None:
        if series:
            keys.append((str(owner_id), provider, cal, series))

    if row is not None and row.provider_series_id:
        _add(row.calendar_id, row.provider_series_id)
    if old_series_id and (old_series_id != new_series_id or old_calendar_id != new_calendar_id):
        if old_calendar_id and old_series_id:
            _add(old_calendar_id, old_series_id)
    if new_series_id:
        _add(new_calendar_id, new_series_id)
    return sort_identity_keys(keys)
