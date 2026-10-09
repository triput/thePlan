"""Task dependency validation and cycle detection (owner-scoped)."""

from __future__ import annotations

import uuid
from collections import deque

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Task, TaskDependency


def _task_ids_for_owner(db: Session, owner_id: uuid.UUID, task_ids: set[uuid.UUID]) -> set[uuid.UUID]:
    if not task_ids:
        return set()
    rows = (
        db.query(Task.id)
        .filter(
            Task.owner_id == owner_id,
            Task.id.in_(task_ids),
            Task.deleted_at.is_(None),
        )
        .all()
    )
    return {row[0] for row in rows}


def load_dependency_edges(
    db: Session,
    owner_id: uuid.UUID,
    task_ids: set[uuid.UUID],
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Blocking -> dependent edges among task_ids plus stored deps touching the set."""
    if not task_ids:
        return []
    rows = (
        db.query(TaskDependency.blocking_task_id, TaskDependency.dependent_task_id)
        .filter(
            TaskDependency.owner_id == owner_id,
            TaskDependency.blocking_task_id.in_(task_ids),
            TaskDependency.dependent_task_id.in_(task_ids),
        )
        .all()
    )
    return [(row[0], row[1]) for row in rows]


def would_create_cycle(
    db: Session,
    owner_id: uuid.UUID,
    blocking_task_id: uuid.UUID,
    dependent_task_id: uuid.UUID,
    *,
    extra_edges: list[tuple[uuid.UUID, uuid.UUID]] | None = None,
) -> bool:
    """True if adding blocking->dependent creates a cycle among involved tasks."""
    seed = {blocking_task_id, dependent_task_id}
    edges = load_dependency_edges(db, owner_id, seed)
    if extra_edges:
        edges = edges + extra_edges
    edges.append((blocking_task_id, dependent_task_id))

    nodes: set[uuid.UUID] = set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)

    in_degree = {node: 0 for node in nodes}
    adj: dict[uuid.UUID, list[uuid.UUID]] = {node: [] for node in nodes}
    for blocker, dependent in edges:
        if blocker not in nodes or dependent not in nodes:
            continue
        adj[blocker].append(dependent)
        in_degree[dependent] += 1

    queue: deque[uuid.UUID] = deque(node for node, deg in in_degree.items() if deg == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for nxt in adj[current]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    return visited != len(nodes)


def assert_tasks_owned(
    db: Session,
    owner_id: uuid.UUID,
    blocking_task_id: uuid.UUID,
    dependent_task_id: uuid.UUID,
) -> None:
    found = _task_ids_for_owner(db, owner_id, {blocking_task_id, dependent_task_id})
    if blocking_task_id not in found:
        raise ApiError(404, "Blocking task not found", "TASK_NOT_FOUND")
    if dependent_task_id not in found:
        raise ApiError(404, "Dependent task not found", "TASK_NOT_FOUND")


def edges_have_cycle(edges: list[tuple[uuid.UUID, uuid.UUID]]) -> bool:
    nodes: set[uuid.UUID] = set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)
    if not nodes:
        return False
    in_degree = {node: 0 for node in nodes}
    adj: dict[uuid.UUID, list[uuid.UUID]] = {node: [] for node in nodes}
    for blocker, dependent in edges:
        if blocker not in nodes or dependent not in nodes:
            continue
        adj[blocker].append(dependent)
        in_degree[dependent] += 1
    queue: deque[uuid.UUID] = deque(node for node, deg in in_degree.items() if deg == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for nxt in adj[current]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    return visited != len(nodes)


def assert_no_cycle(
    db: Session,
    owner_id: uuid.UUID,
    blocking_task_id: uuid.UUID,
    dependent_task_id: uuid.UUID,
    *,
    extra_edges: list[tuple[uuid.UUID, uuid.UUID]] | None = None,
) -> None:
    if would_create_cycle(
        db,
        owner_id,
        blocking_task_id,
        dependent_task_id,
        extra_edges=extra_edges,
    ):
        raise ApiError(
            422,
            "Dependency would create a cycle",
            "DEPENDENCY_CYCLE",
        )
