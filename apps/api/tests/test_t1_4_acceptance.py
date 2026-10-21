"""T1-4a acceptance — persisted series policy + resolve (Dex contract §9).

Real concurrent tests open separate ``SessionLocal`` connections and fail unless
``pg_locks`` shows a new ungranted ``pg_advisory_xact_lock`` waiter while resolve
is still uncommitted. Simulated tests use the single-session ``db_session``
savepoint and are named ``test_simulated_*``.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    FreeBusyOccurrenceBaseline,
    FreeBusySeriesPolicy,
    FreeBusySeriesPolicyDecision,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.busy_map import busy_from_sources, load_immovable_busy_sources
from app.scheduler.collect import collect_inputs
from app.scheduler.free_busy import (
    BusyInputTrustError,
    evaluate_busy_input_trust,
    events_for_busy_merge,
    require_busy_input_trust,
)
from app.services.free_busy_resolver_allowlist import parse_resolver_allowlist_file
from app.services.free_busy_series_policy import (
    _FREE_BUSY_IDENTITY_NAMESPACE,
    ConflictAcknowledgment,
    ResolveSeriesPolicyRequest,
    apply_post_transparency_policy_effects,
    authoritative_pending_events,
    compute_conflict_revision,
    load_series_policies_for_owner,
    policy_diagnostic_enrichment,
    resolve_series_policy,
)
from app.services.google_calendar import _upsert_external_event
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
H0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
H1 = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    if os.environ.get("T1A_REQUIRE_DISPOSABLE_DSN") != "1":
        pytest.skip("T1-4a acceptance requires T1A_REQUIRE_DISPOSABLE_DSN=1")
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _owner(db: Session) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:8]
    user = User(
        email=f"t1-4a-{token}@example.test",
        username=f"t1_4a_{token}",
        display_name="T1-4a",
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        session_epoch=1,
    )
    db.add(user)
    db.flush()
    settings = UserSettings(
        owner_id=user.id,
        timezone="UTC",
        workday_minutes=480,
        workday_start_local=dt_time(8, 0),
        workweek_days=5,
        inter_block_buffer_minutes=15,
        upcoming_horizon_days=7,
        default_schedule_style=ScheduleStyle.standalone,
        scheduling_revision=0,
    )
    db.add(settings)
    db.flush()
    return user, settings


def _account(db: Session, owner: User) -> CalendarAccount:
    acct = CalendarAccount(
        owner_id=owner.id,
        provider=CalendarProvider.google,
        account_email=f"{uuid.uuid4().hex[:6]}@example.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(acct)
    db.flush()
    return acct


def _sub(db: Session, account: CalendarAccount, *, cal_id: str = "cal-primary") -> CalendarSubscription:
    sub = CalendarSubscription(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=cal_id,
        summary="Primary",
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
        provider_timezone="UTC",
    )
    db.add(sub)
    db.flush()
    return sub


def _event(
    db: Session,
    *,
    owner: User,
    account: CalendarAccount,
    sub: CalendarSubscription,
    external_id: str,
    series_id: str,
    transparency: str = "opaque",
    provenance: str = "provider_explicit",
    pending: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        provider=CalendarProvider.google,
        external_event_id=external_id,
        calendar_id=sub.external_calendar_id,
        provider_series_id=series_id,
        title=f"evt-{external_id}",
        start_time=start or H0,
        end_time=end or H1,
        transparency=transparency,
        free_busy_provenance=provenance,
        free_busy_pending_exception=pending,
    )
    db.add(row)
    db.flush()
    return row


def _allowlist_file(*user_ids: UUID) -> str:
    fd, path = tempfile.mkstemp(suffix=".allowlist")
    os.close(fd)
    lines = [f"{uid}\n" for uid in user_ids]
    Path(path).write_text("".join(lines), encoding="utf-8")
    return path


def _identity_key(owner: User, sub: CalendarSubscription, series: str) -> tuple[str, str, str, str]:
    return (str(owner.id), "google", sub.external_calendar_id, series)


def _revision(
    owner: User,
    sub: CalendarSubscription,
    series: str,
    row: ExternalCalendarEvent,
    *,
    latch: int = 0,
) -> str:
    key = _identity_key(owner, sub, series)
    return compute_conflict_revision(
        identity=key,
        external_event_id=row.external_event_id,
        transparency=row.transparency,
        provenance=row.free_busy_provenance,
        pending=True,
        latch_generation=latch,
    )


def test_allowlist_fail_closed_and_reread(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    path_a = _allowlist_file(owner.id)
    path_b = _allowlist_file(uuid.uuid4())
    try:
        monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path_a)
        get_settings.cache_clear()
        assert parse_resolver_allowlist_file(path_a)

        acct = _account(db_session, owner)
        sub = _sub(db_session, acct)
        row = _event(
            db_session,
            owner=owner,
            account=acct,
            sub=sub,
            external_id="e-allow",
            series_id="series-allow",
            pending=True,
        )
        body = ResolveSeriesPolicyRequest(
            external_event_id=row.external_event_id,
            conflict_acknowledgments=(
                ConflictAcknowledgment(
                    external_event_id=row.external_event_id,
                    conflict_revision=_revision(owner, sub, "series-allow", row),
                ),
            ),
            reason="ack",
        )
        resolve_series_policy(
            db_session,
            user=owner,
            body=body,
            allowlist_path=get_settings().free_busy_resolver_allowlist_path,
        )

        monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path_b)
        get_settings.cache_clear()
        row.free_busy_pending_exception = True
        db_session.flush()
        with pytest.raises(ApiError) as exc:
            resolve_series_policy(
                db_session,
                user=owner,
                body=body,
                allowlist_path=get_settings().free_busy_resolver_allowlist_path,
            )
        assert exc.value.content["code"] == "FREE_BUSY_RESOLVE_FORBIDDEN"
    finally:
        Path(path_a).unlink(missing_ok=True)
        Path(path_b).unlink(missing_ok=True)
        get_settings.cache_clear()


def test_stale_conflict_revision_409(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    path = _allowlist_file(owner.id)
    monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path)
    get_settings.cache_clear()
    try:
        acct = _account(db_session, owner)
        sub = _sub(db_session, acct)
        row = _event(
            db_session,
            owner=owner,
            account=acct,
            sub=sub,
            external_id="e-stale",
            series_id="series-stale",
            pending=True,
        )
        stale = "0" * 32
        body = ResolveSeriesPolicyRequest(
            external_event_id=row.external_event_id,
            conflict_acknowledgments=(
                ConflictAcknowledgment(row.external_event_id, stale),
            ),
            reason="stale test",
        )
        with pytest.raises(ApiError) as exc:
            resolve_series_policy(db_session, user=owner, body=body, allowlist_path=path)
        assert exc.value.content["code"] == "FREE_BUSY_CONFLICT_STALE"
    finally:
        Path(path).unlink(missing_ok=True)
        get_settings.cache_clear()


def test_resolve_clears_pending_and_collect_trust_ok(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    path = _allowlist_file(owner.id)
    monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path)
    get_settings.cache_clear()
    try:
        acct = _account(db_session, owner)
        sub = _sub(db_session, acct)
        series = "series-resolve"
        row = _event(
            db_session,
            owner=owner,
            account=acct,
            sub=sub,
            external_id="e-resolve",
            series_id=series,
            transparency="transparent",
            pending=True,
        )
        rev = _revision(owner, sub, series, row)
        resolve_series_policy(
            db_session,
            user=owner,
            body=ResolveSeriesPolicyRequest(
                external_event_id=row.external_event_id,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(row.external_event_id, rev),
                ),
                reason="operator accepts transparent",
            ),
            allowlist_path=path,
        )
        db_session.refresh(row)
        assert row.free_busy_pending_exception is False
        policy = (
            db_session.query(FreeBusySeriesPolicy)
            .filter(FreeBusySeriesPolicy.owner_id == owner.id)
            .one()
        )
        assert policy.mapping == "free"
        assert (
            db_session.query(FreeBusySeriesPolicyDecision)
            .filter(FreeBusySeriesPolicyDecision.policy_id == policy.id)
            .count()
            == 1
        )

        inputs = collect_inputs(db_session, owner.id, H0)
        assert inputs.busy_input_trust is not None
        assert inputs.busy_input_trust.ok is True
        merged = events_for_busy_merge(
            [row], policy_map=load_series_policies_for_owner(db_session, owner.id)
        )
        assert merged == []
    finally:
        Path(path).unlink(missing_ok=True)
        get_settings.cache_clear()


def test_partial_ack_retains_latch_and_sibling_pending(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    path = _allowlist_file(owner.id)
    monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path)
    get_settings.cache_clear()
    try:
        acct = _account(db_session, owner)
        sub = _sub(db_session, acct)
        series = "series-partial"
        a = _event(
            db_session,
            owner=owner,
            account=acct,
            sub=sub,
            external_id="sib-a",
            series_id=series,
            pending=True,
            start=H0,
            end=H0 + timedelta(hours=1),
        )
        b = _event(
            db_session,
            owner=owner,
            account=acct,
            sub=sub,
            external_id="sib-b",
            series_id=series,
            pending=True,
            start=H0 + timedelta(days=30),
            end=H0 + timedelta(days=30, hours=1),
        )
        policy = FreeBusySeriesPolicy(
            owner_id=owner.id,
            provider=CalendarProvider.google,
            calendar_id=sub.external_calendar_id,
            provider_series_id=series,
            mapping="free",
            conflict_pending_latched=True,
            latch_generation=2,
        )
        db_session.add(policy)
        db_session.flush()

        resolve_series_policy(
            db_session,
            user=owner,
            body=ResolveSeriesPolicyRequest(
                external_event_id=a.external_event_id,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(
                        a.external_event_id,
                        _revision(owner, sub, series, a, latch=2),
                    ),
                ),
                reason="only A",
            ),
            allowlist_path=path,
        )
        db_session.refresh(a)
        db_session.refresh(b)
        db_session.refresh(policy)
        assert a.free_busy_pending_exception is False
        assert b.free_busy_pending_exception is True
        assert policy.conflict_pending_latched is True
    finally:
        Path(path).unlink(missing_ok=True)
        get_settings.cache_clear()


def test_google_ingest_future_baseline_then_latch(
    db_session: Session,
) -> None:
    owner, _ = _owner(db_session)
    acct = _account(db_session, owner)
    sub = _sub(db_session, acct)
    series = "series-future"
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.google,
        calendar_id=sub.external_calendar_id,
        provider_series_id=series,
        mapping="free",
        acknowledged_calendar_id=sub.external_calendar_id,
        acknowledged_series_id=series,
    )
    db_session.add(policy)
    db_session.flush()

    ext_id = f"new-inst-{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    ok = _upsert_external_event(
        db_session,
        account=acct,
        subscription=sub,
        event={
            "id": ext_id,
            "summary": "New",
            "start": {"dateTime": "2026-11-01T10:00:00Z"},
            "end": {"dateTime": "2026-11-01T11:00:00Z"},
            "transparency": "transparent",
            "recurringEventId": series,
        },
        now=now,
        sync_run_id="sync-1",
    )
    assert ok
    row = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == ext_id)
        .one()
    )
    baseline = (
        db_session.query(FreeBusyOccurrenceBaseline)
        .filter(FreeBusyOccurrenceBaseline.external_event_id == ext_id)
        .one()
    )
    assert baseline.source == "automatic_first_trustworthy_observation"
    assert row.free_busy_pending_exception is False
    assert (
        db_session.query(FreeBusySeriesPolicyDecision)
        .filter(FreeBusySeriesPolicyDecision.decided_by_user_id.isnot(None))
        .count()
        == 0
    )

    ok2 = _upsert_external_event(
        db_session,
        account=acct,
        subscription=sub,
        event={
            "id": ext_id,
            "summary": "New",
            "start": {"dateTime": "2026-11-01T10:00:00Z"},
            "end": {"dateTime": "2026-11-01T11:00:00Z"},
            "transparency": "opaque",
            "recurringEventId": series,
        },
        now=now,
        sync_run_id="sync-2",
    )
    assert ok2 is True
    db_session.refresh(row)
    db_session.refresh(policy)
    assert row.transparency == "opaque"
    assert row.free_busy_pending_exception is True
    assert policy.conflict_pending_latched is True


def test_loss_of_trust_reopens_until_resolve(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    path = _allowlist_file(owner.id)
    acct = _account(db_session, owner)
    sub = _sub(db_session, acct)
    series = "series-t0b"
    row = _event(
        db_session,
        owner=owner,
        account=acct,
        sub=sub,
        external_id="t0b-1",
        series_id=series,
        transparency="transparent",
        pending=False,
    )
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.google,
        calendar_id=sub.external_calendar_id,
        provider_series_id=series,
        mapping="free",
        acknowledged_calendar_id=sub.external_calendar_id,
        acknowledged_series_id=series,
    )
    db_session.add(policy)
    db_session.flush()
    apply_post_transparency_policy_effects(
        db_session,
        row,
        identity_keys=[_identity_key(owner, sub, series)],
        old_calendar_id=sub.external_calendar_id,
        old_series_id=series,
    )
    db_session.flush()

    row.transparency = None
    row.free_busy_provenance = "unknown_projection"
    apply_post_transparency_policy_effects(
        db_session,
        row,
        identity_keys=[_identity_key(owner, sub, series)],
        old_calendar_id=sub.external_calendar_id,
        old_series_id=series,
    )
    db_session.flush()
    db_session.refresh(row)
    db_session.refresh(policy)
    assert row.free_busy_pending_exception is True
    assert policy.conflict_pending_latched is True
    pmap = load_series_policies_for_owner(db_session, owner.id)
    trust = evaluate_busy_input_trust([row], horizon_start=H0, horizon_end=H1, policy_map=pmap)
    assert trust.ok is False

    row.transparency = "transparent"
    row.free_busy_provenance = "provider_explicit"
    db_session.flush()
    apply_post_transparency_policy_effects(
        db_session,
        row,
        identity_keys=[_identity_key(owner, sub, series)],
        old_calendar_id=sub.external_calendar_id,
        old_series_id=series,
    )
    db_session.flush()
    db_session.refresh(row)
    assert row.free_busy_pending_exception is True
    assert row.free_busy_provenance == "provider_explicit"

    rev = _revision(owner, sub, series, row, latch=int(policy.latch_generation))
    resolve_series_policy(
        db_session,
        user=owner,
        body=ResolveSeriesPolicyRequest(
            external_event_id=row.external_event_id,
            conflict_acknowledgments=(ConflictAcknowledgment(row.external_event_id, rev),),
            reason="restored trust ack",
        ),
        allowlist_path=path,
    )
    db_session.refresh(row)
    trust2 = evaluate_busy_input_trust(
        [row],
        horizon_start=H0,
        horizon_end=H1,
        policy_map=load_series_policies_for_owner(db_session, owner.id),
    )
    assert trust2.ok is True
    Path(path).unlink(missing_ok=True)


def test_http_resolve_route(db_session: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    me = client.get("/api/v1/auth/me").json()
    user = db_session.get(User, UUID(me["id"]))
    assert user is not None
    path = _allowlist_file(user.id)
    monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path)
    get_settings.cache_clear()
    try:
        acct = _account(db_session, user)
        sub = _sub(db_session, acct)
        series = "series-http"
        row = _event(
            db_session,
            owner=user,
            account=acct,
            sub=sub,
            external_id="http-1",
            series_id=series,
            transparency="transparent",
            pending=True,
        )
        rev = _revision(user, sub, series, row)
        resp = client.post(
            "/api/v1/calendar/resolve-series-policy",
            json={
                "external_event_id": row.external_event_id,
                "conflict_acknowledgments": [
                    {"external_event_id": row.external_event_id, "conflict_revision": rev}
                ],
                "reason": "via HTTP",
            },
        )
        assert resp.status_code == 200, resp.text
        db_session.refresh(row)
        assert row.free_busy_pending_exception is False
    finally:
        Path(path).unlink(missing_ok=True)
        get_settings.cache_clear()


def test_diagnostics_enrichment_fields(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    acct = _account(db_session, owner)
    sub = _sub(db_session, acct)
    series = "series-diag"
    row = _event(
        db_session,
        owner=owner,
        account=acct,
        sub=sub,
        external_id="diag-1",
        series_id=series,
        pending=True,
    )
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.google,
        calendar_id=sub.external_calendar_id,
        provider_series_id=series,
        mapping="free",
        conflict_pending_latched=True,
    )
    db_session.add(policy)
    db_session.flush()
    pmap = load_series_policies_for_owner(db_session, owner.id)
    enrich = policy_diagnostic_enrichment(db_session, row, policy_map=pmap)
    assert enrich is not None
    assert enrich["conflict_revision"]
    assert enrich["current_provider_evidence"]["transparency"] == "opaque"
    assert "retained_manual_choice" in enrich


def _gdt(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _google_event(
    ext_id: str,
    series: str,
    transparency: str,
    start: datetime,
    end: datetime,
) -> dict[str, object]:
    return {
        "id": ext_id,
        "summary": ext_id,
        "start": {"dateTime": _gdt(start)},
        "end": {"dateTime": _gdt(end)},
        "transparency": transparency,
        "recurringEventId": series,
    }


def _policies(db: Session, owner_id: UUID) -> list[FreeBusySeriesPolicy]:
    return (
        db.query(FreeBusySeriesPolicy)
        .filter(FreeBusySeriesPolicy.owner_id == owner_id)
        .all()
    )


def _decision_count(db: Session, owner_id: UUID) -> int:
    return (
        db.query(FreeBusySeriesPolicyDecision)
        .join(FreeBusySeriesPolicy)
        .filter(FreeBusySeriesPolicy.owner_id == owner_id)
        .count()
    )


def _baseline_count(db: Session, owner_id: UUID) -> int:
    return (
        db.query(FreeBusyOccurrenceBaseline)
        .filter(FreeBusyOccurrenceBaseline.owner_id == owner_id)
        .count()
    )


def _event_by_external_id(db: Session, external_id: str) -> ExternalCalendarEvent:
    return (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == external_id)
        .one()
    )


def _advisory_lock_rows() -> list[tuple[bool, str | None]]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT l.granted, a.query
                FROM pg_locks AS l
                JOIN pg_stat_activity AS a ON a.pid = l.pid
                WHERE l.locktype = 'advisory'
                  AND l.classid = :ns
                """
            ),
            {"ns": _FREE_BUSY_IDENTITY_NAMESPACE},
        ).all()
        return [(bool(granted), query) for granted, query in rows]
    finally:
        db.close()


