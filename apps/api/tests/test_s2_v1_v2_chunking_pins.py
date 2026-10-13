"""S2-V1/V2 placer budget, fingerprint v4, and stale-preview activation.

No database. SS-30 buffer evidence is a hook only — A15 is not closed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.scheduler.busy_map import add_busy_interval
from app.scheduler.input_fingerprint import (
    SCHEDULING_ACTIVATIONS,
    SNAPSHOT_VERSION,
    SNAPSHOT_VERSION_V4,
    STALE_PROVENANCE,
    STALE_SCHEDULING_ACTIVATION,
    assemble_snapshot,
    diff_stale_categories,
    owner_snapshot_predates_activation,
)
from app.scheduler.pin_reservation import (
    CONFLICT_EXCESS_PIN,
    CONFLICT_MULTIPLE_PINS,
    CONFLICT_SHORTER_PIN,
    evaluate_auto_placement,
    reservation_minutes,
)
from app.scheduler.placement import slice_sizes_for_remaining
from app.scheduler.reasons import (
    REASON_EXCLUDED_KEEP_IN_ONE_RESERVED,
    REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT,
    REASON_UNPLACED_KEEP_IN_ONE_CONFLICT,
    REASON_UNPLACED_PIN_RESERVATION_EXCESS,
    format_summary_text,
    ReasonFact,
)
from app.services.chunking_cutover_activation import chunking_activation_revision
from app.services.chunking_effective import resolve_block_bounds
from app.services.task_chunking_guard import chunking_cutover_writes_unlocked

NOW = datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc)


def _settings(**overrides: object) -> SimpleNamespace:
    base = dict(
        default_min_block_duration_minutes=15,
        default_max_block_duration_minutes=120,
        default_max_block_unbounded=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _task(**overrides: object) -> SimpleNamespace:
    base = dict(
        estimated_duration_minutes=240,
        remaining_minutes=240,
        worked_minutes=0,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        max_block_unbounded=False,
        keep_in_one_block=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _pin(start: datetime, end: datetime) -> SimpleNamespace:
    return SimpleNamespace(start_time=start, end_time=end)


def _snap(**overrides: object) -> dict:
    base = dict(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
    )
    base.update(overrides)
    return assemble_snapshot(**base)


def test_writes_unlocked_at_s2_tip() -> None:
    assert chunking_cutover_writes_unlocked() is True


def test_inherit_explicit_and_no_limit() -> None:
    inherited = resolve_block_bounds(
        _task(min_block_duration_minutes=None, max_block_duration_minutes=None),
        _settings(default_min_block_duration_minutes=20, default_max_block_duration_minutes=90),
    )
    assert inherited.effective_min_minutes == 20
    assert inherited.effective_max_minutes == 90
    assert inherited.min_source == "user_default"
    assert inherited.max_source == "user_default"
    assert inherited.bounds_conflict() is False

    explicit = resolve_block_bounds(_task(), _settings())
    assert explicit.effective_min_minutes == 15
    assert explicit.effective_max_minutes == 120
    assert explicit.min_source == "task_explicit"
    assert explicit.keep_in_one_block is False

    unbounded = resolve_block_bounds(
        _task(max_block_unbounded=True, max_block_duration_minutes=30),
        _settings(),
    )
    assert unbounded.max_unbounded is True
    assert unbounded.effective_max_minutes is None
    assert unbounded.max_source == "no_limit"
    assert unbounded.bounds_conflict() is False


def test_bounds_conflict_is_a_correction_and_places_nothing() -> None:
    task = _task(min_block_duration_minutes=180, max_block_duration_minutes=60)
    decision = evaluate_auto_placement(task, _settings(), [], NOW)
    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.reason_code == REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT
    assert decision.effort_minutes == 240


def test_no_limit_does_not_use_a_synthetic_max_and_remainder_under_min_stays() -> None:
    sizes = slice_sizes_for_remaining(400, min_block=15, max_block=None, keep_in_one=False)
    assert sizes[0] == 400
    assert 120 not in sizes
    assert slice_sizes_for_remaining(10, min_block=15, max_block=120, keep_in_one=False) == [10]
    assert slice_sizes_for_remaining(240, min_block=15, max_block=120, keep_in_one=True) == [240]


def test_future_tail_reservation_and_no_double_subtract() -> None:
    past = _pin(NOW - timedelta(hours=2), NOW)
    future = _pin(NOW + timedelta(hours=1), NOW + timedelta(hours=3))
    active = _pin(NOW - timedelta(minutes=30), NOW + timedelta(minutes=90))
    assert reservation_minutes(past.start_time, past.end_time, NOW) == 0
    assert reservation_minutes(future.start_time, future.end_time, NOW) == 120
    assert reservation_minutes(active.start_time, active.end_time, NOW) == 90
    assert reservation_minutes(NOW, NOW + timedelta(minutes=45), NOW) == 45

    decision = evaluate_auto_placement(_task(), _settings(), [future], NOW)
    assert decision.reserved_minutes == 120
    assert decision.minutes_to_place == 120
    assert decision.effort_minutes == 240
    assert decision.auto_place is True


def test_excess_pin_does_not_clamp_remaining() -> None:
    pin = _pin(NOW + timedelta(hours=1), NOW + timedelta(hours=6))
    decision = evaluate_auto_placement(_task(remaining_minutes=180), _settings(), [pin], NOW)
    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.effort_minutes == 180
    assert decision.reserved_minutes == 300
    assert decision.reason_code == REASON_UNPLACED_PIN_RESERVATION_EXCESS
    assert decision.reason_params["clamped"] is False


def test_keep_in_one_table() -> None:
    settings = _settings()
    task = _task(keep_in_one_block=True, max_block_duration_minutes=None, max_block_unbounded=True)

    no_pin = evaluate_auto_placement(task, settings, [], NOW)
    assert no_pin.auto_place is True
    assert no_pin.minutes_to_place == 240

    past = _pin(NOW - timedelta(hours=3), NOW - timedelta(hours=1))
    after_past = evaluate_auto_placement(task, settings, [past], NOW)
    assert after_past.auto_place is True
    assert after_past.minutes_to_place == 240
    assert after_past.reserved_minutes == 0

    exact = _pin(NOW + timedelta(hours=1), NOW + timedelta(hours=5))
    covered = evaluate_auto_placement(task, settings, [exact], NOW)
    assert covered.auto_place is False
    assert covered.minutes_to_place == 0
    assert covered.conflicts == ()
    assert covered.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED

    short = _pin(NOW + timedelta(hours=1), NOW + timedelta(hours=3))
    conflict = evaluate_auto_placement(task, settings, [short], NOW)
    assert conflict.auto_place is False
    assert conflict.minutes_to_place == 0
    assert conflict.effort_minutes == 240
    assert conflict.conflicts[0]["code"] == CONFLICT_SHORTER_PIN
    assert conflict.reason_code == REASON_UNPLACED_KEEP_IN_ONE_CONFLICT
    summary = format_summary_text([ReasonFact(conflict.reason_code, conflict.reason_params)])
    assert "240-minute" in summary
    assert "120 minutes" in summary
    assert conflict.conflicts[0]["detail"]["pins_protected"] is True
    assert conflict.conflicts[0]["detail"]["automatic_work_minutes"] == 0

    longer = _pin(NOW + timedelta(hours=1), NOW + timedelta(hours=6))
    excess = evaluate_auto_placement(task, settings, [longer], NOW)
    assert excess.minutes_to_place == 0
    assert excess.effort_minutes == 240
    assert excess.conflicts[0]["code"] == CONFLICT_EXCESS_PIN

    second = _pin(NOW + timedelta(hours=6), NOW + timedelta(hours=7))
    multiple = evaluate_auto_placement(task, settings, [short, second], NOW)
    assert multiple.auto_place is False
    assert multiple.minutes_to_place == 0
    assert multiple.conflicts[0]["code"] == CONFLICT_MULTIPLE_PINS

    tail = _pin(NOW - timedelta(hours=1), NOW + timedelta(hours=2))
    tail_cover = evaluate_auto_placement(
        _task(keep_in_one_block=True, remaining_minutes=120, max_block_unbounded=True),
        settings,
        [tail],
        NOW,
    )
    assert tail_cover.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    tail_short = evaluate_auto_placement(task, settings, [tail], NOW)
    assert tail_short.conflicts[0]["code"] == CONFLICT_SHORTER_PIN

    both = evaluate_auto_placement(task, settings, [tail, short], NOW)
    assert both.conflicts[0]["code"] == CONFLICT_MULTIPLE_PINS
    assert both.minutes_to_place == 0


def test_v3_snapshot_is_provenance_and_activation_token_stales_v4() -> None:
    historical = _snap(snapshot_version=SNAPSHOT_VERSION)
    live = _snap(snapshot_version=SNAPSHOT_VERSION_V4, worked_minutes=0, remaining_minutes=30)
    assert "scheduling_activation" not in historical
    assert diff_stale_categories(historical, live) == [STALE_PROVENANCE]
    assert historical["duration"]["estimated_duration_minutes"] == 30

    missing = dict(live)
    missing["scheduling_activation"] = {"ids": ["s2-v1-duration-bounds"]}
    assert diff_stale_categories(missing, live) == [STALE_SCHEDULING_ACTIVATION]

    changed_default = _snap(
        snapshot_version=SNAPSHOT_VERSION_V4,
        worked_minutes=0,
        remaining_minutes=30,
        effective_min_minutes=45,
        min_block_source="user_default",
    )
    assert diff_stale_categories(live, changed_default) == ["duration"]
    assert owner_snapshot_predates_activation({"snapshot_version": 3, "v": 1}) is True
    assert owner_snapshot_predates_activation(
        {
            "snapshot_version": 4,
            "scheduling_activation": {"ids": list(SCHEDULING_ACTIVATIONS)},
        }
    ) is False
    assert chunking_activation_revision(7) == 8


def test_buffer_pad_is_trailing_only_and_a15_is_open() -> None:
    start = NOW
    end = NOW + timedelta(minutes=30)
    busy = add_busy_interval([], start, end, 5)
    assert busy[0].start == start
    assert busy[0].end == end + timedelta(minutes=5)
    # A15 is not closed: this is not both-sides clearance against fixed busy.
