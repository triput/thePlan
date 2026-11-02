from __future__ import annotations

import argparse
import getpass
import sys

from theplan.api_client import api_json, api_logout
from theplan.db_session import api_db_session
from theplan.errors import CliError
from theplan.output import emit_ok
from theplan.recovery import run_reset_password
from theplan.session_file import normalize_api_origin, save_bearer_token


def register_auth(sub: argparse._SubParsersAction) -> None:
    auth = sub.add_parser("auth", help="Authentication and account recovery")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    reset = auth_sub.add_parser(
        "reset-password",
        help="Host-local password recovery (DATABASE_URL, no HTTP)",
    )
    reset.add_argument("--user", required=True, help="Username or email")
    mode = reset.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--generate",
        action="store_true",
        help="Generate a temporary password (included in JSON output)",
    )
    mode.add_argument(
        "--password",
        metavar="X",
        help="Set explicit new password (never logged)",
    )
    mode.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read new password from a pipe/redirect (or --interactive prompt)",
    )

    login = auth_sub.add_parser(
        "login",
        help="Log in with an agent/CLI credential (Bearer token)",
    )
    login.add_argument(
        "--token",
        metavar="SECRET",
        help="Agent credential secret (tp_agent_…); never logged",
    )
    login.add_argument(
        "--token-stdin",
        action="store_true",
        help="Read agent credential secret from stdin (or --interactive getpass)",
    )
    # Retired password login — fail closed with a stable code (do not call /auth/login).
    login.add_argument("--identifier", help=argparse.SUPPRESS)
    login.add_argument("--password", metavar="Y", help=argparse.SUPPRESS)
    login.add_argument("--password-stdin", action="store_true", help=argparse.SUPPRESS)

    auth_sub.add_parser("logout", help="Clear local agent/CLI session file")
    auth_sub.add_parser("me", help="Current session user via API")


def _resolve_token(args: argparse.Namespace) -> str:
    if getattr(args, "password", None) or getattr(args, "password_stdin", False) or getattr(
        args, "identifier", None
    ):
        raise CliError(
            code="CLI_PASSWORD_LOGIN_RETIRED",
            message=(
                "CLI password login is retired. Create an agent credential in the web app "
                "(Allow agent and CLI access) and run: theplan auth login --token <secret>"
            ),
            exit_code=2,
        )
    if args.token and args.token_stdin:
        raise CliError(
            code="TOKEN_REQUIRED",
            message="Pass only one of --token or --token-stdin",
            exit_code=1,
        )
    if args.token_stdin:
        if sys.stdin.isatty():
            if not getattr(args, "interactive", False):
                raise CliError(
                    code="TOKEN_REQUIRED",
                    message="Pass --token, pipe secret to --token-stdin, or use --interactive",
                    exit_code=1,
                )
            secret = getpass.getpass("Agent credential secret: ").strip()
        else:
            secret = sys.stdin.readline().strip()
    else:
        secret = (args.token or "").strip()
    if not secret:
        raise CliError(
            code="TOKEN_REQUIRED",
            message="Agent credential secret required: --token or --token-stdin",
            exit_code=1,
        )
    return secret


def _run_login(args: argparse.Namespace) -> None:
    secret = _resolve_token(args)
    # Validate candidate **before** persist — previous session file stays intact on failure.
    body = api_json(
        "GET",
        "/api/v1/auth/me",
        bearer=secret,
        persist_session=False,
    )
    save_bearer_token(secret, api_origin=normalize_api_origin())
    emit_ok(body or {"authenticated": True, "api_origin": normalize_api_origin()})


def _run_logout() -> None:
    api_logout()
    emit_ok({"logged_out": True})


def _run_me() -> None:
    body = api_json("GET", "/api/v1/auth/me", persist_session=False)
    emit_ok(body or {})


def run_auth(args: argparse.Namespace) -> None:
    cmd = args.auth_command
    if cmd == "reset-password":
        with api_db_session() as db:
            payload = run_reset_password(
                db,
                user=args.user,
                generate=args.generate,
                password=args.password,
                password_stdin=args.password_stdin,
            )
        emit_ok(payload)
        return
    if cmd == "login":
        _run_login(args)
        return
    if cmd == "logout":
        _run_logout()
        return
    if cmd == "me":
        _run_me()
        return
