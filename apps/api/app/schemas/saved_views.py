from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SavedViewPresentation(BaseModel):
    mode: Literal["list", "board"] | None = None
    sort: str | None = None


class SavedViewOut(BaseModel):
    id: UUID
    name: str
    slug: str
    predicate_json: dict[str, Any]
    presentation_json: dict[str, Any] = Field(default_factory=dict)
    is_system: bool
    sort_order: int

    model_config = {"from_attributes": True}


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=100)
    predicate_json: dict[str, Any]
    presentation_json: dict[str, Any] | None = None
    sort_order: int | None = None


class SavedViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=100)
    predicate_json: dict[str, Any] | None = None
    presentation_json: dict[str, Any] | None = None
    sort_order: int | None = None


class SavedViewInvalidReference(BaseModel):
    kind: str
    id: str


class SavedViewTasksResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int
    invalid_references: list[SavedViewInvalidReference] | None = None
