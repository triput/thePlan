# ==============================================================================
#  File: apps/api/app/services/scheduling_day_scoped.py
#  Description: S2-V4b day-scoped writers (Change / Only-allow / scoped family+rules).
#  Component: Scheduling / Settings — S2-V4b
#  Version: 1.1
#  Created: 2026-10-14
#  Last Update: 2026-10-14 (V4b-D1: JSON-ready family_payload)
# ==============================================================================

"""Authorized V4b day-scoped writers. Standing V4 writers stay in
``scheduling_assignments`` and still reject temporal selectors.

Resolution / fingerprint hashing of stored rows is Tesla's lane — do not edit
``composition.py`` / ``input_fingerprint.py`` / ``placement.py`` here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal, Mapping
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import User
from app.models.enums import (
    SchedulingAssignmentFamily,
    SchedulingDayPayloadKind,
    SchedulingDayScopedOpKind,
    SchedulingDaySelectorKind,
    SchedulingRuleKind,
)
from app.models.scheduling_day_scoped import SchedulingDayScopedOp
from app.scheduler.assignment_resolve import load_exceptions_at_scope
from app.services import scheduling_assignments as standing
from app.services.scheduling_revision import (
    assert_scheduling_revision,
    increment_scheduling_revision,
    lock_owner_scheduling,
)

ScopeKind = Literal["task", "project", "epic"]

SELECTOR_REQUIRED_CODE = "SCHEDULING_DAY_SELECTOR_REQUIRED"
SELECTOR_INVALID_CODE = "SCHEDULING_DAY_SELECTOR_INVALID"
EXPIRY_INVALID_CODE = "SCHEDULING_DAY_EXPIRY_INVALID"
OVERLAP_UNRESOLVED_CODE = "SCHEDULING_DAY_OVERLAP_UNRESOLVED"
PAYLOAD_INVALID_CODE = "SCHEDULING_DAY_PAYLOAD_INVALID"
OP_NOT_FOUND_CODE = "SCHEDULING_DAY_SCOPED_OP_NOT_FOUND"
SCOPED_REVERT_MISSING = "SCHEDULING_SCOPED_REVERT_NOT_AVAILABLE"
SCOPED_REVERT_MISMATCH = "SCHEDULING_SCOPED_REVERT_MISMATCH"
SCOPED_REVERT_UNUSABLE = "SCHEDULING_SCOPED_REVERT_UNUSABLE_PRIOR"

_REPLACEMENT_OP_KINDS = frozenset(
    {
        SchedulingDayScopedOpKind.change_selected,
        SchedulingDayScopedOpKind.replace_named_scoped,
        SchedulingDayScopedOpKind.family_replace_scoped,
    }
)
_ADDITION_OP_KINDS = frozenset(
    {
        SchedulingDayScopedOpKind.add_scoped,
        # Only-allow is exclusive eligibility, not May-union; for overlap with a
        # replacement it still needs an explicit addition_survives choice.
        SchedulingDayScopedOpKind.only_allow,
    }
)


@dataclass(frozen=True)
class ParsedSelector:
    kind: SchedulingDaySelectorKind
    on_date: date | None = None
    weekdays: tuple[int, ...] | None = None
    start_date: date | None = None
    end_date: date | None = None


def _json_ready_payload(value: Any) -> Any:
    """Coerce nested values for JSONB columns (UUID / date / datetime / Enum).

    Scoped family payloads are stored as JSONB. Route ``model_dump()`` without
    ``mode="json"`` leaves ``UUID`` instances inside ``rules``; PostgreSQL flush
    then raises ``TypeError``. Apply to the complete stored payload, not just
    individual fields.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return _json_ready_payload(value.value)
    if isinstance(value, Mapping):
        return {
            (str(key) if isinstance(key, UUID) else key): _json_ready_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_ready_payload(item) for item in value]
    raise TypeError(
        f"scoped family payload value of type {type(value).__name__} "
        "is not JSON serializable"
    )


