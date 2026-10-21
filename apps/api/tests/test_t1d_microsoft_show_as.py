"""Track 1 T1-D: Microsoft Graph showAs → BusyInputTrust mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import quote
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    ExternalCalendarEvent,
    User,
    UserSettings,
)
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.free_busy import (
    apply_transparency_update,
    effective_free_busy_kind,
    evaluate_busy_input_trust,
    events_for_busy_merge,
    resolve_microsoft_show_as,
)
from app.services import microsoft_calendar as ms_cal
from app.services.token_crypto import encrypt_token
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

HORIZON_START = datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc)
HORIZON_END = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)
UTC = timezone.utc
_FERNET = Fernet.generate_key().decode("utf-8")

SEED_START = datetime(2026, 10, 19, 18, 0, tzinfo=UTC)
SEED_END = datetime(2026, 10, 19, 19, 0, tzinfo=UTC)


@dataclass
class _Evt:
    transparency: str | None
    free_busy_provenance: str | None
    start_time: datetime | None
    end_time: datetime | None
    calendar_id: str = "cal-ms-1"
    title: str = "Outlook meeting"
    external_event_id: str = "ms-evt-1"
    provider_series_id: str | None = None
    owner_id: str = "owner-1"
    provider: str = "microsoft"
    source_zone_missing: bool = False
    free_busy_pending_exception: bool = False
    is_provider_cancelled: bool = False
    is_all_day: bool = False
    source_timezone: str | None = "UTC"


# --- Unit: locked mapping table (§1.2 / §1.5) ---------------------------------


@pytest.mark.parametrize(
    "show_as,stored,provenance,kind",
    [
        ("free", "transparent", "provider_explicit", "free"),
        ("busy", "opaque", "provider_explicit", "busy"),
        ("oof", "opaque", "provider_explicit", "busy"),
        ("unknown", None, "provider_explicit", "unknown"),
        ("tentative", "opaque", "provider_explicit", "busy"),
        ("workingElsewhere", "transparent", "provider_explicit", "free"),
        ("workingElsewhereFuture", None, "provider_explicit", "unknown"),
        ("tentativeBusy", None, "provider_explicit", "unknown"),
        ("", None, "provider_explicit", "unknown"),
        (None, None, "provider_explicit", "unknown"),
    ],
)
def test_resolve_microsoft_show_as_table(
    show_as: str | None,
    stored: str | None,
    provenance: str,
    kind: str,
) -> None:
    event = {"showAs": show_as}
    assert resolve_microsoft_show_as(event) == (stored, provenance, kind)


def test_resolve_microsoft_missing_on_complete_is_unknown_missing() -> None:
    stored, provenance, kind = resolve_microsoft_show_as({})
    assert stored is None
    assert provenance == "unknown_missing"
    assert kind == "unknown"


def test_resolve_microsoft_projection_and_incomplete() -> None:
    # Projected field sets always demote, even with an explicit showAs value.
    assert resolve_microsoft_show_as(
        {"showAs": "busy"}, field_projected=True
    ) == (None, "unknown_projection", "unknown")
    # Incomplete + explicit showAs still maps (incomplete-update handler).
    assert resolve_microsoft_show_as(
        {"showAs": "busy"}, complete_representation=False
    ) == ("opaque", "provider_explicit", "busy")
    assert resolve_microsoft_show_as(
        {"showAs": "free"}, complete_representation=False
    ) == ("transparent", "provider_explicit", "free")
    # Incomplete + omitted showAs → unknown_projection (not unknown_missing).
    assert resolve_microsoft_show_as(
        {}, complete_representation=False
    ) == (None, "unknown_projection", "unknown")
    # Projection wins even when showAs is absent.
    assert resolve_microsoft_show_as({}, field_projected=True)[1] == "unknown_projection"


def test_resolve_microsoft_differs_from_google_defaults() -> None:
    """Missing showAs must not become Google's omitted-busy default."""
    from app.scheduler.free_busy import resolve_google_transparency

    g_stored, g_prov, g_kind = resolve_google_transparency({})
    assert (g_stored, g_prov, g_kind) == ("opaque", "provider_default_omitted", "busy")
    m_stored, m_prov, m_kind = resolve_microsoft_show_as({})
    assert (m_stored, m_prov, m_kind) == (None, "unknown_missing", "unknown")


# --- complete_representation fetch-shape evidence (no live Graph) -------------


def test_event_list_params_omit_event_select() -> None:
    """calendarView / delta list builders must not pass event $select."""
    window = ms_cal.microsoft_event_list_window_params(
        time_min=SEED_START, time_max=SEED_END
    )
    with_top = ms_cal.microsoft_event_list_window_params(
        time_min=SEED_START, time_max=SEED_END, top="100"
    )
    assert ms_cal.microsoft_event_list_omits_event_select(window)
    assert ms_cal.microsoft_event_list_omits_event_select(with_top)
    assert ms_cal.microsoft_event_list_omits_event_select(None)
    assert ms_cal.MS_EVENT_LIST_SELECT_PARAM not in window
    assert ms_cal.MS_EVENT_LIST_SELECT_PARAM not in with_top
    assert set(window) == {"startDateTime", "endDateTime"}
    assert set(with_top) == {"startDateTime", "endDateTime", "$top"}


