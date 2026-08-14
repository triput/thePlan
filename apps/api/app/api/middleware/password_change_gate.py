from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.deps import _parse_session_user_id
from app.db import SessionLocal
from app.models import User

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_API_PREFIX = "/api/v1"
_EXEMPT_ROUTES = frozenset(
    {
        ("POST", f"{_API_PREFIX}/auth/register"),
        ("POST", f"{_API_PREFIX}/auth/login"),
        ("POST", f"{_API_PREFIX}/auth/logout"),
        ("PATCH", f"{_API_PREFIX}/auth/me"),
    }
)


def _is_gated_request(request: Request) -> bool:
    if request.method not in _MUTATING_METHODS:
        return False
    path = request.url.path.rstrip("/") or "/"
    if not path.startswith(_API_PREFIX):
        return False
    return (request.method, path) not in _EXEMPT_ROUTES


class PasswordChangeGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not _is_gated_request(request):
            return await call_next(request)

        user_id = _parse_session_user_id(request)
        if user_id is None:
            return await call_next(request)

        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if user is not None and not user.is_disabled and user.must_change_password:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Password change required before continuing",
                        "code": "PASSWORD_CHANGE_REQUIRED",
                    },
                )
        finally:
            db.close()

        return await call_next(request)
