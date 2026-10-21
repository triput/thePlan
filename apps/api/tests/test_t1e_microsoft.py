"""T1-E Microsoft ms_view acceptance (E1–E10, E14–E16, E19–E20, E22).

Disposable Postgres only (theplan-t1a-postgres, 127.0.0.1:5433). Graph is mocked.
Gate cases E11–E13 live in test_t1e_gate.py. E17/E18/E21 are gate/Apply behavior.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Iterator
from unittest.mock import MagicMock
from uuid import UUID

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings
from app.db import SessionLocal, engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    ExternalCalendarEvent,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.calendar_freshness import (
    evaluate_calendar_freshness,
    required_coverage_window,
)
from app.scheduler.free_busy import evaluate_busy_input_trust
from app.services import microsoft_calendar as ms_cal
from app.services.token_crypto import decrypt_token, encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
_FERNET = Fernet.generate_key().decode("utf-8")


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["host_ip"] == "127.0.0.1"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


@pytest.fixture(autouse=True)
def _reset_pagination_knobs() -> Iterator[None]:
    ms_cal.pagination_max_pages = None
    yield
    ms_cal.pagination_max_pages = None


def _settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        microsoft_client_id="t1e-ms-client",
        microsoft_client_secret="t1e-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _owner(db: Session) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"t1e-{token}@example.test",
        username=f"t1e_{token}",
        display_name="T1E acceptance",
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        session_epoch=0,
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
    cfg = _settings()
    account = CalendarAccount(
        owner_id=owner.id,
        provider=CalendarProvider.microsoft,
        account_email=f"t1e-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc=encrypt_token(cfg, "access-token"),
        refresh_token_enc=encrypt_token(cfg, "refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=False,
        last_synced_at=None,
    )
    db.add(account)
    db.flush()
    return account


def _sub(
    db: Session,
    account: CalendarAccount,
    *,
    calendar_id: str,
    summary: str,
    cursor: str | None = None,
    enabled: bool = True,
) -> CalendarSubscription:
    row = CalendarSubscription(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary=summary,
        role=CalendarSubscriptionRole.primary,
        is_enabled=enabled,
        sync_cursor=cursor,
        provider_timezone="UTC",
    )
    db.add(row)
    db.flush()
    return row


def _wide_bounds(settings: UserSettings, now: datetime) -> tuple[datetime, datetime]:
    start, end = required_coverage_window(settings, now)
    return start - timedelta(hours=2), end + timedelta(hours=2)


def _mint_ms(
    sub: CalendarSubscription,
    *,
    now: datetime,
    start: datetime,
    end: datetime,
    generation: int = 1,
) -> None:
    sub.coverage_window_start = start
    sub.coverage_window_end = end
    sub.coverage_mode = "ms_view"
    sub.coverage_success_at = now
    sub.coverage_fetched_at = now
    sub.coverage_pagination_complete = True
    sub.coverage_active_generation = generation
    sub.coverage_success_generation = generation
    sub.coverage_show_deleted = None
    sub.coverage_single_events = None
    sub.coverage_page_count = 1
    sub.coverage_item_count = 0
    sub.coverage_token_fingerprint = None
    sub.coverage_last_failure_at = None
    sub.coverage_last_failure_cause = None


def _ms_event(
    event_id: str,
    start: datetime,
    end: datetime,
    *,
    subject: str | None = None,
    show_as: str | None = "busy",
    cancelled: bool = False,
    removed: bool = False,
    include_times: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {"id": event_id, "subject": subject or event_id}
    if include_times:
        body["start"] = {
            "dateTime": start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "UTC",
        }
        body["end"] = {
            "dateTime": end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "UTC",
        }
    if show_as is not None:
        body["showAs"] = show_as
    if cancelled:
        body["isCancelled"] = True
    if removed:
        body["@removed"] = {"reason": "deleted"}
    return body


def _patch_clock(monkeypatch: pytest.MonkeyPatch, fixed: datetime) -> None:
    """Freeze ``datetime.now`` without replacing ``fromisoformat`` and friends."""
    real = ms_cal.datetime

    class _FixedNow(real):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed.astimezone(tz)
            return fixed

    monkeypatch.setattr(ms_cal, "datetime", _FixedNow)


def _patch_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ms_cal, "get_valid_access_token", lambda *_a, **_k: "ms-access")


def _patch_view(monkeypatch: pytest.MonkeyPatch, view: Any) -> None:
    monkeypatch.setattr(ms_cal, "list_calendar_view", view)


def _no_delta(*_a: Any, **_k: Any) -> None:
    raise AssertionError("bounded ms_view strategy must not call delta helpers")


def _sync(db: Session, account: CalendarAccount, start: datetime, end: datetime) -> int:
    return ms_cal.sync_account_events(
        db,
        settings=_settings(),
        account=account,
        time_min=start,
        time_max=end,
    )


def _causes(trust) -> set[str]:
    return {d.cause for d in trust.blocking_diagnostics}


def _row(db: Session, external_id: str) -> ExternalCalendarEvent | None:
    return (
        db.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == external_id)
        .one_or_none()
    )


def _seed_busy(
    db: Session,
    *,
    account: CalendarAccount,
    calendar_id: str,
    external_id: str,
    start: datetime,
    end: datetime,
    pending_deletion: bool = False,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        provider=CalendarProvider.microsoft,
        external_event_id=external_id,
        calendar_id=calendar_id,
        title=external_id,
        start_time=start,
        end_time=end,
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        pending_deletion=pending_deletion,
        is_provider_cancelled=False,
        is_all_day=False,
        source_timezone="UTC",
        free_busy_change_history=[
            {
                "at": "2026-10-20T12:00:00Z",
                "sync_run_id": "seed",
                "from_transparency": None,
                "from_provenance": None,
                "to_transparency": "opaque",
                "to_provenance": "provider_explicit",
            }
        ],
    )
    db.add(row)
    db.flush()
    return row


@dataclass(frozen=True)
class _Committed:
    owner_id: UUID
    account_id: UUID
    sub_ids: tuple[UUID, ...]
    prior_display: str
    summaries: dict[UUID, str]
    cursors: dict[UUID, str | None]
    mint_now: datetime
    window_start: datetime
    window_end: datetime


def _cleanup(owner_id: UUID) -> None:
    cleanup = SessionLocal()
    try:
        sub_ids = [
            row.id
            for row in cleanup.query(CalendarSubscription)
            .filter(CalendarSubscription.owner_id == owner_id)
            .all()
        ]
        if sub_ids:
            cleanup.query(CalendarSubscriptionRefreshFailure).filter(
                CalendarSubscriptionRefreshFailure.subscription_id.in_(sub_ids)
            ).delete(synchronize_session=False)
        cleanup.query(ExternalCalendarEvent).filter(
            ExternalCalendarEvent.owner_id == owner_id
        ).delete(synchronize_session=False)
        cleanup.query(CalendarSubscription).filter(
            CalendarSubscription.owner_id == owner_id
        ).delete(synchronize_session=False)
        cleanup.query(CalendarAccount).filter(CalendarAccount.owner_id == owner_id).delete(
            synchronize_session=False
        )
        cleanup.query(UserSettings).filter(UserSettings.owner_id == owner_id).delete(
            synchronize_session=False
        )
        cleanup.query(User).filter(User.id == owner_id).delete(synchronize_session=False)
        cleanup.commit()
    finally:
        cleanup.close()


@contextmanager
def _committed_ms(
    caller: Session,
    *,
    calendars: list[tuple[str, str]],
    cursor: str | None = "prior-cursor",
    mint: bool = True,
) -> Iterator[_Committed]:
    """Commit MS account + enabled subs on SessionLocal so autonomous failure can see them."""
    mint_now = datetime.now(UTC).replace(microsecond=0)
    seed = SessionLocal()
    owner_id: UUID | None = None
    try:
        owner, settings = _owner(seed)
        window_start, window_end = _wide_bounds(settings, mint_now)
        account = _account(seed, owner)
        subs: list[CalendarSubscription] = []
        for calendar_id, summary in calendars:
            sub = _sub(
                seed,
                account,
                calendar_id=calendar_id,
                summary=summary,
                cursor=cursor,
            )
            if mint:
                _mint_ms(sub, now=mint_now, start=window_start, end=window_end)
            subs.append(sub)
        seed.commit()
        owner_id = owner.id
        yield _Committed(
            owner_id=owner.id,
            account_id=account.id,
            sub_ids=tuple(sub.id for sub in subs),
            prior_display=owner.display_name,
            summaries={sub.id: sub.summary or "" for sub in subs},
            cursors={sub.id: sub.sync_cursor for sub in subs},
            mint_now=mint_now,
            window_start=window_start,
            window_end=window_end,
        )
    finally:
        seed.close()
        try:
            caller.rollback()
            caller.expire_all()
        except Exception:
            pass
        if owner_id is not None:
            _cleanup(owner_id)


def _load(db: Session, fx: _Committed) -> tuple[User, UserSettings, CalendarAccount, list[CalendarSubscription]]:
    owner = db.get(User, fx.owner_id)
    settings = db.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
    account = db.get(CalendarAccount, fx.account_id)
    subs = [db.get(CalendarSubscription, sub_id) for sub_id in fx.sub_ids]
    assert owner is not None and account is not None
    assert all(sub is not None for sub in subs)
    return owner, settings, account, subs  # type: ignore[return-value]


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    transport = httpx.MockTransport(handler)
    real = httpx.Client

    def _factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(ms_cal.httpx, "Client", _factory)


# --- collector ----------------------------------------------------------------


def test_calendar_view_truncated_next_link_does_not_follow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "value": [{"id": "page-1"}],
                "@odata.nextLink": (
                    "https://graph.microsoft.com/v1.0/me/calendars/cal/calendarView?$skiptoken=2"
                ),
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/should-not-stick",
            },
        )

    ms_cal.pagination_max_pages = 1
    _patch_httpx(monkeypatch, handler)
    start = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    items, page_count, complete = ms_cal.list_calendar_view(
        "tok", "cal", time_min=start, time_max=start + timedelta(hours=1)
    )
    assert calls["n"] == 1
    assert items == [{"id": "page-1"}]
    assert page_count == 1
    assert complete is False


def test_calendar_view_drained_two_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [
        {
            "value": [{"id": "a"}],
            "@odata.nextLink": (
                "https://graph.microsoft.com/v1.0/me/calendars/cal/calendarView?$skiptoken=2"
            ),
        },
        {"value": [{"id": "b"}]},
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payloads.pop(0))

    _patch_httpx(monkeypatch, handler)
    start = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    items, page_count, complete = ms_cal.list_calendar_view(
        "tok", "cal", time_min=start, time_max=start + timedelta(hours=1)
    )
    assert [item["id"] for item in items] == ["a", "b"]
    assert page_count == 2
    assert complete is True


# --- E1 / E2 ------------------------------------------------------------------


def test_e1_populated_cursor_still_pulls_calendar_view(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    cursor = "https://graph.microsoft.com/v1.0/me/calendars/cal/calendarView/delta?$deltatoken=old"
    sub = _sub(db_session, account, calendar_id="cal-e1", summary="E1", cursor=cursor)
    start = window_start + timedelta(hours=3)
    monkeypatch.setattr(ms_cal, "list_calendar_events", _no_delta)
    monkeypatch.setattr(ms_cal, "list_calendar_events_incremental", _no_delta)
    _patch_token(monkeypatch)
    _patch_view(
        monkeypatch,
        lambda *_a, **_k: [
            _ms_event("e1-evt", start, start + timedelta(hours=1), subject="View only")
        ],
    )
    assert _sync(db_session, account, window_start, window_end) == 1
    db_session.refresh(sub)
    assert sub.sync_cursor == cursor
    assert sub.coverage_mode == "ms_view"
    assert sub.coverage_token_fingerprint is None


def test_e2_drained_view_mints_ms_view(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-e2", summary="E2", cursor="leave-me")
    start = window_start + timedelta(hours=4)
    _patch_token(monkeypatch)
    _patch_view(
        monkeypatch,
        lambda *_a, **_k: (
            [_ms_event("e2-evt", start, start + timedelta(hours=1), subject="Standup")],
            2,
            True,
        ),
    )
    assert _sync(db_session, account, window_start, window_end) == 1
    db_session.refresh(sub)
    assert sub.coverage_mode == "ms_view"
    assert sub.coverage_success_at == now
    assert sub.coverage_fetched_at == now
    assert sub.coverage_show_deleted is None
    assert sub.coverage_single_events is None
    assert sub.coverage_pagination_complete is True
    assert sub.coverage_page_count == 2
    assert sub.coverage_item_count == 1
    assert sub.coverage_token_fingerprint is None
    assert sub.coverage_success_generation == sub.coverage_active_generation
    assert sub.sync_cursor == "leave-me"
    trust = evaluate_calendar_freshness(db_session, owner.id, settings, now)
    assert trust.ok is True
    later = evaluate_calendar_freshness(db_session, owner.id, settings, now + timedelta(seconds=30))
    assert later.ok is True
    db_session.refresh(sub)
    assert sub.coverage_success_at == now


# --- E3–E5 / E14 durable failure ----------------------------------------------


def test_e3_truncated_view_does_not_mint(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-e3", "E3")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)
        _patch_view(
            monkeypatch,
            lambda *_a, **_k: (
                [_ms_event("e3", fx.window_start, fx.window_start + timedelta(hours=1))],
                1,
                False,
            ),
        )
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "CALENDAR_PAGINATION_INCOMPLETE"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.sync_cursor == fx.cursors[sub.id]
            assert durable.coverage_last_failure_at is not None
            assert durable.coverage_last_failure_cause == "calendar_pagination_incomplete"
            # Column commit runs begin_subscription_refresh, which supersedes the
            # sidecar. Sidecar remains only when that UPDATE times out (E15c).
            sidecar = (
                verify.query(CalendarSubscriptionRefreshFailure)
                .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub.id)
                .one_or_none()
            )
            if sidecar is not None:
                assert sidecar.cause == "calendar_pagination_incomplete"
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_e4_missing_id_does_not_mint(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-e4", "E4")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        start = fx.window_start + timedelta(hours=2)
        _patch_token(monkeypatch)
        _patch_view(
            monkeypatch,
            lambda *_a, **_k: [
                {"subject": "no id", "showAs": "busy", "start": {}, "end": {}},
                _ms_event("e4-ok", start, start + timedelta(hours=1)),
            ],
        )
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MS_VIEW_ITEM_UNRESOLVABLE"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "microsoft_apply_ms_view_failed"
            assert (
                verify.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.external_event_id == "e4-ok")
                .count()
                == 0
            )
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_e5_upsert_false_does_not_mint(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-e5", "E5")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        start = fx.window_start + timedelta(hours=2)
        bad = _ms_event("e5-bad", start + timedelta(hours=2), start + timedelta(hours=1))
        _patch_token(monkeypatch)
        _patch_view(
            monkeypatch,
            lambda *_a, **_k: [
                _ms_event("e5-ok", start, start + timedelta(hours=1)),
                bad,
            ],
        )
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MS_VIEW_ITEM_UNRESOLVABLE"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "microsoft_apply_ms_view_failed"
        finally:
            verify.close()


def test_e14_mid_apply_failure_clears_prior_success(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-e14", "E14")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        start = fx.window_start + timedelta(hours=2)

        def _boom(*_a: Any, **_k: Any) -> bool:
            raise RuntimeError("apply blew up")

        _patch_token(monkeypatch)
        _patch_view(
            monkeypatch,
            lambda *_a, **_k: [_ms_event("e14", start, start + timedelta(hours=1))],
        )
        monkeypatch.setattr(ms_cal, "_upsert_external_event", _boom)
        with pytest.raises(RuntimeError, match="apply blew up"):
            _sync(db_session, account, fx.window_start, fx.window_end)
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "microsoft_apply_ms_view_failed"
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


# --- E6–E10 retention / classification ----------------------------------------


def test_e6_cancelled_non_tombstone_is_soft_cancelled(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-e6", summary="E6")
    start = window_start + timedelta(hours=5)
    kept = _seed_busy(
        db_session,
        account=account,
        calendar_id="cal-e6",
        external_id="e6-cancel",
        start=start,
        end=start + timedelta(hours=1),
    )
    removed = _seed_busy(
        db_session,
        account=account,
        calendar_id="cal-e6",
        external_id="e6-removed",
        start=start + timedelta(hours=2),
        end=start + timedelta(hours=3),
    )
    kept_id, removed_id = kept.id, removed.id
    _patch_token(monkeypatch)
    _patch_view(
        monkeypatch,
        lambda *_a, **_k: [
            _ms_event("e6-cancel", start, start + timedelta(hours=1), cancelled=True),
            _ms_event(
                "e6-removed",
                start + timedelta(hours=2),
                start + timedelta(hours=3),
                removed=True,
            ),
        ],
    )
    _sync(db_session, account, window_start, window_end)
    db_session.refresh(sub)
    assert sub.coverage_mode == "ms_view"
    for external_id, row_id in (("e6-cancel", kept_id), ("e6-removed", removed_id)):
        row = _row(db_session, external_id)
        assert row is not None
        assert row.id == row_id
        assert row.is_provider_cancelled is True
        assert row.pending_deletion is False
    busy_ids = {
        row.external_event_id
        for row in db_session.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.owner_id == owner.id,
            *ExternalCalendarEvent.immovable_busy_clause(),
        )
        .all()
    }
    assert "e6-cancel" not in busy_ids
    assert "e6-removed" not in busy_ids


def test_e7_unseen_in_window_row_is_soft_cancelled_not_deleted(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="cal-e7", summary="E7")
    start = window_start + timedelta(hours=6)
    seeded = _seed_busy(
        db_session,
        account=account,
        calendar_id="cal-e7",
        external_id="e7-gone",
        start=start,
        end=start + timedelta(minutes=30),
    )
    seeded_id = seeded.id
    history = list(seeded.free_busy_change_history or [])
    _patch_token(monkeypatch)
    _patch_view(monkeypatch, lambda *_a, **_k: [])
    assert _sync(db_session, account, window_start, window_end) == 0
    row = _row(db_session, "e7-gone")
    assert row is not None
    assert row.id == seeded_id
    assert row.is_provider_cancelled is True
    assert row.pending_deletion is False
    assert row.free_busy_change_history == history
    assert (
        db_session.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.external_event_id == "e7-gone",
            *ExternalCalendarEvent.immovable_busy_clause(),
        )
        .count()
        == 0
    )


def test_e8_pending_deletion_tombstone_is_not_hard_deleted(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-e8", summary="E8")
    start = window_start + timedelta(hours=3)
    tomb = _seed_busy(
        db_session,
        account=account,
        calendar_id="cal-e8",
        external_id="e8-tomb",
        start=start,
        end=start + timedelta(hours=1),
        pending_deletion=True,
    )
    tomb_id = tomb.id
    _patch_token(monkeypatch)
    monkeypatch.setattr(
        ms_cal,
        "delete_microsoft_event",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("remote delete failed")),
    )
    _patch_view(
        monkeypatch,
        lambda *_a, **_k: [
            _ms_event("e8-tomb", start, start + timedelta(hours=1), removed=True),
            _ms_event("e8-live", start + timedelta(hours=2), start + timedelta(hours=3)),
        ],
    )
    assert _sync(db_session, account, window_start, window_end) == 1
    db_session.refresh(sub)
    assert sub.coverage_mode == "ms_view"
    assert sub.coverage_success_at is not None
    row = _row(db_session, "e8-tomb")
    assert row is not None
    assert row.id == tomb_id
    assert row.pending_deletion is True


def test_e9_empty_drained_window_mints(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-e9", summary="E9")
    _patch_token(monkeypatch)
    _patch_view(monkeypatch, lambda *_a, **_k: [])
    assert _sync(db_session, account, window_start, window_end) == 0
    db_session.refresh(sub)
    assert sub.coverage_mode == "ms_view"
    assert sub.coverage_success_at == now
    assert sub.coverage_item_count == 0
    assert sub.coverage_pagination_complete is True
    assert sub.coverage_show_deleted is None
    assert sub.coverage_single_events is None
    trust = evaluate_calendar_freshness(db_session, owner.id, settings, now)
    assert trust.ok is True


def test_e10_suppressed_tombstone_id_is_a_classified_skip(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-e10", summary="E10")
    start = window_start + timedelta(hours=4)
    tomb = _seed_busy(
        db_session,
        account=account,
        calendar_id="cal-e10",
        external_id="e10-tomb",
        start=start,
        end=start + timedelta(hours=1),
        pending_deletion=True,
    )
    tomb_id = tomb.id
    _patch_token(monkeypatch)
    monkeypatch.setattr(
        ms_cal,
        "delete_microsoft_event",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("still pending")),
    )
    _patch_view(
        monkeypatch,
        lambda *_a, **_k: [
            _ms_event("e10-tomb", start, start + timedelta(hours=1), subject="Should stay tombstone"),
            _ms_event("e10-live", start + timedelta(hours=3), start + timedelta(hours=4)),
        ],
    )
    assert _sync(db_session, account, window_start, window_end) == 1
    db_session.refresh(sub)
    assert sub.coverage_success_at is not None
    assert sub.coverage_mode == "ms_view"
    row = _row(db_session, "e10-tomb")
    assert row is not None
    assert row.id == tomb_id
    assert row.pending_deletion is True
    live = _row(db_session, "e10-live")
    assert live is not None
    assert live.is_provider_cancelled is False


# --- E15 / E16 ----------------------------------------------------------------


def test_e15_auth_failure_before_begin_is_durable_unreadiness(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-e15", "E15")]) as fx:
        owner, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        owner.display_name = "MUST NOT COMMIT WITH FAILURE"
        monkeypatch.setattr(
            ms_cal,
            "get_valid_access_token",
            lambda *_a, **_k: (_ for _ in ()).throw(
                ApiError(502, "Synthetic auth failure", "SYNTHETIC_AUTH")
            ),
        )
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "SYNTHETIC_AUTH"
        assert owner.display_name == "MUST NOT COMMIT WITH FAILURE"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            user = verify.get(User, fx.owner_id)
            assert durable is not None and user is not None
            assert user.display_name == fx.prior_display
            assert durable.sync_cursor == fx.cursors[sub.id]
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_e15_later_page_error_before_begin(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-e15-page", "E15 page")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)

        def handler(request: httpx.Request) -> httpx.Response:
            if "skiptoken" in str(request.url):
                return httpx.Response(500, json={"error": {"code": "Boom", "message": "page 2"}})
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "should-not-stick",
                            "subject": "Partial",
                            "showAs": "busy",
                            "start": {"dateTime": "2026-10-20T15:00:00", "timeZone": "UTC"},
                            "end": {"dateTime": "2026-10-20T16:00:00", "timeZone": "UTC"},
                        }
                    ],
                    "@odata.nextLink": (
                        "https://graph.microsoft.com/v1.0/me/calendars/cal-e15-page/"
                        "calendarView?$skiptoken=2"
                    ),
                },
            )

        _patch_httpx(monkeypatch, handler)
        with pytest.raises(ApiError):
            _sync(db_session, account, fx.window_start, fx.window_end)
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            assert (
                verify.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.external_event_id == "should-not-stick")
                .count()
                == 0
            )
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_e15b_auth_failure_marks_every_enabled_sub(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(
        db_session,
        calendars=[("cal-e15b-a", "Alpha"), ("cal-e15b-b", "Beta")],
    ) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        monkeypatch.setattr(
            ms_cal,
            "get_valid_access_token",
            lambda *_a, **_k: (_ for _ in ()).throw(
                ApiError(502, "Synthetic auth failure", "SYNTHETIC_AUTH")
            ),
        )
        with pytest.raises(ApiError):
            _sync(db_session, account, fx.window_start, fx.window_end)
        db_session.rollback()
        verify = SessionLocal()
        try:
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            for sub_id in fx.sub_ids:
                durable = verify.get(CalendarSubscription, sub_id)
                assert durable is not None
                assert durable.coverage_success_at is None
                assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
            assert len(trust.blocking_diagnostics) >= 2
        finally:
            verify.close()


def test_e15c_flushed_row_lock_sidecar_survives(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-e15c-lock", "Row Lock")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        sub.summary = "FLUSHED ROW LOCK"
        db_session.flush()
        monkeypatch.setattr(
            ms_cal,
            "get_valid_access_token",
            lambda *_a, **_k: (_ for _ in ()).throw(
                ApiError(502, "Synthetic auth failure", "SYNTHETIC_AUTH")
            ),
        )
        with pytest.raises(ApiError):
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert sub.summary == "FLUSHED ROW LOCK"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            sidecar = (
                verify.query(CalendarSubscriptionRefreshFailure)
                .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub.id)
                .one()
            )
            assert durable is not None
            assert durable.summary == fx.summaries[sub.id]
            assert durable.sync_cursor == fx.cursors[sub.id]
            assert durable.coverage_mode == "ms_view"
            assert durable.coverage_success_at is not None
            assert durable.coverage_last_failure_at is None
            assert sidecar.cause == "calendar_refresh_failed"
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
            assert "calendar_refresh_failed" in _causes(trust)
            assert "microsoft_coverage_unverified" not in _causes(trust)
        finally:
            verify.close()


def test_e15c_unflushed_summary_survives_narrow_expire(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.calendar_refresh_failures import FAILURE_PERSIST_EXPIRE_ATTRS

    with _committed_ms(db_session, calendars=[("cal-e15c-edit", "Narrow")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        sub.summary = "CALLER EDIT"
        monkeypatch.setattr(
            ms_cal,
            "get_valid_access_token",
            lambda *_a, **_k: (_ for _ in ()).throw(
                ApiError(502, "Synthetic auth failure", "SYNTHETIC_AUTH")
            ),
        )
        with pytest.raises(ApiError):
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert "summary" not in FAILURE_PERSIST_EXPIRE_ATTRS
        assert "sync_cursor" not in FAILURE_PERSIST_EXPIRE_ATTRS
        assert sub.summary == "CALLER EDIT"
        assert sub.coverage_last_failure_at is not None
        assert sub.summary == "CALLER EDIT"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.summary == fx.summaries[sub.id]
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


# --- Dex bounce: response shape / decode (0653bd7) ------------------------------


def test_graph_collection_page_rejects_missing_value_object() -> None:
    """Unit seam: HTTP 200 ``{}`` is malformed, not an empty collection."""
    response = httpx.Response(200, json={})
    with pytest.raises(ApiError) as raised:
        ms_cal._graph_collection_page(
            response,
            list_error_code="MICROSOFT_EVENTS_LIST",
            list_error_detail="Microsoft Calendar events list failed",
        )
    assert raised.value.content["code"] == "MICROSOFT_GRAPH_PAGE_MALFORMED"


def test_graph_collection_page_accepts_genuine_empty_list() -> None:
    items, next_link, delta_link = ms_cal._graph_collection_page(
        httpx.Response(200, json={"value": []}),
        list_error_code="MICROSOFT_EVENTS_LIST",
        list_error_detail="Microsoft Calendar events list failed",
    )
    assert items == []
    assert next_link is None
    assert delta_link is None


def test_dex_missing_value_does_not_mint_empty_ms_view(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTTP 200 ``{}`` must not coerce to empty ``value`` and mint success."""
    with _committed_ms(db_session, calendars=[("cal-dex-missing", "Missing")]) as fx:
        # Seed cached busy before attaching rows to the caller session so the
        # autonomous failure UPDATE is not blocked (E15c lock path).
        start = fx.window_start + timedelta(hours=3)
        seed = SessionLocal()
        try:
            account_row = seed.get(CalendarAccount, fx.account_id)
            assert account_row is not None
            kept = _seed_busy(
                seed,
                account=account_row,
                calendar_id="cal-dex-missing",
                external_id="dex-kept-missing",
                start=start,
                end=start + timedelta(hours=1),
            )
            kept_id = kept.id
            seed.commit()
        finally:
            seed.close()

        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)
        _patch_httpx(monkeypatch, lambda _request: httpx.Response(200, json={}))
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MICROSOFT_GRAPH_PAGE_MALFORMED"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            row = (
                verify.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.external_event_id == "dex-kept-missing")
                .one()
            )
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            assert row.is_provider_cancelled is False
            assert row.id == kept_id
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            # Gate may surface microsoft_coverage_unverified after failure clears mode
            # (T1-E tip residual); unreadiness is required, not a specific cause string.
            assert trust.ok is False
        finally:
            verify.close()


