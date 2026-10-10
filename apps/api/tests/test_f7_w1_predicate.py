"""F7 W1 predicate engine: validation, missing refs, rolling windows in owner TZ."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.bootstrap import ensure_bootstrap_user
from app.models import Epic, Label, Project, Task, TaskLabel, User
from app.models.enums import ScheduleStatus, ScheduleStyle, TaskPriority, TaskWorkflowState
from app.services.saved_filter_predicate import (
    MAX_DIMENSIONS,
    MAX_OR_FANOUT,
    check_missing_refs,
    validate_predicate,
)
from app.services.saved_filter_query import (
    apply_default_task_visibility,
    apply_predicate_to_query,
    rolling_due_window,
)
from app.services.saved_filter_v1 import (
    INBOX_PREDICATE_V1,
    TODAY_PREDICATE_V1,
    UPCOMING_PREDICATE_V1,
)

UTC = timezone.utc
# 2026-03-08 10:30 UTC is 03:30 PDT, after the US spring-forward (23-hour local day).
SPRING_NOW = datetime(2026, 3, 8, 10, 30, tzinfo=UTC)
# 2026-11-01 08:30 UTC is 01:30 PDT, before the US fall-back (25-hour local day).
FALL_NOW = datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
# 2026-10-10 12:00 UTC is 2026-10-11 01:00 in Pacific/Auckland (NZDT, UTC+13).
AUCKLAND_NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def _raises(raw: object, code: str) -> None:
    with pytest.raises(ApiError) as caught:
        validate_predicate(raw)
    assert caught.value.status_code == 422
    assert caught.value.content["code"] == code


def _owner(db: Session) -> User:
    user = ensure_bootstrap_user(db, commit=False)
    assert user.settings is not None
    return user


def _project(db: Session, owner_id: uuid.UUID, *, archived: bool = False, epic_id: uuid.UUID | None = None) -> Project:
    project = Project(
        owner_id=owner_id,
        title=f"f7-{uuid.uuid4().hex[:8]}",
        is_archived=archived,
        epic_id=epic_id,
    )
    db.add(project)
    db.flush()
    return project


def _task(db: Session, owner_id: uuid.UUID, **kwargs: object) -> Task:
    task = Task(owner_id=owner_id, title=str(kwargs.pop("title", "f7-task")), **kwargs)  # type: ignore[arg-type]
    db.add(task)
    db.flush()
    return task


def _apply(
    db: Session,
    owner_id: uuid.UUID,
    predicate: dict,
    *,
    timezone_name: str,
    now: datetime | None = None,
):
    query = db.query(Task).filter(Task.owner_id == owner_id)
    return apply_predicate_to_query(
        query,
        db,
        owner_id,
        predicate,
        timezone_name=timezone_name,
        now=now,
    )


def _ids(result) -> set[uuid.UUID]:
    return {row.id for row in result.query.all()}


def test_system_predicates_normalize_idempotently() -> None:
    for raw in (INBOX_PREDICATE_V1, TODAY_PREDICATE_V1, UPCOMING_PREDICATE_V1):
        once = validate_predicate(raw)
        assert validate_predicate(once) == once
        assert once["v"] == 1
    assert validate_predicate(INBOX_PREDICATE_V1)["dimensions"]["inbox"] is True
    assert validate_predicate(TODAY_PREDICATE_V1)["dimensions"]["due"] == {
        "kind": "rolling",
        "rolling": "today",
    }
    upcoming = validate_predicate(UPCOMING_PREDICATE_V1)["dimensions"]["due"]
    assert upcoming == {"kind": "rolling", "rolling": "within_days", "days": 7}


def test_within_days_defaults_days_and_dedupes_ids() -> None:
    implied = validate_predicate(
        {"v": 1, "dimensions": {"due": {"kind": "rolling", "rolling": "within_days"}}}
    )
    assert implied["dimensions"]["due"]["days"] == 7

    pid = uuid.uuid4()
    normalized = validate_predicate(
        {"v": 1, "dimensions": {"project_ids": [str(pid).upper(), str(pid)]}}
    )
    assert normalized["dimensions"]["project_ids"] == [str(pid)]


def test_fixed_range_canonicalizes_to_utc_and_rejects_empty_window() -> None:
    ok = validate_predicate(
        {
            "v": 1,
            "dimensions": {
                "due": {
                    "kind": "fixed",
                    "from": "2026-10-10T17:00:00-07:00",
                    "to": "2026-10-12T00:00:00Z",
                }
            },
        }
    )
    assert ok["dimensions"]["due"]["from"] == "2026-10-11T00:00:00Z"
    assert ok["dimensions"]["due"]["to"] == "2026-10-12T00:00:00Z"
    _raises(
        {
            "v": 1,
            "dimensions": {
                "due": {
                    "kind": "fixed",
                    "from": "2026-10-11T00:00:00Z",
                    "to": "2026-10-11T00:00:00Z",
                }
            },
        },
        "INVALID_PREDICATE",
    )


@pytest.mark.parametrize(
    "raw",
    [
        {"op": "and", "clauses": [{"field": "project_id", "op": "is_null"}]},
        {"v": 1, "op": "and", "clauses": [], "dimensions": {"completion": "open"}},
        {"op": "legacy"},
        {"v": 2, "dimensions": {}},
        {"v": True, "dimensions": {}},
        {"dimensions": {}},
        {"v": 1, "dimensions": {}, "notes": "widen"},
        {"v": 1, "dimensions": {"inbox": False}},
        {"v": 1, "dimensions": {"project_ids": []}},
        {"v": 1, "dimensions": {"labels": {"ids": [str(uuid.uuid4())]}}},
        {"v": 1, "dimensions": {"labels": {"ids": [str(uuid.uuid4())], "match": "xor"}}},
        {"v": 1, "dimensions": {"priorities": ["P1"]}},
        {"v": 1, "dimensions": {"workflow_states": ["done"]}},
        {"v": 1, "dimensions": {"schedule_statuses": ["canceled"]}},
        {"v": 1, "dimensions": {"completion": "closed"}},
        {"v": 1, "dimensions": {"due": {"kind": "fixed", "from": "2026-10-10T00:00:00", "to": "2026-10-11T00:00:00Z"}}},
        {"v": 1, "dimensions": {"due": {"kind": "rolling", "rolling": "today", "days": 3}}},
        {"v": 1, "dimensions": {"due": {"kind": "rolling", "rolling": "within_days", "days": 0}}},
        {"v": 1, "dimensions": {"due": {"kind": "rolling", "rolling": "within_days", "days": True}}},
        {"v": 1, "dimensions": {"archived": True}},
        {
            "v": 1,
            "dimensions": {
                "inbox": True,
                "project_ids": [str(uuid.uuid4())],
            },
        },
    ],
)
def test_invalid_predicates_rejected(raw: dict) -> None:
    _raises(raw, "INVALID_PREDICATE")


def test_nested_label_id_is_too_complex() -> None:
    _raises(
        {
            "v": 1,
            "dimensions": {"labels": {"ids": [{"op": "eq"}], "match": "any"}},
        },
        "PREDICATE_TOO_COMPLEX",
    )


def test_dimension_and_fanout_bounds() -> None:
    eight = {
        "v": 1,
        "dimensions": {
            "epic_ids": [str(uuid.uuid4())],
            "labels": {"ids": [str(uuid.uuid4())], "match": "all"},
            "priorities": ["p1", "p1"],
            "workflow_states": ["ready"],
            "completion": "any",
            "schedule_statuses": ["unscheduled"],
            "schedule_styles": ["bundle"],
            "due": {"kind": "unbounded"},
        },
    }
    assert len(validate_predicate(eight)["dimensions"]) == MAX_DIMENSIONS
    assert validate_predicate(eight)["dimensions"]["priorities"] == ["p1"]

    nine = {
        "v": 1,
        "dimensions": {**eight["dimensions"], "inbox": True},
    }
    _raises(nine, "PREDICATE_TOO_COMPLEX")

    at_cap = {
        "v": 1,
        "dimensions": {"project_ids": [str(uuid.uuid4()) for _ in range(MAX_OR_FANOUT)]},
    }
    assert len(validate_predicate(at_cap)["dimensions"]["project_ids"]) == MAX_OR_FANOUT
    _raises(
        {
            "v": 1,
            "dimensions": {"project_ids": [str(uuid.uuid4()) for _ in range(MAX_OR_FANOUT + 1)]},
        },
        "PREDICATE_TOO_COMPLEX",
    )


def test_empty_dimensions_are_valid() -> None:
    assert validate_predicate({"v": 1, "dimensions": {}}) == {"v": 1, "dimensions": {}}


def test_legacy_field_path_and_inbox_conflict_field() -> None:
    with pytest.raises(ApiError) as legacy:
        validate_predicate({"op": "and", "clauses": []})
    assert legacy.value.content["field"] == "predicate"
    assert "legacy" in str(legacy.value.content["detail"])

    with pytest.raises(ApiError) as both:
        validate_predicate(
            {
                "v": 1,
                "dimensions": {"inbox": True, "project_ids": [str(uuid.uuid4())]},
            }
        )
    assert both.value.content["field"] == "dimensions"


def test_spring_forward_today_is_local_midnight_not_utc() -> None:
    window = rolling_due_window(
        {"kind": "rolling", "rolling": "today"},
        timezone_name="America/Los_Angeles",
        now=SPRING_NOW,
    )
    assert window == (
        datetime(2026, 3, 8, 8, 0, tzinfo=UTC),
        datetime(2026, 3, 9, 7, 0, tzinfo=UTC),
    )


def test_fall_back_today_includes_the_repeated_hour() -> None:
    window = rolling_due_window(
        {"kind": "rolling", "rolling": "today"},
        timezone_name="America/Los_Angeles",
        now=FALL_NOW,
    )
    assert window == (
        datetime(2026, 11, 1, 7, 0, tzinfo=UTC),
        datetime(2026, 11, 2, 8, 0, tzinfo=UTC),
    )


def test_auckland_date_line_and_week_windows() -> None:
    today = rolling_due_window(
        {"kind": "rolling", "rolling": "today"},
        timezone_name="Pacific/Auckland",
        now=AUCKLAND_NOW,
    )
    assert today == (
        datetime(2026, 10, 10, 11, 0, tzinfo=UTC),
        datetime(2026, 10, 11, 11, 0, tzinfo=UTC),
    )
    next_seven = rolling_due_window(
        {"kind": "rolling", "rolling": "next_7_days"},
        timezone_name="Pacific/Auckland",
        now=AUCKLAND_NOW,
    )
    assert next_seven == (
        datetime(2026, 10, 10, 11, 0, tzinfo=UTC),
        datetime(2026, 10, 17, 11, 0, tzinfo=UTC),
    )
    upcoming = rolling_due_window(
        {"kind": "rolling", "rolling": "within_days", "days": 7},
        timezone_name="Pacific/Auckland",
        now=AUCKLAND_NOW,
    )
    assert upcoming == (
        datetime(2026, 10, 11, 11, 0, tzinfo=UTC),
        datetime(2026, 10, 18, 11, 0, tzinfo=UTC),
    )
    week = rolling_due_window(
        {"kind": "rolling", "rolling": "this_calendar_week"},
        timezone_name="Pacific/Auckland",
        now=AUCKLAND_NOW,
    )
    # Local Sunday 2026-10-11 belongs to the ISO week starting Monday 2026-10-05.
    assert week == (
        datetime(2026, 10, 4, 11, 0, tzinfo=UTC),
        datetime(2026, 10, 11, 11, 0, tzinfo=UTC),
    )


def test_unknown_timezone_is_422() -> None:
    with pytest.raises(ApiError) as caught:
        rolling_due_window(
            {"kind": "rolling", "rolling": "today"},
            timezone_name="Not/AZone",
            now=AUCKLAND_NOW,
        )
    assert caught.value.status_code == 422
    assert caught.value.content["code"] == "INVALID_TIMEZONE"


def test_rolling_membership_follows_settings_timezone(db_session: Session) -> None:
    user = _owner(db_session)
    user.settings.timezone = "Pacific/Auckland"
    project = _project(db_session, user.id)
    db_session.flush()

    def due_task(instant: datetime) -> Task:
        return _task(
            db_session,
            user.id,
            project_id=project.id,
            due_at=instant,
            is_completed=False,
        )

    before_local_today = due_task(datetime(2026, 10, 10, 10, 0, tzinfo=UTC))
    during_local_today = due_task(datetime(2026, 10, 10, 12, 0, tzinfo=UTC))
    tomorrow_start = due_task(datetime(2026, 10, 11, 11, 0, tzinfo=UTC))
    next_seven_end = due_task(datetime(2026, 10, 17, 11, 0, tzinfo=UTC))
    within_last = due_task(datetime(2026, 10, 18, 10, 0, tzinfo=UTC))
    within_end = due_task(datetime(2026, 10, 18, 11, 0, tzinfo=UTC))
    no_due = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=None,
        is_completed=False,
    )

    def members(rolling: str, **extra: object) -> set[uuid.UUID]:
        due: dict = {"kind": "rolling", "rolling": rolling}
        due.update(extra)
        predicate = {
            "v": 1,
            "dimensions": {"project_ids": [str(project.id)], "due": due},
        }
        result = _apply(
            db_session,
            user.id,
            predicate,
            timezone_name=user.settings.timezone,
            now=AUCKLAND_NOW,
        )
        assert result.unsatisfiable is False
        return _ids(result)

    assert members("today") == {during_local_today.id}
    assert before_local_today.id not in members("today")
    assert members("next_7_days") == {during_local_today.id, tomorrow_start.id}
    assert next_seven_end.id not in members("next_7_days")
    assert within_last.id not in members("next_7_days")
    assert members("within_days", days=7) == {
        tomorrow_start.id,
        next_seven_end.id,
        within_last.id,
    }
    assert during_local_today.id not in members("within_days", days=7)
    assert within_end.id not in members("within_days", days=7)
    assert no_due.id not in members("today")


def test_spring_forward_query_uses_short_local_day(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    inside = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=datetime(2026, 3, 9, 6, 59, tzinfo=UTC),
        is_completed=False,
    )
    exclusive_end = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=datetime(2026, 3, 9, 7, 0, tzinfo=UTC),
        is_completed=False,
    )
    result = _apply(
        db_session,
        user.id,
        {
            "v": 1,
            "dimensions": {
                "project_ids": [str(project.id)],
                "due": {"kind": "rolling", "rolling": "today"},
            },
        },
        timezone_name="America/Los_Angeles",
        now=SPRING_NOW,
    )
    assert _ids(result) == {inside.id}
    assert exclusive_end.id not in _ids(result)


def test_calendar_week_boundaries(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    previous_sunday = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=datetime(2026, 10, 3, 23, 0, tzinfo=UTC),
        is_completed=False,
    )
    monday_start = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=datetime(2026, 10, 4, 11, 30, tzinfo=UTC),
        is_completed=False,
    )
    next_monday = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=datetime(2026, 10, 11, 11, 0, tzinfo=UTC),
        is_completed=False,
    )
    result = _apply(
        db_session,
        user.id,
        {
            "v": 1,
            "dimensions": {
                "project_ids": [str(project.id)],
                "due": {"kind": "rolling", "rolling": "this_calendar_week"},
            },
        },
        timezone_name="Pacific/Auckland",
        now=AUCKLAND_NOW,
    )
    assert _ids(result) == {monday_start.id}
    assert previous_sunday.id not in _ids(result)
    assert next_monday.id not in _ids(result)


def test_fixed_range_ignores_timezone_and_now(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    inside = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
        is_completed=False,
    )
    exclusive_end = _task(
        db_session,
        user.id,
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
        },
    }
    for timezone_name in ("Pacific/Auckland", "America/Los_Angeles", "UTC"):
        result = _apply(
            db_session,
            user.id,
            predicate,
            timezone_name=timezone_name,
            now=datetime(2030, 1, 1, tzinfo=UTC),
        )
        assert _ids(result) == {inside.id}
        assert exclusive_end.id not in _ids(result)


def test_due_none_and_unbounded(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    undated = _task(db_session, user.id, project_id=project.id, due_at=None, is_completed=False)
    dated = _task(
        db_session,
        user.id,
        project_id=project.id,
        due_at=datetime(2026, 1, 2, tzinfo=UTC),
        is_completed=False,
    )
    none_ids = _ids(
        _apply(
            db_session,
            user.id,
            {
                "v": 1,
                "dimensions": {
                    "project_ids": [str(project.id)],
                    "due": {"kind": "none"},
                },
            },
            timezone_name="UTC",
        )
    )
    any_ids = _ids(
        _apply(
            db_session,
            user.id,
            {
                "v": 1,
                "dimensions": {
                    "project_ids": [str(project.id)],
                    "due": {"kind": "unbounded"},
                },
            },
            timezone_name="UTC",
        )
    )
    assert none_ids == {undated.id}
    assert any_ids == {undated.id, dated.id}


def test_missing_ref_empties_query_instead_of_dropping_the_id(db_session: Session) -> None:
    user = _owner(db_session)
    live = _project(db_session, user.id)
    task = _task(db_session, user.id, project_id=live.id, is_completed=False)
    ghost = uuid.uuid4()
    predicate = {
        "v": 1,
        "dimensions": {
            "project_ids": [str(live.id), str(ghost)],
            "completion": "any",
        },
    }
    normalized = validate_predicate(predicate)
    missing = check_missing_refs(db_session, user.id, normalized)
    assert missing == [{"kind": "project", "id": str(ghost), "dimension": "project_ids"}]
    assert str(live.id) in normalized["dimensions"]["project_ids"]

    result = _apply(db_session, user.id, predicate, timezone_name="UTC")
    assert result.unsatisfiable is True
    assert result.invalid_references == missing
    assert task.id not in _ids(result)
    assert _ids(result) == set()


def test_foreign_owner_ref_matches_missing_without_leaking_title(db_session: Session) -> None:
    user = _owner(db_session)
    other = User(
        email=f"f7-other-{uuid.uuid4().hex[:8]}@example.com",
        username=f"f7other{uuid.uuid4().hex[:8]}",
    )
    db_session.add(other)
    db_session.flush()
    secret = Project(owner_id=other.id, title="secret-project-title", is_archived=False)
    db_session.add(secret)
    db_session.flush()
    predicate = {"v": 1, "dimensions": {"project_ids": [str(secret.id)]}}
    result = _apply(db_session, user.id, predicate, timezone_name="UTC")
    assert result.unsatisfiable is True
    assert result.invalid_references == [
        {"kind": "project", "id": str(secret.id), "dimension": "project_ids"}
    ]
    assert "secret-project-title" not in str(result.invalid_references)


def test_archived_row_is_not_a_missing_ref(db_session: Session) -> None:
    user = _owner(db_session)
    archived = _project(db_session, user.id, archived=True)
    predicate = validate_predicate(
        {"v": 1, "dimensions": {"project_ids": [str(archived.id)]}}
    )
    assert check_missing_refs(db_session, user.id, predicate) == []


def test_missing_label_does_not_match_the_surviving_label(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    label = Label(owner_id=user.id, name=f"f7-{uuid.uuid4().hex[:8]}")
    db_session.add(label)
    db_session.flush()
    task = _task(db_session, user.id, project_id=project.id, is_completed=False)
    db_session.add(TaskLabel(task_id=task.id, label_id=label.id))
    db_session.flush()
    ghost = uuid.uuid4()
    result = _apply(
        db_session,
        user.id,
        {
            "v": 1,
            "dimensions": {
                "project_ids": [str(project.id)],
                "labels": {"ids": [str(label.id), str(ghost)], "match": "any"},
            },
        },
        timezone_name="UTC",
    )
    assert result.unsatisfiable is True
    assert result.invalid_references == [
        {"kind": "label", "id": str(ghost), "dimension": "labels"}
    ]
    assert task.id not in _ids(result)


def test_label_any_versus_all(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    label_a = Label(owner_id=user.id, name=f"f7a-{uuid.uuid4().hex[:8]}")
    label_b = Label(owner_id=user.id, name=f"f7b-{uuid.uuid4().hex[:8]}")
    db_session.add_all([label_a, label_b])
    db_session.flush()
    only_a = _task(db_session, user.id, project_id=project.id, is_completed=False)
    both = _task(db_session, user.id, project_id=project.id, is_completed=False)
    db_session.add_all(
        [
            TaskLabel(task_id=only_a.id, label_id=label_a.id),
            TaskLabel(task_id=both.id, label_id=label_a.id),
            TaskLabel(task_id=both.id, label_id=label_b.id),
        ]
    )
    db_session.flush()

    def members(match: str) -> set[uuid.UUID]:
        return _ids(
            _apply(
                db_session,
                user.id,
                {
                    "v": 1,
                    "dimensions": {
                        "project_ids": [str(project.id)],
                        "labels": {"ids": [str(label_a.id), str(label_b.id)], "match": match},
                    },
                },
                timezone_name="UTC",
            )
        )

    assert members("any") == {only_a.id, both.id}
    assert members("all") == {both.id}


def test_completion_omitted_includes_done_and_workflow_stays_open(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    open_ready = _task(
        db_session,
        user.id,
        project_id=project.id,
        is_completed=False,
        workflow_state=TaskWorkflowState.ready,
    )
    done_ready = _task(
        db_session,
        user.id,
        project_id=project.id,
        is_completed=True,
        workflow_state=TaskWorkflowState.ready,
    )
    open_waiting = _task(
        db_session,
        user.id,
        project_id=project.id,
        is_completed=False,
        workflow_state=TaskWorkflowState.waiting,
    )
    scoped = {"project_ids": [str(project.id)]}
    both = _ids(
        _apply(
            db_session,
            user.id,
            {"v": 1, "dimensions": scoped},
            timezone_name="UTC",
        )
    )
    assert both == {open_ready.id, done_ready.id, open_waiting.id}
    open_only = _ids(
        _apply(
            db_session,
            user.id,
            {"v": 1, "dimensions": {**scoped, "completion": "open"}},
            timezone_name="UTC",
        )
    )
    assert open_only == {open_ready.id, open_waiting.id}
    waiting = _ids(
        _apply(
            db_session,
            user.id,
            {"v": 1, "dimensions": {**scoped, "workflow_states": ["waiting"]}},
            timezone_name="UTC",
        )
    )
    assert waiting == {open_waiting.id}


def test_priority_and_schedule_filters(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    hot = _task(
        db_session,
        user.id,
        project_id=project.id,
        priority=TaskPriority.p1,
        status=ScheduleStatus.overbooked,
        schedule_style=ScheduleStyle.manual,
        is_completed=False,
    )
    other = _task(
        db_session,
        user.id,
        project_id=project.id,
        priority=TaskPriority.p4,
        status=ScheduleStatus.unscheduled,
        schedule_style=ScheduleStyle.standalone,
        is_completed=False,
    )
    matched = _ids(
        _apply(
            db_session,
            user.id,
            {
                "v": 1,
                "dimensions": {
                    "project_ids": [str(project.id)],
                    "priorities": ["p1"],
                    "schedule_statuses": ["overbooked"],
                    "schedule_styles": ["manual"],
                },
            },
            timezone_name="UTC",
        )
    )
    assert matched == {hot.id}
    assert other.id not in matched


def test_epic_filter_and_archive_exclusion(db_session: Session) -> None:
    user = _owner(db_session)
    live_epic = Epic(owner_id=user.id, title=f"f7-epic-{uuid.uuid4().hex[:8]}", is_archived=False)
    archived_epic = Epic(
        owner_id=user.id, title=f"f7-epic-arch-{uuid.uuid4().hex[:8]}", is_archived=True
    )
    db_session.add_all([live_epic, archived_epic])
    db_session.flush()
    live_project = _project(db_session, user.id, epic_id=live_epic.id)
    archived_project = _project(db_session, user.id, archived=True, epic_id=live_epic.id)
    under_archived_epic = _project(db_session, user.id, epic_id=archived_epic.id)
    live_task = _task(db_session, user.id, project_id=live_project.id, is_completed=False)
    archived_project_task = _task(
        db_session, user.id, project_id=archived_project.id, is_completed=False
    )
    archived_epic_task = _task(
        db_session, user.id, project_id=under_archived_epic.id, is_completed=False
    )
    inbox = _task(db_session, user.id, project_id=None, is_completed=False)
    trashed = _task(
        db_session,
        user.id,
        project_id=live_project.id,
        is_completed=False,
        deleted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    epic_result = _apply(
        db_session,
        user.id,
        {"v": 1, "dimensions": {"epic_ids": [str(live_epic.id)], "completion": "any"}},
        timezone_name="UTC",
    )
    epic_ids = _ids(epic_result)
    assert live_task.id in epic_ids
    assert archived_project_task.id not in epic_ids
    assert archived_epic_task.id not in epic_ids
    assert trashed.id not in epic_ids

    # Route currently treats epic_ids as explicit project scope. The engine
    # still excludes archived containers when project_ids is absent.
    widened = db_session.query(Task).filter(Task.owner_id == user.id)
    widened = apply_default_task_visibility(widened, explicit_project_filter=True)
    widened_result = apply_predicate_to_query(
        widened,
        db_session,
        user.id,
        {"v": 1, "dimensions": {"epic_ids": [str(live_epic.id)], "completion": "any"}},
        timezone_name="UTC",
    )
    widened_ids = _ids(widened_result)
    assert live_task.id in widened_ids
    assert archived_project_task.id not in widened_ids

    project_scope = _ids(
        _apply(
            db_session,
            user.id,
            {
                "v": 1,
                "dimensions": {
                    "project_ids": [str(archived_project.id)],
                    "completion": "any",
                },
            },
            timezone_name="UTC",
        )
    )
    assert archived_project_task.id in project_scope
    assert trashed.id not in project_scope

    inbox_ids = _ids(
        _apply(db_session, user.id, INBOX_PREDICATE_V1, timezone_name="UTC")
    )
    assert inbox.id in inbox_ids
    assert live_task.id not in inbox_ids
    assert archived_project_task.id not in inbox_ids


def test_visibility_outerjoin_still_applies_inbox_predicate(db_session: Session) -> None:
    """Route order: archive outerjoin, then apply. EXISTS must keep its FROM."""
    user = _owner(db_session)
    inbox = _task(db_session, user.id, project_id=None, is_completed=False)
    archived = _project(db_session, user.id, archived=True)
    hidden = _task(db_session, user.id, project_id=archived.id, is_completed=False)
    query = db_session.query(Task).filter(Task.owner_id == user.id)
    query = apply_default_task_visibility(query, explicit_project_filter=False)
    result = apply_predicate_to_query(
        query,
        db_session,
        user.id,
        INBOX_PREDICATE_V1,
        timezone_name="UTC",
    )
    found = _ids(result)
    assert inbox.id in found
    assert hidden.id not in found


def test_missing_epic_is_reported(db_session: Session) -> None:
    user = _owner(db_session)
    ghost = uuid.uuid4()
    result = _apply(
        db_session,
        user.id,
        {"v": 1, "dimensions": {"epic_ids": [str(ghost)]}},
        timezone_name="UTC",
    )
    assert result.unsatisfiable is True
    assert result.invalid_references == [
        {"kind": "epic", "id": str(ghost), "dimension": "epic_ids"}
    ]


def test_query_binds_parameters_and_does_not_embed_timezone_sql(db_session: Session) -> None:
    user = _owner(db_session)
    project = _project(db_session, user.id)
    result = _apply(
        db_session,
        user.id,
        {
            "v": 1,
            "dimensions": {
                "project_ids": [str(project.id)],
                "due": {"kind": "rolling", "rolling": "today"},
            },
        },
        timezone_name="Pacific/Auckland",
        now=AUCKLAND_NOW,
    )
    compiled = result.query.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "AT TIME ZONE" not in sql.upper()
    assert "Pacific/Auckland" not in sql
    assert str(project.id) not in sql
    bound = " ".join(str(value) for value in compiled.params.values())
    assert str(project.id) in bound

