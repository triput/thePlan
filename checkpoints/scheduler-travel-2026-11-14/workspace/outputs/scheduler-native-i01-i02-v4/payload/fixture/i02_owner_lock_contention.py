"""I02 owner advisory-lock contention: mutator / observer / assessment barriers."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import CalendarSubscription
from app.services.covering_refresh import _assemble_final_assessment
from app.services.scheduling_revision import (
    increment_scheduling_revision,
    lock_owner_scheduling,
    owner_scheduling_lock_key,
)
from i01_i02_receipts import sanitize_cleanup_failure
from tests.support.assessment_sql_fixture import (
    ASSESSMENT_NOW,
    HORIZON_LABEL,
    coverage_span_for_settings,
    default_pull_window,
    freshness_age_just_inside_ceiling,
    mark_covering_fresh,
    seed_account,
    seed_owner,
    seed_subscription,
)

OWNER_LOCK_NAMESPACE = 1_886_415_951
OBSERVER_QUERY_ID = "i02_observer_advisory_xact_two_int_v1"
JOIN_LIMIT_SECONDS = 30.0
OBSERVER_POLL_SECONDS = 2.0
OBSERVER_SLEEP_SECONDS = 0.02

# Production predicate cause when success_gen != active_gen (calendar_freshness.py).
GENERATION_MISMATCH_CAUSE = "calendar_coverage_generation_mismatch"


@dataclass
class I02Barriers:
    holding_lock: Event = field(default_factory=Event)
    release_hold: Event = field(default_factory=Event)
    hold_confirmed: Event = field(default_factory=Event)
    assessment_pid_ready: Event = field(default_factory=Event)
    mutation_committed: Event = field(default_factory=Event)
    admit_mutation: Event = field(default_factory=Event)
    retire_mutator: Event = field(default_factory=Event)
    stop: Event = field(default_factory=Event)


@dataclass
class I02Evidence:
    holder_pid: int | None = None
    waiter_pid: int | None = None
    assessment_backend_pid: int | None = None
    database_oid: int | None = None
    owner_lock_key: int | None = None
    contention_class: str = "advisory_xact_lock"
    assessment_started_after_hold_confirmed: bool = False
    scheduling_revision: int | None = None
    requested_ok: bool | None = None
    scheduling_ready: bool | None = None
    mismatch_cause: str | None = None
    db_mismatch_observation: str | None = None
    mixed_revision_detected: bool | None = None
    coverage_active_generation: int | None = None
    coverage_success_generation: int | None = None
    mutator_result: dict[str, int] | None = None
    mutator_committed: bool = False
    lock_row_relationship: dict[str, Any] = field(default_factory=dict)
    observer_rows: list[dict[str, Any]] = field(default_factory=list)
    join_timeout: bool = False
    workers_alive_at_limit: list[str] = field(default_factory=list)
    workers_joined: dict[str, bool] = field(default_factory=dict)
    cleanup_failures: list[dict[str, str]] = field(default_factory=list)


def seed_i02_owner(setup: Session, *, username_prefix: str = "i02") -> dict[str, Any]:
    """Seed active=success=1 and known fresh state; revision R0=1."""
    owner = seed_owner(setup, username_prefix=username_prefix, scheduling_revision=1)
    account = seed_account(setup, owner.user)
    cov_start, cov_end = coverage_span_for_settings(owner.settings)
    sub = seed_subscription(
        setup,
        account,
        calendar_id=f"cal-{username_prefix}",
        summary=f"{username_prefix}-sub",
    )
    mark_covering_fresh(
        sub,
        window_start=cov_start,
        window_end=cov_end,
        success_at=freshness_age_just_inside_ceiling(),
        generation=1,
    )
    setup.flush()
    assert int(sub.coverage_active_generation) == 1
    assert int(sub.coverage_success_generation) == 1
    return {
        "owner_id": owner.owner_id,
        "subscription_id": sub.id,
        "lock_key": owner_scheduling_lock_key(owner.owner_id),
        "scheduling_revision": 1,
    }


def open_observer_connection(factory) -> Session:
    """Privileged monitoring session on the disposable DB (setup-class session)."""
    return factory.open_setup_session()


def capture_database_oid(observer: Session) -> int:
    row = observer.execute(text("SELECT oid FROM pg_database WHERE datname = current_database()")).one()
    return int(row[0])


def _normalize_blocking_pids(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        return [int(part) for part in value.strip("{}").split(",") if part]
    return [int(pid) for pid in value]


def observe_advisory_contention(
    observer: Session,
    *,
    database_oid: int,
    owner_lock_key: int,
    holder_pid: int,
    waiter_pid: int,
    deadline: float,
) -> dict[str, Any] | None:
    """Poll until exact holder + assessment-waiter evidence matches reconciled requirements."""
    query = text(
        """
        SELECT
          l.locktype, l.database, l.classid, l.objid, l.objsubid,
          l.pid, l.mode, l.granted,
          a.backend_type, a.wait_event_type, a.wait_event, a.state,
          pg_blocking_pids(l.pid) AS blocking_pids
        FROM pg_locks l
        JOIN pg_stat_activity a ON a.pid = l.pid
        WHERE l.locktype = 'advisory'
          AND l.database = :database_oid
          AND l.classid = :namespace
          AND l.objid = :owner_lock_key
          AND l.objsubid = 2
          AND l.pid = ANY(:pids)
        """
    )
    expected_pids = sorted({int(holder_pid), int(waiter_pid)})
    while time.monotonic() < deadline:
        rows = observer.execute(
            query,
            {
                "database_oid": database_oid,
                "namespace": OWNER_LOCK_NAMESPACE,
                "owner_lock_key": owner_lock_key,
                "pids": expected_pids,
            },
        ).mappings().all()
        granted = [dict(row) for row in rows if row["granted"] is True and int(row["pid"]) == int(holder_pid)]
        waiting = [dict(row) for row in rows if row["granted"] is False and int(row["pid"]) == int(waiter_pid)]
        if len(granted) == 1 and len(waiting) == 1:
            holder = granted[0]
            waiter = waiting[0]
            if int(holder["pid"]) == int(waiter["pid"]):
                time.sleep(OBSERVER_SLEEP_SECONDS)
                continue
            if (
                int(holder["database"]) != int(database_oid)
                or int(waiter["database"]) != int(database_oid)
                or int(holder["classid"]) != OWNER_LOCK_NAMESPACE
                or int(waiter["classid"]) != OWNER_LOCK_NAMESPACE
                or int(holder["objid"]) != int(owner_lock_key)
                or int(waiter["objid"]) != int(owner_lock_key)
                or int(holder["objsubid"]) != 2
                or int(waiter["objsubid"]) != 2
            ):
                time.sleep(OBSERVER_SLEEP_SECONDS)
                continue
            blocking = _normalize_blocking_pids(waiter.get("blocking_pids"))
            if int(holder["pid"]) not in set(blocking):
                time.sleep(OBSERVER_SLEEP_SECONDS)
                continue
            return {
                "holder_pid": int(holder["pid"]),
                "waiter_pid": int(waiter["pid"]),
                "rows": [dict(row) for row in rows],
                "blocking_pids": blocking,
                "lock_row_relationship": {
                    "database_oid": int(database_oid),
                    "namespace": OWNER_LOCK_NAMESPACE,
                    "owner_lock_key": int(owner_lock_key),
                    "objsubid": 2,
                    "holder_pid": int(holder["pid"]),
                    "waiter_pid": int(waiter["pid"]),
                    "holder_in_pg_blocking_pids_waiter": True,
                    "granted_holder_rows": 1,
                    "ungranted_waiter_rows": 1,
                },
            }
        time.sleep(OBSERVER_SLEEP_SECONDS)
    return None


def mutate_under_hold(mut: Session, *, owner_id: UUID, subscription_id: UUID) -> dict[str, int]:
    """Under held txn: bump revision to R1; change ONLY coverage_success_generation to 2."""
    settings = lock_owner_scheduling(mut, owner_id)
    revision = increment_scheduling_revision(mut, settings)
    sub = (
        mut.query(CalendarSubscription)
        .filter(CalendarSubscription.id == subscription_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    # Reconciled override: active stays 1; success becomes 2 → generation mismatch.
    if int(sub.coverage_active_generation or 0) != 1:
        raise RuntimeError("I02 seed active generation invariant broken")
    sub.coverage_success_generation = 2
    mut.flush()
    return {
        "scheduling_revision": int(revision),
        "coverage_active_generation": int(sub.coverage_active_generation),
        "coverage_success_generation": int(sub.coverage_success_generation),
    }


def expected_mismatch_from_production(sub: CalendarSubscription) -> str | None:
    """Derive failure cause from the same production predicate (do not invent)."""
    active_gen = int(sub.coverage_active_generation or 0)
    success_gen = sub.coverage_success_generation
    if success_gen is None or int(success_gen) != active_gen:
        return GENERATION_MISMATCH_CAUSE
    return None


def await_mutation_admission(
    barriers: I02Barriers,
    *,
    join_limit: float = JOIN_LIMIT_SECONDS,
) -> bool:
    """Wait for success admission or failure wake-up. Bare release_hold is not enough.

    Returns True only when admit_mutation wins. retire_mutator yields False without
    authorizing mutate+commit.
    """
    deadline = time.monotonic() + join_limit
    while time.monotonic() < deadline:
        if barriers.admit_mutation.is_set():
            return True
        if barriers.retire_mutator.is_set():
            return False
        time.sleep(0.01)
    raise TimeoutError("I02 mutation admission/retirement not signaled")


def assert_intended_subscription_diagnostic(
    *,
    intended_subscription_id: str,
    blocking_diagnostics: list[Any],
    db_mismatch_observation: str | None,
    required_cause: str = GENERATION_MISMATCH_CAUSE,
) -> str:
    """Require the actual final assessment diagnostic for the intended subscription.

    DB cause is a separate observation — never a silent substitute for PASS.
    """
    intended_causes = [
        getattr(diag, "cause", None)
        for diag in (blocking_diagnostics or [])
        if str(getattr(diag, "event_id", "")) == str(intended_subscription_id)
    ]
    if required_cause not in intended_causes:
        raise RuntimeError(
            "I02 missing/wrong intended-subscription final diagnostic "
            f"(observed={intended_causes!r}, db_observation={db_mismatch_observation!r})"
        )
    return required_cause


def record_observer_close_failure(
    evidence: I02Evidence,
    cleanup_exc: BaseException,
) -> None:
    """Append observer/cleanup failure evidence without inventing a primary."""
    evidence.cleanup_failures.append(sanitize_cleanup_failure(cleanup_exc))


def select_i02_primary(
    *,
    owner_primary: BaseException | None,
    mutator_errors: list[BaseException],
    assessment_errors: list[BaseException],
    cleanup_failures: list[dict[str, str]],
) -> BaseException | None:
    """Prefer recorded worker *operational* cause over owner generics; attach secondaries.

    ``mutator_errors`` / ``assessment_errors`` MUST carry only operational worker
    failures (try-body). Worker ``factory.close`` failures belong in
    ``cleanup_failures`` (cleanup secondary), never in those lists — otherwise a
    close-only fault can replace an independent owner primary.

    Promote operational worker cause over generic owner signaling (result/commit
    missing, etc.). Preserve independent owner primary when only cleanup fails.
    Cleanup-only failure still rejects PASS.
    """
    # Operational primary only — callers must not pass worker-close into these lists.
    worker: BaseException | None = None
    if mutator_errors:
        worker = mutator_errors[0]
    elif assessment_errors:
        worker = assessment_errors[0]

    if worker is not None:
        if cleanup_failures:
            setattr(worker, "fixture_cleanup_failures", list(cleanup_failures))
        if owner_primary is not None and owner_primary is not worker:
            setattr(
                worker,
                "fixture_owner_secondary",
                {
                    "kind": type(owner_primary).__name__,
                    "message": str(owner_primary)[:200],
                },
            )
        return worker

    # No operational worker cause: owner primary wins; cleanup attaches secondary.
    if owner_primary is not None:
        if cleanup_failures:
            setattr(owner_primary, "fixture_cleanup_failures", list(cleanup_failures))
        return owner_primary

    if cleanup_failures:
        primary = RuntimeError("I02 cleanup_failures prevent PASS")
        setattr(primary, "fixture_cleanup_failures", list(cleanup_failures))
        return primary
    return None


def close_preserving_primary(
    close_fn: Any,
    *,
    primary: BaseException | None,
    evidence: I02Evidence | None = None,
) -> BaseException | None:
    """Invoke close; preserve existing primary and attach close failure as secondary.

    Cleanup failure alone becomes a rejecting primary (cannot PASS).
    """
    try:
        close_fn()
        return primary
    except BaseException as exc:
        failure = sanitize_cleanup_failure(exc)
        if evidence is not None:
            evidence.cleanup_failures.append(failure)
        if primary is None:
            primary = RuntimeError("I02 cleanup/close failure prevents PASS")
            setattr(primary, "fixture_cleanup_failures", [failure])
            return primary
        failures = list(getattr(primary, "fixture_cleanup_failures", []) or [])
        failures.append(failure)
        setattr(primary, "fixture_cleanup_failures", failures)
        return primary


def run_verification_query_with_close(
    *,
    factory: Any,
    subscription_id: Any,
    subscription_model: Any,
) -> tuple[Any, BaseException | None]:
    """Post-assessment verify query under primary-preserving close discipline.

    Returns (subscription_or_None, primary_or_None). Dual-fault keeps query
    exception as primary with close failure attached; close-only still rejects.
    """
    verify = factory.open_setup_session()
    primary: BaseException | None = None
    sub = None
    try:
        sub = (
            verify.query(subscription_model)
            .filter(subscription_model.id == subscription_id)
            .populate_existing()
            .one()
        )
    except BaseException as exc:
        primary = exc
    finally:
        primary = close_preserving_primary(
            lambda: factory.close(verify),
            primary=primary,
        )
    return sub, primary


def run_i02_contention(
    *,
    factory,
    seed: dict[str, Any],
    join_limit: float = JOIN_LIMIT_SECONDS,
) -> tuple[Any, I02Evidence]:
    """Mutator holds lock; assessment waits; observer confirms; post-release mismatch."""
    barriers = I02Barriers()
    evidence = I02Evidence(owner_lock_key=int(seed["lock_key"]))
    mutator_errors: list[BaseException] = []
    assessment_errors: list[BaseException] = []
    final = None
    mutator_session = None
    assess_session = None
    observer = None
    holder_backend_pid: int | None = None
    mutator_result: dict[str, int] | None = None

    def mutator_main() -> None:
        nonlocal mutator_session, holder_backend_pid, mutator_result
        try:
            mut = factory.open_mutator_session()
            mutator_session = mut
            pid_row = mut.execute(text("SELECT pg_backend_pid()")).one()
            holder_backend_pid = int(pid_row[0])
            settings = lock_owner_scheduling(mut, seed["owner_id"])
            assert int(settings.scheduling_revision) == 1
            barriers.holding_lock.set()
            # Wait for either success admission (permits mutate+commit) or
            # failure wake-up (retire without commit). Bare release_hold alone
            # must not authorize commit.
            admitted = await_mutation_admission(barriers, join_limit=join_limit)
            if not admitted:
                # Failure wake-up: exit cleanly without mutate+commit.
                evidence.mutator_committed = False
                barriers.mutation_committed.set()
                return
            # Success admission only — proceed to mutate+commit.
            # Do not honor stop here — that race let mutator skip under normal success.
            mutator_result = mutate_under_hold(
                mut,
                owner_id=seed["owner_id"],
                subscription_id=seed["subscription_id"],
            )
            mut.commit()
            evidence.mutator_result = dict(mutator_result)
            evidence.mutator_committed = True
            barriers.mutation_committed.set()
        except BaseException as exc:
            # Operational worker primary only — close failures go to cleanup_failures.
            mutator_errors.append(exc)
            raise
        finally:
            barriers.release_hold.set()
            barriers.mutation_committed.set()
            if mutator_session is not None:
                try:
                    factory.close(mutator_session)
                except BaseException as exc:
                    # Cleanup secondary — must not enter mutator_errors (would
                    # wrongly displace an independent owner primary in select).
                    evidence.cleanup_failures.append(sanitize_cleanup_failure(exc))
                mutator_session = None

    def assessment_main() -> None:
        nonlocal assess_session, final
        try:
            if not barriers.hold_confirmed.wait(join_limit):
                raise TimeoutError("I02 hold not confirmed before assessment")
            evidence.assessment_started_after_hold_confirmed = True
            assess = factory.open_assessment_session()
            assess_session = assess
            # Capture backend PID before owner-lock wait inside assessment.
            pid_row = assess.execute(text("SELECT pg_backend_pid()")).one()
            evidence.assessment_backend_pid = int(pid_row[0])
            barriers.assessment_pid_ready.set()
            window = default_pull_window()
            final = _assemble_final_assessment(
                assess,
                owner_id=seed["owner_id"],
                subscription_ids=[seed["subscription_id"]],
                window=window,
                horizon_label=HORIZON_LABEL,
                assessment_clock=lambda: ASSESSMENT_NOW,
            )
        except BaseException as exc:
            # Operational worker primary only — close failures go to cleanup_failures.
            assessment_errors.append(exc)
            raise
        finally:
            if assess_session is not None:
                try:
                    factory.close_known(assess_session)
                except BaseException as exc:
                    # Cleanup secondary — must not enter assessment_errors.
                    evidence.cleanup_failures.append(sanitize_cleanup_failure(exc))
                assess_session = None

    mutator = Thread(target=mutator_main, name="i02-mutator", daemon=False)
    assessment = Thread(target=assessment_main, name="i02-assessment", daemon=False)
    primary: BaseException | None = None
    try:
        observer = open_observer_connection(factory)
        evidence.database_oid = capture_database_oid(observer)
        mutator.start()
        if not barriers.holding_lock.wait(join_limit):
            raise TimeoutError("I02 mutator did not acquire lock")
        # Confirm holder via observer before starting assessment.
        holder_only = observer.execute(
            text(
                """
                SELECT l.pid, l.granted, l.objsubid, l.database, l.classid, l.objid
                FROM pg_locks l
                WHERE l.locktype = 'advisory'
                  AND l.database = :database_oid
                  AND l.classid = :namespace
                  AND l.objid = :owner_lock_key
                  AND l.objsubid = 2
                  AND l.granted IS TRUE
                  AND l.pid = :holder_pid
                """
            ),
            {
                "database_oid": evidence.database_oid,
                "namespace": OWNER_LOCK_NAMESPACE,
                "owner_lock_key": evidence.owner_lock_key,
                "holder_pid": holder_backend_pid,
            },
        ).mappings().all()
        if len(holder_only) != 1 or holder_backend_pid is None:
            raise RuntimeError("I02 holder acquisition not observed")
        evidence.holder_pid = int(holder_only[0]["pid"])
        barriers.hold_confirmed.set()
        assessment.start()
        if not barriers.assessment_pid_ready.wait(join_limit):
            raise TimeoutError("I02 assessment backend PID not captured before lock wait")
        if evidence.assessment_backend_pid is None:
            raise RuntimeError("I02 assessment backend PID missing")
        contention = observe_advisory_contention(
            observer,
            database_oid=evidence.database_oid,
            owner_lock_key=evidence.owner_lock_key or 0,
            holder_pid=evidence.holder_pid,
            waiter_pid=evidence.assessment_backend_pid,
            deadline=time.monotonic() + OBSERVER_POLL_SECONDS,
        )
        if contention is None:
            raise RuntimeError("I02 observer failed to capture holder/waiter/blocking evidence")
        evidence.holder_pid = contention["holder_pid"]
        evidence.waiter_pid = contention["waiter_pid"]
        evidence.observer_rows = contention["rows"]
        evidence.lock_row_relationship = contention["lock_row_relationship"]
        # Success admission after contention observed; only this permits commit.
        barriers.admit_mutation.set()
        barriers.release_hold.set()
        if not barriers.mutation_committed.wait(join_limit):
            raise TimeoutError("I02 mutator did not commit after admit_mutation")
        if not evidence.mutator_committed or evidence.mutator_result is None:
            raise RuntimeError("I02 mutator result/commit missing")
    except BaseException as exc:
        primary = exc
    finally:
        # Teardown / failure wake-up: retire without authorizing mutate+commit.
        # Do not set admit_mutation here.
        barriers.retire_mutator.set()
        barriers.release_hold.set()
        barriers.hold_confirmed.set()
        barriers.holding_lock.set()
        barriers.assessment_pid_ready.set()
        barriers.mutation_committed.set()
        barriers.stop.set()
        for worker in (mutator, assessment):
            if worker.ident is not None or worker.is_alive():
                worker.join(timeout=join_limit)
            alive = worker.is_alive()
            evidence.workers_joined[worker.name] = not alive
            if alive:
                evidence.join_timeout = True
                evidence.workers_alive_at_limit.append(worker.name)
        if evidence.join_timeout:
            evidence.cleanup_failures.append({"kind": "SuiteStopWorkersAlive"})
            if primary is None:
                primary = RuntimeError("I02 workers alive at join limit — suite STOP")
        if observer is not None:
            try:
                factory.close(observer)
            except BaseException as exc:
                # Record only — do not assign generic primary here. Worker failures
                # recorded in mutator_errors/assessment_errors must win via select.
                record_observer_close_failure(evidence, exc)
            observer = None

    primary = select_i02_primary(
        owner_primary=primary,
        mutator_errors=mutator_errors,
        assessment_errors=assessment_errors,
        cleanup_failures=list(evidence.cleanup_failures),
    )

    if primary is not None:
        raise primary

    if final is None:
        raise RuntimeError("I02 final assessment missing")
    if evidence.mutator_result is None or not evidence.mutator_committed:
        raise RuntimeError("I02 mutator commit evidence missing")

    # Derive revision / generations / mismatch / coherence from real final + DB.
    sub, verify_primary = run_verification_query_with_close(
        factory=factory,
        subscription_id=seed["subscription_id"],
        subscription_model=CalendarSubscription,
    )
    if verify_primary is not None:
        raise verify_primary
    if sub is None:
        raise RuntimeError("I02 verification query returned no subscription")
    db_active = int(sub.coverage_active_generation or 0)
    db_success = int(sub.coverage_success_generation or 0)
    db_cause = expected_mismatch_from_production(sub)

    evidence.scheduling_revision = int(final.readiness.scheduling_revision)
    evidence.requested_ok = bool(final.requested.ok)
    evidence.scheduling_ready = bool(final.readiness.scheduling_ready)
    evidence.coverage_active_generation = db_active
    evidence.coverage_success_generation = db_success
    evidence.db_mismatch_observation = db_cause
    intended = str(seed["subscription_id"])
    evidence.mismatch_cause = assert_intended_subscription_diagnostic(
        intended_subscription_id=intended,
        blocking_diagnostics=list(final.requested.blocking_diagnostics or []),
        db_mismatch_observation=db_cause,
        required_cause=GENERATION_MISMATCH_CAUSE,
    )
    # FinalCoveringAssessment has no mixed_revision_detected field — derive
    # coherence from one observed revision matching mutator+DB evidence.
    mut_rev = int(evidence.mutator_result["scheduling_revision"])
    coherent = (
        evidence.scheduling_revision == mut_rev
        and db_active == int(evidence.mutator_result["coverage_active_generation"])
        and db_success == int(evidence.mutator_result["coverage_success_generation"])
        and evidence.requested_ok is False
        and evidence.scheduling_ready is False
        and evidence.mismatch_cause == GENERATION_MISMATCH_CAUSE
    )
    evidence.mixed_revision_detected = not coherent
    if not coherent:
        raise RuntimeError("I02 post-release assessment/DB coherence failed")
    return final, evidence
