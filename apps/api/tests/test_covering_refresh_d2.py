"""Decision 2 covering-refresh validation V1–V39 plus Dex Phase-1 regressions on disposable Postgres.

Contract: ``docs/delivery/0.7-S2-D2-Covering-Refresh-Contract-2026-10-21.md`` §9.
Provider HTTP is mocked. Seeds are committed so token and failure units, which
open their own ``SessionLocal``, can see them. Barrier rows (V23, V38, V39)
use a second and third session; they are not helper-only imitations.
"""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time as time_of_day, timedelta, timezone
from typing import Any, Iterator
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.config import Settings
from app.db import SessionLocal, engine, get_db
from app.main import create_app
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    ExternalCalendarEvent,
    FreeBusySeriesPolicy,
    SchedulePreview,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.calendar_freshness import (
    FRESHNESS_AGE_CEILING,
    evaluate_calendar_freshness,
    required_coverage_window,
)
from app.schemas.calendar import CoveringRefreshRequest
from app.services import covering_refresh as covering_refresh_mod
from app.services import covering_refresh_failure as failure_mod
from app.services import covering_refresh_import as import_mod
from app.services import covering_refresh_locks as locks_mod
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services.calendar_alias_canonicalize import (
    GOOGLE_PRIMARY_ALIAS,
    IDENTITY_UNRESOLVED_CAUSE,
)
from app.services.covering_refresh import run_covering_refresh
from app.services.covering_refresh_locks import covering_identity_fingerprint
from app.services.schedule_preview_apply import apply_schedule_preview
from app.services import scheduling_revision as scheduling_revision_mod
from app.services.scheduling_revision import (
    _OWNER_LOCK_NAMESPACE,
    assert_scheduling_revision,
    increment_scheduling_revision,
    lock_owner_scheduling,
    owner_scheduling_lock_key,
)
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
NOW = datetime(2026, 10, 21, 16, 0, tzinfo=UTC)
_FERNET = Fernet.generate_key().decode("utf-8")


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["host_ip"] == "127.0.0.1"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


@pytest.fixture(autouse=True)
def provider_spies(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock Google/Microsoft reads. Count writes the covering route must not make."""
    state: dict[str, Any] = {
        "fail": set(),
        "events": {},
        "incr_events": {},
        "ms_events": {},
        "list": [],
        "incr": [],
        "ms": [],
        "identity_lists": [],
        "delete_g": 0,
        "delete_m": 0,
        "retry": 0,
        "ensure_primary": 0,
        "http": [],
    }

    def list_events(access: str, calendar_id: str, *, time_min: datetime, time_max: datetime):
        del access, time_min, time_max
        state["list"].append(calendar_id)
        if calendar_id in state["fail"]:
            raise ApiError(502, "upstream unavailable", "CALENDAR_UPSTREAM_BAD_GATEWAY")
        return list(state["events"].get(calendar_id, [])), "next-sync", 1

    def list_incr(access: str, calendar_id: str, sync_token: str):
        del access, sync_token
        state["incr"].append(calendar_id)
        if calendar_id in state["fail"]:
            raise ApiError(502, "upstream unavailable", "CALENDAR_UPSTREAM_BAD_GATEWAY")
        return list(state["incr_events"].get(calendar_id, [])), "next-sync", 1

    def list_view(access: str, calendar_id: str, *, time_min: datetime, time_max: datetime):
        del access, time_min, time_max
        state["ms"].append(calendar_id)
        if calendar_id in state["fail"]:
            raise ApiError(502, "graph unavailable", "MICROSOFT_GRAPH_ERROR")
        return list(state["ms_events"].get(calendar_id, [])), 1, True

    def delete_g(*_a: object, **_k: object) -> None:
        state["delete_g"] += 1

    def delete_m(*_a: object, **_k: object) -> None:
        state["delete_m"] += 1

    def retry(*_a: object, **_k: object) -> set[str]:
        state["retry"] += 1
        return set()

    def ensure(*_a: object, **_k: object) -> None:
        state["ensure_primary"] += 1

    class _Http:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def __enter__(self) -> "_Http":
            return self

        def __exit__(self, *_a: object) -> bool:
            return False

        def request(self, method: str, url: str, **_k: object) -> None:
            state["http"].append(method.upper())
            raise AssertionError(f"unexpected provider HTTP {method} {url}")

        def get(self, url: str, **kwargs: object) -> None:
            self.request("GET", url, **kwargs)

        def post(self, url: str, **kwargs: object) -> None:
            self.request("POST", url, **kwargs)

        def patch(self, url: str, **kwargs: object) -> None:
            self.request("PATCH", url, **kwargs)

        def delete(self, url: str, **kwargs: object) -> None:
            self.request("DELETE", url, **kwargs)

    monkeypatch.setattr(gcal, "list_calendar_events", list_events)
    monkeypatch.setattr(gcal, "list_calendar_events_incremental", list_incr)
    monkeypatch.setattr(gcal, "get_valid_access_token", lambda *_a, **_k: "synthetic-access")
    monkeypatch.setattr(gcal, "delete_google_event", delete_g)
    monkeypatch.setattr(gcal, "ensure_primary_subscription", ensure)
    monkeypatch.setattr(gcal.httpx, "Client", _Http)
    monkeypatch.setattr(ms_cal, "list_calendar_view", list_view)
    monkeypatch.setattr(ms_cal, "get_valid_access_token", lambda *_a, **_k: "synthetic-access")
    monkeypatch.setattr(ms_cal, "delete_microsoft_event", delete_m)
    monkeypatch.setattr(ms_cal.httpx, "Client", _Http)
    monkeypatch.setattr("app.services.mirror_tombstone.retry_pending_deletions", retry)
    return state


def _settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        google_client_id="d2-test-client",
        google_client_secret="d2-test-secret",
        google_redirect_uri="http://127.0.0.1/unused",
        microsoft_client_id="d2-ms-client",
        microsoft_client_secret="d2-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _owner(db: Session) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"d2-renee-{token}@example.test",
        username=f"d2_{token}",
        display_name="D2 covering",
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
        workday_start_local=time_of_day(8, 0),
        workweek_days=5,
        inter_block_buffer_minutes=15,
        upcoming_horizon_days=7,
        default_schedule_style=ScheduleStyle.standalone,
        scheduling_revision=0,
    )
    db.add(settings)
    db.flush()
    return user, settings


def _account(
    db: Session,
    owner: User,
    *,
    provider: CalendarProvider = CalendarProvider.google,
) -> CalendarAccount:
    cfg = _settings()
    account = CalendarAccount(
        owner_id=owner.id,
        provider=provider,
        account_email=f"d2-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc=encrypt_token(cfg, "access-token"),
        refresh_token_enc=encrypt_token(cfg, "refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=False,
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
    sub_id: UUID | None = None,
    enabled: bool = True,
    role: CalendarSubscriptionRole = CalendarSubscriptionRole.informational,
    cursor: str | None = None,
    generation: int = 0,
) -> CalendarSubscription:
    row = CalendarSubscription(
        id=sub_id or uuid.uuid4(),
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary=summary,
        role=role,
        is_enabled=enabled,
        sync_cursor=cursor,
        provider_timezone="UTC",
        coverage_active_generation=generation,
    )
    db.add(row)
    db.flush()
    return row


def _sorted_pair() -> tuple[UUID, UUID]:
    left, right = uuid.uuid4(), uuid.uuid4()
    if str(left) > str(right):
        left, right = right, left
    return left, right


def _window(start: datetime | None = None, days: int = 2) -> tuple[datetime, datetime]:
    start = start or NOW
    return start, start + timedelta(days=days)


def _g_event(event_id: str, start: datetime, end: datetime, *, transparency: str = "opaque") -> dict[str, Any]:
    return {
        "id": event_id,
        "summary": event_id,
        "status": "confirmed",
        "transparency": transparency,
        "start": {"dateTime": start.astimezone(UTC).isoformat().replace("+00:00", "Z")},
        "end": {"dateTime": end.astimezone(UTC).isoformat().replace("+00:00", "Z")},
    }


def _purge(owner_id: UUID) -> None:
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": owner_id})
        db.commit()
    finally:
        db.close()


@dataclass
class World:
    db: Session
    user: User
    settings: UserSettings

    @property
    def owner_id(self) -> UUID:
        return self.user.id


@contextmanager
def world() -> Iterator[World]:
    db = SessionLocal()
    owner_id: UUID | None = None
    try:
        user, settings = _owner(db)
        db.commit()
        owner_id = user.id
        yield World(db=db, user=user, settings=settings)
    finally:
        db.close()
        if owner_id is not None:
            _purge(owner_id)


def _run(
    owner_id: UUID,
    sub_ids: list[UUID],
    start: datetime,
    end: datetime,
    *,
    label: str | None = None,
    now: datetime = NOW,
    clock: Any = None,
):
    db = SessionLocal()
    try:
        body = CoveringRefreshRequest(
            subscription_ids=list(sub_ids),
            window_start=start,
            window_end=end,
            scheduling_horizon_label=label,
        )
        stamped: dict[str, Any] = {"clock": clock} if clock is not None else {"now": now}
        return run_covering_refresh(
            db,
            settings=_settings(),
            owner_id=owner_id,
            body=body,
            **stamped,
        )
    finally:
        db.close()


def _snap(sub_id: UUID) -> dict[str, Any]:
    db = SessionLocal()
    try:
        row = db.get(CalendarSubscription, sub_id)
        assert row is not None
        fail = (
            db.query(CalendarSubscriptionRefreshFailure)
            .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub_id)
            .one_or_none()
        )
        settings = db.query(UserSettings).filter(UserSettings.owner_id == row.owner_id).one()
        return {
            "coverage_success_at": row.coverage_success_at,
            "coverage_mode": row.coverage_mode,
            "active_generation": int(row.coverage_active_generation or 0),
            "success_generation": (
                None if row.coverage_success_generation is None else int(row.coverage_success_generation)
            ),
            "external_calendar_id": row.external_calendar_id,
            "is_enabled": bool(row.is_enabled),
            "sync_cursor": row.sync_cursor,
            "failure_cause": row.coverage_last_failure_cause,
            "sidecar": None if fail is None else fail.cause,
            "sidecar_at": None if fail is None else fail.failure_at,
            "revision": int(settings.scheduling_revision),
            "window_start": row.coverage_window_start,
            "window_end": row.coverage_window_end,
            "role": row.role.value if hasattr(row.role, "value") else str(row.role),
        }
    finally:
        db.close()


def _events(owner_id: UUID, external_id: str | None = None) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = db.query(ExternalCalendarEvent).filter(ExternalCalendarEvent.owner_id == owner_id)
        if external_id is not None:
            query = query.filter(ExternalCalendarEvent.external_event_id == external_id)
        return [
            {
                "id": row.external_event_id,
                "pending": bool(row.pending_deletion),
                "cancelled": bool(row.is_provider_cancelled),
                "transparency": row.transparency,
                "provenance": row.free_busy_provenance,
                "calendar_id": row.calendar_id,
            }
            for row in query.all()
        ]
    finally:
        db.close()


def _no_writes(state: dict[str, Any]) -> None:
    assert state["delete_g"] == 0
    assert state["delete_m"] == 0
    assert state["retry"] == 0
    assert state["http"] == []


def _row(response: Any, sub_id: UUID) -> Any:
    matches = [row for row in response.results if row.subscription_id == sub_id]
    assert len(matches) == 1
    return matches[0]


def _seed_legacy_event(
    db: Session,
    *,
    owner: User,
    account: CalendarAccount,
    calendar_id: str,
    external_id: str,
    start: datetime,
    end: datetime,
    pending: bool = False,
) -> None:
    db.add(
        ExternalCalendarEvent(
            owner_id=owner.id,
            calendar_account_id=account.id,
            provider=account.provider,
            external_event_id=external_id,
            calendar_id=calendar_id,
            title="legacy-null",
            start_time=start,
            end_time=end,
            is_all_day=False,
            pending_deletion=pending,
            last_synced_at=NOW - timedelta(days=30),
            transparency=None,
            free_busy_provenance=None,
            source_timezone="UTC",
            source_zone_missing=False,
            series_identity_state="verified_non_recurring",
            is_provider_cancelled=False,
        )
    )
    db.flush()


def _mint_incremental(sub: CalendarSubscription, start: datetime, end: datetime) -> None:
    sub.sync_cursor = "sync-token-v1"
    sub.coverage_window_start = start
    sub.coverage_window_end = end
    sub.coverage_mode = "full"
    sub.coverage_success_at = NOW - timedelta(hours=1)
    sub.coverage_fetched_at = NOW - timedelta(hours=1)
    sub.coverage_pagination_complete = True
    sub.coverage_active_generation = 1
    sub.coverage_success_generation = 1
    sub.coverage_show_deleted = True
    sub.coverage_single_events = True
    sub.coverage_page_count = 1
    sub.coverage_item_count = 0


@contextmanager
def _http_as(owner_id: UUID) -> Iterator[TestClient]:
    """Real HTTP route with this owner, using committed SessionLocal rows."""
    app = create_app()

    def _db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _user() -> User:
        db = SessionLocal()
        try:
            row = db.get(User, owner_id)
            assert row is not None
            db.expunge(row)
            return row
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _post_refresh(client: TestClient, sub_ids: list[UUID], start: datetime, end: datetime, **extra: object):
    body: dict[str, object] = {
        "subscription_ids": [str(item) for item in sub_ids],
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }
    body.update(extra)
    return client.post("/api/v1/calendar/covering-refresh", json=body)


def test_v1_no_provider_writes_or_tombstone_retry(provider_spies: dict[str, Any]) -> None:
    """V1: a successful covering pull never calls tombstone retry or event writes."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v1", summary="V1")
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
    assert response.overall_outcome == "success"
    assert provider_spies["list"] == ["cal-v1"]
    assert provider_spies["ensure_primary"] == 0
    _no_writes(provider_spies)


