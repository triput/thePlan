"""Built-in outline template packs — Theme F / ADR-011.

Service layer — map outline JSON → propose actions (coursera_specialization / hierarchy_v1).
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Epic, Project, Section, User
from app.schemas import (
    OutlineAction,
    OutlineAttachUnder,
    OutlineCreateEpicAction,
    OutlineCreateProjectAction,
    OutlineCreateSectionAction,
    OutlineCreateTaskAction,
    OutlineProposeSummary,
)

TEMPLATE_COURSERA_SPECIALIZATION = "coursera_specialization"
TEMPLATE_HIERARCHY_V1 = "hierarchy_v1"
_KNOWN_TEMPLATES = frozenset({TEMPLATE_COURSERA_SPECIALIZATION, TEMPLATE_HIERARCHY_V1})

_OPTIONAL_PREFIX = re.compile(r"^(?:\(\s*Optional\s*\)|\[\s*Optional\s*\])\s*", re.IGNORECASE)
_TYPE_PREFIXES = (
    "video",
    "reading",
    "assignment",
    "lab",
    "app_item",
    "app item",
    "discussion",
    "podcast",
    "project",
)


class _OutlineTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_type: str
    title: str
    duration_minutes: int | float | None = None
    optional: bool = False
    task_order: int = 0
    id: str | None = None


class _OutlineModule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    module_order: int
    title: str
    estimated_hours: int | float | None = None
    tasks: list[_OutlineTask] = Field(default_factory=list)


class _OutlineCourse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    course_order: int
    title: str
    estimated_hours: int | float | None = None
    url: str | None = None
    modules: list[_OutlineModule] = Field(default_factory=list)


class _OutlineCertificate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    provider: str | None = None
    platform: str | None = None
    source_url: str | None = None
    notes: str | None = None


class _CourseraSpecializationOutline(BaseModel):
    model_config = ConfigDict(extra="ignore")

    certificate: _OutlineCertificate
    courses: list[_OutlineCourse] = Field(default_factory=list)


def _clamp_duration(raw: int | float | None) -> int | None:
    if raw is None:
        return None
    return max(1, min(24 * 60, int(raw)))


def _clean_task_title(title: str, task_type: str) -> str:
    """Normalize whitespace and strip a leading optional marker only.

    Task-type prefixes such as ``Lab:`` / ``Video:`` are preserved so the
    supplied syllabus title matches what Apply creates (DEF-029). Classification
    remains on the task-type label, not the title.
    """
    del task_type  # retained for call-site compatibility; not used for stripping
    cleaned = title.strip()
    cleaned = _OPTIONAL_PREFIX.sub("", cleaned).strip()
    return cleaned or title.strip()


def _epic_description(cert: _OutlineCertificate) -> str:
    lines: list[str] = []
    if cert.provider:
        lines.append(f"provider: {cert.provider}")
    if cert.platform:
        lines.append(f"platform: {cert.platform}")
    if cert.source_url:
        lines.append(f"source_url: {cert.source_url}")
    if cert.notes:
        lines.append(f"notes: {cert.notes}")
    return "\n".join(lines) if lines else ""


def _project_description(course: _OutlineCourse) -> str:
    lines: list[str] = []
    if course.url:
        lines.append(f"url: {course.url}")
    if course.estimated_hours is not None:
        lines.append(f"estimated_hours: {course.estimated_hours}")
    for module in course.modules:
        if module.estimated_hours is None:
            continue
        title = module.title.strip() or "module"
        lines.append(f"module_estimated_hours: {title}={module.estimated_hours}")
    return "\n".join(lines) if lines else ""


def _task_labels(task: _OutlineTask) -> list[str]:
    labels: list[str] = []
    task_type = (task.task_type or "").strip().lower()
    if task_type:
        labels.append(task_type)
    if task.optional and "optional" not in labels:
        labels.append("optional")
    return labels


def _invalid(detail: str) -> None:
    raise ApiError(400, detail, "OUTLINE_INVALID")


def _attach_not_found(detail: str) -> None:
    raise ApiError(404, detail, "OUTLINE_ATTACH_NOT_FOUND")


def _parse_coursera(outline: dict[str, Any]) -> _CourseraSpecializationOutline:
    try:
        return _CourseraSpecializationOutline.model_validate(outline)
    except ValidationError as exc:
        _invalid(f"Invalid outline shape: {exc.errors()[0].get('msg', 'validation failed')}")
        raise  # pragma: no cover — unreachable; satisfies type checkers


def _parse_course(raw: dict[str, Any]) -> _OutlineCourse:
    try:
        return _OutlineCourse.model_validate(raw)
    except ValidationError as exc:
        _invalid(f"Invalid course shape: {exc.errors()[0].get('msg', 'validation failed')}")
        raise  # pragma: no cover


def _parse_module(raw: dict[str, Any]) -> _OutlineModule:
    try:
        return _OutlineModule.model_validate(raw)
    except ValidationError as exc:
        _invalid(f"Invalid module shape: {exc.errors()[0].get('msg', 'validation failed')}")
        raise  # pragma: no cover


def _parse_task_list(raw: list[Any]) -> list[_OutlineTask]:
    tasks: list[_OutlineTask] = []
    for item in raw:
        try:
            tasks.append(_OutlineTask.model_validate(item))
        except ValidationError as exc:
            _invalid(f"Invalid task shape: {exc.errors()[0].get('msg', 'validation failed')}")
            raise  # pragma: no cover
    return tasks


def _extract_courses(outline: dict[str, Any]) -> list[_OutlineCourse]:
    if "certificate" in outline:
        return _parse_coursera(outline).courses
    if "course" in outline and isinstance(outline["course"], dict):
        return [_parse_course(outline["course"])]
    if "courses" in outline:
        raw = outline["courses"]
        if not isinstance(raw, list):
            _invalid("courses must be an array")
        if not raw:
            _invalid("courses array is empty")
        return [_parse_course(item) for item in raw if isinstance(item, dict)]
    _invalid("Expected certificate+courses, course, or courses[] for this attach target")


def _extract_modules(outline: dict[str, Any]) -> list[_OutlineModule]:
    if "module" in outline and isinstance(outline["module"], dict):
        return [_parse_module(outline["module"])]
    if "modules" in outline:
        raw = outline["modules"]
        if not isinstance(raw, list):
            _invalid("modules must be an array")
        if not raw:
            _invalid("modules array is empty")
        return [_parse_module(item) for item in raw if isinstance(item, dict)]
    if "course" in outline and isinstance(outline["course"], dict):
        course = _parse_course(outline["course"])
        if not course.modules:
            _invalid("course has no modules")
        return course.modules
    courses = _extract_courses(outline)
    if len(courses) != 1:
        _invalid("Attach under project requires one course or a modules[] fragment")
    if not courses[0].modules:
        _invalid("course has no modules")
    return courses[0].modules


def _extract_tasks(outline: dict[str, Any]) -> list[_OutlineTask]:
    if "tasks" in outline:
        raw = outline["tasks"]
        if not isinstance(raw, list):
            _invalid("tasks must be an array")
        if not raw:
            _invalid("tasks array is empty")
        return _parse_task_list(raw)
    if "module" in outline and isinstance(outline["module"], dict):
        module = _parse_module(outline["module"])
        if not module.tasks:
            _invalid("module has no tasks")
        return module.tasks
    modules = _extract_modules(outline)
    if len(modules) != 1:
        _invalid("Attach under section requires one module or a tasks[] fragment")
    if not modules[0].tasks:
        _invalid("module has no tasks")
    return modules[0].tasks


def _resolve_attach_target(
    db: Session,
    user: User,
    attach: OutlineAttachUnder,
) -> tuple[UUID | None, UUID | None, UUID | None]:
    if attach.kind == "epic":
        epic = db.get(Epic, attach.id)
        if epic is None or epic.owner_id != user.id:
            _attach_not_found("Epic not found")
        return epic.id, None, None

    if attach.kind == "project":
        project = db.get(Project, attach.id)
        if project is None or project.owner_id != user.id:
            _attach_not_found("Project not found")
        return project.epic_id, project.id, None

    section = db.get(Section, attach.id)
    if section is None or section.owner_id != user.id:
        _attach_not_found("Section not found")
    return None, section.project_id, section.id


def _append_task_actions(
    actions: list[OutlineAction],
    *,
    tasks: list[_OutlineTask],
    skip_optional: bool,
    project_key: str | None,
    project_id: UUID | None,
    section_key: str | None,
    section_id: UUID | None,
    key_prefix: str,
    optional_skipped: int,
) -> int:
    for task in tasks:
        if skip_optional and task.optional:
            optional_skipped += 1
            continue

        outline_id = (task.id or "").strip() or None
        task_key = outline_id or f"{key_prefix}-task-{task.task_order}"
        duration = _clamp_duration(task.duration_minutes)
        desc = f"outline_id: {outline_id}" if outline_id else None

        actions.append(
            OutlineCreateTaskAction(
                key=task_key,
                title=_clean_task_title(task.title, task.task_type),
                description=desc,
                sort_order=task.task_order,
                project_key=project_key,
                project_id=project_id,
                section_key=section_key,
                section_id=section_id,
                label_names=_task_labels(task),
                estimated_duration_minutes=duration,
                optional=bool(task.optional),
                outline_id=outline_id,
            )
        )
    return optional_skipped


def _propose_full_tree(
    parsed: _CourseraSpecializationOutline,
    *,
    skip_optional: bool,
) -> tuple[list[OutlineAction], int]:
    actions: list[OutlineAction] = []
    optional_skipped = 0
    epic_key = "epic"
    actions.append(
        OutlineCreateEpicAction(
            key=epic_key,
            title=parsed.certificate.title.strip(),
            description=_epic_description(parsed.certificate) or None,
            sort_order=0,
        )
    )

    for course in parsed.courses:
        course_n = course.course_order
        project_key = f"course-{course_n}"
        actions.append(
            OutlineCreateProjectAction(
                key=project_key,
                title=course.title.strip(),
                description=_project_description(course) or None,
                sort_order=course_n,
                epic_key=epic_key,
            )
        )

        for module in course.modules:
            module_n = module.module_order
            section_key = f"section-{course_n}-{module_n}"
            actions.append(
                OutlineCreateSectionAction(
                    key=section_key,
                    title=module.title.strip(),
                    sort_order=module_n,
                    project_key=project_key,
                )
            )

            optional_skipped = _append_task_actions(
                actions,
                tasks=module.tasks,
                skip_optional=skip_optional,
                project_key=project_key,
                project_id=None,
                section_key=section_key,
                section_id=None,
                key_prefix=f"{course_n}-{module_n}",
                optional_skipped=optional_skipped,
            )

    return actions, optional_skipped


def _propose_under_epic(
    outline: dict[str, Any],
    epic_id: UUID,
    *,
    skip_optional: bool,
) -> tuple[list[OutlineAction], int]:
    actions: list[OutlineAction] = []
    optional_skipped = 0
    courses = _extract_courses(outline)

    for course in courses:
        course_n = course.course_order
        project_key = f"course-{course_n}"
        actions.append(
            OutlineCreateProjectAction(
                key=project_key,
                title=course.title.strip(),
                description=_project_description(course) or None,
                sort_order=course_n,
                epic_id=epic_id,
            )
        )

        for module in course.modules:
            module_n = module.module_order
            section_key = f"section-{course_n}-{module_n}"
            actions.append(
                OutlineCreateSectionAction(
                    key=section_key,
                    title=module.title.strip(),
                    sort_order=module_n,
                    project_key=project_key,
                )
            )

            optional_skipped = _append_task_actions(
                actions,
                tasks=module.tasks,
                skip_optional=skip_optional,
                project_key=project_key,
                project_id=None,
                section_key=section_key,
                section_id=None,
                key_prefix=f"{course_n}-{module_n}",
                optional_skipped=optional_skipped,
            )

    return actions, optional_skipped


def _propose_under_project(
    outline: dict[str, Any],
    project_id: UUID,
    *,
    skip_optional: bool,
) -> tuple[list[OutlineAction], int]:
    actions: list[OutlineAction] = []
    optional_skipped = 0
    modules = _extract_modules(outline)

    for module in modules:
        module_n = module.module_order
        section_key = f"section-{module_n}"
        actions.append(
            OutlineCreateSectionAction(
                key=section_key,
                title=module.title.strip(),
                sort_order=module_n,
                project_id=project_id,
            )
        )

        optional_skipped = _append_task_actions(
            actions,
            tasks=module.tasks,
            skip_optional=skip_optional,
            project_key=None,
            project_id=project_id,
            section_key=section_key,
            section_id=None,
            key_prefix=str(module_n),
            optional_skipped=optional_skipped,
        )

    return actions, optional_skipped


def _propose_under_section(
    outline: dict[str, Any],
    project_id: UUID,
    section_id: UUID,
    *,
    skip_optional: bool,
) -> tuple[list[OutlineAction], int]:
    actions: list[OutlineAction] = []
    optional_skipped = 0
    tasks = _extract_tasks(outline)

    optional_skipped = _append_task_actions(
        actions,
        tasks=tasks,
        skip_optional=skip_optional,
        project_key=None,
        project_id=project_id,
        section_key=None,
        section_id=section_id,
        key_prefix="section",
        optional_skipped=optional_skipped,
    )

    return actions, optional_skipped


def propose_outline_actions(
    outline: dict[str, Any],
    *,
    template_id: str = TEMPLATE_COURSERA_SPECIALIZATION,
    skip_optional: bool = False,
    attach_under: OutlineAttachUnder | None = None,
    db: Session | None = None,
    user: User | None = None,
) -> tuple[list[OutlineAction], OutlineProposeSummary]:
    if template_id not in _KNOWN_TEMPLATES:
        _invalid(f"Unknown template_id: {template_id}")

    if not isinstance(outline, dict):
        _invalid("outline must be an object")

    if attach_under is not None:
        if db is None or user is None:
            _invalid("attach_under requires authenticated propose context")
        _, project_id, section_id = _resolve_attach_target(db, user, attach_under)

        if attach_under.kind == "epic":
            actions, optional_skipped = _propose_under_epic(
                outline, attach_under.id, skip_optional=skip_optional
            )
        elif attach_under.kind == "project":
            assert project_id is not None
            actions, optional_skipped = _propose_under_project(
                outline, project_id, skip_optional=skip_optional
            )
        else:
            assert project_id is not None and section_id is not None
            actions, optional_skipped = _propose_under_section(
                outline, project_id, section_id, skip_optional=skip_optional
            )
    else:
        if "certificate" not in outline:
            _invalid("Full import requires certificate; use attach_under for course/module fragments")
        parsed = _parse_coursera(outline)
        actions, optional_skipped = _propose_full_tree(parsed, skip_optional=skip_optional)

    summary = OutlineProposeSummary(
        epic_count=sum(1 for a in actions if a.type == "create_epic"),
        project_count=sum(1 for a in actions if a.type == "create_project"),
        section_count=sum(1 for a in actions if a.type == "create_section"),
        task_count=sum(1 for a in actions if a.type == "create_task"),
        optional_skipped=optional_skipped,
    )
    return actions, summary
