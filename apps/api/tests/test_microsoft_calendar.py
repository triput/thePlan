"""Microsoft Calendar Graph tests — mock httpx, no live Entra."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CalendarAccount, CalendarSubscription, ExternalCalendarEvent, ScheduledBlock, Task
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.schemas import CalendarAccountUpdate
from app.services import microsoft_calendar as ms_cal
from app.services.token_crypto import encrypt_token

UTC = timezone.utc
_FERNET_KEY = Fernet.generate_key().decode("utf-8")
_GRAPH = "https://graph.microsoft.com/v1.0"


def _current_user_id(client: TestClient) -> uuid.UUID:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    return uuid.UUID(me.json()["id"])


def _ms_settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET_KEY,
        microsoft_client_id="test-ms-client",
        microsoft_client_secret="test-ms-secret",
        microsoft_redirect_uri="http://localhost/api/v1/calendar/oauth/microsoft/callback",
        microsoft_tenant_id="common",
        google_client_id="test-g-client",
        google_client_secret="test-g-secret",
        google_redirect_uri="http://localhost/api/v1/calendar/oauth/google/callback",
    )


def _patch_ms_httpx(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def _factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(ms_cal.httpx, "Client", _factory)


def _graph_event(event_id: str, subject: str, start: str, end: str) -> dict:
    return {
        "id": event_id,
        "subject": subject,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }


class FakeGraph:
    """Scripted Graph/token responses keyed off method + path."""

    def __init__(self, calendar_id: str) -> None:
        self.calendar_id = calendar_id
        self.calls: list[tuple[str, str]] = []
        self.delta_status = 200
        self.incremental_status = 200
        self.delta_events: list[dict] = []
        self.view_events: list[dict] = []
        self.incremental_events: list[dict] = []
        self.delta_link = (
            f"{_GRAPH}/me/calendars/{quote(calendar_id, safe='')}/calendarView/delta?$deltatoken=cursor-2"
        )
        self.created_event_id = f"created-{uuid.uuid4()}"
        self.calendars: list[dict] = [
            {
                "id": calendar_id,
                "name": "Calendar",
                "isDefaultCalendar": True,
                "canEdit": True,
                "canShare": True,
                "canViewPrivateItems": True,
            }
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        path = request.url.path
        self.calls.append((request.method, url))

        if request.method == "POST" and "/oauth2/v2.0/token" in url:
            return httpx.Response(
                200,
                json={
                    "access_token": "ms-access",
                    "refresh_token": "ms-refresh",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        if request.method == "POST" and path.endswith("/events"):
            return httpx.Response(
                201,
                json={"id": self.created_event_id, "subject": "Scheduled block"},
            )
        if "calendarView/delta" in path:
            is_incremental = "deltatoken" in url.lower()
            status = self.incremental_status if is_incremental else self.delta_status
            if status != 200:
                return httpx.Response(
                    status,
                    json={"error": {"code": "SyncStateNotFound", "message": "delta expired"}},
                )
            events = self.incremental_events if is_incremental else self.delta_events
            return httpx.Response(
                200,
                json={"value": events, "@odata.deltaLink": self.delta_link},
            )
        if "calendarView" in path:
            return httpx.Response(200, json={"value": self.view_events})
        if path.rstrip("/").endswith("/me/calendar"):
            return httpx.Response(
                200,
                json={"id": self.calendar_id, "name": "Calendar", "isDefaultCalendar": True},
            )
        if path.rstrip("/").endswith("/me/calendars"):
            return httpx.Response(200, json={"value": self.calendars})
        if path.rstrip("/").endswith("/v1.0/me"):
            return httpx.Response(
                200,
                json={"mail": "pytest-ms@contoso.test", "userPrincipalName": "pytest-ms@contoso.test"},
            )
        return httpx.Response(500, json={"error": {"code": "Unexpected", "message": url}})


def _seed_microsoft_account(
    db: Session,
    *,
    owner_id: uuid.UUID,
    settings: Settings,
    calendar_id: str,
    email: str | None = None,
    mirror_blocks: bool = False,
    sync_cursor: str | None = None,
) -> CalendarAccount:
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.microsoft,
        account_email=email or f"pytest-ms-{uuid.uuid4().hex[:8]}@contoso.test",
        access_token_enc=encrypt_token(settings, "ms-access"),
        refresh_token_enc=encrypt_token(settings, "ms-refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=mirror_blocks,
    )
    db.add(account)
    db.flush()
    db.add(
        CalendarSubscription(
            owner_id=owner_id,
            calendar_account_id=account.id,
            external_calendar_id=calendar_id,
            summary="Calendar",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
            sync_cursor=sync_cursor,
        )
    )
    db.flush()
    return account


def _seed_google_account(
    db: Session,
    *,
    owner_id: uuid.UUID,
    settings: Settings,
) -> CalendarAccount:
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.google,
        account_email=f"pytest-g-{uuid.uuid4().hex[:8]}@gmail.test",
        access_token_enc=encrypt_token(settings, "g-access"),
        refresh_token_enc=encrypt_token(settings, "g-refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
    )
    db.add(account)
    db.flush()
    return account


def test_calendar_account_update_accepts_legacy_mirror_alias() -> None:
    legacy = CalendarAccountUpdate.model_validate({"mirror_blocks_to_google": True})
    assert legacy.mirror_blocks is True
    current = CalendarAccountUpdate.model_validate({"mirror_blocks": False})
    assert current.mirror_blocks is False


def test_oauth_upsert_creates_microsoft_account_with_guid_primary(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar_id = str(uuid.uuid4())
    uuid.UUID(calendar_id)
    settings = _ms_settings()
    graph = FakeGraph(calendar_id)
    _patch_ms_httpx(monkeypatch, graph)
    owner_id = _current_user_id(client)
    config = ms_cal.load_microsoft_oauth_config(settings)

    tokens = ms_cal.exchange_code_for_tokens(config, "auth-code")
    account = ms_cal.upsert_account_tokens(
        db_session,
        settings=settings,
        owner_id=owner_id,
        account_email=f"pytest-ms-{uuid.uuid4().hex[:8]}@contoso.test",
        token_payload=tokens,
    )
    db_session.flush()

    assert account.provider == CalendarProvider.microsoft
    assert account.account_email is not None
    assert account.account_email.endswith("@contoso.test")
    assert account.is_enabled is True
    sub = (
        db_session.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .one()
    )
    assert sub.external_calendar_id == calendar_id
    assert sub.external_calendar_id != "primary"
    uuid.UUID(sub.external_calendar_id)
    assert sub.role == CalendarSubscriptionRole.primary
    assert any("/oauth2/v2.0/token" in url for _, url in graph.calls)
    assert any(path_url.endswith("/me/calendar") or "/me/calendar?" in path_url for _, path_url in graph.calls)


def test_ensure_primary_rewrites_legacy_primary_id(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar_id = str(uuid.uuid4())
    settings = _ms_settings()
    graph = FakeGraph(calendar_id)
    _patch_ms_httpx(monkeypatch, graph)
    owner_id = _current_user_id(client)
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.microsoft,
        account_email=f"legacy-{uuid.uuid4().hex[:8]}@contoso.test",
        access_token_enc=encrypt_token(settings, "ms-access"),
        refresh_token_enc=encrypt_token(settings, "ms-refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
    )
    db_session.add(account)
    db_session.flush()
    legacy = CalendarSubscription(
        owner_id=owner_id,
        calendar_account_id=account.id,
        external_calendar_id="primary",
        summary="Primary",
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
    )
    db_session.add(legacy)
    db_session.flush()

    sub = ms_cal.ensure_primary_subscription(db_session, account, settings=settings, access_token="ms-access")
    db_session.flush()
    assert sub.id == legacy.id
    assert sub.external_calendar_id == calendar_id
    assert sub.external_calendar_id != "primary"


def test_sync_full_upserts_microsoft_events(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar_id = str(uuid.uuid4())
    event_id = f"evt-{uuid.uuid4()}"
    settings = _ms_settings()
    graph = FakeGraph(calendar_id)
    graph.delta_events = [
        _graph_event(event_id, "Standup", "2026-08-14T15:00:00", "2026-08-14T16:00:00"),
    ]
    _patch_ms_httpx(monkeypatch, graph)
    owner_id = _current_user_id(client)
    account = _seed_microsoft_account(
        db_session, owner_id=owner_id, settings=settings, calendar_id=calendar_id
    )

    now = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
    upserted = ms_cal.sync_account_events(
        db_session,
        settings=settings,
        account=account,
        time_min=now - timedelta(days=7),
        time_max=now + timedelta(days=21),
    )
    db_session.flush()

    assert upserted == 1
    row = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == event_id)
        .one()
    )
    assert row.provider == CalendarProvider.microsoft
    assert row.calendar_id == calendar_id
    assert row.title == "Standup"
    assert row.scheduled_block_id is None
    sub = (
        db_session.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .one()
    )
    assert sub.sync_cursor == graph.delta_link
    assert any("calendarView/delta" in url for _, url in graph.calls)


def test_sync_delta_incremental_and_expired_fallback(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar_id = str(uuid.uuid4())
    event_id = f"evt-{uuid.uuid4()}"
    settings = _ms_settings()
    graph = FakeGraph(calendar_id)
    cursor = f"{_GRAPH}/me/calendars/{quote(calendar_id, safe='')}/calendarView/delta?$deltatoken=cursor-1"
    graph.incremental_events = [
        _graph_event(event_id, "Delta meet", "2026-08-15T10:00:00", "2026-08-15T10:30:00"),
    ]
    _patch_ms_httpx(monkeypatch, graph)
    owner_id = _current_user_id(client)
    account = _seed_microsoft_account(
        db_session,
        owner_id=owner_id,
        settings=settings,
        calendar_id=calendar_id,
        sync_cursor=cursor,
    )

    now = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
    upserted = ms_cal.sync_account_events(
        db_session,
        settings=settings,
        account=account,
        time_min=now - timedelta(days=7),
        time_max=now + timedelta(days=21),
    )
    db_session.flush()
    assert upserted == 1
    row = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == event_id)
        .one()
    )
    assert row.provider == CalendarProvider.microsoft
    assert row.title == "Delta meet"

    expired_id = f"evt-{uuid.uuid4()}"
    graph.incremental_status = 410
    graph.delta_events = [
        _graph_event(expired_id, "Resync", "2026-08-16T09:00:00", "2026-08-16T10:00:00"),
    ]
    upserted = ms_cal.sync_account_events(
        db_session,
        settings=settings,
        account=account,
        time_min=now - timedelta(days=7),
        time_max=now + timedelta(days=21),
    )
    db_session.flush()
    assert upserted == 1
    recovered = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == expired_id)
        .one()
    )
    assert recovered.provider == CalendarProvider.microsoft
    assert recovered.title == "Resync"


def test_push_scheduled_block_creates_graph_event_when_mirroring(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar_id = str(uuid.uuid4())
    settings = _ms_settings()
    graph = FakeGraph(calendar_id)
    _patch_ms_httpx(monkeypatch, graph)
    owner_id = _current_user_id(client)
    account = _seed_microsoft_account(
        db_session,
        owner_id=owner_id,
        settings=settings,
        calendar_id=calendar_id,
        mirror_blocks=True,
    )

    created = client.post("/api/v1/tasks", json={"title": "Deep work"})
    assert created.status_code == 201, created.text
    task_id = uuid.UUID(created.json()["id"])
    start = datetime(2026, 8, 14, 18, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    block = ScheduledBlock(owner_id=owner_id, task_id=task_id, start_time=start, end_time=end)
    db_session.add(block)
    db_session.flush()

    ms_cal.push_scheduled_block(db_session, settings, block)
    db_session.flush()

    row = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
        .one()
    )
    assert row.provider == CalendarProvider.microsoft
    assert row.external_event_id == graph.created_event_id
    assert row.calendar_id == calendar_id
    assert row.calendar_account_id == account.id
    assert row.task_id == task_id
    assert any(method == "POST" and "/events" in url for method, url in graph.calls)


def test_push_scheduled_block_noops_when_mirror_disabled(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calendar_id = str(uuid.uuid4())
    settings = _ms_settings()
    graph = FakeGraph(calendar_id)
    _patch_ms_httpx(monkeypatch, graph)
    owner_id = _current_user_id(client)
    _seed_microsoft_account(
        db_session,
        owner_id=owner_id,
        settings=settings,
        calendar_id=calendar_id,
        mirror_blocks=False,
    )
    task = Task(owner_id=owner_id, title="No mirror")
    db_session.add(task)
    db_session.flush()
    block = ScheduledBlock(
        owner_id=owner_id,
        task_id=task.id,
        start_time=datetime(2026, 8, 14, 19, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
    )
    db_session.add(block)
    db_session.flush()

    ms_cal.push_scheduled_block(db_session, settings, block)
    db_session.flush()
    mirrored = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
        .count()
    )
    assert mirrored == 0
    assert not any(method == "POST" for method, _ in graph.calls)


def test_calendars_and_sync_dispatch_by_provider(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _ms_settings()
    monkeypatch.setattr("app.api.routes.calendar.get_settings", lambda: settings)
    owner_id = _current_user_id(client)
    ms_account = _seed_microsoft_account(
        db_session,
        owner_id=owner_id,
        settings=settings,
        calendar_id=str(uuid.uuid4()),
    )
    g_account = _seed_google_account(db_session, owner_id=owner_id, settings=settings)

    google_list_calls: list[str] = []
    microsoft_list_calls: list[str] = []
    google_sync_calls: list[uuid.UUID] = []
    microsoft_sync_calls: list[uuid.UUID] = []

    monkeypatch.setattr(
        "app.api.routes.calendar.get_google_access_token",
        lambda db, settings, account: "g-access",
    )
    monkeypatch.setattr(
        "app.api.routes.calendar.get_microsoft_access_token",
        lambda db, settings, account: "ms-access",
    )

    def _list_google(access: str) -> list[dict]:
        google_list_calls.append(access)
        return [{"id": "primary", "summary": "GCal", "primary": True, "accessRole": "owner"}]

    def _list_microsoft(access: str) -> list[dict]:
        microsoft_list_calls.append(access)
        return [
            {
                "id": str(uuid.uuid4()),
                "summary": "Outlook",
                "primary": True,
                "accessRole": "owner",
            }
        ]

    monkeypatch.setattr("app.api.routes.calendar.list_google_calendars", _list_google)
    monkeypatch.setattr("app.api.routes.calendar.list_microsoft_calendars", _list_microsoft)

    def _sync_google(db, *, settings, account, time_min, time_max) -> int:  # noqa: ANN001
        google_sync_calls.append(account.id)
        return 3

    def _sync_microsoft(db, *, settings, account, time_min, time_max) -> int:  # noqa: ANN001
        microsoft_sync_calls.append(account.id)
        return 5

    monkeypatch.setattr("app.api.routes.calendar.sync_google_account_events", _sync_google)
    monkeypatch.setattr("app.api.routes.calendar.sync_microsoft_account_events", _sync_microsoft)

    ms_list = client.get("/api/v1/calendar/calendars", params={"account_id": str(ms_account.id)})
    assert ms_list.status_code == 200, ms_list.text
    assert ms_list.json().get("code") != "CALENDAR_NOT_GOOGLE"
    assert ms_list.json()["items"][0]["summary"] == "Outlook"
    assert microsoft_list_calls == ["ms-access"]
    assert google_list_calls == []

    g_list = client.get("/api/v1/calendar/calendars", params={"account_id": str(g_account.id)})
    assert g_list.status_code == 200, g_list.text
    assert g_list.json()["items"][0]["summary"] == "GCal"
    assert google_list_calls == ["g-access"]

    ms_sync = client.post(f"/api/v1/calendar/accounts/{ms_account.id}/sync")
    assert ms_sync.status_code == 200, ms_sync.text
    assert ms_sync.json().get("code") != "CALENDAR_NOT_GOOGLE"
    assert ms_sync.json()["upserted"] == 5
    assert microsoft_sync_calls == [ms_account.id]
    assert google_sync_calls == []

    g_sync = client.post(f"/api/v1/calendar/accounts/{g_account.id}/sync")
    assert g_sync.status_code == 200, g_sync.text
    assert g_sync.json()["upserted"] == 3
    assert google_sync_calls == [g_account.id]


def test_patch_account_mirror_blocks_and_legacy_alias(
    client: TestClient,
    db_session: Session,
) -> None:
    settings = _ms_settings()
    owner_id = _current_user_id(client)
    account = _seed_microsoft_account(
        db_session,
        owner_id=owner_id,
        settings=settings,
        calendar_id=str(uuid.uuid4()),
        mirror_blocks=False,
    )

    legacy = client.patch(
        f"/api/v1/calendar/accounts/{account.id}",
        json={"mirror_blocks_to_google": True},
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["mirror_blocks"] is True
    assert "mirror_blocks_to_google" not in legacy.json()

    current = client.patch(
        f"/api/v1/calendar/accounts/{account.id}",
        json={"mirror_blocks": False},
    )
    assert current.status_code == 200, current.text
    assert current.json()["mirror_blocks"] is False
