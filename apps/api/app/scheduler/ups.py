"""UPS scoring per functional spec §9."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.models import Epic, Project, Task, TaskDependency, TaskPriority, UserSettings
DEFAULT_WEIGHTS = {"Wp": 0.35, "Wu": 0.40, "Wd": 0.15, "We": 0.10, "k": 0.5}

PRIORITY_SCORES = {
    TaskPriority.p1: 100.0,
    TaskPriority.p2: 75.0,
    TaskPriority.p3: 50.0,
    TaskPriority.p4: 25.0,
}


def _weights(settings: UserSettings) -> dict[str, float]:
    raw = settings.ups_weights or {}
    return {
        "Wp": float(raw.get("Wp", DEFAULT_WEIGHTS["Wp"])),
        "Wu": float(raw.get("Wu", DEFAULT_WEIGHTS["Wu"])),
        "Wd": float(raw.get("Wd", DEFAULT_WEIGHTS["Wd"])),
        "We": float(raw.get("We", DEFAULT_WEIGHTS["We"])),
        "k": float(raw.get("k", DEFAULT_WEIGHTS["k"])),
    }


def slack_due_at(task: Task) -> datetime | None:
    """First defined of deadline_at, soft_target_at, due_at."""
    return task.deadline_at or task.soft_target_at or task.due_at


def compute_urgency(
    *,
    due_at: datetime | None,
    now_utc: datetime,
    remaining_minutes: int,
    k: float,
) -> float:
    if due_at is None or remaining_minutes <= 0:
        return 0.0
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    minutes_until_due = (due_at - now_utc).total_seconds() / 60.0
    slack = (minutes_until_due - remaining_minutes) / remaining_minutes
    if slack <= 0:
        return 100.0
    return 100.0 * math.exp(-k * slack)


def compute_epic_alignment(
    task: Task,
    project: Project | None,
    epic: Epic | None,
    now_utc: datetime,
) -> float:
    if epic is None or epic.target_date is None:
        return 0.0
    today = now_utc.date()
    delta_days = (epic.target_date - today).days
    if 0 <= delta_days <= 30:
        return 100.0
    return 0.0


def dependent_counts(
    task_ids: set[UUID],
    dependencies: list[TaskDependency],
) -> dict[UUID, int]:
    counts = {task_id: 0 for task_id in task_ids}
    for dep in dependencies:
        if dep.blocking_task_id in counts:
            counts[dep.blocking_task_id] += 1
    return counts


def normalize_dependent_score(count: int, max_count: int) -> float:
    if max_count <= 0:
        return 0.0
    return min(100.0, (count / max_count) * 100.0)


def compute_ups(
    task: Task,
    *,
    settings: UserSettings,
    remaining_minutes: int,
    now_utc: datetime,
    dependent_score: float,
    epic_score: float,
) -> float:
    weights = _weights(settings)
    priority = PRIORITY_SCORES.get(task.priority, 25.0)
    urgency = compute_urgency(
        due_at=slack_due_at(task),
        now_utc=now_utc,
        remaining_minutes=remaining_minutes,
        k=weights["k"],
    )
    return (
        weights["Wp"] * priority
        + weights["Wu"] * urgency
        + weights["Wd"] * dependent_score
        + weights["We"] * epic_score
    )


def score_tasks(
    tasks: list[Task],
    *,
    settings: UserSettings,
    remaining_by_task: dict[UUID, int],
    dependencies: list[TaskDependency],
    projects: dict[UUID, Project],
    epics: dict[UUID, Epic],
    now_utc: datetime,
) -> dict[UUID, float]:
    task_ids = {task.id for task in tasks}
    dep_counts = dependent_counts(task_ids, dependencies)
    max_dep = max(dep_counts.values()) if dep_counts else 0

    scores: dict[UUID, float] = {}
    for task in tasks:
        project = projects.get(task.project_id) if task.project_id else None
        epic = epics.get(project.epic_id) if project and project.epic_id else None
        dep_score = normalize_dependent_score(dep_counts.get(task.id, 0), max_dep)
        epic_score = compute_epic_alignment(task, project, epic, now_utc)
        scores[task.id] = compute_ups(
            task,
            settings=settings,
            remaining_minutes=remaining_by_task[task.id],
            now_utc=now_utc,
            dependent_score=dep_score,
            epic_score=epic_score,
        )
    return scores
