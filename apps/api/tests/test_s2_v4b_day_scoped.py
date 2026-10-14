"""S2-V4b day-scoped resolution, A14c counterfactual, fingerprint, and activation token.

No database. Household activation is not invoked.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import Task, UserSettings
from app.models.enums import TaskPriority
from app.scheduler.busy_map import BusyInterval
from app.scheduler.composition import (
    RANK_ELIGIBLE,
    AssignmentFamily,
    CompositionInput,
    DeferredForm,
    MayMode,
    RuleRole,
    composition_fingerprint,
    composition_input_from_mapping,
    composition_search_windows,
    make_window,
    resolve_effective_composition,
    rule,
)
from app.scheduler.day_scoped import (
    CivilSelector,
    DayScopedDeclaration,
    DayScopedOp,
    LegacyBand,
    LegacyMapView,
    LegacyOverride,
    SelectorKind,
    declaration_problem,
)
from app.scheduler.input_fingerprint import SCHEDULING_ACTIVATIONS, assemble_snapshot
from app.scheduler.placement import place_task
from app.scheduler.proposal_revalidation import lifetime_crossed, proposal_lifetime_stale
from app.scheduler.ranking_protection import (
    DECISION_HIGHER_RANKED,
    DECISION_PREFER,
    RANK_MODE_ELIGIBLE,
    RANK_MODE_PREFER,
    HigherRankedTask,
    choose_rank_mode,
    simulate_ranked_completion,
)
from app.scheduler.reasons import REASON_UNMET_PREFERENCE, ReasonFact, format_summary_text
from app.services.day_scoped_ranking_cutover_activation import (
    ACTIVATION_TOKEN,
    day_scoped_ranking_activation_revision,
)
from app.scheduler.composition import ScopeLayer

UTC = timezone.utc
TZ = ZoneInfo("UTC")
LA = ZoneInfo("America/Los_Angeles")
MONDAY = date(2026, 10, 12)
TUESDAY = date(2026, 10, 13)
WEDNESDAY = date(2026, 10, 14)


def _window(hour: int, minute: int, duration: int, weekday: int = 1):
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
    composed = resolve_effective_composition(
        CompositionInput(family=AssignmentFamily.NEW_RULE, layers=layers, day_scoped=tuple(day_scoped))
    )
    return composed


def _decl(op, selector, **kwargs):
    return DayScopedDeclaration(
        declaration_id=kwargs.pop("declaration_id", op.value),
        operation=op,
        scope=kwargs.pop("scope", "task"),
        scope_id=kwargs.pop("scope_id", "t"),
        selector=selector,
        **kwargs,
    )


def _task(minutes: int, *, min_block: int | None = None, max_block: int | None = None, priority=TaskPriority.p4, deadline=None) -> Task:
    block = minutes if min_block is None else min_block
    cap = minutes if max_block is None else max_block
    return Task(
        id=uuid4(),
        owner_id=uuid4(),
        title="v4b",
        estimated_duration_minutes=minutes,
        min_block_duration_minutes=block,
        max_block_duration_minutes=cap,
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


def _place(composition, task, *, now, end, busy=None, higher_ranked=()):
    result, _busy = place_task(
        None,  # type: ignore[arg-type]
        task=task,
        owner_id=task.owner_id,
        settings=_settings(),
        remaining_minutes=task.estimated_duration_minutes,
        busy=list(busy or []),
        horizon_start=now,
        horizon_end=end,
        preferred_windows={},
        now_utc=now,
        finalize_status=False,
        persist_blocks=False,
        working_windows=[],
        general_windows=[],
        composition=composition,
        higher_ranked=higher_ranked,
    )
    return result


def test_activation_token_is_appended_and_bump_is_not_run() -> None:
    assert ACTIVATION_TOKEN == "s2-v4b-day-scoped-ranking-protection"
    assert SCHEDULING_ACTIVATIONS[-1] == ACTIVATION_TOKEN
    assert "s2-v4-may-must-prefer-composition" in SCHEDULING_ACTIVATIONS
    assert day_scoped_ranking_activation_revision(3) == 4


def test_change_range_keeps_overnight_tail_until_explicit_expiry() -> None:
    standing = _resolve(
        _layer(
            "task",
            "t",
            may=(
                rule(
                    "night",
                    RuleRole.MAY,
                    (make_window(0, time(22, 0), 240), _window(9, 0, 180, weekday=1)),
                    scope="task",
                    scope_id="t",
                ),
            ),
        )
    )
    change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.DATE_RANGE, range_start=MONDAY, range_end=MONDAY),
        windows=(make_window(0, time(22, 0), 240),),
    )
    folded = _resolve(
        _layer(
            "task",
            "t",
            may=(
                rule(
                    "night",
                    RuleRole.MAY,
                    (make_window(0, time(22, 0), 240), _window(9, 0, 180, weekday=1)),
                    scope="task",
                    scope_id="t",
                ),
            ),
        ),
        day_scoped=(change,),
    )
    monday = composition_search_windows(MONDAY, TZ, folded, [])
    assert (datetime(2026, 10, 12, 22, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC), RANK_ELIGIBLE) in [
        (item[0], item[1], item[2]) for item in monday
    ]
    tuesday = composition_search_windows(TUESDAY, TZ, folded, [])
    assert any(item[0] == datetime(2026, 10, 13, 0, 0, tzinfo=UTC) and item[1] == datetime(2026, 10, 13, 2, 0, tzinfo=UTC) for item in tuesday)
    assert any(item[0] == datetime(2026, 10, 13, 9, 0, tzinfo=UTC) for item in tuesday)
    clipped = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.DATE_RANGE, range_start=MONDAY, range_end=MONDAY),
        windows=(make_window(0, time(22, 0), 240),),
        expires_at=datetime(2026, 10, 13, 1, 0, tzinfo=UTC),
        declaration_id="change-cut",
    )
    cut = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("night", RuleRole.MAY, (make_window(0, time(22, 0), 240),), scope="task", scope_id="t"),),
        ),
        day_scoped=(clipped,),
    )
    cut_monday = composition_search_windows(MONDAY, TZ, cut, [])
    assert cut_monday
    assert max(item[1] for item in cut_monday) == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    assert clipped.expires_at == datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    untouched = composition_search_windows(WEDNESDAY, TZ, folded, [])
    plain = composition_search_windows(WEDNESDAY, TZ, standing, [])
    assert untouched == plain


def test_only_allow_lifetime_is_not_the_change_tail() -> None:
    overnight = (
        rule("night", RuleRole.MAY, (make_window(0, time(22, 0), 240),), scope="task", scope_id="t"),
    )
    weekday_only = _decl(
        DayScopedOp.ONLY_ALLOW,
        CivilSelector(SelectorKind.WEEKDAY, weekdays=(0,)),
        windows=(make_window(0, time(22, 0), 120),),
    )
    exclusive = _resolve(_layer("task", "t", may=overnight), day_scoped=(weekday_only,))
    monday = composition_search_windows(MONDAY, TZ, exclusive, [])
    assert monday
    assert max(item[1] for item in monday) == datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
    assert composition_search_windows(TUESDAY, TZ, exclusive, []) == []
    ranged = _decl(
        DayScopedOp.ONLY_ALLOW,
        CivilSelector(SelectorKind.DATE_RANGE, range_start=MONDAY, range_end=MONDAY),
        windows=(make_window(0, time(9, 0), 480),),
        declaration_id="only-range",
    )
    ranged_comp = _resolve(_layer("task", "t", may=overnight), day_scoped=(ranged,))
    ranged_monday = composition_search_windows(MONDAY, TZ, ranged_comp, [])
    assert any(item[0] == datetime(2026, 10, 13, 0, 0, tzinfo=UTC) and item[1] == datetime(2026, 10, 13, 2, 0, tzinfo=UTC) for item in ranged_monday)
    assert not any(item[0] == datetime(2026, 10, 12, 22, 0, tzinfo=UTC) for item in ranged_monday)


def test_one_date_does_not_leak_and_empty_change_does_not_borrow_general() -> None:
    may = (rule("day", RuleRole.MAY, (_window(9, 0, 180, weekday=0), _window(9, 0, 180, weekday=1)), scope="task", scope_id="t"),)
    one = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(make_window(0, time(15, 0), 60),),
    )
    folded = _resolve(_layer("task", "t", may=may), day_scoped=(one,))
    monday = composition_search_windows(MONDAY, TZ, folded, [])
    assert [item[0].hour for item in monday] == [15]
    next_monday = composition_search_windows(MONDAY + timedelta(days=7), TZ, folded, [])
    assert any(item[0].hour == 9 for item in next_monday)
    empty = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        empty_set=True,
        declaration_id="empty",
    )
    closed = _resolve(_layer("task", "t", may=may), day_scoped=(empty,))
    assert composition_search_windows(TUESDAY, TZ, closed, []) == []
    assert composition_search_windows(MONDAY, TZ, closed, [])


def test_scoped_clear_restores_current_local_after_expiry() -> None:
    parent = _layer(
        "project",
        "p",
        may=(
            rule(
                "a",
                RuleRole.MAY,
                (_window(9, 0, 180, weekday=1), _window(9, 0, 180, weekday=2)),
                scope="project",
                scope_id="p",
            ),
        ),
    )
    local = _layer(
        "task",
        "t",
        may=(
            rule(
                "b2",
                RuleRole.MAY,
                (_window(15, 0, 60, weekday=1), _window(15, 0, 60, weekday=2)),
                scope="task",
                scope_id="t",
            ),
        ),
    )
    clear = _decl(
        DayScopedOp.CLEAR_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        scope="task",
        scope_id="t",
    )
    folded = _resolve(parent, local, day_scoped=(clear,))
    tuesday = composition_search_windows(TUESDAY, TZ, folded, [])
    assert [(item[0].hour, item[1].hour) for item in tuesday] == [(9, 12)]
    wednesday = composition_search_windows(WEDNESDAY, TZ, folded, [])
    hours = sorted((item[0].hour, item[1].hour) for item in wednesday)
    assert (9, 12) in hours
    assert (15, 16) in hours


def test_preserve_instant_expiry_is_not_reread_as_a_civil_label() -> None:
    expires = datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=MONDAY),
        windows=(make_window(0, time(22, 0), 240),),
        expires_at=expires,
    )
    assert declaration_problem(change, TZ) is None
    assert declaration_problem(change, LA) is None
    assert change.expires_at == expires
    folded = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("night", RuleRole.MAY, (make_window(0, time(22, 0), 240),), scope="task", scope_id="t"),),
        ),
        day_scoped=(change,),
    )
    utc_end = max(item[1] for item in composition_search_windows(MONDAY, TZ, folded, []))
    assert utc_end == expires
    la_clips = composition_search_windows(MONDAY, LA, folded, [])
    assert all(item[1] <= expires for item in la_clips)
    assert change.expires_at == expires
    assert change.windows[0].start_time == time(22, 0)


def test_authorized_op_is_applied_and_context_stays_deferred() -> None:
    payload = {
        "family": "new_rule",
        "layers": [
            {
                "scope": "task",
                "scope_id": "t",
                "may_mode": "present",
                "may_rules": [
                    {
                        "rule_id": "am",
                        "role": "may",
                        "windows": [{"weekday": 0, "start_time": "09:00:00", "duration_minutes": 180}],
                    }
                ],
                "exceptions": [
                    {
                        "operation": "day.change_selected",
                        "on_date": "2026-10-12",
                        "windows": [{"weekday": 0, "start_time": "15:00:00", "duration_minutes": 60}],
                    },
                    {"operation": "add", "context_id": "office"},
                ],
            }
        ],
    }
    composed = resolve_effective_composition(composition_input_from_mapping(payload))
    assert [item.form for item in composed.deferred_rejected] == [DeferredForm.CONTEXT]
    monday = composition_search_windows(MONDAY, TZ, composed, [])
    assert [item[0].hour for item in monday] == [15]
    fingerprint = composition_fingerprint(composed)
    assert "day_scoped" in fingerprint
    assert fingerprint["day_scoped"][0]["expires_at"] is None
    assert fingerprint["day_scoped"][0]["selector"]["on_date"] == "2026-10-12"
    snap = assemble_snapshot(
        estimated_duration_minutes=30,
        min_block_duration_minutes=15,
        max_block_duration_minutes=120,
        deadline_at=None,
        schedule_style="standalone",
        time_window_id=None,
        strict_mode=None,
        bands=[],
        blocking_task_ids=[],
        composition=fingerprint,
        priority="p3",
        ups_weights={"Wp": 0.35, "Wu": 0.40, "Wd": 0.15, "We": 0.10, "k": 0.5},
    )
    assert "day_scoped" not in snap["availability"]
    assert snap["priority_ups"]["priority"] == "p3"
    assert snap["composition"]["day_scoped"][0]["operation"] == "day.change_selected"


def test_a14c_deadline_fallback_beats_a_prefer_chunk() -> None:
    # Prefer sits in the middle of the only pre-deadline span. A 90-minute
    # chunk there leaves two gaps shorter than min. The earlier packing fits
    # two chunks before the deadline. Min/max stay 90.
    composed = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("span", RuleRole.MAY, (_window(9, 0, 180),), scope="task", scope_id="t"),),
            prefer=(rule("mid", RuleRole.PREFER, (_window(9, 30, 90),), scope="task", scope_id="t"),),
        )
    )
    task = _task(180, min_block=90, max_block=90, deadline=datetime(2026, 10, 13, 12, 0, tzinfo=UTC))
    result = _place(
        composed,
        task,
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert result.blocks_created == 1
    assert result.proposed_blocks[0].start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert result.proposed_blocks[0].end_time == datetime(2026, 10, 13, 10, 30, tzinfo=UTC)
    assert result.unmet_preference["decision"] == "deadline_fallback"
    text = format_summary_text([ReasonFact(REASON_UNMET_PREFERENCE, result.unmet_preference)])
    assert "deadline" in text
    assert "did not create hours" in text


def test_a14c_higher_ranked_slot_is_kept_across_days() -> None:
    low = _resolve(
        _layer(
            "task",
            "low",
            may=(
                rule(
                    "either",
                    RuleRole.MAY,
                    (_window(9, 0, 60, weekday=1), _window(15, 0, 60, weekday=2)),
                    scope="task",
                    scope_id="low",
                ),
            ),
            prefer=(rule("wed", RuleRole.PREFER, (_window(15, 0, 60, weekday=2),), scope="task", scope_id="low"),),
        )
    )
    high = _resolve(
        _layer(
            "task",
            "high",
            may=(rule("tue", RuleRole.MAY, (_window(13, 0, 60, weekday=1),), scope="task", scope_id="high"),),
        )
    )
    subject = _task(60, priority=TaskPriority.p4)
    peer = _task(60, priority=TaskPriority.p1)
    claim = HigherRankedTask(
        task=peer,
        remaining_minutes=60,
        composition=high,
        blocked_by_subject=True,
    )
    result = _place(
        low,
        subject,
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 14, 18, 0, tzinfo=UTC),
        higher_ranked=(claim,),
    )
    assert result.proposed_blocks[0].start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert result.unmet_preference["decision"] == "higher_ranked_competition"
    text = format_summary_text([ReasonFact(REASON_UNMET_PREFERENCE, result.unmet_preference)])
    assert "higher-ranked" in text


def test_a14c_prefer_wins_when_both_meet_the_deadline() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may=(
                rule(
                    "either",
                    RuleRole.MAY,
                    (_window(9, 0, 60, weekday=1), _window(15, 0, 60, weekday=2)),
                    scope="task",
                    scope_id="t",
                ),
            ),
            prefer=(rule("wed", RuleRole.PREFER, (_window(15, 0, 60, weekday=2),), scope="task", scope_id="t"),),
        )
    )
    task = _task(60, deadline=datetime(2026, 10, 16, 17, 0, tzinfo=UTC))
    result = _place(
        composed,
        task,
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 14, 18, 0, tzinfo=UTC),
    )
    assert result.proposed_blocks[0].start_time == datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
    assert result.unmet_preference is None


def test_a14c_pins_stay_protected() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 180),), scope="task", scope_id="t"),),
            prefer=(rule("mid", RuleRole.PREFER, (_window(10, 0, 60),), scope="task", scope_id="t"),),
        )
    )
    pin = BusyInterval(
        start=datetime(2026, 10, 13, 9, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        source="pinned",
    )
    result = _place(
        composed,
        _task(60),
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
        busy=[pin],
    )
    assert result.blocks_created == 0
    assert result.unmet_preference["decision"] == "hard_infeasibility"
    assert result.unmet_preference["hard_constraints_protected"] is True
    text = format_summary_text([ReasonFact(REASON_UNMET_PREFERENCE, result.unmet_preference)])
    assert "pins" in text or "Hard requirements" in text
    assert pin.start == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert pin.end == datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def test_expiry_between_preview_and_apply_rejects_without_a_new_write() -> None:
    change = _decl(
        DayScopedOp.CHANGE_SELECTED,
        CivilSelector(SelectorKind.DATE_RANGE, range_start=MONDAY, range_end=MONDAY),
        expires_at=datetime(2026, 10, 13, 1, 0, tzinfo=UTC),
    )
    preview_at = datetime(2026, 10, 12, 18, 0, tzinfo=UTC)
    apply_at = datetime(2026, 10, 13, 1, 30, tzinfo=UTC)
    assert lifetime_crossed((change,), preview_at=preview_at, apply_at=apply_at, tz=TZ)
    assert not lifetime_crossed(
        (change,),
        preview_at=preview_at,
        apply_at=datetime(2026, 10, 12, 20, 0, tzinfo=UTC),
        tz=TZ,
    )
    composed = _resolve(
        _layer("task", "t", may=(rule("day", RuleRole.MAY, (_window(9, 0, 60, weekday=0),), scope="task", scope_id="t"),)),
        day_scoped=(change,),
    )
    task_id = uuid4()

    class _Comp:
        day_scoped = (change,)

    stale = proposal_lifetime_stale(
        composition_by_task={task_id: composed},
        proposal={
            "proposed_blocks": [
                {
                    "task_id": str(task_id),
                    "start_time": "2026-10-12T22:00:00+00:00",
                    "end_time": "2026-10-13T01:00:00+00:00",
                }
            ]
        },
        preview_at=preview_at,
        apply_at=apply_at,
        tz=TZ,
    )
    assert stale is True
    assert _Comp is not None


def _hours(clips) -> list[tuple[int, int]]:
    return [(item[0].hour, item[0].minute, item[1].hour, item[1].minute) for item in clips if item[2] == RANK_ELIGIBLE]


def test_scoped_family_inserts_explicit_empty_when_nothing_is_local() -> None:
    closed = _layer("task", "t", may_mode=MayMode.EXPLICIT_EMPTY)
    decl = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="new_rule",
        replacement_layer=closed,
        declaration_id="empty-family",
    )
    folded = _resolve(day_scoped=(decl,))
    general = (_window(15, 0, 60),)
    assert composition_search_windows(TUESDAY, TZ, folded, general) == []
    later = composition_search_windows(TUESDAY + timedelta(days=7), TZ, folded, general)
    assert (15, 0, 16, 0) in _hours(later)


def test_scoped_family_none_suppresses_local_and_uses_general() -> None:
    local = _layer(
        "task",
        "t",
        may=(rule("am", RuleRole.MAY, (_window(9, 0, 60),), scope="task", scope_id="t"),),
    )
    decl = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="none",
        declaration_id="to-none",
    )
    folded = _resolve(local, day_scoped=(decl,))
    general = (_window(15, 0, 60),)
    assert (15, 0, 16, 0) in _hours(composition_search_windows(TUESDAY, TZ, folded, general))
    assert (9, 0, 10, 0) in _hours(
        composition_search_windows(TUESDAY + timedelta(days=7), TZ, folded, general)
    )
    expired = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="none",
        expires_at=datetime(2026, 10, 13, 0, 0, tzinfo=UTC),
        declaration_id="expired-none",
    )
    restored = _resolve(local, day_scoped=(expired,))
    assert (9, 0, 10, 0) in _hours(composition_search_windows(TUESDAY, TZ, restored, general))


def test_scoped_family_inserts_over_inherited_assignment() -> None:
    parent = _layer(
        "project",
        "p",
        may=(rule("parent", RuleRole.MAY, (_window(9, 0, 180),), scope="project", scope_id="p"),),
    )
    child = _layer(
        "task",
        "t",
        may=(rule("child", RuleRole.MAY, (_window(15, 0, 60),), scope="task", scope_id="t"),),
    )
    decl = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="new_rule",
        replacement_layer=child,
        declaration_id="insert-task",
    )
    folded = _resolve(parent, day_scoped=(decl,))
    tuesday = _hours(composition_search_windows(TUESDAY, TZ, folded, []))
    assert (15, 0, 16, 0) in tuesday
    assert (9, 0, 12, 0) in _hours(
        composition_search_windows(TUESDAY + timedelta(days=7), TZ, folded, [])
    )
    closed = _layer("task", "t", may_mode=MayMode.EXPLICIT_EMPTY)
    empty = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="new_rule",
        replacement_layer=closed,
        declaration_id="close-inherited",
    )
    shut = _resolve(parent, day_scoped=(empty,))
    assert composition_search_windows(TUESDAY, TZ, shut, []) == []
    assert (9, 0, 12, 0) in _hours(
        composition_search_windows(TUESDAY + timedelta(days=7), TZ, shut, [])
    )


def _legacy_view(*rows: tuple[str, time, time]) -> LegacyMapView:
    return LegacyMapView(
        map_id="map-expiry",
        strict_mode=True,
        bands=tuple(
            LegacyBand(
                tier=tier,
                start_time=start,
                end_time=end,
                days_of_week=127,
                sort_order=index,
            )
            for index, (tier, start, end) in enumerate(rows)
        ),
    )


def _crosses(clips, instant: datetime) -> bool:
    return any(item[0] < instant < item[1] for item in clips)


def test_layer_ops_midday_expiry_restore_standing_without_a_straddle() -> None:
    """Explicit 13:00 expiry is not an end-of-day approximation."""
    expiry = datetime(2026, 10, 13, 13, 0, tzinfo=UTC)
    standing = _layer(
        "task",
        "t",
        may=(rule("pm", RuleRole.MAY, (_window(16, 0, 60),), scope="task", scope_id="t"),),
    )
    late_map = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="legacy",
        legacy_map=_legacy_view(("green", time(14, 0), time(15, 0))),
        expires_at=expiry,
        declaration_id="late-map",
    )
    late = _resolve(standing, day_scoped=(late_map,))
    tuesday = composition_search_windows(TUESDAY, TZ, late, [])
    assert not _crosses(tuesday, expiry)
    assert not any(item[0] == datetime(2026, 10, 13, 14, 0, tzinfo=UTC) for item in tuesday)
    assert any(item[0] == datetime(2026, 10, 13, 16, 0, tzinfo=UTC) and item[1] == datetime(2026, 10, 13, 17, 0, tzinfo=UTC) for item in tuesday)
    wholly_after = _place(
        late,
        _task(60),
        now=expiry,
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert wholly_after.blocks_created == 1
    assert wholly_after.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    wednesday = composition_search_windows(WEDNESDAY, TZ, late, [])
    assert not any(item[0].hour == 14 for item in wednesday)
    nxt = composition_search_windows(TUESDAY + timedelta(days=7), TZ, late, [])
    assert any(item[0].hour == 16 for item in nxt)
    assert not any(item[0].hour == 14 for item in nxt)

    crossing_map = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="legacy",
        legacy_map=_legacy_view(
            ("green", time(10, 0), time(11, 0)),
            ("green", time(14, 0), time(15, 0)),
        ),
        expires_at=expiry,
        declaration_id="cross-map",
    )
    crossing = _resolve(standing, day_scoped=(crossing_map,))
    cross_windows = composition_search_windows(TUESDAY, TZ, crossing, [])
    assert not _crosses(cross_windows, expiry)
    assert any(item[0] == datetime(2026, 10, 13, 10, 0, tzinfo=UTC) and item[1] == datetime(2026, 10, 13, 11, 0, tzinfo=UTC) for item in cross_windows)
    assert not any(item[0] == datetime(2026, 10, 13, 14, 0, tzinfo=UTC) for item in cross_windows)
    morning = _place(
        crossing,
        _task(60),
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert morning.proposed_blocks[0].start_time == datetime(2026, 10, 13, 10, 0, tzinfo=UTC)
    after_morning = _place(
        crossing,
        _task(60),
        now=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    assert after_morning.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)

    straddling = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="legacy",
        legacy_map=_legacy_view(("green", time(12, 30), time(14, 30))),
        expires_at=expiry,
        declaration_id="straddle-map",
    )
    straddled = _resolve(standing, day_scoped=(straddling,))
    straddle_windows = composition_search_windows(TUESDAY, TZ, straddled, [])
    assert not _crosses(straddle_windows, expiry)
    assert any(item[1] == expiry for item in straddle_windows)
    placed = _place(
        straddled,
        _task(60),
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
    )
    block = placed.proposed_blocks[0]
    assert block.start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    assert not (block.start_time < expiry < block.end_time)

    replaced = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="new_rule",
        replacement_layer=_layer(
            "task",
            "t",
            may=(rule("early", RuleRole.MAY, (_window(14, 0, 60),), scope="task", scope_id="t"),),
        ),
        expires_at=expiry,
        declaration_id="new-rule-cut",
    )
    new_rule = _resolve(standing, day_scoped=(replaced,))
    new_windows = composition_search_windows(TUESDAY, TZ, new_rule, [])
    assert not _crosses(new_windows, expiry)
    assert _hours(new_windows) == [(16, 0, 17, 0)]

    cleared = _decl(
        DayScopedOp.CLEAR_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        expires_at=expiry,
        declaration_id="clear-cut",
    )
    cleared_comp = _resolve(standing, day_scoped=(cleared,))
    general = (_window(10, 0, 60), _window(14, 0, 60))
    clear_windows = composition_search_windows(TUESDAY, TZ, cleared_comp, general)
    assert not _crosses(clear_windows, expiry)
    assert (10, 0, 11, 0) in _hours(clear_windows)
    assert (14, 0, 15, 0) not in _hours(clear_windows)
    assert (16, 0, 17, 0) in _hours(clear_windows)

    prior = _layer(
        "task",
        "t",
        may=(rule("old", RuleRole.MAY, (_window(14, 0, 60),), scope="task", scope_id="t"),),
    )
    reverted = _decl(
        DayScopedOp.REVERT_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        prior_layer=prior,
        expires_at=expiry,
        declaration_id="revert-cut",
    )
    revert_windows = composition_search_windows(
        TUESDAY, TZ, _resolve(standing, day_scoped=(reverted,)), []
    )
    assert not _crosses(revert_windows, expiry)
    assert _hours(revert_windows) == [(16, 0, 17, 0)]


def test_scoped_family_legacy_replaces_local_new_rule_hours() -> None:
    local = _layer(
        "task",
        "t",
        may=(rule("am", RuleRole.MAY, (_window(9, 0, 60),), scope="task", scope_id="t"),),
    )
    legacy = _layer(
        "task",
        "t",
        may=(rule("map", RuleRole.MAY, (_window(14, 0, 60),), scope="task", scope_id="t"),),
    )
    decl = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="legacy",
        replacement_layer=legacy,
        declaration_id="to-legacy",
    )
    folded = _resolve(local, day_scoped=(decl,))
    tuesday = _hours(composition_search_windows(TUESDAY, TZ, folded, []))
    assert (14, 0, 15, 0) in tuesday
    assert (9, 0, 10, 0) not in tuesday
    assert (9, 0, 10, 0) in _hours(
        composition_search_windows(TUESDAY + timedelta(days=7), TZ, folded, [])
    )


def test_a14c_multi_chunk_counterfactual_finishes_inside_one_window() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may=(rule("span", RuleRole.MAY, (_window(9, 0, 180),), scope="task", scope_id="t"),),
            prefer=(rule("late", RuleRole.PREFER, (_window(11, 0, 60),), scope="task", scope_id="t"),),
        )
    )
    task = _task(120, min_block=60, max_block=60, deadline=datetime(2026, 10, 13, 12, 0, tzinfo=UTC))
    now = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
    end = datetime(2026, 10, 13, 18, 0, tzinfo=UTC)
    settings = _settings()

    def _done(mode: str):
        result, _busy = simulate_ranked_completion(
            db=None,
            task=task,
            owner_id=task.owner_id,
            settings=settings,
            remaining_minutes=120,
            busy=[],
            horizon_start=now,
            horizon_end=end,
            preferred_windows={},
            now_utc=now,
            preferred_window_id=None,
            project_daily_usage={},
            daily_cap=None,
            prerequisite_not_before=None,
            time_map_overrides_by_map={},
            working_windows=[],
            general_windows=[],
            composition=composed,
            mode=mode,
        )
        return result

    prefer = _done(RANK_MODE_PREFER)
    fallback = _done(RANK_MODE_ELIGIBLE)
    assert prefer.blocks_created == 2
    assert prefer.remaining_minutes == 0
    assert fallback.blocks_created == 2
    assert fallback.remaining_minutes == 0
    assert prefer.last_block_end is not None and prefer.last_block_end <= task.deadline_at
    choice = choose_rank_mode(
        db=None,
        task=task,
        owner_id=task.owner_id,
        settings=settings,
        remaining_minutes=120,
        busy=[],
        horizon_start=now,
        horizon_end=end,
        preferred_windows={},
        now_utc=now,
        preferred_window_id=None,
        project_daily_usage={},
        daily_cap=None,
        prerequisite_not_before=None,
        time_map_overrides_by_map={},
        working_windows=[],
        general_windows=[],
        composition=composed,
    )
    assert choice.decision == DECISION_PREFER
    assert choice.bound_exhausted is False
    placed = _place(composed, task, now=now, end=end)
    assert placed.preference_decision["decision"] == DECISION_PREFER
    assert placed.unmet_preference is None or placed.unmet_preference.get("bound_exhausted") is not True


def test_a14c_multi_chunk_higher_ranked_dependent() -> None:
    subject_comp = _resolve(
        _layer(
            "task",
            "low",
            may=(
                rule(
                    "either",
                    RuleRole.MAY,
                    (_window(9, 0, 60), _window(12, 0, 60)),
                    scope="task",
                    scope_id="low",
                ),
            ),
            prefer=(rule("noon", RuleRole.PREFER, (_window(12, 0, 60),), scope="task", scope_id="low"),),
        )
    )
    peer_comp = _resolve(
        _layer(
            "task",
            "high",
            may=(rule("span", RuleRole.MAY, (_window(12, 0, 120),), scope="task", scope_id="high"),),
        )
    )
    subject = _task(60, min_block=60, max_block=60, priority=TaskPriority.p4)
    peer = _task(120, min_block=60, max_block=60, priority=TaskPriority.p1)
    now = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
    end = datetime(2026, 10, 13, 18, 0, tzinfo=UTC)
    claim = HigherRankedTask(task=peer, remaining_minutes=120, composition=peer_comp)
    choice = choose_rank_mode(
        db=None,
        task=subject,
        owner_id=subject.owner_id,
        settings=_settings(),
        remaining_minutes=60,
        busy=[],
        horizon_start=now,
        horizon_end=end,
        preferred_windows={},
        now_utc=now,
        preferred_window_id=None,
        project_daily_usage={},
        daily_cap=None,
        prerequisite_not_before=None,
        time_map_overrides_by_map={},
        working_windows=[],
        general_windows=[],
        composition=subject_comp,
        higher_ranked=(claim,),
    )
    assert choice.decision == DECISION_HIGHER_RANKED
    assert choice.mode == RANK_MODE_ELIGIBLE
    placed = _place(subject_comp, subject, now=now, end=end, higher_ranked=(claim,))
    assert placed.proposed_blocks[0].start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert placed.unmet_preference["decision"] == "higher_ranked_competition"


def test_fingerprint_changes_when_only_replacement_layer_hours_change() -> None:
    standing = _layer(
        "task",
        "t",
        may=(rule("am", RuleRole.MAY, (_window(9, 0, 60),), scope="task", scope_id="t"),),
    )
    early = _layer(
        "task",
        "t",
        may=(rule("pm", RuleRole.MAY, (_window(15, 0, 60),), scope="task", scope_id="t"),),
    )
    late = _layer(
        "task",
        "t",
        may=(rule("pm", RuleRole.MAY, (_window(16, 0, 60),), scope="task", scope_id="t"),),
    )
    selector = CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY)
    first = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        selector,
        replacement_family="new_rule",
        replacement_layer=early,
        output_rule_id="pm",
        declaration_id="same-id",
    )
    second = _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        selector,
        replacement_family="new_rule",
        replacement_layer=late,
        output_rule_id="pm",
        declaration_id="same-id",
    )
    left = _resolve(standing, day_scoped=(first,))
    right = _resolve(standing, day_scoped=(second,))
    left_hours = _hours(composition_search_windows(TUESDAY, TZ, left, []))
    right_hours = _hours(composition_search_windows(TUESDAY, TZ, right, []))
    assert (15, 0, 16, 0) in left_hours
    assert (16, 0, 17, 0) in right_hours
    left_fp = composition_fingerprint(left)
    right_fp = composition_fingerprint(right)
    assert left_fp != right_fp
    assert left_fp["day_scoped"][0]["id"] == right_fp["day_scoped"][0]["id"]
    assert left_fp["day_scoped"][0]["selector"] == right_fp["day_scoped"][0]["selector"]
    assert left_fp["day_scoped"][0]["output_rule_id"] == "pm"
    assert left_fp["rules"] == right_fp["rules"]
    assert left_fp["day_scoped"][0]["replacement_layer"]["may_rules"][0]["windows"][0]["start_time"] == "15:00:00"
    assert right_fp["day_scoped"][0]["replacement_layer"]["may_rules"][0]["windows"][0]["start_time"] == "16:00:00"


def _legacy_standing(*decls: DayScopedDeclaration, view: LegacyMapView) -> object:
    composed = resolve_effective_composition(
        CompositionInput(
            family=AssignmentFamily.LEGACY,
            standing_legacy_map=view,
            day_scoped=tuple(decls),
        )
    )
    fingerprint = composition_fingerprint(composed)
    assert fingerprint["family"] == "legacy"
    assert fingerprint["rules"] == []
    assert "standing_legacy_map" not in fingerprint
    return composed


def _temp_may(hour: int, *, declaration_id: str) -> DayScopedDeclaration:
    layer = _layer(
        "task",
        "t",
        may=(rule("temp", RuleRole.MAY, (_window(hour, 0, 60),), scope="task", scope_id="t"),),
    )
    return _decl(
        DayScopedOp.FAMILY_REPLACE_SCOPED,
        CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
        replacement_family="new_rule",
        replacement_layer=layer,
        expires_at=datetime(2026, 10, 13, 13, 0, tzinfo=UTC),
        declaration_id=declaration_id,
    )


def _legacy_clips(composed, general=()):
    return composition_search_windows(
        TUESDAY,
        TZ,
        composed,
        general,
        working_windows=[_window(9, 0, 480)],
    )


def _place_on_legacy(composed, now: datetime, end: datetime, minutes: int = 60):
    task = _task(minutes, min_block=60, max_block=60)
    result, _busy = place_task(
        None,  # type: ignore[arg-type]
        task=task,
        owner_id=task.owner_id,
        settings=_settings(),
        remaining_minutes=minutes,
        busy=[],
        horizon_start=now,
        horizon_end=end,
        preferred_windows={},
        now_utc=now,
        finalize_status=False,
        persist_blocks=False,
        working_windows=[_window(9, 0, 480)],
        general_windows=[_window(11, 0, 60)],
        composition=composed,
        ranking_protection=False,
    )
    return result


def test_expiry_restores_legacy_standing_map_across_the_cut() -> None:
    """A midday expiry resumes the standing map, not an empty new-rule search."""
    expiry = datetime(2026, 10, 13, 13, 0, tzinfo=UTC)
    afternoon = datetime(2026, 10, 13, 18, 0, tzinfo=UTC)
    morning = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
    standing = _legacy_view(("green", time(16, 0), time(17, 0)))

    expired_later = _legacy_standing(_temp_may(14, declaration_id="after-cut"), view=standing)
    later = _legacy_clips(expired_later)
    assert not _crosses(later, expiry)
    assert _hours(later) == []
    assert [(item[0].hour, item[1].hour) for item in later] == [(16, 17)]
    placed = _place_on_legacy(expired_later, expiry, afternoon)
    assert placed.blocks_created == 1
    assert placed.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    assert not (placed.proposed_blocks[0].start_time < expiry < placed.proposed_blocks[0].end_time)

    crossing = _legacy_standing(_temp_may(10, declaration_id="cross-cut"), view=standing)
    crossed = _legacy_clips(crossing)
    assert not _crosses(crossed, expiry)
    assert (10, 0, 11, 0) in _hours(crossed)
    assert any(item[0].hour == 16 and item[1].hour == 17 for item in crossed)
    early = _place_on_legacy(crossing, morning, afternoon)
    assert early.proposed_blocks[0].start_time == datetime(2026, 10, 13, 10, 0, tzinfo=UTC)
    resumed = _place_on_legacy(crossing, expiry, afternoon)
    assert resumed.proposed_blocks[0].start_time == datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
    both = _place_on_legacy(crossing, morning, afternoon, minutes=120)
    assert [(block.start_time.hour, block.end_time.hour) for block in both.proposed_blocks] == [
        (10, 11),
        (16, 17),
    ]
    assert not any(block.start_time < expiry < block.end_time for block in both.proposed_blocks)

    wide = _legacy_view(("green", time(12, 0), time(17, 0)))
    split_map = _legacy_standing(_temp_may(10, declaration_id="wide-map"), view=wide)
    split_clips = _legacy_clips(split_map)
    assert not _crosses(split_clips, expiry)
    assert not any(item[0].hour == 12 for item in split_clips)
    assert any(item[0] == expiry and item[1].hour == 17 for item in split_clips)
    resumed_wide = _place_on_legacy(split_map, expiry, afternoon)
    assert resumed_wide.proposed_blocks[0].start_time == expiry

    ranked = LegacyMapView(
        map_id="ranked",
        strict_mode=True,
        bands=(
            LegacyBand("yellow", time(14, 0), time(17, 0), 127, 0),
            LegacyBand("green", time(16, 0), time(17, 0), 127, 1),
        ),
    )
    green_first = _legacy_standing(_temp_may(10, declaration_id="green-first"), view=ranked)
    assert _place_on_legacy(green_first, expiry, afternoon).proposed_blocks[0].start_time == datetime(
        2026, 10, 13, 16, 0, tzinfo=UTC
    )

    red_map = LegacyMapView(
        map_id="red",
        strict_mode=True,
        bands=(
            LegacyBand("green", time(14, 0), time(17, 0), 127, 0),
            LegacyBand("red", time(14, 0), time(15, 0), 127, 1),
        ),
    )
    red = _legacy_standing(_temp_may(10, declaration_id="red-cut"), view=red_map)
    red_clips = _legacy_clips(red)
    assert not any(item[0].hour == 14 for item in red_clips)
    assert any(item[0].hour == 15 for item in red_clips)
    assert _place_on_legacy(red, expiry, afternoon).proposed_blocks[0].start_time == datetime(
        2026, 10, 13, 15, 0, tzinfo=UTC
    )

    override = LegacyOverride(
        override_id="ov",
        map_id="standing",
        local_start_date=TUESDAY,
        local_end_date=TUESDAY,
        timezone="UTC",
        strict_mode=True,
        bands=(LegacyBand("yellow", time(15, 0), time(16, 0), 127, 0),),
    )
    replace_map = LegacyMapView(
        map_id="standing",
        strict_mode=True,
        bands=(LegacyBand("green", time(16, 0), time(17, 0), 127, 0),),
        overrides=(override,),
    )
    moved = _legacy_standing(_temp_may(10, declaration_id="override-cut"), view=replace_map)
    moved_clips = _legacy_clips(moved)
    assert not any(item[0].hour == 16 for item in moved_clips)
    assert any(item[0].hour == 15 and item[1].hour == 16 and item[2] == "yellow" for item in moved_clips)
    assert _place_on_legacy(moved, expiry, afternoon).proposed_blocks[0].start_time == datetime(
        2026, 10, 13, 15, 0, tzinfo=UTC
    )

    outside = _legacy_view(("green", time(19, 0), time(20, 0)))
    hidden = _legacy_standing(_temp_may(14, declaration_id="outside-work"), view=outside)
    assert _legacy_clips(hidden) == []
    assert _place_on_legacy(hidden, expiry, afternoon).blocks_created == 0

    flexible = LegacyMapView(
        map_id="flex",
        strict_mode=False,
        bands=(LegacyBand("red", time(16, 0), time(17, 0), 127, 0),),
    )
    spilled = _legacy_standing(_temp_may(10, declaration_id="flex-cut"), view=flexible)
    spill = _legacy_clips(spilled)
    assert any(item[0] == expiry and item[1].hour == 16 and item[2] == "neutral" for item in spill)
    assert not any(item[0].hour == 16 and item[2] != "neutral" for item in spill)
    assert _place_on_legacy(spilled, expiry, afternoon).proposed_blocks[0].start_time == expiry

    general = (_window(11, 0, 60),)
    cleared = _legacy_standing(
        _decl(
            DayScopedOp.CLEAR_SCOPED,
            CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
            expires_at=expiry,
            declaration_id="clear-legacy",
        ),
        view=standing,
    )
    clear_clips = _legacy_clips(cleared, general)
    assert not _crosses(clear_clips, expiry)
    assert (11, 0, 12, 0) in _hours(clear_clips)
    assert any(item[0].hour == 16 for item in clear_clips)
    assert _place_on_legacy(cleared, morning, afternoon).proposed_blocks[0].start_time.hour == 11
    assert _place_on_legacy(cleared, expiry, afternoon).proposed_blocks[0].start_time.hour == 16

    none_family = _legacy_standing(
        _decl(
            DayScopedOp.FAMILY_REPLACE_SCOPED,
            CivilSelector(SelectorKind.ONE_DATE, on_date=TUESDAY),
            replacement_family="none",
            expires_at=expiry,
            declaration_id="none-legacy",
        ),
        view=standing,
    )
    none_clips = _legacy_clips(none_family, general)
    assert (11, 0, 12, 0) in _hours(none_clips)
    assert any(item[0].hour == 16 for item in none_clips)
    assert not _crosses(none_clips, expiry)
