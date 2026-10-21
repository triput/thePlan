"""T1-13 Microsoft appointment churn — occupancy evidence (local / synthetic).

Authorization: newly added and retimed MS appointments must appear in refreshed
scheduler inputs through the **production** ``sync_account_events`` path, with
mocked Graph ``calendarView`` responses and disposable Postgres only (:5433).

Reuses T1-C / T1-E / Boundary B fixture patterns (``_committed_ms``-style
SessionLocal seed, ``list_calendar_view`` mock, ms_view mint, collect_inputs).
Does **not** reopen Boundary B preview invalidation (Dex ACCEPTED @ ``f75cc39``).

Proofs: initial pull → add → retime (old interval off / new on) → owner
isolation → trusted complete identity → no stale duplicate occupancy →
committed later-session readback. Google churn remains the parity control in
``test_t1c_acceptance.test_t1_13_incremental_churn_updates_cache``.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any, Iterator
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

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
from app.scheduler.calendar_freshness import required_coverage_window
from app.scheduler.collect import collect_inputs
from app.services import microsoft_calendar as ms_cal
from app.services.token_crypto import encrypt_token
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
        microsoft_client_id="t113-ms-client",
        microsoft_client_secret="t113-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _owner(db: Session) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"t113-{token}@example.test",
        username=f"t113_{token}",
        display_name="T1-13 MS churn",
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
        account_email=f"t113-{uuid.uuid4().hex[:8]}@example.test",
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
) -> CalendarSubscription:
    row = CalendarSubscription(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary=summary,
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
        sync_cursor=None,
        provider_timezone="UTC",
    )
    db.add(row)
    db.flush()
    return row


def _wide_bounds(settings: UserSettings, now: datetime) -> tuple[datetime, datetime]:
    start, end = required_coverage_window(settings, now)
    return start - timedelta(hours=2), end + timedelta(hours=2)


def _ms_event(
    event_id: str,
    start: datetime,
    end: datetime,
    *,
    subject: str | None = None,
    show_as: str = "busy",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "subject": subject or event_id,
        "type": "singleInstance",
        "showAs": show_as,
        "start": {
            "dateTime": start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "UTC",
        },
    }


def _no_delta(*_a: Any, **_k: Any) -> None:
    raise AssertionError("bounded ms_view strategy must not call delta helpers")


def _patch_ms_sync(
    monkeypatch: pytest.MonkeyPatch,
    *,
    view: Any,
    fixed_now: datetime,
) -> None:
    real = ms_cal.datetime

    class _FixedNow(real):  # type: ignore[misc,valid-type]
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed_now.astimezone(tz)
            return fixed_now

    monkeypatch.setattr(ms_cal, "datetime", _FixedNow)
    monkeypatch.setattr(ms_cal, "get_valid_access_token", lambda *_a, **_k: "ms-access")
    monkeypatch.setattr(ms_cal, "list_calendar_view", view)
    monkeypatch.setattr(ms_cal, "list_calendar_events", _no_delta)
    monkeypatch.setattr(ms_cal, "list_calendar_events_incremental", _no_delta)


def _sync(db: Session, account: CalendarAccount, start: datetime, end: datetime) -> int:
    return ms_cal.sync_account_events(
        db,
        settings=_settings(),
        account=account,
        time_min=start,
        time_max=end,
    )


def _busy_pairs(inputs) -> set[tuple[datetime, datetime]]:
    return {
        (item.start.astimezone(UTC), item.end.astimezone(UTC))
        for item in inputs.immovable_busy
        if item.source == "external"
    }


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


@dataclass(frozen=True)
class _Seeded:
    owner_id: UUID
    account_id: UUID
    sub_id: UUID
    now: datetime
    window_start: datetime
    window_end: datetime


@contextmanager
def _committed_owner(
    *,
    calendar_id: str,
    summary: str,
    now: datetime,
) -> Iterator[_Seeded]:
    """Commit owner/account/sub via SessionLocal (T1-E persistence pattern)."""
    seed = SessionLocal()
    owner_id: UUID | None = None
    try:
        owner, settings = _owner(seed)
        window_start, window_end = _wide_bounds(settings, now)
        account = _account(seed, owner)
        sub = _sub(seed, account, calendar_id=calendar_id, summary=summary)
        seed.commit()
        owner_id = owner.id
        yield _Seeded(
            owner_id=owner.id,
            account_id=account.id,
            sub_id=sub.id,
            now=now,
            window_start=window_start,
            window_end=window_end,
        )
    finally:
        seed.close()
        if owner_id is not None:
            _cleanup(owner_id)


def test_t1_13_ms_churn_refreshes_collected_busy_via_production_sync(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MS ms_view churn → collect immovable_busy updates (committed readback).

    Rolls db_session so fixture teardown cannot hold locks against SessionLocal
    cleanup (same discipline as T1-E ``_committed_ms``).
    """
    db_session.rollback()
    now = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    original_start = now + timedelta(hours=5)
    original_end = original_start + timedelta(hours=1)
    moved_start = original_start + timedelta(hours=2)
    moved_end = moved_start + timedelta(hours=1)
    added_start = moved_start + timedelta(hours=3)
    added_end = added_start + timedelta(hours=1)
    other_start = original_start + timedelta(minutes=30)
    other_end = other_start + timedelta(hours=1)
    phase = {"n": 0}

    def _view(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        phase["n"] += 1
        if phase["n"] == 1:
            return [_ms_event("appt", original_start, original_end, subject="Original")]
        return [
            _ms_event("appt", moved_start, moved_end, subject="Moved"),
            _ms_event("appt-new", added_start, added_end, subject="Added"),
        ]

    with (
        _committed_owner(calendar_id="cal-churn-ms", summary="Churn MS", now=now) as primary,
        _committed_owner(calendar_id="cal-other-ms", summary="Other owner", now=now) as other,
    ):
        # --- other-owner seed (isolation control) via production sync ---
        _patch_ms_sync(
            monkeypatch,
            view=lambda *_a, **_k: [
                _ms_event("other-only", other_start, other_end, subject="Foreign")
            ],
            fixed_now=now,
        )
        other_work = SessionLocal()
        try:
            other_account = other_work.get(CalendarAccount, other.account_id)
            assert other_account is not None
            assert (
                _sync(other_work, other_account, other.window_start, other.window_end)
                == 1
            )
            other_work.commit()
        finally:
            other_work.close()

        # --- primary: initial pull ---
        _patch_ms_sync(monkeypatch, view=_view, fixed_now=now)
        work = SessionLocal()
        try:
            account = work.get(CalendarAccount, primary.account_id)
            assert account is not None
            assert _sync(work, account, primary.window_start, primary.window_end) == 1
            work.commit()
        finally:
            work.close()

        # Committed later-session readback after initial pull.
        verify_initial = SessionLocal()
        try:
            inputs0 = collect_inputs(verify_initial, primary.owner_id, now)
            pairs0 = _busy_pairs(inputs0)
            assert (original_start, original_end) in pairs0
            assert (moved_start, moved_end) not in pairs0
            assert (added_start, added_end) not in pairs0
            assert (other_start, other_end) not in pairs0
            assert inputs0.busy_input_trust is not None and inputs0.busy_input_trust.ok
            assert (
                inputs0.calendar_freshness_trust is not None
                and inputs0.calendar_freshness_trust.ok
            )
            row0 = (
                verify_initial.query(ExternalCalendarEvent)
                .filter(
                    ExternalCalendarEvent.owner_id == primary.owner_id,
                    ExternalCalendarEvent.external_event_id == "appt",
                )
                .one()
            )
            assert row0.transparency == "opaque"
            assert row0.free_busy_provenance == "provider_explicit"
            assert row0.source_timezone == "UTC"
            assert row0.is_provider_cancelled is False
            sub0 = verify_initial.get(CalendarSubscription, primary.sub_id)
            assert sub0 is not None
            assert sub0.coverage_mode == "ms_view"
            assert sub0.coverage_success_at is not None
            assert sub0.coverage_pagination_complete is True
        finally:
            verify_initial.close()

        # --- primary: add + retime (same production sync path) ---
        work2 = SessionLocal()
        try:
            account2 = work2.get(CalendarAccount, primary.account_id)
            assert account2 is not None
            assert _sync(work2, account2, primary.window_start, primary.window_end) == 2
            work2.commit()
        finally:
            work2.close()

        # Committed later-session readback after churn.
        verify = SessionLocal()
        try:
            inputs = collect_inputs(verify, primary.owner_id, now)
            pairs = _busy_pairs(inputs)
            # Retime: old interval removed, new interval present.
            assert (original_start, original_end) not in pairs
            assert (moved_start, moved_end) in pairs
            # Add: new appointment present.
            assert (added_start, added_end) in pairs
            # No stale duplicate occupancy (one interval per busy slot).
            assert len([p for p in pairs if p == (moved_start, moved_end)]) == 1
            assert len(pairs) == 2
            # Owner isolation: foreign owner's busy never enters this collect.
            assert (other_start, other_end) not in pairs
            foreign = (
                verify.query(ExternalCalendarEvent)
                .filter(
                    ExternalCalendarEvent.owner_id == primary.owner_id,
                    ExternalCalendarEvent.external_event_id == "other-only",
                )
                .count()
            )
            assert foreign == 0
            other_inputs = collect_inputs(verify, other.owner_id, now)
            other_pairs = _busy_pairs(other_inputs)
            assert (other_start, other_end) in other_pairs
            assert (moved_start, moved_end) not in other_pairs
            assert (added_start, added_end) not in other_pairs

            # Trusted complete identity + freshness after churn.
            assert inputs.busy_input_trust is not None and inputs.busy_input_trust.ok
            assert (
                inputs.calendar_freshness_trust is not None
                and inputs.calendar_freshness_trust.ok
            )
            rows = {
                row.external_event_id: row
                for row in verify.query(ExternalCalendarEvent)
                .filter(ExternalCalendarEvent.owner_id == primary.owner_id)
                .all()
            }
            assert set(rows) == {"appt", "appt-new"}
            assert rows["appt"].title == "Moved"
            assert rows["appt"].start_time.astimezone(UTC) == moved_start
            assert rows["appt"].end_time.astimezone(UTC) == moved_end
            assert rows["appt"].transparency == "opaque"
            assert rows["appt"].free_busy_provenance == "provider_explicit"
            assert rows["appt"].source_timezone == "UTC"
            assert rows["appt"].is_provider_cancelled is False
            assert rows["appt-new"].transparency == "opaque"
            assert rows["appt-new"].free_busy_provenance == "provider_explicit"
            assert rows["appt-new"].is_provider_cancelled is False
            # Immovable busy clause excludes cancelled; no ghost of original window.
            immovable_ids = {
                row.external_event_id
                for row in verify.query(ExternalCalendarEvent)
                .filter(
                    ExternalCalendarEvent.owner_id == primary.owner_id,
                    *ExternalCalendarEvent.immovable_busy_clause(),
                )
                .all()
            }
            assert immovable_ids == {"appt", "appt-new"}
            sub = verify.get(CalendarSubscription, primary.sub_id)
            assert sub is not None
            assert sub.coverage_mode == "ms_view"
            assert sub.coverage_success_generation == sub.coverage_active_generation
        finally:
            verify.close()

        assert phase["n"] == 2
