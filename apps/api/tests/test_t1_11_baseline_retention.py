"""T1-11 synthetic acceptance — export comparison baseline retention (G1–G12, M1–M2).

Grounding checkout at implementation start: feature/0.7-s2-cutover @ 0046c6a.
Disposable Postgres only (T1A_REQUIRE_DISPOSABLE_DSN=1); provider HTTP mocked.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import Settings
from app.db import SessionLocal, engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    ScheduledBlock,
    Task,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services.export_baseline import (
    EXPORT_BASELINE_SCHEMA_VERSION,
    GOOGLE_MIRROR_PUSH_SOURCE,
    MICROSOFT_MIRROR_PUSH_SOURCE,
    compute_export_baseline_fingerprint,
)
from app.services.mirror_tombstone import mark_block_mirrors_pending_deletion
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
_T1_11_START_SHA = "0046c6acfcc51ccb2d75ef5387abcfcacaa8216e"
_FERNET = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode(
    "utf-8"
)
_NOW = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
_GRAPH = "https://graph.microsoft.com/v1.0"


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def test_t1_11_start_sha_is_ancestor_of_tip() -> None:
    tip = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    subprocess.check_call(["git", "merge-base", "--is-ancestor", _T1_11_START_SHA, tip])


def _settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        google_client_id="t1-11-g",
        google_client_secret="t1-11-g-secret",
        google_redirect_uri="http://127.0.0.1/unused-g",
        microsoft_client_id="t1-11-ms",
        microsoft_client_secret="t1-11-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _owner(db: Session) -> User:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"t1-11-{token}@example.test",
        username=f"t1_11_{token}",
        display_name="T1-11",
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        session_epoch=0,
    )
    db.add(user)
    db.flush()
    db.add(
        UserSettings(
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
    )
    db.flush()
    return user


def _account(
    db: Session,
    owner: User,
    *,
    provider: CalendarProvider,
    calendar_id: str,
    mirror_blocks: bool = True,
) -> CalendarAccount:
    cfg = _settings()
    account = CalendarAccount(
        owner_id=owner.id,
        provider=provider,
        account_email=f"t1-11-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc=encrypt_token(cfg, "access"),
        refresh_token_enc=encrypt_token(cfg, "refresh"),
        token_expires_at=_NOW + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=mirror_blocks,
    )
    db.add(account)
    db.flush()
    db.add(
        CalendarSubscription(
            owner_id=owner.id,
            calendar_account_id=account.id,
            external_calendar_id=calendar_id,
            summary="Primary",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
        )
    )
    db.flush()
    return account


def _block(
    db: Session,
    owner: User,
    *,
    title: str = "Deep work",
    start: datetime | None = None,
    end: datetime | None = None,
) -> ScheduledBlock:
    task = Task(owner_id=owner.id, title=title)
    db.add(task)
    db.flush()
    block_start = start or datetime(2026, 8, 14, 18, 0, tzinfo=UTC)
    block_end = end or (block_start + timedelta(hours=1))
    block = ScheduledBlock(
        owner_id=owner.id,
        task_id=task.id,
        start_time=block_start,
        end_time=block_end,
    )
    db.add(block)
    db.flush()
    return block


def _patch_google_mirror_httpx(
    monkeypatch: pytest.MonkeyPatch,
    *,
    calendar_id: str,
    create_body: dict[str, Any] | None = None,
    patch_body: dict[str, Any] | None = None,
    create_status: int = 200,
    patch_status: int = 200,
) -> dict[str, str]:
    created_id = f"g-ev-{uuid.uuid4().hex[:8]}"
    ids = {"created": created_id}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "/events" in str(request.url):
            if create_status >= 400:
                return httpx.Response(create_status, text="create failed")
            body = create_body or {
                "id": created_id,
                "etag": '"create-etag"',
                "updated": "2026-08-14T18:00:00.000Z",
            }
            return httpx.Response(200, json=body)
        if request.method == "PATCH":
            if patch_status >= 400:
                return httpx.Response(patch_status, text="patch failed")
            body = patch_body or {
                "id": created_id,
                "etag": '"patch-etag"',
                "updated": "2026-08-14T19:00:00.000Z",
            }
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real = httpx.Client

    def factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(gcal.httpx, "Client", factory)
    return ids


def _patch_ms_mirror_httpx(
    monkeypatch: pytest.MonkeyPatch,
    calendar_id: str,
    *,
    create_body: dict[str, Any] | None = None,
    patch_body: dict[str, Any] | None = None,
    create_status: int = 201,
    patch_status: int = 200,
) -> dict[str, str]:
    created_id = f"ms-ev-{uuid.uuid4().hex[:8]}"
    ids = {"created": created_id}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/events"):
            if create_status >= 400:
                return httpx.Response(create_status, text="create failed")
            body = create_body or {
                "id": created_id,
                "@odata.etag": 'W/"ms-create"',
                "changeKey": "ck-create",
                "lastModifiedDateTime": "2026-08-14T18:00:00.000Z",
            }
            return httpx.Response(create_status, json=body)
        if request.method == "PATCH":
            if patch_status >= 400:
                return httpx.Response(patch_status, text="patch failed")
            body = patch_body or {
                "id": created_id,
                "@odata.etag": 'W/"ms-patch"',
                "changeKey": "ck-patch",
                "lastModifiedDateTime": "2026-08-14T19:00:00.000Z",
            }
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real = httpx.Client

    def factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(ms_cal.httpx, "Client", factory)
    return ids


@pytest.mark.parametrize(
    ("provider", "push", "patch_http", "source"),
    [
        (
            CalendarProvider.google,
            gcal.push_scheduled_block,
            _patch_google_mirror_httpx,
            GOOGLE_MIRROR_PUSH_SOURCE,
        ),
        (
            CalendarProvider.microsoft,
            ms_cal.push_scheduled_block,
            _patch_ms_mirror_httpx,
            MICROSOFT_MIRROR_PUSH_SOURCE,
        ),
    ],
    ids=["google-g1", "microsoft-m1"],
)
def test_mirror_push_captures_export_baseline(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
    source: str,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id)
    monkeypatch.setattr(
        gcal if provider == CalendarProvider.google else ms_cal,
        "get_valid_access_token",
        lambda *_a, **_k: "mock-access",
    )
    db = SessionLocal()
    try:
        owner = _owner(db)
        account = _account(db, owner, provider=provider, calendar_id=calendar_id)
        block = _block(db, owner)
        db.commit()
        push(db, _settings(), block)
        db.commit()
        row = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
            .one()
        )
        assert row.export_baseline_at is not None
        assert row.export_baseline_source == source
        assert row.export_calendar_id == calendar_id
        assert row.export_baseline_schema_version == EXPORT_BASELINE_SCHEMA_VERSION
        fp = compute_export_baseline_fingerprint(
            provider=provider,
            title=row.title or "",
            start=block.start_time,
            end=block.end_time,
            is_all_day=False,
        )
        assert row.export_baseline_fingerprint == fp
        if provider == CalendarProvider.google:
            assert row.export_baseline_etag == '"create-etag"'
            assert row.export_baseline_change_key is None
        else:
            assert row.export_baseline_etag == 'W/"ms-create"'
            assert row.export_baseline_change_key == "ck-create"
        assert row.calendar_account_id == account.id
    finally:
        db.close()


@pytest.mark.parametrize(
    ("provider", "push", "patch_http", "upsert"),
    [
        (CalendarProvider.google, gcal.push_scheduled_block, _patch_google_mirror_httpx, gcal._upsert_external_event),
        (
            CalendarProvider.microsoft,
            ms_cal.push_scheduled_block,
            _patch_ms_mirror_httpx,
            ms_cal._upsert_external_event,
        ),
    ],
    ids=["google-g2", "microsoft-m2"],
)
def test_ingest_refresh_does_not_overwrite_baseline(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
    upsert: Any,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id)
    monkeypatch.setattr(
        gcal if provider == CalendarProvider.google else ms_cal,
        "get_valid_access_token",
        lambda *_a, **_k: "mock-access",
    )
    db = SessionLocal()
    try:
        owner = _owner(db)
        account = _account(db, owner, provider=provider, calendar_id=calendar_id)
        block = _block(db, owner)
        db.commit()
        push(db, _settings(), block)
        db.commit()
        row = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
            .one()
        )
        baseline_fp = row.export_baseline_fingerprint
        baseline_cal = row.export_calendar_id
        sub = (
            db.query(CalendarSubscription)
            .filter(CalendarSubscription.calendar_account_id == account.id)
            .one()
        )
        if provider == CalendarProvider.google:
            remote = {
                "id": row.external_event_id,
                "summary": "Remote edited title",
                "start": {"dateTime": "2026-08-14T20:00:00.000Z", "timeZone": "UTC"},
                "end": {"dateTime": "2026-08-14T21:00:00.000Z", "timeZone": "UTC"},
                "transparency": "opaque",
            }
        else:
            remote = {
                "id": row.external_event_id,
                "subject": "Remote edited title",
                "start": {"dateTime": "2026-08-14T20:00:00.000Z", "timeZone": "UTC"},
                "end": {"dateTime": "2026-08-14T21:00:00.000Z", "timeZone": "UTC"},
                "showAs": "busy",
            }
        upsert(
            db,
            account=account,
            subscription=sub,
            event=remote,
            now=_NOW + timedelta(hours=1),
            sync_run_id="t1-11-refresh",
        )
        db.commit()
        refreshed = db.get(ExternalCalendarEvent, row.id)
        assert refreshed is not None
        assert refreshed.title == "Remote edited title"
        assert refreshed.export_baseline_fingerprint == baseline_fp
        assert refreshed.export_calendar_id == baseline_cal
    finally:
        db.close()


@pytest.mark.parametrize(
    ("provider", "push", "patch_http", "patch_fn"),
    [
        (
            CalendarProvider.google,
            gcal.push_scheduled_block,
            _patch_google_mirror_httpx,
            "patch_google_event",
        ),
        (
            CalendarProvider.microsoft,
            ms_cal.push_scheduled_block,
            _patch_ms_mirror_httpx,
            "patch_microsoft_event",
        ),
    ],
    ids=["google-g3", "microsoft-g3"],
)
def test_second_successful_push_replaces_single_latest_baseline(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
    patch_fn: str,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id)
    mod = gcal if provider == CalendarProvider.google else ms_cal
    monkeypatch.setattr(mod, "get_valid_access_token", lambda *_a, **_k: "mock-access")
    db = SessionLocal()
    try:
        owner = _owner(db)
        _account(db, owner, provider=provider, calendar_id=calendar_id)
        block = _block(db, owner, title="First")
        db.commit()
        push(db, _settings(), block)
        db.commit()
        row = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
            .one()
        )
        first_fp = row.export_baseline_fingerprint
        task = db.get(Task, block.task_id)
        assert task is not None
        task.title = "Second export title"
        db.commit()

        if provider == CalendarProvider.google:

            def _patch_2(*_a, **_k):
                return {
                    "id": row.external_event_id,
                    "etag": '"patch-2"',
                    "updated": "2026-08-14T20:00:00.000Z",
                }
        else:

            def _patch_2(*_a, **_k):
                return {
                    "id": row.external_event_id,
                    "@odata.etag": 'W/"patch-2"',
                    "changeKey": "ck-2",
                    "lastModifiedDateTime": "2026-08-14T20:00:00.000Z",
                }

        monkeypatch.setattr(mod, patch_fn, _patch_2)
        push(db, _settings(), block)
        db.commit()
        row2 = db.get(ExternalCalendarEvent, row.id)
        assert row2 is not None
        assert row2.export_baseline_fingerprint != first_fp
        if provider == CalendarProvider.google:
            assert row2.export_baseline_etag == '"patch-2"'
        else:
            assert row2.export_baseline_change_key == "ck-2"
    finally:
        db.close()


def test_soft_cancel_row_does_not_invent_baseline(db_session: Session) -> None:
    owner = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.google, calendar_id="cal-soft")
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        provider=CalendarProvider.google,
        external_event_id="ext-soft",
        calendar_id="cal-soft",
        title="Busy",
        start_time=_NOW,
        end_time=_NOW + timedelta(hours=1),
        is_all_day=False,
        is_provider_cancelled=True,
    )
    db_session.add(row)
    db_session.flush()
    assert row.export_baseline_at is None


@pytest.mark.parametrize(
    ("provider", "mark_cancelled", "source"),
    [
        (CalendarProvider.google, gcal._mark_provider_cancelled, GOOGLE_MIRROR_PUSH_SOURCE),
        (
            CalendarProvider.microsoft,
            ms_cal._mark_provider_cancelled,
            MICROSOFT_MIRROR_PUSH_SOURCE,
        ),
    ],
    ids=["google-g5", "microsoft-g5"],
)
def test_provider_cancelled_mirror_row_keeps_baseline(
    db_session: Session,
    provider: CalendarProvider,
    mark_cancelled: Any,
    source: str,
) -> None:
    calendar_id = f"cal-cancel-{uuid.uuid4().hex[:6]}"
    owner = _owner(db_session)
    account = _account(db_session, owner, provider=provider, calendar_id=calendar_id)
    block = _block(db_session, owner)
    external_id = f"ext-cancel-{uuid.uuid4().hex[:8]}"
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        scheduled_block_id=block.id,
        task_id=block.task_id,
        provider=provider,
        external_event_id=external_id,
        calendar_id=calendar_id,
        title="Mirrored",
        start_time=block.start_time,
        end_time=block.end_time,
        is_all_day=False,
        export_baseline_at=_NOW,
        export_baseline_source=source,
        export_calendar_id=calendar_id,
        export_baseline_fingerprint="abc",
        export_baseline_schema_version=1,
    )
    db_session.add(row)
    db_session.flush()
    mark_cancelled(
        db_session,
        owner_id=owner.id,
        external_id=external_id,
        now=_NOW + timedelta(minutes=5),
    )
    db_session.flush()
    assert row.is_provider_cancelled is True
    assert row.export_baseline_fingerprint == "abc"


def test_pending_deletion_tombstone_retains_baseline(db_session: Session) -> None:
    owner = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft, calendar_id="cal-tomb")
    block = _block(db_session, owner)
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        scheduled_block_id=block.id,
        provider=CalendarProvider.microsoft,
        external_event_id="ext-tomb",
        calendar_id="cal-tomb",
        title="Mirrored",
        start_time=block.start_time,
        end_time=block.end_time,
        is_all_day=False,
        export_baseline_at=_NOW,
        export_baseline_source=MICROSOFT_MIRROR_PUSH_SOURCE,
        export_calendar_id="cal-tomb",
        export_baseline_fingerprint="tomb-fp",
        export_baseline_schema_version=1,
    )
    db_session.add(row)
    db_session.flush()
    mark_block_mirrors_pending_deletion(db_session, block.id)
    db_session.flush()
    assert row.pending_deletion is True
    assert row.scheduled_block_id is None
    assert row.export_baseline_fingerprint == "tomb-fp"


def test_unlinked_upsert_does_not_fabricate_baseline(db_session: Session) -> None:
    owner = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.google, calendar_id="cal-ext")
    sub = (
        db_session.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .one()
    )
    external_id = f"external-only-{uuid.uuid4().hex[:8]}"
    inserted = gcal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={
            "id": external_id,
            "summary": "External busy",
            "start": {"dateTime": "2026-08-14T10:00:00.000Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-14T11:00:00.000Z", "timeZone": "UTC"},
            "transparency": "opaque",
            "status": "confirmed",
        },
        now=_NOW,
        sync_run_id="t1-11-g7",
    )
    assert inserted is True
    db_session.flush()
    row = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == external_id)
        .one()
    )
    assert row.scheduled_block_id is None
    assert row.export_baseline_at is None


def test_t1f_cache_calendar_rewrite_preserves_export_calendar_id(db_session: Session) -> None:
    owner = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.google, calendar_id="survivor@gmail.com")
    sub = (
        db_session.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .one()
    )
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        scheduled_block_id=None,
        provider=CalendarProvider.google,
        external_event_id="surv-ev",
        calendar_id="primary",
        title="Mirrored",
        start_time=_NOW,
        end_time=_NOW + timedelta(hours=1),
        is_all_day=False,
        export_calendar_id="legacy-primary",
        export_baseline_at=_NOW,
        export_baseline_source=GOOGLE_MIRROR_PUSH_SOURCE,
        export_baseline_fingerprint="g8-fp",
        export_baseline_schema_version=1,
    )
    db_session.add(row)
    db_session.flush()
    gcal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={
            "id": "surv-ev",
            "summary": "Remote",
            "start": {"dateTime": "2026-08-14T10:00:00.000Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-14T11:00:00.000Z", "timeZone": "UTC"},
            "transparency": "opaque",
        },
        now=_NOW,
        sync_run_id="t1-11-g8",
    )
    assert row.calendar_id == "survivor@gmail.com"
    assert row.export_calendar_id == "legacy-primary"


def test_ms_seeded_baseline_survives_refresh(db_session: Session) -> None:
    owner = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft, calendar_id="ms-seed")
    block = _block(db_session, owner)
    sub = (
        db_session.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .one()
    )
    row = ExternalCalendarEvent(
        owner_id=owner.id,
        calendar_account_id=account.id,
        scheduled_block_id=block.id,
        provider=CalendarProvider.microsoft,
        external_event_id="ms-seed-ev",
        calendar_id="ms-seed",
        title="Seeded",
        start_time=_NOW,
        end_time=_NOW + timedelta(hours=1),
        is_all_day=False,
        export_baseline_at=_NOW - timedelta(days=1),
        export_baseline_source=MICROSOFT_MIRROR_PUSH_SOURCE,
        export_calendar_id="ms-seed",
        export_baseline_etag='W/"seed"',
        export_baseline_change_key="seed-ck",
        export_baseline_fingerprint="seed-fp",
        export_baseline_schema_version=1,
    )
    db_session.add(row)
    db_session.flush()
    ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={
            "id": "ms-seed-ev",
            "subject": "Changed remotely",
            "start": {"dateTime": "2026-08-14T12:00:00.000Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-14T13:00:00.000Z", "timeZone": "UTC"},
            "showAs": "busy",
        },
        now=_NOW,
        sync_run_id="t1-11-g12",
    )
    assert row.title == "Changed remotely"
    assert row.export_baseline_fingerprint == "seed-fp"
    assert row.export_baseline_etag == 'W/"seed"'


@pytest.mark.parametrize(
    ("provider", "push", "patch_http"),
    [
        (CalendarProvider.google, gcal.push_scheduled_block, _patch_google_mirror_httpx),
        (CalendarProvider.microsoft, ms_cal.push_scheduled_block, _patch_ms_mirror_httpx),
    ],
    ids=["google-g10-rollback", "microsoft-g10-rollback"],
)
def test_successful_patch_then_transaction_rollback_restores_prior_baseline(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id)
    monkeypatch.setattr(
        gcal if provider == CalendarProvider.google else ms_cal,
        "get_valid_access_token",
        lambda *_a, **_k: "mock-access",
    )
    seed = SessionLocal()
    try:
        owner = _owner(seed)
        _account(seed, owner, provider=provider, calendar_id=calendar_id)
        block = _block(seed, owner)
        seed.commit()
        push(seed, _settings(), block)
        seed.commit()
        row_id = (
            seed.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
            .one()
            .id
        )
        block_id = block.id
    finally:
        seed.close()

    patch_http(
        monkeypatch,
        calendar_id=calendar_id,
        patch_body=(
            {"id": "x", "etag": '"would-change"', "updated": "2026-08-14T22:00:00.000Z"}
            if provider == CalendarProvider.google
            else {
                "id": "x",
                "@odata.etag": 'W/"would-change"',
                "changeKey": "would-ck",
                "lastModifiedDateTime": "2026-08-14T22:00:00.000Z",
            }
        ),
    )
    worker = SessionLocal()
    try:
        block = worker.get(ScheduledBlock, block_id)
        assert block is not None
        push(worker, _settings(), block)
        worker.flush()
        worker.rollback()
    finally:
        worker.close()

    verify = SessionLocal()
    try:
        row = verify.get(ExternalCalendarEvent, row_id)
        assert row is not None
        if provider == CalendarProvider.google:
            assert row.export_baseline_etag == '"create-etag"'
        else:
            assert row.export_baseline_change_key == "ck-create"
        assert row.title == "Deep work"
    finally:
        verify.close()


@pytest.mark.parametrize(
    ("provider", "push", "patch_http"),
    [
        (CalendarProvider.google, gcal.push_scheduled_block, _patch_google_mirror_httpx),
        (CalendarProvider.microsoft, ms_cal.push_scheduled_block, _patch_ms_mirror_httpx),
    ],
    ids=["google-g11-rollback", "microsoft-g11-rollback"],
)
def test_failed_create_then_rollback_leaves_no_row_or_baseline(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id, create_status=502)
    monkeypatch.setattr(
        gcal if provider == CalendarProvider.google else ms_cal,
        "get_valid_access_token",
        lambda *_a, **_k: "mock-access",
    )
    seed = SessionLocal()
    try:
        owner = _owner(seed)
        _account(seed, owner, provider=provider, calendar_id=calendar_id)
        block = _block(seed, owner)
        seed.commit()
        block_id = block.id
    finally:
        seed.close()

    worker = SessionLocal()
    try:
        block = worker.get(ScheduledBlock, block_id)
        assert block is not None
        with pytest.raises(ApiError):
            push(worker, _settings(), block)
        worker.rollback()
    finally:
        worker.close()

    verify = SessionLocal()
    try:
        count = (
            verify.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block_id)
            .count()
        )
        assert count == 0
    finally:
        verify.close()


@pytest.mark.parametrize(
    ("provider", "push", "patch_http"),
    [
        (CalendarProvider.google, gcal.push_scheduled_block, _patch_google_mirror_httpx),
        (CalendarProvider.microsoft, ms_cal.push_scheduled_block, _patch_ms_mirror_httpx),
    ],
    ids=["google-failed-patch", "microsoft-failed-patch"],
)
def test_failed_patch_api_error_leaves_baseline_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id)
    monkeypatch.setattr(
        gcal if provider == CalendarProvider.google else ms_cal,
        "get_valid_access_token",
        lambda *_a, **_k: "mock-access",
    )
    db = SessionLocal()
    try:
        owner = _owner(db)
        _account(db, owner, provider=provider, calendar_id=calendar_id)
        block = _block(db, owner)
        db.commit()
        push(db, _settings(), block)
        db.commit()
        prior = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
            .one()
        )
        prior_fp = prior.export_baseline_fingerprint
        prior_title = prior.title
        if provider == CalendarProvider.google:
            monkeypatch.setattr(
                gcal,
                "patch_google_event",
                lambda *_a, **_k: (_ for _ in ()).throw(
                    ApiError(502, "patch failed", "GOOGLE_EVENT_PATCH")
                ),
            )
        else:
            monkeypatch.setattr(
                ms_cal,
                "patch_microsoft_event",
                lambda *_a, **_k: (_ for _ in ()).throw(
                    ApiError(502, "patch failed", "MICROSOFT_EVENT_PATCH")
                ),
            )
        with pytest.raises(ApiError):
            push(db, _settings(), block)
        db.rollback()
        row = db.get(ExternalCalendarEvent, prior.id)
        assert row is not None
        assert row.title == prior_title
        assert row is not None
        assert row.export_baseline_fingerprint == prior_fp
    finally:
        db.close()


@pytest.mark.parametrize(
    ("provider", "push", "patch_http", "patch_fn", "token_mode"),
    [
        (
            CalendarProvider.google,
            gcal.push_scheduled_block,
            _patch_google_mirror_httpx,
            "patch_google_event",
            "absent",
        ),
        (
            CalendarProvider.google,
            gcal.push_scheduled_block,
            _patch_google_mirror_httpx,
            "patch_google_event",
            "malformed",
        ),
        (
            CalendarProvider.microsoft,
            ms_cal.push_scheduled_block,
            _patch_ms_mirror_httpx,
            "patch_microsoft_event",
            "absent",
        ),
        (
            CalendarProvider.microsoft,
            ms_cal.push_scheduled_block,
            _patch_ms_mirror_httpx,
            "patch_microsoft_event",
            "malformed",
        ),
    ],
    ids=[
        "google-absent-tokens",
        "google-malformed-tokens",
        "microsoft-absent-tokens",
        "microsoft-malformed-tokens",
    ],
)
def test_successful_patch_revision_tokens_clear_stale_fields(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
    patch_fn: str,
    token_mode: str,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id)
    mod = gcal if provider == CalendarProvider.google else ms_cal
    monkeypatch.setattr(mod, "get_valid_access_token", lambda *_a, **_k: "mock-access")
    db = SessionLocal()
    try:
        owner = _owner(db)
        _account(db, owner, provider=provider, calendar_id=calendar_id)
        block = _block(db, owner)
        db.commit()
        push(db, _settings(), block)
        db.commit()
        row = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
            .one()
        )
        if provider == CalendarProvider.google:
            assert row.export_baseline_etag is not None
        else:
            assert row.export_baseline_change_key is not None

        if token_mode == "absent":

            def _patch_no_tokens(*_a, **_k):
                return {"id": row.external_event_id}

        elif provider == CalendarProvider.google:

            def _patch_no_tokens(*_a, **_k):
                return {
                    "id": row.external_event_id,
                    "etag": 12345,
                    "updated": "2026-10-20T12:00:00",
                }

        else:

            def _patch_no_tokens(*_a, **_k):
                return {
                    "id": row.external_event_id,
                    "@odata.etag": 999,
                    "changeKey": "",
                    "lastModifiedDateTime": "not-a-date",
                }

        monkeypatch.setattr(mod, patch_fn, _patch_no_tokens)
        push(db, _settings(), block)
        db.commit()
        row2 = db.get(ExternalCalendarEvent, row.id)
        assert row2 is not None
        assert row2.export_baseline_etag is None
        assert row2.export_baseline_change_key is None
        assert row2.export_baseline_updated is None
        assert row2.export_baseline_fingerprint is not None
    finally:
        db.close()


@pytest.mark.parametrize(
    ("provider", "push", "patch_http"),
    [
        (CalendarProvider.google, gcal.push_scheduled_block, _patch_google_mirror_httpx),
        (CalendarProvider.microsoft, ms_cal.push_scheduled_block, _patch_ms_mirror_httpx),
    ],
    ids=["google-create-rollback", "microsoft-create-rollback"],
)
def test_successful_create_then_transaction_rollback_leaves_no_row_or_baseline(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
) -> None:
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    patch_http(monkeypatch, calendar_id=calendar_id)
    mod = gcal if provider == CalendarProvider.google else ms_cal
    monkeypatch.setattr(mod, "get_valid_access_token", lambda *_a, **_k: "mock-access")
    seed = SessionLocal()
    try:
        owner = _owner(seed)
        _account(seed, owner, provider=provider, calendar_id=calendar_id)
        block = _block(seed, owner)
        seed.commit()
        block_id = block.id
    finally:
        seed.close()

    worker = SessionLocal()
    try:
        block = worker.get(ScheduledBlock, block_id)
        assert block is not None
        push(worker, _settings(), block)
        worker.flush()
        worker.rollback()
    finally:
        worker.close()

    verify = SessionLocal()
    try:
        count = (
            verify.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block_id)
            .count()
        )
        assert count == 0
    finally:
        verify.close()


@pytest.mark.parametrize(
    ("provider", "push", "patch_http"),
    [
        (CalendarProvider.google, gcal.push_scheduled_block, _patch_google_mirror_httpx),
        (CalendarProvider.microsoft, ms_cal.push_scheduled_block, _patch_ms_mirror_httpx),
    ],
    ids=["google-fingerprint-body", "microsoft-fingerprint-body"],
)
def test_export_baseline_fingerprint_matches_mirror_request_body(
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    push: Any,
    patch_http: Any,
) -> None:
    """Microsecond wall times must hash like the provider JSON body (MS truncates seconds)."""
    calendar_id = f"cal-{uuid.uuid4().hex[:8]}"
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "events" in str(request.url.path):
            captured["body"] = json.loads(request.content.decode("utf-8"))
            if provider == CalendarProvider.google:
                return httpx.Response(
                    200,
                    json={
                        "id": f"g-{uuid.uuid4().hex[:8]}",
                        "etag": '"fp-etag"',
                        "updated": "2026-08-14T18:30:45.123Z",
                    },
                )
            return httpx.Response(
                201,
                json={
                    "id": f"ms-{uuid.uuid4().hex[:8]}",
                    "@odata.etag": 'W/"fp-ms"',
                    "changeKey": "fp-ck",
                    "lastModifiedDateTime": "2026-08-14T18:30:45.123Z",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real = httpx.Client
    mod = gcal if provider == CalendarProvider.google else ms_cal

    def factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(mod.httpx, "Client", factory)
    monkeypatch.setattr(mod, "get_valid_access_token", lambda *_a, **_k: "mock-access")

    micro_start = datetime(2026, 8, 14, 18, 30, 45, 123456, tzinfo=UTC)
    micro_end = micro_start + timedelta(hours=1)

    db = SessionLocal()
    try:
        owner = _owner(db)
        _account(db, owner, provider=provider, calendar_id=calendar_id)
        block = _block(db, owner, start=micro_start, end=micro_end)
        db.commit()
        push(db, _settings(), block)
        db.commit()
        row = (
            db.query(ExternalCalendarEvent)
            .filter(ExternalCalendarEvent.scheduled_block_id == block.id)
            .one()
        )
        assert "body" in captured
        body = captured["body"]
        if provider == CalendarProvider.google:
            assert body["start"]["dateTime"].endswith(".123456Z")
        else:
            assert body["start"]["dateTime"] == "2026-08-14T18:30:45"
        expected_fp = compute_export_baseline_fingerprint(
            provider=provider,
            title=row.title or "",
            start=block.start_time,
            end=block.end_time,
            is_all_day=False,
        )
        assert row.export_baseline_fingerprint == expected_fp
    finally:
        db.close()