def _dump_advisory_locks() -> list[tuple]:
    db = SessionLocal()
    try:
        return list(
            db.execute(
                text(
                    """
                    SELECT classid, objid, granted, mode
                    FROM pg_locks
                    WHERE locktype = 'advisory'
                    """
                )
            ).all()
        )
    finally:
        db.close()


def _assert_new_advisory_waiter(prior_ungranted: int) -> None:
    """Fail unless a new session is blocked inside pg_advisory_xact_lock."""
    deadline = time.monotonic() + 8
    last: list[tuple[bool, str | None]] = []
    while time.monotonic() < deadline:
        last = _advisory_lock_rows()
        ungranted = [(granted, query) for granted, query in last if not granted]
        granted = [row for row in last if row[0]]
        if len(ungranted) > prior_ungranted and granted:
            queries = [query or "" for _granted, query in ungranted]
            if any("pg_advisory_xact_lock" in query for query in queries):
                return
            if queries and all(query == "" for query in queries):
                # Same-role query text hidden; ungranted advisory row is still a waiter.
                return
        time.sleep(0.05)
    raise AssertionError(
        "expected a new ungranted pg_advisory_xact_lock waiter while resolve "
        f"held the identity lock; prior_ungranted={prior_ungranted} rows={last!r} "
        f"all_advisory={_dump_advisory_locks()!r}"
    )


