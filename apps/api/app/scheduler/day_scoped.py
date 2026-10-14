"""Day-scoped Change / Only-allow / named / family ops (S2-V4b).

Standing ``resolve_effective_composition`` stays date-blind. This module folds
authorized declarations into the windows ``composition_search_windows`` already
returns, keyed by that function's ``day`` argument. Legacy placements never
call it.

Jules owns writers and the table. Until ``load_day_scoped_declarations`` exists
on ``app.services.scheduling_assignments``, ``load_day_scoped_declarations``
here returns an empty map. Resolution accepts :class:`DayScopedDeclaration`
either way.

Clocks (discovery §2.1):

- **Occurrence** — the start day in the schedule timezone owns the window,
  overnight tail included.
- **Lifetime** — Change keeps the selected occurrence in full. Only an
  explicit instant expiry clips a tail. Only-allow's end is independent:
  a date-range or one-date without an instant expiry runs until the start
  of the civil day after the last selected date, and that bound does not
  clip a Change tail.
- **Evaluation** — each occurrence start in the collected horizon is decided
  on its own. A horizon may contain instants before, inside, and after a
  lifetime.

Civil labels (dates, weekday masks, recurring wall clocks) are re-read in the
schedule timezone passed in. Fixed instants (``expires_at``, one-time
boundaries) stay the chosen UTC instant. A combined declaration that does not
validate is not applied and is not rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from app.scheduler.availability_materializer import (
    as_policy_window,
    occurrence_span,
    resolve_recurring_wall,
)
from app.scheduler.composition import (
    RANK_ELIGIBLE,
    RANK_PREFER,
    AssignmentFamily,
    CompositionInput,
    EffectiveComposition,
    EffectiveRule,
    ExceptionOp,
    MayMode,
    NamedRule,
    RuleRole,
    ScopeLayer,
    StandingException,
    make_window,
    resolve_effective_composition,
)

AUTHORIZED_OPERATIONS: frozenset[str] = frozenset(
    {
        "day.change_selected",
        "day.only_allow",
        "assignment.family_replace_scoped",
        "assignment.clear_scoped",
        "assignment.revert_scoped",
        "rule.add_scoped",
        "rule.replace_named_scoped",
        "rule.waive_named_scoped",
        "rule.remove_named_scoped",
    }
)


class SelectorKind(str, Enum):
    ONE_DATE = "one_date"
    WEEKDAY = "weekday"
    DATE_RANGE = "date_range"


class DayScopedOp(str, Enum):
    CHANGE_SELECTED = "day.change_selected"
    ONLY_ALLOW = "day.only_allow"
    FAMILY_REPLACE_SCOPED = "assignment.family_replace_scoped"
    CLEAR_SCOPED = "assignment.clear_scoped"
    REVERT_SCOPED = "assignment.revert_scoped"
    ADD_SCOPED = "rule.add_scoped"
    REPLACE_NAMED_SCOPED = "rule.replace_named_scoped"
    WAIVE_NAMED_SCOPED = "rule.waive_named_scoped"
    REMOVE_NAMED_SCOPED = "rule.remove_named_scoped"


_LAYER_OPS = frozenset(
    {
        DayScopedOp.CLEAR_SCOPED,
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        DayScopedOp.REVERT_SCOPED,
    }
)
_NAMED_OPS = frozenset(
    {
        DayScopedOp.ADD_SCOPED,
        DayScopedOp.REPLACE_NAMED_SCOPED,
        DayScopedOp.WAIVE_NAMED_SCOPED,
    }
)


@dataclass(frozen=True)
class CivilSelector:
    """Schedule-timezone labels. Not a stored IANA zone."""

    kind: SelectorKind
    on_date: date | None = None
    weekdays: tuple[int, ...] = ()
    range_start: date | None = None
    range_end: date | None = None

    def selected(self, start: date) -> bool:
        if self.kind == SelectorKind.ONE_DATE:
            return self.on_date is not None and start == self.on_date
        if self.kind == SelectorKind.WEEKDAY:
            return start.weekday() in self.weekdays
        if self.range_start is None or self.range_end is None:
            return False
        return self.range_start <= start <= self.range_end


@dataclass(frozen=True)
class DayScopedDeclaration:
    """One authorized scoped op. Storage spelling is Jules's; this is the resolver contract."""

    declaration_id: str
    operation: DayScopedOp
    scope: str
    scope_id: str
    selector: CivilSelector
    windows: tuple[Any, ...] = ()
    empty_set: bool = False
    expires_at: datetime | None = None
    one_time_start: datetime | None = None
    one_time_end: datetime | None = None
    target_rule_id: str | None = None
    role: str | None = None
    output_rule_id: str | None = None
    replaces_id: str | None = None
    replaces_ids: tuple[str, ...] = ()
    addition_survives: bool | None = None
    reverts_id: str | None = None
    provenance: str = "day_scoped"
    replacement_family: str | None = None
    replacement_layer: ScopeLayer | None = None
    prior_layer: ScopeLayer | None = None
    expiry_rejected: str | None = None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _parse_instant(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value)
    if "T" not in text and " " not in text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return _as_utc(parsed)


def _parse_weekdays(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, int) and not isinstance(value, bool):
        return (int(value),)
    names = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tuesday": 1,
        "wed": 2,
        "wednesday": 2,
        "thu": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }
    out: list[int] = []
    items = value if isinstance(value, (list, tuple)) else [value]
    for item in items:
        if isinstance(item, int) and not isinstance(item, bool):
            out.append(int(item))
            continue
        key = str(item).strip().lower()
        if key in names:
            out.append(names[key])
        else:
            out.append(int(key))
    return tuple(sorted(set(out)))