def _parse_date(value: Any, *, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        raise ApiError(
            422,
            f"{field} must be a civil date (YYYY-MM-DD), not a datetime instant",
            SELECTOR_INVALID_CODE,
            field=field,
        )
    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ApiError(
            422,
            f"{field} must be an ISO civil date (YYYY-MM-DD)",
            SELECTOR_INVALID_CODE,
            field=field,
            value=text,
        ) from exc


def _parse_weekdays(raw: Any) -> tuple[int, ...]:
    if isinstance(raw, int):
        values = [raw]
    elif isinstance(raw, list):
        values = list(raw)
    else:
        raise ApiError(
            422,
            "weekdays must be an int or list of ints (Mon=0 … Sun=6)",
            SELECTOR_INVALID_CODE,
            field="weekdays",
        )
    out: list[int] = []
    for item in values:
        day = int(item)
        if day < 0 or day > 6:
            raise ApiError(
                422,
                "weekday values must be 0..6 (Monday=0)",
                SELECTOR_INVALID_CODE,
                field="weekdays",
                value=day,
            )
        if day not in out:
            out.append(day)
    if not out:
        raise ApiError(
            422,
            "weekday selector requires at least one weekday",
            SELECTOR_INVALID_CODE,
            field="weekdays",
        )
    return tuple(sorted(out))


def parse_selector(payload: dict[str, Any]) -> ParsedSelector:
    """Require exactly one V4b selector form. No silent drop of unknown keys."""
    structured = payload.get("selector")
    if structured is not None:
        if not isinstance(structured, dict):
            raise ApiError(
                422,
                "selector must be an object",
                SELECTOR_INVALID_CODE,
                field="selector",
            )
        kind_raw = str(structured.get("kind") or "").strip()
        try:
            kind = SchedulingDaySelectorKind(kind_raw)
        except ValueError as exc:
            raise ApiError(
                422,
                "selector.kind must be one_date, weekday_standing, or date_range",
                SELECTOR_INVALID_CODE,
                field="selector.kind",
            ) from exc
        if kind == SchedulingDaySelectorKind.one_date:
            on = structured.get("on_date", structured.get("on"))
            if on is None:
                raise ApiError(
                    422,
                    "one_date selector requires on_date",
                    SELECTOR_INVALID_CODE,
                )
            return ParsedSelector(
                kind=kind, on_date=_parse_date(on, field="selector.on_date")
            )
        if kind == SchedulingDaySelectorKind.weekday_standing:
            days = structured.get("weekdays", structured.get("weekday"))
            if days is None:
                days = structured.get("days_of_week")
            if days is None:
                raise ApiError(
                    422,
                    "weekday_standing selector requires weekdays",
                    SELECTOR_INVALID_CODE,
                )
            return ParsedSelector(kind=kind, weekdays=_parse_weekdays(days))
        start = structured.get("start_date", structured.get("local_start_date"))
        end = structured.get("end_date", structured.get("local_end_date"))
        if start is None or end is None:
            raise ApiError(
                422,
                "date_range selector requires start_date and end_date",
                SELECTOR_INVALID_CODE,
            )
        start_d = _parse_date(start, field="selector.start_date")
        end_d = _parse_date(end, field="selector.end_date")
        if end_d < start_d:
            raise ApiError(
                422,
                "date_range end_date must be on or after start_date",
                SELECTOR_INVALID_CODE,
            )
        return ParsedSelector(kind=kind, start_date=start_d, end_date=end_d)

    has_one = any(k in payload for k in ("on_date", "on"))
    has_week = any(k in payload for k in ("weekday", "weekdays", "days_of_week"))
    has_range = "date_range" in payload or (
        "local_start_date" in payload and "local_end_date" in payload
    )
    forms = sum(bool(x) for x in (has_one, has_week, has_range))
    if forms == 0:
        raise ApiError(
            422,
            "Day-scoped writers require a selector (one_date, weekday_standing, "
            "or date_range). Saved configuration is unchanged.",
            SELECTOR_REQUIRED_CODE,
        )
    if forms > 1:
        raise ApiError(
            422,
            "Provide exactly one selector form; combinations reject with no write.",
            SELECTOR_INVALID_CODE,
        )
    if has_one:
        on = payload.get("on_date", payload.get("on"))
        return ParsedSelector(
            kind=SchedulingDaySelectorKind.one_date,
            on_date=_parse_date(on, field="on_date"),
        )
    if has_week:
        days = payload.get("weekdays", payload.get("weekday"))
        if days is None:
            days = payload.get("days_of_week")
        return ParsedSelector(
            kind=SchedulingDaySelectorKind.weekday_standing,
            weekdays=_parse_weekdays(days),
        )
    if "date_range" in payload:
        raw = payload["date_range"]
        if not isinstance(raw, dict):
            raise ApiError(
                422,
                "date_range must be an object with start and end civil dates",
                SELECTOR_INVALID_CODE,
            )
        start = raw.get("start", raw.get("start_date", raw.get("local_start_date")))
        end = raw.get("end", raw.get("end_date", raw.get("local_end_date")))
    else:
        start = payload.get("local_start_date")
        end = payload.get("local_end_date")
    if start is None or end is None:
        raise ApiError(
            422,
            "date_range requires start and end civil dates",
            SELECTOR_INVALID_CODE,
        )
    start_d = _parse_date(start, field="local_start_date")
    end_d = _parse_date(end, field="local_end_date")
    if end_d < start_d:
        raise ApiError(
            422,
            "date_range end must be on or after start",
            SELECTOR_INVALID_CODE,
        )
    return ParsedSelector(
        kind=SchedulingDaySelectorKind.date_range,
        start_date=start_d,
        end_date=end_d,
    )


def parse_expires_at(payload: dict[str, Any]) -> datetime | None:
    """Optional fixed-instant expiry. Civil date-only values reject (R1)."""
    present: list[tuple[str, Any]] = []
    for key in ("expires_at", "expiry", "expires_on"):
        if key in payload and payload[key] is not None:
            present.append((key, payload[key]))
    if not present:
        return None
    instants: list[datetime] = []
    for key, value in present:
        if isinstance(value, datetime):
            instant = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        else:
            text = str(value).strip()
            if len(text) <= 10 and "T" not in text and " " not in text:
                raise ApiError(
                    422,
                    f"{key} must be an explicit timestamptz instant, not a civil "
                    "date. Last selected occurrence date is not expiry (R1).",
                    EXPIRY_INVALID_CODE,
                    field=key,
                )
            try:
                instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ApiError(
                    422,
                    f"{key} must be an ISO-8601 timestamptz instant",
                    EXPIRY_INVALID_CODE,
                    field=key,
                ) from exc
            if instant.tzinfo is None:
                raise ApiError(
                    422,
                    f"{key} must include a timezone offset (fixed instant)",
                    EXPIRY_INVALID_CODE,
                    field=key,
                )
        instants.append(instant.astimezone(timezone.utc))
    unique = {i.isoformat() for i in instants}
    if len(unique) > 1:
        raise ApiError(
            422,
            "Contradictory instant expiry values reject with no write.",
            EXPIRY_INVALID_CODE,
            rejected_fields=[k for k, _ in present],
        )
    return instants[0]


def _selector_dates(sel: ParsedSelector) -> set[date] | None:
    """Finite civil dates when known; None means open weekday-standing."""
    if sel.kind == SchedulingDaySelectorKind.one_date:
        assert sel.on_date is not None
        return {sel.on_date}
    if sel.kind == SchedulingDaySelectorKind.date_range:
        assert sel.start_date is not None and sel.end_date is not None
        out: set[date] = set()
        cur = sel.start_date
        while cur <= sel.end_date:
            out.add(cur)
            cur += timedelta(days=1)
        return out
    return None


def selectors_overlap(a: ParsedSelector, b: ParsedSelector) -> bool:
    """Civil-date / weekday overlap for writer precedence (V4b-P3)."""
    dates_a = _selector_dates(a)
    dates_b = _selector_dates(b)
    if dates_a is not None and dates_b is not None:
        return bool(dates_a.intersection(dates_b))
    if dates_a is not None and b.kind == SchedulingDaySelectorKind.weekday_standing:
        assert b.weekdays is not None
        return any(d.weekday() in b.weekdays for d in dates_a)
    if dates_b is not None and a.kind == SchedulingDaySelectorKind.weekday_standing:
        assert a.weekdays is not None
        return any(d.weekday() in a.weekdays for d in dates_b)
    if (
        a.kind == SchedulingDaySelectorKind.weekday_standing
        and b.kind == SchedulingDaySelectorKind.weekday_standing
    ):
        assert a.weekdays is not None and b.weekdays is not None
        return bool(set(a.weekdays).intersection(b.weekdays))
    return False


def _row_selector(row: SchedulingDayScopedOp) -> ParsedSelector:
    return ParsedSelector(
        kind=row.selector_kind,
        on_date=row.civil_on_date,
        weekdays=tuple(row.civil_weekdays) if row.civil_weekdays else None,
        start_date=row.civil_start_date,
        end_date=row.civil_end_date,
    )


def _same_named_target(a: SchedulingDayScopedOp, *, name: str | None, kind: str | None) -> bool:
    if name is None:
        return False
    if a.target_rule_name == name:
        if kind is None or a.target_rule_kind is None:
            return True
        return a.target_rule_kind.value == kind
    if a.rule_name == name:
        if kind is None or a.rule_kind is None:
            return True
        return a.rule_kind.value == kind
    return False


def _same_policy_lane(
    existing: SchedulingDayScopedOp,
    *,
    policy_id: UUID | None,
    named_target: str | None,
    named_kind: str | None,
    op_kind: SchedulingDayScopedOpKind,
) -> bool:
    """Different named targets do not conflict from date overlap alone."""
    if op_kind in (
        SchedulingDayScopedOpKind.change_selected,
        SchedulingDayScopedOpKind.only_allow,
    ):
        # Day Change / Only-allow share a scope-level availability lane when
        # they touch the same policy identity (or both empty).
        if existing.op_kind not in (
            SchedulingDayScopedOpKind.change_selected,
            SchedulingDayScopedOpKind.only_allow,
        ):
            return False
        if policy_id is None:
            return existing.payload_kind == SchedulingDayPayloadKind.empty
        return (
            existing.payload_kind == SchedulingDayPayloadKind.policy
            and existing.policy_id == policy_id
        )
    if op_kind == SchedulingDayScopedOpKind.add_scoped:
        return existing.op_kind == SchedulingDayScopedOpKind.add_scoped and _same_named_target(
            existing, name=named_target, kind=named_kind
        )
    if op_kind == SchedulingDayScopedOpKind.replace_named_scoped:
        return existing.op_kind in (
            SchedulingDayScopedOpKind.replace_named_scoped,
            SchedulingDayScopedOpKind.add_scoped,
        ) and _same_named_target(existing, name=named_target, kind=named_kind)
    if op_kind == SchedulingDayScopedOpKind.waive_named_scoped:
        return existing.op_kind == SchedulingDayScopedOpKind.waive_named_scoped and (
            existing.target_rule_name == named_target
        )
    if op_kind in (
        SchedulingDayScopedOpKind.family_replace_scoped,
        SchedulingDayScopedOpKind.clear_scoped,
    ):
        return existing.op_kind in (
            SchedulingDayScopedOpKind.family_replace_scoped,
            SchedulingDayScopedOpKind.clear_scoped,
        )
    return False


def _detect_cycle(
    new_id: UUID,
    replaces: list[UUID],
    edges: dict[UUID, list[UUID]],
) -> bool:
    graph = {k: list(v) for k, v in edges.items()}
    graph[new_id] = list(replaces)
    visiting: set[UUID] = set()
    seen: set[UUID] = set()

    def dfs(node: UUID) -> bool:
        if node in visiting:
            return True
        if node in seen:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if dfs(nxt):
                return True
        visiting.remove(node)
        seen.add(node)
        return False

    return dfs(new_id)


def _assert_overlap_ok(
    db: Session,
    *,
    owner_id: UUID,
    scope: ScopeKind,
    scope_id: UUID,
    op_kind: SchedulingDayScopedOpKind,
    selector: ParsedSelector,
    policy_id: UUID | None,
    named_target: str | None,
    named_kind: str | None,
    replaces_op_ids: list[UUID] | None,
    addition_survives: bool | None,
    new_id: UUID,
) -> None:
    rows = (
        db.query(SchedulingDayScopedOp)
        .filter(
            SchedulingDayScopedOp.owner_id == owner_id,
            SchedulingDayScopedOp.scope_kind == standing._scope_enum(scope),
            SchedulingDayScopedOp.scope_id == scope_id,
        )
        .all()
    )
    overlapping_replacements: list[SchedulingDayScopedOp] = []
    overlapping_additions: list[SchedulingDayScopedOp] = []
    for row in rows:
        if not _same_policy_lane(
            row,
            policy_id=policy_id,
            named_target=named_target,
            named_kind=named_kind,
            op_kind=op_kind,
        ):
            continue
        if not selectors_overlap(selector, _row_selector(row)):
            continue
        if row.op_kind in _REPLACEMENT_OP_KINDS:
            overlapping_replacements.append(row)
        if row.op_kind in _ADDITION_OP_KINDS:
            overlapping_additions.append(row)

    replaces = list(replaces_op_ids or [])
    if op_kind in _REPLACEMENT_OP_KINDS and overlapping_replacements:
        needed = {row.id for row in overlapping_replacements}
        if set(replaces) != needed:
            raise ApiError(
                422,
                "Overlapping replacements require explicit which-replaces-which "
                "naming every overlapping stable op id. Atomic reject; no write.",
                OVERLAP_UNRESOLVED_CODE,
                overlapping_op_ids=[str(i) for i in sorted(needed, key=str)],
                provided_replaces_op_ids=[str(i) for i in replaces],
            )
        edges = {
            row.id: list(row.replaces_op_ids or [])
            for row in rows
            if row.replaces_op_ids
        }
        if _detect_cycle(new_id, replaces, edges):
            raise ApiError(
                422,
                "Cyclic which-replaces-which precedence rejects atomically.",
                OVERLAP_UNRESOLVED_CODE,
            )
    elif replaces:
        # No overlapping replacements — explicit replaces list must be empty
        # or name only known overlapping targets (already handled). Extra ids
        # that are not overlapping replacements reject.
        known = {row.id for row in rows}
        unknown = [i for i in replaces if i not in known]
        if unknown:
            raise ApiError(
                422,
                "replaces_op_ids must name existing scoped ops at this scope",
                OVERLAP_UNRESOLVED_CODE,
                unknown_op_ids=[str(i) for i in unknown],
            )

    if op_kind in _ADDITION_OP_KINDS and overlapping_replacements:
        if addition_survives is None:
            raise ApiError(
                422,
                "Addition overlapping a replacement requires explicit "
                "addition_survives. Atomic reject; no write.",
                OVERLAP_UNRESOLVED_CODE,
                overlapping_op_ids=[
                    str(row.id) for row in overlapping_replacements
                ],
            )
    # Additions combine with each other — overlapping_additions is not a conflict.
    _ = overlapping_additions


def _apply_selector_columns(
    row: SchedulingDayScopedOp, selector: ParsedSelector
) -> None:
    row.selector_kind = selector.kind
    row.civil_on_date = selector.on_date
    row.civil_weekdays = list(selector.weekdays) if selector.weekdays else None
    row.civil_start_date = selector.start_date
    row.civil_end_date = selector.end_date


def _parse_windows_payload(
    payload: dict[str, Any],
    *,
    require: bool,
) -> tuple[SchedulingDayPayloadKind, UUID | None]:
    """Distinct omit vs empty vs policy windows."""
    empty_set = bool(payload.get("empty_set") or payload.get("empty"))
    policy_raw = payload.get("policy_id")
    windows_key_present = any(
        k in payload for k in ("empty_set", "empty", "policy_id", "windows")
    )
    if not require and not windows_key_present:
        return SchedulingDayPayloadKind.none, None
    if require and not windows_key_present and not empty_set and policy_raw is None:
        raise ApiError(
            422,
            "Windows payload required: send empty_set=true or policy_id. "
            "Omit is not empty.",
            PAYLOAD_INVALID_CODE,
        )
    if empty_set:
        if policy_raw is not None:
            raise ApiError(
                422,
                "empty_set must not include policy_id",
                PAYLOAD_INVALID_CODE,
            )
        return SchedulingDayPayloadKind.empty, None
    if policy_raw is None:
        raise ApiError(
            422,
            "Non-empty windows require policy_id (omit is not empty)",
            PAYLOAD_INVALID_CODE,
        )
    return SchedulingDayPayloadKind.policy, UUID(str(policy_raw))


def _load_ops_at_scope(
    db: Session, *, owner_id: UUID, scope: ScopeKind, scope_id: UUID
) -> list[SchedulingDayScopedOp]:
    return (
        db.query(SchedulingDayScopedOp)
        .filter(
            SchedulingDayScopedOp.owner_id == owner_id,
            SchedulingDayScopedOp.scope_kind == standing._scope_enum(scope),
            SchedulingDayScopedOp.scope_id == scope_id,
        )
        .order_by(SchedulingDayScopedOp.created_at, SchedulingDayScopedOp.id)
        .all()
    )


def _op_out(row: SchedulingDayScopedOp) -> dict[str, Any]:
    return {
        "id": row.id,
        "op_kind": row.op_kind.value,
        "scope": row.scope_kind.value,
        "scope_id": row.scope_id,
        "selector_kind": row.selector_kind.value,
        "civil_on_date": row.civil_on_date.isoformat() if row.civil_on_date else None,
        "civil_weekdays": list(row.civil_weekdays) if row.civil_weekdays else None,
        "civil_start_date": (
            row.civil_start_date.isoformat() if row.civil_start_date else None
        ),
        "civil_end_date": (
            row.civil_end_date.isoformat() if row.civil_end_date else None
        ),
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "payload_kind": row.payload_kind.value,
        "policy_id": row.policy_id,
        "rule_name": row.rule_name,
        "rule_kind": row.rule_kind.value if row.rule_kind else None,
        "target_rule_name": row.target_rule_name,
        "target_rule_kind": (
            row.target_rule_kind.value if row.target_rule_kind else None
        ),
        "replacement_name": row.replacement_name,
        "replacement_policy_id": row.replacement_policy_id,
        "replacement_empty_set": bool(row.replacement_empty_set),
        "target_family": row.target_family.value if row.target_family else None,
        "replaces_op_ids": [str(i) for i in (row.replaces_op_ids or [])],
        "addition_survives": row.addition_survives,
        "assignment_id": row.assignment_id,
    }


def _begin_scoped_write(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    raw_body: dict[str, Any] | None,
) -> tuple[Any, ParsedSelector, datetime | None, Any]:
    standing.reject_deferred_exception_forms(raw_body, allow_v4b_temporal=True)
    entity = standing._get_scope_entity(db, user, scope, scope_id)
    body = raw_body or {}
    selector = parse_selector(body)
    expires_at = parse_expires_at(body)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)
    return entity, selector, expires_at, settings