def test_v2_suppression_without_delete(provider_spies: dict[str, Any]) -> None:
    """V2: pending-deletion id is skipped on apply and no provider delete runs."""
    start, end = _window()
    event_id = f"tomb-{uuid.uuid4().hex}"
    event_start = NOW + timedelta(hours=2)
    event_end = event_start + timedelta(hours=1)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v2", summary="V2")
        _seed_legacy_event(
            w.db,
            owner=w.user,
            account=account,
            calendar_id="cal-v2",
            external_id=event_id,
            start=event_start,
            end=event_end,
            pending=True,
        )
        w.db.commit()
        provider_spies["events"]["cal-v2"] = [_g_event(event_id, event_start, event_end)]
        response = _run(w.owner_id, [sub.id], start, end)
        rows = _events(w.owner_id, event_id)
    assert response.overall_outcome == "success"
    assert rows == [
        {
            "id": event_id,
            "pending": True,
            "cancelled": False,
            "transparency": None,
            "provenance": None,
            "calendar_id": "cal-v2",
        }
    ]
    _no_writes(provider_spies)


def test_v3_prepare_reports_canonicalize_identity(provider_spies: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """V3: primary alias rewrite is reported and the requested set is not widened."""
    start, end = _window()

    def _list(token: str) -> list[dict[str, Any]]:
        provider_spies["identity_lists"].append(token)
        return [{"id": "canon-cal-v3", "primary": True, "summary": "Primary"}]

    monkeypatch.setattr(gcal, "list_google_calendars", _list)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(
            w.db,
            account,
            calendar_id=GOOGLE_PRIMARY_ALIAS,
            summary="Alias",
            role=CalendarSubscriptionRole.primary,
        )
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    row = _row(response, sub.id)
    assert row.status == "ok"
    assert "canonicalize_identity" in row.preflight_effects
    assert snap["external_calendar_id"] == "canon-cal-v3"
    assert snap["role"] == "primary"
    assert len(response.results) == 1
    assert provider_spies["identity_lists"]
    assert provider_spies["list"] == ["canon-cal-v3"]
    _no_writes(provider_spies)


def test_v4_identity_blocked_preflight_skips_list(provider_spies: dict[str, Any]) -> None:
    """V4: T1-F blocked subscription is a preflight row and the list mock is not called."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v4", summary="Blocked")
        sub.coverage_last_failure_cause = IDENTITY_UNRESOLVED_CAUSE
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    row = _row(response, sub.id)
    assert response.overall_outcome == "no_op"
    assert row.phase == "preflight"
    assert row.preflight_code == "CALENDAR_IDENTITY_BLOCKED"
    assert snap["coverage_success_at"] is None
    assert provider_spies["list"] == []
    assert provider_spies["identity_lists"] == []
    _no_writes(provider_spies)


def test_v5_google_covering_resolves_legacy_null(provider_spies: dict[str, Any]) -> None:
    """V5: covering clears the cursor and full-fetches a legacy null/null row."""
    start, end = _window()
    event_id = f"legacy-{uuid.uuid4().hex}"
    event_start = NOW + timedelta(hours=3)
    event_end = event_start + timedelta(minutes=30)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v5", summary="Legacy")
        _mint_incremental(sub, start, end)
        _seed_legacy_event(
            w.db,
            owner=w.user,
            account=account,
            calendar_id="cal-v5",
            external_id=event_id,
            start=event_start,
            end=event_end,
        )
        w.db.commit()
        provider_spies["events"]["cal-v5"] = [
            _g_event(event_id, event_start, event_end, transparency="opaque")
        ]
        response = _run(w.owner_id, [sub.id], start, end)
        rows = _events(w.owner_id, event_id)
    assert response.coverage_action.all_requested_covering_ok is True
    assert _row(response, sub.id).status == "ok"
    assert provider_spies["incr"] == []
    assert provider_spies["list"] == ["cal-v5"]
    assert rows[0]["transparency"] == "opaque"
    assert rows[0]["provenance"] == "provider_explicit"


def test_v6_legacy_incremental_leaves_legacy_null(provider_spies: dict[str, Any]) -> None:
    """V6 control: the same cursor fixture on legacy sync does not resolve the null row."""
    start, end = _window()
    event_id = f"legacy-{uuid.uuid4().hex}"
    event_start = NOW + timedelta(hours=3)
    event_end = event_start + timedelta(minutes=30)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v6", summary="Legacy")
        _mint_incremental(sub, start, end)
        _seed_legacy_event(
            w.db,
            owner=w.user,
            account=account,
            calendar_id="cal-v6",
            external_id=event_id,
            start=event_start,
            end=event_end,
        )
        w.db.commit()
        db = SessionLocal()
        try:
            live = db.get(CalendarAccount, account.id)
            assert live is not None
            gcal.sync_account_events(
                db,
                settings=_settings(),
                account=live,
                time_min=start,
                time_max=end,
            )
            db.commit()
        finally:
            db.close()
        rows = _events(w.owner_id, event_id)
    assert provider_spies["list"] == []
    assert provider_spies["incr"] == ["cal-v6"]
    assert rows[0]["transparency"] is None
    assert rows[0]["provenance"] is None


def test_v7_ms_view_soft_cancels_and_mints_coverage(provider_spies: dict[str, Any]) -> None:
    """V7: a stale immovable missing from calendarView is soft-cancelled and coverage is ms_view."""
    start, end = _window()
    event_id = f"ms-{uuid.uuid4().hex}"
    event_start = NOW + timedelta(hours=4)
    event_end = event_start + timedelta(hours=1)
    with world() as w:
        account = _account(w.db, w.user, provider=CalendarProvider.microsoft)
        sub = _sub(w.db, account, calendar_id="cal-v7", summary="MS")
        _seed_legacy_event(
            w.db,
            owner=w.user,
            account=account,
            calendar_id="cal-v7",
            external_id=event_id,
            start=event_start,
            end=event_end,
        )
        db_row = (
            w.db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.external_event_id == event_id)
            .one()
        )
        db_row.transparency = "opaque"
        db_row.free_busy_provenance = "provider_explicit"
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
        rows = _events(w.owner_id, event_id)
    assert _row(response, sub.id).status == "ok"
    assert snap["coverage_mode"] == "ms_view"
    assert snap["coverage_success_at"] == NOW
    assert rows[0]["cancelled"] is True
    assert provider_spies["ms"] == ["cal-v7"]
    _no_writes(provider_spies)


def test_v8_a_ok_b_fail_same_account_fresh_session(provider_spies: dict[str, Any]) -> None:
    """V8: fresh session sees A's mint after B's failure on the same account."""
    start, end = _window()
    a_id, b_id = _sorted_pair()
    with world() as w:
        account = _account(w.db, w.user)
        sub_a = _sub(w.db, account, calendar_id="cal-v8a", summary="A", sub_id=a_id)
        sub_b = _sub(w.db, account, calendar_id="cal-v8b", summary="B", sub_id=b_id)
        w.db.commit()
        provider_spies["fail"].add("cal-v8b")
        response = _run(w.owner_id, [sub_a.id, sub_b.id], start, end)
        fresh_a = _snap(sub_a.id)
        fresh_b = _snap(sub_b.id)
    assert response.overall_outcome == "partial"
    assert _row(response, sub_a.id).status == "ok"
    assert _row(response, sub_b.id).status == "failed"
    assert fresh_a["coverage_success_at"] is not None
    assert fresh_b["coverage_success_at"] is None
    assert fresh_b["sidecar"]


def test_v9_b_fail_then_a_ok_inverse_order(provider_spies: dict[str, Any]) -> None:
    """V9: failure first still leaves the later success committed."""
    start, end = _window()
    fail_id, ok_id = _sorted_pair()
    with world() as w:
        account = _account(w.db, w.user)
        failing = _sub(w.db, account, calendar_id="cal-v9-fail", summary="Fail", sub_id=fail_id)
        ok = _sub(w.db, account, calendar_id="cal-v9-ok", summary="Ok", sub_id=ok_id)
        w.db.commit()
        provider_spies["fail"].add("cal-v9-fail")
        response = _run(w.owner_id, [failing.id, ok.id], start, end)
        fresh_ok = _snap(ok.id)
        fresh_fail = _snap(failing.id)
    assert [row.subscription_id for row in response.results] == [fail_id, ok_id]
    assert fresh_fail["coverage_success_at"] is None
    assert fresh_fail["sidecar"]
    assert fresh_ok["coverage_success_at"] is not None
    assert fresh_ok["sidecar"] is None


def test_v10_later_account_failure_leaves_account1(provider_spies: dict[str, Any]) -> None:
    """V10: account 2 failure does not roll back account 1's committed mint."""
    start, end = _window()
    first_id, second_id = _sorted_pair()
    seen: dict[str, Any] = {}
    real = covering_refresh_mod._process_one_target

    def _wrapped(db: Session, **kwargs: Any):
        result = real(db, **kwargs)
        if result.subscription_id == first_id:
            seen["mid"] = _snap(first_id)
        return result

    with world() as w:
        account1 = _account(w.db, w.user)
        account2 = _account(w.db, w.user)
        sub1 = _sub(w.db, account1, calendar_id="cal-v10-a", summary="A1", sub_id=first_id)
        sub2 = _sub(w.db, account2, calendar_id="cal-v10-b", summary="A2", sub_id=second_id)
        w.db.commit()
        provider_spies["fail"].add("cal-v10-b")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(covering_refresh_mod, "_process_one_target", _wrapped)
            response = _run(w.owner_id, [sub1.id, sub2.id], start, end)
        final = _snap(sub1.id)
        failed = _snap(sub2.id)
    assert response.overall_outcome == "partial"
    assert seen["mid"]["coverage_success_at"] is not None
    assert final["coverage_success_at"] == seen["mid"]["coverage_success_at"]
    assert final["active_generation"] == seen["mid"]["active_generation"]
    assert final["success_generation"] == seen["mid"]["success_generation"]
    assert failed["coverage_success_at"] is None
    assert failed["sidecar"]


def test_v11_revision_bumped_mid_batch_not_ready(provider_spies: dict[str, Any]) -> None:
    """V11: busy import bumps revision inside A's commit; a later failure is not scheduling_ready."""
    start, end = _window()
    a_id, b_id = _sorted_pair()
    event_id = f"busy-{uuid.uuid4().hex}"
    event_start = NOW + timedelta(hours=2)
    with world() as w:
        account = _account(w.db, w.user)
        sub_a = _sub(w.db, account, calendar_id="cal-v11a", summary="A", sub_id=a_id)
        sub_b = _sub(w.db, account, calendar_id="cal-v11b", summary="B", sub_id=b_id)
        w.db.commit()
        start_rev = _snap(sub_a.id)["revision"]
        provider_spies["events"]["cal-v11a"] = [
            _g_event(event_id, event_start, event_start + timedelta(hours=1))
        ]
        provider_spies["fail"].add("cal-v11b")
        response = _run(w.owner_id, [sub_a.id, sub_b.id], start, end)
        final = _snap(sub_a.id)
        rows = _events(w.owner_id, event_id)
    assert response.overall_outcome == "partial"
    assert response.scheduling_revision_bumped is True
    assert response.scheduling_revision_at_end is not None
    assert response.scheduling_revision_at_end > start_rev
    assert response.scheduling_readiness is not None
    assert response.scheduling_readiness.scheduling_ready is False
    assert final["revision"] == response.scheduling_revision_at_end
    assert rows


def test_v12_forced_rollback_never_status_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """V12: apply explosion rolls the unit back. The row is failed and coverage_success_at stays null."""
    start, end = _window()

    def _boom(*_a: object, **_k: object) -> int:
        raise RuntimeError("forced covering rollback")

    monkeypatch.setattr(import_mod, "_apply_provider", _boom)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v12", summary="Rollback")
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    row = _row(response, sub.id)
    assert row.status == "failed"
    assert row.status != "ok"
    assert response.overall_outcome == "failed"
    assert snap["coverage_success_at"] is None
    assert snap["sidecar"]


def test_v13_subset_versus_all_enabled_freshness() -> None:
    """V13: one requested sub can be covering-ok while the enabled sibling keeps scheduling_ready false."""
    with world() as w:
        account = _account(w.db, w.user)
        requested = _sub(w.db, account, calendar_id="cal-v13-yes", summary="Requested")
        sibling = _sub(w.db, account, calendar_id="cal-v13-no", summary="Sibling stale")
        w.db.commit()
        w.db.refresh(w.settings)
        start, end = required_coverage_window(w.settings, NOW)
        response = _run(w.owner_id, [requested.id], start, end)
    readiness = response.scheduling_readiness
    assert readiness is not None
    assert response.coverage_action.all_requested_covering_ok is True
    freshness = readiness.freshness_all_enabled or {}
    assert freshness.get("ok") is False
    names = {item.get("calendar_name") for item in freshness.get("blocking_diagnostics") or []}
    assert "Sibling stale" in names
    assert readiness.scheduling_ready is False
    assert len(response.results) == 1


def test_v14_busy_input_trust_blocks_on_legacy_null() -> None:
    """V14: readiness includes busy_input_trust and blocks while a legacy null row remains."""
    start = NOW + timedelta(days=60)
    end = NOW + timedelta(days=70)
    event_id = f"null-{uuid.uuid4().hex}"
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v14", summary="Far")
        _seed_legacy_event(
            w.db,
            owner=w.user,
            account=account,
            calendar_id="cal-v14",
            external_id=event_id,
            start=NOW + timedelta(hours=2),
            end=NOW + timedelta(hours=3),
        )
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        still = _events(w.owner_id, event_id)
    trust = response.scheduling_readiness.busy_input_trust if response.scheduling_readiness else None
    assert isinstance(trust, dict)
    assert trust.get("ok") is False
    causes = {item.get("cause") for item in trust.get("blocking_diagnostics") or []}
    assert "unknown_free_busy" in causes
    assert still[0]["transparency"] is None
    assert response.scheduling_readiness is not None
    assert response.scheduling_readiness.scheduling_ready is False


def test_v15_evaluated_at_matches_post_commit_revision() -> None:
    """V15: evaluated_at is the assessment instant and the revision matches the committed owner row."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v15", summary="Rev")
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    readiness = response.scheduling_readiness
    assert readiness is not None
    assert readiness.evaluated_at == NOW
    assert readiness.scheduling_revision == snap["revision"]
    assert response.scheduling_revision_at_end == snap["revision"]


def test_v16_window_never_widened() -> None:
    """V16: effective window equals the requested UTC bounds and widen flags stay frozen."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v16", summary="Window")
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
    assert response.window_requested.start == start
    assert response.window_requested.end == end
    assert response.window_effective.start == start
    assert response.window_effective.end == end
    assert response.window_widened is False
    assert response.window_widen_reason == "none"


