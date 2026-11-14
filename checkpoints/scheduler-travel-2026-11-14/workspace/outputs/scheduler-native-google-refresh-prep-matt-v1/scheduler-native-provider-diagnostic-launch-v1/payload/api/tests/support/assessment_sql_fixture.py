# ==============================================================================
#  File: apps/api/tests/support/assessment_sql_fixture.py
#  Description: Test-only ORM setup helpers + session-factory Protocol for A01–A10
#               assessment SQL cases. No native factory, TLS profile, or runtime
#               approval is supplied here — Dex owns that seam.
#  Component: Covering assessment fixture (Jim / prep-only; REVISE1)
#  Version: 1.1-REVISE1
#  Created: 2026-11-09
#  Last Update: 2026-11-09
# ==============================================================================
"""Assessment SQL fixture (test-only).

Hard holds for this packet:
- Does not invent a working NativeORMFactories / TLS checkout / approved profile.
- Does not replace ``_assemble_final_assessment`` with an exception stub.
- Does not claim fake query doubles are SQL proof.
- Setup transactions must be recorded separately from the operation under test.
- Cases do **not** purge synthetic owners on failure; Dex supervisor owns
  disposable-DB wipe after full suite success.

Dex wires ``AssessmentSessionFactory`` (see FIXTURE-INTERFACE.md) before any
authorized isolated PostgreSQL run. Until that binding exists, cases must not
be marked passed.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Iterator, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    ExternalCalendarEvent,
    FreeBusyOccurrenceBaseline,
    FreeBusySeriesPolicy,
    FreeBusySeriesPolicyDecision,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.calendar_freshness import (
    FRESHNESS_AGE_CEILING,
    required_coverage_window,
)
from app.services.covering_refresh import (
    FinalCoveringAssessment,
    _assemble_final_assessment,
)
from app.services.covering_refresh_window import CoveringPullWindow

UTC = timezone.utc

# Fixed assessment clock for deterministic horizons / freshness age.
ASSESSMENT_NOW = datetime(2026, 11, 9, 16, 0, 0, tzinfo=UTC)
HORIZON_LABEL = "assessment-fixture-horizon-v1"

# Opaque token placeholders only — assessment read path does not decrypt.
_TOKEN_ENC_PLACEHOLDER = "assessment-fixture-token-enc-not-a-secret"


class AssessmentFixtureUnboundError(RuntimeError):
    """Raised when Dex has not bound a real session factory for SQL proof."""


class AssessmentSessionFactory(Protocol):
    """Dex-owned seam. Jim authors requirements; Dex supplies the implementation.

    Requirements (see FIXTURE-INTERFACE.md):
    - ``open_setup_session``: mutable setup txn; commit/rollback owned by fixture
      helpers / ordinary ``close``. Setup role — never treat as ASSESSMENT terminal.
    - ``open_assessment_session``: clean ASSESSMENT-role session (no pending writes).
    - ``open_mutator_session``: concurrent session for A06/A07.
    - ``close``: ordinary close for **setup** and **mutator** sessions only.
    - ``close_known``: factory-owned ASSESSMENT-role terminal retirement. Callers
      must not issue ``session.rollback()`` / ``session.commit()`` on ASSESSMENT
      sessions — that would bypass native known-terminal classification.
    - Owner purge / disposable-DB wipe is **supervisor-owned post-success**, not a
      case ``finally`` responsibility. Cases leave synthetic owners in place on
      assertion failure / UNKNOWN / skip.
    - Concurrent open of a second session must be possible for A06/A07.
    - Sessions must be real SQLAlchemy Session against the disposable PG target.
    - No ambient production DSN; no provider HTTP; no endpoint binding.
    """

    def open_setup_session(self) -> Session: ...

    def open_assessment_session(self) -> Session: ...

    def open_mutator_session(self) -> Session: ...

    def close(self, session: Session) -> None: ...

    def close_known(self, session: Session) -> None: ...


_BOUND_FACTORY: AssessmentSessionFactory | None = None


def bind_assessment_session_factory(factory: AssessmentSessionFactory | None) -> None:
    """Test/process hook for Dex to inject the native-backed factory later."""
    global _BOUND_FACTORY
    _BOUND_FACTORY = factory


def require_assessment_session_factory() -> AssessmentSessionFactory:
    """Return the Dex-bound factory or raise unbound (never invent one)."""
    if _BOUND_FACTORY is None:
        raise AssessmentFixtureUnboundError(
            "AssessmentSessionFactory unbound — Dex owns native/PG binding; "
            "Jim assessment cases refuse to invent a factory or ambient SessionLocal."
        )
    return _BOUND_FACTORY


@dataclass
class OwnerBundle:
    user: User
    settings: UserSettings

    @property
    def owner_id(self) -> UUID:
        return self.user.id


@dataclass
class SubscriptionBundle:
    account: CalendarAccount
    subscription: CalendarSubscription


def seed_owner(
    db: Session,
    *,
    username_prefix: str,
    scheduling_revision: int = 1,
    upcoming_horizon_days: int = 7,
    inter_block_buffer_minutes: int = 15,
    timezone_name: str = "UTC",
) -> OwnerBundle:
    """Plant a unique synthetic owner (uuid suffix). Cases never purge on failure."""
    user = User(
        id=uuid4(),
        username=f"{username_prefix}-{uuid4().hex[:8]}",
        email=f"{username_prefix}-{uuid4().hex[:8]}@assessment.fixture.test",
        password_hash="assessment-fixture-hash-not-used",
        display_name=username_prefix,
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        session_epoch=0,
    )
    db.add(user)
    db.flush()
    settings = UserSettings(
        owner_id=user.id,
        timezone=timezone_name,
        workday_minutes=480,
        workday_start_local=time(8, 0),
        workweek_days=5,
        inter_block_buffer_minutes=inter_block_buffer_minutes,
        upcoming_horizon_days=upcoming_horizon_days,
        default_schedule_style=ScheduleStyle.standalone,
        scheduling_revision=scheduling_revision,
    )
    db.add(settings)
    db.flush()
    return OwnerBundle(user=user, settings=settings)


def seed_account(
    db: Session,
    owner: User,
    *,
    provider: CalendarProvider = CalendarProvider.google,
    enabled: bool = True,
    email_suffix: str | None = None,
) -> CalendarAccount:
    suffix = email_suffix or uuid4().hex[:8]
    account = CalendarAccount(
        owner_id=owner.id,
        provider=provider,
        account_email=f"a-{suffix}@assessment.fixture.test",
        access_token_enc=_TOKEN_ENC_PLACEHOLDER,
        refresh_token_enc=_TOKEN_ENC_PLACEHOLDER,
        token_expires_at=ASSESSMENT_NOW + timedelta(hours=2),
        is_enabled=enabled,
        mirror_blocks=False,
    )
    db.add(account)
    db.flush()
    return account


def seed_subscription(
    db: Session,
    account: CalendarAccount,
    *,
    calendar_id: str,
    summary: str,
    enabled: bool = True,
    sub_id: UUID | None = None,
) -> CalendarSubscription:
    row = CalendarSubscription(
        id=sub_id or uuid4(),
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary=summary,
        role=CalendarSubscriptionRole.informational,
        is_enabled=enabled,
        provider_timezone="UTC",
        coverage_active_generation=0,
    )
    db.add(row)
    db.flush()
    return row


def mark_covering_fresh(
    sub: CalendarSubscription,
    *,
    window_start: datetime,
    window_end: datetime,
    success_at: datetime,
    provider: CalendarProvider = CalendarProvider.google,
    generation: int = 1,
) -> None:
    """Plant complete-window evidence that passes ``_evaluate_one_subscription`` at ``success_at`` age."""
    sub.coverage_window_start = window_start
    sub.coverage_window_end = window_end
    # Microsoft readiness requires ms_view provenance; Google uses full.
    if provider == CalendarProvider.microsoft:
        sub.coverage_mode = "ms_view"
    else:
        sub.coverage_mode = "full"
    sub.coverage_success_at = success_at
    sub.coverage_fetched_at = success_at
    sub.coverage_pagination_complete = True
    sub.coverage_active_generation = generation
    sub.coverage_success_generation = generation
    sub.coverage_show_deleted = True
    sub.coverage_single_events = True
    sub.coverage_page_count = 1
    sub.coverage_item_count = 0
    sub.coverage_last_failure_at = None
    sub.coverage_last_failure_cause = None


def mark_covering_stale(
    sub: CalendarSubscription,
    *,
    window_start: datetime,
    window_end: datetime,
    success_at: datetime,
    provider: CalendarProvider = CalendarProvider.google,
) -> None:
    mark_covering_fresh(
        sub,
        window_start=window_start,
        window_end=window_end,
        success_at=success_at,
        provider=provider,
    )


def plant_sidecar_failure(
    db: Session,
    subscription_id: UUID,
    *,
    failure_at: datetime,
    cause: str = "calendar_refresh_failed",
) -> CalendarSubscriptionRefreshFailure:
    row = CalendarSubscriptionRefreshFailure(
        subscription_id=subscription_id,
        failure_at=failure_at,
        cause=cause,
    )
    db.add(row)
    db.flush()
    return row


def plant_busy_event(
    db: Session,
    *,
    owner_id: UUID,
    account_id: UUID,
    provider: CalendarProvider,
    calendar_id: str,
    external_event_id: str,
    title: str,
    start_time: datetime,
    end_time: datetime,
    transparency: str = "opaque",
    free_busy_provenance: str = "google_transparency",
    pending_exception: bool = False,
    provider_series_id: str | None = None,
    series_identity_state: str = "verified_non_recurring",
    source_timezone: str = "UTC",
    source_zone_missing: bool = False,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=owner_id,
        calendar_account_id=account_id,
        provider=provider,
        external_event_id=external_event_id,
        calendar_id=calendar_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        is_all_day=False,
        pending_deletion=False,
        last_synced_at=ASSESSMENT_NOW,
        transparency=transparency,
        free_busy_provenance=free_busy_provenance,
        provider_series_id=provider_series_id,
        series_identity_state=series_identity_state,
        source_timezone=source_timezone,
        source_zone_missing=source_zone_missing,
        free_busy_pending_exception=pending_exception,
        is_provider_cancelled=False,
    )
    db.add(row)
    db.flush()
    return row


def plant_series_policy(
    db: Session,
    *,
    owner_id: UUID,
    provider: CalendarProvider,
    calendar_id: str,
    provider_series_id: str,
    mapping: str = "free",
    conflict_pending_latched: bool = False,
    latch_generation: int = 0,
    resolved_at: datetime | None = None,
    resolved_by_user_id: UUID | None = None,
) -> FreeBusySeriesPolicy:
    row = FreeBusySeriesPolicy(
        owner_id=owner_id,
        provider=provider,
        calendar_id=calendar_id,
        provider_series_id=provider_series_id,
        mapping=mapping,
        conflict_pending_latched=conflict_pending_latched,
        latch_generation=latch_generation,
        resolved_at=resolved_at,
        resolved_by_user_id=resolved_by_user_id,
        decision_source="manual_resolve",
    )
    db.add(row)
    db.flush()
    return row


def plant_occurrence_baseline(
    db: Session,
    *,
    owner_id: UUID,
    provider: CalendarProvider,
    external_event_id: str,
    transparency: str = "transparent",
    free_busy_provenance: str = "manual_resolve",
    occupancy_kind: str = "free",
    source: str = "manual_resolve",
) -> FreeBusyOccurrenceBaseline:
    """Inventory-only plant. Dex confirmed: not reachable from policy_diagnostic_enrichment.

    Not a required assessment read. Do not assert this SELECT fires on the
    assessment assembly path.
    """
    row = FreeBusyOccurrenceBaseline(
        owner_id=owner_id,
        provider=provider,
        external_event_id=external_event_id,
        transparency=transparency,
        free_busy_provenance=free_busy_provenance,
        occupancy_kind=occupancy_kind,
        source=source,
    )
    db.add(row)
    db.flush()
    return row


def plant_policy_decision(
    db: Session,
    *,
    policy_id: UUID,
    decided_at: datetime,
    external_event_id: str,
    decided_by_user_id: UUID | None = None,
) -> FreeBusySeriesPolicyDecision:
    """Inventory-only decision-history plant. Not a required assessment read.

    Dex confirmed: ``policy_diagnostic_enrichment`` does not reach
    ``get_decision_baseline_for_event``.
    """
    row = FreeBusySeriesPolicyDecision(
        policy_id=policy_id,
        decided_at=decided_at,
        decided_by_user_id=decided_by_user_id,
        reason="assessment-fixture-decision",
        mapping="free",
        decision_source="manual_resolve",
        snapshot={
            "conflict_acknowledgments": [
                {
                    "external_event_id": external_event_id,
                    "provider_evidence": {
                        "transparency": "transparent",
                        "provenance": "manual_resolve",
                        "occupancy_kind": "free",
                        "source": "decision_history",
                    },
                }
            ]
        },
    )
    db.add(row)
    db.flush()
    return row


def default_pull_window(
    *,
    now: datetime = ASSESSMENT_NOW,
    days: int = 2,
) -> CoveringPullWindow:
    start = now
    end = now + timedelta(days=days)
    return CoveringPullWindow(
        effective_start=start,
        effective_end=end,
        widened=False,
        reason="none",
    )


def coverage_span_for_settings(
    settings: UserSettings,
    *,
    now: datetime = ASSESSMENT_NOW,
    extra_headroom: timedelta = timedelta(hours=1),
) -> tuple[datetime, datetime]:
    """Window large enough for both pull freshness and scheduling horizon pads."""
    h_start, h_end = required_coverage_window(settings, now)
    pull = default_pull_window(now=now)
    start = min(h_start, pull.effective_start) - extra_headroom
    end = max(h_end, pull.effective_end) + extra_headroom
    return start, end


def run_final_assessment(
    db: Session,
    *,
    owner_id: UUID,
    subscription_ids: list[UUID],
    window: CoveringPullWindow,
    assessment_now: datetime = ASSESSMENT_NOW,
    horizon_label: str | None = HORIZON_LABEL,
) -> FinalCoveringAssessment:
    """Call the real final-assessment assembly (not a stub). Session must be clean."""
    return _assemble_final_assessment(
        db,
        owner_id=owner_id,
        subscription_ids=list(subscription_ids),
        window=window,
        horizon_label=horizon_label,
        assessment_clock=lambda: assessment_now,
    )


def blocking_causes(trust_dict: dict | None) -> list[str]:
    rows = (trust_dict or {}).get("blocking_diagnostics") or []
    out: list[str] = []
    for item in rows:
        if isinstance(item, dict) and item.get("cause") is not None:
            out.append(str(item["cause"]))
    return out


def blocking_by_calendar(trust_dict: dict | None) -> dict[str, str]:
    rows = (trust_dict or {}).get("blocking_diagnostics") or []
    named: dict[str, str] = {}
    for item in rows:
        if isinstance(item, dict):
            named[str(item.get("calendar_name"))] = str(item.get("cause"))
    return named


def freshness_age_just_inside_ceiling(now: datetime = ASSESSMENT_NOW) -> datetime:
    return now - FRESHNESS_AGE_CEILING + timedelta(minutes=1)


def freshness_age_just_outside_ceiling(now: datetime = ASSESSMENT_NOW) -> datetime:
    return now - FRESHNESS_AGE_CEILING - timedelta(minutes=1)


@contextmanager
def open_setup_session(
    factory: AssessmentSessionFactory,
) -> Iterator[Session]:
    """Open a **setup-role** session. Caller seeds, commits, then ordinary ``close``.

    Receipt note: setup commit is fixture protocol, not application write evidence.
    Do not use this context for ASSESSMENT-role terminal retirement — that is
    ``close_known`` on sessions from ``open_assessment_session``.
    """
    setup = factory.open_setup_session()
    try:
        yield setup
    finally:
        factory.close(setup)


__all__ = [
    "ASSESSMENT_NOW",
    "HORIZON_LABEL",
    "AssessmentFixtureUnboundError",
    "AssessmentSessionFactory",
    "OwnerBundle",
    "SubscriptionBundle",
    "bind_assessment_session_factory",
    "blocking_by_calendar",
    "blocking_causes",
    "coverage_span_for_settings",
    "default_pull_window",
    "freshness_age_just_inside_ceiling",
    "freshness_age_just_outside_ceiling",
    "mark_covering_fresh",
    "mark_covering_stale",
    "open_setup_session",
    "plant_busy_event",
    "plant_occurrence_baseline",
    "plant_policy_decision",
    "plant_series_policy",
    "plant_sidecar_failure",
    "require_assessment_session_factory",
    "run_final_assessment",
    "seed_account",
    "seed_owner",
    "seed_subscription",
]
