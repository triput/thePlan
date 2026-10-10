"""Validate and normalize saved-view predicate JSON (F7 v1).

Runtime accepts the versioned dimension bag only. Legacy ``op`` / ``clauses``
documents are rejected here; a migration normalizer may rewrite them once,
but query and CRUD paths must not.

Jules: persist the dict returned by :func:`validate_predicate`. Call
:func:`check_missing_refs` (or :func:`apply_predicate_to_query`, which does)
at read time. Missing project, epic, and label ids stay in the predicate and
are returned as structured refs — this module never deletes them to widen
the match set.

Complexity (422 ``PREDICATE_TOO_COMPLEX``):

* ``MAX_DIMENSIONS`` — keys present on ``dimensions`` (omitted axes do not count).
* ``MAX_OR_FANOUT`` — raw array length for each OR list (ids or enum values).
* ``MAX_NESTING_DEPTH`` — one dimension bag. ``labels`` and ``due`` are the only
  structured values, and their fields are scalars. Clause trees are rejected.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import Epic, Label, Project

PREDICATE_VERSION = 1
MAX_DIMENSIONS = 8
MAX_OR_FANOUT = 32
MAX_NESTING_DEPTH = 1
MAX_WITHIN_DAYS = 366

_ALLOWED_TOP_LEVEL = frozenset({"v", "dimensions"})
_LEGACY_KEYS = frozenset({"op", "clauses"})
_ALLOWED_DIMENSION_KEYS = frozenset(
    {
        "inbox",
        "project_ids",
        "epic_ids",
        "labels",
        "priorities",
        "workflow_states",
        "completion",
        "schedule_statuses",
        "schedule_styles",
        "due",
    }
)
_DIMENSION_ORDER = (
    "inbox",
    "project_ids",
    "epic_ids",
    "labels",
    "priorities",
    "workflow_states",
    "completion",
    "schedule_statuses",
    "schedule_styles",
    "due",
)

_ALLOWED_PRIORITIES = frozenset({"p1", "p2", "p3", "p4"})
_ALLOWED_WORKFLOW = frozenset({"ready", "in_progress", "waiting"})
_ALLOWED_COMPLETION = frozenset({"open", "done", "any"})
_ALLOWED_SCHEDULE_STATUS = frozenset(
    {"unscheduled", "scheduled", "pinned", "completed", "cancelled", "overbooked"}
)
_ALLOWED_SCHEDULE_STYLE = frozenset({"standalone", "time_block", "manual", "bundle"})
_ALLOWED_LABEL_MATCH = frozenset({"any", "all"})
_ALLOWED_DUE_KIND = frozenset({"none", "unbounded", "fixed", "rolling"})
_ALLOWED_ROLLING = frozenset({"today", "next_7_days", "this_calendar_week", "within_days"})
_ROLLING_WITH_DAYS = frozenset({"within_days"})


def validate_predicate(raw: Any) -> dict[str, Any]:
    """Return a canonical v1 predicate or raise ``ApiError`` 422.

    The result is JSON-ready: UUID strings are canonical lowercase, fixed
    instants are UTC ``Z``, ``within_days`` always includes ``days``, and
    duplicate OR values are collapsed in input order. Empty arrays are
    rejected so a present dimension cannot disappear and match everything.
    """
    if not isinstance(raw, dict):
        raise ApiError(422, "predicate must be an object", "INVALID_PREDICATE", field="predicate")
    _reject_legacy(raw)
    unknown_top = set(raw.keys()) - _ALLOWED_TOP_LEVEL
    if unknown_top:
        names = ", ".join(sorted(str(key) for key in unknown_top))
        raise ApiError(
            422,
            f"unknown predicate fields: {names}",
            "INVALID_PREDICATE",
            field="predicate",
        )

    version = raw.get("v")
    if isinstance(version, bool) or version != PREDICATE_VERSION:
        raise ApiError(
            422,
            f"predicate v must be {PREDICATE_VERSION}",
            "INVALID_PREDICATE",
            field="v",
        )

    dimensions = raw.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ApiError(
            422,
            "predicate.dimensions must be an object",
            "INVALID_PREDICATE",
            field="dimensions",
        )
    if any(not isinstance(key, str) for key in dimensions):
        raise ApiError(
            422,
            "predicate.dimensions keys must be strings",
            "INVALID_PREDICATE",
            field="dimensions",
        )
    if len(dimensions) > MAX_DIMENSIONS:
        raise ApiError(
            422,
            f"predicate has {len(dimensions)} dimensions; max is {MAX_DIMENSIONS}",
            "PREDICATE_TOO_COMPLEX",
            field="dimensions",
        )

    unknown = set(dimensions.keys()) - _ALLOWED_DIMENSION_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ApiError(
            422,
            f"unknown predicate dimensions: {names}",
            "INVALID_PREDICATE",
            field="dimensions",
        )

    normalized: dict[str, Any] = {}
    if "inbox" in dimensions:
        inbox = dimensions["inbox"]
        if inbox is not True:
            raise ApiError(
                422,
                "dimensions.inbox must be true when present",
                "INVALID_PREDICATE",
                field="dimensions.inbox",
            )
        normalized["inbox"] = True

    if "project_ids" in dimensions:
        normalized["project_ids"] = _parse_uuid_list(
            dimensions["project_ids"], field="dimensions.project_ids"
        )
    if "epic_ids" in dimensions:
        normalized["epic_ids"] = _parse_uuid_list(
            dimensions["epic_ids"], field="dimensions.epic_ids"
        )

    if normalized.get("inbox") and normalized.get("project_ids"):
        raise ApiError(
            422,
            "inbox and project_ids cannot both be set",
            "INVALID_PREDICATE",
            field="dimensions",
        )

    if "labels" in dimensions:
        normalized["labels"] = _normalize_labels(dimensions["labels"])
    if "priorities" in dimensions:
        normalized["priorities"] = _parse_enum_list(
            dimensions["priorities"],
            allowed=_ALLOWED_PRIORITIES,
            field="dimensions.priorities",
        )
    if "workflow_states" in dimensions:
        normalized["workflow_states"] = _parse_enum_list(
            dimensions["workflow_states"],
            allowed=_ALLOWED_WORKFLOW,
            field="dimensions.workflow_states",
        )
    if "completion" in dimensions:
        completion = dimensions["completion"]
        if completion not in _ALLOWED_COMPLETION:
            raise ApiError(
                422,
                "dimensions.completion must be open, done, or any",
                "INVALID_PREDICATE",
                field="dimensions.completion",
            )
        normalized["completion"] = completion
    if "schedule_statuses" in dimensions:
        normalized["schedule_statuses"] = _parse_enum_list(
            dimensions["schedule_statuses"],
            allowed=_ALLOWED_SCHEDULE_STATUS,
            field="dimensions.schedule_statuses",
        )
    if "schedule_styles" in dimensions:
        normalized["schedule_styles"] = _parse_enum_list(
            dimensions["schedule_styles"],
            allowed=_ALLOWED_SCHEDULE_STYLE,
            field="dimensions.schedule_styles",
        )
    if "due" in dimensions:
        normalized["due"] = _normalize_due(dimensions["due"])

    ordered = {key: normalized[key] for key in _DIMENSION_ORDER if key in normalized}
    return {"v": PREDICATE_VERSION, "dimensions": ordered}


def check_missing_refs(
    db: Session,
    owner_id: uuid.UUID,
    predicate: dict[str, Any],
) -> list[dict[str, str]]:
    """Return project, epic, and label ids the owner does not have.

    Each item is ``{"kind", "id", "dimension"}``. Foreign-owner rows count as
    missing (the id is the one the caller already sent; no other metadata).
    Archived rows still exist and are not listed. Ids are not removed from
    ``predicate``.
    """
    dims = predicate.get("dimensions") or {}
    if not isinstance(dims, dict):
        return []
    missing: list[dict[str, str]] = []
    missing.extend(
        _missing_ids(
            db,
            owner_id,
            model=Project,
            raw_ids=dims.get("project_ids") or [],
            kind="project",
            dimension="project_ids",
        )
    )
    missing.extend(
        _missing_ids(
            db,
            owner_id,
            model=Epic,
            raw_ids=dims.get("epic_ids") or [],
            kind="epic",
            dimension="epic_ids",
        )
    )
    labels = dims.get("labels") or {}
    label_ids = labels.get("ids") if isinstance(labels, dict) else []
    missing.extend(
        _missing_ids(
            db,
            owner_id,
            model=Label,
            raw_ids=label_ids or [],
            kind="label",
            dimension="labels",
        )
    )
    return missing


def _reject_legacy(raw: dict[str, Any]) -> None:
    present = _LEGACY_KEYS.intersection(raw.keys())
    if not present:
        return
    names = ", ".join(sorted(present))
    raise ApiError(
        422,
        f"legacy predicate fields ({names}) are not accepted; use v1 dimensions",
        "INVALID_PREDICATE",
        field="predicate",
    )


def _normalize_labels(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ApiError(
            422,
            "dimensions.labels must be an object",
            "INVALID_PREDICATE",
            field="dimensions.labels",
        )
    _reject_nested_keys(raw, allowed={"ids", "match"}, field="dimensions.labels")
    if "match" not in raw:
        raise ApiError(
            422,
            "dimensions.labels.match must be any or all",
            "INVALID_PREDICATE",
            field="dimensions.labels.match",
        )
    match = raw["match"]
    if match not in _ALLOWED_LABEL_MATCH:
        raise ApiError(
            422,
            "dimensions.labels.match must be any or all",
            "INVALID_PREDICATE",
            field="dimensions.labels.match",
        )
    ids = _parse_uuid_list(raw.get("ids"), field="dimensions.labels.ids")
    return {"ids": ids, "match": match}


def _normalize_due(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ApiError(
            422,
            "dimensions.due must be an object",
            "INVALID_PREDICATE",
            field="dimensions.due",
        )
    kind = raw.get("kind")
    if kind not in _ALLOWED_DUE_KIND:
        raise ApiError(
            422,
            "dimensions.due.kind must be none, unbounded, fixed, or rolling",
            "INVALID_PREDICATE",
            field="dimensions.due.kind",
        )
    if kind == "none":
        _reject_nested_keys(raw, allowed={"kind"}, field="dimensions.due")
        return {"kind": "none"}
    if kind == "unbounded":
        _reject_nested_keys(raw, allowed={"kind"}, field="dimensions.due")
        return {"kind": "unbounded"}
    if kind == "fixed":
        _reject_nested_keys(raw, allowed={"kind", "from", "to"}, field="dimensions.due")
        start = _parse_aware_utc(raw.get("from"), field="dimensions.due.from")
        end = _parse_aware_utc(raw.get("to"), field="dimensions.due.to")
        if start >= end:
            raise ApiError(
                422,
                "dimensions.due fixed range must be half-open with from < to",
                "INVALID_PREDICATE",
                field="dimensions.due",
            )
        return {"kind": "fixed", "from": _utc_z(start), "to": _utc_z(end)}

    _reject_nested_keys(raw, allowed={"kind", "rolling", "days"}, field="dimensions.due")
    rolling = raw.get("rolling")
    if rolling not in _ALLOWED_ROLLING:
        raise ApiError(
            422,
            "dimensions.due.rolling must be today, next_7_days, this_calendar_week, or within_days",
            "INVALID_PREDICATE",
            field="dimensions.due.rolling",
        )
    due: dict[str, Any] = {"kind": "rolling", "rolling": rolling}
    if rolling in _ROLLING_WITH_DAYS:
        days = raw.get("days", 7)
        _validate_within_days(days)
        due["days"] = days
    elif "days" in raw:
        raise ApiError(
            422,
            "dimensions.due.days is only valid for rolling within_days",
            "INVALID_PREDICATE",
            field="dimensions.due.days",
        )
    return due


def _validate_within_days(days: object) -> None:
    if isinstance(days, bool) or not isinstance(days, int) or days < 1 or days > MAX_WITHIN_DAYS:
        raise ApiError(
            422,
            f"dimensions.due.days must be an integer from 1 to {MAX_WITHIN_DAYS}",
            "INVALID_PREDICATE",
            field="dimensions.due.days",
        )


def _reject_nested_keys(raw: dict[str, Any], *, allowed: set[str], field: str) -> None:
    unknown = set(raw.keys()) - allowed
    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise ApiError(
            422,
            f"unknown fields on {field}: {names}",
            "INVALID_PREDICATE",
            field=field,
        )
    for key, value in raw.items():
        if isinstance(value, (dict, list)) and key != "ids":
            raise ApiError(
                422,
                f"{field}.{key} exceeds nesting depth {MAX_NESTING_DEPTH}",
                "PREDICATE_TOO_COMPLEX",
                field=f"{field}.{key}",
            )


def _parse_uuid_list(raw: object, *, field: str) -> list[str]:
    if not isinstance(raw, list):
        raise ApiError(422, f"{field} must be an array", "INVALID_PREDICATE", field=field)
    if len(raw) > MAX_OR_FANOUT:
        raise ApiError(
            422,
            f"{field} has {len(raw)} values; max is {MAX_OR_FANOUT}",
            "PREDICATE_TOO_COMPLEX",
            field=field,
        )
    if len(raw) == 0:
        raise ApiError(
            422,
            f"{field} must list at least one id",
            "INVALID_PREDICATE",
            field=field,
        )
    parsed: list[str] = []
    seen: set[uuid.UUID] = set()
    for item in raw:
        if isinstance(item, (dict, list)):
            raise ApiError(
                422,
                f"{field} exceeds nesting depth {MAX_NESTING_DEPTH}",
                "PREDICATE_TOO_COMPLEX",
                field=field,
            )
        try:
            value = item if isinstance(item, uuid.UUID) else uuid.UUID(str(item))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ApiError(
                422, f"{field} contains an invalid uuid", "INVALID_PREDICATE", field=field
            ) from exc
        if value in seen:
            continue
        seen.add(value)
        parsed.append(str(value))
    return parsed


def _parse_enum_list(raw: object, *, allowed: frozenset[str], field: str) -> list[str]:
    if not isinstance(raw, list):
        raise ApiError(422, f"{field} must be an array", "INVALID_PREDICATE", field=field)
    if len(raw) > MAX_OR_FANOUT:
        raise ApiError(
            422,
            f"{field} has {len(raw)} values; max is {MAX_OR_FANOUT}",
            "PREDICATE_TOO_COMPLEX",
            field=field,
        )
    if len(raw) == 0:
        raise ApiError(
            422,
            f"{field} must list at least one value",
            "INVALID_PREDICATE",
            field=field,
        )
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, (dict, list)) or not isinstance(item, str):
            raise ApiError(
                422,
                f"{field} must contain strings",
                "INVALID_PREDICATE",
                field=field,
            )
        if item not in allowed:
            raise ApiError(
                422,
                f"{field} contains an unsupported value",
                "INVALID_PREDICATE",
                field=field,
            )
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _parse_aware_utc(raw: object, *, field: str) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise ApiError(
            422,
            f"{field} must be a timezone-aware ISO-8601 string",
            "INVALID_PREDICATE",
            field=field,
        )
    text = raw.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ApiError(
            422,
            f"{field} must be a timezone-aware ISO-8601 string",
            "INVALID_PREDICATE",
            field=field,
        ) from exc
    if parsed.tzinfo is None:
        raise ApiError(
            422,
            f"{field} must include a timezone offset",
            "INVALID_PREDICATE",
            field=field,
        )
    return parsed.astimezone(timezone.utc)


def _utc_z(value: datetime) -> str:
    stamp = value.astimezone(timezone.utc).replace(microsecond=value.microsecond)
    text = stamp.strftime("%Y-%m-%dT%H:%M:%S")
    if stamp.microsecond:
        text += f".{stamp.microsecond:06d}".rstrip("0")
    return text + "Z"


def _missing_ids(
    db: Session,
    owner_id: uuid.UUID,
    *,
    model: type[Project] | type[Epic] | type[Label],
    raw_ids: object,
    kind: str,
    dimension: str,
) -> list[dict[str, str]]:
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    parsed: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for item in raw_ids:
        try:
            value = item if isinstance(item, uuid.UUID) else uuid.UUID(str(item))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ApiError(
                422,
                f"dimensions.{dimension} contains an invalid uuid",
                "INVALID_PREDICATE",
                field=f"dimensions.{dimension}",
            ) from exc
        if value in seen:
            continue
        seen.add(value)
        parsed.append(value)
    found = {
        row_id
        for (row_id,) in db.query(model.id)
        .filter(model.owner_id == owner_id, model.id.in_(parsed))
        .all()
    }
    return [
        {"kind": kind, "id": str(value), "dimension": dimension}
        for value in parsed
        if value not in found
    ]
