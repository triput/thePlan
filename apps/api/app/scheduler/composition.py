"""May / Must / Prefer composition for S2-V4.

The placer calls this only for an activated **new-rule** assignment. An
unconverted legacy map stays on map ∩ Working and never enters the stack.

Order (SPEC §4.2, discovery §5):

1. Walk epic → project → task. Apply standing named-rule additions,
   replacements, and waivers into the effective rule set. Authorized day-scoped
   ops are **not** applied here; ``composition_search_windows`` folds them per
   day before May union / Must intersect / Prefer rank. Context and ignore-all
   stay recorded and not applied. A standing op that carries a selector stays
   deferred.
2. May alternatives **union**. Absent May keeps the inherited permission; if
   no permission resolves anywhere, the baseline is General. An explicit empty
   May stays empty and does not borrow General.
3. Must requirements **intersect**. An active empty Must yields no eligibility.
   A child addition does not erase an ancestor Must, including when the child
   reuses the ancestor's name. Names are unique inside one scope only. A named
   replacement deletes only the selected target. Its output may reuse that
   target's identity; it does not overwrite a different sibling.
4. Prefer **ranks** the eligible spans. It does not add spans, does not drop a
   Must, and does not punch the eligible fallback into fragments.

Fingerprint: resolved rules, exception operations, and rejected deferred
forms are the ``composition`` category (sibling of ``availability``). Working
and General hours stay on ``availability``. See ``composition_fingerprint``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, time
from enum import Enum
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from app.scheduler.availability_materializer import (
    materialize_windows_for_local_date,
    merge_utc_intervals,
)

RANK_PREFER = "prefer"
RANK_ELIGIBLE = "eligible"

_SCOPE_RANK = {"epic": 0, "project": 1, "task": 2}


class AssignmentFamily(str, Enum):
    ABSENT = "absent"
    LEGACY = "legacy"
    NEW_RULE = "new_rule"
    CONFLICT = "conflict"


class RuleRole(str, Enum):
    MAY = "may"
    MUST = "must"
    PREFER = "prefer"


class MayMode(str, Enum):
    ABSENT = "absent"
    EXPLICIT_EMPTY = "explicit_empty"
    PRESENT = "present"


class ExceptionOp(str, Enum):
    ADD = "add"
    REPLACE_NAMED = "replace_named"
    WAIVE_NAMED = "waive_named"


class DeferredForm(str, Enum):
    DATE_RANGE = "date_range"
    WEEKDAY_STANDING = "weekday_standing"
    CONTEXT = "context"
    IGNORE_ALL = "ignore_all"


@dataclass(frozen=True)
class WindowSpec:
    """Recurring local window. Same fields the availability materializer reads."""

    weekday: int
    start_time: time
    duration_minutes: int
    ends_next_day: bool
    sort_order: int = 0


@dataclass(frozen=True)
class NamedRule:
    rule_id: str
    role: RuleRole
    windows: tuple[WindowSpec, ...]
    scope: str
    scope_id: str


@dataclass(frozen=True)
class StandingException:
    """One standing named-rule change. Applied before the eligibility stack."""

    operation: ExceptionOp
    scope: str
    scope_id: str
    target_rule_id: str | None = None
    rule: NamedRule | None = None


@dataclass(frozen=True)
class DeferredException:
    """A dated, weekday-standing, or context request. Not applied."""

    form: DeferredForm
    scope: str
    scope_id: str


@dataclass(frozen=True)
class ScopeLayer:
    """Local contribution at one scope. Layers are ordered ancestor → child."""

    scope: str
    scope_id: str
    may_mode: MayMode = MayMode.ABSENT
    may_rules: tuple[NamedRule, ...] = ()
    must_rules: tuple[NamedRule, ...] = ()
    prefer_rules: tuple[NamedRule, ...] = ()
    exceptions: tuple[StandingException, ...] = ()
    deferred: tuple[DeferredException, ...] = ()
    day_scoped: tuple[Any, ...] = ()


@dataclass(frozen=True)
class CompositionInput:
    """What the assignment resolver hands the placer.

    ``layers`` are the new-rule chain only. ``LEGACY`` and ``CONFLICT`` do not
    compose, even if a caller stuffed rules into ``layers``.
    """

    family: AssignmentFamily
    layers: tuple[ScopeLayer, ...] = ()
    day_scoped: tuple[Any, ...] = ()


@dataclass(frozen=True)
class EffectiveRule:
    rule_id: str
    role: RuleRole
    windows: tuple[WindowSpec, ...]
    scope: str
    scope_id: str
    origin: str


@dataclass(frozen=True)
class AppliedException:
    operation: str
    scope: str
    scope_id: str
    target_rule_id: str | None
    rule_id: str | None
    applied: bool


@dataclass(frozen=True)
class EffectiveComposition:
    """Rules after exceptions, before May union / Must intersect / Prefer rank."""

    family: AssignmentFamily
    may_source: str | None
    may_rules: tuple[EffectiveRule, ...]
    must_rules: tuple[EffectiveRule, ...]
    prefer_rules: tuple[EffectiveRule, ...]
    waived_must_ids: tuple[str, ...]
    exceptions: tuple[AppliedException, ...]
    deferred_rejected: tuple[DeferredException, ...]
    must_blocks_all: bool
    day_scoped: tuple[Any, ...] = ()
    source: CompositionInput | None = None

    def supplies_eligibility(self) -> bool:
        """True only when the placer must leave the legacy map ∩ Working path."""
        return self.family == AssignmentFamily.NEW_RULE


def make_window(
    weekday: int,
    start: time,
    duration_minutes: int,
    *,
    sort_order: int = 0,
) -> WindowSpec:
    seconds = start.hour * 3600 + start.minute * 60 + start.second
    ends = seconds + duration_minutes * 60 >= 86400
    return WindowSpec(
        weekday=int(weekday),
        start_time=start,
        duration_minutes=int(duration_minutes),
        ends_next_day=ends,
        sort_order=int(sort_order),
    )


def rule(
    rule_id: str,
    role: RuleRole | str,
    windows: Sequence[WindowSpec],
    *,
    scope: str,
    scope_id: str,
) -> NamedRule:
    return NamedRule(
        rule_id=str(rule_id),
        role=RuleRole(role),
        windows=tuple(windows),
        scope=scope,
        scope_id=str(scope_id),
    )


def _ordered_layers(layers: Sequence[ScopeLayer]) -> tuple[ScopeLayer, ...]:
    indexed = list(enumerate(layers))
    indexed.sort(key=lambda pair: (_SCOPE_RANK.get(pair[1].scope, 99), pair[0]))
    return tuple(layer for _, layer in indexed)


def select_scoped_name(
    candidates: Sequence[tuple[str, str, str]],
    *,
    scope: str,
    scope_id: str,
) -> tuple[str, str, str] | None:
    """Pick the one rule an explicit replace or waiver names.

    Each candidate is ``(scope, scope_id, rule_id)`` and already matches the
    target name and role. Names are unique inside one scope, not across the
    chain. A single match is that rule. Several matches: the nearest inherited
    rule (replace/waive targets the inherited rule, not a same-named local
    addition). If every match sits on the exception's own scope, that local rule.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    inherited = [
        item for item in candidates if (item[0], item[1]) != (scope, scope_id)
    ]
    pool = list(inherited or candidates)
    pool.sort(key=lambda item: _SCOPE_RANK.get(item[0], 99))
    return pool[-1]


