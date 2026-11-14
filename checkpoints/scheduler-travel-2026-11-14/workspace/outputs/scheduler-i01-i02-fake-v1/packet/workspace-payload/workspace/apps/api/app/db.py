from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Register Boundary A before_commit / after_begin listeners.
from app.services.agent_auth_context import ensure_boundary_a_listener  # noqa: E402

ensure_boundary_a_listener()


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield a request-scoped Session; clear leftover agent ContextVar on exit."""
    from app.services import agent_auth_context as agent_ctx

    # Do not clear middleware-set ContextVar here — middleware owns request lifetime.
    # Only clear a leaked sync-deps token if present without middleware (tests).
    db = SessionLocal()
    try:
        yield db
    finally:
        token = getattr(request.state, "agent_context_reset_token", None)
        if token is not None:
            agent_ctx.reset_agent_mutating_credential(token)
            request.state.agent_context_reset_token = None
        db.close()
