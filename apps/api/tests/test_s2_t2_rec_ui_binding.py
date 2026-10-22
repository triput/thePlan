"""T2-REC-UI API binding + true read-only review (disposable theplan_s1_test @ :5433).

Matrix A-BIND* / A-RO* / A-Z* against accepted contract
``0.7-S2-T2-REC-UI-Integration-Contract-2026-10-21.md``. No household :8000.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Task, TaskOccurrenceDisposition, UserSettings
from app.models.task_occurrence_disposition import (
    EVENT_MISS_DETECTED,
    RESOLUTION_RECOVERED,
    RESOLUTION_RELEASED,
    RESOLUTION_UNRESOLVED_HELD,
    DispositionEvent,
    ProgressEpochMembership,
)
from app.services.occurrence_disposition import (
    observe_session_writes,
    recover_held,
    review_recover_held,
)
from test_s2_t2_rec_recovery import (
    FIXED_NOW,
    _AUG18,
    _CATCH_DEADLINE,
    _CATCH_DUE,
    _CATCH_EARLIEST,
    _CATCH_LATEST,
    _CATCH_UP_FIELD_SET,
    _books,
    _catch_up_body,
    _catch_up_named,
    _hold,
    _iso,
    _prepare,
    _recover,
    _review,
    _revision,
    _set_now,
    _task,
    _uid,
)
from test_schedule_replan import _patch_schedule_clock

UTC = timezone.utc
_REQUIRED_DB = "theplan_s1_test"
_REQUIRED_HEAD = "043_recovery_epoch"


@pytest.fixture(autouse=True)
def _disposable_db(db_session: Session) -> None:
    name = db_session.execute(text("SELECT current_database()")).scalar()
    assert name == _REQUIRED_DB
    assert name != "theplan"
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _REQUIRED_HEAD


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_schedule_clock(monkeypatch)
    monkeypatch.setattr(
        "app.services.occurrence_disposition.utc_now",
        lambda: FIXED_NOW,
    )


def _counts(db: Session, owner_id: uuid.UUID, task_id: uuid.UUID) -> dict[str, int]:
    return {
        "tasks": db.query(Task).filter(Task.owner_id == owner_id).count(),
        "events": (
            db.query(DispositionEvent)
            .join(TaskOccurrenceDisposition)
            .filter(TaskOccurrenceDisposition.task_id == task_id)
            .count()
        ),
        "memberships": (
            db.query(ProgressEpochMembership)
            .filter(ProgressEpochMembership.task_id == task_id)
            .count()
        ),
        "rev": int(
            db.query(UserSettings)
            .filter(UserSettings.owner_id == owner_id)
            .one()
            .scheduling_revision
        ),
    }


def test_a_bind1_review_then_authorize_happy(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    rev = _review(client, task["id"], row.id)
    assert rev.status_code == 200, rev.text
    body = rev.json()
    assert body["contract_version"] == "t2-rec-ui-v1"
    assert body["review_binding"]
    assert body["authorize_instant"]
    assert body["review_ok_for_authorize"] is True
    assert body["eligibility"]["recurring"] is True
    assert body["cadence"]["timezone"] == "UTC"
    assert body["next_normal"]["due_at"] is not None
    auth = _recover(
        client,
        task["id"],
        row.id,
        review_binding=body["review_binding"],
        authorize_instant=body["authorize_instant"],
    )
    assert auth.status_code == 200, auth.text
    assert auth.json()["resolution"] == "recovered"
    assert _task(db_session, task["id"]).due_at == _AUG18


def test_a_bind2_altered_intent_rejects(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    rev = _review(client, task["id"], row.id)
    assert rev.status_code == 200, rev.text
    body = rev.json()
    tampered = _recover(
        client,
        task["id"],
        row.id,
        review_binding=body["review_binding"],
        authorize_instant=body["authorize_instant"],
        catch_up_remaining_minutes=7,
    )
    assert tampered.status_code == 422, tampered.text
    assert tampered.json()["code"] == "REVIEW_BINDING_MISMATCH"
    assert db_session.get(TaskOccurrenceDisposition, row.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )
    assert _catch_up_named(db_session, task["title"]) == []


def test_a_bind3_cross_review_binding_rejects(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    a = _books(client, title=f"Bind A {_uid()}")
    b = _books(client, title=f"Bind B {_uid()}")
    row_a = _hold(db_session, a["id"])
    row_b = _hold(db_session, b["id"])
    rev_a = _review(client, a["id"], row_a.id)
    rev_b = _review(client, b["id"], row_b.id)
    assert rev_a.status_code == 200 and rev_b.status_code == 200
    mixed = _recover(
        client,
        a["id"],
        row_a.id,
        review_binding=rev_b.json()["review_binding"],
        authorize_instant=rev_a.json()["authorize_instant"],
    )
    assert mixed.status_code == 422, mixed.text
    assert mixed.json()["code"] in {
        "REVIEW_BINDING_MISMATCH",
        "REVIEW_BINDING_INVALID",
    }
    assert db_session.get(TaskOccurrenceDisposition, row_a.id).resolution == (
        RESOLUTION_UNRESOLVED_HELD
    )


def test_a_bind4_fresh_clock_without_bound_instant_no_silent_shift(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    due = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    reviewed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    task = _books(client, title=f"Clock {_uid()}")
    # Rebuild as completion-anchored daily for cadence sensitivity.
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Clock bind {_uid()}",
            "estimated_duration_minutes": 60,
            "priority": "p1",
            "schedule_style": "standalone",
            "due_at": _iso(due),
            "start_no_earlier_at": _iso(due),
            "start_no_later_at": _iso(due + timedelta(hours=2)),
            "deadline_at": _iso(due + timedelta(hours=2, minutes=30)),
            "recurrence": {
                "rrule": "FREQ=DAILY;INTERVAL=1",
                "is_fixed": False,
                "timezone": "UTC",
            },
        },
    ).json()
    row = _hold(db_session, task["id"])
    _set_now(monkeypatch, reviewed)
    rev = _review(client, task["id"], row.id)
    assert rev.status_code == 200, rev.text
    binding = rev.json()["review_binding"]
    auth_instant = rev.json()["authorize_instant"]
    # Later wall clock — authorize must keep bound instant (Aug 11 09:00), not Wed.
    _set_now(monkeypatch, datetime(2026, 8, 10, 18, 0, tzinfo=UTC))
    ok = _recover(
        client,
        task["id"],
        row.id,
        review_binding=binding,
        authorize_instant=auth_instant,
    )
    assert ok.status_code == 200, ok.text
    assert _task(db_session, task["id"]).due_at == datetime(2026, 8, 11, 9, 0, tzinfo=UTC)


def test_a_bind5_invalid_binding_rejects(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    rev = _review(client, task["id"], row.id)
    assert rev.status_code == 200, rev.text
    good = rev.json()["review_binding"]
    truncated = good[:-4]
    bad = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/recover",
        json={
            "disposition_id": str(row.id),
            "expected_revision": _revision(client),
            "review_binding": truncated,
            **_catch_up_body(),
        },
    )
    assert bad.status_code == 422, bad.text
    assert bad.json()["code"] == "REVIEW_BINDING_INVALID"
    missing = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/recover",
        json={
            "disposition_id": str(row.id),
            "expected_revision": _revision(client),
            **_catch_up_body(),
        },
    )
    assert missing.status_code == 422, missing.text


def test_a_ro1_review_leaves_no_writes(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fresh SessionLocal before/after on committed probe head (A-RO1)."""
    from test_s2_t2_rec_recovery import _commit_recurring_probe, _purge_probe_users

    _patch_schedule_clock(monkeypatch)
    monkeypatch.setattr("app.services.occurrence_disposition.utc_now", lambda: FIXED_NOW)
    _purge_probe_users()
    try:
        owner_id, task_id, disp_id, rev, _title = _commit_recurring_probe()
        before = SessionLocal()
        try:
            counts_before = _counts(before, owner_id, task_id)
            assert observe_session_writes(before).empty
        finally:
            before.close()

        review_db = SessionLocal()
        try:
            assert observe_session_writes(review_db).empty
            review_recover_held(
                review_db,
                owner_id=owner_id,
                task_id=task_id,
                disposition_id=disp_id,
                expected_revision=rev,
                catch_up_due_at=_CATCH_DUE,
                catch_up_start_no_earlier_at=_CATCH_EARLIEST,
                catch_up_start_no_later_at=_CATCH_LATEST,
                catch_up_deadline_at=_CATCH_DEADLINE,
                intent_fields_set=_CATCH_UP_FIELD_SET,
            )
            assert observe_session_writes(review_db).empty
            review_db.rollback()
        finally:
            review_db.close()

        after = SessionLocal()
        try:
            counts_after = _counts(after, owner_id, task_id)
            assert observe_session_writes(after).empty
            assert counts_after == counts_before
            row_after = after.get(TaskOccurrenceDisposition, disp_id)
            assert row_after is not None
            assert row_after.resolution == RESOLUTION_UNRESOLVED_HELD
            assert row_after.catch_up_task_id is None
        finally:
            after.close()
    finally:
        _purge_probe_users()


