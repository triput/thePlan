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


def _apply_exceptions(
    rules: list[ResolvedRule],
    exceptions: list[SchedulingRuleException],
    *,
    scope: ScopeKind,
) -> tuple[list[ResolvedRule], list[AppliedException]]:
    """Apply standing replace/waive exceptions before May/Must/Prefer stack."""
    applied: list[AppliedException] = []
    waived: set[tuple[str, str]] = set()
    replacements: dict[tuple[str, str], ResolvedRule] = {}

    for exc in exceptions:
        key = (exc.target_rule_kind.value, exc.target_rule_name)
        applied.append(
            AppliedException(
                operation=exc.operation.value,  # type: ignore[arg-type]
                target_rule_name=exc.target_rule_name,
                target_rule_kind=exc.target_rule_kind.value,  # type: ignore[arg-type]
                scope=scope,
            )
        )
        if exc.operation == SchedulingExceptionOp.waive_named:
            waived.add(key)
            continue
        assert exc.replacement_name is not None
        replacements[key] = ResolvedRule(
            name=exc.replacement_name,
            kind=exc.target_rule_kind.value,  # type: ignore[arg-type]
            policy_id=exc.replacement_policy_id,
            empty_set=bool(exc.replacement_empty_set),
            source_scope=scope,
            origin="replacement",
        )

    out: list[ResolvedRule] = []
    for rule in rules:
        key = (rule.kind, rule.name)
        if key in waived:
            continue
        if key in replacements:
            out.append(replacements[key])
            continue
        out.append(rule)
    return out, applied


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
    May omit retains inherited May; Must/Prefer additions accumulate; named
    replace/waive exceptions apply before the composition stack.
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

    # May: walk from winning scope through farther new-rule/none ancestors until
    # an explicit may_presence is found; else absent → General baseline.
    may_presence: MayPresence = "absent"
    may_rules: list[ResolvedRule] = []
    must_rules: list[ResolvedRule] = []
    prefer_rules: list[ResolvedRule] = []
    exceptions_applied: list[AppliedException] = []

    # Collect Must/Prefer from all new-rule scopes (near to far): additions
    # accumulate; nearer named rules of the same name shadow for that kind via
    # exception replace, not by silent erase of other Musts.
    for scope in new_rule_scopes:
        local = locals_map[scope]
        assert local.assignment is not None
        origin: Literal["local", "inherited"] = (
            "local" if scope == winning_scope else "inherited"
        )
        scope_rules = [
            _rule_from_row(row, source_scope=scope, origin=origin)
            for row in local.assignment.rules
        ]
        exceptions = load_exceptions_at_scope(
            db, owner_id=owner_id, scope=scope, scope_id=local.scope_id
        )
        scope_rules, applied = _apply_exceptions(
            scope_rules, exceptions, scope=scope
        )
        exceptions_applied.extend(applied)

        for rule in scope_rules:
            if rule.kind == "must":
                must_rules.append(rule)
            elif rule.kind == "prefer":
                prefer_rules.append(rule)

    # May presence: nearer omit keeps looking; explicit (incl. empty) wins.
    for scope in chain[win_index:]:
        local = locals_map.get(scope)
        if local is None or local.family != "new_rule" or local.assignment is None:
            if local is not None and local.family == "legacy":
                break
            continue
        if local.assignment.may_presence == SchedulingMayPresence.omit:
            continue
        may_presence = "explicit"
        may_rules = [
            _rule_from_row(
                row,
                source_scope=scope,
                origin="local" if scope == winning_scope else "inherited",
            )
            for row in local.assignment.rules
            if row.kind == SchedulingRuleKind.may
        ]
        exceptions = load_exceptions_at_scope(
            db, owner_id=owner_id, scope=scope, scope_id=local.scope_id
        )
        may_rules, applied = _apply_exceptions(may_rules, exceptions, scope=scope)
        # Only May-affecting exceptions matter here; record them if not already.
        for item in applied:
            if item not in exceptions_applied:
                exceptions_applied.append(item)
        break
    else:
        # No explicit May anywhere on the new-rule chain → absent (General).
        may_presence = "absent"

    all_for_personal = may_rules + must_rules + prefer_rules
    return ResolvedSchedulingAssignment(
        family="new_rule",
        winning_scope=winning_scope,
        winning_scope_id=winning_scope_id,
        legacy_map_id=None,
        legacy_source=None,
        may_presence=may_presence,
        may_rules=tuple(may_rules),
        must_rules=tuple(must_rules),
        prefer_rules=tuple(prefer_rules),
        exceptions_applied=tuple(exceptions_applied),
        consumes_personal_policy=_consumes_personal(all_for_personal, personal_policy_id),
        local_by_scope=locals_map,
    )
