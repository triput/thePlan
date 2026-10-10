"""Replan horizon wipe must cancel provider mirrors, not leave them as external busy."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.models import CalendarAccount, CalendarSubscription, ExternalCalendarEvent, ScheduledBlock, Task
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.scheduler.busy_map import BusyInterval, build_busy_map
from app.scheduler.horizon import wipe_unpinned_blocks_in_horizon
from app.services import google_calendar, microsoft_calendar

UTC = timezone.utc
# Far from synced local calendars so busy_map assertions are not polluted by the operator DB.
HORIZON_START = datetime(2099, 3, 2, 12, 0, tzinfo=UTC)
HORIZON_END = HORIZON_START + timedelta(days=7)


def _current_user_id(client: TestClient) -> uuid.UUID:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    return uuid.UUID(me.json()["id"])


def _account(db: Session, owner_id: uuid.UUID, provider: CalendarProvider) -> CalendarAccount:
    account = CalendarAccount(
        owner_id=owner_id,
        provider=provider,
        account_email=f"wipe-{provider.value}-{uuid.uuid4().hex[:8]}@example.test",
        access_token_enc="enc-access",
        refresh_token_enc="enc-refresh",
        token_expires_at=datetime.now(UTC) + timedelta(hours=2),
        is_enabled=True,
        mirror_blocks=True,
    )
    db.add(account)
    db.flush()
    return account


def _block(
    db: Session,
    *,
    owner_id: uuid.UUID,
    task_id: uuid.UUID,
    start: datetime,
    end: datetime,
    is_pinned: bool = False,
) -> ScheduledBlock:
    block = ScheduledBlock(
        owner_id=owner_id,
        task_id=task_id,
        start_time=start,
        end_time=end,
        is_pinned=is_pinned,
    )
    db.add(block)
    db.flush()
    return block


def _mirror(
    db: Session,
    *,
    owner_id: uuid.UUID,
    account: CalendarAccount,
    provider: CalendarProvider,
    block: ScheduledBlock | None,
    start: datetime,
    end: datetime,
    external_event_id: str,
) -> ExternalCalendarEvent:
    row = ExternalCalendarEvent(
        owner_id=owner_id,
        calendar_account_id=account.id,
        scheduled_block_id=block.id if block is not None else None,
        task_id=block.task_id if block is not None else None,
        provider=provider,
        external_event_id=external_event_id,
        calendar_id="primary" if provider == CalendarProvider.google else str(uuid.uuid4()),
        title="Mirrored block" if block is not None else "Real meeting",
        start_time=start,
        end_time=end,
        is_all_day=False,
        last_synced_at=HORIZON_START,
    )
    db.add(row)
    db.flush()
    return row


def _patch_remote_delete(
    monkeypatch: pytest.MonkeyPatch,
    *,
    google_error: Exception | None = None,
    microsoft_error: Exception | None = None,
) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def _token(db: Session, *, settings: object, account: CalendarAccount) -> str:
        return "access-token"

    def _delete_google(access_token: str, calendar_id: str, event_id: str) -> None:
        calls.append(("google", event_id))
        if google_error is not None:
            raise google_error

    def _delete_microsoft(access_token: str, calendar_id: str, event_id: str) -> None:
        calls.append(("microsoft", event_id))
        if microsoft_error is not None:
            raise microsoft_error

    monkeypatch.setattr(google_calendar, "get_valid_access_token", _token)
    monkeypatch.setattr(microsoft_calendar, "get_valid_access_token", _token)
    monkeypatch.setattr(google_calendar, "delete_google_event", _delete_google)
    monkeypatch.setattr(microsoft_calendar, "delete_microsoft_event", _delete_microsoft)
    return calls


def test_wipe_deletes_mirrored_events_and_keeps_external_busy(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_remote_delete(monkeypatch)
    owner_id = _current_user_id(client)
    task = Task(owner_id=owner_id, title="Wipe me")
    db_session.add(task)
    db_session.flush()

    google = _account(db_session, owner_id, CalendarProvider.google)
    microsoft = _account(db_session, owner_id, CalendarProvider.microsoft)

    mirror_start = datetime(2099, 3, 2, 13, 0, tzinfo=UTC)
    mirror_end = mirror_start + timedelta(hours=1)
    wiped = _block(
        db_session,
        owner_id=owner_id,
        task_id=task.id,
        start=mirror_start,
        end=mirror_end,
    )
    google_id = f"g-{uuid.uuid4()}"
    ms_id = f"ms-{uuid.uuid4()}"
    _mirror(
        db_session,
        owner_id=owner_id,
        account=google,
        provider=CalendarProvider.google,
        block=wiped,
        start=mirror_start,
        end=mirror_end,
        external_event_id=google_id,
    )
    _mirror(
        db_session,
        owner_id=owner_id,
        account=microsoft,
        provider=CalendarProvider.microsoft,
        block=wiped,
        start=mirror_start,
        end=mirror_end,
        external_event_id=ms_id,
    )

    pin_start = datetime(2099, 3, 2, 16, 0, tzinfo=UTC)
    pin_end = pin_start + timedelta(hours=1)
    pinned = _block(
        db_session,
        owner_id=owner_id,
        task_id=task.id,
        start=pin_start,
        end=pin_end,
        is_pinned=True,
    )
    pinned_event_id = f"g-pin-{uuid.uuid4()}"
    _mirror(
        db_session,
        owner_id=owner_id,
        account=google,
        provider=CalendarProvider.google,
        block=pinned,
        start=pin_start,
        end=pin_end,
        external_event_id=pinned_event_id,
    )

    outside_start = HORIZON_END + timedelta(hours=1)
    outside_end = outside_start + timedelta(hours=1)
    outside = _block(
        db_session,
        owner_id=owner_id,
        task_id=task.id,
        start=outside_start,
        end=outside_end,
    )
    outside_event_id = f"g-out-{uuid.uuid4()}"
    _mirror(
        db_session,
        owner_id=owner_id,
        account=google,
        provider=CalendarProvider.google,
        block=outside,
        start=outside_start,
        end=outside_end,
        external_event_id=outside_event_id,
    )

    external_start = datetime(2099, 3, 2, 18, 0, tzinfo=UTC)
    external_end = external_start + timedelta(hours=1)
    external_id = f"g-ext-{uuid.uuid4()}"
    _mirror(
        db_session,
        owner_id=owner_id,
        account=google,
        provider=CalendarProvider.google,
        block=None,
        start=external_start,
        end=external_end,
        external_event_id=external_id,
    )

    deleted = wipe_unpinned_blocks_in_horizon(
        db_session, owner_id, HORIZON_START, HORIZON_END
    )
    assert deleted == 1
    assert db_session.get(ScheduledBlock, wiped.id) is None
    assert db_session.get(ScheduledBlock, pinned.id) is not None
    assert db_session.get(ScheduledBlock, outside.id) is not None

    remaining_ids = {
        row.external_event_id
        for row in db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.owner_id == owner_id)
        .all()
    }
    assert google_id not in remaining_ids
    assert ms_id not in remaining_ids
    assert pinned_event_id in remaining_ids
    assert outside_event_id in remaining_ids
    assert external_id in remaining_ids

    assert ("google", google_id) in calls
    assert ("microsoft", ms_id) in calls
    assert ("google", pinned_event_id) not in calls
    assert ("google", outside_event_id) not in calls
    assert ("google", external_id) not in calls

    busy = build_busy_map(db_session, owner_id, HORIZON_START, HORIZON_END)
    assert busy == [
        BusyInterval(pin_start, pin_end, source="pinned"),
        BusyInterval(external_start, external_end, source="external"),
    ]


def test_wipe_tombstones_mirror_when_remote_delete_fails(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_remote_delete(
        monkeypatch,
        google_error=ApiError(502, "Google Calendar event delete failed", "GOOGLE_EVENT_DELETE"),
    )
    owner_id = _current_user_id(client)
    task = Task(owner_id=owner_id, title="Remote delete fails")
    db_session.add(task)
    db_session.flush()

    google = _account(db_session, owner_id, CalendarProvider.google)
    microsoft = _account(db_session, owner_id, CalendarProvider.microsoft)
    start = datetime(2099, 3, 2, 13, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    block = _block(db_session, owner_id=owner_id, task_id=task.id, start=start, end=end)
    google_id = f"g-fail-{uuid.uuid4()}"
    ms_id = f"ms-ok-{uuid.uuid4()}"
    _mirror(
        db_session,
        owner_id=owner_id,
        account=google,
        provider=CalendarProvider.google,
        block=block,
        start=start,
        end=end,
        external_event_id=google_id,
    )
    _mirror(
        db_session,
        owner_id=owner_id,
        account=microsoft,
        provider=CalendarProvider.microsoft,
        block=block,
        start=start,
        end=end,
        external_event_id=ms_id,
    )

    deleted = wipe_unpinned_blocks_in_horizon(
        db_session, owner_id, HORIZON_START, HORIZON_END
    )
    assert deleted == 1
    assert db_session.get(ScheduledBlock, block.id) is None
    tombstone = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == google_id)
        .one()
    )
    assert tombstone.pending_deletion is True
    assert tombstone.scheduled_block_id is None
    assert tombstone.calendar_id == "primary"
    assert tombstone.provider == CalendarProvider.google
    assert (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == ms_id)
        .count()
    ) == 0
    assert ("google", google_id) in calls
    assert ("microsoft", ms_id) in calls

    busy = build_busy_map(db_session, owner_id, HORIZON_START, HORIZON_END)
    assert busy == []


def _subscription(
    db: Session,
    *,
    owner_id: uuid.UUID,
    account: CalendarAccount,
    calendar_id: str,
) -> CalendarSubscription:
    row = CalendarSubscription(
        owner_id=owner_id,
        calendar_account_id=account.id,
        external_calendar_id=calendar_id,
        summary="Primary",
        role=CalendarSubscriptionRole.primary,
        is_enabled=True,
    )
    db.add(row)
    db.flush()
    return row


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@pytest.mark.parametrize(
    ("provider", "retry_succeeds"),
    [
        (CalendarProvider.google, False),
        (CalendarProvider.google, True),
        (CalendarProvider.microsoft, False),
        (CalendarProvider.microsoft, True),
    ],
)
def test_sync_retries_tombstone_and_does_not_reimport_as_busy(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    provider: CalendarProvider,
    retry_succeeds: bool,
) -> None:
    provider_error = ApiError(502, "delete failed", "EVENT_DELETE")
    _patch_remote_delete(
        monkeypatch,
        google_error=provider_error if provider == CalendarProvider.google else None,
        microsoft_error=provider_error if provider == CalendarProvider.microsoft else None,
    )
    owner_id = _current_user_id(client)
    task = Task(owner_id=owner_id, title="Tombstone sync")
    db_session.add(task)
    db_session.flush()

    account = _account(db_session, owner_id, provider)
    start = datetime(2099, 3, 2, 13, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    block = _block(db_session, owner_id=owner_id, task_id=task.id, start=start, end=end)
    external_id = f"{provider.value}-tomb-{uuid.uuid4()}"
    mirror = _mirror(
        db_session,
        owner_id=owner_id,
        account=account,
        provider=provider,
        block=block,
        start=start,
        end=end,
        external_event_id=external_id,
    )
    calendar_id = mirror.calendar_id
    _subscription(db_session, owner_id=owner_id, account=account, calendar_id=calendar_id)

    deleted = wipe_unpinned_blocks_in_horizon(
        db_session, owner_id, HORIZON_START, HORIZON_END
    )
    assert deleted == 1
    tombstone = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == external_id)
        .one()
    )
    assert tombstone.pending_deletion is True

    other_start = datetime(2099, 3, 2, 18, 0, tzinfo=UTC)
    other_end = other_start + timedelta(hours=1)
    other_id = f"{provider.value}-other-{uuid.uuid4()}"
    retry_calls: list[str] = []

    def _retry_delete(access_token: str, cal_id: str, event_id: str) -> None:
        retry_calls.append(event_id)
        if not retry_succeeds and event_id == external_id:
            raise provider_error

    if provider == CalendarProvider.google:
        pulled = [
            {
                "id": external_id,
                "status": "confirmed",
                "summary": "Mirrored block",
                "start": {"dateTime": _iso_z(start)},
                "end": {"dateTime": _iso_z(end)},
            },
            {
                "id": other_id,
                "status": "confirmed",
                "summary": "Dentist",
                "start": {"dateTime": _iso_z(other_start)},
                "end": {"dateTime": _iso_z(other_end)},
            },
        ]
        monkeypatch.setattr(
            google_calendar,
            "list_calendar_events",
            lambda access, cal, *, time_min, time_max: (pulled, "cursor"),
        )
        monkeypatch.setattr(google_calendar, "delete_google_event", _retry_delete)
        upserted = google_calendar.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=HORIZON_START,
            time_max=HORIZON_END,
        )
    else:
        pulled = [
            {
                "id": external_id,
                "subject": "Mirrored block",
                "start": {"dateTime": "2099-03-02T13:00:00", "timeZone": "UTC"},
                "end": {"dateTime": "2099-03-02T14:00:00", "timeZone": "UTC"},
            },
            {
                "id": other_id,
                "subject": "Dentist",
                "start": {"dateTime": "2099-03-02T18:00:00", "timeZone": "UTC"},
                "end": {"dateTime": "2099-03-02T19:00:00", "timeZone": "UTC"},
            },
        ]
        monkeypatch.setattr(
            microsoft_calendar,
            "list_calendar_events",
            lambda access, cal, *, time_min, time_max: (pulled, "cursor"),
        )
        monkeypatch.setattr(microsoft_calendar, "delete_microsoft_event", _retry_delete)
        upserted = microsoft_calendar.sync_account_events(
            db_session,
            settings=get_settings(),
            account=account,
            time_min=HORIZON_START,
            time_max=HORIZON_END,
        )

    db_session.flush()
    assert external_id in retry_calls
    assert upserted == 1
    rows = {
        row.external_event_id: row
        for row in db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.calendar_account_id == account.id)
        .all()
    }
    dentist = rows[other_id]
    assert dentist.pending_deletion is False
    assert dentist.title == "Dentist"
    if retry_succeeds:
        assert external_id not in rows
    else:
        kept = rows[external_id]
        assert kept.pending_deletion is True
        assert kept.scheduled_block_id is None
        assert kept.id == tombstone.id

    busy = build_busy_map(db_session, owner_id, HORIZON_START, HORIZON_END)
    assert busy == [BusyInterval(other_start, other_end, source="external")]


def test_block_delete_failure_keeps_tombstone_out_of_busy(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_remote_delete(
        monkeypatch,
        google_error=ApiError(502, "Google Calendar event delete failed", "GOOGLE_EVENT_DELETE"),
    )
    owner_id = _current_user_id(client)
    task = Task(owner_id=owner_id, title="Block delete tombstone")
    db_session.add(task)
    db_session.flush()
    account = _account(db_session, owner_id, CalendarProvider.google)
    start = datetime(2099, 3, 3, 13, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    block = _block(db_session, owner_id=owner_id, task_id=task.id, start=start, end=end)
    external_id = f"g-block-{uuid.uuid4()}"
    _mirror(
        db_session,
        owner_id=owner_id,
        account=account,
        provider=CalendarProvider.google,
        block=block,
        start=start,
        end=end,
        external_event_id=external_id,
    )

    deleted = client.delete(f"/api/v1/scheduled-blocks/{block.id}")
    assert deleted.status_code == 204, deleted.text
    db_session.expire_all()
    assert db_session.get(ScheduledBlock, block.id) is None
    tombstone = (
        db_session.query(ExternalCalendarEvent)
        .filter(ExternalCalendarEvent.external_event_id == external_id)
        .one()
    )
    assert tombstone.pending_deletion is True
    assert tombstone.scheduled_block_id is None
    busy = build_busy_map(db_session, owner_id, start - timedelta(hours=1), end + timedelta(hours=1))
    assert busy == []
