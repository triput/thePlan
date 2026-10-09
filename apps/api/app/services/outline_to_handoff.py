"""Map approved outline propose actions → F1 handoff graph (F5 templates)."""

from __future__ import annotations

from typing import Any

from app.api.errors import ApiError
from app.schemas.handoffs import HandoffEntity, HandoffGraphPayload, HandoffParentRef, HandoffSourceRef
from app.schemas.outlines import (
    OutlineAction,
    OutlineCreateEpicAction,
    OutlineCreateProjectAction,
    OutlineCreateSectionAction,
    OutlineCreateTaskAction,
)
from app.services.outline_templates import (
    _clamp_duration,
    _clean_task_title,
    _extract_courses,
    _project_description,
    _task_labels,
)


def outline_actions_to_handoff(
    actions: list[OutlineAction],
    *,
    source_refs: list[HandoffSourceRef],
    schedule_policy: str | None = None,
) -> HandoffGraphPayload:
    entities: list[HandoffEntity] = []
    for action in actions:
        if isinstance(action, OutlineCreateEpicAction):
            entities.append(
                HandoffEntity(
                    key=action.key,
                    kind="epic",
                    title=action.title,
                    description=action.description,
                    sort_order=action.sort_order,
                )
            )
            continue
        if isinstance(action, OutlineCreateProjectAction):
            parent_key = action.epic_key
            parent = None
            if action.epic_id is not None:
                parent = HandoffParentRef(kind="epic", id=action.epic_id)
                parent_key = None
            entities.append(
                HandoffEntity(
                    key=action.key,
                    kind="project",
                    title=action.title,
                    description=action.description,
                    sort_order=action.sort_order,
                    parent_key=parent_key,
                    parent=parent,
                )
            )
            continue
        if isinstance(action, OutlineCreateSectionAction):
            parent_key = action.project_key
            parent = None
            if action.project_id is not None:
                parent = HandoffParentRef(kind="project", id=action.project_id)
                parent_key = None
            entities.append(
                HandoffEntity(
                    key=action.key,
                    kind="section",
                    title=action.title,
                    description=action.description,
                    sort_order=action.sort_order,
                    parent_key=parent_key,
                    parent=parent,
                )
            )
            continue
        if isinstance(action, OutlineCreateTaskAction):
            parent_key: str | None = None
            parent: HandoffParentRef | None = None
            if action.section_id is not None:
                parent = HandoffParentRef(kind="section", id=action.section_id)
            elif action.section_key is not None:
                parent_key = action.section_key
            elif action.project_id is not None:
                parent = HandoffParentRef(kind="project", id=action.project_id)
            else:
                parent_key = action.project_key
            entities.append(
                HandoffEntity(
                    key=action.key,
                    kind="task",
                    title=action.title,
                    description=action.description,
                    sort_order=action.sort_order,
                    parent_key=parent_key,
                    parent=parent,
                    label_names=list(action.label_names),
                    estimated_duration_minutes=action.estimated_duration_minutes,
                )
            )
    if not entities:
        raise ApiError(400, "Outline produced no entities to create", "OUTLINE_INVALID")
    policy = schedule_policy
    if policy not in (None, "manual", "inherited", "automatic"):
        policy = "manual"
    return HandoffGraphPayload(
        source_refs=source_refs,
        schedule_policy=policy or "manual",
        entities=entities,
        dependencies=[],
    )


def standalone_course_to_handoff(
    outline: dict[str, Any],
    *,
    source_refs: list[HandoffSourceRef],
    skip_optional: bool = False,
) -> tuple[HandoffGraphPayload, int]:
    """Single project + sections + tasks without an epic (F5 individual course, standalone)."""
    courses = _extract_courses(outline)
    if len(courses) != 1:
        raise ApiError(
            400,
            "Standalone course requires exactly one course",
            "OUTLINE_INVALID",
        )
    course = courses[0]
    entities: list[HandoffEntity] = []
    project_key = "project"
    entities.append(
        HandoffEntity(
            key=project_key,
            kind="project",
            title=course.title.strip(),
            description=_project_description(course) or None,
            sort_order=course.course_order,
        )
    )
    optional_skipped = 0
    for module in course.modules:
        module_n = module.module_order
        section_key = f"section-{module_n}"
        entities.append(
            HandoffEntity(
                key=section_key,
                kind="section",
                title=module.title.strip(),
                sort_order=module_n,
                parent_key=project_key,
            )
        )
        for task in module.tasks:
            if skip_optional and task.optional:
                optional_skipped += 1
                continue
            outline_id = (task.id or "").strip() or None
            task_key = outline_id or f"{module_n}-task-{task.task_order}"
            duration = _clamp_duration(task.duration_minutes)
            desc = f"outline_id: {outline_id}" if outline_id else None
            entities.append(
                HandoffEntity(
                    key=task_key,
                    kind="task",
                    title=_clean_task_title(task.title, task.task_type),
                    description=desc,
                    sort_order=task.task_order,
                    parent_key=section_key,
                    label_names=_task_labels(task),
                    estimated_duration_minutes=duration,
                )
            )
    payload = HandoffGraphPayload(
        source_refs=source_refs,
        schedule_policy="manual",
        entities=entities,
        dependencies=[],
    )
    return payload, optional_skipped
