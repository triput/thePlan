"""F5 Coursera built-in templates — list/get/propose/apply + receipt lookup."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.handoffs import HandoffApplyRequest, HandoffApplyResult
from app.schemas.templates import (
    TemplateApplyResponse,
    TemplateDetailOut,
    TemplateListItem,
    TemplateProposeRequest,
    TemplateProposeResponse,
)
from app.services.template_apply import (
    apply_template,
    propose_template,
    template_detail,
    template_receipt_by_key,
    templates_list,
)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateListItem])
def templates_index() -> list[TemplateListItem]:
    return templates_list()


@router.get("/receipts/by-key/{idempotency_key}", response_model=HandoffApplyResult)
def templates_receipt_by_key(
    idempotency_key: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HandoffApplyResult:
    return template_receipt_by_key(db, user, idempotency_key)


@router.get("/{template_id}", response_model=TemplateDetailOut)
def templates_get(template_id: str) -> TemplateDetailOut:
    return template_detail(template_id)


@router.post("/{template_id}/propose", response_model=TemplateProposeResponse)
def templates_propose(
    template_id: str,
    body: TemplateProposeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TemplateProposeResponse:
    return propose_template(
        db,
        user,
        template_id,
        body.outline,
        skip_optional=body.skip_optional,
        attach_under=body.attach_under,
        source_refs=body.source_refs,
    )


@router.post("/{template_id}/apply", response_model=TemplateApplyResponse)
def templates_apply(
    template_id: str,
    body: HandoffApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TemplateApplyResponse:
    result = apply_template(db, user, template_id, body)
    db.commit()
    return TemplateApplyResponse.model_validate(result.model_dump())