def test_a_ro2_review_exception_path_clean(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    task_id = uuid.UUID(task["id"])
    before = _counts(db_session, owner_id, task_id)
    stale = _review(client, task["id"], row.id, expected_revision=_revision(client) + 9)
    assert stale.status_code == 409, stale.text
    db_session.expire_all()
    after = _counts(db_session, owner_id, task_id)
    assert after == before
    assert observe_session_writes(db_session).empty


def test_a_ro3_cross_owner_review_404(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    victim_owner = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    before = _counts(db_session, victim_owner, uuid.UUID(task["id"]))

    from app.api.errors import ApiError

    denied = SessionLocal()
    try:
        with pytest.raises(ApiError) as caught:
            review_recover_held(
                denied,
                owner_id=uuid.uuid4(),
                task_id=uuid.UUID(task["id"]),
                disposition_id=row.id,
                expected_revision=0,
                catch_up_due_at=_CATCH_DUE,
                catch_up_start_no_earlier_at=_CATCH_EARLIEST,
                catch_up_start_no_later_at=_CATCH_LATEST,
                catch_up_deadline_at=_CATCH_DEADLINE,
                intent_fields_set=_CATCH_UP_FIELD_SET,
            )
        assert caught.value.status_code == 404
        denied.rollback()
    finally:
        denied.close()

    db_session.expire_all()
    assert _counts(db_session, victim_owner, uuid.UUID(task["id"])) == before


def test_a_ro4_terminal_and_revision_drift(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    released = _books(client, title=f"Released {_uid()}")
    rel_row = _hold(db_session, released["id"])
    rel_row.resolution = RESOLUTION_RELEASED
    db_session.add(
        DispositionEvent(
            disposition_id=rel_row.id,
            event_type=EVENT_MISS_DETECTED,
            payload={},
        )
    )
    db_session.commit()
    terminal = _review(client, released["id"], rel_row.id)
    assert terminal.status_code == 409, terminal.text
    assert terminal.json()["code"] == "CONFLICT_TERMINAL"

    task = _books(client, title=f"Stale {_uid()}")
    row = _hold(db_session, task["id"])
    drift = _review(client, task["id"], row.id, expected_revision=_revision(client) + 3)
    assert drift.status_code == 409, drift.text


def test_a_ro5_concurrent_review_and_authorize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.errors import ApiError
    from test_s2_t2_rec_recovery import (
        _commit_recurring_probe,
        _probe_issue_binding,
        _probe_recover_kwargs,
        _purge_probe_users,
    )

    _patch_schedule_clock(monkeypatch)
    monkeypatch.setattr("app.services.occurrence_disposition.utc_now", lambda: FIXED_NOW)
    _purge_probe_users()
    try:
        owner_id, task_id, disp_id, rev, title = _commit_recurring_probe()
        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def review_worker() -> None:
            db = SessionLocal()
            try:
                barrier.wait(timeout=15)
                before = observe_session_writes(db)
                review_recover_held(
                    db,
                    owner_id=owner_id,
                    task_id=task_id,
                    disposition_id=disp_id,
                    expected_revision=rev,
                    catch_up_due_at=_CATCH_DUE,
                    catch_up_start_no_earlier_at=_CATCH_EARLIEST,
                    catch_up_start_no_later_at=_CATCH_LATEST,
                    catch_up_deadline_at=_CATCH_DEADLINE,
                    intent_fields_set=_CATCH_UP_FIELD_SET,
                )
                after = observe_session_writes(db)
                assert before.empty and after.empty
                db.rollback()
                outcomes.append("review_ok")
            except Exception as exc:  # noqa: BLE001 — surface in join
                outcomes.append(f"review_err:{type(exc).__name__}")
                db.rollback()
            finally:
                db.close()

        def authorize_worker() -> None:
            db = SessionLocal()
            try:
                binding = _probe_issue_binding(db, owner_id, task_id, disp_id, rev)
                barrier.wait(timeout=15)
                recover_held(
                    db,
                    **_probe_recover_kwargs(owner_id, task_id, disp_id, rev, binding),
                )
                db.commit()
                outcomes.append("auth_ok")
            except ApiError as exc:
                outcomes.append(f"auth_err:{exc.content.get('code')}")
                db.rollback()
            except Exception as exc:  # noqa: BLE001
                outcomes.append(f"auth_err:{type(exc).__name__}")
                db.rollback()
            finally:
                db.close()

        threads = [
            threading.Thread(target=review_worker),
            threading.Thread(target=authorize_worker),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert "review_ok" in outcomes
        assert any(item.startswith("auth_") for item in outcomes)
        fresh = SessionLocal()
        try:
            row = fresh.get(TaskOccurrenceDisposition, disp_id)
            assert row is not None
            # Authorize is sole mutator; review leaves no residue either way.
            if row.resolution == RESOLUTION_RECOVERED:
                assert row.catch_up_task_id is not None
                assert (
                    fresh.query(Task)
                    .filter(Task.title == f"{title} (catch-up)")
                    .count()
                    == 1
                )
            else:
                assert (
                    fresh.query(Task)
                    .filter(Task.title == f"{title} (catch-up)")
                    .count()
                    == 0
                )
        finally:
            fresh.close()
    finally:
        _purge_probe_users()


def test_a_ro6_shared_projection_matches(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    rev = _review(client, task["id"], row.id)
    assert rev.status_code == 200, rev.text
    body = rev.json()
    assert str(body["next_normal"]["due_at"]).startswith("2026-08-18T09:00:00")
    auth = _recover(
        client,
        task["id"],
        row.id,
        review_binding=body["review_binding"],
        authorize_instant=body["authorize_instant"],
    )
    assert auth.status_code == 200, auth.text
    series = _task(db_session, task["id"])
    assert series.due_at == _AUG18


def test_a_z1_omit_vs_null_in_binding(
    client: TestClient, db_session: Session
) -> None:
    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    # Explicit null clear of catch-up due vs omit — different bindings.
    with_null = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/recover/review",
        json={
            "disposition_id": str(row.id),
            "expected_revision": _revision(client),
            "catch_up_due_at": None,
            "catch_up_start_no_earlier_at": _iso(_CATCH_EARLIEST),
            "catch_up_start_no_later_at": _iso(_CATCH_LATEST),
            "catch_up_deadline_at": _iso(_CATCH_DEADLINE),
        },
    )
    omitted = client.post(
        f"/api/v1/schedule/held-misses/{task['id']}/recover/review",
        json={
            "disposition_id": str(row.id),
            "expected_revision": _revision(client),
            "catch_up_start_no_earlier_at": _iso(_CATCH_EARLIEST),
            "catch_up_start_no_later_at": _iso(_CATCH_LATEST),
            "catch_up_deadline_at": _iso(_CATCH_DEADLINE),
        },
    )
    assert with_null.status_code == 200, with_null.text
    assert omitted.status_code == 200, omitted.text
    assert with_null.json()["review_binding"] != omitted.json()["review_binding"]
    # Wire UTC of reviewed catch-up earliest round-trips.
    assert with_null.json()["catch_up"]["start_no_earlier_at"].startswith(
        "2026-08-13T14:00:00"
    )


def test_a_z2_gap_fold_on_review_no_writes(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(client, db_session)
    now = datetime(2026, 3, 8, 13, 0, tzinfo=UTC)
    _set_now(monkeypatch, now)
    due = datetime(2026, 3, 7, 17, 0, tzinfo=UTC)
    latest = datetime(2026, 3, 7, 7, 30, tzinfo=UTC)
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": f"Gap review {_uid()}",
            "estimated_duration_minutes": 60,
            "priority": "p1",
            "schedule_style": "standalone",
            "due_at": _iso(due),
            "start_no_later_at": _iso(latest),
            "recurrence": {
                "rrule": "FREQ=DAILY;INTERVAL=1",
                "is_fixed": True,
                "timezone": "America/New_York",
            },
        },
    )
    assert task.status_code == 201, task.text
    task_json = task.json()
    row = _hold(db_session, task_json["id"])
    owner_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
    before = _counts(db_session, owner_id, uuid.UUID(task_json["id"]))
    resp = _review(client, task_json["id"], row.id)
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "BOUNDS_ROLL_INDETERMINATE_LOCAL"
    db_session.expire_all()
    assert _counts(db_session, owner_id, uuid.UUID(task_json["id"])) == before
    assert observe_session_writes(db_session).empty


def test_a_bind_idempotent_recover_rejects_bad_binding_accepts_genuine_replay(
    client: TestClient, db_session: Session
) -> None:
    """Recovered replay authenticates binding; fabricated/wrong/changed reject."""
    import hashlib
    import hmac

    from app.schemas.occurrence_disposition import RECOVER_REVIEW_CONTRACT_VERSION
    from app.services.occurrence_disposition import (
        _b64url,
        _canonical,
        _parse_recover_review_binding,
        _review_binding_key,
    )

    _prepare(client, db_session)
    task = _books(client)
    row = _hold(db_session, task["id"])
    reviewed = _review(client, task["id"], row.id)
    assert reviewed.status_code == 200, reviewed.text
    binding = reviewed.json()["review_binding"]
    auth_instant = reviewed.json()["authorize_instant"]
    first = _recover(
        client,
        task["id"],
        row.id,
        review_binding=binding,
        authorize_instant=auth_instant,
    )
    assert first.status_code == 200, first.text
    catch_id = first.json()["catch_up_task_id"]
    current_rev = _revision(client)

    # Review of terminal episode still 409 (no new binding issued).
    terminal_rev = _review(client, task["id"], row.id)
    assert terminal_rev.status_code == 409, terminal_rev.text
    assert terminal_rev.json()["code"] == "CONFLICT_TERMINAL"

    def _authorize(review_binding: str, **extra: object):
        body = {
            "disposition_id": str(row.id),
            "expected_revision": current_rev,
            "review_binding": review_binding,
            "authorize_instant": auth_instant,
            **_catch_up_body(),
            **extra,
        }
        return client.post(
            f"/api/v1/schedule/held-misses/{task['id']}/recover",
            json=body,
        )

    malformed = _authorize("t2-rec-ui-v1.not-used.deadbeef")
    assert malformed.status_code == 422, malformed.text
    assert malformed.json()["code"] == "REVIEW_BINDING_INVALID"

    claims = _parse_recover_review_binding(binding)
    claims["owner_id"] = str(uuid.uuid4())
    payload = _canonical(claims).encode("utf-8")
    digest = hmac.new(_review_binding_key(), payload, hashlib.sha256).hexdigest()
    wrong_owner = f"{RECOVER_REVIEW_CONTRACT_VERSION}.{_b64url(payload)}.{digest}"
    alien = _authorize(wrong_owner)
    assert alien.status_code == 422, alien.text
    assert alien.json()["code"] == "REVIEW_BINDING_MISMATCH"

    changed = _authorize(binding, catch_up_remaining_minutes=7)
    assert changed.status_code == 422, changed.text
    assert changed.json()["code"] == "REVIEW_BINDING_MISMATCH"

    # Genuine lost-response: original binding + same intent + current rev.
    genuine = _authorize(binding)
    assert genuine.status_code == 200, genuine.text
    assert genuine.json()["catch_up_task_id"] == catch_id
    assert genuine.json()["resolution"] == RESOLUTION_RECOVERED
    assert _revision(client) == current_rev
    assert (
        db_session.query(Task)
        .filter(Task.title == f"{task['title']} (catch-up)")
        .count()
        == 1
    )
