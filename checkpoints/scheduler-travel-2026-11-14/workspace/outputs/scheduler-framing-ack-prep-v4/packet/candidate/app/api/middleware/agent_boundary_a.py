"""Request-lifetime Boundary A ContextVar for mutating agent Bearer requests.

Set in async middleware **before** ``call_next`` so AnyIO copies the context into
sync threadpool workers (deps + route + side SessionLocal). Cleared in ``finally``.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.services.agent_auth_context import (
    clear_agent_mutating_credential,
    reset_agent_mutating_credential,
    set_agent_mutating_credential,
)
from app.services.agent_credentials import parse_secret_credential_id

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_API_PREFIX = "/api/v1"


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header is None:
        return None
    parts = header.split(None, 1)
    if not parts or parts[0].lower() != "bearer":
        return None
    if len(parts) == 1:
        return ""
    return parts[1].strip()


class AgentBoundaryAMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        reset_token = None
        if (
            request.method in _MUTATING_METHODS
            and request.url.path.startswith(_API_PREFIX)
        ):
            bearer = _extract_bearer(request)
            if bearer is not None:
                cred_id = parse_secret_credential_id(bearer)
                if cred_id is not None:
                    reset_token = set_agent_mutating_credential(cred_id)
                    request.state.agent_mutating_credential_id = cred_id
        try:
            return await call_next(request)
        finally:
            if reset_token is not None:
                reset_agent_mutating_credential(reset_token)
            else:
                clear_agent_mutating_credential()
            if hasattr(request.state, "agent_mutating_credential_id"):
                delattr(request.state, "agent_mutating_credential_id")
