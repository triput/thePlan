"""Boundary A agent-auth guard — request-bound + Session.info (not sync-deps ContextVar alone).

FastAPI runs sync ``Depends`` / route bodies in threadpool workers. A ContextVar set
inside sync ``get_current_user`` does **not** reliably propagate into the handler
thread's ``before_commit``. Dex ``1793144777.380669``.

Approach (request-lifetime + session-bound):
1. Async middleware sets ContextVar **before** ``call_next`` (AnyIO copies context
   into threadpool) so side ``SessionLocal()`` created in the handler thread inherits
   the credential via session factory stamping.
2. Auth also stamps ``session.info["agent_mutating_credential_id"]`` on the request
   Session (object-local — thread-safe regardless of ContextVar).
3. ``before_commit`` reads ``session.info`` first, then ContextVar fallback.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

SESSION_INFO_KEY = "agent_mutating_credential_id"

# Set in async middleware (request lifetime) for mutating agent Bearer requests.
agent_mutating_credential_id: ContextVar[uuid.UUID | None] = ContextVar(
    "agent_mutating_credential_id",
    default=None,
)


def set_agent_mutating_credential(credential_id: uuid.UUID) -> Token:
    return agent_mutating_credential_id.set(credential_id)


def reset_agent_mutating_credential(token: Token) -> None:
    agent_mutating_credential_id.reset(token)


def clear_agent_mutating_credential() -> None:
    agent_mutating_credential_id.set(None)


def bind_session_agent_guard(session: Session, credential_id: uuid.UUID) -> None:
    """Stamp a Session so before_commit always sees the credential (request or side)."""
    session.info[SESSION_INFO_KEY] = credential_id


def resolve_session_agent_credential(session: Session) -> uuid.UUID | None:
    raw = session.info.get(SESSION_INFO_KEY)
    if isinstance(raw, uuid.UUID):
        return raw
    return agent_mutating_credential_id.get()


@event.listens_for(Session, "after_begin")
def _stamp_session_from_contextvar(
    session: Session, transaction: Any, connection: Any
) -> None:
    """Side SessionLocal under middleware ContextVar inherits session.info stamp."""
    if SESSION_INFO_KEY in session.info:
        return
    cred = agent_mutating_credential_id.get()
    if cred is not None:
        session.info[SESSION_INFO_KEY] = cred


@event.listens_for(Session, "before_commit")
def _boundary_a_before_commit(session: Session) -> None:
    credential_id = resolve_session_agent_credential(session)
    if credential_id is None:
        return
    if getattr(session, "_agent_boundary_a_checking", False):
        return
    session._agent_boundary_a_checking = True  # type: ignore[attr-defined]
    try:
        from app.services.agent_credentials import assert_agent_write_still_authorized

        assert_agent_write_still_authorized(session, credential_id)
    finally:
        session._agent_boundary_a_checking = False  # type: ignore[attr-defined]


def ensure_boundary_a_listener() -> None:
    """Import side-effect: listeners registered at module import."""
    return None
