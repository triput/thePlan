"""T1-4a acceptance — persisted series policy + resolve (Dex contract §9)."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.db import engine
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
from app.scheduler.free_busy import evaluate_busy_input_trust, events_for_busy_merge
from app.services.free_busy_resolver_allowlist import parse_resolver_allowlist_file
from app.services.free_busy_series_policy import (
    ConflictAcknowledgment,
    ResolveSeriesPolicyRequest,
    apply_post_transparency_policy_effects,
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
        workday_start_local=time(8, 0),
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
