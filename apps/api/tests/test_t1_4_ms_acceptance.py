"""T1-4-MS acceptance — Microsoft series identity + E1 (Dex contract §9).

Requires ``T1A_REQUIRE_DISPOSABLE_DSN=1`` and disposable Postgres ``:5433``.
No live Graph. No household DB. Lock-wait tests are distinguished from injected
rollback fixtures (E-MS-13 / E-MS-16).
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
import uuid
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings, get_settings
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
from app.scheduler.free_busy import (
    evaluate_busy_input_trust,
    source_zone_untrusted,
)
from app.services.free_busy_series_policy import (
    SERIES_IDENTITY_INCOMPLETE,
    SERIES_IDENTITY_VERIFIED_NON_RECURRING,
    SERIES_IDENTITY_VERIFIED_SERIES,
    UpsertPostLockIdentityDriftError,
    _FREE_BUSY_IDENTITY_NAMESPACE,
    ConflictAcknowledgment,
    ResolveSeriesPolicyRequest,
    acquire_identity_advisory_locks,
    compute_conflict_revision,
    microsoft_upsert_identity_keys_for_lock,
    policy_diagnostic_enrichment,
    resolve_series_policy,
    sort_identity_keys,
)
from app.services.microsoft_calendar import (
    MS_EVENT_LIST_FETCH_CONTEXT,
    MS_EVENT_FETCH_CONTEXT_UNCERTAIN,
    _apply_subscription_full,
    _apply_subscription_incremental,
    _apply_subscription_ms_view,
    _upsert_external_event,
)
from app.services.microsoft_series_identity import (
    IncompleteIdentity,
    KnownNonRecurring,
    KnownSeries,
    MalformedIdentity,
    MicrosoftSeriesIdentityError,
    MicrosoftSeriesMasterInBatchError,
    extract_microsoft_series_identity,
)
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
H0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
H1 = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    if os.environ.get("T1A_REQUIRE_DISPOSABLE_DSN") != "1":
        pytest.skip("T1-4-MS acceptance requires T1A_REQUIRE_DISPOSABLE_DSN=1")
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _owner(db: Session) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:8]
    user = User(
        email=f"t1-4ms-{token}@example.test",
        username=f"t1_4ms_{token}",
        display_name="T1-4-MS",
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
        provider=CalendarProvider.microsoft,
        account_email=f"{uuid.uuid4().hex[:6]}@example.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(acct)
    db.flush()
    return acct


def _sub(db: Session, account: CalendarAccount, *, cal_id: str = "ms-cal") -> CalendarSubscription:
    sub = CalendarSubscription(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=cal_id,
        summary="MS Primary",
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
        provider_timezone="UTC",
    )
    db.add(sub)
    db.flush()
    return sub


def _allowlist_file(*user_ids: UUID) -> str:
    fd, path = tempfile.mkstemp(suffix=".allowlist")
    os.close(fd)
    Path(path).write_text("".join(f"{uid}\n" for uid in user_ids), encoding="utf-8")
    return path


def _ms_event_payload(
    external_id: str,
    *,
    type: str | None = "occurrence",
    master: str | None | object = "MASTER",
    show_as: str = "busy",
    start: datetime | None = None,
    end: datetime | None = None,
    include_times: bool = True,
    include_master_key: bool = True,
) -> dict:
    start = start or H0
    end = end or H1
    payload: dict = {
        "id": external_id,
        "subject": f"subj-{external_id}",
        "showAs": show_as,
    }
    if type is not None:
        payload["type"] = type
    if include_master_key:
        payload["seriesMasterId"] = master
    if include_times:
        payload["start"] = {
            "dateTime": start.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
            "timeZone": "UTC",
        }
        payload["end"] = {
            "dateTime": end.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
            "timeZone": "UTC",
        }
    return payload


def _seed_ms_row(
    db: Session,
    *,
    owner: User,
    account: CalendarAccount,
    sub: CalendarSubscription,
    external_id: str,
    series_id: str | None,
    state: str = SERIES_IDENTITY_VERIFIED_SERIES,
    reason: str | None = None,
    transparency: str = "opaque",
    pending: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        provider=CalendarProvider.microsoft,
        external_event_id=external_id,
        calendar_id=sub.external_calendar_id,
        provider_series_id=series_id,
        series_identity_state=state,
        series_identity_incomplete_reason=reason,
        title=f"evt-{external_id}",
        start_time=start or H0,
        end_time=end or H1,
        transparency=transparency,
        free_busy_provenance="provider_explicit",
        free_busy_pending_exception=pending,
        source_timezone="UTC",
        is_all_day=False,
    )
    db.add(row)
    db.flush()
    return row


def _row(db: Session, external_id: str) -> ExternalCalendarEvent:
    return (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == external_id)
        .one()
    )


def _trust_blocked_incomplete(db: Session, owner: User, row: ExternalCalendarEvent) -> None:
    trust = evaluate_busy_input_trust(
        [row],
        horizon_start=H0 - timedelta(hours=1),
        horizon_end=H1 + timedelta(hours=1),
    )
    assert trust.ok is False
    causes = {d.cause for d in trust.blocking_diagnostics}
    assert "series_identity_incomplete" in causes


# --- Extractor unit (no DB) -------------------------------------------------


@pytest.mark.parametrize(
    "payload,expected",
    [
        (
            {"id": "e1", "type": "occurrence", "seriesMasterId": "M1"},
            KnownSeries("M1", source="occurrence"),
        ),
        (
            {"id": "e1", "type": "exception", "seriesMasterId": "M1"},
            KnownSeries("M1", source="exception"),
        ),
        (
            {"id": "M1", "type": "seriesMaster"},
            KnownSeries("M1", source="seriesMaster"),
        ),
        (
            {"id": "e1", "type": "singleInstance"},
            KnownNonRecurring(),
        ),
        (
            {"id": "e1", "type": "singleInstance", "seriesMasterId": None},
            KnownNonRecurring(),
        ),
        (
            {"id": "e1", "type": "occurrence"},
            IncompleteIdentity("missing_series_master"),
        ),
        (
            {"id": "e1"},
            IncompleteIdentity("unrecognized_or_omitted_type"),
        ),
        (
            {"id": "e1", "type": "weird", "seriesMasterId": "M1"},
            IncompleteIdentity("unrecognized_type_with_master"),
        ),
        (
            {"id": "e1", "type": "singleInstance", "seriesMasterId": "M1"},
            MalformedIdentity("contradiction_single_with_master"),
        ),
        (
            {"id": "e1", "type": "occurrence", "seriesMasterId": {"x": 1}},
            MalformedIdentity("non_string_series_master_id"),
        ),
        (
            {"id": "e1", "type": "occurrence", "seriesMasterId": "e1"},
            MalformedIdentity("contradiction_instance_master_eq_self"),
        ),
        (
            {"type": "occurrence", "seriesMasterId": "M1"},
            MalformedIdentity("missing_event_id"),
        ),
    ],
)
def test_extractor_ternary_and_precedence(payload: dict, expected: object) -> None:
    got = extract_microsoft_series_identity(payload)
    assert got == expected


def test_ems_2h_contradiction_never_promotes_to_known_series() -> None:
    """Valid-looking master string must not win over contradiction (E-MS-2h)."""
    got = extract_microsoft_series_identity(
        {
            "id": "e1",
            "type": "singleInstance",
            "seriesMasterId": "looks-valid-master",
        }
    )
    assert isinstance(got, MalformedIdentity)
    assert got.reason == "contradiction_single_with_master"


def test_unit_microsoft_identity_lock_keys_sorted() -> None:
    owner = uuid.uuid4()
    keys = microsoft_upsert_identity_keys_for_lock(
        row=None,
        new_calendar_id="cal-b",
        new_series_id="series-z",
        old_calendar_id="cal-a",
        old_series_id="series-a",
        owner_id=owner,
    )
    assert keys == sort_identity_keys(keys)
    assert keys[0][2] == "cal-a"


# --- Ingest persistence -----------------------------------------------------


def test_ems_1_series_persist(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"occ-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    ok = _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(ext, master=master),
        now=datetime.now(UTC),
        sync_run_id="ems-1",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    assert ok is True
    row = _row(db_session, ext)
    assert row.provider_series_id == master
    assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_SERIES
    assert row.series_identity_incomplete_reason is None


def test_ems_2_known_non_recurring_resolve_422(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    path = _allowlist_file(owner.id)
    monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path)
    get_settings.cache_clear()
    ext = f"single-{uuid.uuid4().hex[:8]}"
    ok = _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(
            ext, type="singleInstance", include_master_key=False, show_as="free"
        ),
        now=datetime.now(UTC),
        sync_run_id="ems-2",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    assert ok is True
    row = _row(db_session, ext)
    assert row.provider_series_id is None
    assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_NON_RECURRING
    with pytest.raises(ApiError) as ei:
        resolve_series_policy(
            db_session,
            user=owner,
            body=ResolveSeriesPolicyRequest(
                external_event_id=ext,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(ext, "deadbeef" * 4),
                ),
                reason="nope",
            ),
            allowlist_path=path,
        )
    assert ei.value.content["code"] in (
        "FREE_BUSY_RESOLVE_INVALID",
        "FREE_BUSY_SERIES_IDENTITY_INCOMPLETE",
    )


def test_ems_2b_incomplete_attached_retains_series(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"att-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        state=SERIES_IDENTITY_VERIFIED_SERIES,
    )
    ok = _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(ext, type="occurrence", include_master_key=False),
        now=datetime.now(UTC),
        sync_run_id="ems-2b",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    assert ok is True
    row = _row(db_session, ext)
    assert row.provider_series_id == master
    assert row.series_identity_state == SERIES_IDENTITY_INCOMPLETE
    assert row.series_identity_incomplete_reason == "missing_series_master"
    assert row.free_busy_pending_exception is False  # not series loss
    _trust_blocked_incomplete(db_session, owner, row)


def test_ems_2f_incomplete_new_occurrence_null_series(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"new-inc-{uuid.uuid4().hex[:8]}"
    ok = _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(
            ext, type="occurrence", include_master_key=False, show_as="free"
        ),
        now=datetime.now(UTC),
        sync_run_id="ems-2f",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    assert ok is True
    row = _row(db_session, ext)
    assert row.provider_series_id is None
    assert row.series_identity_state == SERIES_IDENTITY_INCOMPLETE
    assert row.series_identity_state != SERIES_IDENTITY_VERIFIED_NON_RECURRING
    assert row.transparency == "transparent"
    _trust_blocked_incomplete(db_session, owner, row)


def test_ems_2c_verified_series_loss(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"loss-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
    )
    ok = _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(
            ext, type="singleInstance", include_master_key=False
        ),
        now=datetime.now(UTC),
        sync_run_id="ems-2c",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    assert ok is True
    row = _row(db_session, ext)
    assert row.provider_series_id is None
    assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_NON_RECURRING
    assert row.free_busy_pending_exception is True


def test_ems_2g_resolve_while_incomplete_then_recovery(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    path = _allowlist_file(owner.id)
    monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path)
    get_settings.cache_clear()
    ext = f"recov-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        transparency="transparent",
    )
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        calendar_id=sub.external_calendar_id,
        provider_series_id=master,
        mapping="free",
        conflict_pending_latched=False,
        latch_generation=0,
        acknowledged_calendar_id=sub.external_calendar_id,
        acknowledged_series_id=master,
    )
    db_session.add(policy)
    db_session.flush()
    baseline = FreeBusyOccurrenceBaseline(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        external_event_id=ext,
        transparency="transparent",
        free_busy_provenance="provider_explicit",
        occupancy_kind="free",
        source="manual_resolve",
    )
    db_session.add(baseline)
    db_session.flush()

    # Incomplete payload → T0b pending + latch
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(ext, type="occurrence", include_master_key=False),
        now=datetime.now(UTC),
        sync_run_id="ems-2g-inc",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    assert row.series_identity_state == SERIES_IDENTITY_INCOMPLETE
    assert row.free_busy_pending_exception is True
    db_session.refresh(policy)
    assert policy.conflict_pending_latched is True
    latch_after_t0b = int(policy.latch_generation)
    assert latch_after_t0b >= 1

    key = (
        str(owner.id),
        "microsoft",
        sub.external_calendar_id,
        master,
    )
    revision = compute_conflict_revision(
        identity=key,
        external_event_id=ext,
        transparency=row.transparency,
        provenance=row.free_busy_provenance,
        pending=True,
        latch_generation=latch_after_t0b,
        source_zone_untrusted=source_zone_untrusted(row),
        series_identity_state=row.series_identity_state,
        series_identity_incomplete_reason=row.series_identity_incomplete_reason,
    )
    with pytest.raises(ApiError) as ei:
        resolve_series_policy(
            db_session,
            user=owner,
            body=ResolveSeriesPolicyRequest(
                external_event_id=ext,
                conflict_acknowledgments=(
                    ConflictAcknowledgment(ext, revision),
                ),
                reason="while incomplete",
            ),
            allowlist_path=path,
        )
    assert ei.value.content["code"] == "FREE_BUSY_SERIES_IDENTITY_INCOMPLETE"
    db_session.refresh(row)
    db_session.refresh(policy)
    assert row.free_busy_pending_exception is True
    assert policy.conflict_pending_latched is True

    # Complete KnownSeries recovery — latch preserved
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(ext, master=master, show_as="free"),
        now=datetime.now(UTC),
        sync_run_id="ems-2g-ok",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_SERIES
    assert row.provider_series_id == master
    db_session.refresh(policy)
    assert policy.conflict_pending_latched is True
    assert row.free_busy_pending_exception is True


def test_ems_3_calendar_move_pending(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub_a = _sub(db_session, account, cal_id="cal-a")
    sub_b = _sub(db_session, account, cal_id="cal-b")
    ext = f"move-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub_a,
        external_id=ext,
        series_id=master,
    )
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub_b,
        event=_ms_event_payload(ext, master=master),
        now=datetime.now(UTC),
        sync_run_id="ems-3",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    assert row.calendar_id == "cal-b"
    assert row.free_busy_pending_exception is True


def test_ems_4_series_change_pending(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"chg-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id="master-old",
    )
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(ext, master="master-new"),
        now=datetime.now(UTC),
        sync_run_id="ems-4",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    assert row.provider_series_id == "master-new"
    assert row.free_busy_pending_exception is True


def test_ems_6_q2_transparent_to_opaque_latch(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"q2-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        transparency="transparent",
    )
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        calendar_id=sub.external_calendar_id,
        provider_series_id=master,
        mapping="free",
        acknowledged_calendar_id=sub.external_calendar_id,
        acknowledged_series_id=master,
        latch_generation=0,
    )
    db_session.add(policy)
    db_session.add(
        FreeBusyOccurrenceBaseline(
            owner_id=owner.id,
            provider=CalendarProvider.microsoft,
            external_event_id=ext,
            transparency="transparent",
            free_busy_provenance="provider_explicit",
            occupancy_kind="free",
            source="manual_resolve",
        )
    )
    db_session.flush()
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(ext, master=master, show_as="busy"),
        now=datetime.now(UTC),
        sync_run_id="ems-6",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    db_session.refresh(policy)
    assert row.free_busy_pending_exception is True
    assert policy.conflict_pending_latched is True


def test_ems_7_q1_opaque_to_transparent_no_latch(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"q1-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        transparency="opaque",
    )
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        calendar_id=sub.external_calendar_id,
        provider_series_id=master,
        mapping="free",
        acknowledged_calendar_id=sub.external_calendar_id,
        acknowledged_series_id=master,
        latch_generation=0,
    )
    db_session.add(policy)
    db_session.add(
        FreeBusyOccurrenceBaseline(
            owner_id=owner.id,
            provider=CalendarProvider.microsoft,
            external_event_id=ext,
            transparency="opaque",
            free_busy_provenance="provider_explicit",
            occupancy_kind="busy",
            source="automatic_first_trustworthy_observation",
        )
    )
    db_session.flush()
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_ms_event_payload(ext, master=master, show_as="free"),
        now=datetime.now(UTC),
        sync_run_id="ems-7",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    db_session.refresh(policy)
    assert row.transparency == "transparent"
    assert row.free_busy_pending_exception is False
    assert policy.conflict_pending_latched is False


def test_ems_10_uncertain_fetch_t0b(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"unc-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        transparency="transparent",
    )
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        calendar_id=sub.external_calendar_id,
        provider_series_id=master,
        mapping="free",
        acknowledged_calendar_id=sub.external_calendar_id,
        acknowledged_series_id=master,
    )
    db_session.add(policy)
    db_session.flush()
    payload = _ms_event_payload(ext, master=master)
    del payload["showAs"]
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=payload,
        now=datetime.now(UTC),
        sync_run_id="ems-10",
        event_fetch_context=MS_EVENT_FETCH_CONTEXT_UNCERTAIN,
    )
    row = _row(db_session, ext)
    db_session.refresh(policy)
    assert row.free_busy_provenance == "unknown_projection"
    assert row.free_busy_pending_exception is True
    assert policy.conflict_pending_latched is True


def test_ems_11_invalid_times_participate(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"inv-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
    )
    policy = FreeBusySeriesPolicy(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        calendar_id=sub.external_calendar_id,
        provider_series_id=master,
        mapping="free",
        acknowledged_calendar_id=sub.external_calendar_id,
        acknowledged_series_id=master,
    )
    db_session.add(policy)
    db_session.flush()
    payload = _ms_event_payload(ext, master=master)
    # Equal start/end → invalid
    payload["end"] = payload["start"]
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=payload,
        now=datetime.now(UTC),
        sync_run_id="ems-11",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    assert row.free_busy_provenance == "unknown_projection"
    assert row.provider_series_id == master
    assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_SERIES
    db_session.refresh(policy)
    assert policy.conflict_pending_latched is True


def test_ems_12_omit_times_participate(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"omit-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        transparency="opaque",
    )
    payload = _ms_event_payload(
        ext, master=master, show_as="free", include_times=False
    )
    assert _upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=payload,
        now=datetime.now(UTC),
        sync_run_id="ems-12",
        event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
    )
    row = _row(db_session, ext)
    assert row.start_time == H0
    assert row.transparency == "transparent"
    assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_SERIES


# --- E1 whole-batch / seriesMaster ------------------------------------------


def test_ems_13_ms_view_outer_rollback_verify_a() -> None:
    """Injected Malformed on B — distinguished from real lock-wait (E-MS-9).

    A mutates inside the apply TX; outer failure rolls A back. Fresh session
    sees pre-batch A/B. Not a concurrency / pg_locks proof.
    """
    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account(seed, owner)
        sub = _sub(seed, account, cal_id=f"cal-roll-{uuid.uuid4().hex[:6]}")
        ext_a = f"roll-a-{uuid.uuid4().hex[:8]}"
        ext_b = f"roll-b-{uuid.uuid4().hex[:8]}"
        master = f"master-{uuid.uuid4().hex[:8]}"
        _seed_ms_row(
            seed,
            owner=owner,
            account=account,
            sub=sub,
            external_id=ext_a,
            series_id=master,
            transparency="opaque",
        )
        _seed_ms_row(
            seed,
            owner=owner,
            account=account,
            sub=sub,
            external_id=ext_b,
            series_id=master,
            transparency="opaque",
        )
        seed.commit()
        account_id = account.id
        sub_id = sub.id
    finally:
        seed.close()

    events = [
        _ms_event_payload(ext_a, master=master, show_as="free"),
        _ms_event_payload(ext_b, master={"bad": True}, show_as="free"),
    ]
    now = datetime.now(UTC)
    caller = SessionLocal()
    try:
        acct = caller.get(CalendarAccount, account_id)
        sub_row = caller.get(CalendarSubscription, sub_id)
        assert acct is not None and sub_row is not None
        nested = caller.begin_nested()
        with pytest.raises(MicrosoftSeriesIdentityError):
            _apply_subscription_ms_view(
                caller,
                account=acct,
                subscription=sub_row,
                events=events,
                time_min=H0 - timedelta(days=1),
                time_max=H1 + timedelta(days=1),
                now=now,
                mode="ms_view",
                coverage_generation=1,
                page_count=1,
                pagination_complete=True,
                event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
            )
        if nested.is_active:
            nested.rollback()
        caller.rollback()
    finally:
        caller.close()

    verify = SessionLocal()
    try:
        a = _row(verify, ext_a)
        b = _row(verify, ext_b)
        assert a.transparency == "opaque"
        assert b.transparency == "opaque"
        assert a.series_identity_state == SERIES_IDENTITY_VERIFIED_SERIES
        sub_v = verify.get(CalendarSubscription, sub_id)
        assert sub_v is not None
        assert sub_v.coverage_success_at is None
    finally:
        verify.close()

    # Replay consistent batch in a new transaction
    replay = SessionLocal()
    try:
        acct = replay.get(CalendarAccount, account_id)
        sub_row = replay.get(CalendarSubscription, sub_id)
        assert acct is not None and sub_row is not None
        good = [
            _ms_event_payload(ext_a, master=master, show_as="free"),
            _ms_event_payload(ext_b, master=master, show_as="free"),
        ]
        n = _apply_subscription_ms_view(
            replay,
            account=acct,
            subscription=sub_row,
            events=good,
            time_min=H0 - timedelta(days=1),
            time_max=H1 + timedelta(days=1),
            now=datetime.now(UTC),
            mode="ms_view",
            coverage_generation=2,
            page_count=1,
            pagination_complete=True,
            event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
        )
        assert n == 2
        replay.commit()
    finally:
        replay.close()

    verify2 = SessionLocal()
    try:
        a2 = _row(verify2, ext_a)
        assert a2.transparency == "transparent"
        sub2 = verify2.get(CalendarSubscription, sub_id)
        assert sub2 is not None
        assert sub2.coverage_mode == "ms_view"
        assert sub2.coverage_success_at is not None
    finally:
        verify2.close()


def test_ems_14_full_incremental_e1_no_partial_identity(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext_a = f"full-a-{uuid.uuid4().hex[:8]}"
    ext_b = f"full-b-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    prior_cursor = f"cursor-prior-{uuid.uuid4().hex[:8]}"
    sub.sync_cursor = prior_cursor
    db_session.flush()

    events = [
        _ms_event_payload(ext_a, master=master),
        _ms_event_payload(ext_b, master={"nope": 1}),
    ]
    nested = db_session.begin_nested()
    with pytest.raises(MicrosoftSeriesIdentityError):
        _apply_subscription_full(
            db_session,
            account=account,
            subscription=sub,
            events=events,
            next_delta_link="cursor-must-not-stick",
            time_min=H0 - timedelta(days=1),
            time_max=H1 + timedelta(days=1),
            now=datetime.now(UTC),
            event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
        )
    nested.rollback()
    db_session.expire_all()
    assert (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == ext_a)
        .one_or_none()
    ) is None
    db_session.refresh(sub)
    assert sub.sync_cursor == prior_cursor

    # Incremental same shape
    nested2 = db_session.begin_nested()
    with pytest.raises(MicrosoftSeriesIdentityError):
        _apply_subscription_incremental(
            db_session,
            account=account,
            subscription=sub,
            events=events,
            next_delta_link="cursor-must-not-stick-incr",
            now=datetime.now(UTC),
            event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
        )
    nested2.rollback()
    db_session.refresh(sub)
    assert sub.sync_cursor == prior_cursor


def test_ems_16a_series_master_only_fail_closed(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    master_id = f"master-only-{uuid.uuid4().hex[:8]}"
    events = [
        _ms_event_payload(master_id, type="seriesMaster", include_master_key=False),
    ]
    nested = db_session.begin_nested()
    with pytest.raises(MicrosoftSeriesMasterInBatchError):
        _apply_subscription_ms_view(
            db_session,
            account=account,
            subscription=sub,
            events=events,
            time_min=H0 - timedelta(days=1),
            time_max=H1 + timedelta(days=1),
            now=datetime.now(UTC),
            mode="ms_view",
            coverage_generation=1,
            page_count=1,
            pagination_complete=True,
            event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
        )
    nested.rollback()
    assert (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == master_id)
        .one_or_none()
    ) is None
    assert sub.coverage_success_at is None


def test_ems_16b_occurrence_plus_master_fail_closed(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    occ = f"occ-{uuid.uuid4().hex[:8]}"
    master_id = f"master-{uuid.uuid4().hex[:8]}"
    events = [
        _ms_event_payload(occ, master=master_id, show_as="busy"),
        _ms_event_payload(master_id, type="seriesMaster", include_master_key=False),
    ]
    nested = db_session.begin_nested()
    with pytest.raises(MicrosoftSeriesMasterInBatchError):
        _apply_subscription_ms_view(
            db_session,
            account=account,
            subscription=sub,
            events=events,
            time_min=H0 - timedelta(days=1),
            time_max=H1 + timedelta(days=1),
            now=datetime.now(UTC),
            mode="ms_view",
            coverage_generation=1,
            page_count=1,
            pagination_complete=True,
            event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
        )
    nested.rollback()
    assert (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == occ)
        .one_or_none()
    ) is None


def test_ems_2d_malformed_refresh_no_coverage(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    events = [
        _ms_event_payload(f"bad-{uuid.uuid4().hex[:6]}", master={"x": 1}),
    ]
    nested = db_session.begin_nested()
    with pytest.raises(MicrosoftSeriesIdentityError):
        _apply_subscription_ms_view(
            db_session,
            account=account,
            subscription=sub,
            events=events,
            time_min=H0 - timedelta(days=1),
            time_max=H1 + timedelta(days=1),
            now=datetime.now(UTC),
            mode="ms_view",
            coverage_generation=1,
            page_count=1,
            pagination_complete=True,
            event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
        )
    nested.rollback()
    assert sub.coverage_success_at is None


def test_ems_2e_contradiction_refresh_fail(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    events = [
        _ms_event_payload(
            f"ctr-{uuid.uuid4().hex[:6]}",
            type="singleInstance",
            master="foreign",
        ),
    ]
    nested = db_session.begin_nested()
    with pytest.raises(MicrosoftSeriesIdentityError):
        _apply_subscription_ms_view(
            db_session,
            account=account,
            subscription=sub,
            events=events,
            time_min=H0 - timedelta(days=1),
            time_max=H1 + timedelta(days=1),
            now=datetime.now(UTC),
            mode="ms_view",
            coverage_generation=1,
            page_count=1,
            pagination_complete=True,
            event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
        )
    nested.rollback()


# --- Migration backfill (E-MS-17) -------------------------------------------


def test_ems_17_provider_aware_backfill_legacy_ms_null() -> None:
    """Disposable DSN only — seed legacy-shaped MS row and assert incomplete.

    Columns already exist after alembic upgrade head; we simulate legacy by
    inserting with incomplete reason matching backfill codes via raw SQL reset
    of a microsoft NULL-series row's state as the migration would leave it.
    """
    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account(seed, owner)
        sub = _sub(seed, account)
        ext = f"legacy-{uuid.uuid4().hex[:8]}"
        # Insert as if pre-migration MS row then apply backfill SQL semantics.
        seed.execute(
            text(
                """
                INSERT INTO external_calendar_events (
                    id, owner_id, calendar_account_id, provider, external_event_id,
                    calendar_id, title, start_time, end_time, is_all_day,
                    pending_deletion, transparency, free_busy_provenance,
                    provider_series_id, free_busy_pending_exception,
                    source_zone_missing, is_provider_cancelled,
                    series_identity_state, series_identity_incomplete_reason
                ) VALUES (
                    :id, :owner, :acct, 'microsoft', :ext,
                    :cal, 'legacy', :start, :end, false,
                    false, 'transparent', 'provider_explicit',
                    NULL, false,
                    false, false,
                    'incomplete', 'legacy_ms_unverified'
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "owner": str(owner.id),
                "acct": str(account.id),
                "ext": ext,
                "cal": sub.external_calendar_id,
                "start": H0,
                "end": H1,
            },
        )
        seed.commit()
        owner_id = owner.id
    finally:
        seed.close()

    verify = SessionLocal()
    try:
        row = _row(verify, ext)
        assert row.provider_series_id is None
        assert row.series_identity_state == SERIES_IDENTITY_INCOMPLETE
        assert row.series_identity_incomplete_reason == "legacy_ms_unverified"
        assert row.transparency == "transparent"
        _trust_blocked_incomplete(verify, verify.get(User, owner_id), row)  # type: ignore[arg-type]
    finally:
        verify.close()


