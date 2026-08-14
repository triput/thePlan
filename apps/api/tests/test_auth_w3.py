"""Auth API tests for W3 Slice 1 (ADR-007 account self-service)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

TEST_PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "fresh cedar canyon brook"


def _register_admin(
    client: TestClient, *, username: str = "admin", email: str = "admin@example.com"
) -> dict:
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


def _create_member(
    client: TestClient,
    *,
    username: str = "member",
    email: str = "member@example.com",
    display_name: str = "Housemate",
) -> dict:
    created = client.post(
        "/api/v1/auth/users",
        json={
            "username": username,
            "email": email,
            "password": TEST_PASSWORD,
            "display_name": display_name,
            "is_admin": False,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["must_change_password"] is False
    return body


def _login(client: TestClient, identifier: str, password: str = TEST_PASSWORD) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _admin_set_password(client: TestClient, user_id: str, password: str) -> dict:
    patched = client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"password": password},
    )
    assert patched.status_code == 200, patched.text
    return patched.json()


def test_patch_me_updates_display_name_email_and_password(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"self{uid}"
    _register_admin(auth_client, username=username, email=f"{username}@example.com")

    display = auth_client.patch(
        "/api/v1/auth/me",
        json={"display_name": "Renamed Self"},
    )
    assert display.status_code == 200, display.text
    assert display.json()["display_name"] == "Renamed Self"
    assert display.json()["must_change_password"] is False

    new_email = f"self-new-{uid}@example.com"
    email = auth_client.patch("/api/v1/auth/me", json={"email": new_email})
    assert email.status_code == 200, email.text
    assert email.json()["email"] == new_email

    password = auth_client.patch("/api/v1/auth/me", json={"password": NEW_PASSWORD})
    assert password.status_code == 200, password.text
    assert password.json()["must_change_password"] is False

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["display_name"] == "Renamed Self"
    assert body["email"] == new_email
    assert body["username"] == username
    assert body["must_change_password"] is False

    auth_client.post("/api/v1/auth/logout")
    old_login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401
    new_login = _login(auth_client, username, NEW_PASSWORD)
    assert new_login["email"] == new_email


def test_patch_me_email_taken_is_422(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    admin_email = f"admin-{uid}@example.com"
    member_email = f"member-{uid}@example.com"
    _register_admin(auth_client, username=f"admin{uid}", email=admin_email)
    member = _create_member(
        auth_client,
        username=f"member{uid}",
        email=member_email,
    )

    conflict = auth_client.patch("/api/v1/auth/me", json={"email": member_email})
    assert conflict.status_code == 422, conflict.text
    assert conflict.json()["code"] == "EMAIL_TAKEN"

    auth_client.post("/api/v1/auth/logout")
    _login(auth_client, member["username"])
    member_conflict = auth_client.patch("/api/v1/auth/me", json={"email": admin_email})
    assert member_conflict.status_code == 422, member_conflict.text
    assert member_conflict.json()["code"] == "EMAIL_TAKEN"

    same = auth_client.patch("/api/v1/auth/me", json={"email": member_email})
    assert same.status_code == 200, same.text
    assert same.json()["email"] == member_email


def test_create_user_email_taken_remains_409(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    email = f"taken-{uid}@example.com"
    _register_admin(auth_client, username=f"admin{uid}", email=email)

    created = auth_client.post(
        "/api/v1/auth/users",
        json={
            "username": f"copy{uid}",
            "email": email,
            "password": TEST_PASSWORD,
        },
    )
    assert created.status_code == 409, created.text
    assert created.json()["code"] == "EMAIL_TAKEN"


def test_patch_me_requires_at_least_one_field(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")

    empty = auth_client.patch("/api/v1/auth/me", json={})
    assert empty.status_code == 422, empty.text
    assert "at least one field" in empty.text.lower()


def test_admin_password_sets_must_change_password(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")
    member = _create_member(
        auth_client,
        username=f"member{uid}",
        email=f"member{uid}@example.com",
    )

    patched = _admin_set_password(auth_client, member["id"], NEW_PASSWORD)
    assert patched["must_change_password"] is True
    assert patched["id"] == member["id"]

    listed = auth_client.get("/api/v1/auth/users")
    assert listed.status_code == 200, listed.text
    flagged = next(user for user in listed.json() if user["id"] == member["id"])
    assert flagged["must_change_password"] is True

    auth_client.post("/api/v1/auth/logout")
    login = _login(auth_client, member["username"], NEW_PASSWORD)
    assert login["must_change_password"] is True

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True


def test_self_password_change_clears_must_change_password(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")
    member = _create_member(
        auth_client,
        username=f"member{uid}",
        email=f"member{uid}@example.com",
    )
    _admin_set_password(auth_client, member["id"], NEW_PASSWORD)

    auth_client.post("/api/v1/auth/logout")
    _login(auth_client, member["username"], NEW_PASSWORD)

    cleared = auth_client.patch(
        "/api/v1/auth/me",
        json={"password": "maple harbor quiet lane"},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["must_change_password"] is False

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False


def test_self_password_change_does_not_set_flag_when_already_clear(
    auth_client: TestClient,
) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"admin{uid}"
    _register_admin(auth_client, username=username, email=f"{username}@example.com")

    me_before = auth_client.get("/api/v1/auth/me")
    assert me_before.json()["must_change_password"] is False

    patched = auth_client.patch("/api/v1/auth/me", json={"password": NEW_PASSWORD})
    assert patched.status_code == 200, patched.text
    assert patched.json()["must_change_password"] is False


def test_password_change_required_blocks_domain_mutate_but_allows_patch_me(
    auth_client: TestClient,
) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")
    member = _create_member(
        auth_client,
        username=f"member{uid}",
        email=f"member{uid}@example.com",
    )
    _admin_set_password(auth_client, member["id"], NEW_PASSWORD)

    auth_client.post("/api/v1/auth/logout")
    _login(auth_client, member["username"], NEW_PASSWORD)

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True

    settings = auth_client.patch("/api/v1/settings", json={"workday_minutes": 400})
    assert settings.status_code == 403, settings.text
    assert settings.json()["code"] == "PASSWORD_CHANGE_REQUIRED"

    task = auth_client.post("/api/v1/tasks", json={"title": f"blocked-{uid}"})
    assert task.status_code == 403, task.text
    assert task.json()["code"] == "PASSWORD_CHANGE_REQUIRED"

    renamed = auth_client.patch("/api/v1/auth/me", json={"display_name": "Still Flagged"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "Still Flagged"
    assert renamed.json()["must_change_password"] is True

    still_blocked = auth_client.patch("/api/v1/settings", json={"workday_minutes": 400})
    assert still_blocked.status_code == 403
    assert still_blocked.json()["code"] == "PASSWORD_CHANGE_REQUIRED"

    cleared = auth_client.patch("/api/v1/auth/me", json={"password": "silver inlet timber walk"})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["must_change_password"] is False

    allowed = auth_client.patch("/api/v1/settings", json={"workday_minutes": 400})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["workday_minutes"] == 400


def test_admin_can_update_user_email(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")
    member = _create_member(
        auth_client,
        username=f"member{uid}",
        email=f"member{uid}@example.com",
    )
    new_email = f"renamed-{uid}@example.com"

    patched = auth_client.patch(
        f"/api/v1/auth/users/{member['id']}",
        json={"email": new_email},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["email"] == new_email
    assert patched.json()["must_change_password"] is False

    conflict = auth_client.patch(
        f"/api/v1/auth/users/{member['id']}",
        json={"email": f"admin{uid}@example.com"},
    )
    assert conflict.status_code == 422, conflict.text
    assert conflict.json()["code"] == "EMAIL_TAKEN"


def test_admin_can_clear_must_change_password_without_password(
    auth_client: TestClient,
) -> None:
    uid = uuid.uuid4().hex[:8]
    _register_admin(auth_client, username=f"admin{uid}", email=f"admin{uid}@example.com")
    member = _create_member(
        auth_client,
        username=f"member{uid}",
        email=f"member{uid}@example.com",
    )
    _admin_set_password(auth_client, member["id"], NEW_PASSWORD)

    recovered = auth_client.patch(
        f"/api/v1/auth/users/{member['id']}",
        json={"must_change_password": False},
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["must_change_password"] is False

    auth_client.post("/api/v1/auth/logout")
    login = _login(auth_client, member["username"], NEW_PASSWORD)
    assert login["must_change_password"] is False

    settings = auth_client.patch("/api/v1/settings", json={"workday_minutes": 420})
    assert settings.status_code == 200, settings.text
