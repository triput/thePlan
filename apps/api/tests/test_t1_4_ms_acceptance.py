"""T1-4-MS acceptance — Microsoft series identity + E1 (Dex contract §9).

Requires ``T1A_REQUIRE_DISPOSABLE_DSN=1`` and disposable Postgres ``:5433``.
No live Graph. No household DB. Lock-wait tests are distinguished from injected
rollback fixtures (E-MS-13 / E-MS-16).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

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
    sync_account_events,
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
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

_FERNET = Fernet.generate_key().decode("utf-8")
_MIG040_DB = "theplan_t1a_mig040_disp"

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


def _ms_sync_settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        microsoft_client_id="t14ms-client",
        microsoft_client_secret="t14ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _account_with_tokens(db: Session, owner: User) -> CalendarAccount:
    cfg = _ms_sync_settings()
    acct = CalendarAccount(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        account_email=f"{uuid.uuid4().hex[:6]}@example.test",
        access_token_enc=encrypt_token(cfg, "access-token"),
        refresh_token_enc=encrypt_token(cfg, "refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(acct)
    db.flush()
    return acct


def test_ems_13_injected_ms_view_malformed_not_lock_wait() -> None:
    """Injected Malformed on B via ``_apply_subscription_ms_view`` only.

    Distinguished from real lock-wait (E-MS-9) and from production
    ``sync_account_events`` outer evidence (``test_ems_13_production_…``).
    Caller still rolls the session; this does **not** prove production-outer
    failure trust durability.
    """
    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account(seed, owner)
        sub = _sub(seed, account, cal_id=f"cal-inj-{uuid.uuid4().hex[:6]}")
        ext_a = f"inj-a-{uuid.uuid4().hex[:8]}"
        ext_b = f"inj-b-{uuid.uuid4().hex[:8]}"
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


def test_ems_13_production_sync_outer_rollback_verify_a(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production ``sync_account_events`` outer failure/rollback boundary.

    Mocked fetch: A would succeed, B Malformed. Fresh session: A+B pre-batch,
    durable subscription failure trust; then replay succeeds. Not lock-wait;
    not apply-helper-only injection.
    """
    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account_with_tokens(seed, owner)
        sub = _sub(seed, account, cal_id=f"cal-prod-{uuid.uuid4().hex[:6]}")
        ext_a = f"prod-a-{uuid.uuid4().hex[:8]}"
        ext_b = f"prod-b-{uuid.uuid4().hex[:8]}"
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
        owner_id = owner.id
    finally:
        seed.close()

    bad_batch = [
        _ms_event_payload(ext_a, master=master, show_as="free"),
        _ms_event_payload(ext_b, master={"bad": True}, show_as="free"),
    ]
    good_batch = [
        _ms_event_payload(ext_a, master=master, show_as="free"),
        _ms_event_payload(ext_b, master=master, show_as="free"),
    ]
    batches = iter([bad_batch, good_batch])

    monkeypatch.setattr(
        "app.services.microsoft_calendar.get_valid_access_token",
        lambda *_a, **_k: "ms-access",
    )
    monkeypatch.setattr(
        "app.services.microsoft_calendar.list_calendar_view",
        lambda *_a, **_k: next(batches),
    )

    cfg = _ms_sync_settings()
    t_min = H0 - timedelta(days=1)
    t_max = H1 + timedelta(days=1)

    fail_sess = SessionLocal()
    try:
        acct = fail_sess.get(CalendarAccount, account_id)
        assert acct is not None
        with pytest.raises(MicrosoftSeriesIdentityError):
            sync_account_events(
                fail_sess,
                settings=cfg,
                account=acct,
                time_min=t_min,
                time_max=t_max,
            )
        fail_sess.rollback()
    finally:
        fail_sess.close()

    verify = SessionLocal()
    try:
        a = _row(verify, ext_a)
        b = _row(verify, ext_b)
        assert a.transparency == "opaque"
        assert b.transparency == "opaque"
        assert a.series_identity_state == SERIES_IDENTITY_VERIFIED_SERIES
        assert a.provider_series_id == master
        sub_v = verify.get(CalendarSubscription, sub_id)
        assert sub_v is not None
        assert sub_v.coverage_success_at is None
        assert sub_v.coverage_last_failure_cause == "microsoft_apply_ms_view_failed"
        assert sub_v.coverage_last_failure_at is not None
    finally:
        verify.close()

    replay = SessionLocal()
    try:
        acct = replay.get(CalendarAccount, account_id)
        assert acct is not None
        n = sync_account_events(
            replay,
            settings=cfg,
            account=acct,
            time_min=t_min,
            time_max=t_max,
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
        assert sub2.coverage_last_failure_cause is None
        _ = owner_id  # seeded owner retained for freshness quals if needed
    finally:
        verify2.close()


def test_ems_14_full_incremental_e1_no_partial_identity() -> None:
    """E1 owning savepoint: Malformed **and** False/unresolvable mid-batch.

    Apply helpers own rollback — caller may commit the outer session after
    failure without leaving A durable or advancing cursor. Fresh sessions.
    """
    # --- Malformed path (full + incremental) ---
    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account(seed, owner)
        sub = _sub(seed, account, cal_id=f"cal-e1m-{uuid.uuid4().hex[:6]}")
        prior_cursor = f"cursor-prior-{uuid.uuid4().hex[:8]}"
        sub.sync_cursor = prior_cursor
        seed.commit()
        account_id = account.id
        sub_id = sub.id
    finally:
        seed.close()

    ext_a = f"full-a-{uuid.uuid4().hex[:8]}"
    ext_b = f"full-b-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    malformed_events = [
        _ms_event_payload(ext_a, master=master),
        _ms_event_payload(ext_b, master={"nope": 1}),
    ]

    apply_sess = SessionLocal()
    try:
        acct = apply_sess.get(CalendarAccount, account_id)
        sub_row = apply_sess.get(CalendarSubscription, sub_id)
        assert acct is not None and sub_row is not None
        with pytest.raises(MicrosoftSeriesIdentityError):
            _apply_subscription_full(
                apply_sess,
                account=acct,
                subscription=sub_row,
                events=malformed_events,
                next_delta_link="cursor-must-not-stick",
                time_min=H0 - timedelta(days=1),
                time_max=H1 + timedelta(days=1),
                now=datetime.now(UTC),
                event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
            )
        # Owning boundary rolled the apply savepoint — outer commit must not
        # durably mint A or advance cursor.
        apply_sess.commit()
    finally:
        apply_sess.close()

    verify = SessionLocal()
    try:
        assert (
            verify.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.external_event_id == ext_a)
            .one_or_none()
        ) is None
        sub_v = verify.get(CalendarSubscription, sub_id)
        assert sub_v is not None
        assert sub_v.sync_cursor == prior_cursor
    finally:
        verify.close()

    apply_incr = SessionLocal()
    try:
        acct = apply_incr.get(CalendarAccount, account_id)
        sub_row = apply_incr.get(CalendarSubscription, sub_id)
        assert acct is not None and sub_row is not None
        with pytest.raises(MicrosoftSeriesIdentityError):
            _apply_subscription_incremental(
                apply_incr,
                account=acct,
                subscription=sub_row,
                events=malformed_events,
                next_delta_link="cursor-must-not-stick-incr",
                now=datetime.now(UTC),
                event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
            )
        apply_incr.commit()
    finally:
        apply_incr.close()

    verify_i = SessionLocal()
    try:
        assert (
            verify_i.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.external_event_id == ext_a)
            .one_or_none()
        ) is None
        sub_i = verify_i.get(CalendarSubscription, sub_id)
        assert sub_i is not None
        assert sub_i.sync_cursor == prior_cursor
    finally:
        verify_i.close()

    # --- False / unresolvable path: A gains identity, B new+unusable bounds ---
    seed2 = SessionLocal()
    try:
        owner2, _ = _owner(seed2)
        account2 = _account(seed2, owner2)
        sub2 = _sub(seed2, account2, cal_id=f"cal-e1f-{uuid.uuid4().hex[:6]}")
        prior2 = f"cursor-false-{uuid.uuid4().hex[:8]}"
        sub2.sync_cursor = prior2
        seed2.commit()
        account2_id = account2.id
        sub2_id = sub2.id
    finally:
        seed2.close()

    ext_a2 = f"false-a-{uuid.uuid4().hex[:8]}"
    ext_b2 = f"false-b-{uuid.uuid4().hex[:8]}"
    master2 = f"master-{uuid.uuid4().hex[:8]}"
    false_events = [
        _ms_event_payload(ext_a2, master=master2),
        {
            "id": ext_b2,
            "type": "occurrence",
            "seriesMasterId": master2,
            "showAs": "busy",
            "start": {"dateTime": "not-a-graph-datetime", "timeZone": "UTC"},
            "end": {"dateTime": "also-not-valid", "timeZone": "UTC"},
        },
    ]

    apply_f = SessionLocal()
    try:
        acct = apply_f.get(CalendarAccount, account2_id)
        sub_row = apply_f.get(CalendarSubscription, sub2_id)
        assert acct is not None and sub_row is not None
        with pytest.raises(ApiError) as ei:
            _apply_subscription_full(
                apply_f,
                account=acct,
                subscription=sub_row,
                events=false_events,
                next_delta_link="cursor-false-must-not-stick",
                time_min=H0 - timedelta(days=1),
                time_max=H1 + timedelta(days=1),
                now=datetime.now(UTC),
                event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
            )
        assert ei.value.content["code"] == "MS_VIEW_ITEM_UNRESOLVABLE"
        apply_f.commit()
    finally:
        apply_f.close()

    verify_f = SessionLocal()
    try:
        assert (
            verify_f.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.external_event_id == ext_a2)
            .one_or_none()
        ) is None
        assert (
            verify_f.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.external_event_id == ext_b2)
            .one_or_none()
        ) is None
        sub_f = verify_f.get(CalendarSubscription, sub2_id)
        assert sub_f is not None
        assert sub_f.sync_cursor == prior2
    finally:
        verify_f.close()

    apply_fi = SessionLocal()
    try:
        acct = apply_fi.get(CalendarAccount, account2_id)
        sub_row = apply_fi.get(CalendarSubscription, sub2_id)
        assert acct is not None and sub_row is not None
        with pytest.raises(ApiError) as ei:
            _apply_subscription_incremental(
                apply_fi,
                account=acct,
                subscription=sub_row,
                events=false_events,
                next_delta_link="cursor-false-incr-no",
                now=datetime.now(UTC),
                event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
            )
        assert ei.value.content["code"] == "MS_VIEW_ITEM_UNRESOLVABLE"
        apply_fi.commit()
    finally:
        apply_fi.close()

    verify_fi = SessionLocal()
    try:
        assert (
            verify_fi.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.external_event_id == ext_a2)
            .one_or_none()
        ) is None
        sub_fi = verify_fi.get(CalendarSubscription, sub2_id)
        assert sub_fi is not None
        assert sub_fi.sync_cursor == prior2
    finally:
        verify_fi.close()


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


