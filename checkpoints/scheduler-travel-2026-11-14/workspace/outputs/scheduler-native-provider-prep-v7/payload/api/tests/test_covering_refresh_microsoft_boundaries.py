"""Microsoft covering boundaries with scripted Graph data and disposable PostgreSQL."""

from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from app.db import SessionLocal, engine
from app.models import CalendarAccount, CalendarSubscription, ExternalCalendarEvent, User
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.services import covering_refresh_import as covering
from app.services import microsoft_calendar as microsoft
from app.services.covering_refresh_locks import covering_unit_locks
from support.t1a_pg import assert_disposable_database_url
from test_covering_refresh_d2 import NOW, _account, _owner, _seed_legacy_event, _settings, _sub, _window, world
from test_covering_refresh_microsoft_identity import COLLISION, _columns


@pytest.fixture(scope="module", autouse=True)
def _disposable_database_required():
    if os.environ.get("T1A_REQUIRE_DISPOSABLE_DSN") != "1":
        raise pytest.UsageError("Microsoft boundary fixture requires the disposable DSN guard")
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


@pytest.fixture
def scripted_view(monkeypatch):
    payloads = []
    calls = []
    forbidden = []

    def list_view(access, calendar_id, *, time_min, time_max):
        assert access == "synthetic-access"
        calls.append((calendar_id, time_min, time_max))
        return payloads, 1, True

    def reject(*_args, **_kwargs):
        forbidden.append(True)
        raise AssertionError("UNEXPECTED_MICROSOFT_FIXTURE_PROVIDER_CALL")

    monkeypatch.setattr(microsoft, "list_calendar_view", list_view)
    monkeypatch.setattr(microsoft, "delete_microsoft_event", reject)
    monkeypatch.setattr(microsoft.httpx, "Client", reject)
    yield payloads, calls
    assert not forbidden


def _payload(external_id):
    start = NOW + timedelta(hours=2)
    return {
        "id": external_id,
        "subject": "Synthetic Microsoft update",
        "type": "singleInstance",
        "showAs": "busy",
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": (start + timedelta(hours=1)).isoformat(), "timeZone": "UTC"},
    }


def _find(db, external_id):
    return db.query(ExternalCalendarEvent).filter_by(
        provider=CalendarProvider.microsoft, external_event_id=external_id
    ).one()


def _seed(db, owner, account, calendar_id, *, external_id=None, pending=False, hour=2):
    external_id = external_id or f"ms-boundary-{uuid4().hex}"
    start = NOW + timedelta(hours=hour)
    _seed_legacy_event(
        db, owner=owner, account=account, calendar_id=calendar_id, external_id=external_id,
        start=start, end=start + timedelta(hours=1), pending=pending,
    )
    row = db.query(ExternalCalendarEvent).filter_by(
        provider=account.provider, external_event_id=external_id
    ).one()
    row.transparency = "opaque"
    row.free_busy_provenance = "provider_explicit"
    db.flush()
    return row


def _target(db, owner):
    account = _account(db, owner, provider=CalendarProvider.microsoft)
    sub = _sub(db, account, calendar_id="ms-selected", summary="Selected",
               role=CalendarSubscriptionRole.primary)
    return account, sub


def _run(db, account, sub):
    start, end = _window()
    with covering_unit_locks(
        db, owner_id=account.owner_id, account_id=account.id, subscription_id=sub.id
    ) as locks:
        return covering.import_covering_subscription_cache(
            db, settings=_settings(), account=account, subscription=sub,
            access_token="synthetic-access", window_start=start, window_end=end,
            lock_receipt=locks, now=NOW,
        )


def _assert_collision(result):
    assert result.outcome == covering.OUTCOME_FAILED
    assert result.cause == COLLISION
    assert result.rollback_required and result.needs_failure_unit
    assert not result.commit_unit
    assert result.coverage_generation_minted is None


def _assert_view(calls, calendar_id):
    assert calls == [(calendar_id, *_window())]


