"""T2-S2 B-auto held miss — disposable acceptance (theplan_s1_test @ :5433).

Honest A1–A10 evidence: no force-drift hooks, no GREEN for unexercised paths.
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime, timedelta, time as time_of_day, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import SessionLocal
from app.models import (
    Project,
    SchedulePreview,
    ScheduledBlock,
    Task,
    TaskOccurrenceDisposition,
    User,
    UserSettings,
)
from app.models.enums import ScheduleStyle
from app.models.task_occurrence_disposition import (
    EVENT_LEAVE_HELD,
    EVENT_MISS_DETECTED,
    RESOLUTION_UNRESOLVED_HELD,
)
from app.scheduler.calculate import calculate
from app.scheduler.collect import collect_inputs
from app.scheduler.input_fingerprint import (
    STALE_OCCURRENCE_DISPOSITION,
    diff_stale_categories,
    normalize_occurrence_disposition,
)
from app.scheduler.preview import run_preview
from app.services.availability_seed import ensure_default_availability_policies
from app.services.occurrence_disposition import orchestration_input_drift
from app.services.scheduling_revision import owner_scheduling_lock_key
from test_schedule_replan import FIXED_NOW, _create_task, _patch_schedule_clock, _prepare_settings

UTC = timezone.utc
_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "042_task_occurrence_dispositions"
_PROBE_EMAIL_LIKE = "justin-t2s2-bauto-%@example.com"

cli_root = Path(__file__).resolve().parents[2] / "cli"
if str(cli_root) not in sys.path:
    sys.path.insert(0, str(cli_root))


@pytest.fixture(autouse=True)
def _disposable_db(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_schedule_clock(monkeypatch)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _prepare(client: TestClient, db: Session) -> None:
    _prepare_settings(client)
    ensure_default_availability_policies(db, _owner_id(client))
    db.commit()


def _owner_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me").json()["id"])


def _miss_task(client: TestClient, db: Session, *, title: str | None = None) -> dict:
    latest = FIXED_NOW - timedelta(hours=2)
    return _create_task(
        client,
        title=title or f"Miss {_uid()}",
        estimated_duration_minutes=60,
        start_no_later_at=latest.isoformat().replace("+00:00", "Z"),
    )


def _ready_preview(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    assert started.status_code == 202, started.text
    run_preview(uuid.UUID(started.json()["id"]), db=db)
    db.flush()
    got = client.get(f"/api/v1/schedule/previews/{started.json()['id']}")
    assert got.status_code == 200
    return got.json()


def _revision(client: TestClient) -> int:
    return int(client.get("/api/v1/settings").json()["scheduling_revision"])


def _fresh_session_on(connection) -> Session:
    """Separate Session/identity map on the fixture connection (no cross-connection commit)."""
    return Session(
        bind=connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )


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
            response = call(path, json=json_body if json_body is not None else kwargs.get("json"), params=params)
        if response.status_code >= 400:
            raise api_error_from_response(response)
        if not response.content:
            return None
        return response.json()

    monkeypatch.setattr("theplan.commands.schedule.api_json", api_json)


def _purge_probe_users() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        db.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": _PROBE_EMAIL_LIKE},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _seed_always_on_availability(db: Session, owner_id: uuid.UUID) -> None:
    from app.models import AvailabilityPolicy, AvailabilityWindow
    from app.models.enums import AvailabilityPolicySlug
    from app.services.availability_seed import derive_window_end

    ensure_default_availability_policies(db, owner_id)
    start = time_of_day(0, 0)
    end, overnight = derive_window_end(start, 1440)
    for slug in (AvailabilityPolicySlug.work.value, AvailabilityPolicySlug.general.value):
        policy = (
            db.query(AvailabilityPolicy)
            .filter(
                AvailabilityPolicy.owner_id == owner_id,
                AvailabilityPolicy.slug == slug,
            )
            .one()
        )
        policy.windows.clear()
        db.flush()
        for weekday in range(7):
            policy.windows.append(
                AvailabilityWindow(
                    owner_id=owner_id,
                    weekday=weekday,
                    start_time=start,
                    end_time=end,
                    ends_next_day=overnight,
                    duration_minutes=1440,
                    sort_order=0,
                )
            )
    db.flush()


def _commit_miss_probe(
    *,
    n_previews: int = 1,
    n_miss_tasks: int = 1,
) -> tuple[uuid.UUID, list[uuid.UUID], list[uuid.UUID]]:
    """Committed throwaway owner + miss task(s) + running preview(s) for cross-session races."""
    token = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        user = User(
            email=f"justin-t2s2-bauto-{token}@example.com",
            username=f"justin-t2s2-{token}",
            display_name="Justin T2-S2 B-auto probe",
            is_admin=False,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        if owner_scheduling_lock_key(user.id) == owner_scheduling_lock_key(BOOTSTRAP_USER_ID):
            raise RuntimeError("probe owner collided with bootstrap scheduling lock key")
        db.add(
            UserSettings(
                owner_id=user.id,
                timezone="UTC",
                inter_block_buffer_minutes=0,
                upcoming_horizon_days=7,
                default_schedule_style=ScheduleStyle.standalone,
                scheduling_revision=0,
            )
        )
        _seed_always_on_availability(db, user.id)
        project = Project(owner_id=user.id, title=f"justin-t2s2-{token}")
        db.add(project)
        db.flush()
        task_ids: list[uuid.UUID] = []
        latest = FIXED_NOW - timedelta(hours=2)
        for i in range(n_miss_tasks):
            task = Task(
                owner_id=user.id,
                project_id=project.id,
                title=f"justin-t2s2-miss-{token}-{i}",
                estimated_duration_minutes=60,
                schedule_style=ScheduleStyle.standalone,
                start_no_later_at=latest,
            )
            db.add(task)
            db.flush()
            task_ids.append(task.id)
        preview_ids: list[uuid.UUID] = []
        for _ in range(n_previews):
            preview = SchedulePreview(owner_id=user.id, status="running")
            db.add(preview)
            db.flush()
            preview_ids.append(preview.id)
        db.commit()
        return user.id, task_ids, preview_ids
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Drift unit cases (fix 2)
# ---------------------------------------------------------------------------


def test_drift_exempts_only_disposition_on_staged_task() -> None:
    task_id = str(uuid.uuid4())
    snap0 = {
        "v": 4,
        "duration": {"estimated_duration_minutes": 60},
        "occurrence_disposition": normalize_occurrence_disposition(None, None),
    }
    snap1 = {
        "v": 4,
        "duration": {"estimated_duration_minutes": 60},
        "occurrence_disposition": normalize_occurrence_disposition(
            RESOLUTION_UNRESOLVED_HELD, "ep1"
        ),
    }
    staged = {(task_id, "ep1", RESOLUTION_UNRESOLVED_HELD)}
    assert (
        orchestration_input_drift(
            revision_at_start=1,
            revision_live=1,
            snapshot_at_start={
                "task_snapshots": {task_id: snap0},
                "task_fingerprints": {task_id: "a"},
                "dependency_edges": [],
                "ups_scores": {},
                "scheduling_activation": {"ids": []},
                "snapshot_version": 4,
            },
            fingerprint_at_start="f0",
            snapshot_live={
                "task_snapshots": {task_id: snap1},
                "task_fingerprints": {task_id: "b"},
                "dependency_edges": [],
                "ups_scores": {},
                "scheduling_activation": {"ids": []},
                "snapshot_version": 4,
            },
            fingerprint_live="f1",
            disposition_before=(),
            disposition_live=((task_id, "ep1", RESOLUTION_UNRESOLVED_HELD),),
            staged_keys=staged,
        )
        is False
    )


def test_drift_staged_task_other_field_is_external() -> None:
    task_id = str(uuid.uuid4())
    snap0 = {
        "v": 4,
        "duration": {"estimated_duration_minutes": 60},
        "occurrence_disposition": normalize_occurrence_disposition(None, None),
    }
    snap1 = {
        "v": 4,
        "duration": {"estimated_duration_minutes": 90},
        "occurrence_disposition": normalize_occurrence_disposition(
            RESOLUTION_UNRESOLVED_HELD, "ep1"
        ),
    }
    staged = {(task_id, "ep1", RESOLUTION_UNRESOLVED_HELD)}
    assert (
        orchestration_input_drift(
            revision_at_start=1,
            revision_live=1,
            snapshot_at_start={
                "task_snapshots": {task_id: snap0},
                "dependency_edges": [],
                "ups_scores": {},
                "scheduling_activation": {"ids": []},
                "snapshot_version": 4,
            },
            fingerprint_at_start="f0",
            snapshot_live={
                "task_snapshots": {task_id: snap1},
                "dependency_edges": [],
                "ups_scores": {},
                "scheduling_activation": {"ids": []},
                "snapshot_version": 4,
            },
            fingerprint_live="f1",
            disposition_before=(),
            disposition_live=((task_id, "ep1", RESOLUTION_UNRESOLVED_HELD),),
            staged_keys=staged,
        )
        is True
    )


def test_drift_no_revision_fingerprint_change_is_external() -> None:
    task_id = str(uuid.uuid4())
    snap0 = {"v": 4, "duration": {"estimated_duration_minutes": 60}}
    snap1 = {"v": 4, "duration": {"estimated_duration_minutes": 90}}
    assert (
        orchestration_input_drift(
            revision_at_start=3,
            revision_live=3,
            snapshot_at_start={
                "task_snapshots": {task_id: snap0},
                "dependency_edges": [],
                "ups_scores": {},
                "scheduling_activation": {"ids": []},
                "snapshot_version": 4,
            },
            fingerprint_at_start="f0",
            snapshot_live={
                "task_snapshots": {task_id: snap1},
                "dependency_edges": [],
                "ups_scores": {},
                "scheduling_activation": {"ids": []},
                "snapshot_version": 4,
            },
            fingerprint_live="f1",
            disposition_before=(),
            disposition_live=(),
            staged_keys=set(),
        )
        is True
    )


# ---------------------------------------------------------------------------
# A1–A10 + extras
# ---------------------------------------------------------------------------


def test_a1_external_revision_drift_aborts(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual mid-orchestration edit (revision bump), not a force_drift hook."""
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])
    edited = {"done": False}
    real_lock = __import__(
        "app.services.scheduling_revision", fromlist=["lock_owner_scheduling"]
    ).lock_owner_scheduling

    def lock_after_real_edit(db: Session, owner_id: uuid.UUID):
        if not edited["done"]:
            edited["done"] = True
            rev = _revision(client)
            patched = client.patch(
                f"/api/v1/tasks/{task['id']}",
                json={
                    "expected_revision": rev,
                    "estimated_duration_minutes": 90,
                },
            )
            assert patched.status_code == 200, patched.text
        return real_lock(db, owner_id)

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration.lock_owner_scheduling",
        lock_after_real_edit,
    )
    run_preview(preview_id, db=db_session)
    db_session.expire_all()
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] in {"stale", "failed"}
    assert got.json()["status"] != "ready"
    assert db_session.query(TaskOccurrenceDisposition).count() == 0


