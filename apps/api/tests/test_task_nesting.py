import uuid

from app.api.errors import ApiError
from app.services.task_helpers import resolve_nesting_level


class FakeTask:
    def __init__(self, owner_id: uuid.UUID, nesting_level: int) -> None:
        self.owner_id = owner_id
        self.nesting_level = nesting_level


class FakeSession:
    def __init__(self, tasks: dict[uuid.UUID, FakeTask]) -> None:
        self.tasks = tasks

    def get(self, _model, task_id: uuid.UUID) -> FakeTask | None:
        return self.tasks.get(task_id)


def test_resolve_nesting_level_root() -> None:
    owner_id = uuid.uuid4()
    db = FakeSession({})
    assert resolve_nesting_level(db, owner_id, None) == 0


def test_resolve_nesting_level_child() -> None:
    owner_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    db = FakeSession({parent_id: FakeTask(owner_id, 1)})
    assert resolve_nesting_level(db, owner_id, parent_id) == 2


def test_resolve_nesting_level_rejects_depth_three() -> None:
    owner_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    db = FakeSession({parent_id: FakeTask(owner_id, 2)})
    try:
        resolve_nesting_level(db, owner_id, parent_id)
        raise AssertionError("Expected ApiError")
    except ApiError as exc:
        assert exc.status_code == 400
        assert exc.content["code"] == "NESTING_DEPTH_EXCEEDED"
