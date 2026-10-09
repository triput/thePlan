"""F1 planning handoff — validate graph, propose defaults, atomic apply with receipts."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Epic, HandoffReceipt, Project, Section, Task, TaskDependency, TaskLabel, User
from app.models.enums import ScheduleStyle, TaskPriority
from app.models.handoff import HANDOFF_APPLY_KIND
from app.schemas.handoffs import (
    HandoffApplyRequest,
    HandoffApplyResult,
    HandoffEntity,
    HandoffGraphPayload,
    HandoffProposeResponse,
    HandoffReceiptEntityRef,
    HandoffResolvedDefault,
    HandoffSchedulePolicy,
    HandoffSourceRef,
)
from app.services.assist_apply import _ensure_labels
from app.services.auth_users import get_or_provision_user_settings
from app.services.task_dependencies import edges_have_cycle, load_dependency_edges
from app.services.task_helpers import resolve_nesting_level


@dataclass(frozen=True)
class _ResolvedParent:
    epic_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None


def canonical_payload_hash(payload: HandoffGraphPayload) -> str:
    data = payload.model_dump(mode="json", exclude_none=False)
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _effective_schedule_policy(
    payload: HandoffGraphPayload,
    entity: HandoffEntity,
) -> HandoffSchedulePolicy:
    if entity.schedule_policy is not None:
        return entity.schedule_policy
    if payload.schedule_policy is not None:
        return payload.schedule_policy
    return "manual"


def _schedule_style_for_policy(
    policy: HandoffSchedulePolicy,
    settings_default: ScheduleStyle,
) -> ScheduleStyle | None:
    if policy == "manual":
        return ScheduleStyle.manual
    if policy == "inherited":
        return None
    if policy == "automatic":
        return settings_default
    raise ApiError(422, f"Unknown schedule_policy: {policy}", "INVALID_SCHEDULE_POLICY")


def _invalid(entity_key: str | None, field: str, message: str) -> None:
    detail = f"{message}" if entity_key is None else f"entity '{entity_key}' {field}: {message}"
    raise ApiError(422, detail, "HANDOFF_VALIDATION", details={"entity_key": entity_key, "field": field})


def _validate_entities(payload: HandoffGraphPayload) -> None:
    keys: set[str] = set()
    for entity in payload.entities:
        if entity.key in keys:
            _invalid(entity.key, "key", "duplicate key")
        keys.add(entity.key)

    key_by_kind = {entity.key: entity for entity in payload.entities}

    for entity in payload.entities:
        if entity.parent is not None:
            if entity.parent.kind == entity.kind and entity.kind in {"epic", "project", "section"}:
                _invalid(entity.key, "parent", "cannot parent to same kind as self")
            continue
        if entity.parent_key is None:
            if entity.kind == "section":
                _invalid(entity.key, "parent_key", "section requires a project parent")
            if entity.kind == "task":
                _invalid(entity.key, "parent_key", "task requires a section or task parent")
            continue
        parent_entity = key_by_kind.get(entity.parent_key)
        if parent_entity is None:
            _invalid(entity.key, "parent_key", f"unknown parent key '{entity.parent_key}'")
        allowed = {
            "project": {"epic"},
            "section": {"project"},
            "task": {"section", "task"},
        }
        expected = allowed.get(entity.kind, set())
        if parent_entity.kind not in expected:
            _invalid(
                entity.key,
                "parent_key",
                f"parent kind '{parent_entity.kind}' invalid for '{entity.kind}'",
            )


def _resolve_existing_parent(
    db: Session,
    user: User,
    entity: HandoffEntity,
) -> _ResolvedParent:
    if entity.parent is None:
        return _ResolvedParent()
    ref = entity.parent
    if ref.kind == "epic":
        epic = db.get(Epic, ref.id)
        if epic is None or epic.owner_id != user.id:
            _invalid(entity.key, "parent.id", "epic not found or not owned")
        return _ResolvedParent(epic_id=epic.id)
    if ref.kind == "project":
        project = db.get(Project, ref.id)
        if project is None or project.owner_id != user.id:
            _invalid(entity.key, "parent.id", "project not found or not owned")
        return _ResolvedParent(project_id=project.id, epic_id=project.epic_id)
    if ref.kind == "section":
        section = db.get(Section, ref.id)
        if section is None or section.owner_id != user.id:
            _invalid(entity.key, "parent.id", "section not found or not owned")
        return _ResolvedParent(
            project_id=section.project_id,
            section_id=section.id,
        )
    if ref.kind == "task":
        task = db.get(Task, ref.id)
        if task is None or task.owner_id != user.id or task.deleted_at is not None:
            _invalid(entity.key, "parent.id", "task not found or not owned")
        return _ResolvedParent(
            project_id=task.project_id,
            section_id=task.section_id,
            parent_task_id=task.id,
        )
    _invalid(entity.key, "parent.kind", "unsupported parent kind")
    return _ResolvedParent()


def _entity_creation_order(entities: list[HandoffEntity]) -> list[HandoffEntity]:
    by_key = {entity.key: entity for entity in entities}
    in_degree = {entity.key: 0 for entity in entities}
    children: dict[str, list[str]] = {entity.key: [] for entity in entities}
    for entity in entities:
        if entity.parent_key and entity.parent_key in by_key:
            in_degree[entity.key] += 1
            children[entity.parent_key].append(entity.key)
    queue = deque(sorted(key for key, deg in in_degree.items() if deg == 0))
    ordered_keys: list[str] = []
    while queue:
        current = queue.popleft()
        ordered_keys.append(current)
        for child_key in sorted(children[current]):
            in_degree[child_key] -= 1
            if in_degree[child_key] == 0:
                queue.append(child_key)
    if len(ordered_keys) != len(entities):
        _invalid(None, "entities", "entity parent graph contains a cycle")
    return [by_key[key] for key in ordered_keys]


def _task_key_map(entities: list[HandoffEntity]) -> dict[str, HandoffEntity]:
    return {entity.key: entity for entity in entities if entity.kind == "task"}


def _validate_dependencies(
    db: Session,
    user: User,
    payload: HandoffGraphPayload,
) -> tuple[list[tuple[uuid.UUID, uuid.UUID]], list[tuple[str, str]]]:
    task_entities = _task_key_map(payload.entities)
    pending_edges: list[tuple[uuid.UUID, uuid.UUID]] = []
    symbolic_edges: list[tuple[str, str]] = []

    for dep in payload.dependencies:
        if dep.blocking_key:
            if dep.blocking_key not in task_entities or dep.dependent_key not in task_entities:
                _invalid(None, "dependencies", "dependency keys must refer to task entities in graph")
            symbolic_edges.append((dep.blocking_key, dep.dependent_key))
            continue
        assert dep.blocking_task_id and dep.dependent_task_id
        for task_id, label in (
            (dep.blocking_task_id, "blocking_task_id"),
            (dep.dependent_task_id, "dependent_task_id"),
        ):
            task = db.get(Task, task_id)
            if task is None or task.owner_id != user.id or task.deleted_at is not None:
                _invalid(None, label, "task not found or not owned")
        pending_edges.append((dep.blocking_task_id, dep.dependent_task_id))

    if symbolic_edges:
        # Validate symbolic cycle before ids exist using Kahn on keys.
        nodes = {key for pair in symbolic_edges for key in pair}
        in_degree = {node: 0 for node in nodes}
        adj: dict[str, list[str]] = {node: [] for node in nodes}
        for blocker, dependent in symbolic_edges:
            adj[blocker].append(dependent)
            in_degree[dependent] += 1
        queue = deque(node for node, deg in in_degree.items() if deg == 0)
        seen = 0
        while queue:
            current = queue.popleft()
            seen += 1
            for nxt in adj[current]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        if seen != len(nodes):
            _invalid(None, "dependencies", "dependency cycle among new tasks")

    return pending_edges, symbolic_edges  # type: ignore[return-value]


def _validate_nesting(db: Session, user: User, payload: HandoffGraphPayload) -> None:
    by_key = {entity.key: entity for entity in payload.entities}
    memo: dict[str, int] = {}

    def depth_for_task_key(key: str, stack: set[str]) -> int:
        if key in memo:
            return memo[key]
        if key in stack:
            _invalid(key, "parent_key", "task parent cycle")
        entity = by_key.get(key)
        if entity is None or entity.kind != "task":
            _invalid(key, "key", "expected task entity")
        stack.add(key)
        if entity.parent is not None and entity.parent.kind == "task":
            parent = db.get(Task, entity.parent.id)
            if parent is None:
                _invalid(key, "parent", "parent task not found")
            nesting = parent.nesting_level + 1
        elif entity.parent_key and by_key.get(entity.parent_key, None) and by_key[entity.parent_key].kind == "task":
            nesting = depth_for_task_key(entity.parent_key, stack) + 1
        else:
            nesting = 0
        stack.remove(key)
        if nesting > 2:
            _invalid(key, "parent_key", "maximum task nesting depth is 2")
        memo[key] = nesting
        return nesting

    for entity in payload.entities:
        if entity.kind != "task":
            continue
        if entity.parent is not None and entity.parent.kind == "task":
            parent = db.get(Task, entity.parent.id)
            if parent is None or parent.owner_id != user.id:
                _invalid(entity.key, "parent", "parent task not found")
            if parent.nesting_level + 1 > 2:
                _invalid(entity.key, "parent", "maximum task nesting depth is 2")
        elif entity.parent_key and by_key.get(entity.parent_key, None) and by_key[entity.parent_key].kind == "task":
            depth_for_task_key(entity.key, set())


def _collect_resolved_defaults(
    payload: HandoffGraphPayload,
    default_duration: int,
    default_priority: TaskPriority,
    *,
    policy_was_omitted: bool,
) -> list[HandoffResolvedDefault]:
    resolved: list[HandoffResolvedDefault] = []
    for entity in payload.entities:
        if entity.kind != "task":
            continue
        if entity.estimated_duration_minutes is None:
            resolved.append(
                HandoffResolvedDefault(
                    entity_key=entity.key,
                    field="estimated_duration_minutes",
                    value=default_duration,
                )
            )
        if entity.priority is None:
            resolved.append(
                HandoffResolvedDefault(
                    entity_key=entity.key,
                    field="priority",
                    value=default_priority.value,
                )
            )
    if policy_was_omitted:
        resolved.append(
            HandoffResolvedDefault(
                entity_key="*",
                field="schedule_policy",
                value="manual",
                source="design_default",
            )
        )
    return resolved


def propose_handoff(
    db: Session,
    user: User,
    payload: HandoffGraphPayload,
) -> HandoffProposeResponse:
    settings = get_or_provision_user_settings(db, user)
    policy_was_omitted = payload.schedule_policy is None
    canonical = payload.model_copy(deep=True)
    if canonical.schedule_policy is None:
        canonical.schedule_policy = "manual"
    _validate_entities(canonical)
    _validate_nesting(db, user, canonical)
    _validate_dependencies(db, user, canonical)
    warnings: list[str] = []
    if not any(entity.kind in {"epic", "project"} for entity in canonical.entities):
        if any(entity.kind == "task" for entity in canonical.entities):
            warnings.append("task-only graft: source_refs stored on receipt only")
    resolved = _collect_resolved_defaults(
        canonical,
        settings.default_estimated_duration_minutes,
        TaskPriority.p4,
        policy_was_omitted=policy_was_omitted,
    )
    return HandoffProposeResponse(payload=canonical, resolved_defaults=resolved, warnings=warnings)


def _source_refs_json(source_refs: list[HandoffSourceRef]) -> list[dict[str, Any]] | None:
    if not source_refs:
        return None
    return [ref.model_dump(mode="json") for ref in source_refs]


def _existing_receipt(
    db: Session,
    user: User,
    idempotency_key: uuid.UUID,
) -> HandoffReceipt | None:
    return (
        db.query(HandoffReceipt)
        .filter(
            HandoffReceipt.owner_id == user.id,
            HandoffReceipt.operation_kind == HANDOFF_APPLY_KIND,
            HandoffReceipt.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )


def _validate_apply_cycles(
    db: Session,
    user: User,
    payload: HandoffGraphPayload,
) -> None:
    temp_ids = {entity.key: uuid.uuid4() for entity in payload.entities}
    new_edges: list[tuple[uuid.UUID, uuid.UUID]] = []
    for dep in payload.dependencies:
        if dep.blocking_key:
            blocker = temp_ids.get(dep.blocking_key)
            dependent = temp_ids.get(dep.dependent_key)
            if blocker is None or dependent is None:
                _invalid(None, "dependencies", "dependency keys must refer to task entities in graph")
            new_edges.append((blocker, dependent))
        else:
            assert dep.blocking_task_id and dep.dependent_task_id
            new_edges.append((dep.blocking_task_id, dep.dependent_task_id))

    involved: set[uuid.UUID] = set()
    for blocker_id, dependent_id in new_edges:
        involved.add(blocker_id)
        involved.add(dependent_id)
    existing_edges = load_dependency_edges(db, user.id, involved)
    if edges_have_cycle(existing_edges + new_edges):
        _invalid(None, "dependencies", "dependency cycle among tasks")


def apply_handoff(db: Session, user: User, body: HandoffApplyRequest) -> HandoffApplyResult:
    payload = HandoffGraphPayload.model_validate(body.model_dump(exclude={"idempotency_key"}))
    if payload.schedule_policy is None:
        payload.schedule_policy = "manual"

    propose = propose_handoff(db, user, payload)
    payload = propose.payload
    payload_hash = canonical_payload_hash(payload)

    existing = _existing_receipt(db, user, body.idempotency_key)
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise ApiError(
                409,
                "Idempotency key already used with a different payload",
                "IDEMPOTENCY_KEY_REUSE",
            )
        stored = HandoffApplyResult.model_validate(existing.receipt_json)
        return stored.model_copy(update={"replayed": True})

    settings = get_or_provision_user_settings(db, user)
    default_style = settings.default_schedule_style
    source_json = _source_refs_json(payload.source_refs)
    ordered = _entity_creation_order(payload.entities)
    key_to_id: dict[str, uuid.UUID] = {}
    entity_refs: list[HandoffReceiptEntityRef] = []
    created_counts: dict[str, int] = {"epic": 0, "project": 0, "section": 0, "task": 0}

    _, symbolic_dep_edges = _validate_dependencies(db, user, payload)
    _validate_apply_cycles(db, user, payload)

    try:
        with db.begin_nested():
            for entity in ordered:
                policy = _effective_schedule_policy(payload, entity)
                style = _schedule_style_for_policy(policy, default_style)

                if entity.kind == "epic":
                    epic = Epic(
                        owner_id=user.id,
                        title=entity.title.strip(),
                        description=entity.description,
                        sort_order=entity.sort_order,
                        schedule_style=style,
                        source_refs=source_json,
                    )
                    db.add(epic)
                    db.flush()
                    key_to_id[entity.key] = epic.id
                    entity_refs.append(
                        HandoffReceiptEntityRef(key=entity.key, kind="epic", id=epic.id)
                    )
                    created_counts["epic"] += 1
                    continue

                if entity.kind == "project":
                    resolved = _resolve_existing_parent(db, user, entity)
                    epic_id = resolved.epic_id
                    if entity.parent_key:
                        epic_id = key_to_id.get(entity.parent_key)
                        if epic_id is None:
                            _invalid(entity.key, "parent_key", "epic key not found")
                    standalone_root = (
                        epic_id is None and entity.parent is None and entity.parent_key is None
                    )
                    project = Project(
                        owner_id=user.id,
                        epic_id=epic_id,
                        title=entity.title.strip(),
                        description=entity.description,
                        sort_order=entity.sort_order,
                        schedule_style=style,
                        source_refs=source_json if standalone_root else None,
                    )
                    db.add(project)
                    db.flush()
                    key_to_id[entity.key] = project.id
                    entity_refs.append(
                        HandoffReceiptEntityRef(key=entity.key, kind="project", id=project.id)
                    )
                    created_counts["project"] += 1
                    continue

                if entity.kind == "section":
                    project_id: uuid.UUID | None = None
                    if entity.parent is not None and entity.parent.kind == "project":
                        project_id = entity.parent.id
                    elif entity.parent_key:
                        project_id = key_to_id.get(entity.parent_key)
                    if project_id is None:
                        _invalid(entity.key, "parent", "project parent required")
                    section = Section(
                        owner_id=user.id,
                        project_id=project_id,
                        title=entity.title.strip(),
                        sort_order=entity.sort_order,
                    )
                    db.add(section)
                    db.flush()
                    key_to_id[entity.key] = section.id
                    entity_refs.append(
                        HandoffReceiptEntityRef(key=entity.key, kind="section", id=section.id)
                    )
                    created_counts["section"] += 1
                    continue

                if entity.kind == "task":
                    resolved = _resolve_existing_parent(db, user, entity)
                    project_id = resolved.project_id
                    section_id = resolved.section_id
                    parent_task_id = resolved.parent_task_id

                    if entity.parent_key:
                        parent_ent = next(
                            (e for e in payload.entities if e.key == entity.parent_key),
                            None,
                        )
                        if parent_ent is None:
                            _invalid(entity.key, "parent_key", "parent not found")
                        if parent_ent.kind == "section":
                            section_id = key_to_id.get(entity.parent_key)
                            if section_id is None:
                                _invalid(entity.key, "parent_key", "section key not resolved")
                            section = db.get(Section, section_id)
                            project_id = section.project_id if section else project_id
                        elif parent_ent.kind == "task":
                            parent_task_id = key_to_id.get(entity.parent_key)
                            if parent_task_id is None:
                                _invalid(entity.key, "parent_key", "task key not resolved")
                            parent_task = db.get(Task, parent_task_id)
                            if parent_task:
                                project_id = parent_task.project_id
                                section_id = parent_task.section_id

                    if project_id is None:
                        _invalid(entity.key, "parent", "project context required for task")

                    nesting = resolve_nesting_level(db, user.id, parent_task_id)
                    estimated = entity.estimated_duration_minutes
                    if estimated is None:
                        estimated = settings.default_estimated_duration_minutes
                    priority = entity.priority or TaskPriority.p4

                    task = Task(
                        owner_id=user.id,
                        title=entity.title.strip(),
                        description=entity.description,
                        project_id=project_id,
                        section_id=section_id,
                        parent_task_id=parent_task_id,
                        nesting_level=nesting,
                        priority=priority,
                        sort_order=entity.sort_order,
                        estimated_duration_minutes=estimated,
                        due_at=entity.due_at,
                        deadline_at=entity.deadline_at,
                        schedule_style=style,
                    )
                    db.add(task)
                    db.flush()
                    label_ids, _ = _ensure_labels(db, user, entity.label_names)
                    for label_id in label_ids:
                        db.add(TaskLabel(task_id=task.id, label_id=label_id))
                    db.flush()
                    key_to_id[entity.key] = task.id
                    entity_refs.append(
                        HandoffReceiptEntityRef(key=entity.key, kind="task", id=task.id)
                    )
                    created_counts["task"] += 1

            dep_count = 0
            for blocker_key, dependent_key in symbolic_dep_edges:
                db.add(
                    TaskDependency(
                        owner_id=user.id,
                        blocking_task_id=key_to_id[blocker_key],
                        dependent_task_id=key_to_id[dependent_key],
                    )
                )
                dep_count += 1

            for dep in payload.dependencies:
                if dep.blocking_task_id:
                    db.add(
                        TaskDependency(
                            owner_id=user.id,
                            blocking_task_id=dep.blocking_task_id,
                            dependent_task_id=dep.dependent_task_id,
                        )
                    )
                    dep_count += 1

            receipt_id = uuid.uuid4()
            result = HandoffApplyResult(
                receipt_id=receipt_id,
                idempotency_key=body.idempotency_key,
                replayed=False,
                source_refs=payload.source_refs,
                entities=entity_refs,
                dependencies_created=dep_count,
                created_counts=created_counts,
                defaulted_fields=propose.resolved_defaults,
                warnings=propose.warnings,
            )

            receipt = HandoffReceipt(
                id=receipt_id,
                owner_id=user.id,
                operation_kind=HANDOFF_APPLY_KIND,
                idempotency_key=body.idempotency_key,
                payload_hash=payload_hash,
                receipt_json=result.model_dump(mode="json"),
            )
            db.add(receipt)
            db.flush()
    except IntegrityError as exc:
        raced = _existing_receipt(db, user, body.idempotency_key)
        if raced is not None:
            if raced.payload_hash == payload_hash:
                stored = HandoffApplyResult.model_validate(raced.receipt_json)
                return stored.model_copy(update={"replayed": True})
            raise ApiError(
                409,
                "Idempotency key already used with a different payload",
                "IDEMPOTENCY_KEY_REUSE",
            ) from exc
        raise

    db.flush()
    return result
