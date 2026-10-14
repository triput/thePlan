"""Scheduling calculation — proposed blocks and reason facts (no persistence)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ScheduledBlock, Task, TaskDependency
from app.models.enums import ScheduleStyle, TaskPriority
from app.scheduler.busy_map import BusyInterval
from app.scheduler.candidates import (
    LifecycleExcludedTask,
    TaskCandidate,
)
from app.scheduler.collect import SchedulingInputs
from app.scheduler.pin_reservation import reserved_minutes_from_blocks
from app.scheduler.placement import ProposedBlock, ProjectDailyUsage, place_one_block
from app.scheduler.task_effort import placement_effort_minutes
from app.scheduler.reasons import (
    REASON_BLOCKED_DEPENDENCY_CYCLE,
    REASON_BLOCKED_PREREQUISITE,
    REASON_EXCLUDED_DURATION_COVERED_BY_PINS,
    REASON_EXCLUDED_MANUAL_OR_BUNDLE,
    REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER,
    REASON_PLACED,
    REASON_UNPLACED_DEADLINE_LIMIT,
    REASON_UNPLACED_HORIZON_EXHAUSTED,
    REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK,
    REASON_UNPLACED_NO_SLOT,
    REASON_UNPLACED_PROJECT_DAILY_CAP,
    ReasonFact,
    TaskSchedulingOutcome,
)
from app.scheduler.style import effective_schedule_style_source

PRIORITY_ORDER = [
    TaskPriority.p1,
    TaskPriority.p2,
    TaskPriority.p3,
    TaskPriority.p4,
]
_PRIORITY_RANK = {priority: index for index, priority in enumerate(PRIORITY_ORDER)}


@dataclass
class CalculationResult:
    proposed_blocks: list[ProposedBlock] = field(default_factory=list)
    outcomes: list[TaskSchedulingOutcome] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    remaining_by_task: dict[UUID, int] = field(default_factory=dict)
    task_had_blocks: dict[UUID, bool] = field(default_factory=dict)
    minutes_by_project: dict[str, int] = field(default_factory=dict)
    placement_facts_by_task: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    tasks_scheduled: int = 0
    blocks_created: int = 0
    overbooked_count: int = 0


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _task_deadline_binds(
    task: Task,
    inputs: SchedulingInputs,
    *,
    not_before: datetime | None = None,
) -> bool:
    if task.deadline_at is None:
        return False
    deadline = _ensure_utc(task.deadline_at)
    bound = not_before if not_before is not None else inputs.horizon_start
    bound = _ensure_utc(bound)
    if bound >= deadline:
        return True
    if deadline <= inputs.horizon_start:
        return True
    return False


def _fixed_buffer_warning_hints(pass_hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hints that name a pre-existing tight fixed pair.

    This is a warning. It is not placement failure telemetry, and a later
    successful block must not drop it.
    """
    return [
        hint
        for hint in pass_hints
        if hint.get("reason_code") == REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER
    ]


def _retain_fixed_buffer_warning(
    task_id: UUID,
    *,
    observed: list[str],
    pass_hints: list[dict[str, Any]],
    observed_constraints_by_task: dict[UUID, list[str]],
    buffer_warning_hints_by_task: dict[UUID, list[dict[str, Any]]],
) -> None:
    hints = _fixed_buffer_warning_hints(pass_hints)
    if (
        not hints
        and REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER not in observed
    ):
        return
    observed_constraints_by_task[task_id] = _merge_constraint_codes(
        observed_constraints_by_task.get(task_id, []),
        [REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER],
    )
    if hints:
        buffer_warning_hints_by_task[task_id] = hints


def _merge_constraint_codes(
    existing: list[str],
    observed: list[str],
) -> list[str]:
    seen = set(existing)
    merged = list(existing)
    for code in observed:
        if code not in seen:
            merged.append(code)
            seen.add(code)
    return merged


