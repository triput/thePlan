"""V5b / V5d / Boundary A commit-guard — real multi-connection interleavings.

Proves (on disposable ``theplan_agent_cli_test`` @ 044 only):

* **V5b:** revoke committed on connection R before peer B reaches final
  ``before_commit`` check → B aborts ``AGENT_CREDENTIAL_REVOKED``; second
  credential for same owner still commits.
* **V5d:** two mutating sessions each pass final check (barrier), then revoke
  commits, then both complete ``Session.commit`` without re-check — both
  writes stand (documented Boundary A TOCTOU). Not a product failure.
* **Commit-guard / side session:** agent mutating ContextVar active + revoke
  visible → a *different* ``SessionLocal().commit()`` (not the request
  session monkeypatch) also aborts. Covers alternate durable-write sessions.

No household / no new migration apply.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db import SessionLocal
from app.models import AgentCredential, Task, User, UserSettings
from app.services import agent_auth_context as agent_ctx
from app.services.agent_auth_context import bind_session_agent_guard
from app.services.agent_credentials import (
    assert_agent_write_still_authorized,
    create_agent_credential,
)
from app.services.passwords import hash_password

_REQUIRED_DATABASE = "theplan_agent_cli_test"
_REQUIRED_REVISION = "044_agent_cli_access"
_PROBE_EMAIL_LIKE = "renee-agent-cli-%@example.com"
_PASSWORD = "correct horse battery staple"


def _open_checked() -> Session:
    db = SessionLocal()
    try:
        name = db.execute(text("SELECT current_database()")).scalar()
    except Exception:
        db.close()
        raise
    if name != _REQUIRED_DATABASE:
        db.close()
        raise AssertionError(
            f"agent CLI concurrency refuses database {name!r}; "
            f"set DATABASE_URL to disposable {_REQUIRED_DATABASE}"
        )
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    if version != _REQUIRED_REVISION:
        db.close()
        raise AssertionError(
            f"disposable alembic {version!r}; expected {_REQUIRED_REVISION} "
            "(do not upgrade household)"
        )
    return db


@pytest.fixture(autouse=True)
def _disposable_agent_cli_db() -> None:
    db = _open_checked()
    db.close()


def _purge_probes() -> None:
    db = _open_checked()
    try:
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
        db.execute(
            text("DELETE FROM users WHERE email LIKE :pattern"),
            {"pattern": _PROBE_EMAIL_LIKE},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@dataclass
class _Seed:
    owner_id: uuid.UUID
    cred_a_id: uuid.UUID
    secret_a: str
    cred_b_id: uuid.UUID
    secret_b: str


def _seed_owner_with_two_credentials() -> _Seed:
    _purge_probes()
    token = uuid.uuid4().hex[:12]
    db = _open_checked()
    try:
        user = User(
            email=f"renee-agent-cli-{token}@example.com",
            username=f"reneeacl{token}",
            password_hash=hash_password(_PASSWORD),
            display_name="Agent CLI probe",
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
                allow_agent_cli_access_grandfathered=False,
            )
        )
        db.commit()
        db.refresh(user)
        row_a, secret_a = create_agent_credential(db, user, label="cred-a")
        row_b, secret_b = create_agent_credential(db, user, label="cred-b")
        return _Seed(
            owner_id=user.id,
            cred_a_id=row_a.id,
            secret_a=secret_a,
            cred_b_id=row_b.id,
            secret_b=secret_b,
        )
    finally:
        db.close()


def test_v5b_revoke_before_final_check_aborts_peer_other_cred_ok() -> None:
    """Revoke visible before B's before_commit → B aborts; credential A still writes."""
    seed = _seed_owner_with_two_credentials()
    try:
        # Peer B: mutate under ContextVar, flush, then wait for revoke.
        ready = threading.Event()
        revoked = threading.Event()
        outcome: dict[str, object] = {}

        def peer_b() -> None:
            db = _open_checked()
            token = agent_ctx.set_agent_mutating_credential(seed.cred_b_id)
            bind_session_agent_guard(db, seed.cred_b_id)
            try:
                db.add(
                    Task(
                        owner_id=seed.owner_id,
                        title=f"v5b-b-{uuid.uuid4().hex[:8]}",
                    )
                )
                db.flush()
                ready.set()
                assert revoked.wait(timeout=10), "revoke did not signal"
                try:
                    db.commit()
                    outcome["b"] = "committed"
                except ApiError as exc:
                    outcome["b"] = exc.content.get("code")
                    db.rollback()
            finally:
                agent_ctx.reset_agent_mutating_credential(token)
                db.close()

        t = threading.Thread(target=peer_b, name="v5b-b", daemon=True)
        t.start()
        assert ready.wait(timeout=10)

        from datetime import datetime, timezone

        rev = _open_checked()
        try:
            row = rev.get(AgentCredential, seed.cred_b_id)
            assert row is not None
            row.revoked_at = datetime.now(timezone.utc)
            rev.commit()
        finally:
            rev.close()
        revoked.set()
        t.join(timeout=15)
        assert not t.is_alive()
        assert outcome.get("b") == "AGENT_CREDENTIAL_REVOKED"

        # Second credential unaffected.
        db_a = _open_checked()
        token_a = agent_ctx.set_agent_mutating_credential(seed.cred_a_id)
        bind_session_agent_guard(db_a, seed.cred_a_id)
        try:
            db_a.add(
                Task(
                    owner_id=seed.owner_id,
                    title=f"v5b-a-{uuid.uuid4().hex[:8]}",
                )
            )
            db_a.commit()
            outcome["a"] = "committed"
        finally:
            agent_ctx.reset_agent_mutating_credential(token_a)
            db_a.close()
        assert outcome.get("a") == "committed"
    finally:
        _purge_probes()