def replacement_output_clobbers_sibling(
    output_key: tuple,
    chosen_key: tuple | None,
    *,
    bucket_has_output: bool,
) -> bool:
    """True when a named replacement would overwrite a sibling (V4-D2).

    §2.1 replaces the selected rule only. The output may reuse that rule's
    identity (in-place same-name replace). Any other occupied identity is a
    sibling and must survive. Callers skip the replace entirely: do not delete
    the target and do not write the output key. ``assignment_resolve`` uses
    the same predicate so effective read and placement stay aligned.
    """
    return bucket_has_output and output_key != chosen_key


def _as_effective(item: NamedRule, origin: str) -> EffectiveRule:
    return EffectiveRule(
        rule_id=item.rule_id,
        role=item.role,
        windows=item.windows,
        scope=item.scope,
        scope_id=item.scope_id,
        origin=origin,
    )


def _empty_effective(family: AssignmentFamily, deferred: tuple[DeferredException, ...]) -> EffectiveComposition:
    return EffectiveComposition(
        family=family,
        may_source=None,
        may_rules=(),
        must_rules=(),
        prefer_rules=(),
        waived_must_ids=(),
        exceptions=(),
        deferred_rejected=deferred,
        must_blocks_all=False,
        day_scoped=(),
        source=None,
    )