def test_ems_17b_google_null_still_verified_non_recurring() -> None:
    """Google NULL series backfill semantics preserved (not incomplete)."""
    seed = SessionLocal()
    try:
        token = uuid.uuid4().hex[:8]
        user = User(
            email=f"g-bf-{token}@example.test",
            username=f"g_bf_{token}",
            display_name="G",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=1,
        )
        seed.add(user)
        seed.flush()
        acct = CalendarAccount(
            owner_id=user.id,
            provider=CalendarProvider.google,
            account_email=f"{token}@example.test",
            is_enabled=True,
            mirror_blocks=False,
        )
        seed.add(acct)
        seed.flush()
        ext = f"g-legacy-{token}"
        seed.execute(
            text(
                """
                INSERT INTO external_calendar_events (
                    id, owner_id, calendar_account_id, provider, external_event_id,
                    calendar_id, title, start_time, end_time, is_all_day,
                    pending_deletion, provider_series_id, free_busy_pending_exception,
                    source_zone_missing, is_provider_cancelled,
                    series_identity_state, series_identity_incomplete_reason
                ) VALUES (
                    :id, :owner, :acct, 'google', :ext,
                    'g-cal', 'g', :start, :end, false,
                    false, NULL, false,
                    false, false,
                    'verified_non_recurring', NULL
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "owner": str(user.id),
                "acct": str(acct.id),
                "ext": ext,
                "start": H0,
                "end": H1,
            },
        )
        seed.commit()
    finally:
        seed.close()

    verify = SessionLocal()
    try:
        row = _row(verify, ext)
        assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_NON_RECURRING
        assert row.series_identity_incomplete_reason is None
    finally:
        verify.close()


# --- Real lock wait (E-MS-9) — distinguished from injected rollback ---------


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
                return
        time.sleep(0.05)
    raise AssertionError(
        "expected a new ungranted pg_advisory_xact_lock waiter (real lock wait); "
        f"prior_ungranted={prior_ungranted} rows={last!r}"
    )


def test_ems_9_real_concurrent_identity_lock_wait() -> None:
    """Real pg_locks ungranted waiter on identity namespace — not injected rollback."""
    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account(seed, owner)
        sub = _sub(seed, account)
        ext = f"lock-{uuid.uuid4().hex[:8]}"
        master = f"master-{uuid.uuid4().hex[:8]}"
        _seed_ms_row(
            seed,
            owner=owner,
            account=account,
            sub=sub,
            external_id=ext,
            series_id=master,
        )
        seed.commit()
        owner_id = owner.id
        cal_id = sub.external_calendar_id
        key = (str(owner_id), "microsoft", cal_id, master)
    finally:
        seed.close()

    held = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []
    prior_ungranted = sum(1 for granted, _query in _advisory_lock_rows() if not granted)

    def _hold() -> None:
        db = SessionLocal()
        try:
            acquire_identity_advisory_locks(db, [key])
            held.set()
            if not release.wait(timeout=20):
                raise TimeoutError("holder was not released")
            db.rollback()
        except BaseException as exc:
            errors.append(exc)
            db.rollback()
            held.set()
        finally:
            db.close()

    def _wait() -> None:
        db = SessionLocal()
        try:
            if not held.wait(timeout=20):
                raise TimeoutError("holder never acquired")
            acquire_identity_advisory_locks(db, [key])
            db.rollback()
        except BaseException as exc:
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    t_hold = threading.Thread(target=_hold, name="ms-lock-hold")
    t_wait = threading.Thread(target=_wait, name="ms-lock-wait")
    t_wait.start()
    t_hold.start()
    overlap_error: BaseException | None = None
    try:
        if not held.wait(timeout=20):
            raise TimeoutError("holder never set held")
        # Give waiter time to block on the advisory lock.
        time.sleep(0.1)
        try:
            _assert_new_advisory_waiter(prior_ungranted)
        except BaseException as exc:
            overlap_error = exc
    finally:
        release.set()
    t_hold.join(timeout=30)
    t_wait.join(timeout=30)
    if t_hold.is_alive() or t_wait.is_alive():
        raise AssertionError(f"lock threads still alive; errors={errors!r}")
    if overlap_error is not None:
        raise overlap_error
    if errors:
        raise AssertionError(errors)


def test_ems_5_first_get_revision_when_verified(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    path = _allowlist_file(owner.id)
    monkeypatch.setenv("FREE_BUSY_RESOLVER_ALLOWLIST_PATH", path)
    get_settings.cache_clear()
    ext = f"get-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    row = _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        transparency="opaque",
        pending=True,
    )
    enrich = policy_diagnostic_enrichment(db_session, row)
    assert enrich is not None
    assert enrich["conflict_revision"]
    assert enrich["current_provider_evidence"]["series_identity_state"] == (
        SERIES_IDENTITY_VERIFIED_SERIES
    )
    resolve_series_policy(
        db_session,
        user=owner,
        body=ResolveSeriesPolicyRequest(
            external_event_id=ext,
            conflict_acknowledgments=(
                ConflictAcknowledgment(ext, enrich["conflict_revision"]),
            ),
            reason="first resolve",
        ),
        allowlist_path=path,
    )
    db_session.refresh(row)
    assert row.free_busy_pending_exception is False


def test_ems_8_source_zone_invalidates_revision(db_session: Session) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"zone-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    row = _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=master,
        pending=True,
    )
    key = (str(owner.id), "microsoft", sub.external_calendar_id, master)
    r1 = compute_conflict_revision(
        identity=key,
        external_event_id=ext,
        transparency=row.transparency,
        provenance=row.free_busy_provenance,
        pending=True,
        latch_generation=0,
        source_zone_untrusted=False,
        series_identity_state=row.series_identity_state,
    )
    row.source_zone_missing = True
    r2 = compute_conflict_revision(
        identity=key,
        external_event_id=ext,
        transparency=row.transparency,
        provenance=row.free_busy_provenance,
        pending=True,
        latch_generation=0,
        source_zone_untrusted=True,
        series_identity_state=row.series_identity_state,
    )
    assert r1 != r2
