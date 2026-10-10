# ==============================================================================
#  File: apps/cli/theplan/api_client.py
#  Description: HTTP helpers for thePlan CLI — base URL, session cookies, and JSON API calls.
#  Component: CLI
#  Version: 1.0
#  Created: 2026-10-09
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations

import json
from typing import Any

import httpx

from theplan.errors import CliError, exit_code_for_api_status
from theplan.session_file import clear_session_file, load_cookies, save_cookies


def api_base_url() -> str:
    import os

    return os.environ.get("THEPLAN_API_URL", "http://127.0.0.1:8000").rstrip("/")


def api_error_from_response(response: httpx.Response) -> CliError:
    status = response.status_code
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    detail = body.get("detail", response.text or f"HTTP {status}")
    if isinstance(detail, list):
        message = json.dumps(detail, default=str)
        code = str(body.get("code", "VALIDATION_ERROR"))
    else:
        message = str(detail)
        code = str(body.get("code", "API_ERROR"))
    extra = {key: value for key, value in body.items() if key not in {"detail", "code"}}
    return CliError(
        code=code,
        message=message,
        exit_code=exit_code_for_api_status(status),
        extra=extra or None,
    )


def _parse_success_json(response: httpx.Response) -> dict[str, Any] | None:
    if response.status_code == 204 or not response.content:
        return None
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise CliError(
            code="INVALID_RESPONSE",
            message=f"API returned non-JSON body (HTTP {response.status_code})",
            exit_code=4,
        ) from exc
    if isinstance(data, dict):
        return data
    return {"data": data}


def api_request(
    method: str,
    path: str,
    *,
    json_body: dict | list | None = None,
    params: dict[str, Any] | None = None,
    cookies: httpx.Cookies | None = None,
    persist_session: bool = False,
) -> httpx.Response:
    url = f"{api_base_url()}{path}"
    jar = cookies if cookies is not None else load_cookies()
    try:
        with httpx.Client(timeout=30.0, cookies=jar) as client:
            response = client.request(method, url, json=json_body, params=params)
            if persist_session:
                save_cookies(client.cookies)
            return response
    except httpx.RequestError as exc:
        raise CliError(
            code="API_UNAVAILABLE",
            message=f"Could not reach API at {api_base_url()}: {exc}",
            exit_code=4,
        ) from exc


def api_json(
    method: str,
    path: str,
    *,
    json_body: dict | list | None = None,
    params: dict[str, Any] | None = None,
    cookies: httpx.Cookies | None = None,
    persist_session: bool = False,
    allowed_status: frozenset[int] | None = None,
) -> dict[str, Any] | None:
    response = api_request(
        method,
        path,
        json_body=json_body,
        params=params,
        cookies=cookies,
        persist_session=persist_session,
    )
    allowed = allowed_status or frozenset()
    if response.status_code >= 400 and response.status_code not in allowed:
        raise api_error_from_response(response)
    if response.status_code in allowed and response.status_code >= 400:
        return None
    return _parse_success_json(response)


def api_json_authed(
    method: str,
    path: str,
    *,
    json_body: dict | list | None = None,
    params: dict[str, Any] | None = None,
    persist_session: bool = True,
) -> dict[str, Any] | None:
    return api_json(
        method,
        path,
        json_body=json_body,
        params=params,
        persist_session=persist_session,
    )


def api_logout() -> None:
    response = api_request("POST", "/api/v1/auth/logout")
    if response.status_code >= 400:
        raise api_error_from_response(response)
    clear_session_file()


def focus_window_overrides_path(map_id: str, override_id: str | None = None) -> str:
    """Nested F4 override routes under one owned focus window."""
    base = f"/api/v1/focus-windows/{map_id}/overrides"
    if override_id:
        return f"{base}/{override_id}"
    return base


def unwrap_api_list(body: dict[str, Any] | None) -> list[Any]:
    """Normalize list endpoints that return a JSON array (wrapped as ``data`` by api_json)."""
    if not body:
        return []
    data = body.get("data")
    if isinstance(data, list):
        return data
    return []
