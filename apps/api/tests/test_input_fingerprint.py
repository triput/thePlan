"""W1 explanation fingerprint: category diffs, no database."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.scheduler.input_fingerprint import (
    STALE_PROVENANCE,
    W1_STALE_CATEGORIES,
    assemble_snapshot,
    diff_stale_categories,
    fingerprint_snapshot,
    outcome_family,
)


def _sample(**overrides: object) -> dict:
    base = assemble_snapshot(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc),
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
    )
    # Shallow category replace for tests that pass a whole category.
    for key, value in overrides.items():
        base[key] = value
    return base


def test_unchanged_snapshot_is_fresh() -> None:
    stored = _sample()
    assert diff_stale_categories(stored, _sample()) == []
    assert fingerprint_snapshot(stored) == fingerprint_snapshot(_sample())


def test_duration_deadline_map_and_deps_name_their_category() -> None:
    stored = _sample()
    duration = _sample()
    duration["duration"] = {**duration["duration"], "estimated_duration_minutes": 90}
    assert diff_stale_categories(stored, duration) == ["duration"]

    deadline = _sample()
    deadline["deadline"] = {"deadline_at": None}
    assert diff_stale_categories(stored, deadline) == ["deadline"]

    window = uuid4()
    mapped = _sample()
    mapped["map_style"] = {
        "schedule_style": "time_block",
        "time_window_id": str(window),
        "strict_mode": True,
        "bands": [
            {
                "tier": "green",
                "start": "09:00:00",
                "end": "12:00:00",
                "days_of_week": 31,
                "sort_order": 0,
            }
        ],
    }
    assert diff_stale_categories(stored, mapped) == ["map_style"]

    blocker = uuid4()
    deps = _sample()
    deps["deps"] = {"blocking_task_ids": [str(blocker)]}
    assert diff_stale_categories(stored, deps) == ["deps"]


def test_band_order_does_not_change_the_fingerprint() -> None:
    first = {
        "tier": "yellow",
        "start": "13:00:00",
        "end": "17:00:00",
        "days_of_week": 31,
        "sort_order": 1,
    }
    second = {
        "tier": "green",
        "start": "09:00:00",
        "end": "12:00:00",
        "days_of_week": 31,
        "sort_order": 0,
    }
    forward = assemble_snapshot(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=False,
        bands=[first, second],
        blocking_task_ids=[],
    )
    backward = assemble_snapshot(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=False,
        bands=[second, first],
        blocking_task_ids=[],
    )
    assert forward["map_style"]["bands"] == backward["map_style"]["bands"]
    assert fingerprint_snapshot(forward) == fingerprint_snapshot(backward)


def test_missing_snapshot_is_provenance_not_a_guess() -> None:
    assert diff_stale_categories(None, _sample()) == [STALE_PROVENANCE]
    assert diff_stale_categories({"v": 0}, _sample()) == [STALE_PROVENANCE]


def test_w1_categories_are_the_compared_set() -> None:
    assert W1_STALE_CATEGORIES == ("duration", "deadline", "map_style", "deps")


def test_outcome_family_from_reason_code() -> None:
    assert outcome_family("placed") == "placed"
    assert outcome_family("excluded_manual_or_bundle") == "excluded"
    assert outcome_family("excluded_duration_covered_by_pins") == "excluded"
    assert outcome_family("blocked_prerequisite") == "blocked"
    assert outcome_family("unplaced_horizon_exhausted") == "unplaced"
    assert outcome_family("unplaced_no_slot") == "unplaced"
    assert outcome_family("something_new") == "recorded"
