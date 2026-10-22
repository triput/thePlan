"""T1-C: calendar complete-window freshness gate (collect + Apply).

Gate-only: never initiates provider sync. ok=True is this check only — not overall readiness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    UserSettings,
)
from app.models.enums import CalendarProvider
from app.scheduler.free_busy import FreeBusyDiagnostic
from app.scheduler.horizon import compute_horizon

# Engineering candidates — not live household settings (T1-C proposal).
FRESHNESS_AGE_CEILING = timedelta(minutes=15)
MIN_COVERAGE_PAD = timedelta(hours=24)
# Default explicit sync pulls past the collect gate's right edge so rolling
# ``now`` during the freshness interval does not outrun fetched coverage.
COVERAGE_SYNC_FETCH_HEADROOM = FRESHNESS_AGE_CEILING


class CalendarFreshnessError(RuntimeError):
    def __init__(self, trust: "CalendarFreshnessTrust") -> None:
        self.trust = trust
        super().__init__(
            "CalendarFreshnessTrust.ok=false: stale or incomplete calendar coverage "
            "blocks placement (gate-only — sync explicitly first)."
        )


@dataclass
class CalendarFreshnessTrust:
    ok: bool
    blocking_diagnostics: list[FreeBusyDiagnostic] = field(default_factory=list)
    affected_horizon: dict[str, str] | Literal["unknown_extent"] | None = None
    required_window_start: datetime | None = None
    required_window_end: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocking_diagnostics": [d.to_jsonable() for d in self.blocking_diagnostics],
            "affected_horizon": self.affected_horizon,
            "required_window_start": (
                self.required_window_start.isoformat() if self.required_window_start else None
            ),
            "required_window_end": (
                self.required_window_end.isoformat() if self.required_window_end else None
            ),
        }


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def coverage_pad_elapsed(user_settings: UserSettings) -> timedelta:
    buffer_minutes = user_settings.inter_block_buffer_minutes
    if buffer_minutes is None:
        return MIN_COVERAGE_PAD
    buffer_pad = timedelta(minutes=int(buffer_minutes))
    return max(buffer_pad, MIN_COVERAGE_PAD)


def required_coverage_window(
    user_settings: UserSettings,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    """Padded scheduling horizon bounds required for complete-window evidence."""
    now_utc = _ensure_utc(now_utc)
    horizon_start, horizon_end = compute_horizon(user_settings, now_utc)
    pad = coverage_pad_elapsed(user_settings)
    return horizon_start - pad, horizon_end + pad


def default_explicit_sync_window(
    user_settings: UserSettings,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    """Provider pull bounds when the sync route omits start/end."""
    req_start, req_end = required_coverage_window(user_settings, now_utc)
    return req_start, req_end + COVERAGE_SYNC_FETCH_HEADROOM


def proposal_padded_coverage_window(
    proposal: dict[str, Any],
    user_settings: UserSettings,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    """Placement horizon for Apply: proposed block span + pad (fallback: scheduling horizon)."""
    blocks = proposal.get("proposed_blocks") or []
    if not blocks:
        return required_coverage_window(user_settings, now_utc)
    starts: list[datetime] = []
    ends: list[datetime] = []
    for row in blocks:
        starts.append(_ensure_utc(datetime.fromisoformat(str(row["start_time"]).replace("Z", "+00:00"))))
        ends.append(_ensure_utc(datetime.fromisoformat(str(row["end_time"]).replace("Z", "+00:00"))))
    pad = coverage_pad_elapsed(user_settings)
    return min(starts) - pad, max(ends) + pad


def _effective_failure(
    subscription: CalendarSubscription,
    sidecar: tuple[datetime, str] | None,
) -> tuple[datetime | None, str | None]:
    """Latest of the row failure columns and the durable sidecar, if any."""
    best_at: datetime | None = None
    best_cause: str | None = None
    candidates: list[tuple[datetime, str | None]] = []
    if subscription.coverage_last_failure_at is not None:
        candidates.append(
            (subscription.coverage_last_failure_at, subscription.coverage_last_failure_cause)
        )
    if sidecar is not None:
        candidates.append(sidecar)
    for failure_at, cause in candidates:
        failure_utc = _ensure_utc(failure_at)
        if best_at is None or failure_utc >= best_at:
            best_at = failure_utc
            best_cause = cause or "calendar_refresh_failed"
    return best_at, best_cause


def _failure_blocks_readiness(
    subscription: CalendarSubscription,
    sidecar: tuple[datetime, str] | None = None,
) -> bool:
    failure_at, _cause = _effective_failure(subscription, sidecar)
    success_at = subscription.coverage_success_at
    if failure_at is None:
        return False
    if success_at is None:
        return True
    return failure_at >= _ensure_utc(success_at)


def _load_sidecar_failures(
    db: Session,
    subscription_ids: list[UUID],
) -> dict[UUID, tuple[datetime, str]]:
    if not subscription_ids:
        return {}
    rows = (
        db.query(CalendarSubscriptionRefreshFailure)
        .filter(CalendarSubscriptionRefreshFailure.subscription_id.in_(subscription_ids))
        .all()
    )
    return {row.subscription_id: (row.failure_at, row.cause) for row in rows}


def _subscription_label(subscription: CalendarSubscription) -> str:
    return (subscription.summary or subscription.external_calendar_id or str(subscription.id))[:255]


def _recovery_for(cause: str) -> str:
    """Operator hint. Must not describe Microsoft as incomplete solely for lacking a delta cursor."""
    hints = {
        "calendar_coverage_missing": (
            "Request an explicit sync that finishes the padded horizon before collect or Apply."
        ),
        "calendar_coverage_stale": (
            "Request an explicit sync; this calendar's complete-window evidence is older than 15 minutes."
        ),
        "calendar_coverage_window_insufficient": (
            "Request an explicit sync covering the full padded horizon, including the right edge."
        ),
        "calendar_pagination_incomplete": (
            "Retry the explicit sync until the provider page chain is fully drained."
        ),
        "calendar_coverage_generation_mismatch": (
            "Retry the explicit sync so cache, cursor, and coverage finish as one generation."
        ),
        "calendar_coverage_window_missing": (
            "Request an explicit sync that records a complete coverage window."
        ),
        "calendar_freshness_not_evaluated": (
            "Re-run collect so calendar freshness is evaluated before Apply."
        ),
        "microsoft_coverage_unverified": (
            "Microsoft coverage is unverified this increment and does not count as fresh."
        ),
        "google_subscription_refresh_failed": (
            "Retry an explicit Google sync for this calendar; last refresh failed before minting coverage."
        ),
        "calendar_refresh_failed": (
            "Retry an explicit sync for this calendar; last refresh failed before minting coverage."
        ),
        "calendar_requested_subscription_missing": (
            "A requested calendar subscription is no longer present; re-select calendars or reconnect the account."
        ),
    }
    return hints.get(cause, "Retry an explicit sync for this calendar before collect or Apply.")


def _evaluate_one_subscription(
    subscription: CalendarSubscription,
    account: CalendarAccount,
    *,
    now_utc: datetime,
    required_start: datetime,
    required_end: datetime,
    sidecar: tuple[datetime, str] | None = None,
) -> FreeBusyDiagnostic | None:
    name = _subscription_label(subscription)
    horizon_label = f"{required_start.isoformat()} – {required_end.isoformat()}"

    # T1-E: narrow MS short-circuit only when coverage_mode is the bounded
    # view provenance. Arbitrary populated success fields do not count.
    if account.provider == CalendarProvider.microsoft and subscription.coverage_mode != "ms_view":
        return FreeBusyDiagnostic(
            cause="microsoft_coverage_unverified",
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=None,
            end=None,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            provenance="microsoft_success_minting_deferred",
            recovery=_recovery_for("microsoft_coverage_unverified"),
        )

    if _failure_blocks_readiness(subscription, sidecar):
        _failure_at, failure_cause = _effective_failure(subscription, sidecar)
        cause = failure_cause or "calendar_refresh_failed"
        return FreeBusyDiagnostic(
            cause=cause,
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=None,
            end=None,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            recovery=_recovery_for(cause),
        )

    success_at = subscription.coverage_success_at
    if success_at is None:
        return FreeBusyDiagnostic(
            cause="calendar_coverage_missing",
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=None,
            end=None,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            recovery=_recovery_for("calendar_coverage_missing"),
        )

    age = _ensure_utc(now_utc) - _ensure_utc(success_at)
    if age > FRESHNESS_AGE_CEILING:
        return FreeBusyDiagnostic(
            cause="calendar_coverage_stale",
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=subscription.coverage_window_start,
            end=subscription.coverage_window_end,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            recovery=_recovery_for("calendar_coverage_stale"),
        )

    if not subscription.coverage_pagination_complete:
        return FreeBusyDiagnostic(
            cause="calendar_pagination_incomplete",
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=None,
            end=None,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            recovery=_recovery_for("calendar_pagination_incomplete"),
        )

    active_gen = int(subscription.coverage_active_generation or 0)
    success_gen = subscription.coverage_success_generation
    if success_gen is None or int(success_gen) != active_gen:
        return FreeBusyDiagnostic(
            cause="calendar_coverage_generation_mismatch",
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=None,
            end=None,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            recovery=_recovery_for("calendar_coverage_generation_mismatch"),
        )

    win_start = subscription.coverage_window_start
    win_end = subscription.coverage_window_end
    if win_start is None or win_end is None:
        return FreeBusyDiagnostic(
            cause="calendar_coverage_window_missing",
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=None,
            end=None,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            recovery=_recovery_for("calendar_coverage_window_missing"),
        )

    ws = _ensure_utc(win_start)
    we = _ensure_utc(win_end)
    if ws > required_start or we < required_end:
        return FreeBusyDiagnostic(
            cause="calendar_coverage_window_insufficient",
            calendar_name=name,
            event_title="(subscription)",
            event_id=str(subscription.id),
            start=ws,
            end=we,
            blocking_current_proposal=True,
            affected_horizon=horizon_label,
            recovery=_recovery_for("calendar_coverage_window_insufficient"),
        )

    return None


def evaluate_calendar_freshness(
    db: Session,
    owner_id: UUID,
    user_settings: UserSettings,
    now_utc: datetime,
    *,
    required_start: datetime | None = None,
    required_end: datetime | None = None,
) -> CalendarFreshnessTrust:
    now_utc = _ensure_utc(now_utc)
    if required_start is None or required_end is None:
        required_start, required_end = required_coverage_window(user_settings, now_utc)
    else:
        required_start = _ensure_utc(required_start)
        required_end = _ensure_utc(required_end)

    rows = (
        db.query(CalendarSubscription, CalendarAccount)
        .join(CalendarAccount, CalendarSubscription.calendar_account_id == CalendarAccount.id)
        .filter(
            CalendarSubscription.owner_id == owner_id,
            CalendarSubscription.is_enabled.is_(True),
            CalendarAccount.is_enabled.is_(True),
        )
        .all()
    )

    sidecar_by_sub = _load_sidecar_failures(db, [subscription.id for subscription, _account in rows])
    blocking: list[FreeBusyDiagnostic] = []
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


def require_calendar_freshness(trust: CalendarFreshnessTrust | None) -> None:
    if trust is None:
        missing = CalendarFreshnessTrust(
            ok=False,
            blocking_diagnostics=[
                FreeBusyDiagnostic(
                    cause="calendar_freshness_not_evaluated",
                    calendar_name="(unknown)",
                    event_title="(subscription)",
                    event_id="",
                    start=None,
                    end=None,
                    blocking_current_proposal=True,
                    affected_horizon="unknown_extent",
                    recovery=_recovery_for("calendar_freshness_not_evaluated"),
                )
            ],
            affected_horizon="unknown_extent",
        )
        raise CalendarFreshnessError(missing)
    if not trust.ok:
        raise CalendarFreshnessError(trust)