def test_v17_readiness_horizon_is_not_the_visible_window() -> None:
    """V17: scheduling_readiness.horizon comes from required_coverage_window, not the visible pull."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v17", summary="Horizon")
        w.db.commit()
        w.db.refresh(w.settings)
        horizon_start, horizon_end = required_coverage_window(w.settings, NOW)
        response = _run(w.owner_id, [sub.id], start, end, label="ui-week")
    readiness = response.scheduling_readiness
    assert readiness is not None and readiness.horizon is not None
    assert (start, end) != (horizon_start, horizon_end)
    assert readiness.horizon.start == horizon_start
    assert readiness.horizon.end == horizon_end
    assert readiness.horizon_label == "ui-week"
    assert response.window_effective.start == start


def test_v18_http_200_partial_when_one_sub_returns_502(provider_spies: dict[str, Any]) -> None:
    """V18: one mocked 502 is overall partial and the route returns HTTP 200, not 502."""
    start, end = _window()
    ok_id, bad_id = _sorted_pair()
    with world() as w:
        account = _account(w.db, w.user)
        ok = _sub(w.db, account, calendar_id="cal-v18-ok", summary="Ok", sub_id=ok_id)
        bad = _sub(w.db, account, calendar_id="cal-v18-bad", summary="Bad", sub_id=bad_id)
        w.db.commit()
        provider_spies["fail"].add("cal-v18-bad")
        with _http_as(w.owner_id) as client:
            http = _post_refresh(client, [ok.id, bad.id], start, end)
    assert http.status_code == 200, http.text
    body = http.json()
    assert body["overall_outcome"] == "partial"
    statuses = {row["subscription_id"]: row["status"] for row in body["results"]}
    assert statuses[str(ok_id)] == "ok"
    assert statuses[str(bad_id)] == "failed"


def test_v19_no_op_when_every_target_is_preflight() -> None:
    """V19: disabled targets produce no_op and honest preflight counts."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        first = _sub(w.db, account, calendar_id="cal-v19a", summary="Off A", enabled=False)
        second = _sub(w.db, account, calendar_id="cal-v19b", summary="Off B", enabled=False)
        w.db.commit()
        response = _run(w.owner_id, [first.id, second.id], start, end)
    assert response.overall_outcome == "no_op"
    assert response.action_summary.requested == 2
    assert response.action_summary.preflight_rejected == 2
    assert response.action_summary.import_attempted == 0
    assert response.action_summary.import_ok == 0
    assert response.action_summary.import_failed == 0