def _seed_committed_series(
    *,
    series: str,
    rows: list[dict],
    policy_kwargs: dict | None = None,
    latch_for_revision: int = 0,
) -> dict:
    db = SessionLocal()
    try:
        owner, _settings = _owner(db)
        account = _account(db, owner)
        sub = _sub(db, account, cal_id=f"cal-{uuid.uuid4().hex[:8]}")
        revisions: dict[str, str] = {}
        external_ids: list[str] = []
        for spec in rows:
            row = _event(
                db,
                owner=owner,
                account=account,
                sub=sub,
                series_id=series,
                **spec,
            )
            external_ids.append(row.external_event_id)
            revisions[row.external_event_id] = _revision(
                owner, sub, series, row, latch=latch_for_revision
            )
        if policy_kwargs is not None:
            kwargs = dict(policy_kwargs)
            kwargs.setdefault("acknowledged_calendar_id", sub.external_calendar_id)
            kwargs.setdefault("acknowledged_series_id", series)
            db.add(
                FreeBusySeriesPolicy(
                    owner_id=owner.id,
                    provider=CalendarProvider.google,
                    calendar_id=sub.external_calendar_id,
                    provider_series_id=series,
                    **kwargs,
                )
            )
        db.commit()
        return {
            "owner_id": owner.id,
            "account_id": account.id,
            "sub_id": sub.id,
            "calendar_id": sub.external_calendar_id,
            "series": series,
            "external_ids": external_ids,
            "revisions": revisions,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_resolve_holds_ingest_waits(
    *,
    seeded: dict,
    allowlist_path: str,
    resolve_external_id: str,
    ingest_event: dict,
    during_hold: Callable[[], None] | None = None,
) -> None:
    """Resolve keeps its transaction (and identity lock) open until ingest is waiting.

    Real concurrent sessions. Not a simulated sequential call pair.
    """
    held = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []
    prior_ungranted = sum(1 for granted, _query in _advisory_lock_rows() if not granted)

    def _resolve() -> None:
        db = SessionLocal()
        try:
            user = db.get(User, seeded["owner_id"])
            assert user is not None
            resolve_series_policy(
                db,
                user=user,
                body=ResolveSeriesPolicyRequest(
                    external_event_id=resolve_external_id,
                    conflict_acknowledgments=(
                        ConflictAcknowledgment(
                            resolve_external_id,
                            seeded["revisions"][resolve_external_id],
                        ),
                    ),
                    reason="concurrent resolve holds identity lock",
                ),
                allowlist_path=allowlist_path,
            )
            held.set()
            if not release.wait(timeout=20):
                raise TimeoutError("resolve identity-lock hold was not released")
            db.commit()
        except BaseException as exc:
            errors.append(exc)
            db.rollback()
            held.set()
        finally:
            db.close()

    def _ingest() -> None:
        db = SessionLocal()
        try:
            if not held.wait(timeout=20):
                raise TimeoutError("resolve never held the identity lock")
            account = db.get(CalendarAccount, seeded["account_id"])
            sub = db.get(CalendarSubscription, seeded["sub_id"])
            assert account is not None and sub is not None
            ok = _upsert_external_event(
                db,
                account=account,
                subscription=sub,
                event=ingest_event,
                now=datetime.now(UTC),
                sync_run_id="t1-4a-race",
            )
            if not ok:
                raise AssertionError("ingest upsert returned false")
            db.commit()
        except BaseException as exc:
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    t_resolve = threading.Thread(target=_resolve, name="t1-4a-resolve")
    t_ingest = threading.Thread(target=_ingest, name="t1-4a-ingest")
    t_ingest.start()
    t_resolve.start()
    overlap_error: BaseException | None = None
    try:
        if not held.wait(timeout=25):
            overlap_error = AssertionError(
                f"resolve did not hold the identity lock; thread errors={errors!r}"
            )
        else:
            try:
                _assert_new_advisory_waiter(prior_ungranted)
                if during_hold is not None:
                    during_hold()
            except BaseException as exc:
                overlap_error = exc
    finally:
        release.set()
    t_resolve.join(timeout=30)
    t_ingest.join(timeout=30)
    if t_resolve.is_alive() or t_ingest.is_alive():
        raise AssertionError(f"race threads still alive; errors={errors!r}")
    if overlap_error is not None:
        raise overlap_error
    if errors:
        raise AssertionError(errors)


def test_real_concurrent_sibling_race() -> None:
    """Two siblings, one identity. Resolve holds the lock; ingest on B waits.

    Real concurrent sessions. Coherent resolve-first outcome: A cleared, B stays
    pending, latch retained, ingest's transparency write lands only after the lock.
    """
    series = f"race-sib-{uuid.uuid4().hex[:12]}"
    ext_a = f"sib-a-{uuid.uuid4().hex}"
    ext_b = f"sib-b-{uuid.uuid4().hex}"
    seeded = _seed_committed_series(
        series=series,
        latch_for_revision=1,
        policy_kwargs={
            "mapping": "free",
            "conflict_pending_latched": True,
            "latch_generation": 1,
            "acknowledged_series_id": series,
        },
        rows=[
            {
                "external_id": ext_a,
                "transparency": "opaque",
                "pending": True,
                "start": H0,
                "end": H0 + timedelta(hours=1),
            },
            {
                "external_id": ext_b,
                "transparency": "opaque",
                "pending": True,
                "start": H0 + timedelta(hours=2),
                "end": H0 + timedelta(hours=3),
            },
        ],
    )
    path = _allowlist_file(seeded["owner_id"])

    def _during_hold() -> None:
        probe = SessionLocal()
        try:
            # Resolve has flushed but not committed; ingest has not committed.
            assert _event_by_external_id(probe, ext_a).free_busy_pending_exception is True
            sibling = _event_by_external_id(probe, ext_b)
            assert sibling.transparency == "opaque"
            assert sibling.free_busy_pending_exception is True
            assert _decision_count(probe, seeded["owner_id"]) == 0
        finally:
            probe.close()

    try:
        _run_resolve_holds_ingest_waits(
            seeded=seeded,
            allowlist_path=path,
            resolve_external_id=ext_a,
            ingest_event=_google_event(
                ext_b,
                series,
                "transparent",
                H0 + timedelta(hours=2),
                H0 + timedelta(hours=3),
            ),
            during_hold=_during_hold,
        )
    finally:
        Path(path).unlink(missing_ok=True)

    verify = SessionLocal()
    try:
        policies = _policies(verify, seeded["owner_id"])
        assert len(policies) == 1
        assert policies[0].conflict_pending_latched is True
        assert int(policies[0].latch_generation) == 1
        assert _decision_count(verify, seeded["owner_id"]) == 1
        assert _event_by_external_id(verify, ext_a).free_busy_pending_exception is False
        sibling = _event_by_external_id(verify, ext_b)
        assert sibling.free_busy_pending_exception is True
        assert sibling.transparency == "transparent"
    finally:
        verify.close()


def test_real_concurrent_first_policy_race() -> None:
    """No policy row yet. Resolve creates it under the identity lock; sibling ingest waits.

    Real concurrent sessions. One policy, one decision, no duplicate insert.
    """
    series = f"race-first-{uuid.uuid4().hex[:12]}"
    ext_a = f"first-a-{uuid.uuid4().hex}"
    ext_b = f"first-b-{uuid.uuid4().hex}"
    seeded = _seed_committed_series(
        series=series,
        rows=[
            {
                "external_id": ext_a,
                "transparency": "opaque",
                "pending": True,
                "start": H0,
                "end": H0 + timedelta(hours=1),
            },
            {
                "external_id": ext_b,
                "transparency": "opaque",
                "pending": True,
                "start": H0 + timedelta(hours=2),
                "end": H0 + timedelta(hours=3),
            },
        ],
    )
    path = _allowlist_file(seeded["owner_id"])

    def _during_hold() -> None:
        probe = SessionLocal()
        try:
            assert _policies(probe, seeded["owner_id"]) == []
            assert _decision_count(probe, seeded["owner_id"]) == 0
            sibling = _event_by_external_id(probe, ext_b)
            assert sibling.transparency == "opaque"
            assert sibling.free_busy_pending_exception is True
        finally:
            probe.close()

    try:
        _run_resolve_holds_ingest_waits(
            seeded=seeded,
            allowlist_path=path,
            resolve_external_id=ext_a,
            ingest_event=_google_event(
                ext_b,
                series,
                "transparent",
                H0 + timedelta(hours=2),
                H0 + timedelta(hours=3),
            ),
            during_hold=_during_hold,
        )
    finally:
        Path(path).unlink(missing_ok=True)

    verify = SessionLocal()
    try:
        policies = _policies(verify, seeded["owner_id"])
        assert len(policies) == 1
        assert policies[0].mapping == "free"
        assert policies[0].conflict_pending_latched is True
        assert _decision_count(verify, seeded["owner_id"]) == 1
        assert _event_by_external_id(verify, ext_a).free_busy_pending_exception is False
        sibling = _event_by_external_id(verify, ext_b)
        assert sibling.free_busy_pending_exception is True
        assert sibling.transparency == "transparent"
    finally:
        verify.close()


def test_real_concurrent_new_instance_race() -> None:
    """Resolve in flight; ingest inserts occurrence C only after the identity lock.

    Real concurrent sessions. C is absent to other sessions during the wait.
    After both commit, C's automatic baseline shows the new policy was visible.
    """
    series = f"race-new-{uuid.uuid4().hex[:12]}"
    ext_a = f"new-a-{uuid.uuid4().hex}"
    ext_c = f"new-c-{uuid.uuid4().hex}"
    c_start = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
    c_end = datetime(2026, 11, 2, 11, 0, tzinfo=UTC)
    seeded = _seed_committed_series(
        series=series,
        rows=[
            {
                "external_id": ext_a,
                "transparency": "transparent",
                "pending": True,
                "start": H0,
                "end": H1,
            },
        ],
    )
    path = _allowlist_file(seeded["owner_id"])

    def _during_hold() -> None:
        probe = SessionLocal()
        try:
            assert (
                probe.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.external_event_id == ext_c)
                .count()
                == 0
            )
            assert _decision_count(probe, seeded["owner_id"]) == 0
        finally:
            probe.close()

    try:
        _run_resolve_holds_ingest_waits(
            seeded=seeded,
            allowlist_path=path,
            resolve_external_id=ext_a,
            ingest_event=_google_event(ext_c, series, "transparent", c_start, c_end),
            during_hold=_during_hold,
        )
    finally:
        Path(path).unlink(missing_ok=True)

    verify = SessionLocal()
    try:
        policies = _policies(verify, seeded["owner_id"])
        assert len(policies) == 1
        assert policies[0].mapping == "free"
        assert policies[0].conflict_pending_latched is False
        assert _decision_count(verify, seeded["owner_id"]) == 1
        trigger = _event_by_external_id(verify, ext_a)
        assert trigger.free_busy_pending_exception is False
        created = _event_by_external_id(verify, ext_c)
        assert created.free_busy_pending_exception is False
        assert created.provider_series_id == series
        baseline = (
            verify.query(FreeBusyOccurrenceBaseline)
            .filter(
                FreeBusyOccurrenceBaseline.owner_id == seeded["owner_id"],
                FreeBusyOccurrenceBaseline.external_event_id == ext_c,
            )
            .one()
        )
        assert baseline.source == "automatic_first_trustworthy_observation"
        decision = (
            verify.query(FreeBusySeriesPolicyDecision)
            .join(FreeBusySeriesPolicy)
            .filter(FreeBusySeriesPolicy.owner_id == seeded["owner_id"])
            .one()
        )
        acked = {
            item["external_event_id"]
            for item in decision.snapshot["conflict_acknowledgments"]
        }
        assert ext_c not in acked
        assert decision.decided_by_user_id == seeded["owner_id"]
    finally:
        verify.close()


