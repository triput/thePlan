"""F7 W1 quality exit: API matrix the engine tests do not already prove.

F7-A mixed dimensions, label any/all, persistence round-trip, matching-only query.
F7-B rolling today/week/within_days against user_settings.timezone (not UTC);
fixed ranges stay absolute.
F7-C deleted project/label → empty + invalid_references; bad predicate 422;
foreign owner 404; (delete-view leaves tasks lives in test_f7_w1_views).
F7-D system slug queries, truthful total under label fan-out, system mutate rejected.
Safety: trash/archive excluded by default; predicate values are bound parameters.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models import Label, Project, SavedFilter, Task, TaskLabel, User
from app.models.enums import ScheduleStatus, ScheduleStyle, TaskPriority, TaskWorkflowState
from app.services.saved_filter_predicate import validate_predicate
from app.services.saved_filter_query import apply_predicate_to_query

UTC = timezone.utc
# 2026-10-10 12:00 UTC is 2026-10-11 01:00 in Pacific/Auckland (NZDT, UTC+13).
AUCKLAND_NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
FAR_FUTURE = datetime(2030, 1, 1, tzinfo=UTC)


def _owner_id(client: TestClient) -> uuid.UUID:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    return uuid.UUID(me.json()["id"])


def _set_timezone(db: Session, owner_id: uuid.UUID, name: str) -> None:
    user = db.get(User, owner_id)
    assert user is not None and user.settings is not None
    user.settings.timezone = name
    db.flush()


def _freeze_now(monkeypatch, moment: datetime) -> None:
    def _aware(now: datetime | None = None) -> datetime:
        if now is None:
            return moment
        assert now.tzinfo is not None and now.tzinfo.utcoffset(now) is not None
        return now.astimezone(UTC)

    monkeypatch.setattr("app.services.saved_filter_query._aware_now", _aware)


def _project(db: Session, owner_id: uuid.UUID, *, archived: bool = False) -> Project:
    project = Project(
        owner_id=owner_id,
        title=f"f7q-{uuid.uuid4().hex[:8]}",
        is_archived=archived,
    )
    db.add(project)
    db.flush()
    return project


def _label(db: Session, owner_id: uuid.UUID) -> Label:
    label = Label(owner_id=owner_id, name=f"f7q-{uuid.uuid4().hex[:8]}")
    db.add(label)
    db.flush()
    return label


def _task(db: Session, owner_id: uuid.UUID, **kwargs: object) -> Task:
    task = Task(owner_id=owner_id, title=str(kwargs.pop("title", "f7q-task")), **kwargs)  # type: ignore[arg-type]
    db.add(task)
    db.flush()
    return task


def _tag(db: Session, task: Task, label: Label) -> None:
    db.add(TaskLabel(task_id=task.id, label_id=label.id))
    db.flush()


def _create_view(
    client: TestClient,
    *,
    name: str,
    predicate: dict,
    presentation: dict | None = None,
    slug: str | None = None,
) -> dict:
    body: dict = {
        "name": name,
        "predicate_json": predicate,
        "presentation_json": presentation if presentation is not None else {"mode": "list"},
    }
    if slug is not None:
        body["slug"] = slug
    created = client.post("/api/v1/views", json=body)
    assert created.status_code == 201, created.text
    return created.json()


def _query(client: TestClient, view_id: str, **params: object) -> dict:
    response = client.get(f"/api/v1/views/{view_id}/tasks", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _ids(body: dict) -> set[str]:
    return {item["id"] for item in body["items"]}


def _paged_ids(client: TestClient, path: str) -> tuple[int, set[str]]:
    found: set[str] = set()
    offset = 0
    limit = 200
    total = 0
    while True:
        response = client.get(path, params={"limit": limit, "offset": offset})
        assert response.status_code == 200, response.text
        body = response.json()
        total = body["total"]
        page = body["items"]
        found.update(item["id"] for item in page)
        offset += limit
        if not page or offset >= total:
            break
    return total, found


def test_f7_a_mixed_dimensions_round_trip_and_matching_only(
    client: TestClient, db_session: Session
) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    other = _project(db_session, owner)
    label = _label(db_session, owner)
    sent = {
        "v": 1,
        "dimensions": {
            "project_ids": [str(project.id).upper(), str(project.id)],
            "labels": {"ids": [str(label.id)], "match": "any"},
            "priorities": ["p2", "p1", "p1"],
            "workflow_states": ["ready"],
            "completion": "open",
            "schedule_statuses": ["scheduled"],
            "schedule_styles": ["manual"],
            "due": {"kind": "none"},
        },
    }
    presentation = {"mode": "board", "sort": "board_rank"}
    created = _create_view(
        client,
        name="Mixed hot",
        slug=f"mixed-{uuid.uuid4().hex[:8]}",
        predicate=sent,
        presentation=presentation,
    )
    canonical = validate_predicate(sent)
    assert created["predicate_json"] == canonical
    assert created["predicate_json"]["dimensions"]["project_ids"] == [str(project.id)]
    assert created["predicate_json"]["dimensions"]["priorities"] == ["p2", "p1"]
    assert created["presentation_json"] == presentation
    assert created["is_system"] is False

    fetched = client.get(f"/api/v1/views/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["predicate_json"] == canonical
    assert fetched.json()["presentation_json"] == presentation

    listed = client.get("/api/v1/views")
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == created["id"])
    assert row["predicate_json"] == canonical

    match = _task(
        db_session,
        owner,
        project_id=project.id,
        priority=TaskPriority.p1,
        workflow_state=TaskWorkflowState.ready,
        status=ScheduleStatus.scheduled,
        schedule_style=ScheduleStyle.manual,
        is_completed=False,
        due_at=None,
        sort_order=1,
    )
    _tag(db_session, match, label)

    def decoy(**kwargs: object) -> Task:
        skip_label = bool(kwargs.pop("skip_label", False))
        fields: dict = {
            "project_id": project.id,
            "priority": TaskPriority.p2,
            "workflow_state": TaskWorkflowState.ready,
            "status": ScheduleStatus.scheduled,
            "schedule_style": ScheduleStyle.manual,
            "is_completed": False,
            "due_at": None,
        }
        fields.update(kwargs)
        task = _task(db_session, owner, **fields)
        if not skip_label:
            _tag(db_session, task, label)
        return task

    wrong_priority = decoy(priority=TaskPriority.p4)
    completed = decoy(is_completed=True)
    other_project = decoy(project_id=other.id)
    waiting = decoy(workflow_state=TaskWorkflowState.waiting)
    unscheduled = decoy(status=ScheduleStatus.unscheduled)
    standalone = decoy(schedule_style=ScheduleStyle.standalone)
    dated = decoy(due_at=datetime(2026, 1, 2, tzinfo=UTC))
    unlabeled = decoy(skip_label=True)
    trashed = decoy(deleted_at=datetime(2026, 1, 1, tzinfo=UTC))

    by_id = _query(client, created["id"], limit=50, offset=0)
    assert by_id["invalid_references"] is None
    assert by_id["total"] == 1
    assert _ids(by_id) == {str(match.id)}
    assert by_id["limit"] == 50
    assert by_id["offset"] == 0

    by_slug = client.get(f"/api/v1/views/by-slug/{created['slug']}/tasks")
    assert by_slug.status_code == 200, by_slug.text
    assert by_slug.json()["total"] == 1
    assert _ids(by_slug.json()) == {str(match.id)}

    excluded = {
        wrong_priority.id,
        completed.id,
        other_project.id,
        waiting.id,
        unscheduled.id,
        standalone.id,
        dated.id,
        unlabeled.id,
        trashed.id,
    }
    assert excluded.isdisjoint({uuid.UUID(item_id) for item_id in _ids(by_id)})

    patched_predicate = {
        "v": 1,
        "dimensions": {
            "project_ids": [str(project.id)],
            "priorities": ["p4"],
            "completion": "open",
        },
    }
    patched = client.patch(
        f"/api/v1/views/{created['id']}",
        json={
            "predicate_json": patched_predicate,
            "presentation_json": {"mode": "list", "sort": "sort_order"},
            "name": "Mixed warm",
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["predicate_json"] == validate_predicate(patched_predicate)
    assert patched.json()["presentation_json"]["mode"] == "list"
    again = client.get(f"/api/v1/views/{created['id']}")
    assert again.json()["name"] == "Mixed warm"
    assert again.json()["predicate_json"] == validate_predicate(patched_predicate)
    requery = _query(client, created["id"])
    assert _ids(requery) == {str(wrong_priority.id)}
    assert str(match.id) not in _ids(requery)


def test_f7_a_labels_any_versus_all(client: TestClient, db_session: Session) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    label_a = _label(db_session, owner)
    label_b = _label(db_session, owner)
    only_a = _task(db_session, owner, project_id=project.id, is_completed=False)
    both = _task(db_session, owner, project_id=project.id, is_completed=False)
    neither = _task(db_session, owner, project_id=project.id, is_completed=False)
    _tag(db_session, only_a, label_a)
    _tag(db_session, both, label_a)
    _tag(db_session, both, label_b)

    def view_for(match: str) -> str:
        created = _create_view(
            client,
            name=f"Labels {match}",
            slug=f"labels-{match}-{uuid.uuid4().hex[:8]}",
            predicate={
                "v": 1,
                "dimensions": {
                    "project_ids": [str(project.id)],
                    "labels": {
                        "ids": [str(label_a.id), str(label_b.id)],
                        "match": match,
                    },
                    "completion": "any",
                },
            },
        )
        stored = created["predicate_json"]["dimensions"]["labels"]
        assert stored == {
            "ids": [str(label_a.id), str(label_b.id)],
            "match": match,
        }
        return created["id"]

    any_body = _query(client, view_for("any"))
    all_body = _query(client, view_for("all"))
    assert _ids(any_body) == {str(only_a.id), str(both.id)}
    assert any_body["total"] == 2
    assert _ids(all_body) == {str(both.id)}
    assert all_body["total"] == 1
    assert str(neither.id) not in _ids(any_body)
    assert str(neither.id) not in _ids(all_body)


def test_f7_b_rolling_windows_follow_settings_timezone(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    _freeze_now(monkeypatch, AUCKLAND_NOW)
    owner = _owner_id(client)
    _set_timezone(db_session, owner, "Pacific/Auckland")
    project = _project(db_session, owner)

    def due(instant: datetime, **kwargs: object) -> Task:
        fields: dict = {
            "project_id": project.id,
            "due_at": instant,
            "is_completed": False,
        }
        fields.update(kwargs)
        return _task(db_session, owner, **fields)

    before_local_today = due(datetime(2026, 10, 10, 10, 0, tzinfo=UTC))
    during_local_today = due(datetime(2026, 10, 10, 12, 0, tzinfo=UTC))
    tomorrow_start = due(datetime(2026, 10, 11, 11, 0, tzinfo=UTC))
    next_seven_end = due(datetime(2026, 10, 17, 11, 0, tzinfo=UTC))
    within_last = due(datetime(2026, 10, 18, 10, 0, tzinfo=UTC))
    within_end = due(datetime(2026, 10, 18, 11, 0, tzinfo=UTC))
    week_monday = due(datetime(2026, 10, 4, 11, 30, tzinfo=UTC))
    previous_sunday = due(datetime(2026, 10, 3, 23, 0, tzinfo=UTC))
    done_today = due(datetime(2026, 10, 10, 15, 0, tzinfo=UTC), is_completed=True)

    def scoped(rolling: str, **extra: object) -> set[str]:
        due_dim: dict = {"kind": "rolling", "rolling": rolling}
        due_dim.update(extra)
        created = _create_view(
            client,
            name=f"Roll {rolling}",
            slug=f"roll-{rolling.replace('_', '-')}-{uuid.uuid4().hex[:8]}",
            predicate={
                "v": 1,
                "dimensions": {
                    "project_ids": [str(project.id)],
                    "due": due_dim,
                    "completion": "any",
                },
            },
        )
        body = _query(client, created["id"])
        assert body["invalid_references"] is None
        return _ids(body)

    # Auckland local today is 2026-10-11. The ISO week also contains that Sunday
    # and the Saturday instant that is still "yesterday" locally.
    assert scoped("today") == {str(during_local_today.id), str(done_today.id)}
    week = scoped("this_calendar_week")
    assert week == {
        str(week_monday.id),
        str(before_local_today.id),
        str(during_local_today.id),
        str(done_today.id),
    }
    assert str(previous_sunday.id) not in week
    assert str(tomorrow_start.id) not in week
    within = scoped("within_days", days=7)
    assert within == {
        str(tomorrow_start.id),
        str(next_seven_end.id),
        str(within_last.id),
    }
    assert str(during_local_today.id) not in within
    assert str(within_end.id) not in within

    today_total, today_ids = _paged_ids(client, "/api/v1/views/by-slug/today/tasks")
    assert today_total == len(today_ids)
    assert str(during_local_today.id) in today_ids
    assert str(before_local_today.id) not in today_ids
    assert str(done_today.id) not in today_ids
    upcoming_total, upcoming_ids = _paged_ids(client, "/api/v1/views/by-slug/upcoming/tasks")
    assert upcoming_total == len(upcoming_ids)
    assert str(tomorrow_start.id) in upcoming_ids
    assert str(during_local_today.id) not in upcoming_ids

    _set_timezone(db_session, owner, "UTC")
    utc_today = scoped("today")
    assert str(before_local_today.id) in utc_today
    assert str(during_local_today.id) in utc_today
    assert str(tomorrow_start.id) not in utc_today
    assert str(week_monday.id) not in utc_today


def test_f7_b_fixed_range_ignores_settings_timezone(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    _freeze_now(monkeypatch, FAR_FUTURE)
    owner = _owner_id(client)
    project = _project(db_session, owner)
    inside = _task(
        db_session,
        owner,
        project_id=project.id,
        due_at=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
        is_completed=False,
    )
    exclusive_end = _task(
        db_session,
        owner,
        project_id=project.id,
        due_at=datetime(2026, 6, 16, 0, 0, tzinfo=UTC),
        is_completed=False,
    )
    predicate = {
        "v": 1,
        "dimensions": {
            "project_ids": [str(project.id)],
            "due": {
                "kind": "fixed",
                "from": "2026-06-15T00:00:00Z",
                "to": "2026-06-16T00:00:00Z",
            },
            "completion": "any",
        },
    }
    created = _create_view(
        client,
        name="Fixed June",
        slug=f"fixed-{uuid.uuid4().hex[:8]}",
        predicate=predicate,
    )
    assert created["predicate_json"]["dimensions"]["due"] == {
        "kind": "fixed",
        "from": "2026-06-15T00:00:00Z",
        "to": "2026-06-16T00:00:00Z",
    }
    for zone in ("Pacific/Auckland", "America/Los_Angeles", "UTC"):
        _set_timezone(db_session, owner, zone)
        body = _query(client, created["id"])
        assert _ids(body) == {str(inside.id)}
        assert str(exclusive_end.id) not in _ids(body)
        assert body["total"] == 1


def test_f7_c_deleted_project_and_label_do_not_widen(
    client: TestClient, db_session: Session
) -> None:
    owner = _owner_id(client)
    live = _project(db_session, owner)
    doomed = _project(db_session, owner)
    on_live = _task(db_session, owner, project_id=live.id, is_completed=False, title="stay-live")
    on_doomed = _task(
        db_session, owner, project_id=doomed.id, is_completed=False, title="goes-with-project"
    )
    inbox = _task(db_session, owner, project_id=None, is_completed=False, title="inbox-decoy")
    project_view = _create_view(
        client,
        name="Both projects",
        slug=f"both-{uuid.uuid4().hex[:8]}",
        predicate={
            "v": 1,
            "dimensions": {
                "project_ids": [str(doomed.id), str(live.id)],
                "completion": "any",
            },
        },
    )
    before = _query(client, project_view["id"])
    assert _ids(before) == {str(on_live.id), str(on_doomed.id)}

    doomed_id = str(doomed.id)
    db_session.delete(doomed)
    db_session.flush()

    after = _query(client, project_view["id"])
    assert after["items"] == []
    assert after["total"] == 0
    assert after["invalid_references"]
    assert any(
        ref["kind"] == "project" and ref["id"] == doomed_id for ref in after["invalid_references"]
    )
    assert str(on_live.id) not in _ids(after)
    still = client.get("/api/v1/tasks", params={"ids": [str(on_live.id), str(inbox.id)]})
    assert still.status_code == 200
    assert still.json()["total"] == 2

    label = _label(db_session, owner)
    labeled = _task(db_session, owner, project_id=live.id, is_completed=False, title="was-labeled")
    unlabeled = _task(db_session, owner, project_id=live.id, is_completed=False, title="never-labeled")
    _tag(db_session, labeled, label)
    label_id = str(label.id)
    label_view = _create_view(
        client,
        name="Needs label",
        slug=f"needs-label-{uuid.uuid4().hex[:8]}",
        predicate={
            "v": 1,
            "dimensions": {
                "project_ids": [str(live.id)],
                "labels": {"ids": [label_id], "match": "any"},
                "completion": "any",
            },
        },
    )
    assert _ids(_query(client, label_view["id"])) == {str(labeled.id)}
    db_session.delete(label)
    db_session.flush()
    missing_label = _query(client, label_view["id"])
    assert missing_label["items"] == []
    assert missing_label["total"] == 0
    assert any(
        ref["kind"] == "label" and ref["id"] == label_id
        for ref in missing_label["invalid_references"]
    )
    assert "was-labeled" not in str(missing_label)
    survivors = client.get(
        "/api/v1/tasks", params={"ids": [str(labeled.id), str(unlabeled.id)]}
    )
    assert survivors.status_code == 200
    assert survivors.json()["total"] == 2


def test_f7_c_bad_predicate_and_foreign_owner_are_not_leaks(
    client: TestClient, db_session: Session
) -> None:
    owner = _owner_id(client)
    created = _create_view(
        client,
        name="Stable",
        slug=f"stable-{uuid.uuid4().hex[:8]}",
        predicate={"v": 1, "dimensions": {"completion": "open"}},
    )
    bad = client.patch(
        f"/api/v1/views/{created['id']}",
        json={"name": "Hijacked", "predicate_json": {"op": "or", "clauses": [{"sql": "1=1"}]}},
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "INVALID_PREDICATE"
    db_session.rollback()
    kept = client.get(f"/api/v1/views/{created['id']}")
    assert kept.status_code == 200
    assert kept.json()["name"] == "Stable"
    assert kept.json()["predicate_json"] == {"v": 1, "dimensions": {"completion": "open"}}

    injection = client.post(
        "/api/v1/views",
        json={
            "name": "drop tasks",
            "predicate_json": {
                "v": 1,
                "dimensions": {
                    "project_ids": ["00000000-0000-0000-0000-000000000000' OR 1=1 --"],
                },
            },
        },
    )
    assert injection.status_code == 422
    assert injection.json()["code"] == "INVALID_PREDICATE"

    too_wide = {
        "v": 1,
        "dimensions": {
            "inbox": True,
            "epic_ids": [str(uuid.uuid4())],
            "labels": {"ids": [str(uuid.uuid4())], "match": "any"},
            "priorities": ["p1"],
            "workflow_states": ["ready"],
            "completion": "open",
            "schedule_statuses": ["unscheduled"],
            "schedule_styles": ["manual"],
            "due": {"kind": "none"},
        },
    }
    complex_resp = client.post(
        "/api/v1/views",
        json={"name": "Too many", "predicate_json": too_wide},
    )
    assert complex_resp.status_code == 422
    assert complex_resp.json()["code"] == "PREDICATE_TOO_COMPLEX"

    other = User(
        email=f"f7q-other-{uuid.uuid4().hex[:8]}@example.com",
        username=f"f7qother{uuid.uuid4().hex[:8]}",
    )
    db_session.add(other)
    db_session.flush()
    assert other.id != owner
    secret_name = f"secret-view-{uuid.uuid4().hex[:8]}"
    secret = SavedFilter(
        owner_id=other.id,
        name=secret_name,
        slug=f"secret-{uuid.uuid4().hex[:8]}",
        predicate_json={"v": 1, "dimensions": {"inbox": True, "completion": "open"}},
        presentation_json={"mode": "list"},
        is_system=False,
        sort_order=1,
    )
    db_session.add(secret)
    db_session.flush()
    secret_id = str(secret.id)
    missing_id = str(uuid.uuid4())

    missing_get = client.get(f"/api/v1/views/{missing_id}")
    foreign_get = client.get(f"/api/v1/views/{secret_id}")
    assert missing_get.status_code == 404
    assert foreign_get.status_code == 404
    assert foreign_get.json() == missing_get.json()
    assert secret_name not in foreign_get.text

    missing_tasks = client.get(f"/api/v1/views/{missing_id}/tasks")
    foreign_tasks = client.get(f"/api/v1/views/{secret_id}/tasks")
    assert missing_tasks.status_code == 404
    assert foreign_tasks.status_code == 404
    assert foreign_tasks.json() == missing_tasks.json()
    assert secret_name not in foreign_tasks.text

    missing_patch = client.patch(f"/api/v1/views/{missing_id}", json={"name": "nope"})
    foreign_patch = client.patch(f"/api/v1/views/{secret_id}", json={"name": "nope"})
    assert missing_patch.status_code == 404
    assert foreign_patch.status_code == 404
    assert foreign_patch.json() == missing_patch.json()

    missing_delete = client.delete(f"/api/v1/views/{missing_id}")
    foreign_delete = client.delete(f"/api/v1/views/{secret_id}")
    assert missing_delete.status_code == 404
    assert foreign_delete.status_code == 404

    listing = client.get("/api/v1/views")
    assert listing.status_code == 200
    assert all(row["id"] != secret_id for row in listing.json())
    assert secret_name not in listing.text
    foreign_slug = client.get(f"/api/v1/views/by-slug/{secret.slug}/tasks")
    assert foreign_slug.status_code == 404


def test_f7_d_pagination_total_and_system_views(
    client: TestClient, db_session: Session
) -> None:
    owner = _owner_id(client)
    project = _project(db_session, owner)
    label_a = _label(db_session, owner)
    label_b = _label(db_session, owner)
    first = _task(db_session, owner, project_id=project.id, sort_order=1, is_completed=False)
    second = _task(db_session, owner, project_id=project.id, sort_order=2, is_completed=False)
    decoy = _task(db_session, owner, project_id=project.id, sort_order=3, is_completed=False)
    for task in (first, second):
        _tag(db_session, task, label_a)
        _tag(db_session, task, label_b)

    created = _create_view(
        client,
        name="Two labels",
        slug=f"two-labels-{uuid.uuid4().hex[:8]}",
        predicate={
            "v": 1,
            "dimensions": {
                "project_ids": [str(project.id)],
                "labels": {"ids": [str(label_a.id), str(label_b.id)], "match": "any"},
                "completion": "any",
            },
        },
    )
    pages: list[str] = []
    for offset in range(3):
        body = _query(client, created["id"], limit=1, offset=offset)
        assert body["total"] == 2
        assert body["limit"] == 1
        assert body["offset"] == offset
        if offset < 2:
            assert len(body["items"]) == 1
            item = body["items"][0]
            assert set(item["label_ids"]) == {str(label_a.id), str(label_b.id)}
            pages.append(item["id"])
        else:
            assert body["items"] == []
    assert pages == [str(first.id), str(second.id)]
    assert str(decoy.id) not in pages

    listing = client.get("/api/v1/views")
    assert listing.status_code == 200
    by_slug = {row["slug"]: row for row in listing.json()}
    for slug in ("inbox", "today", "upcoming"):
        assert by_slug[slug]["is_system"] is True
        assert by_slug[slug]["predicate_json"]["v"] == 1

    inbox = by_slug["inbox"]
    original_name = inbox["name"]
    original_predicate = inbox["predicate_json"]
    original_sort = inbox["sort_order"]
    rejected = client.patch(
        f"/api/v1/views/{inbox['id']}",
        json={
            "name": "Renamed inbox",
            "sort_order": 999,
            "predicate_json": {"v": 1, "dimensions": {"completion": "any"}},
        },
    )
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "SYSTEM_VIEW_READ_ONLY"
    kept = client.get(f"/api/v1/views/{inbox['id']}")
    assert kept.status_code == 200
    assert kept.json()["name"] == original_name
    assert kept.json()["predicate_json"] == original_predicate
    assert kept.json()["sort_order"] == original_sort

    today = client.get("/api/v1/views/by-slug/today/tasks", params={"limit": 1, "offset": 0})
    upcoming = client.get("/api/v1/views/by-slug/upcoming/tasks", params={"limit": 1, "offset": 0})
    assert today.status_code == 200
    assert upcoming.status_code == 200
    assert isinstance(today.json()["total"], int)
    assert isinstance(upcoming.json()["total"], int)
    assert today.json()["total"] >= len(today.json()["items"])


def test_safety_archive_and_trash_excluded_by_default(
    client: TestClient, db_session: Session
) -> None:
    owner = _owner_id(client)
    live = _project(db_session, owner)
    archived = _project(db_session, owner, archived=True)
    label = _label(db_session, owner)
    visible = _task(db_session, owner, project_id=live.id, is_completed=False, title="visible")
    hidden_archive = _task(
        db_session, owner, project_id=archived.id, is_completed=False, title="archived-project"
    )
    trashed = _task(
        db_session,
        owner,
        project_id=live.id,
        is_completed=False,
        deleted_at=datetime(2026, 2, 2, tzinfo=UTC),
        title="trashed",
    )
    for task in (visible, hidden_archive, trashed):
        _tag(db_session, task, label)

    created = _create_view(
        client,
        name="Label default vis",
        slug=f"vis-{uuid.uuid4().hex[:8]}",
        predicate={
            "v": 1,
            "dimensions": {
                "labels": {"ids": [str(label.id)], "match": "any"},
                "completion": "any",
            },
        },
    )
    body = _query(client, created["id"])
    assert _ids(body) == {str(visible.id)}
    assert body["total"] == 1
    assert str(hidden_archive.id) not in _ids(body)
    assert str(trashed.id) not in _ids(body)

    explicit = _create_view(
        client,
        name="Archived on purpose",
        slug=f"arch-{uuid.uuid4().hex[:8]}",
        predicate={
            "v": 1,
            "dimensions": {
                "project_ids": [str(archived.id)],
                "completion": "any",
            },
        },
    )
    scoped = _query(client, explicit["id"])
    assert str(hidden_archive.id) in _ids(scoped)
    assert str(trashed.id) not in _ids(scoped)
    assert str(visible.id) not in _ids(scoped)


def test_safety_predicate_values_are_bound_parameters(db_session: Session) -> None:
    from app.bootstrap import ensure_bootstrap_user

    user = ensure_bootstrap_user(db_session, commit=False)
    project = _project(db_session, user.id)
    predicate = {
        "v": 1,
        "dimensions": {
            "project_ids": [str(project.id)],
            "due": {
                "kind": "fixed",
                "from": "2026-06-15T00:00:00Z",
                "to": "2026-06-16T00:00:00Z",
            },
        },
    }
    result = apply_predicate_to_query(
        db_session.query(Task).filter(Task.owner_id == user.id),
        db_session,
        user.id,
        predicate,
        timezone_name="Pacific/Auckland'; DROP TABLE tasks; --",
        now=AUCKLAND_NOW,
    )
    compiled = result.query.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    upper = sql.upper()
    assert "DROP TABLE" not in upper
    assert "DELETE FROM" not in upper
    assert "PACIFIC/AUCKLAND" not in upper
    assert "2026-06-15" not in sql
    assert str(project.id) not in sql
    bound = " ".join(str(value) for value in compiled.params.values())
    assert str(project.id) in bound
    assert "2026-06-15" in bound or "2026-06-15 00:00:00" in bound
