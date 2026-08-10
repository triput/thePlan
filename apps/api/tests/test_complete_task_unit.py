"""Unit tests for complete_task decision logic (no DB)."""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.models.enums import ScheduleStatus
from app.services import task_helpers


class _FakeQuery:
    def __init__(self, rows: list) -> None:
        self._rows = rows
        self._filters: list = []

    def filter(self, *args):
        self._filters.extend(args)
        return self

    def count(self) -> int:
        return len(self._rows)

    def all(self) -> list:
        return self._rows

    def update(self, values, synchronize_session=False):  # noqa: ANN001
        for row in self._rows:
            for key, value in values.items():
                # SQLAlchemy ColumnElement keys — set by attribute name when possible
                name = getattr(key, "key", None) or getattr(key, "name", None)
                if name:
                    setattr(row, name, value)
        return len(self._rows)


class _FakeSession:
    def __init__(self, children_by_parent: dict[uuid.UUID, list]) -> None:
        self.children_by_parent = children_by_parent
        self._update_targets: list = []

    def query(self, *entities):  # noqa: ANN001
        # count_open_children / collect use Task or Task.id
        # We approximate by returning open children for the last parent filter
        # Tests call complete_task which uses count then optionally collect.
        return _OpenChildrenQuery(self)


class _OpenChildrenQuery:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session
        self.parent_id: uuid.UUID | None = None
        self._mode = "count"
        self._ids_only = False

    def filter(self, *args):  # noqa: ANN001
        for arg in args:
            # Capture parent_task_id == X via binary expression left/right if present
            left = getattr(arg, "left", None)
            right = getattr(arg, "right", None)
            key = getattr(left, "key", None) if left is not None else None
            if key == "parent_task_id" and right is not None:
                self.parent_id = getattr(right, "value", right)
        return self

    def count(self) -> int:
        assert self.parent_id is not None
        return len(self.session.children_by_parent.get(self.parent_id, []))

    def all(self) -> list:
        assert self.parent_id is not None
        children = self.session.children_by_parent.get(self.parent_id, [])
        return [(c.id,) for c in children]

    def update(self, values, synchronize_session=False):  # noqa: ANN001
        # bulk update path uses id.in_(descendant_ids) — mark all known open kids
        updated = 0
        for kids in self.session.children_by_parent.values():
            for kid in kids:
                kid.is_completed = True
                kid.completed_at = datetime.utcnow()
                kid.status = ScheduleStatus.completed
                updated += 1
        return updated


def _task(*, nesting_level: int = 0, completed: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        nesting_level=nesting_level,
        is_completed=completed,
        completed_at=None,
        status=ScheduleStatus.unscheduled,
        due_at=None,
        recurrence_rule=None,
    )


def test_complete_task_omitted_bulk_raises_open_children() -> None:
    parent = _task()
    child = _task(nesting_level=1)
    db = _FakeSession({parent.id: [child]})

    with pytest.raises(ApiError) as exc_info:
        task_helpers.complete_task(db, parent, bulk_children=None, force_parent_only=False)

    assert exc_info.value.status_code == 409
    assert exc_info.value.content["code"] == "OPEN_CHILDREN"
    assert parent.is_completed is False


def test_complete_task_explicit_false_parent_only() -> None:
    parent = _task()
    child = _task(nesting_level=1)
    db = _FakeSession({parent.id: [child]})

    task_helpers.complete_task(db, parent, bulk_children=False, force_parent_only=False)
    assert parent.is_completed is True
    assert child.is_completed is False


def test_complete_task_force_parent_only() -> None:
    parent = _task()
    child = _task(nesting_level=1)
    db = _FakeSession({parent.id: [child]})

    task_helpers.complete_task(db, parent, bulk_children=None, force_parent_only=True)
    assert parent.is_completed is True
    assert child.is_completed is False
