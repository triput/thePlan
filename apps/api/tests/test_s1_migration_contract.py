"""S1 first-slice migration and API guards (contract §10 item 7).

Covers SS-01 (028 seed does not rewrite blocks, fingerprint JSON, or
scheduling_revision), progress init, original-estimate reject, chunking-write
reject, and General/Working/Personal seed read-back. Not S2 and not SS-30.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import (
    AvailabilityPolicy,
    SchedulePreview,
    ScheduleRun,
    ScheduleTaskOutcome,
    ScheduledBlock,
    Task,
    User,
    UserSettings,
)
from app.models.enums import AvailabilityPolicySlug
from app.schemas.availability import SCHEDULING_CONFIG_ONLY_COPY
from app.services.availability_seed import ensure_default_availability_policies

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "028_availability_progress.py"
)
_FORBIDDEN_DML = (
    "scheduled_blocks",
    "schedule_task_outcomes",
    "schedule_previews",
    "scheduling_revision",
    "input_fingerprint",
    "input_snapshot",
    "task_progress_entries",
    "worked_minutes",
)


def _migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_028_availability_progress", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_dml() -> list[str]:
    """Return INSERT/UPDATE/DELETE strings inside 028 upgrade(), source order."""
    module = _migration_module()
    tree = ast.parse(Path(_MIGRATION_PATH).read_text(encoding="utf-8"))
    upgrade = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    found: list[str] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str):
                sql = node.value.strip()
                head = sql.split(None, 1)[0].upper() if sql else ""
                if head in {"INSERT", "UPDATE", "DELETE"}:
                    found.append(sql)
            self.generic_visit(node)

    _Visitor().visit(upgrade)
    assert module.revision == "028_availability_progress"
    return found


def _rows(db: Session, sql: str) -> list[tuple]:
    return [tuple(row) for row in db.execute(text(sql))]


def _protected_snapshot(db: Session) -> dict[str, list[tuple] | int]:
    return {
        "blocks": _rows(
            db,
            """
            SELECT id::text, owner_id::text, task_id::text,
                   start_time, end_time, is_pinned, bundle_meta::text,
                   created_at, updated_at
            FROM scheduled_blocks
            ORDER BY id
            """,
        ),
        "outcomes": _rows(
            db,
            """
            SELECT id::text, input_fingerprint, input_snapshot::text,
                   reason_facts::text, placement_facts::text, algorithm_version
            FROM schedule_task_outcomes
            ORDER BY id
            """,
        ),
        "previews": _rows(
            db,
            """
            SELECT id::text, scheduling_revision, input_fingerprint,
                   input_snapshot::text, proposal_json::text
            FROM schedule_previews
            ORDER BY id
            """,
        ),
        "revisions": _rows(
            db,
            """
            SELECT owner_id::text, scheduling_revision
            FROM user_settings
            ORDER BY owner_id
            """,
        ),
        "task_columns": _rows(
            db,
            """
            SELECT id::text, estimated_duration_minutes, worked_minutes,
                   min_block_duration_minutes, max_block_duration_minutes,
                   max_block_unbounded, keep_in_one_block, is_completed,
                   deleted_at
            FROM tasks
            ORDER BY id
            """,
        ),
        "progress_entries": _rows(
            db,
            """
            SELECT id::text, task_id::text, owner_id::text,
                   minutes_worked, remaining_minutes, note
            FROM task_progress_entries
            ORDER BY id
            """,
        ),
    }


def _require_s1_head(db: Session) -> None:
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "030_progress_intent_hash", (
        f"test database alembic version is {version!r}; "
        "upgrade the disposable test database to 030_progress_intent_hash before this suite"
    )


def _replay_028_seed(db: Session) -> None:
    """Re-run 028's data statements. Schema is already at head; rows are not."""
    db.execute(text("DELETE FROM availability_windows"))
    db.execute(text("DELETE FROM availability_policies"))
    db.flush()
    for statement in _upgrade_dml():
        db.execute(text(statement))
    db.flush()
    db.expire_all()


