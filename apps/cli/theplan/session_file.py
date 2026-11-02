from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from theplan.errors import CliError


def default_session_path() -> Path:
    override = os.environ.get("THEPLAN_SESSION_FILE")
    if override:
        return Path(override).expanduser()
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".config"
    return base / "theplan" / "session"


def session_path() -> Path:
    return default_session_path()


def api_base_url_raw() -> str:
    return os.environ.get("THEPLAN_API_URL", "http://127.0.0.1:8000").rstrip("/")


def normalize_api_origin(url: str | None = None) -> str:
    """scheme + host + effective port (defaults 80/443 when omitted)."""
    raw = (url if url is not None else api_base_url_raw()).strip()
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    scheme = (parsed.scheme or "http").lower()
    host = (parsed.hostname or "").lower()
    if not host:
        raise CliError(
            code="API_ORIGIN_INVALID",
            message=f"Cannot parse API origin from {raw!r}",
            exit_code=1,
        )
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return f"{scheme}://{host}:{port}"


def _api_host() -> str:
    return (urlparse(api_base_url_raw()).hostname or "").lower()


def _cookie_records(cookies: httpx.Cookies) -> list[dict[str, str]]:
    """Serialize jar entries without Cookies.items() (conflicts on duplicate names)."""
    records: list[dict[str, str]] = []
    for cookie in cookies.jar:
        records.append(
            {
                "name": cookie.name,
                "value": cookie.value if cookie.value is not None else "",
                "domain": cookie.domain or "",
                "path": cookie.path or "/",
            }
        )
    return records


def _domain_matches_host(domain: str, host: str) -> bool:
    if not domain:
        return True
    d = domain.lstrip(".").lower()
    h = host.lower()
    return h == d or h.endswith("." + d)


def _prefer_for_api_host(records: list[dict[str, str]], host: str) -> list[dict[str, str]]:
    """Keep one cookie per name, preferring domain match for the API host."""
    by_name: dict[str, dict[str, str]] = {}
    for rec in records:
        name = rec["name"]
        prev = by_name.get(name)
        if prev is None:
            by_name[name] = rec
            continue
        prev_match = _domain_matches_host(prev.get("domain", ""), host)
        cur_match = _domain_matches_host(rec.get("domain", ""), host)
        if cur_match and not prev_match:
            by_name[name] = rec
        elif cur_match == prev_match:
            if rec.get("domain") and not prev.get("domain"):
                by_name[name] = rec
    return list(by_name.values())


def _read_raw() -> Any | None:
    path = session_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_bearer_token() -> str | None:
    """Agent credential secret bound to the current API origin.

    Legacy cookie-only files → None (caller must fail closed; never use cookies).
    Origin mismatch → CliError before any network I/O.
    """
    raw = _read_raw()
    if not isinstance(raw, dict):
        return None
    token = raw.get("bearer_token")
    if not isinstance(token, str) or not token.strip():
        return None
    saved_origin = raw.get("api_origin")
    current = normalize_api_origin()
    if not isinstance(saved_origin, str) or not saved_origin.strip():
        raise CliError(
            code="CLI_SESSION_ORIGIN_MISSING",
            message=(
                "Saved agent session has no API origin binding. "
                "Re-login: theplan auth login --token <secret>"
            ),
            exit_code=2,
        )
    if normalize_api_origin(saved_origin) != current:
        raise CliError(
            code="CLI_SESSION_ORIGIN_MISMATCH",
            message=(
                f"Saved agent session is for {saved_origin!r}, but THEPLAN_API_URL "
                f"origin is {current!r}. Re-login against the intended API, or unset "
                "THEPLAN_SESSION_FILE / clear the session."
            ),
            exit_code=2,
        )
    return token.strip()


def peek_bearer_token_unbound() -> str | None:
    """Read bearer without origin check (tests / pre-persist validation helpers)."""
    raw = _read_raw()
    if isinstance(raw, dict):
        token = raw.get("bearer_token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    return None


def load_cookies() -> httpx.Cookies:
    """Legacy cookie loader for unit tests of jar serialization only.

    Supported CLI auth must not call this for API requests (Bearer-only).
    """
    cookies = httpx.Cookies()
    raw = _read_raw()
    if raw is None:
        return cookies

    records: list[dict[str, str]] = []
    if isinstance(raw, dict) and "cookies" in raw:
        cookie_list = raw.get("cookies")
        if isinstance(cookie_list, list):
            raw = cookie_list
        else:
            raw = []
    if isinstance(raw, dict) and raw.get("bearer_token"):
        return cookies

    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if isinstance(name, str) and isinstance(value, str):
                records.append(
                    {
                        "name": name,
                        "value": value,
                        "domain": str(item.get("domain") or ""),
                        "path": str(item.get("path") or "/"),
                    }
                )
    elif isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(name, str) and isinstance(value, str) and name != "bearer_token":
                records.append({"name": name, "value": value, "domain": "", "path": "/"})

    host = _api_host()
    for rec in _prefer_for_api_host(records, host):
        cookies.set(
            rec["name"],
            rec["value"],
            domain=rec.get("domain") or "",
            path=rec.get("path") or "/",
        )
    return cookies


def save_bearer_token(token: str, *, api_origin: str | None = None) -> None:
    """Persist agent credential bound to normalized API origin (no browser cookie)."""
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    origin = normalize_api_origin(api_origin) if api_origin else normalize_api_origin()
    payload = {
        "version": 2,
        "bearer_token": token.strip(),
        "api_origin": origin,
        "cookies": [],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def save_cookies(cookies: httpx.Cookies) -> None:
    """Legacy cookie persist — kept for jar unit tests; CLI login does not mint cookies."""
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_token = peek_bearer_token_unbound()
    records = _prefer_for_api_host(_cookie_records(cookies), _api_host())
    if existing_token:
        raw = _read_raw()
        origin = raw.get("api_origin") if isinstance(raw, dict) else None
        payload: dict[str, Any] = {
            "version": 2,
            "bearer_token": existing_token,
            "api_origin": origin if isinstance(origin, str) and origin else normalize_api_origin(),
            "cookies": records,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def clear_session_file() -> None:
    path = session_path()
    if path.is_file():
        path.unlink()