def test_a2_two_previews_same_owner_serialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two concurrent SessionLocal() previews, same owner — one durable episode."""
    _patch_schedule_clock(monkeypatch)
    _purge_probe_users()
    owner_id, task_ids, preview_ids = _commit_miss_probe(n_previews=2, n_miss_tasks=1)
    assert len(preview_ids) == 2
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker(preview_id: uuid.UUID) -> None:
        try:
            barrier.wait(timeout=15)
            run_preview(preview_id)
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(preview_ids[0],))
    t2 = threading.Thread(target=worker, args=(preview_ids[1],))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert errors == [], errors
    readback = SessionLocal()
    try:
        rows = (
            readback.query(TaskOccurrenceDisposition)
            .filter(TaskOccurrenceDisposition.task_id == task_ids[0])
            .all()
        )
        assert len(rows) == 1
        statuses = {
            readback.get(SchedulePreview, pid).status for pid in preview_ids  # type: ignore[union-attr]
        }
        assert "ready" in statuses
        assert statuses <= {"ready", "stale", "failed", "running"}
        ready_count = sum(
            1
            for pid in preview_ids
            if readback.get(SchedulePreview, pid).status == "ready"  # type: ignore[union-attr]
        )
        assert ready_count >= 1
    finally:
        readback.close()
        _purge_probe_users()


def test_a3_rollback_removes_flushed_dispositions(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DB publication failure at ready commit — not a proposal-builder boom."""
    _prepare(client, db_session)
    _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])
    real_commit = Session.commit

    def flaky_commit(self: Session) -> None:
        for obj in self.identity_map.values():
            if isinstance(obj, SchedulePreview) and getattr(obj, "status", None) == "ready":
                raise RuntimeError("publication_fail_probe")
        return real_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)
    run_preview(preview_id, db=db_session)
    db_session.expire_all()
    assert db_session.query(TaskOccurrenceDisposition).count() == 0
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] == "failed"


