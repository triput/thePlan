"""Covering-refresh HTTP orchestration (Decision 2 §2, §4.2, §5, §7)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CalendarAccount, CalendarSubscription, ExternalCalendarEvent
from app.scheduler.calendar_freshness import (
    CalendarFreshnessTrust,
    _evaluate_one_subscription,
    _load_sidecar_failures,
    evaluate_calendar_freshness,
    required_coverage_window,
)
from app.scheduler.free_busy import evaluate_busy_input_trust
from app.schemas.calendar import (
    CoveringActionOut,
    CoveringActionSummaryOut,
    CoveringRefreshRequest,
    CoveringRefreshResponse,
    CoveringRefreshResultRow,
    CoveringWindowOut,
    SchedulingReadinessOut,
)
from app.services.covering_refresh_failure import persist_covering_refresh_failure
from app.services.covering_refresh_import import (
    OUTCOME_FAILED,
    OUTCOME_OK,
    OUTCOME_PREFLIGHT,
    ImportCoveringCacheResult,
    import_covering_subscription_cache,
    read_covering_access_token,
)
from app.services.covering_refresh_locks import covering_unit_locks
from app.services.covering_refresh_window import (
    COVERING_WINDOW_WIDEN_REASON,
    COVERING_WINDOW_WIDENED,
    CoveringPullWindow,
    CoveringWindowError,
    effective_covering_pull_window,
)
from app.services.free_busy_series_policy import (
    load_series_policies_for_owner,
    policy_diagnostic_enrichment,
)
from app.services.scheduling_revision import lock_owner_scheduling

logger = logging.getLogger(__name__)

ELIGIBILITY_CODE = "CALENDAR_SUBSCRIPTION_NOT_ELIGIBLE"


class CoveringSubscriptionNotEligible(Exception):
    """Whole-request abort before any provider calendar HTTP (§2.1)."""

    def __init__(self, detail: str = "One or more calendar subscriptions are not eligible") -> None:
        self.code = ELIGIBILITY_CODE
        self.detail = detail
        super().__init__(detail)


def _ensure_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _preflight_load_targets(
    db: Session,
    *,
    owner_id: UUID,
    subscription_ids: list[UUID],
) -> list[tuple[CalendarAccount, CalendarSubscription]]:
    sorted_ids = sorted(subscription_ids, key=lambda value: str(value))
    if not sorted_ids:
        raise CoveringSubscriptionNotEligible("subscription_ids must be non-empty")
    rows = (
        db.query(CalendarSubscription, CalendarAccount)
        .join(CalendarAccount, CalendarSubscription.calendar_account_id == CalendarAccount.id)
        .filter(CalendarSubscription.id.in_(sorted_ids))
        .all()
    )
    by_id: dict[UUID, tuple[CalendarAccount, CalendarSubscription]] = {
        subscription.id: (account, subscription) for subscription, account in rows
    }
    if len(by_id) != len(sorted_ids):
        raise CoveringSubscriptionNotEligible()
    owner_ids = {subscription.owner_id for _account, subscription in by_id.values()}
    if len(owner_ids) != 1 or owner_id not in owner_ids:
        raise CoveringSubscriptionNotEligible()
    ordered: list[tuple[CalendarAccount, CalendarSubscription]] = []
    for sub_id in sorted_ids:
        account, subscription = by_id[sub_id]
        if subscription.owner_id != owner_id or account.owner_id != owner_id:
            raise CoveringSubscriptionNotEligible()
        ordered.append((account, subscription))
    return ordered


def _window_out(start: datetime, end: datetime) -> CoveringWindowOut:
    return CoveringWindowOut(start=start, end=end)


def _result_row(result: ImportCoveringCacheResult) -> CoveringRefreshResultRow:
    if result.outcome == OUTCOME_PREFLIGHT:
        phase: str = "preflight"
        status: str = "preflight_rejected"
    else:
        phase = "import"
        status = result.outcome
    return CoveringRefreshResultRow(
        subscription_id=result.subscription_id,
        phase=phase,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        preflight_code=result.preflight_code,
        preflight_effects=list(result.preflight_effects),
        cause=result.cause,
        upserted=int(result.upserted),
    )


def _derive_overall_outcome(
    rows: list[CoveringRefreshResultRow],
    *,
    import_attempted: int,
    import_ok: int,
) -> str:
    _ = rows
    if import_attempted == 0:
        return "no_op"
    if import_ok == 0:
        return "failed"
    if import_ok == len(rows):
        return "success"
    return "partial"


def _evaluate_requested_freshness(
    db: Session,
    *,
    owner_id: UUID,
    subscription_ids: list[UUID],
    now_utc: datetime,
    required_start: datetime,
    required_end: datetime,
) -> CalendarFreshnessTrust:
    rows = (
        db.query(CalendarSubscription, CalendarAccount)
        .join(CalendarAccount, CalendarSubscription.calendar_account_id == CalendarAccount.id)
        .filter(
            CalendarSubscription.owner_id == owner_id,
            CalendarSubscription.id.in_(subscription_ids),
        )
        .all()
    )
    sidecar_by_sub = _load_sidecar_failures(db, [subscription.id for subscription, _ in rows])
    blocking = []
    for subscription, account in rows:
        diag = _evaluate_one_subscription(
            subscription,
            account,
            now_utc=now_utc,
            required_start=required_start,
            required_end=required_end,
            sidecar=sidecar_by_sub.get(subscription.id),
        )
        if diag is not None:
            blocking.append(diag)
    affected = {
        "start": required_start.isoformat(),
        "end": required_end.isoformat(),
    }
    return CalendarFreshnessTrust(
        ok=len(blocking) == 0,
        blocking_diagnostics=blocking,
        affected_horizon=affected if blocking else None,
        required_window_start=required_start,
        required_window_end=required_end,
    )


def _blocking_summary(
    *,
    freshness: CalendarFreshnessTrust,
    busy_trust_ok: bool,
    busy_trust: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    for diag in freshness.blocking_diagnostics:
        label = diag.calendar_name or "(calendar)"
        lines.append(f"{label}: {diag.cause}")
    if not busy_trust_ok:
        for row in busy_trust.get("blocking_diagnostics") or []:
            if isinstance(row, dict):
                name = row.get("calendar_name") or "(calendar)"
                cause = row.get("cause") or "busy_input_untrusted"
                lines.append(f"{name}: {cause}")
    return lines


def _assemble_scheduling_readiness(
    db: Session,
    *,
    owner_id: UUID,
    now_utc: datetime,
    horizon_label: str | None,
) -> SchedulingReadinessOut:
    settings = lock_owner_scheduling(db, owner_id)
    revision = int(settings.scheduling_revision)
    horizon_start, horizon_end = required_coverage_window(settings, now_utc)
    freshness = evaluate_calendar_freshness(
        db,
        owner_id,
        settings,
        now_utc,
        required_start=horizon_start,
        required_end=horizon_end,
    )
    events = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner_id,
            *ExternalCalendarEvent.immovable_busy_clause(),
        )
        .all()
    )
    names = {
        s.external_calendar_id: (s.summary or s.external_calendar_id)
        for s in db.query(CalendarSubscription)
        .filter(CalendarSubscription.owner_id == owner_id)
        .all()
    }
    policy_map = load_series_policies_for_owner(db, owner_id)
    enrichments = {
        e.external_event_id: policy_diagnostic_enrichment(db, e, policy_map=policy_map)
        for e in events
        if e.free_busy_pending_exception
    }
    enrichments = {k: v for k, v in enrichments.items() if v}
    busy_trust = evaluate_busy_input_trust(
        events,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        calendar_name_by_id=names,
        policy_map=policy_map,
        policy_enrichment_by_event_id=enrichments,
    )
    busy_dict = busy_trust.to_dict()
    scheduling_ready = bool(freshness.ok and busy_trust.ok)
    blocking = _blocking_summary(
        freshness=freshness,
        busy_trust_ok=busy_trust.ok,
        busy_trust=busy_dict,
    )
    if not scheduling_ready and not blocking:
        blocking = ["scheduling_not_ready"]
    return SchedulingReadinessOut(
        evaluated_at=now_utc,
        scheduling_revision=revision,
        horizon=_window_out(horizon_start, horizon_end),
        horizon_label=horizon_label,
        freshness_all_enabled=freshness.to_dict(),
        busy_input_trust=busy_dict,
        scheduling_ready=scheduling_ready,
        blocking_summary=blocking,
    )


def _process_one_target(
    db: Session,
    *,
    settings: Settings,
    owner_id: UUID,
    account: CalendarAccount,
    subscription: CalendarSubscription,
    window: CoveringPullWindow,
    now_utc: datetime,
) -> ImportCoveringCacheResult:
    token = read_covering_access_token(
        settings=settings,
        owner_id=owner_id,
        account_id=account.id,
        subscription_id=subscription.id,
    )
    with covering_unit_locks(
        db,
        owner_id=owner_id,
        account_id=account.id,
        subscription_id=subscription.id,
    ) as receipt:
        result = import_covering_subscription_cache(
            db,
            settings=settings,
            account=account,
            subscription=subscription,
            access_token=token.access_token,
            window_start=window.effective_start,
            window_end=window.effective_end,
            lock_receipt=receipt,
            now=now_utc,
        )
        if result.commit_unit and not result.rollback_required:
            db.commit()
        else:
            db.rollback()
    if result.needs_failure_unit and result.attempt is not None and result.cause:
        persist_covering_refresh_failure(
            attempt=result.attempt,
            now=now_utc,
            cause=result.cause,
        )
    return result


def run_covering_refresh(
    db: Session,
    *,
    settings: Settings,
    owner_id: UUID,
    body: CoveringRefreshRequest,
    now: datetime | None = None,
) -> CoveringRefreshResponse:
    """Orchestrate POST covering-refresh. Caller owns session lifecycle after return."""
    now_utc = _ensure_utc(now or datetime.now(timezone.utc))
    window = effective_covering_pull_window(body.window_start, body.window_end)
    targets = _preflight_load_targets(db, owner_id=owner_id, subscription_ids=body.subscription_ids)

    settings_row = lock_owner_scheduling(db, owner_id)
    scheduling_revision_at_start = int(settings_row.scheduling_revision)
    db.rollback()

    import_results: list[ImportCoveringCacheResult] = []
    for account, subscription in targets:
        import_results.append(
            _process_one_target(
                db,
                settings=settings,
                owner_id=owner_id,
                account=account,
                subscription=subscription,
                window=window,
                now_utc=now_utc,
            )
        )

    result_rows = [_result_row(item) for item in import_results]
    preflight_rejected = sum(1 for row in result_rows if row.phase == "preflight")
    import_attempted = sum(
        1 for item in import_results if item.provider_event_read_attempted
    )
    import_ok = sum(1 for row in result_rows if row.status == OUTCOME_OK)
    import_failed = sum(1 for row in result_rows if row.status == OUTCOME_FAILED)
    overall = _derive_overall_outcome(
        result_rows,
        import_attempted=import_attempted,
        import_ok=import_ok,
    )
    action_summary = CoveringActionSummaryOut(
        requested=len(body.subscription_ids),
        preflight_rejected=preflight_rejected,
        import_attempted=import_attempted,
        import_ok=import_ok,
        import_failed=import_failed,
    )

    requested_freshness = _evaluate_requested_freshness(
        db,
        owner_id=owner_id,
        subscription_ids=body.subscription_ids,
        now_utc=now_utc,
        required_start=window.effective_start,
        required_end=window.effective_end,
    )
    coverage_action = CoveringActionOut(
        window=_window_out(window.effective_start, window.effective_end),
        all_requested_covering_ok=requested_freshness.ok,
        freshness_requested=requested_freshness.to_dict(),
    )

    scheduling_readiness: SchedulingReadinessOut | None = None
    scheduling_revision_at_end: int | None = None
    try:
        scheduling_readiness = _assemble_scheduling_readiness(
            db,
            owner_id=owner_id,
            now_utc=now_utc,
            horizon_label=body.scheduling_horizon_label,
        )
        scheduling_revision_at_end = scheduling_readiness.scheduling_revision
        db.rollback()
    except Exception as exc:
        logger.exception("covering refresh readiness assessment failed owner=%s", owner_id)
        db.rollback()
        scheduling_readiness = SchedulingReadinessOut(
            assessment_error=str(exc)[:512],
        )

    bumped = (
        scheduling_revision_at_end is not None
        and scheduling_revision_at_end > scheduling_revision_at_start
    )

    window_requested = _window_out(window.effective_start, window.effective_end)
    return CoveringRefreshResponse(
        window_requested=window_requested,
        window_effective=window_requested,
        window_widened=COVERING_WINDOW_WIDENED,
        window_widen_reason=COVERING_WINDOW_WIDEN_REASON,
        overall_outcome=overall,  # type: ignore[arg-type]
        action_summary=action_summary,
        results=result_rows,
        coverage_action=coverage_action,
        scheduling_readiness=scheduling_readiness,
        scheduling_revision_at_start=scheduling_revision_at_start,
        scheduling_revision_at_end=scheduling_revision_at_end,
        scheduling_revision_bumped=bumped,
    )


__all__ = [
    "CoveringSubscriptionNotEligible",
    "run_covering_refresh",
]