def _precedence_from_body(
    body: dict[str, Any],
) -> tuple[list[UUID] | None, bool | None]:
    replaces_raw = body.get("replaces_op_ids", body.get("replaces"))
    replaces: list[UUID] | None = None
    if replaces_raw is not None:
        if not isinstance(replaces_raw, list):
            raise ApiError(
                422,
                "replaces_op_ids must be a list of UUIDs",
                OVERLAP_UNRESOLVED_CODE,
            )
        replaces = [UUID(str(x)) for x in replaces_raw]
    survives = body.get("addition_survives")
    if survives is not None:
        survives = bool(survives)
    return replaces, survives


def day_change_selected(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``day.change_selected`` — replacement on selected occurrences."""
    _entity, selector, expires_at, settings = _begin_scoped_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=expected_revision,
        raw_body=raw_body,
    )
    body = raw_body or {}
    payload_kind, policy_id = _parse_windows_payload(body, require=True)
    if policy_id is not None:
        standing._verify_owned_policy(db, user, policy_id)
    replaces, survives = _precedence_from_body(body)
    new_id = uuid4()
    _assert_overlap_ok(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.change_selected,
        selector=selector,
        policy_id=policy_id,
        named_target=None,
        named_kind=None,
        replaces_op_ids=replaces,
        addition_survives=survives,
        new_id=new_id,
    )
    local = standing.read_local_scope(db, user, scope, scope_id)
    row = SchedulingDayScopedOp(
        id=new_id,
        owner_id=user.id,
        scope_kind=standing._scope_enum(scope),
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.change_selected,
        payload_kind=payload_kind,
        policy_id=policy_id,
        expires_at=expires_at,
        replaces_op_ids=replaces,
        addition_survives=survives,
        assignment_id=local.assignment.id if local.assignment is not None else None,
    )
    _apply_selector_columns(row, selector)
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "op": row,
        "op_out": _op_out(row),
    }


def day_only_allow(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``day.only_allow`` — exclusive eligibility on selected days/times."""
    _entity, selector, expires_at, settings = _begin_scoped_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=expected_revision,
        raw_body=raw_body,
    )
    body = raw_body or {}
    payload_kind, policy_id = _parse_windows_payload(body, require=True)
    if policy_id is not None:
        standing._verify_owned_policy(db, user, policy_id)
    replaces, survives = _precedence_from_body(body)
    new_id = uuid4()
    # Only-allow is exclusive, not a May addition; still need addition_survives
    # when it overlaps a replacement on the same policy lane.
    _assert_overlap_ok(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.only_allow,
        selector=selector,
        policy_id=policy_id,
        named_target=None,
        named_kind=None,
        replaces_op_ids=replaces,
        addition_survives=survives,
        new_id=new_id,
    )
    local = standing.read_local_scope(db, user, scope, scope_id)
    row = SchedulingDayScopedOp(
        id=new_id,
        owner_id=user.id,
        scope_kind=standing._scope_enum(scope),
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.only_allow,
        payload_kind=payload_kind,
        policy_id=policy_id,
        expires_at=expires_at,
        replaces_op_ids=replaces,
        addition_survives=survives,
        assignment_id=local.assignment.id if local.assignment is not None else None,
    )
    _apply_selector_columns(row, selector)
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "op": row,
        "op_out": _op_out(row),
    }


