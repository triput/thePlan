"""Structured scheduling reason codes and deterministic summary text (F3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

# First tranche — extend in later F3 waves.
REASON_EXCLUDED_MANUAL_OR_BUNDLE = "excluded_manual_or_bundle"
REASON_EXCLUDED_DURATION_COVERED_BY_PINS = "excluded_duration_covered_by_pins"
REASON_BLOCKED_PREREQUISITE = "blocked_prerequisite"
REASON_PLACED = "placed"
REASON_UNPLACED_HORIZON_EXHAUSTED = "unplaced_horizon_exhausted"
REASON_UNPLACED_NO_SLOT = "unplaced_no_slot"
REASON_UNPLACED_DEADLINE_LIMIT = "unplaced_deadline_limit"
REASON_BLOCKED_DEPENDENCY_CYCLE = "blocked_dependency_cycle"
REASON_UNPLACED_PROJECT_DAILY_CAP = "unplaced_project_daily_cap"
REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK = "unplaced_insufficient_min_block"
REASON_UNPLACED_NO_TIME_MAP_INTERVAL = "unplaced_no_time_map_interval"
REASON_UNPLACED_RED_EXCLUSION = "unplaced_red_exclusion"
REASON_UNPLACED_BUSY_CONFLICT = "unplaced_busy_conflict"
REASON_UNPLACED_PINNED_CONFLICT = "unplaced_pinned_conflict"
REASON_EXCLUDED_LIFECYCLE_COMPLETED = "excluded_lifecycle_completed"
REASON_EXCLUDED_LIFECYCLE_TRASHED = "excluded_lifecycle_trashed"
REASON_EXCLUDED_LIFECYCLE_ARCHIVED = "excluded_lifecycle_archived"
REASON_EXCLUDED_KEEP_IN_ONE_RESERVED = "excluded_keep_in_one_reserved"
# Secondary outcome fact when a reserved pin is not fully inside Working
# availability (wholly outside or an uncovered partial). Primary placement
# reason stays excluded_keep_in_one_reserved.
REASON_OUTSIDE_WORKING_AVAILABILITY = "outside_working_availability"
REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT = "unplaced_block_bounds_conflict"
REASON_UNPLACED_PIN_RESERVATION_EXCESS = "unplaced_pin_reservation_excess"
REASON_UNPLACED_KEEP_IN_ONE_CONFLICT = "unplaced_keep_in_one_conflict"
# Pre-existing pins and external events sit closer than the buffer. They are
# not moved. Not an unplaced-* code: the task may still place elsewhere.
REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER = "fixed_items_closer_than_buffer"


@dataclass
class ReasonFact:
    code: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {"code": self.code, "params": self.params}


@dataclass
class TaskSchedulingOutcome:
    """In-memory outcome for one task from a single calculation pass."""

    task_id: UUID
    requested_minutes: int
    pinned_minutes: int
    placed_minutes: int
    remaining_minutes: int
    reason_facts: list[ReasonFact] = field(default_factory=list)
    placement_facts: dict[str, Any] | None = None

    @property
    def primary_code(self) -> str:
        if self.reason_facts:
            return self.reason_facts[0].code
        if self.remaining_minutes <= 0 and self.placed_minutes > 0:
            return REASON_PLACED
        if self.remaining_minutes > 0:
            return REASON_UNPLACED_HORIZON_EXHAUSTED
        return REASON_EXCLUDED_DURATION_COVERED_BY_PINS


def _param_str(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    return str(value)


def format_summary_text(facts: list[ReasonFact]) -> str:
    """Deterministic one-line summary from reason facts (no LLM)."""
    if not facts:
        return "No scheduling evaluation recorded."

    lines: list[str] = []
    for fact in facts:
        code = fact.code
        p = fact.params
        if code == REASON_EXCLUDED_MANUAL_OR_BUNDLE:
            style = _param_str(p, "schedule_style") or "manual"
            source = _param_str(p, "style_source")
            if source:
                lines.append(f"Excluded from auto-scheduling ({style} via {source}).")
            else:
                lines.append(f"Excluded from auto-scheduling ({style}).")
        elif code == REASON_EXCLUDED_DURATION_COVERED_BY_PINS:
            pinned = p.get("pinned_minutes")
            requested = p.get("requested_minutes")
            if pinned is not None and requested is not None:
                lines.append(
                    f"Duration fully covered by pinned blocks ({pinned} of {requested} minutes)."
                )
            else:
                lines.append("Duration fully covered by pinned blocks.")
        elif code == REASON_BLOCKED_PREREQUISITE:
            blockers = p.get("blocking_task_ids") or []
            if blockers:
                lines.append(
                    f"Waiting on unfinished prerequisite(s): {', '.join(str(b) for b in blockers)}."
                )
            else:
                lines.append("Waiting on unfinished prerequisite(s).")
        elif code == REASON_PLACED:
            placed = p.get("placed_minutes")
            tier = _param_str(p, "tier")
            src = _param_str(p, "time_window_source")
            parts = []
            if placed is not None:
                parts.append(f"Placed {placed} minute(s)")
            else:
                parts.append("Placed")
            if tier:
                parts.append(f"in {tier} tier")
            if src:
                parts.append(f"(time map from {src})")
            lines.append(" ".join(parts) + ".")
        elif code == REASON_UNPLACED_HORIZON_EXHAUSTED:
            rem = p.get("remaining_minutes")
            if rem is not None:
                lines.append(f"Could not place {rem} remaining minute(s) within the horizon.")
            else:
                lines.append("Could not place remaining work within the horizon.")
        elif code == REASON_UNPLACED_NO_SLOT:
            rem = p.get("remaining_minutes")
            if rem is not None:
                lines.append(f"No suitable slot found for {rem} remaining minute(s).")
            else:
                lines.append("No suitable slot found for remaining work.")
        elif code == REASON_UNPLACED_DEADLINE_LIMIT:
            rem = p.get("remaining_minutes")
            deadline = _param_str(p, "deadline_at")
            if rem is not None and deadline:
                lines.append(
                    f"Could not place {rem} remaining minute(s) before the deadline ({deadline})."
                )
            elif rem is not None:
                lines.append(
                    f"Could not place {rem} remaining minute(s) before the deadline."
                )
            else:
                lines.append("Remaining work does not fit before the deadline.")
        elif code == REASON_BLOCKED_DEPENDENCY_CYCLE:
            members = p.get("cycle_task_ids") or []
            if members:
                lines.append(
                    "Blocked by a dependency cycle involving: "
                    f"{', '.join(str(m) for m in members)}."
                )
            else:
                lines.append("Blocked by a dependency cycle among prerequisites.")
        elif code == REASON_UNPLACED_PROJECT_DAILY_CAP:
            cap = p.get("daily_cap_minutes")
            day = _param_str(p, "local_date")
            if cap is not None and day:
                lines.append(
                    f"Project daily auto-schedule cap ({cap} min) reached for {day}."
                )
            elif cap is not None:
                lines.append(f"Project daily auto-schedule cap ({cap} min) reached.")
            else:
                lines.append("Project daily auto-schedule cap reached.")
        elif code == REASON_UNPLACED_INSUFFICIENT_MIN_BLOCK:
            mbl = p.get("min_block_minutes")
            rem = p.get("remaining_minutes")
            if mbl is not None and rem is not None:
                lines.append(
                    f"No contiguous window of at least {mbl} minutes for {rem} remaining minute(s)."
                )
            elif mbl is not None:
                lines.append(f"No contiguous window of at least {mbl} minutes.")
            else:
                lines.append("No contiguous window large enough for the minimum block size.")
        elif code == REASON_UNPLACED_NO_TIME_MAP_INTERVAL:
            lines.append("No allowed Time Map interval in the horizon for this task.")
        elif code == REASON_UNPLACED_RED_EXCLUSION:
            lines.append("Time Map red bands exclude the remaining work in this horizon.")
        elif code == REASON_UNPLACED_BUSY_CONFLICT:
            lines.append("External calendar busy time blocks placement in available windows.")
        elif code == REASON_UNPLACED_PINNED_CONFLICT:
            lines.append("Pinned blocks conflict with the remaining work in available windows.")
        elif code == REASON_EXCLUDED_KEEP_IN_ONE_RESERVED:
            reserved = p.get("pinned_minutes")
            remaining = p.get("remaining_minutes", p.get("requested_minutes"))
            if reserved is not None and remaining is not None:
                lines.append(
                    "Remaining work is already reserved in one pinned block "
                    f"({reserved} of {remaining} minutes). Other constraints are separate."
                )
            else:
                lines.append(
                    "Remaining work is already reserved in one pinned block. "
                    "Other constraints are separate."
                )
        elif code == REASON_OUTSIDE_WORKING_AVAILABILITY:
            lines.append(
                "Pinned reservation is outside Working availability. "
                "The pin was preserved and no automatic work was added."
            )
        elif code == REASON_UNPLACED_BLOCK_BOUNDS_CONFLICT:
            minimum = p.get("min_block_minutes")
            maximum = p.get("max_block_minutes")
            if minimum is not None and maximum is not None:
                lines.append(
                    f"Effective minimum block ({minimum} min) exceeds effective maximum "
                    f"({maximum} min). Correct the bounds before scheduling."
                )
            else:
                lines.append(
                    "Effective minimum and maximum block bounds conflict. "
                    "Correct the bounds before scheduling."
                )
        elif code == REASON_UNPLACED_PIN_RESERVATION_EXCESS:
            reserved = p.get("reserved_minutes", p.get("pinned_minutes"))
            remaining = p.get("remaining_estimate_minutes", p.get("remaining_minutes"))
            if reserved is not None and remaining is not None:
                lines.append(
                    f"Pinned reservation ({reserved} minutes) exceeds remaining effort "
                    f"({remaining} minutes). The pin was not shortened and remaining was not clamped."
                )
            else:
                lines.append(
                    "Pinned reservation exceeds remaining effort. "
                    "The pin was not shortened and remaining was not clamped."
                )
        elif code == REASON_UNPLACED_KEEP_IN_ONE_CONFLICT:
            arrangement = p.get("arrangement")
            remaining = p.get("remaining_minutes")
            reserved = p.get("reserved_minutes")
            if arrangement == "shorter" and remaining is not None and reserved is not None:
                lines.append(
                    f"This task needs one {remaining}-minute block, but its pinned block "
                    f"reserves {reserved} minutes."
                )
            elif arrangement == "multiple":
                lines.append(
                    "Pinned reservations are separate blocks and cannot satisfy keep-in-one. "
                    "No automatic work was added."
                )
            elif arrangement == "exceeds_max":
                lines.append(
                    "Keep-in-one needs one block for the remaining effort, which exceeds "
                    "the effective maximum. No automatic work was added."
                )
            else:
                lines.append(
                    "Keep-in-one conflicts with the pinned arrangement. No automatic work was added."
                )
        elif code == REASON_FIXED_ITEMS_CLOSER_THAN_BUFFER:
            buffer = p.get("buffer_minutes")
            gap = p.get("gap_minutes")
            if buffer is not None and gap is not None:
                lines.append(
                    f"Pinned blocks and external events are {gap} minute(s) apart, "
                    f"closer than the {buffer}-minute buffer. They were not moved."
                )
            elif buffer is not None:
                lines.append(
                    "Pinned blocks and external events are closer than the "
                    f"{buffer}-minute buffer. They were not moved."
                )
            else:
                lines.append(
                    "Pinned blocks and external events are closer than the required buffer. "
                    "They were not moved."
                )
        elif code == REASON_EXCLUDED_LIFECYCLE_COMPLETED:
            lines.append("Excluded from auto-scheduling (task completed).")
        elif code == REASON_EXCLUDED_LIFECYCLE_TRASHED:
            lines.append("Excluded from auto-scheduling (task in trash).")
        elif code == REASON_EXCLUDED_LIFECYCLE_ARCHIVED:
            scope = _param_str(p, "archived_scope") or "container"
            lines.append(f"Excluded from auto-scheduling ({scope} archived).")
        else:
            lines.append(f"Scheduling note: {code}.")

    return " ".join(lines)
