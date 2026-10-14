"""S2-V4b Quality fixtures — A14b clocks, overlap, R1–R3, A14c bounds, fingerprint.

No database. Household activation is not invoked.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import Task, UserSettings
from app.models.enums import TaskPriority
from app.scheduler.composition import (
    RANK_ELIGIBLE,
    AssignmentFamily,
    CompositionInput,
    MayMode,
    RuleRole,
    ScopeLayer,
    composition_fingerprint,
    composition_search_windows,
    make_window,
    resolve_effective_composition,
    rule,
)
from app.scheduler.day_scoped import (
    CivilSelector,
    DayScopedDeclaration,
    DayScopedOp,
    SelectorKind,
    declaration_problem,
)
from app.scheduler.input_fingerprint import (
    COMPARED_STALE_CATEGORIES,
    DEFERRED_STALE_CATEGORIES,
    SCHEDULING_ACTIVATIONS,
    STALE_COMPOSITION,
    STALE_PRIORITY_UPS,
    assemble_snapshot,
    diff_stale_categories,
)
from app.scheduler.placement import place_task
from app.scheduler.reasons import REASON_UNMET_PREFERENCE, ReasonFact, format_summary_text

UTC = timezone.utc
TZ = ZoneInfo("UTC")
LA = ZoneInfo("America/Los_Angeles")
MONDAY = date(2026, 10, 12)
TUESDAY = date(2026, 10, 13)
NEXT_MONDAY = date(2026, 10, 19)
SPRING = date(2026, 3, 8)
FOLD = date(2026, 11, 1)


def _window(hour: int, minute: int, duration: int, weekday: int = 0):
    return make_window(weekday, time(hour, minute), duration)


def _layer(scope, scope_id, *, may_mode=MayMode.PRESENT, may=(), must=(), prefer=()):
    return ScopeLayer(
        scope=scope,
        scope_id=scope_id,
        may_mode=may_mode,
        may_rules=may,
        must_rules=must,
        prefer_rules=prefer,
    )


def _resolve(*layers, day_scoped=()):
    return resolve_effective_composition(
        CompositionInput(
            family=AssignmentFamily.NEW_RULE,
            layers=layers,
            day_scoped=tuple(day_scoped),
        )
    )


def _decl(op, selector, **kwargs):
    return DayScopedDeclaration(
        declaration_id=kwargs.pop("declaration_id", op.value),
        operation=op,
        scope=kwargs.pop("scope", "task"),
        scope_id=kwargs.pop("scope_id", "t"),
        selector=selector,
        **kwargs,
    )


def _eligible(day, composed, general=()):
    return [
        (item[0], item[1])
        for item in composition_search_windows(day, TZ, composed, general)
        if item[2] == RANK_ELIGIBLE
    ]


def _task(minutes: int, *, priority=TaskPriority.p4, deadline=None) -> Task:
    return Task(
        id=uuid4(),
        owner_id=uuid4(),
        title="v4b-quality",
        estimated_duration_minutes=minutes,
        min_block_duration_minutes=60,
        max_block_duration_minutes=minutes,
        max_block_unbounded=False,
        keep_in_one_block=False,
        worked_minutes=0,
        priority=priority,
        deadline_at=deadline,
    )


def _settings() -> UserSettings:
    return UserSettings(
        owner_id=uuid4(),
        timezone="UTC",
        inter_block_buffer_minutes=0,
        default_min_block_duration_minutes=15,
        default_max_block_duration_minutes=120,
        default_max_block_unbounded=False,
    )


def _place(composition, task, *, now, end, general=None):
    result, _busy = place_task(
        None,  # type: ignore[arg-type]
        task=task,
        owner_id=task.owner_id,
        settings=_settings(),
        remaining_minutes=task.estimated_duration_minutes,
        busy=[],
        horizon_start=now,
        horizon_end=end,
        preferred_windows={},
        now_utc=now,
        finalize_status=False,
        persist_blocks=False,
        working_windows=[],
        general_windows=list(general or []),
        composition=composition,
    )
    return result


def _standing_week():
    return (
        rule(
            "day",
            RuleRole.MAY,
            (
                _window(9, 0, 180, weekday=0),
                make_window(0, time(22, 0), 240),
                _window(9, 0, 180, weekday=1),
            ),
            scope="task",
            scope_id="t",
        ),
    )


def test_r1_change_keeps_overnight_tail_only_allow_uses_its_own_instant() -> None:
    """Monday–Monday Change keeps the Tuesday 02:00 tail. Only-allow does not share that end."""
    standing = _standing_week()
    change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.DATE_RANGE, range_start=MONDAY, range_end=MONDAY),
        windows=(make_window(0, time(22, 0), 240),),
    )
    changed = _resolve(_layer("task", "t", may=standing), day_scoped=(change,))
    monday = _eligible(MONDAY, changed)
    assert (datetime(2026, 10, 12, 22, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC)) in monday
    tuesday = _eligible(TUESDAY, changed)
    assert (datetime(2026, 10, 13, 0, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC)) in tuesday
    assert (datetime(2026, 10, 13, 9, 0, tzinfo=UTC), datetime(2026, 10, 13, 12, 0, tzinfo=UTC)) in tuesday

    clipped = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.DATE_RANGE, range_start=MONDAY, range_end=MONDAY),
        windows=(make_window(0, time(22, 0), 240),),
        expires_at=datetime(2026, 10, 13, 1, 0, tzinfo=UTC),
        declaration_id="change-cut",
    )
    cut = _resolve(_layer("task", "t", may=standing), day_scoped=(clipped,))
    cut_monday = composition_search_windows(MONDAY, TZ, cut, [])
    assert max(item[1] for item in cut_monday) == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    assert (datetime(2026, 10, 13, 9, 0, tzinfo=UTC), datetime(2026, 10, 13, 12, 0, tzinfo=UTC)) in _eligible(
        TUESDAY, cut
    )

    weekday_only = _decl(
        DayScopedOp.ONLY_ALLOW,
        CivilSelector(SelectorKind.WEEKDAY, weekdays=(0,)),
        windows=(_window(9, 0, 480, weekday=0),),
        declaration_id="only-weekday",
    )
    exclusive = _resolve(_layer("task", "t", may=standing), day_scoped=(weekday_only,))
    assert _eligible(TUESDAY, exclusive) == []
    monday_only = _eligible(MONDAY, exclusive)
    assert (datetime(2026, 10, 12, 9, 0, tzinfo=UTC), datetime(2026, 10, 12, 12, 0, tzinfo=UTC)) in monday_only
    assert all(end <= datetime(2026, 10, 13, 0, 0, tzinfo=UTC) for _start, end in monday_only)
    assert all(start.hour != 22 for start, _end in monday_only)

    overnight_only = _decl(
        DayScopedOp.ONLY_ALLOW,
        CivilSelector(SelectorKind.WEEKDAY, weekdays=(0,)),
        windows=(make_window(0, time(22, 0), 240),),
        declaration_id="only-overnight",
    )
    overnight_exclusive = _resolve(
        _layer("task", "t", may=standing), day_scoped=(overnight_only,)
    )
    overnight_monday = _eligible(MONDAY, overnight_exclusive)
    assert overnight_monday
    assert max(end for _start, end in overnight_monday) == datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
    assert _eligible(TUESDAY, overnight_exclusive) == []

    ranged_only = _decl(
        DayScopedOp.ONLY_ALLOW,
        CivilSelector(SelectorKind.DATE_RANGE, range_start=MONDAY, range_end=MONDAY),
        windows=(_window(9, 0, 480, weekday=0),),
        declaration_id="only-range",
    )
    ranged = _resolve(_layer("task", "t", may=standing), day_scoped=(ranged_only,))
    assert (datetime(2026, 10, 13, 9, 0, tzinfo=UTC), datetime(2026, 10, 13, 12, 0, tzinfo=UTC)) in _eligible(
        TUESDAY, ranged
    )
    ranged_monday = _eligible(MONDAY, ranged)
    assert (datetime(2026, 10, 13, 0, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC)) in ranged_monday
    assert all(start.hour != 22 for start, _end in ranged_monday)


def test_weekday_standing_repeats_and_one_date_does_not() -> None:
    may = (
        rule(
            "day",
            RuleRole.MAY,
            (_window(9, 0, 180, weekday=0),),
            scope="task",
            scope_id="t",
        ),
    )
    every = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.WEEKDAY, weekdays=(0,)),
        windows=(_window(15, 0, 60, weekday=0),),
    )
    folded = _resolve(_layer("task", "t", may=may), day_scoped=(every,))
    assert [start.hour for start, _end in _eligible(MONDAY, folded)] == [15]
    assert [start.hour for start, _end in _eligible(NEXT_MONDAY, folded)] == [15]
    assert _eligible(TUESDAY, folded) == []

    once = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(15, 0, 60, weekday=0),),
        declaration_id="this-monday",
    )
    once_folded = _resolve(_layer("task", "t", may=may), day_scoped=(once,))
    assert [start.hour for start, _end in _eligible(MONDAY, once_folded)] == [15]
    assert [start.hour for start, _end in _eligible(NEXT_MONDAY, once_folded)] == [9]


def test_empty_exclusive_does_not_borrow_ancestor_or_general() -> None:
    parent = _layer(
        "project",
        "p",
        may=(
            rule(
                "ancestor",
                RuleRole.MAY,
                (_window(9, 0, 180, weekday=0), _window(9, 0, 180, weekday=1)),
                scope="project",
                scope_id="p",
            ),
        ),
    )
    general = (_window(18, 0, 60, weekday=0), _window(18, 0, 60, weekday=1))
    empty_change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        empty_set=True,
    )
    closed = _resolve(parent, _layer("task", "t", may_mode=MayMode.ABSENT), day_scoped=(empty_change,))
    assert composition_search_windows(TUESDAY, TZ, closed, general) == []
    monday = _eligible(MONDAY, closed, general)
    assert (datetime(2026, 10, 12, 9, 0, tzinfo=UTC), datetime(2026, 10, 12, 12, 0, tzinfo=UTC)) in monday
    assert all(start.hour != 18 for start, _end in monday)

    empty_only = _decl(
        DayScopedOp.ONLY_ALLOW,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        empty_set=True,
        declaration_id="empty-only",
    )
    exclusive = _resolve(parent, _layer("task", "t", may_mode=MayMode.ABSENT), day_scoped=(empty_only,))
    assert composition_search_windows(TUESDAY, TZ, exclusive, general) == []
    assert (datetime(2026, 10, 12, 9, 0, tzinfo=UTC), datetime(2026, 10, 12, 12, 0, tzinfo=UTC)) in _eligible(
        MONDAY, exclusive, general
    )

    placed = _place(
        exclusive,
        _task(60, priority=TaskPriority.p1, deadline=datetime(2026, 10, 13, 20, 0, tzinfo=UTC)),
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 21, 0, tzinfo=UTC),
        general=general,
    )
    assert placed.blocks_created == 0


def test_additions_combine_overlapping_minutes_once() -> None:
    standing = (
        rule("base", RuleRole.MAY, (_window(9, 0, 60, weekday=0),), scope="task", scope_id="t"),
    )
    first = _decl(
        DayScopedOp.ADD_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(10, 0, 120, weekday=0),),
        role="may",
        output_rule_id="add-a",
        declaration_id="add-a",
    )
    second = _decl(
        DayScopedOp.ADD_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(11, 0, 120, weekday=0),),
        role="may",
        output_rule_id="add-b",
        declaration_id="add-b",
    )
    folded = _resolve(_layer("task", "t", may=standing), day_scoped=(first, second))
    spans = _eligible(MONDAY, folded)
    assert spans == [
        (datetime(2026, 10, 12, 9, 0, tzinfo=UTC), datetime(2026, 10, 12, 13, 0, tzinfo=UTC))
    ]
    assert spans[0][1] - spans[0][0] == timedelta(hours=4)


def test_which_replaces_which_names_the_winner_and_cycles_do_not() -> None:
    standing = (
        rule("day", RuleRole.MAY, (_window(9, 0, 180, weekday=0),), scope="task", scope_id="t"),
    )
    loser = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(15, 0, 60, weekday=0),),
        declaration_id="loser",
    )
    winner = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(8, 0, 60, weekday=0),),
        replaces_id="loser",
        declaration_id="winner",
    )
    named = _resolve(_layer("task", "t", may=standing), day_scoped=(loser, winner))
    assert _eligible(MONDAY, named) == [
        (datetime(2026, 10, 12, 8, 0, tzinfo=UTC), datetime(2026, 10, 12, 9, 0, tzinfo=UTC))
    ]

    unresolved = _resolve(_layer("task", "t", may=standing), day_scoped=(loser, replace(winner, replaces_id=None, declaration_id="other")))
    assert [start.hour for start, _end in _eligible(MONDAY, unresolved)] == [9]

    cycle_a = replace(loser, replaces_id="winner", declaration_id="cycle-a")
    cycle_b = replace(winner, replaces_id="cycle-a", declaration_id="winner")
    cyclic = _resolve(_layer("task", "t", may=standing), day_scoped=(cycle_a, cycle_b))
    assert [start.hour for start, _end in _eligible(MONDAY, cyclic)] == [9]


def test_addition_survives_is_required_and_not_inferred() -> None:
    standing = (
        rule("day", RuleRole.MAY, (_window(9, 0, 180, weekday=0),), scope="task", scope_id="t"),
    )
    change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(15, 0, 60, weekday=0),),
        declaration_id="change",
    )
    added = _decl(
        DayScopedOp.ADD_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(15, 30, 60, weekday=0),),
        role="may",
        output_rule_id="extra",
        declaration_id="extra",
    )
    survived = _resolve(
        _layer("task", "t", may=standing),
        day_scoped=(change, replace(added, addition_survives=True)),
    )
    assert _eligible(MONDAY, survived) == [
        (datetime(2026, 10, 12, 15, 0, tzinfo=UTC), datetime(2026, 10, 12, 16, 30, tzinfo=UTC))
    ]

    dropped = _resolve(
        _layer("task", "t", may=standing),
        day_scoped=(change, replace(added, addition_survives=False)),
    )
    assert _eligible(MONDAY, dropped) == [
        (datetime(2026, 10, 12, 15, 0, tzinfo=UTC), datetime(2026, 10, 12, 16, 0, tzinfo=UTC))
    ]

    omitted = _resolve(
        _layer("task", "t", may=standing),
        day_scoped=(change, added),
    )
    assert [start.hour for start, _end in _eligible(MONDAY, omitted)] == [9]


def test_different_named_targets_do_not_conflict_on_date_overlap() -> None:
    standing = (
        rule("study", RuleRole.MAY, (_window(9, 0, 180, weekday=0),), scope="task", scope_id="t"),
        rule("work", RuleRole.MAY, (_window(13, 0, 180, weekday=0),), scope="task", scope_id="t"),
    )
    study = _decl(
        DayScopedOp.REPLACE_NAMED_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(8, 0, 60, weekday=0),),
        role="may",
        target_rule_id="study",
        output_rule_id="study-mon",
        declaration_id="study-mon",
    )
    personal = _decl(
        DayScopedOp.ADD_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(18, 0, 60, weekday=0),),
        role="may",
        output_rule_id="personal",
        declaration_id="personal",
    )
    folded = _resolve(_layer("task", "t", may=standing), day_scoped=(study, personal))
    assert _eligible(MONDAY, folded) == [
        (datetime(2026, 10, 12, 8, 0, tzinfo=UTC), datetime(2026, 10, 12, 9, 0, tzinfo=UTC)),
        (datetime(2026, 10, 12, 13, 0, tzinfo=UTC), datetime(2026, 10, 12, 16, 0, tzinfo=UTC)),
        (datetime(2026, 10, 12, 18, 0, tzinfo=UTC), datetime(2026, 10, 12, 19, 0, tzinfo=UTC)),
    ]


def test_scoped_clear_with_local_removed_inherits_current_parent() -> None:
    parent = _layer(
        "project",
        "p",
        may=(
            rule(
                "ancestor",
                RuleRole.MAY,
                (_window(15, 0, 60, weekday=1),),
                scope="project",
                scope_id="p",
            ),
        ),
    )
    clear = _decl(
        DayScopedOp.CLEAR_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        scope="task",
        scope_id="t",
    )
    folded = _resolve(parent, day_scoped=(clear,))
    assert _eligible(TUESDAY, folded) == [
        (datetime(2026, 10, 13, 15, 0, tzinfo=UTC), datetime(2026, 10, 13, 16, 0, tzinfo=UTC))
    ]


def test_dst_gap_and_fold_reuse_approved_instants() -> None:
    spring_change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=SPRING),
        windows=(make_window(SPRING.weekday(), time(1, 30), 120),),
    )
    spring = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("sun", RuleRole.MAY, (_window(9, 0, 60, weekday=SPRING.weekday()),), scope="task", scope_id="t"),),
        ),
        day_scoped=(spring_change,),
    )
    spring_spans = composition_search_windows(SPRING, LA, spring, [])
    assert spring_spans
    assert spring_spans[0][0] == datetime(2026, 3, 8, 9, 30, tzinfo=UTC)
    assert spring_spans[0][1] == datetime(2026, 3, 8, 10, 30, tzinfo=UTC)
    assert spring_spans[0][1] - spring_spans[0][0] == timedelta(hours=1)

    skipped = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=SPRING),
        windows=(make_window(SPRING.weekday(), time(2, 15), 20),),
        declaration_id="gap-skip",
    )
    skipped_comp = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("sun", RuleRole.MAY, (_window(9, 0, 60, weekday=SPRING.weekday()),), scope="task", scope_id="t"),),
        ),
        day_scoped=(skipped,),
    )
    assert composition_search_windows(SPRING, LA, skipped_comp, []) == []

    fold_change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=FOLD),
        windows=(make_window(FOLD.weekday(), time(1, 15), 30),),
        declaration_id="fold",
    )
    folded = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("sun", RuleRole.MAY, (_window(9, 0, 60, weekday=FOLD.weekday()),), scope="task", scope_id="t"),),
        ),
        day_scoped=(fold_change,),
    )
    fold_spans = composition_search_windows(FOLD, LA, folded, [])
    assert fold_spans[0][0] == datetime(2026, 11, 1, 8, 15, tzinfo=UTC)
    assert fold_spans[0][1] == datetime(2026, 11, 1, 8, 45, tzinfo=UTC)


def test_r3_one_time_instant_is_not_reread_as_a_civil_label() -> None:
    start = datetime(2026, 11, 1, 8, 15, tzinfo=UTC)
    end = datetime(2026, 11, 1, 8, 45, tzinfo=UTC)
    change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=FOLD),
        windows=(_window(9, 0, 60, weekday=FOLD.weekday()),),
        one_time_start=start,
        one_time_end=end,
    )
    assert declaration_problem(change, LA) is None
    assert declaration_problem(change, ZoneInfo("America/New_York")) is None
    folded = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("sun", RuleRole.MAY, (_window(9, 0, 60, weekday=FOLD.weekday()),), scope="task", scope_id="t"),),
        ),
        day_scoped=(change,),
    )
    for tz in (LA, ZoneInfo("America/New_York"), TZ):
        spans = composition_search_windows(FOLD, tz, folded, [])
        assert spans
        assert spans[0][0] == start
        assert spans[0][1] == end
    assert change.one_time_start == start
    assert change.one_time_end == end
    assert change.windows[0].start_time == time(9, 0)


def test_contradictory_instant_ends_are_not_applied() -> None:
    bad = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(make_window(0, time(22, 0), 240),),
        expires_at=datetime(2026, 10, 13, 1, 0, tzinfo=UTC),
        one_time_end=datetime(2026, 10, 13, 2, 0, tzinfo=UTC),
    )
    assert declaration_problem(bad, TZ) == "contradictory_instant_ends"
    standing = (
        rule("day", RuleRole.MAY, (_window(9, 0, 180, weekday=0),), scope="task", scope_id="t"),
    )
    folded = _resolve(_layer("task", "t", may=standing), day_scoped=(bad,))
    assert [start.hour for start, _end in _eligible(MONDAY, folded)] == [9]
    assert bad.expires_at == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    assert bad.one_time_end == datetime(2026, 10, 13, 2, 0, tzinfo=UTC)


def test_a14c_bound_exhausted_is_named() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("hour", RuleRole.MAY, (_window(9, 0, 60, weekday=1),), scope="task", scope_id="t"),),
            prefer=(rule("hour", RuleRole.PREFER, (_window(9, 0, 60, weekday=1),), scope="task", scope_id="t"),),
        )
    )
    result = _place(
        composed,
        _task(180),
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert result.blocks_created == 1
    assert result.remaining_minutes == 120
    assert result.unmet_preference["decision"] == "bound_exhausted"
    assert result.unmet_preference["bound_exhausted"] is True
    text = format_summary_text([ReasonFact(REASON_UNMET_PREFERENCE, result.unmet_preference)])
    assert "horizon" in text or "bound" in text


def test_a14c_empty_must_stays_a_hard_failure() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 180, weekday=1),), scope="task", scope_id="t"),),
            must=(rule("closed", RuleRole.MUST, (), scope="task", scope_id="t"),),
            prefer=(rule("mid", RuleRole.PREFER, (_window(10, 0, 60, weekday=1),), scope="task", scope_id="t"),),
        )
    )
    assert composed.must_blocks_all is True
    result = _place(
        composed,
        _task(60, priority=TaskPriority.p1, deadline=datetime(2026, 10, 13, 17, 0, tzinfo=UTC)),
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert result.blocks_created == 0
    assert result.unmet_preference["decision"] == "hard_infeasibility"
    assert result.unmet_preference["hard_constraints_protected"] is True
    text = format_summary_text([ReasonFact(REASON_UNMET_PREFERENCE, result.unmet_preference)])
    assert "Hard requirements" in text or "pins" in text


def test_fingerprint_compares_day_scoped_and_priority_ups() -> None:
    assert "s2-v4b-day-scoped-ranking-protection" in SCHEDULING_ACTIVATIONS
    assert "s2-v4-may-must-prefer-composition" in SCHEDULING_ACTIVATIONS
    assert STALE_PRIORITY_UPS in COMPARED_STALE_CATEGORIES
    assert DEFERRED_STALE_CATEGORIES == ()

    change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(_window(15, 0, 60, weekday=0),),
        expires_at=datetime(2026, 10, 13, 1, 0, tzinfo=UTC),
        replaces_id="prior",
        addition_survives=True,
    )
    composed = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 60, weekday=0),), scope="task", scope_id="t"),),
        ),
        day_scoped=(change,),
    )
    fingerprint = composition_fingerprint(composed)
    row = fingerprint["day_scoped"][0]
    assert row["selector"]["on_date"] == "2026-10-12"
    assert row["expires_at"] == "2026-10-13T01:00:00+00:00"
    assert row["replaces_id"] == "prior"
    assert row["addition_survives"] is True

    weights = {"Wp": 0.35, "Wu": 0.40, "Wd": 0.15, "We": 0.10, "k": 0.5}
    stored = _snap(fingerprint, priority="p3", ups_weights=weights)
    assert "s2-v4b-day-scoped-ranking-protection" in stored["scheduling_activation"]["ids"]
    assert "day_scoped" not in stored["availability"]

    later = dict(fingerprint)
    later_rows = [dict(row)]
    later_rows[0]["expires_at"] = "2026-10-13T02:00:00+00:00"
    later["day_scoped"] = later_rows
    moved = _snap(later, priority="p3", ups_weights=weights)
    assert diff_stale_categories(stored, moved) == [STALE_COMPOSITION]

    reranked = _snap(fingerprint, priority="p1", ups_weights={**weights, "Wp": 0.5})
    assert diff_stale_categories(stored, reranked) == [STALE_PRIORITY_UPS]


def _snap(composition, *, priority: str, ups_weights: dict) -> dict:
    return assemble_snapshot(
        estimated_duration_minutes=60,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
        composition=composition,
        priority=priority,
        ups_weights=ups_weights,
    )


def replace(decl: DayScopedDeclaration, **kwargs) -> DayScopedDeclaration:
    from dataclasses import replace as dc_replace

    return dc_replace(decl, **kwargs)
