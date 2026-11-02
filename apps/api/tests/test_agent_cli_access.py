"""Phase 1 agent/CLI access — disposable acceptance (V1–V13 as feasible).

Requires schema 044_agent_cli_access. Prefer DATABASE_URL → theplan_s1_test.
Do not apply 044 to household (pinned at 042).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.models import UserSettings

TEST_PASSWORD = "correct horse battery staple"
_REQUIRED_REVISION = "044_agent_cli_access"


def _ensure_no_bootstrap_settings(db: Session) -> None:
    """In-txn precondition: first-time settings creation must not reuse durable rows."""
    db.query(UserSettings).filter(UserSettings.owner_id == BOOTSTRAP_USER_ID).delete(
        synchronize_session=False
    )
    db.flush()
    remaining = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == BOOTSTRAP_USER_ID)
        .count()
    )
    assert remaining == 0, "precondition: bootstrap must have no UserSettings in this txn"


def _ensure_bootstrap_settings_enabled(db: Session) -> UserSettings:
    """In-txn seed/reuse: existing enabled settings row for claim-preserves-flags."""
    row = (
        db.query(UserSettings)
        .filter(UserSettings.owner_id == BOOTSTRAP_USER_ID)
        .one_or_none()
    )
    if row is None:
        row = UserSettings(
            owner_id=BOOTSTRAP_USER_ID,
            allow_agent_cli_access=True,
            allow_agent_cli_access_grandfathered=False,
        )
        db.add(row)
    else:
        row.allow_agent_cli_access = True
        row.allow_agent_cli_access_grandfathered = False
    db.flush()
    return row


def _register(client: TestClient, *, username: str, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": TEST_PASSWORD,
            "display_name": username,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def _enable_and_create_credential(
    client: TestClient, *, label: str = "cli"
) -> tuple[dict, str]:
    patched = client.patch("/api/v1/settings", json={"allow_agent_cli_access": True})
    assert patched.status_code == 200, patched.text
    assert patched.json()["allow_agent_cli_access"] is True
    created = client.post("/api/v1/agent-credentials", json={"label": label})
    assert created.status_code == 201, created.text
    body = created.json()
    assert "secret" in body
    assert body["secret"].startswith("tp_agent_")
    assert "secret_hash" not in body
    return body, body["secret"]


@pytest.fixture(autouse=True)
def _require_agent_cli_schema(db_session: Session) -> None:
    try:
        version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as exc:
        pytest.skip(f"database unavailable for agent CLI tests: {exc}")
    if version != _REQUIRED_REVISION:
        pytest.skip(
            f"alembic at {version!r}; need {_REQUIRED_REVISION} on disposable DB only "
            f"(do not upgrade household)"
        )


# --- V1 / V2 / V3 / V4 ---


def test_v1_new_account_setting_off_browser_ok(
    auth_client: TestClient, db_session: Session
) -> None:
    _ensure_no_bootstrap_settings(db_session)
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v1{uid}", email=f"v1{uid}@example.com")
    settings = auth_client.get("/api/v1/settings")
    assert settings.status_code == 200
    body = settings.json()
    assert body["allow_agent_cli_access"] is False
    assert body["allow_agent_cli_access_grandfathered"] is False
    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200


def test_v1_claim_reuses_preexisting_settings_flags(
    auth_client: TestClient, db_session: Session
) -> None:
    """claim_bootstrap_user must not reset existing UserSettings flags."""
    _ensure_bootstrap_settings_enabled(db_session)
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v1r{uid}", email=f"v1r{uid}@example.com")
    settings = auth_client.get("/api/v1/settings")
    assert settings.status_code == 200
    body = settings.json()
    assert body["allow_agent_cli_access"] is True
    assert body["allow_agent_cli_access_grandfathered"] is False


def test_v2_setting_off_bearer_denied_browser_ok(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v2{uid}", email=f"v2{uid}@example.com")
    # Force-enable to mint, then disable.
    _cred, secret = _enable_and_create_credential(auth_client, label="temp")
    off = auth_client.patch("/api/v1/settings", json={"allow_agent_cli_access": False})
    assert off.status_code == 200
    denied = auth_client.get("/api/v1/auth/me", headers=_bearer(secret))
    assert denied.status_code == 403
    assert denied.json()["code"] == "AGENT_ACCESS_DISABLED"
    browser = auth_client.get("/api/v1/auth/me")
    assert browser.status_code == 200


def test_v3_grandfathered_can_create(auth_client: TestClient, db_session: Session) -> None:
    uid = uuid.uuid4().hex[:8]
    user = _register(auth_client, username=f"v3{uid}", email=f"v3{uid}@example.com")
    settings = (
        db_session.query(UserSettings)
        .filter(UserSettings.owner_id == uuid.UUID(user["id"]))
        .one()
    )
    settings.allow_agent_cli_access = True
    settings.allow_agent_cli_access_grandfathered = True
    db_session.flush()
    created = auth_client.post("/api/v1/agent-credentials", json={"label": "grandpa"})
    assert created.status_code == 201, created.text


def test_v4_valid_credential_read_write(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v4{uid}", email=f"v4{uid}@example.com")
    _cred, secret = _enable_and_create_credential(auth_client)
    me = auth_client.get("/api/v1/auth/me", headers=_bearer(secret))
    assert me.status_code == 200
    task = auth_client.post(
        "/api/v1/tasks",
        headers=_bearer(secret),
        json={"title": f"agent-task-{uid}"},
    )
    assert task.status_code == 201, task.text


# --- V5 family ---


def test_v5_revoke_denies_other_cred_and_browser_ok(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v5{uid}", email=f"v5{uid}@example.com")
    a, secret_a = _enable_and_create_credential(auth_client, label="a")
    b, secret_b = _enable_and_create_credential(auth_client, label="b")
    revoked = auth_client.post(f"/api/v1/agent-credentials/{a['id']}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    denied = auth_client.get("/api/v1/auth/me", headers=_bearer(secret_a))
    assert denied.status_code == 403
    assert denied.json()["code"] == "AGENT_CREDENTIAL_REVOKED"
    ok_b = auth_client.get("/api/v1/auth/me", headers=_bearer(secret_b))
    assert ok_b.status_code == 200
    browser = auth_client.get("/api/v1/auth/me")
    assert browser.status_code == 200


def test_v5c_revoked_plus_setting_off_precedence(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v5c{uid}", email=f"v5c{uid}@example.com")
    cred, secret = _enable_and_create_credential(auth_client)
    auth_client.post(f"/api/v1/agent-credentials/{cred['id']}/revoke")
    auth_client.patch("/api/v1/settings", json={"allow_agent_cli_access": False})
    denied = auth_client.get("/api/v1/auth/me", headers=_bearer(secret))
    assert denied.status_code == 403
    assert denied.json()["code"] == "AGENT_CREDENTIAL_REVOKED"


def test_v5_final_check_blocks_write_after_revoke(
    auth_client: TestClient, db_session: Session
) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v5f{uid}", email=f"v5f{uid}@example.com")
    cred, secret = _enable_and_create_credential(auth_client)
    # Revoke visible before mutating request's final check.
    auth_client.post(f"/api/v1/agent-credentials/{cred['id']}/revoke")
    denied = auth_client.post(
        "/api/v1/tasks",
        headers=_bearer(secret),
        json={"title": f"should-fail-{uid}"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "AGENT_CREDENTIAL_REVOKED"


def test_v6_setting_off_denies_at_gate_and_write(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v6{uid}", email=f"v6{uid}@example.com")
    _cred, secret = _enable_and_create_credential(auth_client)
    auth_client.patch("/api/v1/settings", json={"allow_agent_cli_access": False})
    gate = auth_client.get("/api/v1/auth/me", headers=_bearer(secret))
    assert gate.status_code == 403
    assert gate.json()["code"] == "AGENT_ACCESS_DISABLED"
    write = auth_client.post(
        "/api/v1/tasks",
        headers=_bearer(secret),
        json={"title": f"blocked-{uid}"},
    )
    assert write.status_code == 403
    assert write.json()["code"] == "AGENT_ACCESS_DISABLED"


# --- V8–V13 ---


def test_v8_user_agent_spoof_without_bearer_is_browser_only(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v8{uid}", email=f"v8{uid}@example.com")
    # Cookie session still browser path; no agent channel without Bearer.
    me = auth_client.get(
        "/api/v1/auth/me",
        headers={"User-Agent": "theplan-cli/0.7"},
    )
    assert me.status_code == 200
    # Credential admin still works via cookie (not agent).
    listed = auth_client.get(
        "/api/v1/agent-credentials",
        headers={"User-Agent": "theplan-cli/0.7"},
    )
    # Setting off by default → list OK (empty), proves UA did not grant agent admin bypass.
    assert listed.status_code == 200


def test_v9_secret_not_in_list(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v9{uid}", email=f"v9{uid}@example.com")
    created, secret = _enable_and_create_credential(auth_client)
    listed = auth_client.get("/api/v1/agent-credentials")
    assert listed.status_code == 200
    payload = listed.text
    assert secret not in payload
    assert "secret_hash" not in payload
    assert all("secret" not in row for row in listed.json())


def test_v10_agent_cannot_admin(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v10{uid}", email=f"v10{uid}@example.com")
    _cred, secret = _enable_and_create_credential(auth_client)
    create = auth_client.post(
        "/api/v1/agent-credentials",
        headers=_bearer(secret),
        json={"label": "nope"},
    )
    assert create.status_code == 403
    assert create.json()["code"] == "AGENT_CREDENTIAL_CANNOT_ADMIN"
    toggle = auth_client.patch(
        "/api/v1/settings",
        headers=_bearer(secret),
        json={"allow_agent_cli_access": False},
    )
    assert toggle.status_code == 403
    assert toggle.json()["code"] == "AGENT_CREDENTIAL_CANNOT_ADMIN"


def test_v11_mixed_denied_bearer_not_browser_success(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v11{uid}", email=f"v11{uid}@example.com")
    cred, secret = _enable_and_create_credential(auth_client)
    auth_client.post(f"/api/v1/agent-credentials/{cred['id']}/revoke")
    # Cookie still valid on client; Bearer revoked → agent error, not browser success.
    denied = auth_client.get("/api/v1/auth/me", headers=_bearer(secret))
    assert denied.status_code == 403
    assert denied.json()["code"] == "AGENT_CREDENTIAL_REVOKED"
    unknown = auth_client.get(
        "/api/v1/auth/me",
        headers=_bearer("tp_agent_" + "0" * 32 + "_notarealsecret"),
    )
    assert unknown.status_code == 401
    assert unknown.json()["code"] == "UNAUTHENTICATED"


def test_v12_credential_admin_rejects_mixed_bearer(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v12{uid}", email=f"v12{uid}@example.com")
    _cred, secret = _enable_and_create_credential(auth_client)
    before = auth_client.get("/api/v1/agent-credentials")
    assert before.status_code == 200
    count = len(before.json())
    mixed = auth_client.post(
        "/api/v1/agent-credentials",
        headers=_bearer(secret),
        json={"label": "mixed-nope"},
    )
    assert mixed.status_code == 403
    assert mixed.json()["code"] == "AGENT_CREDENTIAL_CANNOT_ADMIN"
    after = auth_client.get("/api/v1/agent-credentials")
    assert len(after.json()) == count


def test_v13_valid_cookie_and_bearer_uses_agent_path(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    _register(auth_client, username=f"v13{uid}", email=f"v13{uid}@example.com")
    _cred, secret = _enable_and_create_credential(auth_client)
    # Cookie present on TestClient + Bearer → agent path (still succeeds).
    me = auth_client.get("/api/v1/auth/me", headers=_bearer(secret))
    assert me.status_code == 200
    # Admin still rejected when Bearer present.
    admin = auth_client.get("/api/v1/agent-credentials", headers=_bearer(secret))
    assert admin.status_code == 403
    assert admin.json()["code"] == "AGENT_CREDENTIAL_CANNOT_ADMIN"


def test_v7_browser_password_login_unchanged(auth_client: TestClient) -> None:
    uid = uuid.uuid4().hex[:8]
    username = f"v7{uid}"
    _register(auth_client, username=username, email=f"{username}@example.com")
    auth_client.post("/api/v1/auth/logout")
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": TEST_PASSWORD},
        headers={"User-Agent": "theplan-cli/0.7"},
    )
    assert login.status_code == 200, login.text
