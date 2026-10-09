"""F1 planning handoff graph payloads and receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ScheduleStyle, TaskPriority

HandoffEntityKind = Literal["epic", "project", "section", "task"]
HandoffParentKind = Literal["epic", "project", "section", "task"]
HandoffSchedulePolicy = Literal["manual", "inherited", "automatic"]


class HandoffSourceRef(BaseModel):
    system: str = Field(min_length=1, max_length=128)
    id: str = Field(min_length=1, max_length=256)
    url: str | None = None


class HandoffParentRef(BaseModel):
    kind: HandoffParentKind
    id: UUID


class HandoffEntity(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    kind: HandoffEntityKind
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    parent_key: str | None = None
    parent: HandoffParentRef | None = None
    sort_order: int = 0
    label_names: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    deadline_at: datetime | None = None
    schedule_policy: HandoffSchedulePolicy | None = None

    @model_validator(mode="after")
    def _parent_xor(self) -> HandoffEntity:
        if self.parent_key and self.parent is not None:
            raise ValueError("Use parent_key or parent, not both")
        return self


class HandoffDependency(BaseModel):
    blocking_key: str | None = None
    dependent_key: str | None = None
    blocking_task_id: UUID | None = None
    dependent_task_id: UUID | None = None

    @model_validator(mode="after")
    def _blocking_dependent_pair(self) -> HandoffDependency:
        def _one_of(key: str | None, task_id: UUID | None, label: str) -> None:
            has_key = key is not None
            has_id = task_id is not None
            if has_key == has_id:
                raise ValueError(f"{label} requires exactly one of *_key or *_task_id")

        _one_of(self.blocking_key, self.blocking_task_id, "blocking")
        _one_of(self.dependent_key, self.dependent_task_id, "dependent")
        if self.blocking_key is not None and self.blocking_key == self.dependent_key:
            raise ValueError("blocking_key and dependent_key must differ")
        if (
            self.blocking_task_id is not None
            and self.dependent_task_id is not None
            and self.blocking_task_id == self.dependent_task_id
        ):
            raise ValueError("blocking_task_id and dependent_task_id must differ")
        return self


class HandoffGraphPayload(BaseModel):
    schema_version: int = 1
    source_refs: list[HandoffSourceRef] = Field(default_factory=list)
    schedule_policy: HandoffSchedulePolicy | None = None
    entities: list[HandoffEntity] = Field(min_length=1)
    dependencies: list[HandoffDependency] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Only schema_version 1 is supported")
        return value


class HandoffResolvedDefault(BaseModel):
    entity_key: str
    field: str
    value: Any
    source: str = "user_settings"


class HandoffProposeResponse(BaseModel):
    payload: HandoffGraphPayload
    resolved_defaults: list[HandoffResolvedDefault] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HandoffApplyRequest(HandoffGraphPayload):
    idempotency_key: UUID


class HandoffReceiptEntityRef(BaseModel):
    key: str
    kind: HandoffEntityKind
    id: UUID


class HandoffApplyResult(BaseModel):
    receipt_id: UUID
    idempotency_key: UUID
    replayed: bool = False
    source_refs: list[HandoffSourceRef] = Field(default_factory=list)
    entities: list[HandoffReceiptEntityRef] = Field(default_factory=list)
    dependencies_created: int = 0
    created_counts: dict[str, int] = Field(default_factory=dict)
    defaulted_fields: list[HandoffResolvedDefault] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HandoffReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operation_kind: str
    idempotency_key: UUID
    payload_hash: str
    receipt_json: HandoffApplyResult
    created_at: datetime


class TaskDependencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    blocking_task_id: UUID
    dependent_task_id: UUID
    created_at: datetime


class TaskDependencyCreate(BaseModel):
    blocking_task_id: UUID
    dependent_task_id: UUID
