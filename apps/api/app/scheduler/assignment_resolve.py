# ==============================================================================
#  File: apps/api/app/scheduler/assignment_resolve.py
#  Description: Sibling to windows.py — resolve legacy/new-rule family + May/Must/Prefer.
#  Component: Scheduling / Settings — S2-V4
#  Version: 1.0
#  Created: 2026-10-13
#  Last Update: 2026-10-13
# ==============================================================================

"""Resolved scheduling assignment for collect + effective-read.

Tesla wires placer May∪ / Must∩ / Prefer-rank against these structures.
Do not stuff new-rule refs into ``effective_preferred_time_window_id``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import Epic, Project, Task
from app.models.enums import (
    SchedulingAssignmentFamily,
    SchedulingExceptionOp,
    SchedulingMayPresence,
    SchedulingRuleKind,
    SchedulingScopeKind,
)
from app.models.scheduling_assignment import (
    SchedulingAssignment,
    SchedulingAssignmentRule,
    SchedulingRuleException,
)
from app.scheduler.composition import select_scoped_name
from app.scheduler.windows import (
    effective_preferred_time_window_id,
    effective_preferred_time_window_source,
)

ScopeKind = Literal["task", "project", "epic"]
RuleKind = Literal["may", "must", "prefer"]
FamilyKind = Literal["none", "legacy", "new_rule"]
MayPresence = Literal["omit", "explicit", "absent"]


@dataclass(frozen=True)
class ResolvedRule:
    """One May / Must / Prefer rule after exceptions-before-stack."""

    name: str
    kind: RuleKind
    policy_id: UUID | None
    empty_set: bool
    source_scope: ScopeKind
    origin: Literal["local", "inherited", "replacement"]


@dataclass(frozen=True)
class AppliedException:
    operation: Literal["replace_named", "waive_named"]
    target_rule_name: str
    target_rule_kind: RuleKind
    scope: ScopeKind


@dataclass(frozen=True)
class RepairableFamilyConflict:
    """Both families active at the same scope (malformed / imported)."""

    scope: ScopeKind
    scope_id: UUID
    preferred_time_window_id: UUID
    assignment_id: UUID
    guidance: str = (
        "Both a legacy Time Map and a new-rule assignment are active at this "
        "scope. Clear one family or use explicit family-replace; do not rely on "
        "save order."
    )


@dataclass(frozen=True)
class LocalScopeAssignment:
    """Local state at one epic/project/task scope (before inheritance)."""

    scope: ScopeKind
    scope_id: UUID
    family: FamilyKind
    preferred_time_window_id: UUID | None
    assignment: SchedulingAssignment | None
    conflict: RepairableFamilyConflict | None = None


@dataclass(frozen=True)
class ResolvedSchedulingAssignment:
    """Effective assignment for one task after cross-level precedence + exceptions.

    Tesla: when ``family == "new_rule"``, compose May∪ / Must∩ / Prefer-rank from
    the lists below (exceptions already applied). When ``family == "legacy"``,
    keep map ∩ Working — do not run May/Must composition. When ``family ==
    "none"``, unclassified → General (V3).
    """

    family: FamilyKind
    winning_scope: ScopeKind | None
    winning_scope_id: UUID | None
    legacy_map_id: UUID | None
    legacy_source: str | None
    may_presence: MayPresence
    may_rules: tuple[ResolvedRule, ...] = ()
    must_rules: tuple[ResolvedRule, ...] = ()
    prefer_rules: tuple[ResolvedRule, ...] = ()
    exceptions_applied: tuple[AppliedException, ...] = ()
    conflict: RepairableFamilyConflict | None = None
    consumes_personal_policy: bool = False
    local_by_scope: dict[ScopeKind, LocalScopeAssignment] = field(default_factory=dict)


def _scope_enum(scope: ScopeKind) -> SchedulingScopeKind:
    return SchedulingScopeKind(scope)


def load_assignment_at_scope(
    db: Session,
    *,
    owner_id: UUID,
    scope: ScopeKind,
    scope_id: UUID,
) -> SchedulingAssignment | None:
    return (
        db.query(SchedulingAssignment)
        .options(joinedload(SchedulingAssignment.rules))
        .filter(
            SchedulingAssignment.owner_id == owner_id,
            SchedulingAssignment.scope_kind == _scope_enum(scope),
            SchedulingAssignment.scope_id == scope_id,
        )
        .one_or_none()
    )


def load_exceptions_at_scope(
    db: Session,
    *,
    owner_id: UUID,
    scope: ScopeKind,
    scope_id: UUID,
) -> list[SchedulingRuleException]:
    return (
        db.query(SchedulingRuleException)
        .filter(
            SchedulingRuleException.owner_id == owner_id,
            SchedulingRuleException.scope_kind == _scope_enum(scope),
            SchedulingRuleException.scope_id == scope_id,
        )
        .order_by(SchedulingRuleException.target_rule_name)
        .all()
    )


def local_scope_assignment(
    *,
    scope: ScopeKind,
    scope_id: UUID,
    preferred_time_window_id: UUID | None,
    assignment: SchedulingAssignment | None,
) -> LocalScopeAssignment:
    has_legacy = preferred_time_window_id is not None
    has_new = assignment is not None
    if has_legacy and has_new:
        assert preferred_time_window_id is not None and assignment is not None
        return LocalScopeAssignment(
            scope=scope,
            scope_id=scope_id,
            family="legacy",  # not authoritative while conflict stands
            preferred_time_window_id=preferred_time_window_id,
            assignment=assignment,
            conflict=RepairableFamilyConflict(
                scope=scope,
                scope_id=scope_id,
                preferred_time_window_id=preferred_time_window_id,
                assignment_id=assignment.id,
            ),
        )
    if has_new:
        return LocalScopeAssignment(
            scope=scope,
            scope_id=scope_id,
            family="new_rule",
            preferred_time_window_id=None,
            assignment=assignment,
        )
    if has_legacy:
        return LocalScopeAssignment(
            scope=scope,
            scope_id=scope_id,
            family="legacy",
            preferred_time_window_id=preferred_time_window_id,
            assignment=None,
        )
    return LocalScopeAssignment(
        scope=scope,
        scope_id=scope_id,
        family="none",
        preferred_time_window_id=None,
        assignment=None,
    )


def _rule_from_row(
    row: SchedulingAssignmentRule,
    *,
    source_scope: ScopeKind,
    origin: Literal["local", "inherited", "replacement"] = "local",
) -> ResolvedRule:
    return ResolvedRule(
        name=row.name,
        kind=row.kind.value,  # type: ignore[arg-type]
        policy_id=row.policy_id,
        empty_set=bool(row.empty_set),
        source_scope=source_scope,
        origin=origin,
    )


def _rule_identity(rule: ResolvedRule) -> tuple[str, str]:
    return (rule.source_scope, rule.name)


def _pick_named(
    bucket: dict[tuple[str, str], ResolvedRule],
    name: str,
    *,
    scope: ScopeKind,
) -> tuple[str, str] | None:
    """Same choice as composition ``select_scoped_name`` (scope kind is the id)."""
    matches = [
        (key[0], key[0], key[1]) for key, rule in bucket.items() if rule.name == name
    ]
    chosen = select_scoped_name(matches, scope=scope, scope_id=scope)
    if chosen is None:
        return None
    return (chosen[0], chosen[2])


def _apply_layer_exceptions(
    may_rules: dict[tuple[str, str], ResolvedRule] | None,
    must_rules: dict[tuple[str, str], ResolvedRule],
    prefer_rules: dict[tuple[str, str], ResolvedRule],
    exceptions: list[SchedulingRuleException],
    *,
    scope: ScopeKind,
) -> tuple[dict[tuple[str, str], ResolvedRule] | None, list[AppliedException]]:
    """Apply this scope's standing exceptions to the accumulated chain.

    Ancestors are already in the buckets, so a child waiver of a project Must
    removes that inherited rule. Same-named rules at other scopes stay until
    an explicit replace/waive selects one of them.
    """
    applied: list[AppliedException] = []
    for exc in exceptions:
        applied.append(
            AppliedException(
                operation=exc.operation.value,  # type: ignore[arg-type]
                target_rule_name=exc.target_rule_name,
                target_rule_kind=exc.target_rule_kind.value,  # type: ignore[arg-type]
                scope=scope,
            )
        )
        kind = exc.target_rule_kind.value
        if exc.operation == SchedulingExceptionOp.waive_named:
            if kind != "must":
                continue
            chosen = _pick_named(must_rules, exc.target_rule_name, scope=scope)
            if chosen is not None:
                del must_rules[chosen]
            continue
        assert exc.replacement_name is not None
        if kind == "may":
            if may_rules is None:
                may_rules = {}
            bucket: dict[tuple[str, str], ResolvedRule] = may_rules
        elif kind == "must":
            bucket = must_rules
        else:
            bucket = prefer_rules
        chosen = _pick_named(bucket, exc.target_rule_name, scope=scope)
        if chosen is not None:
            del bucket[chosen]
        replacement = ResolvedRule(
            name=exc.replacement_name,
            kind=kind,  # type: ignore[arg-type]
            policy_id=exc.replacement_policy_id,
            empty_set=bool(exc.replacement_empty_set),
            source_scope=scope,
            origin="replacement",
        )
        bucket[_rule_identity(replacement)] = replacement
    return may_rules, applied


def _sorted_rules(
    bucket: dict[tuple[str, str], ResolvedRule],
) -> tuple[ResolvedRule, ...]:
    return tuple(sorted(bucket.values(), key=lambda rule: (rule.name, rule.source_scope)))


def _consumes_personal(rules: list[ResolvedRule], personal_policy_id: UUID | None) -> bool:
    if personal_policy_id is None:
        return False
    return any(
        (not rule.empty_set) and rule.policy_id == personal_policy_id for rule in rules
    )


def resolve_task_scheduling_assignment(
    db: Session,
    task: Task,
    project: Project | None,
    epic: Epic | None,
    *,
    personal_policy_id: UUID | None = None,
) -> ResolvedSchedulingAssignment:
    """Cross-level family precedence + new-rule stack inputs (exceptions applied).

    Nearest explicit local assignment wins the family (cutover §4.1). Same-scope
    both-families → repairable conflict (no arbitrary winner). New-to-new: child
    May omit retains inherited May; explicit May unions with it; explicit empty
    May clears it. Must/Prefer additions accumulate as scoped identities (the
    same name at another scope is a second rule). Named replace/waive applies
    to that accumulated set, so a child exception can remove an inherited rule.
    """
    owner_id = task.owner_id
    task_asg = load_assignment_at_scope(
        db, owner_id=owner_id, scope="task", scope_id=task.id
    )
    project_asg = (
        load_assignment_at_scope(
            db, owner_id=owner_id, scope="project", scope_id=project.id
        )
        if project is not None
        else None
    )
    epic_asg = (
        load_assignment_at_scope(db, owner_id=owner_id, scope="epic", scope_id=epic.id)
        if epic is not None
        else None
    )

    locals_map: dict[ScopeKind, LocalScopeAssignment] = {
        "task": local_scope_assignment(
            scope="task",
            scope_id=task.id,
            preferred_time_window_id=task.preferred_time_window_id,
            assignment=task_asg,
        ),
    }
    if project is not None:
        locals_map["project"] = local_scope_assignment(
            scope="project",
            scope_id=project.id,
            preferred_time_window_id=project.preferred_time_window_id,
            assignment=project_asg,
        )
    if epic is not None:
        locals_map["epic"] = local_scope_assignment(
            scope="epic",
            scope_id=epic.id,
            preferred_time_window_id=epic.preferred_time_window_id,
            assignment=epic_asg,
        )

    chain: list[ScopeKind] = ["task"]
    if project is not None:
        chain.append("project")
    if epic is not None:
        chain.append("epic")

    for scope in chain:
        local = locals_map[scope]
        if local.conflict is not None:
            legacy_id = effective_preferred_time_window_id(task, project, epic)
            return ResolvedSchedulingAssignment(
                family="none",
                winning_scope=scope,
                winning_scope_id=local.scope_id,
                legacy_map_id=legacy_id,
                legacy_source=effective_preferred_time_window_source(task, project, epic),
                may_presence="absent",
                conflict=local.conflict,
                local_by_scope=locals_map,
            )
        if local.family == "none":
            continue
        if local.family == "legacy":
            return ResolvedSchedulingAssignment(
                family="legacy",
                winning_scope=scope,
                winning_scope_id=local.scope_id,
                legacy_map_id=local.preferred_time_window_id,
                legacy_source=scope,
                may_presence="absent",
                local_by_scope=locals_map,
            )
        # new_rule wins at this scope — compose from this scope + ancestors
        # (ancestors used only for new-to-new inheritance, not legacy maps).
        return _resolve_new_rule_stack(
            db,
            owner_id=owner_id,
            winning_scope=scope,
            winning_scope_id=local.scope_id,
            chain=chain,
            locals_map=locals_map,
            personal_policy_id=personal_policy_id,
        )

    return ResolvedSchedulingAssignment(
        family="none",
        winning_scope=None,
        winning_scope_id=None,
        legacy_map_id=None,
        legacy_source=None,
        may_presence="absent",
        local_by_scope=locals_map,
    )


def _resolve_new_rule_stack(
    db: Session,
    *,
    owner_id: UUID,
    winning_scope: ScopeKind,
    winning_scope_id: UUID,
    chain: list[ScopeKind],
    locals_map: dict[ScopeKind, LocalScopeAssignment],
    personal_policy_id: UUID | None,
) -> ResolvedSchedulingAssignment:
    # Ancestor chain from winning scope downward through farther ancestors only
    # for new-rule layers. Stop collecting if an ancestor is legacy (cross-family
    # precedence already chose this new_rule winner; do not compose onto maps).
    win_index = chain.index(winning_scope)
    new_rule_scopes: list[ScopeKind] = []
    for scope in chain[win_index:]:
        local = locals_map[scope]
        if local.family == "legacy":
            break
        if local.family == "new_rule":
            new_rule_scopes.append(scope)
        # family none: skip (no local assignment); still look farther for May

    # Far → near, same order composition folds layers. Exceptions apply after
    # that scope's rules join the chain, so they can see inherited rules.
    may_rules: dict[tuple[str, str], ResolvedRule] | None = None
    must_rules: dict[tuple[str, str], ResolvedRule] = {}
    prefer_rules: dict[tuple[str, str], ResolvedRule] = {}
    exceptions_applied: list[AppliedException] = []

    for scope in reversed(new_rule_scopes):
        local = locals_map[scope]
        assert local.assignment is not None
        origin: Literal["local", "inherited"] = (
            "local" if scope == winning_scope else "inherited"
        )
        rows = [
            _rule_from_row(row, source_scope=scope, origin=origin)
            for row in local.assignment.rules
        ]
        may_rows = [rule for rule in rows if rule.kind == "may"]
        if local.assignment.may_presence == SchedulingMayPresence.omit:
            pass
        elif not may_rows or all(rule.empty_set for rule in may_rows):
            # Explicit empty clears inherited May. It does not borrow General.
            may_rules = {}
        else:
            if may_rules is None:
                may_rules = {}
            for rule in may_rows:
                key = _rule_identity(rule)
                if key not in may_rules:
                    may_rules[key] = rule
        for rule in rows:
            if rule.kind == "must":
                key = _rule_identity(rule)
                if key not in must_rules:
                    must_rules[key] = rule
            elif rule.kind == "prefer":
                key = _rule_identity(rule)
                if key not in prefer_rules:
                    prefer_rules[key] = rule
        exceptions = load_exceptions_at_scope(
            db, owner_id=owner_id, scope=scope, scope_id=local.scope_id
        )
        may_rules, applied = _apply_layer_exceptions(
            may_rules,
            must_rules,
            prefer_rules,
            exceptions,
            scope=scope,
        )
        exceptions_applied.extend(applied)

    if may_rules is None:
        may_presence: MayPresence = "absent"
        may_tuple: tuple[ResolvedRule, ...] = ()
    else:
        may_presence = "explicit"
        # Contentless May matches composition's explicit-empty output: no rules.
        if may_rules and all(rule.empty_set for rule in may_rules.values()):
            may_tuple = ()
        else:
            may_tuple = _sorted_rules(may_rules)

    must_tuple = _sorted_rules(must_rules)
    prefer_tuple = _sorted_rules(prefer_rules)
    all_for_personal = [*may_tuple, *must_tuple, *prefer_tuple]
    return ResolvedSchedulingAssignment(
        family="new_rule",
        winning_scope=winning_scope,
        winning_scope_id=winning_scope_id,
        legacy_map_id=None,
        legacy_source=None,
        may_presence=may_presence,
        may_rules=may_tuple,
        must_rules=must_tuple,
        prefer_rules=prefer_tuple,
        exceptions_applied=tuple(exceptions_applied),
        consumes_personal_policy=_consumes_personal(all_for_personal, personal_policy_id),
        local_by_scope=locals_map,
    )
