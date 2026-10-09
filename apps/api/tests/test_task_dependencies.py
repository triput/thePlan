"""Task dependency graph helpers (cycle detection closure)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

import pytest

from app.api.errors import ApiError
from app.models import Project, Task, TaskDependency, User
from app.services.task_dependencies import assert_no_cycle, load_dependency_edges


def _task(db: Session, user: User, project_id, title: str) -> Task:
    row = Task(owner_id=user.id, title=title, project_id=project_id)
    db.add(row)
    db.flush()
    return row


def test_load_dependency_edges_expands_chain(db_session: Session) -> None:
    me = db_session.query(User).first()
    assert me is not None
    project = Project(owner_id=me.id, title="Dep closure")
    db_session.add(project)
    db_session.flush()
    a = _task(db_session, me, project.id, "A")
    b = _task(db_session, me, project.id, "B")
    c = _task(db_session, me, project.id, "C")
    db_session.add(
        TaskDependency(owner_id=me.id, blocking_task_id=a.id, dependent_task_id=b.id)
    )
    db_session.add(
        TaskDependency(owner_id=me.id, blocking_task_id=b.id, dependent_task_id=c.id)
    )
    db_session.flush()

    edges = load_dependency_edges(db_session, me.id, {c.id, a.id})
    edge_set = set(edges)
    assert (a.id, b.id) in edge_set
    assert (b.id, c.id) in edge_set


def test_three_node_cycle_rejected(db_session: Session) -> None:
    me = db_session.query(User).first()
    assert me is not None
    project = Project(owner_id=me.id, title="Dep cycle")
    db_session.add(project)
    db_session.flush()
    a = _task(db_session, me, project.id, "A")
    b = _task(db_session, me, project.id, "B")
    c = _task(db_session, me, project.id, "C")
    db_session.add(
        TaskDependency(owner_id=me.id, blocking_task_id=a.id, dependent_task_id=b.id)
    )
    db_session.add(
        TaskDependency(owner_id=me.id, blocking_task_id=b.id, dependent_task_id=c.id)
    )
    db_session.flush()

    with pytest.raises(ApiError) as raised:
        assert_no_cycle(db_session, me.id, c.id, a.id)
    assert raised.value.content["code"] == "DEPENDENCY_CYCLE"