def family_replace_scoped(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    target_family: Literal["legacy", "new_rule", "none"],
    preferred_time_window_id: UUID | None = None,
    may_presence: Literal["omit", "explicit"] = "omit",
    rules: list[dict[str, Any]] | None = None,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``assignment.family_replace_scoped`` — overlay; standing left intact."""
    _entity, selector, expires_at, settings = _begin_scoped_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=expected_revision,
        raw_body=raw_body,
    )
    body = raw_body or {}
    replaces, survives = _precedence_from_body(body)
    current = standing.read_local_scope(db, user, scope, scope_id)
    prior_family = SchedulingAssignmentFamily(current.family)
    prior_map = current.preferred_time_window_id
    prior_payload: dict[str, Any] | None = None
    if current.assignment is not None:
        prior_payload = standing._snapshot_new_rule(
            current.assignment,
            load_exceptions_at_scope(
                db, owner_id=user.id, scope=scope, scope_id=scope_id
            ),
        )

    family_payload: dict[str, Any] = {"target_family": target_family}
    if target_family == "legacy":
        if preferred_time_window_id is None:
            raise ApiError(
                422,
                "family-replace-scoped to legacy requires preferred_time_window_id",
                "LEGACY_MAP_REQUIRED",
            )
        standing._verify_owned_focus_window(db, user, preferred_time_window_id)
        family_payload["preferred_time_window_id"] = str(preferred_time_window_id)
    elif target_family == "new_rule":
        family_payload["may_presence"] = may_presence
        family_payload["rules"] = list(rules or [])
        for rule in family_payload["rules"]:
            if rule.get("empty_set") or rule.get("policy_id") is None:
                continue
            standing._verify_owned_policy(db, user, UUID(str(rule["policy_id"])))
    # Complete payload must be JSONB-safe before flush (V4b-D1).
    family_payload = _json_ready_payload(family_payload)

    new_id = uuid4()
    _assert_overlap_ok(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.family_replace_scoped,
        selector=selector,
        policy_id=None,
        named_target=None,
        named_kind=None,
        replaces_op_ids=replaces,
        addition_survives=survives,
        new_id=new_id,
    )
    row = SchedulingDayScopedOp(
        id=new_id,
        owner_id=user.id,
        scope_kind=standing._scope_enum(scope),
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.family_replace_scoped,
        payload_kind=SchedulingDayPayloadKind.family,
        family_payload=family_payload,
        target_family=SchedulingAssignmentFamily(target_family),
        prior_family=prior_family,
        prior_preferred_time_window_id=prior_map,
        prior_new_rule_payload=prior_payload,
        expires_at=expires_at,
        replaces_op_ids=replaces,
        addition_survives=survives,
        assignment_id=current.assignment.id if current.assignment is not None else None,
    )
    _apply_selector_columns(row, selector)
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "replacement_id": row.id,
        "op": row,
        "op_out": _op_out(row),
    }


def clear_scoped(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``assignment.clear_scoped`` — suppress local; do not delete standing."""
    _entity, selector, expires_at, settings = _begin_scoped_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=expected_revision,
        raw_body=raw_body,
    )
    body = raw_body or {}
    replaces, survives = _precedence_from_body(body)
    current = standing.read_local_scope(db, user, scope, scope_id)
    if current.family == "none" and current.conflict is None:
        raise ApiError(
            422,
            "No local scheduling assignment to suppress at this scope",
            "NO_LOCAL_ASSIGNMENT",
            scope=scope,
            scope_id=str(scope_id),
        )
    new_id = uuid4()
    _assert_overlap_ok(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.clear_scoped,
        selector=selector,
        policy_id=None,
        named_target=None,
        named_kind=None,
        replaces_op_ids=replaces,
        addition_survives=survives,
        new_id=new_id,
    )
    row = SchedulingDayScopedOp(
        id=new_id,
        owner_id=user.id,
        scope_kind=standing._scope_enum(scope),
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.clear_scoped,
        payload_kind=SchedulingDayPayloadKind.none,
        expires_at=expires_at,
        replaces_op_ids=replaces,
        addition_survives=survives,
        assignment_id=current.assignment.id if current.assignment is not None else None,
    )
    _apply_selector_columns(row, selector)
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "cleared_scoped": True,
        "op": row,
        "op_out": _op_out(row),
    }


