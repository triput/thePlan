"""CLI unit tests import `theplan` without an editable install.

Host-recovery error mapping imports `app.api.errors`, so apps/api is on
sys.path as well. These tests mock the service; they do not open Postgres.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CLI_ROOT = Path(__file__).resolve().parents[1]
_API_ROOT = _CLI_ROOT.parent / "api"

for _path in (_API_ROOT, _CLI_ROOT):
    entry = str(_path)
    if entry not in sys.path:
        sys.path.insert(0, entry)


@pytest.fixture(autouse=True)
def _json_output_format():
    from theplan.output import set_output_format

    set_output_format("json")
    yield
    set_output_format("json")
