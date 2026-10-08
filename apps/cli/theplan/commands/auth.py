from __future__ import annotations

import argparse

import httpx

from theplan.api_client import api_json, api_logout
from theplan.db_session import api_db_session
from theplan.input_helpers import resolve_password
from theplan.output import emit_ok
from theplan.recovery import run_reset_password


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

    login = auth_sub.add_parser("login", help="Log in via API (session cookie file)")
    login.add_argument("--identifier", required=True, help="Username or email")
    login_mode = login.add_mutually_exclusive_group(required=True)
    login_mode.add_argument("--password", metavar="Y", help="Account password")
    login_mode.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read password from a pipe/redirect (or --interactive prompt)",
    )

    auth_sub.add_parser("logout", help="Log out via API and clear session file")
    auth_sub.add_parser("me", help="Current session user via API")


def _run_login(args: argparse.Namespace) -> None:
    secret = resolve_password(password=args.password, password_stdin=args.password_stdin)
    body = api_json(
        "POST",
        "/api/v1/auth/login",
        json_body={"identifier": args.identifier.strip(), "password": secret},
        cookies=httpx.Cookies(),
        persist_session=True,
    )
    emit_ok(body or {})


def _run_logout() -> None:
    api_logout()
    emit_ok({"logged_out": True})


def _run_me() -> None:
    body = api_json("GET", "/api/v1/auth/me", persist_session=True)
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
