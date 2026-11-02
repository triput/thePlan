"""HTTP / real get_db Boundary A evidence (Dex 1793144777.380669 / 1793145187.536879).

Uses disposable ``theplan_agent_cli_test`` @ 044 with **no** ``get_db`` dependency
override — real ``SessionLocal`` / middleware / ``before_commit`` lifecycle.

Protocol per case:
1. Pause after successful agent auth on a mutating ASGI request.
2. Independent connection commits revoke / setting-off / user-disable.
3. Release route to durable commit → expect agent/account denial.
4. Assert write absent; ContextVar cleaned on same app/client; browser mutating OK.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

# Refuse anything but disposable before importing app engine bind.
os.environ["SEED_DEMO_USER"] = "false"

from app.api import deps as deps_mod
from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.config import get_settings
from app.db import SessionLocal
from app.main import create_app
from app.models import AgentCredential, Task, User, UserSettings
from app.services.agent_auth_context import (
    SESSION_INFO_KEY,
    agent_mutating_credential_id,
)

_REQUIRED_DATABASE = "theplan_agent_cli_test"
_REQUIRED_REVISION = "044_agent_cli_access"
_PASSWORD = "correct horse battery staple"
_PROBE_EMAIL_LIKE = "renee-http-boundary-%@example.com"
_SIDE_WRITE_PATH = "/api/v1/_test/agent-side-session-write"


def _assert_disposable_dsn() -> None:
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        name = db.execute(text("SELECT current_database()")).scalar()
        ver = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        db.close()
    if name != _REQUIRED_DATABASE:
        pytest.skip(
            f"HTTP Boundary A tests require {_REQUIRED_DATABASE}, got {name!r}"
        )
    if ver != _REQUIRED_REVISION:
        pytest.skip(
            f"need alembic {_REQUIRED_REVISION} on disposable only, got {ver!r}"
        )


@pytest.fixture(autouse=True)
def _disposable_only() -> None:
    _assert_disposable_dsn()


def _purge() -> None:
    """Delete probe users only — never claim/delete bootstrap via register email."""
    from app.bootstrap import BOOTSTRAP_USER_ID, ensure_bootstrap_user

    db = SessionLocal()
    try:
        db.execute(
            text("DELETE FROM users WHERE email LIKE :p AND id <> :boot"),
            {"p": _PROBE_EMAIL_LIKE, "boot": BOOTSTRAP_USER_ID},
        )
        db.commit()
        ensure_bootstrap_user(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _mount_side_session_probe(app: FastAPI) -> None:
    """Test-only handler: durable write on a **separate** SessionLocal.

    Does **not** call ``bind_session_agent_guard`` — relies on middleware ContextVar
    → ``Session.after_begin`` stamping for Boundary A.
    """

    @app.post(_SIDE_WRITE_PATH)
    def agent_side_session_write(
        body: dict[str, Any],
        user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        title = str(body.get("title") or "")
        if not title:
            raise ApiError(422, "title required", "VALIDATION_ERROR")
        # Middleware must have set ContextVar for this mutating Bearer request.
        cred = agent_mutating_credential_id.get()
        assert cred is not None
        # Separate SessionLocal — do NOT call bind_session_agent_guard.
        side = SessionLocal()
        try:
            assert SESSION_INFO_KEY not in side.info  # pre-begin: not manually stamped
            side.add(Task(owner_id=user.id, title=title))
            side.flush()  # autobegin → after_begin copies ContextVar into session.info
            assert side.info.get(SESSION_INFO_KEY) == cred
            side.commit()
            return {"ok": True, "title": title}
        except ApiError:
            side.rollback()
            raise
        finally:
            side.close()


def _open_app_client(*, with_side_probe: bool = False) -> tuple[FastAPI, TestClient]:
    """Real app — no get_db override. Caller owns one lifespan for deny + browser follow-up."""
    get_settings.cache_clear()
    app = create_app()
    if with_side_probe:
        _mount_side_session_probe(app)
    client = TestClient(app)
    client.__enter__()
    return app, client


def _close_client(client: TestClient) -> None:
    client.__exit__(None, None, None)


def _seed_agent(client: TestClient) -> tuple[str, str, str, str]:
    """Returns username, user_id, credential_id, secret."""
    from app.services.passwords import hash_password

    _purge()
    uid = uuid.uuid4().hex[:10]
    username = f"httpb{uid}"
    email = f"renee-http-boundary-{uid}@example.com"
    db = SessionLocal()
    try:
        user = User(
            email=email,
            username=username,
            password_hash=hash_password(_PASSWORD),
            display_name=username,
            is_admin=True,
            is_disabled=False,
            must_change_password=False,
            session_epoch=0,
        )
        db.add(user)
        db.flush()
        db.add(
            UserSettings(
                owner_id=user.id,
                allow_agent_cli_access=True,
            )
        )
        db.commit()
        user_id = str(user.id)
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": _PASSWORD},
    )
    assert login.status_code == 200, login.text

    patched = client.patch("/api/v1/settings", json={"allow_agent_cli_access": True})
    assert patched.status_code == 200, patched.text
    created = client.post("/api/v1/agent-credentials", json={"label": "http-boundary"})
    assert created.status_code == 201, created.text
    body = created.json()
    return username, user_id, body["id"], body["secret"]


def _count_tasks(owner_id: str, title: str) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(Task)
            .filter(Task.owner_id == uuid.UUID(owner_id), Task.title == title)
            .count()
        )
    finally:
        db.close()


def _run_paused_mutating_on_client(
    client: TestClient,
    *,
    path: str,
    secret: str,
    json_body: dict[str, Any],
    after_auth: Callable[[], None],
    require_request_session_stamp: bool = True,
) -> dict[str, object]:
    """Mutating request on **this** client; pause after auth; after_auth(); resume.

    Same TestClient lifespan as caller — worker does not open a second app.
    """
    auth_passed = threading.Event()
    release = threading.Event()
    outcome: dict[str, object] = {}
    original = deps_mod._resolve_agent_user

    def wrapped(request, db, token):  # type: ignore[no-untyped-def]
        user = original(request, db, token)
        if require_request_session_stamp:
            assert db.info.get(SESSION_INFO_KEY) is not None
        # Middleware ContextVar must be visible in this sync auth thread.
        assert agent_mutating_credential_id.get() is not None
        auth_passed.set()
        assert release.wait(timeout=20), "release not signaled"
        return user

    deps_mod._resolve_agent_user = wrapped  # type: ignore[assignment]

    def worker() -> None:
        try:
            resp = client.post(
                path,
                headers={"Authorization": f"Bearer {secret}"},
                json=json_body,
            )
            outcome["status"] = resp.status_code
            try:
                outcome["body"] = resp.json()
            except Exception:
                outcome["body"] = {"raw": resp.text}
        except Exception as exc:
            outcome["error"] = f"{type(exc).__name__}:{exc}"

    try:
        t = threading.Thread(target=worker, name="http-boundary-worker", daemon=True)
        t.start()
        assert auth_passed.wait(timeout=20), "auth never passed"
        after_auth()
        release.set()
        t.join(timeout=30)
        assert not t.is_alive()
        return outcome
    finally:
        deps_mod._resolve_agent_user = original  # type: ignore[assignment]


def _assert_contextvar_cleared() -> None:
    """Middleware finally must leave no mutating ContextVar for the next request."""
    assert agent_mutating_credential_id.get() is None


def _browser_follow_up_ok(client: TestClient, username: str, user_id: str) -> None:
    _assert_contextvar_cleared()
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": _PASSWORD},
    )
    assert login.status_code == 200, login.text
    browser_title = f"browser-ok-{uuid.uuid4().hex[:8]}"
    created = client.post("/api/v1/tasks", json={"title": browser_title})
    assert created.status_code == 201, created.text
    assert _count_tasks(user_id, browser_title) == 1
    _assert_contextvar_cleared()


def test_http_boundary_a_revoke_denies_commit_write_absent() -> None:
    _app, client = _open_app_client()
    try:
        username, user_id, cred_id, secret = _seed_agent(client)
        title = f"deny-revoke-{uuid.uuid4().hex[:8]}"

        def revoke() -> None:
            db = SessionLocal()
            try:
                row = db.get(AgentCredential, uuid.UUID(cred_id))
                assert row is not None
                row.revoked_at = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.close()

        outcome = _run_paused_mutating_on_client(
            client,
            path="/api/v1/tasks",
            secret=secret,
            json_body={"title": title},
            after_auth=revoke,
        )
        assert outcome.get("status") == 403, outcome
        assert outcome.get("body", {}).get("code") == "AGENT_CREDENTIAL_REVOKED"
        assert _count_tasks(user_id, title) == 0
        _browser_follow_up_ok(client, username, user_id)
    finally:
        _close_client(client)
        _purge()


def test_http_boundary_a_setting_off_denies_commit_write_absent() -> None:
    _app, client = _open_app_client()
    try:
        username, user_id, _cred_id, secret = _seed_agent(client)
        title = f"deny-setting-{uuid.uuid4().hex[:8]}"

        def disable_setting() -> None:
            db = SessionLocal()
            try:
                settings = (
                    db.query(UserSettings)
                    .filter(UserSettings.owner_id == uuid.UUID(user_id))
                    .one()
                )
                settings.allow_agent_cli_access = False
                db.commit()
            finally:
                db.close()

        outcome = _run_paused_mutating_on_client(
            client,
            path="/api/v1/tasks",
            secret=secret,
            json_body={"title": title},
            after_auth=disable_setting,
        )
        assert outcome.get("status") == 403, outcome
        assert outcome.get("body", {}).get("code") == "AGENT_ACCESS_DISABLED"
        assert _count_tasks(user_id, title) == 0
        _browser_follow_up_ok(client, username, user_id)
    finally:
        _close_client(client)
        _purge()


def test_http_boundary_a_user_disable_denies_commit_write_absent() -> None:
    _app, client = _open_app_client()
    try:
        username, user_id, _cred_id, secret = _seed_agent(client)
        title = f"deny-disable-{uuid.uuid4().hex[:8]}"

        def disable_user() -> None:
            db = SessionLocal()
            try:
                user = db.get(User, uuid.UUID(user_id))
                assert user is not None
                user.is_disabled = True
                db.commit()
            finally:
                db.close()

        outcome = _run_paused_mutating_on_client(
            client,
            path="/api/v1/tasks",
            secret=secret,
            json_body={"title": title},
            after_auth=disable_user,
        )
        assert outcome.get("status") in (401, 403), outcome
        assert outcome.get("body", {}).get("code") == "UNAUTHENTICATED", outcome
        assert _count_tasks(user_id, title) == 0

        _assert_contextvar_cleared()
        db = SessionLocal()
        try:
            user = db.get(User, uuid.UUID(user_id))
            assert user is not None
            user.is_disabled = False
            db.commit()
        finally:
            db.close()
        _browser_follow_up_ok(client, username, user_id)
    finally:
        _close_client(client)
        _purge()


def test_http_boundary_a_side_sessionlocal_revoke_denies_without_manual_bind() -> None:
    """Dex 1793145187.536879: side SessionLocal write, no bind_session_agent_guard.

    Proves middleware ContextVar → after_begin stamp path (not only request Session.info).
    Same create_app/TestClient lifespan for deny + browser follow-up + cleanup check.
    """
    _app, client = _open_app_client(with_side_probe=True)
    try:
        username, user_id, cred_id, secret = _seed_agent(client)
        title = f"deny-side-{uuid.uuid4().hex[:8]}"

        def revoke() -> None:
            db = SessionLocal()
            try:
                row = db.get(AgentCredential, uuid.UUID(cred_id))
                assert row is not None
                row.revoked_at = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.close()

        outcome = _run_paused_mutating_on_client(
            client,
            path=_SIDE_WRITE_PATH,
            secret=secret,
            json_body={"title": title},
            after_auth=revoke,
            require_request_session_stamp=True,
        )
        assert outcome.get("status") == 403, outcome
        assert outcome.get("body", {}).get("code") == "AGENT_CREDENTIAL_REVOKED"
        assert _count_tasks(user_id, title) == 0
        _browser_follow_up_ok(client, username, user_id)
    finally:
        _close_client(client)
        _purge()
