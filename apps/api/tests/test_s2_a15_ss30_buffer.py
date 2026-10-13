"""A15 / SS-30 buffer evidence on the V1/V2 placer path.

No database. Approved policy is S0 §6.1 (Trish 2026-10-12). These tests are
the alongside matrix for changed placement: ``place_one_block`` → ``place_task``
→ ``add_busy_interval`` / ``find_slot``.

Travel vs buffer is deferred (event travel is not live). Not an S2-V3 case.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest

from app.models import Task, UserSettings
from app.models.enums import TaskPriority
from app.scheduler import busy_map
from app.scheduler.busy_map import BusyInterval
from app.scheduler.calculate import calculate
from app.scheduler.candidates import TaskCandidate
from app.scheduler.collect import SchedulingInputs
from app.scheduler.placement import PlacementResult, ProposedBlock, place_one_block
from app.scheduler.preview_proposal import (
    build_proposal_json,
    calculation_result_from_proposal,
)
from app.scheduler.reasons import (
    REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER,
    REASON_PLACED,
    format_summary_text,
)

DAY = datetime(2026, 10, 13, tzinfo=timezone.utc)  # Tuesday
NOW = DAY.replace(hour=7)
HORIZON_END = DAY + timedelta(days=1, hours=7)
WORK_MINUTES = 30


def _at(hour: int, minute: int = 0) -> datetime:
    return DAY.replace(hour=hour, minute=minute)


def _minutes(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def _settings(buffer_minutes: int) -> UserSettings:
    return UserSettings(
        owner_id=uuid4(),
        timezone="UTC",
        workday_start_local=time(8, 0),
        workday_minutes=540,
        workweek_days=7,
        inter_block_buffer_minutes=buffer_minutes,
        default_min_block_duration_minutes=15,
        default_max_block_duration_minutes=120,
        default_max_block_unbounded=False,
        auto_defer_enabled=False,
    )


def _task(*, minutes: int = WORK_MINUTES, remaining: int | None = None, title: str = "auto") -> Task:
    span = remaining if remaining is not None else minutes
    return Task(
        id=uuid4(),
        owner_id=uuid4(),
        title=title,
        estimated_duration_minutes=span,
        remaining_minutes=span,
        min_block_duration_minutes=minutes,
        max_block_duration_minutes=minutes,
        max_block_unbounded=False,
        keep_in_one_block=False,
    )


def _place(
    task: Task,
    settings: UserSettings,
    busy: list[BusyInterval],
    *,
    remaining: int | None = None,
    prerequisite_not_before: datetime | None = None,
) -> tuple[PlacementResult, list[BusyInterval]]:
    return place_one_block(
        None,  # type: ignore[arg-type]
        task=task,
        owner_id=task.owner_id,
        settings=settings,
        remaining_minutes=task.estimated_duration_minutes if remaining is None else remaining,
        busy=list(busy),
        horizon_start=NOW,
        horizon_end=HORIZON_END,
        preferred_windows={},
        now_utc=NOW,
        prerequisite_not_before=prerequisite_not_before,
        persist_blocks=False,
    )


def _only_block(result: PlacementResult) -> ProposedBlock:
    assert result.blocks_created == 1, result
    assert result.proposed_blocks is not None and len(result.proposed_blocks) == 1
    return result.proposed_blocks[0]


def _fixed_still_covers(
    busy: list[BusyInterval],
    source: str,
    start: datetime,
    end: datetime,
    buffer_minutes: int,
) -> None:
    """Fixed occupancy still covers its original span and was not slid aside."""
    matched = [item for item in busy if item.source == source and item.start <= start and item.end >= end]
    assert matched, f"{source} {start.isoformat()}–{end.isoformat()} missing from {busy}"
    item = matched[0]
    slack = timedelta(minutes=buffer_minutes)
    assert item.start >= start - slack
    assert item.end <= end + slack


def _gap_between(first: ProposedBlock, second: ProposedBlock) -> int:
    earlier, later = sorted((first, second), key=lambda block: block.start_time)
    return _minutes(earlier.end_time, later.start_time)


def _fixed_buffer_conflict_visible(
    result: PlacementResult,
    busy: list[BusyInterval],
    buffer_minutes: int,
) -> bool:
    """True when this pass reports a pre-existing fixed-item buffer conflict.

    Accepts a placer/busy-map hook. There is no such reporter today.
    """
    for name in ("fixed_buffer_conflicts", "report_fixed_buffer_conflicts"):
        fn = getattr(busy_map, name, None)
        if not callable(fn):
            continue
        found = fn(busy, buffer_minutes)
        if found:
            return True
    payload = result.last_failure, result.pass_hints, result.observed_constraints
    text = repr(payload).lower()
    return "buffer" in text and ("pinned" in text or "external" in text or "fixed" in text)


def test_buffer_zero_allows_adjacency_on_both_sides_and_between_autos() -> None:
    settings = _settings(0)
    pin = BusyInterval(_at(8, 30), _at(9, 30), source="pinned")
    before_pin, busy = _place(_task(title="before-pin"), settings, [pin])
    block = _only_block(before_pin)
    assert block.start_time == _at(8, 0)
    assert block.end_time == pin.start

    external = BusyInterval(_at(8, 0), _at(9, 0), source="external")
    after_external, _ = _place(_task(title="after-external"), settings, [external])
    block = _only_block(after_external)
    assert block.start_time == external.end
    assert block.end_time == _at(9, 30)

    first, busy = _place(_task(title="A"), settings, [])
    second, _ = _place(_task(title="B"), settings, busy)
    assert _gap_between(_only_block(first), _only_block(second)) == 0


@pytest.mark.parametrize("buffer_minutes", [0, 5, 10])
def test_auto_auto_separation_equals_buffer(buffer_minutes: int) -> None:
    settings = _settings(buffer_minutes)
    first, busy = _place(_task(title="A"), settings, [])
    second, _ = _place(_task(title="B"), settings, busy)
    earlier = _only_block(first)
    later = _only_block(second)
    assert _minutes(earlier.start_time, earlier.end_time) == WORK_MINUTES
    assert _minutes(later.start_time, later.end_time) == WORK_MINUTES
    assert _minutes(earlier.end_time, later.start_time) == buffer_minutes


@pytest.mark.parametrize("buffer_minutes", [5, 10])
@pytest.mark.parametrize("source", ["pinned", "external"])
def test_auto_keeps_buffer_after_fixed_busy(buffer_minutes: int, source: str) -> None:
    fixed = BusyInterval(_at(8, 0), _at(9, 0), source=source)
    result, busy = _place(_task(), _settings(buffer_minutes), [fixed])
    block = _only_block(result)
    assert block.start_time == fixed.end + timedelta(minutes=buffer_minutes)
    assert block.end_time == block.start_time + timedelta(minutes=WORK_MINUTES)
    _fixed_still_covers(busy, source, fixed.start, fixed.end, buffer_minutes)


@pytest.mark.parametrize("buffer_minutes", [5, 10])
@pytest.mark.parametrize("source", ["pinned", "external"])
def test_auto_keeps_buffer_before_fixed_busy(buffer_minutes: int, source: str) -> None:
    """A 30-minute gap before fixed busy cannot hold a 30-minute block plus buffer.

    The legal slot is after the fixed item, buffer minutes clear of it.
    """
    fixed = BusyInterval(_at(8, 30), _at(9, 30), source=source)
    result, busy = _place(_task(), _settings(buffer_minutes), [fixed])
    block = _only_block(result)
    assert block.start_time == fixed.end + timedelta(minutes=buffer_minutes)
    assert block.end_time == block.start_time + timedelta(minutes=WORK_MINUTES)
    assert block.end_time <= fixed.start or block.start_time >= fixed.end + timedelta(
        minutes=buffer_minutes
    )
    _fixed_still_covers(busy, source, fixed.start, fixed.end, buffer_minutes)


@pytest.mark.parametrize("buffer_minutes", [0, 5, 10])
def test_same_task_split_keeps_buffer_between_consecutive_blocks(buffer_minutes: int) -> None:
    task = _task(remaining=60)
    settings = _settings(buffer_minutes)
    first, busy = _place(task, settings, [], remaining=60)
    assert first.remaining_minutes == 30
    second, _ = _place(task, settings, busy, remaining=first.remaining_minutes)
    earlier = _only_block(first)
    later = _only_block(second)
    assert earlier.task_id == later.task_id == task.id
    assert _minutes(earlier.start_time, earlier.end_time) == WORK_MINUTES
    assert _minutes(later.start_time, later.end_time) == WORK_MINUTES
    assert _minutes(earlier.end_time, later.start_time) == buffer_minutes
    assert second.remaining_minutes == 0


@pytest.mark.parametrize("buffer_minutes", [0, 5, 10])
def test_order_independence_required_gap_is_min_not_sum(buffer_minutes: int) -> None:
    def _ordered_gap(first_title: str, second_title: str) -> int:
        settings = _settings(buffer_minutes)
        first, busy = _place(_task(title=first_title), settings, [])
        second, _ = _place(_task(title=second_title), settings, busy)
        return _gap_between(_only_block(first), _only_block(second))

    gap_ab = _ordered_gap("A", "B")
    gap_ba = _ordered_gap("B", "A")
    assert gap_ab == buffer_minutes
    assert gap_ba == buffer_minutes
    if buffer_minutes:
        assert gap_ab != buffer_minutes * 2
        assert gap_ba != buffer_minutes * 2


@pytest.mark.parametrize("buffer_minutes", [5, 10])
@pytest.mark.parametrize("source", ["pinned", "external"])
def test_tighter_than_buffer_is_unscheduled_with_explanation(
    buffer_minutes: int,
    source: str,
) -> None:
    fixed = BusyInterval(_at(8, 30), _at(17, 0), source=source)
    result, busy = _place(_task(), _settings(buffer_minutes), [fixed])
    assert result.blocks_created == 0
    assert not result.proposed_blocks
    assert result.remaining_minutes == WORK_MINUTES
    assert result.last_failure is not None
    assert result.observed_constraints
    _fixed_still_covers(busy, source, fixed.start, fixed.end, buffer_minutes)


def test_preexisting_tight_fixed_pair_reports_conflict_and_stays_put() -> None:
    """Pin and external event 5 minutes apart, buffer 10. Report it; do not move them."""
    pin = BusyInterval(_at(10, 0), _at(10, 30), source="pinned")
    event = BusyInterval(_at(10, 35), _at(11, 5), source="external")
    result, busy = _place(_task(minutes=15), _settings(10), [pin, event])
    _fixed_still_covers(busy, "pinned", pin.start, pin.end, 10)
    _fixed_still_covers(busy, "external", event.start, event.end, 10)
    assert _fixed_buffer_conflict_visible(result, busy, 10), (
        "S0 section 6.1 row 8: fixed items closer than buffer must be reported and left "
        f"unmoved. gap=5 buffer=10 observed={result.observed_constraints} "
        f"hints={result.pass_hints} last_failure={result.last_failure}. "
        "busy_map.add_busy_interval only pads a new auto block's trailing edge; "
        "no fixed-pair buffer reporter exists."
    )


@pytest.mark.parametrize("buffer_minutes", [0, 5, 10])
def test_reverse_chronological_insert_keeps_single_buffer(buffer_minutes: int) -> None:
    """S2-D4: a later auto placed first still keeps one gap when an earlier task follows.

    Title swaps still place in chronological order, so they miss this. The first
    task cannot start before 08:30. The second opens at 08:00. The gap is the
    buffer once, including buffer 0 flush, and never twice the buffer.
    """
    settings = _settings(buffer_minutes)
    later, busy = _place(
        _task(title="later-prerequisite"),
        settings,
        [],
        prerequisite_not_before=_at(8, 30),
    )
    earlier, _ = _place(_task(title="earlier-opening"), settings, busy)
    later_block = _only_block(later)
    earlier_block = _only_block(earlier)

    assert later_block.start_time == _at(8, 30)
    assert later_block.end_time == _at(9, 0)
    assert _minutes(earlier_block.start_time, earlier_block.end_time) == WORK_MINUTES
    assert _minutes(later_block.start_time, later_block.end_time) == WORK_MINUTES
    gap = _gap_between(later_block, earlier_block)
    assert gap == buffer_minutes
    if buffer_minutes:
        assert earlier_block.start_time == _at(9, 0) + timedelta(minutes=buffer_minutes)
        assert gap != buffer_minutes * 2
        assert earlier_block.end_time <= later_block.start_time or earlier_block.start_time >= (
            later_block.end_time + timedelta(minutes=buffer_minutes)
        )
    else:
        assert earlier_block.start_time == _at(8, 0)
        assert earlier_block.end_time == later_block.start_time


def test_successful_placement_reports_fixed_pair_on_calculate_and_preview() -> None:
    """S2-D5: a placed task still carries the tight fixed-pair warning.

    Pins at 14:00–14:30 and 14:35–15:05 stay put (gap 5, buffer 10). The
    15-minute task places. The warning is on the calculation outcome and the
    preview proposal, and it is not a reason to drop the block.
    """
    pin = BusyInterval(_at(14, 0), _at(14, 30), source="pinned")
    event = BusyInterval(_at(14, 35), _at(15, 5), source="external")
    busy = [pin, event]
    pin_bounds = [(item.source, item.start, item.end) for item in busy]
    task = _task(minutes=15, title="elsewhere")
    task.priority = TaskPriority.p4
    settings = _settings(10)
    candidate = TaskCandidate(
        task=task,
        remaining_minutes=15,
        reserved_minutes=0,
        effort_minutes=15,
    )
    inputs = SchedulingInputs(
        owner_id=task.owner_id,
        user_settings=settings,
        now_utc=NOW,
        horizon_start=NOW,
        horizon_end=HORIZON_END,
        busy=list(busy),
        candidates=[candidate],
        excluded_tasks=[],
        lifecycle_excluded_tasks=[],
        dependencies=[],
        projects={},
        epics={},
        ups_scores={task.id: 1.0},
        ordered_candidates=[candidate],
        dependency_stats={},
        effective_window_by_task={task.id: None},
        effective_window_source_by_task={task.id: None},
        preferred_windows={},
        time_map_overrides_by_map={},
        daily_cap=None,
        pinned_blocks_by_task={},
        immovable_busy=list(busy),
    )

    result = calculate(None, inputs)  # type: ignore[arg-type]

    assert [(item.source, item.start, item.end) for item in busy] == pin_bounds
    assert result.blocks_created == 1
    assert result.proposed_blocks is not None and len(result.proposed_blocks) == 1
    block = result.proposed_blocks[0]
    assert block.task_id == task.id
    assert _minutes(block.start_time, block.end_time) == 15
    assert block.end_time <= pin.start or block.start_time >= event.end
    assert not (block.start_time < pin.end and block.end_time > pin.start)
    assert not (block.start_time < event.end and block.end_time > event.start)

    outcome = next(item for item in result.outcomes if item.task_id == task.id)
    codes = [fact.code for fact in outcome.reason_facts]
    assert codes[0] == REASON_PLACED
    assert outcome.primary_code == REASON_PLACED
    assert outcome.placed_minutes == 15
    assert outcome.remaining_minutes == 0
    warning = next(
        fact for fact in outcome.reason_facts if fact.code == REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER
    )
    assert warning.params["buffer_minutes"] == 10
    assert warning.params["gap_minutes"] == 5
    summary = format_summary_text(outcome.reason_facts)
    assert "Placed 15" in summary
    assert "were not moved" in summary

    placement = result.placement_facts_by_task[task.id]
    hint_codes = [
        hint.get("reason_code")
        for hint in placement.get("pass_hints") or []
        if isinstance(hint, dict)
    ]
    assert REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER in hint_codes
    assert placement.get("last_failure") is None

    proposal = build_proposal_json(inputs=inputs, result=result, before_blocks=[])
    proposed_outcome = next(
        row for row in proposal["outcomes"] if row["task_id"] == str(task.id)
    )
    proposed_codes = [fact["code"] for fact in proposed_outcome["reason_facts"]]
    assert proposed_codes[0] == REASON_PLACED
    assert REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER in proposed_codes
    assert proposed_outcome["primary_reason_code"] == REASON_PLACED
    assert proposed_outcome["placed_minutes"] == 15

    rebuilt = calculation_result_from_proposal(proposal)
    rebuilt_outcome = next(item for item in rebuilt.outcomes if item.task_id == task.id)
    rebuilt_codes = [fact.code for fact in rebuilt_outcome.reason_facts]
    assert REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER in rebuilt_codes
    assert rebuilt_outcome.primary_code == REASON_PLACED
    assert rebuilt.blocks_created == 1