@dataclass
class Seeded:
    owner_id: uuid.UUID
    open_task_id: uuid.UUID
    completed_task_id: uuid.UUID
    trashed_task_id: uuid.UUID
    logged_task_id: uuid.UUID
    overnight_owner_id: uuid.UUID
    before: dict[str, list[tuple] | int]


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, title: str, **extra) -> dict:
    response = client.post("/api/v1/tasks", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def seeded(client: TestClient, db_session: Session) -> Seeded:
    """Plant pre-seed rows, replay 028 DML inside the rolled-back test transaction."""
    _require_s1_head(db_session)
    me = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == me).one()
    settings.workweek_days = 3
    settings.workday_start_local = time(10, 0)
    settings.workday_minutes = 360
    settings.scheduling_revision = 42

    open_task = _create_task(client, f"s1-open-{_uid()}", estimated_duration_minutes=90)
    completed_body = _create_task(
        client, f"s1-done-{_uid()}", estimated_duration_minutes=45
    )
    trashed_body = _create_task(client, f"s1-trash-{_uid()}", estimated_duration_minutes=20)
    logged_body = _create_task(client, f"s1-logged-{_uid()}", estimated_duration_minutes=80)

    open_id = uuid.UUID(open_task["id"])
    completed_id = uuid.UUID(completed_body["id"])
    trashed_id = uuid.UUID(trashed_body["id"])
    logged_id = uuid.UUID(logged_body["id"])

    completed = db_session.get(Task, completed_id)
    trashed = db_session.get(Task, trashed_id)
    assert completed is not None and trashed is not None
    completed.is_completed = True
    completed.completed_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    completed.min_block_duration_minutes = 30
    completed.max_block_duration_minutes = 90
    trashed.deleted_at = datetime(2026, 10, 2, tzinfo=timezone.utc)
    trashed.min_block_duration_minutes = 15
    trashed.max_block_duration_minutes = 120
    db_session.flush()

    # Simulate columns that exist but have not been backfilled yet.
    db_session.execute(
        text(
            """
            UPDATE tasks
            SET remaining_minutes = NULL, worked_minutes = 0
            WHERE id IN (:open_id, :completed_id, :trashed_id)
            """
        ),
        {"open_id": open_id, "completed_id": completed_id, "trashed_id": trashed_id},
    )

    db_session.refresh(settings)
    progress = client.post(
        f"/api/v1/tasks/{logged_id}/progress-entries",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": 4,
            "remaining_minutes": 12,
            "expected_revision": settings.scheduling_revision,
        },
    )
    assert progress.status_code == 200, progress.text
    assert progress.json()["time_worked_minutes"] == 4
    assert progress.json()["remaining_estimate_minutes"] == 12
    assert progress.json()["original_estimate_minutes"] == 80

    # Progress logging bumps revision. Pin it again so the seed must not move it.
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == me).one()
    settings.scheduling_revision = 42

    pin_start = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc)
    block = ScheduledBlock(
        owner_id=me,
        task_id=open_id,
        start_time=pin_start,
        end_time=pin_start + timedelta(minutes=60),
        is_pinned=True,
        bundle_meta={"s1": "leave-me"},
    )
    run = ScheduleRun(
        owner_id=me,
        status="completed",
        finished_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    db_session.add(block)
    db_session.add(run)
    db_session.flush()
    fingerprint = {
        "version": 3,
        "duration": {"estimated": 90, "sentinel": "s1-do-not-rewrite"},
    }
    db_session.add(
        ScheduleTaskOutcome(
            schedule_run_id=run.id,
            owner_id=me,
            task_id=open_id,
            requested_minutes=90,
            pinned_minutes=60,
            placed_minutes=0,
            remaining_minutes=90,
            primary_reason_code="unplaced_horizon_exhausted",
            reason_facts=[{"code": "unplaced_horizon_exhausted", "params": {"remaining_minutes": 90}}],
            summary_text="s1 fingerprint sentinel",
            outcome="unplaced",
            input_fingerprint="s1-fingerprint-sentinel",
            input_snapshot=fingerprint,
            algorithm_version="v3",
        )
    )
    db_session.add(
        SchedulePreview(
            owner_id=me,
            status="ready",
            scheduling_revision=42,
            input_fingerprint="s1-preview-fingerprint",
            input_snapshot=fingerprint,
            proposal_json={"blocks": [{"keep": True}], "fingerprint": "s1-preview-fingerprint"},
        )
    )

    overnight = User(email=f"s1-night-{_uid()}@example.com", username=f"s1n{_uid()}")
    db_session.add(overnight)
    db_session.flush()
    # 028's window INSERT still skips workweek_days = 0 (`spec.workweek_days > 0`).
    # This fixture uses 1 so the replay inserts an overnight window. Storing 0
    # is legal after 029; that is not what this seed case checks.
    db_session.add(
        UserSettings(
            owner_id=overnight.id,
            workweek_days=1,
            workday_start_local=time(22, 0),
            workday_minutes=180,
            scheduling_revision=7,
        )
    )
    db_session.flush()

    before = _protected_snapshot(db_session)
    _replay_028_seed(db_session)
    return Seeded(
        owner_id=me,
        open_task_id=open_id,
        completed_task_id=completed_id,
        trashed_task_id=trashed_id,
        logged_task_id=logged_id,
        overnight_owner_id=overnight.id,
        before=before,
    )


def _policy(db: Session, owner_id: uuid.UUID, slug: AvailabilityPolicySlug) -> AvailabilityPolicy:
    policy = (
        db.query(AvailabilityPolicy)
        .filter(AvailabilityPolicy.owner_id == owner_id, AvailabilityPolicy.slug == slug)
        .one()
    )
    return policy


def test_028_seed_dml_does_not_name_blocks_fingerprints_or_revision() -> None:
    statements = _upgrade_dml()
    assert len(statements) == 4
    normalized = [" ".join(sql.split()) for sql in statements]
    assert normalized[0].lower().startswith("update user_settings")
    assert "nominal_workday_minutes = workday_minutes" in normalized[0].lower()
    assert "where nominal_workday_minutes is null" in normalized[0].lower()
    assert normalized[1].lower().startswith("update tasks")
    assert "when is_completed then 0" in normalized[1].lower()
    assert "else estimated_duration_minutes" in normalized[1].lower()
    assert "where remaining_minutes is null" in normalized[1].lower()
    assert normalized[2].lower().startswith("insert into availability_policies")
    assert normalized[3].lower().startswith("insert into availability_windows")
    assert "spec.workweek_days > 0" in normalized[3].lower()
    blob = "\n".join(normalized).lower()
    for forbidden in _FORBIDDEN_DML:
        assert forbidden not in blob, forbidden
    source = Path(_MIGRATION_PATH).read_text(encoding="utf-8")
    assert 'sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0")' in source


def test_ss01_seed_does_not_rewrite_blocks_fingerprints_or_revision(
    db_session: Session, seeded: Seeded
) -> None:
    after = _protected_snapshot(db_session)
    assert after["blocks"] == seeded.before["blocks"]
    assert after["blocks"], "seed fixture must plant at least one scheduled block"
    assert after["outcomes"] == seeded.before["outcomes"]
    assert after["previews"] == seeded.before["previews"]
    assert after["revisions"] == seeded.before["revisions"]
    assert after["task_columns"] == seeded.before["task_columns"]
    assert after["progress_entries"] == seeded.before["progress_entries"]
    revisions = {owner: revision for owner, revision in after["revisions"]}
    assert revisions[str(seeded.owner_id)] == 42
    assert revisions[str(seeded.overnight_owner_id)] == 7
    pinned = [row for row in after["blocks"] if row[2] == str(seeded.open_task_id)]
    assert len(pinned) == 1
    assert pinned[0][5] is True
    assert json.loads(pinned[0][6]) == {"s1": "leave-me"}


def test_progress_init_existing_tasks_no_invented_log(
    client: TestClient, db_session: Session, seeded: Seeded
) -> None:
    open_task = db_session.get(Task, seeded.open_task_id)
    completed = db_session.get(Task, seeded.completed_task_id)
    trashed = db_session.get(Task, seeded.trashed_task_id)
    logged = db_session.get(Task, seeded.logged_task_id)
    assert open_task is not None and completed is not None
    assert trashed is not None and logged is not None

    assert open_task.worked_minutes == 0
    assert open_task.remaining_minutes == 90
    assert open_task.estimated_duration_minutes == 90
    assert open_task.is_completed is False

    assert completed.worked_minutes == 0
    assert completed.remaining_minutes == 0
    assert completed.estimated_duration_minutes == 45
    assert completed.is_completed is True
    assert completed.min_block_duration_minutes == 30
    assert completed.max_block_duration_minutes == 90

    assert trashed.worked_minutes == 0
    assert trashed.remaining_minutes == 20
    assert trashed.estimated_duration_minutes == 20
    assert trashed.deleted_at is not None
    assert trashed.min_block_duration_minutes == 15
    assert trashed.max_block_duration_minutes == 120
    assert trashed.max_block_unbounded is False
    assert trashed.keep_in_one_block is False

    # An already-initialized task is not reset, and seed does not invent log rows.
    assert logged.worked_minutes == 4
    assert logged.remaining_minutes == 12
    assert logged.estimated_duration_minutes == 80
    after_entries = _protected_snapshot(db_session)["progress_entries"]
    assert after_entries == seeded.before["progress_entries"]
    logged_entries = [row for row in after_entries if row[1] == str(seeded.logged_task_id)]
    assert len(logged_entries) == 1
    assert logged_entries[0][3] == 4
    assert logged_entries[0][4] == 12
    for task_id in (seeded.open_task_id, seeded.completed_task_id, seeded.trashed_task_id):
        assert not [row for row in after_entries if row[1] == str(task_id)]

    read_back = client.get(f"/api/v1/tasks/{seeded.open_task_id}")
    assert read_back.status_code == 200, read_back.text
    body = read_back.json()
    assert body["original_estimate_minutes"] == 90
    assert body["time_worked_minutes"] == 0
    assert body["remaining_estimate_minutes"] == 90
    assert body["estimated_duration_minutes"] == 90

    done = client.get(f"/api/v1/tasks/{seeded.completed_task_id}")
    assert done.status_code == 200, done.text
    done_body = done.json()
    assert done_body["time_worked_minutes"] == 0
    assert done_body["remaining_estimate_minutes"] == 0
    assert done_body["original_estimate_minutes"] == 45


def test_general_work_seed_readback_personal_empty_not_effective(
    client: TestClient, db_session: Session, seeded: Seeded
) -> None:
    def _windows(owner_id: uuid.UUID, slug: AvailabilityPolicySlug) -> list:
        policy = _policy(db_session, owner_id, slug)
        db_session.refresh(policy)
        return list(policy.windows)

    general = _windows(seeded.owner_id, AvailabilityPolicySlug.general)
    work = _windows(seeded.owner_id, AvailabilityPolicySlug.work)
    personal = _windows(seeded.owner_id, AvailabilityPolicySlug.personal)
    assert [(row.weekday, row.start_time, row.end_time, row.duration_minutes, row.ends_next_day) for row in general] == [
        (day, time(10, 0), time(16, 0), 360, False) for day in (0, 1, 2)
    ]
    assert [(row.weekday, row.start_time, row.duration_minutes, row.ends_next_day) for row in work] == [
        (day, time(10, 0), 360, False) for day in (0, 1, 2)
    ]
    assert {row.id for row in general}.isdisjoint({row.id for row in work})
    assert personal == []

    night_work = _windows(seeded.overnight_owner_id, AvailabilityPolicySlug.work)
    night_general = _windows(seeded.overnight_owner_id, AvailabilityPolicySlug.general)
    assert len(night_work) == 1 and len(night_general) == 1
    assert night_work[0].weekday == 0
    assert night_work[0].start_time == time(22, 0)
    assert night_work[0].end_time == time(1, 0)
    assert night_work[0].ends_next_day is True
    assert night_work[0].duration_minutes == 180
    assert night_work[0].id != night_general[0].id
    assert _windows(seeded.overnight_owner_id, AvailabilityPolicySlug.personal) == []
    assert _policy(db_session, seeded.overnight_owner_id, AvailabilityPolicySlug.personal).name == "Personal"

    for slug in ("general", "work"):
        listed = client.get("/api/v1/availability-policies", params={"slug": slug})
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["slug"] == slug
        assert rows[0]["scheduling_effective"] is False
        assert rows[0]["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY
        assert len(rows[0]["windows"]) == 3

        fetched = client.get(f"/api/v1/availability-policies/{slug}")
        assert fetched.status_code == 200, fetched.text
        body = fetched.json()
        assert body["scheduling_effective"] is False
        assert body["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY
        assert [window["weekday"] for window in body["windows"]] == [0, 1, 2]
        assert body["windows"][0]["start_time"] == "10:00"
        assert body["windows"][0]["end_time"] == "16:00"
        assert body["windows"][0]["duration_minutes"] == 360
        assert body["windows"][0]["ends_next_day"] is False

        effective = client.get(
            f"/api/v1/availability-policies/{slug}/effective",
            params={"on": "2026-10-12"},
        )
        assert effective.status_code == 200, effective.text
        effective_body = effective.json()
        assert effective_body["scheduling_effective"] is False
        assert effective_body["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY
        assert effective_body["on_date"] == "2026-10-12"
        assert len(effective_body["windows"]) == 1
        assert any("Placer does not consume" in line for line in effective_body["provenance"])

        weekend = client.get(
            f"/api/v1/availability-policies/{slug}/effective",
            params={"on": "2026-10-17"},
        )
        assert weekend.status_code == 200, weekend.text
        assert weekend.json()["scheduling_effective"] is False
        assert weekend.json()["windows"] == []

    personal_get = client.get("/api/v1/availability-policies/personal")
    assert personal_get.status_code == 200, personal_get.text
    assert personal_get.json()["windows"] == []
    assert personal_get.json()["scheduling_effective"] is False
    assert personal_get.json()["scheduling_effective_note"] == SCHEDULING_CONFIG_ONLY_COPY

    personal_effective = client.get(
        "/api/v1/availability-policies/personal/effective",
        params={"on": "2026-10-12"},
    )
    assert personal_effective.status_code == 200, personal_effective.text
    assert personal_effective.json()["scheduling_effective"] is False
    assert personal_effective.json()["windows"] == []


def test_fresh_account_seed_does_not_touch_blocks_or_revision(db_session: Session) -> None:
    _require_s1_head(db_session)
    owner = User(email=f"s1-fresh-{_uid()}@example.com", username=f"s1f{_uid()}")
    db_session.add(owner)
    db_session.flush()
    db_session.add(
        UserSettings(
            owner_id=owner.id,
            workweek_days=2,
            workday_start_local=time(8, 0),
            workday_minutes=300,
            scheduling_revision=11,
        )
    )
    task = Task(
        owner_id=owner.id,
        title="fresh seed block host",
        estimated_duration_minutes=50,
        worked_minutes=0,
        remaining_minutes=50,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
    )
    db_session.add(task)
    db_session.flush()
    start = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
    db_session.add(
        ScheduledBlock(
            owner_id=owner.id,
            task_id=task.id,
            start_time=start,
            end_time=start + timedelta(minutes=25),
            is_pinned=True,
        )
    )
    db_session.flush()
    before = _protected_snapshot(db_session)
    created = ensure_default_availability_policies(db_session, owner.id)
    db_session.flush()
    db_session.expire_all()
    assert [policy.slug for policy in created] == [
        AvailabilityPolicySlug.general,
        AvailabilityPolicySlug.work,
        AvailabilityPolicySlug.personal,
    ]
    assert ensure_default_availability_policies(db_session, owner.id) == []
    after = _protected_snapshot(db_session)
    assert after["blocks"] == before["blocks"]
    assert after["outcomes"] == before["outcomes"]
    assert after["previews"] == before["previews"]
    assert after["revisions"] == before["revisions"]
    assert after["progress_entries"] == before["progress_entries"]
    assert after["task_columns"] == before["task_columns"]

    general = _policy(db_session, owner.id, AvailabilityPolicySlug.general)
    work = _policy(db_session, owner.id, AvailabilityPolicySlug.work)
    personal = _policy(db_session, owner.id, AvailabilityPolicySlug.personal)
    db_session.refresh(general)
    db_session.refresh(work)
    db_session.refresh(personal)
    expected = [(day, time(9, 0), time(17, 0), 480, False) for day in range(5)]

    def shape(rows: list) -> list[tuple]:
        return [
            (row.weekday, row.start_time, row.end_time, row.duration_minutes, row.ends_next_day)
            for row in rows
        ]

    assert shape(general.windows) == expected
    assert shape(work.windows) == expected
    assert {row.id for row in general.windows}.isdisjoint({row.id for row in work.windows})
    assert list(personal.windows) == []


def test_patch_changed_original_estimate_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    task = _create_task(client, f"s1-immutable-{_uid()}", estimated_duration_minutes=40)
    task_id = task["id"]
    before_entries = db_session.execute(text("SELECT count(*) FROM task_progress_entries")).scalar()

    changed = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"estimated_duration_minutes": 55},
    )
    assert changed.status_code == 422, changed.text
    body = changed.json()
    assert body["code"] == "ORIGINAL_ESTIMATE_IMMUTABLE"
    detail = body["detail"].lower()
    assert "remaining" in detail
    assert "progress" in detail

    read_back = client.get(f"/api/v1/tasks/{task_id}")
    assert read_back.status_code == 200, read_back.text
    current = read_back.json()
    assert current["estimated_duration_minutes"] == 40
    assert current["original_estimate_minutes"] == 40
    assert current["remaining_estimate_minutes"] == 40
    assert current["time_worked_minutes"] == 0
    after_entries = db_session.execute(text("SELECT count(*) FROM task_progress_entries")).scalar()
    assert after_entries == before_entries

    batch = client.patch(
        "/api/v1/tasks/batch",
        json={"task_ids": [task_id], "patch": {"estimated_duration_minutes": 70}},
    )
    assert batch.status_code == 422, batch.text
    assert batch.json()["code"] == "ORIGINAL_ESTIMATE_IMMUTABLE"
    still = client.get(f"/api/v1/tasks/{task_id}")
    assert still.json()["estimated_duration_minutes"] == 40
    assert still.json()["remaining_estimate_minutes"] == 40


def test_patch_same_original_estimate_is_accepted(client: TestClient) -> None:
    task = _create_task(client, f"s1-same-{_uid()}", estimated_duration_minutes=40)
    same = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"estimated_duration_minutes": 40},
    )
    assert same.status_code == 200, same.text
    body = same.json()
    assert body["estimated_duration_minutes"] == 40
    assert body["original_estimate_minutes"] == 40
    assert body["remaining_estimate_minutes"] == 40
    assert body["time_worked_minutes"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"min_block_duration_minutes": None},
        {"max_block_duration_minutes": None},
        {"max_block_unbounded": True},
        {"keep_in_one_block": True},
    ],
)
def test_chunking_cutover_writes_are_rejected(
    client: TestClient, db_session: Session, payload: dict
) -> None:
    task = _create_task(client, f"s1-chunk-{_uid()}", estimated_duration_minutes=30)
    task_id = uuid.UUID(task["id"])
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    settings = db_session.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    revision_before = settings.scheduling_revision

    response = client.patch(f"/api/v1/tasks/{task_id}", json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "CHUNKING_CUTOVER_PENDING"

    stored = db_session.get(Task, task_id)
    assert stored is not None
    db_session.refresh(stored)
    assert stored.min_block_duration_minutes == 15
    assert stored.max_block_duration_minutes == 120
    assert stored.max_block_unbounded is False
    assert stored.keep_in_one_block is False
    db_session.refresh(settings)
    assert settings.scheduling_revision == revision_before


def test_explicit_numeric_bounds_remain_writable(client: TestClient, db_session: Session) -> None:
    task = _create_task(client, f"s1-bounds-{_uid()}", estimated_duration_minutes=30)
    task_id = uuid.UUID(task["id"])
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "min_block_duration_minutes": 25,
            "max_block_duration_minutes": 100,
            "max_block_unbounded": False,
            "keep_in_one_block": False,
        },
    )
    assert response.status_code == 200, response.text
    stored = db_session.get(Task, task_id)
    assert stored is not None
    db_session.refresh(stored)
    assert stored.min_block_duration_minutes == 25
    assert stored.max_block_duration_minutes == 100
    assert stored.max_block_unbounded is False
    assert stored.keep_in_one_block is False
