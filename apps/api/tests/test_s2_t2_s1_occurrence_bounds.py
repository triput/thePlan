"""T2-S1 occurrence bounds — full disposable acceptance (theplan_s1_test @ :5433)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import SchedulePreview, ScheduledBlock, Task
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import (
    SCHEDULING_ACTIVATIONS,
    STALE_OCCURRENCE_BOUNDS,
    STALE_SCHEDULING_ACTIVATION,
    diff_stale_categories,
)
from app.scheduler.occurrence_bounds import (
    _feasible_start_exists_in_horizon,
    feasible_start_window,
    horizon_blocks_placement,
    pin_bounds_conflict,
)
from app.services.availability_seed import ensure_default_availability_policies
from app.services.task_occurrence_bounds import OCCURRENCE_BOUNDS_NAIVE_INSTANT
from app.scheduler.outcomes import snapshots_from_collected
from app.scheduler.preview import run_preview
from app.scheduler.reasons import (
    REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT,
    REASON_OCCURRENCE_BOUNDS_MISS,
    REASON_OCCURRENCE_BOUNDS_NO_SLOT,
    REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT,
    REASON_PLACED,
)
from test_schedule_replan import (
    FIXED_NOW,
    _create_task,
    _isolate_tasks,
    _patch_schedule_clock,
    _prepare_settings,
)

UTC = timezone.utc
_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "042_task_occurrence_dispositions"


@pytest.fixture(autouse=True)
def _disposable_s1_database(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _day_time(days_ahead: int = 1, hour: int = 0, minute: int = 0) -> datetime:
    """Calendar day offset from FIXED_NOW with explicit local hour (not +hours drift)."""
    base = FIXED_NOW + timedelta(days=days_ahead)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _ready_preview(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    assert started.status_code == 202, started.text
    run_preview(uuid.UUID(started.json()["id"]), db=db_session)
    db_session.flush()
    got = client.get(f"/api/v1/schedule/previews/{started.json()['id']}")
    assert got.status_code == 200
    preview = got.json()
    assert preview["status"] == "ready"
    return preview


def _outcome(result, task_id: uuid.UUID):
    return next(item for item in result.outcomes if item.task_id == task_id)


def _scheduling_revision(client: TestClient) -> int:
    return int(client.get("/api/v1/settings").json()["scheduling_revision"])


def _put_prefer_assignment(client: TestClient, task_id: str, *, policy_id: str) -> None:
    response = client.put(
        f"/api/v1/tasks/{task_id}/scheduling",
        json={
            "expected_revision": _scheduling_revision(client),
            "may": {"presence": "omit", "rules": []},
            "must": [],
            "prefer": [{"name": "afternoon", "policy_id": policy_id}],
        },
    )
    assert response.status_code == 200, response.text


def _bind_cli_to_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from theplan.api_client import api_error_from_response

    def api_json(
        method: str,
        path: str,
        *,
        json_body: dict | list | None = None,
        params: dict | None = None,
        **kwargs,
    ):
        call = getattr(client, method.lower())
        if method.upper() in {"GET", "DELETE"}:
            response = call(path, params=params)
        else:
            response = call(path, json=json_body, params=params)
        if response.status_code >= 400:
            raise api_error_from_response(response)
        if not response.content:
            return None
        return response.json()

    monkeypatch.setattr("theplan.commands.tasks.api_json", api_json)


def test_unit_pin_bounds_no_false_positive_when_deadline_tighter_than_latest() -> None:
    day = datetime(2026, 8, 12, tzinfo=UTC)
    task = Task(
        title="pin-fp",
        owner_id=uuid.uuid4(),
        estimated_duration_minutes=60,
        start_no_earlier_at=day.replace(hour=9),
        start_no_later_at=day.replace(hour=12),
        deadline_at=day.replace(hour=10),
    )
    pin = [(day.replace(hour=9, minute=30), day.replace(hour=10))]
    assert pin_bounds_conflict(task, pin_intervals=pin, effort_minutes=60) is False


def test_unit_pin_bounds_flags_finish_overrun() -> None:
    day = datetime(2026, 8, 12, tzinfo=UTC)
    task = Task(
        title="pin-over",
        owner_id=uuid.uuid4(),
        estimated_duration_minutes=30,
        start_no_earlier_at=day.replace(hour=9),
        start_no_later_at=day.replace(hour=12),
        deadline_at=day.replace(hour=10),
    )
    pin = [(day.replace(hour=9, minute=30), day.replace(hour=10, minute=1))]
    assert pin_bounds_conflict(task, pin_intervals=pin, effort_minutes=30) is True


def test_offset_naive_bounds_rejected_create_and_patch(client: TestClient) -> None:
    _prepare_settings(client)
    naive = client.post(
        "/api/v1/tasks",
        json={"title": f"naive-{_uid()}", "start_no_earlier_at": "2026-08-12T09:00:00"},
    )
    assert naive.status_code == 422
    assert naive.json()["code"] == OCCURRENCE_BOUNDS_NAIVE_INSTANT
    ok = client.post(
        "/api/v1/tasks",
        json={
            "title": f"aware-{_uid()}",
            "start_no_earlier_at": "2026-08-12T09:00:00+00:00",
        },
    )
    assert ok.status_code == 201
    task_id = ok.json()["id"]
    merged = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_later_at": "2026-08-12T17:00:00"},
    )
    assert merged.status_code == 422
    assert merged.json()["code"] == OCCURRENCE_BOUNDS_NAIVE_INSTANT


def test_offset_equivalent_instants_round_trip(client: TestClient) -> None:
    _prepare_settings(client)
    pacific = ZoneInfo("America/Los_Angeles")
    instant = datetime(2026, 8, 12, 9, 0, tzinfo=pacific)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"tz-{_uid()}",
            "start_no_earlier_at": instant.isoformat(),
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    got = client.get(f"/api/v1/tasks/{task_id}").json()
    stored = datetime.fromisoformat(got["start_no_earlier_at"].replace("Z", "+00:00"))
    assert stored == instant.astimezone(UTC)
    same_utc = client.post(
        "/api/v1/tasks",
        json={
            "title": f"tz2-{_uid()}",
            "start_no_earlier_at": instant.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        },
    )
    assert same_utc.status_code == 201
    stored2 = datetime.fromisoformat(
        client.get(f"/api/v1/tasks/{same_utc.json()['id']}").json()["start_no_earlier_at"].replace(
            "Z", "+00:00"
        )
    )
    assert stored2 == instant.astimezone(UTC)


def test_unit_horizon_allows_loose_upper_with_feasible_start_today() -> None:
    task = Task(
        title="unit",
        owner_id=uuid.uuid4(),
        estimated_duration_minutes=60,
        start_no_earlier_at=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
        start_no_later_at=datetime(2026, 10, 22, 17, 0, tzinfo=UTC),
        deadline_at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
    )
    hs = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    he = hs + timedelta(days=7)
    assert _feasible_start_exists_in_horizon(
        task, effort_minutes=60, horizon_start=hs, horizon_end=he
    )
    assert not horizon_blocks_placement(
        task, effort_minutes=60, horizon_start=hs, horizon_end=he
    )
    window = feasible_start_window(
        task, effort_minutes=60, horizon_start=hs, horizon_end=he
    )
    assert window is not None
    lo, hi = window
    assert lo <= datetime(2026, 10, 22, 11, 0, tzinfo=UTC) <= hi


def test_a1_unbounded_and_bound_combinations(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    cases = (
        ("unbounded", {}),
        ("lower", {"start_no_earlier_at": _iso(_day_time(1, 9))}),
        ("upper", {"start_no_later_at": _iso(_day_time(1, 17))}),
        (
            "both",
            {
                "start_no_earlier_at": _iso(_day_time(1, 9)),
                "start_no_later_at": _iso(_day_time(1, 17)),
            },
        ),
    )
    for label, bounds in cases:
        created = _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            priority="p1",
            **bounds,
        )
        task_id = uuid.UUID(created["id"])
        _isolate_tasks(db_session, client, {task_id})
        result = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
        outcome = _outcome(result, task_id)
        assert outcome.primary_code == REASON_PLACED, label
        assert len([b for b in result.proposed_blocks if b.task_id == task_id]) == 1


def test_a2_exact_start_and_loose_latest_finish_by(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    day = (FIXED_NOW + timedelta(days=1)).date()
    equal = _create_task(
        client,
        estimated_duration_minutes=30,
        schedule_style="time_block",
        start_no_earlier_at=_iso(datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)),
        start_no_later_at=_iso(datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)),
    )
    loose = _create_task(
        client,
        estimated_duration_minutes=60,
        schedule_style="time_block",
        start_no_earlier_at=_iso(datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)),
        start_no_later_at=_iso(datetime(day.year, day.month, day.day, 17, 0, tzinfo=UTC)),
        deadline_at=_iso(datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC)),
    )
    _isolate_tasks(db_session, client, {uuid.UUID(equal["id"]), uuid.UUID(loose["id"])})
    result = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
    prop_equal = [b for b in result.proposed_blocks if b.task_id == uuid.UUID(equal["id"])]
    assert len(prop_equal) == 1
    assert prop_equal[0].start_time == datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)
    prop_loose = [b for b in result.proposed_blocks if b.task_id == uuid.UUID(loose["id"])]
    assert len(prop_loose) == 1
    start = prop_loose[0].start_time
    assert start >= datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)
    assert start + timedelta(minutes=60) <= datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC)


def test_a2b_patch_geometry_infeasible_then_calculate(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    created = _create_task(
        client,
        estimated_duration_minutes=30,
        schedule_style="time_block",
        start_no_earlier_at=_iso(_day_time(1, 9)),
        deadline_at=_iso(_day_time(1, 10)),
    )
    task_id = uuid.UUID(created["id"])
    _isolate_tasks(db_session, client, {task_id})
    rev = int(client.get("/api/v1/settings").json()["scheduling_revision"])
    patched = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"remaining_estimate_minutes": 120, "expected_revision": rev},
    )
    assert patched.status_code == 200, patched.text
    outcome = _outcome(calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id)
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_NO_SLOT


def test_a3_no_slot_open_window(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
            deadline_at=_iso(_day_time(1, 9, 30)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_NO_SLOT


def test_a4_auto_defer_respects_bounds_placed_and_infeasible_upper(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    client.patch("/api/v1/settings", json={"auto_defer_enabled": True})
    owner_id = _owner_id(client)
    earliest = _day_time(1, 9)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_earlier_at=_iso(earliest),
            soft_target_at=_iso(FIXED_NOW - timedelta(hours=2)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    first = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
    placed = _outcome(first, task_id)
    assert placed.primary_code == REASON_PLACED
    block = next(b for b in first.proposed_blocks if b.task_id == task_id)
    assert block.start_time >= earliest

    tight = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
            deadline_at=_iso(_day_time(1, 9, 45)),
            soft_target_at=_iso(FIXED_NOW - timedelta(hours=1)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {tight})
    infeasible = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), tight
    )
    assert infeasible.primary_code == REASON_OCCURRENCE_BOUNDS_NO_SLOT


def test_a5_preview_apply_stale_bounds_activation_no_domain_write(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    preview = _ready_preview(client, db_session, monkeypatch)
    blocks_before = (
        db_session.query(ScheduledBlock).filter(ScheduledBlock.owner_id == owner_id).count()
    )
    client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_earlier_at": _iso(_day_time(1, 10))},
    )
    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    body = rejected.json()
    assert body["code"] == "PREVIEW_STALE"
    assert STALE_OCCURRENCE_BOUNDS in body.get("stale_categories", [])
    assert (
        db_session.query(ScheduledBlock).filter(ScheduledBlock.owner_id == owner_id).count()
        == blocks_before
    )

    preview2 = _ready_preview(client, db_session, monkeypatch)
    row = db_session.get(SchedulePreview, uuid.UUID(preview2["id"]))
    assert row is not None
    snap = dict(row.input_snapshot or {})
    task_key = str(task_id)
    stored_task = dict((snap.get("task_snapshots") or {}).get(task_key) or {})
    stored_task["scheduling_activation"] = {
        "ids": list(reversed(SCHEDULING_ACTIVATIONS)),
    }
    snap.setdefault("task_snapshots", {})[task_key] = stored_task
    snap.setdefault("task_fingerprints", {})[task_key] = "stale-task-fingerprint"
    row.input_snapshot = snap
    row.input_fingerprint = "stale-owner-fingerprint"
    db_session.flush()
    rejected_activation = client.post(f"/api/v1/schedule/previews/{preview2['id']}/apply")
    assert rejected_activation.status_code == 409
    assert rejected_activation.json()["code"] == "PREVIEW_STALE"
    assert rejected_activation.json().get("stale_categories")
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    live_snap = inputs.input_snapshots[task_id]
    stored_snap = dict(live_snap)
    stored_snap["scheduling_activation"] = {"ids": list(reversed(SCHEDULING_ACTIVATIONS))}
    assert STALE_SCHEDULING_ACTIVATION in diff_stale_categories(stored_snap, live_snap)
    assert (
        db_session.query(ScheduledBlock).filter(ScheduledBlock.owner_id == owner_id).count()
        == blocks_before
    )


def test_a6_prefer_assignment_loses_to_hard_bounds(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    ensure_default_availability_policies(db_session, owner_id)
    weekday = _day_time(1).weekday()
    afternoon = client.patch(
        "/api/v1/availability-policies/personal",
        json={
            "windows": [
                {
                    "weekday": weekday,
                    "start_time": "13:00",
                    "duration_minutes": 240,
                    "sort_order": 0,
                }
            ]
        },
    )
    assert afternoon.status_code == 200, afternoon.text
    latest = _day_time(1, 12)
    created = _create_task(
        client,
        estimated_duration_minutes=30,
        schedule_style="time_block",
        start_no_later_at=_iso(latest),
    )
    task_id = uuid.UUID(created["id"])
    _put_prefer_assignment(client, created["id"], policy_id=afternoon.json()["id"])
    _isolate_tasks(db_session, client, {task_id})
    blocks = [
        b
        for b in calculate(
            db_session, collect_inputs(db_session, owner_id, FIXED_NOW)
        ).proposed_blocks
        if b.task_id == task_id
    ]
    assert len(blocks) == 1
    assert blocks[0].start_time <= latest
    assert blocks[0].start_time.hour < 13


def test_a7_miss_when_window_elapsed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_later_at=_iso(FIXED_NOW - timedelta(hours=1)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_MISS


def test_a8_api_and_cli_bounds_round_trip(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import sys
    from pathlib import Path

    cli_root = Path(__file__).resolve().parents[2] / "cli"
    if str(cli_root) not in sys.path:
        sys.path.insert(0, str(cli_root))
    from theplan.commands.tasks import run_tasks
    from theplan.main import _build_parser
    from theplan.output import set_output_format

    _prepare_settings(client)
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": f"a8-{_uid()}",
            "start_no_earlier_at": _iso(_day_time(1, 9)),
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    merged_bad = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_later_at": _iso(_day_time(1, 8))},
    )
    assert merged_bad.status_code == 422
    assert merged_bad.json()["code"] == "OCCURRENCE_BOUNDS_INVERTED"

    _bind_cli_to_client(client, monkeypatch)
    set_output_format("json")
    latest_cli = _day_time(1, 11).isoformat().replace("+00:00", "Z")
    run_tasks(
        _build_parser().parse_args(
            [
                "tasks",
                "patch",
                "--id",
                task_id,
                "--start-no-later-at",
                latest_cli,
            ]
        )
    )
    patched = json.loads(capsys.readouterr().out)
    assert patched["start_no_later_at"] is not None
    run_tasks(
        _build_parser().parse_args(
            [
                "tasks",
                "get",
                "--id",
                task_id,
            ]
        )
    )
    shown = json.loads(capsys.readouterr().out)
    assert shown["start_no_earlier_at"] is not None
    assert shown["start_no_later_at"] is not None
    run_tasks(
        _build_parser().parse_args(
            [
                "tasks",
                "scheduling-effective",
                "--id",
                task_id,
            ]
        )
    )
    effective = json.loads(capsys.readouterr().out)
    assert effective.get("occurrence_bounds") is not None
    run_tasks(
        _build_parser().parse_args(
            [
                "tasks",
                "patch",
                "--id",
                task_id,
                "--clear-start-no-earlier-at",
                "--clear-start-no-later-at",
            ]
        )
    )
    cleared = json.loads(capsys.readouterr().out)
    assert cleared["start_no_earlier_at"] is None
    assert cleared["start_no_later_at"] is None
    run_tasks(
        _build_parser().parse_args(
            ["tasks", "scheduling-effective", "--id", task_id]
        )
    )
    assert json.loads(capsys.readouterr().out).get("occurrence_bounds") is None


def test_a9_hold_pin_conflict_and_preserved_pin(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    pin_start = FIXED_NOW + timedelta(hours=2)
    pin_end = pin_start + timedelta(minutes=30)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(FIXED_NOW + timedelta(hours=5)),
            start_no_later_at=_iso(FIXED_NOW + timedelta(hours=6)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=pin_start,
            end_time=pin_end,
            is_pinned=True,
        )
    )
    db_session.commit()
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    codes = [f.code for f in outcome.reason_facts]
    assert REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT in codes
    assert REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT in codes
    after = db_session.query(ScheduledBlock).filter(ScheduledBlock.task_id == task_id).one()
    assert after.start_time == pin_start
    assert after.end_time == pin_end
    assert after.is_pinned is True


def test_a9_hold_without_pin_conflict_when_pin_respects_explicit_bounds(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    day = _day_time(1)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(day.replace(hour=9)),
            start_no_later_at=_iso(day.replace(hour=12)),
            deadline_at=_iso(day.replace(hour=10)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    pin_start = day.replace(hour=9, minute=30)
    pin_end = day.replace(hour=10)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=pin_start,
            end_time=pin_end,
            is_pinned=True,
        )
    )
    db_session.commit()
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    codes = [f.code for f in outcome.reason_facts]
    assert REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT in codes
    assert REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT not in codes


def test_a9b_seeded_auto_block_single_replacement_proposal(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
            start_no_later_at=_iso(_day_time(1, 17)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    stale_start = _day_time(1, 15)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=stale_start,
            end_time=stale_start + timedelta(minutes=30),
            is_pinned=False,
        )
    )
    db_session.commit()
    client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"start_no_later_at": _iso(_day_time(1, 12))},
    )
    result = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
    proposed = [b for b in result.proposed_blocks if b.task_id == task_id]
    assert len(proposed) == 1
    assert proposed[0].start_time <= _day_time(1, 12)
    assert proposed[0].start_time.hour < 13
    persisted = db_session.query(ScheduledBlock).filter(ScheduledBlock.task_id == task_id).all()
    assert len(persisted) == 1
    assert persisted[0].start_time == stale_start
    second = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
    assert len([b for b in second.proposed_blocks if b.task_id == task_id]) == 1


def test_a10_repeated_calculate_preserves_progress_pin_and_remaining(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=60,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    pin_start = FIXED_NOW + timedelta(hours=1)
    pin_end = pin_start + timedelta(minutes=30)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=pin_start,
            end_time=pin_end,
            is_pinned=True,
        )
    )
    db_session.commit()
    rev = _scheduling_revision(client)
    progress = client.post(
        f"/api/v1/tasks/{task_id}/progress-entries",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": 15,
            "remaining_minutes": 45,
            "expected_revision": rev,
        },
    )
    assert progress.status_code == 200, progress.text
    db_session.expire_all()
    task = db_session.get(Task, task_id)
    assert task is not None
    assert task.worked_minutes == 15
    assert task.remaining_minutes == 45
    _outcome(calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id)
    _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW + timedelta(hours=1))),
        task_id,
    )
    db_session.refresh(task)
    assert task.worked_minutes == 15
    assert task.remaining_minutes == 45
    pin = db_session.query(ScheduledBlock).filter(ScheduledBlock.task_id == task_id).one()
    assert pin.is_pinned is True
    assert pin.start_time == pin_start
    assert pin.end_time == pin_end


def test_hold_started_block_outside_horizon(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_later_at=_iso(FIXED_NOW + timedelta(days=2)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    past_start = FIXED_NOW - timedelta(days=2)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=past_start,
            end_time=past_start + timedelta(minutes=30),
            is_pinned=False,
        )
    )
    db_session.commit()
    outcome = _outcome(
        calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW)), task_id
    )
    assert outcome.reason_facts[0].code == REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT


def test_hold_full_pin_coverage_bounded(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_schedule_clock(monkeypatch)
    _prepare_settings(client)
    owner_id = _owner_id(client)
    task_id = uuid.UUID(
        _create_task(
            client,
            estimated_duration_minutes=30,
            schedule_style="time_block",
            start_no_earlier_at=_iso(_day_time(1, 9)),
        )["id"]
    )
    _isolate_tasks(db_session, client, {task_id})
    ps = _day_time(1, 10)
    db_session.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=task_id,
            start_time=ps,
            end_time=ps + timedelta(minutes=30),
            is_pinned=True,
        )
    )
    db_session.commit()
    result = calculate(db_session, collect_inputs(db_session, owner_id, FIXED_NOW))
    outcome = next((o for o in result.outcomes if o.task_id == task_id), None)
    assert outcome is not None
    assert any(f.code == REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT for f in outcome.reason_facts)
