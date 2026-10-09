"""F5 Coursera templates — propose/apply via outline mapper + F1 handoff apply."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Epic, HandoffReceipt, Project, User
from app.models.handoff import TEMPLATE_APPLY_KIND
from app.schemas.handoffs import (
    HandoffApplyRequest,
    HandoffApplyResult,
    HandoffGraphPayload,
    HandoffSourceRef,
)
from app.schemas.outlines import OutlineAttachUnder, OutlineProposeSummary
from app.schemas.templates import TemplateDetailOut, TemplateListItem, TemplateProposeResponse
from app.services.builtin_templates import (
    get_template,
    is_blank_scaffold,
    list_templates,
    example_outline_for,
)
from app.services.handoff_apply import apply_handoff, propose_handoff
from app.services.outline_to_handoff import outline_actions_to_handoff, standalone_course_to_handoff
from app.services.outline_templates import propose_outline_actions


def _template_not_found(template_id: str) -> None:
    raise ApiError(404, f"Unknown template: {template_id}", "TEMPLATE_NOT_FOUND")


def templates_list() -> list[TemplateListItem]:
    return [
        TemplateListItem(
            id=t.id,
            version=t.version,
            title=t.title,
            description=t.description,
            attach_modes=list(t.attach_modes),
        )
        for t in list_templates()
    ]


def template_detail(template_id: str) -> TemplateDetailOut:
    row = get_template(template_id)
    if row is None:
        _template_not_found(template_id)
    assert row is not None
    example = example_outline_for(template_id)
    return TemplateDetailOut(
        id=row.id,
        version=row.version,
        title=row.title,
        description=row.description,
        attach_modes=list(row.attach_modes),
        outline_pack=row.outline_pack,
        example_outline=example,
        is_scaffold=is_blank_scaffold(example, template_id),
    )


def _source_refs_from_outline(
    outline: dict[str, Any],
    extra: list[HandoffSourceRef],
) -> list[HandoffSourceRef]:
    refs = list(extra)
    cert = outline.get("certificate") or {}
    url = cert.get("source_url") or cert.get("url")
    course = outline.get("course")
    if isinstance(course, dict) and course.get("url"):
        url = url or course.get("url")
    if url:
        refs.append(
            HandoffSourceRef(
                system="coursera",
                id=str(url).rstrip("/").split("/")[-1] or "course",
                url=str(url),
            )
        )
    return refs


def _estimate_notes(outline: dict[str, Any]) -> list[str]:
    """Supplied estimated_hours labels. These are metadata, not task minutes."""
    notes: list[str] = []

    def add(raw: dict[str, Any]) -> None:
        hours = raw.get("estimated_hours")
        if hours is None:
            return
        title = str(raw.get("title") or "item").strip() or "item"
        notes.append(f"{title}={hours}")

    def walk_course(course: dict[str, Any]) -> None:
        add(course)
        modules = course.get("modules") or []
        if isinstance(modules, list):
            for module in modules:
                if isinstance(module, dict):
                    add(module)

    walked_course = False
    courses = outline.get("courses")
    if isinstance(courses, list):
        walked_course = True
        for course in courses:
            if isinstance(course, dict):
                walk_course(course)
    course = outline.get("course")
    if isinstance(course, dict):
        walked_course = True
        walk_course(course)
    if walked_course:
        return notes
    module = outline.get("module")
    if isinstance(module, dict):
        add(module)
    modules = outline.get("modules")
    if isinstance(modules, list):
        for item in modules:
            if isinstance(item, dict):
                add(item)
    return notes


def _estimate_disclosure_warnings(outline: dict[str, Any]) -> list[str]:
    notes = _estimate_notes(outline)
    if not notes:
        return []
    base = (
        "Supplied estimated_hours are outline metadata, not task scheduling durations. "
        "Task minutes come from duration_minutes or the disclosed default."
    )
    if len(notes) <= 8:
        return [f"{base} Noted: {'; '.join(notes)}."]
    return [f"{base} Noted on {len(notes)} outline fields."]


def _duplicate_source_warnings(db: Session, user: User, source_refs: list[HandoffSourceRef]) -> list[str]:
    warnings: list[str] = []
    urls = {ref.url for ref in source_refs if ref.url}
    if not urls:
        return warnings
    for url in urls:
        for epic in db.query(Epic).filter(Epic.owner_id == user.id).limit(500):
            if not epic.source_refs:
                continue
            for ref in epic.source_refs:
                if isinstance(ref, dict) and ref.get("url") == url:
                    warnings.append(
                        "A source URL in this proposal already appears on an existing epic; "
                        "apply creates a new instance — merge is not supported."
                    )
                    return warnings
        for project in db.query(Project).filter(Project.owner_id == user.id).limit(500):
            if not project.source_refs:
                continue
            for ref in project.source_refs:
                if isinstance(ref, dict) and ref.get("url") == url:
                    warnings.append(
                        "A source URL in this proposal already appears on an existing project; "
                        "apply creates a new instance — merge is not supported."
                    )
                    return warnings
    return warnings


def _validate_attach(template_id: str, attach_under: OutlineAttachUnder | None) -> None:
    row = get_template(template_id)
    if row is None:
        _template_not_found(template_id)
    assert row is not None
    if template_id == "coursera_module":
        if attach_under is None:
            raise ApiError(
                422,
                "coursera_module requires attach_under project or section",
                "TEMPLATE_ATTACH_REQUIRED",
            )
        if attach_under.kind not in {"project", "section"}:
            raise ApiError(
                422,
                "coursera_module attach_under must be a project or section",
                "TEMPLATE_ATTACH_INVALID",
            )
        return
    if template_id == "coursera_course" and attach_under is not None and attach_under.kind != "epic":
        raise ApiError(
            422,
            "coursera_course attach_under must be an epic when grafting",
            "TEMPLATE_ATTACH_INVALID",
        )
    if template_id == "coursera_specialization" and attach_under is not None and attach_under.kind != "epic":
        raise ApiError(
            422,
            "coursera_specialization attach_under must be an epic when grafting courses",
            "TEMPLATE_ATTACH_INVALID",
        )


def _build_graph(
    template_id: str,
    outline: dict[str, Any],
    *,
    skip_optional: bool,
    attach_under: OutlineAttachUnder | None,
    source_refs: list[HandoffSourceRef],
    db: Session,
    user: User,
) -> tuple[HandoffGraphPayload, OutlineProposeSummary, list[str]]:
    row = get_template(template_id)
    if row is None:
        _template_not_found(template_id)
    assert row is not None

    warnings: list[str] = []
    if is_blank_scaffold(outline, template_id):
        warnings.append("Outline still looks like the blank scaffold — replace titles before apply.")
    warnings.extend(_estimate_disclosure_warnings(outline))

    merged_sources = _source_refs_from_outline(outline, source_refs)
    warnings.extend(_duplicate_source_warnings(db, user, merged_sources))

    optional_skipped = 0
    try:
        if template_id == "coursera_course" and attach_under is None:
            if "certificate" in outline:
                raise ApiError(
                    400,
                    "Standalone coursera_course expects a course object; "
                    "use coursera_specialization for a certificate",
                    "OUTLINE_INVALID",
                )
            payload, optional_skipped = standalone_course_to_handoff(
                outline,
                source_refs=merged_sources,
                skip_optional=skip_optional,
            )
        else:
            actions, outline_summary = propose_outline_actions(
                outline,
                template_id=row.outline_pack,
                skip_optional=skip_optional,
                attach_under=attach_under,
                db=db,
                user=user,
            )
            optional_skipped = outline_summary.optional_skipped
            payload = outline_actions_to_handoff(
                actions, source_refs=merged_sources, schedule_policy="manual"
            )
    except ValueError as exc:
        raise ApiError(422, str(exc), "TEMPLATE_OUTLINE_INVALID") from exc

    summary = OutlineProposeSummary(
        epic_count=sum(1 for e in payload.entities if e.kind == "epic"),
        project_count=sum(1 for e in payload.entities if e.kind == "project"),
        section_count=sum(1 for e in payload.entities if e.kind == "section"),
        task_count=sum(1 for e in payload.entities if e.kind == "task"),
        optional_skipped=optional_skipped,
    )
    return payload, summary, warnings


def propose_template(
    db: Session,
    user: User,
    template_id: str,
    outline: dict[str, Any],
    *,
    skip_optional: bool = False,
    attach_under: OutlineAttachUnder | None = None,
    source_refs: list[HandoffSourceRef] | None = None,
) -> TemplateProposeResponse:
    _validate_attach(template_id, attach_under)
    payload, summary, extra_warnings = _build_graph(
        template_id,
        outline,
        skip_optional=skip_optional,
        attach_under=attach_under,
        source_refs=source_refs or [],
        db=db,
        user=user,
    )
    handoff = propose_handoff(db, user, payload)
    warnings = list(extra_warnings) + list(handoff.warnings)
    row = get_template(template_id)
    assert row is not None
    return TemplateProposeResponse(
        template_id=row.id,
        template_version=row.version,
        payload=handoff.payload,
        summary=summary,
        resolved_defaults=handoff.resolved_defaults,
        warnings=warnings,
        is_scaffold=is_blank_scaffold(outline, template_id),
    )


def apply_template(
    db: Session,
    user: User,
    template_id: str,
    body: HandoffApplyRequest,
) -> HandoffApplyResult:
    row = get_template(template_id)
    if row is None:
        _template_not_found(template_id)
    assert row is not None
    metadata = {"template_id": row.id, "template_version": row.version}
    return apply_handoff(
        db,
        user,
        body,
        operation_kind=TEMPLATE_APPLY_KIND,
        receipt_metadata=metadata,
    )


def template_receipt_by_key(db: Session, user: User, idempotency_key: UUID) -> HandoffApplyResult:
    receipt = (
        db.query(HandoffReceipt)
        .filter(
            HandoffReceipt.owner_id == user.id,
            HandoffReceipt.operation_kind == TEMPLATE_APPLY_KIND,
            HandoffReceipt.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if receipt is None:
        raise ApiError(404, "Template apply receipt not found", "RECEIPT_NOT_FOUND")
    return HandoffApplyResult.model_validate(receipt.receipt_json)
