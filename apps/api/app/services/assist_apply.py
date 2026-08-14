"""Apply approved Assist actions via existing task/label ownership rules. ADR-010."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Label, Project, Section, Task, TaskLabel, User
from app.models.enums import TaskPriority
from app.schemas import AssistApplyResultItem, AssistCreateTaskAction
from app.services.auth_users import get_or_provision_user_settings


def _normalize_label_name(name: str) -> str:
    return " ".join(name.strip().split())


def _resolve_project_section(
    db: Session,
    user: User,
    project_name: str | None,
    section_name: str | None,
) -> tuple[object | None, object | None, str | None]:
    if not project_name:
        return None, None, None

    project = (
        db.query(Project)
        .filter(Project.owner_id == user.id, func.lower(Project.title) == project_name.lower())
        .first()
    )
    if project is None:
        return None, None, f"project not found: {project_name}"

    if not section_name:
        return project.id, None, None

    section = (
        db.query(Section)
        .filter(
            Section.owner_id == user.id,
            Section.project_id == project.id,
            func.lower(Section.title) == section_name.lower(),
        )
        .first()
    )
    if section is None:
        return project.id, None, f"section not found: {section_name}"
    return project.id, section.id, None


def _ensure_labels(
    db: Session,
    user: User,
    names: list[str],
) -> tuple[list[object], list[str]]:
    label_ids: list[object] = []
    created: list[str] = []
    for raw in names:
        name = _normalize_label_name(raw)
        if not name:
            continue
        existing = (
            db.query(Label)
            .filter(Label.owner_id == user.id, func.lower(Label.name) == name.lower())
            .first()
        )
        if existing is not None:
            label_ids.append(existing.id)
            continue
        label = Label(owner_id=user.id, name=name, color_hex="#635F75")
        db.add(label)
        db.flush()
        label_ids.append(label.id)
        created.append(name)
    return label_ids, created


def apply_assist_actions(
    db: Session,
    user: User,
    actions: list[AssistCreateTaskAction],
) -> list[AssistApplyResultItem]:
    results: list[AssistApplyResultItem] = []
    settings = get_or_provision_user_settings(db, user)

    for action in actions:
        title = action.title.strip()
        if not title:
            results.append(
                AssistApplyResultItem(
                    ok=False,
                    action_type=action.type,
                    title=action.title,
                    error="empty title",
                )
            )
            continue

        try:
            with db.begin_nested():
                project_id, section_id, resolve_err = _resolve_project_section(
                    db, user, action.project_name, action.section_name
                )
                if resolve_err and resolve_err.startswith("project "):
                    project_id, section_id = None, None

                label_ids, created_labels = _ensure_labels(db, user, action.label_names)
                priority = action.priority or TaskPriority.p4
                estimated = action.estimated_duration_minutes
                if estimated is None:
                    estimated = settings.default_estimated_duration_minutes

                task = Task(
                    owner_id=user.id,
                    title=title,
                    description=action.description,
                    project_id=project_id,
                    section_id=section_id,
                    priority=priority,
                    due_at=action.due_at,
                    estimated_duration_minutes=estimated,
                )
                db.add(task)
                db.flush()
                for label_id in label_ids:
                    db.add(TaskLabel(task_id=task.id, label_id=label_id))
                db.flush()

                note = resolve_err if resolve_err and resolve_err.startswith("section ") else None
                results.append(
                    AssistApplyResultItem(
                        ok=True,
                        action_type=action.type,
                        title=title,
                        task_id=task.id,
                        error=note,
                        created_labels=created_labels,
                    )
                )
        except Exception as exc:  # noqa: BLE001 — isolate per action
            results.append(
                AssistApplyResultItem(
                    ok=False,
                    action_type=action.type,
                    title=title,
                    error=str(exc),
                )
            )

    db.commit()
    return results
