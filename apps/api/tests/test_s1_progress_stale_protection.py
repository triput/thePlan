"""S1-D2 / S1-D3: scheduling_revision on progress and remaining-only PATCH."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Task, User, UserSettings
from app.services.task_progress import append_progress_entry


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_task(client: TestClient, title: str, **extra: object) -> dict:
    response = client.post("/api/v1/tasks", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _scheduling_revision(db: Session, owner_id: uuid.UUID) -> int:
    settings = db.query(UserSettings).filter(UserSettings.owner_id == owner_id).one()
    return int(settings.scheduling_revision)


def test_progress_requires_expected_revision(client: TestClient) -> None:
    task = _create_task(client, f"rev-req-{_uid()}", estimated_duration_minutes=60)
    response = client.post(
        f"/api/v1/tasks/{task['id']}/progress-entries",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": 5,
            "remaining_minutes": 50,
        },
    )
    assert response.status_code == 422, response.text


def test_progress_stale_revision_rejected(
    client: TestClient, db_session: Session
) -> None:
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task = _create_task(client, f"stale-prog-{_uid()}", estimated_duration_minutes=60)
    task_id = uuid.UUID(task["id"])
    prepared_rev = _scheduling_revision(db_session, owner_id)

    client.post(
        f"/api/v1/tasks/{task_id}/progress-entries",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": 10,
            "remaining_minutes": 40,
            "expected_revision": prepared_rev,
        },
    )
    assert _scheduling_revision(db_session, owner_id) == prepared_rev + 1

    before_entries = db_session.execute(
        text("SELECT count(*) FROM task_progress_entries WHERE task_id = :tid"),
        {"tid": task_id},
    ).scalar()
    stale = client.post(
        f"/api/v1/tasks/{task_id}/progress-entries",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "minutes_worked": 5,
            "remaining_minutes": 1,
            "expected_revision": prepared_rev,
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "SCHEDULING_REVISION_CONFLICT"
    after_entries = db_session.execute(
        text("SELECT count(*) FROM task_progress_entries WHERE task_id = :tid"),
        {"tid": task_id},
    ).scalar()
    assert after_entries == before_entries
    row = db_session.get(Task, task_id)
    assert row is not None
    assert row.worked_minutes == 10
    assert row.remaining_minutes == 40


def test_progress_idempotent_retry_same_key(
    client: TestClient, db_session: Session
) -> None:
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task = _create_task(client, f"idem-prog-{_uid()}", estimated_duration_minutes=30)
    key = uuid.uuid4()
    rev = _scheduling_revision(db_session, owner_id)
    payload = {
        "idempotency_key": str(key),
        "minutes_worked": 6,
        "remaining_minutes": 20,
        "expected_revision": rev,
    }
    first = client.post(f"/api/v1/tasks/{task['id']}/progress-entries", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["replayed"] is False
    rev_after = first.json()["scheduling_revision"]

    retry = client.post(f"/api/v1/tasks/{task['id']}/progress-entries", json=payload)
    assert retry.status_code == 200, retry.text
    assert retry.json()["replayed"] is True
    assert retry.json()["scheduling_revision"] == rev_after
    count = db_session.execute(
        text("SELECT count(*) FROM task_progress_entries WHERE idempotency_key = :k"),
        {"k": key},
    ).scalar()
    assert count == 1


def test_patch_remaining_requires_expected_revision(client: TestClient) -> None:
    task = _create_task(client, f"patch-rev-req-{_uid()}", estimated_duration_minutes=40)
    response = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"remaining_estimate_minutes": 35},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SCHEDULING_REVISION_REQUIRED"


def test_patch_remaining_stale_revision_rejected(
    client: TestClient, db_session: Session
) -> None:
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task = _create_task(client, f"stale-patch-{_uid()}", estimated_duration_minutes=50)
    task_id = task["id"]
    prepared_rev = _scheduling_revision(db_session, owner_id)

    ok = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"remaining_estimate_minutes": 45, "expected_revision": prepared_rev},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["remaining_estimate_minutes"] == 45

    stale = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"remaining_estimate_minutes": 10, "expected_revision": prepared_rev},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "SCHEDULING_REVISION_CONFLICT"
    read_back = client.get(f"/api/v1/tasks/{task_id}")
    assert read_back.json()["remaining_estimate_minutes"] == 45


def test_progress_increments_from_db_not_stale_identity_map(
    db_session: Session, client: TestClient
) -> None:
    user = db_session.get(User, uuid.UUID(client.get("/api/v1/auth/me").json()["id"]))
    assert user is not None
    task_body = _create_task(client, f"atomic-{_uid()}", estimated_duration_minutes=100)
    task_id = uuid.UUID(task_body["id"])
    rev = _scheduling_revision(db_session, user.id)

    stale_task = db_session.get(Task, task_id)
    assert stale_task is not None
    db_session.execute(
        text("UPDATE tasks SET worked_minutes = 20 WHERE id = :id"),
        {"id": task_id},
    )
    assert stale_task.worked_minutes == 0

    entry, _, replayed = append_progress_entry(
        db_session,
        user,
        stale_task,
        idempotency_key=uuid.uuid4(),
        minutes_worked=30,
        remaining_minutes=70,
        expected_revision=rev,
        note=None,
    )
    assert replayed is False
    assert entry.minutes_worked == 30
    db_session.refresh(stale_task)
    assert stale_task.worked_minutes == 50
    assert stale_task.remaining_minutes == 70
