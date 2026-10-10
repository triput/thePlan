"""Task PATCH / batch field-update rules (section-project, plan bind, labels)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Label, Section, Task, TaskLabel, User
from app.schemas import TaskUpdate
from app.services.ownership import (
    verify_owned_focus_window,
    verify_owned_plan,
    verify_owned_project,
    verify_owned_section,
    verify_owned_task,
)
from app.services.scheduling_revision import (
    increment_scheduling_revision,
    lock_owner_scheduling,
    task_patch_touches_scheduling,
)
from app.services.task_helpers import collect_descendant_ids, resolve_nesting_level

# Sentinel for "field omitted" vs explicit null on soft_target_at / plan_id.
MISSING = object()


def resolve_plan_bind(
    db: Session,
    user: User,
    plan_id: UUID | None,
) -> datetime | None:
    """Return plan soft_target_at when binding, or None if plan has no frame."""
    if plan_id is None:
        return None
    plan = verify_owned_plan(db, plan_id, user)
    return plan.soft_target_at


def apply_plan_bind_soft_target(
    *,
    plan_id: UUID | None,
    explicit_soft_target: datetime | None,
    soft_target_in_request: bool,
    bound_soft_target: datetime | None,
) -> datetime | None:
    soft_target_at = explicit_soft_target if soft_target_in_request else None
    if plan_id is not None and bound_soft_target is not None:
        soft_target_at = bound_soft_target
    if soft_target_in_request:
        soft_target_at = explicit_soft_target
    return soft_target_at


def _load_owned_labels(db: Session, user: User, label_ids: list[UUID]) -> list[Label]:
    labels = db.query(Label).filter(Label.owner_id == user.id, Label.id.in_(label_ids)).all()
    found_ids = {label.id for label in labels}
    missing = [str(label_id) for label_id in label_ids if label_id not in found_ids]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Labels not found: {', '.join(missing)}")
    return labels


def sync_task_labels(db: Session, task: Task, user: User, label_ids: list[UUID]) -> None:
    labels = _load_owned_labels(db, user, label_ids)

    db.query(TaskLabel).filter(TaskLabel.task_id == task.id).delete(synchronize_session=False)
    db.expire(task, ["label_links"])
    for label in labels:
        db.add(TaskLabel(task_id=task.id, label_id=label.id))


def add_task_labels(db: Session, task: Task, user: User, label_ids: list[UUID]) -> None:
    """Merge labels onto a task without replacing existing links (batch add_label_ids)."""
    if not label_ids:
        return
    labels = _load_owned_labels(db, user, label_ids)
    # Task is loaded with joinedload(label_links). Adding a TaskLabel only via
    # db.add(task_id=...) leaves it out of that collection; SQLAlchemy then
    # disassociates it and tries to NULL task_labels.task_id (a PK).
    existing = {link.label_id for link in task.label_links}
    for label in labels:
        if label.id not in existing:
            task.label_links.append(TaskLabel(task_id=task.id, label_id=label.id))
    db.expire(task, ["label_links"])


def section_belongs_to_project(
    db: Session, section_id: UUID, project_id: UUID | None
) -> bool:
    if project_id is None:
        return False
    section = db.get(Section, section_id)
    return section is not None and section.project_id == project_id


def apply_task_patch(db: Session, task: Task, user: User, body: TaskUpdate) -> None:
    updates = body.model_dump(exclude_unset=True)
    label_ids = updates.pop("label_ids", None)
    soft_target_at = updates.pop("soft_target_at", MISSING)
    plan_id = updates.pop("plan_id", MISSING)
    section_explicit = "section_id" in updates
    touches_scheduling = task_patch_touches_scheduling(
        updates,
        plan_touched=plan_id is not MISSING,
        soft_target_touched=soft_target_at is not MISSING,
    )
    scheduling_settings = (
        lock_owner_scheduling(db, task.owner_id) if touches_scheduling else None
    )

    if "title" in updates and updates["title"] is not None:
        updates["title"] = updates["title"].strip()

    if "project_id" in updates and updates["project_id"] is not None:
        verify_owned_project(db, updates["project_id"], user)
    if "section_id" in updates and updates["section_id"] is not None:
        verify_owned_section(db, updates["section_id"], user)
    if "parent_task_id" in updates and updates["parent_task_id"] is not None:
        verify_owned_task(db, updates["parent_task_id"], user)

    if "preferred_time_window_id" in updates and updates["preferred_time_window_id"] is not None:
        verify_owned_focus_window(db, updates["preferred_time_window_id"], user)

    if "parent_task_id" in updates:
        new_parent_id = updates["parent_task_id"]
        if new_parent_id == task.id:
            raise ApiError(
                422,
                "Task cannot be its own parent",
                "PARENT_CYCLE",
            )
        if new_parent_id is not None:
            descendant_ids = set(collect_descendant_ids(db, task.id, user.id))
            if new_parent_id in descendant_ids:
                raise ApiError(
                    422,
                    "Cannot reparent task under its descendant",
                    "PARENT_CYCLE",
                )
        try:
            updates["nesting_level"] = resolve_nesting_level(db, user.id, new_parent_id)
        except ApiError as exc:
            raise exc

    # Sections are project-scoped. Moving project without an explicit section clears
    # an orphaned section_id (constraint: section requires project; wrong-project FK is worse).
    if "project_id" in updates and not section_explicit:
        new_project_id = updates["project_id"]
        effective_section = task.section_id
        if effective_section is not None and not section_belongs_to_project(
            db, effective_section, new_project_id
        ):
            updates["section_id"] = None
    elif section_explicit and updates.get("section_id") is not None:
        target_project = updates["project_id"] if "project_id" in updates else task.project_id
        if not section_belongs_to_project(db, updates["section_id"], target_project):
            raise ApiError(
                422,
                "Section does not belong to the task project",
                "SECTION_PROJECT_MISMATCH",
            )

    if plan_id is not MISSING:
        if plan_id is not None:
            verify_owned_plan(db, plan_id, user)
            task.plan_id = plan_id
            bound_soft_target = resolve_plan_bind(db, user, plan_id)
            if bound_soft_target is not None:
                task.soft_target_at = bound_soft_target
        else:
            task.plan_id = None

    for field, value in updates.items():
        setattr(task, field, value)

    if soft_target_at is not MISSING:
        task.soft_target_at = soft_target_at

    if label_ids is not None:
        sync_task_labels(db, task, user, label_ids)

    if touches_scheduling and scheduling_settings is not None:
        increment_scheduling_revision(db, scheduling_settings)
