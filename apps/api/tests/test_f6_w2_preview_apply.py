"""F6-W2: preview apply, staleness, idempotent receipt, replan serialization."""

from __future__ import annotations

import copy
import threading
import time
import uuid
from datetime import datetime, time as time_of_day, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import projects as project_routes
from app.bootstrap import BOOTSTRAP_USER_ID
from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    CalendarAccount,
    CalendarSubscription,
    Epic,
    Project,
    SchedulePreview,
    ScheduleRun,
    ScheduledBlock,
    Task,
    User,
    UserSettings,
)
from app.schemas import ProjectUpdate
from app.models.enums import CalendarProvider, CalendarSubscriptionRole, ScheduleStyle
from app.scheduler.preview import run_preview
from app.scheduler.replan import run_replan
from app.services import microsoft_calendar as ms_cal
from app.scheduler.preview_planning import PREVIEW_PLANNING_LEAD_SECONDS, preview_collection_time
from app.services.schedule_previews import summarize_diff
from app.services.schedule_preview_apply import apply_schedule_preview
from app.services.scheduling_revision import bump_scheduling_revision, owner_scheduling_lock_key

UTC = timezone.utc
FIXED_NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


class _ScheduleClock:
    def __init__(self) -> None:
        self.instant = FIXED_NOW


def _patch_schedule_clock(monkeypatch: pytest.MonkeyPatch) -> _ScheduleClock:
    clock = _ScheduleClock()

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            if tz is not None:
                return clock.instant.astimezone(tz)
            return clock.instant.replace(tzinfo=None)

    for module in (
        "app.scheduler.replan",
        "app.scheduler.preview",
        "app.services.schedule_previews",
        "app.services.schedule_preview_apply",
        "app.scheduler.placement",
        "app.scheduler.ups",
    ):
        monkeypatch.setattr(f"{module}.datetime", FixedDatetime)
    return clock


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _revision(db: Session, owner_id: uuid.UUID) -> int:
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    db.refresh(settings)
    return int(settings.scheduling_revision)


def _run_count(db: Session, owner_id: uuid.UUID) -> int:
    return db.query(ScheduleRun).filter(ScheduleRun.owner_id == owner_id).count()


def _prepare_settings(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={
            "timezone": "UTC",
            "workweek_days": 7,
            "upcoming_horizon_days": 7,
            "inter_block_buffer_minutes": 0,
            "default_schedule_style": "standalone",
        },
    )
    assert response.status_code == 200, response.text


