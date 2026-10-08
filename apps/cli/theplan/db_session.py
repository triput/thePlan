from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from theplan.errors import CliError


@contextmanager
def api_db_session() -> Iterator[object]:
    """Open a SQLAlchemy session via apps/api app.db (requires PYTHONPATH)."""
    try:
        from app.db import SessionLocal
    except ImportError as exc:
        raise CliError(
            code="SERVICE_UNAVAILABLE",
            message=(
                "Database session requires apps/api on PYTHONPATH and API dependencies "
                f"installed ({exc}). Set DATABASE_URL and install apps/api."
            ),
            exit_code=4,
        ) from exc

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