def test_fetch_context_from_list_params_select_projection() -> None:
    """``$select`` without showAs → projected; with showAs → established."""
    window = ms_cal.microsoft_event_list_window_params(
        time_min=SEED_START, time_max=SEED_END
    )
    assert (
        ms_cal.microsoft_event_fetch_context_from_list_params(window)
        == ms_cal.MS_EVENT_LIST_FETCH_CONTEXT
    )
    projected = ms_cal.microsoft_event_fetch_context_from_list_params(
        {**window, "$select": "id,subject,start,end"}
    )
    assert projected.show_as_field_projected is True
    assert projected.show_as_representation_established is False
    complete, field_projected = ms_cal.microsoft_show_as_resolver_flags(
        fetch_context=projected,
        times_ok=True,
    )
    assert complete is False and field_projected is True
    with_show = ms_cal.microsoft_event_fetch_context_from_list_params(
        {**window, "$select": "id,showAs,start,end"}
    )
    assert with_show.show_as_field_projected is False
    assert with_show.show_as_representation_established is True


def test_list_calendar_events_passes_no_event_select(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, str] | None] = []

    def _capture(access_token, url, *, params=None, **kwargs):
        captured.append(params)
        return [], None

    monkeypatch.setattr(ms_cal, "_graph_collect", _capture)
    ms_cal.list_calendar_events(
        "tok", "cal-1", time_min=SEED_START, time_max=SEED_END
    )
    ms_cal.list_calendar_view(
        "tok", "cal-1", time_min=SEED_START, time_max=SEED_END
    )
    ms_cal.list_calendar_events_incremental(
        "tok",
        "https://graph.microsoft.com/v1.0/me/calendars/cal-1/calendarView/delta?$deltatok=x",
    )
    assert len(captured) == 3
    assert all(ms_cal.microsoft_event_list_omits_event_select(p) for p in captured)
    assert captured[2] is None  # incremental delta-link follow
    assert ms_cal.microsoft_event_fetch_context_from_list_params(captured[0]) == (
        ms_cal.MS_EVENT_LIST_FETCH_CONTEXT
    )
    assert ms_cal.microsoft_event_fetch_context_from_list_params(captured[2]) == (
        ms_cal.MS_EVENT_FETCH_CONTEXT_UNCERTAIN
    )


def test_fetch_context_none_params_is_uncertain_not_established() -> None:
    assert ms_cal.microsoft_event_fetch_context_from_list_params(None) == (
        ms_cal.MS_EVENT_FETCH_CONTEXT_UNCERTAIN
    )


# --- Trust / merge for MS-labeled rows ----------------------------------------


def test_ms_unknown_in_horizon_blocks_trust() -> None:
    unknown = _Evt(None, "provider_explicit", HORIZON_START, HORIZON_END)
    missing = _Evt(None, "unknown_missing", HORIZON_START, HORIZON_END)
    projected = _Evt(None, "unknown_projection", HORIZON_START, HORIZON_END)
    for row in (unknown, missing, projected):
        trust = evaluate_busy_input_trust(
            [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
        )
        assert trust.ok is False
        assert events_for_busy_merge([row]) == []


def test_ms_free_excluded_busy_included_in_merge() -> None:
    free = _Evt("transparent", "provider_explicit", HORIZON_START, HORIZON_END)
    busy = _Evt("opaque", "provider_explicit", HORIZON_START, HORIZON_END)
    assert evaluate_busy_input_trust(
        [free, busy], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    ).ok is True
    merged = events_for_busy_merge([free, busy])
    assert merged == [busy]


def test_ms_working_elsewhere_and_tentative_effective_kinds() -> None:
    we = resolve_microsoft_show_as({"showAs": "workingElsewhere"})
    assert we[2] == "free"
    assert (
        effective_free_busy_kind(transparency=we[0], provenance=we[1]) == "free"
    )
    tent = resolve_microsoft_show_as({"showAs": "tentative"})
    assert tent[2] == "busy"
    assert (
        effective_free_busy_kind(transparency=tent[0], provenance=tent[1]) == "busy"
    )


# --- Complete-path upsert unit transitions (in-memory row shell) --------------


def _ms_row_shell(**overrides: object) -> SimpleNamespace:
    base = dict(
        pending_deletion=False,
        calendar_id="cal-ms-1",
        provider_series_id=None,
        calendar_account_id=None,
        title=None,
        start_time=SEED_START,
        end_time=SEED_END,
        is_all_day=False,
        last_synced_at=None,
        source_zone_missing=False,
        source_timezone="UTC",
        transparency=None,
        free_busy_provenance=None,
        free_busy_prior_transparency=None,
        free_busy_prior_provenance=None,
        free_busy_sync_run_id=None,
        free_busy_changed_at=None,
        free_busy_change_history=None,
        free_busy_pending_exception=False,
        is_provider_cancelled=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _timed_graph_event(*, show_as: str | None = "busy", omit_show_as: bool = False) -> dict:
    event: dict = {
        "id": "ms-evt-1",
        "subject": "Standup",
        "start": {"dateTime": "2026-10-19T18:00:00", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-19T19:00:00", "timeZone": "UTC"},
    }
    if not omit_show_as:
        event["showAs"] = show_as
    return event


def _partial_graph_event(*, show_as: str | None = None, omit_show_as: bool = False) -> dict:
    """Synthetic incomplete payload: id (+ optional showAs), no start/end."""
    event: dict = {"id": "ms-evt-1"}
    if not omit_show_as:
        event["showAs"] = show_as
    return event


def test_upsert_busy_to_free_and_free_to_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    subscription = SimpleNamespace(
        id=uuid4(), external_calendar_id="cal-ms-1", provider_timezone="UTC"
    )
    existing = _ms_row_shell(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )
    monkeypatch.setattr(ms_cal, "_find_external_event", lambda *a, **k: existing)

    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_timed_graph_event(show_as="free"),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-full-run-1",
        )
        is True
    )
    assert existing.transparency == "transparent"
    assert existing.free_busy_provenance == "provider_explicit"
    assert existing.free_busy_prior_transparency == "opaque"
    assert existing.free_busy_sync_run_id == "ms-full-run-1"
    assert len(existing.free_busy_change_history) == 1
    assert existing.free_busy_change_history[0]["to_transparency"] == "transparent"

    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_timed_graph_event(show_as="busy"),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-incr-run-2",
        )
        is True
    )
    assert existing.transparency == "opaque"
    assert existing.free_busy_prior_transparency == "transparent"
    assert existing.free_busy_sync_run_id == "ms-incr-run-2"
    assert len(existing.free_busy_change_history) == 2
    assert existing.free_busy_change_history[0]["sync_run_id"] == "ms-full-run-1"
    assert existing.free_busy_change_history[1]["sync_run_id"] == "ms-incr-run-2"


