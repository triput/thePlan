"""Shared pytest fixtures: transactional TestClient against local Postgres."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import create_app


@pytest.fixture()
def db_session() -> Session:
    """Yield a Session whose commits are rolled back at teardown."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autocommit=False, autoflush=False)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:  # type: ignore[no-untyped-def]
        if trans.nested and not trans._parent.nested:  # noqa: SLF001
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    app = create_app()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