def test_real_session_rollback_no_partial_write() -> None:
    """Flushed resolve then rollback. A new session sees no policy, decision, or baseline."""
    series = f"roll-{uuid.uuid4().hex[:12]}"
    ext_a = f"roll-a-{uuid.uuid4().hex}"
    seeded = _seed_committed_series(
        series=series,
        rows=[
            {
                "external_id": ext_a,
                "transparency": "transparent",
                "pending": True,
                "start": H0,
                "end": H1,
            },
        ],
    )
    path = _allowlist_file(seeded["owner_id"])
    worker = SessionLocal()
    try:
        user = worker.get(User, seeded["owner_id"])
        assert user is not None
        resolve_series_policy(
            worker,
            user=user,
            body=ResolveSeriesPolicyRequest(
                external_event_id=ext_a,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(ext_a, seeded["revisions"][ext_a]),
                ),
                reason="rollback me",
            ),
            allowlist_path=path,
        )
        assert len(_policies(worker, seeded["owner_id"])) == 1
        assert _decision_count(worker, seeded["owner_id"]) == 1
        assert _baseline_count(worker, seeded["owner_id"]) == 1
        assert _event_by_external_id(worker, ext_a).free_busy_pending_exception is False
        worker.rollback()
    finally:
        worker.close()
        Path(path).unlink(missing_ok=True)

    verify = SessionLocal()
    try:
        assert _policies(verify, seeded["owner_id"]) == []
        assert _decision_count(verify, seeded["owner_id"]) == 0
        assert _baseline_count(verify, seeded["owner_id"]) == 0
        row = _event_by_external_id(verify, ext_a)
        assert row.free_busy_pending_exception is True
        assert row.transparency == "transparent"
    finally:
        verify.close()


