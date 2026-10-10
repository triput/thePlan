"""F6-W1: preview calculate path — zero domain writes (F6-A foundation)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, update
from sqlalchemy.orm import Session

from app.models import (
    CalendarAccount,
    ExternalCalendarEvent,
    SchedulePreview,
    ScheduleRun,
    ScheduleTaskOutcome,
    ScheduledBlock,
    Task,
    User,
    UserSettings,
)
from app.models.enums import ScheduleStatus
from app.scheduler.calculate import calculate as real_calculate
from app.scheduler.preview import run_preview
from app.scheduler.preview_planning import preview_collection_time

UTC = timezone.utc
FIXED_NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
LATER_NOW = FIXED_NOW + timedelta(minutes=5)

DOMAIN_MODELS = (
    Task,
    ScheduledBlock,
    ScheduleTaskOutcome,
    ScheduleRun,
    ExternalCalendarEvent,
    CalendarAccount,
    UserSettings,
)

_FORBIDDEN_CALLS = (
    "app.scheduler.apply.apply_calculation",
    "app.scheduler.apply.wipe_unpinned_blocks_in_horizon",
    "app.scheduler.apply.persist_calculation_outcomes",
    "app.scheduler.apply._push_mirrored_block",
    "app.scheduler.replan.run_replan",
    "app.scheduler.horizon.wipe_unpinned_blocks_in_horizon",
    "app.scheduler.outcomes.persist_calculation_outcomes",
    "app.services.google_calendar.push_scheduled_block",
    "app.services.google_calendar.delete_mirrored_block",
    "app.services.google_calendar.create_google_event",
    "app.services.microsoft_calendar.push_scheduled_block",
    "app.services.microsoft_calendar.delete_mirrored_block",
    "app.services.microsoft_calendar.create_microsoft_event",
)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _parse_api_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _domain_snapshot(db: Session) -> dict[str, list[tuple[object, ...]]]:
    snapped: dict[str, list[tuple[object, ...]]] = {}
    for model in DOMAIN_MODELS:
        columns = [column.name for column in model.__table__.columns]
        rows = db.query(model).order_by(model.id).all()
        snapped[model.__tablename__] = [
            tuple(_freeze(getattr(row, name)) for name in columns) for row in rows
        ]
    return snapped


def _same_instant(left: datetime, right: datetime) -> bool:
    if left.tzinfo is None:
        left = left.replace(tzinfo=UTC)
    if right.tzinfo is None:
        right = right.replace(tzinfo=UTC)
    return left.astimezone(UTC) == right.astimezone(UTC)


def _schedule_side_snapshot(db: Session) -> dict[str, list[tuple[object, ...]]]:
    """Tables a preview must not touch, even when the test itself edits a task."""
    keep = {
        ScheduledBlock.__tablename__,
        ScheduleTaskOutcome.__tablename__,
        ScheduleRun.__tablename__,
        ExternalCalendarEvent.__tablename__,
        CalendarAccount.__tablename__,
    }
    full = _domain_snapshot(db)
    return {name: rows for name, rows in full.items() if name in keep}


def _assert_domain_unchanged(
    before: dict[str, list[tuple[object, ...]]],
    after: dict[str, list[tuple[object, ...]]],
) -> None:
    assert before.keys() == after.keys()
    for name in before:
        assert before[name] == after[name], name


class _Clock:
    def __init__(self, *instants: datetime) -> None:
        self._queue = list(instants)
        self.last = instants[-1]

    def now(self, tz: timezone | None = None) -> datetime:
        value = self._queue.pop(0) if self._queue else self.last
        self.last = value
        if tz is not None:
            return value.astimezone(tz)
        return value.replace(tzinfo=None)

    def push(self, instant: datetime) -> None:
        self._queue.append(instant)


def _install_clock(monkeypatch: pytest.MonkeyPatch, clock: _Clock, *modules: str) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return clock.now(tz)

    for module in modules:
        monkeypatch.setattr(f"{module}.datetime", FixedDatetime)


def _patch_schedule_clock(monkeypatch: pytest.MonkeyPatch, clock: _Clock | None = None) -> _Clock:
    clock = clock or _Clock(FIXED_NOW)
    _install_clock(
        monkeypatch,
        clock,
        "app.scheduler.replan",
        "app.scheduler.preview",
        "app.services.schedule_previews",
        "app.scheduler.placement",
        "app.scheduler.ups",
    )
    return clock


def _forbid_domain_and_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(path: str):
        def _called(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(f"{path} called during preview")

        return _called

    for path in _FORBIDDEN_CALLS:
        monkeypatch.setattr(path, _forbidden(path))


def _watch_flushes(db: Session) -> tuple[list[tuple[str, str]], object]:
    seen: list[tuple[str, str]] = []

    def before_flush(session: Session, _flush_context: object, _instances: object) -> None:
        for label, bucket in (
            ("insert", session.new),
            ("update", session.dirty),
            ("delete", session.deleted),
        ):
            for obj in bucket:
                if label == "update" and not session.is_modified(obj, include_collections=False):
                    continue
                seen.append((label, obj.__class__.__name__))

    event.listen(db, "before_flush", before_flush)
    return seen, before_flush


def _assert_only_preview_writes(seen: list[tuple[str, str]]) -> None:
    offenders = [item for item in seen if item[1] != "SchedulePreview"]
    assert offenders == [], offenders
    assert seen, "preview row was not flushed"


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
    payload = {"title": f"preview-{_uid()}", **extra}
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


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


def _start_preview(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    response = client.post("/api/v1/schedule/previews")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "running"
    assert body["proposal"] is None
    return body


def _preview_sync(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    body = _start_preview(client, monkeypatch)
    run_preview(uuid.UUID(body["id"]), db=db_session)
    db_session.flush()
    got = client.get(f"/api/v1/schedule/previews/{body['id']}")
    assert got.status_code == 200, got.text
    return got.json()


def _guard_calculate_session(monkeypatch: pytest.MonkeyPatch) -> None:
    def _guard(db: Session, inputs: object):
        result = real_calculate(db, inputs)
        dirty = [
            obj.__class__.__name__
            for obj in list(db.new) + list(db.deleted) + list(db.dirty)
            if obj.__class__ is not SchedulePreview
            and (
                obj in db.new
                or obj in db.deleted
                or db.is_modified(obj, include_collections=False)
            )
        ]
        assert dirty == [], dirty
        return result

    monkeypatch.setattr("app.scheduler.preview.calculate", _guard)


def _retire_running(db: Session, owner_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    rows = (
        db.query(ScheduleRun)
        .filter(ScheduleRun.owner_id == owner_id, ScheduleRun.status == "running")
        .all()
    )
    for row in rows:
        row.status = "failed"
        row.finished_at = now
        row.error_message = "test retire"
    if rows:
        db.flush()


def test_f6_a_preview_does_not_mutate_domain(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview_clock = _Clock(FIXED_NOW, LATER_NOW)
    _patch_schedule_clock(monkeypatch, _Clock(FIXED_NOW))
    _install_clock(monkeypatch, preview_clock, "app.scheduler.preview")
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
        title=f"hold-{_uid()}",
        schedule_style="manual",
        estimated_duration_minutes=30,
    )
    loose = _create_block(
        client,
        holder["id"],
        FIXED_NOW + timedelta(hours=1),
        FIXED_NOW + timedelta(hours=2),
        is_pinned=False,
    )
    pinned = _create_block(
        client,
        holder["id"],
        FIXED_NOW + timedelta(hours=3),
        FIXED_NOW + timedelta(hours=4),
        is_pinned=True,
    )
    task_id = uuid.UUID(task["id"])
    before_post = _domain_snapshot(db_session)
    started = _start_preview(client, monkeypatch)
    assert _domain_snapshot(db_session) == before_post

    _forbid_domain_and_provider_calls(monkeypatch)
    _guard_calculate_session(monkeypatch)
    writes, hook = _watch_flushes(db_session)
    try:
        run_preview(uuid.UUID(started["id"]), db=db_session)
    finally:
        event.remove(db_session, "before_flush", hook)

    _assert_only_preview_writes(writes)
    _assert_domain_unchanged(before_post, _domain_snapshot(db_session))

    loose_row = db_session.get(ScheduledBlock, uuid.UUID(loose["id"]))
    pinned_row = db_session.get(ScheduledBlock, uuid.UUID(pinned["id"]))
    assert loose_row is not None and pinned_row is not None
    assert loose_row.is_pinned is False
    assert pinned_row.is_pinned is True
    assert _same_instant(loose_row.start_time, FIXED_NOW + timedelta(hours=1))
    assert _same_instant(loose_row.end_time, FIXED_NOW + timedelta(hours=2))
    assert _same_instant(pinned_row.start_time, FIXED_NOW + timedelta(hours=3))
    assert _same_instant(pinned_row.end_time, FIXED_NOW + timedelta(hours=4))
    task_after = db_session.get(Task, task_id)
    assert task_after is not None
    assert task_after.status == ScheduleStatus.unscheduled

    got = client.get(f"/api/v1/schedule/previews/{started['id']}")
    assert got.status_code == 200, got.text
    preview = got.json()
    assert preview["status"] == "ready"
    assert preview["input_fingerprint"]
    assert preview["proposal"]["blocks_created"] >= 1
    assert preview["proposal"]["proposed_blocks"]
    assert any(row["is_pinned"] for row in preview["proposal"]["before_blocks"])
    assert _parse_api_dt(preview["evaluated_at"]) == LATER_NOW
    assert _parse_api_dt(preview["expires_at"]) == LATER_NOW + timedelta(minutes=15)

    proposed_for_task = [
        block
        for block in preview["proposal"]["proposed_blocks"]
        if block["task_id"] == task["id"]
    ]
    assert proposed_for_task
    assert (
        db_session.query(ScheduledBlock).filter(ScheduledBlock.task_id == task_id).count()
        == 0
    )

    stored = db_session.get(SchedulePreview, uuid.UUID(preview["id"]))
    assert stored is not None
    assert stored.input_snapshot is not None
    assert stored.input_snapshot["collected_at"] == preview_collection_time(FIXED_NOW).isoformat()
    assert "ups_scores" in stored.input_snapshot
    settings = (
        db_session.query(UserSettings)
        .filter(UserSettings.owner_id == task_after.owner_id)
        .one()
    )
    assert settings.scheduling_revision == stored.scheduling_revision


def test_f6_a_failed_preview_rolls_back_attempted_writes(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    task_id = uuid.UUID(task["id"])
    before = _domain_snapshot(db_session)
    started = _start_preview(client, monkeypatch)

    def _mutate_then_raise(db: Session, _inputs: object) -> None:
        row = db.get(Task, task_id)
        assert row is not None
        row.status = ScheduleStatus.scheduled
        db.flush()
        raise RuntimeError("preview calculate failed")

    monkeypatch.setattr("app.scheduler.preview.calculate", _mutate_then_raise)
    _forbid_domain_and_provider_calls(monkeypatch)
    run_preview(uuid.UUID(started["id"]), db=db_session)

    _assert_domain_unchanged(before, _domain_snapshot(db_session))
    task_after = db_session.get(Task, task_id)
    assert task_after is not None
    assert task_after.status == ScheduleStatus.unscheduled
    got = client.get(f"/api/v1/schedule/previews/{started['id']}")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["status"] == "failed"
    assert body["proposal"] is None
    assert "preview calculate failed" in (body["error_message"] or "")


def test_clock_advance_on_read_stays_ready(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_clock = _Clock(FIXED_NOW)
    _patch_schedule_clock(monkeypatch, read_clock)
    _prepare_settings(client)
    _create_task(
        client,
        estimated_duration_minutes=60,
        schedule_style="standalone",
        deadline_at=(FIXED_NOW + timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        priority="p1",
    )
    preview = _preview_sync(client, db_session, monkeypatch)
    assert preview["status"] == "ready"

    read_clock.push(FIXED_NOW + timedelta(minutes=10))
    got = client.get(f"/api/v1/schedule/previews/{preview['id']}")
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "ready"


def test_expiry_on_read_does_not_write_domain(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _preview_sync(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    row = db_session.get(SchedulePreview, uuid.UUID(preview["id"]))
    assert row is not None
    row.expires_at = FIXED_NOW - timedelta(minutes=1)
    db_session.flush()
    before = _domain_snapshot(db_session)
    got = client.get(f"/api/v1/schedule/previews/{preview['id']}")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["status"] == "expired"
    assert body["proposal"] is not None
    _assert_domain_unchanged(before, _domain_snapshot(db_session))


def test_duration_and_weight_edits_mark_preview_stale(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    preview = _preview_sync(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    before = _schedule_side_snapshot(db_session)

    duration = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"estimated_duration_minutes": 90},
    )
    assert duration.status_code == 200, duration.text
    got = client.get(f"/api/v1/schedule/previews/{preview['id']}")
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "stale"

    # A preview taken after the duration edit must go stale on a weight edit.
    # Duration alone would not change that second fingerprint.
    fresh = _preview_sync(client, db_session, monkeypatch)
    assert fresh["status"] == "ready"
    settings = client.get("/api/v1/settings")
    assert settings.status_code == 200, settings.text
    weights = dict(settings.json()["ups_weights"])
    weights["Wp"] = float(weights.get("Wp", 0.35)) + 0.05
    weighted = client.patch("/api/v1/settings", json={"ups_weights": weights})
    assert weighted.status_code == 200, weighted.text
    again = client.get(f"/api/v1/schedule/previews/{fresh['id']}")
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "stale"
    _assert_domain_unchanged(before, _schedule_side_snapshot(db_session))


def test_revision_change_during_calculate_marks_stale(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    task = _create_task(client, estimated_duration_minutes=60, schedule_style="standalone")
    task_id = uuid.UUID(task["id"])
    side_before = _schedule_side_snapshot(db_session)
    started = _start_preview(client, monkeypatch)

    def _bump(db: Session, inputs: object):
        db.execute(
            update(UserSettings)
            .where(UserSettings.owner_id == inputs.owner_id)  # type: ignore[attr-defined]
            .values(scheduling_revision=UserSettings.scheduling_revision + 1)
        )
        db.flush()
        return real_calculate(db, inputs)

    monkeypatch.setattr("app.scheduler.preview.calculate", _bump)
    _forbid_domain_and_provider_calls(monkeypatch)
    run_preview(uuid.UUID(started["id"]), db=db_session)

    got = client.get(f"/api/v1/schedule/previews/{started['id']}")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["status"] == "stale"
    assert body["stats_json"]["stale_reason"] == "scheduling_revision"
    _assert_domain_unchanged(side_before, _schedule_side_snapshot(db_session))
    task_after = db_session.get(Task, task_id)
    assert task_after is not None
    assert task_after.status == ScheduleStatus.unscheduled


def test_preview_admission_ignores_running_replan(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    me = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    _retire_running(db_session, me)
    runs_before = db_session.query(ScheduleRun).count()
    db_session.add(ScheduleRun(owner_id=me, status="running"))
    db_session.flush()
    first = _start_preview(client, monkeypatch)
    second = _start_preview(client, monkeypatch)
    assert first["id"] != second["id"]
    assert db_session.query(ScheduleRun).count() == runs_before + 1
    running = (
        db_session.query(ScheduleRun)
        .filter(ScheduleRun.owner_id == me, ScheduleRun.status == "running")
        .count()
    )
    assert running == 1


def test_foreign_preview_matches_missing_404(
    client: TestClient,
    db_session: Session,
) -> None:
    other = User(
        email=f"f6-other-{_uid()}@example.com",
        username=f"f6other{_uid()}",
    )
    db_session.add(other)
    db_session.flush()
    secret = SchedulePreview(
        owner_id=other.id,
        status="ready",
        scheduling_revision=0,
        proposal_json={"secret": "hidden-preview"},
        input_fingerprint="not-yours",
    )
    db_session.add(secret)
    db_session.flush()

    missing = client.get(f"/api/v1/schedule/previews/{uuid.uuid4()}")
    foreign = client.get(f"/api/v1/schedule/previews/{secret.id}")
    assert missing.status_code == 404
    assert foreign.status_code == 404
    assert foreign.json() == missing.json()
    assert foreign.json()["detail"] == "Schedule preview not found"
    assert "hidden-preview" not in foreign.text


def test_apply_missing_preview_is_404(client: TestClient) -> None:
    response = client.post(f"/api/v1/schedule/previews/{uuid.uuid4()}/apply")
    assert response.status_code == 404
    assert response.json()["detail"] == "Schedule preview not found"