def test_upsert_explicit_unknown_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    subscription = SimpleNamespace(
        id=uuid4(), external_calendar_id="cal-ms-1", provider_timezone="UTC"
    )
    existing = _ms_row_shell(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )
    monkeypatch.setattr(ms_cal, "_find_external_event", lambda *a, **k: existing)

    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_timed_graph_event(show_as="unknown"),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-run-unknown",
        )
        is True
    )
    assert existing.transparency is None
    assert existing.free_busy_provenance == "provider_explicit"
    assert existing.free_busy_prior_transparency == "opaque"
    assert len(existing.free_busy_change_history) == 1

    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_timed_graph_event(omit_show_as=True),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-run-missing",
            event_fetch_context=ms_cal.MS_EVENT_LIST_FETCH_CONTEXT,
        )
        is True
    )
    assert existing.transparency is None
    assert existing.free_busy_provenance == "unknown_missing"
    assert existing.free_busy_prior_provenance == "provider_explicit"
    assert existing.free_busy_sync_run_id == "ms-run-missing"
    assert len(existing.free_busy_change_history) == 2


def test_upsert_complete_omit_goes_through_apply_not_silent_erase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Complete payload omitting showAs → unknown_missing; history retained."""
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    subscription = SimpleNamespace(
        id=uuid4(), external_calendar_id="cal-ms-1", provider_timezone="UTC"
    )
    existing = _ms_row_shell(
        transparency="opaque",
        free_busy_provenance="provider_explicit",
        free_busy_change_history=[
            {
                "at": "2026-10-19T12:00:00Z",
                "sync_run_id": "prior",
                "from_transparency": None,
                "from_provenance": None,
                "to_transparency": "opaque",
                "to_provenance": "provider_explicit",
            }
        ],
    )
    monkeypatch.setattr(ms_cal, "_find_external_event", lambda *a, **k: existing)

    calls: list[tuple] = []
    real_apply = apply_transparency_update

    def _watch(row, *, stored, provenance, sync_run_id):
        calls.append((stored, provenance, sync_run_id))
        return real_apply(
            row, stored=stored, provenance=provenance, sync_run_id=sync_run_id
        )

    monkeypatch.setattr(ms_cal, "apply_transparency_update", _watch)

    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_timed_graph_event(omit_show_as=True),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-incr-partial",
            event_fetch_context=ms_cal.MS_EVENT_LIST_FETCH_CONTEXT,
        )
        is True
    )
    assert calls == [(None, "unknown_missing", "ms-incr-partial")]
    assert existing.transparency is None
    assert existing.free_busy_provenance == "unknown_missing"
    assert len(existing.free_busy_change_history) == 2
    assert existing.free_busy_change_history[0]["sync_run_id"] == "prior"


def test_upsert_incomplete_without_existing_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    subscription = SimpleNamespace(
        id=uuid4(), external_calendar_id="cal-ms-1", provider_timezone="UTC"
    )
    monkeypatch.setattr(ms_cal, "_find_external_event", lambda *a, **k: None)
    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_partial_graph_event(show_as="busy"),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-no-row",
        )
        is False
    )


def test_upsert_unrecognized_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    subscription = SimpleNamespace(
        id=uuid4(), external_calendar_id="cal-ms-1", provider_timezone="UTC"
    )
    existing = _ms_row_shell(
        transparency="transparent",
        free_busy_provenance="provider_explicit",
    )
    monkeypatch.setattr(ms_cal, "_find_external_event", lambda *a, **k: existing)

    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_timed_graph_event(show_as="focusTime"),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-run-unrec",
        )
        is True
    )
    assert existing.transparency is None
    assert existing.free_busy_provenance == "provider_explicit"
    assert (
        effective_free_busy_kind(
            transparency=existing.transparency,
            provenance=existing.free_busy_provenance,
        )
        == "unknown"
    )


def test_upsert_without_fetch_context_omit_show_as_unknown_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No fetch evidence → explicit uncertainty (not unknown_missing)."""
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    subscription = SimpleNamespace(
        id=uuid4(), external_calendar_id="cal-ms-1", provider_timezone="UTC"
    )
    existing = _ms_row_shell(
        transparency="transparent",
        free_busy_provenance="provider_explicit",
    )
    monkeypatch.setattr(ms_cal, "_find_external_event", lambda *a, **k: existing)
    assert (
        ms_cal._upsert_external_event(
            MagicMock(),
            account=account,
            subscription=subscription,
            event=_timed_graph_event(omit_show_as=True),
            now=datetime.now(timezone.utc),
            sync_run_id="ms-no-context",
        )
        is True
    )
    assert existing.free_busy_provenance == "unknown_projection"