# --- Migration backfill (E-MS-17) — real 040 on dedicated disposable DB -----


def _mig040_admin_connect():
    import psycopg

    return psycopg.connect("postgresql://t1a@127.0.0.1:5433/postgres")


def _mig040_dsn() -> str:
    return f"postgresql+psycopg://t1a@127.0.0.1:5433/{_MIG040_DB}"


def _mig040_alembic(revision: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = _mig040_dsn()
    env["SEED_DEMO_USER"] = "false"
    api_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [str(api_root / ".venv" / "Scripts" / "python.exe"), "-m", "alembic", "upgrade", revision],
        cwd=str(api_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"alembic upgrade {revision} failed ({proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )


def test_ems_17_real_migration_040_provider_aware_backfill() -> None:
    """Run actual migration 040 against pre-040 fixtures on a dedicated DB.

    Does **not** downgrade the shared ``theplan_t1a_test`` database.
    """
    admin = _mig040_admin_connect()
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{_MIG040_DB}" WITH (FORCE)')
            cur.execute(f'CREATE DATABASE "{_MIG040_DB}"')
    finally:
        admin.close()

    try:
        _mig040_alembic("039_free_busy_series_policy")

        eng = create_engine(_mig040_dsn())
        try:
            with eng.begin() as conn:
                # Confirm pre-040: identity columns absent.
                cols = {
                    r[0]
                    for r in conn.execute(
                        text(
                            """
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'external_calendar_events'
                            """
                        )
                    )
                }
                assert "series_identity_state" not in cols

                owner_g = str(uuid.uuid4())
                owner_m = str(uuid.uuid4())
                acct_g = str(uuid.uuid4())
                acct_m = str(uuid.uuid4())
                for oid, email, uname in (
                    (owner_g, "g-mig@example.test", "g_mig040"),
                    (owner_m, "m-mig@example.test", "m_mig040"),
                ):
                    conn.execute(
                        text(
                            """
                            INSERT INTO users (
                                id, email, username, display_name,
                                is_admin, is_disabled, must_change_password, session_epoch
                            ) VALUES (
                                :id, :email, :uname, 'mig',
                                false, false, false, 1
                            )
                            """
                        ),
                        {"id": oid, "email": email, "uname": uname},
                    )
                conn.execute(
                    text(
                        """
                        INSERT INTO calendar_accounts (
                            id, owner_id, provider, account_email, is_enabled, mirror_blocks
                        ) VALUES
                        (:g, :og, 'google', 'g@example.test', true, false),
                        (:m, :om, 'microsoft', 'm@example.test', true, false)
                        """
                    ),
                    {"g": acct_g, "og": owner_g, "m": acct_m, "om": owner_m},
                )

                history = (
                    '[{"at":"2026-10-19T12:00:00Z","sync_run_id":"pre040",'
                    '"from_transparency":null,"from_provenance":null,'
                    '"to_transparency":"transparent","to_provenance":"provider_explicit"}]'
                )
                fixtures = [
                    # Google NULL → verified_non_recurring
                    ("g-null", acct_g, owner_g, "google", None, False, "opaque", history),
                    # Google non-NULL → verified_series
                    ("g-ser", acct_g, owner_g, "google", "g-series-1", False, "opaque", history),
                    # MS NULL + free storage + pending → incomplete / legacy_ms_unverified
                    (
                        "m-null",
                        acct_m,
                        owner_m,
                        "microsoft",
                        None,
                        True,
                        "transparent",
                        history,
                    ),
                    # MS seeded series retained + latch-style pending
                    (
                        "m-seed",
                        acct_m,
                        owner_m,
                        "microsoft",
                        "ms-series-kept",
                        True,
                        "transparent",
                        history,
                    ),
                ]
                for ext, acct, owner, prov, series, pending, transp, hist in fixtures:
                    conn.execute(
                        text(
                            """
                            INSERT INTO external_calendar_events (
                                id, owner_id, calendar_account_id, provider,
                                external_event_id, calendar_id, title,
                                start_time, end_time, is_all_day,
                                pending_deletion, transparency, free_busy_provenance,
                                free_busy_change_history,
                                provider_series_id, free_busy_pending_exception,
                                source_zone_missing, is_provider_cancelled
                            ) VALUES (
                                :id, :owner, :acct, :prov,
                                :ext, :cal, :title,
                                :start, :end, false,
                                false, :transp, 'provider_explicit',
                                CAST(:hist AS jsonb),
                                :series, :pending,
                                false, false
                            )
                            """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "owner": owner,
                            "acct": acct,
                            "prov": prov,
                            "ext": ext,
                            "cal": "cal-mig",
                            "title": ext,
                            "start": H0,
                            "end": H1,
                            "transp": transp,
                            "hist": hist,
                            "series": series,
                            "pending": pending,
                        },
                    )

                # Policy latch for MS seeded series — must survive 040.
                policy_id = str(uuid.uuid4())
                conn.execute(
                    text(
                        """
                        INSERT INTO free_busy_series_policies (
                            id, owner_id, provider, calendar_id, provider_series_id,
                            mapping, conflict_pending_latched, latch_generation
                        ) VALUES (
                            :id, :owner, 'microsoft', 'cal-mig', 'ms-series-kept',
                            'free', true, 3
                        )
                        """
                    ),
                    {"id": policy_id, "owner": owner_m},
                )
        finally:
            eng.dispose()

        _mig040_alembic("040_series_identity_state")

        eng2 = create_engine(_mig040_dsn())
        SessionMig = sessionmaker(bind=eng2)
        try:
            with eng2.connect() as conn:
                rows = {
                    r.external_event_id: r
                    for r in conn.execute(
                        text(
                            """
                            SELECT external_event_id, provider, provider_series_id,
                                   series_identity_state, series_identity_incomplete_reason,
                                   free_busy_pending_exception, transparency,
                                   free_busy_change_history
                            FROM external_calendar_events
                            """
                        )
                    )
                }
                assert rows["g-null"].series_identity_state == (
                    SERIES_IDENTITY_VERIFIED_NON_RECURRING
                )
                assert rows["g-null"].series_identity_incomplete_reason is None
                assert rows["g-ser"].series_identity_state == SERIES_IDENTITY_VERIFIED_SERIES
                assert rows["g-ser"].provider_series_id == "g-series-1"

                assert rows["m-null"].series_identity_state == SERIES_IDENTITY_INCOMPLETE
                assert rows["m-null"].series_identity_incomplete_reason == (
                    "legacy_ms_unverified"
                )
                assert rows["m-null"].provider_series_id is None
                assert rows["m-null"].free_busy_pending_exception is True
                assert rows["m-null"].transparency == "transparent"
                assert rows["m-null"].free_busy_change_history is not None

                assert rows["m-seed"].series_identity_state == SERIES_IDENTITY_INCOMPLETE
                assert rows["m-seed"].series_identity_incomplete_reason == (
                    "legacy_ms_unverified_seeded"
                )
                assert rows["m-seed"].provider_series_id == "ms-series-kept"
                assert rows["m-seed"].free_busy_pending_exception is True

                pol = conn.execute(
                    text(
                        """
                        SELECT conflict_pending_latched, latch_generation
                        FROM free_busy_series_policies
                        WHERE provider_series_id = 'ms-series-kept'
                        """
                    )
                ).one()
                assert pol.conflict_pending_latched is True
                assert pol.latch_generation == 3

            # Verified MS ingest recovery on post-040 incomplete row.
            mig = SessionMig()
            try:
                acct = (
                    mig.query(CalendarAccount)
                    .filter(CalendarAccount.provider == CalendarProvider.microsoft)
                    .one()
                )
                sub = CalendarSubscription(
                    owner_id=acct.owner_id,
                    calendar_account_id=acct.id,
                    external_calendar_id="cal-mig",
                    summary="mig",
                    role=CalendarSubscriptionRole.primary,
                    is_enabled=True,
                    provider_timezone="UTC",
                )
                mig.add(sub)
                mig.flush()
                ok = _upsert_external_event(
                    mig,
                    account=acct,
                    subscription=sub,
                    event=_ms_event_payload(
                        "m-null",
                        type="singleInstance",
                        include_master_key=False,
                        show_as="busy",
                    ),
                    now=datetime.now(UTC),
                    sync_run_id="mig040-recover",
                    event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
                )
                assert ok is True
                mig.commit()
                row = (
                    mig.query(ExternalCalendarEvent)
                    .filter(ExternalCalendarEvent.external_event_id == "m-null")
                    .one()
                )
                assert row.series_identity_state == SERIES_IDENTITY_VERIFIED_NON_RECURRING
                assert row.series_identity_incomplete_reason is None
                assert row.provider_series_id is None
            finally:
                mig.close()
        finally:
            eng2.dispose()
    finally:
        admin = _mig040_admin_connect()
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(f'DROP DATABASE IF EXISTS "{_MIG040_DB}" WITH (FORCE)')
        finally:
            admin.close()


def test_ems_none_snapshot_post_lock_series_acquire_aborts(
    db_session: Session,
) -> None:
    """Previously non-series row acquires series under lock ⇒ drift (None≠key).

    Payload is KnownSeries (locks new master). Pre-lock snapshot is None; a
    concurrent writer attaches series before for_update reload. Revalidation
    must abort — not skip because ``identity_snapshot is None``.
    """
    from app.services import microsoft_calendar as ms_mod

    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account)
    ext = f"none-snap-{uuid.uuid4().hex[:8]}"
    master = f"master-{uuid.uuid4().hex[:8]}"
    concurrent = f"concurrent-{uuid.uuid4().hex[:8]}"
    _seed_ms_row(
        db_session,
        owner=owner,
        account=account,
        sub=sub,
        external_id=ext,
        series_id=None,
        state=SERIES_IDENTITY_VERIFIED_NON_RECURRING,
        transparency="opaque",
    )
    db_session.flush()

    original = ms_mod._find_external_event

    def _wrapped(db, *, owner_id, external_id, for_update=False):
        row = original(
            db, owner_id=owner_id, external_id=external_id, for_update=for_update
        )
        if for_update and row is not None and row.provider_series_id is None:
            row.provider_series_id = concurrent
            db.flush()
        return row

    ms_mod._find_external_event = _wrapped  # type: ignore[assignment]
    try:
        with pytest.raises(UpsertPostLockIdentityDriftError):
            _upsert_external_event(
                db_session,
                account=account,
                subscription=sub,
                event=_ms_event_payload(ext, master=master, show_as="busy"),
                now=datetime.now(UTC),
                sync_run_id="none-snap",
                event_fetch_context=MS_EVENT_LIST_FETCH_CONTEXT,
            )
    finally:
        ms_mod._find_external_event = original  # type: ignore[assignment]


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
