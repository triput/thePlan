"""Shared pytest fixtures: transactional TestClient against local Postgres."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

# Avoid lifespan demo seed against the shared local Postgres during tests.
os.environ.setdefault("SEED_DEMO_USER", "false")

from app.bootstrap import BOOTSTRAP_USER_ID
from app.config import get_settings
from app.db import engine, get_db
from app.main import create_app
from app.models import User
from app.services.passwords import hash_password

get_settings.cache_clear()

_TEST_PASSWORD = "test passphrase twelve"


class _SharedGateSession:
    """Expose the transactional test session to PasswordChangeGateMiddleware.

    The gate opens SessionLocal() on a separate connection, which cannot see
    uncommitted test data (including must_change_password). Tests share the
    fixture session and no-op close() so teardown still owns the transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *args: object, **kwargs: object) -> object:
        return self._session.get(*args, **kwargs)

    def close(self) -> None:
        return None


def _bind_password_gate_to_test_session(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.middleware.password_change_gate.SessionLocal",
        lambda: _SharedGateSession(db_session),
    )


def _reset_to_setup_required(db: Session) -> None:
    """Within the test transaction, clear all password hashes so setup is required."""
    users = db.query(User).all()
    for user in users:
        user.password_hash = None
        user.is_admin = False
        user.is_disabled = False
        user.must_change_password = False
    db.flush()


def _clear_must_change_password(db: Session) -> None:
    """Domain tests should not inherit a leftover forced-password flag."""
    for user in db.query(User).all():
        user.must_change_password = False
    db.flush()


def _ensure_authenticated(client: TestClient, db: Session) -> None:
    me = client.get("/api/v1/auth/me")
    if me.status_code == 200:
        _clear_must_change_password(db)
        return

    if me.status_code == 401 and me.json().get("code") == "SETUP_REQUIRED":
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testadmin",
                "email": "testadmin@example.com",
                "password": _TEST_PASSWORD,
                "display_name": "Test Admin",
            },
        )
        assert response.status_code == 201, response.text
        return

    if me.status_code == 401 and me.json().get("code") == "UNAUTHENTICATED":
        # Live DB may already be claimed (e.g. operator machine). Align hash in this txn.
        bootstrap = db.get(User, BOOTSTRAP_USER_ID)
        if bootstrap is not None and bootstrap.password_hash:
            bootstrap.password_hash = hash_password(_TEST_PASSWORD)
            if not bootstrap.username:
                bootstrap.username = "testadmin"
            db.flush()
            response = client.post(
                "/api/v1/auth/login",
                json={"identifier": bootstrap.username or "testadmin", "password": _TEST_PASSWORD},
            )
            assert response.status_code == 200, response.text
            return
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": "testadmin", "password": _TEST_PASSWORD},
        )
        assert response.status_code == 200, response.text
        return

    raise AssertionError(f"Unexpected /auth/me response: {me.status_code} {me.text}")


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
def auth_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient without auto-login; forces SETUP_REQUIRED for auth flow tests."""
    _reset_to_setup_required(db_session)
    _bind_password_gate_to_test_session(db_session, monkeypatch)
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


@pytest.fixture()
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Authenticated TestClient for domain API tests."""
    _clear_must_change_password(db_session)
    _bind_password_gate_to_test_session(db_session, monkeypatch)
    app = create_app()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        _ensure_authenticated(test_client, db_session)
        yield test_client
    app.dependency_overrides.clear()
