"""Future-tail pin reservation and keep-in-one placement budget (S2-V2 / S0 §2).

Reservation is evaluated at the run's ``now``. It is not stored on the block.
Busy-map occupancy stays the full pin interval so auto blocks cannot land on it.
Reservation is subtracted once from remaining effort. Pins are never resized,
extended, moved, unpinned, or merged here.

SS-30 / A15 is not closed by this module. Buffer minutes are not reservation
and not remaining work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.scheduler.placement import is_workday, workday_bounds
from app.scheduler.reasons import (
    REASON_EXCLUDED_DURATION_COVERED_BY_PINS,
    REASON_EXCLUDED_KEEP_IN_ONE_RESERVED,
    REASON_OUTSIDE_WORKING_AVAILABILITY,
    REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT,
    REASON_UNPLACED_KEEP_IN_ONE_CONFLICT,
    REASON_UNPLACED_PIN_RESERVATION_EXCESS,
)
from app.scheduler.task_effort import placement_effort_minutes
from app.services.chunking_effective import ResolvedBlockBounds, resolve_block_bounds

# Product codes for effective-read conflicts (KeepInOneSchedulingConflictOut.code).
CONFLICT_SHORTER_PIN = "keep_in_one_shorter_pin"
CONFLICT_EXCESS_PIN = "keep_in_one_excess_pin"
CONFLICT_MULTIPLE_PINS = "keep_in_one_multiple_pins"
CONFLICT_EXCEEDS_MAX = "keep_in_one_exceeds_max"
CONFLICT_BOUNDS = "block_bounds_conflict"
# Same code as the secondary outcome fact. Exact cover is not full validity.
CONFLICT_OUTSIDE_WORKING = REASON_OUTSIDE_WORKING_AVAILABILITY


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def duration_minutes(start: datetime, end: datetime) -> int:
    delta = _utc(end) - _utc(start)
    minutes = int(delta.total_seconds() // 60)
    return minutes if minutes > 0 else 0


def reservation_minutes(start: datetime, end: datetime, now: datetime) -> int:
    """Minutes of a pin that reserve remaining effort at ``now``.

    Past (``end <= now``) reserves 0. Future (``start >= now``) reserves the
    full duration. In progress reserves only ``now`` → ``end``. The elapsed
    head is not worked and not reserved.
    """
    start_utc = _utc(start)
    end_utc = _utc(end)
    now_utc = _utc(now)
    if end_utc <= now_utc:
        return 0
    if start_utc >= now_utc:
        return duration_minutes(start_utc, end_utc)
    return duration_minutes(now_utc, end_utc)


def _interval(block: Any) -> tuple[datetime, datetime] | None:
    if isinstance(block, dict):
        start = block.get("start_time", block.get("start"))
        end = block.get("end_time", block.get("end"))
    else:
        start = getattr(block, "start_time", None)
        end = getattr(block, "end_time", None)
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    return start, end


def reserved_minutes_from_blocks(blocks: list[Any], now: datetime) -> int:
    """Sum of future-tail reservations. Unpinned callers must not pass those rows."""
    total = 0
    for block in blocks:
        interval = _interval(block)
        if interval is None:
            continue
        total += reservation_minutes(interval[0], interval[1], now)
    return total


def _relevant_reservations(blocks: list[Any], now: datetime) -> list[int]:
    relevant: list[int] = []
    for block in blocks:
        interval = _interval(block)
        if interval is None:
            continue
        reserved = reservation_minutes(interval[0], interval[1], now)
        if reserved > 0:
            relevant.append(reserved)
    return relevant


def _conflict(code: str, message: str, **detail: Any) -> dict[str, Any]:
    payload = {
        "pins_protected": True,
        "automatic_work_minutes": 0,
    }
    payload.update(detail)
    return {"code": code, "message": message, "detail": payload}


@dataclass(frozen=True)
class AutoPlacementDecision:
    """Minutes the placer may add. Pins are never mutated by this decision."""

    effort_minutes: int
    reserved_minutes: int
    minutes_to_place: int
    auto_place: bool
    reason_code: str | None = None
    reason_params: dict[str, Any] = field(default_factory=dict)
    conflicts: tuple[dict[str, Any], ...] = ()
    # Outcome row "still unplaced" minutes. Excess does not clamp effort;
    # ``effort_minutes`` stays the remaining estimate.
    outcome_remaining_minutes: int = 0


def _params(effort: int, reserved: int, **extra: Any) -> dict[str, Any]:
    body = {
        "remaining_minutes": effort,
        "remaining_estimate_minutes": effort,
        "reserved_minutes": reserved,
        "pins_protected": True,
        "clamped": False,
    }
    body.update(extra)
    return body


def context_reservation_conflicts(
    task: Any,
    settings: Any,
    blocks: list[Any],
    now: datetime,
) -> tuple[dict[str, Any], ...]:
    """Context and event-travel conflicts for a pinned reservation.

    S2-D3 keeps this hook and returns none. Later inputs append conflicts
    here. Callers can also pass ``context_conflicts`` into
    ``evaluate_auto_placement`` when those inputs already exist.
    """
    del task, settings, blocks, now
    return ()


def _working_configured(settings: Any) -> bool:
    start = getattr(settings, "workday_start_local", None)
    minutes = getattr(settings, "workday_minutes", None)
    weekdays = getattr(settings, "workweek_days", None)
    return start is not None and isinstance(minutes, int) and weekdays is not None


def _zone(settings: Any) -> ZoneInfo | None:
    name = getattr(settings, "timezone", None) or "UTC"
    try:
        return ZoneInfo(str(name))
    except (KeyError, ValueError):
        return None


def _reserved_span(
    start: datetime, end: datetime, now: datetime
) -> tuple[datetime, datetime] | None:
    """Future tail of a pin. The elapsed head is not the relevant reservation."""
    start_utc = _utc(start)
    end_utc = _utc(end)
    now_utc = _utc(now)
    if end_utc <= now_utc or end_utc <= start_utc:
        return None
    reserved_start = now_utc if start_utc < now_utc else start_utc
    if reserved_start >= end_utc:
        return None
    return reserved_start, end_utc


def _merge_intervals(
    windows: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    ordered = sorted(windows, key=lambda item: (item[0], item[1]))
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for window_start, window_end in ordered[1:]:
        last_start, last_end = merged[-1]
        if window_start <= last_end:
            merged[-1] = (last_start, max(last_end, window_end))
        else:
            merged.append((window_start, window_end))
    return merged


def _uncovered_outside_working(
    start: datetime,
    end: datetime,
    settings: Any,
) -> list[tuple[datetime, datetime]] | None:
    """Sub-intervals of ``[start, end)`` that miss eligible Working time.

    ``None`` means Working fields are missing or the zone is unusable, so
    this call does not report a conflict. An empty list means the interval
    is fully contained, including a reservation that ends on the window
    boundary. Wholly outside and partial overlap both return the uncovered
    gaps. Sharing some time with a window is not full containment.
    """
    if not _working_configured(settings):
        return None
    tz = _zone(settings)
    if tz is None:
        return None
    start_utc = _utc(start)
    end_utc = _utc(end)
    if end_utc <= start_utc:
        return None
    day: date = start_utc.astimezone(tz).date() - timedelta(days=1)
    last = end_utc.astimezone(tz).date()
    workweek = int(settings.workweek_days)
    covered: list[tuple[datetime, datetime]] = []
    while day <= last:
        if is_workday(day, workweek):
            window_start, window_end = workday_bounds(day, settings, tz)
            clip_start = max(start_utc, window_start)
            clip_end = min(end_utc, window_end)
            if clip_start < clip_end:
                covered.append((clip_start, clip_end))
        day += timedelta(days=1)
    uncovered: list[tuple[datetime, datetime]] = []
    cursor = start_utc
    for window_start, window_end in _merge_intervals(covered):
        if cursor < window_start:
            uncovered.append((cursor, window_start))
        if window_end > cursor:
            cursor = window_end
    if cursor < end_utc:
        uncovered.append((cursor, end_utc))
    return uncovered


def _relevant_pin_intervals(blocks: list[Any], now: datetime) -> list[tuple[datetime, datetime]]:
    intervals: list[tuple[datetime, datetime]] = []
    for block in blocks:
        interval = _interval(block)
        if interval is None:
            continue
        if reservation_minutes(interval[0], interval[1], now) > 0:
            intervals.append(interval)
    return intervals


def _outside_working_conflict(
    settings: Any,
    blocks: list[Any],
    now: datetime,
    effort: int,
    reserved: int,
) -> dict[str, Any] | None:
    outside: list[dict[str, str]] = []
    for start, end in _relevant_pin_intervals(blocks, now):
        span = _reserved_span(start, end, now)
        if span is None:
            continue
        uncovered = _uncovered_outside_working(span[0], span[1], settings)
        if not uncovered:
            continue
        for gap_start, gap_end in uncovered:
            outside.append({"start": gap_start.isoformat(), "end": gap_end.isoformat()})
    if not outside:
        return None
    return _conflict(
        CONFLICT_OUTSIDE_WORKING,
        (
            "Pinned reservation is outside Working availability. "
            "The pin was preserved and no automatic work was added."
        ),
        arrangement="outside_working",
        remaining_minutes=effort,
        reserved_minutes=reserved,
        outside_intervals=outside,
    )


def independent_reservation_conflicts(
    *,
    task: Any,
    settings: Any,
    blocks: list[Any],
    now: datetime,
    effort: int,
    reserved: int,
    context_conflicts: tuple[dict[str, Any], ...] = (),
) -> tuple[dict[str, Any], ...]:
    """Constraints that stay independent of keep-in-one shape (§0.1).

    Working availability is evaluated now. Context conflicts come from
    ``context_reservation_conflicts`` and from ``context_conflicts``.
    """
    rows: list[dict[str, Any]] = []
    outside = _outside_working_conflict(settings, blocks, now, effort, reserved)
    if outside is not None:
        rows.append(outside)
    rows.extend(context_reservation_conflicts(task, settings, blocks, now))
    rows.extend(context_conflicts)
    return tuple(rows)


def evaluate_auto_placement(
    task: Any,
    settings: Any,
    blocks: list[Any],
    now: datetime,
    *,
    context_conflicts: tuple[dict[str, Any], ...] = (),
) -> AutoPlacementDecision:
    """Remaining minus future-tail reservation, then keep-in-one × pin rules.

    Excess reservation yields zero automatic minutes and does not clamp the
    remaining estimate or shorten the pin. A keep-in-one conflict adds no
    automatic remainder. Final placement of a legal short remainder is the
    placer's slice rule, not this budget.

    Exact keep-in-one cover still reports independent constraints. Working
    availability is checked when settings carry workday fields. A relevant
    reservation that is not fully contained — wholly outside or only partly
    overlapping — reports the uncovered portion. A pin that ends on the
    window boundary is contained. Pass ``context_conflicts`` for later
    context inputs; this function does not invent them.
    """
    bounds = resolve_block_bounds(task, settings)
    effort = placement_effort_minutes(task)
    if effort < 0:
        effort = 0
    reserved = reserved_minutes_from_blocks(blocks, now)
    relevant = _relevant_reservations(blocks, now)
    conflicts = _keep_in_one_conflicts(bounds, effort, reserved, relevant)

    if bounds.bounds_conflict() and not bounds.keep_in_one_block:
        return AutoPlacementDecision(
            effort_minutes=effort,
            reserved_minutes=reserved,
            minutes_to_place=0,
            auto_place=False,
            reason_code=REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT,
            reason_params=_params(
                effort,
                reserved,
                min_block_minutes=bounds.effective_min_minutes,
                max_block_minutes=bounds.effective_max_minutes,
                min_source=bounds.min_source,
                max_source=bounds.max_source,
            ),
            conflicts=(),
            outcome_remaining_minutes=effort,
        )

    if bounds.keep_in_one_block:
        independent: tuple[dict[str, Any], ...] = ()
        if not conflicts and len(relevant) == 1 and relevant[0] == effort:
            independent = independent_reservation_conflicts(
                task=task,
                settings=settings,
                blocks=blocks,
                now=now,
                effort=effort,
                reserved=reserved,
                context_conflicts=context_conflicts,
            )
        return _keep_in_one_decision(
            bounds, effort, reserved, relevant, conflicts, independent
        )

    if reserved > effort:
        excess = reserved - effort
        return AutoPlacementDecision(
            effort_minutes=effort,
            reserved_minutes=reserved,
            minutes_to_place=0,
            auto_place=False,
            reason_code=REASON_UNPLACED_PIN_RESERVATION_EXCESS,
            reason_params=_params(effort, reserved, excess_minutes=excess),
            conflicts=(),
            outcome_remaining_minutes=0,
        )

    minutes_to_place = effort - reserved
    if minutes_to_place <= 0:
        return AutoPlacementDecision(
            effort_minutes=effort,
            reserved_minutes=reserved,
            minutes_to_place=0,
            auto_place=False,
            reason_code=REASON_EXCLUDED_DURATION_COVERED_BY_PINS,
            reason_params={
                "requested_minutes": effort,
                "pinned_minutes": reserved,
            },
            conflicts=(),
            outcome_remaining_minutes=0,
        )

    return AutoPlacementDecision(
        effort_minutes=effort,
        reserved_minutes=reserved,
        minutes_to_place=minutes_to_place,
        auto_place=True,
        reason_code=None,
        reason_params={},
        conflicts=(),
        outcome_remaining_minutes=minutes_to_place,
    )


def _keep_in_one_conflicts(
    bounds: ResolvedBlockBounds,
    effort: int,
    reserved: int,
    relevant: list[int],
) -> tuple[dict[str, Any], ...]:
    if not bounds.keep_in_one_block:
        return ()
    rows: list[dict[str, Any]] = []
    if bounds.bounds_conflict():
        rows.append(
            _conflict(
                CONFLICT_BOUNDS,
                (
                    f"Effective minimum block ({bounds.effective_min_minutes} min) exceeds "
                    f"effective maximum ({bounds.effective_max_minutes} min)."
                ),
                min_block_minutes=bounds.effective_min_minutes,
                max_block_minutes=bounds.effective_max_minutes,
                remaining_minutes=effort,
                reserved_minutes=reserved,
            )
        )
    if len(relevant) >= 2:
        rows.append(
            _conflict(
                CONFLICT_MULTIPLE_PINS,
                (
                    "Pinned reservations are separate blocks and cannot satisfy "
                    "keep-in-one. They were not combined, moved, or supplemented."
                ),
                arrangement="multiple",
                relevant_pin_count=len(relevant),
                remaining_minutes=effort,
                reserved_minutes=reserved,
            )
        )
    elif len(relevant) == 1:
        one = relevant[0]
        if one > effort:
            rows.append(
                _conflict(
                    CONFLICT_EXCESS_PIN,
                    (
                        f"Pinned reservation ({one} minutes) exceeds remaining effort "
                        f"({effort} minutes). The pin was not shortened and remaining "
                        "was not clamped."
                    ),
                    arrangement="excess",
                    remaining_minutes=effort,
                    reserved_minutes=one,
                    excess_minutes=one - effort,
                )
            )
        elif one < effort:
            rows.append(
                _conflict(
                    CONFLICT_SHORTER_PIN,
                    (
                        f"This task needs one {effort}-minute block, but its pinned "
                        f"block reserves {one} minutes."
                    ),
                    arrangement="shorter",
                    remaining_minutes=effort,
                    reserved_minutes=one,
                )
            )
    max_minutes = bounds.effective_max_minutes
    if (
        not bounds.max_unbounded
        and max_minutes is not None
        and effort > max_minutes
        and len(relevant) == 0
    ):
        rows.append(
            _conflict(
                CONFLICT_EXCEEDS_MAX,
                (
                    "Keep-in-one needs one block for the remaining effort, which "
                    f"exceeds the effective maximum ({max_minutes} minutes)."
                ),
                arrangement="exceeds_max",
                remaining_minutes=effort,
                max_block_minutes=max_minutes,
                reserved_minutes=reserved,
            )
        )
    return tuple(rows)


def _keep_in_one_decision(
    bounds: ResolvedBlockBounds,
    effort: int,
    reserved: int,
    relevant: list[int],
    conflicts: tuple[dict[str, Any], ...],
    independent_conflicts: tuple[dict[str, Any], ...] = (),
) -> AutoPlacementDecision:
    """Whole unfinished task, including relevant pins. No auto remainder on conflict."""
    if conflicts:
        primary = conflicts[0]
        code = primary["code"]
        if code == CONFLICT_BOUNDS:
            reason = REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT
            arrangement = "bounds"
        elif code == CONFLICT_EXCESS_PIN:
            reason = REASON_UNPLACED_PIN_RESERVATION_EXCESS
            arrangement = "excess"
        else:
            reason = REASON_UNPLACED_KEEP_IN_ONE_CONFLICT
            arrangement = str(primary.get("detail", {}).get("arrangement") or code)
        gap = effort - reserved if reserved <= effort else effort
        outcome_remaining = 0 if arrangement == "excess" else (effort if arrangement == "bounds" else gap)
        if arrangement == "exceeds_max":
            outcome_remaining = effort
        return AutoPlacementDecision(
            effort_minutes=effort,
            reserved_minutes=reserved,
            minutes_to_place=0,
            auto_place=False,
            reason_code=reason,
            reason_params=_params(
                effort,
                reserved,
                arrangement=arrangement,
                conflict_code=code,
                requested_minutes=effort,
                pinned_minutes=reserved,
            ),
            conflicts=conflicts,
            outcome_remaining_minutes=outcome_remaining,
        )

    if len(relevant) == 1 and relevant[0] == effort:
        # One-block shape is not full validity. Keep the pin, add no automatic
        # work, and still report independent constraints (availability now,
        # context when that hook grows).
        params: dict[str, Any] = {
            "requested_minutes": effort,
            "pinned_minutes": reserved,
            "remaining_minutes": effort,
            "pins_protected": True,
        }
        if independent_conflicts:
            params["constraint_conflicts"] = [
                {
                    "code": row["code"],
                    "message": row["message"],
                    "detail": dict(row.get("detail") or {}),
                }
                for row in independent_conflicts
            ]
        return AutoPlacementDecision(
            effort_minutes=effort,
            reserved_minutes=reserved,
            minutes_to_place=0,
            auto_place=False,
            reason_code=REASON_EXCLUDED_KEEP_IN_ONE_RESERVED,
            reason_params=params,
            conflicts=independent_conflicts,
            outcome_remaining_minutes=0,
        )

    if effort <= 0:
        return AutoPlacementDecision(
            effort_minutes=effort,
            reserved_minutes=reserved,
            minutes_to_place=0,
            auto_place=False,
            reason_code=REASON_EXCLUDED_DURATION_COVERED_BY_PINS,
            reason_params={"requested_minutes": effort, "pinned_minutes": reserved},
            conflicts=(),
            outcome_remaining_minutes=0,
        )

    # No relevant pin (past pins reserve 0 and do not block a new single block).
    return AutoPlacementDecision(
        effort_minutes=effort,
        reserved_minutes=reserved,
        minutes_to_place=effort,
        auto_place=True,
        reason_code=None,
        reason_params={},
        conflicts=(),
        outcome_remaining_minutes=effort,
    )
