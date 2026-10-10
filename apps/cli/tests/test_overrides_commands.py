"""F4 Time Map override CLI — no live API."""

from __future__ import annotations

import json

import pytest

from theplan.commands.overrides import run_overrides
from theplan.errors import CliError
from theplan.main import _build_parser
from theplan.output import set_output_format

MAP_ID = "00000000-0000-0000-0000-000000000060"
OVERRIDE_ID = "00000000-0000-0000-0000-000000000061"
OTHER_OVERRIDE_ID = "00000000-0000-0000-0000-000000000062"

CREATE_BODY = {
    "local_start_date": "2026-10-12",
    "local_end_date": "2026-10-14",
    "timezone": "America/Los_Angeles",
    "strict_mode": True,
    "bands": [
        {
            "tier": "green",
            "start_time": "14:00",
            "end_time": "17:00",
            "days_of_week": 127,
            "sort_order": 0,
        }
    ],
}


def _parse(argv: list[str]):
    return _build_parser().parse_args(argv)


def _sample_override(*, override_id: str = OVERRIDE_ID) -> dict:
    return {
        "id": override_id,
        "map_id": MAP_ID,
        "local_start_date": "2026-10-12",
        "local_end_date": "2026-10-14",
        "timezone": "America/Los_Angeles",
        "strict_mode": True,
        "bands": CREATE_BODY["bands"],
        "created_at": "2026-10-10T18:00:00Z",
        "updated_at": "2026-10-10T18:00:00Z",
    }


def test_overrides_crud_calls_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, str, dict | None]] = []
    row = _sample_override()

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
        base = f"/api/v1/focus-windows/{MAP_ID}/overrides"
        if method == "GET" and path == base:
            return {"data": [row, _sample_override(override_id=OTHER_OVERRIDE_ID)]}
        if method == "GET" and path == f"{base}/{OVERRIDE_ID}":
            return row
        if method == "POST" and path == base:
            assert json_body == CREATE_BODY
            return row
        if method == "PATCH" and path == f"{base}/{OVERRIDE_ID}":
            assert json_body == {"strict_mode": False}
            return {**row, "strict_mode": False}
        if method == "DELETE" and path == f"{base}/{OTHER_OVERRIDE_ID}":
            return None
        raise AssertionError(f"unexpected call {method} {path}")

    monkeypatch.setattr("theplan.commands.overrides.api_json", fake_api)

    run_overrides(_parse(["overrides", "list", "--map-id", MAP_ID]))
    listed = json.loads(capsys.readouterr().out)
    assert listed["ok"] is True
    assert len(listed["overrides"]) == 2

    run_overrides(_parse(["overrides", "get", "--map-id", MAP_ID, "--id", OVERRIDE_ID]))
    got = json.loads(capsys.readouterr().out)
    assert got["timezone"] == "America/Los_Angeles"

    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps(CREATE_BODY)))
    run_overrides(_parse(["overrides", "create", "--map-id", MAP_ID, "--stdin"]))
    created = json.loads(capsys.readouterr().out)
    assert created["ok"] is True

    patch_json = json.dumps({"strict_mode": False})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(patch_json))
    run_overrides(_parse(["overrides", "edit", "--map-id", MAP_ID, "--id", OVERRIDE_ID, "--stdin"]))
    edited = json.loads(capsys.readouterr().out)
    assert edited["strict_mode"] is False

    run_overrides(_parse(["overrides", "delete", "--map-id", MAP_ID, "--id", OTHER_OVERRIDE_ID]))
    deleted = json.loads(capsys.readouterr().out)
    assert deleted["deleted"] is True

    assert [c[0:2] for c in calls] == [
        ("GET", f"/api/v1/focus-windows/{MAP_ID}/overrides"),
        ("GET", f"/api/v1/focus-windows/{MAP_ID}/overrides/{OVERRIDE_ID}"),
        ("POST", f"/api/v1/focus-windows/{MAP_ID}/overrides"),
        ("PATCH", f"/api/v1/focus-windows/{MAP_ID}/overrides/{OVERRIDE_ID}"),
        ("DELETE", f"/api/v1/focus-windows/{MAP_ID}/overrides/{OTHER_OVERRIDE_ID}"),
    ]


def test_edit_empty_body_raises() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("{}"))
    try:
        with pytest.raises(CliError) as err:
            run_overrides(
                _parse(
                    [
                        "overrides",
                        "edit",
                        "--map-id",
                        MAP_ID,
                        "--id",
                        OVERRIDE_ID,
                        "--stdin",
                    ]
                )
            )
        assert err.value.code == "INVALID_USAGE"
    finally:
        monkeypatch.undo()


def test_list_text_format(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    set_output_format("text")

    def fake_api(method: str, path: str, **kwargs: object) -> dict:
        return {"data": [_sample_override()]}

    monkeypatch.setattr("theplan.commands.overrides.api_json", fake_api)
    run_overrides(_parse(["overrides", "list", "--map-id", MAP_ID]))
    out = capsys.readouterr().out
    assert "America/Los_Angeles" in out
    assert OVERRIDE_ID in out


def test_overlap_surfaces_api_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_conflict(method: str, path: str, **kwargs: object) -> dict:
        raise CliError(
            code="TIME_MAP_OVERRIDE_OVERLAP",
            message="Override date range overlaps another override on this Time Map",
            exit_code=5,
            extra={"conflicting_override_id": OTHER_OVERRIDE_ID},
        )

    monkeypatch.setattr("theplan.commands.overrides.api_json", raise_conflict)
    monkeypatch.setattr(
        "theplan.commands.overrides.read_json_body",
        lambda **kwargs: CREATE_BODY,
    )
    with pytest.raises(CliError) as err:
        run_overrides(_parse(["overrides", "create", "--map-id", MAP_ID, "--stdin"]))
    assert err.value.code == "TIME_MAP_OVERRIDE_OVERLAP"
    assert err.value.exit_code == 5
