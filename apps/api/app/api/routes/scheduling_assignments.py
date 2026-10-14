# ==============================================================================
#  File: apps/api/app/api/routes/scheduling_assignments.py
#  Description: HTTP surfaces for V4 family replace/clear/revert + named-rule ops.
#  Component: Scheduling / Settings — S2-V4
#  Version: 1.0
#  Created: 2026-10-13
#  Last Update: 2026-10-14 (V4b-D1: JSON-mode rule dumps for scoped writes)
# ==============================================================================

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.models.enums import SchedulingMayPresence, SchedulingRuleKind
from app.models.scheduling_assignment import (
    SchedulingAssignment,
    SchedulingAssignmentRevert,
    SchedulingAssignmentRule,
    SchedulingRuleException,
)
from app.scheduler.assignment_resolve import load_exceptions_at_scope
from app.schemas.scheduling_assignment import (
    AssignmentClearIn,
    AssignmentMutationOut,
    AssignmentRevertIn,
    ClearScopedIn,
    DayChangeSelectedIn,
    DayOnlyAllowIn,
    DayScopedMutationOut,
    DayScopedOpOut,
    FamilyReplaceIn,
    FamilyReplaceScopedIn,
    LocalAssignmentOut,
    MaySpecIn,
    MaySpecOut,
    NewRuleAssignmentWriteIn,
    RevertScopedIn,
    RuleAddIn,
    RuleAddScopedIn,
    RuleExceptionOut,
    RuleMutationOut,
    RuleRemoveNamedIn,
    RuleRemoveNamedScopedIn,
    RuleReplaceNamedIn,
    RuleReplaceNamedScopedIn,
    RuleWaiveNamedIn,
    RuleWaiveNamedScopedIn,
    SchedulingRuleOut,
)
from app.services import scheduling_assignments as svc
from app.services import scheduling_day_scoped as day_svc

ScopeKind = Literal["task", "project", "epic"]

task_router = APIRouter(prefix="/tasks", tags=["scheduling-assignments"])
project_router = APIRouter(prefix="/projects", tags=["scheduling-assignments"])
epic_router = APIRouter(prefix="/epics", tags=["scheduling-assignments"])


def _rule_out(rule: SchedulingAssignmentRule) -> SchedulingRuleOut:
    return SchedulingRuleOut(
        id=rule.id,
        name=rule.name,
        kind=rule.kind.value,  # type: ignore[arg-type]
        policy_id=rule.policy_id,
        empty_set=bool(rule.empty_set),
        sort_order=int(rule.sort_order),
    )


def _exception_out(row: SchedulingRuleException) -> RuleExceptionOut:
    return RuleExceptionOut(
        id=row.id,
        operation=row.operation.value,  # type: ignore[arg-type]
        target_rule_name=row.target_rule_name,
        target_rule_kind=row.target_rule_kind.value,  # type: ignore[arg-type]
        replacement_name=row.replacement_name,
        replacement_policy_id=row.replacement_policy_id,
        replacement_empty_set=bool(row.replacement_empty_set),
    )


def _local_out(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    assignment: SchedulingAssignment | None = None,
) -> LocalAssignmentOut:
    local = svc.read_local_scope(db, user, scope, scope_id)
    asg = assignment if assignment is not None else local.assignment
    may: MaySpecOut | None = None
    must: list[SchedulingRuleOut] = []
    prefer: list[SchedulingRuleOut] = []
    exceptions = [
        _exception_out(row)
        for row in load_exceptions_at_scope(
            db, owner_id=user.id, scope=scope, scope_id=scope_id
        )
    ]
    if asg is not None:
        may_rules = [_rule_out(r) for r in asg.rules if r.kind == SchedulingRuleKind.may]
        must = [_rule_out(r) for r in asg.rules if r.kind == SchedulingRuleKind.must]
        prefer = [_rule_out(r) for r in asg.rules if r.kind == SchedulingRuleKind.prefer]
        if asg.may_presence == SchedulingMayPresence.omit:
            may = MaySpecOut(
                presence="omit",
                rules=[],
                note="Local May omitted — inherit ancestor May, else General.",
            )
        else:
            may = MaySpecOut(
                presence="explicit",
                rules=may_rules,
                note=(
                    "Explicit empty May — no fall-through to General."
                    if not may_rules
                    else "Explicit May sources — union at composition."
                ),
            )
    revert = (
        db.query(SchedulingAssignmentRevert)
        .filter(
            SchedulingAssignmentRevert.owner_id == user.id,
            SchedulingAssignmentRevert.scope_kind == svc._scope_enum(scope),
            SchedulingAssignmentRevert.scope_id == scope_id,
        )
        .one_or_none()
    )
    conflict = None
    if local.conflict is not None:
        conflict = {
            "scope": local.conflict.scope,
            "scope_id": str(local.conflict.scope_id),
            "preferred_time_window_id": str(local.conflict.preferred_time_window_id),
            "assignment_id": str(local.conflict.assignment_id),
            "guidance": local.conflict.guidance,
        }
    return LocalAssignmentOut(
        scope=scope,
        scope_id=scope_id,
        family=local.family,  # type: ignore[arg-type]
        preferred_time_window_id=local.preferred_time_window_id,
        may=may,
        must=must,
        prefer=prefer,
        exceptions=exceptions,
        conflict=conflict,
        revert_replacement_id=revert.id if revert is not None else None,
    )