def test_v20_same_sub_serialization_and_sequential_control() -> None:
    """V20: overlapping same-sub refreshes serialize. Back-to-back refreshes may both succeed.

    Evidenced by two threads and two sessions. Minted generations are distinct.
    Neither caller gets HTTP 409; the route is not involved in a conflict response.
    """
    start, end = _window()
    errors: list[BaseException] = []
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def _one(owner_id: UUID, sub_id: UUID) -> None:
        try:
            barrier.wait(30)
            response = _run(owner_id, [sub_id], start, end)
            outcomes.append(response.results[0].status)
        except BaseException as exc:  # noqa: BLE001 — thread boundary
            errors.append(exc)

    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v20", summary="Serial", generation=0)
        w.db.commit()
        threads = [threading.Thread(target=_one, args=(w.owner_id, sub.id)) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        assert errors == []
        after_overlap = _snap(sub.id)
        sequential = [_run(w.owner_id, [sub.id], start, end) for _ in range(2)]
        final = _snap(sub.id)
    assert outcomes.count("ok") == 2
    assert after_overlap["active_generation"] == 2
    assert after_overlap["active_generation"] == after_overlap["success_generation"]
    assert all(item.overall_outcome == "success" for item in sequential)
    assert final["coverage_success_at"] is not None
    assert final["active_generation"] == final["success_generation"] == 4


def test_v21a_disable_before_reacquire(monkeypatch: pytest.MonkeyPatch) -> None:
    """V21a: disable after the token unit returns and before the import unit reacquires locks.

    The import unit's own preflight then rejects. No coverage success is minted.
    """
    start, end = _window()
    real = covering_refresh_mod.read_covering_access_token

    def _wrapped(**kwargs: Any):
        token = real(**kwargs)
        db = SessionLocal()
        try:
            row = db.get(CalendarSubscription, kwargs["subscription_id"])
            assert row is not None
            row.is_enabled = False
            db.commit()
        finally:
            db.close()
        return token

    monkeypatch.setattr(covering_refresh_mod, "read_covering_access_token", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v21a", summary="Disable")
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    row = _row(response, sub.id)
    assert row.phase == "preflight"
    assert row.preflight_code == "CALENDAR_SUBSCRIPTION_DISABLED"
    assert snap["coverage_success_at"] is None
    assert snap["is_enabled"] is False


def test_v21b_disable_after_serialized_success() -> None:
    """V21b: a disable after a committed success makes the next attempt preflight-only.

    The earlier mint's success timestamp and generation stay as read back.
    """
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v21b", summary="Later")
        w.db.commit()
        first = _run(w.owner_id, [sub.id], start, end)
        before = _snap(sub.id)
        db = SessionLocal()
        try:
            row = db.get(CalendarSubscription, sub.id)
            assert row is not None
            row.is_enabled = False
            db.commit()
        finally:
            db.close()
        second = _run(w.owner_id, [sub.id], start, end)
        after = _snap(sub.id)
    assert _row(first, sub.id).status == "ok"
    assert _row(second, sub.id).preflight_code == "CALENDAR_SUBSCRIPTION_DISABLED"
    assert second.overall_outcome == "no_op"
    assert after["coverage_success_at"] == before["coverage_success_at"]
    assert after["success_generation"] == before["success_generation"]
    assert after["active_generation"] == before["active_generation"]


def test_v21c_post_fetch_generation_bump_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    """V21c: generation changed after the mock fetch returns aborts apply.

    Feasible probe: the pull returns, then the same locked session flushes a
    generation bump before post-fetch re-check. That is not a second connection
    writing through the FOR UPDATE. No success mint survives.
    """
    start, end = _window()
    real = import_mod._pull_provider

    def _wrapped(db: Session, **kwargs: Any):
        pulled = real(db, **kwargs)
        subscription = kwargs["subscription"]
        subscription.coverage_active_generation = int(subscription.coverage_active_generation or 0) + 9
        db.flush()
        return pulled

    monkeypatch.setattr(import_mod, "_pull_provider", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v21c", summary="Gen", generation=2)
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    row = _row(response, sub.id)
    assert row.status == "failed"
    assert row.cause == "covering_post_fetch_generation"
    assert snap["coverage_success_at"] is None
    assert snap["success_generation"] is None
    # The +9 probe rolled back with the import. No prior success, so the failure
    # unit does not bump generation; the seed value is what remains.
    assert snap["active_generation"] == 2


def test_v22_cross_account_google_and_microsoft() -> None:
    """V22: one POST imports Google and Microsoft subs and reports one owner readiness."""
    start, end = _window()
    g_id, m_id = _sorted_pair()
    with world() as w:
        google = _account(w.db, w.user, provider=CalendarProvider.google)
        microsoft = _account(w.db, w.user, provider=CalendarProvider.microsoft)
        g_sub = _sub(w.db, google, calendar_id="cal-v22-g", summary="G", sub_id=g_id)
        m_sub = _sub(w.db, microsoft, calendar_id="cal-v22-m", summary="M", sub_id=m_id)
        w.db.commit()
        response = _run(w.owner_id, [g_sub.id, m_sub.id], start, end)
        g_snap = _snap(g_sub.id)
        m_snap = _snap(m_sub.id)
    assert response.overall_outcome == "success"
    assert g_snap["coverage_mode"] == "full"
    assert m_snap["coverage_mode"] == "ms_view"
    assert response.scheduling_readiness is not None
    assert response.scheduling_readiness.scheduling_revision == g_snap["revision"] == m_snap["revision"]


def test_v23_revision_atomicity_barrier_separate_session(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V23: after sub A commits and before sub B starts, another session already rejects.

    The pause is a monkeypatch around ``_process_one_target`` after A returns,
    so A's commit has already released the owner advisory lock. The barrier
    session sees A's new busy row, then ``assert_scheduling_revision`` returns
    409 ``SCHEDULING_REVISION_CONFLICT`` and ``apply_schedule_preview`` returns
    409 ``PREVIEW_STALE`` against the pre-request revision. Fingerprint
    collection is stubbed because this disposable schema lacks
    ``tasks.start_no_earlier_at``; the stub returns the preview's own
    fingerprint so the reject is the revision compare.
    """
    start, end = _window()
    a_id, b_id = _sorted_pair()
    event_id = f"busy-{uuid.uuid4().hex}"
    event_start = NOW + timedelta(hours=2)
    after_a = threading.Event()
    release = threading.Event()
    receipt: dict[str, Any] = {}
    errors: list[BaseException] = []
    real = covering_refresh_mod._process_one_target

    def _wrapped(db: Session, **kwargs: Any):
        result = real(db, **kwargs)
        if result.subscription_id == a_id:
            after_a.set()
            if not release.wait(60):
                raise TimeoutError("V23 barrier did not release the orchestrator")
        return result

    monkeypatch.setattr(covering_refresh_mod, "_process_one_target", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        sub_a = _sub(w.db, account, calendar_id="cal-v23a", summary="A", sub_id=a_id)
        _sub(w.db, account, calendar_id="cal-v23b", summary="B", sub_id=b_id)
        start_rev = int(w.settings.scheduling_revision)
        preview = SchedulePreview(
            owner_id=w.owner_id,
            status="ready",
            scheduling_revision=start_rev,
            proposal_json={"proposed_blocks": []},
            input_fingerprint="d2-v23-pre-request",
            input_snapshot=None,
            expires_at=datetime.now(UTC) + timedelta(days=2),
        )
        w.db.add(preview)
        w.db.commit()
        preview_id = preview.id
        provider_spies["events"]["cal-v23a"] = [
            _g_event(event_id, event_start, event_start + timedelta(hours=1))
        ]

        def _barrier() -> None:
            db = SessionLocal()
            try:
                if not after_a.wait(60):
                    raise TimeoutError("V23 orchestrator never committed sub A")
                visible = _events(w.owner_id, event_id)
                rev = int(
                    db.query(UserSettings)
                    .filter(UserSettings.owner_id == w.owner_id)
                    .one()
                    .scheduling_revision
                )
                receipt["visible"] = bool(visible)
                receipt["revision"] = rev
                with pytest.raises(ApiError) as revision_conflict:
                    assert_scheduling_revision(rev, start_rev)
                receipt["revision_code"] = revision_conflict.value.content["code"]
                receipt["revision_status"] = revision_conflict.value.status_code
                user = db.get(User, w.owner_id)
                stored = db.get(SchedulePreview, preview_id)
                assert user is not None and stored is not None
                # Disposable schema has no tasks.start_no_earlier_at, so collect_inputs
                # cannot run. Return the preview's stored fingerprint and let the real
                # revision compare inside apply_schedule_preview reject.
                monkeypatch.setattr(
                    "app.services.schedule_preview_apply.live_owner_fingerprint",
                    lambda *_a, **_k: ({}, "d2-v23-pre-request"),
                )
                with pytest.raises(ApiError) as preview_stale:
                    apply_schedule_preview(db, user, stored)
                receipt["preview_code"] = preview_stale.value.content["code"]
                receipt["preview_status"] = preview_stale.value.status_code
            except BaseException as exc:  # noqa: BLE001 — barrier thread
                errors.append(exc)
            finally:
                db.rollback()
                db.close()
                release.set()

        worker = threading.Thread(target=_barrier)
        worker.start()
        try:
            response = _run(w.owner_id, [a_id, b_id], start, end)
        finally:
            release.set()
            worker.join(30)
    assert errors == []
    assert receipt["visible"] is True
    assert receipt["revision"] > start_rev
    assert receipt["revision_status"] == 409
    assert receipt["revision_code"] == "SCHEDULING_REVISION_CONFLICT"
    assert receipt["preview_status"] == 409
    assert receipt["preview_code"] == "PREVIEW_STALE"
    assert response.results[0].status == "ok"


def test_v24_interrupted_mid_orchestration_readback(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V24: abort after A's commit. A fresh session sees A's busy row and the revision bump together.

    B never starts, so it has no success and no failure sidecar. The request
    raises instead of returning scheduling_ready.
    """
    start, end = _window()
    a_id, b_id = _sorted_pair()
    event_id = f"busy-{uuid.uuid4().hex}"
    event_start = NOW + timedelta(hours=1)
    real = covering_refresh_mod._process_one_target

    def _wrapped(db: Session, **kwargs: Any):
        result = real(db, **kwargs)
        if result.subscription_id == a_id:
            raise RuntimeError("operator abort after sub A commit")
        return result

    monkeypatch.setattr(covering_refresh_mod, "_process_one_target", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        sub_a = _sub(w.db, account, calendar_id="cal-v24a", summary="A", sub_id=a_id)
        sub_b = _sub(w.db, account, calendar_id="cal-v24b", summary="B", sub_id=b_id)
        w.db.commit()
        start_rev = _snap(sub_a.id)["revision"]
        provider_spies["events"]["cal-v24a"] = [
            _g_event(event_id, event_start, event_start + timedelta(hours=1))
        ]
        with pytest.raises(RuntimeError, match="operator abort"):
            _run(w.owner_id, [sub_a.id, sub_b.id], start, end)
        snap_a = _snap(sub_a.id)
        snap_b = _snap(sub_b.id)
        rows = _events(w.owner_id, event_id)
    assert snap_a["coverage_success_at"] is not None
    assert snap_a["revision"] > start_rev
    assert rows
    assert snap_b["coverage_success_at"] is None
    assert snap_b["sidecar"] is None


def _record_covering_lock_order(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    order: list[str] = []
    real_account = locks_mod.lock_calendar_account_for_identity
    real_owner = locks_mod.lock_owner_scheduling

    def _account(db: Session, account_id: UUID) -> CalendarAccount:
        order.append("account")
        return real_account(db, account_id)

    def _owner(db: Session, owner_id: UUID) -> UserSettings:
        order.append("owner")
        return real_owner(db, owner_id)

    monkeypatch.setattr(locks_mod, "lock_calendar_account_for_identity", _account)
    monkeypatch.setattr(locks_mod, "lock_owner_scheduling", _owner)
    return order


def _pause_legacy_owner_lock(monkeypatch: pytest.MonkeyPatch) -> tuple[list[int], threading.Event, threading.Event]:
    """Hold legacy sync inside ``lock_owner_scheduling`` after the advisory lock is taken."""
    legacy_ident: list[int] = []
    holding = threading.Event()
    release = threading.Event()
    paused = {"done": False}
    real_owner = scheduling_revision_mod.lock_owner_scheduling

    def _owner(db: Session, owner_id: UUID) -> UserSettings:
        row = real_owner(db, owner_id)
        if legacy_ident and threading.get_ident() == legacy_ident[0] and not paused["done"]:
            paused["done"] = True
            holding.set()
            if not release.wait(30):
                raise TimeoutError("legacy owner-lock pause was not released")
        return row

    monkeypatch.setattr(scheduling_revision_mod, "lock_owner_scheduling", _owner)
    return legacy_ident, holding, release


def test_v25_lock_order_versus_legacy_different_sub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V25: legacy sync and covering on different subs share the owner lock and both finish.

    Covering's recorded stack is account-identity then owner. Legacy holds the
    owner advisory lock (its own ``lock_owner_scheduling``) until released;
    covering does not finish during that hold.
    """
    start, end = _window()
    order = _record_covering_lock_order(monkeypatch)
    legacy_ident, holding, release = _pause_legacy_owner_lock(monkeypatch)
    errors: list[BaseException] = []
    covering_done = threading.Event()
    with world() as w:
        legacy_account = _account(w.db, w.user)
        cover_account = _account(w.db, w.user)
        legacy_sub = _sub(w.db, legacy_account, calendar_id="cal-v25-legacy", summary="Legacy")
        cover_sub = _sub(w.db, cover_account, calendar_id="cal-v25-cover", summary="Cover")
        w.db.commit()

        def _legacy() -> None:
            legacy_ident.append(threading.get_ident())
            db = SessionLocal()
            try:
                account = db.get(CalendarAccount, legacy_account.id)
                assert account is not None
                gcal.sync_account_events(
                    db, settings=_settings(), account=account, time_min=start, time_max=end
                )
                db.commit()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
                db.rollback()
            finally:
                db.close()
                release.set()

        def _cover() -> None:
            try:
                response = _run(w.owner_id, [cover_sub.id], start, end)
                if response.results[0].status != "ok":
                    errors.append(AssertionError(response.results[0].status))
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                covering_done.set()

        legacy_thread = threading.Thread(target=_legacy)
        cover_thread = threading.Thread(target=_cover)
        legacy_thread.start()
        assert holding.wait(30), "legacy sync never reached the owner lock"
        cover_thread.start()
        time.sleep(1.5)
        assert not covering_done.is_set()
        release.set()
        legacy_thread.join(30)
        cover_thread.join(30)
        assert _snap(legacy_sub.id)["coverage_success_at"] is not None
        assert _snap(cover_sub.id)["coverage_success_at"] is not None
    assert errors == []
    assert order[0] == "account"
    assert any(name == "owner" for name in order)
    for index, name in enumerate(order):
        if name == "owner":
            assert index > 0 and order[index - 1] == "account"


def test_v26_post_fetch_disable_aborts_without_mint(monkeypatch: pytest.MonkeyPatch) -> None:
    """V26: disable flushed after the mock fetch returns fails the post-fetch re-check.

    Same locked session as V21c. The disable rolls back with the import, and
    no coverage success is minted.
    """
    start, end = _window()
    real = import_mod._pull_provider

    def _wrapped(db: Session, **kwargs: Any):
        pulled = real(db, **kwargs)
        kwargs["subscription"].is_enabled = False
        db.flush()
        return pulled

    monkeypatch.setattr(import_mod, "_pull_provider", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v26", summary="Disable")
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    assert _row(response, sub.id).status == "failed"
    assert _row(response, sub.id).cause == "covering_post_fetch_disabled"
    assert snap["coverage_success_at"] is None
    assert snap["is_enabled"] is True


def test_v27_no_primary_non_primary_import_proceeds(provider_spies: dict[str, Any]) -> None:
    """V27: an enabled identity-verified non-primary is imported. No primary bootstrap."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(
            w.db,
            account,
            calendar_id="cal-v27-info",
            summary="Informational only",
            role=CalendarSubscriptionRole.informational,
        )
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    assert response.overall_outcome == "success"
    assert snap["role"] == "informational"
    assert snap["coverage_success_at"] is not None
    assert provider_spies["ensure_primary"] == 0


def test_v28_cross_owner_is_non_enumerating_422(
    provider_spies: dict[str, Any],
) -> None:
    """V28: a foreign subscription id aborts the whole POST before any provider read."""
    start, end = _window()
    other_id: UUID | None = None
    with world() as w:
        try:
            account = _account(w.db, w.user)
            own = _sub(w.db, account, calendar_id="cal-v28-own", summary="Own")
            other_db = SessionLocal()
            try:
                other_user, _settings_row = _owner(other_db)
                other_account = _account(other_db, other_user)
                foreign = _sub(
                    other_db, other_account, calendar_id="cal-v28-foreign", summary="Foreign"
                )
                other_db.commit()
                other_id = other_user.id
                foreign_id = foreign.id
            finally:
                other_db.close()
            w.db.commit()
            with _http_as(w.owner_id) as client:
                http = _post_refresh(client, [own.id, foreign_id], start, end)
        finally:
            if other_id is not None:
                _purge(other_id)
    assert http.status_code == 422
    body = http.json()
    assert body["code"] == "CALENDAR_SUBSCRIPTION_NOT_ELIGIBLE"
    assert "results" not in body
    assert provider_spies["list"] == []
    assert provider_spies["ms"] == []
    assert provider_spies["retry"] == 0
    assert provider_spies["http"] == []


def test_v29_window_over_42_days_is_422(provider_spies: dict[str, Any]) -> None:
    """V29: span over 42 days is 422 CALENDAR_WINDOW_TOO_LARGE before any pull."""
    start = NOW
    end = NOW + timedelta(days=42, seconds=1)
    with world() as w:
        with _http_as(w.owner_id) as client:
            http = _post_refresh(client, [uuid.uuid4()], start, end)
    assert http.status_code == 422
    assert http.json()["code"] == "CALENDAR_WINDOW_TOO_LARGE"
    assert provider_spies["list"] == []
    assert provider_spies["retry"] == 0


def test_v30_mixed_own_account_preflight_is_partial(provider_spies: dict[str, Any]) -> None:
    """V30: one disabled and one eligible sub is HTTP-shaped partial, disabled row only for the disabled sub."""
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        disabled = _sub(w.db, account, calendar_id="cal-v30-off", summary="Off", enabled=False)
        enabled = _sub(w.db, account, calendar_id="cal-v30-on", summary="On")
        w.db.commit()
        with _http_as(w.owner_id) as client:
            http = _post_refresh(client, [disabled.id, enabled.id], start, end)
    assert http.status_code == 200
    body = http.json()
    assert body["overall_outcome"] == "partial"
    by_id = {row["subscription_id"]: row for row in body["results"]}
    assert by_id[str(disabled.id)]["phase"] == "preflight"
    assert by_id[str(disabled.id)]["preflight_code"] == "CALENDAR_SUBSCRIPTION_DISABLED"
    assert by_id[str(enabled.id)]["status"] == "ok"
    assert provider_spies["list"] == ["cal-v30-on"]


def test_v31_same_sub_covering_versus_legacy_cross_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """V31: legacy sync and covering on the same subscription, separate sessions, no deadlock.

    Legacy holds the owner advisory lock. Covering does not finish until that
    lock is released. The survivor has one coherent success generation.
    """
    start, end = _window()
    legacy_ident, holding, release = _pause_legacy_owner_lock(monkeypatch)
    errors: list[BaseException] = []
    covering_done = threading.Event()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v31", summary="Same")
        w.db.commit()

        def _legacy() -> None:
            legacy_ident.append(threading.get_ident())
            db = SessionLocal()
            try:
                live = db.get(CalendarAccount, account.id)
                assert live is not None
                gcal.sync_account_events(
                    db, settings=_settings(), account=live, time_min=start, time_max=end
                )
                db.commit()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
                db.rollback()
            finally:
                db.close()
                release.set()

        def _cover() -> None:
            try:
                _run(w.owner_id, [sub.id], start, end)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                covering_done.set()

        legacy_thread = threading.Thread(target=_legacy)
        cover_thread = threading.Thread(target=_cover)
        legacy_thread.start()
        assert holding.wait(30)
        cover_thread.start()
        time.sleep(1.5)
        assert not covering_done.is_set()
        release.set()
        legacy_thread.join(30)
        cover_thread.join(30)
        snap = _snap(sub.id)
    assert errors == []
    assert snap["coverage_success_at"] is not None
    assert snap["active_generation"] == snap["success_generation"]


def test_v32_same_sub_covering_versus_covering_cross_session() -> None:
    """V32: two covering refreshes, same sub, separate sessions. Both may succeed in order."""
    start, end = _window()
    errors: list[BaseException] = []
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def _one(owner_id: UUID, sub_id: UUID) -> None:
        try:
            barrier.wait(30)
            response = _run(owner_id, [sub_id], start, end)
            outcomes.append(response.results[0].status)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v32", summary="Twice", generation=0)
        w.db.commit()
        threads = [threading.Thread(target=_one, args=(w.owner_id, sub.id)) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        snap = _snap(sub.id)
    assert errors == []
    assert outcomes.count("ok") == 2
    assert snap["active_generation"] == snap["success_generation"] == 2


def test_v33_unknown_field_is_422(provider_spies: dict[str, Any]) -> None:
    """V33: ``mode=incremental`` is a strict-schema 422 and does not reach provider HTTP."""
    start, end = _window()
    with world() as w:
        with _http_as(w.owner_id) as client:
            http = _post_refresh(client, [uuid.uuid4()], start, end, mode="incremental")
    assert http.status_code == 422
    assert "mode" in http.text
    assert provider_spies["list"] == []
    assert provider_spies["ms"] == []
    assert provider_spies["retry"] == 0
    assert provider_spies["http"] == []


def test_v34_readiness_fault_does_not_claim_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    """V34: readiness assessment exploding after the import commit leaves the mint in place.

    The response carries the import row and an assessment_error. It does not raise
    and does not report the import as rolled back.
    """

    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("readiness assessment failed")

    monkeypatch.setattr(covering_refresh_mod, "_assemble_final_assessment", _boom)
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v34", summary="Committed")
        w.db.commit()
        response = _run(w.owner_id, [sub.id], start, end)
        snap = _snap(sub.id)
    assert response.overall_outcome == "success"
    assert _row(response, sub.id).status == "ok"
    assert response.action_summary.import_ok == 1
    assert response.scheduling_readiness is not None
    assert response.scheduling_readiness.assessment_error
    assert "readiness assessment failed" in response.scheduling_readiness.assessment_error
    assert response.scheduling_readiness.scheduling_ready is None
    assert snap["coverage_success_at"] is not None


def test_v35_failed_versus_no_op(provider_spies: dict[str, Any]) -> None:
    """V35: every attempted import failing is ``failed``; preflight-only is ``no_op``."""
    start, end = _window()
    with world() as failed_world:
        account = _account(failed_world.db, failed_world.user)
        first = _sub(failed_world.db, account, calendar_id="cal-v35a", summary="A")
        second = _sub(failed_world.db, account, calendar_id="cal-v35b", summary="B")
        failed_world.db.commit()
        provider_spies["fail"].update({"cal-v35a", "cal-v35b"})
        failed = _run(failed_world.owner_id, [first.id, second.id], start, end)
    assert failed.overall_outcome == "failed"
    assert failed.action_summary.import_attempted == 2
    assert failed.action_summary.import_ok == 0
    assert failed.action_summary.import_failed == 2
    provider_spies["fail"].clear()
    with world() as noop_world:
        account = _account(noop_world.db, noop_world.user)
        off = _sub(noop_world.db, account, calendar_id="cal-v35-off", summary="Off", enabled=False)
        noop_world.db.commit()
        noop = _run(noop_world.owner_id, [off.id], start, end)
    assert noop.overall_outcome == "no_op"
    assert noop.action_summary.import_attempted == 0
    assert noop.action_summary.preflight_rejected == 1


def test_v36_owner_lock_released_before_next_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    """V36: after A commits, the owner advisory lock is not held, and B blocks while a probe holds it.

    ``pg_try_advisory_xact_lock`` from a separate session succeeds in the pause
    after A. Keeping that transaction open stops B. B finishes only after the
    probe rolls back.
    """
    start, end = _window()
    a_id, b_id = _sorted_pair()
    after_a = threading.Event()
    release = threading.Event()
    b_done = threading.Event()
    errors: list[BaseException] = []
    real = covering_refresh_mod._process_one_target

    def _wrapped(db: Session, **kwargs: Any):
        result = real(db, **kwargs)
        if result.subscription_id == a_id:
            after_a.set()
            if not release.wait(30):
                raise TimeoutError("V36 probe did not release the orchestrator")
        if result.subscription_id == b_id:
            b_done.set()
        return result

    monkeypatch.setattr(covering_refresh_mod, "_process_one_target", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        _sub(w.db, account, calendar_id="cal-v36a", summary="A", sub_id=a_id)
        _sub(w.db, account, calendar_id="cal-v36b", summary="B", sub_id=b_id)
        w.db.commit()

        def _orchestrate() -> None:
            try:
                _run(w.owner_id, [a_id, b_id], start, end)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                release.set()

        worker = threading.Thread(target=_orchestrate)
        worker.start()
        assert after_a.wait(30)
        probe = SessionLocal()
        try:
            acquired = probe.execute(
                text("SELECT pg_try_advisory_xact_lock(:namespace, :key)"),
                {
                    "namespace": _OWNER_LOCK_NAMESPACE,
                    "key": owner_scheduling_lock_key(w.owner_id),
                },
            ).scalar()
            assert acquired is True
            release.set()
            time.sleep(1.5)
            assert not b_done.is_set()
        finally:
            probe.rollback()
            probe.close()
        worker.join(30)
    assert errors == []
    assert b_done.is_set()


def test_v37_narrow_window_outside_horizon_stays_requested() -> None:
    """V37: a narrow range outside the scheduling horizon is the effective pull, widen stays false."""
    start = NOW + timedelta(days=60)
    end = NOW + timedelta(days=70)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v37", summary="Far")
        w.db.commit()
        w.db.refresh(w.settings)
        horizon_start, horizon_end = required_coverage_window(w.settings, NOW)
        response = _run(w.owner_id, [sub.id], start, end)
    assert response.window_effective.start == start
    assert response.window_effective.end == end
    assert response.window_widened is False
    assert response.window_widen_reason == "none"
    readiness = response.scheduling_readiness
    assert readiness is not None and readiness.horizon is not None
    assert readiness.horizon.start == horizon_start
    assert readiness.horizon.end == horizon_end
    assert (horizon_start, horizon_end) != (start, end)


def test_v38a_cross_sub_late_failure_does_not_clobber_a(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V38a: separate sessions. A's later success survives B's delayed failure unit.

    B's provider read fails. ``persist_covering_refresh_failure`` is paused
    before it reacquires locks. Another session refreshes A to completion.
    B's failure unit then runs and must leave A's mint and generation alone.
    Owner revision may advance because B's own failure bump is required; it
    must not move backwards.
    """
    start, end = _window()
    a_id, b_id = _sorted_pair()
    ready = threading.Event()
    proceed = threading.Event()
    errors: list[BaseException] = []
    overlap_snap: dict[str, Any] = {}
    real_persist = failure_mod.persist_covering_refresh_failure

    def _slow_persist(**kwargs: Any):
        attempt = kwargs["attempt"]
        if attempt.subscription_id != b_id:
            return real_persist(**kwargs)
        ready.set()
        if not proceed.wait(60):
            raise TimeoutError("V38a overlap did not finish")
        return real_persist(**kwargs)

    monkeypatch.setattr(covering_refresh_mod, "persist_covering_refresh_failure", _slow_persist)
    with world() as w:
        account = _account(w.db, w.user)
        _sub(w.db, account, calendar_id="cal-v38a-a", summary="A", sub_id=a_id)
        _sub(w.db, account, calendar_id="cal-v38a-b", summary="B", sub_id=b_id)
        w.db.commit()
        provider_spies["fail"].add("cal-v38a-b")

        def _overlap() -> None:
            try:
                if not ready.wait(60):
                    raise TimeoutError("V38a failure unit never paused")
                overlap = _run(w.owner_id, [a_id], start, end)
                if overlap.results[0].status != "ok":
                    raise AssertionError(overlap.results[0].status)
                overlap_snap["a"] = _snap(a_id)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                proceed.set()

        worker = threading.Thread(target=_overlap)
        worker.start()
        try:
            response = _run(w.owner_id, [a_id, b_id], start, end)
        finally:
            proceed.set()
            worker.join(30)
        final_a = _snap(a_id)
        final_b = _snap(b_id)
    assert errors == []
    assert overlap_snap["a"]["coverage_success_at"] is not None
    assert final_a["coverage_success_at"] == overlap_snap["a"]["coverage_success_at"]
    assert final_a["active_generation"] == overlap_snap["a"]["active_generation"]
    assert final_a["success_generation"] == overlap_snap["a"]["success_generation"]
    assert final_a["revision"] >= overlap_snap["a"]["revision"]
    assert final_b["coverage_success_at"] is None
    assert final_b["sidecar"]
    assert _row(response, b_id).status == "failed"
    assert final_a["active_generation"] > 1


def test_v38b_same_sub_delayed_failure_refuses_newer_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """V38b: same subscription. Rolled-back generation is not the compare token.

    Import calls ``begin_subscription_refresh`` (in-memory 4→5) then apply
    raises and the unit rolls back. The attempt snapshot still says durable
    generation 4. A second session's covering refresh commits generation 5
    and a success mint while the failure unit is paused outside the locks.
    The failure unit then reacquires the §7 stack and refuses with
    ``superseded_generation`` — the pre-attempt token 4, not the rolled-back
    5. The newer success, identity, and generation stay.
    """
    start, end = _window()
    ready = threading.Event()
    proceed = threading.Event()
    errors: list[BaseException] = []
    captured: dict[str, Any] = {}
    seen_gens: list[int] = []
    real_begin = import_mod.begin_subscription_refresh
    real_apply = import_mod._apply_provider
    real_persist = failure_mod.persist_covering_refresh_failure
    apply_calls = {"n": 0}

    def _begin(subscription: CalendarSubscription, *, now: datetime) -> int:
        generation = real_begin(subscription, now=now)
        seen_gens.append(generation)
        return generation

    def _apply(*args: object, **kwargs: object) -> int:
        apply_calls["n"] += 1
        if apply_calls["n"] == 1:
            raise RuntimeError("first attempt apply rolls back")
        return real_apply(*args, **kwargs)

    def _slow_persist(**kwargs: Any):
        captured["attempt"] = kwargs["attempt"]
        ready.set()
        if not proceed.wait(60):
            raise TimeoutError("V38b newer success did not finish")
        captured["persist"] = real_persist(**kwargs)
        return captured["persist"]

    monkeypatch.setattr(import_mod, "begin_subscription_refresh", _begin)
    monkeypatch.setattr(import_mod, "_apply_provider", _apply)
    monkeypatch.setattr(covering_refresh_mod, "persist_covering_refresh_failure", _slow_persist)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v38b", summary="Same", generation=4)
        w.db.commit()
        sub_id = sub.id

        def _newer_success() -> None:
            db = SessionLocal()
            try:
                if not ready.wait(60):
                    raise TimeoutError("V38b failure unit never paused")
                attempt = captured["attempt"]
                row = db.get(CalendarSubscription, sub_id)
                assert row is not None
                durable_fp = covering_identity_fingerprint(row)
                captured["db_generation_before_success"] = int(row.coverage_active_generation or 0)
                captured["fingerprint_matches"] = (
                    durable_fp == attempt.durable_identity_fingerprint
                )
                captured["gens_before_success"] = list(seen_gens)
            finally:
                db.close()
            try:
                newer = _run(w.owner_id, [sub_id], start, end)
                if newer.results[0].status != "ok":
                    raise AssertionError(newer.results[0].status)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                proceed.set()

        worker = threading.Thread(target=_newer_success)
        worker.start()
        try:
            failed = _run(w.owner_id, [sub_id], start, end)
        finally:
            proceed.set()
            worker.join(30)
        final = _snap(sub_id)
    assert errors == []
    attempt = captured["attempt"]
    assert attempt.durable_coverage_active_generation == 4
    assert captured["db_generation_before_success"] == 4
    assert captured["gens_before_success"] == [5]
    assert captured["fingerprint_matches"] is True
    assert captured["persist"].refused is True
    assert captured["persist"].refuse_reason == "superseded_generation"
    assert _row(failed, sub_id).status == "failed"
    assert final["active_generation"] == 5
    assert final["success_generation"] == 5
    assert final["coverage_success_at"] is not None
    assert final["sidecar"] is None
    assert final["failure_cause"] is None


def test_v39_failure_sidecar_and_revision_commit_together(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V39: a separate session cannot see the failure sidecar without the revision bump.

    ``_commit_failure`` is wrapped so a reader session looks after the sidecar
    flush and before ``commit``. Both the sidecar and the bump are absent.
    After the failure unit returns, one fresh session sees the sidecar and a
    higher scheduling revision together.
    """
    start, end = _window()
    mid = threading.Event()
    mid_seen = threading.Event()
    receipt: dict[str, Any] = {}
    errors: list[BaseException] = []
    real_commit = failure_mod._commit_failure

    def _wrapped(db: Session, **kwargs: Any):
        original = db.commit

        def _pause_commit() -> None:
            mid.set()
            if not mid_seen.wait(30):
                raise TimeoutError("V39 reader did not observe the open failure transaction")
            original()

        db.commit = _pause_commit  # type: ignore[method-assign]
        try:
            return real_commit(db, **kwargs)
        finally:
            db.commit = original  # type: ignore[method-assign]

    monkeypatch.setattr(failure_mod, "_commit_failure", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v39", summary="Fail")
        w.db.commit()
        start_rev = _snap(sub.id)["revision"]
        provider_spies["fail"].add("cal-v39")

        def _reader() -> None:
            try:
                if not mid.wait(60):
                    raise TimeoutError("V39 failure unit never reached commit")
                db = SessionLocal()
                try:
                    fail = (
                        db.query(CalendarSubscriptionRefreshFailure)
                        .filter(CalendarSubscriptionRefreshFailure.subscription_id == sub.id)
                        .one_or_none()
                    )
                    rev = int(
                        db.query(UserSettings)
                        .filter(UserSettings.owner_id == w.owner_id)
                        .one()
                        .scheduling_revision
                    )
                    receipt["mid_sidecar"] = None if fail is None else fail.cause
                    receipt["mid_revision"] = rev
                finally:
                    db.close()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                mid_seen.set()

        worker = threading.Thread(target=_reader)
        worker.start()
        try:
            response = _run(w.owner_id, [sub.id], start, end)
        finally:
            mid_seen.set()
            worker.join(30)
        final = _snap(sub.id)
    assert errors == []
    assert receipt["mid_sidecar"] is None
    assert receipt["mid_revision"] == start_rev
    assert _row(response, sub.id).status == "failed"
    assert final["sidecar"]
    assert final["revision"] > start_rev
    assert final["coverage_success_at"] is None


def test_legacy_account_sync_route_still_imports(
    client: TestClient,
    db_session: Session,
    provider_spies: dict[str, Any],
) -> None:
    """Legacy POST /accounts/{id}/sync still pulls and still calls tombstone retry.

    Covering tests assert retry stays at zero. This route still enters it.
    """
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    owner = db_session.get(User, UUID(me.json()["id"]))
    assert owner is not None
    if db_session.query(UserSettings).filter(UserSettings.owner_id == owner.id).one_or_none() is None:
        db_session.add(
            UserSettings(
                owner_id=owner.id,
                timezone="UTC",
                workday_minutes=480,
                workday_start_local=time_of_day(8, 0),
                workweek_days=5,
                inter_block_buffer_minutes=15,
                upcoming_horizon_days=7,
                default_schedule_style=ScheduleStyle.standalone,
                scheduling_revision=0,
            )
        )
        db_session.flush()
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="cal-legacy-sync", summary="Legacy route")
    db_session.commit()
    event_start = NOW + timedelta(hours=1)
    provider_spies["events"]["cal-legacy-sync"] = [
        _g_event(f"legacy-route-{uuid.uuid4().hex}", event_start, event_start + timedelta(hours=1))
    ]
    start, end = _window()
    response = client.post(
        f"/api/v1/calendar/accounts/{account.id}/sync",
        params={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert response.status_code == 200, response.text
    assert response.json()["upserted"] == 1
    assert provider_spies["retry"] == 1
    assert provider_spies["list"] == ["cal-legacy-sync"]


def _seed_covering_fresh(
    sub: CalendarSubscription,
    start: datetime,
    end: datetime,
    *,
    at: datetime,
) -> None:
    """Enabled row that passes the freshness gate at ``at`` for ``[start, end]``."""
    sub.coverage_window_start = start
    sub.coverage_window_end = end
    sub.coverage_mode = "full"
    sub.coverage_success_at = at
    sub.coverage_fetched_at = at
    sub.coverage_pagination_complete = True
    sub.coverage_active_generation = 1
    sub.coverage_success_generation = 1
    sub.coverage_show_deleted = True
    sub.coverage_single_events = True
    sub.coverage_page_count = 1
    sub.coverage_item_count = 0


def _token_columns(account_id: UUID) -> tuple[Any, ...]:
    db = SessionLocal()
    try:
        row = db.get(CalendarAccount, account_id)
        if row is None:
            return ("<missing>",)
        return (row.access_token_enc, row.refresh_token_enc, row.token_expires_at)
    finally:
        db.close()


def _expire_token(account: CalendarAccount) -> None:
    account.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)


def _forbid_provider_token_refresh(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count get_valid_access_token. A call is a failure: expired tokens would HTTP."""
    hits = [0]

    def _no(*_a: object, **_k: object) -> str:
        hits[0] += 1
        raise AssertionError("provider token refresh ran")

    monkeypatch.setattr(gcal, "get_valid_access_token", _no)
    monkeypatch.setattr(ms_cal, "get_valid_access_token", _no)
    return hits


def _plant_stale_assessment_identity(
    db: Session,
    *,
    owner_id: UUID,
    sibling_id: UUID,
) -> CalendarSubscription:
    """Load owner rows so the request identity map holds unexpired pre-mutation state."""
    subs = db.query(CalendarSubscription).filter(CalendarSubscription.owner_id == owner_id).all()
    accounts = db.query(CalendarAccount).filter(CalendarAccount.owner_id == owner_id).all()
    sub_ids = [row.id for row in subs]
    failures = (
        db.query(CalendarSubscriptionRefreshFailure)
        .filter(CalendarSubscriptionRefreshFailure.subscription_id.in_(sub_ids))
        .all()
    )
    events = db.query(ExternalCalendarEvent).filter(ExternalCalendarEvent.owner_id == owner_id).all()
    policies = db.query(FreeBusySeriesPolicy).filter(FreeBusySeriesPolicy.owner_id == owner_id).all()
    loaded = [*subs, *accounts, *failures, *events, *policies]
    assert subs and accounts and failures and events and policies
    for row in loaded:
        assert sa_inspect(row).expired is False
        assert row.id is not None
    sibling = next(row for row in subs if row.id == sibling_id)
    assert sibling.coverage_success_at is not None
    assert not (db.new or db.dirty or db.deleted)
    return sibling


def _blocking_by_name(freshness: dict[str, Any] | None) -> dict[str, str]:
    rows = (freshness or {}).get("blocking_diagnostics") or []
    named: dict[str, str] = {}
    for item in rows:
        if isinstance(item, dict):
            named[str(item.get("calendar_name"))] = str(item.get("cause"))
    return named


def test_v40_coherent_snapshot_ignores_stale_identity_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """V40: assessment after the owner lock sees the mutator's sibling clear, not the planted map.

    Three SessionLocals. The request pauses inside ``_assemble_final_assessment``
    before ``lock_owner_scheduling`` and touches subscription, account, failure,
    event, and series-policy rows so they are unexpired. A second session then
    locks, clears only the non-requested sibling's ``coverage_success_at``, bumps
    revision, and commits while the request is still paused. A third session
    re-reads freshness and revision. The response must match that read.
    """
    paused = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []
    receipt: dict[str, Any] = {}
    real = covering_refresh_mod._assemble_final_assessment
    sibling_box: dict[str, UUID] = {}

    def _wrapped(db: Session, **kwargs: Any):
        try:
            sibling = _plant_stale_assessment_identity(
                db,
                owner_id=kwargs["owner_id"],
                sibling_id=sibling_box["id"],
            )
            receipt["planted_unexpired"] = sa_inspect(sibling).expired is False
            receipt["planted_success"] = sibling.coverage_success_at is not None
            paused.set()
        except BaseException:
            release.set()
            raise
        if not release.wait(60):
            raise TimeoutError(
                "V40 mutator did not commit while assessment was paused before the owner lock"
            )
        assert sa_inspect(sibling).expired is False
        assert sibling.coverage_success_at is not None
        receipt["stale_after_mutator_commit"] = True
        return real(db, **kwargs)

    monkeypatch.setattr(covering_refresh_mod, "_assemble_final_assessment", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        w.db.commit()
        w.db.refresh(w.settings)
        start, end = required_coverage_window(w.settings, NOW)
        requested = _sub(w.db, account, calendar_id="cal-v40-req", summary="Requested mint")
        sibling = _sub(w.db, account, calendar_id="cal-v40-sib", summary="Sibling fresh")
        _seed_covering_fresh(sibling, start, end, at=NOW - timedelta(minutes=1))
        decoy = _sub(w.db, account, calendar_id="cal-v40-off", summary="Decoy", enabled=False)
        w.db.add(
            CalendarSubscriptionRefreshFailure(
                subscription_id=decoy.id,
                failure_at=NOW - timedelta(days=3),
                cause="calendar_refresh_failed",
            )
        )
        w.db.add(
            ExternalCalendarEvent(
                owner_id=w.owner_id,
                calendar_account_id=account.id,
                provider=account.provider,
                external_event_id=f"v40-{uuid.uuid4().hex}",
                calendar_id="cal-v40-sib",
                title="tombstone",
                start_time=NOW + timedelta(hours=1),
                end_time=NOW + timedelta(hours=2),
                is_all_day=False,
                pending_deletion=True,
                last_synced_at=NOW,
                transparency="opaque",
                free_busy_provenance="google_transparency",
                source_timezone="UTC",
                source_zone_missing=False,
                series_identity_state="verified_non_recurring",
                is_provider_cancelled=False,
            )
        )
        w.db.add(
            FreeBusySeriesPolicy(
                owner_id=w.owner_id,
                provider=account.provider,
                calendar_id="cal-v40-sib",
                provider_series_id=f"series-{uuid.uuid4().hex[:8]}",
                mapping="free",
            )
        )
        w.db.commit()
        sibling_box["id"] = sibling.id
        owner_id = w.owner_id
        sib_id = sibling.id
        start_rev = _snap(requested.id)["revision"]

        def _mutate() -> None:
            db = SessionLocal()
            try:
                if not paused.wait(60):
                    raise TimeoutError("V40 request never paused before the assessment lock")
                db.execute(text("SET lock_timeout = '8s'"))
                settings = lock_owner_scheduling(db, owner_id)
                row = db.get(CalendarSubscription, sib_id)
                assert row is not None and row.coverage_success_at is not None
                row.coverage_success_at = None
                assert not release.is_set()
                revision = increment_scheduling_revision(db, settings)
                db.commit()
                assert not release.is_set()
                receipt["mutator_revision"] = revision
                receipt["committed_while_paused"] = True
            except BaseException as exc:  # noqa: BLE001 — barrier thread
                errors.append(exc)
            finally:
                db.close()
                release.set()

        worker = threading.Thread(target=_mutate)
        worker.start()
        try:
            response = _run(w.owner_id, [requested.id], start, end)
        finally:
            release.set()
            worker.join(30)
        third = SessionLocal()
        try:
            settings = third.query(UserSettings).filter(UserSettings.owner_id == w.owner_id).one()
            third_revision = int(settings.scheduling_revision)
            third_requested = covering_refresh_mod._evaluate_requested_freshness(
                third,
                owner_id=w.owner_id,
                subscription_ids=[requested.id],
                now_utc=NOW,
                required_start=start,
                required_end=end,
            )
            third_fresh = evaluate_calendar_freshness(
                third,
                w.owner_id,
                settings,
                NOW,
                required_start=start,
                required_end=end,
            )
            immovable = (
                third.query(ExternalCalendarEvent)
                .filter(
                    ExternalCalendarEvent.owner_id == w.owner_id,
                    *ExternalCalendarEvent.immovable_busy_clause(),
                )
                .count()
            )
        finally:
            third.close()
        snap_requested = _snap(requested.id)
        snap_sibling = _snap(sibling.id)
    assert errors == []
    assert receipt["planted_unexpired"] is True
    assert receipt["planted_success"] is True
    assert receipt["committed_while_paused"] is True
    assert receipt["stale_after_mutator_commit"] is True
    assert receipt["mutator_revision"] == third_revision
    assert third_revision > start_rev
    readiness = response.scheduling_readiness
    assert readiness is not None
    assert response.scheduling_revision_at_end == third_revision
    assert readiness.scheduling_revision == third_revision
    assert response.coverage_action.all_requested_covering_ok is True
    assert response.coverage_action.all_requested_covering_ok == third_requested.ok
    fresh = readiness.freshness_all_enabled or {}
    assert fresh.get("ok") is False
    assert fresh.get("ok") == third_fresh.ok
    third_causes = {diag.calendar_name: diag.cause for diag in third_fresh.blocking_diagnostics}
    assert _blocking_by_name(fresh) == third_causes
    assert third_causes.get("Sibling fresh") == "calendar_coverage_missing"
    assert "Requested mint" not in third_causes
    third_ready = bool(third_fresh.ok) and immovable == 0
    assert readiness.scheduling_ready is False
    assert readiness.scheduling_ready == third_ready
    assert snap_sibling["coverage_success_at"] is None
    assert snap_requested["coverage_success_at"] is not None


def test_v41_disabled_expired_token_skips_oauth(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V41: a disabled subscription with an expired token never reaches OAuth refresh."""
    hits = _forbid_provider_token_refresh(monkeypatch)
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        _expire_token(account)
        sub = _sub(w.db, account, calendar_id="cal-v41", summary="Off", enabled=False)
        w.db.commit()
        before = _token_columns(account.id)
        response = _run(w.owner_id, [sub.id], start, end)
        after = _token_columns(account.id)
        with pytest.raises(import_mod.CoveringTargetIneligible) as caught:
            import_mod.read_covering_access_token(
                settings=_settings(),
                owner_id=w.owner_id,
                account_id=account.id,
                subscription_id=sub.id,
            )
        after_direct = _token_columns(account.id)
    row = _row(response, sub.id)
    assert response.overall_outcome == "no_op"
    assert row.phase == "preflight"
    assert row.preflight_code == import_mod.PREFLIGHT_SUBSCRIPTION_DISABLED
    assert caught.value.preflight_code == import_mod.PREFLIGHT_SUBSCRIPTION_DISABLED
    assert hits[0] == 0
    assert provider_spies["http"] == []
    assert provider_spies["list"] == []
    assert before == after == after_direct


def test_v41b_account_disabled_expired_token_skips_oauth(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V41b: a disabled account with an expired token is the account-disabled preflight, not OAuth."""
    hits = _forbid_provider_token_refresh(monkeypatch)
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        _expire_token(account)
        account.is_enabled = False
        sub = _sub(w.db, account, calendar_id="cal-v41b", summary="Account off")
        w.db.commit()
        before = _token_columns(account.id)
        response = _run(w.owner_id, [sub.id], start, end)
        after = _token_columns(account.id)
        with pytest.raises(import_mod.CoveringTargetIneligible) as caught:
            import_mod.read_covering_access_token(
                settings=_settings(),
                owner_id=w.owner_id,
                account_id=account.id,
                subscription_id=sub.id,
            )
        after_direct = _token_columns(account.id)
    row = _row(response, sub.id)
    assert row.phase == "preflight"
    assert row.preflight_code == import_mod.PREFLIGHT_ACCOUNT_DISABLED
    assert caught.value.preflight_code == import_mod.PREFLIGHT_ACCOUNT_DISABLED
    assert hits[0] == 0
    assert provider_spies["http"] == []
    assert provider_spies["list"] == []
    assert before == after == after_direct


def test_v42_identity_blocked_expired_token_skips_oauth(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V42: identity-blocked plus an expired token stays preflight. No token HTTP and no column writes."""
    hits = _forbid_provider_token_refresh(monkeypatch)
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        _expire_token(account)
        sub = _sub(w.db, account, calendar_id="cal-v42", summary="Blocked")
        sub.coverage_last_failure_cause = IDENTITY_UNRESOLVED_CAUSE
        w.db.commit()
        before = _token_columns(account.id)
        response = _run(w.owner_id, [sub.id], start, end)
        after = _token_columns(account.id)
        with pytest.raises(import_mod.CoveringTargetIneligible) as caught:
            import_mod.read_covering_access_token(
                settings=_settings(),
                owner_id=w.owner_id,
                account_id=account.id,
                subscription_id=sub.id,
            )
        after_direct = _token_columns(account.id)
    row = _row(response, sub.id)
    assert response.overall_outcome == "no_op"
    assert row.phase == "preflight"
    assert row.preflight_code == import_mod.PREFLIGHT_IDENTITY_BLOCKED
    assert caught.value.preflight_code == import_mod.PREFLIGHT_IDENTITY_BLOCKED
    assert hits[0] == 0
    assert provider_spies["http"] == []
    assert provider_spies["list"] == []
    assert provider_spies["identity_lists"] == []
    assert before == after == after_direct


def _drop_between_preflight_and_token(
    monkeypatch: pytest.MonkeyPatch,
    *,
    drop: Any,
) -> None:
    """After the orchestrator eligibility check passes, mutate durable rows before the token unit."""
    real = covering_refresh_mod.covering_import_eligibility_code
    armed = {"done": False}

    def _wrapped(account: CalendarAccount, subscription: CalendarSubscription, **kwargs: Any) -> str | None:
        code = real(account, subscription, **kwargs)
        if kwargs.get("check_missing_credentials") and code is None and not armed["done"]:
            armed["done"] = True
            drop()
        return code

    monkeypatch.setattr(covering_refresh_mod, "covering_import_eligibility_code", _wrapped)


def test_v43_account_gone_between_preflight_and_token(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V43: account deleted after in-memory eligibility is preflight disconnected, not a 500.

    The token unit re-reads under the §7 locks. A missing account becomes
    ``CALENDAR_ACCOUNT_DISCONNECTED`` and does not call provider token HTTP.
    """
    hits = _forbid_provider_token_refresh(monkeypatch)
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        _expire_token(account)
        sub = _sub(w.db, account, calendar_id="cal-v43", summary="Vanish account")
        w.db.commit()
        account_id = account.id

        def _drop() -> None:
            db = SessionLocal()
            try:
                row = db.get(CalendarAccount, account_id)
                assert row is not None
                db.delete(row)
                db.commit()
            finally:
                db.close()

        _drop_between_preflight_and_token(monkeypatch, drop=_drop)
        response = _run(w.owner_id, [sub.id], start, end)
        remaining = _token_columns(account_id)
    row = _row(response, sub.id)
    assert response.overall_outcome == "no_op"
    assert row.phase == "preflight"
    assert row.preflight_code == import_mod.PREFLIGHT_ACCOUNT_DISCONNECTED
    assert hits[0] == 0
    assert provider_spies["http"] == []
    assert provider_spies["list"] == []
    assert remaining == ("<missing>",)


def test_v44_subscription_gone_between_preflight_and_token(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V44: subscription deleted after in-memory eligibility is preflight not-found, not a 500."""
    hits = _forbid_provider_token_refresh(monkeypatch)
    start, end = _window()
    with world() as w:
        account = _account(w.db, w.user)
        _expire_token(account)
        sub = _sub(w.db, account, calendar_id="cal-v44", summary="Vanish sub")
        w.db.commit()
        before = _token_columns(account.id)
        sub_id = sub.id

        def _drop() -> None:
            db = SessionLocal()
            try:
                row = db.get(CalendarSubscription, sub_id)
                assert row is not None
                db.delete(row)
                db.commit()
            finally:
                db.close()

        _drop_between_preflight_and_token(monkeypatch, drop=_drop)
        response = _run(w.owner_id, [sub.id], start, end)
        after = _token_columns(account.id)
    row = _row(response, sub.id)
    assert response.overall_outcome == "no_op"
    assert row.phase == "preflight"
    assert row.preflight_code == import_mod.PREFLIGHT_SUBSCRIPTION_NOT_FOUND
    assert hits[0] == 0
    assert provider_spies["http"] == []
    assert provider_spies["list"] == []
    assert before == after


def _advance_clock_at_assessment(monkeypatch: pytest.MonkeyPatch, clock: dict[str, datetime], late: datetime) -> None:
    real = covering_refresh_mod._assemble_final_assessment

    def _wrapped(db: Session, **kwargs: Any):
        clock["now"] = late
        return real(db, **kwargs)

    monkeypatch.setattr(covering_refresh_mod, "_assemble_final_assessment", _wrapped)


def test_v45_assessment_clock_past_freshness_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """V45: mint on the early clock; assessment past the freshness ceiling uses the later sample.

    No sleep. ``clock`` advances only once the request enters final assessment.
    ``coverage_success_at`` stays the import stamp. ``evaluated_at``, horizon, and
    freshness age use the advanced sample, so the mint is ``calendar_coverage_stale``.
    """
    early = NOW
    late = early + FRESHNESS_AGE_CEILING + timedelta(minutes=1)
    clock = {"now": early}
    _advance_clock_at_assessment(monkeypatch, clock, late)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v45", summary="Ceiling")
        w.db.commit()
        w.db.refresh(w.settings)
        start, end = required_coverage_window(w.settings, early)
        early_horizon = required_coverage_window(w.settings, early)
        late_horizon = required_coverage_window(w.settings, late)
        response = _run(w.owner_id, [sub.id], start, end, clock=lambda: clock["now"])
        snap = _snap(sub.id)
    assert late_horizon[1] != early_horizon[1]
    assert snap["coverage_success_at"] == early
    readiness = response.scheduling_readiness
    assert readiness is not None and readiness.horizon is not None
    assert readiness.evaluated_at == late
    assert readiness.evaluated_at != early
    assert readiness.horizon.end == late_horizon[1]
    assert readiness.horizon.end != early_horizon[1]
    fresh = readiness.freshness_all_enabled or {}
    assert fresh.get("ok") is False
    assert "calendar_coverage_stale" in {item.get("cause") for item in fresh.get("blocking_diagnostics") or []}
    assert fresh.get("required_window_end") == late_horizon[1].isoformat()
    assert readiness.scheduling_ready is False
    assert response.coverage_action.all_requested_covering_ok is False


def test_v46_assessment_clock_moves_horizon_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """V46: a later assessment sample moves ``required_coverage_window``, not the import-start stamp.

    Intra-request only. The import still mints at the early clock. ``evaluated_at``
    and the readiness horizon end are the advanced sample.
    """
    early = NOW
    late = early + timedelta(days=3)
    clock = {"now": early}
    _advance_clock_at_assessment(monkeypatch, clock, late)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v46", summary="Horizon slide")
        w.db.commit()
        w.db.refresh(w.settings)
        start, end = required_coverage_window(w.settings, early)
        early_horizon = (start, end)
        late_horizon = required_coverage_window(w.settings, late)
        response = _run(w.owner_id, [sub.id], start, end, clock=lambda: clock["now"])
        snap = _snap(sub.id)
    assert late_horizon != early_horizon
    assert snap["coverage_success_at"] == early
    readiness = response.scheduling_readiness
    assert readiness is not None and readiness.horizon is not None
    assert readiness.evaluated_at == late
    assert readiness.evaluated_at != early
    assert readiness.horizon.start == late_horizon[0]
    assert readiness.horizon.end == late_horizon[1]
    assert readiness.horizon.end != early_horizon[1]
    fresh = readiness.freshness_all_enabled or {}
    assert fresh.get("required_window_start") == late_horizon[0].isoformat()
    assert fresh.get("required_window_end") == late_horizon[1].isoformat()
    assert fresh.get("required_window_end") != early_horizon[1].isoformat()


def test_v47_account_gone_between_token_and_import(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V47: account deleted after the token unit returns and before the import unit reacquires locks.

    The import boundary maps ``CoveringAccountMissing`` to preflight disconnected, not a 500.
    Cascade removes the subscription, so requested freshness must fail closed on membership
    instead of treating the vanished id as covering-ok. Provider event read never starts.
    """
    start, end = _window()
    real = covering_refresh_mod.read_covering_access_token

    def _wrapped(**kwargs: Any):
        token = real(**kwargs)
        db = SessionLocal()
        try:
            row = db.get(CalendarAccount, kwargs["account_id"])
            assert row is not None
            db.delete(row)
            db.commit()
        finally:
            db.close()
        return token

    monkeypatch.setattr(covering_refresh_mod, "read_covering_access_token", _wrapped)
    with world() as w:
        account = _account(w.db, w.user)
        sub = _sub(w.db, account, calendar_id="cal-v47", summary="Vanish import")
        w.db.commit()
        account_id = account.id
        sub_id = sub.id
        response = _run(w.owner_id, [sub_id], start, end)
        probe = SessionLocal()
        try:
            assert probe.get(CalendarAccount, account_id) is None
            assert probe.get(CalendarSubscription, sub_id) is None
        finally:
            probe.close()
    row = _row(response, sub_id)
    assert response.overall_outcome == "no_op"
    assert row.phase == "preflight"
    assert row.status == "preflight_rejected"
    assert row.preflight_code == import_mod.PREFLIGHT_ACCOUNT_DISCONNECTED
    assert response.action_summary.preflight_rejected == 1
    assert response.action_summary.import_attempted == 0
    assert response.action_summary.import_ok == 0
    assert provider_spies["list"] == []
    assert provider_spies["identity_lists"] == []
    assert provider_spies["http"] == []
    assert response.scheduling_readiness is not None
    assert response.scheduling_readiness.assessment_error is None
    assert response.coverage_action.all_requested_covering_ok is False
    requested = response.coverage_action.freshness_requested
    assert requested["ok"] is False
    blocking = requested["blocking_diagnostics"]
    assert len(blocking) == 1
    assert blocking[0]["event_id"] == str(sub_id)
    assert blocking[0]["cause"] == "calendar_requested_subscription_missing"
    assert blocking[0]["calendar_name"] == "(missing)"
    assert blocking[0]["blocking_current_proposal"] is True
    assert blocking[0]["recovery"] == (
        "A requested calendar subscription is no longer present; "
        "re-select calendars or reconnect the account."
    )


def test_v48_partial_success_when_peer_account_deleted_after_token(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V48: sub A commits ok; B's account vanishes between token return and import lock → partial.

    A's busy row and coverage mint stay. B never reaches provider event read, and the
    missing requested id keeps ``all_requested_covering_ok`` false.
    """
    start, end = _window()
    a_id, b_id = _sorted_pair()
    real = covering_refresh_mod.read_covering_access_token

    def _wrapped(**kwargs: Any):
        token = real(**kwargs)
        if kwargs["subscription_id"] != b_id:
            return token
        db = SessionLocal()
        try:
            row = db.get(CalendarAccount, kwargs["account_id"])
            assert row is not None
            db.delete(row)
            db.commit()
        finally:
            db.close()
        return token

    monkeypatch.setattr(covering_refresh_mod, "read_covering_access_token", _wrapped)
    with world() as w:
        account_a = _account(w.db, w.user)
        account_b = _account(w.db, w.user)
        _sub(w.db, account_a, calendar_id="cal-v48a", summary="A", sub_id=a_id)
        _sub(w.db, account_b, calendar_id="cal-v48b", summary="B", sub_id=b_id)
        w.db.commit()
        account_a_id = account_a.id
        account_b_id = account_b.id
        provider_spies["events"]["cal-v48a"] = [
            _g_event(f"evt-{uuid.uuid4().hex}", NOW + timedelta(hours=1), NOW + timedelta(hours=2))
        ]
        provider_spies["events"]["cal-v48b"] = [
            _g_event(f"evt-{uuid.uuid4().hex}", NOW + timedelta(hours=3), NOW + timedelta(hours=4))
        ]
        response = _run(w.owner_id, [a_id, b_id], start, end)
        snap_a = _snap(a_id)
        events = _events(w.owner_id)
        probe = SessionLocal()
        try:
            assert probe.get(CalendarAccount, account_b_id) is None
            assert probe.get(CalendarSubscription, b_id) is None
            assert probe.get(CalendarAccount, account_a_id) is not None
        finally:
            probe.close()
    assert response.overall_outcome == "partial"
    assert response.action_summary.import_ok == 1
    assert response.action_summary.preflight_rejected == 1
    assert response.action_summary.import_attempted == 1
    assert _row(response, a_id).status == "ok"
    assert _row(response, b_id).phase == "preflight"
    assert _row(response, b_id).status == "preflight_rejected"
    assert _row(response, b_id).preflight_code == import_mod.PREFLIGHT_ACCOUNT_DISCONNECTED
    assert snap_a["coverage_success_at"] is not None
    assert snap_a["success_generation"] is not None
    assert [row["calendar_id"] for row in events] == ["cal-v48a"]
    assert provider_spies["list"] == ["cal-v48a"]
    assert "cal-v48b" not in provider_spies["list"]
    assert response.scheduling_readiness is not None
    assert response.scheduling_readiness.assessment_error is None
    assert response.scheduling_revision_at_end == snap_a["revision"]
    assert response.coverage_action.all_requested_covering_ok is False
    requested = response.coverage_action.freshness_requested
    assert requested["ok"] is False
    causes = {item["event_id"]: item["cause"] for item in requested["blocking_diagnostics"]}
    assert causes[str(b_id)] == "calendar_requested_subscription_missing"
    assert str(a_id) not in causes
    assert len(requested["blocking_diagnostics"]) == 1


def test_v49_evaluate_requested_freshness_missing_membership() -> None:
    """V49: requested subscription ids absent from DB fail closed even when siblings look fresh."""
    start, end = _window()
    phantom_id = uuid.uuid4()
    with world() as w:
        account = _account(w.db, w.user)
        fresh = _sub(w.db, account, calendar_id="cal-v49-fresh", summary="Fresh")
        doomed = _sub(w.db, account, calendar_id="cal-v49-doom", summary="Doom")
        w.db.commit()
        minted = _run(w.owner_id, [fresh.id, doomed.id], start, end)
        assert minted.overall_outcome == "success"
        db = SessionLocal()
        try:
            never_loaded = covering_refresh_mod._evaluate_requested_freshness(
                db,
                owner_id=w.owner_id,
                subscription_ids=[fresh.id, phantom_id],
                now_utc=NOW,
                required_start=start,
                required_end=end,
            )
            row = db.get(CalendarSubscription, doomed.id)
            assert row is not None
            db.delete(row)
            db.commit()
            after_delete = covering_refresh_mod._evaluate_requested_freshness(
                db,
                owner_id=w.owner_id,
                subscription_ids=[fresh.id, doomed.id],
                now_utc=NOW,
                required_start=start,
                required_end=end,
            )
        finally:
            db.close()
    recovery = (
        "A requested calendar subscription is no longer present; "
        "re-select calendars or reconnect the account."
    )
    assert never_loaded.ok is False
    assert len(never_loaded.blocking_diagnostics) == 1
    phantom = never_loaded.blocking_diagnostics[0]
    assert phantom.event_id == str(phantom_id)
    assert phantom.cause == "calendar_requested_subscription_missing"
    assert phantom.calendar_name == "(missing)"
    assert phantom.blocking_current_proposal is True
    assert phantom.recovery == recovery
    assert never_loaded.affected_horizon == {
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    assert after_delete.ok is False
    assert len(after_delete.blocking_diagnostics) == 1
    deleted = after_delete.blocking_diagnostics[0]
    assert deleted.event_id == str(doomed.id)
    assert deleted.cause == "calendar_requested_subscription_missing"
    assert deleted.recovery == recovery
    assert deleted.blocking_current_proposal is True


def test_v50_import_programming_fault_propagates(
    provider_spies: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V50: a programming fault inside the import lock is not an eligibility success.

    Sub A commits first. Sub B's import raises ``RuntimeError`` after the token unit.
    The new disconnect/lock handlers must not swallow that into a preflight row.
    A's coverage and busy row remain; B gets neither a mint nor a failure sidecar.
    """
    start, end = _window()
    a_id, b_id = _sorted_pair()
    real = covering_refresh_mod.import_covering_subscription_cache

    def _boom(db: Session, **kwargs: Any):
        subscription = kwargs["subscription"]
        if subscription.id == b_id:
            raise RuntimeError("covering import programming fault")
        return real(db, **kwargs)

    monkeypatch.setattr(covering_refresh_mod, "import_covering_subscription_cache", _boom)
    with world() as w:
        account_a = _account(w.db, w.user)
        account_b = _account(w.db, w.user)
        _sub(w.db, account_a, calendar_id="cal-v50a", summary="A", sub_id=a_id)
        _sub(w.db, account_b, calendar_id="cal-v50b", summary="B", sub_id=b_id)
        w.db.commit()
        provider_spies["events"]["cal-v50a"] = [
            _g_event(f"evt-{uuid.uuid4().hex}", NOW + timedelta(hours=1), NOW + timedelta(hours=2))
        ]
        provider_spies["events"]["cal-v50b"] = [
            _g_event(f"evt-{uuid.uuid4().hex}", NOW + timedelta(hours=3), NOW + timedelta(hours=4))
        ]
        with pytest.raises(RuntimeError, match="covering import programming fault"):
            _run(w.owner_id, [a_id, b_id], start, end)
        snap_a = _snap(a_id)
        snap_b = _snap(b_id)
        events = _events(w.owner_id)
    assert snap_a["coverage_success_at"] is not None
    assert snap_a["success_generation"] is not None
    assert snap_b["coverage_success_at"] is None
    assert snap_b["sidecar"] is None
    assert snap_b["failure_cause"] is None
    assert [row["calendar_id"] for row in events] == ["cal-v50a"]
    assert provider_spies["list"] == ["cal-v50a"]
    assert "cal-v50b" not in provider_spies["list"]
