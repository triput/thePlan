"""Compile a validated v1 predicate into SQLAlchemy filters on ``Task``.

Bounds are computed in Python from ``user_settings.timezone`` (passed in as
``timezone_name``) at query time. Fixed ranges stay absolute timestamptz.
Nothing in the predicate is interpolated into SQL text; comparisons use bound
parameters and ORM expressions only.

Jules: build an owner-scoped ``Query`` and call :func:`apply_predicate_to_query`.
Pass ``settings.timezone``. ``upcoming_horizon_days`` is used only when a
``within_days`` dimension has no ``days`` value; :func:`validate_predicate`
always writes ``days`` (default 7), so a saved Upcoming predicate does not
track the settings horizon by itself.

Rolling windows (half-open, owner timezone):

* ``today`` — ``[local midnight, next local midnight)``.
* ``next_7_days`` — ``[local midnight, local midnight + 7 days)`` (includes today).
* ``this_calendar_week`` — ISO week, Monday 00:00 through the next Monday 00:00.
  There is no week-start setting.
* ``within_days`` — Upcoming: ``[start of tomorrow, start of today + (days + 1) days)``.
  ``days=7`` is tomorrow through local day+7, and does not include today.

``due.kind = unbounded`` stores an explicit non-constraint (null and non-null
``due_at`` both match). ``due.kind = none`` is ``due_at IS NULL``.

Visibility applied here, even if the route also calls
:func:`apply_default_task_visibility`:

* Trashed tasks (``deleted_at`` set) stay excluded. v1 has no trash dimension.
* Tasks in an archived project, or a project under an archived epic, stay
  excluded unless ``project_ids`` is set (explicit project scope, same idea as
  ``GET /tasks?project_id=``). ``epic_ids`` does not widen that exclusion.
* Omitted ``completion`` matches open and done. System seeds set ``open``.
* ``workflow_states`` matches open tasks in those states.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, exists, false, or_
from sqlalchemy.orm import Query, Session, aliased

from app.api.errors import ApiError
from app.models import Epic, Project, Task, TaskLabel
from app.models.enums import ScheduleStatus, ScheduleStyle, TaskPriority, TaskWorkflowState
from app.services.saved_filter_predicate import (
    MAX_WITHIN_DAYS,
    check_missing_refs,
    validate_predicate,
)

UTC = timezone.utc


@dataclass
class PredicateApplyResult:
    query: Query
    unsatisfiable: bool = False
    invalid_references: list[dict[str, str]] = field(default_factory=list)


def apply_predicate_to_query(
    query: Query,
    db: Session,
    owner_id: uuid.UUID,
    predicate: dict[str, Any],
    *,
    timezone_name: str,
    upcoming_horizon_days: int = 7,
    now: datetime | None = None,
) -> PredicateApplyResult:
    """Filter ``query`` by a v1 predicate.

    When any project, epic, or label id is missing for ``owner_id``, the query
    matches nothing and ``invalid_references`` lists those ids. Sibling ids in
    the same OR list are not kept.
    """
    normalized = validate_predicate(predicate)
    missing = check_missing_refs(db, owner_id, normalized)
    if missing:
        return PredicateApplyResult(
            query=query.filter(Task.owner_id == owner_id, false()),
            unsatisfiable=True,
            invalid_references=missing,
        )

    dims = normalized["dimensions"]
    moment = _aware_now(now)
    query = query.filter(Task.owner_id == owner_id, Task.deleted_at.is_(None))
    if not dims.get("project_ids"):
        query = _exclude_archived(query, owner_id)

    if dims.get("inbox"):
        query = query.filter(Task.project_id.is_(None))

    project_ids = _uuids(dims.get("project_ids") or [], field="dimensions.project_ids")
    if project_ids:
        query = query.filter(Task.project_id.in_(project_ids))

    epic_ids = _uuids(dims.get("epic_ids") or [], field="dimensions.epic_ids")
    if epic_ids:
        # Alias so this EXISTS keeps its own FROM when the caller already
        # outer-joined projects (apply_default_task_visibility).
        project_match = aliased(Project)
        query = query.filter(
            exists()
            .where(project_match.id == Task.project_id)
            .where(project_match.owner_id == owner_id)
            .where(project_match.epic_id.in_(epic_ids))
        )

    labels = dims.get("labels")
    if labels:
        label_ids = _uuids(labels["ids"], field="dimensions.labels.ids")
        if labels["match"] == "any":
            query = query.filter(
                exists()
                .where(TaskLabel.task_id == Task.id)
                .where(TaskLabel.label_id.in_(label_ids))
            )
        else:
            for label_id in label_ids:
                query = query.filter(
                    exists()
                    .where(TaskLabel.task_id == Task.id)
                    .where(TaskLabel.label_id == label_id)
                )

    priorities = dims.get("priorities") or []
    if priorities:
        query = query.filter(Task.priority.in_(_enums(priorities, TaskPriority, "dimensions.priorities")))

    workflow_states = dims.get("workflow_states") or []
    if workflow_states:
        query = query.filter(
            Task.is_completed.is_(False),
            Task.workflow_state.in_(
                _enums(workflow_states, TaskWorkflowState, "dimensions.workflow_states")
            ),
        )

    completion = dims.get("completion")
    if completion == "open":
        query = query.filter(Task.is_completed.is_(False))
    elif completion == "done":
        query = query.filter(Task.is_completed.is_(True))

    schedule_statuses = dims.get("schedule_statuses") or []
    if schedule_statuses:
        query = query.filter(
            Task.status.in_(_enums(schedule_statuses, ScheduleStatus, "dimensions.schedule_statuses"))
        )

    schedule_styles = dims.get("schedule_styles") or []
    if schedule_styles:
        query = query.filter(
            Task.schedule_style.in_(
                _enums(schedule_styles, ScheduleStyle, "dimensions.schedule_styles")
            )
        )

    due = dims.get("due")
    if due is not None:
        query = _apply_due_filter(
            query,
            due,
            timezone_name=timezone_name,
            upcoming_horizon_days=upcoming_horizon_days,
            now=moment,
        )

    return PredicateApplyResult(query=query)


def apply_default_task_visibility(query: Query, *, explicit_project_filter: bool) -> Query:
    """Trash excluded; archived project/epic hidden unless project scope is explicit.

    Pass ``explicit_project_filter=True`` only when the predicate sets
    ``project_ids``. ``epic_ids`` keeps the archive exclusion.
    :func:`apply_predicate_to_query` applies the same rule itself.
    """
    query = query.filter(Task.deleted_at.is_(None))
    if not explicit_project_filter:
        query = query.outerjoin(Project, Task.project_id == Project.id).outerjoin(
            Epic, Project.epic_id == Epic.id
        )
        query = query.filter(
            or_(
                Task.project_id.is_(None),
                and_(
                    Project.is_archived.is_(False),
                    or_(
                        Project.epic_id.is_(None),
                        Epic.is_archived.is_(False),
                    ),
                ),
            )
        )
    return query


def rolling_due_window(
    due: dict[str, Any],
    *,
    timezone_name: str,
    now: datetime,
    upcoming_horizon_days: int = 7,
) -> tuple[datetime, datetime]:
    """Return the half-open UTC window for a rolling ``due`` object."""
    if due.get("kind") != "rolling":
        raise ApiError(
            422,
            "rolling_due_window requires due.kind rolling",
            "INVALID_PREDICATE",
            field="dimensions.due.kind",
        )
    tz = _zone(timezone_name)
    moment = _aware_now(now).astimezone(tz)
    start_today = datetime.combine(moment.date(), time.min, tzinfo=tz)
    rolling = due.get("rolling")
    if rolling == "today":
        end = start_today + timedelta(days=1)
        return _utc_pair(start_today, end)
    if rolling == "next_7_days":
        end = start_today + timedelta(days=7)
        return _utc_pair(start_today, end)
    if rolling == "this_calendar_week":
        week_start = start_today - timedelta(days=start_today.weekday())
        week_end = week_start + timedelta(days=7)
        return _utc_pair(week_start, week_end)
    if rolling == "within_days":
        days = _resolve_within_days(due, upcoming_horizon_days)
        start = start_today + timedelta(days=1)
        end = start_today + timedelta(days=days + 1)
        return _utc_pair(start, end)
    raise ApiError(
        422,
        "dimensions.due.rolling is invalid",
        "INVALID_PREDICATE",
        field="dimensions.due.rolling",
    )


def _apply_due_filter(
    query: Query,
    due: dict[str, Any],
    *,
    timezone_name: str,
    upcoming_horizon_days: int,
    now: datetime,
) -> Query:
    kind = due.get("kind")
    if kind == "none":
        return query.filter(Task.due_at.is_(None))
    if kind == "unbounded":
        return query
    if kind == "fixed":
        start = _parse_fixed_bound(due.get("from"), field="dimensions.due.from")
        end = _parse_fixed_bound(due.get("to"), field="dimensions.due.to")
        return query.filter(Task.due_at.isnot(None), Task.due_at >= start, Task.due_at < end)
    if kind == "rolling":
        start, end = rolling_due_window(
            due,
            timezone_name=timezone_name,
            now=now,
            upcoming_horizon_days=upcoming_horizon_days,
        )
        return query.filter(Task.due_at.isnot(None), Task.due_at >= start, Task.due_at < end)
    raise ApiError(
        422,
        "dimensions.due.kind is invalid",
        "INVALID_PREDICATE",
        field="dimensions.due.kind",
    )


def _exclude_archived(query: Query, owner_id: uuid.UUID) -> Query:
    # Aliases stay in the subquery FROM even when the outer query already
    # joined Project/Epic. Correlating those tables drops the FROM clause.
    project = aliased(Project)
    epic = aliased(Epic)
    live_epic = (
        exists()
        .where(epic.id == project.epic_id)
        .where(epic.owner_id == owner_id)
        .where(epic.is_archived.is_(False))
    )
    live_project = (
        exists()
        .where(project.id == Task.project_id)
        .where(project.owner_id == owner_id)
        .where(project.is_archived.is_(False))
        .where(or_(project.epic_id.is_(None), live_epic))
    )
    return query.filter(or_(Task.project_id.is_(None), live_project))


def _resolve_within_days(due: dict[str, Any], upcoming_horizon_days: int) -> int:
    days = due["days"] if "days" in due else upcoming_horizon_days
    if isinstance(days, bool) or not isinstance(days, int) or days < 1 or days > MAX_WITHIN_DAYS:
        raise ApiError(
            422,
            f"dimensions.due.days must be an integer from 1 to {MAX_WITHIN_DAYS}",
            "INVALID_PREDICATE",
            field="dimensions.due.days",
        )
    return days


def _zone(timezone_name: str) -> ZoneInfo:
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise ApiError(422, "timezone is required", "INVALID_TIMEZONE", field="timezone")
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ApiError(
            422,
            f"unknown timezone {timezone_name}",
            "INVALID_TIMEZONE",
            field="timezone",
        ) from exc


def _aware_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ApiError(422, "now must be timezone-aware", "INVALID_PREDICATE", field="now")
    return now.astimezone(UTC)


def _utc_pair(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    return (start.astimezone(UTC), end.astimezone(UTC))


def _parse_fixed_bound(raw: object, *, field: str) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise ApiError(
            422,
            f"{field} must be a timezone-aware ISO-8601 string",
            "INVALID_PREDICATE",
            field=field,
        )
    text = raw.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ApiError(
            422,
            f"{field} must be a timezone-aware ISO-8601 string",
            "INVALID_PREDICATE",
            field=field,
        ) from exc
    if parsed.tzinfo is None:
        raise ApiError(
            422,
            f"{field} must include a timezone offset",
            "INVALID_PREDICATE",
            field=field,
        )
    return parsed.astimezone(UTC)


def _uuids(values: list[Any], *, field: str) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    for item in values:
        try:
            parsed.append(item if isinstance(item, uuid.UUID) else uuid.UUID(str(item)))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ApiError(
                422, f"{field} contains an invalid uuid", "INVALID_PREDICATE", field=field
            ) from exc
    return parsed


def _enums(values: list[str], enum_cls: type[Any], field_name: str) -> list[Any]:
    parsed: list[Any] = []
    for value in values:
        try:
            parsed.append(enum_cls(value))
        except ValueError as exc:
            raise ApiError(
                422,
                f"{field_name} contains an unsupported value",
                "INVALID_PREDICATE",
                field=field_name,
            ) from exc
    return parsed