def test_a4_duplicate_miss_idempotent(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    count1 = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .count()
    )
    _ready_preview(client, db_session, monkeypatch)
    count2 = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .count()
    )
    assert count1 == 1
    assert count2 == 1


def test_a5_widen_after_held_suppresses_placement(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    wider = (FIXED_NOW + timedelta(days=2)).isoformat().replace("+00:00", "Z")
    patch = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={
            "expected_revision": _revision(client),
            "start_no_later_at": wider,
        },
    )
    assert patch.status_code == 200, patch.text
    preview = _ready_preview(client, db_session, monkeypatch)
    row = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .one()
    )
    assert row.resolution == RESOLUTION_UNRESOLVED_HELD
    blocks = (preview.get("proposal") or preview.get("proposal_json") or {}).get(
        "proposed_blocks"
    ) or (preview.get("proposal") or {}).get("blocks") or []
    assert not any(b.get("task_id") == task["id"] for b in blocks)


def test_a6_preview_after_prior_held_ready(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    held = client.get("/api/v1/schedule/held-misses")
    assert held.status_code == 200
    assert len(held.json()) >= 1


def test_a7_same_preview_sync_parallel_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dual-barrier race on the same running preview id; collect thread errors."""
    _patch_schedule_clock(monkeypatch)
    _purge_probe_users()
    _owner_id, task_ids, preview_ids = _commit_miss_probe(n_previews=1, n_miss_tasks=1)
    preview_id = preview_ids[0]
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=15)
            run_preview(preview_id)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert errors == [], errors
    readback = SessionLocal()
    try:
        row = readback.get(SchedulePreview, preview_id)
        assert row is not None
        assert row.status == "ready"
        assert (
            readback.query(TaskOccurrenceDisposition)
            .filter(TaskOccurrenceDisposition.task_id == task_ids[0])
            .count()
            == 1
        )
    finally:
        readback.close()
        _purge_probe_users()


def test_a8_max_iter_exhaustion_not_ready(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exhaustion after real staging — uncovered miss persists across bounded loop."""
    _prepare(client, db_session)
    _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])
    monkeypatch.setattr("app.scheduler.preview_orchestration.MAX_ORCHESTRATION_ITER", 1)
    ghost = uuid.uuid4()
    real_miss = __import__(
        "app.services.occurrence_disposition", fromlist=["miss_tasks_from_calculation"]
    ).miss_tasks_from_calculation
    call = {"n": 0}

    def expand_uncovered(result):
        call["n"] += 1
        base = real_miss(result)
        # After staging real miss, keep an uncovered ghost so reconcile cannot converge.
        fact = type(
            "F",
            (),
            {"code": "occurrence_bounds_miss", "params": {}},
        )()
        if call["n"] >= 2:
            return {**base, ghost: fact}
        return base

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration.miss_tasks_from_calculation",
        expand_uncovered,
    )
    run_preview(preview_id, db=db_session)
    db_session.expire_all()
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] == "failed"
    assert db_session.query(TaskOccurrenceDisposition).count() == 0