def test_apply_full_mints_ms_full_sync_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    sub_id = uuid4()
    subscription = SimpleNamespace(
        id=sub_id,
        external_calendar_id="cal-ms-1",
        provider_timezone="UTC",
        sync_cursor=None,
    )
    captured: list[str] = []

    def _capture(db, *, account, subscription, event, now, sync_run_id, **kwargs):
        captured.append(sync_run_id)
        return True

    monkeypatch.setattr(ms_cal, "_upsert_external_event", _capture)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    ms_cal._apply_subscription_full(
        db,
        account=account,
        subscription=subscription,
        events=[_timed_graph_event(show_as="busy")],
        next_delta_link=None,
        time_min=now,
        time_max=now,
        now=now,
    )
    assert len(captured) == 1
    assert captured[0].startswith("ms-full-20261020T120000Z-")
    assert sub_id.hex[:8] in captured[0]


def test_apply_incremental_mints_ms_incr_sync_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = uuid4()
    account = SimpleNamespace(id=uuid4(), owner_id=owner)
    sub_id = uuid4()
    subscription = SimpleNamespace(
        id=sub_id,
        external_calendar_id="cal-ms-1",
        provider_timezone="UTC",
        sync_cursor=None,
    )
    captured: list[str] = []

    def _capture(db, *, account, subscription, event, now, sync_run_id, **kwargs):
        captured.append(sync_run_id)
        return True

    monkeypatch.setattr(ms_cal, "_upsert_external_event", _capture)
    db = MagicMock()
    now = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)
    ms_cal._apply_subscription_incremental(
        db,
        account=account,
        subscription=subscription,
        events=[_timed_graph_event(show_as="free")],
        next_delta_link=None,
        now=now,
    )
    assert len(captured) == 1
    assert captured[0].startswith("ms-incr-20261020T123000Z-")
    assert sub_id.hex[:8] in captured[0]


# --- Disposable Postgres: real ExternalCalendarEvent persistence --------------


@pytest.fixture()
def disposable_db() -> None:
    """Guard household DSN; require theplan-t1a-postgres @ 127.0.0.1:5433."""
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert meta["host_ip"] == "127.0.0.1"
    assert meta["database"] == "theplan_t1a_test"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _settings() -> Settings:
    return Settings(
        token_encryption_key=_FERNET,
        microsoft_client_id="t1d-ms-client",
        microsoft_client_secret="t1d-ms-secret",
        microsoft_redirect_uri="http://127.0.0.1/unused-ms",
    )


