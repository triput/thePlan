"""DEF-027: session_epoch revocation on password change and host recovery."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models import User
from app.services.auth_users import reset_password_for_recovery

TEST_PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "fresh cedar canyon brook"
RECOVERY_PASSWORD = "quiet lantern harbor road"


def _register_admin(client: TestClient, *, username: str, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": TEST_PASSWORD,
            "display_name": "Test Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, identifier: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _session_cookie(client: TestClient) -> str:
    value = client.cookies.get("session")
    assert value, "expected session cookie"
    return value


def _use_session(client: TestClient, value: str) -> None:
    client.cookies.set("session", value)


def test_self_password_change_keeps_current_session_and_revokes_old_cookie(
    auth_client: TestClient,
) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"epoch{uid}"
    _register_admin(auth_client, username=username, email=f"{username}@example.com")
    stale = _session_cookie(auth_client)

    patched = auth_client.patch("/api/v1/auth/me", json={"password": NEW_PASSWORD})
    assert patched.status_code == 200, patched.text

    current = auth_client.get("/api/v1/auth/me")
    assert current.status_code == 200

    _use_session(auth_client, stale)
    revoked = auth_client.get("/api/v1/auth/me")
    assert revoked.status_code == 401
    assert revoked.json()["code"] == "UNAUTHENTICATED"


def test_admin_password_revokes_member_session(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")
    created = auth_client.post(
        "/api/v1/auth/users",
        json={
            "username": f"member{uid}",
            "email": f"member{uid}@example.com",
            "password": TEST_PASSWORD,
            "display_name": "Housemate",
        },
    )
    assert created.status_code == 201, created.text
    member = created.json()

    auth_client.post("/api/v1/auth/logout")
    _login(auth_client, member["username"], TEST_PASSWORD)
    member_cookie = _session_cookie(auth_client)

    auth_client.post("/api/v1/auth/logout")
    _login(auth_client, f"admin{uid}", TEST_PASSWORD)
    patched = auth_client.patch(
        f"/api/v1/auth/users/{member['id']}",
        json={"password": NEW_PASSWORD},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["must_change_password"] is True

    _use_session(auth_client, member_cookie)
    revoked = auth_client.get("/api/v1/auth/me")
    assert revoked.status_code == 401
    assert revoked.json()["code"] == "UNAUTHENTICATED"

    blocked = auth_client.post("/api/v1/tasks", json={"title": f"revoked-{uid}"})
    assert blocked.status_code == 401
    assert blocked.json()["code"] == "UNAUTHENTICATED"

    auth_client.post("/api/v1/auth/logout")
    login = _login(auth_client, member["username"], NEW_PASSWORD)
    assert login["must_change_password"] is True


def test_display_name_change_does_not_revoke_session(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")
    before = _session_cookie(auth_client)

    renamed = auth_client.patch("/api/v1/auth/me", json={"display_name": "Still Here"})
    assert renamed.status_code == 200, renamed.text
    assert _session_cookie(auth_client) == before

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["display_name"] == "Still Here"


def test_reset_password_for_recovery_generates_and_revokes(
    auth_client: TestClient,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"recover{uid}"
    email = f"{username}@example.com"
    registered = _register_admin(auth_client, username=username, email=email)
    stale = _session_cookie(auth_client)
    before = db_session.get(User, uuid.UUID(registered["id"]))
    assert before is not None
    epoch_before = before.session_epoch

    with caplog.at_level(logging.INFO, logger="app.services.auth_users"):
        user, temporary = reset_password_for_recovery(
            db_session,
            f"  {email.upper()}  ",
            generate=True,
            password="ignored caller secret value",
        )

    assert user.id == uuid.UUID(registered["id"])
    assert user.must_change_password is True
    assert user.session_epoch == epoch_before + 1
    assert temporary is not None
    assert 12 <= len(temporary) <= 128
    assert temporary != "ignored caller secret value"
    assert "password recovery for user_id=" in caplog.text
    assert str(user.id) in caplog.text
    assert temporary not in caplog.text
    assert email not in caplog.text
    assert "ignored caller secret value" not in caplog.text

    _use_session(auth_client, stale)
    revoked = auth_client.get("/api/v1/auth/me")
    assert revoked.status_code == 401
    assert revoked.json()["code"] == "UNAUTHENTICATED"

    login = _login(auth_client, username, temporary)
    assert login["must_change_password"] is True


def test_reset_password_for_recovery_accepts_explicit_password(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"explicit{uid}"
    registered = _register_admin(auth_client, username=username, email=f"{username}@example.com")
    before = db_session.get(User, uuid.UUID(registered["id"]))
    assert before is not None
    epoch_before = before.session_epoch

    user, temporary = reset_password_for_recovery(
        db_session,
        username.upper(),
        password=RECOVERY_PASSWORD,
    )
    assert temporary is None
    assert user.must_change_password is True
    assert user.session_epoch == epoch_before + 1

    auth_client.post("/api/v1/auth/logout")
    login = _login(auth_client, username, RECOVERY_PASSWORD)
    assert login["must_change_password"] is True


def test_reset_password_for_recovery_missing_user(db_session: Session) -> None:
    with pytest.raises(ApiError) as exc:
        reset_password_for_recovery(db_session, "nobody-here", generate=True)
    assert exc.value.status_code == 404
    assert exc.value.content["code"] == "USER_NOT_FOUND"


def test_reset_password_for_recovery_requires_a_secret(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"needsecret{uid}"
    _register_admin(auth_client, username=username, email=f"{username}@example.com")

    with pytest.raises(ApiError) as exc:
        reset_password_for_recovery(db_session, username)
    assert exc.value.status_code == 422
    assert exc.value.content["code"] == "INVALID_PASSWORD"
