# ==============================================================================
#  File: apps/api/app/services/scheduling_assignments.py
#  Description: Owner-scoped V4 assignment/exception writers (family replace/clear/revert).
#  Component: Scheduling / Settings — S2-V4
#  Version: 1.0
#  Created: 2026-10-13
#  Last Update: 2026-10-14 (V4b: split deferred temporal vs V7 context key sets)
# ==============================================================================

"""Assignment writers. Paths are engineering; stubs match Discovery §2.1 labels.

Named-rule HTTP/CLI: ``add``, ``replace-named``, ``waive-named``, ``remove-named``.
``remove-named`` deletes one standing addition or exception row and restores that
named underlying rule; it is not a ``SchedulingExceptionOp`` value.

Standing writers call ``reject_deferred_exception_forms`` (default) so V4b
temporal selectors and V7 context keys reject with no write. Day-scoped writers
live in ``scheduling_day_scoped`` and flip only the temporal set.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.models import AvailabilityPolicy, Epic, FocusWindow, Project, Task, User
from app.models.enums import (
    SchedulingAssignmentFamily,
    SchedulingExceptionOp,
    SchedulingMayPresence,
    SchedulingRuleKind,
    SchedulingScopeKind,
)
from app.models.scheduling_assignment import (
    SchedulingAssignment,
    SchedulingAssignmentRevert,
    SchedulingAssignmentRule,
    SchedulingRuleException,
)
from app.scheduler.assignment_resolve import (
    LocalScopeAssignment,
    load_assignment_at_scope,
    load_exceptions_at_scope,
    local_scope_assignment,
)
from app.services.scheduling_revision import (
    assert_scheduling_revision,
    increment_scheduling_revision,
    lock_owner_scheduling,
)

ScopeKind = Literal["task", "project", "epic"]

FAMILY_COLLISION_CODE = "SCHEDULING_FAMILY_COLLISION"
DEFERRED_FORM_CODE = "SCHEDULING_EXCEPTION_FORM_DEFERRED"
LEGACY_NAMED_RULE_CODE = "NAMED_RULE_REQUIRES_NEW_RULE_FAMILY"
REVERT_UNUSABLE_CODE = "SCHEDULING_REVERT_UNUSABLE_PRIOR"
REVERT_MISSING_CODE = "SCHEDULING_REVERT_NOT_AVAILABLE"
REVERT_MISMATCH_CODE = "SCHEDULING_REVERT_MISMATCH"

# V4b-authorized temporal / selector keys (standing writers still reject).
# Context stays V7 — do not merge into this set.
V4B_TEMPORAL_FORM_KEYS = frozenset(
    {
        "date_range",
        "local_start_date",
        "local_end_date",
        "on_date",
        "on",
        "weekday",
        "weekdays",
        "days_of_week",
        "expiry",
        "expires_on",
        "expires_at",
        "selector",
    }
)
# V7 — always reject on every writer path that uses this helper.
V7_CONTEXT_FORM_KEYS = frozenset(
    {
        "context",
        "context_id",
        "context_slug",
    }
)
# Back-compat alias: standing reject set = temporal ∪ context.
_DEFERRED_FORM_KEYS = V4B_TEMPORAL_FORM_KEYS | V7_CONTEXT_FORM_KEYS
_FORBIDDEN_FORM_KEYS = frozenset(
    {
        "ignore_all",
        "ignore_all_restrictions",
        "ignore_restrictions",
    }
)

_COLLISION_GUIDANCE = (
    "This scope already has an active assignment from the other family. "
    "Use POST …/scheduling/assignment/family-replace with expected_revision to "
    "switch families (preserves revert payload), or clear the current local "
    "assignment first. Ordinary writes do not merge families."
)


def reject_deferred_exception_forms(
    payload: dict[str, Any] | None,
    *,
    allow_v4b_temporal: bool = False,
) -> None:
    """Reject unauthorized exception forms with no write.

    Key sets are split on purpose (Discovery §12.3):

    - **Forbidden** ignore-all — always reject (SPEC §4.4).
    - **V7 context** — always reject; never flipped with V4b temporal keys.
    - **V4b temporal / selector** — reject on standing writers
      (``allow_v4b_temporal=False``). Authorized day-scoped writers pass
      ``allow_v4b_temporal=True`` and validate the selector themselves.
    """
    if not payload:
        return
    forbidden = sorted(_FORBIDDEN_FORM_KEYS.intersection(payload))
    if forbidden:
        raise ApiError(
            422,
            "Ignore-all-restrictions is not a scheduling exception and is not "
            "writable. Saved configuration is unchanged.",
            "SCHEDULING_EXCEPTION_FORBIDDEN",
            rejected_fields=forbidden,
        )
    context_hit = sorted(V7_CONTEXT_FORM_KEYS.intersection(payload))
    if context_hit:
        raise ApiError(
            422,
            "Context-scoped scheduling exception forms are not writable "
            "(deferred to V7). Saved configuration is unchanged.",
            DEFERRED_FORM_CODE,
            rejected_fields=context_hit,
            deferred_to="V7",
        )
    if allow_v4b_temporal:
        return
    temporal_hit = sorted(V4B_TEMPORAL_FORM_KEYS.intersection(payload))
    if not temporal_hit:
        return
    raise ApiError(
        422,
        "Date-range, weekday-standing, and expiry selectors are not writable "
        "on standing assignment writers. Use the day-scoped V4b endpoints. "
        "Saved configuration is unchanged.",
        DEFERRED_FORM_CODE,
        rejected_fields=temporal_hit,
        deferred_to="V4b",
    )


def _scope_enum(scope: ScopeKind) -> SchedulingScopeKind:
    return SchedulingScopeKind(scope)


def _get_scope_entity(
    db: Session, user: User, scope: ScopeKind, scope_id: UUID
) -> Task | Project | Epic:
    if scope == "task":
        entity = db.get(Task, scope_id)
        if entity is None or entity.owner_id != user.id or entity.deleted_at is not None:
            raise ApiError(404, "Task not found", "NOT_FOUND")
        return entity
    if scope == "project":
        entity = db.get(Project, scope_id)
        if entity is None or entity.owner_id != user.id:
            raise ApiError(404, "Project not found", "NOT_FOUND")
        return entity
    entity = db.get(Epic, scope_id)
    if entity is None or entity.owner_id != user.id:
        raise ApiError(404, "Epic not found", "NOT_FOUND")
    return entity


def _legacy_window_id(entity: Task | Project | Epic) -> UUID | None:
    return entity.preferred_time_window_id


def _set_legacy_window_id(entity: Task | Project | Epic, value: UUID | None) -> None:
    entity.preferred_time_window_id = value


def read_local_scope(
    db: Session, user: User, scope: ScopeKind, scope_id: UUID
) -> LocalScopeAssignment:
    entity = _get_scope_entity(db, user, scope, scope_id)
    assignment = load_assignment_at_scope(
        db, owner_id=user.id, scope=scope, scope_id=scope_id
    )
    return local_scope_assignment(
        scope=scope,
        scope_id=scope_id,
        preferred_time_window_id=_legacy_window_id(entity),
        assignment=assignment,
    )


def assert_no_family_collision_for_legacy_write(
    db: Session,
    *,
    owner_id: UUID,
    scope: ScopeKind,
    scope_id: UUID,
    new_preferred_time_window_id: UUID | None,
) -> None:
    """Legacy preferred_time_window_id writers participate in collision checks.

    Setting a non-null map (or keeping one) while a new-rule assignment exists
    at the same scope rejects atomically. Clearing the map to null while a
    new-rule row exists is allowed (repairs both-active).
    """
    assignment = load_assignment_at_scope(
        db, owner_id=owner_id, scope=scope, scope_id=scope_id
    )
    if assignment is None:
        return
    if new_preferred_time_window_id is None:
        return
    raise ApiError(
        409,
        _COLLISION_GUIDANCE,
        FAMILY_COLLISION_CODE,
        scope=scope,
        scope_id=str(scope_id),
        current_family="new_rule",
        attempted_family="legacy",
        guidance="POST /api/v1/{scope}s/{id}/scheduling/assignment/family-replace",
    )


def _verify_owned_policy(
    db: Session, user: User, policy_id: UUID
) -> AvailabilityPolicy:
    policy = db.get(AvailabilityPolicy, policy_id)
    if policy is None or policy.owner_id != user.id:
        raise ApiError(
            422,
            "Availability policy not found for this owner",
            "AVAILABILITY_POLICY_NOT_FOUND",
            policy_id=str(policy_id),
        )
    return policy


def _verify_owned_focus_window(db: Session, user: User, window_id: UUID) -> FocusWindow:
    window = db.get(FocusWindow, window_id)
    if window is None or window.owner_id != user.id:
        raise ApiError(
            422,
            "Time Map not found for this owner",
            "FOCUS_WINDOW_NOT_FOUND",
            preferred_time_window_id=str(window_id),
        )
    return window


def _snapshot_new_rule(
    assignment: SchedulingAssignment,
    exceptions: list[SchedulingRuleException],
) -> dict[str, Any]:
    return {
        "may_presence": assignment.may_presence.value,
        "rules": [
            {
                "name": rule.name,
                "kind": rule.kind.value,
                "policy_id": str(rule.policy_id) if rule.policy_id else None,
                "empty_set": bool(rule.empty_set),
                "sort_order": int(rule.sort_order),
            }
            for rule in assignment.rules
        ],
        "exceptions": [
            {
                "operation": exc.operation.value,
                "target_rule_name": exc.target_rule_name,
                "target_rule_kind": exc.target_rule_kind.value,
                "replacement_name": exc.replacement_name,
                "replacement_policy_id": (
                    str(exc.replacement_policy_id) if exc.replacement_policy_id else None
                ),
                "replacement_empty_set": bool(exc.replacement_empty_set),
            }
            for exc in exceptions
        ],
    }


def _delete_new_rule_at_scope(
    db: Session, *, owner_id: UUID, scope: ScopeKind, scope_id: UUID
) -> None:
    assignment = load_assignment_at_scope(
        db, owner_id=owner_id, scope=scope, scope_id=scope_id
    )
    if assignment is not None:
        db.delete(assignment)
    for exc in load_exceptions_at_scope(
        db, owner_id=owner_id, scope=scope, scope_id=scope_id
    ):
        db.delete(exc)
    db.flush()


def _store_revert(
    db: Session,
    *,
    owner_id: UUID,
    scope: ScopeKind,
    scope_id: UUID,
    prior_family: SchedulingAssignmentFamily,
    prior_preferred_time_window_id: UUID | None,
    prior_new_rule_payload: dict[str, Any] | None,
) -> SchedulingAssignmentRevert:
    existing = (
        db.query(SchedulingAssignmentRevert)
        .filter(
            SchedulingAssignmentRevert.scope_kind == _scope_enum(scope),
            SchedulingAssignmentRevert.scope_id == scope_id,
        )
        .one_or_none()
    )
    if existing is not None:
        db.delete(existing)
        db.flush()
    row = SchedulingAssignmentRevert(
        id=uuid4(),
        owner_id=owner_id,
        scope_kind=_scope_enum(scope),
        scope_id=scope_id,
        prior_family=prior_family,
        prior_preferred_time_window_id=prior_preferred_time_window_id,
        prior_new_rule_payload=prior_new_rule_payload,
    )
    db.add(row)
    db.flush()
    return row


def _build_rules(
    db: Session,
    user: User,
    assignment: SchedulingAssignment,
    rules_in: list[dict[str, Any]],
) -> None:
    for index, raw in enumerate(rules_in):
        name = str(raw.get("name") or "").strip()
        if not name:
            raise ApiError(422, "Rule name is required", "RULE_NAME_REQUIRED")
        kind = SchedulingRuleKind(str(raw["kind"]))
        empty_set = bool(raw.get("empty_set") or raw.get("empty"))
        policy_id_raw = raw.get("policy_id")
        policy_id: UUID | None = None
        if empty_set:
            if policy_id_raw is not None:
                raise ApiError(
                    422,
                    "empty_set rules must not include policy_id",
                    "RULE_EMPTY_WITH_POLICY",
                )
        else:
            if policy_id_raw is None:
                raise ApiError(
                    422,
                    "Non-empty rules require policy_id",
                    "RULE_POLICY_REQUIRED",
                )
            policy_id = UUID(str(policy_id_raw))
            _verify_owned_policy(db, user, policy_id)
        db.add(
            SchedulingAssignmentRule(
                id=uuid4(),
                assignment_id=assignment.id,
                owner_id=user.id,
                name=name,
                kind=kind,
                policy_id=policy_id,
                empty_set=empty_set,
                sort_order=index if raw.get("sort_order") is None else int(raw["sort_order"]),
            )
        )
    db.flush()


def _create_new_rule_assignment(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    may_presence: SchedulingMayPresence,
    rules_in: list[dict[str, Any]],
) -> SchedulingAssignment:
    assignment = SchedulingAssignment(
        id=uuid4(),
        owner_id=user.id,
        scope_kind=_scope_enum(scope),
        scope_id=scope_id,
        may_presence=may_presence,
    )
    db.add(assignment)
    db.flush()
    _build_rules(db, user, assignment, rules_in)
    return (
        db.query(SchedulingAssignment)
        .options(joinedload(SchedulingAssignment.rules))
        .filter(SchedulingAssignment.id == assignment.id)
        .one()
    )


def _restore_new_rule_payload(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    payload: dict[str, Any],
) -> SchedulingAssignment:
    may_presence = SchedulingMayPresence(str(payload.get("may_presence", "omit")))
    rules_in = list(payload.get("rules") or [])
    assignment = _create_new_rule_assignment(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        may_presence=may_presence,
        rules_in=rules_in,
    )
    for raw in list(payload.get("exceptions") or []):
        op = SchedulingExceptionOp(str(raw["operation"]))
        replacement_policy_id = None
        if raw.get("replacement_policy_id"):
            replacement_policy_id = UUID(str(raw["replacement_policy_id"]))
            _verify_owned_policy(db, user, replacement_policy_id)
        db.add(
            SchedulingRuleException(
                id=uuid4(),
                owner_id=user.id,
                scope_kind=_scope_enum(scope),
                scope_id=scope_id,
                operation=op,
                target_rule_name=str(raw["target_rule_name"]),
                target_rule_kind=SchedulingRuleKind(str(raw["target_rule_kind"])),
                replacement_name=raw.get("replacement_name"),
                replacement_policy_id=replacement_policy_id,
                replacement_empty_set=bool(raw.get("replacement_empty_set")),
            )
        )
    db.flush()
    return assignment


def family_replace(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    target_family: Literal["legacy", "new_rule", "none"],
    expected_revision: int,
    preferred_time_window_id: UUID | None = None,
    may_presence: Literal["omit", "explicit"] = "omit",
    rules: list[dict[str, Any]] | None = None,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explicit family switch; preserves prior local state for revert (V4-P1)."""
    reject_deferred_exception_forms(raw_body)
    entity = _get_scope_entity(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    current = read_local_scope(db, user, scope, scope_id)
    prior_family = SchedulingAssignmentFamily(current.family)
    prior_map = current.preferred_time_window_id
    prior_payload: dict[str, Any] | None = None
    if current.assignment is not None:
        prior_payload = _snapshot_new_rule(
            current.assignment,
            load_exceptions_at_scope(
                db, owner_id=user.id, scope=scope, scope_id=scope_id
            ),
        )

    revert = _store_revert(
        db,
        owner_id=user.id,
        scope=scope,
        scope_id=scope_id,
        prior_family=prior_family,
        prior_preferred_time_window_id=prior_map,
        prior_new_rule_payload=prior_payload,
    )

    # Clear both local stores, then apply target.
    _set_legacy_window_id(entity, None)
    _delete_new_rule_at_scope(db, owner_id=user.id, scope=scope, scope_id=scope_id)

    assignment_out: SchedulingAssignment | None = None
    if target_family == "legacy":
        if preferred_time_window_id is None:
            raise ApiError(
                422,
                "family-replace to legacy requires preferred_time_window_id",
                "LEGACY_MAP_REQUIRED",
            )
        _verify_owned_focus_window(db, user, preferred_time_window_id)
        _set_legacy_window_id(entity, preferred_time_window_id)
    elif target_family == "new_rule":
        assignment_out = _create_new_rule_assignment(
            db,
            user,
            scope=scope,
            scope_id=scope_id,
            may_presence=SchedulingMayPresence(may_presence),
            rules_in=list(rules or []),
        )
    # target none: left cleared

    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "family": target_family,
        "replacement_id": revert.id,
        "scheduling_revision": revision,
        "assignment": assignment_out,
        "preferred_time_window_id": _legacy_window_id(entity),
    }


