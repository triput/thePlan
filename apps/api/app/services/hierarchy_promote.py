"""DEF-023: promote / demote hierarchy (project↔epic, task→project).

Thin semantics — no schema migrations. All operations are transactional
create + FK rewire (+ delete epic on demote).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Epic, Project, Task
from app.services.task_helpers import collect_descendant_ids, collect_live_descendant_ids


def promote_project_to_epic(db: Session, project: Project, user_id: uuid.UUID) -> tuple[Epic, Project]:
    """Project becomes the sole child of a new epic cloned from its meta.

    - New epic: title / description / color / time map / schedule style from project.
    - Existing project UUID kept; ``epic_id`` pointed at the new epic.
    - Tasks, sections, and history stay on the project (no copy).
    - Prior parent epic (if any) simply loses this project.
    """
    epic = Epic(
        owner_id=user_id,
        title=project.title,
        description=project.description,
        color_hex=project.color_hex,
        preferred_time_window_id=project.preferred_time_window_id,
        schedule_style=project.schedule_style,
        sort_order=0,
    )
    db.add(epic)
    db.flush()
    project.epic_id = epic.id
    db.flush()
    return epic, project


def demote_epic_to_project(
    db: Session,
    epic: Epic,
    user_id: uuid.UUID,
    *,
    target_epic_id: uuid.UUID | None = None,
) -> tuple[Project, list[uuid.UUID]]:
    """Fold epic into a new project; orphan former child projects.

    - New project: title / description / color / time map / schedule style from epic.
    - ``target_epic_id`` places the new project under another epic (or standalone).
    - Child projects of the demoted epic get ``epic_id = NULL`` (standalone orphans).
    - Demoted epic row is deleted (children already rewired).
    - Tasks live on projects, not epics — none move onto the new shell project.
    """
    if target_epic_id is not None:
        if target_epic_id == epic.id:
            raise ApiError(
                400,
                "Cannot demote an epic under itself",
                "DEMOTE_TARGET_IS_SELF",
            )
        target = db.get(Epic, target_epic_id)
        if target is None or target.owner_id != user_id:
            raise ApiError(404, "Epic not found", "EPIC_NOT_FOUND")

    children = (
        db.query(Project)
        .filter(Project.owner_id == user_id, Project.epic_id == epic.id)
        .all()
    )
    orphaned_ids = [child.id for child in children]
    for child in children:
        child.epic_id = None

    project = Project(
        owner_id=user_id,
        title=epic.title,
        description=epic.description,
        color_hex=epic.color_hex,
        epic_id=target_epic_id,
        preferred_time_window_id=epic.preferred_time_window_id,
        schedule_style=epic.schedule_style,
        sort_order=0,
    )
    db.add(project)
    db.flush()

    db.delete(epic)
    db.flush()
    return project, orphaned_ids


def promote_task_to_project(
    db: Session,
    task: Task,
    user_id: uuid.UUID,
    *,
    include_descendants: bool = True,
    epic_id: uuid.UUID | None = None,
) -> tuple[Project, Task]:
    """Create a project from the task and move the task (optionally subtree) into it.

    - New project title/description from the task; color default.
    - Epic: explicit ``epic_id``, else the task's current project's epic, else standalone.
    - Promoted task becomes a root (``parent_task_id`` cleared, nesting 0).
    - Descendants keep relative nesting; ``section_id`` cleared (sections are project-scoped).
    - If ``include_descendants`` is false and live children exist → 400.
    """
    if task.deleted_at is not None:
        raise ApiError(400, "Cannot promote a trashed task", "TASK_TRASHED")

    live_children = collect_live_descendant_ids(db, task.id, user_id)
    if not include_descendants and live_children:
        raise ApiError(
            400,
            "Task has descendants; pass include_descendants=true or move children first",
            "PROMOTE_HAS_DESCENDANTS",
        )

    resolved_epic_id = epic_id
    if resolved_epic_id is None and task.project_id is not None:
        current_project = db.get(Project, task.project_id)
        if current_project is not None and current_project.owner_id == user_id:
            resolved_epic_id = current_project.epic_id
    if resolved_epic_id is not None:
        target = db.get(Epic, resolved_epic_id)
        if target is None or target.owner_id != user_id:
            raise ApiError(404, "Epic not found", "EPIC_NOT_FOUND")

    project = Project(
        owner_id=user_id,
        title=task.title[:255],
        description=task.description,
        epic_id=resolved_epic_id,
        sort_order=0,
    )
    db.add(project)
    db.flush()

    old_level = task.nesting_level
    task.project_id = project.id
    task.section_id = None
    task.parent_task_id = None
    task.nesting_level = 0

    if include_descendants:
        # Include soft-deleted descendants so trash restore stays coherent.
        move_ids = collect_descendant_ids(db, task.id, user_id)
        if move_ids:
            descendants = (
                db.query(Task)
                .filter(Task.owner_id == user_id, Task.id.in_(move_ids))
                .all()
            )
            for desc in descendants:
                desc.project_id = project.id
                desc.section_id = None
                desc.nesting_level = max(0, desc.nesting_level - old_level)

    db.flush()
    return project, task