def _rules_from_write(body: FamilyReplaceIn | NewRuleAssignmentWriteIn) -> list[dict[str, Any]]:
    may = body.may if body.may is not None else MaySpecIn()
    out: list[dict[str, Any]] = []
    if may.presence == "explicit":
        for rule in may.rules:
            # mode=json so UUID/date fields are JSON scalars (scoped JSONB path).
            payload = rule.model_dump(mode="json")
            payload["kind"] = "may"
            out.append(payload)
    for rule in body.must:
        payload = rule.model_dump(mode="json")
        payload["kind"] = "must"
        out.append(payload)
    for rule in body.prefer:
        payload = rule.model_dump(mode="json")
        payload["kind"] = "prefer"
        out.append(payload)
    return out


def _mutation_out(
    db: Session,
    user: User,
    result: dict[str, Any],
) -> AssignmentMutationOut:
    scope: ScopeKind = result["scope"]
    scope_id: UUID = result["scope_id"]
    assignment = result.get("assignment")
    return AssignmentMutationOut(
        scope=scope,
        scope_id=scope_id,
        family=result["family"],
        scheduling_revision=int(result["scheduling_revision"]),
        replacement_id=result.get("replacement_id"),
        restored_replacement_id=result.get("restored_replacement_id"),
        cleared=result.get("cleared"),
        preferred_time_window_id=result.get("preferred_time_window_id"),
        assignment=_local_out(db, user, scope, scope_id, assignment=assignment),
    )


