"""S2-D3: exact keep-in-one cover still reports Working availability.

No database. A pin that matches remaining effort is reserved and adds no
automatic work. That shape is not proof the pin sits inside Working hours.
Partial overlap reports the uncovered portion. Ending on the window boundary
is contained; starting on that boundary is not.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.models.enums import ScheduleStyle
from app.scheduler.calculate import _outcomes_for_excluded
from app.scheduler.candidates import ExcludedTask
from app.scheduler.pin_reservation import (
    CONFLICT_OUTSIDE_WORKING,
    AutoPlacementDecision,
    evaluate_auto_placement,
)
from app.scheduler.reasons import (
    REASON_EXCLUDED_KEEP_IN_ONE_RESERVED,
    REASON_OUTSIDE_WORKING_AVAILABILITY,
    TaskSchedulingOutcome,
    format_summary_text,
)

NOW = datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc)


def _working_settings() -> SimpleNamespace:
    return SimpleNamespace(
        default_min_block_duration_minutes=15,
        default_max_block_duration_minutes=120,
        default_max_block_unbounded=False,
        timezone="UTC",
        workday_start_local=time(9, 0),
        workday_minutes=480,
        workweek_days=5,
    )


def _task() -> SimpleNamespace:
    return SimpleNamespace(
        estimated_duration_minutes=240,
        remaining_minutes=240,
        worked_minutes=0,
        min_block_duration_minutes=15,
        max_block_duration_minutes=None,
        max_block_unbounded=True,
        keep_in_one_block=True,
    )


def _pin(start: datetime, end: datetime) -> SimpleNamespace:
    return SimpleNamespace(start_time=start, end_time=end)


def _outcome_codes(
    decision: AutoPlacementDecision,
) -> tuple[list[str], TaskSchedulingOutcome]:
    item = ExcludedTask(
        task=SimpleNamespace(id=uuid4()),
        requested_minutes=decision.effort_minutes,
        pinned_minutes=decision.reserved_minutes,
        remaining_minutes=decision.outcome_remaining_minutes,
        schedule_style=ScheduleStyle.standalone,
        style_source="task",
        reason_code=decision.reason_code,
        reason_params=dict(decision.reason_params),
    )
    outcomes = _outcomes_for_excluded(SimpleNamespace(excluded_tasks=[item]))
    assert len(outcomes) == 1
    return [fact.code for fact in outcomes[0].reason_facts], outcomes[0]


def test_exact_cover_outside_working_keeps_pin_and_reports_conflict() -> None:
    pin = _pin(
        datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 13, 0, 0, tzinfo=timezone.utc),
    )
    start, end = pin.start_time, pin.end_time
    decision = evaluate_auto_placement(_task(), _working_settings(), [pin], NOW)

    assert pin.start_time == start
    assert pin.end_time == end
    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.effort_minutes == 240
    assert decision.reserved_minutes == 240
    assert decision.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert decision.conflicts[0]["code"] == CONFLICT_OUTSIDE_WORKING
    assert decision.conflicts[0]["detail"]["pins_protected"] is True
    assert decision.conflicts[0]["detail"]["automatic_work_minutes"] == 0
    assert decision.conflicts[0]["detail"]["outside_intervals"] == [
        {
            "start": "2026-10-12T20:00:00+00:00",
            "end": "2026-10-13T00:00:00+00:00",
        }
    ]

    codes, outcome = _outcome_codes(decision)
    assert codes[0] == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert REASON_OUTSIDE_WORKING_AVAILABILITY in codes
    assert outcome.placed_minutes == 0
    assert outcome.remaining_minutes == 0
    summary = format_summary_text(outcome.reason_facts)
    assert "reserved in one pinned block" in summary
    assert "outside Working availability" in summary


def test_exact_cover_inside_working_stays_reserved_without_availability_conflict() -> None:
    pin = _pin(
        datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc),
    )
    decision = evaluate_auto_placement(_task(), _working_settings(), [pin], NOW)

    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert decision.conflicts == ()
    assert "constraint_conflicts" not in decision.reason_params
    codes, _outcome = _outcome_codes(decision)
    assert codes == [REASON_EXCLUDED_KEEP_IN_ONE_RESERVED]


def test_context_conflict_hook_survives_exact_cover() -> None:
    pin = _pin(
        datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc),
    )
    sentinel = {
        "code": "context_not_in_scope",
        "message": "Context constraint reserved for a later input.",
        "detail": {"pins_protected": True, "automatic_work_minutes": 0},
    }
    decision = evaluate_auto_placement(
        _task(),
        _working_settings(),
        [pin],
        NOW,
        context_conflicts=(sentinel,),
    )

    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert [row["code"] for row in decision.conflicts] == ["context_not_in_scope"]
    codes, _outcome = _outcome_codes(decision)
    assert codes[0] == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert "context_not_in_scope" in codes
    assert REASON_OUTSIDE_WORKING_AVAILABILITY not in codes


def test_exact_cover_partial_overlap_reports_uncovered_portion() -> None:
    """Dex residual: 16:00–20:00 overlaps 09:00–17:00 and still leaves 17:00–20:00 out."""
    pin = _pin(
        datetime(2026, 10, 13, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc),
    )
    start, end = pin.start_time, pin.end_time
    decision = evaluate_auto_placement(_task(), _working_settings(), [pin], NOW)

    assert pin.start_time == start
    assert pin.end_time == end
    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.effort_minutes == 240
    assert decision.reserved_minutes == 240
    assert decision.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert decision.conflicts[0]["code"] == CONFLICT_OUTSIDE_WORKING
    assert decision.conflicts[0]["detail"]["pins_protected"] is True
    assert decision.conflicts[0]["detail"]["automatic_work_minutes"] == 0
    assert decision.conflicts[0]["detail"]["outside_intervals"] == [
        {
            "start": "2026-10-13T17:00:00+00:00",
            "end": "2026-10-13T20:00:00+00:00",
        }
    ]

    codes, outcome = _outcome_codes(decision)
    assert codes[0] == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert REASON_OUTSIDE_WORKING_AVAILABILITY in codes
    assert outcome.placed_minutes == 0
    assert outcome.remaining_minutes == 0
    summary = format_summary_text(outcome.reason_facts)
    assert "reserved in one pinned block" in summary
    assert "outside Working availability" in summary


def test_exact_cover_ending_on_window_boundary_is_contained() -> None:
    pin = _pin(
        datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 13, 17, 0, tzinfo=timezone.utc),
    )
    decision = evaluate_auto_placement(_task(), _working_settings(), [pin], NOW)

    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert decision.conflicts == ()
    assert "constraint_conflicts" not in decision.reason_params
    codes, _outcome = _outcome_codes(decision)
    assert codes == [REASON_EXCLUDED_KEEP_IN_ONE_RESERVED]


def test_exact_cover_starting_on_window_boundary_is_outside() -> None:
    pin = _pin(
        datetime(2026, 10, 13, 17, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 13, 21, 0, tzinfo=timezone.utc),
    )
    start, end = pin.start_time, pin.end_time
    decision = evaluate_auto_placement(_task(), _working_settings(), [pin], NOW)

    assert pin.start_time == start
    assert pin.end_time == end
    assert decision.auto_place is False
    assert decision.minutes_to_place == 0
    assert decision.reason_code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert decision.conflicts[0]["code"] == CONFLICT_OUTSIDE_WORKING
    assert decision.conflicts[0]["detail"]["automatic_work_minutes"] == 0
    assert decision.conflicts[0]["detail"]["outside_intervals"] == [
        {
            "start": "2026-10-13T17:00:00+00:00",
            "end": "2026-10-13T21:00:00+00:00",
        }
    ]
    codes, _outcome = _outcome_codes(decision)
    assert codes[0] == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED
    assert REASON_OUTSIDE_WORKING_AVAILABILITY in codes