def _seed_owner_account_sub(
    db: Session,
) -> tuple[User, CalendarAccount, CalendarSubscription]:
    token = uuid4().hex[:10]
    user = User(
        email=f"t1d-renee-{token}@example.test",
        username=f"t1d_{token}",
        display_name="T1D residual",
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
    cfg = _settings()
    account = CalendarAccount(
        owner_id=user.id,
        provider=CalendarProvider.microsoft,
        account_email=f"t1d-{uuid4().hex[:8]}@example.test",
        access_token_enc=encrypt_token(cfg, "access-token"),
        refresh_token_enc=encrypt_token(cfg, "refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=False,
        last_synced_at=None,
    )
    db.add(account)
    db.flush()
    sub = CalendarSubscription(
        owner_id=user.id,
        calendar_account_id=account.id,
        external_calendar_id="cal-ms-t1d",
        summary="T1D calendar",
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
        provider_timezone="UTC",
    )
    db.add(sub)
    db.flush()
    return user, account, sub


def _seed_external_event(
    db: Session,
    *,
    account: CalendarAccount,
    calendar_id: str,
    external_id: str,
    transparency: str | None,
    provenance: str,
    title: str = "Seeded free block",
    history: list[dict] | None = None,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=account.owner_id,
        calendar_account_id=account.id,
        provider=CalendarProvider.microsoft,
        external_event_id=external_id,
        calendar_id=calendar_id,
        title=title,
        start_time=SEED_START,
        end_time=SEED_END,
        is_all_day=False,
        source_zone_missing=False,
        source_timezone="UTC",
        transparency=transparency,
        free_busy_provenance=provenance,
        free_busy_change_history=history
        or [
            {
                "at": "2026-10-19T12:00:00Z",
                "sync_run_id": "seed-run",
                "from_transparency": None,
                "from_provenance": None,
                "to_transparency": transparency,
                "to_provenance": provenance,
            }
        ],
        free_busy_sync_run_id="seed-run",
        last_synced_at=datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
    )
    db.add(row)
    db.flush()
    return row


def test_db_partial_show_as_busy_flips_seeded_free(
    disposable_db: None, db_session: Session
) -> None:
    """Dex residual: {id, showAs: busy} must flip trusted free → busy on disk."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-partial-busy-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )
    prior_history_len = len(seeded.free_busy_change_history or [])
    prior_title = seeded.title
    prior_start = seeded.start_time
    prior_end = seeded.end_time
    prior_all_day = seeded.is_all_day
    prior_zone = seeded.source_timezone
    prior_zone_missing = seeded.source_zone_missing

    # Complete singleInstance identity — showAs-only residual, not incomplete gate.
    ok = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={"id": external_id, "type": "singleInstance", "showAs": "busy"},
        now=datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
        sync_run_id="ms-incr-partial-busy",
    )
    assert ok is True
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.transparency == "opaque"
    assert row.free_busy_provenance == "provider_explicit"
    assert row.free_busy_prior_transparency == "transparent"
    assert row.free_busy_sync_run_id == "ms-incr-partial-busy"
    assert row.start_time == prior_start
    assert row.end_time == prior_end
    assert row.is_all_day == prior_all_day
    assert row.source_timezone == prior_zone
    assert row.source_zone_missing == prior_zone_missing
    assert row.title == prior_title
    assert len(row.free_busy_change_history or []) == prior_history_len + 1
    assert row.free_busy_change_history[0]["sync_run_id"] == "seed-run"
    assert row.free_busy_change_history[-1]["to_transparency"] == "opaque"
    assert row.series_identity_state == "verified_non_recurring"
    assert (
        effective_free_busy_kind(
            transparency=row.transparency, provenance=row.free_busy_provenance
        )
        == "busy"
    )
    assert events_for_busy_merge([row]) == [row]

    # Deliberately incomplete omit-type payload: new blocker, not showAs merge.
    ok_inc = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={"id": external_id, "showAs": "free"},
        now=datetime(2026, 10, 20, 9, 1, tzinfo=UTC),
        sync_run_id="ms-incr-partial-incomplete",
    )
    assert ok_inc is True
    db_session.flush()
    db_session.expire(row)
    row_inc = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row_inc is not None
    assert row_inc.series_identity_state == "incomplete"
    assert events_for_busy_merge([row_inc]) == []
    trust_inc = evaluate_busy_input_trust(
        [row_inc], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust_inc.ok is False
    assert any(
        d.cause == "series_identity_incomplete" for d in trust_inc.blocking_diagnostics
    )


def test_db_partial_show_as_unknown_trust_posture(
    disposable_db: None, db_session: Session
) -> None:
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-partial-unk-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="opaque",
        provenance="provider_explicit",
    )

    ok = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={"id": external_id, "showAs": "unknown"},
        now=datetime(2026, 10, 20, 9, 5, tzinfo=UTC),
        sync_run_id="ms-incr-partial-unknown",
    )
    assert ok is True
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.transparency is None
    assert row.free_busy_provenance == "provider_explicit"
    assert row.start_time == SEED_START
    assert row.end_time == SEED_END
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert events_for_busy_merge([row]) == []


def test_db_apply_full_list_context_omit_show_as_unknown_missing(
    disposable_db: None,
    db_session: Session,
) -> None:
    """Apply path with default list fetch context → unknown_missing (not placement escape)."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-apply-miss-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="opaque",
        provenance="provider_explicit",
    )
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    ms_cal._apply_subscription_full(
        db_session,
        account=account,
        subscription=sub,
        events=[_timed_graph_event(omit_show_as=True) | {"id": external_id}],
        next_delta_link=None,
        time_min=SEED_START,
        time_max=SEED_END,
        now=now,
        event_fetch_context=ms_cal.MS_EVENT_LIST_FETCH_CONTEXT,
    )
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.free_busy_provenance == "unknown_missing"
    assert events_for_busy_merge([row]) == []
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False


def test_db_apply_full_projected_omit_show_as_unknown_projection(
    disposable_db: None,
    db_session: Session,
) -> None:
    """Parseable bounds + projected fetch → unknown_projection; blocks trusted free."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-apply-proj-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )
    projected = ms_cal.microsoft_event_fetch_context_from_list_params(
        {
            "startDateTime": "2026-10-19T18:00:00Z",
            "endDateTime": "2026-10-19T20:00:00Z",
            "$select": "id,subject,start,end",
        }
    )
    now = datetime(2026, 10, 20, 12, 5, tzinfo=UTC)
    ms_cal._apply_subscription_full(
        db_session,
        account=account,
        subscription=sub,
        events=[_timed_graph_event(omit_show_as=True) | {"id": external_id}],
        next_delta_link=None,
        time_min=SEED_START,
        time_max=SEED_END,
        now=now,
        event_fetch_context=projected,
    )
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.free_busy_provenance == "unknown_projection"
    assert row.free_busy_prior_transparency == "transparent"
    assert events_for_busy_merge([row]) == []
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False


def test_db_apply_incremental_preserves_projected_fetch_context(
    disposable_db: None,
    db_session: Session,
) -> None:
    """Delta continuation apply keeps session fetch qualification (no URL decode)."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-incr-proj-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )
    projected = ms_cal.MicrosoftEventFetchContext(
        show_as_field_projected=True,
        show_as_representation_established=False,
    )
    now = datetime(2026, 10, 20, 12, 10, tzinfo=UTC)
    ms_cal._apply_subscription_incremental(
        db_session,
        account=account,
        subscription=sub,
        events=[_timed_graph_event(omit_show_as=True) | {"id": external_id}],
        next_delta_link="https://graph.microsoft.com/v1.0/delta?$deltatoken=opaque",
        now=now,
        event_fetch_context=projected,
    )
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.free_busy_provenance == "unknown_projection"
    assert sub.sync_cursor == "https://graph.microsoft.com/v1.0/delta?$deltatoken=opaque"
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False


def _patch_ms_sync_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ms_cal, "get_valid_access_token", lambda *_a, **_k: "access-token"
    )