def test_dex_null_value_does_not_mint(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-dex-null", "Null value")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)
        _patch_httpx(
            monkeypatch,
            lambda _request: httpx.Response(200, json={"value": None}),
        )
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MICROSOFT_GRAPH_PAGE_MALFORMED"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_dex_non_list_value_does_not_mint(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-dex-obj-value", "Object value")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)
        _patch_httpx(
            monkeypatch,
            lambda _request: httpx.Response(200, json={"value": {"id": "nope"}}),
        )
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MICROSOFT_GRAPH_PAGE_MALFORMED"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_dex_genuine_empty_value_list_mints(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drained page with ``value: []`` is a proven empty window — mint stays valid."""
    with _committed_ms(db_session, calendars=[("cal-dex-empty", "Empty")], mint=False) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)
        _patch_httpx(
            monkeypatch,
            lambda _request: httpx.Response(200, json={"value": []}),
        )
        assert _sync(db_session, account, fx.window_start, fx.window_end) == 0
        db_session.refresh(sub)
        assert sub.coverage_mode == "ms_view"
        assert sub.coverage_item_count == 0
        assert sub.coverage_success_at is not None
        trust = evaluate_calendar_freshness(
            db_session, fx.owner_id, _settings_row, datetime.now(UTC)
        )
        assert trust.ok is True


