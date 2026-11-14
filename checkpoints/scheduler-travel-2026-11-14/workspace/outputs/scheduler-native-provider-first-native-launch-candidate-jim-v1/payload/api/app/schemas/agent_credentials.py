from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentCredentialCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)


class AgentCredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class AgentCredentialCreatedOut(AgentCredentialOut):
    """Create response — plaintext secret returned once only."""

    secret: str
