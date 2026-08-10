"""Auth API tests for Wave 1.5."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import BOOTSTRAP_USER_ID

TEST_PASSWORD = "correct horse battery staple"
PASSPHRASE_WITH_SPACES = "sunlit river stone meadow"


def _register_admin(client: TestClient, *, username: str = "admin", email: str = "admin@example.com") -> dict:
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


def test_me_setup_required(auth_client: TestClient) -> None:
    response = auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "SETUP_REQUIRED"


def test_register_claims_bootstrap_id(auth_client: TestClient) -> None:
    user = _register_admin(auth_client)
    assert user["id"] == str(BOOTSTRAP_USER_ID)
    assert user["username"] == "admin"
    assert user["is_admin"] is True

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(BOOTSTRAP_USER_ID)


def test_login_wrong_password(auth_client: TestClient) -> None:
    _register_admin(auth_client)
    auth_client.post("/api/v1/auth/logout")

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin", "password": "wrong password here"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_by_username_and_email(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"user{uid}"
    email = f"{username}@example.com"
    _register_admin(auth_client, username=username, email=email)
    auth_client.post("/api/v1/auth/logout")

    by_username = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": TEST_PASSWORD},
    )
    assert by_username.status_code == 200
    auth_client.post("/api/v1/auth/logout")

    by_email = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": email.upper(), "password": TEST_PASSWORD},
    )
    assert by_email.status_code == 200


def test_logout(auth_client: TestClient) -> None:
    _register_admin(auth_client)
    assert auth_client.get("/api/v1/auth/me").status_code == 200

    logout = auth_client.post("/api/v1/auth/logout")
    assert logout.status_code == 204

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 401
    assert me.json()["code"] == "UNAUTHENTICATED"


def test_admin_create_second_user(auth_client: TestClient) -> None:
    _register_admin(auth_client)

    create = auth_client.post(
        "/api/v1/auth/users",
        json={
            "username": "housemate",
            "email": "housemate@example.com",
            "password": TEST_PASSWORD,
            "display_name": "Housemate",
            "is_admin": False,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["username"] == "housemate"
    assert body["is_admin"] is False


def test_non_admin_cannot_create_user(auth_client: TestClient) -> None:
    _register_admin(auth_client)
    auth_client.post(
        "/api/v1/auth/users",
        json={
            "username": "member",
            "email": "member@example.com",
            "password": TEST_PASSWORD,
        },
    )
    auth_client.post("/api/v1/auth/logout")
    auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "member", "password": TEST_PASSWORD},
    )

    denied = auth_client.post(
        "/api/v1/auth/users",
        json={
            "username": "blocked",
            "email": "blocked@example.com",
            "password": TEST_PASSWORD,
        },
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"


def test_passphrase_with_spaces(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"space{uid}",
            "email": f"space{uid}@example.com",
            "password": PASSPHRASE_WITH_SPACES,
        },
    )
    assert response.status_code == 201, response.text

    auth_client.post("/api/v1/auth/logout")
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": f"space{uid}", "password": PASSPHRASE_WITH_SPACES},
    )
    assert login.status_code == 200


def test_admin_set_user_password(auth_client: TestClient) -> None:
    _register_admin(auth_client)
    created = auth_client.post(
        "/api/v1/auth/users",
        json={
            "username": "member",
            "email": "member@example.com",
            "password": TEST_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    new_password = "fresh meadow willow creek"

    patched = auth_client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"password": new_password},
    )
    assert patched.status_code == 200, patched.text

    auth_client.post("/api/v1/auth/logout")
    old_login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "member", "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "member", "password": new_password},
    )
    assert new_login.status_code == 200


def test_admin_can_set_own_password(auth_client: TestClient) -> None:
    admin = _register_admin(auth_client)
    new_password = "admin river canyon summit"
    patched = auth_client.patch(
        f"/api/v1/auth/users/{admin['id']}",
        json={"password": new_password},
    )
    assert patched.status_code == 200, patched.text

    auth_client.post("/api/v1/auth/logout")
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin", "password": new_password},
    )
    assert login.status_code == 200


def test_me_without_cookie(auth_client: TestClient) -> None:
    _register_admin(auth_client)
    auth_client.post("/api/v1/auth/logout")
    response = auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