def test_real_session_restart_persists_resolved_and_latched() -> None:
    """Commit, close, new session. Resolved trust survives; a later latch survives too."""
    series = f"restart-{uuid.uuid4().hex[:12]}"
    ext_a = f"restart-a-{uuid.uuid4().hex}"
    seeded = _seed_committed_series(
        series=series,
        rows=[
            {
                "external_id": ext_a,
                "transparency": "transparent",
                "pending": True,
                "start": H0,
                "end": H1,
            },
        ],
    )
    path = _allowlist_file(seeded["owner_id"])
    writer = SessionLocal()
    try:
        user = writer.get(User, seeded["owner_id"])
        assert user is not None
        resolve_series_policy(
            writer,
            user=user,
            body=ResolveSeriesPolicyRequest(
                external_event_id=ext_a,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(ext_a, seeded["revisions"][ext_a]),
                ),
                reason="persist across sessions",
            ),
            allowlist_path=path,
        )
        writer.commit()
    finally:
        writer.close()
        Path(path).unlink(missing_ok=True)

    restarted = SessionLocal()
    try:
        inputs = collect_inputs(restarted, seeded["owner_id"], H0)
        assert inputs.busy_input_trust is not None
        assert inputs.busy_input_trust.ok is True
        policies = _policies(restarted, seeded["owner_id"])
        assert len(policies) == 1
        assert policies[0].mapping == "free"
        assert policies[0].conflict_pending_latched is False
        assert _decision_count(restarted, seeded["owner_id"]) == 1
        assert _event_by_external_id(restarted, ext_a).free_busy_pending_exception is False
    finally:
        restarted.close()

    disagree = SessionLocal()
    try:
        account = disagree.get(CalendarAccount, seeded["account_id"])
        sub = disagree.get(CalendarSubscription, seeded["sub_id"])
        assert account is not None and sub is not None
        ok = _upsert_external_event(
            disagree,
            account=account,
            subscription=sub,
            event=_google_event(ext_a, series, "opaque", H0, H1),
            now=datetime.now(UTC),
            sync_run_id="t1-4a-restart-disagree",
        )
        assert ok is True
        disagree.commit()
    finally:
        disagree.close()

    latched = SessionLocal()
    try:
        policies = _policies(latched, seeded["owner_id"])
        assert len(policies) == 1
        assert policies[0].conflict_pending_latched is True
        row = _event_by_external_id(latched, ext_a)
        assert row.free_busy_pending_exception is True
        assert row.transparency == "opaque"
        assert _decision_count(latched, seeded["owner_id"]) == 1
        inputs = collect_inputs(latched, seeded["owner_id"], H0)
        assert inputs.busy_input_trust is not None
        assert inputs.busy_input_trust.ok is False
    finally:
        latched.close()