def _window_tuple(payload: Mapping[str, Any]) -> tuple[Any, ...]:
    rows = payload.get("windows") or []
    built = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        start = row.get("start_time")
        if isinstance(start, str):
            start = time.fromisoformat(start)
        built.append(
            make_window(
                int(row["weekday"]),
                start,
                int(row["duration_minutes"]),
                sort_order=int(row.get("sort_order") or index),
            )
        )
    return tuple(built)


def _selector_from_mapping(payload: Mapping[str, Any]) -> CivilSelector:
    explicit = payload.get("selector")
    if isinstance(explicit, Mapping) and explicit.get("kind"):
        kind = SelectorKind(str(explicit["kind"]))
        return CivilSelector(
            kind=kind,
            on_date=_parse_date(explicit.get("on_date")),
            weekdays=_parse_weekdays(explicit.get("weekdays")),
            range_start=_parse_date(explicit.get("range_start")),
            range_end=_parse_date(explicit.get("range_end")),
        )
    date_range = payload.get("date_range")
    if isinstance(date_range, Mapping):
        return CivilSelector(
            kind=SelectorKind.DATE_RANGE,
            range_start=_parse_date(date_range.get("start") or date_range.get("start_date")),
            range_end=_parse_date(date_range.get("end") or date_range.get("end_date")),
        )
    one = (
        payload.get("on_date")
        or payload.get("on")
        or payload.get("applies_on")
        or payload.get("local_date")
    )
    weekdays = payload.get("weekdays")
    if weekdays is None:
        weekdays = payload.get("weekday_standing")
    if weekdays is None:
        weekdays = payload.get("days_of_week")
    if weekdays is None and payload.get("weekday") is not None and not isinstance(
        payload.get("windows"), list
    ):
        weekdays = payload.get("weekday")
    start = payload.get("local_start_date") or payload.get("start_date")
    end = payload.get("local_end_date") or payload.get("end_date")
    if one and not start and not end and not weekdays:
        return CivilSelector(kind=SelectorKind.ONE_DATE, on_date=_parse_date(one))
    if weekdays and not start and not end and not one:
        return CivilSelector(kind=SelectorKind.WEEKDAY, weekdays=_parse_weekdays(weekdays))
    if start or end:
        return CivilSelector(
            kind=SelectorKind.DATE_RANGE,
            range_start=_parse_date(start or one),
            range_end=_parse_date(end or start or one),
        )
    if one:
        return CivilSelector(kind=SelectorKind.ONE_DATE, on_date=_parse_date(one))
    raise ValueError("day-scoped declaration requires a selector")


def declaration_from_mapping(
    payload: Mapping[str, Any],
    *,
    scope: str,
    scope_id: str,
) -> DayScopedDeclaration:
    """Build a declaration from an authorized mapping. Does not rewrite instants or labels."""
    operation = DayScopedOp(str(payload["operation"]))
    selector = _selector_from_mapping(payload)
    expiry_rejected = None
    expires_at = None
    for key in ("expires_at", "expiry", "expires_on"):
        if payload.get(key) in (None, ""):
            continue
        raw = payload.get(key)
        parsed = _parse_instant(raw)
        if parsed is None:
            expiry_rejected = "expiry_not_instant"
            break
        expires_at = parsed
        break
    declaration_id = str(
        payload.get("id")
        or payload.get("declaration_id")
        or f"{operation.value}:{scope}:{scope_id}:{selector.kind.value}"
    )
    return DayScopedDeclaration(
        declaration_id=declaration_id,
        operation=operation,
        scope=str(payload.get("scope") or scope),
        scope_id=str(payload.get("scope_id") or scope_id),
        selector=selector,
        windows=_window_tuple(payload),
        empty_set=bool(payload.get("empty_set")),
        expires_at=expires_at,
        one_time_start=_parse_instant(payload.get("one_time_start")),
        one_time_end=_parse_instant(payload.get("one_time_end")),
        target_rule_id=(
            str(payload["target_rule_id"])
            if payload.get("target_rule_id")
            else (
                str(payload["target_rule_name"])
                if payload.get("target_rule_name")
                else None
            )
        ),
        role=str(payload["role"]) if payload.get("role") else None,
        output_rule_id=(
            str(payload["output_rule_id"]) if payload.get("output_rule_id") else None
        ),
        replaces_id=(
            str(payload["replaces_id"]) if payload.get("replaces_id") else None
        ),
        replaces_ids=tuple(
            str(item)
            for item in (payload.get("replaces_op_ids") or payload.get("replaces_ids") or [])
        )
        or (
            (str(payload["replaces_id"]),)
            if payload.get("replaces_id")
            else ()
        ),
        addition_survives=(
            payload.get("addition_survives")
            if payload.get("addition_survives") is None
            or isinstance(payload.get("addition_survives"), bool)
            else bool(payload.get("addition_survives"))
        ),
        reverts_id=str(payload["reverts_id"]) if payload.get("reverts_id") else None,
        provenance=str(payload.get("provenance") or "day_scoped"),
        expiry_rejected=expiry_rejected,
    )


def declaration_problem(decl: DayScopedDeclaration, tz: ZoneInfo) -> str | None:
    """Combined civil + fixed-instant check. Returns a reason and changes nothing."""
    if decl.expiry_rejected:
        return decl.expiry_rejected
    if (
        decl.expires_at is not None
        and decl.one_time_end is not None
        and _as_utc(decl.expires_at) != _as_utc(decl.one_time_end)
    ):
        return "contradictory_instant_ends"
    if (
        decl.one_time_start is not None
        and decl.one_time_end is not None
        and _as_utc(decl.one_time_end) <= _as_utc(decl.one_time_start)
    ):
        return "invalid_one_time_bounds"
    if decl.expires_at is None:
        return None
    first = decl.selector.on_date or decl.selector.range_start
    if first is None and decl.selector.kind == SelectorKind.WEEKDAY:
        return None
    if first is None:
        return None
    civil_start = resolve_recurring_wall(first, time.min, tz)
    if _as_utc(decl.expires_at) <= civil_start:
        return "expiry_before_lifetime_start"
    return None