def resolve_effective_composition(item: CompositionInput) -> EffectiveComposition:
    """Fold inheritance and standing exceptions. Does not union or intersect yet.

    Non-new-rule families return no rules. That is the legacy-map guard: stuffed
    May/Must rows on an unconverted assignment do not become eligibility.
    """
    layers = _ordered_layers(item.layers)
    deferred = tuple(ex for layer in layers for ex in layer.deferred)
    day_scoped = tuple(item.day_scoped) + tuple(
        decl for layer in layers for decl in layer.day_scoped
    )
    if item.family != AssignmentFamily.NEW_RULE:
        empty = _empty_effective(item.family, deferred)
        return replace(empty, day_scoped=day_scoped, source=item)

    # Identity is scope + name. The same name at two scopes is two rules.
    may_rules: dict[tuple[str, str, str], EffectiveRule] | None = None
    must_rules: dict[tuple[str, str, str], EffectiveRule] = {}
    prefer_rules: dict[tuple[str, str, str], EffectiveRule] = {}
    waived: list[str] = []
    applied: list[AppliedException] = []

    def _key(entry: EffectiveRule) -> tuple[str, str, str]:
        return (entry.scope, entry.scope_id, entry.rule_id)

    def _bucket(role: RuleRole) -> dict[tuple[str, str, str], EffectiveRule] | None:
        if role == RuleRole.MAY:
            return may_rules
        if role == RuleRole.MUST:
            return must_rules
        return prefer_rules

    def _put(entry: EffectiveRule, *, overwrite: bool) -> None:
        nonlocal may_rules
        if entry.role == RuleRole.MAY:
            if may_rules is None:
                may_rules = {}
            if overwrite or _key(entry) not in may_rules:
                may_rules[_key(entry)] = entry
            return
        bucket = must_rules if entry.role == RuleRole.MUST else prefer_rules
        if overwrite or _key(entry) not in bucket:
            bucket[_key(entry)] = entry

    def _named_key(bucket: dict[tuple[str, str, str], EffectiveRule], name: str, exc: StandingException):
        return select_scoped_name(
            [key for key, entry in bucket.items() if entry.rule_id == name],
            scope=exc.scope,
            scope_id=exc.scope_id,
        )

    for layer in layers:
        if layer.may_mode == MayMode.EXPLICIT_EMPTY:
            may_rules = {}
        elif layer.may_mode == MayMode.PRESENT:
            for named in layer.may_rules:
                _put(_as_effective(named, "addition"), overwrite=False)
        for named in layer.must_rules:
            _put(_as_effective(named, "addition"), overwrite=False)
        for named in layer.prefer_rules:
            _put(_as_effective(named, "addition"), overwrite=False)

        for exc in layer.exceptions:
            if exc.operation == ExceptionOp.ADD and exc.rule is not None:
                # Same scoped id does not replace. A new id unions (May) or adds a
                # requirement/preference without clearing its siblings. The same
                # name at another scope is a different rule.
                before = _bucket(exc.rule.role)
                add_key = (exc.rule.scope, exc.rule.scope_id, exc.rule.rule_id)
                already = before is not None and add_key in before
                _put(_as_effective(exc.rule, "exception_add"), overwrite=False)
                applied.append(
                    AppliedException(
                        operation=exc.operation.value,
                        scope=exc.scope,
                        scope_id=exc.scope_id,
                        target_rule_id=exc.target_rule_id,
                        rule_id=exc.rule.rule_id,
                        applied=not already,
                    )
                )
                continue
            if exc.operation == ExceptionOp.REPLACE_NAMED and exc.rule is not None:
                target = exc.target_rule_id or exc.rule.rule_id
                # Names are unique inside one assignment, not across roles or
                # scopes. Replace only the named role so a Must replace cannot
                # drop a May that happens to share the name, and only the one
                # scoped rule select_scoped_name picks.
                role = exc.rule.role
                if role == RuleRole.MAY:
                    if may_rules is None:
                        may_rules = {}
                    bucket = may_rules
                elif role == RuleRole.MUST:
                    bucket = must_rules
                else:
                    bucket = prefer_rules
                chosen = _named_key(bucket, target, exc)
                replacement = _as_effective(exc.rule, "exception_replace")
                replacement_key = _key(replacement)
                # Output key is (replacement scope, scope id, output name).
                # That may be the selected target. It must not clobber a sibling.
                if replacement_output_clobbers_sibling(
                    replacement_key,
                    chosen,
                    bucket_has_output=replacement_key in bucket,
                ):
                    applied.append(
                        AppliedException(
                            operation=exc.operation.value,
                            scope=exc.scope,
                            scope_id=exc.scope_id,
                            target_rule_id=target,
                            rule_id=exc.rule.rule_id,
                            applied=False,
                        )
                    )
                    continue
                if chosen is not None:
                    del bucket[chosen]
                _put(replacement, overwrite=chosen == replacement_key)
                applied.append(
                    AppliedException(
                        operation=exc.operation.value,
                        scope=exc.scope,
                        scope_id=exc.scope_id,
                        target_rule_id=target,
                        rule_id=exc.rule.rule_id,
                        applied=True,
                    )
                )
                continue
            if exc.operation == ExceptionOp.WAIVE_NAMED:
                target = exc.target_rule_id or ""
                chosen = _named_key(must_rules, target, exc) if target else None
                removed = chosen is not None
                if chosen is not None:
                    del must_rules[chosen]
                    waived.append(target)
                applied.append(
                    AppliedException(
                        operation=exc.operation.value,
                        scope=exc.scope,
                        scope_id=exc.scope_id,
                        target_rule_id=target or None,
                        rule_id=None,
                        applied=removed,
                    )
                )

    if may_rules is None:
        may_source = "general"
        may_tuple: tuple[EffectiveRule, ...] = ()
    elif not any(entry.windows for entry in may_rules.values()):
        may_source = "explicit_empty"
        may_tuple = ()
    else:
        may_source = "explicit"
        may_tuple = tuple(
            sorted(may_rules.values(), key=lambda entry: (entry.rule_id, entry.scope, entry.scope_id))
        )

    must_tuple = tuple(
        sorted(must_rules.values(), key=lambda entry: (entry.rule_id, entry.scope, entry.scope_id))
    )
    prefer_tuple = tuple(
        sorted(prefer_rules.values(), key=lambda entry: (entry.rule_id, entry.scope, entry.scope_id))
    )
    must_blocks_all = any(not entry.windows for entry in must_tuple)
    return EffectiveComposition(
        family=AssignmentFamily.NEW_RULE,
        may_source=may_source,
        may_rules=may_tuple,
        must_rules=must_tuple,
        prefer_rules=prefer_tuple,
        waived_must_ids=tuple(sorted(set(waived))),
        exceptions=tuple(applied),
        deferred_rejected=deferred,
        must_blocks_all=must_blocks_all,
        day_scoped=day_scoped,
        source=item,
    )


