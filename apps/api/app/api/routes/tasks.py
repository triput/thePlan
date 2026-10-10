from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, inspect as sa_inspect, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.db import get_db
from app.models.enums import TaskBoardColumn, TaskWorkflowState
from app.models import Epic, Plan, Project, RecurrenceRule, Reminder, Task, User
from app.schemas import (
    PaginatedResponse,
    ProjectOut,
    RecurrenceOut,
    RecurrenceUpsert,
    ReminderCreate,
    ReminderOut,
    ReorderRequest,
    TaskBatchUpdate,
    TaskBatchUpdateResponse,
    TaskCompleteBody,
    TaskCreate,
    TaskOut,
    TaskWorkflowTransition,
    TaskPromoteToProjectBody,
    TaskPromoteToProjectOut,
    TaskUpdate,
)
from app.services.auth_users import get_or_provision_user_settings
from app.services.bundle_blocks import shrink_bundle_blocks_for_completed_members
from app.services.hierarchy_promote import promote_task_to_project
from app.services.ownership import (
    verify_owned_focus_window,
    verify_owned_plan,
    verify_owned_project,
    verify_owned_section,
)
from app.services.recurrence import (
    first_due_at,
    humanize_recurrence,
    spec_from_parts,
    validate_frame,
)
from app.services.reorder import batch_reorder_sort_order
from app.services.task_helpers import (
    collect_open_descendant_ids,
    complete_task,
    empty_trash_for_user,
    hard_purge_trashed_task_subtree,
    mark_task_complete,
    resolve_nesting_level,
    restore_task_subtree,
    soft_delete_task_subtree,
)
from app.services.task_workflow import board_column_for_task, transition_task_workflow
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling
from app.services.task_patch import (
    add_task_labels,
    apply_plan_bind_soft_target,
    apply_task_patch,
    resolve_plan_bind,
    sync_task_labels,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_owned_task(
    db: Session,
    task_id: UUID,
    user: User,
    *,
    for_update: bool = False,
) -> Task:
    query = db.query(Task).filter(Task.id == task_id)
    if for_update:
        query = query.with_for_update()
    else:
        query = query.options(
            joinedload(Task.recurrence_rule),
            joinedload(Task.label_links),
        )
    task = query.one_or_none()
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
    plan_names: dict[UUID, str] | None = None,
) -> TaskOut:
    label_ids = [link.label_id for link in task.label_links]
    open_subtask_count = (
        db.query(Task)
        .filter(
            Task.owner_id == task.owner_id,
            Task.parent_task_id == task.id,
            Task.is_completed.is_(False),
            Task.deleted_at.is_(None),
        )
        .count()
    )
    plan_name: str | None = None
    if task.plan_id is not None:
        if plan_names is not None:
            plan_name = plan_names.get(task.plan_id)
        else:
            plan = db.get(Plan, task.plan_id)
            plan_name = plan.name if plan is not None else None
    mapper = sa_inspect(Task)
    payload = {attr.key: getattr(task, attr.key) for attr in mapper.column_attrs}
    payload.update(
        {
            "board_column": board_column_for_task(task),
            "label_ids": label_ids,
            "open_subtask_count": open_subtask_count,
            "recurrence": recurrence_to_out(task.recurrence_rule),
            "recurrence_advanced": recurrence_advanced,
            "previous_due_at": previous_due_at,
            "plan_name": plan_name,
        }
    )
    return TaskOut.model_validate(payload)


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
    workflow: TaskBoardColumn | None = Query(
        default=None,
        description="Kanban column filter (done uses completion; others require open tasks).",
    ),
    board_order: bool = Query(
        default=False,
        description="When true, order by board_rank then created_at instead of sort_order.",
    ),
    due_from: datetime | None = None,
    due_to: datetime | None = None,
    ids: list[UUID] | None = Query(default=None),
    inbox: bool = Query(default=False),
    trashed: bool = Query(
        default=False,
        description="When true, return only soft-deleted tasks (trash). Default excludes trash.",
    ),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse:
    query = (
        db.query(Task)
        .options(joinedload(Task.recurrence_rule), joinedload(Task.label_links))
        .filter(Task.owner_id == user.id)
    )
    if trashed:
        query = query.filter(Task.deleted_at.isnot(None))
    else:
        query = query.filter(Task.deleted_at.is_(None))
    project_joined = False
    if inbox:
        query = query.filter(Task.project_id.is_(None))
    elif project_id is not None:
        query = query.filter(Task.project_id == project_id)
    if epic_id is not None:
        query = query.join(Project, Task.project_id == Project.id).filter(
            Project.epic_id == epic_id,
            Project.owner_id == user.id,
        )
        project_joined = True
    if section_id is not None:
        query = query.filter(Task.section_id == section_id)
    if parent_task_id is not None:
        query = query.filter(Task.parent_task_id == parent_task_id)
    if label_id is not None:
        query = query.join(TaskLabel, TaskLabel.task_id == Task.id).filter(TaskLabel.label_id == label_id)
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)
    if workflow is not None:
        if workflow == TaskBoardColumn.done:
            query = query.filter(Task.is_completed.is_(True))
        else:
            query = query.filter(
                Task.is_completed.is_(False),
                Task.workflow_state == TaskWorkflowState(workflow.value),
            )
    if due_from is not None:
        query = query.filter(Task.due_at.isnot(None), Task.due_at >= due_from)
    if due_to is not None:
        query = query.filter(Task.due_at.isnot(None), Task.due_at < due_to)
    if ids:
        query = query.filter(Task.id.in_(ids))
    # Exclude archived project/epic tasks by default on all non-trash lists.
    # Explicit project_id still returns that project's tasks (archived project detail).
    if not trashed and project_id is None:
        if not project_joined:
            query = query.outerjoin(Project, Task.project_id == Project.id)
        query = query.outerjoin(Epic, Project.epic_id == Epic.id).filter(
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
    total = query.count()
    if board_order or workflow is not None:
        order = (Task.board_rank, Task.created_at)
    else:
        order = (Task.sort_order, Task.created_at)
    items = query.order_by(*order).offset(offset).limit(limit).all()
    plan_ids = {item.plan_id for item in items if item.plan_id is not None}
    plan_names: dict[UUID, str] = {}
    if plan_ids:
        plan_names = {
            row.id: row.name
            for row in db.query(Plan).filter(Plan.owner_id == user.id, Plan.id.in_(plan_ids)).all()
        }
    return PaginatedResponse(
        items=[task_to_out(item, db, plan_names=plan_names) for item in items],
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
    if body.preferred_time_window_id is not None:
        verify_owned_focus_window(db, body.preferred_time_window_id, user)
    explicit_fields = body.model_dump(exclude_unset=True)
    if body.plan_id is not None:
        verify_owned_plan(db, body.plan_id, user)
    try:
        nesting_level = resolve_nesting_level(db, user.id, body.parent_task_id)
    except ApiError as exc:
        raise exc

    if body.estimated_duration_minutes is None:
        user_settings = get_or_provision_user_settings(db, user)
        estimated_duration_minutes = user_settings.default_estimated_duration_minutes
    else:
        estimated_duration_minutes = body.estimated_duration_minutes

    scheduling_settings = lock_owner_scheduling(db, user.id)
    bound_soft_target = resolve_plan_bind(db, user, body.plan_id)
    soft_target_at = apply_plan_bind_soft_target(
        plan_id=body.plan_id,
        explicit_soft_target=body.soft_target_at,
        soft_target_in_request="soft_target_at" in explicit_fields,
        bound_soft_target=bound_soft_target,
    )

    from app.services.task_workflow import next_board_rank

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
        soft_target_at=soft_target_at,
        estimated_duration_minutes=estimated_duration_minutes,
        preferred_time_window_id=body.preferred_time_window_id,
        plan_id=body.plan_id,
        schedule_style=body.schedule_style,
        board_rank=next_board_rank(db, user.id),
    )
    db.add(task)
    db.flush()

    if body.label_ids:
        sync_task_labels(db, task, user, body.label_ids)

    if body.recurrence is not None:
        _upsert_recurrence(db, task, user, body.recurrence)

    increment_scheduling_revision(db, scheduling_settings)
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


@router.patch("/batch", response_model=TaskBatchUpdateResponse)
def batch_update_tasks(
    body: TaskBatchUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskBatchUpdateResponse:
    patch_fields = body.patch.model_dump(exclude_unset=True)
    updated_ids: list[UUID] = []
    for task_id in body.task_ids:
        task = _get_owned_task(db, task_id, user)
        if patch_fields:
            apply_task_patch(db, task, user, body.patch)
        if body.add_label_ids:
            add_task_labels(db, task, user, body.add_label_ids)
        updated_ids.append(task.id)
    db.commit()
    return TaskBatchUpdateResponse(
        items=[task_to_out(_get_owned_task(db, task_id, user), db) for task_id in updated_ids]
    )


@router.delete("/trash", status_code=status.HTTP_204_NO_CONTENT)
def empty_trash(
    older_than_days: int | None = Query(
        None,
        ge=1,
        description=(
            "When set, only permanently delete trashed tasks whose deleted_at "
            "is older than this many days. When omitted, empty all trash."
        ),
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Permanently delete soft-deleted tasks for the current user."""
    empty_trash_for_user(db, user.id, older_than_days=older_than_days)
    db.commit()


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
    apply_task_patch(db, task, user, body)
    db.commit()
    return task_to_out(_get_owned_task(db, task.id, user), db)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    hard: bool = Query(
        default=False,
        description="When true, permanently delete a task already in trash.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Soft-delete task + live descendants (same ``deleted_at`` wave).

    Unpinned ``scheduled_blocks`` for those tasks are hard-deleted (no block
    soft-delete column). Pinned blocks are left. Idempotent if already trashed.

    With ``hard=true``, permanently purge a trashed task subtree (409 if not trashed).
    """
    task = _get_owned_task(db, task_id, user)
    if hard:
        try:
            hard_purge_trashed_task_subtree(db, task)
        except ApiError as exc:
            raise exc
        db.commit()
        return
    if task.deleted_at is None:
        soft_delete_task_subtree(db, task)
        db.commit()


@router.post("/{task_id}/restore", response_model=TaskOut)
def restore_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    """Restore a soft-deleted task and descendants stamped in the same delete wave."""
    task = _get_owned_task(db, task_id, user)
    try:
        restore_task_subtree(db, task)
    except ApiError as exc:
        raise exc
    db.commit()
    return task_to_out(_get_owned_task(db, task.id, user), db)


@router.post("/{task_id}/promote-to-project", response_model=TaskPromoteToProjectOut)
def promote_task_to_project_endpoint(
    task_id: UUID,
    body: TaskPromoteToProjectBody | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskPromoteToProjectOut:
    """DEF-023: create project from task; move task (+ descendants by default) into it."""
    settings = lock_owner_scheduling(db, user.id)
    task = _get_owned_task(db, task_id, user)
    payload = body or TaskPromoteToProjectBody()
    try:
        project, task = promote_task_to_project(
            db,
            task,
            user.id,
            include_descendants=payload.include_descendants,
            epic_id=payload.epic_id,
        )
    except ApiError as exc:
        raise exc
    increment_scheduling_revision(db, settings)
    db.commit()
    db.refresh(project)
    return TaskPromoteToProjectOut(
        project=ProjectOut.model_validate(project),
        task=task_to_out(_get_owned_task(db, task.id, user), db),
    )


@router.post("/{task_id}/workflow", response_model=TaskOut)
def transition_task_workflow_endpoint(
    task_id: UUID,
    body: TaskWorkflowTransition,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user, for_update=True)
    transition_fields = body.model_dump(exclude_unset=True)
    waiting_note_set = "waiting_note" in transition_fields
    bulk_descendant_ids: list[UUID] = []
    if body.bulk_children is True and body.column == TaskBoardColumn.done:
        bulk_descendant_ids = collect_open_descendant_ids(db, task.id, user.id)
    try:
        advanced, previous_due = transition_task_workflow(
            db,
            task,
            column=body.column,
            expected_revision=body.expected_revision,
            waiting_note=body.waiting_note,
            waiting_note_set=waiting_note_set,
            board_rank=body.board_rank,
            insert_before_id=body.insert_before_id,
            insert_after_id=body.insert_after_id,
            bulk_children=body.bulk_children,
            force_parent_only=body.force_parent_only,
        )
    except ApiError as exc:
        raise exc
    if body.column == TaskBoardColumn.done and not advanced:
        db.flush()
        completed_ids = [task.id, *bulk_descendant_ids]
        shrink_bundle_blocks_for_completed_members(db, user, completed_ids)
    db.commit()
    refreshed = _get_owned_task(db, task.id, user)
    return task_to_out(
        refreshed,
        db,
        recurrence_advanced=advanced,
        previous_due_at=previous_due,  # type: ignore[arg-type]
    )


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task_endpoint(
    task_id: UUID,
    body: TaskCompleteBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _get_owned_task(db, task_id, user)
    # Capture open descendants before complete mutates them (bulk path).
    bulk_descendant_ids: list[UUID] = []
    if body.bulk_children is True:
        bulk_descendant_ids = collect_open_descendant_ids(db, task.id, user.id)
    try:
        previous_due, advanced = complete_task(
            db,
            task,
            bulk_children=body.bulk_children,
            force_parent_only=body.force_parent_only,
        )
    except ApiError as exc:
        raise exc
    # DEF-019: shrink calendar bundles when members complete (skip recurrence rollover —
    # member stays incomplete after advance).
    if not advanced:
        db.flush()
        completed_ids = [task.id, *bulk_descendant_ids]
        shrink_bundle_blocks_for_completed_members(db, user, completed_ids)
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
    settings = lock_owner_scheduling(db, user.id)
    task = _get_owned_task(db, task_id, user)
    due_before = task.due_at
    rule = _upsert_recurrence(db, task, user, body)
    # First occurrence fills due_at, which is a fingerprint input. Rule text alone is not.
    if task.due_at != due_before:
        increment_scheduling_revision(db, settings)
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