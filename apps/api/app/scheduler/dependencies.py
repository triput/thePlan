"""Topological ordering of task candidates with UPS tie-break."""

from __future__ import annotations

from collections import deque
from typing import Any
from uuid import UUID

from app.models import TaskDependency
from app.scheduler.candidates import TaskCandidate


def order_candidates(
    candidates: list[TaskCandidate],
    dependencies: list[TaskDependency],
    ups_scores: dict[UUID, float],
) -> tuple[list[TaskCandidate], dict[str, Any]]:
    """Kahn topo with max-UPS ready queue; cycle => input list order."""
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
        stats["dependency_cycle"] = True
        stats["ordered_count"] = len(ordered_ids)
        return list(candidates), stats

    stats["dependency_cycle"] = False
    return [candidate_by_id[task_id] for task_id in ordered_ids], stats