def test_covering_soft_cancels_exact_rows(db_session, scripted_view):
    db = db_session
    owner, _ = _owner(db)
    account, sub = _target(db, owner)
    removed = _seed(db, owner, account, sub.external_calendar_id)
    cancelled = _seed(db, owner, account, sub.external_calendar_id)
    pending = _seed(db, owner, account, sub.external_calendar_id, pending=True)
    pending_before = _columns(pending)
    absent = f"ms-absent-{uuid4().hex}"
    payloads, calls = scripted_view
    payloads.extend((
        {"id": removed.external_event_id, "@removed": {"reason": "deleted"}},
        {"id": cancelled.external_event_id, "isCancelled": True},
        {"id": pending.external_event_id, "@removed": {"reason": "deleted"}},
        {"id": absent, "@removed": {"reason": "deleted"}},
    ))
    ids = [removed.id, cancelled.id]
    result = _run(db, account, sub)
    _assert_view(calls, sub.external_calendar_id)
    assert result.outcome == covering.OUTCOME_OK and result.upserted == 0
    for row, expected_id in zip((removed, cancelled), ids, strict=True):
        db.refresh(row)
        assert row.id == expected_id and row.is_provider_cancelled and not row.pending_deletion
        assert row.calendar_id == sub.external_calendar_id
    db.refresh(pending)
    assert _columns(pending) == pending_before
    assert db.query(ExternalCalendarEvent.id).filter_by(external_event_id=absent).first() is None


@pytest.mark.parametrize("scope", ["other-calendar", "other-account", "foreign-owner"])
def test_covering_refuses_foreign_cancellation(db_session, scripted_view, scope):
    db = db_session
    owner, _ = _owner(db)
    account, sub = _target(db, owner)
    foreign_owner = _owner(db)[0] if scope == "foreign-owner" else owner
    foreign_account = (
        account if scope == "other-calendar"
        else _account(db, foreign_owner, provider=CalendarProvider.microsoft)
    )
    row = _seed(db, foreign_owner, foreign_account, "ms-outside")
    before = _columns(row)
    payloads, calls = scripted_view
    payloads.append({"id": row.external_event_id, "isCancelled": True})
    attempt = db.begin_nested()
    try:
        result = _run(db, account, sub)
        _assert_collision(result)
        db.refresh(row)
        db.refresh(sub)
        assert _columns(row) == before
        assert sub.coverage_success_generation is None
        _assert_view(calls, sub.external_calendar_id)
    finally:
        attempt.rollback()


def test_covering_stale_sweep_stays_in_scope(db_session, scripted_view):
    db = db_session
    owner, _ = _owner(db)
    other_owner, _ = _owner(db)
    account, sub = _target(db, owner)
    same_owner_account = _account(db, owner, provider=CalendarProvider.microsoft)
    foreign_account = _account(db, other_owner, provider=CalendarProvider.microsoft)
    google = _account(db, owner, provider=CalendarProvider.google)
    calendar = sub.external_calendar_id
    stale = _seed(db, owner, account, calendar)
    seen = _seed(db, owner, account, calendar)
    sentinels = (
        _seed(db, owner, account, "ms-sibling"),
        _seed(db, owner, same_owner_account, calendar),
        _seed(db, other_owner, foreign_account, calendar),
        _seed(db, other_owner, account, calendar),
        _seed(db, owner, google, calendar, external_id=seen.external_event_id),
        _seed(db, owner, account, calendar, pending=True),
        _seed(db, owner, account, calendar, hour=60),
    )
    before = [_columns(row) for row in sentinels]
    payloads, calls = scripted_view
    payloads.append(_payload(seen.external_event_id))
    result = _run(db, account, sub)
    _assert_view(calls, calendar)
    assert result.outcome == covering.OUTCOME_OK and result.upserted == 1
    db.refresh(stale)
    db.refresh(seen)
    assert stale.is_provider_cancelled and not seen.is_provider_cancelled
    assert stale.calendar_id == calendar and seen.calendar_id == calendar
    for row, snapshot in zip(sentinels, before, strict=True):
        db.refresh(row)
        assert _columns(row) == snapshot


def _race(db, monkeypatch, external_id, *, before_lookup, competitor):
    """Interleave an independent committed session at the final locked lookup."""
    original = microsoft._find_external_event
    parent_pid = db.scalar(text("SELECT pg_backend_pid()"))
    observed = []

    def interleave(session, *, owner_id, external_id: str, for_update=False, covering_identity=None):
        if not (session is db and external_id == event_id and for_update):
            return original(session, owner_id=owner_id, external_id=external_id,
                            for_update=for_update, covering_identity=covering_identity)
        assert covering_identity is not None and not observed

        def commit_competitor():
            with SessionLocal() as other:
                pid = other.scalar(text("SELECT pg_backend_pid()"))
                assert pid != parent_pid
                competitor(other)
                other.commit()
                observed.append(pid)

        if before_lookup:
            commit_competitor()
        row = original(session, owner_id=owner_id, external_id=external_id,
                       for_update=True, covering_identity=covering_identity)
        if not before_lookup:
            assert row is None
            commit_competitor()
        return row

    event_id = external_id
    monkeypatch.setattr(microsoft, "_find_external_event", interleave)
    return observed


