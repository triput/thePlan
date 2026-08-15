"""Outline ingest routes — propose / apply (ADR-011 Theme F)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import (
    OutlineApplyRequest,
    OutlineApplyResponse,
    OutlineProposeRequest,
    OutlineProposeResponse,
)
from app.services.outline_apply import apply_outline_actions
from app.services.outline_templates import propose_outline_actions

router = APIRouter(prefix="/outlines", tags=["outlines"])


@router.post("/propose", response_model=OutlineProposeResponse)
def outlines_propose(
    body: OutlineProposeRequest,
    user: User = Depends(get_current_user),
) -> OutlineProposeResponse:
    _ = user
    actions, summary = propose_outline_actions(
        body.outline,
        template_id=body.template_id,
        skip_optional=body.skip_optional,
    )
    return OutlineProposeResponse(
        actions=actions,
        template_id=body.template_id,
        summary=summary,
    )


@router.post("/apply", response_model=OutlineApplyResponse)
def outlines_apply(
    body: OutlineApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OutlineApplyResponse:
    results = apply_outline_actions(db, user, body.actions)
    return OutlineApplyResponse(results=results)