def revert_scoped(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    replacement_id: UUID,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``assignment.revert_scoped`` — restore captured prior; remove overlay."""
    standing.reject_deferred_exception_forms(raw_body, allow_v4b_temporal=True)
    # Revert identifies the replacement; selector on the body is optional noise
    # that must not be required. Context / ignore-all still rejected above.
    if raw_body and any(
        k in raw_body for k in standing.V4B_TEMPORAL_FORM_KEYS if k != "selector"
    ):
        # Allow empty body or only expected_revision / replacement_id.
        # If temporal keys are present without matching the stored selector,
        # still OK — identity is replacement_id. Reject context already done.
        pass
    entity = standing._get_scope_entity(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    row = (
        db.query(SchedulingDayScopedOp)
        .filter(
            SchedulingDayScopedOp.owner_id == user.id,
            SchedulingDayScopedOp.scope_kind == standing._scope_enum(scope),
            SchedulingDayScopedOp.scope_id == scope_id,
            SchedulingDayScopedOp.op_kind
            == SchedulingDayScopedOpKind.family_replace_scoped,
            SchedulingDayScopedOp.id == replacement_id,
        )
        .one_or_none()
    )
    if row is None:
        raise ApiError(
            422,
            "No identified scoped family-replace at this scope for replacement_id",
            SCOPED_REVERT_MISSING,
            scope=scope,
            scope_id=str(scope_id),
            provided_replacement_id=str(replacement_id),
            repair="Perform family-replace-scoped before revert, or remove the op.",
        )

    if row.prior_family == SchedulingAssignmentFamily.legacy:
        if row.prior_preferred_time_window_id is None:
            raise ApiError(
                422,
                "Prior legacy Time Map is missing or was deleted; choose a repair",
                SCOPED_REVERT_UNUSABLE,
                repair="Clear, pick another map, or family-replace-scoped fresh.",
            )
        try:
            standing._verify_owned_focus_window(
                db, user, row.prior_preferred_time_window_id
            )
        except ApiError as exc:
            raise ApiError(
                422,
                "Prior legacy Time Map is no longer usable for this owner",
                SCOPED_REVERT_UNUSABLE,
                repair="Clear, pick another map, or family-replace-scoped fresh.",
                cause=exc.content.get("code"),
            ) from exc

    if row.prior_family == SchedulingAssignmentFamily.new_rule:
        payload = row.prior_new_rule_payload
        if not isinstance(payload, dict):
            raise ApiError(
                422,
                "Prior new-rule payload is missing or unusable",
                SCOPED_REVERT_UNUSABLE,
                repair="Clear and re-assign, or family-replace-scoped fresh.",
            )
        for rule in list(payload.get("rules") or []):
            if rule.get("empty_set") or rule.get("policy_id") is None:
                continue
            try:
                standing._verify_owned_policy(db, user, UUID(str(rule["policy_id"])))
            except ApiError as exc:
                raise ApiError(
                    422,
                    "Prior new-rule references a removed or foreign policy",
                    SCOPED_REVERT_UNUSABLE,
                    repair="Clear and re-assign with current policies.",
                    cause=exc.content.get("code"),
                ) from exc

    # Drop the overlay first so assignment delete does not fight the optional
    # assignment_id FK, then restore captured prior into standing.
    prior_family = row.prior_family
    prior_map = row.prior_preferred_time_window_id
    prior_payload = row.prior_new_rule_payload
    db.delete(row)
    db.flush()

    standing._set_legacy_window_id(entity, None)
    standing._delete_new_rule_at_scope(
        db, owner_id=user.id, scope=scope, scope_id=scope_id
    )
    assignment_out = None
    if prior_family == SchedulingAssignmentFamily.legacy:
        standing._set_legacy_window_id(entity, prior_map)
    elif prior_family == SchedulingAssignmentFamily.new_rule:
        assert isinstance(prior_payload, dict)
        assignment_out = standing._restore_new_rule_payload(
            db,
            user,
            scope=scope,
            scope_id=scope_id,
            payload=prior_payload,
        )

    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "family": prior_family.value if prior_family else "none",
        "scheduling_revision": revision,
        "restored_replacement_id": replacement_id,
        "assignment": assignment_out,
        "preferred_time_window_id": standing._legacy_window_id(entity),
    }


def rule_add_scoped(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    name: str,
    kind: Literal["may", "must", "prefer"],
    policy_id: UUID | None = None,
    empty_set: bool = False,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``rule.add_scoped`` — named May/Must/Prefer addition with selector."""
    _entity, selector, expires_at, settings = _begin_scoped_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=expected_revision,
        raw_body=raw_body,
    )
    _entity2, assignment = standing._require_new_rule_family(
        db, user, scope, scope_id
    )
    del _entity2
    body = raw_body or {}
    clean_name = name.strip()
    if not clean_name:
        raise ApiError(422, "Rule name is required", "RULE_NAME_REQUIRED")
    if empty_set:
        if policy_id is not None:
            raise ApiError(
                422,
                "empty_set rules must not include policy_id",
                PAYLOAD_INVALID_CODE,
            )
        payload_kind = SchedulingDayPayloadKind.empty
        resolved_policy = None
    else:
        if policy_id is None:
            raise ApiError(422, "policy_id is required", "RULE_POLICY_REQUIRED")
        standing._verify_owned_policy(db, user, policy_id)
        payload_kind = SchedulingDayPayloadKind.policy
        resolved_policy = policy_id
    replaces, survives = _precedence_from_body(body)
    new_id = uuid4()
    _assert_overlap_ok(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.add_scoped,
        selector=selector,
        policy_id=resolved_policy,
        named_target=clean_name,
        named_kind=kind,
        replaces_op_ids=replaces,
        addition_survives=survives,
        new_id=new_id,
    )
    row = SchedulingDayScopedOp(
        id=new_id,
        owner_id=user.id,
        scope_kind=standing._scope_enum(scope),
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.add_scoped,
        payload_kind=payload_kind,
        policy_id=resolved_policy,
        rule_name=clean_name,
        rule_kind=SchedulingRuleKind(kind),
        expires_at=expires_at,
        replaces_op_ids=replaces,
        addition_survives=survives,
        assignment_id=assignment.id,
    )
    _apply_selector_columns(row, selector)
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "op": row,
        "op_out": _op_out(row),
    }


