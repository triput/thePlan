"""Unit tests for dependency ordering."""

from __future__ import annotations

from uuid import uuid4

from app.models import Task, TaskDependency
from app.scheduler.candidates import TaskCandidate
from app.scheduler.dependencies import order_candidates


def _candidate(title: str) -> TaskCandidate:
    task = Task(id=uuid4(), owner_id=uuid4(), title=title)
    return TaskCandidate(task=task, remaining_minutes=30)


def test_topo_order_respects_blocking_edges() -> None:
    a = _candidate("a")
    b = _candidate("b")
    c = _candidate("c")
    owner_id = uuid4()
    deps = [
        TaskDependency(owner_id=owner_id, blocking_task_id=a.task.id, dependent_task_id=b.task.id),
        TaskDependency(owner_id=owner_id, blocking_task_id=b.task.id, dependent_task_id=c.task.id),
    ]
    ups = {a.task.id: 10.0, b.task.id: 50.0, c.task.id: 30.0}
    ordered, stats = order_candidates([c, b, a], deps, ups)
    assert [item.task.id for item in ordered] == [a.task.id, b.task.id, c.task.id]
    assert stats["dependency_cycle"] is False


def test_topo_prefers_higher_ups_among_ready() -> None:
    a = _candidate("a")
    b = _candidate("b")
    ordered, stats = order_candidates([a, b], [], {a.task.id: 20.0, b.task.id: 80.0})
    assert ordered[0].task.id == b.task.id
    assert stats["dependency_cycle"] is False


def test_cycle_falls_back_to_input_order() -> None:
    a = _candidate("a")
    b = _candidate("b")
    owner_id = uuid4()
    deps = [
        TaskDependency(owner_id=owner_id, blocking_task_id=a.task.id, dependent_task_id=b.task.id),
        TaskDependency(owner_id=owner_id, blocking_task_id=b.task.id, dependent_task_id=a.task.id),
    ]
    input_order = [a, b]
    ordered, stats = order_candidates(input_order, deps, {a.task.id: 1.0, b.task.id: 2.0})
    assert [item.task.id for item in ordered] == [a.task.id, b.task.id]
    assert stats["dependency_cycle"] is True