def _civil_day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = resolve_recurring_wall(day, time.min, tz)
    end = resolve_recurring_wall(day + timedelta(days=1), time.min, tz)
    return start, end


def only_allow_bounds(
    decl: DayScopedDeclaration, tz: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """Only-allow lifetime. Explicit ``expires_at`` wins over the civil midnight end."""
    end = _as_utc(decl.expires_at) if decl.expires_at is not None else None
    start: datetime | None = None
    if decl.selector.kind in (SelectorKind.ONE_DATE, SelectorKind.DATE_RANGE):
        first = decl.selector.on_date or decl.selector.range_start
        last = decl.selector.on_date or decl.selector.range_end
        if first is not None:
            start = resolve_recurring_wall(first, time.min, tz)
        if end is None and last is not None:
            end = resolve_recurring_wall(last + timedelta(days=1), time.min, tz)
    return start, end


def lifetime_end_instant(decl: DayScopedDeclaration, tz: ZoneInfo) -> datetime | None:
    """Exclusive end used for apply-time expiry crossing. Open lifetimes return None."""
    if decl.expires_at is not None:
        return _as_utc(decl.expires_at)
    if decl.operation == DayScopedOp.ONLY_ALLOW:
        _start, end = only_allow_bounds(decl, tz)
        return end
    return None


def occurrence_applies(decl: DayScopedDeclaration, start: date, tz: ZoneInfo) -> bool:
    if declaration_problem(decl, tz):
        return False
    if not decl.selector.selected(start):
        return False
    if decl.expires_at is None:
        return True
    # The occurrence applies when it starts before the instant. The tail is
    # clipped later; the last selected date is not this end.
    start_instant = resolve_recurring_wall(start, time.min, tz)
    return start_instant < _as_utc(decl.expires_at)


def _target_ids(item: DayScopedDeclaration) -> tuple[str, ...]:
    if item.replaces_ids:
        return item.replaces_ids
    if item.replaces_id:
        return (item.replaces_id,)
    return ()


def _cyclic_ids(decls: Sequence[DayScopedDeclaration]) -> set[str]:
    graph: dict[str, list[str]] = {item.declaration_id: [] for item in decls}
    known = set(graph)
    for item in decls:
        for target in _target_ids(item):
            if target in known:
                graph[item.declaration_id].append(target)
    cyclic: set[str] = set()

    def visit(node: str, stack: set[str]) -> None:
        if node in stack:
            cyclic.update(stack)
            return
        stack.add(node)
        for nxt in graph.get(node, []):
            visit(nxt, stack)
        stack.discard(node)

    for node in list(graph):
        visit(node, set())
    return cyclic


def _winners(decls: Sequence[DayScopedDeclaration]) -> list[DayScopedDeclaration] | None:
    """Stable precedence. None means unresolved overlap (do not invent a winner)."""
    if len(decls) <= 1:
        return list(decls)
    cyclic = _cyclic_ids(decls)
    if cyclic:
        return None
    by_id = {item.declaration_id: item for item in decls}
    replaced: set[str] = set()
    for item in decls:
        for target in _target_ids(item):
            if target in by_id:
                replaced.add(target)
    if not replaced and len(decls) > 1:
        return None
    winners = [item for item in decls if item.declaration_id not in replaced]
    if len(winners) != 1 and len(decls) > 1:
        return None
    return winners


def _same_scope(layer: ScopeLayer, decl: DayScopedDeclaration) -> bool:
    return layer.scope == decl.scope and layer.scope_id == decl.scope_id


def _scope_nearness(scope: str) -> int:
    return {"task": 0, "project": 1, "epic": 2}.get(scope, 9)


def _hours_layer(scope: str, scope_id: str, windows: Sequence[Any], *, rule_id: str) -> ScopeLayer:
    """Explicit May from resolved hours. Empty stays empty — no General borrow."""
    if not windows:
        return ScopeLayer(scope=scope, scope_id=scope_id, may_mode=MayMode.EXPLICIT_EMPTY)
    named = NamedRule(
        rule_id=rule_id,
        role=RuleRole.MAY,
        windows=tuple(windows),
        scope=scope,
        scope_id=scope_id,
    )
    return ScopeLayer(
        scope=scope,
        scope_id=scope_id,
        may_mode=MayMode.PRESENT,
        may_rules=(named,),
    )


def _apply_layer_edits(
    layers: Sequence[ScopeLayer],
    edits: Sequence[DayScopedDeclaration],
) -> list[ScopeLayer]:
    """Overlay clear / family replace / revert onto the standing chain.

    ``none`` suppresses that scope. ``new_rule`` replaces or inserts it.
    ``legacy`` wins exclusively when it is the nearest participating scope,
    the same way an unconverted map stops the standing walk. A scope that
    had no standing layer still receives an inserted replacement.
    """
    keyed: dict[tuple[str, str], ScopeLayer] = {
        (layer.scope, layer.scope_id): layer for layer in layers
    }
    family: dict[tuple[str, str], str] = {key: "new_rule" for key in keyed}
    for edit in edits:
        key = (edit.scope, edit.scope_id)
        if edit.operation == DayScopedOp.CLEAR_SCOPED:
            keyed.pop(key, None)
            family[key] = "none"
            continue
        if edit.operation == DayScopedOp.REVERT_SCOPED and edit.prior_layer is not None:
            keyed[key] = edit.prior_layer
            family[key] = "new_rule"
            continue
        if edit.operation != DayScopedOp.FAMILY_REPLACE_SCOPED:
            continue
        target = edit.replacement_family
        if target is None and edit.replacement_layer is not None:
            target = "new_rule"
        if target == "none":
            keyed.pop(key, None)
            family[key] = "none"
        elif target == "legacy":
            layer = edit.replacement_layer or _hours_layer(
                edit.scope,
                edit.scope_id,
                edit.windows,
                rule_id=edit.output_rule_id or edit.declaration_id,
            )
            keyed[key] = layer
            family[key] = "legacy"
        elif target == "new_rule" and edit.replacement_layer is not None:
            keyed[key] = edit.replacement_layer
            family[key] = "new_rule"

    participating: list[tuple[int, tuple[str, str], str]] = []
    seen: set[tuple[str, str]] = set()
    for key, fam in family.items():
        seen.add(key)
        if fam != "none":
            participating.append((_scope_nearness(key[0]), key, fam))
    for key in keyed:
        if key not in seen and family.get(key, "new_rule") != "none":
            participating.append((_scope_nearness(key[0]), key, "new_rule"))
    if not participating:
        return []
    participating.sort(key=lambda item: item[0])
    win_rank, win_key, win_fam = participating[0]
    if win_fam == "legacy":
        layer = keyed.get(win_key)
        return [layer] if layer is not None else []

    ordered = sorted(keyed, key=lambda key: _scope_nearness(key[0]))
    kept: list[ScopeLayer] = []
    started = False
    for key in ordered:
        if _scope_nearness(key[0]) < win_rank:
            continue
        fam = family.get(key, "new_rule")
        if not started:
            if key != win_key:
                continue
            started = True
        if fam == "legacy":
            break
        if fam == "none":
            continue
        layer = keyed.get(key)
        if layer is not None:
            kept.append(layer)
    return kept


def _as_standing(decl: DayScopedDeclaration) -> StandingException:
    if decl.operation == DayScopedOp.WAIVE_NAMED_SCOPED:
        return StandingException(
            operation=ExceptionOp.WAIVE_NAMED,
            scope=decl.scope,
            scope_id=decl.scope_id,
            target_rule_id=decl.target_rule_id,
        )
    role = RuleRole(decl.role or RuleRole.MAY.value)
    named = NamedRule(
        rule_id=decl.output_rule_id or decl.target_rule_id or decl.declaration_id,
        role=role,
        windows=tuple(decl.windows),
        scope=decl.scope,
        scope_id=decl.scope_id,
    )
    operation = (
        ExceptionOp.ADD
        if decl.operation == DayScopedOp.ADD_SCOPED
        else ExceptionOp.REPLACE_NAMED
    )
    return StandingException(
        operation=operation,
        scope=decl.scope,
        scope_id=decl.scope_id,
        target_rule_id=decl.target_rule_id,
        rule=named,
    )


def _reverted_ids(decls: Sequence[Any]) -> set[str]:
    return {
        item.reverts_id
        for item in decls
        if isinstance(item, DayScopedDeclaration) and item.reverts_id
    }


def composition_for_occurrence(
    effective: EffectiveComposition,
    start: date,
    tz: ZoneInfo,
) -> EffectiveComposition:
    """Standing stack, with scoped clear / replace / named ops for ``start`` only."""
    if not effective.day_scoped:
        return effective
    usable = [
        item
        for item in effective.day_scoped
        if isinstance(item, DayScopedDeclaration)
        and declaration_problem(item, tz) is None
        and item.operation != DayScopedOp.REMOVE_NAMED_SCOPED
        and item.declaration_id not in _reverted_ids(effective.day_scoped)
    ]
    active = [item for item in usable if occurrence_applies(item, start, tz)]
    if not active:
        return effective
    layer_edits = [item for item in active if item.operation in _LAYER_OPS]
    named = [item for item in active if item.operation in _NAMED_OPS]
    changes = [item for item in active if item.operation == DayScopedOp.CHANGE_SELECTED]
    change_winners = _winners(changes)
    if change_winners is None:
        changes = []
    else:
        changes = change_winners
    may_adds = [
        item
        for item in named
        if item.operation == DayScopedOp.ADD_SCOPED and (item.role or "may") == "may"
    ]
    if changes and may_adds and any(item.addition_survives is None for item in may_adds):
        named = [item for item in named if item not in may_adds]
        changes = []
        surviving_adds: list[DayScopedDeclaration] = []
    else:
        surviving_adds = [item for item in may_adds if item.addition_survives]
        if changes:
            named = [
                item
                for item in named
                if not (
                    item.operation == DayScopedOp.ADD_SCOPED
                    and (item.role or "may") == "may"
                    and item.addition_survives is False
                )
            ]
    if not layer_edits and not named and not changes:
        return effective
    base = effective
    if layer_edits or named:
        base = _reresolve(effective, layer_edits, named)
    if changes:
        base = _apply_changes(base, changes, surviving_adds)
    return base


def _reresolve(
    effective: EffectiveComposition,
    edits: Sequence[DayScopedDeclaration],
    named: Sequence[DayScopedDeclaration],
) -> EffectiveComposition:
    source = effective.source
    if source is not None and source.family == AssignmentFamily.CONFLICT:
        return effective
    layers = _apply_layer_edits(list(source.layers) if source is not None else [], edits)
    if named:
        layers.append(
            ScopeLayer(
                scope=named[0].scope,
                scope_id=named[0].scope_id,
                exceptions=tuple(_as_standing(item) for item in named),
            )
        )
    resolved = resolve_effective_composition(
        CompositionInput(family=AssignmentFamily.NEW_RULE, layers=tuple(layers))
    )
    return replace(
        resolved,
        day_scoped=effective.day_scoped,
        source=source,
        deferred_rejected=effective.deferred_rejected,
    )


def _apply_changes(
    base: EffectiveComposition,
    changes: Sequence[DayScopedDeclaration],
    surviving_adds: Sequence[DayScopedDeclaration],
) -> EffectiveComposition:
    change = changes[0]
    if change.empty_set or not change.windows and change.one_time_start is None:
        return replace(base, may_source="explicit_empty", may_rules=())
    windows = tuple(change.windows)
    for extra in surviving_adds:
        windows = windows + tuple(extra.windows)
    rule = EffectiveRule(
        rule_id=change.output_rule_id or change.declaration_id,
        role=RuleRole.MAY,
        windows=windows,
        scope=change.scope,
        scope_id=change.scope_id,
        origin="day_change",
    )
    return replace(base, may_source="explicit", may_rules=(rule,))


def _spans_starting(windows: Sequence[Any], start: date, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
    spans: list[tuple[datetime, datetime]] = []
    for window in windows:
        policy = as_policy_window(window)
        if int(policy.weekday) != start.weekday():
            continue
        full = occurrence_span(policy, start, tz)
        if full is not None:
            spans.append((full.start, full.end))
    return _merge(spans)


def _merge(spans: Sequence[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda item: (item[0], item[1]))
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _intersect(
    left: Sequence[tuple[datetime, datetime]],
    right: Sequence[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not left or not right:
        return []
    out: list[tuple[datetime, datetime]] = []
    i = 0
    j = 0
    left_l = list(left)
    right_l = list(right)
    while i < len(left_l) and j < len(right_l):
        start = max(left_l[i][0], right_l[j][0])
        end = min(left_l[i][1], right_l[j][1])
        if start < end:
            out.append((start, end))
        if left_l[i][1] <= right_l[j][1]:
            i += 1
        else:
            j += 1
    return out


def _clip_end(
    spans: Sequence[tuple[datetime, datetime]],
    end_instant: datetime,
) -> list[tuple[datetime, datetime]]:
    end_instant = _as_utc(end_instant)
    out: list[tuple[datetime, datetime]] = []
    for start, end in spans:
        if end_instant <= start:
            continue
        clipped = min(end, end_instant)
        if start < clipped:
            out.append((start, clipped))
    return out


def _slice_day(
    spans: Sequence[tuple[datetime, datetime]],
    day: date,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    day_start, day_end = _civil_day_bounds(day, tz)
    out: list[tuple[datetime, datetime]] = []
    for start, end in spans:
        left = max(start, day_start)
        right = min(end, day_end)
        if left < right:
            out.append((left, right))
    return out


def _one_time_span(decl: DayScopedDeclaration) -> tuple[datetime, datetime] | None:
    if decl.one_time_start is None or decl.one_time_end is None:
        return None
    return _as_utc(decl.one_time_start), _as_utc(decl.one_time_end)


def _may_spans(comp: EffectiveComposition, start: date, tz: ZoneInfo, general: Sequence[Any] | None, changes: Sequence[DayScopedDeclaration]) -> list[tuple[datetime, datetime]]:
    fixed = None
    for change in changes:
        fixed = _one_time_span(change)
        if fixed is not None:
            break
    if fixed is not None:
        spans = [fixed]
    elif comp.may_source == "general":
        spans = _spans_starting(list(general or []), start, tz)
    else:
        spans = []
        for rule in comp.may_rules:
            spans.extend(_spans_starting(rule.windows, start, tz))
    spans = _merge(spans)
    for change in changes:
        if change.expires_at is not None:
            spans = _clip_end(spans, change.expires_at)
    return spans


def _clip_allowed_to_selected_days(
    spans: Sequence[tuple[datetime, datetime]],
    decl: DayScopedDeclaration,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    """Only-allow is by instant. An overnight tail on an unselected day is not allowed."""
    out: list[tuple[datetime, datetime]] = []
    for start, end in spans:
        day = start.astimezone(tz).date() - timedelta(days=1)
        last = end.astimezone(tz).date()
        while day <= last:
            if decl.selector.selected(day):
                day_start, day_end = _civil_day_bounds(day, tz)
                left = max(start, day_start)
                right = min(end, day_end)
                if left < right:
                    out.append((left, right))
            day += timedelta(days=1)
    return _merge(out)


def _allowed_spans(
    decl: DayScopedDeclaration,
    left: datetime,
    right: datetime,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    if decl.empty_set:
        return []
    fixed = _one_time_span(decl)
    if fixed is not None:
        return _intersect([fixed], [(left, right)])
    if decl.windows:
        pieces: list[tuple[datetime, datetime]] = []
        day = left.astimezone(tz).date() - timedelta(days=1)
        last = right.astimezone(tz).date()
        while day <= last:
            if decl.selector.selected(day):
                pieces.extend(_spans_starting(decl.windows, day, tz))
            day += timedelta(days=1)
        clipped = _clip_allowed_to_selected_days(_merge(pieces), decl, tz)
        return _intersect(clipped, [(left, right)])
    pieces = []
    day = left.astimezone(tz).date() - timedelta(days=1)
    last = right.astimezone(tz).date()
    while day <= last:
        if decl.selector.selected(day):
            pieces.append(_civil_day_bounds(day, tz))
        day += timedelta(days=1)
    return _intersect(_merge(pieces), [(left, right)])


def _only_allow_active(decls: Sequence[DayScopedDeclaration], instant: datetime, tz: ZoneInfo) -> list[DayScopedDeclaration]:
    active = []
    for decl in decls:
        if decl.operation != DayScopedOp.ONLY_ALLOW:
            continue
        if declaration_problem(decl, tz):
            continue
        start, end = only_allow_bounds(decl, tz)
        if start is not None and instant < start:
            continue
        if end is not None and instant >= end:
            continue
        if decl.selector.kind == SelectorKind.WEEKDAY and end is None and start is None:
            active.append(decl)
            continue
        active.append(decl)
    return active


def apply_only_allow(
    spans: Sequence[tuple[datetime, datetime]],
    decls: Sequence[DayScopedDeclaration],
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    onlys = [
        item
        for item in decls
        if isinstance(item, DayScopedDeclaration) and item.operation == DayScopedOp.ONLY_ALLOW
    ]
    if not onlys:
        return list(spans)
    out: list[tuple[datetime, datetime]] = []
    for start, end in spans:
        out.extend(_filter_only_allow_span(start, end, onlys, tz))
    return _merge(out)


def _filter_only_allow_span(
    start: datetime,
    end: datetime,
    onlys: Sequence[DayScopedDeclaration],
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    cuts = {start, end}
    for decl in onlys:
        life_start, life_end = only_allow_bounds(decl, tz)
        if life_start is not None and start < life_start < end:
            cuts.add(life_start)
        if life_end is not None and start < life_end < end:
            cuts.add(life_end)
        for allowed_start, allowed_end in _allowed_spans(decl, start, end, tz):
            if start < allowed_start < end:
                cuts.add(allowed_start)
            if start < allowed_end < end:
                cuts.add(allowed_end)
    ordered = sorted(cuts)
    pieces: list[tuple[datetime, datetime]] = []
    for left, right in zip(ordered, ordered[1:]):
        if left >= right:
            continue
        active = _only_allow_active(onlys, left, tz)
        if not active:
            pieces.append((left, right))
            continue
        winners = _winners(active)
        if winners is None or not winners:
            pieces.append((left, right))
            continue
        winner = winners[0]
        if winner.empty_set:
            continue
        if any(a <= left and right <= b for a, b in _allowed_spans(winner, left, right, tz)):
            pieces.append((left, right))
    return pieces


def _declaration_touches(decl: DayScopedDeclaration, day: date, tz: ZoneInfo) -> bool:
    if not isinstance(decl, DayScopedDeclaration):
        return False
    if decl.operation == DayScopedOp.REMOVE_NAMED_SCOPED:
        return False
    if declaration_problem(decl, tz):
        return False
    if decl.operation == DayScopedOp.ONLY_ALLOW:
        life_start, life_end = only_allow_bounds(decl, tz)
        day_start, day_end = _civil_day_bounds(day, tz)
        if life_start is None and life_end is None:
            return True
        if life_start is None:
            life_start = datetime.min.replace(tzinfo=timezone.utc)
        if life_end is None:
            life_end = datetime.max.replace(tzinfo=timezone.utc)
        return day_start < life_end and life_start < day_end
    for back in range(8):
        start = day - timedelta(days=back)
        if occurrence_applies(decl, start, tz):
            return True
    return False


def folded_search_windows(
    day: date,
    tz: ZoneInfo,
    composition: EffectiveComposition,
    general_windows: Sequence[Any] | None,
) -> list[tuple[datetime, datetime, str]] | None:
    """Per-day fold. None means the standing search is already the right answer."""
    decls = [
        item
        for item in composition.day_scoped
        if isinstance(item, DayScopedDeclaration) and _declaration_touches(item, day, tz)
    ]
    if not decls:
        return None
    eligible_parts: list[tuple[datetime, datetime]] = []
    prefer_parts: list[tuple[datetime, datetime]] = []
    for back in range(8):
        start = day - timedelta(days=back)
        comp = composition_for_occurrence(composition, start, tz)
        if not comp.supplies_eligibility():
            continue
        changes = [
            item
            for item in decls
            if item.operation == DayScopedOp.CHANGE_SELECTED and occurrence_applies(item, start, tz)
        ]
        change_winners = _winners(changes)
        changes = [] if change_winners is None else change_winners
        if comp.must_blocks_all or comp.may_source == "explicit_empty":
            may_spans: list[tuple[datetime, datetime]] = []
        else:
            may_spans = _may_spans(comp, start, tz, general_windows, changes)
            for must in comp.must_rules:
                must_spans = _spans_starting(must.windows, start, tz)
                may_spans = _intersect(may_spans, _merge(must_spans))
                if not may_spans:
                    break
        may_spans = apply_only_allow(may_spans, composition.day_scoped, tz)
        if start != day:
            may_spans = _slice_day(may_spans, day, tz)
        prefer_spans: list[tuple[datetime, datetime]] = []
        for prefer in comp.prefer_rules:
            prefer_spans.extend(_spans_starting(prefer.windows, start, tz))
        preferred = _intersect(may_spans, _merge(prefer_spans)) if prefer_spans else []
        if start != day:
            preferred = _slice_day(preferred, day, tz)
        eligible_parts.extend(may_spans)
        prefer_parts.extend(preferred)
    eligible = _merge(eligible_parts)
    preferred = _merge(prefer_parts)
    if not eligible and not preferred:
        return []
    ordered: list[tuple[datetime, datetime, str]] = [
        (start, end, RANK_PREFER) for start, end in preferred
    ]
    ordered.extend((start, end, RANK_ELIGIBLE) for start, end in eligible)
    return ordered


def _window_fingerprint(window: Any) -> dict[str, Any]:
    return {
        "weekday": int(window.weekday),
        "start_time": window.start_time.isoformat(),
        "duration_minutes": int(window.duration_minutes),
        "ends_next_day": bool(window.ends_next_day),
        "sort_order": int(window.sort_order),
    }


def _named_fingerprint(rules: Sequence[Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "rule_id": item.rule_id,
            "role": item.role.value if hasattr(item.role, "value") else str(item.role),
            "windows": [_window_fingerprint(window) for window in item.windows],
        }
        for item in rules
    ]
    rows.sort(key=lambda row: (row["role"], row["rule_id"]))
    return rows


def _layer_fingerprint(layer: ScopeLayer | None) -> dict[str, Any] | None:
    """Family payload the placer actually uses. Hours live here, not on the declaration."""
    if layer is None:
        return None
    return {
        "scope": layer.scope,
        "scope_id": layer.scope_id,
        "may_mode": layer.may_mode.value,
        "may_rules": _named_fingerprint(layer.may_rules),
        "must_rules": _named_fingerprint(layer.must_rules),
        "prefer_rules": _named_fingerprint(layer.prefer_rules),
    }


def day_scoped_fingerprint_rows(declarations: Sequence[Any]) -> list[dict[str, Any]]:
    """Compared composition keys. Civil labels and fixed instants both participate."""
    rows: list[dict[str, Any]] = []
    for item in declarations:
        if not isinstance(item, DayScopedDeclaration):
            continue
        selector = item.selector
        rows.append(
            {
                "id": item.declaration_id,
                "operation": item.operation.value,
                "scope": item.scope,
                "scope_id": item.scope_id,
                "selector": {
                    "kind": selector.kind.value,
                    "on_date": selector.on_date.isoformat() if selector.on_date else None,
                    "weekdays": list(selector.weekdays),
                    "range_start": selector.range_start.isoformat() if selector.range_start else None,
                    "range_end": selector.range_end.isoformat() if selector.range_end else None,
                },
                "windows": [_window_fingerprint(window) for window in item.windows],
                "empty_set": bool(item.empty_set),
                "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                "one_time_start": item.one_time_start.isoformat() if item.one_time_start else None,
                "one_time_end": item.one_time_end.isoformat() if item.one_time_end else None,
                "target_rule_id": item.target_rule_id,
                "output_rule_id": item.output_rule_id,
                "role": item.role,
                "replacement_family": item.replacement_family,
                "replacement_layer": _layer_fingerprint(item.replacement_layer),
                "prior_layer": _layer_fingerprint(item.prior_layer),
                "replaces_id": item.replaces_id,
                "replaces_ids": list(item.replaces_ids),
                "addition_survives": item.addition_survives,
                "reverts_id": item.reverts_id,
                "provenance": item.provenance,
            }
        )
    rows.sort(key=lambda row: (row["scope"], row["scope_id"], row["operation"], row["id"]))
    return rows


def _policy_windows(policy: Any) -> tuple[Any, ...]:
    if policy is None:
        return ()
    rows = sorted(policy.windows, key=lambda window: (window.weekday, window.sort_order))
    return tuple(
        make_window(
            int(row.weekday),
            row.start_time,
            int(row.duration_minutes),
            sort_order=int(row.sort_order),
        )
        for row in rows
    )


def _selector_from_row(row: Any) -> CivilSelector:
    kind = row.selector_kind.value if hasattr(row.selector_kind, "value") else str(row.selector_kind)
    if kind == "one_date":
        return CivilSelector(kind=SelectorKind.ONE_DATE, on_date=row.civil_on_date)
    if kind == "weekday_standing":
        return CivilSelector(
            kind=SelectorKind.WEEKDAY,
            weekdays=tuple(int(day) for day in (row.civil_weekdays or ())),
        )
    return CivilSelector(
        kind=SelectorKind.DATE_RANGE,
        range_start=row.civil_start_date,
        range_end=row.civil_end_date,
    )


def _windows_from_focus(focus: Any) -> tuple[Any, ...]:
    """Green and yellow bands as recurring May windows. Red does not grant time."""
    if focus is None:
        return ()
    built = []
    order = 0
    for band in list(getattr(focus, "bands", ()) or ()):
        tier = band.tier.value if hasattr(band.tier, "value") else str(band.tier)
        if tier not in ("green", "yellow"):
            continue
        start = band.start_time
        end = band.end_time
        duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
        if duration <= 0:
            continue
        mask = int(band.days_of_week)
        for weekday in range(7):
            if mask & (1 << weekday):
                built.append(make_window(weekday, start, duration, sort_order=order))
                order += 1
    return tuple(built)


def _focus_for_payload(payload: Mapping[str, Any], focus_windows: Mapping[Any, Any]) -> Any:
    raw_id = payload.get("preferred_time_window_id")
    if raw_id is None or not focus_windows:
        return None
    found = focus_windows.get(raw_id)
    if found is not None:
        return found
    if isinstance(raw_id, str):
        from uuid import UUID

        try:
            return focus_windows.get(UUID(raw_id))
        except ValueError:
            return None
    return None


def _layer_from_family_payload(
    payload: Mapping[str, Any] | None,
    *,
    scope: str,
    scope_id: str,
    policies: Mapping[Any, Any],
    focus_windows: Mapping[Any, Any] | None = None,
) -> ScopeLayer | None:
    if not payload:
        return None
    target = payload.get("target_family")
    if target == "none":
        return None
    if target == "legacy":
        windows = _windows_from_focus(_focus_for_payload(payload, focus_windows or {}))
        return _hours_layer(scope, scope_id, windows, rule_id="legacy-map")
    if target != "new_rule":
        return None
    may_rules: list[NamedRule] = []
    must_rules: list[NamedRule] = []
    prefer_rules: list[NamedRule] = []
    for row in payload.get("rules") or []:
        if not isinstance(row, Mapping):
            continue
        empty = bool(row.get("empty_set"))
        policy_key = row.get("policy_id")
        if isinstance(policy_key, str):
            from uuid import UUID

            try:
                policy_key = UUID(policy_key)
            except ValueError:
                policy_key = None
        windows = () if empty or policy_key is None else _policy_windows(policies.get(policy_key))
        named = NamedRule(
            rule_id=str(row.get("name") or row.get("rule_id") or "scoped"),
            role=RuleRole(str(row.get("kind") or row.get("role") or "may")),
            windows=windows,
            scope=scope,
            scope_id=scope_id,
        )
        role = named.role
        if role == RuleRole.MUST:
            must_rules.append(named)
        elif role == RuleRole.PREFER:
            prefer_rules.append(named)
        else:
            may_rules.append(named)
    presence = str(payload.get("may_presence") or "omit")
    if presence == "omit":
        may_mode = MayMode.ABSENT
        may_rules = []
    elif not may_rules or all(not item.windows for item in may_rules):
        may_mode = MayMode.EXPLICIT_EMPTY
        may_rules = []
    else:
        may_mode = MayMode.PRESENT
    return ScopeLayer(
        scope=scope,
        scope_id=scope_id,
        may_mode=may_mode,
        may_rules=tuple(may_rules),
        must_rules=tuple(must_rules),
        prefer_rules=tuple(prefer_rules),
    )


_STORED_OP = {
    "change_selected": DayScopedOp.CHANGE_SELECTED,
    "only_allow": DayScopedOp.ONLY_ALLOW,
    "family_replace_scoped": DayScopedOp.FAMILY_REPLACE_SCOPED,
    "clear_scoped": DayScopedOp.CLEAR_SCOPED,
    "add_scoped": DayScopedOp.ADD_SCOPED,
    "replace_named_scoped": DayScopedOp.REPLACE_NAMED_SCOPED,
    "waive_named_scoped": DayScopedOp.WAIVE_NAMED_SCOPED,
}


def declaration_from_row(
    row: Any,
    policies: Mapping[Any, Any] | None = None,
    focus_windows: Mapping[Any, Any] | None = None,
) -> DayScopedDeclaration:
    """Coerce one ``scheduling_day_scoped_ops`` row. Does not rewrite civil labels or ``expires_at``."""
    policies = policies or {}
    op_kind = row.op_kind.value if hasattr(row.op_kind, "value") else str(row.op_kind)
    operation = _STORED_OP[op_kind]
    scope = row.scope_kind.value if hasattr(row.scope_kind, "value") else str(row.scope_kind)
    scope_id = str(row.scope_id)
    payload_kind = (
        row.payload_kind.value if hasattr(row.payload_kind, "value") else str(row.payload_kind)
    )
    policy = policies.get(row.policy_id) if row.policy_id is not None else None
    replacement_policy = (
        policies.get(row.replacement_policy_id) if row.replacement_policy_id is not None else None
    )
    windows = _policy_windows(policy)
    empty_set = payload_kind == "empty" or bool(getattr(row, "replacement_empty_set", False))
    role = None
    if getattr(row, "rule_kind", None) is not None:
        role = row.rule_kind.value if hasattr(row.rule_kind, "value") else str(row.rule_kind)
    elif getattr(row, "target_rule_kind", None) is not None:
        role = (
            row.target_rule_kind.value
            if hasattr(row.target_rule_kind, "value")
            else str(row.target_rule_kind)
        )
    if operation == DayScopedOp.REPLACE_NAMED_SCOPED:
        windows = () if row.replacement_empty_set else _policy_windows(replacement_policy)
        empty_set = bool(row.replacement_empty_set)
    replaces = tuple(str(item) for item in (row.replaces_op_ids or []))
    family_payload = row.family_payload if isinstance(row.family_payload, Mapping) else None
    replacement_family = None
    if family_payload and family_payload.get("target_family"):
        replacement_family = str(family_payload.get("target_family"))
    return DayScopedDeclaration(
        declaration_id=str(row.id),
        operation=operation,
        scope=scope,
        scope_id=scope_id,
        selector=_selector_from_row(row),
        windows=windows,
        empty_set=empty_set and operation != DayScopedOp.CLEAR_SCOPED,
        expires_at=_as_utc(row.expires_at) if row.expires_at is not None else None,
        target_rule_id=row.target_rule_name,
        role=role,
        output_rule_id=row.replacement_name or row.rule_name,
        replaces_id=replaces[0] if replaces else None,
        replaces_ids=replaces,
        addition_survives=row.addition_survives,
        provenance="scheduling_day_scoped_ops",
        replacement_family=replacement_family,
        replacement_layer=_layer_from_family_payload(
            family_payload,
            scope=scope,
            scope_id=scope_id,
            policies=policies,
            focus_windows=focus_windows,
        ),
    )


def load_day_scoped_declarations(
    db: Any,
    owner_id: Any,
    tasks: Sequence[Any],
    projects: Mapping[Any, Any] | None = None,
    epics: Mapping[Any, Any] | None = None,
) -> dict[Any, tuple[DayScopedDeclaration, ...]]:
    """Load Jules's ``scheduling_day_scoped_ops`` rows for the tasks being resolved.

    Empty when the table is absent or there is no session. Does not write.
    """
    del epics
    if db is None or not tasks:
        return {}
    try:
        from sqlalchemy.orm import joinedload

        from app.models import AvailabilityPolicy, FocusWindow
        from app.models.scheduling_day_scoped import SchedulingDayScopedOp
    except ImportError:
        return {}
    try:
        policies = {
            row.id: row
            for row in (
                db.query(AvailabilityPolicy)
                .options(joinedload(AvailabilityPolicy.windows))
                .filter(AvailabilityPolicy.owner_id == owner_id)
                .all()
            )
        }
        focus_windows = {
            row.id: row
            for row in (
                db.query(FocusWindow)
                .options(joinedload(FocusWindow.bands))
                .filter(FocusWindow.owner_id == owner_id)
                .all()
            )
        }
        stored = (
            db.query(SchedulingDayScopedOp)
            .filter(SchedulingDayScopedOp.owner_id == owner_id)
            .all()
        )
    except Exception as exc:
        from sqlalchemy.exc import SQLAlchemyError

        if not isinstance(exc, SQLAlchemyError):
            raise
        return {}
    by_scope: dict[tuple[str, Any], list[Any]] = {}
    for row in stored:
        scope = row.scope_kind.value if hasattr(row.scope_kind, "value") else str(row.scope_kind)
        by_scope.setdefault((scope, row.scope_id), []).append(row)
    projects = projects or {}
    out: dict[Any, tuple[DayScopedDeclaration, ...]] = {}
    for task in tasks:
        rows: list[Any] = list(by_scope.get(("task", task.id), []))
        project = projects.get(getattr(task, "project_id", None))
        if project is not None:
            rows.extend(by_scope.get(("project", project.id), []))
            epic_id = getattr(project, "epic_id", None)
            if epic_id is not None:
                rows.extend(by_scope.get(("epic", epic_id), []))
        if rows:
            out[task.id] = tuple(
                declaration_from_row(row, policies, focus_windows) for row in rows
            )
    return out
