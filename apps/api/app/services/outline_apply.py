"""Apply approved outline actions — Theme F / ADR-011."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Epic, Project, Section, Task, TaskLabel, User
from app.models.enums import TaskPriority
from app.schemas import (
    OutlineAction,
    OutlineApplyResultItem,
    OutlineCreateEpicAction,
    OutlineCreateProjectAction,
    OutlineCreateSectionAction,
    OutlineCreateTaskAction,
)
from app.services.assist_apply import _ensure_labels
from app.services.auth_users import get_or_provision_user_settings
from app.services.scheduling_revision import increment_scheduling_revision, lock_owner_scheduling


def apply_outline_actions(
    db: Session,
    user: User,
    actions: list[OutlineAction],
) -> list[OutlineApplyResultItem]:
    results: list[OutlineApplyResultItem] = []
    key_map: dict[str, UUID] = {}
    settings = get_or_provision_user_settings(db, user)
    creates_task = any(isinstance(action, OutlineCreateTaskAction) for action in actions)
    scheduling_settings = lock_owner_scheduling(db, user.id) if creates_task else None

    for action in actions:
        title = action.title.strip() if action.title else ""
        if not title:
            results.append(
                OutlineApplyResultItem(
                    ok=False,
                    action_type=action.type,
                    title=action.title,
                    key=action.key,
                    error="empty title",
                )
            )
            continue

        try:
            with db.begin_nested():
                entity_id, created_labels = _apply_one(
                    db, user, action, key_map, settings.default_estimated_duration_minutes
                )
                results.append(
                    OutlineApplyResultItem(
                        ok=True,
                        action_type=action.type,
                        title=title,
                        key=action.key,
                        entity_id=entity_id,
                        created_labels=created_labels,
                    )
                )
        except Exception as exc:  # noqa: BLE001 — isolate per action
            results.append(
                OutlineApplyResultItem(
                    ok=False,
                    action_type=action.type,
                    title=title,
                    key=action.key,
                    error=str(exc),
                )
            )

    if scheduling_settings is not None and any(
        item.ok and item.action_type == "create_task" for item in results
    ):
        increment_scheduling_revision(db, scheduling_settings)
    db.commit()
    return results


def _owned_epic(db: Session, user: User, epic_id: UUID) -> Epic:
    epic = db.get(Epic, epic_id)
    if epic is None or epic.owner_id != user.id:
        raise ValueError("epic not found or not owned")
    return epic


def _owned_project(db: Session, user: User, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise ValueError("project not found or not owned")
    return project


def _owned_section(db: Session, user: User, section_id: UUID) -> Section:
    section = db.get(Section, section_id)
    if section is None or section.owner_id != user.id:
        raise ValueError("section not found or not owned")
    return section


def _apply_one(
    db: Session,
    user: User,
    action: OutlineAction,
    key_map: dict[str, UUID],
    default_estimated: int,
) -> tuple[UUID, list[str]]:
    if isinstance(action, OutlineCreateEpicAction):
        epic = Epic(
            owner_id=user.id,
            title=action.title.strip(),
            description=action.description,
            sort_order=action.sort_order,
        )
        db.add(epic)
        db.flush()
        key_map[action.key] = epic.id
        return epic.id, []

    if isinstance(action, OutlineCreateProjectAction):
        if action.epic_id is not None:
            epic_id = _owned_epic(db, user, action.epic_id).id
        else:
            epic_id = key_map.get(action.epic_key)  # type: ignore[arg-type]
            if epic_id is None:
                raise ValueError(f"epic key not found: {action.epic_key}")
        project = Project(
            owner_id=user.id,
            epic_id=epic_id,
            title=action.title.strip(),
            description=action.description,
            sort_order=action.sort_order,
        )
        db.add(project)
        db.flush()
        key_map[action.key] = project.id
        return project.id, []

    if isinstance(action, OutlineCreateSectionAction):
        if action.project_id is not None:
            project_id = _owned_project(db, user, action.project_id).id
        else:
            project_id = key_map.get(action.project_key)  # type: ignore[arg-type]
            if project_id is None:
                raise ValueError(f"project key not found: {action.project_key}")
        section = Section(
            owner_id=user.id,
            project_id=project_id,
            title=action.title.strip(),
            sort_order=action.sort_order,
        )
        db.add(section)
        db.flush()
        key_map[action.key] = section.id
        return section.id, []

    if isinstance(action, OutlineCreateTaskAction):
        if action.project_id is not None:
            project_id = _owned_project(db, user, action.project_id).id
        else:
            project_id = key_map.get(action.project_key)  # type: ignore[arg-type]
            if project_id is None:
                raise ValueError(f"project key not found: {action.project_key}")

        section_id: UUID | None = None
        if action.section_id is not None:
            section = _owned_section(db, user, action.section_id)
            if section.project_id != project_id:
                raise ValueError("section does not belong to project")
            section_id = section.id
        elif action.section_key:
            section_id = key_map.get(action.section_key)
            if section_id is None:
                raise ValueError(f"section key not found: {action.section_key}")

        label_ids, created_labels = _ensure_labels(db, user, action.label_names)
        estimated = action.estimated_duration_minutes
        if estimated is None:
            estimated = default_estimated

        task = Task(
            owner_id=user.id,
            title=action.title.strip(),
            description=action.description,
            project_id=project_id,
            section_id=section_id,
            priority=TaskPriority.p4,
            sort_order=action.sort_order,
            estimated_duration_minutes=estimated,
        )
        db.add(task)
        db.flush()
        for label_id in label_ids:
            db.add(TaskLabel(task_id=task.id, label_id=label_id))
        db.flush()
        key_map[action.key] = task.id
        return task.id, created_labels

    raise ValueError(f"unsupported action type: {getattr(action, 'type', action)}")