def _spans_for(windows: Sequence[Any], day: date, tz: ZoneInfo) -> list[tuple[Any, Any]]:
    spans = materialize_windows_for_local_date(windows, day, tz)
    return [(span.start, span.end) for span in spans]


def _intersect_merged(
    left: Sequence[tuple[Any, Any]],
    right: Sequence[tuple[Any, Any]],
) -> list[tuple[Any, Any]]:
    if not left or not right:
        return []
    out: list[tuple[Any, Any]] = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        start = max(left[i][0], right[j][0])
        end = min(left[i][1], right[j][1])
        if start < end:
            out.append((start, end))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return out


def composition_search_windows(
    day: date,
    tz: ZoneInfo,
    composition: EffectiveComposition,
    general_windows: Sequence[Any] | None,
) -> list[tuple[Any, Any, str]]:
    """Eligible clips for one local day, preferred spans first.

    Returns ``[]`` for every non-new-rule family, explicit empty May, and
    empty Must. General is used only as the absent-May baseline. Prefer clips
    are the overlap of Prefer with that eligible set — never a new span.
    The eligible fallback is the full continuous May ∩ Must set. Prefer is
    tried first and is not subtracted out of that fallback.

    Day-scoped declarations fold here, after the standing composition and
    before May union / Must intersect / Prefer rank. No second search path.
    """
    if composition.day_scoped:
        from app.scheduler.day_scoped import folded_search_windows

        folded = folded_search_windows(day, tz, composition, general_windows)
        if folded is not None:
            return folded
    return _standing_search_windows(day, tz, composition, general_windows)


