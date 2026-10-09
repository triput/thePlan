"""F5 Coursera template API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.handoffs import (
    HandoffApplyRequest,
    HandoffApplyResult,
    HandoffGraphPayload,
    HandoffResolvedDefault,
    HandoffSourceRef,
)
from app.schemas.outlines import OutlineAttachUnder, OutlineProposeSummary


class TemplateListItem(BaseModel):
    id: str
    version: int
    title: str
    description: str
    attach_modes: list[str]


class TemplateDetailOut(TemplateListItem):
    outline_pack: str
    example_outline: dict[str, Any]
    is_scaffold: bool = False


class TemplateProposeRequest(BaseModel):
    outline: dict[str, Any]
    skip_optional: bool = False
    attach_under: OutlineAttachUnder | None = None
    source_refs: list[HandoffSourceRef] = Field(default_factory=list)


class TemplateProposeResponse(BaseModel):
    template_id: str
    template_version: int
    payload: HandoffGraphPayload
    summary: OutlineProposeSummary
    resolved_defaults: list[HandoffResolvedDefault] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_scaffold: bool = False


class TemplateApplyRequest(HandoffGraphPayload):
    idempotency_key: UUID


class TemplateApplyResponse(HandoffApplyResult):
    pass