def test_apply_recollect_gate_fresh_session_without_live_apply() -> None:
    """Same collect + require_busy_input_trust gate Apply uses, without a preview write.

    Fresh session after commit. Not a concurrent race and not live Apply.
    """
    series = f"recollect-{uuid.uuid4().hex[:12]}"
    ext_a = f"recollect-a-{uuid.uuid4().hex}"
    seeded = _seed_committed_series(
        series=series,
        rows=[
            {
                "external_id": ext_a,
                "transparency": "transparent",
                "pending": True,
                "start": H0,
                "end": H1,
            },
        ],
    )
    path = _allowlist_file(seeded["owner_id"])
    writer = SessionLocal()
    try:
        user = writer.get(User, seeded["owner_id"])
        assert user is not None
        resolve_series_policy(
            writer,
            user=user,
            body=ResolveSeriesPolicyRequest(
                external_event_id=ext_a,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(ext_a, seeded["revisions"][ext_a]),
                ),
                reason="recollect gate",
            ),
            allowlist_path=path,
        )
        writer.commit()
    finally:
        writer.close()
        Path(path).unlink(missing_ok=True)

    fresh = SessionLocal()
    try:
        # apply_schedule_preview collects at replay time and again at `now`
        # inside _validate_ready_for_apply, then require_busy_input_trust.
        at_replay = collect_inputs(fresh, seeded["owner_id"], H0)
        at_now = collect_inputs(fresh, seeded["owner_id"], H0 + timedelta(hours=2))
        require_busy_input_trust(at_replay.busy_input_trust)
        require_busy_input_trust(at_now.busy_input_trust)
        assert at_replay.busy_input_trust is not None and at_replay.busy_input_trust.ok
        assert at_now.busy_input_trust is not None and at_now.busy_input_trust.ok

        row = _event_by_external_id(fresh, ext_a)
        row.free_busy_pending_exception = True
        policy = _policies(fresh, seeded["owner_id"])[0]
        policy.conflict_pending_latched = True
        fresh.flush()
        blocked = collect_inputs(fresh, seeded["owner_id"], H0)
        with pytest.raises(BusyInputTrustError):
            require_busy_input_trust(blocked.busy_input_trust)
        fresh.rollback()
    finally:
        fresh.close()