def _do_family_replace(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: FamilyReplaceIn,
) -> AssignmentMutationOut:
    may_presence: Literal["omit", "explicit"] = "omit"
    rules: list[dict[str, Any]] = []
    if body.target_family == "new_rule":
        may = body.may if body.may is not None else MaySpecIn()
        may_presence = may.presence
        rules = _rules_from_write(body)
    result = svc.family_replace(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        target_family=body.target_family,
        expected_revision=body.expected_revision,
        preferred_time_window_id=body.preferred_time_window_id,
        may_presence=may_presence,
        rules=rules,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _mutation_out(db, user, result)


def _do_clear(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: AssignmentClearIn,
) -> AssignmentMutationOut:
    result = svc.clear_assignment(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _mutation_out(db, user, result)


def _do_revert(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: AssignmentRevertIn,
) -> AssignmentMutationOut:
    result = svc.revert_assignment(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        replacement_id=body.replacement_id,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _mutation_out(db, user, result)


def _do_rule_add(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleAddIn,
) -> RuleMutationOut:
    result = svc.rule_add(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        name=body.name,
        kind=body.kind,
        policy_id=body.policy_id,
        empty_set=body.empty_set,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return RuleMutationOut(
        scope=scope,
        scope_id=scope_id,
        scheduling_revision=int(result["scheduling_revision"]),
        rule=_rule_out(result["rule"]),
    )


def _do_rule_replace(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleReplaceNamedIn,
) -> RuleMutationOut:
    result = svc.rule_replace_named(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        target_rule_name=body.target_rule_name,
        target_rule_kind=body.target_rule_kind,
        replacement_name=body.replacement_name,
        policy_id=body.policy_id,
        empty_set=body.empty_set,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return RuleMutationOut(
        scope=scope,
        scope_id=scope_id,
        scheduling_revision=int(result["scheduling_revision"]),
        exception=_exception_out(result["exception"]),
    )


def _do_rule_waive(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleWaiveNamedIn,
) -> RuleMutationOut:
    result = svc.rule_waive_named(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        target_rule_name=body.target_rule_name,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return RuleMutationOut(
        scope=scope,
        scope_id=scope_id,
        scheduling_revision=int(result["scheduling_revision"]),
        exception=_exception_out(result["exception"]),
    )


def _do_rule_remove(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleRemoveNamedIn,
) -> RuleMutationOut:
    """POST …/rules/remove-named — targeted standing-row removal (V4-D4)."""
    result = svc.rule_remove_named(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        operation=body.operation,
        target_rule_name=body.target_rule_name,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    rule_out = _rule_out(result["rule"]) if result.get("rule") is not None else None
    exc_out = (
        _exception_out(result["exception"])
        if result.get("exception") is not None
        else None
    )
    return RuleMutationOut(
        scope=scope,
        scope_id=scope_id,
        scheduling_revision=int(result["scheduling_revision"]),
        rule=rule_out,
        exception=exc_out,
    )


def _do_put_new_rule(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: NewRuleAssignmentWriteIn,
) -> AssignmentMutationOut:
    result = svc.ordinary_new_rule_write(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        may_presence=body.may.presence,
        rules=_rules_from_write(body),
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _mutation_out(db, user, result)


def _day_op_out(raw: dict[str, Any]) -> DayScopedOpOut:
    return DayScopedOpOut(**raw)


def _day_mutation_out(
    db: Session,
    user: User,
    result: dict[str, Any],
) -> DayScopedMutationOut:
    scope: ScopeKind = result["scope"]
    scope_id: UUID = result["scope_id"]
    op_raw = result.get("op_out") or result.get("removed")
    assignment = result.get("assignment")
    return DayScopedMutationOut(
        scope=scope,
        scope_id=scope_id,
        scheduling_revision=int(result["scheduling_revision"]),
        op=_day_op_out(op_raw) if op_raw and result.get("op_out") else None,
        replacement_id=result.get("replacement_id"),
        restored_replacement_id=result.get("restored_replacement_id"),
        cleared_scoped=result.get("cleared_scoped"),
        removed_op_id=result.get("removed_op_id"),
        removed=_day_op_out(result["removed"]) if result.get("removed") else None,
        family=result.get("family"),
        preferred_time_window_id=result.get("preferred_time_window_id"),
        assignment=(
            _local_out(db, user, scope, scope_id, assignment=assignment)
            if assignment is not None or result.get("restored_replacement_id")
            else None
        ),
    )


def _do_day_change(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: DayChangeSelectedIn,
) -> DayScopedMutationOut:
    result = day_svc.day_change_selected(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_day_only_allow(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: DayOnlyAllowIn,
) -> DayScopedMutationOut:
    result = day_svc.day_only_allow(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_family_replace_scoped(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: FamilyReplaceScopedIn,
) -> DayScopedMutationOut:
    may_presence: Literal["omit", "explicit"] = "omit"
    rules: list[dict[str, Any]] = []
    if body.target_family == "new_rule":
        may = body.may if body.may is not None else MaySpecIn()
        may_presence = may.presence
        rules = _rules_from_write(body)
    result = day_svc.family_replace_scoped(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        target_family=body.target_family,
        preferred_time_window_id=body.preferred_time_window_id,
        may_presence=may_presence,
        rules=rules,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_clear_scoped(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: ClearScopedIn,
) -> DayScopedMutationOut:
    result = day_svc.clear_scoped(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_revert_scoped(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RevertScopedIn,
) -> DayScopedMutationOut:
    result = day_svc.revert_scoped(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        replacement_id=body.replacement_id,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_rule_add_scoped(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleAddScopedIn,
) -> DayScopedMutationOut:
    result = day_svc.rule_add_scoped(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        name=body.name,
        kind=body.kind,
        policy_id=body.policy_id,
        empty_set=body.empty_set,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_rule_replace_scoped(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleReplaceNamedScopedIn,
) -> DayScopedMutationOut:
    result = day_svc.rule_replace_named_scoped(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        target_rule_name=body.target_rule_name,
        target_rule_kind=body.target_rule_kind,
        replacement_name=body.replacement_name,
        policy_id=body.policy_id,
        empty_set=body.empty_set,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_rule_waive_scoped(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleWaiveNamedScopedIn,
) -> DayScopedMutationOut:
    result = day_svc.rule_waive_named_scoped(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        target_rule_name=body.target_rule_name,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


def _do_rule_remove_scoped(
    db: Session,
    user: User,
    scope: ScopeKind,
    scope_id: UUID,
    body: RuleRemoveNamedScopedIn,
) -> DayScopedMutationOut:
    result = day_svc.rule_remove_named_scoped(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        expected_revision=body.expected_revision,
        op_id=body.op_id,
        raw_body=body.model_dump(exclude_unset=True),
    )
    db.commit()
    return _day_mutation_out(db, user, result)


# ---- task ----


@task_router.get("/{task_id}/scheduling", response_model=LocalAssignmentOut)
def get_task_scheduling(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LocalAssignmentOut:
    svc._get_scope_entity(db, user, "task", task_id)
    return _local_out(db, user, "task", task_id)


@task_router.put("/{task_id}/scheduling", response_model=AssignmentMutationOut)
def put_task_scheduling(
    task_id: UUID,
    body: NewRuleAssignmentWriteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_put_new_rule(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/assignment/family-replace",
    response_model=AssignmentMutationOut,
)
def task_family_replace(
    task_id: UUID,
    body: FamilyReplaceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_family_replace(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/assignment/clear",
    response_model=AssignmentMutationOut,
)
def task_clear(
    task_id: UUID,
    body: AssignmentClearIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_clear(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/assignment/revert",
    response_model=AssignmentMutationOut,
)
def task_revert(
    task_id: UUID,
    body: AssignmentRevertIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_revert(db, user, "task", task_id, body)


@task_router.post("/{task_id}/scheduling/rules/add", response_model=RuleMutationOut)
def task_rule_add(
    task_id: UUID,
    body: RuleAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_add(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/rules/replace-named",
    response_model=RuleMutationOut,
)
def task_rule_replace(
    task_id: UUID,
    body: RuleReplaceNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_replace(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/rules/waive-named",
    response_model=RuleMutationOut,
)
def task_rule_waive(
    task_id: UUID,
    body: RuleWaiveNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_waive(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/rules/remove-named",
    response_model=RuleMutationOut,
)
def task_rule_remove(
    task_id: UUID,
    body: RuleRemoveNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_remove(db, user, "task", task_id, body)


@task_router.get(
    "/{task_id}/scheduling/day-scoped",
    response_model=list[DayScopedOpOut],
)
def task_list_day_scoped(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DayScopedOpOut]:
    return [
        DayScopedOpOut(**row)
        for row in day_svc.list_day_scoped_ops(
            db, user, scope="task", scope_id=task_id
        )
    ]


@task_router.post(
    "/{task_id}/scheduling/day/change-selected",
    response_model=DayScopedMutationOut,
)
def task_day_change(
    task_id: UUID,
    body: DayChangeSelectedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_day_change(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/day/only-allow",
    response_model=DayScopedMutationOut,
)
def task_day_only_allow(
    task_id: UUID,
    body: DayOnlyAllowIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_day_only_allow(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/assignment/family-replace-scoped",
    response_model=DayScopedMutationOut,
)
def task_family_replace_scoped(
    task_id: UUID,
    body: FamilyReplaceScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_family_replace_scoped(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/assignment/clear-scoped",
    response_model=DayScopedMutationOut,
)
def task_clear_scoped(
    task_id: UUID,
    body: ClearScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_clear_scoped(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/assignment/revert-scoped",
    response_model=DayScopedMutationOut,
)
def task_revert_scoped(
    task_id: UUID,
    body: RevertScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_revert_scoped(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/rules/add-scoped",
    response_model=DayScopedMutationOut,
)
def task_rule_add_scoped(
    task_id: UUID,
    body: RuleAddScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_add_scoped(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/rules/replace-named-scoped",
    response_model=DayScopedMutationOut,
)
def task_rule_replace_scoped(
    task_id: UUID,
    body: RuleReplaceNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_replace_scoped(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/rules/waive-named-scoped",
    response_model=DayScopedMutationOut,
)
def task_rule_waive_scoped(
    task_id: UUID,
    body: RuleWaiveNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_waive_scoped(db, user, "task", task_id, body)


@task_router.post(
    "/{task_id}/scheduling/rules/remove-named-scoped",
    response_model=DayScopedMutationOut,
)
def task_rule_remove_scoped(
    task_id: UUID,
    body: RuleRemoveNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_remove_scoped(db, user, "task", task_id, body)


# ---- project ----


@project_router.get("/{project_id}/scheduling", response_model=LocalAssignmentOut)
def get_project_scheduling(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LocalAssignmentOut:
    svc._get_scope_entity(db, user, "project", project_id)
    return _local_out(db, user, "project", project_id)


@project_router.put("/{project_id}/scheduling", response_model=AssignmentMutationOut)
def put_project_scheduling(
    project_id: UUID,
    body: NewRuleAssignmentWriteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_put_new_rule(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/assignment/family-replace",
    response_model=AssignmentMutationOut,
)
def project_family_replace(
    project_id: UUID,
    body: FamilyReplaceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_family_replace(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/assignment/clear",
    response_model=AssignmentMutationOut,
)
def project_clear(
    project_id: UUID,
    body: AssignmentClearIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_clear(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/assignment/revert",
    response_model=AssignmentMutationOut,
)
def project_revert(
    project_id: UUID,
    body: AssignmentRevertIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_revert(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/add", response_model=RuleMutationOut
)
def project_rule_add(
    project_id: UUID,
    body: RuleAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_add(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/replace-named",
    response_model=RuleMutationOut,
)
def project_rule_replace(
    project_id: UUID,
    body: RuleReplaceNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_replace(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/waive-named",
    response_model=RuleMutationOut,
)
def project_rule_waive(
    project_id: UUID,
    body: RuleWaiveNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_waive(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/remove-named",
    response_model=RuleMutationOut,
)
def project_rule_remove(
    project_id: UUID,
    body: RuleRemoveNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_remove(db, user, "project", project_id, body)


@project_router.get(
    "/{project_id}/scheduling/day-scoped",
    response_model=list[DayScopedOpOut],
)
def project_list_day_scoped(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DayScopedOpOut]:
    return [
        DayScopedOpOut(**row)
        for row in day_svc.list_day_scoped_ops(
            db, user, scope="project", scope_id=project_id
        )
    ]


@project_router.post(
    "/{project_id}/scheduling/day/change-selected",
    response_model=DayScopedMutationOut,
)
def project_day_change(
    project_id: UUID,
    body: DayChangeSelectedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_day_change(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/day/only-allow",
    response_model=DayScopedMutationOut,
)
def project_day_only_allow(
    project_id: UUID,
    body: DayOnlyAllowIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_day_only_allow(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/assignment/family-replace-scoped",
    response_model=DayScopedMutationOut,
)
def project_family_replace_scoped(
    project_id: UUID,
    body: FamilyReplaceScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_family_replace_scoped(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/assignment/clear-scoped",
    response_model=DayScopedMutationOut,
)
def project_clear_scoped(
    project_id: UUID,
    body: ClearScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_clear_scoped(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/assignment/revert-scoped",
    response_model=DayScopedMutationOut,
)
def project_revert_scoped(
    project_id: UUID,
    body: RevertScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_revert_scoped(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/add-scoped",
    response_model=DayScopedMutationOut,
)
def project_rule_add_scoped(
    project_id: UUID,
    body: RuleAddScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_add_scoped(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/replace-named-scoped",
    response_model=DayScopedMutationOut,
)
def project_rule_replace_scoped(
    project_id: UUID,
    body: RuleReplaceNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_replace_scoped(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/waive-named-scoped",
    response_model=DayScopedMutationOut,
)
def project_rule_waive_scoped(
    project_id: UUID,
    body: RuleWaiveNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_waive_scoped(db, user, "project", project_id, body)


@project_router.post(
    "/{project_id}/scheduling/rules/remove-named-scoped",
    response_model=DayScopedMutationOut,
)
def project_rule_remove_scoped(
    project_id: UUID,
    body: RuleRemoveNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_remove_scoped(db, user, "project", project_id, body)


# ---- epic ----


@epic_router.get("/{epic_id}/scheduling", response_model=LocalAssignmentOut)
def get_epic_scheduling(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LocalAssignmentOut:
    svc._get_scope_entity(db, user, "epic", epic_id)
    return _local_out(db, user, "epic", epic_id)


@epic_router.put("/{epic_id}/scheduling", response_model=AssignmentMutationOut)
def put_epic_scheduling(
    epic_id: UUID,
    body: NewRuleAssignmentWriteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_put_new_rule(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/assignment/family-replace",
    response_model=AssignmentMutationOut,
)
def epic_family_replace(
    epic_id: UUID,
    body: FamilyReplaceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_family_replace(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/assignment/clear",
    response_model=AssignmentMutationOut,
)
def epic_clear(
    epic_id: UUID,
    body: AssignmentClearIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_clear(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/assignment/revert",
    response_model=AssignmentMutationOut,
)
def epic_revert(
    epic_id: UUID,
    body: AssignmentRevertIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssignmentMutationOut:
    return _do_revert(db, user, "epic", epic_id, body)


@epic_router.post("/{epic_id}/scheduling/rules/add", response_model=RuleMutationOut)
def epic_rule_add(
    epic_id: UUID,
    body: RuleAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_add(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/rules/replace-named",
    response_model=RuleMutationOut,
)
def epic_rule_replace(
    epic_id: UUID,
    body: RuleReplaceNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_replace(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/rules/waive-named",
    response_model=RuleMutationOut,
)
def epic_rule_waive(
    epic_id: UUID,
    body: RuleWaiveNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_waive(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/rules/remove-named",
    response_model=RuleMutationOut,
)
def epic_rule_remove(
    epic_id: UUID,
    body: RuleRemoveNamedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleMutationOut:
    return _do_rule_remove(db, user, "epic", epic_id, body)


@epic_router.get(
    "/{epic_id}/scheduling/day-scoped",
    response_model=list[DayScopedOpOut],
)
def epic_list_day_scoped(
    epic_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DayScopedOpOut]:
    return [
        DayScopedOpOut(**row)
        for row in day_svc.list_day_scoped_ops(
            db, user, scope="epic", scope_id=epic_id
        )
    ]


@epic_router.post(
    "/{epic_id}/scheduling/day/change-selected",
    response_model=DayScopedMutationOut,
)
def epic_day_change(
    epic_id: UUID,
    body: DayChangeSelectedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_day_change(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/day/only-allow",
    response_model=DayScopedMutationOut,
)
def epic_day_only_allow(
    epic_id: UUID,
    body: DayOnlyAllowIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_day_only_allow(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/assignment/family-replace-scoped",
    response_model=DayScopedMutationOut,
)
def epic_family_replace_scoped(
    epic_id: UUID,
    body: FamilyReplaceScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_family_replace_scoped(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/assignment/clear-scoped",
    response_model=DayScopedMutationOut,
)
def epic_clear_scoped(
    epic_id: UUID,
    body: ClearScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_clear_scoped(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/assignment/revert-scoped",
    response_model=DayScopedMutationOut,
)
def epic_revert_scoped(
    epic_id: UUID,
    body: RevertScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_revert_scoped(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/rules/add-scoped",
    response_model=DayScopedMutationOut,
)
def epic_rule_add_scoped(
    epic_id: UUID,
    body: RuleAddScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_add_scoped(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/rules/replace-named-scoped",
    response_model=DayScopedMutationOut,
)
def epic_rule_replace_scoped(
    epic_id: UUID,
    body: RuleReplaceNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_replace_scoped(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/rules/waive-named-scoped",
    response_model=DayScopedMutationOut,
)
def epic_rule_waive_scoped(
    epic_id: UUID,
    body: RuleWaiveNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_waive_scoped(db, user, "epic", epic_id, body)


@epic_router.post(
    "/{epic_id}/scheduling/rules/remove-named-scoped",
    response_model=DayScopedMutationOut,
)
def epic_rule_remove_scoped(
    epic_id: UUID,
    body: RuleRemoveNamedScopedIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayScopedMutationOut:
    return _do_rule_remove_scoped(db, user, "epic", epic_id, body)
