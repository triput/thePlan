"""CLI Bearer-only + origin binding (Dex 1793145567.172009)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from theplan.api_client import api_request
from theplan.commands.auth import _resolve_token, _run_login
from theplan.errors import CliError
from theplan.session_file import (
    load_bearer_token,
    normalize_api_origin,
    peek_bearer_token_unbound,
    save_bearer_token,
)


def test_normalize_api_origin_effective_port() -> None:
    assert normalize_api_origin("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert normalize_api_origin("http://127.0.0.1") == "http://127.0.0.1:80"
    assert normalize_api_origin("https://api.example.com") == "https://api.example.com:443"


def test_legacy_cookie_session_fails_closed_no_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "session"
    monkeypatch.setenv("THEPLAN_SESSION_FILE", str(path))
    monkeypatch.setenv("THEPLAN_API_URL", "http://127.0.0.1:8000")
    # Legacy cookie jar only — setting-off scenario: must not send that cookie.
    path.write_text(
        json.dumps([{"name": "session", "value": "legacy-cookie", "domain": "127.0.0.1", "path": "/"}])
        + "\n",
        encoding="utf-8",
    )

    called: list[object] = []

    class BoomClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            called.append(("init", kwargs.get("cookies")))

        def __enter__(self) -> BoomClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def request(self, *args: object, **kwargs: object) -> httpx.Response:
            called.append(("request", args, kwargs))
            raise AssertionError("network must not be reached without Bearer")

    with patch("theplan.api_client.httpx.Client", BoomClient):
        with pytest.raises(CliError) as excinfo:
            api_request("GET", "/api/v1/auth/me")
    assert excinfo.value.code == "CLI_BEARER_REQUIRED"
    assert called == []  # Client never constructed → no cookie attached to a request


def test_origin_mismatch_refuses_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "session"
    monkeypatch.setenv("THEPLAN_SESSION_FILE", str(path))
    monkeypatch.setenv("THEPLAN_API_URL", "http://127.0.0.1:8000")
    save_bearer_token("tp_agent_" + "a" * 32 + "_synthetic", api_origin="http://127.0.0.1:8000")

    monkeypatch.setenv("THEPLAN_API_URL", "http://127.0.0.1:9000")

    with patch("theplan.api_client.httpx.Client") as client_cls:
        with pytest.raises(CliError) as excinfo:
            load_bearer_token()
        assert excinfo.value.code == "CLI_SESSION_ORIGIN_MISMATCH"
        client_cls.assert_not_called()

        with pytest.raises(CliError) as excinfo2:
            api_request("GET", "/api/v1/tasks")
        assert excinfo2.value.code == "CLI_SESSION_ORIGIN_MISMATCH"
        client_cls.assert_not_called()


def test_login_validates_before_persist_preserves_prior_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "session"
    monkeypatch.setenv("THEPLAN_SESSION_FILE", str(path))
    monkeypatch.setenv("THEPLAN_API_URL", "http://127.0.0.1:8000")
    prior = "tp_agent_" + "b" * 32 + "_prior"
    save_bearer_token(prior, api_origin="http://127.0.0.1:8000")
    assert peek_bearer_token_unbound() == prior

    def boom_api_json(*args: object, **kwargs: object) -> None:
        raise CliError(code="UNAUTHENTICATED", message="bad", exit_code=2)

    monkeypatch.setattr("theplan.commands.auth.api_json", boom_api_json)
    args = SimpleNamespace(
        token="tp_agent_" + "c" * 32 + "_bad",
        token_stdin=False,
        password=None,
        password_stdin=False,
        identifier=None,
        interactive=False,
    )
    with pytest.raises(CliError) as excinfo:
        _run_login(args)
    assert excinfo.value.code == "UNAUTHENTICATED"
    # Previous valid session preserved.
    assert peek_bearer_token_unbound() == prior
    assert load_bearer_token() == prior


def test_login_success_persists_origin_bound_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "session"
    monkeypatch.setenv("THEPLAN_SESSION_FILE", str(path))
    monkeypatch.setenv("THEPLAN_API_URL", "https://api.example.com")
    secret = "tp_agent_" + "d" * 32 + "_ok"

    monkeypatch.setattr(
        "theplan.commands.auth.api_json",
        lambda *a, **k: {"id": "user-1", "username": "nebula"},
    )
    monkeypatch.setattr("theplan.commands.auth.emit_ok", lambda payload: None)
    args = SimpleNamespace(
        token=secret,
        token_stdin=False,
        password=None,
        password_stdin=False,
        identifier=None,
        interactive=False,
    )
    _run_login(args)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["bearer_token"] == secret
    assert raw["api_origin"] == "https://api.example.com:443"
    assert load_bearer_token() == secret


def test_interactive_token_uses_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("theplan.commands.auth.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "theplan.commands.auth.getpass.getpass",
        lambda prompt="": "  tp_agent_secret_from_getpass  ",
    )
    args = SimpleNamespace(
        token=None,
        token_stdin=True,
        password=None,
        password_stdin=False,
        identifier=None,
        interactive=True,
    )
    assert _resolve_token(args) == "tp_agent_secret_from_getpass"
