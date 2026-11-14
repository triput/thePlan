# ==============================================================================
#  File: apps/api/tests/test_assessment_cases_a01_a10.py
#  Description: A01–A10 assessment SQL cases (text-authored). Intended for a
#               later separately authorized isolated PostgreSQL run after Dex
#               binds AssessmentSessionFactory. Not executed in this prep packet.
#  Component: Covering assessment cases (Jim / prep-only; REVISE3)
#  Version: 1.3-REVISE3
#  Created: 2026-11-09
#  Last Update: 2026-11-09
# ==============================================================================
"""Acceptance-Matrix A01–A10 against real ``_assemble_final_assessment`` SQL.

N01–N08 remain Dex native ownership — not claimed here.

These cases:
- call the real final-assessment assembly (no assessment exception stub);
- plant ORM rows via setup transactions separate from the assessment session;
- assert exact independent expectations;
- refuse to invent a native factory (``require_assessment_session_factory``);
- leave synthetic owners in place on failure (Dex supervisor wipes disposable DB
  only after full suite success — no per-case destructive purge);
- retire ASSESSMENT sessions via ``factory.close_known`` (never caller rollback);
- A06/A07: from successful ``thread.start`` onward, checkout lives inside the
  protected try; bounded join always runs; ``close_known`` only if a session was
  returned; primary checkout/assessment failure preserved over secondaries.

Fake query doubles elsewhere in the v3 baseline are regression wiring only and
are not SQL proof for these IDs.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import inspect as sa_inspect

from app.api.errors import ApiError
from app.models import CalendarSubscription, UserSettings
from app.models.enums import CalendarProvider
from app.scheduler.calendar_freshness import required_coverage_window
from app.services import covering_domain_dispatch as domain
from app.services.covering_refresh import _assemble_final_assessment
from app.services.covering_role_admission import CoveringRole
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown
from app.services.scheduling_revision import (
    increment_scheduling_revision,
    lock_owner_scheduling,
)
from app.schemas.calendar import CoveringRefreshRequest

from tests.support.assessment_sql_fixture import (
    ASSESSMENT_NOW,
    HORIZON_LABEL,
    AssessmentFixtureUnboundError,
    blocking_by_calendar,
    blocking_causes,
    coverage_span_for_settings,
    default_pull_window,
    freshness_age_just_inside_ceiling,
    freshness_age_just_outside_ceiling,
    mark_covering_fresh,
    open_setup_session,
    plant_busy_event,
    plant_occurrence_baseline,
    plant_policy_decision,
    plant_series_policy,
    plant_sidecar_failure,
    require_assessment_session_factory,
    run_final_assessment,
    seed_account,
    seed_owner,
    seed_subscription,
)

# Collection marker only. Passing still requires Dex binding + authorized PG run.
pytestmark = pytest.mark.assessment_sql_fixture


def _factory():
    try:
        return require_assessment_session_factory()
    except AssessmentFixtureUnboundError as exc:
        pytest.skip(str(exc))


def _join_mutator(thread: threading.Thread, *, label: str, timeout: float = 60.0) -> None:
    """Bounded join with completion proof. Timed join alone is not success."""
    thread.join(timeout=timeout)
    if thread.is_alive():
        raise TimeoutError(
            f"{label}: mutator thread still alive after {timeout}s join — "
            "timed join alone is not completion proof"
        )


def _raise_mutator_errors(errors: list[BaseException], *, label: str) -> None:
    if errors:
        raise RuntimeError(f"{label}: mutator thread raised") from errors[0]


def _note_secondary(primary: BaseException, *, label: str, detail: str) -> None:
    """Attach a secondary cleanup failure without replacing the primary."""
    try:
        primary.add_note(f"{label}: {detail}")
    except Exception:
        pass


def _close_known_then_join_mutator(
    factory,
    assess: Any | None,
    mutator: threading.Thread,
    mutator_errors: list[BaseException],
    *,
    label: str,
    primary: BaseException | None = None,
) -> None:
    """Retire ASSESSMENT (if any), then always join mutator (REVISE3 lifetime).

    Structure::

        try:
            if assess is not None:
                factory.close_known(assess)
        finally:
            _join_mutator(...)  # always runs after successful thread.start

    Covers checkout failure (``assess is None``): skip ``close_known``, still join.
    Nested ``finally`` also covers ``close_known`` raising. No new DB cleanup
    sessions (including after UNKNOWN). Thread exceptions stay explicit via
    ``mutator_errors``.

    Exception priority: checkout/assessment primary > ``close_known`` > join/mutator.
    Secondary failures are noted on the surviving exception; they do not clobber
    a primary already in flight.
    """
    close_exc: BaseException | None = None
    join_exc: BaseException | None = None
    try:
        if assess is not None:
            factory.close_known(assess)
    except BaseException as exc:
        close_exc = exc
    finally:
        # Always runs after a successful mutator.start — even if checkout failed
        # (assess is None) or close_known raised.
        try:
            _join_mutator(mutator, label=label)
            _raise_mutator_errors(mutator_errors, label=label)
        except BaseException as exc:
            join_exc = exc

    if primary is not None:
        if close_exc is not None:
            _note_secondary(
                primary, label=label, detail=f"close_known also failed: {close_exc!r}"
            )
        if join_exc is not None:
            _note_secondary(
                primary, label=label, detail=f"mutator join also failed: {join_exc!r}"
            )
        # Caller already raised primary; do not replace it.
        return
    if close_exc is not None:
        if join_exc is not None:
            _note_secondary(
                close_exc, label=label, detail=f"mutator join also failed: {join_exc!r}"
            )
        raise close_exc
    if join_exc is not None:
        raise join_exc


# ---------------------------------------------------------------------------
# A01 — Healthy requested + all-enabled
# ---------------------------------------------------------------------------


def test_a01_healthy_requested_and_all_enabled() -> None:
    """A01: real final assessment; exact windows; one timestamp/revision; ready true."""
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a01", scheduling_revision=11)
        owner_id = primary.owner_id
        account = seed_account(setup, primary.user, provider=CalendarProvider.google)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        success_at = freshness_age_just_inside_ceiling()
        req = seed_subscription(
            setup, account, calendar_id="cal-a01-req", summary="A01 Requested"
        )
        sib = seed_subscription(
            setup, account, calendar_id="cal-a01-sib", summary="A01 Sibling"
        )
        mark_covering_fresh(
            req, window_start=cov_start, window_end=cov_end, success_at=success_at
        )
        mark_covering_fresh(
            sib, window_start=cov_start, window_end=cov_end, success_at=success_at
        )
        setup.commit()
        req_id, sib_id = req.id, sib.id
        revision = int(primary.settings.scheduling_revision)
        settings_snapshot = primary.settings

    window = default_pull_window()
    assess = factory.open_assessment_session()
    try:
        final = run_final_assessment(
            assess,
            owner_id=owner_id,
            subscription_ids=[req_id],
            window=window,
        )
    finally:
        factory.close_known(assess)

    horizon_start, horizon_end = required_coverage_window(
        settings_snapshot, ASSESSMENT_NOW
    )
    assert final.requested.ok is True
    assert final.requested.blocking_diagnostics == []
    assert final.requested.required_window_start == window.effective_start
    assert final.requested.required_window_end == window.effective_end
    assert final.readiness.scheduling_ready is True
    assert final.readiness.assessment_error is None
    assert final.readiness.evaluated_at == ASSESSMENT_NOW
    assert final.readiness.scheduling_revision == revision == 11
    assert final.readiness.horizon is not None
    assert final.readiness.horizon.start == horizon_start
    assert final.readiness.horizon.end == horizon_end
    assert final.readiness.horizon_label == HORIZON_LABEL
    assert (final.readiness.freshness_all_enabled or {}).get("ok") is True
    assert (final.readiness.busy_input_trust or {}).get("ok") is True
    assert final.readiness.blocking_summary == []
    # Independent: requested subset freshness must not be confused with all-enabled.
    assert final.requested.ok is True and (final.readiness.freshness_all_enabled or {}).get(
        "ok"
    ) is True
    # Owners left in place — Dex supervisor wipes disposable DB after full success.


# ---------------------------------------------------------------------------
# A02 — Requested vs all-enabled
# ---------------------------------------------------------------------------


def test_a02_requested_ok_all_enabled_blocked_by_unrequested_stale() -> None:
    """A02: requested freshness passes; unrequested enabled stale blocks readiness."""
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a02", scheduling_revision=3)
        owner_id = primary.owner_id
        account = seed_account(setup, primary.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        req = seed_subscription(
            setup, account, calendar_id="cal-a02-req", summary="A02 Requested"
        )
        stale = seed_subscription(
            setup, account, calendar_id="cal-a02-stale", summary="A02 Stale Enabled"
        )
        disabled = seed_subscription(
            setup,
            account,
            calendar_id="cal-a02-off",
            summary="A02 Disabled",
            enabled=False,
        )
        disabled_acct = seed_account(
            setup, primary.user, enabled=False, email_suffix="disabled"
        )
        orphan = seed_subscription(
            setup,
            disabled_acct,
            calendar_id="cal-a02-disabled-acct",
            summary="A02 Disabled Account Sub",
        )
        mark_covering_fresh(
            req,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        mark_covering_fresh(
            stale,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_outside_ceiling(),
        )
        mark_covering_fresh(
            disabled,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_outside_ceiling(),
        )
        mark_covering_fresh(
            orphan,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_outside_ceiling(),
        )
        setup.commit()
        req_id = req.id

    window = default_pull_window()
    assess = factory.open_assessment_session()
    try:
        final = run_final_assessment(
            assess,
            owner_id=owner_id,
            subscription_ids=[req_id],
            window=window,
        )
    finally:
        factory.close_known(assess)

    assert final.requested.ok is True
    assert final.readiness.scheduling_ready is False
    all_enabled = final.readiness.freshness_all_enabled or {}
    assert all_enabled.get("ok") is False
    by_name = blocking_by_calendar(all_enabled)
    assert by_name.get("A02 Stale Enabled") == "calendar_coverage_stale"
    # Disabled subscription / disabled-account sub must not appear in all-enabled blockers.
    assert "A02 Disabled" not in by_name
    assert "A02 Disabled Account Sub" not in by_name
    assert "A02 Requested" not in by_name


# ---------------------------------------------------------------------------
# A03 — Owner isolation
# ---------------------------------------------------------------------------


def test_a03_other_owner_rows_cannot_contaminate() -> None:
    """A03: other-owner subs/failures/events/policies do not affect primary results."""
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a03p", scheduling_revision=5)
        other = seed_owner(setup, username_prefix="a03o", scheduling_revision=99)
        p_acct = seed_account(setup, primary.user)
        o_acct = seed_account(setup, other.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        p_sub = seed_subscription(
            setup, p_acct, calendar_id="cal-a03-p", summary="A03 Primary"
        )
        o_sub = seed_subscription(
            setup, o_acct, calendar_id="cal-a03-o", summary="A03 Other Contaminant"
        )
        mark_covering_fresh(
            p_sub,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        # Other owner: stale + sidecar failure + pending busy + latched policy.
        mark_covering_fresh(
            o_sub,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_outside_ceiling(),
        )
        plant_sidecar_failure(
            setup,
            o_sub.id,
            failure_at=ASSESSMENT_NOW,
            cause="google_subscription_refresh_failed",
        )
        series_id = f"series-a03-{uuid4().hex[:8]}"
        plant_busy_event(
            setup,
            owner_id=other.owner_id,
            account_id=o_acct.id,
            provider=CalendarProvider.google,
            calendar_id="cal-a03-o",
            external_event_id=f"evt-a03-other-{uuid4().hex[:8]}",
            title="Other Pending",
            start_time=ASSESSMENT_NOW + timedelta(hours=1),
            end_time=ASSESSMENT_NOW + timedelta(hours=2),
            pending_exception=True,
            provider_series_id=series_id,
        )
        plant_series_policy(
            setup,
            owner_id=other.owner_id,
            provider=CalendarProvider.google,
            calendar_id="cal-a03-o",
            provider_series_id=series_id,
            conflict_pending_latched=True,
            latch_generation=3,
        )
        setup.commit()
        p_sub_id = p_sub.id
        primary_owner_id = primary.owner_id

    assess = factory.open_assessment_session()
    try:
        final = run_final_assessment(
            assess,
            owner_id=primary_owner_id,
            subscription_ids=[p_sub_id],
            window=default_pull_window(),
        )
    finally:
        factory.close_known(assess)

    assert final.requested.ok is True
    assert final.readiness.scheduling_ready is True
    assert final.readiness.scheduling_revision == 5
    all_enabled = final.readiness.freshness_all_enabled or {}
    assert all_enabled.get("ok") is True
    assert "A03 Other Contaminant" not in blocking_by_calendar(all_enabled)
    busy = final.readiness.busy_input_trust or {}
    assert busy.get("ok") is True
    for cause in blocking_causes(busy):
        assert "policy_" not in cause
        assert cause != "pending_exception_policy"


# ---------------------------------------------------------------------------
# A04 — Coverage gates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gate,mutator,expected_cause",
    [
        (
            "missing_success",
            lambda sub, *_: setattr(sub, "coverage_success_at", None),
            "calendar_coverage_missing",
        ),
        (
            "stale_age",
            lambda sub, cov_start, cov_end: mark_covering_fresh(
                sub,
                window_start=cov_start,
                window_end=cov_end,
                success_at=freshness_age_just_outside_ceiling(),
            ),
            "calendar_coverage_stale",
        ),
        (
            "window_missing",
            lambda sub, *_: (
                setattr(sub, "coverage_window_start", None),
                setattr(sub, "coverage_window_end", None),
            ),
            "calendar_coverage_window_missing",
        ),
        (
            "window_short",
            lambda sub, cov_start, cov_end: (
                setattr(sub, "coverage_window_start", default_pull_window().effective_start + timedelta(minutes=1)),
                setattr(sub, "coverage_window_end", cov_end - timedelta(days=1)),
            ),
            "calendar_coverage_window_insufficient",
        ),
        (
            "pages_incomplete",
            lambda sub, *_: setattr(sub, "coverage_pagination_complete", False),
            "calendar_pagination_incomplete",
        ),
        (
            "generation_mismatch",
            lambda sub, *_: (
                setattr(sub, "coverage_success_generation", 1),
                setattr(sub, "coverage_active_generation", 2),
            ),
            "calendar_coverage_generation_mismatch",
        ),
        (
            "microsoft_ms_view",
            lambda sub, cov_start, cov_end: (
                mark_covering_fresh(
                    sub,
                    window_start=cov_start,
                    window_end=cov_end,
                    success_at=freshness_age_just_inside_ceiling(),
                    provider=CalendarProvider.google,  # deliberately wrong mode below
                ),
                setattr(sub, "coverage_mode", "full"),
            ),
            "microsoft_coverage_unverified",
        ),
    ],
)
def test_a04_coverage_gates(gate: str, mutator, expected_cause: str) -> None:
    """A04: each coverage gate yields the exact diagnostic cause."""
    factory = _factory()
    with open_setup_session(factory) as setup:
        provider = (
            CalendarProvider.microsoft
            if gate == "microsoft_ms_view"
            else CalendarProvider.google
        )
        primary = seed_owner(setup, username_prefix=f"a04-{gate}", scheduling_revision=2)
        owner_id = primary.owner_id
        account = seed_account(setup, primary.user, provider=provider)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        sub = seed_subscription(
            setup, account, calendar_id=f"cal-a04-{gate}", summary=f"A04 {gate}"
        )
        mark_covering_fresh(
            sub,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
            provider=provider,
        )
        mutator(sub, cov_start, cov_end)
        setup.commit()
        sub_id = sub.id

    assess = factory.open_assessment_session()
    try:
        final = run_final_assessment(
            assess,
            owner_id=owner_id,
            subscription_ids=[sub_id],
            window=default_pull_window(),
        )
    finally:
        factory.close_known(assess)

    assert final.requested.ok is False
    assert expected_cause in blocking_causes(final.requested.to_dict())
    assert final.readiness.scheduling_ready is False
    assert expected_cause in blocking_causes(final.readiness.freshness_all_enabled)


# ---------------------------------------------------------------------------
# A05 — Failure ordering (sidecar vs success)
# ---------------------------------------------------------------------------


def test_a05_newer_sidecar_failure_blocks_equal_protects() -> None:
    """A05: newer/equal sidecar failure blocks; later success protects."""
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a05", scheduling_revision=4)
        owner_id = primary.owner_id
        account = seed_account(setup, primary.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        blocked = seed_subscription(
            setup, account, calendar_id="cal-a05-block", summary="A05 Blocked"
        )
        protected = seed_subscription(
            setup, account, calendar_id="cal-a05-ok", summary="A05 Protected"
        )
        success_at = freshness_age_just_inside_ceiling()
        mark_covering_fresh(
            blocked, window_start=cov_start, window_end=cov_end, success_at=success_at
        )
        mark_covering_fresh(
            protected, window_start=cov_start, window_end=cov_end, success_at=success_at
        )
        # Newer-or-equal failure vs success_at blocks.
        plant_sidecar_failure(
            setup,
            blocked.id,
            failure_at=success_at,
            cause="calendar_refresh_failed",
        )
        # Older sidecar than success does not block.
        plant_sidecar_failure(
            setup,
            protected.id,
            failure_at=success_at - timedelta(minutes=5),
            cause="calendar_refresh_failed",
        )
        setup.commit()
        blocked_id, protected_id = blocked.id, protected.id

    # Independent call 1: blocked id alone.
    assess = factory.open_assessment_session()
    try:
        blocked_final = run_final_assessment(
            assess,
            owner_id=owner_id,
            subscription_ids=[blocked_id],
            window=default_pull_window(),
        )
    finally:
        factory.close_known(assess)

    assert blocked_final.requested.ok is False
    assert "calendar_refresh_failed" in blocking_causes(blocked_final.requested.to_dict())

    # Independent call 2: protected id alone — requested ok; all-enabled still sees blocked sibling.
    assess = factory.open_assessment_session()
    try:
        protected_final = run_final_assessment(
            assess,
            owner_id=owner_id,
            subscription_ids=[protected_id],
            window=default_pull_window(),
        )
    finally:
        factory.close_known(assess)

    assert protected_final.requested.ok is True
    assert protected_final.readiness.scheduling_ready is False
    by_name = blocking_by_calendar(protected_final.readiness.freshness_all_enabled)
    assert by_name.get("A05 Blocked") == "calendar_refresh_failed"
    assert "A05 Protected" not in by_name


# ---------------------------------------------------------------------------
# A06 — Concurrent persisted change / identity-map refresh
# ---------------------------------------------------------------------------


def test_a06_identity_map_cannot_conceal_deleted_requested() -> None:
    """A06: preloaded identity map cannot hide deleted requested subscription."""
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a06", scheduling_revision=6)
        account = seed_account(setup, primary.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        surviving = seed_subscription(
            setup, account, calendar_id="cal-a06-keep", summary="A06 Keep"
        )
        doomed = seed_subscription(
            setup, account, calendar_id="cal-a06-gone", summary="A06 Gone"
        )
        mark_covering_fresh(
            surviving,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        mark_covering_fresh(
            doomed,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        setup.commit()
        surviving_id, doomed_id = surviving.id, doomed.id
        owner_id = primary.owner_id

    paused = threading.Event()
    release = threading.Event()
    receipt: dict[str, Any] = {}
    mutator_errors: list[BaseException] = []
    real = _assemble_final_assessment

    def _wrapped(db, **kwargs):
        # Preload requested rows into identity map before owner lock (stale snapshot).
        loaded = (
            db.query(CalendarSubscription)
            .filter(CalendarSubscription.owner_id == owner_id)
            .all()
        )
        assert {row.id for row in loaded} >= {surviving_id, doomed_id}
        for row in loaded:
            assert sa_inspect(row).expired is False
        receipt["planted_unexpired"] = True
        paused.set()
        if not release.wait(60):
            raise TimeoutError("A06 mutator did not delete while assessment paused")
        return real(db, **kwargs)

    # Patch only for this case's assessment call path.
    import app.services.covering_refresh as covering_refresh_mod

    covering_refresh_mod._assemble_final_assessment = _wrapped  # type: ignore[assignment]
    try:

        def _mutate() -> None:
            try:
                if not paused.wait(60):
                    raise TimeoutError("A06 assessment never paused")
                mut = factory.open_mutator_session()
                try:
                    row = mut.get(CalendarSubscription, doomed_id)
                    assert row is not None
                    mut.delete(row)
                    mut.commit()
                    receipt["deleted"] = True
                finally:
                    factory.close(mut)
            except BaseException as exc:
                mutator_errors.append(exc)
                raise
            finally:
                release.set()

        mutator = threading.Thread(target=_mutate, name="a06-mutator")
        mutator.start()
        # Lifetime from successful start: checkout + assessment inside protected try;
        # finally always joins; close_known only if a session was returned.
        assess = None
        primary_exc: BaseException | None = None
        try:
            assess = factory.open_assessment_session()
            # Call through module so wrap applies.
            final = covering_refresh_mod._assemble_final_assessment(
                assess,
                owner_id=owner_id,
                subscription_ids=[surviving_id, doomed_id],
                window=default_pull_window(),
                horizon_label=HORIZON_LABEL,
                assessment_clock=lambda: ASSESSMENT_NOW,
            )
        except BaseException as exc:
            primary_exc = exc
            raise
        finally:
            # Join always runs after start; skip close_known when assess is None
            # (checkout failed / UNKNOWN). No post-UNKNOWN DB cleanup.
            _close_known_then_join_mutator(
                factory,
                assess,
                mutator,
                mutator_errors,
                label="A06",
                primary=primary_exc,
            )
    finally:
        covering_refresh_mod._assemble_final_assessment = real  # type: ignore[assignment]

    assert receipt.get("planted_unexpired") is True
    assert receipt.get("deleted") is True
    assert final.requested.ok is False
    causes = blocking_causes(final.requested.to_dict())
    assert "calendar_requested_subscription_missing" in causes
    # Surviving requested id must not be reported missing.
    missing_ids = {
        str(d.event_id)
        for d in final.requested.blocking_diagnostics
        if d.cause == "calendar_requested_subscription_missing"
    }
    assert str(doomed_id) in missing_ids
    assert str(surviving_id) not in missing_ids


# ---------------------------------------------------------------------------
# A07 — Owner lock / revision (committed-before-lock ordering, not lock contention)
# ---------------------------------------------------------------------------


def test_a07_owner_lock_returns_locked_revision_not_mixed() -> None:
    """A07: returned revision is the post-mutator committed value seen under lock.

    Proof scope (do not overstate): wrap pauses *before* ``lock_owner_scheduling``,
    mutator commits revision 21, then assessment resumes and locks. This proves a
    **committed revision before lock** is what assessment returns — not that two
    sessions contended on the advisory lock simultaneously. Actual lock-contention
    evidence would require overlapping FOR UPDATE / advisory-lock waits and is
    **out of scope** for this case.
    """
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a07", scheduling_revision=20)
        account = seed_account(setup, primary.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        sub = seed_subscription(
            setup, account, calendar_id="cal-a07", summary="A07 Locked"
        )
        mark_covering_fresh(
            sub,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        setup.commit()
        sub_id = sub.id
        owner_id = primary.owner_id

    paused = threading.Event()
    release = threading.Event()
    receipt: dict[str, Any] = {}
    mutator_errors: list[BaseException] = []
    real = _assemble_final_assessment

    def _wrapped(db, **kwargs):
        # Pause before real assembly (before lock) so mutator can commit first.
        paused.set()
        if not release.wait(60):
            raise TimeoutError("A07 mutator did not finish")
        return real(db, **kwargs)

    import app.services.covering_refresh as covering_refresh_mod

    covering_refresh_mod._assemble_final_assessment = _wrapped  # type: ignore[assignment]
    try:

        def _mutate() -> None:
            try:
                if not paused.wait(60):
                    raise TimeoutError("A07 assessment never paused")
                mut = factory.open_mutator_session()
                try:
                    settings = lock_owner_scheduling(mut, owner_id)
                    receipt["mutator_saw_revision"] = int(settings.scheduling_revision)
                    receipt["mutator_new_revision"] = increment_scheduling_revision(
                        mut, settings
                    )
                    mut.commit()
                finally:
                    factory.close(mut)
            except BaseException as exc:
                mutator_errors.append(exc)
                raise
            finally:
                release.set()

        # Assessment starts first but pauses *before* lock; mutator commits 21;
        # assessment then locks and must return 21 (committed-before-lock), not 20.
        mutator = threading.Thread(target=_mutate, name="a07-mutator")
        mutator.start()
        # Lifetime from successful start: checkout + assessment inside protected try;
        # finally always joins; close_known only if a session was returned.
        assess = None
        primary_exc: BaseException | None = None
        try:
            assess = factory.open_assessment_session()
            final = covering_refresh_mod._assemble_final_assessment(
                assess,
                owner_id=owner_id,
                subscription_ids=[sub_id],
                window=default_pull_window(),
                horizon_label=HORIZON_LABEL,
                assessment_clock=lambda: ASSESSMENT_NOW,
            )
        except BaseException as exc:
            primary_exc = exc
            raise
        finally:
            # Join always runs after start; skip close_known when assess is None
            # (checkout failed / UNKNOWN). No post-UNKNOWN DB cleanup.
            _close_known_then_join_mutator(
                factory,
                assess,
                mutator,
                mutator_errors,
                label="A07",
                primary=primary_exc,
            )
    finally:
        covering_refresh_mod._assemble_final_assessment = real  # type: ignore[assignment]

    assert receipt.get("mutator_saw_revision") == 20
    assert receipt.get("mutator_new_revision") == 21
    assert final.readiness.scheduling_revision == 21
    assert final.readiness.evaluated_at == ASSESSMENT_NOW
    # No mixed evidence: readiness revision matches locked post-mutator value only.
    assert final.readiness.scheduling_revision != 20


# ---------------------------------------------------------------------------
# A08 — Busy readiness / policy enrichment
# ---------------------------------------------------------------------------


def test_a08_busy_policy_enrichment_and_horizon_filtering() -> None:
    """A08: immovable busy, pending enrichment, series policy; inventory baselines.

    Dex confirmed (REVISE1): occurrence-baseline and decision-history SQL are
    **not** reachable from ``policy_diagnostic_enrichment``. Planted inventory
    rows remain labeled inventory-only — not required assessment proof. Required
    reachable evidence is FreeBusySeriesPolicy load + enrichment payload causes.
    """
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a08", scheduling_revision=8)
        owner_id = primary.owner_id
        account = seed_account(setup, primary.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        sub = seed_subscription(
            setup, account, calendar_id="cal-a08", summary="A08 Busy Cal"
        )
        mark_covering_fresh(
            sub,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        series_pending = f"series-a08-pending-{uuid4().hex[:8]}"
        series_latched = f"series-a08-latched-{uuid4().hex[:8]}"
        pending_id = f"evt-a08-pending-{uuid4().hex[:8]}"
        latched_id = f"evt-a08-latched-{uuid4().hex[:8]}"
        # Trusted opaque busy inside horizon — not a trust blocker by itself.
        plant_busy_event(
            setup,
            owner_id=owner_id,
            account_id=account.id,
            provider=CalendarProvider.google,
            calendar_id="cal-a08",
            external_event_id=f"evt-a08-busy-{uuid4().hex[:8]}",
            title="Trusted Busy",
            start_time=ASSESSMENT_NOW + timedelta(hours=2),
            end_time=ASSESSMENT_NOW + timedelta(hours=3),
            transparency="opaque",
            free_busy_provenance="google_transparency",
            provider_series_id=f"series-a08-busy-{uuid4().hex[:8]}",
        )
        # Outside padded horizon — must not alone make busy trust fail when known busy.
        plant_busy_event(
            setup,
            owner_id=owner_id,
            account_id=account.id,
            provider=CalendarProvider.google,
            calendar_id="cal-a08",
            external_event_id=f"evt-a08-far-{uuid4().hex[:8]}",
            title="Far Busy",
            start_time=ASSESSMENT_NOW + timedelta(days=40),
            end_time=ASSESSMENT_NOW + timedelta(days=40, hours=1),
            transparency="opaque",
            free_busy_provenance="google_transparency",
            provider_series_id=f"series-a08-far-{uuid4().hex[:8]}",
        )
        pending_evt = plant_busy_event(
            setup,
            owner_id=owner_id,
            account_id=account.id,
            provider=CalendarProvider.google,
            calendar_id="cal-a08",
            external_event_id=pending_id,
            title="Pending Exception",
            start_time=ASSESSMENT_NOW + timedelta(hours=4),
            end_time=ASSESSMENT_NOW + timedelta(hours=5),
            pending_exception=True,
            provider_series_id=series_pending,
        )
        latched_evt = plant_busy_event(
            setup,
            owner_id=owner_id,
            account_id=account.id,
            provider=CalendarProvider.google,
            calendar_id="cal-a08",
            external_event_id=latched_id,
            title="Latched Conflict",
            start_time=ASSESSMENT_NOW + timedelta(hours=6),
            end_time=ASSESSMENT_NOW + timedelta(hours=7),
            pending_exception=True,
            provider_series_id=series_latched,
        )
        policy_pending = plant_series_policy(
            setup,
            owner_id=owner_id,
            provider=CalendarProvider.google,
            calendar_id="cal-a08",
            provider_series_id=series_pending,
            mapping="free",
            conflict_pending_latched=False,
            latch_generation=1,
        )
        policy_latched = plant_series_policy(
            setup,
            owner_id=owner_id,
            provider=CalendarProvider.google,
            calendar_id="cal-a08",
            provider_series_id=series_latched,
            mapping="free",
            conflict_pending_latched=True,
            latch_generation=2,
        )
        # Inventory-only — Dex confirmed not required assessment reads.
        plant_occurrence_baseline(
            setup,
            owner_id=owner_id,
            provider=CalendarProvider.google,
            external_event_id=pending_id,
        )
        plant_policy_decision(
            setup,
            policy_id=policy_pending.id,
            decided_at=ASSESSMENT_NOW - timedelta(days=1),
            external_event_id=pending_id,
            decided_by_user_id=owner_id,
        )
        setup.commit()
        sub_id = sub.id
        _ = (pending_evt.id, latched_evt.id, policy_latched.id)

    assess = factory.open_assessment_session()
    try:
        final = run_final_assessment(
            assess,
            owner_id=owner_id,
            subscription_ids=[sub_id],
            window=default_pull_window(),
        )
    finally:
        factory.close_known(assess)

    assert final.requested.ok is True
    assert final.readiness.scheduling_ready is False
    busy = final.readiness.busy_input_trust or {}
    assert busy.get("ok") is False
    causes = blocking_causes(busy)
    assert "policy_occupancy_disagreement" in causes
    assert "policy_conflict_latched" in causes
    # Enrichment must surface on diagnostics (policy_conflict payload).
    diags = busy.get("blocking_diagnostics") or []
    enriched = [
        d
        for d in diags
        if isinstance(d, dict) and d.get("policy_conflict")
    ]
    assert enriched, "expected policy_diagnostic_enrichment on pending diagnostics"
    causes_enriched = {str(d["policy_conflict"].get("cause")) for d in enriched}
    assert "policy_occupancy_disagreement" in causes_enriched
    assert "policy_conflict_latched" in causes_enriched
    for d in enriched:
        assert "conflict_revision" in d["policy_conflict"]
        assert "recovery" in d["policy_conflict"]


# ---------------------------------------------------------------------------
# A09 — Clean session / terminal errors
# ---------------------------------------------------------------------------


def test_a09_pending_writes_refused_and_terminal_sanitization(monkeypatch) -> None:
    """A09: dirty setup session refused; known ApiError sanitized; UNKNOWN stops.

    Role ownership:
    - Pending-write rejection uses a **setup-labeled** session (ordinary ``close``).
      Intent is clean-session gate proof, not ASSESSMENT terminal retirement.
    - Domain path ASSESSMENT admission/retirement is exercised via synthetic
      connector events (not a native ASSESSMENT ``close_known`` in this subcase).
    - Full ingress HTTP 503 body proof remains **explicitly pending** (domain-only
      A09; see B3 / UNSOUND-SEAMS).
    """
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a09", scheduling_revision=9)
        owner_id = primary.owner_id
        account = seed_account(setup, primary.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        sub = seed_subscription(
            setup, account, calendar_id="cal-a09", summary="A09 Clean"
        )
        mark_covering_fresh(
            sub,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        setup.commit()
        sub_id = sub.id
        account_id = account.id

    # --- pending writes refused on SETUP-labeled session (not ASSESSMENT role) ---
    dirty = factory.open_setup_session()
    try:
        settings = dirty.query(UserSettings).filter_by(owner_id=owner_id).one()
        settings.locale = "xx-XX"
        assert dirty.dirty
        with pytest.raises(RuntimeError, match="clean SQLAlchemy session"):
            run_final_assessment(
                dirty,
                owner_id=owner_id,
                subscription_ids=[sub_id],
                window=default_pull_window(),
            )
    finally:
        # Setup-owned ordinary close — may roll back pending writes.
        # Must NOT use open_assessment_session + caller rollback (native ASSESSMENT
        # terminal must go through factory.close_known only).
        factory.close(dirty)

    # --- known assessment error sanitized after retirement (domain path) ---
    from app.api.middleware.covering_ingress import CoveringRequestContext
    from app.services.covering_request_budget import CoveringRequestBudget
    from contextlib import contextmanager

    clock = SimpleNamespace(value=0)

    class _Clock:
        def __call__(self) -> float:
            return float(clock.value)

    budget = CoveringRequestBudget(_Clock())
    context = CoveringRequestContext(budget, threading.Event())

    class _Connector:
        def __init__(self) -> None:
            self.events: list[tuple[str, CoveringRole]] = []
            self.session = SimpleNamespace(
                info={},
                get=lambda *a, **k: None,
                execute=lambda *a, **k: None,
            )

        def set_authenticated_credential(self, credential) -> None:
            self.credential = credential

        @contextmanager
        def session_scope(self, role):
            budget.work_remaining()
            self.events.append(("open", role))
            try:
                yield self.session
            finally:
                self.events.append(("retire", role))

        def run_target(self, **kw):
            window = domain.effective_covering_pull_window(
                body.window_start, body.window_end
            )
            return (
                domain._static_preflight_result(
                    subscription_id=kw["subscription_id"],
                    window=window,
                    preflight_code="synthetic",
                ),
                None,
            )

    connector = _Connector()
    now = ASSESSMENT_NOW
    body = CoveringRefreshRequest(
        subscription_ids=[sub_id],
        window_start=now,
        window_end=now + timedelta(days=1),
    )
    request = SimpleNamespace(state=SimpleNamespace(), session={}, headers={}, method="POST")
    targets = (domain.Target(owner_id, account_id, sub_id, None),)
    monkeypatch.setattr(
        domain, "authenticate", lambda request, db: domain.Identity(owner_id, None)
    )
    monkeypatch.setattr(domain, "_preflight", lambda db, identity, body: (targets, 9))

    def _boom(_db, **kwargs):
        raise ApiError(503, "secret-sql-detail-must-not-leak", "INTERNAL_FAKE")

    monkeypatch.setattr(domain, "_assemble_final_assessment", _boom)
    ports = domain.CoveringDomainPorts(lambda *a, **k: domain.TokenReady("x"), None, None)
    result = domain.run_bounded_domain(request, body, context, connector, ports)
    assert result.scheduling_readiness is not None
    assert (
        result.scheduling_readiness.assessment_error
        == "CALENDAR_REFRESH_ASSESSMENT_FAILED"
    )
    assert connector.events[-1] == ("retire", CoveringRole.ASSESSMENT)
    dumped = result.model_dump_json()
    assert "secret-sql-detail-must-not-leak" not in dumped
    assert "INTERNAL_FAKE" not in dumped

    # --- unknown terminal stops before assessment ---
    connector2 = _Connector()
    context2 = CoveringRequestContext(CoveringRequestBudget(_Clock()), threading.Event())

    def _unknown(**kw):
        raise CoveringRootOutcomeUnknown()

    connector2.run_target = _unknown  # type: ignore[method-assign]
    with pytest.raises(CoveringRootOutcomeUnknown):
        domain.run_bounded_domain(request, body, context2, connector2, ports)
    assert not any(role is CoveringRole.ASSESSMENT for _op, role in connector2.events)
    # PENDING (B3): full ingress HTTP 503 response body is not proven by this
    # domain-only case. Do not claim HTTP 503 sanitization from A09 alone.


# ---------------------------------------------------------------------------
# A10 — Public result integration
# ---------------------------------------------------------------------------


def test_a10_public_response_preserves_targets_and_assessment(monkeypatch) -> None:
    """A10: ordered target results preserved; correct assessment in public response."""
    factory = _factory()
    with open_setup_session(factory) as setup:
        primary = seed_owner(setup, username_prefix="a10", scheduling_revision=10)
        owner_id = primary.owner_id
        account = seed_account(setup, primary.user)
        cov_start, cov_end = coverage_span_for_settings(primary.settings)
        first = seed_subscription(
            setup, account, calendar_id="cal-a10-1", summary="A10 First"
        )
        second = seed_subscription(
            setup, account, calendar_id="cal-a10-2", summary="A10 Second"
        )
        mark_covering_fresh(
            first,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        mark_covering_fresh(
            second,
            window_start=cov_start,
            window_end=cov_end,
            success_at=freshness_age_just_inside_ceiling(),
        )
        setup.commit()
        first_id, second_id = first.id, second.id
        account_id = account.id
        revision = int(primary.settings.scheduling_revision)

    from contextlib import contextmanager

    from app.api.middleware.covering_ingress import CoveringRequestContext
    from app.services.covering_request_budget import CoveringRequestBudget

    class _Clock:
        def __call__(self) -> float:
            return 0.0

    budget = CoveringRequestBudget(_Clock())
    context = CoveringRequestContext(budget, threading.Event())

    class _Connector:
        def __init__(self) -> None:
            self.events: list[tuple[str, CoveringRole]] = []

        def set_authenticated_credential(self, credential) -> None:
            self.credential = credential

        @contextmanager
        def session_scope(self, role):
            budget.work_remaining()
            self.events.append(("open", role))
            # AUTH/TELEMETRY may use a lightweight session; ASSESSMENT must be real SQL
            # and must retire via close_known (never caller rollback/commit).
            if role is CoveringRole.ASSESSMENT:
                session = factory.open_assessment_session()
                try:
                    yield session
                finally:
                    factory.close_known(session)
                    self.events.append(("retire", role))
            else:
                session = SimpleNamespace(
                    info={},
                    get=lambda *a, **k: None,
                    execute=lambda *a, **k: SimpleNamespace(first=lambda: (False,)),
                )
                try:
                    yield session
                finally:
                    self.events.append(("retire", role))

        def run_target(self, **kw):
            window = domain.effective_covering_pull_window(
                body.window_start, body.window_end
            )
            from dataclasses import replace

            base = domain._static_preflight_result(
                subscription_id=kw["subscription_id"],
                window=window,
                preflight_code="unused",
            )
            return (
                replace(
                    base,
                    outcome="ok",
                    preflight_code=None,
                    provider_event_read_attempted=True,
                ),
                None,
            )

    connector = _Connector()
    now = ASSESSMENT_NOW
    # Request order deliberately opposite of plant order to prove preservation.
    body = CoveringRefreshRequest(
        subscription_ids=[second_id, first_id],
        window_start=now,
        window_end=now + timedelta(days=2),
        scheduling_horizon_label=HORIZON_LABEL,
    )
    request = SimpleNamespace(state=SimpleNamespace(), session={}, headers={}, method="POST")
    targets = (
        domain.Target(owner_id, account_id, second_id, None),
        domain.Target(owner_id, account_id, first_id, None),
    )
    monkeypatch.setattr(
        domain, "authenticate", lambda request, db: domain.Identity(owner_id, None)
    )
    monkeypatch.setattr(
        domain, "_preflight", lambda db, identity, body: (targets, revision)
    )

    # Real assessment assembly — not a stub. Clock fixed via wrap.
    real = domain._assemble_final_assessment

    def _assess(db, **kwargs):
        kwargs = dict(kwargs)
        kwargs["assessment_clock"] = lambda: ASSESSMENT_NOW
        return real(db, **kwargs)

    monkeypatch.setattr(domain, "_assemble_final_assessment", _assess)
    ports = domain.CoveringDomainPorts(
        lambda *a, **k: domain.TokenReady("synthetic-only"), None, None
    )
    response = domain.run_bounded_domain(request, body, context, connector, ports)

    assert [r.subscription_id for r in response.results] == [second_id, first_id]
    assert [r.status for r in response.results] == ["ok", "ok"]
    assert response.action_summary.import_attempted == 2
    assert response.coverage_action.all_requested_covering_ok is True
    assert response.scheduling_readiness is not None
    assert response.scheduling_readiness.scheduling_ready is True
    assert response.scheduling_readiness.scheduling_revision == revision
    assert response.scheduling_readiness.evaluated_at == ASSESSMENT_NOW
    assert response.scheduling_readiness.assessment_error is None
    assert response.scheduling_revision_at_start == revision
    assert response.scheduling_revision_at_end == revision
    dumped = response.model_dump_json()
    assert "Traceback" not in dumped
    assert "psycopg" not in dumped.lower()
    assert any(role is CoveringRole.ASSESSMENT for _op, role in connector.events)