def test_dex_invalid_json_initial_page_is_durable_unreadiness(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-dex-json", "Bad JSON")]) as fx:
        start = fx.window_start + timedelta(hours=4)
        seed = SessionLocal()
        try:
            account_row = seed.get(CalendarAccount, fx.account_id)
            assert account_row is not None
            _seed_busy(
                seed,
                account=account_row,
                calendar_id="cal-dex-json",
                external_id="dex-kept-json",
                start=start,
                end=start + timedelta(hours=1),
            )
            seed.commit()
        finally:
            seed.close()

        owner, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        owner.display_name = "MUST NOT COMMIT WITH FAILURE"
        _patch_token(monkeypatch)
        _patch_httpx(
            monkeypatch,
            lambda _request: httpx.Response(200, content=b"not json"),
        )
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MICROSOFT_GRAPH_PAGE_MALFORMED"
        assert owner.display_name == "MUST NOT COMMIT WITH FAILURE"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            user = verify.get(User, fx.owner_id)
            row = (
                verify.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.external_event_id == "dex-kept-json")
                .one()
            )
            assert durable is not None and user is not None
            assert user.display_name == fx.prior_display
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            assert row.is_provider_cancelled is False
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_dex_malformed_later_page_is_durable_unreadiness(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-dex-later", "Later page")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)

        def handler(request: httpx.Request) -> httpx.Response:
            if "skiptoken" in str(request.url):
                return httpx.Response(200, json={})
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "should-not-stick",
                            "subject": "Partial",
                            "showAs": "busy",
                            "start": {"dateTime": "2026-10-20T15:00:00", "timeZone": "UTC"},
                            "end": {"dateTime": "2026-10-20T16:00:00", "timeZone": "UTC"},
                        }
                    ],
                    "@odata.nextLink": (
                        "https://graph.microsoft.com/v1.0/me/calendars/cal-dex-later/"
                        "calendarView?$skiptoken=2"
                    ),
                },
            )

        _patch_httpx(monkeypatch, handler)
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MICROSOFT_GRAPH_PAGE_MALFORMED"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            assert (
                verify.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.external_event_id == "should-not-stick")
                .count()
                == 0
            )
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_dex_invalid_json_later_page_is_durable_unreadiness(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(db_session, calendars=[("cal-dex-later-json", "Later JSON")]) as fx:
        _owner_row, _settings_row, account, subs = _load(db_session, fx)
        sub = subs[0]
        _patch_token(monkeypatch)

        def handler(request: httpx.Request) -> httpx.Response:
            if "skiptoken" in str(request.url):
                return httpx.Response(200, content=b"{broken")
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "page-1-only", "subject": "P1", "showAs": "busy"}],
                    "@odata.nextLink": (
                        "https://graph.microsoft.com/v1.0/me/calendars/cal-dex-later-json/"
                        "calendarView?$skiptoken=2"
                    ),
                },
            )

        _patch_httpx(monkeypatch, handler)
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MICROSOFT_GRAPH_PAGE_MALFORMED"
        db_session.rollback()
        verify = SessionLocal()
        try:
            durable = verify.get(CalendarSubscription, sub.id)
            assert durable is not None
            assert durable.coverage_success_at is None
            assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            assert (
                verify.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.external_event_id == "page-1-only")
                .count()
                == 0
            )
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