def _patch_ms_httpx(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    real_client = httpx.Client

    def _factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(ms_cal.httpx, "Client", _factory)


def _request_query_params(request: httpx.Request) -> dict[str, str]:
    return {key: value for key, value in request.url.params.multi_items()}


def _patch_ms_sync_fixed_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    fixed = datetime(2026, 10, 20, 14, 0, tzinfo=UTC)
    real_dt = ms_cal.datetime

    class _FixedNow(real_dt):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed.astimezone(tz)
            return fixed

    monkeypatch.setattr(ms_cal, "datetime", _FixedNow)
    return fixed


def test_db_sync_ms_view_http_collect_unprojected_omit_show_as_unknown_missing(
    disposable_db: None,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``sync_account_events`` via real ``list_calendar_view`` / ``_graph_collect`` (mock HTTP)."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-sync-miss-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )
    _patch_ms_sync_token(monkeypatch)
    _patch_ms_sync_fixed_now(monkeypatch)
    time_min = HORIZON_START - timedelta(hours=1)
    time_max = HORIZON_END + timedelta(hours=1)
    builder_snapshots: list[dict[str, str]] = []
    real_builder = ms_cal.microsoft_calendar_view_list_params

    def _tracking_builder(*, time_min: datetime, time_max: datetime) -> dict[str, str]:
        params = real_builder(time_min=time_min, time_max=time_max)
        builder_snapshots.append(dict(params))
        return params

    monkeypatch.setattr(ms_cal, "microsoft_calendar_view_list_params", _tracking_builder)
    requests_log: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_log.append(request)
        return httpx.Response(
            200,
            json={
                "value": [_timed_graph_event(omit_show_as=True) | {"id": external_id}],
            },
        )

    _patch_ms_httpx(monkeypatch, handler)
    count = ms_cal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    assert count == 1
    assert len(builder_snapshots) >= 2
    expected_params = builder_snapshots[0]
    assert all(snapshot == expected_params for snapshot in builder_snapshots)
    assert len(requests_log) == 1
    assert _request_query_params(requests_log[0]) == expected_params
    assert ms_cal.MS_EVENT_LIST_SELECT_PARAM not in expected_params
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.free_busy_provenance == "unknown_missing"
    assert row.free_busy_prior_transparency == "transparent"
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert events_for_busy_merge([row]) == []


def test_db_sync_ms_view_http_collect_projected_builder_params_sent_nextlink(
    disposable_db: None,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projected builder seam → same params on wire; nextLink drain; demotes trusted free."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-sync-proj-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )
    _patch_ms_sync_token(monkeypatch)
    _patch_ms_sync_fixed_now(monkeypatch)
    time_min = HORIZON_START - timedelta(hours=1)
    time_max = HORIZON_END + timedelta(hours=1)
    builder_snapshots: list[dict[str, str]] = []
    real_builder = ms_cal.microsoft_calendar_view_list_params
    projected_select = "id,subject,start,end"

    def _projected_builder(*, time_min: datetime, time_max: datetime) -> dict[str, str]:
        params = {
            **real_builder(time_min=time_min, time_max=time_max),
            ms_cal.MS_EVENT_LIST_SELECT_PARAM: projected_select,
        }
        builder_snapshots.append(dict(params))
        return params

    monkeypatch.setattr(ms_cal, "microsoft_calendar_view_list_params", _projected_builder)
    cal_id = sub.external_calendar_id
    next_link = (
        "https://graph.microsoft.com/v1.0/me/calendars/"
        f"{quote(cal_id, safe='')}/calendarView?$skiptoken=page-2"
    )
    payloads = [
        {
            "value": [_timed_graph_event(omit_show_as=True) | {"id": external_id}],
            "@odata.nextLink": next_link,
        },
        {"value": []},
    ]
    requests_log: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_log.append(request)
        return httpx.Response(200, json=payloads.pop(0))

    _patch_ms_httpx(monkeypatch, handler)
    count = ms_cal.sync_account_events(
        db_session,
        settings=_settings(),
        account=account,
        time_min=time_min,
        time_max=time_max,
    )
    assert count == 1
    assert len(builder_snapshots) >= 2
    expected_params = builder_snapshots[0]
    assert all(snapshot == expected_params for snapshot in builder_snapshots)
    assert expected_params[ms_cal.MS_EVENT_LIST_SELECT_PARAM] == projected_select
    assert (
        ms_cal.microsoft_event_fetch_context_from_list_params(expected_params).show_as_field_projected
        is True
    )
    assert len(requests_log) == 2
    assert _request_query_params(requests_log[0]) == expected_params
    second_q = _request_query_params(requests_log[1])
    assert str(requests_log[1].url).startswith(next_link.split("?", 1)[0])
    assert second_q.get("$skiptoken") == "page-2"
    assert "startDateTime" not in second_q
    assert "endDateTime" not in second_q
    assert ms_cal.MS_EVENT_LIST_SELECT_PARAM not in second_q
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.free_busy_provenance == "unknown_projection"
    assert row.free_busy_prior_transparency == "transparent"
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert events_for_busy_merge([row]) == []


def test_db_apply_incremental_without_fetch_context_omit_show_as_uncertain(
    disposable_db: None,
    db_session: Session,
) -> None:
    """Opaque delta continuation with no inherited session context stays uncertain."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-incr-nctx-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )
    now = datetime(2026, 10, 20, 12, 15, tzinfo=UTC)
    ms_cal._apply_subscription_incremental(
        db_session,
        account=account,
        subscription=sub,
        events=[_timed_graph_event(omit_show_as=True) | {"id": external_id}],
        next_delta_link="https://graph.microsoft.com/v1.0/delta?$deltatoken=opaque",
        now=now,
    )
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.free_busy_provenance == "unknown_projection"
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False
    assert events_for_busy_merge([row]) == []


def test_db_partial_omit_show_as_demotes_unknown_projection(
    disposable_db: None,
    db_session: Session,
) -> None:
    """Incomplete omit must not leave trusted free intact."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-partial-omit-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )

    ok = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={"id": external_id},
        now=datetime(2026, 10, 20, 9, 10, tzinfo=UTC),
        sync_run_id="ms-incr-partial-omit",
    )
    assert ok is True
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.transparency is None
    assert row.free_busy_provenance == "unknown_projection"
    assert row.free_busy_prior_transparency == "transparent"
    assert row.free_busy_prior_provenance == "provider_explicit"
    assert row.start_time == SEED_START
    assert row.end_time == SEED_END
    assert (
        effective_free_busy_kind(
            transparency=row.transparency, provenance=row.free_busy_provenance
        )
        == "unknown"
    )
    assert events_for_busy_merge([row]) == []


def test_db_transitions_free_busy_unknown_and_incomplete_omit(
    disposable_db: None,
    db_session: Session,
) -> None:
    """Persisted free↔busy, explicit unknown, then incomplete omit demotion."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-trans-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="opaque",
        provenance="provider_explicit",
        title="Transition subject",
    )

    # Complete free
    assert (
        ms_cal._upsert_external_event(
            db_session,
            account=account,
            subscription=sub,
            event=_timed_graph_event(show_as="free") | {"id": external_id},
            now=datetime(2026, 10, 20, 10, 0, tzinfo=UTC),
            sync_run_id="ms-full-free",
        )
        is True
    )
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert (row.transparency, row.free_busy_provenance) == (
        "transparent",
        "provider_explicit",
    )

    # Incomplete busy (Dex residual shape)
    assert (
        ms_cal._upsert_external_event(
            db_session,
            account=account,
            subscription=sub,
            event={"id": external_id, "showAs": "busy"},
            now=datetime(2026, 10, 20, 10, 1, tzinfo=UTC),
            sync_run_id="ms-incr-busy",
        )
        is True
    )
    db_session.flush()
    db_session.expire(row)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert (row.transparency, row.free_busy_provenance) == (
        "opaque",
        "provider_explicit",
    )
    assert row.start_time == SEED_START
    assert row.end_time == SEED_END

    # Incomplete explicit unknown
    assert (
        ms_cal._upsert_external_event(
            db_session,
            account=account,
            subscription=sub,
            event={"id": external_id, "showAs": "unknown"},
            now=datetime(2026, 10, 20, 10, 2, tzinfo=UTC),
            sync_run_id="ms-incr-unk",
        )
        is True
    )
    db_session.flush()
    db_session.expire(row)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert (row.transparency, row.free_busy_provenance) == (None, "provider_explicit")

    # Incomplete omit → unknown_projection
    assert (
        ms_cal._upsert_external_event(
            db_session,
            account=account,
            subscription=sub,
            event={"id": external_id},
            now=datetime(2026, 10, 20, 10, 3, tzinfo=UTC),
            sync_run_id="ms-incr-omit",
        )
        is True
    )
    db_session.flush()
    db_session.expire(row)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert (row.transparency, row.free_busy_provenance) == (None, "unknown_projection")
    assert len(row.free_busy_change_history or []) >= 4
    assert row.free_busy_change_history[0]["sync_run_id"] == "seed-run"
    assert row.free_busy_change_history[-1]["to_provenance"] == "unknown_projection"


def _invalid_range_graph_event(
    *,
    start_dt: str,
    end_dt: str,
    show_as: str = "busy",
    external_id: str,
) -> dict:
    """Graph-shaped payload with supplied start/end (may be invalid/reversed)."""
    return {
        "id": external_id,
        "showAs": show_as,
        "start": {"dateTime": start_dt, "timeZone": "UTC"},
        "end": {"dateTime": end_dt, "timeZone": "UTC"},
    }


def test_db_invalid_reversed_bounds_fail_closed_trust(
    disposable_db: None, db_session: Session
) -> None:
    """Dex residual: start=20:00/end=19:00 + showAs=busy must not keep trusted busy."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-inv-rev-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="opaque",
        provenance="provider_explicit",
        title="Prior busy block",
    )
    prior_start = seeded.start_time
    prior_end = seeded.end_time
    prior_history_len = len(seeded.free_busy_change_history or [])

    ok = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_invalid_range_graph_event(
            start_dt="2026-10-19T20:00:00",
            end_dt="2026-10-19T19:00:00",
            show_as="busy",
            external_id=external_id,
        ),
        now=datetime(2026, 10, 20, 11, 0, tzinfo=UTC),
        sync_run_id="ms-invalid-reversed",
    )
    assert ok is True
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    # Historical bounds retained as evidence — not rewritten to the invalid range.
    assert row.start_time == prior_start == SEED_START
    assert row.end_time == prior_end == SEED_END
    assert row.start_time != datetime(2026, 10, 19, 20, 0, tzinfo=UTC)
    # Fail closed on trust: showAs alone must not leave opaque/provider_explicit.
    assert row.transparency is None
    assert row.free_busy_provenance == "unknown_projection"
    assert row.free_busy_prior_transparency == "opaque"
    assert row.free_busy_prior_provenance == "provider_explicit"
    assert row.free_busy_sync_run_id == "ms-invalid-reversed"
    assert len(row.free_busy_change_history or []) == prior_history_len + 1
    assert (
        effective_free_busy_kind(
            transparency=row.transparency, provenance=row.free_busy_provenance
        )
        == "unknown"
    )
    assert events_for_busy_merge([row]) == []
    trust = evaluate_busy_input_trust(
        [row], horizon_start=HORIZON_START, horizon_end=HORIZON_END
    )
    assert trust.ok is False


