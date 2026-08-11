from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models import Label, Project, RecurrenceRule, Reminder, Task, TaskLabel, User
from app.schemas import (
    PaginatedResponse,
    RecurrenceOut,
    RecurrenceUpsert,
    ReminderCreate,
    ReminderOut,
    ReorderRequest,
    TaskCompleteBody,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.services.ownership import verify_owned_project, verify_owned_section, verify_owned_task
from app.services.recurrence import (
    first_due_at,
    humanize_recurrence,
    spec_from_parts,
    validate_frame,
)
from app.services.reorder import batch_reorder_sort_order
from app.services.task_helpers import complete_task, mark_task_complete, resolve_nesting_level

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_owned_task(db: Session, task_id: UUID, user: User) -> Task:
    task = (
        db.query(Task)
        .options(joinedload(Task.recurrence_rule), joinedload(Task.label_links))
        .filter(Task.id == task_id)
        .one_or_none()
    )
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def recurrence_to_out(rule: RecurrenceRule | None) -> RecurrenceOut | None:
    if rule is None:
        return None
    from app.services.recurrence import RecurrenceSpec

    spec = RecurrenceSpec(
        rrule=rule.rrule,
        is_fixed=rule.is_fixed,
        timezone=rule.timezone,
        starts_on=rule.starts_on,
        ends_on=rule.ends_on,
    )
    return RecurrenceOut(
        rrule=rule.rrule,
        is_fixed=rule.is_fixed,
        timezone=rule.timezone,
        starts_on=rule.starts_on,
        ends_on=rule.ends_on,
        display=humanize_recurrence(spec),
    )


def task_to_out(
    task: Task,
    db: Session,
    *,
    recurrence_advanced: bool = False,
    previous_due_at: datetime | None = None,
) -> TaskOut:
    label_ids = [link.label_id for link in task.label_links]
    open_subtask_count = (
        db.query(Task)
        .filter(
            Task.owner_id == task.owner_id,
            Task.parent_task_id == task.id,
            Task.is_completed.is_(False),
        )
        .count()
    )
    return TaskOut.model_validate(
        {
            **TaskOut.model_validate(task).model_dump(),
            "label_ids": label_ids,
            "open_subtask_count": open_subtask_count,
            "recurrence": recurrence_to_out(task.recurrence_rule),
            "recurrence_advanced": recurrence_advanced,
            "previous_due_at": previous_due_at,
        }
    )


def _sync_task_labels(db: Session, task: Task, user: User, label_ids: list[UUID]) -> None:
    labels = db.query(Label).filter(Label.owner_id == user.id, Label.id.in_(label_ids)).all()
    found_ids = {label.id for label in labels}
    missing = [str(label_id) for label_id in label_ids if label_id not in found_ids]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Labels not found: {', '.join(missing)}")

    db.query(TaskLabel).filter(TaskLabel.task_id == task.id).delete(synchronize_session=False)
    for label in labels:
        db.add(TaskLabel(task_id=task.id, label_id=label.id))


def _upsert_recurrence(
    db: Session,
    task: Task,
    user: User,
    body: RecurrenceUpsert,
) -> RecurrenceRule:
    timezone_name = body.timezone or (user.settings.timezone if user.settings else "UTC")
    if body.text:
        spec = spec_from_parts(text=body.text, timezone=timezone_name)
        extras = body.model_dump(exclude_unset=True)
        if "starts_on" in extras:
            spec.starts_on = extras["starts_on"]
        if "ends_on" in extras:
            spec.ends_on = extras["ends_on"]
        validate_frame(spec.starts_on, spec.ends_on)
    else:
        if not body.rrule:
            raise ApiError(422, "rrule or text is required", "INVALID_RECURRENCE")
        spec = spec_from_parts(
            rrule=body.rrule,
            is_fixed=body.is_fixed,
            timezone=timezone_name,
            starts_on=body.starts_on,
            ends_on=body.ends_on,
        )

    rule = (
        db.query(RecurrenceRule)
        .filter(RecurrenceRule.task_id == task.id)
        .one_or_none()
    )
    if rule is None:
        rule = RecurrenceRule(owner_id=user.id, task_id=task.id)
        db.add(rule)

    rule.rrule = spec.rrule
    rule.is_fixed = spec.is_fixed
    rule.timezone = spec.timezone
    rule.starts_on = spec.starts_on
    rule.ends_on = spec.ends_on
    db.flush()
    task.recurrence_rule = rule

    if task.due_at is None:
        first = first_due_at(spec)
        if first is not None:
            task.due_at = first
    return rule


@router.get("", response_model=PaginatedResponse)
def list_tasks(
    project_id: UUID | None = None,
    section_id: UUID | None = None,
    parent_task_id: UUID | None = None,
    label_id: UUID | None = None,
    epic_id: UUID | None = None,
    is_completed: bool | None = None,
    due_from: datetime | None = None,
    due_to: datetime | None = None,
    inbox: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = (
        db.query(Task)
        .options(joinedload(Task.recurrence_rule), joinedload(Task.label_links))
        .filter(Task.owner_id == user.id)
    )
    if inbox:
        query = query.filter(Task.project_id.is_(None))
    elif project_id is not None:
        query = query.filter(Task.project_id == project_id)
    if epic_id is not None:
        query = query.join(Project, Task.project_id == Project.id).filter(
            Project.epic_id == epic_id,
            Project.owner_id == user.id,
        )
    if section_id is not None:
        query = query.filter(Task.section_id == section_id)
    if parent_task_id is not None:
        query = query.filter(Task.parent_task_id == parent_task_id)
    if label_id is not None:
        query = query.join(TaskLabel, TaskLabel.task_id == Task.id).filter(TaskLabel.label_id == label_id)
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)
    if due_from is not None:
        query = query.filter(Task.due_at.isnot(None), Task.due_at >= due_from)
    if due_to is not None:
        query = query.filter(Task.due_at.isnot(None), Task.due_at < due_to)
    total = query.count()
    items = query.order_by(Task.sort_order, Task.created_at).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[task_to_out(item, db) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    if body.project_id is not None:
        verify_owned_project(db, body.project_id, user)
    if body.section_id is not None:
        verify_owned_section(db, body.section_id, user)
    try:
        nesting_level = resolve_nesting_level(db, user.id, body.parent_task_id)
    except ApiError as exc:
        raise exc

    task = Task(
        owner_id=user.id,
        title=body.title.strip(),
        description=body.description,
        project_id=body.project_id,
        section_id=body.section_id,
        parent_task_id=body.parent_task_id,
        nesting_level=nesting_level,
        priority=body.priority,
        due_at=body.due_at,
        deadline_at=body.deadline_at,
        soft_target_at=body.soft_target_at,
        estimated_duration_minutes=body.estimated_duration_minutes,
    )
    db.add(task)
    db.flush()

    if body.label_ids:
        _sync_task_labels(db, task, user, body.label_ids)

    if body.recurrence is not None:
        _upsert_recurrence(db, task, user, body.recurrence)

    db.commit()
    db.refresh(task)
    return task_to_out(_get_owned_task(db, task.id, user), db)


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_tasks(
    body: ReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    batch_reorder_sort_order(
        db,
        Task,
        user.id,
        body.items,
        not_found_detail="Tasks not found",
    )


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    return task_to_out(task, db)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: UUID,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    updates = body.model_dump(exclude_unset=True)
    label_ids = updates.pop("label_ids", None)

    if "title" in updates and updates["title"] is not None:
        updates["title"] = updates["title"].strip()

    if "project_id" in updates and updates["project_id"] is not None:
        verify_owned_project(db, updates["project_id"], user)
    if "section_id" in updates and updates["section_id"] is not None:
        verify_owned_section(db, updates["section_id"], user)
    if "parent_task_id" in updates and updates["parent_task_id"] is not None:
        verify_owned_task(db, updates["parent_task_id"], user)

    if "parent_task_id" in updates:
        try:
            updates["nesting_level"] = resolve_nesting_level(db, user.id, updates["parent_task_id"])
        except ApiError as exc:
            raise exc

    for field, value in updates.items():
        setattr(task, field, value)

    if label_ids is not None:
        _sync_task_labels(db, task, user, label_ids)

    db.commit()
    return task_to_out(_get_owned_task(db, task.id, user), db)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    task = _get_owned_task(db, task_id, user)
    db.delete(task)
    db.commit()


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task_endpoint(
    task_id: UUID,
    body: TaskCompleteBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    try:
        previous_due, advanced = complete_task(
            db,
            task,
            bulk_children=body.bulk_children,
            force_parent_only=body.force_parent_only,
        )
    except ApiError as exc:
        raise exc
    db.commit()
    refreshed = _get_owned_task(db, task.id, user)
    return task_to_out(
        refreshed,
        db,
        recurrence_advanced=advanced,
        previous_due_at=previous_due,
    )


@router.post("/{task_id}/uncomplete", response_model=TaskOut)
def uncomplete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    mark_task_complete(task, completed=False)
    db.commit()
    return task_to_out(_get_owned_task(db, task.id, user), db)


@router.get("/{task_id}/recurrence", response_model=RecurrenceOut)
def get_recurrence(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecurrenceOut:
    task = _get_owned_task(db, task_id, user)
    out = recurrence_to_out(task.recurrence_rule)
    if out is None:
        raise ApiError(404, "Recurrence not found", "RECURRENCE_NOT_FOUND")
    return out


@router.put("/{task_id}/recurrence", response_model=RecurrenceOut)
def put_recurrence(
    task_id: UUID,
    body: RecurrenceUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecurrenceOut:
    task = _get_owned_task(db, task_id, user)
    rule = _upsert_recurrence(db, task, user, body)
    db.commit()
    db.refresh(rule)
    return recurrence_to_out(rule)  # type: ignore[return-value]


@router.delete("/{task_id}/recurrence", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurrence(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    task = _get_owned_task(db, task_id, user)
    if task.recurrence_rule is not None:
        db.delete(task.recurrence_rule)
        db.commit()


@router.get("/{task_id}/reminders", response_model=list[ReminderOut])
def list_task_reminders(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReminderOut]:
    _get_owned_task(db, task_id, user)
    rows = (
        db.query(Reminder)
        .filter(Reminder.task_id == task_id, Reminder.owner_id == user.id)
        .order_by(Reminder.fire_at.asc())
        .all()
    )
    return [ReminderOut.model_validate(row) for row in rows]


@router.post(
    "/{task_id}/reminders",
    response_model=ReminderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_task_reminder(
    task_id: UUID,
    body: ReminderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReminderOut:
    _get_owned_task(db, task_id, user)
    reminder = Reminder(
        owner_id=user.id,
        task_id=task_id,
        fire_at=body.fire_at,
        channel=body.channel,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return ReminderOut.model_validate(reminder)