def test_dex_auth_token_invalid_json_marks_all_enabled_subs(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auth parse seam: invalid token JSON → durable unreadiness on every enabled sub."""
    with _committed_ms(
        db_session,
        calendars=[("cal-dex-auth-a", "Auth A"), ("cal-dex-auth-b", "Auth B")],
    ) as fx:
        _owner_row, _settings_row, account, _subs = _load(db_session, fx)
        # Force refresh path so token-body decode runs.
        account.token_expires_at = datetime(2000, 1, 1, tzinfo=UTC)
        account.refresh_token_enc = encrypt_token(_settings(), "refresh-dex-auth")
        db_session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            if "oauth2/v2.0/token" in str(request.url):
                return httpx.Response(200, content=b"not-a-token-json")
            raise AssertionError(f"unexpected request {request.url}")

        _patch_httpx(monkeypatch, handler)
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MICROSOFT_TOKEN_REFRESH"
        db_session.rollback()
        verify = SessionLocal()
        try:
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            for sub_id in fx.sub_ids:
                durable = verify.get(CalendarSubscription, sub_id)
                assert durable is not None
                assert durable.coverage_success_at is None
                assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
            assert len(trust.blocking_diagnostics) >= 2
        finally:
            verify.close()


def test_validated_oauth_token_fields_shape() -> None:
    """Field shape is typed ApiError before any caller can mutate an account."""
    now = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
    kwargs = {
        "missing_access_detail": "missing access",
        "shape_code": "MICROSOFT_TOKEN_REFRESH",
        "shape_detail": "bad shape",
        "now": now,
    }
    access, expires_in, refresh, expires_at = ms_cal._validated_oauth_token_fields(
        {"access_token": "ok"},
        **kwargs,
    )
    assert (access, expires_in, refresh) == ("ok", 3600, None)
    assert expires_at == now + timedelta(seconds=3540)

    access, expires_in, refresh, expires_at = ms_cal._validated_oauth_token_fields(
        {"access_token": "ok", "expires_in": "", "refresh_token": ""},
        **kwargs,
    )
    assert (access, expires_in, refresh) == ("ok", 3600, None)
    assert expires_at == now + timedelta(seconds=3540)

    access, expires_in, refresh, expires_at = ms_cal._validated_oauth_token_fields(
        {"access_token": "ok", "expires_in": "7200", "refresh_token": "rotated"},
        **kwargs,
    )
    assert (access, expires_in, refresh) == ("ok", 7200, "rotated")
    assert expires_at == now + timedelta(seconds=7140)

    # Large negatives clamp to the existing 60s floor; they are representable.
    access, expires_in, refresh, expires_at = ms_cal._validated_oauth_token_fields(
        {"access_token": "ok", "expires_in": -(10**30)},
        **kwargs,
    )
    assert expires_in == -(10**30)
    assert refresh is None
    assert expires_at == now + timedelta(seconds=60)

    with pytest.raises(ApiError) as raised:
        ms_cal._validated_oauth_token_fields(
            {"access_token": "synthetic", "expires_in": "invalid"},
            **kwargs,
        )
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_REFRESH"

    with pytest.raises(ApiError) as raised:
        ms_cal._validated_oauth_token_fields(
            {"access_token": {"nested": True}, "expires_in": 3600},
            **kwargs,
        )
    assert raised.value.content["code"] == "MICROSOFT_NO_ACCESS_TOKEN"

    with pytest.raises(ApiError) as raised:
        ms_cal._validated_oauth_token_fields(
            {"access_token": "ok", "expires_in": 3600, "refresh_token": {"x": 1}},
            **kwargs,
        )
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_REFRESH"


@pytest.mark.parametrize(
    "raw_expires",
    [10**30, 10**12, 10**14, str(10**30), float("inf")],
)
@pytest.mark.parametrize(
    "shape_code",
    ["MICROSOFT_TOKEN_REFRESH", "MICROSOFT_TOKEN_EXCHANGE"],
)
def test_validated_oauth_token_fields_rejects_unrepresentable_expiry(
    raw_expires: object,
    shape_code: str,
) -> None:
    """int() success is not enough: the expiry instant must be representable."""
    with pytest.raises(ApiError) as raised:
        ms_cal._validated_oauth_token_fields(
            {"access_token": "ok", "expires_in": raw_expires},
            missing_access_detail="missing access",
            shape_code=shape_code,
            shape_detail="bad shape",
            now=datetime(2026, 10, 20, 15, 0, tzinfo=UTC),
        )
    assert raised.value.content["code"] == shape_code
    assert raised.value.status_code == 502
    assert isinstance(raised.value.__cause__, OverflowError)


def test_validated_oauth_token_fields_maps_expiry_valueerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ValueError from the instant construction uses the same auth shape code."""

    def _boom(*_args: object, **_kwargs: object) -> timedelta:
        raise ValueError("unrepresentable expiry")

    monkeypatch.setattr(ms_cal, "timedelta", _boom)
    with pytest.raises(ApiError) as raised:
        ms_cal._validated_oauth_token_fields(
            {"access_token": "ok", "expires_in": 3600},
            missing_access_detail="missing access",
            shape_code="MICROSOFT_TOKEN_REFRESH",
            shape_detail="bad shape",
            now=datetime(2026, 10, 20, 15, 0, tzinfo=UTC),
        )
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_REFRESH"
    assert isinstance(raised.value.__cause__, ValueError)


def test_get_valid_access_token_rejects_malformed_refresh_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    prior_access = encrypt_token(settings, "prior-access")
    prior_refresh = encrypt_token(settings, "prior-refresh")
    prior_expiry = datetime(2000, 1, 1, tzinfo=UTC)
    account = SimpleNamespace(
        access_token_enc=prior_access,
        refresh_token_enc=prior_refresh,
        token_expires_at=prior_expiry,
    )
    monkeypatch.setattr(
        ms_cal,
        "refresh_access_token",
        lambda *_a, **_k: {"access_token": "synthetic", "expires_in": "invalid"},
    )
    db = MagicMock()
    with pytest.raises(ApiError) as raised:
        ms_cal.get_valid_access_token(db, settings=settings, account=account)
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_REFRESH"
    assert account.access_token_enc == prior_access
    assert account.refresh_token_enc == prior_refresh
    assert account.token_expires_at == prior_expiry
    db.flush.assert_not_called()

    monkeypatch.setattr(
        ms_cal,
        "refresh_access_token",
        lambda *_a, **_k: {"access_token": {"nested": True}, "expires_in": 3600},
    )
    with pytest.raises(ApiError) as raised:
        ms_cal.get_valid_access_token(db, settings=settings, account=account)
    assert raised.value.content["code"] == "MICROSOFT_NO_ACCESS_TOKEN"
    assert account.access_token_enc == prior_access
    db.flush.assert_not_called()


@pytest.mark.parametrize("expires_in", [10**30, 10**12, 10**14])
def test_get_valid_access_token_rejects_unrepresentable_expiry_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
    expires_in: int,
) -> None:
    settings = _settings()
    prior_access = encrypt_token(settings, "prior-access")
    prior_refresh = encrypt_token(settings, "prior-refresh")
    prior_expiry = datetime(2000, 1, 1, tzinfo=UTC)
    account = SimpleNamespace(
        access_token_enc=prior_access,
        refresh_token_enc=prior_refresh,
        token_expires_at=prior_expiry,
    )
    monkeypatch.setattr(
        ms_cal,
        "refresh_access_token",
        lambda *_a, **_k: {"access_token": "synthetic", "expires_in": expires_in},
    )
    db = MagicMock()
    with pytest.raises(ApiError) as raised:
        ms_cal.get_valid_access_token(db, settings=settings, account=account)
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_REFRESH"
    assert isinstance(raised.value.__cause__, OverflowError)
    assert account.access_token_enc == prior_access
    assert account.refresh_token_enc == prior_refresh
    assert account.token_expires_at == prior_expiry
    db.flush.assert_not_called()


