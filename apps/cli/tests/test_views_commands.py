"""F7 saved views CLI — no live API."""

from __future__ import annotations

import json

import pytest

from theplan.commands.views import run_views
from theplan.errors import CliError
from theplan.main import _build_parser
from theplan.output import handle_cli_error, set_output_format

VIEW_ID = "00000000-0000-0000-0000-000000000050"
OTHER_ID = "00000000-0000-0000-0000-000000000051"
SYSTEM_INBOX_ID = "00000000-0000-0000-0000-000000000001"

PREDICATE = {
    "v": 1,
    "dimensions": {"inbox": True, "completion": "open"},
}


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def _sample_view(*, view_id: str = VIEW_ID, slug: str = "cli-test", is_system: bool = False) -> dict:
    return {
        "id": view_id,
        "name": "CLI test",
        "slug": slug,
        "predicate_json": PREDICATE,
        "presentation_json": {"mode": "list"},
        "is_system": is_system,
        "sort_order": 100,
    }


def test_views_crud_and_query_call_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, str, dict | None]] = []
    store = _sample_view()

    def fake_api(
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        persist_session: bool = True,
        **kwargs: object,
    ) -> dict | None:
        assert persist_session is True
        calls.append((method, path, json_body))
        if method == "GET" and path == "/api/v1/views":
            return {"data": [_sample_view(slug="inbox", is_system=True, view_id=SYSTEM_INBOX_ID), store]}
        if method == "GET" and path == f"/api/v1/views/{VIEW_ID}":
            return store
        if method == "POST" and path == "/api/v1/views":
            assert json_body is not None
            assert json_body["predicate_json"] == PREDICATE
            return {**store, "name": json_body.get("name", store["name"])}
        if method == "PATCH" and path == f"/api/v1/views/{VIEW_ID}":
            assert json_body == {"name": "Renamed"}
            return {**store, "name": "Renamed"}
        if method == "DELETE" and path == f"/api/v1/views/{OTHER_ID}":
            return None
        if method == "GET" and path == f"/api/v1/views/{VIEW_ID}/tasks":
            assert params == {"limit": 10, "offset": 0, "board_order": True}
            return {
                "items": [{"id": "t1", "title": "One", "is_completed": False}],
                "total": 42,
                "limit": 10,
                "offset": 0,
            }
        if method == "GET" and path == "/api/v1/views/by-slug/inbox/tasks":
            return {"items": [], "total": 0, "limit": 50, "offset": 0}
        raise AssertionError(f"unexpected call {method} {path}")

    monkeypatch.setattr("theplan.commands.views.api_json", fake_api)

    run_views(_parse(["views", "list"]))
    listed = json.loads(capsys.readouterr().out)
    assert listed["ok"] is True
    assert len(listed["views"]) == 2

    run_views(_parse(["views", "get", "--id", VIEW_ID]))
    got = json.loads(capsys.readouterr().out)
    assert got["slug"] == "cli-test"

    create_json = json.dumps({"name": "New", "predicate_json": PREDICATE})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(create_json))
    run_views(_parse(["views", "create", "--stdin"]))
    created = json.loads(capsys.readouterr().out)
    assert created["ok"] is True

    patch_json = json.dumps({"name": "Renamed"})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(patch_json))
    run_views(_parse(["views", "patch", "--id", VIEW_ID, "--stdin"]))
    patched = json.loads(capsys.readouterr().out)
    assert patched["name"] == "Renamed"

    run_views(_parse(["views", "delete", "--id", OTHER_ID]))
    deleted = json.loads(capsys.readouterr().out)
    assert deleted["deleted"] is True

    run_views(
        _parse(
            [
                "views",
                "query",
                "--id",
                VIEW_ID,
                "--limit",
                "10",
                "--offset",
                "0",
                "--board-order",
            ]
        )
    )
    queried = json.loads(capsys.readouterr().out)
    assert queried["total"] == 42
    assert queried["items"][0]["title"] == "One"

    run_views(_parse(["views", "query", "--slug", "inbox"]))
    by_slug = json.loads(capsys.readouterr().out)
    assert by_slug["total"] == 0

    assert [c[0:2] for c in calls] == [
        ("GET", "/api/v1/views"),
        ("GET", f"/api/v1/views/{VIEW_ID}"),
        ("POST", "/api/v1/views"),
        ("PATCH", f"/api/v1/views/{VIEW_ID}"),
        ("DELETE", f"/api/v1/views/{OTHER_ID}"),
        ("GET", f"/api/v1/views/{VIEW_ID}/tasks"),
        ("GET", "/api/v1/views/by-slug/inbox/tasks"),
    ]


def test_system_view_read_only_surfaces_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_readonly(method: str, path: str, **kwargs: object) -> dict:
        raise CliError(
            code="SYSTEM_VIEW_READ_ONLY",
            message="System views cannot be modified",
            exit_code=2,
        )

    monkeypatch.setattr("theplan.commands.views.api_json", raise_readonly)
    with pytest.raises(CliError) as err:
        run_views(_parse(["views", "delete", "--id", SYSTEM_INBOX_ID]))
    assert err.value.code == "SYSTEM_VIEW_READ_ONLY"
    assert err.value.exit_code == 2


@pytest.mark.parametrize("fmt", ["json", "text"])
def test_system_readonly_error_emits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fmt: str,
) -> None:
    set_output_format(fmt)
    err = CliError(
        code="SYSTEM_VIEW_READ_ONLY",
        message="System views cannot be modified",
        exit_code=2,
    )
    with pytest.raises(SystemExit) as exc:
        handle_cli_error(err)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    if fmt == "json":
        body = json.loads(captured.out)
        assert body["ok"] is False
        assert body["code"] == "SYSTEM_VIEW_READ_ONLY"
    else:
        assert "SYSTEM_VIEW_READ_ONLY" in captured.err


def test_query_text_format_shows_total(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    set_output_format("text")

    def fake_api(method: str, path: str, **kwargs: object) -> dict:
        return {
            "items": [{"id": "a", "title": "Alpha", "is_completed": False}],
            "total": 99,
            "limit": 50,
            "offset": 0,
        }

    monkeypatch.setattr("theplan.commands.views.api_json", fake_api)
    run_views(_parse(["views", "query", "--slug", "today"]))
    out = capsys.readouterr().out
    assert "total: 99" in out
    assert "Alpha" in out