def _reason_fact_for_constraint(
    code: str,
    *,
    task: Task,
    settings,
    remaining: int,
    daily_cap: int | None,
    cycle_task_ids: list[str],
) -> ReasonFact:
    params: dict[str, Any] = {"remaining_minutes": remaining}
    if code == REASON_UNPLACED_DEADLINE_LIMIT and task.deadline_at is not None:
        params["deadline_at"] = task.deadline_at.isoformat()
    if code == REASON_UNPLACED_PROJECT_DAILY_CAP and daily_cap is not None:
        params["daily_cap_minutes"] = daily_cap
    if code == REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK:
        mbl = task.min_block_duration_minutes or settings.default_min_block_duration_minutes
        params["min_block_minutes"] = mbl
    if code == REASON_BLOCKED_DEPENDENCY_CYCLE:
        params = {"cycle_task_ids": cycle_task_ids}
    return ReasonFact(code, params)


def _placement_facts_payload(
    inputs: SchedulingInputs,
    *,
    task_id: UUID,
    candidate: TaskCandidate,
    proposed_blocks: list[ProposedBlock],
    prerequisite_not_before: datetime | None,
    applicable_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task = candidate.task
    project = inputs.projects.get(task.project_id) if task.project_id else None
    epic = inputs.epics.get(project.epic_id) if project and project.epic_id else None
    window_id = inputs.effective_window_by_task.get(task_id)
    placed = [
        {
            "start_time": block.start_time.isoformat(),
            "end_time": block.end_time.isoformat(),
            "slice_minutes": block.slice_minutes,
            "tier": block.tier,
            "preferred_window_id": str(block.preferred_window_id)
            if block.preferred_window_id
            else None,
        }
        for block in proposed_blocks
        if block.task_id == task_id
    ]
    return {
        "timezone": inputs.user_settings.timezone,
        "horizon_start": inputs.horizon_start.isoformat(),
        "horizon_end": inputs.horizon_end.isoformat(),
        "schedule_style_source": effective_schedule_style_source(task, project, epic),
        "time_window_source": inputs.effective_window_source_by_task.get(task_id),
        "time_window_id": str(window_id) if window_id else None,
        "prerequisite_not_before": prerequisite_not_before.isoformat()
        if prerequisite_not_before is not None
        else None,
        "placed_blocks": placed,
        "applicable_override": applicable_override,
    }


def _blockers_by_dependent(
    dependencies: list[TaskDependency],
    candidate_ids: set[UUID],
) -> dict[UUID, list[UUID]]:
    blockers: dict[UUID, list[UUID]] = {task_id: [] for task_id in candidate_ids}
    for dep in dependencies:
        blocker = dep.blocking_task_id
        dependent = dep.dependent_task_id
        if dependent not in candidate_ids:
            continue
        blockers[dependent].append(blocker)
    return blockers


def _remaining_including_external_blockers(
    db: Session,
    owner_id: UUID,
    remaining_by_task: dict[UUID, int],
    blockers_by_dependent: dict[UUID, list[UUID]],
    *,
    now_utc: datetime,
    pinned_blocks_by_task: dict[UUID, list[ScheduledBlock]] | None = None,
) -> dict[UUID, int]:
    """Remaining minutes for blockers outside the candidate set.

    Pin coverage must come from the collect-time ``pinned_blocks_by_task``
    capture — a live pin reread can mark a prerequisite satisfied while the
    busy map and prerequisite-end seed still have no pin.
    """
    merged = dict(remaining_by_task)
    missing = {
        blocker_id
        for deps in blockers_by_dependent.values()
        for blocker_id in deps
        if blocker_id not in merged
    }
    if not missing:
        return merged
    pins_by_task = pinned_blocks_by_task or {}
    tasks = (
        db.query(Task)
        .filter(Task.owner_id == owner_id, Task.id.in_(missing))
        .all()
    )
    for task in tasks:
        if task.is_completed or task.deleted_at is not None:
            merged[task.id] = 0
            continue
        effort = placement_effort_minutes(task)
        reserved = reserved_minutes_from_blocks(pins_by_task.get(task.id, []), now_utc)
        # Excess reservation: nothing further to place. Do not clamp stored remaining.
        merged[task.id] = 0 if reserved > effort else effort - reserved
    for blocker_id in missing:
        merged.setdefault(blocker_id, 0)
    return merged


def _dependencies_ready(
    task_id: UUID,
    remaining_by_task: dict[UUID, int],
    blockers_by_dependent: dict[UUID, list[UUID]],
) -> bool:
    for blocker_id in blockers_by_dependent.get(task_id, []):
        if remaining_by_task.get(blocker_id, 0) > 0:
            return False
    return True


def _prerequisite_not_before(
    task_id: UUID,
    blockers_by_dependent: dict[UUID, list[UUID]],
    latest_block_end_by_task: dict[UUID, datetime],
    horizon_start: datetime,
) -> datetime:
    not_before = horizon_start
    for blocker_id in blockers_by_dependent.get(task_id, []):
        blocker_end = latest_block_end_by_task.get(blocker_id)
        if blocker_end is not None and blocker_end > not_before:
            not_before = blocker_end
    return not_before


def _placement_pass_order(
    candidates: list[TaskCandidate],
    ordered: list[TaskCandidate],
    ups_scores: dict[UUID, float],
) -> list[TaskCandidate]:
    topo_index = {item.task.id: index for index, item in enumerate(ordered)}
    return sorted(
        candidates,
        key=lambda item: (
            _PRIORITY_RANK.get(item.task.priority, len(PRIORITY_ORDER)),
            -ups_scores.get(item.task.id, 0.0),
            topo_index.get(item.task.id, len(ordered)),
        ),
    )


def _seed_prerequisite_block_ends(
    db: Session,
    owner_id: UUID,
    candidate_ids: set[UUID],
    horizon_start: datetime,
    horizon_end: datetime,
    *,
    pinned_blocks_by_task: dict[UUID, list[ScheduledBlock]] | None = None,
) -> dict[UUID, datetime]:
    """Seed prereq end times from blocks that survive apply.

    Apply wipes unpinned horizon blocks before writing proposals. Seeding from
    those doomed blocks delays dependents with no remaining justification.
    Newly proposed ends are merged into the map as placement succeeds.

    Prefer the collect-time ``pinned_blocks_by_task`` capture so pin minutes,
    busy, and fingerprints stay consistent.
    """
    latest: dict[UUID, datetime] = {}
    if not candidate_ids:
        return latest
    if pinned_blocks_by_task is not None:
        for task_id in candidate_ids:
            for block in pinned_blocks_by_task.get(task_id, []):
                if not (block.start_time < horizon_end and block.end_time > horizon_start):
                    continue
                prev = latest.get(task_id)
                if prev is None or block.end_time > prev:
                    latest[task_id] = block.end_time
        return latest
    blocks = (
        db.query(ScheduledBlock)
        .filter(
            ScheduledBlock.owner_id == owner_id,
            ScheduledBlock.task_id.in_(candidate_ids),
            ScheduledBlock.is_pinned.is_(True),
            ScheduledBlock.start_time < horizon_end,
            ScheduledBlock.end_time > horizon_start,
        )
        .all()
    )
    for block in blocks:
        if block.task_id is None:
            continue
        prev = latest.get(block.task_id)
        if prev is None or block.end_time > prev:
            latest[block.task_id] = block.end_time
    return latest


def _outcomes_for_lifecycle(
    items: list[LifecycleExcludedTask],
) -> list[TaskSchedulingOutcome]:
    outcomes: list[TaskSchedulingOutcome] = []
    for item in items:
        params: dict[str, Any] = {}
        if item.archived_scope:
            params["archived_scope"] = item.archived_scope
        outcomes.append(
            TaskSchedulingOutcome(
                task_id=item.task.id,
                requested_minutes=item.requested_minutes,
                pinned_minutes=0,
                placed_minutes=0,
                remaining_minutes=item.requested_minutes,
                reason_facts=[ReasonFact(item.reason_code, params)],
            )
        )
    return outcomes


def _outcomes_for_excluded(inputs: SchedulingInputs) -> list[TaskSchedulingOutcome]:
    outcomes: list[TaskSchedulingOutcome] = []
    for item in inputs.excluded_tasks:
        if item.schedule_style in {ScheduleStyle.bundle, ScheduleStyle.manual}:
            facts = [
                ReasonFact(
                    REASON_EXCLUDED_MANUAL_OR_BUNDLE,
                    {
                        "schedule_style": item.schedule_style.value,
                        "style_source": item.style_source,
                    },
                )
            ]
        elif item.reason_code:
            params = dict(item.reason_params)
            facts = [ReasonFact(item.reason_code, params)]
            for row in params.get("constraint_conflicts") or []:
                if not isinstance(row, dict):
                    continue
                code = row.get("code")
                if not code:
                    continue
                fact_params = dict(row.get("detail") or {})
                message = row.get("message")
                if message:
                    fact_params["message"] = message
                facts.append(ReasonFact(str(code), fact_params))
        else:
            facts = [
                ReasonFact(
                    REASON_EXCLUDED_DURATION_COVERED_BY_PINS,
                    {
                        "requested_minutes": item.requested_minutes,
                        "pinned_minutes": item.pinned_minutes,
                    },
                )
            ]
        outcomes.append(
            TaskSchedulingOutcome(
                task_id=item.task.id,
                requested_minutes=item.requested_minutes,
                pinned_minutes=item.pinned_minutes,
                placed_minutes=0,
                remaining_minutes=item.remaining_minutes,
                reason_facts=facts,
            )
        )
    return outcomes


def _finalize_candidate_outcomes(
    inputs: SchedulingInputs,
    *,
    ordered: list[TaskCandidate],
    remaining_by_task: dict[UUID, int],
    task_had_blocks: dict[UUID, bool],
    placed_minutes_by_task: dict[UUID, int],
    tiers_by_task: dict[UUID, list[str | None]],
    last_no_slot: dict[UUID, bool],
    blockers_by_dependent: dict[UUID, list[UUID]],
    observed_constraints_by_task: dict[UUID, list[str]],
    cycle_task_ids: set[UUID],
    cycle_members_by_task: dict[UUID, list[str]],
    placement_facts_by_task: dict[UUID, dict[str, Any]],
    prerequisite_not_before_by_task: dict[UUID, datetime],
    hint_params_by_task: dict[UUID, dict[str, dict[str, Any]]] | None = None,
    buffer_warning_hints_by_task: dict[UUID, list[dict[str, Any]]] | None = None,
) -> list[TaskSchedulingOutcome]:
    outcomes: list[TaskSchedulingOutcome] = []
    for candidate in ordered:
        task = candidate.task
        task_id = task.id
        requested = task.estimated_duration_minutes
        pinned = candidate.reserved_minutes
        remaining = remaining_by_task.get(task_id, 0)
        placed = placed_minutes_by_task.get(task_id, 0)

        if remaining <= 0 and task_had_blocks.get(task_id):
            tiers = [t for t in tiers_by_task.get(task_id, []) if t]
            tier = tiers[-1] if tiers else None
            window_id = inputs.effective_window_by_task.get(task_id)
            facts = [
                ReasonFact(
                    REASON_PLACED,
                    {
                        "placed_minutes": placed,
                        "tier": tier,
                        "time_window_id": str(window_id) if window_id else None,
                        "time_window_source": inputs.effective_window_source_by_task.get(
                            task_id
                        ),
                        "block_count": len(tiers_by_task.get(task_id, [])) or (1 if placed > 0 else 0),
                    },
                )
            ]
            for hint in (buffer_warning_hints_by_task or {}).get(task_id, []):
                facts.append(
                    ReasonFact(
                        REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER,
                        dict(hint.get("params") or {}),
                    )
                )
        elif remaining > 0:
            facts = []
            if task_id in cycle_task_ids:
                facts.append(
                    ReasonFact(
                        REASON_BLOCKED_DEPENDENCY_CYCLE,
                        {
                            "cycle_task_ids": cycle_members_by_task.get(
                                task_id, [str(task_id)]
                            )
                        },
                    )
                )
            elif not _dependencies_ready(task_id, remaining_by_task, blockers_by_dependent):
                blocking = [
                    str(bid)
                    for bid in blockers_by_dependent.get(task_id, [])
                    if remaining_by_task.get(bid, 0) > 0
                ]
                facts.append(
                    ReasonFact(
                        REASON_BLOCKED_PREREQUISITE,
                        {"blocking_task_ids": blocking},
                    )
                )

            constraints = [
                code
                for code in observed_constraints_by_task.get(task_id, [])
                if code
                not in {
                    REASON_BLOCKED_DEPENDENCY_CYCLE,
                    REASON_BLOCKED_PREREQUISITE,
                }
            ]
            if (
                REASON_UNPLACED_DEADLINE_LIMIT not in constraints
                and _task_deadline_binds(
                    task,
                    inputs,
                    not_before=prerequisite_not_before_by_task.get(task_id),
                )
            ):
                constraints.insert(0, REASON_UNPLACED_DEADLINE_LIMIT)

            if placed > 0:
                facts.append(
                    ReasonFact(
                        REASON_UNPLACED_HORIZON_EXHAUSTED,
                        {"remaining_minutes": remaining},
                    )
                )
            elif not facts and not constraints:
                if last_no_slot.get(task_id):
                    facts.append(
                        ReasonFact(
                            REASON_UNPLACED_NO_SLOT,
                            {"remaining_minutes": remaining},
                        )
                    )
                else:
                    facts.append(
                        ReasonFact(
                            REASON_UNPLACED_HORIZON_EXHAUSTED,
                            {"remaining_minutes": remaining},
                        )
                    )
            elif (
                placed <= 0
                and last_no_slot.get(task_id)
                and not facts
                and not constraints
            ):
                facts.append(
                    ReasonFact(
                        REASON_UNPLACED_NO_SLOT,
                        {"remaining_minutes": remaining},
                    )
                )

            hint_params = (hint_params_by_task or {}).get(task_id, {})
            for code in constraints:
                if code == REASON_UNPLACED_HORIZON_EXHAUSTED:
                    continue
                observed_params = hint_params.get(code)
                if observed_params is not None:
                    facts.append(ReasonFact(code, dict(observed_params)))
                    continue
                facts.append(
                    _reason_fact_for_constraint(
                        code,
                        task=task,
                        settings=inputs.user_settings,
                        remaining=remaining,
                        daily_cap=inputs.daily_cap,
                        cycle_task_ids=cycle_members_by_task.get(
                            task_id, [str(task_id)]
                        ),
                    )
                )
        else:
            facts = []

        outcomes.append(
            TaskSchedulingOutcome(
                task_id=task_id,
                requested_minutes=requested,
                pinned_minutes=pinned,
                placed_minutes=placed,
                remaining_minutes=remaining,
                reason_facts=facts,
                placement_facts=placement_facts_by_task.get(task_id),
            )
        )
    return outcomes


def calculate(
    db: Session,
    inputs: SchedulingInputs,
) -> CalculationResult:
    """Produce proposed blocks and per-task outcomes without writing blocks."""
    stats: dict[str, Any] = {
        "horizon_start": inputs.horizon_start.isoformat(),
        "horizon_end": inputs.horizon_end.isoformat(),
        "candidate_count": len(inputs.candidates),
    }
    stats.update(inputs.dependency_stats)

    ordered = inputs.ordered_candidates
    remaining_by_task = {item.task.id: item.remaining_minutes for item in inputs.candidates}

    cycle_task_ids_str = list(inputs.dependency_stats.get("cycle_task_ids") or [])
    cycle_task_ids = {UUID(value) for value in cycle_task_ids_str}
    cycle_members_by_task: dict[UUID, list[str]] = {}
    for group in inputs.dependency_stats.get("cycle_groups") or []:
        members = [str(value) for value in group]
        for member in members:
            cycle_members_by_task[UUID(member)] = members
    # Flat cycle_task_ids without groups (legacy stats): each member lists all.
    if cycle_task_ids and not cycle_members_by_task:
        for task_id in cycle_task_ids:
            cycle_members_by_task[task_id] = cycle_task_ids_str

    candidate_ids = {item.task.id for item in inputs.candidates}
    blockers_by_dependent = _blockers_by_dependent(inputs.dependencies, candidate_ids)
    remaining_by_task = _remaining_including_external_blockers(
        db,
        inputs.owner_id,
        remaining_by_task,
        blockers_by_dependent,
        now_utc=inputs.now_utc,
        pinned_blocks_by_task=inputs.pinned_blocks_by_task,
    )

    prereq_seed_ids = candidate_ids | {
        blocker_id
        for deps in blockers_by_dependent.values()
        for blocker_id in deps
    }
    latest_block_end_by_task = _seed_prerequisite_block_ends(
        db,
        inputs.owner_id,
        prereq_seed_ids,
        inputs.horizon_start,
        inputs.horizon_end,
        pinned_blocks_by_task=inputs.pinned_blocks_by_task,
    )

    busy: list[BusyInterval] = list(inputs.busy)
    project_daily_usage: ProjectDailyUsage = {}
    proposed_blocks: list[ProposedBlock] = []
    task_had_blocks: dict[UUID, bool] = {}
    placed_minutes_by_task: dict[UUID, int] = {}
    tiers_by_task: dict[UUID, list[str | None]] = {}
    last_no_slot: dict[UUID, bool] = {}
    observed_constraints_by_task: dict[UUID, list[str]] = {}
    failure_telemetry_by_task: dict[UUID, dict[str, Any]] = {}
    buffer_warning_hints_by_task: dict[UUID, list[dict[str, Any]]] = {}
    applicable_override_by_task: dict[UUID, dict[str, Any]] = {}
    prerequisite_not_before_by_task: dict[UUID, datetime] = {}
    minutes_by_project: dict[str, int] = {}
    blocks_created = 0

    placed_in_sweep = True
    while placed_in_sweep:
        placed_in_sweep = False
        ready = [
            candidate
            for candidate in ordered
            if remaining_by_task.get(candidate.task.id, 0) > 0
            and _dependencies_ready(
                candidate.task.id,
                remaining_by_task,
                blockers_by_dependent,
            )
        ]
        if not ready:
            break
        for candidate in _placement_pass_order(ready, ordered, inputs.ups_scores):
            task_id = candidate.task.id
            remaining = remaining_by_task.get(task_id, 0)
            if remaining <= 0:
                continue
            if task_id in cycle_task_ids:
                continue
            if not _dependencies_ready(
                task_id, remaining_by_task, blockers_by_dependent
            ):
                continue
            prereq_not_before = _prerequisite_not_before(
                task_id,
                blockers_by_dependent,
                latest_block_end_by_task,
                inputs.horizon_start,
            )
            result, busy = place_one_block(
                db,
                task=candidate.task,
                owner_id=inputs.owner_id,
                settings=inputs.user_settings,
                remaining_minutes=remaining,
                busy=busy,
                horizon_start=inputs.horizon_start,
                horizon_end=inputs.horizon_end,
                preferred_windows=inputs.preferred_windows,
                now_utc=inputs.now_utc,
                preferred_window_id=inputs.effective_window_by_task[task_id],
                project_daily_usage=project_daily_usage,
                daily_cap=inputs.daily_cap,
                prerequisite_not_before=prereq_not_before,
                persist_blocks=False,
                time_map_overrides_by_map=inputs.time_map_overrides_by_map,
                working_windows=inputs.working_windows,
                general_windows=inputs.general_windows,
            )
            prerequisite_not_before_by_task[task_id] = prereq_not_before
            if result.applicable_override is not None:
                applicable_override_by_task[task_id] = result.applicable_override
            remaining_by_task[task_id] = result.remaining_minutes
            # Tight fixed pairs are a warning, including when this block placed.
            # Failure telemetry is cleared on success below; this map is not.
            _retain_fixed_buffer_warning(
                task_id,
                observed=result.observed_constraints,
                pass_hints=result.pass_hints,
                observed_constraints_by_task=observed_constraints_by_task,
                buffer_warning_hints_by_task=buffer_warning_hints_by_task,
            )
            if result.blocks_created <= 0:
                observed_constraints_by_task[task_id] = _merge_constraint_codes(
                    observed_constraints_by_task.get(task_id, []),
                    result.observed_constraints,
                )
                if _task_deadline_binds(
                    candidate.task,
                    inputs,
                    not_before=prereq_not_before,
                ):
                    observed_constraints_by_task[task_id] = _merge_constraint_codes(
                        observed_constraints_by_task.get(task_id, []),
                        [REASON_UNPLACED_DEADLINE_LIMIT],
                    )
                # A task that never placed has no suitable slot. A later miss
                # after minutes were placed means the horizon could not take
                # the remainder. Do not let an earlier miss stick once placement
                # has started, or horizon exhaustion is unreachable.
                if (
                    remaining_by_task.get(task_id, 0) > 0
                    and placed_minutes_by_task.get(task_id, 0) <= 0
                ):
                    last_no_slot[task_id] = True
                failure_telemetry_by_task[task_id] = {
                    "last_failure": result.last_failure,
                    "pass_hints": list(result.pass_hints),
                }
                continue
            placed_in_sweep = True
            last_no_slot.pop(task_id, None)
            failure_telemetry_by_task.pop(task_id, None)
            task_had_blocks[task_id] = True
            blocks_created += result.blocks_created
            if result.proposed_blocks:
                proposed_blocks.extend(result.proposed_blocks)
                for block in result.proposed_blocks:
                    tiers_by_task.setdefault(task_id, []).append(block.tier)
            elif result.last_placed_tier is not None:
                tiers_by_task.setdefault(task_id, []).append(result.last_placed_tier)

            minutes_placed = remaining - result.remaining_minutes
            placed_minutes_by_task[task_id] = (
                placed_minutes_by_task.get(task_id, 0) + minutes_placed
            )
            if result.last_block_end is not None:
                prev_end = latest_block_end_by_task.get(task_id)
                if prev_end is None or result.last_block_end > prev_end:
                    latest_block_end_by_task[task_id] = result.last_block_end
            project_key = (
                str(candidate.task.project_id)
                if candidate.task.project_id
                else "inbox"
            )
            minutes_by_project[project_key] = (
                minutes_by_project.get(project_key, 0) + minutes_placed
            )

    overbooked_count = 0
    for candidate in ordered:
        task_id = candidate.task.id
        remaining = remaining_by_task.get(task_id, 0)
        if remaining > 0:
            overbooked_count += 1

    tasks_scheduled = len(task_had_blocks)
    if minutes_by_project:
        stats["minutes_by_project"] = minutes_by_project

    placement_facts_by_task: dict[UUID, dict[str, Any]] = {}
    for candidate in ordered:
        task_id = candidate.task.id
        placement_facts_by_task[task_id] = _placement_facts_payload(
            inputs,
            task_id=task_id,
            candidate=candidate,
            proposed_blocks=proposed_blocks,
            prerequisite_not_before=prerequisite_not_before_by_task.get(task_id),
            applicable_override=applicable_override_by_task.get(task_id),
        )
        telemetry = failure_telemetry_by_task.get(task_id)
        if telemetry and (telemetry.get("last_failure") or telemetry.get("pass_hints")):
            placement_facts_by_task[task_id]["last_failure"] = telemetry["last_failure"]
            placement_facts_by_task[task_id]["pass_hints"] = telemetry["pass_hints"]
        warning_hints = buffer_warning_hints_by_task.get(task_id) or []
        if warning_hints:
            existing_hints = list(placement_facts_by_task[task_id].get("pass_hints") or [])
            seen_codes = {
                hint.get("reason_code")
                for hint in existing_hints
                if isinstance(hint, dict)
            }
            for hint in warning_hints:
                code = hint.get("reason_code")
                if code not in seen_codes:
                    existing_hints.append(hint)
                    seen_codes.add(code)
            placement_facts_by_task[task_id]["pass_hints"] = existing_hints

    hint_params_by_task: dict[UUID, dict[str, dict[str, Any]]] = {}
    for task_id, telemetry in failure_telemetry_by_task.items():
        by_code: dict[str, dict[str, Any]] = {}
        for hint in telemetry.get("pass_hints") or []:
            code = hint.get("reason_code")
            params = hint.get("params")
            if code and isinstance(params, dict):
                by_code[str(code)] = dict(params)
        if by_code:
            hint_params_by_task[task_id] = by_code

    excluded_outcomes = _outcomes_for_excluded(inputs)
    lifecycle_outcomes = _outcomes_for_lifecycle(inputs.lifecycle_excluded_tasks)
    candidate_outcomes = _finalize_candidate_outcomes(
        inputs,
        ordered=ordered,
        remaining_by_task=remaining_by_task,
        task_had_blocks=task_had_blocks,
        placed_minutes_by_task=placed_minutes_by_task,
        tiers_by_task=tiers_by_task,
        last_no_slot=last_no_slot,
        blockers_by_dependent=blockers_by_dependent,
        observed_constraints_by_task=observed_constraints_by_task,
        cycle_task_ids=cycle_task_ids,
        cycle_members_by_task=cycle_members_by_task,
        placement_facts_by_task=placement_facts_by_task,
        prerequisite_not_before_by_task=prerequisite_not_before_by_task,
        hint_params_by_task=hint_params_by_task,
        buffer_warning_hints_by_task=buffer_warning_hints_by_task,
    )

    return CalculationResult(
        proposed_blocks=proposed_blocks,
        outcomes=excluded_outcomes + lifecycle_outcomes + candidate_outcomes,
        stats=stats,
        remaining_by_task=remaining_by_task,
        task_had_blocks=task_had_blocks,
        minutes_by_project=minutes_by_project,
        placement_facts_by_task=placement_facts_by_task,
        tasks_scheduled=tasks_scheduled,
        blocks_created=blocks_created,
        overbooked_count=overbooked_count,
    )
