"""Topological ordering of task candidates with UPS tie-break."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models import TaskDependency
from app.scheduler.candidates import TaskCandidate


def _strongly_connected_components(
    node_ids: set[UUID],
    dependents: dict[UUID, list[UUID]],
) -> list[list[UUID]]:
    """Tarjan SCCs. Returns components in discovery order."""
    index = 0
    stack: list[UUID] = []
    on_stack: set[UUID] = set()
    indices: dict[UUID, int] = {}
    lowlinks: dict[UUID, int] = {}
    components: list[list[UUID]] = []

    def strongconnect(node: UUID) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for nxt in dependents.get(node, []):
            if nxt not in node_ids:
                continue
            if nxt not in indices:
                strongconnect(nxt)
                lowlinks[node] = min(lowlinks[node], lowlinks[nxt])
            elif nxt in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[nxt])

        if lowlinks[node] == indices[node]:
            component: list[UUID] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            components.append(component)

    for node in node_ids:
        if node not in indices:
            strongconnect(node)
    return components


def _cycle_groups_from_graph(
    candidate_ids: set[UUID],
    dependents: dict[UUID, list[UUID]],
    in_degree: dict[UUID, int],
) -> list[list[UUID]]:
    """SCCs that are true cycles (size > 1, or a self-loop)."""
    self_loop: set[UUID] = set()
    for blocker, deps in dependents.items():
        for dependent in deps:
            if dependent == blocker:
                self_loop.add(blocker)

    groups: list[list[UUID]] = []
    for component in _strongly_connected_components(candidate_ids, dependents):
        if len(component) > 1 or (len(component) == 1 and component[0] in self_loop):
            groups.append(sorted(component, key=str))
    return groups


def order_candidates(
    candidates: list[TaskCandidate],
    dependencies: list[TaskDependency],
    ups_scores: dict[UUID, float],
) -> tuple[list[TaskCandidate], dict[str, Any]]:
    """Kahn topo with max-UPS ready queue; cycle => input list order.

    ``cycle_task_ids`` / ``cycle_groups`` name only tasks that participate in a
    strongly connected cycle — not merely downstream of one.
    """
    stats: dict[str, Any] = {}
    if not candidates:
        return [], stats

    candidate_ids = {item.task.id for item in candidates}
    candidate_by_id = {item.task.id: item for item in candidates}

    in_degree: dict[UUID, int] = {task_id: 0 for task_id in candidate_ids}
    dependents: dict[UUID, list[UUID]] = {task_id: [] for task_id in candidate_ids}

    for dep in dependencies:
        blocker = dep.blocking_task_id
        dependent = dep.dependent_task_id
        if blocker not in candidate_ids or dependent not in candidate_ids:
            continue
        in_degree[dependent] += 1
        dependents[blocker].append(dependent)

    ready = [task_id for task_id, degree in in_degree.items() if degree == 0]
    ordered_ids: list[UUID] = []

    while ready:
        ready.sort(key=lambda task_id: ups_scores.get(task_id, 0.0), reverse=True)
        current = ready.pop(0)
        ordered_ids.append(current)
        for dependent_id in dependents[current]:
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                ready.append(dependent_id)

    if len(ordered_ids) != len(candidate_ids):
        cycle_groups = _cycle_groups_from_graph(candidate_ids, dependents, in_degree)
        cycle_ids = sorted(
            {task_id for group in cycle_groups for task_id in group},
            key=str,
        )
        stats["dependency_cycle"] = True
        stats["ordered_count"] = len(ordered_ids)
        stats["cycle_task_ids"] = [str(task_id) for task_id in cycle_ids]
        stats["cycle_groups"] = [
            [str(task_id) for task_id in group] for group in cycle_groups
        ]
        return list(candidates), stats

    stats["dependency_cycle"] = False
    stats["cycle_task_ids"] = []
    stats["cycle_groups"] = []
    return [candidate_by_id[task_id] for task_id in ordered_ids], stats
