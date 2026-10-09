"""Structured scheduling reason codes and deterministic summary text (F3-W1)."""

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
        else:
            lines.append(f"Scheduling note: {code}.")

    return " ".join(lines)
