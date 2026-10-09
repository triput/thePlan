"""F5 CLI templates list/get smoke — no live API."""

from __future__ import annotations

import json

import pytest

from theplan.commands.templates import run_templates
from theplan.main import _build_parser
from theplan.output import set_output_format


def _install_api(monkeypatch: pytest.MonkeyPatch, catalog: list[dict], detail: dict) -> None:
    def fake_api(method: str, path: str, **kwargs: object) -> object:
        if path == "/api/v1/templates":
            return catalog
        return detail

    monkeypatch.setattr("theplan.commands.templates.api_json", fake_api)


def test_templates_list_and_get_text_and_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = [
        {
            "id": "coursera_specialization",
            "version": 1,
            "title": "Coursera specialization or certificate",
            "attach_modes": ["root", "epic"],
        }
    ]
    detail = {
        "id": "coursera_specialization",
        "version": 1,
        "title": "Coursera specialization or certificate",
        "description": "Epic with course projects.",
        "attach_modes": ["root", "epic"],
        "outline_pack": "coursera_specialization",
        "is_scaffold": True,
    }
    _install_api(monkeypatch, catalog, detail)
    parser = _build_parser()
    try:
        set_output_format("text")
        run_templates(parser.parse_args(["templates", "list"]))
        listed = capsys.readouterr().out
        assert "coursera_specialization (v1)" in listed
        assert "attach_modes: root, epic" in listed

        set_output_format("json")
        run_templates(parser.parse_args(["templates", "list"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["templates"][0]["id"] == "coursera_specialization"

        set_output_format("text")
        run_templates(parser.parse_args(["templates", "get", "coursera_specialization"]))
        got = capsys.readouterr().out
        assert "id: coursera_specialization" in got
        assert "is_scaffold: True" in got
        assert "outline_pack: coursera_specialization" in got

        set_output_format("json")
        run_templates(parser.parse_args(["templates", "get", "coursera_specialization"]))
        detail_payload = json.loads(capsys.readouterr().out)
        assert detail_payload["ok"] is True
        assert detail_payload["is_scaffold"] is True
        assert detail_payload["id"] == "coursera_specialization"
    finally:
        set_output_format("json")
