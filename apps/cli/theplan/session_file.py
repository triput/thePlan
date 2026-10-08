from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


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


def _api_host() -> str:
    import os

    base = os.environ.get("THEPLAN_API_URL", "http://127.0.0.1:8000")
    return (urlparse(base).hostname or "").lower()


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
            # Same fit: prefer non-empty domain (Set-Cookie from server).
            if rec.get("domain") and not prev.get("domain"):
                by_name[name] = rec
    return list(by_name.values())


def load_cookies() -> httpx.Cookies:
    path = session_path()
    cookies = httpx.Cookies()
    if not path.is_file():
        return cookies
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cookies

    records: list[dict[str, str]] = []
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
        # Legacy name→value map from M2 first cut.
        for name, value in raw.items():
            if isinstance(name, str) and isinstance(value, str):
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


def save_cookies(cookies: httpx.Cookies) -> None:
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _prefer_for_api_host(_cookie_records(cookies), _api_host())
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def clear_session_file() -> None:
    path = session_path()
    if path.is_file():
        path.unlink()
