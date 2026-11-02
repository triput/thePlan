"""Browser-session-only agent credential admin (create / list / revoke)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_browser_user
from app.db import get_db
from app.models import User
from app.schemas.agent_credentials import (
    AgentCredentialCreate,
    AgentCredentialCreatedOut,
    AgentCredentialOut,
)
from app.services.agent_credentials import (
    create_agent_credential,
    list_agent_credentials,
    revoke_agent_credential,
)

router = APIRouter(prefix="/agent-credentials", tags=["agent-credentials"])


@router.get("", response_model=list[AgentCredentialOut])
def list_credentials(
    db: Session = Depends(get_db),
    user: User = Depends(get_browser_user),
) -> list[AgentCredentialOut]:
    rows = list_agent_credentials(db, user)
    return [AgentCredentialOut.model_validate(row) for row in rows]


@router.post("", response_model=AgentCredentialCreatedOut, status_code=status.HTTP_201_CREATED)
def create_credential(
    body: AgentCredentialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_browser_user),
) -> AgentCredentialCreatedOut:
    row, plain = create_agent_credential(db, user, label=body.label)
    return AgentCredentialCreatedOut(
        id=row.id,
        label=row.label,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        secret=plain,
    )


@router.post("/{credential_id}/revoke", response_model=AgentCredentialOut)
def revoke_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_browser_user),
) -> AgentCredentialOut:
    row = revoke_agent_credential(db, user, credential_id)
    return AgentCredentialOut.model_validate(row)
