"""Isolated fake-only entry for covering-refresh HTTP harness (review / Dex).

REVISE2: disable pytest plugin autoload **before** importing pytest; clear ambient
``PYTEST_ADDOPTS`` / ``PYTEST_PLUGINS``; use an explicit empty ``-c`` config;
install complete synthetic Settings env with dotenv disabled and credential-like
ambient env scrubbed; engine connect tripwire; ``-x``; no bytecode/cache writes.

Code-prep packet: proposed verification only â€” does **not** authorize DB bind,
household Postgres, or live provider access.

---------------------------------------------------------------------------
Interpreter / dependency source (for later launch review â€” not bare ``python``)
---------------------------------------------------------------------------
Build or reuse a venv whose site-packages match::

    workspace-copy/apps/api/requirements.txt

Example (launch review only)::

    Set-Location "...\\workspace-copy\\apps\\api"
    py -3.11 -m venv .venv-covering-harness-offline
    .\\.venv-covering-harness-offline\\Scripts\\python.exe -m pip install -r requirements.txt
    .\\.venv-covering-harness-offline\\Scripts\\python.exe .\\tests\\support\\run_covering_refresh_http_harness_offline.py

Document the concrete ``sys.executable`` from that venv in the launch review
receipt. Do not rely on ambient PATH ``python``.

PowerShell argv (after the venv exists)::

    Set-Location "F:\\DropFolder\\pending\\covering-refresh-http-harness-v1-2026-11-09\\workspace-copy\\apps\\api"
    .\\.venv-covering-harness-offline\\Scripts\\python.exe .\\tests\\support\\run_covering_refresh_http_harness_offline.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SUPPORT_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _SUPPORT_DIR.parent
_API_ROOT = _TESTS_DIR.parent
_EMPTY_PYTEST_INI = _SUPPORT_DIR / "_empty_pytest.ini"
_REQUIREMENTS = _API_ROOT / "requirements.txt"

HARNESS_SESSION_SECRET = "covering-refresh-http-harness-offline-session-secret-v1"
# Unbound dial target â€” connect must tripwire; never a household/profile bind.
UNBOUND_DATABASE_URL = (
    "postgresql+psycopg://unbound_harness:unbound@127.0.0.1:1/unbound_covering_harness"
)

# Credential-shaped / provider keys â€” scrub ambient values before Settings loads.
_CREDENTIAL_ENV_KEYS = frozenset(
    {
        "DATABASE_URL",
        "SESSION_SECRET",
        "DEMO_NEBULA_PASSWORD",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "GOOGLE_CLIENT_SECRETS_FILE",
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET",
        "MICROSOFT_REDIRECT_URI",
        "TOKEN_ENCRYPTION_KEY",
        "FREE_BUSY_RESOLVER_ALLOWLIST_PATH",
    }
)


def _scrub_ambient_credential_env() -> None:
    for key in list(os.environ):
        upper = key.upper()
        if upper in _CREDENTIAL_ENV_KEYS:
            del os.environ[key]
            continue
        # Catch alternate casings / leaked secret-ish names without reading values.
        if any(
            token in upper
            for token in (
                "CLIENT_SECRET",
                "CLIENT_ID",
                "ENCRYPTION_KEY",
                "NEBULA_PASSWORD",
                "SECRETS_FILE",
            )
        ):
            del os.environ[key]


def _install_complete_synthetic_settings_env() -> None:
    """Full Settings field coverage via env; dotenv file loading disabled below."""
    os.environ["DATABASE_URL"] = UNBOUND_DATABASE_URL
    os.environ["SESSION_SECRET"] = HARNESS_SESSION_SECRET
    os.environ["SEED_DEMO_USER"] = "false"
    os.environ["SESSION_HTTPS_ONLY"] = "false"
    os.environ["SESSION_MAX_AGE_SECONDS"] = "1209600"
    os.environ["BOOTSTRAP_USER_ID"] = "00000000-0000-0000-0000-000000000001"
    os.environ["BOOTSTRAP_USER_EMAIL"] = "harness-offline@localhost"
    os.environ["BOOTSTRAP_USER_DISPLAY_NAME"] = "Harness Offline"
    os.environ["FRONTEND_ORIGIN"] = "http://127.0.0.1:9"
    os.environ["CORS_ORIGINS"] = '["http://127.0.0.1:9"]'
    os.environ["SCHEDULE_DISPATCH"] = "external"
    os.environ["SCHEDULE_POLL_SECONDS"] = "2.0"
    os.environ["ASSIST_ENABLED"] = "false"
    os.environ["ASSIST_BASE_URL"] = "http://127.0.0.1:9/v1"
    os.environ["ASSIST_MODEL"] = "harness-offline"
    os.environ["ASSIST_TIMEOUT_SECONDS"] = "1.0"
    os.environ["MICROSOFT_TENANT_ID"] = "common"
    os.environ["GOOGLE_OAUTH_SCOPES"] = (
        "https://www.googleapis.com/auth/calendar.events "
        "https://www.googleapis.com/auth/calendar.calendarlist.readonly"
    )
    os.environ["MICROSOFT_OAUTH_SCOPES"] = "Calendars.ReadWrite offline_access User.Read"
    # Explicit empty â€” never inherit ambient provider credentials.
    os.environ["DEMO_NEBULA_PASSWORD"] = ""
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_CLIENT_SECRET"] = ""
    os.environ["GOOGLE_REDIRECT_URI"] = ""
    os.environ["GOOGLE_CLIENT_SECRETS_FILE"] = ""
    os.environ["MICROSOFT_CLIENT_ID"] = ""
    os.environ["MICROSOFT_CLIENT_SECRET"] = ""
    os.environ["MICROSOFT_REDIRECT_URI"] = ""
    os.environ["TOKEN_ENCRYPTION_KEY"] = ""
    os.environ["FREE_BUSY_RESOLVER_ALLOWLIST_PATH"] = ""


def _disable_dotenv_on_settings() -> None:
    """Exclude ``env_file='.env'`` before any ``get_settings()`` / dependent import."""
    from pydantic_settings import SettingsConfigDict

    import app.config as config_mod

    config_mod.Settings.model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    config_mod.get_settings.cache_clear()


def _install_engine_connect_tripwire() -> None:
    import sqlalchemy

    real_create_engine = sqlalchemy.create_engine

    def create_engine_with_connect_tripwire(*args: object, **kwargs: object):  # noqa: ANN001
        engine = real_create_engine(*args, **kwargs)

        def _trip(*_a: object, **_k: object) -> None:
            raise RuntimeError(
                "covering harness: engine connect/raw_connection tripwire â€” "
                "DB endpoint unbound (fake-only entry)"
            )

        engine.connect = _trip  # type: ignore[method-assign]
        engine.raw_connection = _trip  # type: ignore[method-assign]
        return engine

    sqlalchemy.create_engine = create_engine_with_connect_tripwire  # type: ignore[assignment]


def install_offline_guards() -> None:
    """Synthetic settings (no dotenv / no ambient creds) + engine tripwire."""
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    _scrub_ambient_credential_env()
    _install_complete_synthetic_settings_env()
    _install_engine_connect_tripwire()
    _disable_dotenv_on_settings()


def _clear_ambient_pytest_overrides() -> None:
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST"):
        os.environ.pop(key, None)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    api = str(_API_ROOT)
    tests = str(_TESTS_DIR)
    if api not in sys.path:
        sys.path.insert(0, api)
    if tests not in sys.path:
        sys.path.insert(0, tests)

    # Must precede ``import pytest`` so setuptools/entry-point plugins stay cold.
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    _clear_ambient_pytest_overrides()

    install_offline_guards()

    import pytest

    if not _EMPTY_PYTEST_INI.is_file():
        raise SystemExit(f"missing empty pytest config: {_EMPTY_PYTEST_INI}")
    if not _REQUIREMENTS.is_file():
        raise SystemExit(f"missing dependency pin file: {_REQUIREMENTS}")

    target = str(_TESTS_DIR / "test_covering_refresh_http_harness.py")
    # -c empty ini: skip ambient pytest.ini / pyproject pytest discovery.
    # --noconftest: skip shared tests/conftest.py.
    # -x: first-failure stop. -p no:cacheprovider: no cache writes.
    return int(
        pytest.main(
            [
                "-c",
                str(_EMPTY_PYTEST_INI),
                "--noconftest",
                "-p",
                "no:cacheprovider",
                "-x",
                "-q",
                "--tb=short",
                target,
                str(_TESTS_DIR / "test_covering_http_connector_seam.py"),
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