def rule_replace_named_scoped(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    target_rule_name: str,
    target_rule_kind: Literal["may", "must", "prefer"],
    replacement_name: str,
    policy_id: UUID | None = None,
    empty_set: bool = False,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``rule.replace_named_scoped``."""
    _entity, selector, expires_at, settings = _begin_scoped_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=expected_revision,
        raw_body=raw_body,
    )
    _e, assignment = standing._require_new_rule_family(db, user, scope, scope_id)
    del _e
    body = raw_body or {}
    clean_target = target_rule_name.strip()
    clean_replacement = replacement_name.strip()
    if not clean_target or not clean_replacement:
        raise ApiError(422, "target and replacement names are required", "RULE_NAME_REQUIRED")
    if empty_set:
        if policy_id is not None:
            raise ApiError(
                422,
                "empty_set replacement must not include policy_id",
                PAYLOAD_INVALID_CODE,
            )
        payload_kind = SchedulingDayPayloadKind.empty
        resolved_policy = None
    else:
        if policy_id is None:
            raise ApiError(422, "policy_id is required", "RULE_POLICY_REQUIRED")
        standing._verify_owned_policy(db, user, policy_id)
        payload_kind = SchedulingDayPayloadKind.policy
        resolved_policy = policy_id
    replaces, survives = _precedence_from_body(body)
    new_id = uuid4()
    _assert_overlap_ok(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.replace_named_scoped,
        selector=selector,
        policy_id=resolved_policy,
        named_target=clean_target,
        named_kind=target_rule_kind,
        replaces_op_ids=replaces,
        addition_survives=survives,
        new_id=new_id,
    )
    row = SchedulingDayScopedOp(
        id=new_id,
        owner_id=user.id,
        scope_kind=standing._scope_enum(scope),
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.replace_named_scoped,
        payload_kind=payload_kind,
        policy_id=resolved_policy,
        target_rule_name=clean_target,
        target_rule_kind=SchedulingRuleKind(target_rule_kind),
        replacement_name=clean_replacement,
        replacement_policy_id=resolved_policy,
        replacement_empty_set=empty_set,
        expires_at=expires_at,
        replaces_op_ids=replaces,
        addition_survives=survives,
        assignment_id=assignment.id,
    )
    _apply_selector_columns(row, selector)
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "op": row,
        "op_out": _op_out(row),
    }


def rule_waive_named_scoped(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    target_rule_name: str,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``rule.waive_named_scoped`` — named Must waiver with selector."""
    _entity, selector, expires_at, settings = _begin_scoped_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=expected_revision,
        raw_body=raw_body,
    )
    _e, assignment = standing._require_new_rule_family(db, user, scope, scope_id)
    del _e
    body = raw_body or {}
    clean_target = target_rule_name.strip()
    if not clean_target:
        raise ApiError(422, "target_rule_name is required", "RULE_NAME_REQUIRED")
    replaces, survives = _precedence_from_body(body)
    new_id = uuid4()
    _assert_overlap_ok(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.waive_named_scoped,
        selector=selector,
        policy_id=None,
        named_target=clean_target,
        named_kind="must",
        replaces_op_ids=replaces,
        addition_survives=survives,
        new_id=new_id,
    )
    row = SchedulingDayScopedOp(
        id=new_id,
        owner_id=user.id,
        scope_kind=standing._scope_enum(scope),
        scope_id=scope_id,
        op_kind=SchedulingDayScopedOpKind.waive_named_scoped,
        payload_kind=SchedulingDayPayloadKind.none,
        target_rule_name=clean_target,
        target_rule_kind=SchedulingRuleKind.must,
        expires_at=expires_at,
        replaces_op_ids=replaces,
        addition_survives=survives,
        assignment_id=assignment.id,
    )
    _apply_selector_columns(row, selector)
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "op": row,
        "op_out": _op_out(row),
    }


