# ==============================================================================
#  File: apps/api/app/schemas/scheduling_assignment.py
#  Description: API shapes for S2-V4 assignment / named-rule exception ops.
#  Component: Scheduling / Settings — S2-V4
#  Version: 1.0
#  Created: 2026-10-13
#  Last Update: 2026-10-14 (V4b day-scoped schemas)
# ==============================================================================

"""Distinct representations (V4-P3):

- omit / inherit May: ``may.presence = "omit"`` (no local May set)
- clear assignment: local ``family = "none"`` / ``assignment = null``
- explicit empty May: ``may.presence = "explicit"`` with ``rules: []``
  (or a may rule with ``empty_set: true``)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuleContentIn(BaseModel):
    """Named rule body without kind (kind comes from the parent list / op)."""

    name: str
    policy_id: UUID | None = None
    empty_set: bool = False
    sort_order: int | None = None

    @model_validator(mode="after")
    def _content_xor(self) -> RuleContentIn:
        if self.empty_set and self.policy_id is not None:
            raise ValueError("empty_set rules must not include policy_id")
        if not self.empty_set and self.policy_id is None:
            raise ValueError("non-empty rules require policy_id")
        return self


class SchedulingRuleIn(RuleContentIn):
    kind: Literal["may", "must", "prefer"]


class MaySpecIn(BaseModel):
    """Local May presence. omit = inherit; explicit + empty rules = empty May."""

    presence: Literal["omit", "explicit"] = "omit"
    rules: list[RuleContentIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _omit_has_no_may_rules(self) -> MaySpecIn:
        if self.presence == "omit" and self.rules:
            raise ValueError("may.presence=omit cannot include may rules")
        return self


class FamilyReplaceIn(BaseModel):
    # extra=allow so dated / weekday / context keys that are not declared fields
    # still reach reject_deferred_exception_forms (no silent drop).
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    target_family: Literal["legacy", "new_rule", "none"]
    preferred_time_window_id: UUID | None = None
    may: MaySpecIn | None = None
    must: list[RuleContentIn] = Field(default_factory=list)
    prefer: list[RuleContentIn] = Field(default_factory=list)
    # Deferred forms — if present, writers reject with no write.
    date_range: Any | None = None
    local_start_date: Any | None = None
    local_end_date: Any | None = None
    on_date: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None
    expiry: Any | None = None


class AssignmentClearIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    date_range: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None


class AssignmentRevertIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    replacement_id: UUID
    date_range: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None


class NewRuleAssignmentWriteIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    may: MaySpecIn = Field(default_factory=MaySpecIn)
    must: list[RuleContentIn] = Field(default_factory=list)
    prefer: list[RuleContentIn] = Field(default_factory=list)
    date_range: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None


class RuleAddIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    name: str
    kind: Literal["may", "must", "prefer"]
    policy_id: UUID | None = None
    empty_set: bool = False
    date_range: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None


class RuleReplaceNamedIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    target_rule_name: str
    target_rule_kind: Literal["may", "must", "prefer"]
    replacement_name: str
    policy_id: UUID | None = None
    empty_set: bool = False
    date_range: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None


class RuleWaiveNamedIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    target_rule_name: str
    date_range: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None


class RuleRemoveNamedIn(BaseModel):
    """Targeted removal of one standing named-rule row (§2.1).

    HTTP path ``remove-named`` matches ``replace-named`` / ``waive-named``.
    ``operation`` selects which standing row to drop:

    - ``addition`` — local ``rule.add`` row (``SchedulingAssignmentRule``)
    - ``replace_named`` — standing replace exception
    - ``waive_named`` — standing waive exception

    Removal restores that named underlying rule; siblings stay. Not a new
    ``SchedulingExceptionOp`` — resolve applies remaining rows only.
    """

    model_config = ConfigDict(extra="allow")

    expected_revision: int
    operation: Literal["addition", "replace_named", "waive_named"]
    target_rule_name: str
    date_range: Any | None = None
    weekday: Any | None = None
    weekdays: Any | None = None
    context: Any | None = None
    context_id: Any | None = None


class SchedulingRuleOut(BaseModel):
    id: UUID | None = None
    name: str
    kind: Literal["may", "must", "prefer"]
    policy_id: UUID | None = None
    empty_set: bool = False
    sort_order: int = 0
    source_scope: str | None = None
    origin: str | None = None


class MaySpecOut(BaseModel):
    presence: Literal["omit", "explicit", "absent"]
    rules: list[SchedulingRuleOut] = Field(default_factory=list)
    note: str | None = None


class RuleExceptionOut(BaseModel):
    id: UUID
    operation: Literal["replace_named", "waive_named"]
    target_rule_name: str
    target_rule_kind: Literal["may", "must", "prefer"]
    replacement_name: str | None = None
    replacement_policy_id: UUID | None = None
    replacement_empty_set: bool = False


class LocalAssignmentOut(BaseModel):
    scope: Literal["task", "project", "epic"]
    scope_id: UUID
    family: Literal["none", "legacy", "new_rule"]
    preferred_time_window_id: UUID | None = None
    may: MaySpecOut | None = None
    must: list[SchedulingRuleOut] = Field(default_factory=list)
    prefer: list[SchedulingRuleOut] = Field(default_factory=list)
    exceptions: list[RuleExceptionOut] = Field(default_factory=list)
    conflict: dict[str, Any] | None = None
    revert_replacement_id: UUID | None = None


class AssignmentMutationOut(BaseModel):
    scope: Literal["task", "project", "epic"]
    scope_id: UUID
    family: Literal["none", "legacy", "new_rule"]
    scheduling_revision: int
    replacement_id: UUID | None = None
    restored_replacement_id: UUID | None = None
    cleared: bool | None = None
    preferred_time_window_id: UUID | None = None
    assignment: LocalAssignmentOut | None = None


class ResolvedSchedulingOut(BaseModel):
    """Effective resolved assignment for a task (placer / effective-read)."""

    family: Literal["none", "legacy", "new_rule"]
    winning_scope: Literal["task", "project", "epic"] | None = None
    winning_scope_id: UUID | None = None
    legacy_map_id: UUID | None = None
    legacy_source: str | None = None
    may: MaySpecOut
    must: list[SchedulingRuleOut] = Field(default_factory=list)
    prefer: list[SchedulingRuleOut] = Field(default_factory=list)
    exceptions_applied: list[dict[str, Any]] = Field(default_factory=list)
    conflict: dict[str, Any] | None = None
    consumes_personal_policy: bool = False
    placer_active: bool = False
    note: str | None = None


class RuleMutationOut(BaseModel):
    scope: Literal["task", "project", "epic"]
    scope_id: UUID
    scheduling_revision: int
    rule: SchedulingRuleOut | None = None
    exception: RuleExceptionOut | None = None


# ---- S2-V4b day-scoped (extra=allow so undeclared keys reach writers) ----


class DayScopedSelectorIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: Literal["one_date", "weekday_standing", "date_range"]
    on_date: date | None = None
    on: date | None = None
    weekdays: list[int] | int | None = None
    weekday: int | None = None
    days_of_week: list[int] | None = None
    start_date: date | None = None
    end_date: date | None = None
    local_start_date: date | None = None
    local_end_date: date | None = None


class DayScopedBaseIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    selector: DayScopedSelectorIn | None = None
    on_date: date | str | None = None
    on: date | str | None = None
    weekday: int | None = None
    weekdays: list[int] | int | None = None
    days_of_week: list[int] | None = None
    date_range: dict[str, Any] | None = None
    local_start_date: date | str | None = None
    local_end_date: date | str | None = None
    expires_at: datetime | str | None = None
    expiry: datetime | str | None = None
    expires_on: datetime | str | None = None
    replaces_op_ids: list[UUID] | None = None
    replaces: list[UUID] | None = None
    addition_survives: bool | None = None
    context: Any | None = None
    context_id: Any | None = None
    context_slug: Any | None = None


class DayChangeSelectedIn(DayScopedBaseIn):
    policy_id: UUID | None = None
    empty_set: bool = False
    empty: bool | None = None


class DayOnlyAllowIn(DayScopedBaseIn):
    policy_id: UUID | None = None
    empty_set: bool = False
    empty: bool | None = None


class FamilyReplaceScopedIn(DayScopedBaseIn):
    target_family: Literal["legacy", "new_rule", "none"]
    preferred_time_window_id: UUID | None = None
    may: MaySpecIn | None = None
    must: list[RuleContentIn] = Field(default_factory=list)
    prefer: list[RuleContentIn] = Field(default_factory=list)


class ClearScopedIn(DayScopedBaseIn):
    pass


class RevertScopedIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    replacement_id: UUID
    context: Any | None = None
    context_id: Any | None = None


class RuleAddScopedIn(DayScopedBaseIn):
    name: str
    kind: Literal["may", "must", "prefer"]
    policy_id: UUID | None = None
    empty_set: bool = False


class RuleReplaceNamedScopedIn(DayScopedBaseIn):
    target_rule_name: str
    target_rule_kind: Literal["may", "must", "prefer"]
    replacement_name: str
    policy_id: UUID | None = None
    empty_set: bool = False


class RuleWaiveNamedScopedIn(DayScopedBaseIn):
    target_rule_name: str


class RuleRemoveNamedScopedIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: int
    op_id: UUID
    context: Any | None = None
    context_id: Any | None = None


class DayScopedOpOut(BaseModel):
    id: UUID
    op_kind: str
    scope: Literal["task", "project", "epic"]
    scope_id: UUID
    selector_kind: str
    civil_on_date: str | None = None
    civil_weekdays: list[int] | None = None
    civil_start_date: str | None = None
    civil_end_date: str | None = None
    expires_at: str | None = None
    payload_kind: str
    policy_id: UUID | None = None
    rule_name: str | None = None
    rule_kind: str | None = None
    target_rule_name: str | None = None
    target_rule_kind: str | None = None
    replacement_name: str | None = None
    replacement_policy_id: UUID | None = None
    replacement_empty_set: bool = False
    target_family: str | None = None
    replaces_op_ids: list[str] = Field(default_factory=list)
    addition_survives: bool | None = None
    assignment_id: UUID | None = None


class DayScopedMutationOut(BaseModel):
    scope: Literal["task", "project", "epic"]
    scope_id: UUID
    scheduling_revision: int
    op: DayScopedOpOut | None = None
    replacement_id: UUID | None = None
    restored_replacement_id: UUID | None = None
    cleared_scoped: bool | None = None
    removed_op_id: UUID | None = None
    removed: DayScopedOpOut | None = None
    family: Literal["none", "legacy", "new_rule"] | None = None
    preferred_time_window_id: UUID | None = None
    assignment: LocalAssignmentOut | None = None
