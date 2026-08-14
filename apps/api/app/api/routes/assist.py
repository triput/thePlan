"""SLM Assist routes — propose / apply / status (ADR-010)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas import (
    AssistApplyRequest,
    AssistApplyResponse,
    AssistProposeRequest,
    AssistProposeResponse,
    AssistStatusOut,
)
from app.services.assist_apply import apply_assist_actions
from app.services.assist_llm import check_assist_reachable, propose_actions

router = APIRouter(prefix="/assist", tags=["assist"])


@router.get("/status", response_model=AssistStatusOut)
def assist_status(user: User = Depends(get_current_user)) -> AssistStatusOut:
    _ = user
    settings = get_settings()
    reachable, detail = check_assist_reachable(settings=settings)
    return AssistStatusOut(
        reachable=reachable,
        base_url=settings.assist_base_url,
        model=settings.assist_model,
        detail=detail,
        enabled=settings.assist_enabled,
    )


@router.post("/propose", response_model=AssistProposeResponse)
def assist_propose(
    body: AssistProposeRequest,
    user: User = Depends(get_current_user),
) -> AssistProposeResponse:
    _ = user
    actions, model = propose_actions(body.text)
    return AssistProposeResponse(actions=actions, model=model)


@router.post("/apply", response_model=AssistApplyResponse)
def assist_apply(
    body: AssistApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssistApplyResponse:
    results = apply_assist_actions(db, user, body.actions)
    return AssistApplyResponse(results=results)
