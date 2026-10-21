"""T2-S1 hard start occurrence bounds (single-block path)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.models import ScheduledBlock, Task, UserSettings
from app.scheduler.reasons import (
    REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT,
    REASON_OCCURRENCE_BOUNDS_HORIZON,
    REASON_OCCURRENCE_BOUNDS_MISS,
    REASON_OCCURRENCE_BOUNDS_NO_SLOT,
    REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT,
    REASON_OCCURRENCE_BOUNDS_UNSUPPORTED_SHAPE,
    ReasonFact,
)
from app.services.chunking_effective import resolve_block_bounds

DETAIL_SPLIT_NOT_IN_T2_S1 = "split_not_in_T2_S1"


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def has_occurrence_bounds(task: Task) -> bool:
    return task.start_no_earlier_at is not None or task.start_no_later_at is not None


def effective_latest_start(
    task: Task,
    *,
    effort_minutes: int,
) -> datetime | None:
    latest = _utc(task.start_no_later_at)
    deadline = _utc(task.deadline_at)
    candidates: list[datetime] = []
    if latest is not None:
        candidates.append(latest)
    if deadline is not None and effort_minutes > 0:
        candidates.append(deadline - timedelta(minutes=effort_minutes))
    if not candidates:
        return None
    return min(candidates)


def earliest_start_bound(task: Task) -> datetime | None:
    return _utc(task.start_no_earlier_at)


def geometry_infeasible(task: Task, *, effort_minutes: int) -> bool:
    earliest = earliest_start_bound(task)
    deadline = _utc(task.deadline_at)
    if earliest is None or deadline is None or effort_minutes <= 0:
        return False
    return earliest + timedelta(minutes=effort_minutes) > deadline


def _block_intervals(blocks: list[ScheduledBlock]) -> list[tuple[datetime, datetime]]:
    rows: list[tuple[datetime, datetime]] = []
    for block in blocks:
        start = _utc(block.start_time)
        end = _utc(block.end_time)
        if start is None or end is None:
            continue
        rows.append((start, end))
    return rows


def pin_bounds_conflict(
    task: Task,
    *,
    pin_intervals: list[tuple[datetime, datetime]],
) -> bool:
    earliest = earliest_start_bound(task)
    latest = effective_latest_start(task, effort_minutes=1)
    if earliest is None and latest is None:
        return False
    for start, end in pin_intervals:
        pin_start, pin_end = start, end
        if earliest is not None and pin_end <= earliest:
            continue
        if latest is not None and pin_start > latest:
            continue
        if earliest is not None and pin_start < earliest:
            return True
        if latest is not None and pin_start > latest:
            return True
    return False


def in_flight_hold_trigger(
    task: Task,
    *,
    reserved_minutes: int,
    pin_intervals: list[tuple[datetime, datetime]],
    scheduled_intervals: list[tuple[datetime, datetime]],
    now_utc: datetime,
) -> bool:
    if int(task.worked_minutes or 0) > 0:
        return True
    if reserved_minutes > 0 or pin_intervals:
        return True
    now = _utc(now_utc) or datetime.now(timezone.utc)
    for start, _end in scheduled_intervals:
        if start <= now:
            return True
    return False


def unsupported_shape(task: Task, settings: UserSettings, *, effort_minutes: int) -> bool:
    bounds = resolve_block_bounds(task, settings)
    if bounds.keep_in_one_block and bounds.effective_max_minutes is not None:
        if effort_minutes > bounds.effective_max_minutes:
            return True
    if not bounds.keep_in_one_block:
        max_block = None if bounds.max_unbounded else bounds.effective_max_minutes
        if max_block is not None and effort_minutes > max_block:
            return True
    return False


def _feasible_start_exists_in_horizon(
    task: Task,
    *,
    effort_minutes: int,
    horizon_start: datetime,
    horizon_end: datetime,
) -> bool:
    earliest = earliest_start_bound(task) or horizon_start
    latest = effective_latest_start(task, effort_minutes=effort_minutes)
    if latest is None:
        latest = horizon_end - timedelta(minutes=effort_minutes)
    deadline = _utc(task.deadline_at)
    hs = _utc(horizon_start) or horizon_start
    he = _utc(horizon_end) or horizon_end
    if earliest > latest:
        return False
    # Quick probe: latest feasible start must fit completion inside horizon and deadline.
    start_hi = latest
    start_lo = max(earliest, hs)
    if start_hi < start_lo:
        return False
    finish_cap = he
    if deadline is not None:
        finish_cap = min(finish_cap, deadline)
    if start_lo + timedelta(minutes=effort_minutes) > finish_cap:
        return False
    if start_hi + timedelta(minutes=effort_minutes) > finish_cap:
        return False
    return start_lo <= start_hi


def horizon_blocks_placement(
    task: Task,
    *,
    effort_minutes: int,
    horizon_start: datetime,
    horizon_end: datetime,
) -> bool:
    if not has_occurrence_bounds(task):
        return False
    return not _feasible_start_exists_in_horizon(
        task,
        effort_minutes=effort_minutes,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    )


@dataclass
class OccurrenceBoundsDecision:
    skip_new_placement: bool = False
    primary_code: str | None = None
    secondary_codes: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)

    def reason_facts(self) -> list[ReasonFact]:
        facts: list[ReasonFact] = []
        if self.primary_code:
            facts.append(ReasonFact(self.primary_code, dict(self.params)))
        for code in self.secondary_codes:
            facts.append(ReasonFact(code, dict(self.params)))
        return facts


def evaluate_occurrence_bounds(
    task: Task,
    settings: UserSettings,
    *,
    effort_minutes: int,
    reserved_minutes: int,
    pin_blocks: list[ScheduledBlock],
    scheduled_blocks: list[ScheduledBlock],
    horizon_start: datetime,
    horizon_end: datetime,
    now_utc: datetime,
) -> OccurrenceBoundsDecision:
    if not has_occurrence_bounds(task):
        return OccurrenceBoundsDecision()
    pin_intervals = _block_intervals(pin_blocks)
    scheduled_intervals = _block_intervals(scheduled_blocks)
    params: dict[str, Any] = {
        "start_no_earlier_at": _utc(task.start_no_earlier_at).isoformat()
        if task.start_no_earlier_at
        else None,
        "start_no_later_at": _utc(task.start_no_later_at).isoformat()
        if task.start_no_later_at
        else None,
        "effective_latest_start": (
            effective_latest_start(task, effort_minutes=effort_minutes).isoformat()
            if effective_latest_start(task, effort_minutes=effort_minutes)
            else None
        ),
    }
    secondaries: list[str] = []
    if pin_bounds_conflict(task, pin_intervals=pin_intervals):
        secondaries.append(REASON_OCCURRENCE_BOUNDS_PIN_CONFLICT)

    if in_flight_hold_trigger(
        task,
        reserved_minutes=reserved_minutes,
        pin_intervals=pin_intervals,
        scheduled_intervals=scheduled_intervals,
        now_utc=now_utc,
    ):
        return OccurrenceBoundsDecision(
            skip_new_placement=True,
            primary_code=REASON_OCCURRENCE_BOUNDS_HOLD_INFLIGHT,
            secondary_codes=secondaries,
            params=params,
        )

    if unsupported_shape(task, settings, effort_minutes=effort_minutes):
        params["detail"] = DETAIL_SPLIT_NOT_IN_T2_S1
        return OccurrenceBoundsDecision(
            skip_new_placement=True,
            primary_code=REASON_OCCURRENCE_BOUNDS_UNSUPPORTED_SHAPE,
            secondary_codes=secondaries,
            params=params,
        )

    latest = effective_latest_start(task, effort_minutes=effort_minutes)
    now = _utc(now_utc) or datetime.now(timezone.utc)
    if latest is not None and latest < now:
        return OccurrenceBoundsDecision(
            skip_new_placement=True,
            primary_code=REASON_OCCURRENCE_BOUNDS_MISS,
            secondary_codes=secondaries,
            params=params,
        )

    if geometry_infeasible(task, effort_minutes=effort_minutes):
        return OccurrenceBoundsDecision(
            skip_new_placement=True,
            primary_code=REASON_OCCURRENCE_BOUNDS_NO_SLOT,
            secondary_codes=secondaries,
            params=params,
        )

    if horizon_blocks_placement(
        task,
        effort_minutes=effort_minutes,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
    ):
        return OccurrenceBoundsDecision(
            skip_new_placement=True,
            primary_code=REASON_OCCURRENCE_BOUNDS_HORIZON,
            secondary_codes=secondaries,
            params=params,
        )

    return OccurrenceBoundsDecision(secondary_codes=secondaries, params=params)


def load_scheduled_blocks_in_horizon(
    blocks: list[ScheduledBlock],
    *,
    horizon_start: datetime,
    horizon_end: datetime,
) -> list[ScheduledBlock]:
    hs = _utc(horizon_start) or horizon_start
    he = _utc(horizon_end) or horizon_end
    kept: list[ScheduledBlock] = []
    for block in blocks:
        start = _utc(block.start_time)
        end = _utc(block.end_time)
        if start is None or end is None:
            continue
        if start < he and end > hs:
            kept.append(block)
    return kept


def scheduled_blocks_by_task(
    blocks: list[ScheduledBlock],
    task_ids: set[UUID],
) -> dict[UUID, list[ScheduledBlock]]:
    out: dict[UUID, list[ScheduledBlock]] = {}
    for block in blocks:
        if block.task_id not in task_ids:
            continue
        out.setdefault(block.task_id, []).append(block)
    return out
