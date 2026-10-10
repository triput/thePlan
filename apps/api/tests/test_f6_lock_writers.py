"""Dex P1 leftovers: scheduling writers hold the owner lock through commit."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Query, Session

from app.api.routes import calendar as calendar_routes
from app.config import get_settings
from app.models import CalendarAccount, CalendarSubscription, ExternalCalendarEvent, UserSettings
from app.models.enums import CalendarProvider, CalendarSubscriptionRole
from app.services import assist_apply
from app.services import google_calendar as gcal
from app.services import microsoft_calendar as ms_cal
from app.services.scheduling_revision import lock_owner_scheduling

UTC = timezone.utc


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _revision(db: Session, owner_id: uuid.UUID) -> int:
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    db.refresh(settings)
    return int(settings.scheduling_revision)


def test_delete_project_cascade_bumps_scheduling_revision(
    client: TestClient, db_session: Session
) -> None:
    owner_id = _owner_id(client)
    project = client.post("/api/v1/projects", json={"title": f"del-{_uid()}"}).json()
    task = client.post(
        "/api/v1/tasks",
        json={"title": f"gone-{_uid()}", "project_id": project["id"]},
    ).json()
    before = _revision(db_session, owner_id)

    deleted = client.delete(f"/api/v1/projects/{project['id']}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == before + 1
    db_session.expire_all()
    leftover = client.get(f"/api/v1/tasks/{task['id']}")
    assert leftover.status_code == 200, leftover.text
    assert leftover.json()["project_id"] is None


def test_delete_epic_bumps_and_orphans_projects(
    client: TestClient, db_session: Session
) -> None:
    owner_id = _owner_id(client)
    epic = client.post("/api/v1/epics", json={"title": f"epic-{_uid()}"}).json()
    project = client.post(
        "/api/v1/projects",
        json={"title": f"child-{_uid()}", "epic_id": epic["id"]},
    ).json()
    before = _revision(db_session, owner_id)

    deleted = client.delete(f"/api/v1/epics/{epic['id']}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == before + 1
    orphan = client.get(f"/api/v1/projects/{project['id']}")
    assert orphan.status_code == 200
    assert orphan.json()["epic_id"] is None


def test_promote_project_and_demote_epic_bump_scheduling_revision(
    client: TestClient, db_session: Session
) -> None:
    owner_id = _owner_id(client)
    project = client.post("/api/v1/projects", json={"title": f"promo-{_uid()}"}).json()
    before_promote = _revision(db_session, owner_id)
    promoted = client.post(f"/api/v1/projects/{project['id']}/promote-to-epic")
    assert promoted.status_code == 200, promoted.text
    assert _revision(db_session, owner_id) == before_promote + 1

    epic = client.post("/api/v1/epics", json={"title": f"demo-{_uid()}"}).json()
    client.post(
        "/api/v1/projects",
        json={"title": f"kid-{_uid()}", "epic_id": epic["id"]},
    )
    before_demote = _revision(db_session, owner_id)
    demoted = client.post(f"/api/v1/epics/{epic['id']}/demote-to-project", json={})
    assert demoted.status_code == 200, demoted.text
    assert _revision(db_session, owner_id) == before_demote + 1


def test_promote_task_to_project_bumps_scheduling_revision(
    client: TestClient, db_session: Session
) -> None:
    owner_id = _owner_id(client)
    task = client.post("/api/v1/tasks", json={"title": f"lift-{_uid()}"}).json()
    before = _revision(db_session, owner_id)
    promoted = client.post(f"/api/v1/tasks/{task['id']}/promote-to-project", json={})
    assert promoted.status_code == 200, promoted.text
    assert _revision(db_session, owner_id) == before + 1
    assert promoted.json()["task"]["project_id"] == promoted.json()["project"]["id"]


def test_outline_task_apply_bumps_epic_only_does_not(
    client: TestClient, db_session: Session
) -> None:
    owner_id = _owner_id(client)
    project = client.post("/api/v1/projects", json={"title": f"outline-{_uid()}"}).json()
    before_epic = _revision(db_session, owner_id)
    epic_only = client.post(
        "/api/v1/outlines/apply",
        json={
            "actions": [
                {"type": "create_epic", "key": "e1", "title": f"Epic-{_uid()}"},
            ]
        },
    )
    assert epic_only.status_code == 200, epic_only.text
    assert epic_only.json()["results"][0]["ok"] is True
    assert _revision(db_session, owner_id) == before_epic

    before_task = _revision(db_session, owner_id)
    applied = client.post(
        "/api/v1/outlines/apply",
        json={
            "actions": [
                {
                    "type": "create_task",
                    "key": "t1",
                    "title": f"Task-{_uid()}",
                    "project_id": project["id"],
                    "estimated_duration_minutes": 25,
                }
            ]
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["results"][0]["ok"] is True
    assert _revision(db_session, owner_id) == before_task + 1


def _seed_subscription(
    db: Session,
    *,
    owner_id: uuid.UUID,
    provider: CalendarProvider,
) -> CalendarAccount:
    account = CalendarAccount(
        owner_id=owner_id,
        provider=provider,
        account_email=f"busy-{_uid()}@example.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db.add(account)
    db.flush()
    db.add(
        CalendarSubscription(
            owner_id=owner_id,
            calendar_account_id=account.id,
            external_calendar_id=f"cal-{_uid()}",
            summary="Calendar",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
        )
    )
    db.flush()
    return account


def test_google_and_microsoft_busy_sync_lock_before_mutation(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = _owner_id(client)
    window_start = datetime(2026, 10, 8, tzinfo=UTC)
    window_end = datetime(2026, 10, 16, tzinfo=UTC)

    google_account = _seed_subscription(
        db_session, owner_id=owner_id, provider=CalendarProvider.google
    )
    microsoft_account = _seed_subscription(
        db_session, owner_id=owner_id, provider=CalendarProvider.microsoft
    )

    google_order: list[str] = []
    microsoft_order: list[str] = []
    phase = {"name": "google"}

    def google_list(access: str, calendar: str, *, time_min: datetime, time_max: datetime):
        google_order.append("fetch")
        return (
            [
                {
                    "id": f"g-{_uid()}",
                    "summary": "Dentist",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-10-09T18:00:00Z"},
                    "end": {"dateTime": "2026-10-09T19:00:00Z"},
                }
            ],
            "g-cursor",
        )

    def microsoft_list(access: str, calendar: str, *, time_min: datetime, time_max: datetime):
        microsoft_order.append("fetch")
        return (
            [
                {
                    "id": f"m-{_uid()}",
                    "subject": "Dentist",
                    "start": {"dateTime": "2026-10-09T18:00:00", "timeZone": "UTC"},
                    "end": {"dateTime": "2026-10-09T19:00:00", "timeZone": "UTC"},
                }
            ],
            "m-cursor",
        )

    real_lock = lock_owner_scheduling

    def watched_lock(db: Session, lock_owner: uuid.UUID):
        if phase["name"] == "google":
            google_order.append("lock")
        else:
            microsoft_order.append("lock")
        return real_lock(db, lock_owner)

    real_google_upsert = gcal._upsert_external_event
    real_microsoft_upsert = ms_cal._upsert_external_event

    def google_upsert(*args, **kwargs):
        google_order.append("upsert")
        return real_google_upsert(*args, **kwargs)

    def microsoft_upsert(*args, **kwargs):
        microsoft_order.append("upsert")
        return real_microsoft_upsert(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.scheduling_revision.lock_owner_scheduling", watched_lock
    )
    monkeypatch.setattr(gcal, "get_valid_access_token", lambda db, *, settings, account: "tok")
    monkeypatch.setattr(gcal, "list_calendar_events", google_list)
    monkeypatch.setattr(gcal, "_upsert_external_event", google_upsert)
    monkeypatch.setattr(ms_cal, "get_valid_access_token", lambda db, *, settings, account: "tok")
    monkeypatch.setattr(ms_cal, "list_calendar_events", microsoft_list)
    monkeypatch.setattr(ms_cal, "_upsert_external_event", microsoft_upsert)

    gcal.sync_account_events(
        db_session,
        settings=get_settings(),
        account=google_account,
        time_min=window_start,
        time_max=window_end,
    )
    phase["name"] = "microsoft"
    ms_cal.sync_account_events(
        db_session,
        settings=get_settings(),
        account=microsoft_account,
        time_min=window_start,
        time_max=window_end,
    )

    assert google_order == ["fetch", "lock", "upsert"]
    assert microsoft_order == ["fetch", "lock", "upsert"]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def test_delete_block_commits_mirror_and_local_together(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.orm import Session as OrmSession

    commits = {"n": 0}
    real_commit = OrmSession.commit

    def counting_commit(self: OrmSession) -> None:
        commits["n"] += 1
        real_commit(self)

    monkeypatch.setattr(OrmSession, "commit", counting_commit)
    monkeypatch.setattr(
        "app.api.routes.scheduled_blocks.push_scheduled_block",
        lambda *args, **kwargs: None,
    )

    seen = {"during_mirror": None}

    def mirror(db: Session, settings: object, block: object) -> None:
        seen["during_mirror"] = commits["n"]

    monkeypatch.setattr("app.api.routes.scheduled_blocks.delete_mirrored_block", mirror)

    task = client.post("/api/v1/tasks", json={"title": f"block-{_uid()}"}).json()
    start = datetime(2026, 10, 10, 15, 0, tzinfo=UTC)
    created = client.post(
        "/api/v1/scheduled-blocks",
        json={
            "task_id": task["id"],
            "start_time": _iso(start),
            "end_time": _iso(start + timedelta(hours=1)),
        },
    )
    assert created.status_code == 201, created.text
    baseline = commits["n"]

    deleted = client.delete(f"/api/v1/scheduled-blocks/{created.json()['id']}")
    assert deleted.status_code == 204, deleted.text
    assert seen["during_mirror"] == baseline
    assert commits["n"] == baseline + 1
    assert client.get(f"/api/v1/scheduled-blocks/{created.json()['id']}").status_code == 404


def test_assist_task_apply_locks_before_create_and_bumps_once(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = _owner_id(client)
    before = _revision(db_session, owner_id)
    order: list[str] = []
    real_lock = assist_apply.lock_owner_scheduling
    real_create = assist_apply._apply_create_task

    def watched_lock(db: Session, lock_owner: uuid.UUID):
        order.append("lock")
        return real_lock(db, lock_owner)

    def watched_create(*args, **kwargs):
        order.append("create")
        return real_create(*args, **kwargs)

    monkeypatch.setattr(assist_apply, "lock_owner_scheduling", watched_lock)
    monkeypatch.setattr(assist_apply, "_apply_create_task", watched_create)

    applied = client.post(
        "/api/v1/assist/apply",
        json={
            "actions": [
                {"type": "create_task", "title": f"one-{_uid()}", "estimated_duration_minutes": 25},
                {"type": "create_task", "title": f"two-{_uid()}"},
            ]
        },
    )
    assert applied.status_code == 200, applied.text
    assert [item["ok"] for item in applied.json()["results"]] == [True, True]
    assert order == ["lock", "create", "create"]
    assert _revision(db_session, owner_id) == before + 1


def test_assist_project_only_and_failed_task_do_not_bump(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = _owner_id(client)
    before = _revision(db_session, owner_id)
    locks: list[str] = []
    real_lock = assist_apply.lock_owner_scheduling

    def watched_lock(db: Session, lock_owner: uuid.UUID):
        locks.append("lock")
        return real_lock(db, lock_owner)

    monkeypatch.setattr(assist_apply, "lock_owner_scheduling", watched_lock)

    project_only = client.post(
        "/api/v1/assist/apply",
        json={"actions": [{"type": "create_project", "title": f"proj-{_uid()}"}]},
    )
    assert project_only.status_code == 200, project_only.text
    assert project_only.json()["results"][0]["ok"] is True
    assert locks == []
    assert _revision(db_session, owner_id) == before

    failed = client.post(
        "/api/v1/assist/apply",
        json={"actions": [{"type": "create_task", "title": " "}]},
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["results"][0]["ok"] is False
    assert locks == ["lock"]
    assert _revision(db_session, owner_id) == before


def test_disconnect_external_busy_locks_before_delete_and_bumps(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = _owner_id(client)
    account = _seed_subscription(db_session, owner_id=owner_id, provider=CalendarProvider.google)
    event = ExternalCalendarEvent(
        owner_id=owner_id,
        calendar_account_id=account.id,
        provider=CalendarProvider.google,
        external_event_id=f"evt-{_uid()}",
        calendar_id="primary",
        title="Dentist",
        start_time=datetime(2026, 10, 9, 18, 0, tzinfo=UTC),
        end_time=datetime(2026, 10, 9, 19, 0, tzinfo=UTC),
    )
    db_session.add(event)
    db_session.flush()
    event_id = event.id
    account_id = account.id
    before = _revision(db_session, owner_id)
    order: list[str] = []
    real_lock = calendar_routes.lock_owner_scheduling
    real_delete = Query.delete

    def watched_lock(db: Session, lock_owner: uuid.UUID):
        order.append("lock")
        return real_lock(db, lock_owner)

    def watched_delete(self: Query, *args, **kwargs):
        order.append("delete")
        return real_delete(self, *args, **kwargs)

    monkeypatch.setattr(calendar_routes, "lock_owner_scheduling", watched_lock)
    monkeypatch.setattr(Query, "delete", watched_delete)

    deleted = client.delete(f"/api/v1/calendar/accounts/{account_id}")
    assert deleted.status_code == 204, deleted.text
    assert order[0] == "lock"
    assert "delete" in order
    assert order.index("lock") < order.index("delete")
    assert _revision(db_session, owner_id) == before + 1
    db_session.expire_all()
    assert db_session.get(ExternalCalendarEvent, event_id) is None
    assert db_session.get(CalendarAccount, account_id) is None


def test_disconnect_without_external_busy_does_not_bump(
    client: TestClient, db_session: Session
) -> None:
    owner_id = _owner_id(client)
    account = _seed_subscription(db_session, owner_id=owner_id, provider=CalendarProvider.microsoft)
    db_session.flush()
    before = _revision(db_session, owner_id)

    deleted = client.delete(f"/api/v1/calendar/accounts/{account.id}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == before
    db_session.expire_all()
    assert db_session.get(CalendarAccount, account.id) is None


def test_delete_block_mirror_failure_still_drops_local_row(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.scheduled_blocks.push_scheduled_block",
        lambda *args, **kwargs: None,
    )

    def boom(db: Session, settings: object, block: object) -> None:
        raise RuntimeError("provider down")

    monkeypatch.setattr("app.api.routes.scheduled_blocks.delete_mirrored_block", boom)
    owner_id = _owner_id(client)
    task = client.post("/api/v1/tasks", json={"title": f"boom-{_uid()}"}).json()
    start = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)
    created = client.post(
        "/api/v1/scheduled-blocks",
        json={
            "task_id": task["id"],
            "start_time": _iso(start),
            "end_time": _iso(start + timedelta(hours=1)),
        },
    )
    assert created.status_code == 201, created.text
    before = _revision(db_session, owner_id)
    deleted = client.delete(f"/api/v1/scheduled-blocks/{created.json()['id']}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == before + 1
    assert client.get(f"/api/v1/scheduled-blocks/{created.json()['id']}").status_code == 404
