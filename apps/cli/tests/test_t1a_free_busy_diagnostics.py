"""T1-A: read-only CLI listing of BusyInputTrust diagnostics."""

from __future__ import annotations

import argparse

import pytest

from theplan.commands.schedule import run_schedule


def test_free_busy_diagnostics_cli_text_shows_readable_rollup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    listing = """BusyInputTrust.ok=False
affected_horizon='unknown_extent'

Rollups:
  refresh "TP@Gmail": 1 events with unknown_free_busy:unknown_legacy

Diagnostics:
  unknown_free_busy:unknown_legacy: calendar "TP@Gmail", title "Kubernetes graded assessment", 2026-10-19T18:00:00+00:00 – 2026-10-19T19:00:00+00:00, id=evt-k8s-1
"""

    def fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/api/v1/calendar/busy-input-trust"
        assert kwargs.get("params") == {
            "start": "2026-10-19T17:00:00Z",
            "end": "2026-10-20T01:00:00Z",
        }
        return {"trust": {"ok": False}, "cli_listing": listing}

    monkeypatch.setattr("theplan.commands.schedule.api_json", fake_api)
    monkeypatch.setattr("theplan.commands.schedule.get_output_format", lambda: "text")

    args = argparse.Namespace(
        schedule_command="free-busy-diagnostics",
        start="2026-10-19T17:00:00Z",
        end="2026-10-20T01:00:00Z",
    )
    run_schedule(args)
    out = capsys.readouterr().out
    assert "BusyInputTrust.ok=False" in out
    assert "TP@Gmail" in out
    assert "Kubernetes graded assessment" in out
    assert "evt-k8s-1" in out
    assert "2026-10-19T18:00:00" in out
    assert "Rollups:" in out
    assert 'refresh "TP@Gmail"' in out