def test_a9_second_pass_miss_recorded_or_exhaust(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Second-pass new miss: first authoritative pass stages A; reconcile surfaces B."""
    _prepare(client, db_session)
    task_a = _miss_task(client, db_session, title=f"MissA {_uid()}")
    task_b = _miss_task(client, db_session, title=f"MissB {_uid()}")
    id_a = uuid.UUID(task_a["id"])
    id_b = uuid.UUID(task_b["id"])
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])
    real_miss = __import__(
        "app.services.occurrence_disposition", fromlist=["miss_tasks_from_calculation"]
    ).miss_tasks_from_calculation
    calc_passes = {"n": 0}

    def gated_misses(result):
        calc_passes["n"] += 1
        all_misses = real_miss(result)
        # Pass 1 (under-lock calculate): only A. Later passes: A+B so B is second-pass.
        if calc_passes["n"] == 1:
            return {tid: all_misses[tid] for tid in all_misses if tid == id_a}
        return all_misses

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration.miss_tasks_from_calculation",
        gated_misses,
    )
    run_preview(preview_id, db=db_session)
    db_session.expire_all()
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] == "ready"
    assert calc_passes["n"] >= 3  # lock calc + reconcile + (iter2 calc and/or publish path)
    for tid in (id_a, id_b):
        assert (
            db_session.query(TaskOccurrenceDisposition)
            .filter(TaskOccurrenceDisposition.task_id == tid)
            .count()
            == 1
        )


def test_a10_trust_fail_rollback(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trust fail after staging — rolled back; not a pre-stage fail."""
    _prepare(client, db_session)
    _miss_task(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.schedule.dispatch_preview",
        lambda preview_id, sync=False: None,
    )
    started = client.post("/api/v1/schedule/previews")
    preview_id = uuid.UUID(started.json()["id"])
    staged_seen = {"n": 0}
    real_stage = __import__(
        "app.services.occurrence_disposition", fromlist=["stage_auto_misses"]
    ).stage_auto_misses

    def counting_stage(*args, **kwargs):
        out = real_stage(*args, **kwargs)
        if out:
            staged_seen["n"] += 1
        return out

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration.stage_auto_misses",
        counting_stage,
    )
    validate_n = {"n": 0}
    real_validate = __import__(
        "app.scheduler.preview_orchestration", fromlist=["_validate_collect"]
    )._validate_collect

    def fail_after_stage(inputs):
        validate_n["n"] += 1
        # 1 = baseline ephemeral, 2 = under-lock live, 3 = post-stage reconcile
        if validate_n["n"] >= 3 and staged_seen["n"] >= 1:
            from app.scheduler.free_busy import BusyInputTrust, BusyInputTrustError

            raise BusyInputTrustError(
                "blocked_after_stage",
                BusyInputTrust(ok=False, blocking_diagnostics=[]),
            )
        return real_validate(inputs)

    monkeypatch.setattr(
        "app.scheduler.preview_orchestration._validate_collect",
        fail_after_stage,
    )
    run_preview(preview_id, db=db_session)
    db_session.expire_all()
    assert staged_seen["n"] >= 1
    assert db_session.query(TaskOccurrenceDisposition).count() == 0
    got = client.get(f"/api/v1/schedule/previews/{preview_id}")
    assert got.json()["status"] == "failed"


