"""V7 (CLI): password login refused locally after cutover."""

from __future__ import annotations

import pytest

from theplan.commands.auth import _resolve_token
from theplan.errors import CliError


def test_password_login_retired_stable_code() -> None:
    args = type(
        "Args",
        (),
        {
            "password": "any-secret-value",
            "password_stdin": False,
            "identifier": "nebula",
            "token": None,
            "token_stdin": False,
            "interactive": False,
        },
    )()
    with pytest.raises(CliError) as excinfo:
        _resolve_token(args)
    assert excinfo.value.code == "CLI_PASSWORD_LOGIN_RETIRED"
    assert excinfo.value.exit_code == 2


def test_token_required_when_no_secret() -> None:
    args = type(
        "Args",
        (),
        {
            "password": None,
            "password_stdin": False,
            "identifier": None,
            "token": None,
            "token_stdin": False,
            "interactive": False,
        },
    )()
    with pytest.raises(CliError) as excinfo:
        _resolve_token(args)
    assert excinfo.value.code == "TOKEN_REQUIRED"