def clear_assignment(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove current local assignment; does not restore displaced prior (V4-P2)."""
    reject_deferred_exception_forms(raw_body)
    entity = _get_scope_entity(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    current = read_local_scope(db, user, scope, scope_id)
    if current.family == "none" and current.conflict is None:
        raise ApiError(
            422,
            "No local scheduling assignment to clear at this scope",
            "NO_LOCAL_ASSIGNMENT",
            scope=scope,
            scope_id=str(scope_id),
        )

    _set_legacy_window_id(entity, None)
    _delete_new_rule_at_scope(db, owner_id=user.id, scope=scope, scope_id=scope_id)
    # Revert payload from a prior replace is intentionally left alone.
    revision = increment_scheduling_revision(db, settings)
    return {
        "scope": scope,
        "scope_id": scope_id,
        "family": "none",
        "cleared": True,
        "scheduling_revision": revision,
    }


def revert_assignment(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    replacement_id: UUID,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Restore prior local state captured by one identified replace (V4-P2)."""
    reject_deferred_exception_forms(raw_body)
    entity = _get_scope_entity(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    revert = (
        db.query(SchedulingAssignmentRevert)
        .filter(
            SchedulingAssignmentRevert.scope_kind == _scope_enum(scope),
            SchedulingAssignmentRevert.scope_id == scope_id,
            SchedulingAssignmentRevert.owner_id == user.id,
        )
        .one_or_none()
    )
    if revert is None:
        raise ApiError(
            422,
            "No identified family-replace revert payload at this scope",
            REVERT_MISSING_CODE,
            scope=scope,
            scope_id=str(scope_id),
            repair="Perform an explicit family-replace before revert, or clear and re-assign.",
        )
    if revert.id != replacement_id:
        raise ApiError(
            409,
            "replacement_id does not match the captured revert at this scope",
            REVERT_MISMATCH_CODE,
            expected_replacement_id=str(revert.id),
            provided_replacement_id=str(replacement_id),
        )

    if revert.prior_family == SchedulingAssignmentFamily.legacy:
        if revert.prior_preferred_time_window_id is None:
            raise ApiError(
                422,
                "Prior legacy Time Map is missing or was deleted; choose a repair "
                "instead of silent fallback",
                REVERT_UNUSABLE_CODE,
                repair="Clear, pick another map, or family-replace to new_rule.",
            )
        try:
            _verify_owned_focus_window(db, user, revert.prior_preferred_time_window_id)
        except ApiError as exc:
            raise ApiError(
                422,
                "Prior legacy Time Map is no longer usable for this owner",
                REVERT_UNUSABLE_CODE,
                repair="Clear, pick another map, or family-replace to new_rule.",
                cause=exc.content.get("code"),
            ) from exc

    if revert.prior_family == SchedulingAssignmentFamily.new_rule:
        payload = revert.prior_new_rule_payload
        if not isinstance(payload, dict):
            raise ApiError(
                422,
                "Prior new-rule payload is missing or unusable",
                REVERT_UNUSABLE_CODE,
                repair="Clear and re-assign, or family-replace fresh.",
            )
        for rule in list(payload.get("rules") or []):
            if rule.get("empty_set") or rule.get("policy_id") is None:
                continue
            try:
                _verify_owned_policy(db, user, UUID(str(rule["policy_id"])))
            except ApiError as exc:
                raise ApiError(
                    422,
                    "Prior new-rule references a removed or foreign policy",
                    REVERT_UNUSABLE_CODE,
                    repair="Clear and re-assign with current policies.",
                    cause=exc.content.get("code"),
                ) from exc

    # Apply restore: wipe current local, then write prior.
    _set_legacy_window_id(entity, None)
    _delete_new_rule_at_scope(db, owner_id=user.id, scope=scope, scope_id=scope_id)

    assignment_out: SchedulingAssignment | None = None
    if revert.prior_family == SchedulingAssignmentFamily.legacy:
        _set_legacy_window_id(entity, revert.prior_preferred_time_window_id)
    elif revert.prior_family == SchedulingAssignmentFamily.new_rule:
        assert isinstance(revert.prior_new_rule_payload, dict)
        assignment_out = _restore_new_rule_payload(
            db,
            user,
            scope=scope,
            scope_id=scope_id,
            payload=revert.prior_new_rule_payload,
        )

    db.delete(revert)
    revision = increment_scheduling_revision(db, settings)
    return {
        "scope": scope,
        "scope_id": scope_id,
        "family": revert.prior_family.value,
        "restored_replacement_id": replacement_id,
        "scheduling_revision": revision,
        "assignment": assignment_out,
        "preferred_time_window_id": _legacy_window_id(entity),
    }


def _require_new_rule_family(
    db: Session, user: User, scope: ScopeKind, scope_id: UUID
) -> tuple[Task | Project | Epic, SchedulingAssignment]:
    entity = _get_scope_entity(db, user, scope, scope_id)
    local = read_local_scope(db, user, scope, scope_id)
    if local.family != "new_rule" or local.assignment is None:
        raise ApiError(
            422,
            "Named-rule operations require an active new-rule assignment at this "
            "scope. On a legacy Time Map assignment they reject with no write. "
            "Switch family with family-replace first.",
            LEGACY_NAMED_RULE_CODE,
            scope=scope,
            scope_id=str(scope_id),
            current_family=local.family,
        )
    return entity, local.assignment


def rule_add(
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
    reject_deferred_exception_forms(raw_body)
    _entity, assignment = _require_new_rule_family(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    clean_name = name.strip()
    if not clean_name:
        raise ApiError(422, "Rule name is required", "RULE_NAME_REQUIRED")
    existing = (
        db.query(SchedulingAssignmentRule)
        .filter(
            SchedulingAssignmentRule.assignment_id == assignment.id,
            SchedulingAssignmentRule.name == clean_name,
        )
        .one_or_none()
    )
    if existing is not None:
        raise ApiError(
            409,
            f"A rule named '{clean_name}' already exists on this assignment",
            "RULE_NAME_CONFLICT",
        )

    if kind == "may" and assignment.may_presence == SchedulingMayPresence.omit:
        # Adding a May rule implies explicit local May (union with inherited until
        # presence flips — presence becomes explicit so empty-vs-omit stays honest).
        assignment.may_presence = SchedulingMayPresence.explicit

    resolved_policy: UUID | None = None
    if empty_set:
        if policy_id is not None:
            raise ApiError(
                422,
                "empty_set rules must not include policy_id",
                "RULE_EMPTY_WITH_POLICY",
            )
    else:
        if policy_id is None:
            raise ApiError(422, "policy_id is required", "RULE_POLICY_REQUIRED")
        _verify_owned_policy(db, user, policy_id)
        resolved_policy = policy_id

    sort_order = len(assignment.rules)
    rule = SchedulingAssignmentRule(
        id=uuid4(),
        assignment_id=assignment.id,
        owner_id=user.id,
        name=clean_name,
        kind=SchedulingRuleKind(kind),
        policy_id=resolved_policy,
        empty_set=empty_set,
        sort_order=sort_order,
    )
    db.add(rule)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "rule": rule,
        "scheduling_revision": revision,
    }


def _raise_replacement_name_conflict(
    *,
    scope: ScopeKind,
    scope_id: UUID,
    replacement_name: str,
    target_rule_name: str,
    occupant: str,
) -> None:
    """V4-D2. Reuses rule_add's ``RULE_NAME_CONFLICT`` (no new code).

    The replacement output would occupy a sibling identity at this scope.
    §2.1 replaces the targeted rule only; siblings stay.
    """
    raise ApiError(
        409,
        (
            f"Replacement name '{replacement_name}' collides with {occupant} at "
            f"this scope. Named replacement changes only '{target_rule_name}'; "
            f"siblings stay. Choose a different replacement name, or remove "
            f"the sibling first."
        ),
        "RULE_NAME_CONFLICT",
        scope=scope,
        scope_id=str(scope_id),
        replacement_name=replacement_name,
        target_rule_name=target_rule_name,
    )


def _near_ancestors(
    db: Session,
    user: User,
    scope: ScopeKind,
    entity: Task | Project | Epic,
) -> list[tuple[ScopeKind, UUID]]:
    """Ancestor scopes, nearest first. The writing scope is not included."""
    found: list[tuple[ScopeKind, UUID]] = []
    if scope == "task":
        assert isinstance(entity, Task)
        if entity.project_id is None:
            return found
        project = db.get(Project, entity.project_id)
        if project is None or project.owner_id != user.id:
            return found
        found.append(("project", project.id))
        if project.epic_id is None:
            return found
        epic = db.get(Epic, project.epic_id)
        if epic is None or epic.owner_id != user.id:
            return found
        found.append(("epic", epic.id))
        return found
    if scope == "project":
        assert isinstance(entity, Project)
        if entity.epic_id is None:
            return found
        epic = db.get(Epic, entity.epic_id)
        if epic is None or epic.owner_id != user.id:
            return found
        found.append(("epic", epic.id))
    return found


def _inherited_same_kind_name(
    db: Session,
    user: User,
    ancestors: list[tuple[ScopeKind, UUID]],
    *,
    kind: SchedulingRuleKind,
    name: str,
) -> bool:
    """True when a farther new-rule layer still exposes this kind and name.

    Stops at a legacy (or conflicted) ancestor, matching composition's chain.
    Raw rules and replace-named outputs both count. A waiver that would hide
    the row still counts, so the in-place exemption stays strict.
    """
    for ancestor_scope, ancestor_id in ancestors:
        local = read_local_scope(db, user, ancestor_scope, ancestor_id)
        if local.conflict is not None or local.family == "legacy":
            break
        if local.family != "new_rule" or local.assignment is None:
            continue
        if any(rule.kind == kind and rule.name == name for rule in local.assignment.rules):
            return True
        for exc in load_exceptions_at_scope(
            db, owner_id=user.id, scope=ancestor_scope, scope_id=ancestor_id
        ):
            if (
                exc.operation == SchedulingExceptionOp.replace_named
                and exc.target_rule_kind == kind
                and exc.replacement_name == name
            ):
                return True
    return False


def _reject_replacement_output_collision(
    db: Session,
    user: User,
    *,
    entity: Task | Project | Epic,
    assignment: SchedulingAssignment,
    scope: ScopeKind,
    scope_id: UUID,
    target_rule_name: str,
    target_rule_kind: Literal["may", "must", "prefer"],
    replacement_name: str,
) -> None:
    """Reject before any delete or revision bump (V4-D2).

    Collides with a same-scope addition (any kind; names are unique on the
    assignment) or another replace-named output at this scope. In-place
    replace of the selected local rule may keep that rule's name when no
    inherited same-kind rule or replacement output uses it — that output key
    is the target, not a sibling.
    """
    kind = SchedulingRuleKind(target_rule_kind)
    others = (
        db.query(SchedulingRuleException)
        .filter(
            SchedulingRuleException.owner_id == user.id,
            SchedulingRuleException.scope_kind == _scope_enum(scope),
            SchedulingRuleException.scope_id == scope_id,
            SchedulingRuleException.operation == SchedulingExceptionOp.replace_named,
            SchedulingRuleException.replacement_name == replacement_name,
            SchedulingRuleException.target_rule_name != target_rule_name,
        )
        .all()
    )
    if others:
        other = others[0]
        _raise_replacement_name_conflict(
            scope=scope,
            scope_id=scope_id,
            replacement_name=replacement_name,
            target_rule_name=target_rule_name,
            occupant=(
                f"another replace-named exception that already outputs "
                f"'{replacement_name}' (target '{other.target_rule_name}')"
            ),
        )

    addition = next(
        (rule for rule in assignment.rules if rule.name == replacement_name),
        None,
    )
    if addition is None:
        return
    inplace = (
        addition.kind == kind
        and addition.name == target_rule_name
        and not _inherited_same_kind_name(
            db,
            user,
            _near_ancestors(db, user, scope, entity),
            kind=kind,
            name=replacement_name,
        )
    )
    if inplace:
        return
    _raise_replacement_name_conflict(
        scope=scope,
        scope_id=scope_id,
        replacement_name=replacement_name,
        target_rule_name=target_rule_name,
        occupant=f"existing {addition.kind.value} rule '{addition.name}'",
    )


def rule_replace_named(
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
    reject_deferred_exception_forms(raw_body)
    entity, assignment = _require_new_rule_family(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    clean_target = target_rule_name.strip()
    clean_replacement = replacement_name.strip()
    if not clean_target or not clean_replacement:
        raise ApiError(422, "target and replacement names are required", "RULE_NAME_REQUIRED")

    resolved_policy: UUID | None = None
    if empty_set:
        if policy_id is not None:
            raise ApiError(
                422,
                "empty_set replacement must not include policy_id",
                "RULE_EMPTY_WITH_POLICY",
            )
    else:
        if policy_id is None:
            raise ApiError(422, "policy_id is required", "RULE_POLICY_REQUIRED")
        _verify_owned_policy(db, user, policy_id)
        resolved_policy = policy_id

    _reject_replacement_output_collision(
        db,
        user,
        entity=entity,
        assignment=assignment,
        scope=scope,
        scope_id=scope_id,
        target_rule_name=clean_target,
        target_rule_kind=target_rule_kind,
        replacement_name=clean_replacement,
    )

    existing = (
        db.query(SchedulingRuleException)
        .filter(
            SchedulingRuleException.owner_id == user.id,
            SchedulingRuleException.scope_kind == _scope_enum(scope),
            SchedulingRuleException.scope_id == scope_id,
            SchedulingRuleException.operation == SchedulingExceptionOp.replace_named,
            SchedulingRuleException.target_rule_name == clean_target,
        )
        .one_or_none()
    )
    if existing is not None:
        db.delete(existing)
        db.flush()

    row = SchedulingRuleException(
        id=uuid4(),
        owner_id=user.id,
        scope_kind=_scope_enum(scope),
        scope_id=scope_id,
        operation=SchedulingExceptionOp.replace_named,
        target_rule_name=clean_target,
        target_rule_kind=SchedulingRuleKind(target_rule_kind),
        replacement_name=clean_replacement,
        replacement_policy_id=resolved_policy,
        replacement_empty_set=empty_set,
    )
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "exception": row,
        "scheduling_revision": revision,
    }


def rule_waive_named(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    target_rule_name: str,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reject_deferred_exception_forms(raw_body)
    _require_new_rule_family(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    clean_target = target_rule_name.strip()
    if not clean_target:
        raise ApiError(422, "target_rule_name is required", "RULE_NAME_REQUIRED")

    existing = (
        db.query(SchedulingRuleException)
        .filter(
            SchedulingRuleException.owner_id == user.id,
            SchedulingRuleException.scope_kind == _scope_enum(scope),
            SchedulingRuleException.scope_id == scope_id,
            SchedulingRuleException.operation == SchedulingExceptionOp.waive_named,
            SchedulingRuleException.target_rule_name == clean_target,
        )
        .one_or_none()
    )
    if existing is not None:
        db.delete(existing)
        db.flush()

    row = SchedulingRuleException(
        id=uuid4(),
        owner_id=user.id,
        scope_kind=_scope_enum(scope),
        scope_id=scope_id,
        operation=SchedulingExceptionOp.waive_named,
        target_rule_name=clean_target,
        target_rule_kind=SchedulingRuleKind.must,
        replacement_name=None,
        replacement_policy_id=None,
        replacement_empty_set=False,
    )
    db.add(row)
    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "exception": row,
        "scheduling_revision": revision,
    }


def rule_remove_named(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    operation: Literal["addition", "replace_named", "waive_named"],
    target_rule_name: str,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove one standing named-rule addition or exception (§2.1 / V4-D4).

    Path/CLI name ``remove-named`` mirrors ``replace-named`` / ``waive-named``.
    Deletes the identified row under owner lock + revision check; siblings stay.
    Resolver sees the remaining set only — no ``remove_named`` exception op.
    """
    reject_deferred_exception_forms(raw_body)
    _entity, assignment = _require_new_rule_family(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    clean_target = target_rule_name.strip()
    if not clean_target:
        raise ApiError(422, "target_rule_name is required", "RULE_NAME_REQUIRED")

    removed_rule: SchedulingAssignmentRule | None = None
    removed_exception: SchedulingRuleException | None = None

    if operation == "addition":
        row = (
            db.query(SchedulingAssignmentRule)
            .filter(
                SchedulingAssignmentRule.assignment_id == assignment.id,
                SchedulingAssignmentRule.name == clean_target,
            )
            .one_or_none()
        )
        if row is None:
            raise ApiError(
                404,
                f"No local named-rule addition '{clean_target}' at this scope",
                "NAMED_RULE_REMOVE_NOT_FOUND",
                scope=scope,
                scope_id=str(scope_id),
                operation=operation,
                target_rule_name=clean_target,
            )
        removed_rule = row
        db.delete(row)
    elif operation in ("replace_named", "waive_named"):
        exc_op = SchedulingExceptionOp(operation)
        row = (
            db.query(SchedulingRuleException)
            .filter(
                SchedulingRuleException.owner_id == user.id,
                SchedulingRuleException.scope_kind == _scope_enum(scope),
                SchedulingRuleException.scope_id == scope_id,
                SchedulingRuleException.operation == exc_op,
                SchedulingRuleException.target_rule_name == clean_target,
            )
            .one_or_none()
        )
        if row is None:
            raise ApiError(
                404,
                f"No standing {operation} exception for '{clean_target}' at this scope",
                "NAMED_RULE_REMOVE_NOT_FOUND",
                scope=scope,
                scope_id=str(scope_id),
                operation=operation,
                target_rule_name=clean_target,
            )
        removed_exception = row
        db.delete(row)
    else:
        raise ApiError(
            422,
            "operation must be addition, replace_named, or waive_named",
            "NAMED_RULE_REMOVE_OPERATION_INVALID",
            operation=operation,
        )

    revision = increment_scheduling_revision(db, settings)
    db.flush()
    return {
        "scope": scope,
        "scope_id": scope_id,
        "removed_operation": operation,
        "rule": removed_rule,
        "exception": removed_exception,
        "scheduling_revision": revision,
    }


def ordinary_new_rule_write(
    db: Session,
    user: User,
    *,
    scope: ScopeKind,
    scope_id: UUID,
    expected_revision: int,
    may_presence: Literal["omit", "explicit"] = "omit",
    rules: list[dict[str, Any]] | None = None,
    raw_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or replace same-family new-rule local assignment.

    Collides atomically when a legacy map is active at the same scope (V4-P1).
    """
    reject_deferred_exception_forms(raw_body)
    entity = _get_scope_entity(db, user, scope, scope_id)
    settings = lock_owner_scheduling(db, user.id)
    assert_scheduling_revision(int(settings.scheduling_revision), expected_revision)

    local = read_local_scope(db, user, scope, scope_id)
    if local.family == "legacy" or (
        local.conflict is not None and local.preferred_time_window_id is not None
    ):
        raise ApiError(
            409,
            _COLLISION_GUIDANCE,
            FAMILY_COLLISION_CODE,
            scope=scope,
            scope_id=str(scope_id),
            current_family="legacy",
            attempted_family="new_rule",
            guidance="POST /api/v1/{scope}s/{id}/scheduling/assignment/family-replace",
        )

    _delete_new_rule_at_scope(db, owner_id=user.id, scope=scope, scope_id=scope_id)
    # Legacy must stay null for new-rule family.
    _set_legacy_window_id(entity, None)
    assignment = _create_new_rule_assignment(
        db,
        user,
        scope=scope,
        scope_id=scope_id,
        may_presence=SchedulingMayPresence(may_presence),
        rules_in=list(rules or []),
    )
    revision = increment_scheduling_revision(db, settings)
    return {
        "scope": scope,
        "scope_id": scope_id,
        "family": "new_rule",
        "assignment": assignment,
        "scheduling_revision": revision,
    }