def test_apply_gate_occurrence_disposition_stale(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    blocks_before = (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.owner_id == _owner_id(client))
        .count()
    )
    row = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .one()
    )
    row.episode_key = f"mutated-{_uid()}"
    db_session.flush()
    rejected = client.post(f"/api/v1/schedule/previews/{preview['id']}/apply")
    assert rejected.status_code == 409, rejected.text
    body = rejected.json()
    assert body["code"] == "PREVIEW_STALE"
    assert STALE_OCCURRENCE_DISPOSITION in body.get("stale_categories", [])
    assert (
        db_session.query(ScheduledBlock)
        .filter(ScheduledBlock.owner_id == _owner_id(client))
        .count()
        == blocks_before
    )


def test_fresh_session_readback_after_ready(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    preview = _ready_preview(client, db_session, monkeypatch)
    assert preview["status"] == "ready"
    fresh = _fresh_session_on(db_session.connection())
    try:
        rows = (
            fresh.query(TaskOccurrenceDisposition)
            .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
            .all()
        )
        assert len(rows) == 1
        assert rows[0].resolution == RESOLUTION_UNRESOLVED_HELD
        assert any(e.event_type == EVENT_MISS_DETECTED for e in rows[0].events)
    finally:
        fresh.close()


def test_leave_held_audit_no_revision_change(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    rev = _revision(client)
    resp = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/leave-held",
        json={"expected_revision": rev, "note": "still held"},
    )
    assert resp.status_code == 200, resp.text
    events = [e["event_type"] for e in resp.json()["events"]]
    assert EVENT_LEAVE_HELD in events
    assert resp.json()["resolution"] == RESOLUTION_UNRESOLVED_HELD
    assert _revision(client) == rev


def test_owner_isolation_held_list(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    other = User(
        email=f"other-t2s2-{_uid()}@example.com",
        username=f"other-t2s2-{_uid()}",
        display_name="Other",
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        session_epoch=0,
    )
    db_session.add(other)
    db_session.flush()
    foreign_task = Task(
        owner_id=other.id,
        title="foreign miss",
        estimated_duration_minutes=30,
        schedule_style=ScheduleStyle.standalone,
    )
    db_session.add(foreign_task)
    db_session.flush()
    db_session.add(
        TaskOccurrenceDisposition(
            owner_id=other.id,
            task_id=foreign_task.id,
            episode_key="foreign-ep",
            resolution=RESOLUTION_UNRESOLVED_HELD,
            bounds_snapshot={},
            miss_reason_code="occurrence_bounds_miss",
        )
    )
    db_session.flush()
    held = client.get("/api/v1/schedule/held-misses")
    assert held.status_code == 200
    ids = {row["task_id"] for row in held.json()}
    assert task["id"] in ids
    assert str(foreign_task.id) not in ids


def test_cli_held_list_and_leave(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from theplan.commands.schedule import run_schedule
    from theplan.main import _build_parser
    from theplan.output import set_output_format

    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    _bind_cli_to_client(client, monkeypatch)
    set_output_format("json")
    run_schedule(_build_parser().parse_args(["schedule", "held", "list"]))
    listed = json.loads(capsys.readouterr().out)
    assert listed["ok"] is True
    assert listed["count"] >= 1
    assert any(row.get("task_id") == task["id"] for row in listed["items"])
    run_schedule(
        _build_parser().parse_args(
            [
                "schedule",
                "held",
                "leave",
                "--task-id",
                task["id"],
                "--expected-revision",
                str(_revision(client)),
                "--note",
                "cli-leave",
            ]
        )
    )
    left = json.loads(capsys.readouterr().out)
    assert left["ok"] is True
    assert left["resolution"] == RESOLUTION_UNRESOLVED_HELD
    assert any(e.get("event_type") == EVENT_LEAVE_HELD for e in left.get("events") or [])


def test_pure_calculate_no_disposition_write(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    _miss_task(client, db_session)
    owner_id = _owner_id(client)
    before = db_session.query(TaskOccurrenceDisposition).count()
    inputs = collect_inputs(db_session, owner_id, FIXED_NOW)
    calculate(db_session, inputs)
    db_session.flush()
    assert db_session.query(TaskOccurrenceDisposition).count() == before


def test_structured_stale_occurrence_disposition_category() -> None:
    stored = {
        "v": 4,
        "occurrence_disposition": normalize_occurrence_disposition(None, None),
        "duration": {"estimated_duration_minutes": 60},
    }
    live = {
        "v": 4,
        "occurrence_disposition": normalize_occurrence_disposition(
            RESOLUTION_UNRESOLVED_HELD, "ep"
        ),
        "duration": {"estimated_duration_minutes": 60},
    }
    cats = diff_stale_categories(stored, live)
    assert STALE_OCCURRENCE_DISPOSITION in cats


def test_auto_records_miss_detected_event(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    task = _miss_task(client, db_session)
    _ready_preview(client, db_session, monkeypatch)
    row = (
        db_session.query(TaskOccurrenceDisposition)
        .filter(TaskOccurrenceDisposition.task_id == uuid.UUID(task["id"]))
        .one()
    )
    assert any(e.event_type == EVENT_MISS_DETECTED for e in row.events)


def test_literal_accepts_occurrence_disposition_category() -> None:
    from app.schemas.schedule import ScheduleRunStaleSummary

    summary = ScheduleRunStaleSummary(
        stale_task_count=1,
        categories=["occurrence_disposition"],
        total_explanations=1,
    )
    assert summary.categories == ["occurrence_disposition"]
