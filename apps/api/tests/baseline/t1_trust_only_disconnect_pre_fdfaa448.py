"""BASELINE-PRE-CHANGE @ fdfaa448^ (8c83c03) — literal disconnect route only.

Run only from an isolated worktree checked out at parent SHA, not from post-change tip.
Copied/synced into the worktree by tests/support/t1_disconnect_baseline_worktree.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRole,
    ExternalCalendarEvent,
)
from app.models.enums import CalendarProvider
from support.t1a_pg import assert_disposable_database_url, assert_t1a_container_isolated

from test_f6_w2_preview_apply import (
    _owner_id,
    _patch_schedule_clock,
    _prepare_settings,
    _revision,
    _uid,
)

UTC = timezone.utc
BASELINE_PARENT_SHA = "8c83c03aec2f92b92ac1251ff66d20ca1efd43f4"


@pytest.fixture(autouse=True)
def _disposable_db_only() -> None:
    if os.environ.get("T1A_REQUIRE_DISPOSABLE_DSN") != "1":
        pytest.skip("Baseline disconnect requires T1A_REQUIRE_DISPOSABLE_DSN=1")
    meta = assert_t1a_container_isolated()
    assert meta["host_port"] == "5433"
    assert_disposable_database_url(engine.url.render_as_string(hide_password=False))


def _wall_now() -> datetime:
    return datetime.now(UTC)


def _in_horizon_window() -> tuple[datetime, datetime]:
    start = _wall_now() + timedelta(hours=2)
    return start, start + timedelta(hours=1)


def _calendar_account(
    db: Session, owner_id: uuid.UUID, *, provider: CalendarProvider = CalendarProvider.microsoft
) -> tuple[CalendarAccount, str]:
    calendar_id = f"cal-disc-{_uid()}"
    account = CalendarAccount(
        owner_id=owner_id,
        provider=provider,
        account_email=f"disc-{_uid()}@contoso.test",
        is_enabled=True,
        mirror_blocks=False,
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
        )
    )
    db.flush()
    return account, calendar_id


def _add_external_event(
    db: Session,
    *,
    owner_id: uuid.UUID,
    account: CalendarAccount,
    calendar_id: str,
    start_time: datetime,
    end_time: datetime,
    transparency: str | None,
    free_busy_provenance: str | None,
) -> None:
    db.add(
        ExternalCalendarEvent(
            owner_id=owner_id,
            calendar_account_id=account.id,
            provider=account.provider,
            external_event_id=f"evt-{_uid()}",
            calendar_id=calendar_id,
            title="Fixture",
            start_time=start_time,
            end_time=end_time,
            transparency=transparency,
            free_busy_provenance=free_busy_provenance,
            series_identity_state="verified_non_recurring",
        )
    )
    db.flush()


def test_baseline_pre_change_e1_disconnect_bumps_revision(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same fixture as post-change E1; pre-fdfaa448 count-gate disconnect → +1 revision."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    start, end = _in_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=start,
        end_time=end,
        transparency=None,
        free_busy_provenance="unknown_projection",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1


def test_baseline_pre_change_e2_disconnect_bumps_revision(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same fixture as post-change E2; pre-fdfaa448 count-gate disconnect → +1 revision."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    rev_before = _revision(db_session, owner_id)

    account, calendar_id = _calendar_account(db_session, owner_id)
    start, end = _in_horizon_window()
    _add_external_event(
        db_session,
        owner_id=owner_id,
        account=account,
        calendar_id=calendar_id,
        start_time=start,
        end_time=end,
        transparency="opaque",
        free_busy_provenance="provider_explicit",
    )
    db_session.commit()

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1