def test_upsert_account_tokens_rejects_bad_fields_before_db() -> None:
    db = MagicMock()
    with pytest.raises(ApiError) as raised:
        ms_cal.upsert_account_tokens(
            db,
            settings=_settings(),
            owner_id=uuid.uuid4(),
            account_email="shape@example.test",
            token_payload={"access_token": "synthetic", "expires_in": "invalid", "refresh_token": "r"},
        )
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_EXCHANGE"
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.query.assert_not_called()

    with pytest.raises(ApiError) as raised:
        ms_cal.upsert_account_tokens(
            db,
            settings=_settings(),
            owner_id=uuid.uuid4(),
            account_email="shape@example.test",
            token_payload={
                "access_token": "synthetic",
                "expires_in": 3600,
                "refresh_token": {"nested": True},
            },
        )
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_EXCHANGE"
    db.query.assert_not_called()


@pytest.mark.parametrize("expires_in", [10**30, 10**12, 10**14])
def test_upsert_account_tokens_rejects_unrepresentable_expiry_before_db(
    expires_in: int,
) -> None:
    prior_access = object()
    prior_refresh = object()
    prior_expiry = datetime(2000, 1, 1, tzinfo=UTC)
    existing = SimpleNamespace(
        account_email="shape@example.test",
        access_token_enc=prior_access,
        refresh_token_enc=prior_refresh,
        token_expires_at=prior_expiry,
        is_enabled=False,
    )
    db = MagicMock()
    with pytest.raises(ApiError) as raised:
        ms_cal.upsert_account_tokens(
            db,
            settings=_settings(),
            owner_id=uuid.uuid4(),
            account_email="shape@example.test",
            token_payload={
                "access_token": "synthetic",
                "expires_in": expires_in,
                "refresh_token": "r",
            },
            existing=existing,
        )
    assert raised.value.content["code"] == "MICROSOFT_TOKEN_EXCHANGE"
    assert isinstance(raised.value.__cause__, OverflowError)
    assert existing.access_token_enc is prior_access
    assert existing.refresh_token_enc is prior_refresh
    assert existing.token_expires_at == prior_expiry
    assert existing.is_enabled is False
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.query.assert_not_called()


