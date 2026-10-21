"""T1-F synthetic acceptance — calendar identity / alias canonicalize (F1–F22).

Baseline: feature/0.7-s2-cutover @ 7992650577f78ca528892498421ac4539276e0a5
Disposable Postgres only; provider HTTP mocked.
"""

from __future__ import annotations

import os
import subprocess
import threading
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.routes.calendar import put_calendar_subscriptions
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
from app.scheduler.busy_map import busy_from_sources, load_immovable_busy_sources
from app.scheduler.calendar_freshness import evaluate_calendar_freshness, required_coverage_window
from app.schemas.calendar import CalendarSubscriptionPutItem, CalendarSubscriptionsPut
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services import calendar_alias_canonicalize as cal_canon
from app.services.calendar_alias_canonicalize import (
    IDENTITY_DISABLED_TARGET_COLLISION_CAUSE,
    T1F_BASELINE_SHA,
    t1f_tip_sha_allowed,
    canonicalize_calendar_account,
    fetch_account_identity_evidence,
    lock_calendar_account_for_identity,
    prepare_subscriptions_for_sync,
)
from app.services.calendar_coverage import commit_subscription_coverage_success
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

UTC = timezone.utc
_FERNET = Fernet = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode(
    "utf-8"
)
_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _disposable_db_only() -> None:
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def test_t1f_baseline_sha_when_required() -> None:
    if os.environ.get("T1F_REQUIRE_TIP") != "1":
        pytest.skip("T1F_REQUIRE_TIP not set")
    tip = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert t1f_tip_sha_allowed(tip), f"tip {tip} is not baseline, known tip, or descendant"


def _settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        google_client_id="t1f-client",
        google_client_secret="t1f-secret",
        google_redirect_uri="http://127.0.0.1/unused",
        microsoft_client_id="t1f-ms-client",
        microsoft_client_secret="t1f-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _owner(db: Session) -> tuple[User, UserSettings]:
    token = uuid.uuid4().hex[:10]
    user = User(
        email=f"t1f-{token}@example.test",
        username=f"t1f_{token}",
        display_name="T1F",
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
        account_email=f"t1f-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc=encrypt_token(cfg, "access"),
        refresh_token_enc=encrypt_token(cfg, "refresh"),
        token_expires_at=_NOW + timedelta(hours=2),
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
    summary: str = "Cal",
    enabled: bool = True,
    role: CalendarSubscriptionRole = CalendarSubscriptionRole.primary,
) -> CalendarSubscription:
    row = CalendarSubscription(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary=summary,
        role=role,
        is_enabled=enabled,
        provider_timezone="UTC",
    )
    db.add(row)
    db.flush()
    return row


def _google_list(primary_id: str, *, extra: list[dict[str, Any]] | None = None) -> list[dict]:
    items = [{"id": primary_id, "summary": "Primary", "primary": True, "accessRole": "owner"}]
    if extra:
        items.extend(extra)
    return items


def _patch_google_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gcal, "get_valid_access_token", lambda *_a, **_k: "access-token")


def _patch_ms_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ms_cal, "get_valid_access_token", lambda *_a, **_k: "ms-access-token")


def _patch_google_list(monkeypatch: pytest.MonkeyPatch, items: list[dict] | None, *, fail: bool = False) -> None:
    def _list(_token: str) -> list[dict]:
        if fail:
            raise ApiError(502, "list failed", "GOOGLE_CALENDAR_LIST")
        return items or []

    monkeypatch.setattr(gcal, "list_google_calendars", _list)


def _patch_ms_default_and_list(
    monkeypatch: pytest.MonkeyPatch,
    default_id: str,
    listed: list[dict] | None = None,
    *,
    fail: bool = False,
) -> None:
    def _default(_token: str) -> tuple[str, str | None]:
        if fail:
            raise ApiError(502, "default failed", "MICROSOFT_PRIMARY_CALENDAR")
        return default_id, "Calendar"

    def _list(_token: str) -> list[dict]:
        if fail:
            raise ApiError(502, "list failed", "MICROSOFT_CALENDAR_LIST")
        return listed or [{"id": default_id, "summary": "Calendar", "primary": True}]

    monkeypatch.setattr(ms_cal, "_fetch_default_calendar", _default)
    monkeypatch.setattr(ms_cal, "list_microsoft_calendars", _list)


