"""Bounded A14c Prefer-versus-fallback counterfactual.

One collected horizon. Compare the preference-selected placement (Prefer
windows across the horizon, then eligible) with the eligible-only fallback.
One repair step. Hard requirements and pins are not weakened. This is not a
global search.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

DECISION_PREFER = "prefer"
DECISION_DEADLINE_FALLBACK = "deadline_fallback"
DECISION_HIGHER_RANKED = "higher_ranked_competition"
DECISION_HARD = "hard_infeasibility"
DECISION_WINDOW_UNAVAILABLE = "preference_window_unavailable"
DECISION_BOUND_EXHAUSTED = "bound_exhausted"

RANK_MODE_PREFER = "prefer_first"
RANK_MODE_ELIGIBLE = "eligible_only"


@dataclass(frozen=True)
class HigherRankedTask:
    """A not-yet-placed task earlier in priority, then UPS, then stable tie."""

    task: Any
    remaining_minutes: int
    composition: Any
    prerequisite_not_before: datetime | None = None
    blocked_by_subject: bool = False
    general_windows: Any = None
    working_windows: Any = None


@dataclass(frozen=True)
class RankingChoice:
    mode: str
    decision: str
    bound_exhausted: bool = False
    competing_task_id: str | None = None
    hard_constraints_protected: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": self.decision,
            "rank_mode": self.mode,
            "bound_exhausted": self.bound_exhausted,
            "hard_constraints_protected": self.hard_constraints_protected,
        }
        if self.competing_task_id is not None:
            payload["competing_task_id"] = self.competing_task_id
        return payload


def _deadline(task: Any) -> datetime | None:
    value = getattr(task, "deadline_at", None)
    if value is None:
        return None
    if value.tzinfo is None:
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc)
    return value


def _misses(result: Any, deadline: datetime | None) -> bool:
    if deadline is None:
        return False
    if result.remaining_minutes > 0:
        return True
    end = result.last_block_end
    return end is not None and end > deadline


def _completes(result: Any, deadline: datetime | None) -> bool:
    if result.remaining_minutes > 0:
        return False
    if result.blocks_created <= 0 and result.remaining_minutes == 0:
        return False
    end = result.last_block_end
    if deadline is not None and end is not None and end > deadline:
        return False
    return True


def _future_windows(
    *,
    composition: Any,
    tz: Any,
    horizon_start: datetime,
    horizon_end: datetime,
    general_windows: Any,
) -> list[tuple[Any, Any, str]]:
    from datetime import timedelta

    from app.scheduler.composition import composition_search_windows

    found: list[tuple[Any, Any, str]] = []
    day = horizon_start.astimezone(tz).date()
    last = horizon_end.astimezone(tz).date()
    while day <= last:
        for window in composition_search_windows(day, tz, composition, general_windows):
            if window[1] > horizon_start:
                found.append(window)
        day += timedelta(days=1)
    return found


def _windows_blocked(windows: Sequence[tuple[Any, Any, str]], busy: Sequence[Any]) -> bool:
    """True when every future window is covered by busy or a pin. Prefer does not punch a hole."""
    if not windows:
        return False
    for start, end, _label in windows:
        if not any(item.start <= start and item.end >= end for item in busy):
            return False
    return True


def choose_rank_mode(
    *,
    db: Any,
    task: Any,
    owner_id: Any,
    settings: Any,
    remaining_minutes: int,
    busy: list[Any],
    horizon_start: datetime,
    horizon_end: datetime,
    preferred_windows: Any,
    now_utc: datetime,
    preferred_window_id: Any,
    project_daily_usage: Any,
    daily_cap: int | None,
    prerequisite_not_before: datetime | None,
    time_map_overrides_by_map: Any,
    working_windows: Any,
    general_windows: Any,
    composition: Any,
    higher_ranked: Sequence[HigherRankedTask] = (),
) -> RankingChoice:
    """Prefer-first full placement versus one eligible fallback. No third search."""
    from app.scheduler.placement import place_task

    def simulate(mode: str, *, subject: Any, minutes: int, busy_in: list[Any], not_before: datetime | None, comp: Any, general: Any, working: Any):
        usage = dict(project_daily_usage or {})
        return place_task(
            db,
            task=subject,
            owner_id=owner_id,
            settings=settings,
            remaining_minutes=minutes,
            busy=list(busy_in),
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            preferred_windows=preferred_windows,
            now_utc=now_utc,
            preferred_window_id=preferred_window_id if subject is task else None,
            max_blocks=None,
            finalize_status=False,
            project_daily_usage=usage,
            daily_cap=daily_cap,
            prerequisite_not_before=not_before,
            persist_blocks=False,
            time_map_overrides_by_map=time_map_overrides_by_map,
            working_windows=working,
            general_windows=general,
            composition=comp,
            rank_mode=mode,
            ranking_protection=False,
        )

    prefer_result, prefer_busy = simulate(
        RANK_MODE_PREFER,
        subject=task,
        minutes=remaining_minutes,
        busy_in=busy,
        not_before=prerequisite_not_before,
        comp=composition,
        general=general_windows,
        working=working_windows,
    )
    fallback_result, fallback_busy = simulate(
        RANK_MODE_ELIGIBLE,
        subject=task,
        minutes=remaining_minutes,
        busy_in=busy,
        not_before=prerequisite_not_before,
        comp=composition,
        general=general_windows,
        working=working_windows,
    )
    deadline = _deadline(task)
    prefer_done = _completes(prefer_result, deadline)
    fallback_done = _completes(fallback_result, deadline)
    prefer_miss = _misses(prefer_result, deadline)
    fallback_miss = _misses(fallback_result, deadline)

    from zoneinfo import ZoneInfo

    tz = ZoneInfo(settings.timezone)
    future = _future_windows(
        composition=composition,
        tz=tz,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        general_windows=general_windows,
    )
    hard = False
    if not prefer_done and not fallback_done:
        if getattr(composition, "must_blocks_all", False):
            hard = True
        elif future and _windows_blocked(future, busy):
            hard = True
        elif future and deadline is not None and prefer_miss and fallback_miss:
            # Both miss because the deadline clips every eligible window, and
            # busy/pins were not required for that. Still a hard failure when
            # no placement exists at all.
            if prefer_result.blocks_created == 0 and fallback_result.blocks_created == 0:
                hard = True

    if hard:
        return RankingChoice(
            mode=RANK_MODE_PREFER,
            decision=DECISION_HARD,
            hard_constraints_protected=True,
        )

    for peer in higher_ranked:
        peer_deadline = _deadline(peer.task)
        prefer_not_before = peer.prerequisite_not_before
        fallback_not_before = peer.prerequisite_not_before
        if peer.blocked_by_subject:
            base = peer.prerequisite_not_before or horizon_start
            prefer_end = prefer_result.last_block_end
            fallback_end = fallback_result.last_block_end
            if prefer_result.remaining_minutes > 0 or prefer_end is None:
                prefer_not_before = horizon_end
            else:
                prefer_not_before = max(base, prefer_end)
            if fallback_result.remaining_minutes > 0 or fallback_end is None:
                fallback_not_before = horizon_end
            else:
                fallback_not_before = max(base, fallback_end)
        peer_prefer, _busy = simulate(
            RANK_MODE_PREFER,
            subject=peer.task,
            minutes=peer.remaining_minutes,
            busy_in=prefer_busy,
            not_before=prefer_not_before,
            comp=peer.composition,
            general=peer.general_windows if peer.general_windows is not None else general_windows,
            working=peer.working_windows if peer.working_windows is not None else working_windows,
        )
        peer_fallback, _busy = simulate(
            RANK_MODE_ELIGIBLE,
            subject=peer.task,
            minutes=peer.remaining_minutes,
            busy_in=fallback_busy,
            not_before=fallback_not_before,
            comp=peer.composition,
            general=peer.general_windows if peer.general_windows is not None else general_windows,
            working=peer.working_windows if peer.working_windows is not None else working_windows,
        )
        if _completes(peer_fallback, peer_deadline) and not _completes(peer_prefer, peer_deadline):
            return RankingChoice(
                mode=RANK_MODE_ELIGIBLE,
                decision=DECISION_HIGHER_RANKED,
                competing_task_id=str(peer.task.id),
            )

    if prefer_miss and fallback_done and not fallback_miss:
        return RankingChoice(mode=RANK_MODE_ELIGIBLE, decision=DECISION_DEADLINE_FALLBACK)

    if prefer_done and fallback_done:
        return RankingChoice(mode=RANK_MODE_PREFER, decision=DECISION_PREFER)

    exhausted = (
        prefer_result.remaining_minutes > 0
        and fallback_result.remaining_minutes > 0
        and bool(future)
    )
    return RankingChoice(
        mode=RANK_MODE_PREFER,
        decision=DECISION_BOUND_EXHAUSTED if exhausted else DECISION_PREFER,
        bound_exhausted=exhausted,
    )