@pytest.mark.parametrize(
    ("slug", "token_body", "error_code"),
    [
        (
            "expires",
            {"access_token": "synthetic", "expires_in": "invalid"},
            "MICROSOFT_TOKEN_REFRESH",
        ),
        (
            "access-obj",
            {"access_token": {"nested": True}, "expires_in": 3600},
            "MICROSOFT_NO_ACCESS_TOKEN",
        ),
        (
            "expires-huge",
            {"access_token": "synthetic", "expires_in": 10**30},
            "MICROSOFT_TOKEN_REFRESH",
        ),
        (
            "expires-range",
            {"access_token": "synthetic", "expires_in": 10**12},
            "MICROSOFT_TOKEN_REFRESH",
        ),
    ],
)
def test_dex_malformed_refresh_fields_mark_all_enabled_subs(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    slug: str,
    token_body: dict[str, Any],
    error_code: str,
) -> None:
    """HTTP 200 token bodies with bad fields must not skip the E15b unreadiness path.

    Young prior ``ms_view`` on two enabled subs stays trusted if ``ValueError`` /
    ``AttributeError`` escape ``get_valid_access_token`` after a partial token write.
    The same rollback leaves freshness ``ok=True`` when ``expires_in`` passes
    ``int`` and ``timedelta`` / ``datetime`` then raises ``OverflowError`` after
    ``access_token_enc`` was assigned (``10**30``, and ``10**12`` which overflows
    the datetime range rather than ``timedelta`` itself).
    """
    with _committed_ms(
        db_session,
        calendars=[(f"cal-dex-shape-{slug}-a", "Shape A"), (f"cal-dex-shape-{slug}-b", "Shape B")],
    ) as fx:
        owner, _settings_row, account, subs = _load(db_session, fx)
        account.token_expires_at = datetime(2000, 1, 1, tzinfo=UTC)
        account.refresh_token_enc = encrypt_token(_settings(), "refresh-dex-shape")
        db_session.flush()
        prior_access = account.access_token_enc
        prior_expiry = account.token_expires_at
        owner.display_name = "MUST NOT COMMIT WITH FAILURE"
        for sub in subs:
            sub.summary = "CALLER EDIT"

        def handler(request: httpx.Request) -> httpx.Response:
            if "oauth2/v2.0/token" in str(request.url):
                return httpx.Response(200, json=token_body)
            raise AssertionError(f"unexpected request {request.url}")

        _patch_httpx(monkeypatch, handler)
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == error_code
        assert account.access_token_enc == prior_access
        assert account.token_expires_at == prior_expiry
        assert owner.display_name == "MUST NOT COMMIT WITH FAILURE"
        for sub in subs:
            assert sub.summary == "CALLER EDIT"
            assert sub.coverage_last_failure_cause == "calendar_refresh_failed"
        db_session.rollback()
        verify = SessionLocal()
        try:
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            user = verify.get(User, fx.owner_id)
            durable_account = verify.get(CalendarAccount, fx.account_id)
            assert user is not None and durable_account is not None
            assert user.display_name == fx.prior_display
            assert decrypt_token(_settings(), durable_account.access_token_enc) == "access-token"
            for sub_id in fx.sub_ids:
                durable = verify.get(CalendarSubscription, sub_id)
                assert durable is not None
                assert durable.summary == fx.summaries[sub_id]
                assert durable.sync_cursor == fx.cursors[sub_id]
                assert durable.coverage_success_at is None
                assert durable.coverage_last_failure_cause == "calendar_refresh_failed"
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
            assert len(trust.blocking_diagnostics) >= 2
        finally:
            verify.close()


