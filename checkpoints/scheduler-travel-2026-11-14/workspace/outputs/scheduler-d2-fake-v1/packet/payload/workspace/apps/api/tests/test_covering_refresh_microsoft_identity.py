"""Microsoft covering identity regressions on a disposable PostgreSQL database."""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.db import engine
from app.models import ExternalCalendarEvent
from app.models.enums import CalendarProvider
from app.services import covering_refresh_import as covering
from app.services import microsoft_calendar as microsoft
from app.services.covering_refresh_locks import covering_unit_locks
from support.t1a_pg import assert_disposable_database_url
from test_covering_refresh_d2 import NOW, _account, _owner, _seed_legacy_event, _settings, _sub, _window


COLLISION = "CALENDAR_EVENT_IDENTITY_COLLISION"


@pytest.fixture(scope="module", autouse=True)
def _disposable_database_required() -> None:
    if os.environ.get("T1A_REQUIRE_DISPOSABLE_DSN") != "1":
        raise pytest.UsageError("Microsoft collision fixture requires the disposable DSN guard")
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _columns(row: object) -> dict[str, object]:
    return {
        column.key: deepcopy(getattr(row, column.key))
        for column in inspect(type(row)).column_attrs
    }


def _run_case(db: Session, monkeypatch: pytest.MonkeyPatch, *, foreign: bool, pending: bool):
    owner, _ = _owner(db)
    account = _account(db, owner, provider=CalendarProvider.microsoft)
    selected = _sub(db, account, calendar_id="ms-covering-target", summary="Target")
    sibling = _sub(db, account, calendar_id="ms-covering-sibling", summary="Sibling")
    event_id = f"ms-covering-{uuid4().hex}"
    window_start, window_end = _window()
    event_start = NOW + timedelta(hours=2)
    event_end = event_start + timedelta(hours=1)
    _seed_legacy_event(
        db,
        owner=owner,
        account=account,
        calendar_id=sibling.external_calendar_id if foreign else selected.external_calendar_id,
        external_id=event_id,
        start=event_start,
        end=event_end,
        pending=pending,
    )
    row = db.query(ExternalCalendarEvent).filter_by(
        provider=CalendarProvider.microsoft, external_event_id=event_id
    ).one()
    row.transparency = "opaque"
    row.free_busy_provenance = "provider_explicit"
    db.flush()
    before_event = _columns(row)
    before_subscription = _columns(selected)

    payload = {
        "id": event_id,
        "subject": "Synthetic covering update",
        "type": "singleInstance",
        "showAs": "busy",
        "start": {"dateTime": event_start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": event_end.isoformat(), "timeZone": "UTC"},
    }
    reads = []
    unexpected = []

    def list_view(access, calendar_id, *, time_min, time_max):
        reads.append((calendar_id, time_min, time_max))
        assert access == "synthetic-access"
        return [payload], 1, True

    def reject_provider_call(*_args, **_kwargs):
        unexpected.append("unexpected provider call")
        raise AssertionError("UNEXPECTED_MICROSOFT_FIXTURE_PROVIDER_CALL")

    monkeypatch.setattr(microsoft, "list_calendar_view", list_view)
    monkeypatch.setattr(microsoft, "delete_microsoft_event", reject_provider_call)
    monkeypatch.setattr(microsoft.httpx, "Client", reject_provider_call)

    attempt = db.begin_nested()
    try:
        with covering_unit_locks(
            db, owner_id=owner.id, account_id=account.id, subscription_id=selected.id
        ) as lock_receipt:
            result = covering.import_covering_subscription_cache(
                db,
                settings=_settings(),
                account=account,
                subscription=selected,
                access_token="synthetic-access",
                window_start=window_start,
                window_end=window_end,
                lock_receipt=lock_receipt,
                now=NOW,
            )
            db.refresh(row)
            db.refresh(selected)
            after_event = _columns(row)
            after_subscription = _columns(selected)
    finally:
        attempt.rollback()

    assert reads == [("ms-covering-target", window_start, window_end)]
    assert unexpected == []
    db.refresh(row)
    db.refresh(selected)
    assert _columns(row) == before_event
    assert _columns(selected) == before_subscription
    return result, before_event, after_event, before_subscription, after_subscription


@pytest.mark.parametrize("pending", [False, True], ids=["live", "pending-deletion"])
def test_microsoft_covering_rejects_sibling_calendar_identity(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, pending: bool
) -> None:
    result, before, after, prior_subscription, after_subscription = _run_case(
        db_session, monkeypatch, foreign=True, pending=pending
    )
    assert (result.outcome, result.cause) == (covering.OUTCOME_FAILED, COLLISION), (
        "MICROSOFT_COVERING_COLLISION_BASELINE "
        f"outcome={result.outcome} cause={result.cause} pending={pending} "
        f"event_moved={after['calendar_id'] != before['calendar_id']} "
        f"coverage_minted={after_subscription['coverage_success_generation'] is not None}"
    )
    assert result.rollback_required
    assert not result.commit_unit
    assert result.needs_failure_unit
    assert result.coverage_generation_minted is None
    assert after == before
    assert after_subscription["coverage_success_generation"] == prior_subscription["coverage_success_generation"]


def test_microsoft_covering_updates_same_calendar(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, before, after, _, subscription = _run_case(
        db_session, monkeypatch, foreign=False, pending=False
    )
    assert result.outcome == covering.OUTCOME_OK
    assert result.upserted == 1
    assert result.commit_unit
    assert not result.rollback_required
    assert not result.needs_failure_unit
    for key in ("id", "provider", "owner_id", "calendar_account_id", "calendar_id", "external_event_id"):
        assert after[key] == before[key]
    assert after["title"] == "Synthetic covering update"
    assert subscription["coverage_mode"] == "ms_view"
    assert subscription["coverage_success_generation"] == result.coverage_generation_minted
