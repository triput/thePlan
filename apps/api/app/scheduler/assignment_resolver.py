# ==============================================================================
#  File: apps/api/app/scheduler/assignment_resolver.py
#  Description: Tesla seam — resolve_new_rule_compositions → CompositionInput layers.
#  Component: Scheduling / Settings — S2-V4
#  Version: 1.0
#  Created: 2026-10-13
#  Last Update: 2026-10-14 (legacy standing map rides with the composition)
# ==============================================================================

"""Bridge from Jules assignment rows to Tesla's composition stack.

``composition_resolver`` imports ``resolve_new_rule_compositions`` from this
module. Do not query assignment tables from placement.py / collect.py directly.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import AvailabilityPolicy, Epic, Project, Task
from app.models.enums import (
    SchedulingExceptionOp,
    SchedulingMayPresence,
    SchedulingRuleKind,
)
from app.scheduler.assignment_resolve import (
    load_assignment_at_scope,
    load_exceptions_at_scope,
    local_scope_assignment,
)
from app.scheduler.day_scoped import load_day_scoped_declarations


def _composition():
    """Lazy import — Tesla owns ``composition.py``; seam activates when present."""
    from app.scheduler import composition as mod

    return mod


def _windows_for_policy(policy: AvailabilityPolicy | None):
    comp = _composition()
    if policy is None:
        return ()
    return tuple(
        comp.make_window(
            int(row.weekday),
            row.start_time,
            int(row.duration_minutes),
            sort_order=int(row.sort_order),
        )
        for row in sorted(policy.windows, key=lambda w: (w.weekday, w.sort_order))
    )


def _named_rule(
    *,
    name: str,
    kind: SchedulingRuleKind,
    policy_id: UUID | None,
    empty_set: bool,
    scope: str,
    scope_id: UUID,
    policies: dict[UUID, AvailabilityPolicy],
):
    comp = _composition()
    windows = ()
    if not empty_set and policy_id is not None:
        windows = _windows_for_policy(policies.get(policy_id))
    return comp.NamedRule(
        rule_id=name,
        role=comp.RuleRole(kind.value),
        windows=windows,
        scope=scope,
        scope_id=str(scope_id),
    )


def _layer_for_assignment(
    db: Session,
    *,
    owner_id: UUID,
    scope: str,
    scope_id: UUID,
    assignment,
    policies: dict[UUID, AvailabilityPolicy],
):
    comp = _composition()
    may_rules = []
    must_rules = []
    prefer_rules = []
    for row in assignment.rules:
        named = _named_rule(
            name=row.name,
            kind=row.kind,
            policy_id=row.policy_id,
            empty_set=bool(row.empty_set),
            scope=scope,
            scope_id=scope_id,
            policies=policies,
        )
        if row.kind == SchedulingRuleKind.may:
            may_rules.append(named)
        elif row.kind == SchedulingRuleKind.must:
            must_rules.append(named)
        else:
            prefer_rules.append(named)

    if assignment.may_presence == SchedulingMayPresence.omit:
        may_mode = comp.MayMode.ABSENT
        may_rules = []
    elif not may_rules or all(not rule.windows for rule in may_rules):
        may_mode = comp.MayMode.EXPLICIT_EMPTY
        may_rules = []
    else:
        may_mode = comp.MayMode.PRESENT

    exceptions = []
    for exc in load_exceptions_at_scope(
        db, owner_id=owner_id, scope=scope, scope_id=scope_id  # type: ignore[arg-type]
    ):
        if exc.operation == SchedulingExceptionOp.waive_named:
            exceptions.append(
                comp.StandingException(
                    operation=comp.ExceptionOp.WAIVE_NAMED,
                    scope=scope,
                    scope_id=str(scope_id),
                    target_rule_id=exc.target_rule_name,
                    rule=None,
                )
            )
            continue
        # Output identity is this writing scope plus replacement name. Composition
        # and assignment_resolve key the same way. rule_replace_named rejects a
        # name that already belongs to a sibling; both skip rather than overwrite
        # if a colliding row is composed anyway.
        replacement = _named_rule(
            name=exc.replacement_name or exc.target_rule_name,
            kind=exc.target_rule_kind,
            policy_id=exc.replacement_policy_id,
            empty_set=bool(exc.replacement_empty_set),
            scope=scope,
            scope_id=scope_id,
            policies=policies,
        )
        exceptions.append(
            comp.StandingException(
                operation=comp.ExceptionOp.REPLACE_NAMED,
                scope=scope,
                scope_id=str(scope_id),
                target_rule_id=exc.target_rule_name,
                rule=replacement,
            )
        )

    return comp.ScopeLayer(
        scope=scope,
        scope_id=str(scope_id),
        may_mode=may_mode,
        may_rules=tuple(may_rules),
        must_rules=tuple(must_rules),
        prefer_rules=tuple(prefer_rules),
        exceptions=tuple(exceptions),
    )


def _standing_legacy_views(db: Session, owner_id: UUID):
    """One owner load of focus windows and overrides, then a view per map id."""
    from app.models import FocusWindow
    from app.scheduler.day_scoped import _legacy_map_view
    from app.scheduler.time_map_overrides import load_time_map_overrides_for_maps

    focus: dict | None = None
    overrides: dict | None = None

    def view_for(map_id: UUID | None):
        nonlocal focus, overrides
        if map_id is None:
            return None
        if focus is None:
            focus = {
                row.id: row
                for row in (
                    db.query(FocusWindow)
                    .options(joinedload(FocusWindow.bands))
                    .filter(FocusWindow.owner_id == owner_id)
                    .all()
                )
            }
            overrides = load_time_map_overrides_for_maps(db, owner_id, set(focus))
        row = focus.get(map_id)
        if row is None or overrides is None:
            return None
        return _legacy_map_view(row, overrides.get(map_id) or ())

    return view_for


def _composition_for_task(
    db: Session,
    *,
    owner_id: UUID,
    task: Task,
    project: Project | None,
    epic: Epic | None,
    policies: dict[UUID, AvailabilityPolicy],
    legacy_view,
):
    comp = _composition()
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

    locals_ordered: list[tuple[str, UUID, UUID | None, object]] = [
        ("task", task.id, task.preferred_time_window_id, task_asg)
    ]
    if project is not None:
        locals_ordered.append(
            ("project", project.id, project.preferred_time_window_id, project_asg)
        )
    if epic is not None:
        locals_ordered.append(
            ("epic", epic.id, epic.preferred_time_window_id, epic_asg)
        )

    winning = None
    for scope, scope_id, map_id, asg in locals_ordered:
        local = local_scope_assignment(
            scope=scope,  # type: ignore[arg-type]
            scope_id=scope_id,
            preferred_time_window_id=map_id,
            assignment=asg,  # type: ignore[arg-type]
        )
        if local.conflict is not None:
            return comp.CompositionInput(
                family=comp.AssignmentFamily.CONFLICT, layers=()
            )
        if local.family == "none":
            continue
        winning = local
        break

    if winning is None:
        return None
    if winning.family == "legacy":
        return comp.CompositionInput(
            family=comp.AssignmentFamily.LEGACY,
            layers=(),
            standing_legacy_map=legacy_view(winning.preferred_time_window_id),
        )

    win_index = next(
        i
        for i, (scope, scope_id, _, _) in enumerate(locals_ordered)
        if scope == winning.scope and scope_id == winning.scope_id
    )
    # Near → far, same order as ``assignment_resolve._resolve_new_rule_stack``.
    # Tesla's ``_ordered_layers`` re-sorts ancestor→child. A legacy ancestor
    # stops the walk so we do not reach through an unconverted map.
    layers = []
    for scope, scope_id, map_id, asg in locals_ordered[win_index:]:
        local = local_scope_assignment(
            scope=scope,  # type: ignore[arg-type]
            scope_id=scope_id,
            preferred_time_window_id=map_id,
            assignment=asg,  # type: ignore[arg-type]
        )
        if local.family == "legacy":
            break
        if local.family != "new_rule" or local.assignment is None:
            continue
        layers.append(
            _layer_for_assignment(
                db,
                owner_id=owner_id,
                scope=scope,
                scope_id=scope_id,
                assignment=local.assignment,
                policies=policies,
            )
        )

    return comp.CompositionInput(
        family=comp.AssignmentFamily.NEW_RULE,
        layers=tuple(layers),
    )


def resolve_new_rule_compositions(
    db: Session,
    owner_id: UUID,
    tasks: list[Task],
    projects: dict[UUID, Project],
    epics: dict[UUID, Epic],
) -> dict[UUID, object]:
    """Tesla collect/fingerprint seam. See ``composition_resolver`` docstring."""
    policies = {
        row.id: row
        for row in (
            db.query(AvailabilityPolicy)
            .options(joinedload(AvailabilityPolicy.windows))
            .filter(AvailabilityPolicy.owner_id == owner_id)
            .all()
        )
    }
    legacy_view = _standing_legacy_views(db, owner_id)
    out: dict[UUID, object] = {}
    for task in tasks:
        if task.owner_id != owner_id:
            continue
        project = projects.get(task.project_id) if task.project_id else None
        epic = None
        if project is not None and project.epic_id is not None:
            epic = epics.get(project.epic_id)
        payload = _composition_for_task(
            db,
            owner_id=owner_id,
            task=task,
            project=project,
            epic=epic,
            policies=policies,
            legacy_view=legacy_view,
        )
        if payload is not None:
            out[task.id] = payload
    scoped = load_day_scoped_declarations(db, owner_id, tasks, projects, epics)
    if not scoped:
        return out
    comp = _composition()
    for task in tasks:
        if task.owner_id != owner_id:
            continue
        rows = scoped.get(task.id) or ()
        if not rows:
            continue
        payload = out.get(task.id)
        if payload is None:
            # No standing assignment. The scoped family still has to reach the
            # placer. Empty layers are absent May (General) outside the lifetime;
            # an inserted replacement closes or replaces that baseline inside it.
            out[task.id] = comp.CompositionInput(
                family=comp.AssignmentFamily.NEW_RULE,
                layers=(),
                day_scoped=tuple(rows),
            )
            continue
        if getattr(payload, "family", None) is None:
            continue
        out[task.id] = replace(
            payload,
            day_scoped=tuple(getattr(payload, "day_scoped", ()) or ()) + tuple(rows),
        )
    return out