def rule_remove_named_scoped(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    op_id: UUID,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``rule.remove_named_scoped`` — targeted removal by stable identity.

    Also removes day Change / Only-allow / clear / family-replace scoped rows
    identified by ``op_id`` (stable identity removal for any day-scoped op).
    """
    standing.reject_deferred_exception_forms(raw_body, allow_v4b_temporal=True)
    standing._get_scope_entity(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    row = (
        db.query(SchedulingDayScopedOp)
        .filter(
            SchedulingDayScopedOp.owner_id == user.id,
            SchedulingDayScopedOp.scope_kind == standing._scope_enum(scope),
            SchedulingDayScopedOp.scope_id == scope_id,
            SchedulingDayScopedOp.id == op_id,
        )
        .one_or_none()
    )
    if row is None:
        raise ApiError(
            404,
            f"No day-scoped op '{op_id}' at this scope",
            OP_NOT_FOUND_CODE,
            scope=scope,
            scope_id=str(scope_id),
            op_id=str(op_id),
        )
    removed = _op_out(row)
    db.delete(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "scheduling_revision": revision,
        "removed_op_id": op_id,
        "removed": removed,
    }


def list_day_scoped_ops(
    db: Session, user: User, *, scope: ScopeKind, scope_id: UUID
) -> list[dict[str, Any]]:
    standing._get_scope_entity(db, user, scope, scope_id)
    return [
        _op_out(row)
        for row in _load_ops_at_scope(
            db, owner_id=user.id, scope=scope, scope_id=scope_id
        )
    ]
