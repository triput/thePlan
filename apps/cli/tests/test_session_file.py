"""Session cookie jar: no CookieConflict on duplicate names; prefer API host."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from theplan.session_file import load_cookies, save_cookies


def test_save_cookies_tolerates_duplicate_session_names(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "session"
    monkeypatch.setenv("THEPLAN_SESSION_FILE", str(path))
    monkeypatch.setenv("THEPLAN_API_URL", "http://127.0.0.1:8000")

    jar = httpx.Cookies()
    jar.set("session", "stale-localhost", domain="localhost", path="/")
    jar.set("session", "current-loopback", domain="127.0.0.1", path="/")

    save_cookies(jar)  # must not raise CookieConflict

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 1
    assert raw[0]["name"] == "session"
    assert raw[0]["value"] == "current-loopback"
    assert raw[0]["domain"] == "127.0.0.1"


def test_load_legacy_dict_and_round_trip(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "session"
    monkeypatch.setenv("THEPLAN_SESSION_FILE", str(path))
    monkeypatch.setenv("THEPLAN_API_URL", "http://127.0.0.1:8000")
    path.write_text(json.dumps({"session": "legacy-value"}) + "\n", encoding="utf-8")

    loaded = load_cookies()
    assert loaded.get("session") == "legacy-value"

    save_cookies(loaded)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw[0]["value"] == "legacy-value"
