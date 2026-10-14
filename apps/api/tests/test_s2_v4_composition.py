"""S2-V4 May / Must / Prefer placer composition.

V3 Working/General and legacy map ∩ Working stay in place when no new-rule
assignment is supplied. These tests build the composition contract directly so
they do not need Jules's assignment tables.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.models import Task, UserSettings
from app.scheduler.availability_materializer import PolicyWindow
from app.scheduler.busy_map import BusyInterval
from app.scheduler.composition import (
    RANK_ELIGIBLE,
    RANK_PREFER,
    AssignmentFamily,
    CompositionInput,
    DeferredException,
    DeferredForm,
    ExceptionOp,
    MayMode,
    RuleRole,
    ScopeLayer,
    StandingException,
    composition_fingerprint,
    composition_input_from_mapping,
    composition_search_windows,
    make_window,
    resolve_effective_composition,
    rule,
)
from app.scheduler.composition_resolver import load_compositions_by_task
from app.scheduler.input_fingerprint import (
    SCHEDULING_ACTIVATIONS,
    STALE_COMPOSITION,
    assemble_snapshot,
    diff_stale_categories,
)
from app.scheduler.placement import place_task
from app.scheduler.reasons import REASON_ASSIGNMENT_FAMILY_CONFLICT, REASON_UNMET_PREFERENCE, format_summary_text, ReasonFact
from app.services.composition_cutover_activation import (
    ACTIVATION_TOKEN,
    composition_activation_revision,
)

UTC = timezone.utc
TZ = ZoneInfo("UTC")
TUESDAY = date(2026, 10, 13)


def _window(hour: int, minute: int, duration: int, weekday: int = 1) -> object:
    return make_window(weekday, time(hour, minute), duration)


def _layer(
    scope: str,
    scope_id: str,
    *,
    may_mode: MayMode = MayMode.ABSENT,
    may: tuple = (),
    must: tuple = (),
    prefer: tuple = (),
    exceptions: tuple = (),
    deferred: tuple = (),
) -> ScopeLayer:
    return ScopeLayer(
        scope=scope,
        scope_id=scope_id,
        may_mode=may_mode,
        may_rules=may,
        must_rules=must,
        prefer_rules=prefer,
        exceptions=exceptions,
        deferred=deferred,
    )


def _resolve(*layers: ScopeLayer, family: AssignmentFamily = AssignmentFamily.NEW_RULE):
    return resolve_effective_composition(
        CompositionInput(family=family, layers=layers)
    )


def _clips(composition, day: date = TUESDAY, general: list | None = None):
    return composition_search_windows(day, TZ, composition, general or [])


def _starts(clips) -> list[datetime]:
    return [item[0] for item in clips]


def _policy(hour: int, duration: int, weekday: int = 1) -> PolicyWindow:
    return PolicyWindow(
        weekday=weekday,
        start_time=time(hour, 0),
        duration_minutes=duration,
        ends_next_day=False,
    )


def _task(minutes: int = 60) -> Task:
    return Task(
        owner_id=uuid4(),
        title="composition",
        estimated_duration_minutes=minutes,
        min_block_duration_minutes=minutes,
        max_block_duration_minutes=minutes,
        max_block_unbounded=False,
        keep_in_one_block=False,
        worked_minutes=0,
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


def _place(
    composition,
    *,
    now: datetime,
    end: datetime,
    minutes: int = 60,
    general: list | None = None,
    working: list | None = None,
    busy: list | None = None,
):
    result, _busy = place_task(
        None,  # type: ignore[arg-type]
        task=_task(minutes),
        owner_id=uuid4(),
        settings=_settings(),
        remaining_minutes=minutes,
        busy=list(busy or []),
        horizon_start=now,
        horizon_end=end,
        preferred_windows={},
        now_utc=now,
        preferred_window_id=None,
        finalize_status=False,
        persist_blocks=False,
        working_windows=working if working is not None else [],
        general_windows=general if general is not None else [],
        composition=composition,
    )
    return result


def _snap(**overrides):
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
        timezone_name="UTC",
        upcoming_horizon_days=7,
        inter_block_buffer_minutes=0,
        working_windows=[_policy(9, 480)],
        general_windows=[_policy(9, 480)],
    )
    base.update(overrides)
    return assemble_snapshot(**base)


def test_activation_token_appends_after_v3() -> None:
    assert ACTIVATION_TOKEN == "s2-v4-may-must-prefer-composition"
    assert SCHEDULING_ACTIVATIONS[-1] == ACTIVATION_TOKEN
    assert "s2-v3-working-general-availability" in SCHEDULING_ACTIVATIONS
    assert SCHEDULING_ACTIVATIONS.index(
        "s2-v3-working-general-availability"
    ) < SCHEDULING_ACTIVATIONS.index(ACTIVATION_TOKEN)
    assert composition_activation_revision(4) == 5


def test_may_union_merges_overlapping_alternatives() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(
                rule("am", RuleRole.MAY, (_window(9, 0, 180),), scope="task", scope_id="t"),
                rule("mid", RuleRole.MAY, (_window(11, 0, 180),), scope="task", scope_id="t"),
            ),
        )
    )
    clips = _clips(composed)
    assert len(clips) == 1
    assert clips[0][0] == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert clips[0][1] == datetime(2026, 10, 13, 14, 0, tzinfo=UTC)
    assert clips[0][2] == RANK_ELIGIBLE


def test_must_intersect_keeps_only_the_overlap() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(
                rule("wide", RuleRole.MAY, (_window(9, 0, 480),), scope="task", scope_id="t"),
            ),
            must=(
                rule("need", RuleRole.MUST, (_window(10, 0, 120),), scope="task", scope_id="t"),
            ),
        )
    )
    clips = _clips(composed)
    assert [(item[0].hour, item[1].hour) for item in clips] == [(10, 12)]


def test_prefer_ranks_without_creating_evening_hours() -> None:
    general = [_policy(9, 480)]
    composed = _resolve(
        _layer(
            "task",
            "t",
            prefer=(
                rule(
                    "eve",
                    RuleRole.PREFER,
                    (_window(19, 0, 120),),
                    scope="task",
                    scope_id="t",
                ),
            ),
        )
    )
    assert composed.may_source == "general"
    clips = _clips(composed, general=general)
    assert clips
    assert all(item[0].hour < 17 for item in clips)
    assert all(item[2] == RANK_ELIGIBLE for item in clips)
    assert not any(item[0].hour >= 19 for item in clips)


def test_explicit_empty_may_does_not_borrow_general() -> None:
    composed = _resolve(
        _layer("task", "t", may_mode=MayMode.EXPLICIT_EMPTY)
    )
    assert composed.may_source == "explicit_empty"
    assert _clips(composed, general=[_policy(9, 480)]) == []


def test_empty_must_yields_no_eligibility() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="task", scope_id="t"),),
            must=(rule("none", RuleRole.MUST, (), scope="task", scope_id="t"),),
        )
    )
    assert composed.must_blocks_all is True
    assert _clips(composed) == []


def test_absent_may_keeps_general_and_must_narrows_it() -> None:
    composed = _resolve(
        _layer(
            "epic",
            "e",
            must=(rule("need", RuleRole.MUST, (_window(10, 0, 120),), scope="epic", scope_id="e"),),
        )
    )
    clips = _clips(composed, general=[_policy(9, 480)])
    assert [(item[0].hour, item[1].hour) for item in clips] == [(10, 12)]


def test_child_prefer_does_not_erase_ancestor_must() -> None:
    # Parent permits evening and imposes a narrower Must. Child only adds Prefer.
    composed = _resolve(
        _layer(
            "task",
            "t",
            prefer=(
                rule("pref", RuleRole.PREFER, (_window(19, 0, 60),), scope="task", scope_id="t"),
            ),
        ),
        _layer(
            "epic",
            "e",
            may_mode=MayMode.PRESENT,
            may=(rule("eve", RuleRole.MAY, (_window(18, 0, 240),), scope="epic", scope_id="e"),),
            must=(rule("need", RuleRole.MUST, (_window(19, 0, 120),), scope="epic", scope_id="e"),),
        ),
    )
    clips = _clips(composed)
    assert clips[0][2] == RANK_PREFER
    assert clips[0][0] == datetime(2026, 10, 13, 19, 0, tzinfo=UTC)
    assert clips[0][1] == datetime(2026, 10, 13, 20, 0, tzinfo=UTC)
    # Fallback is the continuous Must span, not the leftover after Prefer.
    eligible = [item for item in clips if item[2] == RANK_ELIGIBLE]
    assert eligible == [
        (
            datetime(2026, 10, 13, 19, 0, tzinfo=UTC),
            datetime(2026, 10, 13, 21, 0, tzinfo=UTC),
            RANK_ELIGIBLE,
        )
    ]
    assert all(item[0] >= datetime(2026, 10, 13, 19, 0, tzinfo=UTC) for item in clips)
    assert all(item[1] <= datetime(2026, 10, 13, 21, 0, tzinfo=UTC) for item in clips)


def test_same_id_child_addition_does_not_replace_ancestor_must() -> None:
    composed = _resolve(
        _layer(
            "epic",
            "e",
            may_mode=MayMode.PRESENT,
            may=(rule("wide", RuleRole.MAY, (_window(18, 0, 240),), scope="epic", scope_id="e"),),
            must=(rule("focus", RuleRole.MUST, (_window(19, 0, 120),), scope="epic", scope_id="e"),),
        ),
        _layer(
            "task",
            "t",
            must=(rule("focus", RuleRole.MUST, (_window(18, 0, 240),), scope="task", scope_id="t"),),
        ),
    )
    assert len(composed.must_rules) == 2
    assert {entry.scope for entry in composed.must_rules} == {"epic", "task"}
    clips = _clips(composed)
    assert clips[0][0] == datetime(2026, 10, 13, 19, 0, tzinfo=UTC)
    assert clips[-1][1] == datetime(2026, 10, 13, 21, 0, tzinfo=UTC)


def test_named_may_addition_does_not_waive_parent_must() -> None:
    composed = _resolve(
        _layer(
            "epic",
            "e",
            may_mode=MayMode.PRESENT,
            may=(rule("am", RuleRole.MAY, (_window(10, 0, 120),), scope="epic", scope_id="e"),),
            must=(rule("need", RuleRole.MUST, (_window(10, 0, 60),), scope="epic", scope_id="e"),),
        ),
        _layer(
            "task",
            "t",
            exceptions=(
                StandingException(
                    operation=ExceptionOp.ADD,
                    scope="task",
                    scope_id="t",
                    rule=rule(
                        "extra",
                        RuleRole.MAY,
                        (_window(15, 0, 120),),
                        scope="task",
                        scope_id="t",
                    ),
                ),
            ),
        ),
    )
    clips = _clips(composed)
    assert [(item[0].hour, item[1].hour) for item in clips] == [(10, 11)]


def test_waiver_drops_only_the_named_must() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="task", scope_id="t"),),
            must=(
                rule("am", RuleRole.MUST, (_window(10, 0, 120),), scope="task", scope_id="t"),
                rule("pm", RuleRole.MUST, (_window(14, 0, 120),), scope="task", scope_id="t"),
            ),
            exceptions=(
                StandingException(
                    operation=ExceptionOp.WAIVE_NAMED,
                    scope="task",
                    scope_id="t",
                    target_rule_id="pm",
                ),
            ),
        )
    )
    assert composed.waived_must_ids == ("pm",)
    clips = _clips(composed)
    assert [(item[0].hour, item[1].hour) for item in clips] == [(10, 12)]


def test_named_replace_leaves_sibling_may() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(
                rule("am", RuleRole.MAY, (_window(9, 0, 180),), scope="task", scope_id="t"),
                rule("pm", RuleRole.MAY, (_window(13, 0, 240),), scope="task", scope_id="t"),
            ),
            exceptions=(
                StandingException(
                    operation=ExceptionOp.REPLACE_NAMED,
                    scope="task",
                    scope_id="t",
                    target_rule_id="pm",
                    rule=rule("pm", RuleRole.MAY, (), scope="task", scope_id="t"),
                ),
            ),
        )
    )
    clips = _clips(composed)
    assert len(clips) == 1
    assert clips[0][0].hour == 9
    assert clips[0][1].hour == 12


def test_deferred_forms_do_not_change_eligibility() -> None:
    standing = _layer(
        "task",
        "t",
        may_mode=MayMode.PRESENT,
        may=(rule("am", RuleRole.MAY, (_window(10, 0, 120),), scope="task", scope_id="t"),),
    )
    deferred = _layer(
        "task",
        "t",
        may_mode=MayMode.PRESENT,
        may=(rule("am", RuleRole.MAY, (_window(10, 0, 120),), scope="task", scope_id="t"),),
        deferred=(
            DeferredException(DeferredForm.DATE_RANGE, "task", "t"),
            DeferredException(DeferredForm.WEEKDAY_STANDING, "task", "t"),
            DeferredException(DeferredForm.CONTEXT, "task", "t"),
            DeferredException(DeferredForm.IGNORE_ALL, "task", "t"),
        ),
    )
    plain = _resolve(standing)
    held = _resolve(deferred)
    assert _clips(plain) == _clips(held)
    assert [item.form for item in held.deferred_rejected] == [
        DeferredForm.DATE_RANGE,
        DeferredForm.WEEKDAY_STANDING,
        DeferredForm.CONTEXT,
        DeferredForm.IGNORE_ALL,
    ]
    assert composition_fingerprint(plain) != composition_fingerprint(held)


def test_dated_dict_exception_is_not_applied() -> None:
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
                        "windows": [
                            {"weekday": 1, "start_time": "10:00:00", "duration_minutes": 120}
                        ],
                    }
                ],
                "exceptions": [
                    {
                        "operation": "add",
                        "applies_on": "2026-10-13",
                        "rule": {
                            "rule_id": "monday",
                            "role": "may",
                            "windows": [
                                {
                                    "weekday": 1,
                                    "start_time": "15:00:00",
                                    "duration_minutes": 120,
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    composed = resolve_effective_composition(composition_input_from_mapping(payload))
    assert composed.deferred_rejected[0].form == DeferredForm.DATE_RANGE
    assert [item[0].hour for item in _clips(composed)] == [10]


def test_legacy_family_does_not_compose_stuffed_may() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("eve", RuleRole.MAY, (_window(19, 0, 120),), scope="task", scope_id="t"),),
        ),
        family=AssignmentFamily.LEGACY,
    )
    assert composed.supplies_eligibility() is False
    assert composed.may_rules == ()
    assert _clips(composed, general=[_policy(9, 480)]) == []
    fingerprint = composition_fingerprint(composed)
    assert fingerprint["family"] == "legacy"
    assert fingerprint["rules"] == []


def test_conflict_family_does_not_pick_a_winner() -> None:
    composed = _resolve(family=AssignmentFamily.CONFLICT)
    assert composed.supplies_eligibility() is False
    result = _place(
        composed,
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
        general=[_policy(9, 480)],
    )
    assert result.blocks_created == 0
    assert REASON_ASSIGNMENT_FAMILY_CONFLICT in result.observed_constraints


def test_composition_fingerprint_is_its_own_compared_category() -> None:
    base = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="task", scope_id="t"),),
            prefer=(rule("eve", RuleRole.PREFER, (_window(16, 0, 60),), scope="task", scope_id="t"),),
        )
    )
    later = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="task", scope_id="t"),),
            prefer=(rule("eve", RuleRole.PREFER, (_window(19, 0, 60),), scope="task", scope_id="t"),),
        )
    )
    left = composition_fingerprint(base)
    right = composition_fingerprint(later)
    assert set(left) == {
        "family",
        "may_source",
        "rules",
        "waived_must_ids",
        "exceptions",
        "deferred_rejected",
    }
    stored = _snap(composition=left)
    live = _snap(composition=right)
    assert stored["composition"] == left
    assert diff_stale_categories(stored, live) == [STALE_COMPOSITION]
    assert stored["availability"] == live["availability"]


def test_resolver_seam_is_empty_until_jules_lands() -> None:
    assert load_compositions_by_task(None, uuid4(), [], {}, {}) == {}


def test_overnight_may_tail_is_visible_the_next_morning() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(
                rule(
                    "night",
                    RuleRole.MAY,
                    (make_window(0, time(22, 0), 240),),
                    scope="task",
                    scope_id="t",
                ),
            ),
        )
    )
    clips = _clips(composed, day=TUESDAY)
    assert (datetime(2026, 10, 13, 0, 0, tzinfo=UTC), datetime(2026, 10, 13, 2, 0, tzinfo=UTC), RANK_ELIGIBLE) in clips


def test_afternoon_fallback_explains_unmet_preference() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(
                rule(
                    "both",
                    RuleRole.MAY,
                    (_window(13, 0, 240), _window(19, 0, 120)),
                    scope="task",
                    scope_id="t",
                ),
            ),
            prefer=(
                rule("eve", RuleRole.PREFER, (_window(19, 0, 120),), scope="task", scope_id="t"),
            ),
        )
    )
    busy = [
        BusyInterval(
            start=datetime(2026, 10, 13, 19, 0, tzinfo=UTC),
            end=datetime(2026, 10, 13, 21, 0, tzinfo=UTC),
            source="external",
        )
    ]
    result = _place(
        composed,
        now=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 23, 0, tzinfo=UTC),
        busy=busy,
    )
    assert result.blocks_created == 1
    block = result.proposed_blocks[0]
    assert block.start_time == datetime(2026, 10, 13, 13, 0, tzinfo=UTC)
    assert block.tier is None
    assert result.unmet_preference is not None
    assert result.unmet_preference["placed_outside_preferred_window"] is True
    text = format_summary_text(
        [ReasonFact(REASON_UNMET_PREFERENCE, result.unmet_preference)]
    )
    assert "preferred time" in text
    assert "did not create hours" in text


def test_prefer_without_may_does_not_place_in_the_evening() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            prefer=(rule("eve", RuleRole.PREFER, (_window(19, 0, 120),), scope="task", scope_id="t"),),
        )
    )
    result = _place(
        composed,
        now=datetime(2026, 10, 13, 18, 30, tzinfo=UTC),
        end=datetime(2026, 10, 13, 23, 0, tzinfo=UTC),
        general=[_policy(9, 480)],
        working=[_policy(9, 480)],
    )
    assert result.blocks_created == 0
    assert result.unmet_preference is None


def test_new_rule_may_is_not_capped_by_working() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("eve", RuleRole.MAY, (_window(19, 0, 120),), scope="task", scope_id="t"),),
        )
    )
    result = _place(
        composed,
        now=datetime(2026, 10, 13, 18, 30, tzinfo=UTC),
        end=datetime(2026, 10, 13, 23, 0, tzinfo=UTC),
        general=[_policy(9, 480)],
        working=[_policy(9, 480)],
    )
    assert result.blocks_created == 1
    assert result.proposed_blocks[0].start_time == datetime(2026, 10, 13, 19, 0, tzinfo=UTC)
    assert result.unmet_preference is None


def test_legacy_place_path_ignores_stuffed_evening_may() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("eve", RuleRole.MAY, (_window(19, 0, 120),), scope="task", scope_id="t"),),
        ),
        family=AssignmentFamily.LEGACY,
    )
    result = _place(
        composed,
        now=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
        minutes=30,
        general=[_policy(9, 480)],
        working=[_policy(9, 480)],
    )
    assert result.blocks_created == 1
    assert result.proposed_blocks[0].start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


def test_prefer_does_not_fragment_continuous_eligible_block() -> None:
    """V4-D1: Prefer ranks; it does not split a feasible 2h May into 1h pieces."""
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 180),), scope="task", scope_id="t"),),
            prefer=(
                rule("middle", RuleRole.PREFER, (_window(10, 0, 60),), scope="task", scope_id="t"),
            ),
        )
    )
    clips = _clips(composed)
    prefer = [(item[0].hour, item[1].hour) for item in clips if item[2] == RANK_PREFER]
    eligible = [(item[0].hour, item[1].hour) for item in clips if item[2] == RANK_ELIGIBLE]
    assert prefer == [(10, 11)]
    assert (9, 12) in eligible
    assert (9, 10) not in eligible
    assert (11, 12) not in eligible
    result = _place(
        composed,
        now=datetime(2026, 10, 13, 9, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        minutes=120,
    )
    assert result.blocks_created == 1
    block = result.proposed_blocks[0]
    assert block.start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert block.end_time == datetime(2026, 10, 13, 11, 0, tzinfo=UTC)


def test_prefer_fallback_keeps_must_and_busy_boundaries() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="task", scope_id="t"),),
            must=(rule("am", RuleRole.MUST, (_window(9, 0, 120),), scope="task", scope_id="t"),),
            prefer=(
                rule("mid", RuleRole.PREFER, (_window(9, 30, 60),), scope="task", scope_id="t"),
            ),
        )
    )
    placed = _place(
        composed,
        now=datetime(2026, 10, 13, 9, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 17, 0, tzinfo=UTC),
        minutes=120,
    )
    assert placed.blocks_created == 1
    block = placed.proposed_blocks[0]
    assert block.start_time == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    assert block.end_time == datetime(2026, 10, 13, 11, 0, tzinfo=UTC)

    busy = [
        BusyInterval(
            start=datetime(2026, 10, 13, 10, 0, tzinfo=UTC),
            end=datetime(2026, 10, 13, 11, 0, tzinfo=UTC),
            source="external",
        )
    ]
    wide = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 180),), scope="task", scope_id="t"),),
            prefer=(
                rule("middle", RuleRole.PREFER, (_window(10, 0, 60),), scope="task", scope_id="t"),
            ),
        )
    )
    blocked = _place(
        wide,
        now=datetime(2026, 10, 13, 9, 0, tzinfo=UTC),
        end=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
        minutes=120,
        busy=busy,
    )
    assert blocked.blocks_created == 0


def test_same_named_child_must_intersects_ancestor() -> None:
    """V4-D2: same name at two scopes is two Musts; ordinary add does not drop one."""
    composed = _resolve(
        _layer(
            "project",
            "p",
            must=(rule("hours", RuleRole.MUST, (_window(9, 0, 480),), scope="project", scope_id="p"),),
        ),
        _layer(
            "task",
            "t",
            must=(rule("hours", RuleRole.MUST, (_window(13, 0, 60),), scope="task", scope_id="t"),),
        ),
    )
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("project", "hours"),
        ("task", "hours"),
    }
    clips = _clips(composed, general=[_policy(9, 480)])
    assert [(item[0].hour, item[1].hour) for item in clips] == [(13, 14)]


def test_same_named_may_unions_and_prefer_both_rank() -> None:
    may = _resolve(
        _layer(
            "project",
            "p",
            may_mode=MayMode.PRESENT,
            may=(rule("hours", RuleRole.MAY, (_window(9, 0, 180),), scope="project", scope_id="p"),),
        ),
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("hours", RuleRole.MAY, (_window(11, 0, 240),), scope="task", scope_id="t"),),
        ),
    )
    assert len(may.may_rules) == 2
    assert [(item[0].hour, item[1].hour) for item in _clips(may)] == [(9, 15)]

    prefer = _resolve(
        _layer(
            "project",
            "p",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 180),), scope="project", scope_id="p"),),
            prefer=(
                rule("hours", RuleRole.PREFER, (_window(9, 0, 60),), scope="project", scope_id="p"),
            ),
        ),
        _layer(
            "task",
            "t",
            prefer=(
                rule("hours", RuleRole.PREFER, (_window(11, 0, 60),), scope="task", scope_id="t"),
            ),
        ),
    )
    assert len(prefer.prefer_rules) == 2
    ranked = [(item[0].hour, item[1].hour) for item in _clips(prefer) if item[2] == RANK_PREFER]
    assert ranked == [(9, 10), (11, 12)]


def test_same_name_waiver_and_replace_target_the_inherited_rule() -> None:
    waived = _resolve(
        _layer(
            "project",
            "p",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="project", scope_id="p"),),
            must=(rule("hours", RuleRole.MUST, (_window(9, 0, 480),), scope="project", scope_id="p"),),
        ),
        _layer(
            "task",
            "t",
            must=(rule("hours", RuleRole.MUST, (_window(13, 0, 60),), scope="task", scope_id="t"),),
            exceptions=(
                StandingException(
                    operation=ExceptionOp.WAIVE_NAMED,
                    scope="task",
                    scope_id="t",
                    target_rule_id="hours",
                ),
            ),
        ),
    )
    assert {(entry.scope, entry.rule_id) for entry in waived.must_rules} == {("task", "hours")}
    assert waived.waived_must_ids == ("hours",)
    assert [(item[0].hour, item[1].hour) for item in _clips(waived)] == [(13, 14)]

    replaced = _resolve(
        _layer(
            "project",
            "p",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="project", scope_id="p"),),
            must=(rule("hours", RuleRole.MUST, (_window(9, 0, 480),), scope="project", scope_id="p"),),
        ),
        _layer(
            "task",
            "t",
            must=(rule("hours", RuleRole.MUST, (_window(13, 0, 60),), scope="task", scope_id="t"),),
            exceptions=(
                StandingException(
                    operation=ExceptionOp.REPLACE_NAMED,
                    scope="task",
                    scope_id="t",
                    target_rule_id="hours",
                    rule=rule("tight", RuleRole.MUST, (_window(13, 0, 30),), scope="task", scope_id="t"),
                ),
            ),
        ),
    )
    assert {(entry.scope, entry.rule_id) for entry in replaced.must_rules} == {
        ("task", "hours"),
        ("task", "tight"),
    }
    replaced_clips = _clips(replaced)
    assert len(replaced_clips) == 1
    assert replaced_clips[0][0] == datetime(2026, 10, 13, 13, 0, tzinfo=UTC)
    assert replaced_clips[0][1] == datetime(2026, 10, 13, 13, 30, tzinfo=UTC)


def test_replacement_name_does_not_erase_sibling_must() -> None:
    """V4-D2 residual: replacement output must not overwrite a sibling Must."""
    composed = _resolve(
        _layer(
            "project",
            "p",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="project", scope_id="p"),),
            must=(
                rule(
                    "parent-hours",
                    RuleRole.MUST,
                    (_window(9, 0, 480),),
                    scope="project",
                    scope_id="p",
                ),
            ),
        ),
        _layer(
            "task",
            "t",
            must=(
                rule(
                    "local-hours",
                    RuleRole.MUST,
                    (_window(13, 0, 60),),
                    scope="task",
                    scope_id="t",
                ),
            ),
            exceptions=(
                StandingException(
                    operation=ExceptionOp.REPLACE_NAMED,
                    scope="task",
                    scope_id="t",
                    target_rule_id="parent-hours",
                    rule=rule(
                        "local-hours",
                        RuleRole.MUST,
                        (_window(9, 0, 480),),
                        scope="task",
                        scope_id="t",
                    ),
                ),
            ),
        ),
    )
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("project", "parent-hours"),
        ("task", "local-hours"),
    }
    assert composed.exceptions[-1].applied is False
    assert [(item[0].hour, item[1].hour) for item in _clips(composed)] == [(13, 14)]


def test_second_replacement_output_does_not_erase_the_first() -> None:
    composed = _resolve(
        _layer(
            "project",
            "p",
            may_mode=MayMode.PRESENT,
            may=(rule("day", RuleRole.MAY, (_window(9, 0, 480),), scope="project", scope_id="p"),),
            must=(
                rule(
                    "parent-hours",
                    RuleRole.MUST,
                    (_window(9, 0, 480),),
                    scope="project",
                    scope_id="p",
                ),
                rule(
                    "other-hours",
                    RuleRole.MUST,
                    (_window(13, 0, 60),),
                    scope="project",
                    scope_id="p",
                ),
            ),
        ),
        _layer(
            "task",
            "t",
            exceptions=(
                StandingException(
                    operation=ExceptionOp.REPLACE_NAMED,
                    scope="task",
                    scope_id="t",
                    target_rule_id="parent-hours",
                    rule=rule(
                        "shared-name",
                        RuleRole.MUST,
                        (_window(9, 0, 480),),
                        scope="task",
                        scope_id="t",
                    ),
                ),
                StandingException(
                    operation=ExceptionOp.REPLACE_NAMED,
                    scope="task",
                    scope_id="t",
                    target_rule_id="other-hours",
                    rule=rule(
                        "shared-name",
                        RuleRole.MUST,
                        (_window(9, 0, 480),),
                        scope="task",
                        scope_id="t",
                    ),
                ),
            ),
        ),
    )
    assert {(entry.scope, entry.rule_id) for entry in composed.must_rules} == {
        ("project", "other-hours"),
        ("task", "shared-name"),
    }
    assert [item.applied for item in composed.exceptions] == [True, False]
    assert [(item[0].hour, item[1].hour) for item in _clips(composed)] == [(13, 14)]


def test_resolver_replacement_name_does_not_erase_sibling_must() -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from app.models.enums import SchedulingExceptionOp, SchedulingRuleKind
    from app.scheduler.assignment_resolve import ResolvedRule, _apply_layer_exceptions

    parent_policy = uuid4()
    local_policy = uuid4()
    must = {
        ("project", "parent-hours"): ResolvedRule(
            name="parent-hours",
            kind="must",
            policy_id=parent_policy,
            empty_set=False,
            source_scope="project",
            origin="inherited",
        ),
        ("task", "local-hours"): ResolvedRule(
            name="local-hours",
            kind="must",
            policy_id=local_policy,
            empty_set=False,
            source_scope="task",
            origin="local",
        ),
    }
    exc = SimpleNamespace(
        operation=SchedulingExceptionOp.replace_named,
        target_rule_name="parent-hours",
        target_rule_kind=SchedulingRuleKind.must,
        replacement_name="local-hours",
        replacement_policy_id=uuid4(),
        replacement_empty_set=False,
    )
    _may, applied = _apply_layer_exceptions(None, must, {}, [exc], scope="task")
    assert set(must) == {("project", "parent-hours"), ("task", "local-hours")}
    assert must[("task", "local-hours")].origin == "local"
    assert must[("task", "local-hours")].policy_id == local_policy
    assert applied == []


def test_evening_only_may_does_not_invent_afternoon() -> None:
    composed = _resolve(
        _layer(
            "task",
            "t",
            may_mode=MayMode.PRESENT,
            may=(rule("eve", RuleRole.MAY, (_window(19, 0, 120),), scope="task", scope_id="t"),),
        )
    )
    clips = _clips(composed, general=[_policy(9, 480)])
    assert [item[0].hour for item in clips] == [19]