def _standing_search_windows(
    day: date,
    tz: ZoneInfo,
    composition: EffectiveComposition,
    general_windows: Sequence[Any] | None,
) -> list[tuple[Any, Any, str]]:
    if not composition.supplies_eligibility():
        return []
    if composition.must_blocks_all or composition.may_source == "explicit_empty":
        return []

    if composition.may_source == "general":
        pieces = _spans_for(list(general_windows or []), day, tz)
    else:
        pieces = []
        for entry in composition.may_rules:
            pieces.extend(_spans_for(entry.windows, day, tz))
    eligible = merge_utc_intervals(pieces)
    if not eligible:
        return []

    for must in composition.must_rules:
        must_spans = merge_utc_intervals(_spans_for(must.windows, day, tz))
        eligible = _intersect_merged(eligible, must_spans)
        if not eligible:
            return []

    prefer_pieces: list[tuple[Any, Any]] = []
    for prefer in composition.prefer_rules:
        prefer_pieces.extend(_spans_for(prefer.windows, day, tz))
    preferred = (
        _intersect_merged(eligible, merge_utc_intervals(prefer_pieces))
        if prefer_pieces
        else []
    )
    # Rank Prefer first. Do not carve it out of the fallback: a 2h minimum
    # still has to see the continuous May ∩ Must span that contains the
    # preferred hour, and busy/Must boundaries stay on that span.
    ordered: list[tuple[Any, Any, str]] = [
        (start, end, RANK_PREFER) for start, end in preferred
    ]
    ordered.extend((start, end, RANK_ELIGIBLE) for start, end in eligible)
    return ordered


def _window_payload(windows: Sequence[WindowSpec]) -> list[dict[str, Any]]:
    rows = [
        {
            "weekday": int(item.weekday),
            "start_time": item.start_time.isoformat(),
            "duration_minutes": int(item.duration_minutes),
            "ends_next_day": bool(item.ends_next_day),
            "sort_order": int(item.sort_order),
        }
        for item in windows
    ]
    rows.sort(
        key=lambda row: (
            row["weekday"],
            row["sort_order"],
            row["start_time"],
            row["duration_minutes"],
            row["ends_next_day"],
        )
    )
    return rows


def _rule_payload(entry: EffectiveRule) -> dict[str, Any]:
    return {
        "rule_id": entry.rule_id,
        "role": entry.role.value,
        "scope": entry.scope,
        "scope_id": entry.scope_id,
        "origin": entry.origin,
        "windows": _window_payload(entry.windows),
    }


