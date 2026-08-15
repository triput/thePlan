"""Built-in outline template packs — Theme F / ADR-011.

Service layer — map outline JSON → propose actions (coursera_specialization).
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.api.errors import ApiError
from app.schemas import (
    OutlineAction,
    OutlineCreateEpicAction,
    OutlineCreateProjectAction,
    OutlineCreateSectionAction,
    OutlineCreateTaskAction,
    OutlineProposeSummary,
)

TEMPLATE_COURSERA_SPECIALIZATION = "coursera_specialization"
_KNOWN_TEMPLATES = frozenset({TEMPLATE_COURSERA_SPECIALIZATION})

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
    cleaned = title.strip()
    cleaned = _OPTIONAL_PREFIX.sub("", cleaned).strip()
    candidates = [task_type.replace("_", " "), task_type, *_TYPE_PREFIXES]
    for prefix in candidates:
        pattern = re.compile(rf"^{re.escape(prefix)}\s*:\s*", re.IGNORECASE)
        updated = pattern.sub("", cleaned)
        if updated != cleaned:
            cleaned = updated.strip()
            break
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


def _parse_coursera(outline: dict[str, Any]) -> _CourseraSpecializationOutline:
    try:
        return _CourseraSpecializationOutline.model_validate(outline)
    except ValidationError as exc:
        _invalid(f"Invalid outline shape: {exc.errors()[0].get('msg', 'validation failed')}")
        raise  # pragma: no cover — unreachable; satisfies type checkers


def propose_outline_actions(
    outline: dict[str, Any],
    *,
    template_id: str = TEMPLATE_COURSERA_SPECIALIZATION,
    skip_optional: bool = False,
) -> tuple[list[OutlineAction], OutlineProposeSummary]:
    if template_id not in _KNOWN_TEMPLATES:
        _invalid(f"Unknown template_id: {template_id}")

    if not isinstance(outline, dict):
        _invalid("outline must be an object")

    parsed = _parse_coursera(outline)
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

            for task in module.tasks:
                if skip_optional and task.optional:
                    optional_skipped += 1
                    continue

                outline_id = (task.id or "").strip() or None
                task_key = outline_id or f"task-{course_n}-{module_n}-{task.task_order}"
                duration = _clamp_duration(task.duration_minutes)
                desc = f"outline_id: {outline_id}" if outline_id else None

                actions.append(
                    OutlineCreateTaskAction(
                        key=task_key,
                        title=_clean_task_title(task.title, task.task_type),
                        description=desc,
                        sort_order=task.task_order,
                        project_key=project_key,
                        section_key=section_key,
                        label_names=_task_labels(task),
                        estimated_duration_minutes=duration,
                        optional=bool(task.optional),
                        outline_id=outline_id,
                    )
                )

    summary = OutlineProposeSummary(
        epic_count=sum(1 for a in actions if a.type == "create_epic"),
        project_count=sum(1 for a in actions if a.type == "create_project"),
        section_count=sum(1 for a in actions if a.type == "create_section"),
        task_count=sum(1 for a in actions if a.type == "create_task"),
        optional_skipped=optional_skipped,
    )
    return actions, summary