def _create_task(client: TestClient, **extra: object) -> dict:
    payload = {"title": f"preview-apply-{_uid()}", **extra}
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _start_preview(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    response = client.post("/api/v1/schedule/previews")
    assert response.status_code == 202, response.text
    return response.json()


def _ready_preview(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    body = _start_preview(client, monkeypatch)
    run_preview(uuid.UUID(body["id"]), db=db_session)
    db_session.flush()
    got = client.get(f"/api/v1/schedule/previews/{body['id']}")
    assert got.status_code == 200, got.text
    preview = got.json()
    assert preview["status"] == "ready"
    return preview


def _block_set(db: Session, owner_id: uuid.UUID) -> set[tuple[str, str, str, bool]]:
    rows = (
        db.query(ScheduledBlock)
        .filter(ScheduledBlock.owner_id == owner_id)
        .order_by(ScheduledBlock.start_time.asc())
        .all()
    )
    return {
        (
            str(row.task_id),
            row.start_time.astimezone(UTC).isoformat(),
            row.end_time.astimezone(UTC).isoformat(),
            bool(row.is_pinned),
        )
        for row in rows
    }


def _proposed_identities(preview: dict) -> set[tuple[str, str, str]]:
    proposal = preview["proposal"]
    return {
        (row["task_id"], row["start_time"], row["end_time"])
        for row in proposal["proposed_blocks"]
    }


def test_f6_b_preview_proposal_matches_direct_replan(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.scheduler.preview.preview_collection_time",
        lambda wall: wall.astimezone(UTC),
    )
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=60,
        schedule_style="standalone",
        deadline_at=(FIXED_NOW + timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        priority="p1",
    )
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = task["id"]

    replan = client.post("/api/v1/schedule/replan")
    assert replan.status_code == 202, replan.text
    run_replan(uuid.UUID(replan.json()["id"]), db=db_session)
    db_session.flush()
    live_blocks = {
        (task_id, start, end, pinned)
        for task_id, start, end, pinned in _block_set(db_session, owner_id)
        if not pinned
    }
    proposed = {row for row in _proposed_identities(preview) if row[0] == task_id}
    live_for_task = {
        (tid, start, end)
        for tid, start, end, _pinned in live_blocks
        if tid == task_id
    }
    assert live_for_task == proposed


def test_f6_d_apply_is_idempotent(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    runs_before = _run_count(db_session, owner_id)
    first = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert first.status_code == 200, first.text
    receipt = first.json()
    blocks_after = _block_set(db_session, owner_id)
    runs_after = _run_count(db_session, owner_id)
    assert runs_after == runs_before + 1
    repeat = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert repeat.status_code == 200, repeat.text
    assert repeat.json() == receipt
    assert _block_set(db_session, owner_id) == blocks_after
    assert _run_count(db_session, owner_id) == runs_after


def test_f6_c_apply_rejects_stale_inputs_without_domain_writes(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)

    patch = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"estimated_duration_minutes": 90},
    )
    assert patch.status_code == 200, patch.text
    assert _revision(db_session, owner_id) == rev_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    body = stale.json()
    assert body["code"] == "PREVIEW_STALE"
    assert "duration" in body["stale_categories"]
    after = _block_set(db_session, owner_id)
    assert before == after


def test_f6_c_apply_rejects_expired_preview(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    row = db_session.get(SchedulePreview, uuid.UUID(preview["id"]))
    assert row is not None
    row.expires_at = FIXED_NOW - timedelta(minutes=1)
    db_session.flush()

    expired = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert expired.status_code == 409, expired.text
    assert expired.json()["code"] == "PREVIEW_EXPIRED"


def test_f6_d_apply_blocks_while_replan_running(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    db_session.add(ScheduleRun(owner_id=owner_id, status="running"))
    db_session.flush()

    blocked = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "SCHEDULE_RUN_IN_PROGRESS"


def test_f6_d_foreign_apply_matches_missing_404(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    preview = _ready_preview(client, db_session, monkeypatch)
    other = uuid.uuid4()
    missing = client.post(f"/api/v1/schedule/previews/{other}/apply")
    assert missing.status_code == 404

    other = User(
        email=f"f6-apply-other-{_uid()}@example.com",
        username=f"f6applyother{_uid()}",
    )
    db_session.add(other)
    db_session.flush()
    secret_id = uuid.uuid4()
    db_session.add(
        SchedulePreview(
            id=secret_id,
            owner_id=other.id,
            status="ready",
            scheduling_revision=0,
            proposal_json={"v": 1},
            input_fingerprint="hidden",
        )
    )
    db_session.flush()
    foreign = client.post(f"/api/v1/schedule/previews/{secret_id}/apply")
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "Schedule preview not found"

    owned = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert owned.status_code == 200, owned.text


def test_title_edit_does_not_bump_scheduling_revision(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    settings = (
        db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    )
    rev_before = int(settings.scheduling_revision)

    rename = client.patch(f"/api/v1/tasks/{task['id']}", json={"title": f"renamed-{_uid()}"})
    assert rename.status_code == 200, rename.text
    db_session.refresh(settings)
    assert int(settings.scheduling_revision) == rev_before

    still_ready = client.get(f"/api/v1/schedule/previews/{preview['id']}")
    assert still_ready.status_code == 200
    assert still_ready.json()["status"] == "ready"


def _create_block(
    client: TestClient,
    task_id: str,
    start: datetime,
    end: datetime,
    *,
    is_pinned: bool,
) -> dict:
    response = client.post(
        "/api/v1/scheduled-blocks",
        json={
            "task_id": task_id,
            "start_time": start.isoformat().replace("+00:00", "Z"),
            "end_time": end.isoformat().replace("+00:00", "Z"),
            "is_pinned": is_pinned,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_f6_b_preview_matches_replan_and_keeps_pins(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.scheduler.preview.preview_collection_time",
        lambda wall: wall.astimezone(UTC),
    )
    _patch_schedule_clock(monkeypatch)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_replan",
        lambda run_id, sync=False: None,
    )
    _prepare_settings(client)
    task = _create_task(
        client,
        estimated_duration_minutes=60,
        schedule_style="standalone",
        deadline_at=(FIXED_NOW + timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        priority="p1",
    )
    holder = _create_task(
        client,
        estimated_duration_minutes=30,
        schedule_style="manual",
    )
    pin_start = FIXED_NOW + timedelta(hours=3)
    pin_end = FIXED_NOW + timedelta(hours=4)
    pinned = _create_block(client, holder["id"], pin_start, pin_end, is_pinned=True)
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)

    replan = client.post("/api/v1/schedule/replan")
    assert replan.status_code == 202, replan.text
    run_replan(uuid.UUID(replan.json()["id"]), db=db_session)
    db_session.flush()

    pin_row = db_session.get(ScheduledBlock, uuid.UUID(pinned["id"]))
    assert pin_row is not None
    assert pin_row.is_pinned is True
    assert pin_row.start_time.astimezone(UTC) == pin_start
    assert pin_row.end_time.astimezone(UTC) == pin_end

    task_id = task["id"]
    live_for_task = {
        (tid, start, end)
        for tid, start, end, pinned_flag in _block_set(db_session, owner_id)
        if tid == task_id and not pinned_flag
    }
    proposed = {row for row in _proposed_identities(preview) if row[0] == task_id}
    assert live_for_task == proposed
    assert all(row[0] != holder["id"] for row in _proposed_identities(preview))


def test_f6_c_apply_rejects_past_blocks_without_domain_writes(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    runs_before = _run_count(db_session, owner_id)

    row = db_session.get(SchedulePreview, uuid.UUID(preview["id"]))
    assert row is not None and row.proposal_json is not None
    proposal = copy.deepcopy(row.proposal_json)
    assert proposal["proposed_blocks"], proposal
    start = FIXED_NOW + timedelta(minutes=2)
    proposal["proposed_blocks"][0]["start_time"] = start.isoformat()
    proposal["proposed_blocks"][0]["end_time"] = (start + timedelta(hours=1)).isoformat()
    row.proposal_json = proposal
    db_session.flush()

    clock.instant = start + timedelta(minutes=1)
    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_PAST_BLOCKS"
    assert _block_set(db_session, owner_id) == before
    assert _run_count(db_session, owner_id) == runs_before

    still = client.get(f"/api/v1/schedule/previews/{preview['id']}")
    assert still.status_code == 200, still.text
    assert still.json()["status"] == "ready"


def test_f6_c_soft_delete_bumps_and_stales_apply(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)

    deleted = client.delete(f"/api/v1/tasks/{task['id']}")
    assert deleted.status_code == 204, deleted.text
    assert _revision(db_session, owner_id) == rev_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    body = stale.json()
    assert body["code"] == "PREVIEW_STALE"
    assert "lifecycle" in body["stale_categories"]
    assert _block_set(db_session, owner_id) == before


def test_trash_restore_purge_and_empty_bump_scheduling_revision(
    client: TestClient,
    db_session: Session,
) -> None:
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    owner_id = _owner_id(client)
    rev = _revision(db_session, owner_id)

    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    assert _revision(db_session, owner_id) == rev + 1
    restored = client.post(f"/api/v1/tasks/{task['id']}/restore")
    assert restored.status_code == 200, restored.text
    assert _revision(db_session, owner_id) == rev + 2
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    assert _revision(db_session, owner_id) == rev + 3
    purged = client.delete(f"/api/v1/tasks/{task['id']}", params={"hard": "true"})
    assert purged.status_code == 204, purged.text
    assert _revision(db_session, owner_id) == rev + 4

    other = _create_task(client, estimated_duration_minutes=45, schedule_style="standalone")
    rev_after_create = _revision(db_session, owner_id)
    assert client.delete(f"/api/v1/tasks/{other['id']}").status_code == 204
    emptied = client.delete("/api/v1/tasks/trash")
    assert emptied.status_code == 204, emptied.text
    assert _revision(db_session, owner_id) == rev_after_create + 2


def test_f6_c_revision_only_change_names_provenance(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)

    bump_scheduling_revision(db_session, owner_id)
    db_session.flush()
    assert _revision(db_session, owner_id) == rev_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    body = stale.json()
    assert body["code"] == "PREVIEW_STALE"
    assert body["stale_categories"] == ["provenance"]
    assert _block_set(db_session, owner_id) == before


def test_f6_c_busy_ingest_bumps_only_when_intervals_change(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    rev_before = _revision(db_session, owner_id)

    calendar_id = f"cal-{_uid()}"
    account = CalendarAccount(
        owner_id=owner_id,
        provider=CalendarProvider.microsoft,
        account_email=f"f6-busy-{_uid()}@contoso.test",
        is_enabled=True,
        mirror_blocks=False,
    )
    db_session.add(account)
    db_session.flush()
    db_session.add(
        CalendarSubscription(
            owner_id=owner_id,
            calendar_account_id=account.id,
            external_calendar_id=calendar_id,
            summary="Calendar",
            role=CalendarSubscriptionRole.primary,
            is_enabled=True,
        )
    )
    db_session.flush()

    event = {
        "id": f"evt-{_uid()}",
        "subject": "Dentist",
        "start": {"dateTime": "2026-10-09T18:00:00", "timeZone": "UTC"},
        "end": {"dateTime": "2026-10-09T19:00:00", "timeZone": "UTC"},
    }

    def fake_list(access: str, calendar: str, *, time_min: datetime, time_max: datetime):
        return [event], "cursor-1"

    def fake_incremental(access: str, cursor: str):
        renamed = dict(event)
        renamed["subject"] = "Dentist renamed"
        return [renamed], "cursor-2"

    monkeypatch.setattr(
        ms_cal,
        "get_valid_access_token",
        lambda db, *, settings, account: "tok",
    )
    monkeypatch.setattr(ms_cal, "list_calendar_events", fake_list)
    monkeypatch.setattr(ms_cal, "list_calendar_events_incremental", fake_incremental)

    window_start = FIXED_NOW - timedelta(days=1)
    window_end = FIXED_NOW + timedelta(days=7)
    upserted = ms_cal.sync_account_events(
        db_session,
        settings=get_settings(),
        account=account,
        time_min=window_start,
        time_max=window_end,
    )
    assert upserted == 1
    assert _revision(db_session, owner_id) == rev_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    body = stale.json()
    assert body["code"] == "PREVIEW_STALE"
    assert "busy_external" in body["stale_categories"]
    assert _block_set(db_session, owner_id) == before

    rev_after_busy = _revision(db_session, owner_id)
    again = ms_cal.sync_account_events(
        db_session,
        settings=get_settings(),
        account=account,
        time_min=window_start,
        time_max=window_end,
    )
    assert again == 1
    assert _revision(db_session, owner_id) == rev_after_busy


def test_f6_d_provider_failure_does_not_replay_local_apply(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    calls = {"n": 0}

    def boom(_db: object, _settings: object, _block: object) -> None:
        calls["n"] += 1
        raise RuntimeError("provider down")

    monkeypatch.setattr("app.scheduler.apply._push_mirrored_block", boom)
    first = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert first.status_code == 200, first.text
    assert calls["n"] >= 1
    pushed = calls["n"]
    blocks_after = _block_set(db_session, owner_id)
    assert any(not pinned for _tid, _start, _end, pinned in blocks_after)

    repeat = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()["receipt_id"] == first.json()["receipt_id"]
    assert repeat.json()["schedule_run_id"] == first.json()["schedule_run_id"]
    assert calls["n"] == pushed
    assert _block_set(db_session, owner_id) == blocks_after


def test_summarize_diff_counts_moved_not_added_removed(
) -> None:
    proposal = {
        "before_blocks": [
            {
                "task_id": "t1",
                "start_time": "2026-10-09T23:28:00+00:00",
                "end_time": "2026-10-09T24:28:00+00:00",
                "is_pinned": False,
            }
        ],
        "proposed_blocks": [
            {
                "task_id": "t1",
                "start_time": "2026-10-10T00:29:00+00:00",
                "end_time": "2026-10-10T01:29:00+00:00",
            }
        ],
    }
    counts = summarize_diff(proposal)
    assert counts == {
        "blocks_added": 0,
        "blocks_removed": 0,
        "blocks_moved": 1,
        "blocks_unchanged": 0,
    }


def test_f6_c_preview_planning_lead_keeps_first_block_applyable(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    planning = preview_collection_time(FIXED_NOW)
    assert PREVIEW_PLANNING_LEAD_SECONDS == 90
    first_start = preview["proposal"]["proposed_blocks"][0]["start_time"]
    assert first_start >= planning.isoformat()
    clock.instant = FIXED_NOW + timedelta(seconds=45)
    applied = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert applied.status_code == 200, applied.text


def test_archive_project_stales_ready_preview(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    project = client.post(
        "/api/v1/projects",
        json={"title": f"arch-{_uid()}"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    _create_task(
        client,
        project_id=project_id,
        estimated_duration_minutes=60,
        schedule_style="standalone",
    )
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    archived = client.post(f"/api/v1/projects/{project_id}/archive")
    assert archived.status_code == 200, archived.text
    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "PREVIEW_STALE"
    assert _block_set(db_session, owner_id) == before


def test_reparent_to_manual_epic_stales_ready_preview(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inherited project moved under a Manual epic bumps revision and blocks apply."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    project = client.post("/api/v1/projects", json={"title": f"inherit-{_uid()}"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    assert project.json()["schedule_style"] is None
    task = _create_task(
        client,
        project_id=project_id,
        estimated_duration_minutes=60,
    )
    assert task["schedule_style"] is None
    epic = client.post(
        "/api/v1/epics",
        json={"title": f"manual-{_uid()}", "schedule_style": "manual"},
    )
    assert epic.status_code == 201, epic.text
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    revision_before = _revision(db_session, owner_id)

    renamed = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": f"renamed-{_uid()}"},
    )
    assert renamed.status_code == 200, renamed.text
    assert _revision(db_session, owner_id) == revision_before

    moved = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"epic_id": epic.json()["id"]},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["epic_id"] == epic.json()["id"]
    assert moved.json()["schedule_style"] is None
    assert _revision(db_session, owner_id) == revision_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    body = stale.json()
    assert body["code"] == "PREVIEW_STALE"
    assert "map_style" in body["stale_categories"]
    assert _block_set(db_session, owner_id) == before


def test_detach_project_epic_stales_ready_preview(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """epic_id null is a scheduling patch even when effective style stays put."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    epic = client.post("/api/v1/epics", json={"title": f"plain-{_uid()}"})
    assert epic.status_code == 201, epic.text
    project = client.post(
        "/api/v1/projects",
        json={"title": f"child-{_uid()}", "epic_id": epic.json()["id"]},
    )
    assert project.status_code == 201, project.text
    task = _create_task(
        client,
        project_id=project.json()["id"],
        estimated_duration_minutes=60,
    )
    assert task["schedule_style"] is None
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    revision_before = _revision(db_session, owner_id)

    detached = client.patch(
        f"/api/v1/projects/{project.json()['id']}",
        json={"epic_id": None},
    )
    assert detached.status_code == 200, detached.text
    assert detached.json()["epic_id"] is None
    assert _revision(db_session, owner_id) == revision_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    body = stale.json()
    assert body["code"] == "PREVIEW_STALE"
    assert "provenance" in body["stale_categories"]
    assert _block_set(db_session, owner_id) == before


def test_epic_target_date_patch_bumps_scheduling_revision(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UPS reads epic target_date; a date-only patch must stale apply via revision."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    epic = client.post("/api/v1/epics", json={"title": f"dated-{_uid()}"})
    assert epic.status_code == 201, epic.text
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    revision_before = _revision(db_session, owner_id)

    patched = client.patch(
        f"/api/v1/epics/{epic.json()['id']}",
        json={"target_date": "2026-10-20"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["target_date"] == "2026-10-20"
    assert _revision(db_session, owner_id) == revision_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    body = stale.json()
    assert body["code"] == "PREVIEW_STALE"
    assert body["stale_categories"] == ["provenance"]
    assert _block_set(db_session, owner_id) == before


def test_apply_returns_receipt_when_identity_map_stale(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    user = db_session.query(User).filter(User.id == owner_id).one()
    row = db_session.get(SchedulePreview, uuid.UUID(preview["id"]))
    assert row is not None
    assert row.status == "ready"
    first = apply_schedule_preview(db_session, user, row)
    row.status = "ready"
    second = apply_schedule_preview(db_session, user, row)
    assert second["receipt_id"] == first["receipt_id"]


def test_f6_d_applied_without_receipt_does_not_reapply(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    before = _block_set(db_session, owner_id)
    runs_before = _run_count(db_session, owner_id)
    row = db_session.get(SchedulePreview, uuid.UUID(preview["id"]))
    assert row is not None
    row.status = "applied"
    row.stats_json = {}
    db_session.flush()

    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "PREVIEW_ALREADY_APPLIED"
    assert _block_set(db_session, owner_id) == before
    assert _run_count(db_session, owner_id) == runs_before


def test_recurrence_due_fill_stales_ready_preview(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PUT recurrence that fills a null due_at must bump revision under the owner lock."""
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    assert task["due_at"] is None
    preview = _ready_preview(client, db_session, monkeypatch)
    owner_id = _owner_id(client)
    revision_before = _revision(db_session, owner_id)

    saved = client.put(
        f"/api/v1/tasks/{task['id']}/recurrence",
        json={"rrule": "FREQ=DAILY;INTERVAL=1", "is_fixed": False, "timezone": "UTC"},
    )
    assert saved.status_code == 200, saved.text
    got = client.get(f"/api/v1/tasks/{task['id']}")
    assert got.status_code == 200, got.text
    assert got.json()["due_at"] is not None
    assert _revision(db_session, owner_id) == revision_before + 1

    stale = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "PREVIEW_STALE"


_LOCK_PROBE_EMAIL_LIKE = "renee-f6-lock-%@example.com"


def _purge_lock_probe_users() -> None:
    """Remove committed throwaway owners. The transactional fixture cannot host two sessions."""
    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        db.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": _LOCK_PROBE_EMAIL_LIKE},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _commit_lock_probe_owner() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"renee-f6-lock-{token}@example.com",
            username=f"renee-f6-{token}",
            display_name="Renee F6 lock probe",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        if owner_scheduling_lock_key(user.id) == owner_scheduling_lock_key(BOOTSTRAP_USER_ID):
            raise RuntimeError("probe owner collided with the bootstrap scheduling lock key")
        db.add(
            UserSettings(
                owner_id=user.id,
                timezone="UTC",
                workday_minutes=1440,
                workday_start_local=time_of_day(0, 0),
                workweek_days=7,
                inter_block_buffer_minutes=0,
                upcoming_horizon_days=7,
                default_schedule_style=ScheduleStyle.standalone,
                scheduling_revision=0,
            )
        )
        project = Project(owner_id=user.id, title=f"renee-f6-lock-{token}")
        db.add(project)
        db.flush()
        db.add(
            Task(
                owner_id=user.id,
                project_id=project.id,
                title=f"renee-f6-lock-task-{token}",
                estimated_duration_minutes=60,
                schedule_style=ScheduleStyle.standalone,
            )
        )
        preview = SchedulePreview(owner_id=user.id, status="running")
        db.add(preview)
        db.commit()
        return user.id, project.id, preview.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _commit_reparent_probe_owner() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Inherited project plus a Manual epic, committed so a second session can reparent."""
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"renee-f6-lock-{token}@example.com",
            username=f"renee-f6-{token}",
            display_name="Renee F6 reparent probe",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        if owner_scheduling_lock_key(user.id) == owner_scheduling_lock_key(BOOTSTRAP_USER_ID):
            raise RuntimeError("probe owner collided with the bootstrap scheduling lock key")
        db.add(
            UserSettings(
                owner_id=user.id,
                timezone="UTC",
                workday_minutes=1440,
                workday_start_local=time_of_day(0, 0),
                workweek_days=7,
                inter_block_buffer_minutes=0,
                upcoming_horizon_days=7,
                default_schedule_style=ScheduleStyle.standalone,
                scheduling_revision=0,
            )
        )
        epic = Epic(
            owner_id=user.id,
            title=f"renee-f6-manual-{token}",
            schedule_style=ScheduleStyle.manual,
        )
        project = Project(owner_id=user.id, title=f"renee-f6-reparent-{token}")
        db.add(epic)
        db.add(project)
        db.flush()
        db.add(
            Task(
                owner_id=user.id,
                project_id=project.id,
                title=f"renee-f6-reparent-task-{token}",
                estimated_duration_minutes=60,
            )
        )
        preview = SchedulePreview(owner_id=user.id, status="running")
        db.add(preview)
        db.commit()
        return user.id, project.id, preview.id, epic.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_archive_during_apply_waits_for_owner_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dex P1: archive cannot commit while apply holds the owner scheduling lock.

    Uses two real sessions. The shared pytest transaction hides uncommitted rows
    from a second connection, so this probe commits a throwaway owner and deletes it.
    """
    import app.services.schedule_preview_apply as preview_apply

    _purge_lock_probe_users()
    owner_id, project_id, preview_id = _commit_lock_probe_owner()
    gate = threading.Event()
    holding = threading.Event()
    archive_reached_lock = threading.Event()
    archive_finished = threading.Event()
    archive_tid: list[int] = []
    errors: list[BaseException] = []
    apply_result: dict[str, object] = {}
    apply_thread: threading.Thread | None = None
    archive_thread: threading.Thread | None = None
    real_fingerprint = preview_apply.live_owner_fingerprint
    real_lock = project_routes.lock_owner_scheduling

    def paused_fingerprint(db: Session, fingerprint_owner: uuid.UUID, now: datetime):
        holding.set()
        if not gate.wait(8):
            raise TimeoutError("apply stayed parked in the fingerprint hook")
        return real_fingerprint(db, fingerprint_owner, now)

    def watched_lock(db: Session, lock_owner: uuid.UUID):
        if archive_tid and threading.get_ident() == archive_tid[0]:
            archive_reached_lock.set()
        return real_lock(db, lock_owner)

    def run_apply() -> None:
        db = SessionLocal()
        try:
            user = db.get(User, owner_id)
            preview = db.get(SchedulePreview, preview_id)
            assert user is not None and preview is not None
            apply_result["receipt"] = apply_schedule_preview(db, user, preview)
            db.commit()
        except Exception as exc:
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    def run_archive() -> None:
        archive_tid.append(threading.get_ident())
        db = SessionLocal()
        try:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            user = db.get(User, owner_id)
            assert user is not None
            project_routes.archive_project(project_id, db=db, user=user)
            archive_finished.set()
        except Exception as exc:
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    try:
        run_preview(preview_id)
        ready = SessionLocal()
        try:
            stored = ready.get(SchedulePreview, preview_id)
            assert stored is not None, "probe preview missing after calculate"
            assert stored.status == "ready", stored.error_message
            proposal = stored.proposal_json or {}
            assert proposal.get("proposed_blocks"), proposal
        finally:
            ready.close()

        monkeypatch.setattr(preview_apply, "live_owner_fingerprint", paused_fingerprint)
        monkeypatch.setattr(project_routes, "lock_owner_scheduling", watched_lock)

        apply_thread = threading.Thread(target=run_apply, name="f6-apply")
        apply_thread.start()
        assert holding.wait(8), f"apply did not reach the fingerprint hook: {errors}"

        archive_thread = threading.Thread(target=run_archive, name="f6-archive")
        archive_thread.start()
        assert archive_reached_lock.wait(8), f"archive did not reach the owner lock: {errors}"
        time.sleep(0.3)
        assert not archive_finished.is_set(), "archive committed while apply held the owner lock"
        assert not errors, errors

        watch = SessionLocal()
        try:
            project = watch.get(Project, project_id)
            preview = watch.get(SchedulePreview, preview_id)
            settings = watch.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
            assert project is not None and project.is_archived is False
            assert preview is not None and preview.status == "ready"
            assert int(settings.scheduling_revision) == 0
        finally:
            watch.close()

        gate.set()
        apply_thread.join(15)
        archive_thread.join(15)
        assert not errors, errors
        assert archive_finished.is_set()
        receipt = apply_result["receipt"]
        assert isinstance(receipt, dict) and receipt.get("receipt_id")

        check = SessionLocal()
        try:
            project = check.get(Project, project_id)
            preview = check.get(SchedulePreview, preview_id)
            settings = check.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
            blocks = (
                check.query(ScheduledBlock)
                .filter(ScheduledBlock.owner_id == owner_id, ScheduledBlock.is_pinned.is_(False))
                .count()
            )
            assert project is not None and project.is_archived is True
            assert preview is not None and preview.status == "applied"
            assert blocks >= 1
            assert int(settings.scheduling_revision) >= 2
        finally:
            check.close()
    finally:
        gate.set()
        if apply_thread is not None:
            apply_thread.join(15)
        if archive_thread is not None:
            archive_thread.join(15)
        _purge_lock_probe_users()


def test_reparent_during_apply_waits_for_owner_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dex P1 residual: epic_id patch cannot commit while apply holds the owner lock."""
    import app.services.schedule_preview_apply as preview_apply

    _purge_lock_probe_users()
    owner_id, project_id, preview_id, epic_id = _commit_reparent_probe_owner()
    gate = threading.Event()
    holding = threading.Event()
    reparent_reached_lock = threading.Event()
    reparent_finished = threading.Event()
    reparent_tid: list[int] = []
    errors: list[BaseException] = []
    apply_result: dict[str, object] = {}
    apply_thread: threading.Thread | None = None
    reparent_thread: threading.Thread | None = None
    real_fingerprint = preview_apply.live_owner_fingerprint
    real_lock = project_routes.lock_owner_scheduling

    def paused_fingerprint(db: Session, fingerprint_owner: uuid.UUID, now: datetime):
        holding.set()
        if not gate.wait(8):
            raise TimeoutError("apply stayed parked in the fingerprint hook")
        return real_fingerprint(db, fingerprint_owner, now)

    def watched_lock(db: Session, lock_owner: uuid.UUID):
        if reparent_tid and threading.get_ident() == reparent_tid[0]:
            reparent_reached_lock.set()
        return real_lock(db, lock_owner)

    def run_apply() -> None:
        db = SessionLocal()
        try:
            user = db.get(User, owner_id)
            preview = db.get(SchedulePreview, preview_id)
            assert user is not None and preview is not None
            apply_result["receipt"] = apply_schedule_preview(db, user, preview)
            db.commit()
        except Exception as exc:
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    def run_reparent() -> None:
        reparent_tid.append(threading.get_ident())
        db = SessionLocal()
        try:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            user = db.get(User, owner_id)
            assert user is not None
            project_routes.update_project(
                project_id,
                ProjectUpdate(epic_id=epic_id),
                db=db,
                user=user,
            )
            reparent_finished.set()
        except Exception as exc:
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    try:
        run_preview(preview_id)
        ready = SessionLocal()
        try:
            stored = ready.get(SchedulePreview, preview_id)
            assert stored is not None, "probe preview missing after calculate"
            assert stored.status == "ready", stored.error_message
            proposal = stored.proposal_json or {}
            assert proposal.get("proposed_blocks"), proposal
        finally:
            ready.close()

        monkeypatch.setattr(preview_apply, "live_owner_fingerprint", paused_fingerprint)
        monkeypatch.setattr(project_routes, "lock_owner_scheduling", watched_lock)

        apply_thread = threading.Thread(target=run_apply, name="f6-apply-reparent")
        apply_thread.start()
        assert holding.wait(8), f"apply did not reach the fingerprint hook: {errors}"

        reparent_thread = threading.Thread(target=run_reparent, name="f6-reparent")
        reparent_thread.start()
        assert reparent_reached_lock.wait(8), f"reparent did not reach the owner lock: {errors}"
        time.sleep(0.3)
        assert not reparent_finished.is_set(), "reparent committed while apply held the owner lock"
        assert not errors, errors

        watch = SessionLocal()
        try:
            project = watch.get(Project, project_id)
            preview = watch.get(SchedulePreview, preview_id)
            settings = watch.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
            assert project is not None and project.epic_id is None
            assert preview is not None and preview.status == "ready"
            assert int(settings.scheduling_revision) == 0
        finally:
            watch.close()

        gate.set()
        apply_thread.join(15)
        reparent_thread.join(15)
        assert not errors, errors
        assert reparent_finished.is_set()
        receipt = apply_result["receipt"]
        assert isinstance(receipt, dict) and receipt.get("receipt_id")

        check = SessionLocal()
        try:
            project = check.get(Project, project_id)
            preview = check.get(SchedulePreview, preview_id)
            settings = check.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
            blocks = (
                check.query(ScheduledBlock)
                .filter(ScheduledBlock.owner_id == owner_id, ScheduledBlock.is_pinned.is_(False))
                .count()
            )
            assert project is not None and project.epic_id == epic_id
            assert preview is not None and preview.status == "applied"
            assert blocks >= 1
            assert int(settings.scheduling_revision) >= 2
        finally:
            check.close()
    finally:
        gate.set()
        if apply_thread is not None:
            apply_thread.join(15)
        if reparent_thread is not None:
            reparent_thread.join(15)
        _purge_lock_probe_users()