def test_native_foreign_insert_after_locked_miss(monkeypatch, scripted_view):
    with world() as parent, world() as outside:
        account, sub = _target(parent.db, parent.user)
        foreign_account, _ = _target(outside.db, outside.user)
        account_id, sub_id = account.id, sub.id
        foreign_account_id, foreign_owner_id = foreign_account.id, outside.user.id
        parent.db.commit()
        outside.db.commit()
        external_id = f"ms-race-insert-{uuid4().hex}"
        payloads, calls = scripted_view
        payloads.append(_payload(external_id))
        signals = []

        def competitor(db):
            account_row = db.get(CalendarAccount, foreign_account_id)
            owner_row = db.get(User, foreign_owner_id)
            _seed(db, owner_row, account_row, "ms-outside", external_id=external_id)

        def collect_native_error(context):
            error = context.original_exception
            signals.append((getattr(error, "sqlstate", None),
                            getattr(getattr(error, "diag", None), "constraint_name", None)))

        observed = _race(parent.db, monkeypatch, external_id, before_lookup=False, competitor=competitor)
        event.listen(engine, "handle_error", collect_native_error)
        try:
            result = _run(parent.db, account, sub)
        finally:
            event.remove(engine, "handle_error", collect_native_error)
            parent.db.rollback()
        _assert_collision(result)
        assert len(observed) == 1
        assert signals == [("23505", "unique_external_event")]
        _assert_view(calls, "ms-selected")
        with SessionLocal() as readback:
            row = _find(readback, external_id)
            assert row.calendar_account_id == foreign_account_id and row.owner_id == foreign_owner_id
            assert row.calendar_id == "ms-outside" and row.title == "legacy-null"
            selected = readback.get(CalendarSubscription, sub_id)
            assert selected.calendar_account_id == account_id
            assert selected.coverage_success_generation is None


def test_native_move_before_locked_relookup(monkeypatch, scripted_view):
    with world() as parent:
        account, sub = _target(parent.db, parent.user)
        row = _seed(parent.db, parent.user, account, sub.external_calendar_id)
        external_id, row_id, sub_id = row.external_event_id, row.id, sub.id
        parent.db.commit()
        payloads, calls = scripted_view
        payloads.append(_payload(external_id))

        def competitor(db):
            moved = db.get(ExternalCalendarEvent, row_id)
            moved.calendar_id = "ms-moved-by-peer"

        observed = _race(parent.db, monkeypatch, external_id, before_lookup=True, competitor=competitor)
        try:
            result = _run(parent.db, account, sub)
        finally:
            parent.db.rollback()
        _assert_collision(result)
        assert len(observed) == 1
        _assert_view(calls, "ms-selected")
        with SessionLocal() as readback:
            moved = readback.get(ExternalCalendarEvent, row_id)
            assert moved.calendar_id == "ms-moved-by-peer"
            assert moved.title == "legacy-null"
            assert readback.get(CalendarSubscription, sub_id).coverage_success_generation is None


def test_legacy_sync_retains_view_and_cursor(db_session, monkeypatch, scripted_view):
    db = db_session
    owner, _ = _owner(db)
    account, sub = _target(db, owner)
    sub.sync_cursor = "fixture-delta-cursor"
    row = _seed(db, owner, account, sub.external_calendar_id)
    identity = (row.id, row.owner_id, row.calendar_account_id, row.calendar_id)
    payloads, calls = scripted_view
    payloads.append(_payload(row.external_event_id))
    monkeypatch.setattr(microsoft, "get_valid_access_token", lambda *_args, **_kwargs: "synthetic-access")
    original = microsoft._apply_subscription_ms_view
    flags = []

    def observe(*args, **kwargs):
        flags.append(kwargs.get("covering", False))
        return original(*args, **kwargs)

    monkeypatch.setattr(microsoft, "_apply_subscription_ms_view", observe)
    start, end = _window()
    count = microsoft.sync_account_events(
        db, settings=_settings(), account=account, time_min=start, time_max=end,
    )
    db.refresh(row)
    db.refresh(sub)
    assert count == 1 and flags == [False]
    _assert_view(calls, sub.external_calendar_id)
    assert identity == (row.id, row.owner_id, row.calendar_account_id, row.calendar_id)
    assert row.title == "Synthetic Microsoft update"
    assert sub.sync_cursor == "fixture-delta-cursor" and sub.coverage_mode == "ms_view"
