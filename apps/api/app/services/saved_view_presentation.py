"""Validate saved-view presentation_json and compile task ORDER BY (F7).

Page note — allowlisted ``presentation_json.sort`` string keys (ascending unless
prefixed with ``-``):

* ``sort_order`` (default when omitted) → ``Task.sort_order``, ``Task.created_at``
* ``created_at`` / ``-created_at``
* ``due_at`` / ``-due_at``
* ``priority`` / ``-priority`` (p1 highest; PostgreSQL enum order)
* ``title`` / ``-title``

``board_order=true`` on view task queries uses ``board_rank`` then ``created_at``;
presentation sort is ignored (see ``routes/views.py``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import InstrumentedAttribute

from app.api.errors import ApiError
from app.models import Task

ALLOWED_SORT_KEYS: frozenset[str] = frozenset(
    {
        "sort_order",
        "created_at",
        "-created_at",
        "due_at",
        "-due_at",
        "priority",
        "-priority",
        "title",
        "-title",
    }
)

ALLOWED_MODES: frozenset[str] = frozenset({"list", "board"})


def validate_sort_key(raw: object, *, field: str = "sort") -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ApiError(422, "Invalid sort key", "INVALID_SORT", field=field)
    key = raw.strip()
    if key not in ALLOWED_SORT_KEYS:
        raise ApiError(422, "Invalid sort key", "INVALID_SORT", field=field)
    return key


def _validate_mode(raw: object) -> str:
    if not isinstance(raw, str) or raw not in ALLOWED_MODES:
        raise ApiError(
            422,
            "mode must be list or board",
            "INVALID_PRESENTATION",
            field="presentation_json.mode",
        )
    return raw


def validate_presentation(presentation: dict[str, Any]) -> dict[str, Any]:
    """Normalize mode/sort on create; preserve unknown keys."""
    if not isinstance(presentation, dict):
        raise ApiError(422, "presentation_json must be an object", "INVALID_PRESENTATION")
    out = dict(presentation)
    if "mode" in out and out["mode"] is not None:
        out["mode"] = _validate_mode(out["mode"])
    if "sort" in out and out["sort"] is not None:
        out["sort"] = validate_sort_key(out["sort"], field="presentation_json.sort")
    return out


def merge_presentation(existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge presentation: partial PATCH of mode/sort keeps other keys."""
    if not isinstance(patch, dict):
        raise ApiError(422, "presentation_json must be an object", "INVALID_PRESENTATION")
    merged = dict(existing or {})
    if "mode" in patch:
        mode = patch["mode"]
        if mode is None:
            merged.pop("mode", None)
        else:
            merged["mode"] = _validate_mode(mode)
    if "sort" in patch:
        sort = patch["sort"]
        if sort is None:
            merged.pop("sort", None)
        else:
            merged["sort"] = validate_sort_key(sort, field="presentation_json.sort")
    for key, value in patch.items():
        if key in ("mode", "sort"):
            continue
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def resolve_task_sort(*, query_sort: str | None, presentation: dict[str, Any] | None) -> str:
    if query_sort is not None:
        return validate_sort_key(query_sort, field="sort")
    pres = presentation or {}
    pres_sort = pres.get("sort")
    if pres_sort is not None:
        return validate_sort_key(pres_sort, field="presentation_json.sort")
    return "sort_order"


def task_order_by(sort_key: str) -> tuple[Any, ...]:
    """Return SQLAlchemy order_by clauses for an allowlisted sort key."""
    validate_sort_key(sort_key, field="sort")
    col: InstrumentedAttribute[Any]
    if sort_key == "sort_order":
        return (Task.sort_order.asc(), Task.created_at.asc())
    if sort_key == "created_at":
        return (Task.created_at.asc(),)
    if sort_key == "-created_at":
        return (Task.created_at.desc(),)
    if sort_key == "due_at":
        return (Task.due_at.asc(), Task.created_at.asc())
    if sort_key == "-due_at":
        return (Task.due_at.desc(), Task.created_at.asc())
    if sort_key == "priority":
        return (Task.priority.asc(), Task.created_at.asc())
    if sort_key == "-priority":
        return (Task.priority.desc(), Task.created_at.asc())
    if sort_key == "title":
        return (Task.title.asc(), Task.created_at.asc())
    if sort_key == "-title":
        return (Task.title.desc(), Task.created_at.asc())
    raise ApiError(422, "Invalid sort key", "INVALID_SORT", field="sort")
