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


def test_v1_snapshot_is_provenance() -> None:
    stored = _sample()
    stored["v"] = 1
    assert diff_stale_categories(stored, _sample()) == [STALE_PROVENANCE]


def test_w2_categories_name_themselves() -> None:
    stored = _sample()
    pins = _sample()
    pins["pins"] = {"pinned_minutes": 15, "intervals": []}
    assert diff_stale_categories(stored, pins) == ["pins"]

    cap = _sample()
    cap["project_daily_cap"] = {"max_auto_schedule_minutes_per_project_per_day": 120}
    assert diff_stale_categories(stored, cap) == ["project_daily_cap"]

    horizon = _sample()
    horizon["timezone_horizon_workweek"] = {
        **horizon["timezone_horizon_workweek"],
        "timezone": "America/Los_Angeles",
    }
    assert diff_stale_categories(stored, horizon) == ["timezone_horizon_workweek"]

    life = _sample()
    life["lifecycle"] = {**life["lifecycle"], "is_completed": True}
    assert diff_stale_categories(stored, life) == ["lifecycle"]

    busy = _sample()
    busy["busy_external"] = {
        "intervals": [
            {
                "source": "external",
                "start": "2026-10-08T15:00:00+00:00",
                "end": "2026-10-08T16:00:00+00:00",
            }
        ]
    }
    assert diff_stale_categories(stored, busy) == ["busy_external"]

    prereq = _sample()
    prereq["prerequisite_state"] = {
        "blockers": [
            {
                "task_id": str(uuid4()),
                "estimated_duration_minutes": 30,
                "is_completed": False,
                "deleted_at": None,
            }
        ]
    }
    assert diff_stale_categories(stored, prereq) == ["prerequisite_state"]

    due = _sample()
    due["due_at_soft_target"] = {
        **due["due_at_soft_target"],
        "due_at": "2026-10-12T17:00:00+00:00",
    }
    assert diff_stale_categories(stored, due) == ["due_at_soft_target"]


def test_priority_ups_are_not_compared() -> None:
    stored = _sample()
    live = _sample()
    stored["priority_ups"] = {"priority": "p1"}
    live["priority_ups"] = {"priority": "p4"}
    assert diff_stale_categories(stored, live) == []


def test_v2_snapshot_is_provenance() -> None:
    stored = _sample()
    stored["v"] = 2
    assert diff_stale_categories(stored, _sample()) == [STALE_PROVENANCE]


def test_time_map_override_change_names_its_category() -> None:
    stored = _sample()
    changed = _sample()
    changed["time_map_overrides"] = {
        "overrides": [
            {
                "id": str(uuid4()),
                "map_id": str(uuid4()),
                "local_start_date": "2026-08-11",
                "local_end_date": "2026-08-11",
                "timezone": "America/Los_Angeles",
                "strict_mode": True,
                "bands": [],
            }
        ]
    }
    assert diff_stale_categories(stored, changed) == ["time_map_overrides"]


def test_override_row_order_does_not_change_the_fingerprint() -> None:
    early = {
        "id": "override-early",
        "map_id": "map-1",
        "local_start_date": "2026-08-11",
        "local_end_date": "2026-08-11",
        "timezone": "UTC",
        "strict_mode": True,
        "bands": [],
    }
    late = {
        "id": "override-late",
        "map_id": "map-1",
        "local_start_date": "2026-12-01",
        "local_end_date": "2026-12-03",
        "timezone": "America/Los_Angeles",
        "strict_mode": False,
        "bands": [],
    }
    kwargs = dict(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=False,
        bands=[],
        blocking_task_ids=[],
    )
    forward = assemble_snapshot(**kwargs, time_map_overrides=[early, late])
    backward = assemble_snapshot(**kwargs, time_map_overrides=[late, early])
    assert [row["id"] for row in forward["time_map_overrides"]["overrides"]] == [
        "override-early",
        "override-late",
    ]
    assert forward["time_map_overrides"] == backward["time_map_overrides"]
    assert fingerprint_snapshot(forward) == fingerprint_snapshot(backward)


def test_override_identity_fields_each_name_the_category() -> None:
    base_row = {
        "id": "override-1",
        "map_id": "map-1",
        "local_start_date": "2026-08-11",
        "local_end_date": "2026-08-11",
        "timezone": "UTC",
        "strict_mode": True,
        "bands": [],
    }
    stored = _sample(time_map_overrides={"overrides": [base_row]})

    def _changed(**fields: object) -> dict:
        row = {**base_row, **fields}
        return _sample(time_map_overrides={"overrides": [row]})

    assert diff_stale_categories(stored, _changed(id="override-2")) == ["time_map_overrides"]
    assert diff_stale_categories(stored, _changed(timezone="America/Los_Angeles")) == [
        "time_map_overrides"
    ]
    assert diff_stale_categories(stored, _changed(strict_mode=False)) == ["time_map_overrides"]
    assert diff_stale_categories(stored, _changed(local_end_date="2026-08-12")) == [
        "time_map_overrides"
    ]
    missing = _sample()
    del missing["time_map_overrides"]
    assert diff_stale_categories(missing, stored) == ["time_map_overrides"]


def test_override_band_order_does_not_change_the_fingerprint() -> None:
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
    common = {
        "id": "override-1",
        "map_id": "map-1",
        "local_start_date": "2026-08-11",
        "local_end_date": "2026-08-11",
        "timezone": "UTC",
        "strict_mode": True,
    }
    kwargs = dict(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=False,
        bands=[],
        blocking_task_ids=[],
    )
    forward = assemble_snapshot(
        **kwargs,
        time_map_overrides=[{**common, "bands": [first, second]}],
    )
    backward = assemble_snapshot(
        **kwargs,
        time_map_overrides=[{**common, "bands": [second, first]}],
    )
    assert forward["time_map_overrides"] == backward["time_map_overrides"]
    assert fingerprint_snapshot(forward) == fingerprint_snapshot(backward)


def test_outcome_family_from_reason_code() -> None:
    assert outcome_family("placed") == "placed"
    assert outcome_family("excluded_manual_or_bundle") == "excluded"
    assert outcome_family("excluded_duration_covered_by_pins") == "excluded"
    assert outcome_family("blocked_prerequisite") == "blocked"
    assert outcome_family("unplaced_horizon_exhausted") == "unplaced"
    assert outcome_family("unplaced_no_slot") == "unplaced"
    assert outcome_family("something_new") == "recorded"