@dataclass
class _V5dState:
    errors: list[str] = field(default_factory=list)
    committed: list[str] = field(default_factory=list)


def test_v5d_toctou_both_past_final_check_may_commit_after_revoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both peers pass final check → revoke commits → both commits stand (TOCTOU)."""
    seed = _seed_owner_with_two_credentials()
    state = _V5dState()
    checks_passed = threading.Barrier(3)  # peer1, peer2, revoker
    revoke_done = threading.Event()
    real_assert = assert_agent_write_still_authorized

    def hooked_assert(db: Session, credential_id: uuid.UUID) -> None:
        real_assert(db, credential_id)
        # Rendezvous after successful final check; wait until revoke has committed.
        checks_passed.wait(timeout=15)
        assert revoke_done.wait(timeout=15), "revoke did not complete"
        # Intentionally no re-check — models the post-check TOCTOU window.

    # before_commit does `from agent_credentials import assert_...` each call.
    monkeypatch.setattr(
        "app.services.agent_credentials.assert_agent_write_still_authorized",
        hooked_assert,
    )

    def peer(name: str, cred_id: uuid.UUID) -> None:
        db = _open_checked()
        token = agent_ctx.set_agent_mutating_credential(cred_id)
        bind_session_agent_guard(db, cred_id)
        try:
            db.add(
                Task(
                    owner_id=seed.owner_id,
                    title=f"v5d-{name}-{uuid.uuid4().hex[:8]}",
                )
            )
            db.commit()
            state.committed.append(name)
        except Exception as exc:
            state.errors.append(f"{name}:{type(exc).__name__}:{exc}")
            db.rollback()
        finally:
            agent_ctx.reset_agent_mutating_credential(token)
            db.close()

    try:
        t1 = threading.Thread(
            target=peer, args=("p1", seed.cred_a_id), name="v5d-p1", daemon=True
        )
        t2 = threading.Thread(
            target=peer, args=("p2", seed.cred_b_id), name="v5d-p2", daemon=True
        )
        t1.start()
        t2.start()

        # Revoker: wait until both passed final check, revoke, then release peers.
        checks_passed.wait(timeout=15)
        from datetime import datetime, timezone

        rev = _open_checked()
        try:
            now = datetime.now(timezone.utc)
            for cid in (seed.cred_a_id, seed.cred_b_id):
                row = rev.get(AgentCredential, cid)
                assert row is not None
                row.revoked_at = now
            rev.commit()
        finally:
            rev.close()
        revoke_done.set()

        t1.join(timeout=20)
        t2.join(timeout=20)
        assert not t1.is_alive() and not t2.is_alive()
        assert state.errors == [], state.errors
        assert sorted(state.committed) == ["p1", "p2"]

        # Subsequent request denied at auth gate / final check.
        db = _open_checked()
        token = agent_ctx.set_agent_mutating_credential(seed.cred_a_id)
        try:
            db.add(Task(owner_id=seed.owner_id, title="after-revoke-should-fail"))
            with pytest.raises(ApiError) as excinfo:
                db.commit()
            assert excinfo.value.content["code"] == "AGENT_CREDENTIAL_REVOKED"
            db.rollback()
        finally:
            agent_ctx.reset_agent_mutating_credential(token)
            db.close()
    finally:
        _purge_probes()


def test_boundary_a_side_session_commit_sees_revoke() -> None:
    """Side SessionLocal.commit under agent ContextVar aborts when revoke is visible.

    Proves coverage is not limited to wrapping the request Session.commit.
    """
    seed = _seed_owner_with_two_credentials()
    try:
        from datetime import datetime, timezone

        rev = _open_checked()
        try:
            row = rev.get(AgentCredential, seed.cred_a_id)
            assert row is not None
            row.revoked_at = datetime.now(timezone.utc)
            rev.commit()
        finally:
            rev.close()

        token = agent_ctx.set_agent_mutating_credential(seed.cred_a_id)
        side = _open_checked()
        bind_session_agent_guard(side, seed.cred_a_id)
        try:
            side.add(
                Task(
                    owner_id=seed.owner_id,
                    title=f"side-{uuid.uuid4().hex[:8]}",
                )
            )
            with pytest.raises(ApiError) as excinfo:
                side.commit()
            assert excinfo.value.content["code"] == "AGENT_CREDENTIAL_REVOKED"
            side.rollback()
        finally:
            agent_ctx.reset_agent_mutating_credential(token)
            side.close()
    finally:
        _purge_probes()
