"""S2-V3 CLI: reject legacy workweek fields on settings patch."""

from __future__ import annotations

import pytest

from theplan.commands.settings import run_settings
from theplan.errors import CliError
from theplan.main import _build_parser


def test_settings_patch_rejects_workweek_json_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_read_json_body(*_args, **_kwargs):
        return {"workweek_days": 5}

    monkeypatch.setattr("theplan.commands.settings.read_json_body", fake_read_json_body)

    with pytest.raises(CliError) as exc:
        run_settings(_build_parser().parse_args(["settings", "patch", "--stdin"]))
    assert exc.value.code == "LEGACY_WORKWEEK_SETTINGS_REJECTED"