def _sync_google(db: Session, account: CalendarAccount, monkeypatch: pytest.MonkeyPatch) -> int:
    _patch_google_token(monkeypatch)
    pulls: list[str] = []

    def _pull(*_a, subscription: CalendarSubscription, **_k):
        pulls.append(subscription.external_calendar_id)
        return [], None, True, 1

    monkeypatch.setattr(gcal, "_pull_subscription_changes", _pull)
    start, end = _NOW - timedelta(days=7), _NOW + timedelta(days=21)
    count = gcal.sync_account_events(
        db, settings=_settings(), account=account, time_min=start, time_max=end
    )
    monkeypatch.setattr(gcal, "_pull_subscription_changes", _pull)
    _sync_google.last_pulls = pulls  # type: ignore[attr-defined]
    return count


def test_f1_google_same_calendar_two_aliases(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    _sub(db_session, account, calendar_id="primary", summary="Primary")
    _sub(db_session, account, calendar_id=primary_id, summary="Primary", role=CalendarSubscriptionRole.informational)
    _patch_google_list(monkeypatch, _google_list(primary_id))
    _sync_google(db_session, account, monkeypatch)
    enabled = (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .all()
    )
    assert len(enabled) == 1
    assert enabled[0].external_calendar_id == primary_id
    assert enabled[0].role == CalendarSubscriptionRole.primary
    assert len(_sync_google.last_pulls) == 1  # type: ignore[attr-defined]


def test_f2_google_unrelated_primaries(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    a, b = "cal-a@test.com", "cal-b@test.com"
    _sub(db_session, account, calendar_id=a, summary="Primary")
    _sub(db_session, account, calendar_id=b, summary="Primary")
    _patch_google_list(
        monkeypatch,
        [
            {"id": a, "summary": "Primary", "primary": True},
            {"id": b, "summary": "Primary", "primary": False},
        ],
    )
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    enabled = (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .all()
    )
    assert len(enabled) == 2


def test_f3_google_display_name_trap(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    a, b = "id-a@test.com", "id-b@test.com"
    _sub(db_session, account, calendar_id=a, summary="Same Name")
    _sub(db_session, account, calendar_id=b, summary="Same Name")
    _patch_google_list(
        monkeypatch,
        [
            {"id": a, "summary": "Same Name", "primary": True},
            {"id": b, "summary": "Same Name", "primary": False},
        ],
    )
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    assert (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .count()
        == 2
    )


def test_f4_ms_legacy_primary_plus_graph_id(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft)
    cal_id = str(uuid.uuid4())
    _sub(db_session, account, calendar_id="primary")
    _sub(db_session, account, calendar_id=cal_id, summary="Calendar")
    _patch_ms_default_and_list(monkeypatch, cal_id)
    ms_cal.ensure_primary_subscription(
        db_session, account, settings=_settings(), access_token="ms-access"
    )
    enabled = (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .all()
    )
    assert len(enabled) == 1
    assert enabled[0].external_calendar_id == cal_id


def test_f5_ms_two_defaults_by_name_only(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    _sub(db_session, account, calendar_id=a, summary="Calendar")
    _sub(db_session, account, calendar_id=b, summary="Calendar")
    _patch_ms_default_and_list(
        monkeypatch,
        a,
        listed=[
            {"id": a, "summary": "Calendar", "primary": False},
            {"id": b, "summary": "Calendar", "primary": False},
        ],
    )
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    assert (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .count()
        == 2
    )


def test_f6_put_idempotency(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_google_token(monkeypatch)
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    _sub(db_session, account, calendar_id=primary_id)
    _patch_google_list(monkeypatch, _google_list(primary_id))
    body = CalendarSubscriptionsPut(
        items=[
            CalendarSubscriptionPutItem(
                external_calendar_id=primary_id,
                summary="Primary",
                role=CalendarSubscriptionRole.primary,
                is_enabled=True,
            )
        ]
    )

    def _put() -> None:
        put_calendar_subscriptions(account.id, body, db_session, owner)

    _put()
    sub = (
        db_session.query(CalendarSubscription)
        .filter(CalendarSubscription.calendar_account_id == account.id)
        .one()
    )
    commit_subscription_coverage_success(
        sub,
        now=_NOW,
        window_start=_NOW - timedelta(days=1),
        window_end=_NOW + timedelta(days=1),
        mode="full",
        pagination_complete=True,
        page_count=1,
        item_count=0,
        show_deleted=True,
        single_events=True,
        sync_token="tok",
        generation=1,
    )
    db_session.flush()
    gen_before = sub.coverage_success_generation
    _put()
    db_session.refresh(sub)
    assert sub.coverage_success_generation == gen_before


def test_f7_freshness_cardinality(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    _sub(db_session, account, calendar_id="primary")
    _sub(db_session, account, calendar_id=primary_id)
    _patch_google_list(monkeypatch, _google_list(primary_id))
    prepare_subscriptions_for_sync(
        db_session, account, settings=_settings(), access_token="tok", now=_NOW
    )
    trust = evaluate_calendar_freshness(db_session, owner.id, usettings, _NOW)
    names = {d.calendar_name for d in trust.blocking_diagnostics}
    assert sum(1 for n in names if primary_id in n or "primary" in n.lower()) <= 1


def test_f8_merge_invalidates_readiness(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    survivor = _sub(db_session, account, calendar_id=primary_id)
    alias = _sub(db_session, account, calendar_id="primary", summary="Primary")
    commit_subscription_coverage_success(
        survivor,
        now=_NOW,
        window_start=_NOW - timedelta(days=1),
        window_end=_NOW + timedelta(days=1),
        mode="full",
        pagination_complete=True,
        page_count=1,
        item_count=0,
        show_deleted=True,
        single_events=True,
        sync_token="tok",
        generation=3,
    )
    _patch_google_list(monkeypatch, _google_list(primary_id))
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    db_session.refresh(survivor)
    assert survivor.coverage_success_at is None


def test_f9_alias_failure_survives_merge(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    survivor = _sub(db_session, account, calendar_id=primary_id)
    alias = _sub(db_session, account, calendar_id="primary")
    db_session.add(
        CalendarSubscriptionRefreshFailure(
            subscription_id=alias.id,
            failure_at=_NOW - timedelta(hours=1),
            cause="calendar_refresh_failed",
        )
    )
    db_session.flush()
    _patch_google_list(monkeypatch, _google_list(primary_id))
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    db_session.flush()
    survivor = (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.external_calendar_id == primary_id,
        )
        .one()
    )
    sidecar = (
        db_session.query(CalendarSubscriptionRefreshFailure)
        .filter(CalendarSubscriptionRefreshFailure.subscription_id == survivor.id)
        .one_or_none()
    )
    assert sidecar is not None
    assert survivor.coverage_last_failure_cause == "calendar_refresh_failed"
    trust = evaluate_calendar_freshness(db_session, owner.id, usettings, _NOW)
    assert not trust.ok


def test_f9b_row_failure_newer_than_sidecar_on_merge(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    survivor = _sub(db_session, account, calendar_id=primary_id)
    alias = _sub(db_session, account, calendar_id="primary")
    db_session.add(
        CalendarSubscriptionRefreshFailure(
            subscription_id=alias.id,
            failure_at=_NOW - timedelta(days=2),
            cause="calendar_refresh_failed",
        )
    )
    alias.coverage_last_failure_at = _NOW - timedelta(hours=1)
    alias.coverage_last_failure_cause = "calendar_coverage_missing"
    db_session.flush()
    _patch_google_list(monkeypatch, _google_list(primary_id))
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    db_session.flush()
    db_session.refresh(survivor)
    assert survivor.coverage_last_failure_cause == "calendar_coverage_missing"
    sidecar = (
        db_session.query(CalendarSubscriptionRefreshFailure)
        .filter(CalendarSubscriptionRefreshFailure.subscription_id == survivor.id)
        .one_or_none()
    )
    assert sidecar is not None
    assert sidecar.cause == "calendar_coverage_missing"
    trust = evaluate_calendar_freshness(db_session, owner.id, usettings, _NOW)
    assert not trust.ok


def test_f10_disable_must_not_unblock(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    survivor = _sub(db_session, account, calendar_id=primary_id)
    alias = _sub(db_session, account, calendar_id="primary", enabled=False)
    db_session.add(
        CalendarSubscriptionRefreshFailure(
            subscription_id=alias.id,
            failure_at=_NOW,
            cause="calendar_refresh_failed",
        )
    )
    db_session.flush()
    _patch_google_list(monkeypatch, _google_list(primary_id))
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    db_session.refresh(survivor)
    assert alias.is_enabled is False
    assert survivor.is_enabled is True
    assert survivor.coverage_success_at is None
    assert survivor.coverage_last_failure_cause is None
    trust = evaluate_calendar_freshness(db_session, owner.id, usettings, _NOW)
    assert not trust.ok
    causes = {d.cause for d in trust.blocking_diagnostics}
    assert causes & {"calendar_coverage_missing", "calendar_coverage_window_missing"}


def test_f11_noop_canonicalization_twice(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    sub = _sub(db_session, account, calendar_id=primary_id)
    commit_subscription_coverage_success(
        sub,
        now=_NOW,
        window_start=_NOW - timedelta(days=1),
        window_end=_NOW + timedelta(days=1),
        mode="full",
        pagination_complete=True,
        page_count=1,
        item_count=0,
        show_deleted=True,
        single_events=True,
        sync_token="tok",
        generation=2,
    )
    evidence = fetch_account_identity_evidence(
        db_session, account, settings=_settings(), access_token="tok"
    )
    _patch_google_list(monkeypatch, _google_list(primary_id))
    canonicalize_calendar_account(db_session, account, evidence=evidence, now=_NOW)
    gen = sub.coverage_success_generation
    canonicalize_calendar_account(db_session, account, evidence=evidence, now=_NOW)
    assert sub.coverage_success_generation == gen


def test_f12_same_id_different_accounts(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner1, _ = _owner(db_session)
    owner2, _ = _owner(db_session)
    cal_id = "shared-id@test.com"
    acc1 = _account(db_session, owner1)
    acc2 = _account(db_session, owner2)
    _sub(db_session, acc1, calendar_id=cal_id)
    _sub(db_session, acc2, calendar_id=cal_id)
    _patch_google_list(monkeypatch, _google_list(cal_id))
    for account in (acc1, acc2):
        canonicalize_calendar_account(
            db_session,
            account,
            evidence=fetch_account_identity_evidence(
                db_session, account, settings=_settings(), access_token="tok"
            ),
            now=_NOW,
        )
    assert (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id.in_([acc1.id, acc2.id]),
            CalendarSubscription.is_enabled.is_(True),
        )
        .count()
        == 2
    )


def test_f13_concurrent_put_and_ensure_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    primary_id = "user@gmail.com"
    _patch_google_list(monkeypatch, _google_list(primary_id))
    _patch_google_token(monkeypatch)
    errors: list[BaseException] = []
    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account(seed, owner)
        _sub(seed, account, calendar_id="primary")
        seed.commit()
        account_id = account.id
        owner_id = owner.id
    finally:
        seed.close()

    barrier = threading.Barrier(2)

    def _worker_put() -> None:
        db = SessionLocal()
        try:
            owner = db.query(User).filter(User.id == owner_id).one()
            account = db.query(CalendarAccount).filter(CalendarAccount.id == account_id).one()
            body = CalendarSubscriptionsPut(
                items=[
                    CalendarSubscriptionPutItem(
                        external_calendar_id=primary_id,
                        summary="Primary",
                        role=CalendarSubscriptionRole.primary,
                        is_enabled=True,
                    )
                ]
            )
            barrier.wait(timeout=10)
            put_calendar_subscriptions(account.id, body, db, owner)
            db.commit()
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()

    def _worker_ensure() -> None:
        db = SessionLocal()
        try:
            account = db.query(CalendarAccount).filter(CalendarAccount.id == account_id).one()
            barrier.wait(timeout=10)
            gcal.ensure_primary_subscription(db, account)
            db.commit()
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()

    t1 = threading.Thread(target=_worker_put)
    t2 = threading.Thread(target=_worker_ensure)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not errors
    db = SessionLocal()
    try:
        enabled = (
            db.query(CalendarSubscription)
            .filter(
                CalendarSubscription.calendar_account_id == account_id,
                CalendarSubscription.is_enabled.is_(True),
            )
            .all()
        )
        assert len(enabled) == 1
        assert enabled[0].external_calendar_id == primary_id
        assert enabled[0].role == CalendarSubscriptionRole.primary
    finally:
        db.close()


def test_f14_independent_session_sync_put_merge_no_stale_alias_mint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider sync entry and ensure_primary in separate DB sessions under account lock."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    primary_id = "user@gmail.com"
    _patch_google_list(monkeypatch, _google_list(primary_id))
    _patch_google_token(monkeypatch)

    def _fast_pull(*_a, subscription: CalendarSubscription, **_k):
        return [], None, True, 1

    monkeypatch.setattr(gcal, "_pull_subscription_changes", _fast_pull)

    real_lock = cal_canon.lock_calendar_account_for_identity
    lock_held = threading.Event()
    release_sync = threading.Event()
    sync_finished = threading.Event()
    errors: list[BaseException] = []

    def _lock_with_sync_barrier(db: Session, account_id: UUID) -> CalendarAccount:
        account = real_lock(db, account_id)
        if getattr(threading.current_thread(), "t1f_f14_sync", False):
            lock_held.set()
            assert release_sync.wait(timeout=20)
        return account

    monkeypatch.setattr(cal_canon, "lock_calendar_account_for_identity", _lock_with_sync_barrier)

    seed = SessionLocal()
    try:
        owner, _ = _owner(seed)
        account = _account(seed, owner)
        alias = _sub(seed, account, calendar_id="primary", summary="Primary")
        survivor = _sub(seed, account, calendar_id=primary_id)
        seed.add(
            CalendarSubscriptionRefreshFailure(
                subscription_id=alias.id,
                failure_at=_NOW - timedelta(hours=2),
                cause="calendar_refresh_failed",
            )
        )
        seed.commit()
        account_id = account.id
        owner_id = owner.id
        alias_id = alias.id
        survivor_id = survivor.id
    finally:
        seed.close()

    def _sync_worker() -> None:
        db = SessionLocal()
        try:
            threading.current_thread().t1f_f14_sync = True  # type: ignore[attr-defined]
            account = db.query(CalendarAccount).filter(CalendarAccount.id == account_id).one()
            gcal.sync_account_events(
                db,
                settings=_settings(),
                account=account,
                time_min=_NOW - timedelta(days=1),
                time_max=_NOW + timedelta(days=1),
            )
            db.commit()
        except BaseException as exc:
            errors.append(exc)
        finally:
            sync_finished.set()
            db.close()

    def _ensure_worker() -> None:
        db = SessionLocal()
        try:
            assert lock_held.wait(timeout=20)
            db.execute(text("SET lock_timeout = '8000ms'"))
            account = db.query(CalendarAccount).filter(CalendarAccount.id == account_id).one()
            try:
                gcal.ensure_primary_subscription(db, account)
                db.commit()
            except DBAPIError:
                db.rollback()
            release_sync.set()
            assert sync_finished.wait(timeout=30)
            db2 = SessionLocal()
            try:
                account2 = db2.query(CalendarAccount).filter(CalendarAccount.id == account_id).one()
                gcal.ensure_primary_subscription(db2, account2)
                db2.commit()
            finally:
                db2.close()
        except BaseException as exc:
            errors.append(exc)
            release_sync.set()
        finally:
            db.close()

    t_sync = threading.Thread(target=_sync_worker, name="f14-sync")
    t_ensure = threading.Thread(target=_ensure_worker, name="f14-ensure")
    t_sync.start()
    t_ensure.start()
    t_sync.join(timeout=45)
    t_ensure.join(timeout=45)
    assert not errors, errors

    verify = SessionLocal()
    try:
        enabled = (
            verify.query(CalendarSubscription)
            .filter(
                CalendarSubscription.calendar_account_id == account_id,
                CalendarSubscription.is_enabled.is_(True),
            )
            .all()
        )
        assert len(enabled) == 1
        assert enabled[0].external_calendar_id == primary_id
        assert enabled[0].role == CalendarSubscriptionRole.primary
        primary_rows = (
            verify.query(CalendarSubscription)
            .filter(
                CalendarSubscription.calendar_account_id == account_id,
                CalendarSubscription.external_calendar_id == "primary",
            )
            .all()
        )
        assert len(primary_rows) == 1
        assert primary_rows[0].is_enabled is False
        sidecar = (
            verify.query(CalendarSubscriptionRefreshFailure)
            .filter(CalendarSubscriptionRefreshFailure.subscription_id == survivor_id)
            .one_or_none()
        )
        assert sidecar is not None
        assert sidecar.cause == "calendar_refresh_failed"
        verify.refresh(verify.query(CalendarSubscription).filter(CalendarSubscription.id == survivor_id).one())
        survivor_row = verify.query(CalendarSubscription).filter(CalendarSubscription.id == survivor_id).one()
        assert survivor_row.coverage_last_failure_cause == "calendar_refresh_failed"
        _ = alias_id
    finally:
        verify.close()


def test_f15_unresolved_then_resolved(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    _sub(db_session, account, calendar_id="primary")
    _sub(db_session, account, calendar_id=primary_id)
    state = {"fail": True}

    def _list(_token: str) -> list[dict]:
        if state["fail"]:
            raise ApiError(502, "list failed", "GOOGLE_CALENDAR_LIST")
        return _google_list(primary_id)

    monkeypatch.setattr(gcal, "list_google_calendars", _list)
    _patch_google_token(monkeypatch)
    pulls: list[str] = []

    def _pull(*_a, subscription: CalendarSubscription, **_k):
        pulls.append(subscription.external_calendar_id)
        return [], None, True, 1

    monkeypatch.setattr(gcal, "_pull_subscription_changes", _pull)
    gcal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=_NOW - timedelta(days=1),
        time_max=_NOW + timedelta(days=1),
    )
    assert len(pulls) == 0
    state["fail"] = False
    prepare_subscriptions_for_sync(
        db_session, account, settings=_settings(), access_token="tok", now=_NOW
    )
    assert (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .count()
        == 1
    )


def test_f16a_pre_sync_disabled_target_collision_blocks_without_mutation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enabled ``primary`` + disabled stable id — fail closed; freshness + PUT resolve."""
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    alias = _sub(db_session, account, calendar_id="primary", summary="Primary")
    disabled_stable = _sub(
        db_session,
        account,
        calendar_id=primary_id,
        summary="Primary",
        enabled=False,
        role=CalendarSubscriptionRole.informational,
    )
    _patch_google_list(monkeypatch, _google_list(primary_id))
    _patch_google_token(monkeypatch)
    eligible = prepare_subscriptions_for_sync(
        db_session, account, settings=_settings(), access_token="tok", now=_NOW
    )
    db_session.flush()
    db_session.refresh(disabled_stable)
    db_session.refresh(alias)
    assert disabled_stable.is_enabled is False
    assert alias.is_enabled is True
    assert alias.coverage_last_failure_cause == IDENTITY_DISABLED_TARGET_COLLISION_CAUSE
    assert len(eligible) == 0
    trust = evaluate_calendar_freshness(db_session, owner.id, usettings, _NOW)
    assert not trust.ok
    causes = {d.cause for d in trust.blocking_diagnostics}
    assert IDENTITY_DISABLED_TARGET_COLLISION_CAUSE in causes

    body = CalendarSubscriptionsPut(
        items=[
            CalendarSubscriptionPutItem(
                external_calendar_id=primary_id,
                summary="Primary",
                role=CalendarSubscriptionRole.primary,
                is_enabled=True,
            )
        ]
    )
    put_calendar_subscriptions(account.id, body, db_session, owner)
    enabled = (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .all()
    )
    assert len(enabled) == 1
    assert enabled[0].external_calendar_id == primary_id
    assert enabled[0].coverage_last_failure_cause is None


def test_f16_disabled_row_same_canonical(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_google_token(monkeypatch)
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    disabled = _sub(db_session, account, calendar_id=primary_id, enabled=False)
    body = CalendarSubscriptionsPut(
        items=[
            CalendarSubscriptionPutItem(
                external_calendar_id=primary_id,
                summary="Primary",
                role=CalendarSubscriptionRole.primary,
                is_enabled=True,
            )
        ]
    )
    _patch_google_list(monkeypatch, _google_list(primary_id))
    put_calendar_subscriptions(account.id, body, db_session, owner)
    enabled = (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .all()
    )
    assert len(enabled) == 1


def test_f17b_ms_legacy_primary_event_visibility(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft)
    cal_id = str(uuid.uuid4())
    legacy = _sub(db_session, account, calendar_id="primary", summary="Primary")
    start, end = _NOW, _NOW + timedelta(hours=1)
    db_session.add(
        ExternalCalendarEvent(
            owner_id=owner.id,
            calendar_account_id=account.id,
            provider=CalendarProvider.microsoft,
            external_event_id="ms-evt-1",
            calendar_id="primary",
            title="Busy",
            start_time=start,
            end_time=end,
            transparency="opaque",
            free_busy_provenance="microsoft_event_complete",
        )
    )
    db_session.flush()
    commit_subscription_coverage_success(
        legacy,
        now=_NOW,
        window_start=start - timedelta(days=1),
        window_end=end + timedelta(days=1),
        mode="ms_view",
        pagination_complete=True,
        page_count=1,
        item_count=0,
        show_deleted=True,
        single_events=True,
        sync_token="legacy-cursor",
        generation=1,
    )
    _patch_ms_default_and_list(monkeypatch, cal_id)
    _patch_ms_token(monkeypatch)
    ms_cal.ensure_primary_subscription(
        db_session, account, settings=_settings(), access_token="ms-access"
    )
    db_session.flush()
    row = (
        db_session.query(CalendarSubscription)
        .filter(CalendarSubscription.id == legacy.id)
        .one()
    )
    assert row.external_calendar_id == cal_id
    assert row.coverage_success_at is None
    assert row.sync_cursor is None
    evt = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == "ms-evt-1")
        .one()
    )
    assert evt.calendar_id == cal_id
    _pinned, events = load_immovable_busy_sources(db_session, owner.id)
    assert any(ev.external_event_id == "ms-evt-1" and ev.calendar_id == cal_id for ev in events)


def test_f17_primary_to_list_id_event_visibility(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    sub = _sub(db_session, account, calendar_id="primary")
    start, end = _NOW, _NOW + timedelta(hours=1)
    db_session.add(
        ExternalCalendarEvent(
            owner_id=owner.id,
            calendar_account_id=account.id,
            provider=CalendarProvider.google,
            external_event_id="evt-1",
            calendar_id="primary",
            title="Busy",
            start_time=start,
            end_time=end,
            transparency="opaque",
            free_busy_provenance="google_event_complete",
        )
    )
    db_session.flush()
    _patch_google_list(monkeypatch, _google_list(primary_id))
    canonicalize_calendar_account(
        db_session,
        account,
        evidence=fetch_account_identity_evidence(
            db_session, account, settings=_settings(), access_token="tok"
        ),
        now=_NOW,
    )
    _pinned, events = load_immovable_busy_sources(db_session, owner.id)
    assert any(ev.calendar_id == primary_id for ev in events)
    busy = busy_from_sources(_pinned, events, range_start=start, range_end=end)
    assert len(busy) >= 1


def test_f18_conflicting_put_roles(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    _patch_google_list(monkeypatch, _google_list(primary_id))
    _patch_google_token(monkeypatch)
    body = CalendarSubscriptionsPut(
        items=[
            CalendarSubscriptionPutItem(
                external_calendar_id="primary",
                summary="Primary",
                role=CalendarSubscriptionRole.primary,
                is_enabled=True,
            ),
            CalendarSubscriptionPutItem(
                external_calendar_id=primary_id,
                summary="Primary",
                role=CalendarSubscriptionRole.informational,
                is_enabled=True,
            ),
        ]
    )
    with pytest.raises(ApiError) as exc:
        put_calendar_subscriptions(account.id, body, db_session, owner)
    assert exc.value.content["code"] == "CALENDAR_SUBSCRIPTION_ALIAS_CONFLICT"


def test_f19_google_list_fetch_failure(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    primary_id = "user@gmail.com"
    _patch_google_list(monkeypatch, None, fail=True)
    _patch_google_token(monkeypatch)
    body = CalendarSubscriptionsPut(
        items=[
            CalendarSubscriptionPutItem(
                external_calendar_id="primary",
                summary="Primary",
                role=CalendarSubscriptionRole.primary,
                is_enabled=True,
            ),
            CalendarSubscriptionPutItem(
                external_calendar_id=primary_id,
                summary="Primary",
                role=CalendarSubscriptionRole.informational,
                is_enabled=True,
            ),
        ]
    )
    with pytest.raises(ApiError) as exc:
        put_calendar_subscriptions(account.id, body, db_session, owner)
    assert exc.value.content["code"] == "CALENDAR_IDENTITY_EVIDENCE_REQUIRED"


def test_f20_ms_default_fetch_failure(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner, usettings = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft)
    cal_id = str(uuid.uuid4())
    _sub(db_session, account, calendar_id="primary")
    _sub(db_session, account, calendar_id=cal_id)
    _patch_ms_default_and_list(monkeypatch, cal_id, fail=True)
    prepare_subscriptions_for_sync(
        db_session, account, settings=_settings(), access_token="tok", now=_NOW
    )
    trust = evaluate_calendar_freshness(db_session, owner.id, usettings, _NOW)
    assert not trust.ok
    assert (
        db_session.query(CalendarSubscription)
        .filter(
            CalendarSubscription.calendar_account_id == account.id,
            CalendarSubscription.is_enabled.is_(True),
        )
        .count()
        == 2
    )


def test_f21_google_ambiguous_multiple_primary(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner)
    _sub(db_session, account, calendar_id="primary")
    _sub(db_session, account, calendar_id="a@test.com")
    _patch_google_token(monkeypatch)
    _patch_google_list(
        monkeypatch,
        [
            {"id": "a@test.com", "primary": True},
            {"id": "b@test.com", "primary": True},
        ],
    )
    with pytest.raises(ApiError):
        body = CalendarSubscriptionsPut(
            items=[
                CalendarSubscriptionPutItem(
                    external_calendar_id="primary",
                    role=CalendarSubscriptionRole.primary,
                    is_enabled=True,
                ),
                CalendarSubscriptionPutItem(
                    external_calendar_id="a@test.com",
                    role=CalendarSubscriptionRole.informational,
                    is_enabled=True,
                ),
            ]
        )
        put_calendar_subscriptions(account.id, body, db_session, owner)


def test_f22_ms_ambiguous_multiple_default(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = _owner(db_session)
    account = _account(db_session, owner, provider=CalendarProvider.microsoft)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    _patch_ms_token(monkeypatch)
    _patch_ms_default_and_list(
        monkeypatch,
        a,
        listed=[
            {"id": a, "primary": True},
            {"id": b, "primary": True},
        ],
    )
    with pytest.raises(ApiError):
        body = CalendarSubscriptionsPut(
            items=[
                CalendarSubscriptionPutItem(
                    external_calendar_id=a,
                    role=CalendarSubscriptionRole.primary,
                    is_enabled=True,
                ),
                CalendarSubscriptionPutItem(
                    external_calendar_id=b,
                    role=CalendarSubscriptionRole.informational,
                    is_enabled=True,
                ),
            ]
        )
        put_calendar_subscriptions(account.id, body, db_session, owner)