def test_db_invalid_equal_bounds_fail_closed_trust(
    disposable_db: None, db_session: Session
) -> None:
    """Equal start/end is supplied-invalid, not omit-times."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-inv-eq-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="transparent",
        provenance="provider_explicit",
    )

    ok = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event=_invalid_range_graph_event(
            start_dt="2026-10-19T18:00:00",
            end_dt="2026-10-19T18:00:00",
            show_as="busy",
            external_id=external_id,
        ),
        now=datetime(2026, 10, 20, 11, 5, tzinfo=UTC),
        sync_run_id="ms-invalid-equal",
    )
    assert ok is True
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.start_time == SEED_START
    assert row.end_time == SEED_END
    assert row.transparency is None
    assert row.free_busy_provenance == "unknown_projection"
    assert events_for_busy_merge([row]) == []


def test_db_unresolvable_supplied_times_fail_closed_trust(
    disposable_db: None, db_session: Session
) -> None:
    """Time keys present but unparseable → fail closed; omit-times path untouched."""
    _user, account, sub = _seed_owner_account_sub(db_session)
    external_id = f"ms-inv-unres-{uuid4().hex[:8]}"
    seeded = _seed_external_event(
        db_session,
        account=account,
        calendar_id=sub.external_calendar_id,
        external_id=external_id,
        transparency="opaque",
        provenance="provider_explicit",
    )

    ok = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={
            "id": external_id,
            "type": "singleInstance",
            "showAs": "busy",
            "start": {"dateTime": "not-a-graph-datetime", "timeZone": "UTC"},
            "end": {"dateTime": "also-not-valid", "timeZone": "UTC"},
        },
        now=datetime(2026, 10, 20, 11, 10, tzinfo=UTC),
        sync_run_id="ms-invalid-unresolvable",
    )
    assert ok is True
    db_session.flush()
    db_session.expire(seeded)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.start_time == SEED_START
    assert row.end_time == SEED_END
    assert row.transparency is None
    assert row.free_busy_provenance == "unknown_projection"
    assert row.free_busy_prior_provenance == "provider_explicit"
    assert row.series_identity_state == "verified_non_recurring"
    assert events_for_busy_merge([row]) == []

    # Contrast: omit-times + complete singleInstance + explicit showAs still maps.
    ok_omit = ms_cal._upsert_external_event(
        db_session,
        account=account,
        subscription=sub,
        event={"id": external_id, "type": "singleInstance", "showAs": "busy"},
        now=datetime(2026, 10, 20, 11, 11, tzinfo=UTC),
        sync_run_id="ms-omit-after-invalid",
    )
    assert ok_omit is True
    db_session.flush()
    db_session.expire(row)
    row = db_session.get(ExternalCalendarEvent, seeded.id)
    assert row is not None
    assert row.transparency == "opaque"
    assert row.free_busy_provenance == "provider_explicit"
    assert row.start_time == SEED_START
    assert row.end_time == SEED_END
    assert row.series_identity_state == "verified_non_recurring"
    assert events_for_busy_merge([row]) == [row]