def absent_composition_fingerprint() -> dict[str, Any]:
    """Stable category for a task with no new-rule assignment."""
    return {
        "family": AssignmentFamily.ABSENT.value,
        "may_source": None,
        "rules": [],
        "waived_must_ids": [],
        "exceptions": [],
        "deferred_rejected": [],
    }


def composition_fingerprint(effective: EffectiveComposition | None) -> dict[str, Any]:
    """Compared ``composition`` category.

    Sibling of ``availability`` on purpose. Policy-hour edits keep staling
    ``availability``. Rule refs, Must/Prefer windows, exception operations,
    and rejected deferred forms stale here, including a Prefer edit that does
    not change the eligible set. ``family`` is explicit so legacy ↔ new-rule
    switches stale without copying Time Map bands (those stay on ``map_style``).
    """
    if effective is None or effective.family == AssignmentFamily.ABSENT:
        return absent_composition_fingerprint()
    rules = [
        _rule_payload(entry)
        for entry in (*effective.may_rules, *effective.must_rules, *effective.prefer_rules)
    ]
    rules.sort(key=lambda row: (row["role"], row["rule_id"], row["scope"], row["scope_id"]))
    exceptions = [
        {
            "operation": item.operation,
            "scope": item.scope,
            "scope_id": item.scope_id,
            "target_rule_id": item.target_rule_id,
            "rule_id": item.rule_id,
            "applied": bool(item.applied),
        }
        for item in effective.exceptions
    ]
    exceptions.sort(
        key=lambda row: (
            row["scope"],
            row["operation"],
            row["target_rule_id"] or "",
            row["rule_id"] or "",
        )
    )
    deferred = [
        {"form": item.form.value, "scope": item.scope, "scope_id": item.scope_id}
        for item in effective.deferred_rejected
    ]
    deferred.sort(key=lambda row: (row["form"], row["scope"], row["scope_id"]))
    payload = {
        "family": effective.family.value,
        "may_source": effective.may_source,
        "rules": rules,
        "waived_must_ids": list(effective.waived_must_ids),
        "exceptions": exceptions,
        "deferred_rejected": deferred,
    }
    if effective.day_scoped:
        from app.scheduler.day_scoped import day_scoped_fingerprint_rows

        payload["day_scoped"] = day_scoped_fingerprint_rows(effective.day_scoped)
    return payload


def _parse_time(value: time | str) -> time:
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def _window_from_mapping(payload: Mapping[str, Any], index: int) -> WindowSpec:
    start = _parse_time(payload["start_time"])
    duration = int(payload["duration_minutes"])
    if "ends_next_day" in payload:
        ends = bool(payload["ends_next_day"])
        return WindowSpec(
            weekday=int(payload["weekday"]),
            start_time=start,
            duration_minutes=duration,
            ends_next_day=ends,
            sort_order=int(payload.get("sort_order") or index),
        )
    return make_window(
        int(payload["weekday"]),
        start,
        duration,
        sort_order=int(payload.get("sort_order") or index),
    )


def _rule_from_mapping(payload: Mapping[str, Any], *, scope: str, scope_id: str) -> NamedRule:
    windows = tuple(
        _window_from_mapping(row, index)
        for index, row in enumerate(payload.get("windows") or [])
    )
    return NamedRule(
        rule_id=str(payload["rule_id"]),
        role=RuleRole(payload["role"]),
        windows=windows,
        scope=str(payload.get("scope") or scope),
        scope_id=str(payload.get("scope_id") or scope_id),
    )


def _authorized_day_scoped_ops() -> frozenset[str]:
    from app.scheduler.day_scoped import AUTHORIZED_OPERATIONS

    return AUTHORIZED_OPERATIONS