def test_simulated_mixed_sibling_unchanged_refresh_does_not_reopen() -> None:
    """Simulated sequential single session — not a concurrent DB race.

    One resolve accepts opaque A and transparent B. Unchanged refresh of B does
    not reopen A. A later change on unacknowledged C still blocks.
    """
    db = SessionLocal()
    path: str | None = None
    try:
        owner, _settings = _owner(db)
        account = _account(db, owner)
        sub = _sub(db, account)
        series = f"mixed-{uuid.uuid4().hex[:12]}"
        ext_a = f"mix-a-{uuid.uuid4().hex}"
        ext_b = f"mix-b-{uuid.uuid4().hex}"
        ext_c = f"mix-c-{uuid.uuid4().hex}"
        row_a = _event(
            db,
            owner=owner,
            account=account,
            sub=sub,
            external_id=ext_a,
            series_id=series,
            transparency="opaque",
            pending=True,
            start=H0,
            end=H0 + timedelta(hours=1),
        )
        row_b = _event(
            db,
            owner=owner,
            account=account,
            sub=sub,
            external_id=ext_b,
            series_id=series,
            transparency="transparent",
            pending=True,
            start=H0 + timedelta(hours=2),
            end=H0 + timedelta(hours=3),
        )
        row_c = _event(
            db,
            owner=owner,
            account=account,
            sub=sub,
            external_id=ext_c,
            series_id=series,
            transparency="transparent",
            pending=False,
            start=H0 + timedelta(days=2),
            end=H0 + timedelta(days=2, hours=1),
        )
        db.flush()
        path = _allowlist_file(owner.id)
        resolve_series_policy(
            db,
            user=owner,
            body=ResolveSeriesPolicyRequest(
                external_event_id=ext_a,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(ext_a, _revision(owner, sub, series, row_a)),
                    ConflictAcknowledgment(ext_b, _revision(owner, sub, series, row_b)),
                ),
                reason="mixed sibling ack",
            ),
            allowlist_path=path,
        )
        db.flush()
        decision = (
            db.query(FreeBusySeriesPolicyDecision)
            .join(FreeBusySeriesPolicy)
            .filter(FreeBusySeriesPolicy.owner_id == owner.id)
            .one()
        )
        evidence = {
            item["external_event_id"]: item["provider_evidence"]["transparency"]
            for item in decision.snapshot["conflict_acknowledgments"]
        }
        assert evidence[ext_a] == "opaque"
        assert evidence[ext_b] == "transparent"
        assert ext_c not in evidence

        ok = _upsert_external_event(
            db,
            account=account,
            subscription=sub,
            event=_google_event(
                ext_b,
                series,
                "transparent",
                H0 + timedelta(hours=2),
                H0 + timedelta(hours=3),
            ),
            now=datetime.now(UTC),
            sync_run_id="mixed-refresh-b",
        )
        assert ok is True
        db.flush()
        db.refresh(row_a)
        db.refresh(row_b)
        policy = _policies(db, owner.id)[0]
        assert row_a.free_busy_pending_exception is False
        assert row_b.free_busy_pending_exception is False
        assert policy.conflict_pending_latched is False
        baseline_b = (
            db.query(FreeBusyOccurrenceBaseline)
            .filter(FreeBusyOccurrenceBaseline.external_event_id == ext_b)
            .one()
        )
        assert baseline_b.source == "manual_resolve"

        ok = _upsert_external_event(
            db,
            account=account,
            subscription=sub,
            event=_google_event(
                ext_c,
                series,
                "transparent",
                H0 + timedelta(days=2),
                H0 + timedelta(days=2, hours=1),
            ),
            now=datetime.now(UTC),
            sync_run_id="mixed-seed-c",
        )
        assert ok is True
        db.flush()
        baseline_c = (
            db.query(FreeBusyOccurrenceBaseline)
            .filter(FreeBusyOccurrenceBaseline.external_event_id == ext_c)
            .one()
        )
        assert baseline_c.source == "automatic_first_trustworthy_observation"
        assert row_c.free_busy_pending_exception is False

        ok = _upsert_external_event(
            db,
            account=account,
            subscription=sub,
            event=_google_event(
                ext_c,
                series,
                "opaque",
                H0 + timedelta(days=2),
                H0 + timedelta(days=2, hours=1),
            ),
            now=datetime.now(UTC),
            sync_run_id="mixed-change-c",
        )
        assert ok is True
        db.flush()
        db.refresh(row_a)
        db.refresh(row_c)
        db.refresh(policy)
        assert row_a.free_busy_pending_exception is False
        assert row_c.free_busy_pending_exception is True
        assert policy.conflict_pending_latched is True
        assert _decision_count(db, owner.id) == 1
        trust = evaluate_busy_input_trust(
            [row_a, row_b, row_c],
            horizon_start=H0,
            horizon_end=H0 + timedelta(days=3),
            policy_map=load_series_policies_for_owner(db, owner.id),
        )
        assert trust.ok is False
        assert any(item.event_id == ext_c for item in trust.blocking_diagnostics)
        db.rollback()
    finally:
        db.close()
        if path is not None:
            Path(path).unlink(missing_ok=True)