def test_e16_one_failed_sub_blocks_the_proposal(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _committed_ms(
        db_session,
        calendars=[("cal-e16-ok", "Ok"), ("cal-e16-bad", "Bad")],
    ) as fx:
        _owner_row, settings, account, _subs = _load(db_session, fx)
        start = fx.window_start + timedelta(hours=2)

        def _view(_access: str, calendar_id: str, *, time_min: datetime, time_max: datetime):
            del time_min, time_max
            if calendar_id == "cal-e16-bad":
                return [{"subject": "missing id"}]
            return [_ms_event("e16-ok", start, start + timedelta(hours=1))]

        _patch_token(monkeypatch)
        _patch_view(monkeypatch, _view)
        with pytest.raises(ApiError) as raised:
            _sync(db_session, account, fx.window_start, fx.window_end)
        assert raised.value.content["code"] == "MS_VIEW_ITEM_UNRESOLVABLE"
        db_session.rollback()
        verify = SessionLocal()
        try:
            settings = verify.query(UserSettings).filter(UserSettings.owner_id == fx.owner_id).one()
            by_cal = {
                row.external_calendar_id: row
                for row in verify.query(CalendarSubscription)
                .filter(CalendarSubscription.owner_id == fx.owner_id)
                .all()
            }
            assert by_cal["cal-e16-bad"].coverage_success_at is None
            trust = evaluate_calendar_freshness(verify, fx.owner_id, settings, fx.mint_now)
            assert trust.ok is False
        finally:
            verify.close()


# --- E19 / E20 / E22 ----------------------------------------------------------


def test_e19_delta_helpers_do_not_mint_when_called_directly(
    db_session: Session,
) -> None:
    owner, _settings_row = _owner(db_session)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-e19", summary="E19")
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    start = now + timedelta(hours=1)
    event = _ms_event("e19-full", start, start + timedelta(hours=1))
    upserted = ms_cal._apply_subscription_full(
        db_session,
        account=account,
        subscription=sub,
        events=[event],
        next_delta_link="delta-from-helper",
        time_min=now - timedelta(days=1),
        time_max=now + timedelta(days=2),
        now=now,
    )
    assert upserted == 1
    db_session.refresh(sub)
    assert sub.sync_cursor == "delta-from-helper"
    assert sub.coverage_success_at is None
    assert sub.coverage_mode is None

    sub.sync_cursor = None
    incr = ms_cal._apply_subscription_incremental(
        db_session,
        account=account,
        subscription=sub,
        events=[_ms_event("e19-incr", start, start + timedelta(minutes=30))],
        next_delta_link="incr-from-helper",
        now=now,
    )
    assert incr == 1
    db_session.refresh(sub)
    assert sub.sync_cursor == "incr-from-helper"
    assert sub.coverage_success_at is None
    assert sub.coverage_mode is None


def test_e20_returning_id_clears_provider_cancellation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="cal-e20", summary="E20")
    start = window_start + timedelta(hours=8)
    _patch_token(monkeypatch)
    phases = {"n": 0}

    def _view(*_a: Any, **_k: Any):
        phases["n"] += 1
        if phases["n"] == 1:
            return [_ms_event("e20", start, start + timedelta(hours=1), subject="There")]
        if phases["n"] == 2:
            return [_ms_event("e20", start, start + timedelta(hours=1), cancelled=True)]
        return [_ms_event("e20", start, start + timedelta(hours=1), subject="Back", show_as="busy")]

    _patch_view(monkeypatch, _view)
    _sync(db_session, account, window_start, window_end)
    first = _row(db_session, "e20")
    assert first is not None
    first_id = first.id
    history_after_create = list(first.free_busy_change_history or [])
    assert history_after_create
    _sync(db_session, account, window_start, window_end)
    cancelled = _row(db_session, "e20")
    assert cancelled is not None
    assert cancelled.id == first_id
    assert cancelled.is_provider_cancelled is True
    _sync(db_session, account, window_start, window_end)
    restored = _row(db_session, "e20")
    assert restored is not None
    assert restored.id == first_id
    assert restored.is_provider_cancelled is False
    assert restored.transparency == "opaque"
    assert restored.free_busy_provenance == "provider_explicit"
    assert restored.free_busy_change_history
    assert (
        db_session.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.id == first_id,
            *ExternalCalendarEvent.immovable_busy_clause(),
        )
        .count()
        == 1
    )


