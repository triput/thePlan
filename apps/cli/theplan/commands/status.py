from __future__ import annotations

import argparse
from typing import Any

import httpx

from theplan.api_client import api_base_url, api_error_from_response, api_json
from theplan.errors import CliError
from theplan.output import emit_ok


def register_status(sub: argparse._SubParsersAction) -> None:
    sub.add_parser("status", help="API health, session user, and assist readiness")


def _try_health() -> dict[str, Any]:
    url = f"{api_base_url()}/health"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
    except httpx.RequestError as exc:
        return {"ok": False, "code": "API_UNAVAILABLE", "message": str(exc)}
    if response.status_code >= 400:
        err = api_error_from_response(response)
        return {"ok": False, "code": err.code, "message": err.message}
    try:
        body = response.json()
    except Exception:
        body = {"status": response.text}
    if isinstance(body, dict):
        return {"ok": True, **body}
    return {"ok": True, "data": body}


def _try_authed(path: str) -> dict[str, Any]:
    try:
        body = api_json("GET", path, persist_session=True)
    except CliError as exc:
        return {"ok": False, "code": exc.code, "message": exc.message}
    return {"ok": True, **(body or {})}


def run_status(_args: argparse.Namespace) -> None:
    health = _try_health()
    if not health.get("ok"):
        raise CliError(
            code=str(health.get("code", "API_UNAVAILABLE")),
            message=str(health.get("message", "API unreachable")),
            exit_code=4,
        )
    payload: dict[str, Any] = {
        "api_url": api_base_url(),
        "health": health,
        "auth": _try_authed("/api/v1/auth/me"),
        "assist": _try_authed("/api/v1/assist/status"),
    }
    emit_ok(payload)