def _deferred_form_from_mapping(payload: Mapping[str, Any]) -> DeferredForm | None:
    """Context, ignore-all, and standing ops that carry a selector stay deferred.

    Authorized day-scoped operations are parsed and applied per day. They do
    not land in ``deferred_rejected``.
    """
    operation = str(payload.get("operation") or "")
    if operation in _authorized_day_scoped_ops():
        return None
    if operation == "ignore_all" or payload.get("ignore_all"):
        return DeferredForm.IGNORE_ALL
    if payload.get("form"):
        return DeferredForm(str(payload["form"]))
    if any(payload.get(key) for key in ("applies_on", "local_date", "date_range", "start_date", "end_date")):
        return DeferredForm.DATE_RANGE
    if any(payload.get(key) for key in ("weekdays", "weekday_standing")):
        return DeferredForm.WEEKDAY_STANDING
    if any(payload.get(key) for key in ("context_id", "context")):
        return DeferredForm.CONTEXT
    return None


def _layer_from_mapping(payload: Mapping[str, Any]) -> ScopeLayer:
    scope = str(payload["scope"])
    scope_id = str(payload["scope_id"])
    deferred = [
        DeferredException(
            form=DeferredForm(str(item["form"])),
            scope=str(item.get("scope") or scope),
            scope_id=str(item.get("scope_id") or scope_id),
        )
        for item in payload.get("deferred") or []
    ]
    day_scoped: list[Any] = []
    for item in payload.get("day_scoped") or []:
        if isinstance(item, Mapping):
            from app.scheduler.day_scoped import declaration_from_mapping

            day_scoped.append(declaration_from_mapping(item, scope=scope, scope_id=scope_id))
    exceptions: list[StandingException] = []
    for item in payload.get("exceptions") or []:
        if str(item.get("operation") or "") in _authorized_day_scoped_ops():
            from app.scheduler.day_scoped import declaration_from_mapping

            day_scoped.append(declaration_from_mapping(item, scope=scope, scope_id=scope_id))
            continue
        form = _deferred_form_from_mapping(item)
        if form is not None:
            deferred.append(
                DeferredException(form=form, scope=scope, scope_id=scope_id)
            )
            continue
        rule_payload = item.get("rule")
        named = (
            _rule_from_mapping(rule_payload, scope=scope, scope_id=scope_id)
            if isinstance(rule_payload, Mapping)
            else None
        )
        exceptions.append(
            StandingException(
                operation=ExceptionOp(str(item["operation"])),
                scope=str(item.get("scope") or scope),
                scope_id=str(item.get("scope_id") or scope_id),
                target_rule_id=(
                    str(item["target_rule_id"]) if item.get("target_rule_id") else None
                ),
                rule=named,
            )
        )
    return ScopeLayer(
        scope=scope,
        scope_id=scope_id,
        may_mode=MayMode(str(payload.get("may_mode") or MayMode.ABSENT.value)),
        may_rules=tuple(
            _rule_from_mapping(row, scope=scope, scope_id=scope_id)
            for row in payload.get("may_rules") or []
        ),
        must_rules=tuple(
            _rule_from_mapping(row, scope=scope, scope_id=scope_id)
            for row in payload.get("must_rules") or []
        ),
        prefer_rules=tuple(
            _rule_from_mapping(row, scope=scope, scope_id=scope_id)
            for row in payload.get("prefer_rules") or []
        ),
        exceptions=tuple(exceptions),
        deferred=tuple(deferred),
        day_scoped=tuple(day_scoped),
    )


def composition_input_from_mapping(payload: Mapping[str, Any]) -> CompositionInput:
    """Dict form of :class:`CompositionInput` for the resolver seam."""
    layers = tuple(_layer_from_mapping(row) for row in payload.get("layers") or [])
    return CompositionInput(family=AssignmentFamily(str(payload["family"])), layers=layers)


def coerce_composition_input(value: CompositionInput | Mapping[str, Any]) -> CompositionInput:
    if isinstance(value, CompositionInput):
        return value
    if isinstance(value, Mapping):
        return composition_input_from_mapping(value)
    raise TypeError(f"Cannot coerce composition input from {type(value).__name__}")
