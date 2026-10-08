"""Host-local recovery: mode exclusion, stdin, emit_ok shape, API exit mapping."""

from __future__ import annotations

import json
from io import StringIO
from uuid import UUID

import pytest

from app.api.errors import ApiError
from theplan.errors import CliError
from theplan.output import emit_ok
from theplan.recovery import run_reset_password

USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class _User:
    def __init__(self) -> None:
        self.id = USER_ID
        self.username = "trish"
        self.email = "trish@example.com"
        self.must_change_password = True


def _install_service(monkeypatch: pytest.MonkeyPatch, fn) -> None:
    monkeypatch.setattr("theplan.recovery._load_recovery_fn", lambda: fn)


def test_reset_password_requires_exactly_one_mode() -> None:
    with pytest.raises(CliError) as missing:
        run_reset_password(
            object(),
            user="trish",
            generate=False,
            password=None,
            password_stdin=False,
        )
    assert missing.value.code == "INVALID_USAGE"
    assert missing.value.exit_code == 1

    with pytest.raises(CliError) as both:
        run_reset_password(
            object(),
            user="trish",
            generate=True,
            password="correct horse battery staple",
            password_stdin=False,
        )
    assert both.value.code == "INVALID_USAGE"
    assert both.value.exit_code == 1

    with pytest.raises(CliError) as stdin_and_password:
        run_reset_password(
            object(),
            user="trish",
            generate=False,
            password="correct horse battery staple",
            password_stdin=True,
        )
    assert stdin_and_password.value.code == "INVALID_USAGE"


def test_reset_password_rejects_blank_user() -> None:
    with pytest.raises(CliError) as exc:
        run_reset_password(
            object(),
            user="   ",
            generate=True,
            password=None,
            password_stdin=False,
        )
    assert exc.value.code == "INVALID_USAGE"
    assert exc.value.exit_code == 1
    assert "--user" in exc.value.message


def test_reset_password_rejects_empty_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("\r\n"))
    with pytest.raises(CliError) as exc:
        run_reset_password(
            object(),
            user="trish",
            generate=False,
            password=None,
            password_stdin=True,
        )
    assert exc.value.code == "INVALID_PASSWORD"
    assert exc.value.exit_code == 1


def test_reset_password_stdin_strips_crlf(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fn(db, identifier, *, password, generate):
        seen["password"] = password
        seen["generate"] = generate
        seen["identifier"] = identifier
        return _User(), None

    _install_service(monkeypatch, fn)
    monkeypatch.setattr("sys.stdin", StringIO("quiet lantern harbor\r\n"))

    payload = run_reset_password(
        object(),
        user="  Trish  ",
        generate=False,
        password=None,
        password_stdin=True,
    )

    assert seen == {
        "password": "quiet lantern harbor",
        "generate": False,
        "identifier": "Trish",
    }
    assert "temporary_password" not in payload
    assert payload["user_id"] == str(USER_ID)


def test_generate_emit_ok_includes_temporary_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "temp-secret-value!!"

    def fn(db, identifier, *, password, generate):
        assert db is not None
        assert identifier == "trish@example.com"
        assert password is None
        assert generate is True
        return _User(), secret

    _install_service(monkeypatch, fn)
    payload = run_reset_password(
        object(),
        user="trish@example.com",
        generate=True,
        password=None,
        password_stdin=False,
    )
    emit_ok(payload)
    body = json.loads(capsys.readouterr().out)

    assert body == {
        "ok": True,
        "user_id": str(USER_ID),
        "username": "trish",
        "email": "trish@example.com",
        "must_change_password": True,
        "temporary_password": secret,
    }


def test_explicit_password_is_omitted_from_emit_ok(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    chosen = "quiet lantern harbor road"

    def fn(db, identifier, *, password, generate):
        assert password == chosen
        assert generate is False
        # A leaky service return must still stay out of explicit-mode JSON.
        return _User(), "should-not-leak"

    _install_service(monkeypatch, fn)
    payload = run_reset_password(
        object(),
        user="trish",
        generate=False,
        password=chosen,
        password_stdin=False,
    )
    emit_ok(payload)
    raw = capsys.readouterr().out
    body = json.loads(raw)

    assert body["ok"] is True
    assert "temporary_password" not in body
    assert chosen not in raw
    assert "should-not-leak" not in raw


@pytest.mark.parametrize(
    ("status", "code", "exit_code"),
    [
        (404, "USER_NOT_FOUND", 3),
        (422, "INVALID_PASSWORD", 1),
        (409, "CONFLICT", 5),
        (500, "INTERNAL", 4),
    ],
)
def test_reset_password_maps_api_status_to_exit(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    code: str,
    exit_code: int,
) -> None:
    def fn(db, identifier, *, password, generate):
        raise ApiError(status, "recovery failed", code)

    _install_service(monkeypatch, fn)
    with pytest.raises(CliError) as exc:
        run_reset_password(
            object(),
            user="trish",
            generate=True,
            password=None,
            password_stdin=False,
        )
    assert exc.value.code == code
    assert exc.value.message == "recovery failed"
    assert exc.value.exit_code == exit_code


def test_reset_password_maps_unexpected_errors_to_exit_4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fn(db, identifier, *, password, generate):
        raise RuntimeError("db down")

    _install_service(monkeypatch, fn)
    with pytest.raises(CliError) as exc:
        run_reset_password(
            object(),
            user="trish",
            generate=True,
            password=None,
            password_stdin=False,
        )
    assert exc.value.code == "API_ERROR"
    assert exc.value.exit_code == 4
    assert "db down" in exc.value.message
