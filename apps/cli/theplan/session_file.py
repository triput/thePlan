from __future__ import annotations

import json
import os
from pathlib import Path

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


def load_cookies() -> httpx.Cookies:
    path = session_path()
    cookies = httpx.Cookies()
    if not path.is_file():
        return cookies
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cookies
    if not isinstance(raw, dict):
        return cookies
    for name, value in raw.items():
        if isinstance(name, str) and isinstance(value, str):
            cookies.set(name, value)
    return cookies


def save_cookies(cookies: httpx.Cookies) -> None:
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {name: value for name, value in cookies.items()}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def clear_session_file() -> None:
    path = session_path()
    if path.is_file():
        path.unlink()
