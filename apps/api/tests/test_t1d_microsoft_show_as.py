"""Track 1 T1-D: Microsoft Graph showAs → BusyInputTrust mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.scheduler.free_busy import (
    apply_transparency_update,
    effective_free_busy_kind,
    evaluate_busy_input_trust,
    events_for_busy_merge,
    resolve_microsoft_show_as,
)
from app.services import microsoft_calendar as ms_cal


HORIZON_START = datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc)
HORIZON_END = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)


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
    assert resolve_microsoft_show_as(
        {"showAs": "busy"}, field_projected=True
    ) == (None, "unknown_projection", "unknown")
    assert resolve_microsoft_show_as(
        {"showAs": "busy"}, complete_representation=False
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


# --- Upsert transitions through real _upsert_external_event -------------------


def _ms_row_shell(**overrides: object) -> SimpleNamespace:
    base = dict(
        pending_deletion=False,
        calendar_id="cal-ms-1",
        provider_series_id=None,
        calendar_account_id=None,
        title=None,
        start_time=None,
        end_time=None,
        is_all_day=False,
        last_synced_at=None,
        source_zone_missing=False,
        source_timezone=None,
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
        )
        is True
    )
    assert existing.transparency is None
    assert existing.free_busy_provenance == "unknown_missing"
    assert existing.free_busy_prior_provenance == "provider_explicit"
    assert existing.free_busy_sync_run_id == "ms-run-missing"
    assert len(existing.free_busy_change_history) == 2


def test_upsert_partial_omit_goes_through_apply_not_silent_erase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delta omit must call apply_transparency_update (history retained)."""
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
        )
        is True
    )
    assert calls == [(None, "unknown_missing", "ms-incr-partial")]
    assert existing.transparency is None
    assert existing.free_busy_provenance == "unknown_missing"
    assert len(existing.free_busy_change_history) == 2
    assert existing.free_busy_change_history[0]["sync_run_id"] == "prior"


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

    def _capture(db, *, account, subscription, event, now, sync_run_id):
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

    def _capture(db, *, account, subscription, event, now, sync_run_id):
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