def test_simulated_window_outside_pending_retains_latch(
    db_session: Session,
) -> None:
    """Simulated sequential single session — not a concurrent DB race.

    Authoritative pending includes a sibling outside the queried window.
    Acking only the in-window occurrence keeps the latch and the outside row.
    """
    owner, _settings = _owner(db_session)
    path = _allowlist_file(owner.id)
    try:
        account = _account(db_session, owner)
        sub = _sub(db_session, account)
        series = f"window-{uuid.uuid4().hex[:12]}"
        inside = _event(
            db_session,
            owner=owner,
            account=account,
            sub=sub,
            external_id=f"win-in-{uuid.uuid4().hex}",
            series_id=series,
            pending=True,
            start=H0,
            end=H0 + timedelta(hours=1),
        )
        outside_start = H0 + timedelta(days=30)
        outside = _event(
            db_session,
            owner=owner,
            account=account,
            sub=sub,
            external_id=f"win-out-{uuid.uuid4().hex}",
            series_id=series,
            pending=True,
            start=outside_start,
            end=outside_start + timedelta(hours=1),
        )
        policy = FreeBusySeriesPolicy(
            owner_id=owner.id,
            provider=CalendarProvider.google,
            calendar_id=sub.external_calendar_id,
            provider_series_id=series,
            mapping="free",
            conflict_pending_latched=True,
            latch_generation=4,
        )
        db_session.add(policy)
        db_session.flush()

        window_start = H0
        window_end = H0 + timedelta(days=1)
        in_window = (
            db_session.query(ExternalCalendarEvent)
            .filter(
                ExternalCalendarEvent.owner_id == owner.id,
                ExternalCalendarEvent.provider_series_id == series,
                ExternalCalendarEvent.start_time < window_end,
                ExternalCalendarEvent.end_time > window_start,
            )
            .all()
        )
        assert {row.external_event_id for row in in_window} == {inside.external_event_id}
        authoritative = authoritative_pending_events(
            db_session,
            owner_id=owner.id,
            provider=inside.provider,
            calendar_id=sub.external_calendar_id,
            provider_series_id=series,
        )
        assert {row.external_event_id for row in authoritative} == {
            inside.external_event_id,
            outside.external_event_id,
        }

        resolve_series_policy(
            db_session,
            user=owner,
            body=ResolveSeriesPolicyRequest(
                external_event_id=inside.external_event_id,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(
                        inside.external_event_id,
                        _revision(owner, sub, series, inside, latch=4),
                    ),
                ),
                reason="window-visible only",
            ),
            allowlist_path=path,
        )
        db_session.refresh(inside)
        db_session.refresh(outside)
        db_session.refresh(policy)
        assert inside.free_busy_pending_exception is False
        assert outside.free_busy_pending_exception is True
        assert policy.conflict_pending_latched is True
        trust = evaluate_busy_input_trust(
            [inside, outside],
            horizon_start=window_start,
            horizon_end=window_end,
            policy_map=load_series_policies_for_owner(db_session, owner.id),
        )
        assert trust.ok is False
        assert any(item.event_id == outside.external_event_id for item in trust.blocking_diagnostics)
    finally:
        Path(path).unlink(missing_ok=True)