def test_e22_unknown_projection_may_mint_but_busy_trust_stays_closed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, settings = _owner(db_session)
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    _patch_clock(monkeypatch, now)
    window_start, window_end = _wide_bounds(settings, now)
    account = _account(db_session, owner)
    sub = _sub(db_session, account, calendar_id="cal-e22", summary="E22")
    start = window_start + timedelta(hours=5)
    seeded = _seed_busy(
        db_session,
        account=account,
        calendar_id="cal-e22",
        external_id="e22",
        start=start,
        end=start + timedelta(hours=1),
    )
    seeded_id = seeded.id
    _patch_token(monkeypatch)
    _patch_view(
        monkeypatch,
        lambda *_a, **_k: [
            _ms_event(
                "e22",
                start,
                start + timedelta(hours=1),
                subject="Incomplete",
                show_as=None,
                include_times=False,
            )
        ],
    )
    assert _sync(db_session, account, window_start, window_end) == 1
    db_session.refresh(sub)
    row = _row(db_session, "e22")
    assert row is not None
    assert row.id == seeded_id
    assert sub.coverage_mode == "ms_view"
    assert sub.coverage_success_at is not None
    assert row.free_busy_provenance == "unknown_projection"
    # Omit-type payload ⇒ incomplete; both quals must remain visible.
    assert row.series_identity_state == "incomplete"
    trust = evaluate_busy_input_trust(
        [row],
        horizon_start=start - timedelta(minutes=5),
        horizon_end=start + timedelta(hours=2),
    )
    assert trust.ok is False
    causes = {diag.cause for diag in trust.blocking_diagnostics}
    assert "series_identity_incomplete" in causes
    assert any("unknown_projection" in c for c in causes)
    freshness = evaluate_calendar_freshness(db_session, owner.id, settings, now)
    assert freshness.ok is True
